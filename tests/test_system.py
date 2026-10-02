import copy
import csv
import io
import os
import uuid
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from backend.core import screen, DataError
from backend.provider import expected_end, SH

DAYS=['2026-09-22','2026-09-23','2026-09-24','2026-09-25']


def sample(stock=(100,99,98,97),index=(100,101,102,103)):
    return dict(id=uuid.uuid4().hex,updated_at='2026-09-25T18:10:00+08:00',end=DAYS[-1],source='TEST ONLY',
                calendar=DAYS+['2026-09-28','2026-10-09'],index=dict(zip(DAYS,index)),
                stocks=[dict(code='600000',name='测试股票',board='main')],errors={},
                bars={'600000':{d:dict(close=p,adjusted=p,volume=100) for d,p in zip(DAYS,stock)}})


def test_strict_and_cumulative():
    s=sample()
    for mode in ['strict','cumulative']:
        r=screen(s,mode=mode)
        assert r['results'][0]['opposite_days']==3
        assert r['base_date']==DAYS[0]
        assert r['results'][0]['gap']==pytest.approx(6)


def test_interval_only():
    s=sample(stock=(100,102,99,97))
    assert not screen(s)['results']
    assert len(screen(s,mode='cumulative')['results'])==1


def test_alternating_is_not_strict_even_with_both_directions():
    s=sample(stock=(100,99,101,98),index=(100,101,99,102))
    assert not screen(s,direction='both')['results']
    assert screen(s,mode='cumulative')['results'][0]['opposite_days']==3


def test_reverse_direction_and_thresholds():
    s=sample(stock=(100,101,102,103),index=(100,99,98,97))
    assert screen(s,direction='up')['results']
    assert not screen(s)['results']
    assert not screen(s,direction='up',stock_min=4)['results']


def test_flat_missing_and_suspended():
    assert not screen(sample(stock=(100,100,98,97)))['results']
    s=sample(); del s['bars']['600000'][DAYS[1]]
    r=screen(s);assert r['valid_count']==0 and r['incomplete']
    s=sample();s['bars']['600000'][DAYS[2]]['volume']=0
    assert '停牌' in screen(s)['excluded'][0]['reason']
    s=sample();s['bars']['600000'][DAYS[1]]['adjusted']=float('nan')
    assert screen(s)['valid_count']==0


def test_weekend_and_missing_index():
    assert screen(sample(),end='2026-09-27')['end_date']=='2026-09-25'
    with pytest.raises(DataError):screen(sample(),end='2026-09-28')
    s=sample();del s['index'][DAYS[1]]
    with pytest.raises(DataError):screen(s)
    with pytest.raises(DataError):screen(sample(),window=4)


def test_corporate_action_uses_adjusted_price():
    s=sample(stock=(100,101,102,103))
    s['bars']['600000'][DAYS[-1]]['close']=50
    # The raw-price drop must not become a false down-divergence signal.
    assert not screen(s)['results']


def test_calendar_cutoff_and_holiday():
    cal=DAYS+['2026-09-28','2026-09-29','2026-09-30','2026-10-09']
    assert expected_end(cal,datetime(2026,9,28,17,tzinfo=SH))=='2026-09-25'
    assert expected_end(cal,datetime(2026,9,28,18,tzinfo=SH))=='2026-09-28'
    assert expected_end(cal,datetime(2026,10,1,18,tzinfo=SH))=='2026-09-30'


@pytest.fixture
def client(monkeypatch):
    from backend import store
    from backend.app import app,cached_batch
    path=store.ROOT/'data'/('test-'+uuid.uuid4().hex+'.sqlite3')
    monkeypatch.setattr(store,'DB',path)
    monkeypatch.setenv('DIVERGENCE_AUTO_REFRESH','0')
    cached_batch.cache_clear()
    with TestClient(app) as c:
        yield c,store
    cached_batch.cache_clear()
    for p in path.parent.glob(path.name+'*'):
        p.unlink(missing_ok=True)


