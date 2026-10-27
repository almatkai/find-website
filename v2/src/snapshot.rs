//! Source files are only opened for reading. SQLite opens only the private copy.
use crate::paths::sidecar;
use rusqlite::{Connection, OpenFlags};
use std::{
    fs::{File, OpenOptions},
    io::{Read, Seek, SeekFrom, Write},
    path::Path,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant},
};
const MAX_BYTES: u64 = 256 * 1024 * 1024;
const BUSY: &str = "Browser history is busy. Wait a moment, then retry the search.";
fn check(stop: &AtomicBool, deadline: Instant) -> Result<(), String> {
    if stop.load(Ordering::Acquire) || Instant::now() >= deadline {
        Err("History reading was interrupted. Try again.".into())
    } else {
        Ok(())
    }
}
fn file(p: &Path) -> Result<File, String> {
    let mut options = OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NONBLOCK);
    }
    let f = options
        .open(p)
        .map_err(|_| "Browser history could not be read.")?;
    if !f.metadata().map_err(|_| BUSY)?.is_file() {
        return Err("History is not a regular file.".into());
    }
    Ok(f)
}
#[cfg(unix)]
fn lock(f: &File, offset: u64, len: u64) -> Result<(), String> {
    use std::os::fd::AsRawFd;
    let mut l: libc::flock = unsafe { std::mem::zeroed() };
    l.l_type = libc::F_RDLCK as _;
    l.l_whence = libc::SEEK_SET as _;
    l.l_start = offset as _;
    l.l_len = len as _;
    // Nonblocking SQLite-compatible POSIX byte-range locks, released on close.
    if unsafe { libc::fcntl(f.as_raw_fd(), libc::F_SETLK, &l) } < 0 {
        Err(BUSY.into())
    } else {
        Ok(())
    }
}
#[cfg(windows)]
fn lock(f: &File, offset: u64, len: u64) -> Result<(), String> {
    use std::os::windows::io::AsRawHandle;
    use windows_sys::Win32::{
        Storage::FileSystem::{LockFileEx, LOCKFILE_FAIL_IMMEDIATELY},
        System::IO::OVERLAPPED,
    };
    let mut o: OVERLAPPED = unsafe { std::mem::zeroed() };
    o.Anonymous.Anonymous.Offset = offset as u32;
    o.Anonymous.Anonymous.OffsetHigh = (offset >> 32) as u32;
    if unsafe {
        LockFileEx(
            f.as_raw_handle() as _,
            LOCKFILE_FAIL_IMMEDIATELY,
            0,
            len as u32,
            (len >> 32) as u32,
            &mut o,
        )
    } == 0
    {
        Err(BUSY.into())
    } else {
        Ok(())
    }
}
fn copy(
    src: &mut File,
    dst: &Path,
    budget: &mut u64,
    stop: &AtomicBool,
    deadline: Instant,
) -> Result<(), String> {
    src.seek(SeekFrom::Start(0)).map_err(|_| BUSY)?;
    let len = src.metadata().map_err(|_| BUSY)?.len();
    if len > *budget {
        return Err("Browser history exceeds the safe reading limit.".into());
    }
    *budget -= len;
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut out = options
        .open(dst)
        .map_err(|_| "A private history snapshot could not be created.")?;
    let mut buf = [0u8; 65536];
    let mut left = len;
    while left > 0 {
        check(stop, deadline)?;
        let n = src
            .read(&mut buf[..left.min(65536) as usize])
            .map_err(|_| BUSY)?;
        if n == 0 {
            return Err(BUSY.into());
        }
        out.write_all(&buf[..n])
            .map_err(|_| "The private history snapshot could not be written.")?;
        left -= n as u64;
    }
    if src.metadata().map_err(|_| BUSY)?.len() != len {
        return Err(BUSY.into());
    }
    Ok(())
}
fn be(b: &[u8]) -> u32 {
    u32::from_be_bytes(b[..4].try_into().unwrap())
}
fn checksum(b: &[u8], little: bool, mut s: (u32, u32)) -> (u32, u32) {
    for c in b.chunks_exact(8) {
        let word = |x: &[u8]| {
            if little {
                u32::from_le_bytes(x.try_into().unwrap())
            } else {
                be(x)
            }
        };
        s.0 = s.0.wrapping_add(word(&c[..4])).wrapping_add(s.1);
        s.1 = s.1.wrapping_add(word(&c[4..])).wrapping_add(s.0);
    }
    s
}
/// Return the coherent committed prefix. Old salt generations and uncommitted
/// frames are excluded; malformed current-generation frames fail closed.
pub fn wal_prefix(b: &[u8]) -> Result<usize, String> {
    wal_prefix_checked(b, || Ok(()))
}
fn wal_prefix_checked(
    b: &[u8],
    mut checkpoint: impl FnMut() -> Result<(), String>,
) -> Result<usize, String> {
    let error = "Browser history contains an incomplete or invalid journal.";
    if b.is_empty() {
        return Ok(0);
    }
    if b.len() < 32 {
        return Err(error.into());
    }
    let magic = be(b);
    if ![0x377f0682, 0x377f0683].contains(&magic) || be(&b[4..]) != 3007000 {
        return Err(error.into());
    }
    let page = be(&b[8..]) as usize;
    if !(512..=65536).contains(&page) || !page.is_power_of_two() {
        return Err(error.into());
    }
    let little = magic == 0x377f0682;
    let mut s = checksum(&b[..24], little, (0, 0));
    if s != (be(&b[24..]), be(&b[28..])) {
        return Err(error.into());
    }
    let mut end = 32;
    let mut committed = 0;
    while end + 24 + page <= b.len() {
        checkpoint()?;
        let f = &b[end..end + 24 + page];
        if f[8..16] != b[16..24] {
            break;
        }
        if be(f) == 0 {
            return Err(error.into());
        }
        s = checksum(&f[..8], little, s);
        s = checksum(&f[24..], little, s);
        if s != (be(&f[16..]), be(&f[20..])) {
            return Err(error.into());
        }
        end += 24 + page;
        if be(&f[4..]) != 0 {
            committed = end;
        }
    }
    if end < b.len() && b.len() - end < 24 + page {
        return Err(error.into());
    }
    Ok(committed)
}
pub fn search(
    src: &Path,
    temp: &Path,
    browser: &str,
    text: &str,
    stop: Arc<AtomicBool>,
) -> Result<Vec<serde_json::Value>, String> {
    let deadline = Instant::now() + Duration::from_secs(3);
    check(&stop, deadline)?;
    std::fs::create_dir_all(temp).map_err(|_| "Private temporary storage is unavailable.")?;
    let private = tempfile::Builder::new()
        .prefix("find-website-")
        .tempdir_in(temp)
        .map_err(|_| "Private temporary storage is unavailable.")?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(private.path(), std::fs::Permissions::from_mode(0o700))
            .map_err(|_| "Private temporary storage is unavailable.")?;
    }
    let dst = private.path().join("history.sqlite");
    let mut main = file(src)?;
    // Hold PENDING + SHARED against rollback writes and WAL recovery/mode changes.
    lock(&main, 0x40000000, 1)?;
    lock(&main, 0x40000002, 510)?;
    let wp = sidecar(src, "-wal");
    let sp = sidecar(src, "-shm");
    let jp = sidecar(src, "-journal");
    let shm = if sp.exists() {
        let f = file(&sp)?;
        // SQLite UNIX_SHM_BASE/WIN_SHM_BASE=120; all 8 WAL locks + the dead-man-switch, shared.
        lock(&f, 120, 9)?;
        Some(f)
    } else {
        None
    };
    let has_wal = wp.exists();
    if has_wal && shm.is_none() && std::fs::metadata(&wp).map_err(|_| BUSY)?.len() > 0 {
        return Err(BUSY.into());
    }
    if jp.exists() && std::fs::metadata(&jp).map_err(|_| BUSY)?.len() > 0 {
        return Err(
            "Browser history has an unfinished transaction. Close the browser, then retry.".into(),
        );
    }
    let mut wal = if has_wal { Some(file(&wp)?) } else { None };
    let mut budget = MAX_BYTES;
    copy(&mut main, &dst, &mut budget, &stop, deadline)?;
    if let Some(ref mut f) = wal {
        let private_wal = sidecar(&dst, "-wal");
        copy(f, &private_wal, &mut budget, &stop, deadline)?;
        let b = std::fs::read(&private_wal).map_err(|_| BUSY)?;
        check(&stop, deadline)?;
        let prefix = wal_prefix_checked(&b, || check(&stop, deadline))?;
        if prefix == 0 {
            std::fs::remove_file(private_wal).map_err(|_| BUSY)?;
        } else {
            OpenOptions::new()
                .write(true)
                .open(private_wal)
                .and_then(|f| f.set_len(prefix as u64))
                .map_err(|_| BUSY)?;
        }
    }
    // Detect a WAL writer starting while no SHM existed. Never create source SHM.
    if has_wal != wp.exists()
        || shm.is_some() != sp.exists()
        || (jp.exists() && std::fs::metadata(&jp).map_err(|_| BUSY)?.len() > 0)
    {
        return Err(BUSY.into());
    }
    check(&stop, deadline)?;
    // Source locks stay alive until the private SQLite connection has closed.
    let conn = Connection::open_with_flags(
        &dst,
        OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .map_err(|_| "The history snapshot could not be opened.")?;
    conn.busy_timeout(Duration::from_millis(100))
        .map_err(|_| BUSY)?;
    let flag = stop.clone();
    let mut ticks = 0u64;
    conn.progress_handler(
        1000,
        Some(move || {
            ticks += 1;
            flag.load(Ordering::Acquire) || Instant::now() >= deadline || ticks > 100_000
        }),
    );
    let valid: String = conn
        .query_row("pragma quick_check(1)", [], |r| r.get(0))
        .map_err(|_| "The history snapshot is damaged or could not be checked.")?;
    if valid != "ok" {
        return Err("The history snapshot is damaged.".into());
    }
    crate::query::query(&conn, browser, text, stop, deadline)
}
