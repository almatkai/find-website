pub mod paths;
pub mod query;
pub mod snapshot;
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    future::pending,
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex, Weak,
    },
};
use tezbar_extension_sdk::{
    unchanged, view, BoxFuture, CommandConcurrency, CoreResult, Extension, ExtensionContext,
};
use uuid::Uuid;
#[derive(Default)]
struct Session {
    revision: u64,
    query: String,
    rows: Vec<Value>,
    ids: Vec<String>,
    retry: Option<(String, String)>,
    message: Option<String>,
    missing: Option<String>,
    search_retry: Option<String>,
}
pub struct Adapter {
    sessions: Arc<Mutex<HashMap<String, Weak<Mutex<Session>>>>>,
    workers: Mutex<Vec<tokio::task::JoinHandle<()>>>,
    gate: Arc<tokio::sync::Semaphore>,
}
impl Default for Adapter {
    fn default() -> Self {
        Self::new()
    }
}
impl Adapter {
    pub fn new() -> Self {
        Self {
            sessions: Arc::default(),
            workers: Mutex::default(),
            gate: Arc::new(tokio::sync::Semaphore::new(1)),
        }
    }
}
struct Lease {
    id: String,
    sessions: Arc<Mutex<HashMap<String, Weak<Mutex<Session>>>>>,
    _owner: Arc<Mutex<Session>>,
}
impl Drop for Lease {
    fn drop(&mut self) {
        let mut map = self.sessions.lock().unwrap();
        if map
            .get(&self.id)
            .is_some_and(|w| w.ptr_eq(&Arc::downgrade(&self._owner)))
        {
            map.remove(&self.id);
        }
    }
}
struct Stop(Arc<AtomicBool>);
impl Drop for Stop {
    fn drop(&mut self) {
        self.0.store(true, Ordering::Release);
    }
}
fn fresh() -> String {
    Uuid::new_v4().to_string()
}
fn render(s: &Session) -> Value {
    let mut actions = Vec::new();
    let mut children = Vec::new();
    for (i, row) in s.rows.iter().enumerate() {
        let id = s.ids.get(i).cloned().unwrap_or_default();
        if !id.is_empty() {
            actions.push(json!({"id":id,"title":"Open in Browser","kind":"open"}));
        }
        children.push(json!({"type":"List.Item","props":{"id":row["key"],"title":row["title"],"subtitle":row["url"],"icon":{"source":row["icon"],"tooltip":row["tooltip"]},"accessories":[{"tag":{"value":row["accessory"],"color":row["color"]},"tooltip":row["accessoryTooltip"]}],"actionIds":if id.is_empty(){vec![]}else{vec![id]}}}));
    }
    if let Some((id, _)) = &s.retry {
        actions.push(json!({"id":id,"title":"Retry Opening Website","kind":"action"}));
    }
    if let Some(id) = &s.search_retry {
        actions.push(json!({"id":id,"title":"Retry Search","kind":"action"}));
    }
    if let Some(title) = &s.missing {
        children.push(json!({"type":"List.EmptyView","props":{"icon":"Icon.Warning","title":title,"description":"Please set the browser preference to one you have installed."}}));
    } else if let Some(message) = &s.message {
        children
            .push(json!({"type":"List.EmptyView","props":{"icon":"Icon.Warning","title":message}}));
    }
    let mut v = view(
        "Find Website",
        json!({"type":"List","props":{"navigationTitle":"Find Website","searchBarPlaceholder":"Quickly find the website you're looking for...","filtering":false,"__hasServerSearch":true,"searchText":s.query,"isLoading":false},"children":children}),
        actions,
    );
    v["refreshMs"] = Value::Null;
    if let Some(m) = &s.message {
        v["message"] = json!(m);
    }
    v
}
impl Extension for Adapter {
    fn id(&self) -> &'static str {
        "com.tezbar.native.find-website"
    }
    fn version(&self) -> &'static str {
        "2.0.0"
    }
    fn commands(&self) -> &'static [&'static str] {
        &["find"]
    }
    fn concurrency(&self, _: &str) -> CommandConcurrency {
        CommandConcurrency::Serialize
    }
    fn handle<'a>(
        &'a self,
        ctx: &'a ExtensionContext,
        _: &'a str,
        op: &'a str,
        p: &'a Value,
        state: &'a mut Value,
    ) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            let sid = p["sessionId"]
                .as_str()
                .ok_or("This search session is unavailable.")?
                .to_string();
            if op == "extension:dispose-session" {
                self.sessions.lock().unwrap().remove(&sid);
                return Ok(unchanged());
            }
            let owner = if op == "extension:run-command" {
                let owner = Arc::new(Mutex::new(Session::default()));
                self.sessions
                    .lock()
                    .unwrap()
                    .retain(|_, s| s.strong_count() > 0);
                self.sessions
                    .lock()
                    .unwrap()
                    .insert(sid.clone(), Arc::downgrade(&owner));
                let lease = Lease {
                    id: sid,
                    sessions: self.sessions.clone(),
                    _owner: owner.clone(),
                };
                ctx.spawn(async move {
                    let _lease = lease;
                    pending::<()>().await;
                })?;
                state["owner"] = json!(fresh());
                owner
            } else {
                match self
                    .sessions
                    .lock()
                    .unwrap()
                    .get(&sid)
                    .and_then(Weak::upgrade)
                {
                    Some(s) => s,
                    None => return Ok(unchanged()),
                }
            };
            if op == "extension:refresh-session" {
                return Ok(render(&owner.lock().unwrap()));
            }
            let browser = p["preferences"]["browser"]
                .as_str()
                .unwrap_or("chrome")
                .to_string();
            let profile = p["preferences"]["profile"]
                .as_str()
                .unwrap_or("Default")
                .to_string();
            let mut search = op == "extension:search-text-changed";
            if op == "extension:invoke-action" {
                let action = p["actionId"].as_str().unwrap_or("");
                let target = {
                    let mut s = owner.lock().unwrap();
                    if s.search_retry.as_deref() == Some(action) {
                        s.search_retry = None;
                        search = true;
                        None
                    } else if s.retry.as_ref().is_some_and(|(id, _)| id == action) {
                        let (_, url) = s.retry.take().unwrap();
                        Some((url, s.revision, None))
                    } else if let Some(i) =
                        s.ids.iter().position(|id| !id.is_empty() && id == action)
                    {
                        s.ids.fill(String::new());
                        Some((
                            s.rows[i]["url"].as_str().unwrap().to_string(),
                            s.revision,
                            Some(i),
                        ))
                    } else {
                        return Ok(unchanged());
                    }
                };
                if let Some((target, revision, index)) = target {
                    // Consumed and checkpointed outside SDK staged state before await.
                    {
                        let mut s = owner.lock().unwrap();
                        s.retry = Some((fresh(), target.clone()));
                        s.message=Some("Opening was not confirmed. Retry only if you still want to open this website.".into());
                    }
                    let result = ctx.host("host.shell.open", json!({"target":target})).await;
                    let confirmed = result.ok().is_some_and(|v| {
                        v.as_object().is_some_and(|o| {
                            o.get("ok") == Some(&json!(true))
                                && o.keys().all(|k| k == "ok" || k == "message")
                                && o.get("message").is_none_or(Value::is_string)
                        })
                    });
                    let mut s = owner.lock().unwrap();
                    if s.revision != revision {
                        return Ok(unchanged());
                    }
                    if confirmed {
                        s.retry = None;
                        s.message = None;
                        let _ = index;
                        s.ids = s.rows.iter().map(|_| fresh()).collect();
                    }
                    return Ok(render(&s));
                }
            }
            if op == "extension:run-command" || search {
                // Own the query/revision, clear stale rows/actions BEFORE any await,
                // including validation failure and empty input.
                let (text, revision) = {
                    let mut s = owner.lock().unwrap();
                    let text = if search && op != "extension:invoke-action" {
                        p["searchText"].as_str().unwrap_or("").to_string()
                    } else {
                        s.query.clone()
                    };
                    s.revision = s.revision.wrapping_add(1);
                    s.query = text.clone();
                    s.rows.clear();
                    s.ids.clear();
                    s.retry = None;
                    s.message = None;
                    s.search_retry = None;
                    s.missing = None;
                    (text, s.revision)
                };
                if search && op != "extension:invoke-action" && !p["searchText"].is_string() {
                    let mut s = owner.lock().unwrap();
                    s.message = Some("Search text must be a string.".into());
                    return Ok(render(&s));
                }
                if text.len() > 4096 || text.contains('\0') || text.split(' ').count() > 128 {
                    let mut s = owner.lock().unwrap();
                    s.message =
                        Some("Search is too long or contains an unsupported character.".into());
                    return Ok(render(&s));
                }
                let result = (|| {
                    if !paths::BROWSERS.contains(&browser.as_str()) {
                        return Err("Choose a supported browser in preferences.".into());
                    }
                    let roots = paths::Roots::system()?;
                    let windows = matches!(ctx.platform.as_str(), "windows" | "Windows" | "win32");
                    let installed = paths::installation(&browser, &profile, windows, &roots)
                        .is_some_and(|p| p.exists());
                    if !installed {
                        owner.lock().unwrap().missing =
                            Some(format!("{browser} browser is not installed"));
                        return Ok(None);
                    }
                    if op == "extension:run-command" {
                        return Ok(None);
                    }
                    paths::source(&browser, &profile, windows, &roots).map(Some)
                })();
                let result = match result {
                    Ok(Some(src)) => {
                        if !src.exists() {
                            Ok(vec![])
                        } else {
                            let stop = Arc::new(AtomicBool::new(false));
                            let _stop = Stop(stop.clone());
                            let permit = self
                                .gate
                                .clone()
                                .acquire_owned()
                                .await
                                .map_err(|_| "History reader is unavailable.")?;
                            let (tx, rx) = tokio::sync::oneshot::channel();
                            let temp = ctx.paths.temp_dir.clone();
                            let worker = tokio::task::spawn_blocking(move || {
                                let _permit = permit;
                                let _ =
                                    tx.send(snapshot::search(&src, &temp, &browser, &text, stop));
                            });
                            {
                                let mut workers = self.workers.lock().unwrap();
                                workers.retain(|h| !h.is_finished());
                                workers.push(worker);
                            }
                            tokio::select! {biased;_ = ctx.cancelled()=>return Ok(unchanged()),r=rx=>r.unwrap_or_else(|_|Err("History reader stopped. Try again.".into()))}
                        }
                    }
                    Ok(None) => Ok(vec![]),
                    Err(e) => Err(e),
                };
                let mut s = owner.lock().unwrap();
                if s.revision != revision {
                    return Ok(unchanged());
                }
                match result {
                    Ok(rows) => {
                        s.ids = rows.iter().map(|_| fresh()).collect();
                        s.rows = rows;
                    }
                    Err(e) => {
                        s.message = Some(e);
                        s.search_retry = Some(fresh());
                    }
                }
                return Ok(render(&s));
            }
            Ok(unchanged())
        })
    }
    fn shutdown<'a>(&'a self, _: &'a ExtensionContext) -> BoxFuture<'a, CoreResult> {
        Box::pin(async move {
            self.sessions.lock().unwrap().clear();
            let workers = std::mem::take(&mut *self.workers.lock().unwrap());
            for h in workers {
                let _ = h.await;
            }
            Ok(unchanged())
        })
    }
}

