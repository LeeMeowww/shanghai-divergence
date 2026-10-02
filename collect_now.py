import sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'.deps'))
from backend import store
from backend.collector import start_refresh
store.init()
print(start_refresh(),flush=True)
time.sleep(1)
last=-1
while store.latest_job()['state']=='running':
    j=store.latest_job()
    if j['done']//100>last:
        print(j,flush=True)
        last=j['done']//100
    time.sleep(2)
print(store.latest_job(),flush=True)
