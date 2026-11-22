#!/usr/bin/env python3
"""Wendling FX: builds the free e-book (PDF) from tools/guide.json.

Usage: python3 tools/make_guide.py [out.pdf]   (default: site/guide/copy-trading-starter-guide.pdf)
Fonts: Unbounded (titles) and Inter (body) from tools/fonts; Inter ships as .otf, so it is converted to .ttf once in tools/fonts/ttf/.
"""
import json, os, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Table, TableStyle, KeepTogether
from reportlab.lib.styles import ParagraphStyle

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BG, LIME, INK, MUTED, LINE = HexColor('#0A0A0A'), HexColor('#C6FF3D'), HexColor('#141414'), HexColor('#5C5C5C'), HexColor('#E6E6E6')

def ttf(w):
    d = os.path.join(HERE, 'fonts', 'ttf'); os.makedirs(d, exist_ok=True)
    out = os.path.join(d, f'Inter-{w}.ttf')
    if not os.path.exists(out):
        from fontTools.ttLib import TTFont as FT, newTable
        from fontTools.pens.cu2quPen import Cu2QuPen
        from fontTools.pens.ttGlyphPen import TTGlyphPen
        f = FT(os.path.join(HERE, 'fonts', f'Inter-{w}.otf')); gs = f.getGlyphSet(); order = f.getGlyphOrder(); glyphs = {}
        for n in order:
            pen = TTGlyphPen(gs); gs[n].draw(Cu2QuPen(pen, 1.0, reverse_direction=True)); glyphs[n] = pen.glyph()
        f['loca'] = newTable('loca'); g = newTable('glyf'); g.glyphOrder = order; g.glyphs = glyphs; f['glyf'] = g
        del f['CFF ']
        m = newTable('maxp'); m.tableVersion = 0x00010000
        for a in ('maxZones', 'maxTwilightPoints', 'maxStorage', 'maxFunctionDefs', 'maxInstructionDefs', 'maxStackElements', 'maxSizeOfInstructions', 'maxComponentElements'): setattr(m, a, 0)
        m.maxZones = 1; f['maxp'] = m
        f['head'].glyphDataFormat = 0
        f['post'].formatType = 2.0; f['post'].extraNames = []; f['post'].mapping = {}; f['post'].glyphOrder = order
        f.sfntVersion = '\x00\x01\x00\x00'; f.save(out)
    return out

def fonts():
    pdfmetrics.registerFont(TTFont('Unb', os.path.join(HERE, 'fonts', 'Unbounded.ttf')))
    for w in ('Regular', 'Medium', 'SemiBold'): pdfmetrics.registerFont(TTFont('Inter-' + w, ttf(w)))

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'site', 'guide', 'copy-trading-starter-guide.pdf')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    g = json.load(open(os.path.join(HERE, 'guide.json')))
    fonts()
    W, H = A4
    body = ParagraphStyle('b', fontName='Inter-Regular', fontSize=11, leading=17, textColor=INK, spaceAfter=8)
    h2 = ParagraphStyle('h', fontName='Unb', fontSize=18, leading=23, textColor=INK, spaceBefore=6, spaceAfter=10)
    li = ParagraphStyle('l', parent=body, leftIndent=14, bulletIndent=0, spaceAfter=5)
    tip = ParagraphStyle('t', parent=body, fontName='Inter-Medium', textColor=INK, spaceAfter=0)
    cta = ParagraphStyle('c', parent=body, fontName='Inter-SemiBold', fontSize=12, leading=19)

    def cover(c, d):
        c.setFillColor(BG); c.rect(0, 0, W, H, stroke=0, fill=1)
        c.setFillColor(LIME); c.rect(0, H - 8 * mm, W, 8 * mm, stroke=0, fill=1)
        c.setFont('Unb', 40); c.setFillColor(HexColor('#FFFFFF')); c.drawString(22 * mm, H - 60 * mm, 'w'); wd = c.stringWidth('w', 'Unb', 40)
        c.setFillColor(LIME); c.drawString(22 * mm + wd, H - 60 * mm, 'fx')
        c.setFillColor(HexColor('#FFFFFF')); y = H - 120 * mm
        for line in ('The Copy', 'Trading', 'Starter Guide'):
            c.setFont('Unb', 38); c.drawString(22 * mm, y, line); y -= 16 * mm
        c.setFont('Inter-Regular', 14); c.setFillColor(HexColor('#BDBDBD')); c.drawString(22 * mm, y - 6 * mm, g['subtitle'])
        c.setFont('Inter-Medium', 11); c.setFillColor(HexColor('#A3A3A3')); c.drawString(22 * mm, 24 * mm, 'Free guide by Wendling FX  ·  wendlingfx.com')

    def page(c, d):
        c.setFillColor(LIME); c.rect(0, H - 4 * mm, W, 4 * mm, stroke=0, fill=1)
        c.setFont('Inter-Medium', 8.5); c.setFillColor(MUTED)
        c.drawString(22 * mm, 12 * mm, 'Wendling FX  ·  The Copy Trading Starter Guide'); c.drawRightString(W - 22 * mm, 12 * mm, str(d.page - 1))

    doc = BaseDocTemplate(out, pagesize=A4, title=g['title'], author='Wendling FX', subject=g['subtitle'],
                          leftMargin=22 * mm, rightMargin=22 * mm, topMargin=24 * mm, bottomMargin=24 * mm)
    fr = Frame(22 * mm, 24 * mm, W - 44 * mm, H - 48 * mm, id='f')
    doc.addPageTemplates([PageTemplate('cover', [fr], onPage=cover), PageTemplate('page', [fr], onPage=page)])
    from reportlab.platypus import NextPageTemplate
    story = [NextPageTemplate('page'), PageBreak()]
    for i, s in enumerate(g['sections']):
        block = [Paragraph(s['h'], h2)]
        block += [Paragraph(p, body) for p in s.get('p', [])]
        block += [Paragraph(x, li, bulletText='•') for x in s.get('list', [])]
        story.append(KeepTogether(block[:2])); story += block[2:]
        if s.get('tip'):
            t = Table([[Paragraph(s['tip'], tip)]], colWidths=[W - 44 * mm])
            t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), HexColor('#F1FFD2')), ('LINEBEFORE', (0, 0), (0, -1), 3, LIME),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
            story += [Spacer(1, 4), t]
        if s.get('cta'):
            story += [Spacer(1, 6)] + [Paragraph(x, cta) for x in s['cta'].split('\n')]
        story.append(Spacer(1, 14))
    story += [Spacer(1, 10), Paragraph(g['disclaimer'], ParagraphStyle('d', parent=body, fontSize=8.5, leading=12, textColor=MUTED))]
    doc.build(story)
    print(json.dumps({'file': os.path.relpath(out, ROOT)}))

if __name__ == '__main__':
    main()
