"""Production JSONL pipes; generated browser files + fake host/platform only."""
import os,sys,json,uuid,time,selectors,subprocess,sqlite3,hashlib,threading
from pathlib import Path
from env import ROOT,environment
EXE=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'target/debug/find-website-v2'
class Client:
 def __init__(self,grants=['shell.open'],platform='windows',presence=None):
  self.root=ROOT/'.qa/pipes'/str(uuid.uuid4());self.home=self.root/'home';self.temp=self.root/'temp';self.local=self.home/'local';self.roaming=self.home/'roaming'
  for p in [self.home,self.temp,self.local,self.roaming,self.root/'data']:p.mkdir(parents=True,exist_ok=True)
  self.env=environment();self.env.update(HOME=str(self.home),USERPROFILE=str(self.home),LOCALAPPDATA=str(self.local),APPDATA=str(self.roaming),TMPDIR=str(self.temp),TEMP=str(self.temp),TMP=str(self.temp))
  if presence:
   apps=self.root/'apps';apps.mkdir();[ (apps/name).mkdir()for name in presence['applications'] ];self.env.update(DYLD_INSERT_LIBRARIES=str(presence['library']),FIND_WEBSITE_QA_APPLICATIONS=str(apps),FIND_WEBSITE_QA_PRESENCE_AUDIT=str(self.root/'presence.log'))
  self.p=subprocess.Popen([str(EXE)],env=self.env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  self.sel=selectors.DefaultSelector();self.sel.register(self.p.stdout,selectors.EVENT_READ);self.buffer=b'';self.saved={};self.events=[]
  self.hello=self.read();assert self.hello['type']=='hello' and self.hello['sdkVersion']=='0.1.1'
  r=self.rpc('initialize',dict(protocol=1,extensionId='com.tezbar.native.find-website',platform=platform,packageDir=str(EXE.parent),dataDir=str(self.root/'data'),tempDir=str(self.temp),grantedCapabilities=grants));assert r['result']['ready']
 def write(self,v):self.p.stdin.write((json.dumps(v,ensure_ascii=False)+'\n').encode());self.p.stdin.flush()
 def request(self,method,params):
  id='h:'+str(uuid.uuid4());self.write(dict(type='request',id=id,method=method,params=params));return id
 def read(self,timeout=8):
  deadline=time.monotonic()+timeout
  while b'\n' not in self.buffer:
   if not self.sel.select(max(0,deadline-time.monotonic())):raise TimeoutError('production pipe response timed out')
   b=os.read(self.p.stdout.fileno(),65536)
   if not b:raise AssertionError('unexpected EOF: '+self.p.stderr.read().decode())
   self.buffer+=b
  line,self.buffer=self.buffer.split(b'\n',1);return json.loads(line)
 def wait(self,id):
  if id in self.saved:return self.saved.pop(id)
  while True:
   v=self.read()
   if v.get('id')==id:return v
   if v['type']=='response':self.saved[v['id']]=v
   else:self.events.append(v)
 def rpc(self,method,params):return self.wait(self.request(method,params))
 def open(self,s='s',browser='chrome',profile='Default'):return self.rpc('session.open',dict(sessionId=s,commandName='find',preferences=dict(browser=browser,profile=profile)))
 def call(self,op,payload={},s='s'):return self.rpc('session.call',dict(sessionId=s,operation='extension:'+op,payload=payload))
 def search(self,text,s='s'):return self.call('search-text-changed',dict(searchText=text),s)
 def invoke(self,id,s='s'):return self.call('invoke-action',dict(actionId=id),s)
 def finish(self,eof=False):
  if not eof:assert 'result'in self.rpc('shutdown',{})
  self.p.stdin.close();self.p.wait(timeout=6);assert self.p.returncode==0
  stderr=self.p.stderr.read().decode();assert not stderr,stderr
  assert list(self.temp.iterdir())==[],list(self.temp.iterdir())
 def db(self,browser='chrome',profile='Default'):
  paths={'chrome':self.local/'Google/Chrome/User Data'/profile/'History','arc':self.local/'Arc/User Data/Default/History','brave':self.local/'BraveSoftware/Brave-Browser/User Data/Default/History','edge':self.local/'Microsoft/Edge/User Data/Default/History','vivaldi':self.local/'Vivaldi/User Data/Default/History','opera':self.roaming/'Opera Software/Opera Stable/History','firefox':self.roaming/'Mozilla/Firefox/Profiles/owned/places.sqlite'}
  p=paths[browser];p.parent.mkdir(parents=True,exist_ok=True)
  if browser=='firefox':(self.roaming/'Mozilla/Firefox/profiles.ini').write_text('[Profile0]\nPath=Profiles/not-selected\n[InstallOWNED]\nDefault=Profiles/owned\n')
  return p

def make_db(path,firefox=False):
 c=sqlite3.connect(path);c.execute('create table '+('moz_places(id,title,url,last_visit_date,visit_count)' if firefox else 'urls(id,title,url,last_visit_time,visit_count,typed_count,hidden)'))
 for i in range(1,7):
  row=(i,'alpha' if i%2 else 'beta',f'https://owned.invalid/{i}',1700000000000000+i if firefox else 13300000000000000+i,i)
  c.execute('insert into '+('moz_places values(?,?,?,?,?)' if firefox else 'urls values(?,?,?,?,?,?,?)'),row if firefox else (*row,0,0))
 c.commit();return c

def result(v):assert 'result'in v,v;return v['result']
def rows(v):return [r for r in result(v)['root'].get('children',[]) if r['type']=='List.Item']
def actions(v):return result(v)['actions']
def fingerprints(p):return {f.name:(hashlib.sha256(f.read_bytes()).hexdigest(),f.stat().st_mode&0o777,f.stat().st_size)for f in p.parent.iterdir() if f.is_file()}

def basic():
 c=Client();db=c.db();make_db(db).close();before=fingerprints(db)
 assert rows(c.open())==[];a=c.search('alpha');assert len(rows(a))==6
 assert result(c.invoke('foreign'))['mode']=='unchanged'
 old=actions(a)[0]['id'];b=c.search('beta');assert result(c.invoke(old))['mode']=='unchanged'
 for texts in [('alpha','beta','alpha'),('alpha','\0','alpha'),('alpha','','alpha')]:
  ids=[c.request('session.call',dict(sessionId='s',operation='extension:search-text-changed',payload=dict(searchText=t)))for t in texts]
  replies=[c.wait(i)for i in ids];assert result(replies[-1])['root']['props']['searchText']=='alpha';assert all('alpha'==r['props']['title']for r in rows(replies[-1]))
 invalid=c.search('\0');assert rows(invalid)==[] and actions(invalid)==[]
 for malformed in [None,False,0,{},[]]:
  invalid=c.search(malformed);assert rows(invalid)==[] and actions(invalid)==[];assert result(invalid)['message']=='Search text must be a string.'
 assert len(rows(c.search('')))==6
 assert rows(c.search("'; DROP TABLE urls;--"))==[]
 current=c.search('alpha');id=actions(current)[0]['id'];request=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=id)))
 reverse=c.read();assert reverse['method']=='host.shell.open';target=reverse['params']['target'];assert target.startswith('https://owned.invalid/') and set(reverse['params'])=={'target'}
 c.write(dict(type='response',id=reverse['id'],result={'ok':True,'message':'Opened'}));opened=c.wait(request);assert not result(opened).get('message');assert actions(opened)[0]['id']!=id;assert result(c.invoke(id))['mode']=='unchanged'
 # Every malformed host shape is uncertain; only a manual frozen retry may open.
 for reply in [None,True,'ok',{'ok':False},{'ok':True,'extra':0},{'ok':True,'message':None}]:
  cur=c.search('alpha');action=actions(cur)[0]['id'];req=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=action)))
  rev=c.read();c.write(dict(type='response',id=rev['id'],result=reply));uncertain=c.wait(req);assert len(actions(uncertain))==1 and 'Retry Opening'in actions(uncertain)[0]['title'];assert result(c.invoke(action))['mode']=='unchanged'
  retry=actions(uncertain)[0]['id'];req=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=retry)))
  rev2=c.read();assert rev2['params']==rev['params'];c.write(dict(type='response',id=rev2['id'],result={'ok':True}));success=c.wait(req);assert len(actions(success))==6;assert result(c.invoke(retry))['mode']=='unchanged'
 # Duplicate queued clicks of one ID cannot replay an open after success.
 cur=c.search('alpha');action=actions(cur)[0]['id'];req1=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=action)));req2=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=action)))
 rev=c.read();assert rev['type']=='request';c.write(dict(type='response',id=rev['id'],result={'ok':True}))
 # SDK tasks can acquire the session lock in either scheduling order. Exactly
 # one request opens the URL; the duplicate stays inert, regardless of winner.
 replies=[c.wait(req1),c.wait(req2)];assert sorted(result(v)['mode']for v in replies)==['unchanged','view'];assert len(actions(next(v for v in replies if result(v)['mode']=='view')))==6
 # Canceled reverse call: external checkpoint survives SDK state rollback.
 cur=c.search('beta');action=actions(cur)[0]['id'];req=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=action)))
 rev=c.read();c.write(dict(type='cancel',requestId=req,reason='owned QA'));assert 'error'in c.wait(req)
 refresh=c.call('refresh-session');assert len(actions(refresh))==1 and actions(refresh)[0]['title']=='Retry Opening Website'
 # Source changes must not affect a frozen retry, and refresh never scans.
 original=db.read_bytes();db.write_bytes(b'corrupt owned DB')
 assert actions(c.call('refresh-session'))==actions(refresh)
 retry=actions(refresh)[0]['id'];req=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=retry)))
 while True:
  x=c.read()
  if x['type']=='request':break
 assert x['params']==rev['params'];c.write(dict(type='response',id=x['id'],result={'ok':True}));c.wait(req)
 error=c.search('alpha');assert rows(error)==[];assert actions(error)[0]['title']=='Retry Search'
 db.write_bytes(original);recovered=c.invoke(actions(error)[0]['id']);assert len(rows(recovered))==6
 # Current failure cannot retain rows from the preceding valid query.
 db.unlink();missing=c.search('beta');assert rows(missing)==[]
 db.write_bytes(original);assert fingerprints(db)==before
 assert list(c.temp.iterdir())==[]
 c.finish()
 print('pipes: original UI/action, malformed host replies, frozen retry, cancel, A/B/A, invalid/empty recovery, refresh, missing/corrupt and original-byte identity passed')

