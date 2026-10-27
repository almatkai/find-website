use rusqlite::{params_from_iter, types::ValueRef, Connection};
use serde_json::{json, Value};
use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Instant,
};

pub fn sql(browser: &str, top: bool, text: &str) -> (String, Vec<String>) {
    let host = if browser == "orion" { "host" } else { "url" };
    let words: Vec<String> = text.split(' ').map(|w| format!("%{w}%")).collect();
    let block = |col: &str| {
        words
            .iter()
            .map(|_| format!("{col} like ?"))
            .collect::<Vec<_>>()
            .join(" and ")
    };
    let filter = format!("({}) or ({})", block("title"), block(host));
    let mut values = words.clone();
    values.extend(words);
    let (select, table, order) = match browser {
        "safari" => {
            let q = if top {
                format!("select i.id, v.title as title, i.url as url, i.visit_count as visitCount from history_visits v, history_items i where v.history_item = i.id and ({filter}) group by i.id, v.title, i.url, i.visit_count order by visit_time desc limit 3")
            } else {
                format!("select distinct i.id, v.title as title, i.url as url, datetime(v.visit_time + 978307200, 'unixepoch', 'localtime') as visitTime from history_visits v, history_items i where v.history_item = i.id and ({filter}) order by visit_time desc limit 3")
            };
            return (q, values);
        },
        "firefox" | "zen" => ("select distinct id as id, title as title, url as url, datetime(last_visit_date/1000000, 'unixepoch', 'localtime') as lastVisitDate, visit_count as visitCount", "moz_places", "last_visit_date"),
        "orion" => ("select distinct id as id, title as title, url as url, host as host, last_visit_time as lastVisitTime, visit_count as visitCount, typed_count as typedCount", "history_items", "last_visit_time"),
        _ => ("select distinct id as id, title as title, url as url, datetime(last_visit_time / 1000000 + (strftime('%s', '1601-01-01')), 'unixepoch', 'localtime') as lastVisitTime, visit_count as visitCount, typed_count as typedCount, hidden as hidden", "urls", "last_visit_time"),
    };
    (
        format!(
            "{select} from {table} where ({filter}) order by {} desc limit 3",
            if top { "visit_count" } else { order }
        ),
        values,
    )
}

pub fn query(
    conn: &Connection,
    browser: &str,
    text: &str,
    stop: Arc<AtomicBool>,
    deadline: Instant,
) -> Result<Vec<Value>, String> {
    if stop.load(Ordering::Acquire) || Instant::now() >= deadline {
        return Err("History search was interrupted. Try again.".into());
    }
    conn.set_limit(rusqlite::limits::Limit::SQLITE_LIMIT_LENGTH, 512 * 1024);
    conn.set_limit(rusqlite::limits::Limit::SQLITE_LIMIT_SQL_LENGTH, 64 * 1024);
    let mut ticks = 0u64;
    conn.progress_handler(
        1000,
        Some(move || {
            ticks += 1;
            stop.load(Ordering::Acquire) || Instant::now() >= deadline || ticks > 100_000
        }),
    );
    let mut result = Vec::new();
    // Step calls nextStep (Top visited) first; there are no section wrappers.
    for top in [true, false] {
        let (sql, params) = sql(browser, top, text);
        let mut stmt = conn
            .prepare(&sql)
            .map_err(|_| "History could not be searched.")?;
        let names = stmt
            .column_names()
            .iter()
            .map(|s| s.to_string())
            .collect::<Vec<_>>();
        let mut rows = stmt
            .query(params_from_iter(params))
            .map_err(|_| "History could not be searched.")?;
        let mut i = 0;
        while let Some(row) = rows
            .next()
            .map_err(|_| "History search was interrupted. Try again.")?
        {
            let mut record = serde_json::Map::new();
            for (n, name) in names.iter().enumerate() {
                let v = match row
                    .get_ref(n)
                    .map_err(|_| "History contains an unreadable value.")?
                {
                    ValueRef::Null => Value::Null,
                    ValueRef::Integer(v) => json!(v),
                    ValueRef::Real(v) => json!(v),
                    ValueRef::Text(v) => {
                        json!(std::str::from_utf8(v).map_err(|_| "History contains invalid text.")?)
                    }
                    ValueRef::Blob(_) => {
                        return Err("History contains an unsupported value.".into())
                    }
                };
                record.insert(name.clone(), v);
            }
            let title = record.get("title").cloned().unwrap_or(Value::Null);
            let url = record
                .get("url")
                .and_then(Value::as_str)
                .ok_or("History contains an invalid address.")?;
            // Null converted dates throw in Chromium's V1 .toString adapter; report safely.
            let accessory = if top {
                let count = record
                    .get("visitCount")
                    .filter(|v| !v.is_null())
                    .ok_or("History contains an invalid visit count.")?;
                scalar(count)
            } else {
                let field = match browser {
                    "safari" => "visitTime",
                    "firefox" | "zen" => "lastVisitDate",
                    _ => "lastVisitTime",
                };
                let v = record.get(field).unwrap_or(&Value::Null);
                if v.is_null() && !matches!(browser, "safari" | "firefox" | "zen") {
                    return Err("History contains an invalid visit date.".into());
                }
                if v.is_null() {
                    String::new()
                } else {
                    scalar(v)
                }
            };
            result.push(json!({"key":format!("{i}_{}",if top {"tv"} else {"r"}),"title":if title.is_null(){json!("")}else{title},"url":url,"icon":if top {"Icon.Star"}else{"Icon.RotateAntiClockwise"},"tooltip":if top {"Top visited"}else{"Recents"},"accessory":accessory,"accessoryTooltip":if top {"Visit count"}else{"Last visited"},"color":if top {"yellow"}else{"magenta"}}));
            i += 1;
        }
    }
    // Also fence tiny queries which execute fewer than one progress interval.
    // The progress closure owns the cancellation flag during execution.
    if Instant::now() >= deadline {
        return Err("History search was interrupted. Try again.".into());
    }
    Ok(result)
}
fn scalar(v: &Value) -> String {
    v.as_str().map(str::to_owned).unwrap_or_else(|| {
        v.as_f64()
            .map(|n| ryu_js::Buffer::new().format(n).to_string())
            .unwrap_or_else(|| v.to_string())
    })
}
