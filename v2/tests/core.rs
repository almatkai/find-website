use find_website_v2::{paths, query, snapshot};
use rusqlite::Connection;
use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
fn chrome() -> Connection {
    let c = Connection::open_in_memory().unwrap();
    c.execute_batch("create table urls(id integer,title text,url text,last_visit_time integer,visit_count integer,typed_count integer,hidden integer);insert into urls values(1,'Café Foo','https://example.invalid/bar',13300000000000000,7,0,0),(2,NULL,'https://empty.invalid/',13300000000000000,1,0,0),(3,'O''Reilly','https://quote.invalid/',13300000000000000,9,0,0),(4,'Foo bar','https://other.invalid/',13300000000000000,2,0,0);").unwrap();
    c
}
#[test]
fn wildcard_words_and_bound_quotes() {
    let c = chrome();
    for (text, count) in [
        ("foo bar", 2),
        ("_", 6),
        ("%", 6),
        ("  ", 6),
        ("O'Reilly", 2),
        ("' OR 1=1 --", 0),
        ("café", 2),
        ("CAFÉ", 0),
    ] {
        let r = query::query(
            &c,
            "chrome",
            text,
            Arc::default(),
            Instant::now() + Duration::from_secs(1),
        )
        .unwrap();
        assert_eq!(r.len(), count, "{text}");
    }
    assert_eq!(
        c.query_row("select count(*) from urls", [], |r| r.get::<_, i64>(0))
            .unwrap(),
        4
    );
}
#[test]
fn cancel_and_deadline_interrupt_native_sqlite() {
    let c = chrome();
    let stop = Arc::new(AtomicBool::new(true));
    c.execute_batch("insert into urls select id+100,title,url,last_visit_time,visit_count,typed_count,hidden from urls;").unwrap();
    for _ in 0..12 {
        c.execute_batch("insert into urls select id+100,title,url,last_visit_time,visit_count,typed_count,hidden from urls;").unwrap();
    }
    assert!(query::query(
        &c,
        "chrome",
        "%",
        stop,
        Instant::now() + Duration::from_secs(1)
    )
    .is_err());
    assert!(query::query(&c, "chrome", "%", Arc::default(), Instant::now()).is_err());
}
#[test]
fn snapshot_cleanup_and_source_byte_identity() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(".qa/tmp");
    std::fs::create_dir_all(&root).unwrap();
    let t = tempfile::tempdir_in(root).unwrap();
    let source = t.path().join("History");
    let c = Connection::open(&source).unwrap();
    c.execute_batch("create table urls(id,title,url,last_visit_time,visit_count,typed_count,hidden);insert into urls values(1,'owned','https://owned.invalid',13300000000000000,1,0,0);").unwrap();
    drop(c);
    let before = std::fs::read(&source).unwrap();
    let tmp = t.path().join("private");
    let r = snapshot::search(&source, &tmp, "chrome", "owned", Arc::default()).unwrap();
    assert_eq!(r.len(), 2);
    assert_eq!(before, std::fs::read(source).unwrap());
    assert_eq!(std::fs::read_dir(tmp).unwrap().count(), 0);
}
#[test]
fn corrupt_journals_and_canceled_acquisition_fail_closed() {
    for b in [vec![0u8; 1], vec![0u8; 32], vec![0u8; 100]] {
        assert!(snapshot::wal_prefix(&b).is_err());
    }
    let stop = Arc::new(AtomicBool::default());
    stop.store(true, Ordering::Release);
    assert!(snapshot::search(
        std::path::Path::new("/owned/not-read"),
        std::path::Path::new("/owned/not-written"),
        "chrome",
        "",
        stop
    )
    .is_err());
}
#[test]
fn windows_missing_browsers_and_profile_selection() {
    let r = paths::Roots {
        home: "/owned/home".into(),
        local: "/owned/local".into(),
        roaming: "/owned/roaming".into(),
    };
    for b in ["safari", "orion", "zen"] {
        assert!(paths::installation(b, "Default", true, &r).is_none());
    }
    assert_eq!(
        paths::ini_profile("[General]\nStartWithLastProfile=1\n[Profile0]\nPath=x").unwrap(),
        "undefined"
    );
    assert_eq!(
        paths::ini_profile(
            "[Profile0]\nPath=x\n[InstallB]\nDefault=Profiles/b\n[InstallA]\nDefault=Profiles/a"
        )
        .unwrap(),
        "Profiles/b"
    );
    assert_eq!(
        paths::ini_profile("[Profile0]\nPath=Profiles/a\\#x ;comment").unwrap(),
        "Profiles/a#x"
    );
}

#[test]
fn real_owned_ini_files_follow_original_mac_and_windows_base_rules() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(".qa/tmp");
    std::fs::create_dir_all(&root).unwrap();
    let private = tempfile::tempdir_in(root).unwrap();
    let r = paths::Roots {
        home: private.path().join("home"),
        local: private.path().join("local"),
        roaming: private.path().join("roaming"),
    };
    for (browser, windows, base) in [
        (
            "firefox",
            false,
            r.home.join("Library/Application Support/Firefox"),
        ),
        ("firefox", true, r.roaming.join("Mozilla/Firefox")),
        ("zen", false, r.home.join("Library/Application Support/zen")),
        ("zen", true, r.home.join("Library/Application Support/zen")),
    ] {
        std::fs::create_dir_all(&base).unwrap();
        std::fs::write(base.join("profiles.ini"),"[General]\nStartWithLastProfile=1\n[Profile0]\nPath=Profiles/other\n[InstallFIRST]\nDefault=Profiles/owned\n[InstallSECOND]\nDefault=Profiles/ignored").unwrap();
        assert_eq!(
            paths::source(browser, "ignored chrome profile", windows, &r).unwrap(),
            base.join("Profiles/owned/places.sqlite")
        );
        std::fs::write(
            base.join("profiles.ini"),
            "[Profile0]\nIsRelative=0\nPath=/absolute/path",
        )
        .unwrap();
        assert_eq!(
            paths::source(browser, "ignored", windows, &r).unwrap(),
            base.join("absolute/path/places.sqlite")
        );
        std::fs::write(base.join("profiles.ini"), vec![b'x'; 65537]).unwrap();
        assert!(paths::source(browser, "ignored", windows, &r).is_err());
    }
}

#[test]
fn explicit_byte_bounds_fail_instead_of_truncating_history_rows() {
    let c = chrome();
    c.execute("update urls set title=?1", ["x".repeat(600 * 1024)])
        .unwrap();
    assert!(query::query(
        &c,
        "chrome",
        "",
        Arc::default(),
        Instant::now() + Duration::from_secs(1)
    )
    .is_err());
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(".qa/tmp");
    std::fs::create_dir_all(&root).unwrap();
    let t = tempfile::tempdir_in(root).unwrap();
    let src = t.path().join("History");
    let f = std::fs::File::create(&src).unwrap();
    f.set_len(256 * 1024 * 1024 + 1).unwrap();
    drop(f);
    let temp = t.path().join("private");
    let e = snapshot::search(&src, &temp, "chrome", "", Arc::default()).unwrap_err();
    assert!(e.contains("limit"));
    assert_eq!(std::fs::metadata(src).unwrap().len(), 256 * 1024 * 1024 + 1);
    assert_eq!(std::fs::read_dir(temp).unwrap().count(), 0);
}