def browsers():
 c=Client()
 for browser in ['chrome','arc','brave','edge','vivaldi','opera','firefox']:
  db=c.db(browser,'Profile 2');make_db(db,browser=='firefox').close();assert rows(c.open(browser,browser,'Profile 2'))==[];r=c.search('alpha',browser);assert len(rows(r))==6,(browser,r)
 for browser in ['safari','orion','zen']:
  v=c.open(browser,browser);assert result(v)['root']['children'][0]['props']['title']==f'{browser} browser is not installed';assert rows(c.search('alpha',browser))==[]
 c.finish()
 c=Client([]);make_db(c.db()).close();c.open();cur=c.search('alpha');v=c.invoke(actions(cur)[0]['id']);assert len(actions(v))==1;assert not any(x.get('type')=='request'for x in c.events);c.finish()
 print('pipes: all 10 browser choices, Chrome profile, Firefox INI, Windows source gaps and denied capability passed')

def wal():
 c=Client();db=c.db();writer=make_db(db);assert writer.execute('pragma journal_mode=wal').fetchone()[0]=='wal';writer.execute('pragma wal_autocheckpoint=0');writer.execute("insert into urls values(20,'wal owned','https://owned.invalid/wal',13300000000099999,99,0,0)");writer.commit()
 before=fingerprints(db);c.open();v=c.search('wal');assert len(rows(v))==2 and rows(v)[0]['props']['title']=='wal owned';assert fingerprints(db)==before
 # A truncated current WAL is rejected, with the source and every sidecar unchanged.
 wal_path=Path(str(db)+'-wal');complete=wal_path.read_bytes();wal_path.write_bytes(complete[:-5]);broken=fingerprints(db);assert rows(c.search('wal'))==[];assert fingerprints(db)==broken;wal_path.write_bytes(complete)
 # While a writer owns the WAL write lock, fail promptly without copying stale data.
 writer.execute('begin immediate');writer.execute("update urls set title='uncommitted' where id=20")
 v=c.search('wal');assert rows(v)==[] and 'busy'in result(v)['message'].lower();writer.rollback();assert len(rows(c.search('wal')))==2
 # WAL SHM cannot be silently created by opening the browser DB readonly.
 writer.close();c.finish()
 c=Client();db=c.db();make_db(db).close();writer=sqlite3.connect(db);writer.execute('begin exclusive');c.open();v=c.search('alpha');assert rows(v)==[] and 'busy'in result(v)['message'].lower();writer.rollback();writer.close();assert len(rows(c.search('alpha')))==6
 # Malformed WAL/SHM/journal fixtures fail without writing originals.
 for suffix,data in [('-journal',b'unfinished owned transaction'),('-wal',b'bad owned WAL')]:
  p=Path(str(db)+suffix);p.write_bytes(data);before=fingerprints(db);v=c.search('alpha');assert rows(v)==[];assert fingerprints(db)==before;p.unlink()
 c.finish()
 # Concurrent browser writer: title, url, and accessory must share one commit.
 c=Client();db=c.db();writer=make_db(db);writer.execute('pragma journal_mode=wal');writer.execute('pragma wal_autocheckpoint=0');writer.execute("delete from urls");writer.execute("insert into urls values(1,'owned0','https://owned.invalid/0',13300000000000000,0,0,0)");writer.commit();c.open()
 stop=threading.Event();fail=[]
 def write_loop():
  w=sqlite3.connect(db,timeout=.1)
  for i in range(1,100):
   if stop.is_set():break
   try:w.execute('update urls set title=?,url=?,visit_count=?',(f'owned{i}',f'https://owned.invalid/{i}',i));w.commit()
   except sqlite3.OperationalError:w.rollback()
  w.close()
 thread=threading.Thread(target=write_loop);thread.start();success=0;busy=0
 for _ in range(40):
  v=c.search('owned');r=rows(v)
  if not r:assert 'message'in result(v);busy+=1;continue
  success+=1;assert len(r)==2;num=r[0]['props']['title'][5:];assert r[0]['props']['subtitle']==f'https://owned.invalid/{num}';assert r[0]['props']['accessories'][0]['tag']['value']==num
 stop.set();thread.join(timeout=3);assert not thread.is_alive();assert success>0
 before=fingerprints(db);assert len(rows(c.search('owned')))==2;assert fingerprints(db)==before
 writer.close();c.finish();print(f'pipes: coherent committed WAL, source/all-sidecar identity, WAL and rollback locks, hot/partial journals, concurrent writer passed ({success} coherent/{busy} busy)')

