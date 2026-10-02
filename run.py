"""Local launcher. Compiled web assets are included; Node is not needed to run."""
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
if (ROOT/'.deps').exists():
    sys.path.insert(0,str(ROOT/'.deps'))

if __name__=='__main__':
    import threading
    import time
    import webbrowser
    import urllib.request
    import uvicorn
    url='http://127.0.0.1:8765'
    try:
        import json
        existing=json.load(urllib.request.urlopen(url+'/api/status',timeout=1))
        if 'batch' in existing and 'job' in existing:
            if '--no-browser' not in sys.argv:
                webbrowser.open(url)
            print('沪市背离观察台已运行：'+url)
            sys.exit(0)
    except (OSError,ValueError):
        pass
    def open_when_ready():
        for _ in range(40):
            try:
                urllib.request.urlopen(url+'/api/status',timeout=1)
                webbrowser.open(url)
                return
            except Exception:
                time.sleep(.5)
    if '--no-browser' not in sys.argv:
        threading.Thread(target=open_when_ready,daemon=True).start()
    uvicorn.run('backend.app:app',host='127.0.0.1',port=8765,log_level='info')
