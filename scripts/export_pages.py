"""Export only market fields, never local paths, credentials, or job errors."""
import json,sys,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.deps')]
from backend import store

def export(snapshot=None, target=None):
    store.init()
    s=snapshot or store.load()
    if not s:raise RuntimeError('没有可发布行情批次')
    out=Path(target) if target else ROOT/'public-pages'/'data'
    out.mkdir(parents=True,exist_ok=True)
    s['errors']={code:'行情采集失败' for code in s['errors']}
    name='market-'+s['id']+'.json.gz'
    content=json.dumps(s,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    (out/name).write_bytes(gzip.compress(content,mtime=0))
    m={k:s[k] for k in ('id','end','updated_at','source')}
    m.update(file=name,stock_count=len(s['stocks']),downloaded=len(s['bars']),errors=len(s['errors']),first_date=min(s['index']),calendar_end=max(s['calendar']))
    (out/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(m,ensure_ascii=False))
    return m

if __name__=='__main__':export()
