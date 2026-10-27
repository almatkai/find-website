"""Verify actual locked crate archives; preserve authentic grant/copyright files."""
from pathlib import Path
import hashlib,json,re,tarfile,urllib.request,subprocess
from env import ROOT

def digest(b):return hashlib.sha256(b).hexdigest()
def locked():
 for b in (ROOT/'Cargo.lock').read_text().split('[[package]]')[1:]:
  yield {k:json.loads(m.group(1))for k in ['name','version','source','checksum']if(m:=re.search(r'^'+k+r' = (".*")$',b,re.M))}
def audit():
 records=[];gaps=[];out=ROOT/'licenses';out.mkdir(exist_ok=True)
 for v in locked():
  if 'checksum' not in v:continue
  name=v['name']+'-'+v['version'];archive=next((ROOT/'.qa/cargo/registry/cache').glob('*/'+name+'.crate'));raw=archive.read_bytes();assert digest(raw)==v['checksum'],name
  grants=[]
  with tarfile.open(archive)as t:
   manifest=t.extractfile(name+'/Cargo.toml').read().decode();rv=re.search(r'^rust-version = (".*")$',manifest,re.M);license=re.search(r'^license = (".*")$',manifest,re.M)
   for m in t.getmembers():
    if m.isfile()and any(k in Path(m.name).name.lower()for k in ['license','licence','copying','copyright','authors','notice']):
     rel=Path(m.name).relative_to(name);data=t.extractfile(m).read();dest=out/name/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);grants.append({'archivePath':str(rel),'sha256':digest(data)})
   if name.startswith('libsqlite3-sys-'):
    content=t.extractfile(name+'/sqlite3/sqlite3.c').read();begin=content.index(b'/*\n** 2001 September 15');end=content.index(b'*/',begin)+2;grant=content[begin:end];(out/name/'sqlite3-copyright-disclaimer.txt').write_bytes(grant);grants.append({'archivePath':'sqlite3/sqlite3.c (exact first sqliteInt.h comment)','sha256':digest(grant)})
  if not grants:gaps.append(name+': actual locked archive lacks a recognized grant file; no legal clearance inferred')
  if v['name']=='r-efi':assert b'Permission is hereby granted' in (out/name/'AUTHORS').read_bytes()
  records.append({**v,'archiveSha256':digest(raw),'rustVersion':json.loads(rv[1])if rv else None,'licenseDeclaration':json.loads(license[1])if license else None,'preservedFiles':grants})
 # SDK grant and notice are authenticated against the immutable Git objects.
 sdk=ROOT.parent.parent/'tezbar-extension-sdk-rust';rev='e955911f0bf5b558f9d3eb5183df0adc95c22af2'
 for f in ['LICENSE','NOTICE']:
  data=subprocess.check_output(['git','-C',str(sdk),'show',rev+':'+f]);p=out/'tezbar-extension-sdk-0.1.1'/f;p.parent.mkdir(exist_ok=True);p.write_bytes(data)
 # ini@5 source semantics were translated into Rust; retain the real locked grant.
 ini=ROOT/'.qa/v1/node_modules/ini/LICENSE';assert ini.is_file();p=out/'ini-5.0.0-LICENSE';p.write_bytes(ini.read_bytes())
 url='https://raw.githubusercontent.com/raycast/extensions/6734d85992290066fd31a7f5bee3cca3d3545a1a/LICENSE';data=urllib.request.urlopen(url,timeout=30).read();(out/'raycast-extensions-MIT.txt').write_bytes(data)
 # A fresh independent download, never the existing own/copied asset as oracle.
 provenance=json.loads((ROOT/'resources/icon-provenance.json').read_text());icon=urllib.request.urlopen(provenance['source'],timeout=30).read();assert digest(icon)==provenance['sha256'];assert icon==(ROOT/'resources/logo.png').read_bytes()==(ROOT.parent/'assets/logo.png').read_bytes()
 own=subprocess.check_output(['git','-C',str(ROOT.parent),'show','18b1298844a55c7d90de52f64334092ce7b931ff:assets/logo.png']);assert own==icon
 report={'packages':records,'evidenceGaps':gaps,'sdkRevision':rev,'upstreamLicense':{'url':url,'sha256':digest(data)},'iconSha256':digest(icon),'notes':['r-efi 5.3.0 and 6.0.0 AUTHORS contain the MIT grant and are preserved intact.','wasip2 1.0.4 declares Rust 1.87 on an unused WASI target. Production targets are macOS ARM64 and Windows x64; native MSRV is tested on Rust 1.85.0.','Grant-file presence and authentic preservation are evidence, not legal approval.']}
 (ROOT/'evidence/dependencies.json').write_text(json.dumps(report,indent=2)+'\n');print(f'{len(records)} actual locked archive SHA256 checks and authentic notice collections passed; evidence gaps: {len(gaps)}')
if __name__=='__main__':audit()
