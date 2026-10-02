import {STATIC_MODE} from './runtime';
export {STATIC_MODE};
export async function api<T>(path:string,options?:RequestInit):Promise<T>{
 if(STATIC_MODE){const mod=await import('./static-api');return mod.request(path) as Promise<T>}
 const r=await fetch(path,options);if(!r.ok){const e=await r.json().catch(()=>({detail:'服务响应异常'}));throw new Error(typeof e.detail==='string'?e.detail:'参数无效，请检查日期和数值范围')}return r.json();
}
export async function exportCsv(path:string){const mod=await import('./static-api');await mod.download(path)}
