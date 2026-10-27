"""Create disposable exact-lock V1/validator installations only under v2/.qa."""
import subprocess,json,hashlib
from pathlib import Path
from env import ROOT,environment
SOURCE='18b1298844a55c7d90de52f64334092ce7b931ff'
def bootstrap():
 own=ROOT.parent;copy=ROOT/'.qa/v1';copy.mkdir(parents=True,exist_ok=True);records=[]
 for file in subprocess.check_output(['git','-C',str(own),'ls-tree','-r','--name-only',SOURCE],text=True).splitlines():
  data=subprocess.check_output(['git','-C',str(own),'show',SOURCE+':'+file]);p=copy/file;p.parent.mkdir(parents=True,exist_ok=True)
  if p.exists():assert p.read_bytes()==data,'Disposable V1 source changed: '+file
  else:p.write_bytes(data)
  records.append({'path':file,'sha256':hashlib.sha256(data).hexdigest()})
 subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=copy,env=environment(),check=True)
 q=ROOT/'.qa/validator';q.mkdir(exist_ok=True)
 for name in ['package.json','package-lock.json']:(q/name).write_bytes((ROOT/'scripts'/('validator-'+name)).read_bytes())
 subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=q,env=environment(),check=True)
 (ROOT/'evidence/v1-baseline.json').write_text(json.dumps({'sourceHead':SOURCE,'files':records,'installation':'npm ci --ignore-scripts; exact original package-lock.json, disposable copy only'},indent=2)+'\n')
if __name__=='__main__':bootstrap()