#[cfg(test)]
mod lifecycle_tests {
    use super::*;
    use tezbar_extension_sdk::{ExtensionPaths, TestContext};
    #[tokio::test]
    async fn canceled_scope_after_handler_return_drops_external_session_lease() {
        let adapter = Adapter::new();
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join(".qa/tmp");
        std::fs::create_dir_all(&root).unwrap();
        let private = tempfile::tempdir_in(root).unwrap();
        let make = || {
            let mut t = TestContext::new(
                ExtensionPaths {
                    package_dir: private.path().into(),
                    data_dir: private.path().into(),
                    temp_dir: private.path().into(),
                },
                &[],
            );
            t.context.platform = "windows".into();
            t
        };
        for i in 0..140 {
            let t = make();
            let p = json!({"sessionId":format!("c{i}"),"preferences":{"browser":"safari"}});
            let mut state = json!({});
            adapter
                .handle(&t.context, "find", "extension:run-command", &p, &mut state)
                .await
                .unwrap();
            assert_eq!(adapter.sessions.lock().unwrap().len(), 1);
            // No dispose callback: scope cancellation AFTER the adapter returned.
            drop(t);
            tokio::task::yield_now().await;
            assert_eq!(adapter.sessions.lock().unwrap().len(), 0);
        }
        let mut contexts = Vec::new();
        for i in 0..128 {
            let t = make();
            adapter
                .handle(
                    &t.context,
                    "find",
                    "extension:run-command",
                    &json!({"sessionId":i.to_string(),"preferences":{"browser":"safari"}}),
                    &mut json!({}),
                )
                .await
                .unwrap();
            contexts.push(t);
        }
        assert_eq!(adapter.sessions.lock().unwrap().len(), 128);
        drop(contexts);
        tokio::time::timeout(std::time::Duration::from_secs(1), async {
            while !adapter.sessions.lock().unwrap().is_empty() {
                tokio::task::yield_now().await;
            }
        })
        .await
        .unwrap();
        assert!(adapter.sessions.lock().unwrap().is_empty());
    }
}
