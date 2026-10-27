"""Compile the actual pinned native producer; replace only the OS opener."""
import subprocess,json,re
from pathlib import Path
from env import ROOT,environment
from contracts import capture
p=capture();text=(p/'host-platform.rs').read_text();start=text.index('async fn open_target(');end=text.index('\nasync fn selected_text',start);function=text[start:end]
native=(p/'host-native.rs').read_text();begin=native.index('fn annotate(');end=native.index('\nstruct LaunchCleanup',begin);function+='\n'+native[begin:end]
q=ROOT/'.qa/host-producer';(q/'src').mkdir(parents=True,exist_ok=True)
(q/'Cargo.toml').write_text('''[package]
name="pinned-host-producer-qa"
version="0.0.0"
edition="2021"
[dependencies]
serde_json="=1.0.145"
tokio={version="=1.48.0",features=["rt-multi-thread","macros"]}
''')
(q/'src/lib.rs').write_text('''#![allow(dead_code)]
use serde_json::{json,Value};
type CoreResult=Result<serde_json::Value,String>;
struct Process {generation:String}
struct Entry {canonical:String,command:String,process:Process,policy:Value}
mod open {pub static CALLS:std::sync::Mutex<Vec<String>>=std::sync::Mutex::new(Vec::new());pub fn that_detached(target:String)->Result<(),std::io::Error>{CALLS.lock().unwrap().push(target);Ok(())}}
'''+function+'''
#[test]fn exact_annotation(){let e=Entry{canonical:"com.tezbar.native.generic".into(),command:"lookup".into(),process:Process{generation:"g".into()},policy:json!({"refreshMs":null})};assert_eq!(annotate(&e,"s",json!({"ok":true,"mode":"unchanged"})).unwrap(),json!({"ok":true,"mode":"unchanged"}));let v=annotate(&e,"s",json!({"ok":true,"mode":"view","root":{"type":"List"},"actions":[]})).unwrap();assert_eq!(v["sessionId"],"s");assert_eq!(v["generation"],"g");assert!(annotate(&e,"s",json!({"ok":true,"mode":"bad"})).is_err());}
#[tokio::test]async fn exact_producer_shape(){
for value in ["","  ","nul\\0address"]{assert!(open_target(value).await.is_err());}
assert!(open::CALLS.lock().unwrap().is_empty());
assert_eq!(open_target("https://owned.invalid/").await.unwrap(),json!({"ok":true,"message":"Opened"}));
assert_eq!(*open::CALLS.lock().unwrap(),vec!["https://owned.invalid/"]);
}
''')
(q/'Cargo.lock').write_bytes((ROOT/'scripts/host-producer.Cargo.lock').read_bytes())
subprocess.run(['cargo','test','--locked','--manifest-path',str(q/'Cargo.toml')],env=environment(),cwd=ROOT,check=True)
print('Actual pinned Rust open_target producer: typed response and invalid targets passed; OS producer replaced before evaluation')
