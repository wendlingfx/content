#!/usr/bin/env python3
"""Wendling FX: schematic illustrations for the /start/ guide (our own drawings, not screenshots).
Usage: python3 tools/make_guide_art.py OUT_DIR"""
import os, sys
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from make_card import unb, inter
BG, PANEL, LINE, TXT, MUT, LIME = (14, 14, 14), (24, 24, 24), (48, 48, 48), (240, 240, 240), (150, 150, 150), (198, 255, 61)
W, H = 1200, 680
def base(title):
    img = Image.new('RGB', (W, H), BG); d = ImageDraw.Draw(img)
    d.rounded_rectangle([40, 40, W - 40, H - 40], radius=28, fill=PANEL, outline=LINE, width=2)
    d.text((90, 80), title, font=unb(40, 700), fill=TXT)
    return img, d
def field(d, x, y, w, label, value, hl=False):
    d.text((x, y), label, font=inter(26, 'Medium'), fill=MUT)
    d.rounded_rectangle([x, y + 40, x + w, y + 104], radius=14, fill=(32, 32, 32), outline=LIME if hl else LINE, width=3 if hl else 2)
    d.text((x + 22, y + 56), value, font=inter(30, 'SemiBold'), fill=TXT)
def button(d, x, y, w, text):
    d.rounded_rectangle([x, y, x + w, y + 80], radius=40, fill=LIME)
    tw = d.textlength(text, font=inter(32, 'SemiBold')); d.text((x + (w - tw) / 2, y + 20), text, font=inter(32, 'SemiBold'), fill=(10, 10, 10))
def tag(d, x, y, text):
    f = inter(24, 'SemiBold'); tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + 32, y + 46], radius=10, fill=(40, 52, 10)); d.text((x + 16, y + 9), text, font=f, fill=LIME)
def main():
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    # 1. account type
    img, d = base('Open a live account')
    field(d, 90, 170, 300, 'Account type', 'Zero', True); field(d, 450, 170, 300, 'Platform', 'cTrader', True); field(d, 810, 170, 300, 'Currency', 'USD', True)
    field(d, 90, 330, 300, 'Leverage', 'Highest offered'); tag(d, 450, 410, 'Pick these three: Zero, cTrader, USD')
    button(d, 90, 520, 420, 'Create account'); img.save(os.path.join(out, 'account.png'))
    # 2. verify
    img, d = base('Verify your identity')
    for i, (t, s) in enumerate([('Photo ID', 'Passport or ID card'), ('Proof of address', 'Recent bill or bank statement')]):
        x = 90 + i * 520; d.rounded_rectangle([x, 170, x + 480, 450], radius=22, fill=(32, 32, 32), outline=LINE, width=2)
        d.rounded_rectangle([x + 40, 210, x + 180, 300], radius=12, outline=LIME, width=4); d.line([(x + 60, 240), (x + 160, 240)], fill=LIME, width=4); d.line([(x + 60, 268), (x + 130, 268)], fill=LIME, width=4)
        d.text((x + 40, 330), t, font=inter(34, 'SemiBold'), fill=TXT); d.text((x + 40, 380), s, font=inter(26, 'Regular'), fill=MUT)
    tag(d, 90, 500, 'Upload both in the Fusion Client Hub'); img.save(os.path.join(out, 'verify.png'))
    # 3. fund
    img, d = base('Fund the account')
    field(d, 90, 170, 480, 'Deposit to', 'cTrader Zero account (USD)', True); field(d, 630, 170, 480, 'Amount', 'US$ 500 or more', True)
    for i, m in enumerate(['Card', 'PayPal', 'Skrill', 'Neteller']):
        x = 90 + i * 210; d.rounded_rectangle([x, 350, x + 190, 420], radius=14, fill=(32, 32, 32), outline=LINE, width=2)
        tw = d.textlength(m, font=inter(26, 'Medium')); d.text((x + (190 - tw) / 2, 368), m, font=inter(26, 'Medium'), fill=TXT)
    button(d, 90, 500, 360, 'Deposit'); img.save(os.path.join(out, 'fund.png'))
    # 4. start copying form
    img, d = base('Start copying')
    field(d, 90, 170, 1020, 'Copy from account', 'Your live cTrader account', True); field(d, 90, 320, 480, 'Amount to allocate', 'US$ 500 or more', True)
    d.text((630, 330), 'Fees', font=inter(26, 'Medium'), fill=MUT)
    for i, (k, v) in enumerate([('Performance', '30% of new profit'), ('Management', '0%'), ('Volume', '0')]):
        d.text((630, 380 + i * 40), k, font=inter(28, 'Regular'), fill=MUT); d.text((870, 380 + i * 40), v, font=inter(28, 'SemiBold'), fill=TXT)
    button(d, 90, 520, 420, 'Start copying'); img.save(os.path.join(out, 'copyform.png'))
    # 5. equity stop loss
    img, d = base('Set your loss limit')
    d.rounded_rectangle([90, 170, 560, 520], radius=18, fill=(32, 32, 32), outline=LINE, width=2)
    for i, t in enumerate(['Add funds', 'Remove funds', 'Set equity stop loss', 'Stop copying']):
        y = 190 + i * 80
        if i == 2: d.rounded_rectangle([105, y, 545, y + 66], radius=12, fill=(40, 52, 10))
        d.text((130, y + 16), t, font=inter(30, 'SemiBold' if i == 2 else 'Regular'), fill=LIME if i == 2 else TXT)
    field(d, 630, 200, 480, 'Stop copying if equity falls to', 'US$ 400 (example)', True)
    d.text((630, 340), 'Copying stops and copied positions', font=inter(26, 'Regular'), fill=MUT); d.text((630, 376), 'are closed at that level.', font=inter(26, 'Regular'), fill=MUT)
    button(d, 630, 450, 300, 'Save'); img.save(os.path.join(out, 'stoploss.png'))
    # 6. hedging check
    img, d = base('Check your account type')
    for i, (t, ok) in enumerate([('Hedging', True), ('Netting', False)]):
        x = 90 + i * 520; d.rounded_rectangle([x, 170, x + 480, 440], radius=22, fill=(32, 32, 32), outline=LIME if ok else LINE, width=3 if ok else 2)
        d.text((x + 40, 210), t, font=unb(44, 700), fill=LIME if ok else MUT)
        d.text((x + 40, 300), 'Can copy' if ok else 'Cannot copy', font=inter(32, 'SemiBold'), fill=TXT)
        d.text((x + 40, 350), 'Use this one' if ok else 'Open a hedging account', font=inter(26, 'Regular'), fill=MUT)
    tag(d, 90, 500, 'cTrader Copy works with hedging accounts'); img.save(os.path.join(out, 'hedging.png'))
if __name__ == '__main__':
    main()
