// Only this application's route is attached to this Worker. No visitor cookies are forwarded.
export const PREFIX='/shanghai-divergence';
const ORIGIN='https://leemeowww.github.io/shanghai-divergence/';
const json=(value,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
let updateCache;
async function updateState(upstream){
 if(updateCache&&Date.now()-updateCache.at<120000)return updateCache.value;
 try{
  const r=await upstream('https://api.github.com/repos/LeeMeowww/shanghai-divergence/actions/workflows/pages.yml/runs?per_page=1',{headers:{Accept:'application/vnd.github+json','User-Agent':'shanghai-divergence'},signal:AbortSignal.timeout(5000)});
  if(!r.ok)throw Error('status');
  const run=(await r.json()).workflow_runs?.[0];
  const value=run?{state:run.status==='completed'?run.conclusion:'running',at:run.updated_at}:null;
  updateCache={at:Date.now(),value};return value;
 }catch{return null}
}

export async function handle(request,env,upstream=fetch){
 const url=new URL(request.url);
 if(url.pathname!==PREFIX&&!url.pathname.startsWith(PREFIX+'/'))return new Response('Not found',{status:404});
 if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405,headers:{Allow:'GET, HEAD'}});
 if(url.pathname===PREFIX){url.pathname+='/';return Response.redirect(url.href,308)}
 const path=url.pathname.slice(PREFIX.length+1);
 if(path==='api/market'||path==='data/manifest.json'){
  try{
   const r=await upstream(ORIGIN+'data/manifest.json?t='+Date.now(),{headers:{Accept:'application/json'},signal:AbortSignal.timeout(15000),cf:{cacheTtl:0}});
   if(!r.ok)throw Error('upstream');
   const m=await r.json();
   if(!/^[a-f0-9]+$/.test(m.id)||!/^market-[a-f0-9]+\.json\.gz$/.test(m.file)||!/^\d{4}-\d{2}-\d{2}$/.test(m.end))throw Error('manifest');
   return json({...m,update:await updateState(upstream)});
  }catch{return json({detail:'后台行情暂时不可用，请稍后重试。'},503)}
 }
 if(/^data\/market-[a-f0-9]+\.json\.gz$/.test(path)){
  try{
   const r=await upstream(ORIGIN+path,{signal:AbortSignal.timeout(30000)});
   const headers=new Headers(r.headers);headers.delete('set-cookie');
   headers.set('Cache-Control',r.ok?'public, max-age=31536000, immutable':'no-store');
   headers.set('X-Content-Type-Options','nosniff');
   return new Response(request.method==='HEAD'?null:r.body,{status:r.status,headers});
  }catch{return json({detail:'行情批次下载失败，请稍后重试。'},503)}
 }
 if(path.startsWith('api/')||path.startsWith('data/'))return json({detail:'接口不存在'},404);
 const assetUrl=new URL(request.url);assetUrl.pathname='/'+(path||'index.html');
 const asset=await env.ASSETS.fetch(new Request(assetUrl,{method:request.method}));
 const response=new Response(asset.body,asset);response.headers.set('X-Content-Type-Options','nosniff');
 if(!path||path==='index.html')response.headers.set('Cache-Control','no-cache');
 return response;
}
export default {fetch(request,env){return handle(request,env)}};
