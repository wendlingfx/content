#!/usr/bin/env python3
"""Wendling FX: move the site to a new trading account in one step.

Usage: python3 tools/switch_account.py --login 9xxxxxx --strategy 12xxxx --myfxbook-url https://www.myfxbook.com/members/WendlingFX/<slug>/<id>/<key> [--start 2026-11-23T13:00Z]
- server/account.json: ctrader_login, myfxbook_id (taken from the URL) and start (fresh start; default: now, rounded down to the minute, UTC)
- every Myfxbook link and every cTrader Copy strategy link in site/, site-full/ and tools/make_start.py
Prints what changed. Does not touch keys or tokens, and does not turn the content pause off.
"""
import json, os, re, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def arg(name, default=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a else default

def main():
    login, strategy, mfx = arg('--login'), arg('--strategy'), arg('--myfxbook-url')
    if not (login and login.isdigit() and strategy and strategy.isdigit() and mfx):
        raise SystemExit(__doc__)
    m = re.match(r'https://www\.myfxbook\.com/members/WendlingFX/[^/]+/(\d+)/[A-Za-z0-9]+/?$', mfx)
    if not m: raise SystemExit('myfxbook url not recognised: ' + mfx)
    start = arg('--start') or dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    p = os.path.join(ROOT, 'server', 'account.json')
    acc = json.load(open(p))
    old = dict(acc)
    acc.update({'ctrader_login': login, 'myfxbook_id': int(m.group(1)), 'start': start})
    json.dump(acc, open(p, 'w'), indent=2, ensure_ascii=False); open(p, 'a').write('\n')
    print(json.dumps({'account.json': {k: [old.get(k), acc[k]] for k in ('ctrader_login', 'myfxbook_id', 'start')}}))
    files = [os.path.join(ROOT, 'tools', 'make_start.py')]
    for top in ('site', 'site-full'):
        for d, _, fs in os.walk(os.path.join(ROOT, top)):
            files += [os.path.join(d, f) for f in fs if f.endswith('.html')]
    for f in files:
        s = open(f, encoding='utf-8').read()
        n = re.sub(r'https://www\.myfxbook\.com/members/WendlingFX/[^/"\s]+/\d+/[A-Za-z0-9]+', mfx.rstrip('/'), s)
        n = re.sub(r'(fusionmarkets\.com/copy/strategy/)\d+', r'\g<1>' + strategy, n)
        if n != s:
            open(f, 'w', encoding='utf-8').write(n)
            print(json.dumps({'updated': os.path.relpath(f, ROOT)}))

if __name__ == '__main__':
    main()
