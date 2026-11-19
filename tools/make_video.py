#!/usr/bin/env python3
"""Wendling FX: builds one TikTok video (1080x1920, about 18 to 21 s) from the live data on wendlingfx.com.

Usage: python3 tools/make_video.py KIND OUT_DIR [--music NAME] [--date YYYY-MM-DD]
KIND: diary | week | growth | ctrader | market (needs --points FILE) | promo | auto (auto picks by weekday: Mon week, Wed diary, Fri growth)
Writes OUT_DIR/<file>.mp4 and prints one JSON line: {"file", "kind", "text", "music"}.
Rules kept here on purpose: English, percentages only (never dollar values), real numbers, no promises.
"""
import json, math, os, random, subprocess, sys, urllib.request, datetime as dt
from PIL import Image, ImageDraw, ImageFont
from brand import header

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
CX = 505  # content centre, keeps clear of TikTok's right-side buttons
BG = (10, 10, 10); LIME = (198, 255, 61); WHITE = (245, 245, 245); MUTED = (150, 150, 150)
RED = (255, 77, 77); GREEN = (34, 197, 94); PANEL = (20, 20, 20); LINE = (38, 38, 38)
DATA = 'https://wendlingfx.com/data/'


def unb(size, w=700):
    f = ImageFont.truetype(os.path.join(HERE, 'fonts', 'Unbounded.ttf'), size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f

def inter(size, name='SemiBold'):
    return ImageFont.truetype(os.path.join(HERE, 'fonts', f'Inter-{name}.otf'), size)

def ease(t): t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3
def mix(c, a, bg=BG): return tuple(int(bg[i] + (c[i] - bg[i]) * a) for i in range(3))

GRID = Image.new('RGB', (W, H), BG)
_g = ImageDraw.Draw(GRID)
for x in range(0, W, 72): _g.line([(x, 0), (x, H)], fill=(18, 18, 18))
for y in range(0, H, 72): _g.line([(0, y), (W, y)], fill=(18, 18, 18))
def base(): return GRID.copy()

def tc(d, y, s, font, fill):
    w = d.textlength(s, font=font); d.text((CX - w / 2, y), s, font=font, fill=fill); return w

def fit(d, s, size, maxw=800, w=700):
    while size > 30 and d.textlength(s, font=unb(size, w)) > maxw: size -= 2
    return unb(size, w)

def top(d, kind, a=1.0):  # inner scenes: compact type header
    header(d, kind, a, compact=True)

def fade(img, t, dur=0.2):
    return img if t >= dur else Image.blend(Image.new('RGB', (W, H), BG), img, ease(t / dur))

def pc(x, digits=True):
    a = abs(x); s = f'{round(a)}' if a >= 10 or not digits else f'{round(a, 1):g}'
    return ('+' if x > 0 else '-' if x < 0 else '') + s + '%'

def get(name):
    with urllib.request.urlopen(DATA + name + '?t=' + str(random.random()), timeout=30) as r:
        return json.loads(r.read().decode())

def end_card(sub):
    def fn(t):
        img = base(); d = ImageDraw.Draw(img)
        a = ease(t / 0.5); f = unb(170)
        w1 = d.textlength('w', font=f); w2 = d.textlength('fx', font=f)
        x = CX - (w1 + w2) / 2; y = 680 + (1 - a) * 40
        d.text((x, y), 'w', font=f, fill=mix(WHITE, a)); d.text((x + w1, y), 'fx', font=f, fill=mix(LIME, a))
        b = ease((t - 0.5) / 0.45)
        tc(d, 960 + (1 - b) * 20, sub, inter(46, 'SemiBold'), mix(WHITE, b))
        tc(d, 1030 + (1 - b) * 20, 'wendlingfx.com', inter(46, 'SemiBold'), mix(LIME, b))
        c = ease((t - 1.1) / 0.45)
        tc(d, 1180, 'Trading on margin is high risk. Not financial advice.', inter(28, 'Regular'), mix((110, 110, 110), c))
        return fade(img, t)
    return fn

def hook(lines, label, sub=None):
    def fn(t):
        img = base(); d = ImageDraw.Draw(img); header(d, label)  # cover: full type header
        for i, (s, c) in enumerate(lines):  # fully visible from frame 0: TikTok uses it as the cover
            tc(d, 700 + i * 130, s, fit(d, s, 92), c)
        if sub:
            b = ease((t - 0.55) / 0.3)
            tc(d, 700 + len(lines) * 130 + 40 + (1 - b) * 20, sub, inter(40, 'Medium'), mix(MUTED, b))
        return img
    return fn

# ---------- kinds ----------
def kind_diary():
    trades = [t for t in get('closed-trades.json').get('trades', []) if t.get('pct') is not None][:9]
    trades = list(reversed(trades))
    if not trades: raise SystemExit('no trades')
    label = 'diary'
    def lst(t):
        img = base(); d = ImageDraw.Draw(img); top(d, label)
        a0 = ease(t / 0.4)
        tc(d, 250, 'Latest closed trades', fit(d, 'Latest closed trades', 70, 780), mix(WHITE, a0))
        tc(d, 360, 'Every trade, in % of the account.', inter(38, 'Medium'), mix(MUTED, a0))
        x0, x1, y0, rh = 50, W - 140, 470, 124
        for i, tr in enumerate(trades):
            a = ease((t - 0.5 - i * 0.55) / 0.35)
            if a <= 0: continue
            y = y0 + i * rh + (1 - a) * 30; v = float(tr['pct']); neg = v < 0
            d.rounded_rectangle([x0, y, x1, y + rh - 18], radius=22, fill=mix((40, 16, 16) if neg else PANEL, a),
                                outline=mix((110, 40, 40) if neg else LINE, a), width=2)
            cy = y + (rh - 18) / 2
            day = dt.datetime.strptime(tr['closed'][:10], '%Y-%m-%d').strftime('%b %-d')
            d.text((x0 + 28, cy - 17), day, font=inter(30, 'Medium'), fill=mix(MUTED, a))
            d.text((x0 + 170, cy - 22), tr['symbol'], font=unb(36, 600), fill=mix(WHITE, a))
            side = tr['side']; col = GREEN if side == 'Buy' else RED
            fp = inter(26); pw = d.textlength(side, font=fp) + 36; px = x0 + 415
            d.rounded_rectangle([px, cy - 24, px + pw, cy + 24], radius=24, outline=mix(col, a), width=2)
            d.text((px + 18, cy - 16), side, font=fp, fill=mix(col, a))
            s = pc(v); fr = unb(42); rw = d.textlength(s, font=fr)
            d.text((x1 - 28 - rw, cy - 26), s, font=fr, fill=mix(RED if neg else (LIME if v > 0 else WHITE), a))
        return fade(img, t)
    dur = max(7.0, 0.5 + len(trades) * 0.55 + 2.2)
    last = trades[-1]; lv = float(last['pct'])
    scenes = [(hook([('Last trade:', WHITE), (last['symbol'] + ' ' + pc(lv), RED if lv < 0 else LIME), ('of the account.', WHITE)], label, 'Every trade is public.'), 3.0),
              (lst, dur), (end_card('Verified on Myfxbook.'), 3.4)]
    text = 'Live forex account. Latest closed trades in % of the account. Verified on Myfxbook. #forex #xauusd #eurusd #trading'
    return scenes, text

def kind_week():
    days = get('performance.json').get('days', []); st = get('stats.json')
    if len(days) < 2: raise SystemExit('not enough days')
    today = dt.date.fromisoformat(days[-1]['d'])
    mon = today - dt.timedelta(days=today.weekday() + 7)  # last full week (Mon to Sun)
    sun = mon + dt.timedelta(days=6)
    g0 = 0.0; g1 = None
    for x in days:
        dd = dt.date.fromisoformat(x['d'])
        if dd < mon: g0 = x['g']
        if dd <= sun: g1 = x['g']
    if g1 is None or dt.date.fromisoformat(days[0]['d']) > mon:  # account younger than a full week: week so far
        mon = today - dt.timedelta(days=today.weekday()); g0 = 0.0; g1 = days[-1]['g']
        for x in days:
            if dt.date.fromisoformat(x['d']) < mon: g0 = x['g']
        sun = today
    wk = ((1 + g1 / 100) / (1 + g0 / 100) - 1) * 100
    label = 'week'
    rng = mon.strftime('%b %-d') + ' to ' + sun.strftime('%b %-d')
    def board(t):
        img = base(); d = ImageDraw.Draw(img); top(d, label)
        a = ease(t / 0.45)
        tc(d, 330, 'Week of ' + rng, inter(44, 'Medium'), mix(MUTED, a))
        b = ease((t - 0.3) / 0.6)
        big = pc(wk * min(1, b * 1.15) if b < 0.87 else wk, False); tc(d, 430 + (1 - b) * 40, big, fit(d, pc(wk, False), 200, 780), mix(LIME if wk >= 0 else RED, b))
        tc(d, 700, 'on the account', inter(44, 'Medium'), mix(WHITE, b))
        rows = [('Account total', pc(st['gain'], False)),
                ('Winning trades, after costs', f"{round(st['winRate'])}%"),
                ('Best trade', pc(st.get('bestTrade', 0), False)),
                ('Average losing trade', pc(st.get('avgLoss', 0)))]
        for i, (k, v) in enumerate(rows):
            c = ease((t - 1.2 - i * 0.35) / 0.4)
            if c <= 0: continue
            y = 860 + i * 130
            d.rounded_rectangle([80, y, 930, y + 104], radius=22, fill=mix(PANEL, c), outline=mix(LINE, c), width=2)
            d.text((112, y + 34), k, font=inter(34, 'Medium'), fill=mix(MUTED, c))
            fv = unb(44); vw = d.textlength(v, font=fv)
            col = RED if v.startswith('-') else WHITE
            d.text((898 - vw, y + 26), v, font=fv, fill=mix(col, c))
        return fade(img, t)
    scenes = [(hook([('Week of ' + mon.strftime('%b %-d') + ':', WHITE), (pc(wk, False), LIME if wk >= 0 else RED), ('on the account.', WHITE)], label, 'Real numbers, verified.'), 3.0),
              (board, 8.5), (end_card('Verified on Myfxbook.'), 3.4)]
    text = f'Weekly scoreboard, {rng}: {pc(wk, False)} on the account. Every trade is public and verified on Myfxbook. #forex #trading #copytrading'
    return scenes, text

def kind_growth():
    cv = get('curve.json').get('points', []); st = get('stats.json')
    if len(cv) < 3: raise SystemExit('not enough points')
    pts = [0.0] + [p['g'] for p in cv]
    if st.get('openPct'): pts.append(round(((1 + pts[-1] / 100) * (1 + st['openPct'] / 100) - 1) * 100, 2))  # now, incl. open trades
    if abs(pts[-1] - st['gain']) > 0.15 * max(10.0, abs(st['gain'])): raise SystemExit('curve does not match the account gain')
    label = 'growth'
    lo, hi = min(pts + [0]), max(pts)
    def chart(t):
        img = base(); d = ImageDraw.Draw(img); top(d, label)
        a = ease(t / 0.4)
        tc(d, 260, 'Live account, verified', inter(44, 'Medium'), mix(MUTED, a))
        k = ease((t - 0.4) / 4.5); n = max(2, int(1 + k * (len(pts) - 1)))
        X0, X1, Y0, Y1 = 90, 920, 520, 1280
        def X(i): return X0 + (X1 - X0) * i / (len(pts) - 1)
        def Y(g): return Y1 - (Y1 - Y0) * (g - lo) / ((hi - lo) or 1)
        d.line([(X0, Y(0)), (X1, Y(0))], fill=LINE, width=2)
        seg = [(X(i), Y(pts[i])) for i in range(n)]
        d.line(seg, fill=LIME, width=7, joint='curve')
        x, y = seg[-1]; d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=LIME)
        tc(d, 380, pc(pts[n - 1], False), fit(d, pc(max(pts), False), 110, 780), mix(LIME, a))
        b = ease((t - 5.0) / 0.5)
        tc(d, 1360, f"{st['trades']} trades, {round(st['winRate'])}% winners after costs", inter(38, 'Medium'), mix(WHITE, b))
        tc(d, 1420, 'One point per closed trade.', inter(34, 'Regular'), mix(MUTED, b))
        return fade(img, t)
    scenes = [(hook([('Account growth:', WHITE), (pc(pts[-1], False), LIME if pts[-1] >= 0 else RED), ('every trade public.', WHITE)], label, 'Verified on Myfxbook.'), 3.0),
              (chart, 7.0), (end_card('Verified on Myfxbook.'), 3.4)]
    text = f"Account growth: one point per closed trade. Verified on Myfxbook. #forex #trading #copytrading"
    return scenes, text

