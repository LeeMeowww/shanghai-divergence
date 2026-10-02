import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from . import store
from .provider import Provider, SH, expected_end

LOCK = threading.Lock()


def start_refresh():
    if not LOCK.acquire(blocking=False):
        return store.latest_job()
    job = dict(id=uuid.uuid4().hex, state='running', stage='读取交易日历', done=0,total=0,success=0,failed=0,
               started_at=datetime.now(SH).isoformat(), message='正在连接免费行情源')
    try:
        store.save_job(job)
        threading.Thread(target=collect,args=(job,),daemon=True).start()
    except Exception:
        LOCK.release()
        raise
    return job


def collect(job):
    started = time.monotonic()
    try:
        p = Provider()
        calendar = p.calendar()
        end = expected_end(calendar)
        start = (datetime.fromisoformat(end)-timedelta(days=380)).date().isoformat()
        job.update(stage='采集上证综指',message=f'读取截至 {end} 的指数日线')
        store.save_job(job)
        index = p.index(start,end)
        dates = [d for d in calendar if start <= d <= end]
        if any(d not in index for d in dates):
            raise ValueError('指数行情未完整覆盖预期交易日，保留旧批次，请稍后重试')
        job.update(stage='读取沪市股票清单',message='获取主板与科创板 A 股清单')
        store.save_job(job)
        stocks = p.stocks()
        job.update(stage='验证个股行情源',message='检测东方财富与腾讯证券接口')
        store.save_job(job)
        p.choose_stock_source(start,end)
        job.update(stage='采集沪市股票',total=len(stocks),end_date=end)
        store.save_job(job)
        snap = dict(id=job['id'],end=end,updated_at='',source=p.source,stocks=stocks,
                    calendar=[d for d in calendar if d>=start],index=index,bars={},errors={})
        consecutive = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            for offset in range(0,len(stocks),4):
                futures={pool.submit(p.stock,s['code'],start,end):s for s in stocks[offset:offset+4]}
                for f in as_completed(futures):
                    s=futures[f];code=s['code']
                    job['message']=f"{code} {s['name']} · {p.stock_source}"
                    try:
                        snap['bars'][code]=f.result()
                        job['success']+=1
                        consecutive=0
                    except Exception as e:
                        snap['errors'][code]=str(e)[:600]
                        job['failed']+=1
                        consecutive+=1
                    job['done']+=1
                    job['elapsed_seconds']=round(time.monotonic()-started,1)
                    store.save_job(job)
                if consecutive>=8:
                    for pending in stocks[offset+4:]:
                        snap['errors'][pending['code']]='连续请求失败，采集已中止'
                    break
                time.sleep(.2)
        if not snap['bars']:
            raise ValueError('免费行情源未返回有效股票数据，旧批次仍保留。'+next(iter(snap['errors'].values()),''))
        snap['updated_at'] = datetime.now(SH).isoformat()
        store.save_snapshot(snap)
        job.update(state='partial' if snap['errors'] else 'complete',stage='采集结束',batch_id=snap['id'],
                   message=f"成功 {job['success']} / {job['total']}；未采集 {len(snap['errors'])}")
    except Exception as e:
        stage=job['stage']
        message=str(e) if isinstance(e,ValueError) else '免费行情源连接失败，请稍后重试；已有数据仍可使用。'
        job.update(state='failed',stage=stage+'失败',message=message[:400],error_detail=str(e)[:1200])
    finally:
        job['elapsed_seconds'] = round(time.monotonic()-started,1)
        job['finished_at'] = datetime.now(SH).isoformat()
        try:
            store.save_job(job)
        finally:
            LOCK.release()


def scheduler(stop):
    attempted = None
    while not stop.is_set():
        now = datetime.now(SH)
        today = now.date().isoformat()
        snapshot = store.load()
        calendar = snapshot['calendar'] if snapshot else []
        # On startup validate the calendar online if no usable cached calendar exists.
        try:
            due = expected_end(calendar,now) if calendar else None
        except ValueError:
            due = None
        key = due or (today + ('-after18' if now.hour>=18 else '-before18'))
        if attempted != key and not LOCK.locked() and (not snapshot or due is None or snapshot['end'] < due):
            attempted = key
            start_refresh()
        stop.wait(45)
