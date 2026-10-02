"""Free public market data via AKShare. One source per saved batch."""
import math
import time
from datetime import datetime, timedelta, timezone
import requests

SH = timezone(timedelta(hours=8))
_request = requests.sessions.Session.request


def bounded_request(self, method, url, **kwargs):
    if kwargs.get('timeout') is None:
        kwargs['timeout'] = (8, 18)
    return _request(self, method, url, **kwargs)


requests.sessions.Session.request = bounded_request


def retry(fn):
    for attempt in range(4):
        try:
            return fn()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


class Provider:
    source = 'AKShare / 东方财富（股票后复权与原始收盘价、指数） / 上交所股票清单'

    def __init__(self):
        import akshare as ak
        self.ak = ak
        self.stock_source = 'eastmoney'
        self.index_source = '东方财富'

    def choose_stock_source(self, start, end):
        try:
            for adjust in ('','hfq'):
                f=self.ak.stock_zh_a_hist(symbol='600000',period='daily',start_date=start.replace('-',''),end_date=end.replace('-',''),adjust=adjust,timeout=8)
                if f.empty:
                    raise ValueError('东方财富样本为空')
        except Exception:
            self.stock_source='tencent'
        stock_name='腾讯证券' if self.stock_source=='tencent' else '东方财富'
        self.source=f'AKShare / {stock_name}（股票后复权与原始收盘价） / {self.index_source}（上证综指） / 上交所（股票清单）'

    def calendar(self):
        frame = retry(self.ak.tool_trade_date_hist_sina)
        return sorted(set(str(x)[:10] for x in frame['trade_date']))

    def stocks(self):
        out = []
        for symbol, board in [('主板A股','main'),('科创板','star')]:
            frame = retry(lambda: self.ak.stock_info_sh_name_code(symbol=symbol))
            for r in frame.to_dict('records'):
                code = str(r['证券代码']).zfill(6)
                if code.startswith(('600','601','603','605','688')):
                    out.append(dict(code=code, name=str(r['证券简称']), board=board))
        if not out:
            raise ValueError('未获取到沪市 A 股清单')
        return out

    def index(self, start, end):
        try:
            frame = self.ak.stock_zh_index_daily_em(symbol='sh000001',start_date=start.replace('-',''),end_date=end.replace('-',''))
            if frame.empty:
                raise ValueError('指数数据为空')
        except Exception:
            frame = retry(lambda:self.ak.stock_zh_index_daily_tx(symbol='sh000001',start_date=start.replace('-',''),end_date=end.replace('-','')))
            self.index_source='腾讯证券'
        return {str(r['date'])[:10]:float(r['close']) for r in frame.to_dict('records') if start <= str(r['date'])[:10] <= end}

    def stock(self, code, start, end):
        args = dict(symbol=code, period='daily',start_date=start.replace('-',''),end_date=end.replace('-',''))
        if self.stock_source=='tencent':
            return self.tencent_window(code,start,end)
        else:
            raw = retry(lambda:self.ak.stock_zh_a_hist(**args, adjust='', timeout=18))
            adj = retry(lambda:self.ak.stock_zh_a_hist(**args, adjust='hfq', timeout=18))
        adjusted = {str(r['日期'])[:10]:float(r['收盘']) for r in adj.to_dict('records')}
        out = {}
        for r in raw.to_dict('records'):
            d = str(r['日期'])[:10]
            if d in adjusted:
                b = dict(close=float(r['收盘']),adjusted=adjusted[d],volume=float(r['成交量']))
                if all(math.isfinite(v) for v in b.values()):
                    out[d] = b
        if not out:
            raise ValueError('无有效日线或复权数据')
        return out

    def tencent_window(self, code, start, end):
        """Same public endpoint used by AKShare, fetched once per complete window.

        The endpoint may ignore the requested start date: explicitly filter dates.
        Fetching both series anew prevents mixing adjustment vintages.
        """
        symbol='sh'+code
        def fetch(adjust):
            r=requests.get('https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get',
                           params={'param':f'{symbol},day,{start},{end},640,{adjust}'},timeout=(8,18))
            r.raise_for_status()
            data=r.json()['data'][symbol]
            rows=data.get(adjust+'day',data.get('day',[]))
            return {row[0]:row for row in rows if start<=row[0]<=end}
        raw=retry(lambda:fetch(''))
        adjusted=retry(lambda:fetch('hfq'))
        out={}
        for d,r in raw.items():
            if d not in adjusted:
                continue
            b=dict(close=float(r[2]),adjusted=float(adjusted[d][2]),volume=float(r[5]))
            if all(math.isfinite(v) for v in b.values()):
                out[d]=b
        if not out:
            raise ValueError('无有效日线或复权数据')
        return out


def expected_end(calendar, now=None):
    now = now or datetime.now(SH)
    today = now.date().isoformat()
    # Only publish a session after the planned end-of-day collection time.
    eligible = [d for d in calendar if d < today or (d == today and now.hour >= 18)]
    if not eligible:
        raise ValueError('交易日历为空')
    if max(calendar) < today:
        raise ValueError('交易日历未覆盖当前日期，无法确定最新交易日')
    return max(eligible)
