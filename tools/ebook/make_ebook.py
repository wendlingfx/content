#!/usr/bin/env python3
"""Wendling FX: builds the free e-book "Forex Foundations, Volume 1" as a PDF.

Usage: python3 tools/ebook/make_ebook.py [out.pdf]   (default: site/guide/forex-foundations.pdf)
Steps: draws the charts (charts.py, real data in market.json/h1.json), wraps content.html with the brand styles and prints it with headless Chrome.
Refresh the data first if you want newer charts: curl wendlingfx.com/data/market.json and market-h1.json into this folder.
"""
import os, subprocess, sys, shutil, json, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FONTS = os.path.join(ROOT, 'tools', 'fonts')

CSS = """
@font-face{font-family:Unb;src:url('file://%(f)s/Unbounded.ttf')}
@font-face{font-family:Inter;font-weight:400;src:url('file://%(f)s/Inter-Regular.otf')}
@font-face{font-family:Inter;font-weight:500;src:url('file://%(f)s/Inter-Medium.otf')}
@font-face{font-family:Inter;font-weight:600;src:url('file://%(f)s/Inter-SemiBold.otf')}
@page{size:A4;margin:0}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
html,body{margin:0;background:#0A0A0A}
body{font-family:Inter,sans-serif;color:#E9E9E9;font-size:10.6pt;line-height:1.55}
.page{width:210mm;height:297mm;padding:20mm 18mm 22mm;position:relative;overflow:hidden;page-break-after:always;background:#0A0A0A}
.page:after{content:"Wendling FX · Forex Foundations";position:absolute;left:18mm;bottom:10mm;font-size:7.5pt;color:#6B6B6B}
.page:before{content:"";position:absolute;top:0;left:0;right:0;height:3mm;background:#C6FF3D}
.cover:before,.cover:after,.dark:after{display:none}
.chap{font-family:Unb;font-size:22pt;line-height:1.15;color:#fff;margin:4mm 0 6mm;letter-spacing:-.02em}
.chap span{display:block;font-size:46pt;color:#C6FF3D;line-height:1;margin-bottom:2mm}
h3{font-family:Unb;font-size:12.5pt;color:#fff;margin:6mm 0 2mm;letter-spacing:-.01em}
p{margin:0 0 3mm}
b{color:#fff;font-weight:600}
img{width:100%%;border-radius:3mm;border:1px solid #262626;margin:2mm 0 4mm;display:block}
img.narrow{width:78%%;margin-left:auto;margin-right:auto}
.key{background:#141414;border-left:1.2mm solid #C6FF3D;border-radius:2mm;padding:3.5mm 4.5mm;margin:4mm 0;color:#D9D9D9}
.note{background:#141414;border:1px solid #262626;border-radius:3mm;padding:5mm;margin-top:10mm;color:#BDBDBD}
.grid2,.grid3{display:grid;gap:3mm;margin:3mm 0 4mm}.grid2{grid-template-columns:1fr 1fr}.grid3{grid-template-columns:1fr 1fr 1fr}
.tile{background:#141414;border:1px solid #262626;border-radius:3mm;padding:3.5mm 4mm}
.tile b{display:block;color:#C6FF3D;font-family:Unb;font-weight:500;font-size:10pt;margin-bottom:1.5mm}
.tile span{color:#BDBDBD;font-size:9.3pt;line-height:1.45}
table{width:100%%;border-collapse:collapse;margin:2mm 0 4mm;font-size:9.2pt}
th{text-align:left;color:#C6FF3D;font-weight:600;border-bottom:1px solid #3A3A3A;padding:2mm 2mm}
td{border-bottom:1px solid #222;padding:2mm 2mm;color:#D0D0D0;vertical-align:top}
ul{margin:1mm 0 3mm;padding-left:5mm}li{margin:1.2mm 0}
ul.flags li::marker{color:#FF4D4D}
.check ul{list-style:none;padding:0}.check li{padding-left:8mm;position:relative;margin:2.5mm 0}
.check li:before{content:"";position:absolute;left:0;top:.5mm;width:4mm;height:4mm;border:1.5px solid #C6FF3D;border-radius:1mm}
.flow{display:flex;align-items:center;gap:2mm;margin:4mm 0 5mm}.flow div{flex:1;background:#141414;border:1px solid #262626;border-radius:3mm;padding:3mm;font-size:9pt;text-align:center;color:#fff;min-height:16mm;display:flex;align-items:center;justify-content:center}
.flow i{color:#C6FF3D;font-style:normal;font-size:14pt}
.formula{font-family:Unb;font-size:11pt;color:#C6FF3D;background:#141414;border-radius:3mm;padding:4mm;text-align:center;margin:2mm 0 3mm}
.small{font-size:8.4pt;color:#8A8A8A}
.toc-h{font-family:Unb;font-size:30pt;color:#fff;margin:6mm 0 8mm}
ol.toc{list-style:none;padding:0;margin:0}ol.toc li{display:flex;gap:6mm;align-items:baseline;font-size:14pt;color:#fff;border-bottom:1px solid #222;padding:4mm 0}
ol.toc span{font-family:Unb;color:#C6FF3D;font-size:13pt;width:12mm}
.cover{padding:26mm 20mm}.cover .bar{position:absolute;top:0;left:0;right:0;height:9mm;background:#C6FF3D}
.cover .mark,.dark .mark{font-family:Unb;font-size:30pt;color:#fff}.mark b{color:#C6FF3D;font-weight:400}
.vol{margin-top:38mm;font-size:10pt;letter-spacing:.18em;text-transform:uppercase;color:#C6FF3D}
.dark .vol{margin-top:0}
.cover h1{font-family:Unb;font-size:56pt;line-height:1.02;color:#fff;margin:6mm 0 8mm;letter-spacing:-.03em}
.cover .sub,.dark .sub{font-size:14pt;color:#BDBDBD;max-width:150mm;line-height:1.45}
.cover .foot{position:absolute;bottom:20mm;left:20mm;font-size:10pt;color:#8A8A8A}
.big{font-family:Unb;font-size:34pt;line-height:1.05;color:#fff;margin:5mm 0 6mm;letter-spacing:-.02em}
.cta{margin-top:8mm;font-size:12pt;color:#fff;background:#141414;border:1px solid #C6FF3D;border-radius:3mm;padding:5mm;text-align:center}
.links{display:grid;grid-template-columns:1fr 1fr 1fr;gap:3mm;margin:8mm 0}.links div{background:#141414;border-radius:3mm;padding:4mm}
.links span{display:block;font-size:8.5pt;color:#8A8A8A}.links b{font-size:10pt}
.legal{position:absolute;bottom:18mm;left:18mm;right:18mm;font-size:7.8pt;color:#7A7A7A;line-height:1.45}
"""

def main():
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, 'site', 'guide', 'forex-foundations.pdf')
    work = tempfile.mkdtemp(prefix='wfx-ebook-')
    subprocess.run([sys.executable, os.path.join(HERE, 'charts.py'), work], check=True, capture_output=True)
    body = open(os.path.join(HERE, 'content.html'), encoding='utf-8').read()
    html = '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Forex Foundations · Wendling FX</title><style>' + (CSS % {'f': FONTS}) + '</style></head><body>' + body + '</body></html>'
    src = os.path.join(work, 'book.html'); open(src, 'w', encoding='utf-8').write(html)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    chrome = shutil.which('google-chrome') or shutil.which('chromium')
    subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer', '--allow-file-access-from-files',
                    '--virtual-time-budget=8000', f'--print-to-pdf={out}', 'file://' + src], check=True, capture_output=True)
    print(json.dumps({'file': out}))

if __name__ == '__main__':
    main()
