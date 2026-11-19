#!/usr/bin/env python3
"""Wendling FX: result cards (1080x1920 PNG) for Telegram and TikTok photo posts.

Usage: python3 tools/make_card.py KIND OUT_DIR [--date YYYY-MM-DD]
KIND: day | week | month | auto
  day   = the UTC day of --date (default: yesterday)
  week  = Mon to Sun week containing --date (default: the week that just ended)
  month = calendar month of --date (default: last month)
  auto  = run at about 00:30 UTC: yesterday's day card (Mon to Fri) and the month on the 1st (the week is a video, not a card)
Prints one JSON line per card: {"file", "kind", "caption", "period"}.
Same rules as the videos: English, % only, real numbers, no promises.
"""
import json, os, sys, random, urllib.request, datetime as dt
from PIL import Image, ImageDraw, ImageFont
from brand import header

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 1080, 1920
CX = 505
BG = (10, 10, 10); LIME = (198, 255, 61); WHITE = (245, 245, 245); MUTED = (150, 150, 150)
RED = (255, 77, 77); PANEL = (20, 20, 20); LINE = (38, 38, 38); DIM = (110, 110, 110)
DATA = 'https://wendlingfx.com/data/'

def unb(size, w=700):
    f = ImageFont.truetype(os.path.join(HERE, 'fonts', 'Unbounded.ttf'), size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f
def inter(size, name='SemiBold'): return ImageFont.truetype(os.path.join(HERE, 'fonts', f'Inter-{name}.otf'), size)
def pc(x):
    a = abs(x); s = f'{round(a)}' if a >= 10 else f'{round(a, 1):g}'
    return ('+' if x > 0.04 else '-' if x < -0.04 else '') + s + '%'
def col(x): return LIME if x > 0.04 else RED if x < -0.04 else WHITE
def get(name):
    with urllib.request.urlopen(DATA + name + '?t=' + str(random.random()), timeout=30) as r:
        return json.loads(r.read().decode())
def ratio(g1, g0): return ((1 + g1 / 100) / (1 + g0 / 100) - 1) * 100

def load():
    perf = get('performance.json').get('days', [])
    days = {d['d']: float(d['g']) for d in perf}
    pts = [(p['t'], float(p['g'])) for p in get('curve.json').get('points', [])]
    trades, prev = [], 0.0
    for t, g in pts:
        trades.append((t[:10], ratio(g, prev))); prev = g
    return days, trades, get('stats.json')

def period_gain(days, start, end):
    """Gain from the close before `start` to the last close up to `end` (dates as YYYY-MM-DD)."""
    before = [g for d, g in days.items() if d < start]
    inside = [(d, g) for d, g in sorted(days.items()) if start <= d <= end]
    if not inside: return None
    return ratio(inside[-1][1], before[-1] if before else 0.0)

def tc(d, y, s, font, fill):
    w = d.textlength(s, font=font); d.text((CX - w / 2, y), s, font=font, fill=fill); return w
def fit(d, s, size, maxw):
    while size > 40 and d.textlength(s, font=unb(size)) > maxw: size -= 4
    return unb(size)

def canvas():
    img = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(img)
    for x in range(0, W, 72): d.line([(x, 0), (x, H)], fill=(18, 18, 18))
    for y in range(0, H, 72): d.line([(0, y), (W, y)], fill=(18, 18, 18))
    return img, d

def card(kind, title, big, sub, rows, bars, total, out):
    img, d = canvas()
    header(d, kind, fmt='IMAGE')
    tc(d, 340, title, fit(d, title, 60, 800), WHITE)
    s = pc(big); tc(d, 440, s, fit(d, s, 210, 820), col(big))
    tc(d, 690, sub, inter(42, 'Medium'), MUTED)
    # stat rows
    x0, x1, y = 70, W - 150, 790
    for k, v, c in rows:
        d.rounded_rectangle([x0, y, x1, y + 96], radius=22, fill=PANEL, outline=LINE, width=2)
        d.text((x0 + 32, y + 28), k, font=inter(36, 'Medium'), fill=MUTED)
        f = unb(40, 600); w = d.textlength(v, font=f)
        d.text((x1 - 32 - w, y + 24), v, font=f, fill=c)
        y += 110
    # bars
    if bars:
        vals = [v for _, v in bars if v is not None]
        y0, hgt = 1270, 230
        hasp, hasn = any(v > 0.04 for v in vals), any(v < -0.04 for v in vals)
        base_y = y0 + hgt if not hasn else (y0 if not hasp else y0 + hgt / 2)
        room = (hgt - 40) if not (hasp and hasn) else (hgt / 2 - 34)
        n = len(bars); gap = 14; bw = min(110, (x1 - x0 - gap * (n - 1)) / n)
        tot = n * bw + gap * (n - 1); bx = x0 + ((x1 - x0) - tot) / 2
        m = max([1e-9] + [abs(v) for v in vals])
        d.line([(x0, base_y), (x1, base_y)], fill=LINE, width=2)
        for i, (lab, v) in enumerate(bars):
            xa = bx + i * (bw + gap)
            f = inter(26 if n <= 7 else 22, 'Medium'); w = d.textlength(lab, font=f)
            d.text((xa + bw / 2 - w / 2, y0 + hgt + 12), lab, font=f, fill=MUTED)
            if v is None: continue
            h = max(4, room * abs(v) / m)
            box = [xa, base_y - h, xa + bw, base_y] if v >= 0 else [xa, base_y, xa + bw, base_y + h]
            d.rounded_rectangle(box, radius=8, fill=col(v))
            if n <= 8:
                vs = pc(v); fv = inter(24); wv = d.textlength(vs, font=fv)
                d.text((xa + bw / 2 - wv / 2, (base_y - h - 32) if v >= 0 else (base_y + h + 4)), vs, font=fv, fill=col(v))
    tc(d, 1600, total, inter(40, 'SemiBold'), WHITE)
    f = unb(64); w1 = d.textlength('wendling', font=f); w2 = d.textlength('fx', font=f); xx = CX - (w1 + w2) / 2
    d.text((xx, 1668), 'wendling', font=f, fill=WHITE); d.text((xx + w1, 1668), 'fx', font=f, fill=LIME)
    tc(d, 1750, 'Verified on Myfxbook  ·  wendlingfx.com', inter(32, 'Medium'), MUTED)
    tc(d, 1810, 'Trading on margin is high risk. Not financial advice.', inter(26, 'Regular'), DIM)
    img.save(out, optimize=True)

def summary_rows(tr):
    wins = [p for p in tr if p > 0]; losses = [p for p in tr if p < 0]
    rows = [('Trades closed', str(len(tr)), WHITE),
            ('Won / lost', f'{len(wins)} / {len(losses)}', WHITE)]
    if tr:
        rows.append(('Best trade', pc(max(tr)), col(max(tr))))
        rows.append(('Worst trade', pc(min(tr)), col(min(tr))))
    return rows

def total_line(stats):
    return f"Account total: {pc(float(stats['gain']))}" if stats.get('gain') is not None else ''

def make(kind, date, out_dir, days, trades, stats):
    if kind == 'day':
        s = e = date.isoformat()
        g = period_gain(days, s, e)
        if g is None: return None
        tr = [p for dd, p in trades if dd == s]
        title = date.strftime('%A, %b %-d')
        bars = [(f'#{i + 1}', p) for i, p in enumerate(tr)] if 2 <= len(tr) <= 16 else []
        cap = f"Daily close, {date.strftime('%b %-d')}: {pc(g)} on the account. {len(tr)} trades closed."
    elif kind == 'week':
        mon = date - dt.timedelta(days=date.weekday()); sun = mon + dt.timedelta(days=6)
        s, e = mon.isoformat(), sun.isoformat()
        g = period_gain(days, s, e)
        if g is None: return None
        tr = [p for dd, p in trades if s <= dd <= e]
        title = 'Week of ' + mon.strftime('%b %-d')
        bars = []
        for i in range(5):
            dd = (mon + dt.timedelta(days=i)).isoformat(); v = period_gain(days, dd, dd)
            bars.append(((mon + dt.timedelta(days=i)).strftime('%a'), v))
        cap = f"Week of {mon.strftime('%b %-d')}: {pc(g)} on the account. {len(tr)} trades, every one public."
    else:
        first = date.replace(day=1); nxt = (first + dt.timedelta(days=32)).replace(day=1); last = nxt - dt.timedelta(days=1)
        s, e = first.isoformat(), last.isoformat()
        g = period_gain(days, s, e)
        if g is None: return None
        tr = [p for dd, p in trades if s <= dd <= e]
        title = first.strftime('%B %Y')
        bars, wk = [], first - dt.timedelta(days=first.weekday())
        while wk <= last:
            a, b = max(wk, first).isoformat(), min(wk + dt.timedelta(days=6), last).isoformat()
            v = period_gain(days, a, b)
            if v is not None: bars.append((max(wk, first).strftime('%b %-d'), v))
            wk += dt.timedelta(days=7)
        cap = f"{first.strftime('%B')}: {pc(g)} on the account. {len(tr)} trades closed."
    rows = summary_rows(tr)
    name = f'wendlingfx-{kind}-{s}.png'; out = os.path.join(out_dir, name)
    card(kind, title, g, 'on the account, after costs', rows, bars, total_line(stats), out)
    return {'file': name, 'kind': kind, 'period': s, 'caption': cap + "\n\nVerified record: wendlingfx.com"}

def main():
    a = sys.argv[1:]
    if len(a) < 2: raise SystemExit(__doc__)
    kind, out_dir = a[0], a[1]; os.makedirs(out_dir, exist_ok=True)
    date = None
    if '--date' in a: date = dt.date.fromisoformat(a[a.index('--date') + 1])
    today = dt.datetime.now(dt.timezone.utc).date()
    days, trades, stats = load()
    jobs = []
    if kind == 'auto':
        y = today - dt.timedelta(days=1)
        if y.weekday() < 5: jobs.append(('day', y))
        if today.day == 1: jobs.append(('month', y))
    elif kind == 'day': jobs.append(('day', date or today - dt.timedelta(days=1)))
    elif kind == 'week': jobs.append(('week', date or today - dt.timedelta(days=7)))
    elif kind == 'month': jobs.append(('month', date or (today.replace(day=1) - dt.timedelta(days=1))))
    else: raise SystemExit('unknown kind')
    for k, dte in jobs:
        r = make(k, dte, out_dir, days, trades, stats)
        print(json.dumps(r if r else {'skipped': k, 'date': dte.isoformat()}))

if __name__ == '__main__':
    main()