SHIELD = [(0, -60), (52, -40), (52, 6), (0, 62), (-52, 6), (-52, -40)]
def kind_ctrader():
    label = 'ctrader'
    def ic_server(d, cx, cy, a):
        for k in range(3):
            y = cy - 90 + k * 64
            d.rounded_rectangle([cx - 110, y, cx + 110, y + 50], radius=12, outline=mix(LIME, a), width=6)
            d.ellipse([cx + 66, y + 18, cx + 80, y + 32], fill=mix(LIME, a))
            d.line([(cx - 84, y + 25), (cx - 20, y + 25)], fill=mix(LIME, a), width=6)
    def ic_scale(d, cx, cy, a):
        d.ellipse([cx - 150, cy - 10, cx - 70, cy + 70], outline=mix(LIME, a), width=6)
        d.ellipse([cx - 30, cy - 90, cx + 150, cy + 90], outline=mix(LIME, a), width=6)
        f, f2 = unb(30), unb(56)
        w = d.textlength('5%', font=f); d.text((cx - 110 - w / 2, cy + 12), '5%', font=f, fill=mix(LIME, a))
        w = d.textlength('5%', font=f2); d.text((cx + 60 - w / 2, cy - 32), '5%', font=f2, fill=mix(LIME, a))
    def ic_shield(d, cx, cy, a):
        d.polygon([(cx + x * 1.6, cy + y * 1.6) for x, y in SHIELD], outline=mix(LIME, a), width=6)
        d.line([(cx - 44, cy + 4), (cx + 44, cy + 4)], fill=mix(RED, a), width=8)
    def ic_peak(d, cx, cy, a):
        p = [(cx - 160, cy + 60), (cx - 80, cy - 10), (cx - 30, cy + 30), (cx + 50, cy - 50), (cx + 90, cy - 20), (cx + 160, cy - 90)]
        d.line([(cx - 160, cy - 50), (cx + 160, cy - 50)], fill=mix(MUTED, a * 0.6), width=3)
        d.line(p, fill=mix(LIME, a), width=7, joint='curve'); d.ellipse([cx + 148, cy - 102, cx + 172, cy - 78], fill=mix(LIME, a))
    def ic_exit(d, cx, cy, a):
        d.rounded_rectangle([cx - 140, cy - 90, cx + 10, cy + 90], radius=14, outline=mix(LIME, a), width=6)
        d.line([(cx - 50, cy), (cx + 140, cy)], fill=mix(LIME, a), width=8)
        d.line([(cx + 95, cy - 45), (cx + 140, cy), (cx + 95, cy + 45)], fill=mix(LIME, a), width=8, joint='curve')
    P = [('01', 'Runs on cTrader', 'servers, 24/7.', 'Your computer can be off.', ic_server),
         ('02', 'Sized to', 'your account.', 'Same % as mine, any amount.', ic_scale),
         ('03', 'Your own', 'loss limit.', 'Set it once. Copying stops there.', ic_shield),
         ('04', 'Fee only on', 'new profit.', 'Charged only above your last high.', ic_peak),
         ('05', 'Stop', 'anytime.', 'No lock-in. Your money stays with you.', ic_exit)]
    def point(k):
        num, l1, l2, sub, icon = P[k]
        def fn(t):
            img = base(); d = ImageDraw.Draw(img); top(d, label)
            for j in range(5):
                x = CX + (j - 2) * 60
                d.rounded_rectangle([x - 20, 300, x + 20, 308], radius=4, fill=LIME if j <= k else LINE)
            a = ease(t / 0.35); tc(d, 380 + (1 - a) * 30, num, unb(70), mix(LIME, a))
            b = ease((t - 0.2) / 0.4); icon(d, CX, 680 + (1 - b) * 30, b)
            c = ease((t - 0.35) / 0.45)
            tc(d, 900 + (1 - c) * 40, l1, unb(78), mix(WHITE, c)); tc(d, 1010 + (1 - c) * 40, l2, unb(78), mix(LIME, c))
            e = ease((t - 0.8) / 0.45); tc(d, 1160 + (1 - e) * 20, sub, inter(38, 'Medium'), mix(MUTED, e))
            return fade(img, t, 0.15)
        return fn
    scenes = [(hook([('Copy a trader', WHITE), ('without sending', WHITE), ('him your money.', LIME)], label, 'This is how cTrader Copy works.'), 3.2)]
    scenes += [(point(k), 2.8) for k in range(5)]
    scenes += [(end_card('Copy the strategy on cTrader.'), 3.4)]
    text = 'How copy trading works on cTrader: it runs on their servers, sizes to your account, you set your own loss limit, the fee is only on new profit, and you can stop anytime. #copytrading #ctrader #forex #trading'
    return scenes, text

