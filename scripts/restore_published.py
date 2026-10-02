"""Preserve newer deployed data on source-only pushes; never silently regress."""
import json,os,re,urllib.request,urllib.error
from pathlib import Path
out=Path(__file__).resolve().parents[1]/'public-pages'/'data'
repo=os.environ['GITHUB_REPOSITORY']
owner,name=repo.split('/')
base=f'https://{owner.lower()}.github.io/{name}/data/'
try:
    with urllib.request.urlopen(base+'manifest.json',timeout=30) as r:remote=json.load(r)
except urllib.error.HTTPError as e:
    if e.code==404:
        print('First deployment: use bundled verified market snapshot.');raise SystemExit(0)
    raise
local=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
if (remote['end'],remote['updated_at'])>(local['end'],local['updated_at']):
    name=remote['file']
    if not re.fullmatch(r'market-[a-f0-9]+\.json\.gz',name):raise ValueError('Invalid market filename')
    with urllib.request.urlopen(base+name,timeout=60) as r:body=r.read(50_000_001)
    if len(body)>50_000_000:raise ValueError('Market snapshot exceeds size limit')
    (out/name).write_bytes(body)
    (out/'manifest.json').write_text(json.dumps(remote,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Restored published snapshot:',remote['end'])
