#!/usr/bin/env python3
"""Wendling FX: LEARN video "Best hours to trade gold (XAU/USD)", times in New York time (ET).
Session clock + a real-data scene: gold's average hourly range by ET hour, from https://wendlingfx.com/data/market-h1.json.

Usage: python3 tools/make_gold_hours.py OUT_DIR [--music FILE] [--date YYYY-MM-DD]
Prints one JSON line: {"file", "text", "music", "peak"}.
No buy/sell calls, no promises. Times use US/UK winter time; the DST scene explains the shift.
"""
import collections, json, math, os, random, sys, urllib.request, datetime as dt
from PIL import Image, ImageDraw
import make_video as mv
from make_video import W, H, CX, LIME, WHITE, MUTED, RED, PANEL, LINE, BG, unb, inter, ease, mix, tc, fit, fade
from brand import header

HERE = os.path.dirname(os.path.abspath(__file__))
BLUE = (42, 171, 238); SLATE = (148, 163, 184); CYAN = (34, 211, 238); ORANGE = (255, 138, 61)
CY0 = 840; R = 300  # clock centre y and radius

ASIA = (19, 4, SLATE, 'ASIA')
LONDON = (3, 12, CYAN, 'LONDON')
NEWYORK = (8, 17, LIME, 'NEW YORK')


def ang(h):  # 0h at the top, clockwise
    return -90 + h * 15


def arc(d, h0, h1, col, r, width):
    a0, a1 = ang(h0), ang(h1 if h1 > h0 else h1 + 24)
    d.arc([CX - r, CY0 - r, CX + r, CY0 + r], a0, a1, fill=col, width=width)


def clock(d, focus=None, a=1.0, centre=None):
    d.ellipse([CX - R - 34, CY0 - R - 34, CX + R + 34, CY0 + R + 34], fill=(16, 16, 16), outline=LINE, width=3)
    for i, (h0, h1, col, name) in enumerate((ASIA, LONDON, NEWYORK)):
        on = focus is None or focus == name or (focus == 'OVERLAP' and name in ('LONDON', 'NEW YORK'))
        c = col if on else mix(col, 0.22)
        arc(d, h0, h1, mix(c, a), R + 8 - i * 0 + (0 if name == 'ASIA' else (-26 if name == 'LONDON' else -52)), 18)
    if focus == 'OVERLAP':
        arc(d, 8, 12, mix(LIME, a), R + 40, 10)
    f = inter(30, 'Medium')
    for hh in range(0, 24, 3):
        t = math.radians(ang(hh)); rr = R - 100
        s = f'{hh}h'; w = d.textlength(s, font=f)
        d.text((CX + rr * math.cos(t) - w / 2, CY0 + rr * math.sin(t) - 18), s, font=f, fill=mix(MUTED, a))
    if centre:
        l1, l2, col = centre
        tc(d, CY0 - 62, l1, fit(d, l1, 58, 330), mix(col, a))
        tc(d, CY0 + 10, l2, inter(36, 'SemiBold'), mix(WHITE, a))


def legend(d, a=1.0):
    f = inter(30, 'SemiBold'); x = 90
    for h0, h1, col, name in (ASIA, LONDON, NEWYORK):
        w = d.textlength(name, font=f) + 48
        d.rounded_rectangle([x, 300, x + w, 352], radius=26, outline=mix(col, a), width=3)
        d.text((x + 24, 310), name, font=f, fill=mix(col, a)); x += w + 22


def scene_clock(title, sub, focus, centre, pill=None, pill_col=BLUE):
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn', compact=True)
        legend(d)
        a = ease(t / 0.45)
        clock(d, focus, 1.0, centre if a > 0.3 else None)
        if pill:
            fp = inter(32, 'SemiBold'); w = d.textlength(pill, font=fp) + 56
            d.rounded_rectangle([CX - w / 2, 410, CX + w / 2, 468], radius=29, fill=mix(pill_col, 0.9 * a))
            d.text((CX - w / 2 + 28, 421), pill, font=fp, fill=(10, 10, 10))
        b = ease((t - 0.3) / 0.4)
        tc(d, 1270 + (1 - b) * 30, title, fit(d, title, 64, 860), mix(WHITE, b))
        c = ease((t - 0.7) / 0.4)
        y = 1365
        for line in sub:
            tc(d, y + (1 - c) * 20, line, inter(40, 'Medium'), mix(MUTED, c)); y += 56
        return fade(img, t, 0.15)
    return fn