def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def kind_market():
    """The week in markets. Needs --points FILE: {"week": "Nov 16 to 20", "items": [{"name": "Gold", "chg": -2.1, "why": "..."}]} (3 items)."""
    pts = json.load(open(OPT['--points']))
    items = pts['items'][:3]; label = 'market'
    def item(it):
        def fn(t):
            img = base(); d = ImageDraw.Draw(img); top(d, label)
            a = ease(t / 0.35)
            tc(d, 420 + (1 - a) * 30, it['name'], fit(d, it['name'], 96, 800), mix(WHITE, a))
            v = float(it['chg']); s = pc(v)
            b = ease((t - 0.2) / 0.4); tc(d, 560 + (1 - b) * 30, s, fit(d, s, 170, 800), mix(LIME if v >= 0 else RED, b))
            c = ease((t - 0.6) / 0.45); f = inter(44, 'Medium')
            for i, ln in enumerate(wrap(d, it['why'], f, 800)[:4]): tc(d, 860 + i * 64 + (1 - c) * 20, ln, f, mix(WHITE, c))
            tc(d, 1160, 'this week', inter(36, 'Regular'), mix(MUTED, c))
            return fade(img, t, 0.15)
        return fn
    first = items[0]
    scenes = [(hook([('The week in', WHITE), ('markets:', WHITE), (first['name'] + ' ' + pc(float(first['chg'])), LIME if float(first['chg']) >= 0 else RED)], label, pts.get('week', '')), 3.0)]
    scenes += [(item(it), 3.6) for it in items]
    scenes += [(end_card('Full notes on the blog.'), 3.4)]
    text = f"The week in markets, {pts.get('week', '')}: " + ', '.join(f"{it['name']} {pc(float(it['chg']))}" for it in items) + '. Full notes at wendlingfx.com/blog. #forex #gold #markets #trading'
    return scenes, text

