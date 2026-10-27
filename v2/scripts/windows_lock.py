"""Narrow metadata-only Windows FFI check; does not replace the blocked C build."""
from pathlib import Path
import subprocess
from env import ROOT,environment
s=(ROOT/'src/snapshot.rs').read_text();begin=s.index('#[cfg(windows)]\nfn lock');end=s.index('\nfn copy',begin)
q=ROOT/'.qa/windows-lock.rs';q.write_text('#![allow(dead_code)]\nuse std::fs::File;\nconst BUSY:&str="busy";\n'+s[begin:end]);lib=next((ROOT/'target/x86_64-pc-windows-gnu/debug/deps').glob('libwindows_sys-*.rmeta'))
subprocess.run(['rustc','--edition=2021','--crate-type=lib','--emit=metadata','--target=x86_64-pc-windows-gnu','--crate-name=windows_lock_qa',str(q),'--extern','windows_sys='+str(lib),'-L','dependency='+str(lib.parent),'-o',str(ROOT/'.qa/windows-lock.rmeta')],env=environment(),cwd=ROOT,check=True)
print('Exact Windows lock function metadata-only check passed; full GNU build still requires MinGW; native Windows execution not run')
