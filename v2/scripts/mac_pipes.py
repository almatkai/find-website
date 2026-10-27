"""Actual production macOS browser success paths with prelaunch FS interposition."""
import sys,subprocess,sqlite3,json,hashlib
from pathlib import Path
from env import ROOT,environment
import pipes
if len(sys.argv)>1:pipes.EXE=Path(sys.argv[1]).resolve()
lib=ROOT/'.qa/fake-presence.dylib'
subprocess.run(['/usr/bin/clang','-dynamiclib','-Wall','-Wextra','-Werror',str(ROOT/'scripts/fake_presence.c'),'-o',str(lib)],env=environment(),cwd=ROOT,check=True)
apps={'chrome':'Google Chrome.app','orion':'Orion.app','arc':'Arc.app','safari':'Safari.app','firefox':'Firefox.app','zen':'Zen Browser.app','brave':'Brave Browser.app','vivaldi':'Vivaldi.app','opera':'Opera.app','edge':'Microsoft Edge.app'}
c=pipes.Client(platform='macos',presence={'library':lib,'applications':list(apps.values())})
paths={'chrome':'Library/Application Support/Google/Chrome/Profile 2/History','orion':'Library/Application Support/Orion/Defaults/history','arc':'Library/Application Support/Arc/User Data/Default/History','safari':'Library/Safari/History.db','firefox':'Library/Application Support/Firefox/Profiles/owned/places.sqlite','zen':'Library/Application Support/zen/Profiles/owned/places.sqlite','brave':'Library/Application Support/BraveSoftware/Brave-Browser/Default/History','vivaldi':'Library/Application Support/Vivaldi/Default/History','opera':'Library/Application Support/com.operasoftware.Opera/Default/History','edge':'Library/Application Support/Microsoft Edge/Default/History'}
for browser,relative in paths.items():
 p=c.home/relative;p.parent.mkdir(parents=True,exist_ok=True)
 if browser in ['firefox','zen']:
  base=c.home/('Library/Application Support/'+('Firefox'if browser=='firefox'else'zen'));(base/'profiles.ini').write_text('[General]\nStartWithLastProfile=1\n[Profile0]\nPath=Profiles/ignored\n[InstallOWNED]\nDefault=Profiles/owned\n');pipes.make_db(p,True).close()
 elif browser=='orion':
  db=sqlite3.connect(p);db.execute('create table history_items(id,title,url,host,last_visit_time,visit_count,typed_count)');db.executemany('insert into history_items values(?,?,?,?,?,?,?)',[(i,'alpha',f'https://owned.invalid/{i}','owned.invalid',1700000000+i,i,0)for i in range(1,7)]);db.commit();db.close()
 elif browser=='safari':
  db=sqlite3.connect(p);db.executescript('create table history_items(id,url,visit_count);create table history_visits(history_item,title,visit_time);');db.executemany('insert into history_items values(?,?,?)',[(i,f'https://owned.invalid/{i}',i)for i in range(1,7)]);db.executemany('insert into history_visits values(?,?,?)',[(i,'alpha',770000000+i)for i in range(1,7)]);db.commit();db.close()
 else:pipes.make_db(p).close()
 before=pipes.fingerprints(p);assert pipes.rows(c.open(browser,browser,'Profile 2'))==[]
 v=c.search('alpha',browser);assert len(pipes.rows(v))==6,(browser,v);assert pipes.fingerprints(p)==before
 action=pipes.actions(v)[0]['id'];req=c.request('session.call',dict(sessionId=browser,operation='extension:invoke-action',payload=dict(actionId=action)));rev=c.read();assert rev['method']=='host.shell.open'and set(rev['params'])=={'target'};c.write(dict(type='response',id=rev['id'],result={'ok':True,'message':'Opened'}));assert not pipes.result(c.wait(req)).get('message')
 # IDs from another browser's session stay inert.
 if browser!='chrome':assert pipes.result(c.invoke(action,'chrome'))['mode']=='unchanged'
c.finish()
audit=(c.root/'presence.log').read_text().splitlines();assert set(audit)=={'/Applications/'+n for n in apps.values()},audit
missing=pipes.Client(platform='macos',presence={'library':lib,'applications':[]});v=missing.open('missing','safari');assert pipes.result(v)['root']['children'][0]['props']['title']=='safari browser is not installed';missing.finish()
print('Actual macOS production SDK pipes: all 10 successful browser/factory/query/action paths passed; application-presence producers were prelaunch-injected and audited; generated original files unchanged')