def kind_promo():
    label = 'promo'
    lines = [('The live account,', WHITE), ('every day,', WHITE), ('free on Telegram.', LIME)]
    def card(t):
        img = base(); d = ImageDraw.Draw(img); top(d, label)
        a = ease(t / 0.4)
        tc(d, 560, 'Daily close of the live account', inter(46, 'Medium'), mix(WHITE, a))
        tc(d, 640, 'Weekly results and short videos', inter(46, 'Medium'), mix(WHITE, a))
        b = ease((t - 0.6) / 0.5)
        tc(d, 860, 't.me/wendlingfx', fit(d, 't.me/wendlingfx', 96, 800), mix((42, 171, 238), b))
        tc(d, 1000, 'Link in bio', inter(40, 'Medium'), mix(MUTED, b))
        return fade(img, t, 0.15)
    scenes = [(hook(lines, label, 'Search: Wendling FX'), 3.0), (card, 4.2), (end_card('Free channel. Leave anytime.'), 3.2)]
    text = 'Follow the live account for free on Telegram: daily close, weekly results and short videos. Search Wendling FX or use the link in bio. #forex #trading #copytrading'
    return scenes, text

def kind_howto():
    """How to start copying, 5 steps, with the guide illustrations from site/start/img."""
    label = 'ctrader'; imgdir = os.path.join(os.path.dirname(HERE), 'site', 'start', 'img')
    S = [('Open a Fusion Markets', 'account on cTrader.', 'account.png'), ('Verify your', 'identity.', 'verify.png'),
         ('Fund it with', 'US$500 or more.', 'fund.png'), ('Open my strategy and', 'press Start copying.', 'copyform.png'), ('Set your', 'loss limit.', 'stoploss.png')]
    cache = {}
    def pic(name):
        if name not in cache:
            im = Image.open(os.path.join(imgdir, name)).convert('RGB'); im.thumbnail((900, 520)); cache[name] = im
        return cache[name]
    def step(k):
        l1, l2, name = S[k]
        def fn(t):
            img = base(); d = ImageDraw.Draw(img); top(d, label)
            for j in range(5):
                x = CX + (j - 2) * 60
                d.rounded_rectangle([x - 20, 300, x + 20, 308], radius=4, fill=LIME if j <= k else LINE)
            a = ease(t / 0.35); tc(d, 380 + (1 - a) * 30, f'0{k + 1}', unb(70), mix(LIME, a))
            c = ease((t - 0.2) / 0.4)
            tc(d, 500 + (1 - c) * 30, l1, fit(d, l1, 70, 820), mix(WHITE, c)); tc(d, 590 + (1 - c) * 30, l2, fit(d, l2, 70, 820), mix(LIME, c))
            b = ease((t - 0.5) / 0.45)
            if b > 0:
                im = pic(name); x0 = int(CX - im.width / 2); y0 = int(760 + (1 - b) * 40)
                img.paste(Image.blend(Image.new('RGB', im.size, BG), im, b), (x0, y0))
            return fade(img, t, 0.15)
        return fn
    scenes = [(hook([('Copy my trades', WHITE), ('in 5 steps.', LIME)], label, 'Your money stays in your name.'), 3.0)]
    scenes += [(step(k), 3.0) for k in range(5)]
    scenes += [(end_card('Step by step: wendlingfx.com/start'), 3.4)]
    text = 'How to copy my trades in 5 steps on cTrader Copy: open the account, verify, fund, start copying and set your loss limit. Full guide with screenshots at wendlingfx.com/start. #copytrading #ctrader #forex'
    return scenes, text