def hook():
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn')  # full header on frame 0 (cover)
        tc(d, 640, 'Trading gold', fit(d, 'Trading gold', 104), WHITE)
        tc(d, 770, 'at the wrong', fit(d, 'at the wrong', 104), WHITE)
        tc(d, 900, 'hour?', fit(d, 'hour?', 104), LIME)
        b = ease((t - 0.8) / 0.4)
        tc(d, 1080 + (1 - b) * 20, 'The price drifts. Your stop gets hit.', inter(42, 'Medium'), mix(MUTED, b))
        return img
    return fn


def title():
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn', compact=True)
        a = ease(t / 0.4)
        tc(d, 640 + (1 - a) * 30, 'Best hours to trade', fit(d, 'Best hours to trade', 76), mix(WHITE, a))
        tc(d, 750 + (1 - a) * 30, 'XAU/USD', unb(150, 800), mix(LIME, a))
        b = ease((t - 0.5) / 0.4)
        tc(d, 960 + (1 - b) * 20, 'All times in New York time (ET).', inter(42, 'Medium'), mix(MUTED, b))
        return fade(img, t, 0.15)
    return fn


def data_scene(avg, days):
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn', compact=True)
        a = ease(t / 0.4)
        tc(d, 290, 'Our data', fit(d, 'Our data', 70), mix(LIME, a))
        tc(d, 390, f'Gold: average 1-hour range,', inter(42, 'SemiBold'), mix(WHITE, a))
        tc(d, 445, f'by hour (ET), last {days} trading days.', inter(42, 'SemiBold'), mix(WHITE, a))
        x0, x1, yb, top = 70, W - 130, 1330, 620
        bw = (x1 - x0) / 24; mx = max(avg.values())
        for hh in range(24):
            v = avg.get(hh)
            if v is None: continue
            g = ease((t - 0.4 - hh * 0.04) / 0.35)
            if g <= 0: continue
            hgt = (yb - top) * v / mx * g
            col = LIME if 8 <= hh <= 11 else mix(SLATE, 0.55)
            d.rounded_rectangle([x0 + hh * bw + 4, yb - hgt, x0 + (hh + 1) * bw - 4, yb], radius=6, fill=col)
        fl = inter(26, 'Medium')
        for hh in (0, 3, 6, 9, 12, 15, 18, 21):
            s = f'{hh}h'; w = d.textlength(s, font=fl)
            d.text((x0 + (hh + 0.5) * bw - w / 2, yb + 14), s, font=fl, fill=MUTED)
        c = ease((t - 1.6) / 0.4)
        if c > 0:
            s = f'8am ET: {avg.get(8, 0):.1f}% average range'
            tc(d, 1440 + (1 - c) * 20, s, fit(d, s, 46, 860, 700), mix(LIME, c))
            tc(d, 1520 + (1 - c) * 20, 'Spikes: NY open and data (8 to 10am ET)', inter(36, 'Medium'), mix(MUTED, c))
            tc(d, 1572 + (1 - c) * 20, 'and the Asia open (8 to 9pm ET).', inter(36, 'Medium'), mix(MUTED, c))
        return fade(img, t, 0.15)
    return fn


def dst():
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn', compact=True)
        a = ease(t / 0.4)
        fp = inter(32, 'SemiBold'); s = 'WATCH OUT'; w = d.textlength(s, font=fp) + 56
        d.rounded_rectangle([CX - w / 2, 420, CX + w / 2, 478], radius=29, fill=mix(ORANGE, a))
        d.text((CX - w / 2 + 28, 431), s, font=fp, fill=(10, 10, 10))
        tc(d, 600 + (1 - a) * 30, 'Daylight saving', fit(d, 'Daylight saving', 84), mix(WHITE, a))
        b = ease((t - 0.5) / 0.4)
        for i, line in enumerate(['The US and the UK change clocks', 'on different dates.', '', 'For a few weeks in March', 'and late Oct to early Nov,', 'London opens 1 hour off.']):
            tc(d, 760 + i * 62 + (1 - b) * 20, line, inter(42, 'Medium'), mix(MUTED if i < 2 else WHITE, b))
        return fade(img, t, 0.15)
    return fn


