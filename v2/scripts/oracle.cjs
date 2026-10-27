/* Closed V1 VM. Producers replaced before evaluating trusted source. */
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const base = path.resolve(__dirname, '../.qa/v1');
const esbuild = require(path.join(base,'node_modules/esbuild'));
const ini = require(path.join(base,'node_modules/ini'));
const assert = require('node:assert/strict');
const own = path.resolve(__dirname, '../..');
const fakeHome='/owned/home', local='/owned/local', roaming='/owned/roaming';
function load({platform='darwin',browser='chrome',profile='Default',iniText='[Profile0]\nPath=Profiles/first\n[InstallABC]\nDefault=Profiles/default',exists=true,repair=false,emptyEnv=false}={}) {
  const cache=new Map(), calls=[],logs=[],states=[],present=new Set();let slot=0;
  const mk=(type,props,key)=>({type:typeof type==='object'&&type instanceof String?String(type):type,props:props||{},key});
  const react={createElement:mk,useState(initial){let i=slot++;states[i]=initial;return [initial,v=>states[i]=v]}};
  const ray={Icon:new Proxy({}, {get:(_,key)=>`Icon.${key}`}),Color:{Yellow:'yellow',Magenta:'magenta'},environment:{supportPath:'/owned/support'},getPreferenceValues:()=>({browser,profile}),List:Object.assign('List',{Item:'List.Item',EmptyView:'List.EmptyView'}),Action:{OpenInBrowser:'Action.OpenInBrowser'},ActionPanel:'ActionPanel'};
  const fakeFS={existsSync(p){calls.push(['exists',p]);return exists;},readFileSync(p){calls.push(['ini',p]);return iniText;},mkdirSync(p){present.add(p);calls.push(['mkdir',p]);},copyFileSync(src,dst){calls.push(['copy',src,dst]);if(present.has(dst)&&!repair){let e=new Error('owned EISDIR');e.code='EISDIR';throw e;}}};
  function moduleAt(file){
    if(cache.has(file))return cache.get(file).exports;
    let mod={exports:{}};cache.set(file,mod);
    const source=fs.readFileSync(path.join(own,file),'utf8');
    const js=esbuild.transformSync(source,{loader:file.endsWith('tsx')?'tsx':'ts',format:'cjs',jsx:'automatic',target:'es2022'}).code;
    const req=id=>{
      if(id==='@raycast/api')return ray;
      if(id==='react')return react;
      if(id==='react/jsx-runtime')return {jsx:mk,jsxs:mk,Fragment:'Fragment'};
      if(id==='@raycast/utils')return {executeSQL:async(db,sql)=>{calls.push(['sql',db,sql]);return [{id:1,title:null,url:'https://owned.invalid/',visitCount:7,lastVisitTime:'2026-01-01 00:00:00',visitTime:'2026-01-01 00:00:00',lastVisitDate:'2026-01-01 00:00:00'}];}};
      if(id==='ini')return ini;
      if(id==='fs'||id==='node:fs')return fakeFS;
      if(id==='os')return {homedir:()=>fakeHome};
      if(id==='path')return platform==='win32'?path.win32:path.posix;
      if(id.startsWith('.')){let f=path.posix.normalize(path.posix.join(path.posix.dirname(file),id));let ext=['.ts','.tsx'].find(e=>fs.existsSync(path.join(own,f+e)));if(!ext)throw Error('Unknown own import');return moduleAt(f+ext);}
      throw Error('Unapproved source import: '+id);
    };
    const context=vm.createContext({module:mod,exports:mod.exports,require:req,process:{platform,env:emptyEnv?{}:{LOCALAPPDATA:local,APPDATA:roaming}},console:{log:(...a)=>logs.push(a)},React:react});
    new vm.Script(js,{filename:file}).runInContext(context,{timeout:2000});return mod.exports;
  }
  return {moduleAt,calls,states,logs};
}
async function main(){
 const builders={chrome:'Chrome',orion:'Orion',safari:'Safari',firefox:'Firefox',zen:'Zen',arc:'Arc',brave:'Brave',vivaldi:'Vivaldi',opera:'Opera',edge:'Edge'};
 const queries=[];const texts=['','example','foo bar',' foo  bar ','%','_','é','É','雪','😀','\t','null','https://','mixed CASE','date zero','date negative','date extreme'];
 for(const [browser,cls]of Object.entries(builders)){
  const {moduleAt}=load();const m=moduleAt('src/query-builder.ts');const b=new m[cls+'QueryBuilder']();
  for(const text of texts)queries.push({browser,text,top:b.queryTopVisited(3,text),recent:b.queryRecents(3,text)});
 }
 const paths=[];
 for(const platform of ['darwin','win32'])for(const browser of Object.keys(builders))for(const profile of (browser==='chrome'?['Default','Profile 2','Nested/Profile','../Other','/absolute-profile']:['Profile 2']))for(const emptyEnv of [false,true]){
  const {moduleAt,calls}=load({platform,browser,profile,emptyEnv});const factory=moduleAt('src/factory.ts').Factory.create(browser,profile);
  paths.push({platform,browser,profile,emptyEnv,path:factory.getSrc(),iniCalls:calls.filter(c=>c[0]==='ini')});
  const command=moduleAt('src/find.tsx').default();paths.at(-1).installation=calls.find(c=>c[0]==='exists')?.[1]??null;assert.equal(command.type,'List');assert.equal(command.props.filtering,platform==='win32'&&['orion','safari','zen'].includes(browser)?undefined:false);
 }
 const iniCases=['[Profile0]\nName=a\nPath=Profiles/a','[General]\nStartWithLastProfile=1\n[Profile0]\nPath=Profiles/a','[Profile0]\nPath=Profiles/a\n[InstallB]\nDefault="Profiles/b"','[InstallB]\nDefault=Profiles/b\n[InstallA]\nDefault=Profiles/a','[Profile0]\nPath="Profiles/a # x"','[Profile0]\nPath=Profiles/a\\#x ; comment','[Profile0]\nPath=Profiles/a\nPath=Profiles/b','[Profile0]\nPath=/absolute/path','[Profile0]\nIsRelative=0\nPath=../outside','', '[Install.A]\nDefault=x', '[Install\\.A]\nDefault=y', '[1]\nPath=numeric\n[Profile0]\nPath=other', '[Profile0]\nPath[]=a\nPath[]=b', '[Profile0]\nPath=null', '[Profile0]\nPath=true', '[Profile0]\nPath=\'\"quoted\"\'', ' [Profile0]\nPath=ignored', '[__proto__]\nPath=bad\n[Profile0]\nPath=good', 'root=null\n[Profile0]\nPath=x'];
 const iniResults=iniCases.map(text=>{const {moduleAt}=load({iniText:text});try{return {text,path:moduleAt('src/factory.ts').Factory.create('firefox','ignored').getSrc()};}catch(e){return {text,error:true};}});
 const {moduleAt,calls}=load();const command=moduleAt('src/find.tsx').default();assert.throws(()=>command.props.onSearchTextChange('owned'),{code:'EISDIR'});assert.equal(calls.filter(c=>c[0]==='sql').length,0);
 const fixed=load({repair:true});fixed.moduleAt('src/find.tsx').default().props.onSearchTextChange('owned');await new Promise(setImmediate);await new Promise(setImmediate);
 const sqlCalls=fixed.calls.filter(c=>c[0]==='sql');assert.equal(sqlCalls.length,2);assert.match(sqlCalls[0][2],/order by visit_count desc/);assert.match(sqlCalls[1][2],/order by last_visit_time desc/);
 const rendered=fixed.states[0];assert.equal(rendered.length,2);for(const item of rendered){assert.equal(item.type,'List.Item');assert.equal(item.props.title,'');assert.equal(item.props.actions.props.children.type,'Action.OpenInBrowser');assert.equal(item.props.actions.props.children.props.url,'https://owned.invalid/');assert.equal(Object.keys(item.props.actions.props.children.props).join(','),'url');}
 assert.equal(rendered[0].key,'0_tv');assert.equal(rendered[1].key,'0_r');
 // Missing source leaves existing data; V2 deliberately clears it to avoid stale ownership.
 const missing=load({exists:false});const empty=missing.moduleAt('src/find.tsx').default();assert.equal(empty.props.children.type,'List.EmptyView');
 fs.writeFileSync(path.join(__dirname,'../.qa/oracle.json'),JSON.stringify({queries,paths,iniResults,flow:rendered,copyDefect:'EISDIR reproduced with owned FS',actions:'OpenInBrowser only, no app selection or copy'},null,2));
 console.log(`V1 closed VM: ${queries.length} query pairs, ${paths.length} factories/installation states, ${iniResults.length} INI cases, real Step order/actions and EISDIR passed`);
}
if (require.main===module) main().catch(e=>{console.error(e);process.exit(1)});
module.exports={load};
