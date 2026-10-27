/* Actual pinned renderer functions, evaluated with hooks/timers/IPC injected. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),base=path.join(root,'.qa/v1/node_modules');
const esbuild=require(path.join(base,'esbuild'));
const jsx=(type,props,key)=>({type,props:props||{},key});
class Hooks {
 constructor(){this.slots=[];this.pending=[];this.i=0;this.dirty=false;this.timers=new Map();this.timer=0;}
 react(){const h=this;const memo=(fn,deps)=>{let i=h.i++;const old=h.slots[i];if(!old||!deps||!deps.every((d,n)=>Object.is(d,old.deps?.[n]))){h.slots[i]={value:fn(),deps};}return h.slots[i].value;};return {useState(initial){const i=h.i++;if(!h.slots[i])h.slots[i]={value:typeof initial==='function'?initial():initial};return [h.slots[i].value,v=>{const next=typeof v==='function'?v(h.slots[i].value):v;if(!Object.is(next,h.slots[i].value)){h.slots[i].value=next;h.dirty=true;}}];},useRef(initial){const i=h.i++;return (h.slots[i]??={value:{current:initial}}).value;},useMemo:memo,useCallback:(fn,deps)=>memo(()=>fn,deps),useEffect(fn,deps){const i=h.i++;const old=h.slots[i];if(!old||!deps||!deps.every((d,n)=>Object.is(d,old.deps?.[n]))){h.pending.push(()=>{old?.cleanup?.();h.slots[i]={deps,cleanup:fn()};});}}};}
 render(component,props){let rounds=0;do{this.dirty=false;this.i=0;this.tree=component(props);const effects=this.pending.splice(0);for(const fn of effects)fn();assert(++rounds<20,'hooks did not stabilize');}while(this.dirty);return this.tree;}
 tick(){const tasks=[...this.timers.values()];this.timers.clear();for(const fn of tasks)fn();}
}
function moduleAt(file,h,ipc={}) {
 const react=h.react();const mod={exports:{}};
 const req=id=>{if(id==='react')return {...react,default:react};if(id==='react/jsx-runtime')return {jsx,jsxs:jsx,Fragment:'Fragment'};if(id.includes('extensionSessionRefresh'))return {startSessionRefresh:()=>()=>{}};if(id.includes('raycast-api')&&!id.includes('list-runtime'))return {ExtensionRuntimeSurface:'Surface'};if(id.includes('primitives'))return {Button:'Button',Message:'Message',Hint:'Hint',HintBar:'HintBar',Kbd:'Kbd',ViewHeader:'ViewHeader',cx:(...args)=>args.filter(Boolean).join(' ')};if(id.includes('Markdown'))return {Markdown:'Markdown'};if(id.includes('detail-runtime'))return {MetadataItem:'MetadataItem',MetadataSidebar:'MetadataSidebar'};if(id.includes('colorConverter'))return {buildColorConversionResults:()=>[]};throw Error('unapproved renderer import '+id);};
 const window={tezbar:{extensionDisposeSession:async()=>{},...ipc},setTimeout(fn){const id=++h.timer;h.timers.set(id,fn);return id;},clearTimeout(id){h.timers.delete(id);}};
 const context=vm.createContext({module:mod,exports:mod.exports,require:req,window,Error,console:{log(){},error(){}},setTimeout:window.setTimeout,clearTimeout:window.clearTimeout});
 new vm.Script(esbuild.transformSync(fs.readFileSync(file,'utf8'),{loader:'tsx',format:'cjs',jsx:'automatic',target:'es2022'}).code+(file.endsWith('list-runtime.tsx')?'\nmodule.exports.__qa={parseListRows,RowIcon,Accessory}':''),{filename:path.basename(file)}).runInContext(context,{timeout:2000});return mod.exports;
}
function find(node,type){if(!node||typeof node!=='object')return;if(Array.isArray(node)){for(const n of node){const r=find(n,type);if(r)return r;}}if(node.type===type)return node;return find(node.props?.children,type);}
function view(text='',sessionId='one'){return {ok:true,mode:'view',sessionId,generation:'g',extensionId:'com.tezbar.native.generic',commandName:'lookup',title:'Lookup',root:{type:'List',props:{__hasServerSearch:true,filtering:false,searchText:text},children:[]},actions:[]};}
const micro=async()=>{for(let i=0;i<5;i++)await Promise.resolve();};
async function run(patched){
 const prefix=patched?'patched-':'host-';const ph=new Hooks(),lh=new Hooks(),requests=[],actionRequests=[];let initial=view();
 const parent=moduleAt(path.join(root,'.qa/contracts',prefix+'ExtensionRuntimeView.tsx'),ph,{extensionSearchTextChanged:args=>new Promise((resolve,reject)=>requests.push({args,resolve,reject})),extensionInvokeAction:args=>new Promise((resolve,reject)=>actionRequests.push({args,resolve,reject}))}).default;
 const list=moduleAt(path.join(root,'.qa/contracts',prefix+'list-runtime.tsx'),lh).ListRuntime;
 const parentRender=()=>{ph.render(parent,{initial,onBack(){}});return find(ph.tree,'Surface');};
 let surface=parentRender();function listRender(){surface=parentRender();lh.render(list,{...surface.props,onRunPrimaryAction(){},onOpenActions(){},onLoadMore(){}});return find(lh.tree,'input');}
 function type(text){listRender().props.onChange({target:{value:text}});listRender();}
 listRender();type('A');if(!patched)lh.tick();assert.equal(requests.length,1);type('B');
 // Resolve A during the original renderer's debounce window.
 requests[0].resolve(view('A'));await micro();listRender();
 if(patched){assert.equal(find(lh.tree,'input').props.value,'B');assert.equal(ph.slots[0].value.root.props.searchText,'');assert.equal(requests.length,2);}else{assert.equal(find(lh.tree,'input').props.value,'A');}
 if(!patched)return;
 // A/B/A ownership, empty intermediate and invalid recovery.
 requests[1].resolve(view('B'));await micro();listRender();assert.equal(find(lh.tree,'input').props.value,'B');
 type('A');type('');type('A');const tail=requests.slice(-3);tail[2].resolve(view('A'));tail[0].resolve(view('stale'));tail[1].resolve({ok:false,message:'stale error'});await micro();listRender();assert.equal(ph.slots[0].value.root.props.searchText,'A');assert.equal(ph.slots[1].value,null);
 type('invalid');requests.at(-1).resolve({ok:false,message:'owned failure'});await micro();parentRender();assert.equal(ph.slots[1].value,'owned failure');type('valid');requests.at(-1).resolve(view('valid'));await micro();listRender();assert.equal(ph.slots[1].value,null);
 const before=ph.slots[0].value;const unchanged=surface.props.onSearchTextChanged('same');requests.at(-1).resolve({ok:true,mode:'unchanged'});await unchanged;parentRender();assert.equal(ph.slots[0].value,before);
 const reject=surface.props.onSearchTextChanged('error');requests.at(-1).reject(new Error('transport failed'));await reject;parentRender();assert(ph.slots[1].value.includes('transport failed'));
 const old=surface.props.onSearchTextChanged('old');const pending=requests.at(-1);initial=view('new session','two');const next=parentRender();assert.equal(next.key,'two:g');pending.resolve(view('old'));await old;parentRender();assert.equal(ph.slots[0].value.sessionId,'two');assert.equal(ph.slots[0].value.root.props.searchText,'new session');
 // Old action replies/errors and foreign unchanged cannot replace a newer query.
 surface=parentRender();const action=surface.props.onInvokeAction('owned');const pendingAction=actionRequests.at(-1);const newSearch=surface.props.onSearchTextChanged('fresh');requests.at(-1).resolve(view('fresh','two'));await newSearch;pendingAction.resolve(view('stale action','two'));await action;parentRender();assert.equal(ph.slots[0].value.root.props.searchText,'fresh');
 surface=parentRender();const staleError=surface.props.onInvokeAction('owned');const pendingError=actionRequests.at(-1);const nextSearch=surface.props.onSearchTextChanged('newest');requests.at(-1).resolve(view('newest','two'));await nextSearch;pendingError.reject(new Error('old action error'));await staleError;parentRender();assert.equal(ph.slots[1].value,null);
 const stable=ph.slots[0].value;surface=parentRender();const foreign=surface.props.onInvokeAction('foreign');actionRequests.at(-1).resolve({ok:true,mode:'unchanged'});await foreign;parentRender();assert.equal(ph.slots[0].value,stable);
 // Exact list parser consumes native icons/accessories/action IDs without invention.
 const parseHooks=new Hooks();const symbols=moduleAt(path.join(root,'.qa/contracts',prefix+'list-runtime.tsx'),parseHooks);
 const props={root:{type:'List',props:{__hasServerSearch:true},children:[{type:'List.Item',props:{id:'0_tv',title:'Owned',subtitle:'https://owned.invalid',icon:{source:'Icon.Star'},accessories:[{tag:{value:'7',color:'yellow'}}],actionIds:['owned']}}]},title:'Lookup',commandName:'lookup',actions:[{id:'owned',title:'Open in Browser'}],onBack(){},onRunPrimaryAction(){},onOpenActions(){},onSearchTextChanged(){},onLoadMore(){}};parseHooks.render(symbols.ListRuntime,props);assert(find(parseHooks.tree,'input'));
 const parsed=symbols.__qa.parseListRows({type:'List',children:[{type:'List.Item',props:{id:'0_tv',title:'Owned',icon:{source:'Icon.Star',tooltip:'Top visited'},accessories:[{tag:{value:'7',color:'yellow'},tooltip:'Visit count'}],actionIds:['open']}}]});
 const icon=symbols.__qa.RowIcon({row:parsed[0]});const renderedIcon=icon.type(icon.props);assert.equal(renderedIcon.props.title,'Top visited');
 const accessory=symbols.__qa.Accessory({accessory:parsed[0].accessories[0]});assert.equal(accessory.props.title,'Visit count');assert(accessory.props.className.includes('yellow'));
 const recents=symbols.__qa.Accessory({accessory:{tag:{value:'2026-01-01',color:'magenta'},tooltip:'Last visited'}});assert(recents.props.className.includes('fuchsia'));

}
(async()=>{await run(false);await run(true);console.log('Actual pinned renderer: original debounce restoration reproduced; UNAPPLIED patch passes A/B/A, empty/invalid/error recovery, rejected RPC, cross-session, unchanged and native row rendering');})().catch(e=>{console.error(e);process.exit(1)});
