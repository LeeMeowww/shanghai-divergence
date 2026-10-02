import csv
import io
import os
import threading
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import store
from .core import DataError, screen, compare
from .collector import start_refresh, scheduler


@asynccontextmanager
async def lifespan(app):
    store.init()
    last = store.latest_job()
    if last and last['state'] == 'running':
        last.update(state='failed', message='上次采集被中断，旧数据已保留，可重新更新')
        store.save_job(last)
    stop = threading.Event()
    if os.environ.get('DIVERGENCE_AUTO_REFRESH','1') == '1':
        threading.Thread(target=scheduler,args=(stop,),daemon=True).start()
    yield
    stop.set()


app = FastAPI(title='沪市背离观察台',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])


@lru_cache(maxsize=3)
def cached_batch(batch):
    return store.load(batch)


def snapshot(batch):
    meta = store.latest_meta() if not batch else None
    bid = batch or (meta['id'] if meta else None)
    data = cached_batch(bid) if bid else None
    if data is None:
        raise HTTPException(409,'尚无可用行情批次，请更新行情并检查采集状态')
    return data


@app.get('/api/status')
def status():
    meta = store.latest_meta()
    data = snapshot(meta['id']) if meta else None
    return dict(batch=meta,job=store.latest_job(),stock_count=len(data['stocks']) if data else 0,
                downloaded=len(data['bars']) if data else 0,errors=len(data['errors']) if data else 0,
                first_date=min(data['index']) if data and data['index'] else None,
                calendar_end=max(data['calendar']) if data else None)


@app.post('/api/refresh',status_code=202)
def refresh(request:Request):
    origin = request.headers.get('origin')
    if origin and origin not in ('http://127.0.0.1:8765','http://localhost:8765'):
        raise HTTPException(403,'只允许本机页面启动更新')
    return start_refresh()


def run_screen(batch_id, end, window, mode, direction, board, stock_min, index_min, search, sort, descending):
    try:
        return screen(snapshot(batch_id),str(end) if end else None,window,mode,direction,board,stock_min,index_min,search,sort,descending)
    except DataError as e:
        raise HTTPException(409,str(e))


@app.get('/api/screen')
def get_screen(batch_id:str|None=None,end:date|None=None,window:int=Query(3,ge=2,le=60),
               mode:Literal['strict','cumulative']='strict', direction:Literal['down','up','both']='down',
               board:Literal['all','main','star']='all', stock_min:float=Query(0,ge=0,le=1000,allow_inf_nan=False),
               index_min:float=Query(0,ge=0,le=1000,allow_inf_nan=False),search:str='',
               sort:Literal['gap','stock_return','index_return','code','close','opposite_days']='gap',descending:bool=True):
    return run_screen(batch_id,end,window,mode,direction,board,stock_min,index_min,search,sort,descending)


@app.get('/api/stocks/{code}/comparison')
def comparison(code:str,batch_id:str,end:date,window:int=Query(3,ge=2,le=60)):
    s=snapshot(batch_id)
    stock=next((x for x in s['stocks'] if x['code']==code),None)
    if not stock:
        raise HTTPException(404,'股票不在当前清单内')
    result=run_screen(batch_id,end,window,'cumulative','both','all',0,0,'','gap',True)
    try:
        if code in s['errors']:
            raise DataError('该股票行情采集失败')
        c=compare(s['bars'].get(code,{}),s['index'],result['dates'])
    except DataError as e:
        raise HTTPException(409,str(e))
    return dict(**stock,**c,batch_id=batch_id,base_date=result['base_date'],end_date=result['end_date'],window=window)


@app.get('/api/export')
def export(batch_id:str,end:date|None=None,window:int=Query(3,ge=2,le=60),
           mode:Literal['strict','cumulative']='strict',direction:Literal['down','up','both']='down',
           board:Literal['all','main','star']='all',stock_min:float=Query(0,ge=0,le=1000,allow_inf_nan=False),
           index_min:float=Query(0,ge=0,le=1000,allow_inf_nan=False),search:str='',
           sort:Literal['gap','stock_return','index_return','code','close','opposite_days']='gap',descending:bool=True):
    r=run_screen(batch_id,end,window,mode,direction,board,stock_min,index_min,search,sort,descending)
    out=io.StringIO(newline='')
    writer=csv.writer(out)
    writer.writerow(['代码','名称','板块','收盘价','股票涨跌幅%','指数涨跌幅%','差值(百分点)','反向天数','规则','基准日','截止日','数据批次','数据完整','有效/候选','数据源'])
    for x in r['results']:
        name=x['name']
        if name.startswith(('=','+','-','@','\t','\r')):
            name="'"+name
        writer.writerow([x['code'],name,'主板' if x['board']=='main' else '科创板',x['close'],x['stock_return'],x['index_return'],x['gap'],f"{x['opposite_days']}/{window}",x['rule'],r['base_date'],r['end_date'],r['batch_id'],not r['incomplete'],f"{r['valid_count']}/{r['candidate_count']}",r['source']])
    return Response(out.getvalue().encode('utf-8-sig'),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="divergence-{r["end_date"]}.csv"'})


dist=store.ROOT/'dist'
if dist.exists():
    app.mount('/',StaticFiles(directory=dist,html=True),name='web')
