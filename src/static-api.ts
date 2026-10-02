import {screen,compare,options,csv,type Snapshot} from './static-engine';
type Manifest={id:string;end:string;updated_at:string;source:string;file:string;stock_count:number;downloaded:number;errors:number;first_date:string;calendar_end:string};
let current:Manifest|undefined;
const snapshots=new Map<string,Promise<Snapshot>>();
async function manifest(){const r=await fetch(new URL('data/manifest.json',document.baseURI),{cache:'no-store'});if(!r.ok)throw Error('尚无已发布行情，请查看 GitHub Actions 更新状态');current=await r.json();return current!}
async function load(id?:string){if(!current)await manifest();const key=id||current!.id;if(!snapshots.has(key)){if(key!==current!.id)throw Error('该历史批次已更新，请刷新行情后重新筛选');const file=current!.file;snapshots.set(key,(async()=>{const r=await fetch(new URL('data/'+file,document.baseURI));if(!r.ok)throw Error('行情快照下载失败，请刷新重试');const bytes=new Uint8Array(await r.arrayBuffer());const json=bytes[0]===31&&bytes[1]===139?await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).text():new TextDecoder().decode(bytes);const s=JSON.parse(json) as Snapshot;if(s.id!==key)throw Error('行情批次不一致，请刷新重试');return s})().catch(e=>{snapshots.delete(key);throw e}))}return snapshots.get(key)!}
export async function request(path:string):Promise<unknown>{
 const u=new URL(path,'https://local.invalid'),q=u.searchParams;
 if(u.pathname==='/api/status'||u.pathname==='/api/refresh'){
 const m=await manifest(),job={id:m.id,state:m.errors?'partial':'complete',stage:'已发布行情',done:m.downloaded,total:m.stock_count,success:m.downloaded,failed:m.errors,message:`GitHub Actions 定时更新 · 行情截至 ${m.end}；刷新按钮只读取已发布数据`};
 if(u.pathname==='/api/refresh')return job;
 return {batch:{id:m.id,end_date:m.end,created:m.updated_at},job,stock_count:m.stock_count,downloaded:m.downloaded,errors:m.errors,first_date:m.first_date,calendar_end:m.calendar_end};}
 const s=await load(q.get('batch_id')||undefined),p=options(q);
 if(u.pathname==='/api/screen')return screen(s,p);
 const match=u.pathname.match(/^\/api\/stocks\/(\d{6})\/comparison$/);
 if(match){const x=s.stocks.find(x=>x.code===match[1]);if(!x)throw Error('股票不在当前清单内');if(x.code in s.errors)throw Error('该股票行情采集失败');const r=screen(s,p);return {...x,...compare(s.bars[x.code]||{},s.index,r.dates),batch_id:s.id,base_date:r.base_date,end_date:r.end_date,window:p.window}}
 throw Error('不支持的操作');
}
export async function download(path:string){const q=new URL(path,'https://local.invalid').searchParams,s=await load(q.get('batch_id')||undefined),r=screen(s,options(q));const url=URL.createObjectURL(new Blob([csv(r)],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`divergence-${r.end_date}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
