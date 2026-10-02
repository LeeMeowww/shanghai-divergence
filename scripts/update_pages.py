"""One finite Actions collection, with atomic publication and failure preservation."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.deps'),str(ROOT/'scripts')]
from backend import store
from backend.provider import Provider,expected_end
from backend.collector import start_refresh
from export_pages import export

store.init()
old_path=ROOT/'public-pages'/'data'/'manifest.json'
old=json.loads(old_path.read_text(encoding='utf-8')) if old_path.exists() else None
due=expected_end(Provider().calendar())
if old and old['end']>=due:
    print('Published market is current:',old['end']);sys.exit(0)
start_refresh()
while True:
    job=store.latest_job()
    if job['state']!='running':break
    print(job['stage'],job['done'],'/',job['total'],flush=True)
    time.sleep(15)
if job['state']!='complete':raise RuntimeError('全市场更新未完成，停止发布并保留上次网站；请查看采集日志')
s=store.load(job['batch_id'])
if not s or s['end']<due:raise RuntimeError('采集结果尚未覆盖预期交易日，停止发布')
export(s)
