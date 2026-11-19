"""Wendling FX: content type header (option C, approved 19/11): the type word big at the top, in the type colour,
with a small 'WHAT / FORMAT' line under it. Gains and losses keep lime and red; the type colour is only for the header."""
import os
from PIL import ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
RED = (255, 77, 77); MUTED = (150, 150, 150); BG = (10, 10, 10)

# kind: (big word, small line, colour)
TYPES = {
    'day':     ('DAILY',   'CLOSE  /  IMAGE',  (198, 255, 61)),
    'week':    ('WEEKLY',  'CLOSE  /  VIDEO',  (34, 211, 238)),
    'month':   ('MONTHLY', 'CLOSE  /  VIDEO',  (250, 190, 60)),
    'diary':   ('LIVE',    'TRADES  /  VIDEO', (245, 245, 245)),
    'growth':  ('GROWTH',  'ACCOUNT  /  VIDEO', (167, 139, 250)),
    'ctrader': ('LEARN',   'COPY TRADING  /  VIDEO', (42, 171, 238)),
}

def _unb(size, w=900):
    f = ImageFont.truetype(os.path.join(HERE, 'fonts', 'Unbounded.ttf'), size)
    try: f.set_variation_by_axes([w])
    except Exception: pass
    return f

def _inter(size):
    return ImageFont.truetype(os.path.join(HERE, 'fonts', 'Inter-SemiBold.otf'), size)

def _mix(c, a): return tuple(int(BG[i] + (c[i] - BG[i]) * a) for i in range(3))

def header(d, kind, a=1.0, compact=False, fmt=None):
    """Full: word up to 150 px at y 70, small line at y 250 (ends near y 290).
    Compact (for inner video scenes): word 64 px at y 92, small line at y 176 (ends near y 210)."""
    word, line, col = TYPES[kind]
    if fmt: line = line.split('/')[0].strip() + '  /  ' + fmt
    size, y, ly, ls = (64, 92, 176, 26) if compact else (150, 70, 250, 32)
    while size > 60 and d.textlength(word, font=_unb(size)) > 860: size -= 4
    f = _unb(size); d.text((70, y), word, font=f, fill=_mix(col, a))
    if kind == 'diary':  # live: red dot after the word
        x = 70 + d.textlength(word, font=f) + size * 0.25; r = size * 0.13; cy = y + size * 0.62
        d.ellipse([x, cy - r, x + 2 * r, cy + r], fill=_mix(RED, a))
    d.text((78, ly), line, font=_inter(ls), fill=_mix(MUTED, a))
