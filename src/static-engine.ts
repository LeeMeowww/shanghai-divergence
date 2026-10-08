export type Bar = {close:number;adjusted:number;volume:number};
export type Stock = {code:string;name:string;board:string};
export type Snapshot={id:string;end:string;updated_at:string;source:string;calendar:string[];index:Record<string,number>;stocks:Stock[];bars:Record<string,Record<string,Bar>>;errors:Record<string,string>};
export type Options={end?:string;window:number;mode:string;direction:string;board:string;stock_min:number;index_min:number;search:string;sort:string;descending:boolean};
export function marketFreshness(s:Pick<Snapshot,'calendar'|'end'>,now=new Date()){
 const beijing=new Date(now.getTime()+8*3600000),today=beijing.toISOString().slice(0,10);
 const cutoff=beijing.getUTCHours()>=18?today:new Date(beijing.getTime()-86400000).toISOString().slice(0,10);
 const expected=s.calendar.filter(d=>d<=cutoff).at(-1);
 return {expected,stale:!!expected&&s.end<expected,calendarExpired:!s.calendar.length||today>s.calendar.at(-1)!};
}
export function compare(stock:Record<string,Bar>,index:Record<string,number>,dates:string[]){
 if(dates.some(d=>!stock[d]))throw Error('缺少交易日行情或上市时间不足');
 const bars=dates.map(d=>stock[d]);
 if(bars.some(b=>!Number.isFinite(b.adjusted)||b.adjusted<=0||!Number.isFinite(b.close)||b.close<=0))throw Error('价格无效');
 if(bars.slice(1).some(b=>!Number.isFinite(b.volume)||b.volume<=0))throw Error('窗口内停牌或无成交');
 const series=dates.map((date,n)=>{const stock_day=n?(bars[n].adjusted/bars[n-1].adjusted-1)*100:null,index_day=n?(index[date]/index[dates[n-1]]-1)*100:null;return {date,stock:(bars[n].adjusted/bars[0].adjusted-1)*100,index:(index[date]/index[dates[0]]-1)*100,stock_day,index_day,opposite:!!(n&&stock_day!*index_day!<0),close:bars[n].close}});
 const sr=series.at(-1)!.stock,ir=series.at(-1)!.index;
 return {stock_return:sr,index_return:ir,gap:Math.abs(sr-ir),close:bars.at(-1)!.close,opposite_days:series.filter(s=>s.opposite).length,series,strict_down:series.slice(1).every(s=>s.index_day!>0&&s.stock_day!<0),strict_up:series.slice(1).every(s=>s.index_day!<0&&s.stock_day!>0)};
}
export function matches(c:ReturnType<typeof compare>,p:Options){
 if(Math.abs(c.stock_return)<p.stock_min||Math.abs(c.index_return)<p.index_min)return false;
 const down=p.mode==='strict'?c.strict_down:c.index_return>0&&c.stock_return<0;
 const up=p.mode==='strict'?c.strict_up:c.index_return<0&&c.stock_return>0;
 return (['down','both'].includes(p.direction)&&down)||(['up','both'].includes(p.direction)&&up);
}
export function screen(s:Snapshot,p:Options){
 if(!Number.isInteger(p.window)||p.window<2||p.window>60||!['strict','cumulative'].includes(p.mode)||!['down','up','both'].includes(p.direction)||![p.stock_min,p.index_min].every(n=>Number.isFinite(n)&&n>=0))throw Error('筛选参数无效');
 const cutoff=p.end||s.end;
 if(!s.calendar.length||cutoff>s.calendar.at(-1)!)throw Error('所选日期超出已知交易日历范围');
 if(s.calendar.some(d=>s.end<d&&d<=cutoff))throw Error('所选日期尚无完整收盘数据，请刷新已发布行情或选择较早日期');
 const dates=s.calendar.filter(d=>d<=cutoff&&d<=s.end).slice(-(p.window+1));
 if(dates.length!==p.window+1)throw Error('该区间历史数据不足，需要 N+1 个收盘价');
 if(dates.some(d=>!Number.isFinite(s.index[d])||s.index[d]<=0))throw Error('指数交易日数据缺失，不能计算该区间');
 const candidates=s.stocks.filter(x=>p.board==='all'||x.board===p.board);
 const excluded:{code:string;name:string;reason:string}[]=[],results:(Stock&Omit<ReturnType<typeof compare>,'series'>&{rule:string})[]=[];
 let valid=0;
 for(const x of candidates){let c;try{if(x.code in s.errors)throw Error('行情采集失败');c=compare(s.bars[x.code]||{},s.index,dates)}catch(e){excluded.push({code:x.code,name:x.name,reason:(e as Error).message});continue}valid++;
 if(matches(c,p)){const {series,...rest}=c;results.push({...x,...rest,rule:p.mode==='strict'?'每日严格背离':'区间累计背离'})}}
 const total=results.length,filtered=results.filter(x=>(x.code+x.name).toLowerCase().includes(p.search.toLowerCase()));
 filtered.sort((a,b)=>{const av=a[p.sort as keyof typeof a],bv=b[p.sort as keyof typeof b];const primary=av!<bv!?-1:av!>bv!?1:0;const second=a.code<b.code?-1:a.code>b.code?1:0;return (primary||second)*(p.descending?-1:1)});
 const exclusion_counts:Record<string,number>={};excluded.forEach(x=>{exclusion_counts[x.reason]=(exclusion_counts[x.reason]||0)+1});
 return {batch_id:s.id,source:s.source,updated_at:s.updated_at,base_date:dates[0],start_date:dates[1],end_date:dates.at(-1)!,dates,window:p.window,index_return:(s.index[dates.at(-1)!]/s.index[dates[0]]-1)*100,candidate_count:candidates.length,valid_count:valid,total_matches:total,incomplete:!!excluded.length,excluded,exclusion_counts,results:filtered};
}
export function options(q:URLSearchParams):Options{return {end:q.get('end')||undefined,window:Number(q.get('window')||3),mode:q.get('mode')||'strict',direction:q.get('direction')||'down',board:q.get('board')||'all',stock_min:Number(q.get('stock_min')||0),index_min:Number(q.get('index_min')||0),search:q.get('search')||'',sort:q.get('sort')||'gap',descending:q.get('descending')!=='false'}};
export function csv(result:ReturnType<typeof screen>){
 const rows:unknown[][]=[['代码','名称','板块','收盘价','股票涨跌幅%','指数涨跌幅%','差值(百分点)','反向天数','规则','基准日','截止日','数据批次','数据完整','有效/候选','数据源']];
 for(const r of result.results){const name=/^[=+\-@\t\r]/.test(r.name)?"'"+r.name:r.name;rows.push([r.code,name,r.board==='main'?'主板':'科创板',r.close,r.stock_return,r.index_return,r.gap,`${r.opposite_days}/${result.window}`,r.rule,result.base_date,result.end_date,result.batch_id,!result.incomplete,`${result.valid_count}/${result.candidate_count}`,result.source])}
 return '\ufeff'+rows.map(row=>row.map(x=>'"'+String(x).replaceAll('"','""')+'"').join(',')).join('\r\n')+'\r\n';
}

