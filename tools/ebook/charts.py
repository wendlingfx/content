#!/usr/bin/env python3
"""Wendling FX e-book: draws every chart of the free guide as PNG (2x) in brand style.
Data: tools/ebook/market.json and h1.json (copies of wendlingfx.com/data/market.json and market-h1.json).
Usage: python3 tools/ebook/charts.py OUT_DIR
"""
import json, os, sys, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import Rectangle, FancyBboxPatch, Polygon

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(os.path.dirname(HERE), 'fonts')
for f in ('Unbounded.ttf', 'ttf/Inter-Regular.ttf', 'ttf/Inter-Medium.ttf', 'ttf/Inter-SemiBold.ttf'):
    p = os.path.join(FONTS, f)
    if os.path.exists(p): fm.fontManager.addfont(p)
BG, PANEL, LINE, TXT, MUTED = '#0A0A0A', '#141414', '#262626', '#FFFFFF', '#A3A3A3'
LIME, RED, BLUE, AMBER = '#C6FF3D', '#FF4D4D', '#5AB4FF', '#FFC24B'
plt.rcParams.update({'font.family': 'Inter', 'font.size': 11, 'text.color': TXT, 'axes.labelcolor': MUTED,
                     'axes.edgecolor': LINE, 'xtick.color': MUTED, 'ytick.color': MUTED, 'axes.facecolor': BG, 'figure.facecolor': BG,
                     'savefig.facecolor': BG, 'axes.grid': True, 'grid.color': '#1C1C1C', 'grid.linewidth': 0.8})
OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/ebook'
os.makedirs(OUT, exist_ok=True)

def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=200, bbox_inches='tight', pad_inches=0.25); plt.close(fig)

def title(ax, t, sub=None):
    ax.set_title(t, loc='left', fontsize=15, fontweight='semibold', color=TXT, pad=18 if sub else 10, fontfamily='Inter')
    if sub: ax.text(0, 1.015, sub, transform=ax.transAxes, color=MUTED, fontsize=10)

h1 = json.load(open(os.path.join(HERE, 'h1.json')))['h1']['XAUUSD']
O = [b[1] for b in h1]; H = [b[2] for b in h1]; L = [b[3] for b in h1]; C = [b[4] for b in h1]
N = len(C)

def candles(ax, o, h, l, c, x0=0, w=0.6):
    for i in range(len(c)):
        up = c[i] >= o[i]; col = LIME if up else RED
        ax.vlines(x0 + i, l[i], h[i], color=col, linewidth=0.8)
        ax.add_patch(Rectangle((x0 + i - w / 2, min(o[i], c[i])), w, max(abs(c[i] - o[i]), 0.0001 * c[i]), color=col, linewidth=0))

def ema(v, n):
    k = 2 / (n + 1); out = [v[0]]
    for x in v[1:]: out.append(out[-1] + k * (x - out[-1]))
    return out

def rsi(v, n=14):
    out = [50.0] * len(v); g = l = 0.0
    for i in range(1, len(v)):
        ch = v[i] - v[i - 1]; up, dn = max(ch, 0), max(-ch, 0)
        if i <= n: g += up / n; l += dn / n
        else: g = (g * (n - 1) + up) / n; l = (l * (n - 1) + dn) / n
        if i >= n: out[i] = 100 - 100 / (1 + (g / l if l else 99))
    return out

def plain(ax):
    ax.grid(False); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_visible(False)

# 1. trading sessions (UTC, winter)
fig, ax = plt.subplots(figsize=(10, 3.2))
sessions = [('Sydney', 22, 7, BLUE), ('Tokyo', 0, 9, AMBER), ('London', 8, 17, LIME), ('New York', 13, 22, RED)]
for i, (n, a, b, col) in enumerate(sessions):
    y = 3 - i
    spans = [(a, b - a)] if a < b else [(a, 24 - a), (0, b)]
    ax.broken_barh(spans, (y - 0.32, 0.64), color=col, alpha=0.9)
    ax.text(-0.4, y, n, ha='right', va='center', fontsize=11, fontweight='medium')