def worker_cancel():
 c=Client();db=c.db();w=make_db(db);w.executemany('insert into urls values(?,?,?,?,?,?,?)',((i,'owned '+('x'*256),f'https://owned.invalid/{i}',13300000000000000+i,i,0,0)for i in range(10,160010)));w.commit();w.close();before=fingerprints(db);c.open()
 id=c.request('session.call',dict(sessionId='s',operation='extension:search-text-changed',payload=dict(searchText='owned')))
 deadline=time.monotonic()+3
 while not list(c.temp.iterdir()) and time.monotonic()<deadline:time.sleep(.0005)
 assert list(c.temp.iterdir()),'worker fixture was not observed'
 c.write(dict(type='cancel',requestId=id,reason='cancel active owned file work'));assert 'error'in c.wait(id)
 deadline=time.monotonic()+4
 while list(c.temp.iterdir())and time.monotonic()<deadline:time.sleep(.001)
 assert not list(c.temp.iterdir());assert fingerprints(db)==before
 # EOF during another active scan owns and drains its blocking worker.
 c.request('session.call',dict(sessionId='s',operation='extension:search-text-changed',payload=dict(searchText='owned')))
 deadline=time.monotonic()+3
 while not list(c.temp.iterdir())and time.monotonic()<deadline:time.sleep(.0005)
 assert list(c.temp.iterdir());c.finish(eof=True);assert fingerprints(db)==before
 print('pipes: active large-file worker cancellation/EOF, bounded worker drain, private cleanup and source identity passed')