def test_api_export_and_comparison_same_batch(client):
    c,store=client
    assert c.get('/api/screen').status_code==409
    s=sample();store.save_snapshot(s)
    query=f"batch_id={s['id']}&window=3"
    r=c.get('/api/screen?'+query).json()
    assert r['results'][0]['gap']==pytest.approx(6)
    d=c.get('/api/stocks/600000/comparison?'+query+'&end=2026-09-25').json()
    assert d['gap']==r['results'][0]['gap']
    rows=list(csv.reader(io.StringIO(c.get('/api/export?'+query).content.decode('utf-8-sig'))))
    assert float(rows[1][6])==d['gap']
    assert rows[1][11]==s['id']
    assert c.get('/api/screen?window=1').status_code==422
    assert c.get('/api/screen?stock_min=NaN').status_code==422
    assert c.get('/api/screen?end=bad').status_code==422
    assert c.post('/api/refresh',headers={'origin':'https://untrusted.example'}).status_code==403


def test_partial_and_failed_refresh_keep_old_batch(client):
    c,store=client
    old=sample();store.save_snapshot(old)
    store.save_job(dict(id='failed',state='failed',message='network unavailable'))
    assert c.get('/api/status').json()['batch']['id']==old['id']
    newer=copy.deepcopy(old);newer['id']='partial';newer['updated_at']='2026-09-25T19:10:00+08:00'
    newer['stocks'].append(dict(code='688001',name='缺失股票',board='star'))
    newer['errors']['688001']='timeout'
    store.save_snapshot(newer)
    r=c.get('/api/screen').json()
    assert r['incomplete'] and r['candidate_count']==2 and r['valid_count']==1
    assert c.get('/api/screen?batch_id='+old['id']).json()['candidate_count']==1


def test_tencent_adapter_filters_dates_and_aligns_adjustments(monkeypatch):
    from backend.provider import Provider
    p=Provider.__new__(Provider)
    replies=iter([
        {'data':{'sh600000':{'day':[['2020-01-01','1','1','1','1','10'],['2026-09-30','9','9.48','10','9','120']]}}},
        {'data':{'sh600000':{'hfqday':[['2020-01-01','2','2','2','2','10'],['2026-09-30','130','132.13','133','130','120']]}}}
    ])
    class Reply:
        def raise_for_status(self):pass
        def json(self):return next(replies)
    monkeypatch.setattr('backend.provider.requests.get',lambda *a,**kw:Reply())
    bars=p.tencent_window('600000','2025-09-15','2026-09-30')
    assert len(bars)==1 and bars['2026-09-30']['adjusted']==132.13
    assert bars['2026-09-30']['close']==9.48


def test_collector_publishes_partial_atomically(client,monkeypatch):
    _,store=client
    from backend import collector
    s=sample()
    class FakeProvider:
        source='TEST ONLY'
        stock_source='test'
        def calendar(self):return s['calendar']
        def index(self,start,end):return s['index']
        def stocks(self):return s['stocks']+[dict(code='688001',name='失败样本',board='star')]
        def choose_stock_source(self,*args):pass
        def stock(self,code,*args):
            if code=='688001':raise ConnectionError('offline')
            return s['bars'][code]
    monkeypatch.setattr(collector,'Provider',FakeProvider)
    monkeypatch.setattr(collector,'expected_end',lambda _:DAYS[-1])
    monkeypatch.setattr(collector.time,'sleep',lambda _:None)
    job=dict(id='collect-test',done=0,total=0,success=0,failed=0,state='running',stage='test')
    collector.LOCK.acquire()
    collector.collect(job)
    assert store.latest_job()['state']=='partial'
    assert store.load()['errors']['688001']=='offline'
    assert screen(store.load())['valid_count']==1


def test_out_of_calendar_and_board_filter():
    with pytest.raises(DataError):screen(sample(),end='2030-01-01')
    assert screen(sample(),board='star')['candidate_count']==0
