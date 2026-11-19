#!/usr/bin/env python3
"""Wendling FX: MARKET / LEVELS charts (1080x1920 PNG): 4-hour candles of the last two weeks with last week's high and low,
yesterday's high and low and this week's open. Data: wendlingfx.com/data/market.json and market-h1.json (from cTrader).
Usage: python3 tools/make_levels.py OUT_DIR [SYMBOL ...]   (default XAUUSD EURUSD). Prints {"sym", "file", "caption"} per chart.
Candles in TradingView's default colours. Levels only, never a buy or sell call."""
import datetime as dt, json, os, random, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import make_card as mc
from make_card import unb, inter, W, CX, WHITE, MUTED, LIME, PANEL, LINE, DIM
from brand import header, TYPES
UP, DN, ORANGE, GREY = (38, 166, 154), (239, 83, 80), (255, 138, 61), (200, 200, 200)
NAMES = {'XAUUSD': 'Gold', 'EURUSD': 'EUR/USD', 'USDCAD': 'USD/CAD', 'GBPUSD': 'GBP/USD', 'USDJPY': 'USD/JPY'}
def get(n):
    with urllib.request.urlopen(f'https://wendlingfx.com/data/{n}?t={random.random()}', timeout=30) as r: return json.loads(r.read().decode())
def fmt(sym, p): return f'{p:,.0f}' if sym in ('XAUUSD',) else (f'{p:.3f}' if sym.endswith('JPY') else f'{p:.4f}')
def chart(sym, daily, h1, out):
    c4 = {}
    for t, o, h, l, c in h1:
        k = (t // 240) * 240
        if k not in c4: c4[k] = [k, o, h, l, c]
        else: x = c4[k]; x[2] = max(x[2], h); x[3] = min(x[3], l); x[4] = c
    c4 = [c4[k] for k in sorted(c4)][-60:]
    today = dt.datetime.now(dt.timezone.utc).date(); mon = today - dt.timedelta(days=today.weekday())
    days = [(dt.date.fromisoformat(b['d']), b) for b in daily]
    pd = [b for d, b in days if d < today][-1]
    pw = [b for d, b in days if mon - dt.timedelta(days=7) <= d < mon]
    L = [(max(b['h'] for b in pw), 'PWH', ORANGE), (min(b['l'] for b in pw), 'PWL', ORANGE), (pd['h'], 'PDH', GREY), (pd['l'], 'PDL', GREY)]
    t_open = (int(dt.datetime(mon.year, mon.month, mon.day, tzinfo=dt.timezone.utc).timestamp()) - 7200) // 60
    wo = [{'o': b[1]} for b in h1 if b[0] >= t_open][:1]
    if wo: L.append((wo[0]['o'], 'Open', LIME))
    TYPES['levels'] = ('MARKET', 'LEVELS  /  ' + NAMES.get(sym, sym).upper(), ORANGE)
    img, d = mc.canvas(); header(d, 'levels')
    title = NAMES.get(sym, sym) + ': levels on the chart'
    mc.tc(d, 330, title, mc.fit(d, title, 60, 820), WHITE); mc.tc(d, 410, '4-hour candles, last two weeks', inter(36, 'Medium'), MUTED)
    X0, X1, Y0, Y1 = 70, 840, 500, 1460
    d.rounded_rectangle([X0 - 20, Y0 - 20, X1 + 190, Y1 + 20], radius=20, fill=PANEL, outline=LINE, width=2)
    hi = max(max(b[2] for b in c4), max(p for p, _, _ in L)); lo = min(min(b[3] for b in c4), min(p for p, _, _ in L)); pad = (hi - lo) * 0.04; hi += pad; lo -= pad
    Y = lambda p: Y1 - (Y1 - Y0) * (p - lo) / (hi - lo)
    cw = (X1 - X0) / len(c4)
    for i, (t, o, h, l, c) in enumerate(c4):
        x = X0 + cw * i + cw / 2; col = UP if c >= o else DN
        d.line([(x, Y(h)), (x, Y(l))], fill=col, width=2)
        y1, y2 = sorted([Y(o), Y(c)]); d.rectangle([x - cw * 0.32, y1, x + cw * 0.32, max(y2, y1 + 2)], fill=col)
    items = sorted([(Y(p), p, nm, col) for p, nm, col in L]); ly = []
    for y, *_ in items: ly.append(max(y, ly[-1] + 50) if ly else y)
    for (y, p, nm, col), yy in zip(items, ly):
        x = X0
        while x < X1: d.line([(x, y), (min(x + 14, X1), y)], fill=col, width=3); x += 24
        if abs(yy - y) > 2: d.line([(X1, y), (X1 + 10, yy)], fill=col, width=2)
        d.rounded_rectangle([X1 + 10, yy - 22, X1 + 180, yy + 22], radius=8, fill=col)
        d.text((X1 + 20, yy - 16), f'{nm} {fmt(sym, p)}', font=inter(26 if sym == 'XAUUSD' else 22, 'SemiBold'), fill=(10, 10, 10))
    ty = 1510
    for k, v in [('PWH / PWL', 'last week high and low'), ('PDH / PDL', 'yesterday high and low'), ('Open', 'this week open')]:
        d.text((90, ty), k, font=inter(34, 'SemiBold'), fill=WHITE); d.text((380, ty), v, font=inter(34, 'Regular'), fill=MUTED); ty += 52
    f = unb(56); w1 = d.textlength('wendling', font=f); w2 = d.textlength('fx', font=f); xx = CX - (w1 + w2) / 2
    d.text((xx, 1700), 'wendling', font=f, fill=WHITE); d.text((xx + w1, 1700), 'fx', font=f, fill=LIME)
    mc.tc(d, 1790, 'Levels on the chart, not trade signals.', inter(28, 'Regular'), DIM)
    name = f'wendlingfx-levels-{sym.lower()}-{today.isoformat()}.png'; img.save(os.path.join(out, name), optimize=True)
    cap = f"{NAMES.get(sym, sym)} this week: last week's range {fmt(sym, L[1][0])} to {fmt(sym, L[0][0])}, week open {fmt(sym, wo[0]['o']) if wo else 'n/a'}."
    return name, cap
def main():
    out = sys.argv[1]; syms = sys.argv[2:] or ['XAUUSD', 'EURUSD']; os.makedirs(out, exist_ok=True)
    daily = get('market.json')['daily']; h1 = get('market-h1.json')['h1']
    for s in syms:
        if s not in daily or s not in h1: print(json.dumps({'sym': s, 'skipped': 'no data'})); continue
        name, cap = chart(s, daily[s], h1[s], out); print(json.dumps({'sym': s, 'file': name, 'caption': cap}))
if __name__ == '__main__':
    main()