def capacity():
 c=Client()
 for i in range(140):
  id='h:'+str(uuid.uuid4());frames=[dict(type='request',id=id,method='session.open',params=dict(sessionId=f'c{i}',commandName='find',preferences=dict(browser='safari'))),dict(type='cancel',requestId=id,reason='owned QA')]
  c.p.stdin.write((''.join(json.dumps(v)+'\n'for v in frames)).encode());c.p.stdin.flush();assert 'error'in c.wait(id)
 for i in range(128):assert 'result'in c.open(str(i),'safari')
 assert 'error'in c.open('overflow','safari');assert 'result'in c.rpc('session.dispose',dict(sessionId='0'));assert 'result'in c.open('after-dispose','safari')
 c.finish();print('pipes: 140 canceled opens then 128 live sessions, capacity and dispose passed')

def endings():
 c=Client();make_db(c.db()).close();c.open();v=c.search('alpha');req=c.request('session.call',dict(sessionId='s',operation='extension:invoke-action',payload=dict(actionId=actions(v)[0]['id'])));assert c.read()['type']=='request';c.finish(eof=True)
 for bad in [b'{}\r\n',b'[]\n',b'{"type":"request"}',b'x'*(16*1024*1024+1)+b'\n']:
  c=Client();c.p.stdin.write(bad);c.p.stdin.flush();c.p.stdin.close();c.p.wait(timeout=6);assert c.p.returncode!=0;err=c.p.stderr.read().decode();assert 'Find Website stopped'in err;assert str(c.root)not in err;assert list(c.temp.iterdir())==[]
 print('pipes: EOF with pending effect, malformed/CR/truncated/oversized frames, bounded exit and cleanup passed')
if __name__=='__main__':
 basic();browsers();wal();worker_cancel();capacity();endings()
