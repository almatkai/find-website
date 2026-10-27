import sys,json,sqlite3,subprocess,posixpath
from pathlib import Path
from env import environment,ROOT
Q=ROOT/'.qa'; oracle=json.loads((Q/'oracle.json').read_text()); db=Q/'parity.sqlite';db.unlink(missing_ok=True)
connections={}
for name,schema in {
'chrome':'create table urls(id integer,title text,url text,last_visit_time integer,visit_count integer,typed_count integer,hidden integer);',
'firefox':'create table moz_places(id integer,title text,url text,last_visit_date integer,visit_count integer);',
'orion':'create table history_items(id integer,title text,url text,host text,last_visit_time integer,visit_count integer,typed_count integer);',
'safari':'create table history_items(id integer,url text,visit_count integer); create table history_visits(history_item integer,title text,visit_time real);'
}.items():
 db=Q/('parity-'+name+'.sqlite');db.unlink(missing_ok=True);c=sqlite3.connect(db);c.row_factory=sqlite3.Row;c.executescript(schema);connections[name]=(db,c)
titles=['foo bar','Foo','bar',None,'Café','É','雪 😀',"O'Reilly",'percent_%','mixed CASE','title duplicate','title duplicate','null','example', 'date zero','date negative','date extreme']
for i,title in enumerate(titles,1):
 url=['https://foo.invalid/bar','https://example.invalid/Foo','https://same.invalid/'][i%3];date=13300000000000000+i*1000000 if i<15 else [0,-9000000000000,9223372036854775807][i-15]
 if i in (11,12):date=13300000000000000
 connections['chrome'][1].execute('insert into urls values(?,?,?,?,?,?,?)',(i,title,url,date,i%5,0,0))
 connections['firefox'][1].execute('insert into moz_places values(?,?,?,?,?)',(i,title,url,date-11644473600000000 if i<15 else date,i%5))
 connections['orion'][1].execute('insert into history_items values(?,?,?,?,?,?,?)',(i,title,url,'foo.invalid' if i%2 else 'other.invalid',str(date),i%5,0))
 c=connections['safari'][1];c.execute('insert into history_items values(?,?,?)',(i,url,i%5));c.execute('insert into history_visits values(?,?,?)',(i,title,(date-12622780800000000)/1000000 if i<15 else float(date)))
 if i in (11,12):c.execute('insert into history_visits values(?,?,?)',(i,title,12345))
for db,c in connections.values():c.commit()
def database(browser):return connections[browser if browser in ['orion','safari','firefox'] else 'firefox' if browser=='zen' else 'chrome']
records=[]
for case in oracle['queries']:
 db,c=database(case['browser'])
 records.append({**case,'db':str(db),'top':[dict(r) for r in c.execute(case['top'])],'recent':[dict(r) for r in c.execute(case['recent'])]})
(Q/'adapters-input.json').write_text(json.dumps(records));subprocess.run(['node',str(ROOT/'scripts/adapters.cjs'),str(Q/'adapters-input.json'),str(Q/'adapters-expected.json')],env=environment(),check=True)
expected=json.loads((Q/'adapters-expected.json').read_text())
exe=ROOT/'target/debug/examples/oracle';p=subprocess.Popen([exe],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=environment())
def call(v):p.stdin.write(json.dumps(v)+'\n');p.stdin.flush();return json.loads(p.stdout.readline())
for case,want in zip(records,expected):
 actual=call({'op':'query','db':case['db'],'browser':case['browser'],'text':case['text']});assert actual==want,(case['browser'],case['text'],actual,want)
for case in oracle['paths']:
 got=call({'op':'paths',**case});assert posixpath.normpath(got['path'].replace('\\','/'))==posixpath.normpath(case['path'].replace('\\','/')),(case,got)
 if case.get('installation')is None:assert got['installation']is None
 else:assert posixpath.normpath(got['installation'].replace('\\','/'))==posixpath.normpath(case['installation'].replace('\\','/')),(case,got)
for case in oracle['iniResults']:
 got=call({'op':'ini','text':case['text']});assert got.get('error')==case.get('error'),(case,got)
 if 'path'in case:assert case['path']==posixpath.normpath('/owned/home/Library/Application Support/Firefox/'+got['profile']+'/places.sqlite'),(case,got)
# Quotes are deliberately bound, and cannot execute SQL.
for text in ["O'Reilly","' OR 1=1 --","'; DROP TABLE urls;--"]:
 for browser in ['chrome','firefox','safari','orion']:
  got=call({'op':'query','db':str(database(browser)[0]),'browser':browser,'text':text});assert 'rows'in got
assert connections['chrome'][1].execute('select count(*) from urls').fetchone()[0]==len(titles)
p.stdin.close();assert p.wait(timeout=5)==0
print(f"Native real SQLite parity: {len(records)} original-SQL + actual-adapter cases; {len(oracle['paths'])} factories, {len(oracle['iniResults'])} INI and 12 intentional quote cases passed")
