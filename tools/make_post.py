#!/usr/bin/env python3
"""Wendling FX: publishes a blog post on wendlingfx.com/blog/ from a JSON file.

Usage: python3 tools/make_post.py POST.json
POST.json: {"slug", "title", "date" (YYYY-MM-DD), "dek" (one-line summary), "sections": [{"h": "heading or empty", "p": ["paragraph", ...]}],
            "sources": [{"title", "url"}], "image": "optional repo path of a PNG shown under the title"}
Writes site/blog/<slug>/index.html, rebuilds site/blog/index.html from site/blog/posts.json and adds both to server/manifest.json
(the server pulls them within the hour). Prints {"url"}.
Rules: English, plain and factual, every number with its source, no price targets, no buy or sell calls, no em dashes.
"""
import html, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOG = os.path.join(ROOT, 'site', 'blog')
SITE = 'https://wendlingfx.com'
e = html.escape

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Wendling FX</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:type" content="article">{ogimg}
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Unbounded:wght@500;700;800&display=swap">
<style>
:root{{--bg:#0A0A0A;--panel:#141414;--line:#262626;--text:#fff;--muted:#A3A3A3;--lime:#C6FF3D;--tg:#2AABEE}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;font-size:18px;line-height:1.65;-webkit-font-smoothing:antialiased}}
a{{color:var(--lime);text-decoration:none}}a:hover{{text-decoration:underline}}
.wrap{{max-width:760px;margin:0 auto;padding:0 24px}}
header{{border-bottom:1px solid var(--line)}}.nav{{display:flex;align-items:center;justify-content:space-between;height:64px}}
.brand{{font-family:Unbounded,sans-serif;font-weight:700;font-size:20px;color:var(--text);letter-spacing:-.03em}}.brand b{{color:var(--lime);font-weight:700}}
.nav a.l{{color:var(--muted);font-size:15px}}
h1,h2{{font-family:Unbounded,sans-serif;letter-spacing:-.03em}}h1{{font-size:clamp(30px,5vw,46px);line-height:1.1;margin:48px 0 12px}}
h2{{font-size:22px;margin:36px 0 10px}}.meta{{color:var(--muted);font-size:15px;margin-bottom:28px}}.dek{{font-size:20px;color:#ddd}}
img.cover{{width:100%;height:auto;border-radius:14px;border:1px solid var(--line);margin:8px 0 12px}}
.src{{border-top:1px solid var(--line);margin-top:40px;padding-top:20px;font-size:15px;color:var(--muted)}}.src li{{margin:4px 0}}
.tg{{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:36px 0}}
.tg a.b{{background:var(--tg);color:#fff;border-radius:999px;padding:10px 18px;font-weight:600}}
.list a.post{{display:block;border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:14px 0;color:var(--text)}}.list a.post:hover{{text-decoration:none;border-color:#3a3a3a}}
.list .d{{color:var(--muted);font-size:14px}}.list h3{{font-family:Unbounded,sans-serif;font-size:19px;margin:6px 0}}
footer{{border-top:1px solid var(--line);margin-top:56px;padding:24px 0 40px;color:var(--muted);font-size:13px}}
</style>
</head>
<body>
<header><div class="wrap nav"><a class="brand" href="/">wendling<b>fx</b></a><a class="l" href="/blog/">Blog</a></div></header>
<main class="wrap">
'''
TG = '<div class="tg"><span>Follow the live account for free on Telegram.</span><a class="b" href="https://t.me/wendlingfx">Join on Telegram</a></div>'
FOOT = '''</main>
<footer><div class="wrap">Educational content, not financial advice. Trading on margin is high risk. <a href="/">wendlingfx.com</a></div></footer>
</body></html>
'''

def nice(d):
    import datetime as dt
    return dt.date.fromisoformat(d).strftime('%B %-d, %Y')

def post_page(p):
    canon = f"{SITE}/blog/{p['slug']}/"
    og = f'<meta property="og:image" content="{SITE}/{e(p["image_url"])}">' if p.get('image_url') else ''
    out = [HEAD.format(title=e(p['title']), desc=e(p['dek']), canon=canon, ogimg=og)]
    out.append(f"<article><h1>{e(p['title'])}</h1><div class=\"meta\">{nice(p['date'])} · Wendling FX</div><p class=\"dek\">{e(p['dek'])}</p>")
    if p.get('image_url'): out.append(f'<img class="cover" src="/{e(p["image_url"])}" alt="{e(p.get("image_alt", p["title"]))}">')
    for s in p['sections']:
        if s.get('h'): out.append(f"<h2>{e(s['h'])}</h2>")
        for para in s.get('p', []): out.append(f"<p>{e(para)}</p>")
    out.append(TG)
    if p.get('sources'):
        out.append('<div class="src"><b>Sources</b><ul>' + ''.join(f'<li><a href="{e(x["url"])}" rel="nofollow noopener">{e(x["title"])}</a></li>' for x in p['sources']) + '</ul></div>')
    out.append('</article>' + FOOT)
    return '\n'.join(out)

def index_page(posts):
    out = [HEAD.format(title='Blog', desc='Weekly market notes from the Wendling FX live account.', canon=f'{SITE}/blog/', ogimg='')]
    out.append('<h1>Market notes</h1><p class="dek">What moved the markets this week, from official sources, in plain English.</p><div class="list">')
    for p in sorted(posts, key=lambda x: x['date'], reverse=True):
        out.append(f'<a class="post" href="/blog/{e(p["slug"])}/"><div class="d">{nice(p["date"])}</div><h3>{e(p["title"])}</h3><div class="d">{e(p["dek"])}</div></a>')
    out.append('</div>' + TG + FOOT)
    return '\n'.join(out)

def main():
    p = json.load(open(sys.argv[1]))
    for k in ('slug', 'title', 'date', 'dek', 'sections'):
        if not p.get(k): raise SystemExit('missing ' + k)
    blob = json.dumps(p, ensure_ascii=False)
    if '—' in blob or '–' in blob: raise SystemExit('remove em/en dashes')
    os.makedirs(os.path.join(BLOG, p['slug']), exist_ok=True)
    man_p = os.path.join(ROOT, 'server', 'manifest.json'); man = json.load(open(man_p))
    if p.get('image'):
        name = os.path.basename(p['image']); p['image_url'] = f"blog/{p['slug']}/{name}"
        man[p['image']] = p['image_url']
    open(os.path.join(BLOG, p['slug'], 'index.html'), 'w').write(post_page(p))
    lp = os.path.join(BLOG, 'posts.json'); posts = json.load(open(lp)) if os.path.exists(lp) else []
    posts = [x for x in posts if x['slug'] != p['slug']] + [{'slug': p['slug'], 'title': p['title'], 'date': p['date'], 'dek': p['dek']}]
    json.dump(posts, open(lp, 'w'), indent=2, ensure_ascii=False)
    open(os.path.join(BLOG, 'index.html'), 'w').write(index_page(posts))
    man[f"site/blog/{p['slug']}/index.html"] = f"blog/{p['slug']}/index.html"
    man['site/blog/index.html'] = 'blog/index.html'
    json.dump(man, open(man_p, 'w'), indent=2)
    print(json.dumps({'url': f"{SITE}/blog/{p['slug']}/"}))

if __name__ == '__main__':
    main()
