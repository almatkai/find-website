const {load}=require('./oracle.cjs'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const result=input.map(v=>{
 const {moduleAt}=load();const factory=moduleAt('src/factory.ts').Factory.create(v.browser,'Default');
 try {return {rows:[...v.top.map((r,i)=>factory.getTopVisitedAdapter().adapt(r,i)),...v.recent.map((r,i)=>factory.getRecentsAdapter().adapt(r,i))].map(r=>({key:r.key,title:r.title,url:r.url,icon:r.icon.value,tooltip:r.icon.tooltip,accessory:r.accessories[0].tag.value??'',accessoryTooltip:r.accessories[0].tooltip,color:r.accessories[0].tag.color}))};}catch(e){return {error:true};}
});
fs.writeFileSync(process.argv[3],JSON.stringify(result));
