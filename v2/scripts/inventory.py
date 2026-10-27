"""Close every Git-visible README/v2 candidate, excluding only this inventory."""
import subprocess,json,hashlib,stat
from pathlib import Path
from env import ROOT
SOURCE='18b1298844a55c7d90de52f64334092ce7b931ff'
def inventory():
 repo=ROOT.parent
 def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
 assert git('rev-parse','--show-toplevel')==str(repo)
 assert git('branch','--show-current')=='feat/native-v2-rust';assert git('rev-parse','HEAD')==SOURCE
 assert git('remote','get-url','origin')=='https://github.com/almatkai/find-website.git'
 assert git('diff','--cached','--name-only')=='','Index must remain empty'
 originals=[]
 for file in git('ls-tree','-r','--name-only',SOURCE).splitlines():
  original=subprocess.check_output(['git','-C',str(repo),'show',SOURCE+':'+file]);current=(repo/file).read_bytes()
  if file=='README.md':assert current==original+b'\nStandalone Rust V2 implementation and review instructions: [v2/README.md](v2/README.md).\n'
  else:assert current==original,'V1 changed: '+file
  originals.append({'path':file,'sourceSha256':hashlib.sha256(original).hexdigest(),'unchanged':file!='README.md'})
 # Check actual fresh HTTPS-fetched SDK contents against immutable sibling Git objects.
 fresh=json.loads((ROOT/'evidence/fresh-build.json').read_text());assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in fresh['inputs'].items());home=ROOT/fresh['cargoHome'];sdk=next((home/'git/checkouts').glob('tezbar-extension-sdk-rust-*/*'))
 assert subprocess.check_output(['git','-C',str(sdk),'rev-parse','HEAD'],text=True).strip()=='e955911f0bf5b558f9d3eb5183df0adc95c22af2'
 source_repo=repo.parent/'tezbar-extension-sdk-rust';rev='e955911f0bf5b558f9d3eb5183df0adc95c22af2';sdk_files=[]
 for file in subprocess.check_output(['git','-C',str(source_repo),'ls-tree','-r','--name-only',rev],text=True).splitlines():
  raw=subprocess.check_output(['git','-C',str(source_repo),'show',rev+':'+file]);assert (sdk/file).read_bytes()==raw;sdk_files.append({'path':file,'sha256':hashlib.sha256(raw).hexdigest()})
 immutable={'ownSource':SOURCE,'v1':originals,'sdk':{'revision':rev,'files':sdk_files},'hostTree':subprocess.check_output(['git','-C',str(repo.parent.parent/'Tezbar'),'rev-parse','ea100cee3f69711de12485ba061950c5fc65258f^{tree}'],text=True).strip()}
 (ROOT/'evidence/immutable-comparison.json').write_text(json.dumps(immutable,indent=2)+'\n')
 selected=git('ls-files','--cached','--others','--exclude-standard','--','README.md','v2').splitlines();assert len(selected)==len(set(selected))
 self_path='v2/evidence/candidate-sha256.json';candidates=[]
 for name in sorted(selected):
  if name==self_path:continue
  p=repo/name;assert p.is_file()and not p.is_symlink();assert not any(c in p.relative_to(repo).parts for c in ['.qa','target','dist','node_modules','__pycache__']);assert not name.endswith(('.sqlite','.db','.zip'))
  data=p.read_bytes();candidates.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'mode':oct(stat.S_IMODE(p.stat().st_mode)),'bytes':len(data)})
 out={'root':'rust-extension-ports/find-website','branch':'feat/native-v2-rust','HEAD':SOURCE,'index':'empty','excludesOnly':self_path,'files':candidates}
 (ROOT/'evidence/candidate-sha256.json').write_text(json.dumps(out,indent=2)+'\n')
 # Re-read every candidate after writing; no invisible fixture is relied on by the package.
 for v in candidates:assert hashlib.sha256((repo/v['path']).read_bytes()).hexdigest()==v['sha256']
 assert git('diff','--cached','--name-only')==''
 print(f'{len(candidates)} Git-visible README/v2 candidates inventoried; original V1 and fresh HTTPS SDK byte comparisons passed; index empty')
if __name__=='__main__':inventory()
