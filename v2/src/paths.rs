use std::path::{Path, PathBuf};
pub const BROWSERS: &[&str] = &[
    "chrome", "orion", "arc", "safari", "firefox", "zen", "brave", "vivaldi", "opera", "edge",
];
#[derive(Clone)]
pub struct Roots {
    pub home: PathBuf,
    pub local: PathBuf,
    pub roaming: PathBuf,
}
impl Roots {
    pub fn system() -> Result<Self, String> {
        let home = std::env::var_os(if cfg!(windows) { "USERPROFILE" } else { "HOME" })
            .map(PathBuf::from)
            .filter(|p| p.is_absolute())
            .ok_or("Your home folder is unavailable.")?;
        let local = std::env::var_os("LOCALAPPDATA")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .unwrap_or_default();
        let roaming = std::env::var_os("APPDATA")
            .filter(|v| !v.is_empty())
            .map(PathBuf::from)
            .unwrap_or_default();
        Ok(Self {
            home,
            local,
            roaming,
        })
    }
}
fn env_base(value: &Path, home: &Path, part: &str) -> PathBuf {
    if value.as_os_str().is_empty() {
        home.join("AppData").join(part)
    } else {
        value.to_path_buf()
    }
}
fn normalize(p: PathBuf) -> PathBuf {
    let mut out = PathBuf::new();
    for c in p.components() {
        match c {
            std::path::Component::ParentDir => {
                out.pop();
            }
            std::path::Component::CurDir => {}
            c => out.push(c.as_os_str()),
        }
    }
    out
}
pub fn installation(browser: &str, profile: &str, windows: bool, r: &Roots) -> Option<PathBuf> {
    if windows {
        let (base, suffix) = match browser {
            "orion" | "safari" | "zen" => return None,
            "firefox" => (&r.roaming, "Mozilla/Firefox/profiles.ini".to_string()),
            "chrome" => (
                &r.local,
                format!("Google/Chrome/User Data/{profile}/History"),
            ),
            "arc" => (&r.local, "Arc/User Data/Default/History".into()),
            "edge" => (&r.local, "Microsoft/Edge/User Data/Default/History".into()),
            "brave" => (
                &r.local,
                "BraveSoftware/Brave-Browser/User Data/Default/History".into(),
            ),
            "vivaldi" => (&r.local, "Vivaldi/User Data/Default/History".into()),
            "opera" => (&r.roaming, "Opera Software/Opera Stable/History".into()),
            _ => return None,
        };
        // find.tsx interpolates env or an empty string; no factory fallback here.
        return Some(PathBuf::from(format!("{}/{suffix}", base.display())));
    }
    let name = match browser {
        "chrome" => "Google Chrome",
        "orion" => "Orion",
        "arc" => "Arc",
        "safari" => "Safari",
        "firefox" => "Firefox",
        "zen" => "Zen Browser",
        "brave" => "Brave Browser",
        "vivaldi" => "Vivaldi",
        "opera" => "Opera",
        "edge" => "Microsoft Edge",
        _ => return None,
    };
    Some(PathBuf::from(format!("/Applications/{name}.app")))
}
fn source_base(browser: &str, profile: &str, win: bool, r: &Roots) -> Result<PathBuf, String> {
    let (mac, windows) = match browser {
        "chrome" => (
            format!("Google/Chrome/{profile}/History"),
            format!("Google/Chrome/User Data/{profile}/History"),
        ),
        "arc" => (
            "Arc/User Data/Default/History".into(),
            "Arc/User Data/Default/History".into(),
        ),
        "orion" => (
            "Orion/Defaults/history".into(),
            "Orion/Defaults/history".into(),
        ),
        "brave" => (
            "BraveSoftware/Brave-Browser/Default/History".into(),
            "BraveSoftware/Brave-Browser/User Data/Default/History".into(),
        ),
        "vivaldi" => (
            "Vivaldi/Default/History".into(),
            "Vivaldi/User Data/Default/History".into(),
        ),
        "opera" => (
            "com.operasoftware.Opera/Default/History".into(),
            "Opera Software/Opera Stable/History".into(),
        ),
        "edge" => (
            "Microsoft Edge/Default/History".into(),
            "Microsoft/Edge/User Data/Default/History".into(),
        ),
        "safari" => return Ok(r.home.join("Library/Safari/History.db")),
        _ => return Err("Choose a supported browser in preferences.".into()),
    };
    Ok(normalize(if win {
        let base = if browser == "opera" {
            env_base(&r.roaming, &r.home, "Roaming")
        } else {
            env_base(&r.local, &r.home, "Local")
        };
        if browser == "chrome" {
            base.join("Google/Chrome/User Data")
                .join(profile)
                .join("History")
        } else {
            base.join(windows)
        }
    } else {
        r.home.join("Library/Application Support").join(mac)
    }))
}
pub fn source(browser: &str, profile: &str, windows: bool, r: &Roots) -> Result<PathBuf, String> {
    if !matches!(browser, "firefox" | "zen") {
        return source_base(browser, profile, windows, r);
    }
    let base = if browser == "zen" {
        r.home.join("Library/Application Support/zen")
    } else if windows {
        env_base(&r.roaming, &r.home, "Roaming").join("Mozilla/Firefox")
    } else {
        r.home.join("Library/Application Support/Firefox")
    };
    let mut options = std::fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.custom_flags(libc::O_NONBLOCK);
    }
    let f = options
        .open(base.join("profiles.ini"))
        .map_err(|_| "Browser profiles could not be read.")?;
    if !f
        .metadata()
        .map_err(|_| "Browser profiles could not be read.")?
        .is_file()
    {
        return Err("Browser profiles are not a regular file.".into());
    }
    use std::io::Read;
    let mut b = Vec::new();
    f.take(65537)
        .read_to_end(&mut b)
        .map_err(|_| "Browser profiles could not be read.")?;
    if b.len() > 65536 {
        return Err("Browser profiles file is too large.".into());
    }
    let text = std::str::from_utf8(&b).map_err(|_| "Browser profiles could not be read.")?;
    let profile = ini_profile(text)?;
    Ok(source_from_profile(browser, windows, r, &profile))
}
pub fn source_from_profile(browser: &str, windows: bool, r: &Roots, profile: &str) -> PathBuf {
    let base = if browser == "zen" {
        r.home.join("Library/Application Support/zen")
    } else if windows {
        env_base(&r.roaming, &r.home, "Roaming").join("Mozilla/Firefox")
    } else {
        r.home.join("Library/Application Support/Firefox")
    };
    // V1 concatenates base + '/' + Path, ignoring IsRelative even for absolute Path.
    normalize(PathBuf::from(format!(
        "{}/{profile}/places.sqlite",
        base.display()
    )))
}
/// Profile selection uses the locked ini@5 decoder's scalar, array, escaping,
/// dotted-section and JavaScript Object.keys ordering semantics. See notices.
pub fn ini_profile(text: &str) -> Result<String, String> {
    use serde_json::{Map, Value};
    let error = "Browser profiles could not be read.";
    let mut top: Vec<(String, Value)> = Vec::new();
    let mut current: Option<String> = None;
    let mut discarded = false;
    for raw in text.split(['\r', '\n']) {
        if raw.trim().is_empty() || raw.trim_start().starts_with([';', '#']) {
            continue;
        }
        if let Some(rest) = raw.strip_prefix('[') {
            if let Some((name, tail)) = rest.split_once(']') {
                if tail.trim().is_empty() {
                    let name = js_string(&unsafe_ini(name));
                    discarded = name == "__proto__";
                    if !discarded {
                        let v = top_value(&mut top, &name);
                        if !js_truthy(v) {
                            *v = Value::Object(Map::new());
                        }
                    }
                    current = Some(name);
                    continue;
                }
            }
        }
        let (key, value) = match raw.split_once('=') {
            Some((k, v)) if !k.is_empty() => (k, Some(v)),
            None => (raw, None),
            _ => continue,
        };
        if discarded {
            continue;
        }
        let key = js_string(&unsafe_ini(key));
        let array = key.len() > 2 && key.ends_with("[]");
        let key = if array { &key[..key.len() - 2] } else { &key };
        if key == "__proto__" {
            continue;
        }
        let mut value = value.map(unsafe_ini).unwrap_or(Value::Bool(true));
        if let Some(v) = value.as_str() {
            if ["true", "false", "null"].contains(&v) {
                value = serde_json::from_str(v).unwrap();
            }
        }
        let existed = if let Some(section) = &current {
            top_value(&mut top, section)
                .as_object()
                .ok_or(error)?
                .contains_key(key)
        } else {
            top.iter().any(|x| x.0 == key)
        };
        let dest = if let Some(section) = &current {
            top_value(&mut top, section)
                .as_object_mut()
                .ok_or(error)?
                .entry(key.to_string())
                .or_insert(Value::Null)
        } else {
            top_value(&mut top, key)
        };
        if array && !dest.is_array() {
            *dest = if !existed {
                Value::Array(Vec::new())
            } else {
                Value::Array(vec![dest.clone()])
            };
        }
        if let Value::Array(a) = dest {
            a.push(value);
        } else {
            *dest = value;
        }
    }
    let mut remove = Vec::new();
    for key in top.iter().map(|x| x.0.clone()).collect::<Vec<_>>() {
        let value = top.iter().find(|x| x.0 == key).unwrap().1.clone();
        if !value.is_object() {
            continue;
        }
        let mut parts = split_sections(&key);
        let leaf = parts.pop().unwrap();
        let clean = leaf.replace("\\.", ".");
        if parts.is_empty() && clean == leaf {
            continue;
        }
        let parts = parts
            .into_iter()
            .filter(|p| p != "__proto__")
            .collect::<Vec<_>>();
        if parts.is_empty() {
            *top_value(&mut top, &clean) = value;
        } else {
            let mut node = top_value(&mut top, &parts[0]);
            for part in &parts[1..] {
                if !node.is_object() {
                    *node = Value::Object(Map::new());
                }
                node = node
                    .as_object_mut()
                    .unwrap()
                    .entry(part.clone())
                    .or_insert_with(|| Value::Object(Map::new()));
            }
            if !node.is_object() {
                *node = Value::Object(Map::new());
            }
            node.as_object_mut().unwrap().insert(clean, value);
        }
        remove.push(key);
    }
    top.retain(|x| !remove.contains(&x.0));
    top.sort_by_key(|(k, _)| {
        k.parse::<u32>()
            .ok()
            .filter(|n| n.to_string() == *k && *n != u32::MAX)
            .map(|n| (0, n))
            .unwrap_or((1, 0))
    });
    if top.iter().any(|(_, v)| v.is_null()) {
        return Err(error.into());
    }
    let selected = top
        .iter()
        .find(|x| x.0.starts_with("Install"))
        .or_else(|| top.first())
        .ok_or("No browser profile was found.")?;
    let key = if selected.0.starts_with("Install") {
        "Default"
    } else {
        "Path"
    };
    Ok(selected
        .1
        .get(key)
        .map(js_string)
        .unwrap_or_else(|| "undefined".into()))
}
fn top_value<'a>(
    top: &'a mut Vec<(String, serde_json::Value)>,
    key: &str,
) -> &'a mut serde_json::Value {
    let i = top.iter().position(|x| x.0 == key).unwrap_or_else(|| {
        top.push((key.to_string(), serde_json::Value::Null));
        top.len() - 1
    });
    &mut top[i].1
}
fn js_truthy(v: &serde_json::Value) -> bool {
    match v {
        serde_json::Value::Null => false,
        serde_json::Value::Bool(b) => *b,
        serde_json::Value::String(s) => !s.is_empty(),
        serde_json::Value::Number(n) => n.as_f64() != Some(0.0),
        _ => true,
    }
}
fn js_string(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::String(s) => s.clone(),
        serde_json::Value::Object(_) => "[object Object]".into(),
        serde_json::Value::Array(a) => a
            .iter()
            .map(|v| {
                if v.is_null() {
                    String::new()
                } else {
                    js_string(v)
                }
            })
            .collect::<Vec<_>>()
            .join(","),
        serde_json::Value::Number(n) => ryu_js::Buffer::new()
            .format(n.as_f64().unwrap())
            .to_string(),
        _ => v.to_string(),
    }
}
fn unsafe_ini(s: &str) -> serde_json::Value {
    let s = s.trim();
    if (s.starts_with('"') && s.ends_with('"')) || (s.starts_with('\'') && s.ends_with('\'')) {
        let s = if s.starts_with('\'') && s.len() >= 2 {
            &s[1..s.len() - 1]
        } else {
            s
        };
        return serde_json::from_str(s).unwrap_or_else(|_| serde_json::Value::String(s.into()));
    }
    let mut out = String::new();
    let mut iter = s.chars();
    while let Some(c) = iter.next() {
        match c {
            ';' | '#' => break,
            '\\' => match iter.next() {
                Some(c @ (';' | '#' | '\\')) => out.push(c),
                Some(c) => {
                    out.push('\\');
                    out.push(c);
                }
                None => out.push('\\'),
            },
            _ => out.push(c),
        }
    }
    serde_json::Value::String(out.trim().to_string())
}
fn split_sections(s: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut start = 0;
    let b = s.as_bytes();
    for (i, c) in b.iter().enumerate() {
        if *c == b'.' && (i == 0 || b[i - 1] != b'\\') {
            parts.push(s[start..i].to_string());
            start = i + 1;
        }
    }
    parts.push(s[start..].to_string());
    parts
}
pub fn sidecar(p: &Path, suffix: &str) -> PathBuf {
    let mut s = p.as_os_str().to_os_string();
    s.push(suffix);
    PathBuf::from(s)
}
