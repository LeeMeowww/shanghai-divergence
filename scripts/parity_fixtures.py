"""Generate deterministic Python results for independent browser-engine comparison."""
import sys,json,random
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.deps')]
from backend.core import screen
from datetime import date,timedelta
random.seed(42)
dates=[(date(2026,1,1)+timedelta(days=i)).isoformat() for i in range(65)]
fixtures=[]
for case in range(12):
    s=dict(id=str(case),end=dates[-1],updated_at='2026-03-06',source='TEST',calendar=dates,index={},stocks=[],bars={},errors={})
    idx=100.
    for d in dates:
        idx*=1+random.choice([-.015,0,.01]);s['index'][d]=idx
    for n in range(12):
        code=str(600000+n);s['stocks'].append(dict(code=code,name='测试'+code,board='main' if n%2 else 'star'))
        value=100.;bs={}
        for d in dates:
            value*=1+random.choice([-.02,0,.01]);bs[d]=dict(close=value,adjusted=value,volume=100)
        s['bars'][code]=bs
    if case%3==0:s['bars']['600000'].pop(dates[-2])
    if case%3==1:s['bars']['600001'][dates[-2]]['volume']=0
    if case%3==2:s['errors']['600002']='timeout'
    for mode in ('strict','cumulative'):
      for direction in ('down','up','both'):
        for window in (3,5,20,60):
            p=dict(end=s['end'],window=window,mode=mode,direction=direction,board='all',stock_min=0,index_min=0,search='',sort='gap',descending=True)
            fixtures.append(dict(snapshot=s,options=p,expected=screen(s,**p)))
out=ROOT/'.test-artifacts';out.mkdir(exist_ok=True)
(out/'parity.json').write_text(json.dumps(fixtures,ensure_ascii=False),encoding='utf-8')
print('Generated',len(fixtures),'cross-language cases')
