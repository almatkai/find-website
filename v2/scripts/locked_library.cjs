/* Execute real locked @raycast/utils SQL helper with every producer replaced. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../.qa/v1/node_modules');const esbuild=require(path.join(base,'esbuild'));const map=JSON.parse(fs.readFileSync(path.join(base,'@raycast/utils/dist/main.js.map')));const source=map.sourcesContent[map.sources.indexOf('src/sql-utils.ts')];assert(source);
function load({available=true,busy=false,missing=false,permission=false}={}){
 const calls=[];let opens=0;const mod={exports:{}};const records=[{id:1,title:'Owned',url:'https://owned.invalid'}];
 class DatabaseSync{constructor(p,options){calls.push(['database',p,options]);assert.equal(options.readOnly,true);assert.equal(options.open,false);}open(){calls.push(['open']);if(busy&&opens++===0){let e=new Error('busy');e.errcode=5;throw e;}}prepare(sql){calls.push(['prepare',sql]);return {all(){return records;}};}close(){calls.push(['close']);}}
 const req=id=>{
  if(id==='node:fs')return {existsSync:()=>!missing};
  if(id==='node:fs/promises')return Object.fromEntries(['copyFile','mkdir','writeFile'].map(k=>[k,async(...args)=>calls.push([k,...args])]));
  if(id==='node:os')return {tmpdir:()=>'/owned/temp'};
  if(id==='node:path')return path.posix;
  if(id==='node:child_process')return {spawn:(...args)=>{calls.push(['spawn',...args]);return {};}};
  if(id==='./helpers')return {hash:()=> 'ownedhash'};
  if(id==='./exec-utils')return {getSpawnedPromise:()=>Promise.resolve({}),getSpawnedResult:async()=>[{error:undefined,exitCode:permission?1:0,signal:null},JSON.stringify(records),permission?'authorization denied':'']};
  if(id==='node:sqlite'){if(!available)throw Error('no native producer');return {DatabaseSync};}
  throw Error('unapproved locked helper import '+id);
 };
 const js=esbuild.transformSync(source,{loader:'ts',format:'cjs',target:'es2015',supported:{'dynamic-import':false}}).code;
 new vm.Script(js).runInContext(vm.createContext({module:mod,exports:mod.exports,require:req,Error,process:{platform:'darwin'}}),{timeout:2000});return {api:mod.exports,calls,records};
}
(async()=>{
 let t=load();assert.deepEqual(await t.api.baseExecuteSQL('/owned/history','SELECT owned'),t.records);assert.equal(t.calls.filter(c=>c[0]==='close').length,1);
 t=load({available:false});assert.equal(JSON.stringify(await t.api.baseExecuteSQL('/owned/history','SELECT owned')),JSON.stringify(t.records));assert.equal(JSON.stringify(t.calls.find(c=>c[0]==='spawn').slice(1,3)),JSON.stringify(['sqlite3',['--json','--readonly','/owned/history','SELECT owned']]));
 t=load({busy:true});await t.api.baseExecuteSQL('/owned/history','SELECT owned');assert.equal(t.calls.filter(c=>c[0]==='copyFile').length,1);assert.equal(t.calls.filter(c=>c[0]==='writeFile'&&c[2]==='').length,2);
 t=load({missing:true});await assert.rejects(t.api.baseExecuteSQL('/owned/missing','SELECT owned'),/does not exist/);assert.equal(t.calls.length,0);
 t=load({available:false,permission:true});await assert.rejects(t.api.baseExecuteSQL('/owned/history','SELECT owned'),e=>e.name==='PermissionError');
 console.log('Actual locked SQL helper: native producer, CLI fallback, readonly options, close, missing/permission errors and busy-copy WAL-loss behavior verified with closed producers');
})().catch(e=>{console.error(e);process.exit(1)});
