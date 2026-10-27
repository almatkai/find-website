//! QA only: never included in a development or release archive.
use find_website_v2::{paths, query};
use serde_json::{json, Value};
use std::io::{self, BufRead};
fn main() {
    for line in io::stdin().lock().lines() {
        let v: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let result = match v["op"].as_str().unwrap() {
            "query" => {
                let p = std::path::Path::new(v["db"].as_str().unwrap())
                    .canonicalize()
                    .unwrap();
                assert!(p.starts_with(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(".qa")));
                let c = rusqlite::Connection::open_with_flags(
                    p,
                    rusqlite::OpenFlags::SQLITE_OPEN_READ_ONLY,
                )
                .unwrap();
                match query::query(
                    &c,
                    v["browser"].as_str().unwrap(),
                    v["text"].as_str().unwrap(),
                    std::sync::Arc::default(),
                    std::time::Instant::now() + std::time::Duration::from_secs(3),
                ) {
                    Ok(rows) => json!({"rows":rows}),
                    Err(_) => json!({"error":true}),
                }
            }
            "paths" => {
                let r = paths::Roots {
                    home: "/owned/home".into(),
                    local: if v["emptyEnv"] == true {
                        ""
                    } else {
                        "/owned/local"
                    }
                    .into(),
                    roaming: if v["emptyEnv"] == true {
                        ""
                    } else {
                        "/owned/roaming"
                    }
                    .into(),
                };
                let browser = v["browser"].as_str().unwrap();
                let win = v["platform"] == "win32";
                let profile = v["profile"].as_str().unwrap_or("Profile 2");
                let src = if matches!(browser, "firefox" | "zen") {
                    paths::source_from_profile(browser, win, &r, "Profiles/default")
                        .display()
                        .to_string()
                } else {
                    paths::source(browser, profile, win, &r)
                        .unwrap()
                        .display()
                        .to_string()
                };
                json!({"path":src,"installation":paths::installation(browser,profile,win,&r).map(|p|p.display().to_string())})
            }
            "ini" => match paths::ini_profile(v["text"].as_str().unwrap()) {
                Ok(p) => json!({"profile":p}),
                Err(_) => json!({"error":true}),
            },
            _ => panic!("unknown QA op"),
        };
        println!("{result}");
    }
}
