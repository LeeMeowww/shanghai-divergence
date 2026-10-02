"""Deterministic screening; no network or wall-clock dependencies."""
import math
from collections import Counter


class DataError(ValueError):
    pass


def compare(stock, index, dates):
    if any(d not in stock for d in dates):
        raise DataError("缺少交易日行情或上市时间不足")
    bars = [stock[d] for d in dates]
    if any(not math.isfinite(b['adjusted']) or b['adjusted'] <= 0 or
           not math.isfinite(b['close']) or b['close'] <= 0 for b in bars):
        raise DataError("价格无效")
    if any(not math.isfinite(b['volume']) or b['volume'] <= 0 for b in bars[1:]):
        raise DataError("窗口内停牌或无成交")
    p0, i0 = bars[0]['adjusted'], index[dates[0]]
    series = []
    for n, d in enumerate(dates):
        sr = (bars[n]['adjusted'] / bars[n-1]['adjusted'] - 1) * 100 if n else None
        ir = (index[d] / index[dates[n-1]] - 1) * 100 if n else None
        series.append(dict(date=d, stock=(bars[n]['adjusted']/p0-1)*100,
                           index=(index[d]/i0-1)*100, stock_day=sr, index_day=ir,
                           opposite=bool(n and sr * ir < 0), close=bars[n]['close']))
    sr, ir = series[-1]['stock'], series[-1]['index']
    strict_down = all(s['index_day'] > 0 and s['stock_day'] < 0 for s in series[1:])
    strict_up = all(s['index_day'] < 0 and s['stock_day'] > 0 for s in series[1:])
    return dict(stock_return=sr, index_return=ir, gap=abs(sr-ir), close=bars[-1]['close'],
                opposite_days=sum(s['opposite'] for s in series), series=series,
                strict_down=strict_down, strict_up=strict_up)


def matches(c, mode, direction, stock_min, index_min):
    sr, ir = c['stock_return'], c['index_return']
    if abs(sr) < stock_min or abs(ir) < index_min:
        return False
    down = ir > 0 and sr < 0
    up = ir < 0 and sr > 0
    if mode == 'strict':
        down, up = c['strict_down'], c['strict_up']
    return (direction in ('down', 'both') and down) or (direction in ('up', 'both') and up)


def screen(snapshot, end=None, window=3, mode='strict', direction='down',
           board='all', stock_min=0, index_min=0, search='', sort='gap', descending=True):
    if not 2 <= window <= 60 or mode not in ('strict', 'cumulative') or direction not in ('down','up','both'):
        raise DataError('筛选参数无效')
    cutoff = end or snapshot['end']
    if not snapshot['calendar'] or cutoff > max(snapshot['calendar']):
        raise DataError('所选日期超出已知交易日历范围')
    if cutoff > snapshot['end']:
        # A later date is acceptable only if it contains no uncollected trading day.
        if any(snapshot['end'] < d <= cutoff for d in snapshot['calendar']):
            raise DataError('所选日期尚无完整收盘数据，请先更新或选择较早日期')
    trading = [d for d in snapshot['calendar'] if d <= cutoff and d <= snapshot['end']]
    dates = trading[-(window+1):]
    if len(dates) != window+1:
        raise DataError('该区间历史数据不足，需要 N+1 个收盘价')
    index = snapshot['index']
    if any(d not in index or not math.isfinite(index[d]) or index[d] <= 0 for d in dates):
        raise DataError('指数交易日数据缺失，不能计算该区间')
    results, excluded = [], []
    candidates = [s for s in snapshot['stocks'] if board == 'all' or s['board'] == board]
    valid = 0
    for s in candidates:
        try:
            if s['code'] in snapshot['errors']:
                raise DataError('行情采集失败')
            c = compare(snapshot['bars'].get(s['code'], {}), index, dates)
        except DataError as e:
            excluded.append(dict(code=s['code'], name=s['name'], reason=str(e)))
            continue
        valid += 1
        if matches(c, mode, direction, stock_min, index_min):
            results.append({**s, **{k:v for k,v in c.items() if k != 'series'},
                            'rule': '每日严格背离' if mode == 'strict' else '区间累计背离'})
    total_matches = len(results)
    results = [r for r in results if search.casefold() in (r['code']+r['name']).casefold()]
    results.sort(key=lambda r: (r[sort], r['code']), reverse=descending)
    return dict(batch_id=snapshot['id'], source=snapshot['source'], updated_at=snapshot['updated_at'],
                base_date=dates[0], start_date=dates[1], end_date=dates[-1], dates=dates,
                window=window, index_return=(index[dates[-1]]/index[dates[0]]-1)*100,
                candidate_count=len(candidates), valid_count=valid, total_matches=total_matches,
                incomplete=bool(excluded), excluded=excluded,
                exclusion_counts=dict(Counter(e['reason'] for e in excluded)), results=results)
