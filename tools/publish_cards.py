#!/usr/bin/env python3
"""Wendling FX: makes today's result cards and queues them for Telegram (telegram.json) and TikTok (queue.json).
Run from the repo root at about 00:30 UTC: python3 tools/publish_cards.py [--dry]
Then commit media/cards/, telegram.json and queue.json and push to main. Prints what it queued.
"""
import json, os, subprocess, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, 'media', 'cards')
TAGS = {'day': '#forex #trading #dailyclose', 'week': '#forex #trading #copytrading', 'month': '#forex #trading #copytrading'}

def jload(p):
    try: return json.load(open(p))
    except Exception: return []

def main():
    dry = '--dry' in sys.argv
    os.makedirs(CARDS, exist_ok=True)
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_card.py'), 'auto', CARDS], capture_output=True, text=True, check=True).stdout
    now = dt.datetime.now(dt.timezone.utc)
    tg_due = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    tt_due = (now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1, minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    tgp, qp = os.path.join(ROOT, 'telegram.json'), os.path.join(ROOT, 'queue.json')
    tg, q = jload(tgp), jload(qp)
    have_tg, have_q = {m.get('id') for m in tg}, {m.get('id') for m in q}
    done = []
    for line in out.splitlines():
        r = json.loads(line)
        if 'file' not in r: done.append(r); continue
        path = 'media/cards/' + r['file']; cid = f"card-{r['kind']}-{r['period']}"
        if cid not in have_tg:
            tg.append({'id': cid, 'due': tg_due, 'type': 'photo', 'file': path, 'caption': r['caption']})
        if cid not in have_q:
            q.append({'id': cid, 'images': [path], 'due': tt_due, 'text': r['caption'].split('\n')[0] + ' Verified on Myfxbook. ' + TAGS[r['kind']]})
        done.append({'queued': cid, 'telegram': tg_due, 'tiktok': tt_due})
    if not dry:
        json.dump(tg, open(tgp, 'w'), indent=2, ensure_ascii=False)
        json.dump(q, open(qp, 'w'), indent=2, ensure_ascii=False)
    for d in done: print(json.dumps(d))

if __name__ == '__main__':
    main()
