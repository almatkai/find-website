"""Reproducible isolated verification; records real results without publishing."""
import json,subprocess,sys,hashlib,uuid
from pathlib import Path
from env import ROOT,environment

def verify():
 records=[];logs=ROOT/'.qa/logs';logs.mkdir(parents=True,exist_ok=True)
 def run(name,args,chain='stable',cwd=ROOT,blocked=False,env=None):
  p=subprocess.run(args,cwd=cwd,env=env or environment(chain),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);data=p.stdout.encode();(logs/(name+'.log')).write_bytes(data)
  state='passed'if p.returncode==0 else 'blocked'if blocked and 'failed to find tool "x86_64-w64-mingw32-gcc"'in p.stdout else 'failed'
  records.append({'name':name,'command':args,'toolchain':chain,'state':state,'exitCode':p.returncode,'logSha256':hashlib.sha256(data).hexdigest()});print(name,state,flush=True)
  if state=='failed':print(p.stdout[-4000:]);raise RuntimeError(name+' failed')
 run('bootstrap',['python3','scripts/bootstrap.py'])
 run('v1-test',['npm','test'],cwd=ROOT/'.qa/v1');run('v1-typecheck',['npm','run','typecheck'],cwd=ROOT/'.qa/v1')
 run('host-patch',['python3','scripts/make_host_patch.py'])
 run('original-oracle',['node','scripts/oracle.cjs']);run('locked-library',['node','scripts/locked_library.cjs'])
 run('qa-oracle-build',['cargo','build','--locked','--example','oracle']);run('sqlite-source-parity',['python3','scripts/parity.py'])
 run('renderer',['node','scripts/renderer.cjs']);run('schema3',['node','scripts/schema.cjs']);run('pinned-host-producer',['python3','scripts/host_producer.py'])
 run('fmt',['cargo','fmt','--','--check'])
 for chain in ['stable','1.85.0']:
  run(chain+'-tests',['cargo','test','--locked'],chain);run(chain+'-clippy',['cargo','clippy','--locked','--all-targets','--','-D','warnings'],chain)
 run('production-debug-build',['cargo','build','--locked']);run('production-pipes',['python3','scripts/pipes.py']);run('mac-production-pipes',['python3','scripts/mac_pipes.py'])
 run('windows-gnu-check',['cargo','check','--locked','--target','x86_64-pc-windows-gnu'],blocked=True)
 run('windows-gnu-clippy',['cargo','clippy','--locked','--all-targets','--target','x86_64-pc-windows-gnu','--','-D','warnings'],blocked=True)
 run('windows-lock-metadata',['python3','scripts/windows_lock.py'])
 run('all-archive-fetch',['cargo','fetch','--locked']);run('archive-license-icon-audit',['python3','scripts/licenses.py'])
 if '--fresh-build'in sys.argv:
  suffix=uuid.uuid4().hex;cargo='fresh-cargo-'+suffix;target='.qa/fresh-target-'+suffix;env=environment(cargo_home=cargo,target=target);assert not list((ROOT/'.qa'/cargo).iterdir());assert not (ROOT/target).exists()
  inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in [ROOT/'Cargo.toml',ROOT/'Cargo.lock',*sorted((ROOT/'src').glob('*.rs'))]}
  run('empty-home-https-production',['cargo','build','--release','--locked'],env=env)
  assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in inputs.items())
  (ROOT/'evidence/fresh-build.json').write_text(json.dumps({'inputs':inputs,'buildLogSha256':records[-1]['logSha256'],'exitCode':0,'cargoHome':'.qa/'+cargo,'target':target,'initialState':'empty/nonexistent','sdkSource':'https://github.com/almatkai/tezbar-extension-sdk-rust.git','sdkRevision':'e955911f0bf5b558f9d3eb5183df0adc95c22af2','binary':target+'/release/find-website-v2'},indent=2)+'\n')
 if '--package'in sys.argv:
  fresh=json.loads((ROOT/'evidence/fresh-build.json').read_text());run('deterministic-zip-extracted-pipes',['python3','scripts/package.py',str(ROOT/fresh['binary'])])
 report={'results':records,'nativeHostAcceptance':{'macOS':'not-run','Windows':'not-run'},'unappliedHostPrerequisite':'host-prerequisite.patch','temporaryProjectRegistration':'mcp:1f6ceb42-0ba6-43e7-93b9-07809843380e'}
 (ROOT/'evidence/validation.json').write_text(json.dumps(report,indent=2)+'\n');print('Verification recorded; no staging, commit, push, install or cleanup performed.')
if __name__=='__main__':verify()
