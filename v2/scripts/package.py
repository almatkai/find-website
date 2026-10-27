"""Deterministic closed ARM64 development ZIP. No artifact publication/install."""
from pathlib import Path
import json,hashlib,stat,zipfile,os,subprocess
from env import ROOT,environment
sha=lambda b:hashlib.sha256(b).hexdigest()
def package(binary=None):
 binary=Path(binary)if binary else ROOT/'.qa/fresh-final-target/release/find-website-v2'
 assert binary.is_file()
 members={'bin/find-website-v2':(binary.read_bytes(),0o755),'LICENSE':((ROOT/'LICENSE').read_bytes(),0o644),'NOTICE':((ROOT/'NOTICE').read_bytes(),0o644)}
 for directory in ['resources','licenses']:
  for p in sorted((ROOT/directory).rglob('*')):
   if p.is_file():assert not p.is_symlink();members[p.relative_to(ROOT).as_posix()]=(p.read_bytes(),0o644)
 manifest=json.loads((ROOT/'extension.json').read_text());assert manifest['artifacts']=={};assert all(v['state']=='not-run'for v in manifest['verification']);manifest['files']={name:sha(data)for name,(data,_)in sorted(members.items())}
 members['extension.json']=((json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode(),0o644)
 dist=ROOT/'dist';dist.mkdir(exist_ok=True);archive=dist/'find-website-v2-aarch64-apple-darwin-dev.zip'
 def write(path):
  with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9)as z:
   for name,(data,mode)in sorted(members.items()):
    assert name in ['extension.json','LICENSE','NOTICE','bin/find-website-v2']or name.startswith(('resources/','licenses/'))
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.create_system=3;info.external_attr=(stat.S_IFREG|mode)<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data,compresslevel=9)
 write(archive);second=ROOT/'.qa/package-second.zip';write(second);assert archive.read_bytes()==second.read_bytes()
 inventory=[];extract=ROOT/'.qa/extracted'/sha(archive.read_bytes());extract.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive)as z:
  assert z.namelist()==sorted(members);assert not z.testzip()
  for member in z.infolist():
   data=z.read(member);mode=(member.external_attr>>16)&0o777;assert data==members[member.filename][0]and mode==members[member.filename][1]
   inventory.append({'path':member.filename,'sha256':sha(data),'mode':oct(mode),'bytes':len(data)})
   dest=extract/member.filename;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);dest.chmod(mode)
 report={'archive':archive.relative_to(ROOT).as_posix(),'sha256':sha(archive.read_bytes()),'executableSha256':sha(binary.read_bytes()),'target':'aarch64-apple-darwin','extracted':extract.relative_to(ROOT).as_posix(),'kind':'development; artifacts {}; no installation/publication','deterministicRepack':True,'members':inventory}
 (ROOT/'evidence/package.json').write_text(json.dumps(report,indent=2)+'\n')
 assert sorted(p.relative_to(extract).as_posix()for p in extract.rglob('*')if p.is_file())==sorted(members)
 subprocess.run(['node',str(ROOT/'scripts/schema.cjs'),str(extract/'extension.json')],env=environment(),cwd=ROOT,check=True)
 subprocess.run(['python3',str(ROOT/'scripts/pipes.py'),str(extract/'bin/find-website-v2')],env=environment(),cwd=ROOT,check=True)
 subprocess.run(['python3',str(ROOT/'scripts/mac_pipes.py'),str(extract/'bin/find-website-v2')],env=environment(),cwd=ROOT,check=True)
 print('Deterministic ARM64 dev ZIP, closed SHA/mode inventory, full extracted-production pipes passed:',report['sha256'])
 return report
if __name__=='__main__':
 import sys
 package(sys.argv[1]if len(sys.argv)>1 else None)
