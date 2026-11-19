#!/usr/bin/env python3
"""Wendling FX: original Sunday memes (1080x1920 PNG) in the brand style. No third-party meme templates or images.
Usage: python3 tools/make_meme.py OUT_DIR [ID ...]   (all memes in tools/memes.json when no ID is given)
Prints one JSON line per meme: {"id", "file", "caption"}."""
import json, os, sys, random
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import make_card as mc
from make_card import unb, inter, W, H, CX, WHITE, MUTED, LIME, RED, PANEL, LINE, DIM
from brand import header
PINK = (244, 114, 182)

def wrap(d, text, font, maxw):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def block(d, y, text, font, fill, maxw=820, gap=1.25):
    for ln in wrap(d, text, font, maxw):
        mc.tc(d, y, ln, font, fill); y += int(font.size * gap)
    return y

def chart(d, box, kind, seed):
    x0, y0, x1, y1 = box; rnd = random.Random(seed); n = 60; pts = []
    for i in range(n):
        t = i / (n - 1)
        if kind == 'flat': v = 0.5 + rnd.uniform(-0.01, 0.01)
        elif kind == 'spike': v = 0.55 + rnd.uniform(-0.02, 0.02) if i < 40 else (0.08 if i in (40, 41) else 0.75 + rnd.uniform(-0.03, 0.03))
        elif kind == 'chop': v = 0.5 + (0.38 if i % 2 else -0.38) * (0.4 + 0.6 * rnd.random())
        else: v = 0.85 - 0.7 * t + rnd.uniform(-0.04, 0.04)
        pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * min(1, max(0, v))))
    d.rounded_rectangle([x0 - 30, y0 - 30, x1 + 30, y1 + 30], radius=24, fill=PANEL, outline=LINE, width=2)
    d.line(pts, fill=LIME, width=7, joint='curve')

def make(m, out):
    img, d = mc.canvas(); header(d, 'fun')
    f_set, f_pun = unb(60, 600), unb(70, 700)
    if m['kind'] == 'text':
        y = block(d, 560, m['setup'], f_set, WHITE)
        block(d, y + 90, m['punch'], f_pun, PINK)
    elif m['kind'] == 'chart':
        y = block(d, 400, m['setup'], f_set, WHITE)
        y = block(d, y + 30, m['punch'], f_pun, PINK)
        chart(d, (120, y + 90, 900, y + 600), m['chart'], m['id'])
    else:
        for i, (t, b) in enumerate([m['l'], m['r']]):
            yb = 380 + i * 560
            d.rounded_rectangle([70, yb, W - 150, yb + 480], radius=28, fill=PANEL, outline=PINK if i else LINE, width=3 if i else 2)
            mc.tc(d, yb + 60, t, unb(58, 700), PINK if i else MUTED)
            block(d, yb + 190, b, unb(54, 600), WHITE, maxw=720)
    f = unb(64); w1 = d.textlength('wendling', font=f); w2 = d.textlength('fx', font=f); xx = CX - (w1 + w2) / 2
    d.text((xx, 1668), 'wendling', font=f, fill=WHITE); d.text((xx + w1, 1668), 'fx', font=f, fill=LIME)
    mc.tc(d, 1760, 'Free daily results on Telegram: t.me/wendlingfx', inter(32, 'Medium'), MUTED)
    name = f"wendlingfx-meme-{m['id']}.png"; img.save(os.path.join(out, name), optimize=True)
    return name

def main():
    out = sys.argv[1]; ids = sys.argv[2:]; os.makedirs(out, exist_ok=True)
    for m in json.load(open(os.path.join(HERE, 'memes.json'))):
        if ids and m['id'] not in ids: continue
        name = make(m, out)
        cap = (m.get('setup', '') + ' ' + m.get('punch', '')).strip() if m['kind'] != 'vs' else f"{m['l'][0]} vs {m['r'][0]}"
        print(json.dumps({'id': m['id'], 'file': name, 'caption': cap}))

if __name__ == '__main__':
    main()
