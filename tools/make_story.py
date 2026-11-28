#!/usr/bin/env python3
"""Wendling FX: short MINDSET story video, one line per scene over a darkened stock photo (tools/bg/mindset),
slow zoom, big text, WFX end card. No account numbers.

Usage: python3 tools/make_story.py OUT_DIR [--story NAME] [--music FILE] [--date YYYY-MM-DD]
Prints one JSON line: {"file", "text", "music"}.
"""
import json, math, os, sys, datetime as dt
from PIL import Image, ImageDraw
import make_video as mv
from brand import header

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = mv.W, mv.H

STORIES = {
    'i-changed': {
        'scenes': [  # (line, photo, seconds, colour)
            ('I failed.', 'forex-8207730.jpg', 2.3, mv.WHITE),
            ('I felt lost.', 'man-8575459.jpg', 2.3, mv.WHITE),
            ('I questioned myself.', 'stocks-6377806.jpg', 2.5, mv.WHITE),
            ('I tried again.', 'computer-3033135.jpg', 2.3, mv.WHITE),
            ('I kept going.', 'trader-5129770.jpg', 2.3, mv.WHITE),
            ('I changed.', 'stock-trading-6525083.jpg', 3.6, mv.LIME),
        ],
        'end': 'One trade at a time.',
        'text': 'I failed. I felt lost. I questioned myself. I tried again. I kept going. I changed. '
                '#tradingmindset #forex #trading #discipline #copytrading',
    },
}


def photo(name):
    im = Image.open(os.path.join(HERE, 'bg', 'mindset', name)).convert('RGB')
    sc = max(W / im.width, H / im.height) * 1.08  # room for the slow zoom
    return im.resize((int(im.width * sc) + 2, int(im.height * sc) + 2), Image.LANCZOS)


def overlay():
    col = Image.new('L', (1, H))
    for y in range(H):
        t = y / H
        a = 0.60
        if t < 0.22: a = 0.60 + (0.22 - t) / 0.22 * 0.25
        if t > 0.62: a = 0.60 + (t - 0.62) / 0.38 * 0.34
        col.putpixel((0, y), int(a * 255))
    return col.resize((W, H))


SHADE = None


def scene(line, pic, dur, colour, first=False):
    big = photo(pic)
    def fn(t):
        z = 1.0 + 0.07 * (t / dur)  # slow push in
        w, h = int(W * 1.08 / z), int(H * 1.08 / z)
        x = (big.width - w) // 2; y = (big.height - h) // 2
        img = big.crop((x, y, x + w, y + h)).resize((W, H), Image.BILINEAR)
        img = Image.composite(Image.new('RGB', (W, H), (6, 6, 6)), img, SHADE)
        d = ImageDraw.Draw(img)
        header(d, 'mindset', subline=False, compact=not first)
        a = 1.0 if first else mv.ease(t / 0.35)  # first frame fully drawn: TikTok uses it as the cover
        size = 120
        while size > 60 and d.textlength(line, font=mv.unb(size, 800)) > 860: size -= 4
        words = line.split(' ')
        lines = [line]
        if size < 96 and len(words) > 1:  # two lines, bigger type
            k = len(words) // 2 + (len(words) % 2)
            lines = [' '.join(words[:k]), ' '.join(words[k:])]
            size = 120
            while size > 60 and max(d.textlength(s, font=mv.unb(size, 800)) for s in lines) > 860: size -= 4
        f = mv.unb(size, 800); lh = size * 1.18
        y0 = 860 - (len(lines) - 1) * lh / 2 + (1 - a) * 40
        for i, s in enumerate(lines):
            tw = d.textlength(s, font=f); xx = mv.CX - tw / 2; yy = y0 + i * lh
            d.text((xx + 4, yy + 5), s, font=f, fill=(0, 0, 0))
            d.text((xx, yy), s, font=f, fill=tuple(int(c * a + 6 * (1 - a)) for c in colour))
        if t > dur - 0.25:  # quick dip to black between scenes
            img = Image.blend(img, Image.new('RGB', (W, H), (6, 6, 6)), (t - (dur - 0.25)) / 0.25 * 0.85)
        return img
    return fn


def main():
    global SHADE
    args = sys.argv[1:]
    if not args: raise SystemExit(__doc__)
    out = args[0]; opt = dict(zip(args[1::2], args[2::2]))
    st = STORIES[opt.get('--story', 'i-changed')]
    day = dt.date.fromisoformat(opt['--date']) if '--date' in opt else dt.date.today()
    SHADE = overlay()
    scenes = [(scene(l, p, d, c, first=(i == 0)), d) for i, (l, p, d, c) in enumerate(st['scenes'])]
    scenes.append((mv.end_card(st['end']), 3.4))
    music = opt.get('--music', 'i02.m4a'); start = opt.get('--music-start', '0')
    import subprocess
    track = '/tmp/story-music.m4a'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', start, '-i', os.path.join(HERE, 'music', music), '-af', 'afade=t=in:d=0.3', '-c:a', 'aac', '-b:a', '192k', track], check=True)
    os.makedirs(out, exist_ok=True)
    name = f"wendlingfx-story-{opt.get('--story', 'i-changed')}-{day.isoformat()}.mp4"
    mv.render(scenes, os.path.join(out, name), track)
    print(json.dumps({'file': name, 'text': st['text'], 'music': music}))


if __name__ == '__main__':
    main()