ax.axvspan(13, 17, color='#FFFFFF', alpha=0.06); ax.text(15, 4.0, 'London + New York overlap', ha='center', color=TXT, fontsize=10)
ax.set_xlim(0, 24); ax.set_ylim(-0.7, 4.4); ax.set_yticks([]); ax.set_xticks(range(0, 25, 2)); ax.set_xticklabels([f'{h:02d}:00' for h in range(0, 25, 2)], fontsize=9)
ax.grid(False)
for sp in ('top', 'right', 'left'): ax.spines[sp].set_visible(False)
title(ax, 'The 24-hour market', 'Main trading sessions in UTC (northern winter times, approximate)')
save(fig, 'sessions.png')

# 2. candle anatomy
fig, ax = plt.subplots(figsize=(8, 4.6)); plain(ax)
for x, (o, c, hi, lo, col, lab) in enumerate([(2, 6, 7.2, 1.2, LIME, 'Bullish candle'), (6, 2.4, 7, 1.4, RED, 'Bearish candle')]):
    cx = 2.2 + x * 4.2
    ax.vlines(cx, lo, hi, color=col, linewidth=2.4)
    ax.add_patch(Rectangle((cx - 0.55, min(o, c)), 1.1, abs(c - o), color=col))
    ax.text(cx, 0.35, lab, ha='center', fontsize=12, fontweight='semibold')
    ax.annotate('High', (cx, hi), (cx + 1.25, hi), color=MUTED, va='center', arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
    ax.annotate('Low', (cx, lo), (cx + 1.25, lo), color=MUTED, va='center', arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
    ax.annotate('Close' if c > o else 'Open', (cx + 0.55, max(o, c)), (cx + 1.25, max(o, c)), color=TXT, va='center', arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
    ax.annotate('Open' if c > o else 'Close', (cx + 0.55, min(o, c)), (cx + 1.25, min(o, c)), color=TXT, va='center', arrowprops=dict(arrowstyle='-', color=MUTED, lw=0.8))
    ax.text(cx - 0.8, (hi + max(o, c)) / 2, 'wick', ha='right', va='center', color=MUTED, fontsize=9)
    ax.text(cx - 0.8, (o + c) / 2, 'body', ha='right', va='center', color=MUTED, fontsize=9)
ax.set_xlim(0, 10.5); ax.set_ylim(0, 8)
save(fig, 'candle.png')

# 3. trend structure on gold H1 (zigzag swings)
def swings(v_hi, v_lo, pct=0.014):
    pts, mode, piv, pi = [], None, C[0], 0
    for i in range(N):
        if mode != 'down' and H[i] >= piv: piv, pi, mode = H[i], i, 'up' if mode is None else mode
        if mode == 'up':
            if H[i] > piv: piv, pi = H[i], i
            elif L[i] < piv * (1 - pct): pts.append((pi, piv, 'H')); mode, piv, pi = 'down', L[i], i
        elif mode == 'down':
            if L[i] < piv: piv, pi = L[i], i
            elif H[i] > piv * (1 + pct): pts.append((pi, piv, 'L')); mode, piv, pi = 'up', H[i], i
    return pts
sw = swings(H, L)
fig, ax = plt.subplots(figsize=(10, 4.6))
candles(ax, O, H, L, C)
if len(sw) > 1:
    ax.plot([p[0] for p in sw], [p[1] for p in sw], color=TXT, linewidth=1.2, alpha=0.8)
    prev = {'H': None, 'L': None}
    for i, v, t in sw:
        lab = ('HH' if prev['H'] is not None and v > prev['H'] else 'LH' if prev['H'] is not None else 'H') if t == 'H' else ('HL' if prev['L'] is not None and v > prev['L'] else 'LL' if prev['L'] is not None else 'L')
        prev[t] = v
        ax.text(i, v * (1.0025 if t == 'H' else 0.9975), lab, ha='center', va='bottom' if t == 'H' else 'top', fontsize=9, fontweight='semibold', color=LIME if lab in ('HH', 'HL') else RED if lab in ('LH', 'LL') else MUTED)
ax.set_xlim(-2, N + 1); ax.set_xticks([])
title(ax, 'Market structure', 'Gold (XAU/USD), 1-hour candles, recent weeks. HH/HL = higher highs and lows, LH/LL = lower ones')
save(fig, 'structure.png')

# 4. support and resistance
fig, ax = plt.subplots(figsize=(10, 4.6))
candles(ax, O, H, L, C)
lo_r, hi_r = min(L), max(H)
piv = [v for _, v, _ in swings(H, L, 0.006) if lo_r + 0.15 * (hi_r - lo_r) < v < hi_r - 0.15 * (hi_r - lo_r)]
best = None
for v in piv:
    n = sum(1 for w in piv if abs(w - v) / v < 0.0035)
    if best is None or n > best[0]: best = (n, v)
lvl = sum(w for w in piv if abs(w - best[1]) / best[1] < 0.0035) / best[0]
ax.axhspan(lvl * 0.9985, lvl * 1.0015, color=AMBER, alpha=0.18)
ax.axhline(lvl, color=AMBER, linewidth=1.3, linestyle='--')
ax.text(2, lvl * 1.004, f'Zone near {lvl:,.0f}: price turned here {best[0]} times', color=AMBER, fontsize=9.5, va='bottom')
ax.set_xlim(-2, N + 1); ax.set_xticks([])
title(ax, 'Support and resistance', 'Gold (XAU/USD), 1-hour candles. Levels where price stopped before tend to matter again')
save(fig, 'sr.png')

# 5+6. EMAs and RSI
e20, e50, r = ema(C, 20), ema(C, 50), rsi(C)
fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6.2), gridspec_kw={'height_ratios': [3, 1.2], 'hspace': 0.08}, sharex=True)
candles(ax, O, H, L, C)
ax.plot(range(N), e20, color=AMBER, linewidth=1.6, label='EMA 20 (fast)'); ax.plot(range(N), e50, color=BLUE, linewidth=1.6, label='EMA 50 (slow)')
leg = ax.legend(loc='lower left', frameon=False, fontsize=10)
ax.set_xlim(-2, N + 1)
title(ax, 'Moving averages and RSI', 'Gold (XAU/USD), 1-hour candles. RSI(14) below: 70+ stretched up, 30- stretched down')
ax2.plot(range(N), r, color=LIME, linewidth=1.3); ax2.axhline(70, color=RED, linewidth=0.9, linestyle='--'); ax2.axhline(30, color=LIME, linewidth=0.9, linestyle='--')
ax2.fill_between(range(N), 70, 100, color=RED, alpha=0.06); ax2.fill_between(range(N), 0, 30, color=LIME, alpha=0.06)
ax2.set_ylim(0, 100); ax2.set_yticks([30, 50, 70]); ax2.set_xticks([]); ax2.text(1, 88, 'RSI 14', color=MUTED, fontsize=9)
save(fig, 'ema_rsi.png')

# 7. candlestick patterns grid
pats = [('Hammer', [(5, 5.6, 6, 2.2)], 'Long lower wick after a fall:\nbuyers stepped in'),
        ('Shooting star', [(5, 4.4, 7.8, 4.1)], 'Long upper wick after a rise:\nsellers pushed back'),
        ('Doji', [(5, 5.05, 7, 3)], 'Open = close: indecision'),
        ('Bullish engulfing', [(5.6, 4.4, 5.9, 4.1), (4.2, 6.4, 6.6, 4)], 'Second body swallows the first'),
        ('Bearish engulfing', [(4.4, 5.6, 5.9, 4.1), (5.9, 3.8, 6.2, 3.6)], 'The mirror image at the top'),
        ('Morning star', [(6.6, 4.6, 6.8, 4.4), (4.2, 4.3, 4.6, 3.8), (4.5, 6.4, 6.6, 4.3)], 'Fall, pause, strong recovery')]
fig, axs = plt.subplots(2, 3, figsize=(10, 6))
for ax, (n, cs, d) in zip(axs.flat, pats):
    plain(ax); ax.set_xlim(-1, 3); ax.set_ylim(-0.6, 9.4)
    x0 = 1 - (len(cs) - 1) * 0.5
    for i, (o, c, hi, lo) in enumerate(cs):
        col = LIME if c >= o else RED; x = x0 + i
        ax.vlines(x, lo, hi, color=col, linewidth=2); ax.add_patch(Rectangle((x - 0.28, min(o, c)), 0.56, max(abs(c - o), 0.06), color=col))
    ax.text(1, 8.7, n, ha='center', fontsize=12, fontweight='semibold')
    ax.text(1, -0.2, d, ha='center', va='bottom', fontsize=8.5, color=MUTED, linespacing=1.3)
    ax.add_patch(FancyBboxPatch((-0.9, -0.5), 3.8, 9.85, boxstyle='round,pad=0,rounding_size=0.25', fill=False, edgecolor=LINE, linewidth=1))
fig.subplots_adjust(wspace=0.06, hspace=0.08)
save(fig, 'patterns.png')

# 8. chart patterns schematic
fig, axs = plt.subplots(1, 3, figsize=(10, 3.4))
shapes = [('Double top', [0, 3, 5, 3.4, 5, 2.2, 1.2], 3.4, RED),
          ('Head and shoulders', [0, 3.5, 2.6, 5.2, 2.6, 3.4, 1.4], 2.6, RED),
          ('Ascending triangle', [0, 4.5, 2.2, 4.5, 3.1, 4.5, 3.7, 5.6], 4.5, LIME)]
for ax, (n, ys, neck, col) in zip(axs, shapes):
    plain(ax); xs = range(len(ys)); ax.plot(xs, ys, color=TXT, linewidth=2)
    ax.axhline(neck, color=col, linestyle='--', linewidth=1.2)
    if n == 'Ascending triangle': ax.plot([0.9, 6], [1.6, 4.1], color=LIME, linestyle='--', linewidth=1.2)
    ax.text(len(ys) / 2 - 0.5, 6.4, n, ha='center', fontsize=12, fontweight='semibold'); ax.set_ylim(-0.4, 7)
save(fig, 'chartpatterns.png')

# 9. risk reward
fig, ax = plt.subplots(figsize=(10, 3.8)); plain(ax)
entry, stop, tgt = 100, 96, 108
ax.add_patch(Rectangle((2, entry), 6, tgt - entry, color=LIME, alpha=0.18)); ax.add_patch(Rectangle((2, stop), 6, entry - stop, color=RED, alpha=0.2))
for y, lab, col in ((tgt, 'Target  +8', LIME), (entry, 'Entry', TXT), (stop, 'Stop  -4', RED)):
    ax.hlines(y, 2, 8, color=col, linewidth=1.6); ax.text(8.2, y, lab, va='center', color=col, fontsize=11, fontweight='semibold')
ax.text(5, 104, 'Reward 2', ha='center', fontsize=15, fontweight='semibold', color=LIME); ax.text(5, 98, 'Risk 1', ha='center', fontsize=15, fontweight='semibold', color=RED)
ax.text(0.2, 102, 'Risk : reward\n1 : 2', fontsize=14, fontweight='semibold', va='center')
ax.text(0.2, 97.2, 'Win 4 of 10 trades and still\nfinish ahead (before costs)', fontsize=9.5, color=MUTED, va='center')
ax.set_xlim(0, 10.5); ax.set_ylim(94.5, 109.5)
save(fig, 'riskreward.png')

# 10. drawdown recovery
loss = [10, 20, 30, 40, 50, 60, 75]; gain = [round(l / (100 - l) * 100, 1) for l in loss]
fig, ax = plt.subplots(figsize=(10, 4.2))
xs = range(len(loss))
ax.bar([x - 0.2 for x in xs], loss, width=0.38, color=RED, label='Loss')
ax.bar([x + 0.2 for x in xs], gain, width=0.38, color=LIME, label='Gain needed to get back')
for x, a, b in zip(xs, loss, gain):
    ax.text(x - 0.2, a + 4, f'-{a}%', ha='center', fontsize=9, color=RED); ax.text(x + 0.2, b + 4, f'+{b:g}%', ha='center', fontsize=9, color=LIME)
ax.set_xticks(list(xs)); ax.set_xticklabels([f'{l}% loss' for l in loss], fontsize=9); ax.set_yticks([]); ax.grid(False)
for s in ('top', 'right', 'left'): ax.spines[s].set_visible(False)
ax.legend(frameon=False, loc='upper left'); ax.set_ylim(0, 330)
title(ax, 'Why losses hurt more than gains help', 'The deeper the fall, the harder the climb')
save(fig, 'recovery.png')
print(json.dumps({'out': OUT, 'files': sorted(os.listdir(OUT))}))