def summary():
    rows = [('3am ET', 'London opens', CYAN), ('8am to 12pm', 'Best window', LIME), ('8:30am ET', 'US data', ORANGE)]
    def fn(t):
        img = mv.base(); d = ImageDraw.Draw(img); header(d, 'learn', compact=True)
        a = ease(t / 0.4)
        tc(d, 430 + (1 - a) * 30, 'Save this.', fit(d, 'Save this.', 100), mix(WHITE, a))
        for i, (k, v, col) in enumerate(rows):
            b = ease((t - 0.4 - i * 0.3) / 0.35)
            if b <= 0: continue
            y = 640 + i * 150 + (1 - b) * 30
            d.rounded_rectangle([110, y, W - 190, y + 112], radius=56, fill=mix(PANEL, b), outline=mix(col, b), width=3)
            d.text((160, y + 30), k, font=unb(44, 700), fill=mix(col, b))
            fv = inter(40, 'SemiBold'); w = d.textlength(v, font=fv)
            d.text((W - 230 - w, y + 34), v, font=fv, fill=mix(WHITE, b))
        return fade(img, t, 0.15)
    return fn


def hourly_ranges():
    u = 'https://wendlingfx.com/data/market-h1.json?t=' + str(random.random())
    with urllib.request.urlopen(u, timeout=30) as r: bars = json.loads(r.read().decode())['h1']['XAUUSD']
    acc = collections.defaultdict(list); days = set()
    for ts, o, hi, lo, c in bars:
        et = dt.datetime.fromtimestamp(ts * 60, dt.timezone.utc) - dt.timedelta(hours=5)  # EST (winter)
        acc[et.hour].append((hi - lo) / o * 100); days.add(et.date())
    return {h: sum(v) / len(v) for h, v in acc.items() if len(v) >= 3}, len(days)


def main():
    args = sys.argv[1:]
    if not args: raise SystemExit(__doc__)
    out = args[0]; opt = dict(zip(args[1::2], args[2::2]))
    day = dt.date.fromisoformat(opt['--date']) if '--date' in opt else dt.date.today()
    avg, days = hourly_ranges()
    scenes = [
        (hook(), 2.8),
        (title(), 2.6),
        (scene_clock('Asia: 7pm to 4am ET', ['After the open, gold usually', 'moves in a tighter range.'], 'ASIA', ('ASIA', '7pm to 4am', SLATE)), 4.0),
        (scene_clock('London opens at 3am ET', ['The first move is often a fake one.', 'Let it show its hand.'], 'LONDON', ('LONDON', 'opens 3am', CYAN), 'CAREFUL: FAKE MOVES', RED), 4.0),
        (scene_clock('London + New York overlap', ['8am to 12pm ET: the most volume', 'and the cleanest trends.'], 'OVERLAP', ('BEST', '8am to 12pm', LIME), 'BEST WINDOW', LIME), 4.2),
        (scene_clock('8:30am ET: US data', ['CPI, jobs, GDP.', 'Gold can jump in seconds.'], 'NEW YORK', ('8:30am', 'US news', ORANGE), 'NEWS TIME', ORANGE), 4.0),
        (data_scene(avg, days), 5.0),
        (dst(), 4.6),
        (summary(), 4.0),
        (mv.end_card('Follow for more gold notes.'), 3.4),
    ]
    music = opt.get('--music', 'i01.m4a'); start = opt.get('--music-start', '0')
    os.makedirs(out, exist_ok=True)
    name = f'wendlingfx-{day.isoformat()}-gold-hours.mp4'
    track = os.path.join('/tmp', 'gh-music.m4a')
    import subprocess
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', start, '-i', os.path.join(HERE, 'music', music), '-af', 'afade=t=in:d=0.4', '-c:a', 'aac', '-b:a', '192k', track], check=True)
    mv.render(scenes, os.path.join(out, name), track)
    peak = max(avg, key=avg.get)
    text = ('Best hours to trade gold (XAU/USD), New York time: London opens 3am ET, best window 8am to 12pm ET, '
            'US data at 8:30am ET. Our chart: gold\'s average hourly range, last %d trading days. Save it. '
            '#xauusd #gold #forex #trading #daytrading' % days)
    print(json.dumps({'file': name, 'text': text, 'music': music, 'peak': [peak, round(avg[peak], 2)]}))


if __name__ == '__main__':
    main()
