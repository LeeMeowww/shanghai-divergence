import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get('DIVERGENCE_DB', str(ROOT / 'data' / 'market.sqlite3')))


@contextmanager
def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    try:
        with con:
            yield con
    finally:
        con.close()


def init():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, created TEXT, state TEXT, end_date TEXT, source TEXT);
        CREATE TABLE IF NOT EXISTS stocks(batch TEXT, code TEXT, name TEXT, board TEXT, PRIMARY KEY(batch,code));
        CREATE TABLE IF NOT EXISTS bars(batch TEXT, code TEXT, day TEXT, close REAL, adjusted REAL, volume REAL, PRIMARY KEY(batch,code,day));
        CREATE TABLE IF NOT EXISTS calendar(batch TEXT, day TEXT, PRIMARY KEY(batch,day));
        CREATE TABLE IF NOT EXISTS errors(batch TEXT, code TEXT, detail TEXT, PRIMARY KEY(batch,code));
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT);
        ''')


def save_snapshot(s):
    with connect() as c:
        c.execute('INSERT INTO batches VALUES(?,?,?,?,?)', (s['id'],s['updated_at'],'ready',s['end'],s['source']))
        c.executemany('INSERT INTO stocks VALUES(?,?,?,?)', [(s['id'],x['code'],x['name'],x['board']) for x in s['stocks']])
        c.executemany('INSERT INTO calendar VALUES(?,?)', [(s['id'],d) for d in s['calendar']])
        rows = [(s['id'],'sh000001',d,v,v,1) for d,v in s['index'].items()]
        rows.extend((s['id'],code,d,b['close'],b['adjusted'],b['volume']) for code,bs in s['bars'].items() for d,b in bs.items())
        c.executemany('INSERT INTO bars VALUES(?,?,?,?,?,?)', rows)
        c.executemany('INSERT INTO errors VALUES(?,?,?)', [(s['id'],k,v) for k,v in s['errors'].items()])


def latest_meta():
    with connect() as c:
        r = c.execute("SELECT * FROM batches WHERE state='ready' ORDER BY created DESC LIMIT 1").fetchone()
        return dict(r) if r else None


def load(batch=None):
    with connect() as c:
        r = c.execute('SELECT * FROM batches WHERE id=?', (batch,)).fetchone() if batch else c.execute("SELECT * FROM batches WHERE state='ready' ORDER BY created DESC LIMIT 1").fetchone()
        if not r:
            return None
        bid = r['id']
        s = dict(id=bid, updated_at=r['created'], end=r['end_date'], source=r['source'], bars={}, index={}, errors={})
        s['stocks'] = [dict(x) for x in c.execute('SELECT code,name,board FROM stocks WHERE batch=?',(bid,))]
        s['calendar'] = [x['day'] for x in c.execute('SELECT day FROM calendar WHERE batch=? ORDER BY day',(bid,))]
        s['errors'] = {x['code']:x['detail'] for x in c.execute('SELECT * FROM errors WHERE batch=?',(bid,))}
        for b in c.execute('SELECT * FROM bars WHERE batch=?',(bid,)):
            if b['code'] == 'sh000001':
                s['index'][b['day']] = b['close']
            else:
                s['bars'].setdefault(b['code'],{})[b['day']] = dict(close=b['close'], adjusted=b['adjusted'], volume=b['volume'])
        return s


def save_job(j):
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO jobs VALUES(?,?)',(j['id'],json.dumps(j,ensure_ascii=False)))


def latest_job():
    with connect() as c:
        r = c.execute('SELECT payload FROM jobs ORDER BY rowid DESC LIMIT 1').fetchone()
        return json.loads(r[0]) if r else None