KINDS = {'diary': kind_diary, 'week': kind_week, 'growth': kind_growth, 'ctrader': kind_ctrader, 'market': kind_market, 'promo': kind_promo, 'howto': kind_howto}
OPT = {}

def render(scenes, out_mp4, music):
    tmpdir = out_mp4 + '.parts'; os.makedirs(tmpdir, exist_ok=True); parts = []
    for i, (fn, dur) in enumerate(scenes):
        part = os.path.join(tmpdir, f'{i}.mp4'); tmp = part + '.tmp.mp4'
        p = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
                              '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
                              '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
        for k in range(int(round(dur * FPS))): p.stdin.write(fn(k / FPS).tobytes())
        p.stdin.close()
        if p.wait() != 0: raise SystemExit('ffmpeg failed')
        os.replace(tmp, part); parts.append(part)
    lst = os.path.join(tmpdir, 'list.txt')
    with open(lst, 'w') as f: f.writelines(f"file '{os.path.basename(x)}'\n" for x in parts)
    silent = os.path.join(tmpdir, 'silent.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', silent], check=True)
    total = sum(d for _, d in scenes)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', music, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-af', f'afade=t=out:st={total - 1.7:.2f}:d=1.7', '-c:a', 'aac', '-b:a', '160k', '-t', f'{total:.2f}',
                    '-movflags', '+faststart', out_mp4], check=True)
    for x in os.listdir(tmpdir): os.remove(os.path.join(tmpdir, x))
    os.rmdir(tmpdir)

def main():
    args = sys.argv[1:]
    if len(args) < 2: raise SystemExit(__doc__)
    kind, out = args[0], args[1]
    opt = dict(zip(args[2::2], args[3::2])); OPT.update(opt)
    day = dt.date.fromisoformat(opt['--date']) if '--date' in opt else dt.date.today()
    if kind == 'auto': kind = {0: 'week', 2: 'diary', 4: 'growth'}.get(day.weekday(), 'diary')
    scenes, text = KINDS[kind]()
    mdir = os.path.join(HERE, 'music')
    tracks = sorted(x for x in os.listdir(mdir) if x.endswith('.m4a'))
    music = opt.get('--music') or random.Random(day.toordinal()).choice(tracks)
    os.makedirs(out, exist_ok=True)
    name = f'wendlingfx-{day.isoformat()}-{kind}.mp4'
    render(scenes, os.path.join(out, name), os.path.join(mdir, music))
    print(json.dumps({'file': name, 'kind': kind, 'text': text, 'music': music}))

if __name__ == '__main__':
    main()
