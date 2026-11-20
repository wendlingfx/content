#!/usr/bin/env python3
"""Wendling FX: Sunday posts. Run from the repo root on Sunday morning (Sao Paulo).
1. Meme of the week: the next approved meme in tools/memes.json not used yet ("approved": true, "used": date).
   Telegram gets the image (telegram.json), TikTok gets an 8 s video with music (queue.json), both at 13:00 UTC.
2. Cross promotion: Telegram text pointing to the TikTok profile at 21:00 UTC; on even ISO weeks, the TikTok
   promo video for the Telegram channel at 21:00 UTC.
Then commit media, tools/memes.json, telegram.json and queue.json. Prints what it queued."""
import datetime as dt, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from publish_cards import card_video

def jl(p):
    try: return json.load(open(p))
    except Exception: return []

def main():
    today = dt.datetime.now(dt.timezone.utc).date(); d = today.isoformat()
    tgp, qp, mp = os.path.join(ROOT, 'telegram.json'), os.path.join(ROOT, 'queue.json'), os.path.join(ROOT, 'tools', 'memes.json')
    tg, q, memes = jl(tgp), jl(qp), jl(mp)
    ids_tg, ids_q = {x.get('id') for x in tg}, {x.get('id') for x in q}; done = []
    m = next((x for x in memes if x.get('approved') and not x.get('used')), None)
    if m:
        out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_meme.py'), os.path.join(ROOT, 'media', 'memes'), m['id']], capture_output=True, text=True, check=True).stdout
        r = json.loads(out.strip().splitlines()[-1])
        png = os.path.join(ROOT, 'media', 'memes', r['file']); vid = r['file'].replace('.png', '.mp4')
        card_video(png, os.path.join(ROOT, 'media', vid), m['id'] + d)
        cid = f"meme-{m['id']}"
        if cid not in ids_tg: tg.append({'id': cid, 'due': f'{d}T13:00:00Z', 'type': 'photo', 'file': 'media/memes/' + r['file'], 'caption': 'Sunday mood. Have a good one.'})
        if cid not in ids_q: q.append({'id': cid, 'file': vid, 'noTelegram': True, 'due': f'{d}T13:00:00Z', 'text': 'Sunday mood. ' + r['caption'] + ' #tradinghumor #forex #trading'})
        m['used'] = d; done.append(cid)
    pid = f'promo-tg-{d}'
    if pid not in ids_tg:
        tg.append({'id': pid, 'due': f'{d}T21:00:00Z', 'type': 'text', 'caption': 'Short videos of the account every week on TikTok: https://www.tiktok.com/@wendling.fx'}); done.append(pid)
    if today.isocalendar()[1] % 2 == 0:
        vid_id = f'promo-tt-{d}'
        if vid_id not in ids_q:
            out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_video.py'), 'promo', os.path.join(ROOT, 'media'), '--date', d], capture_output=True, text=True, check=True).stdout
            r = json.loads(out.strip().splitlines()[-1])
            q.append({'id': vid_id, 'file': r['file'], 'noTelegram': True, 'due': f'{d}T21:00:00Z', 'text': r['text']}); done.append(vid_id)
    json.dump(tg, open(tgp, 'w'), indent=2, ensure_ascii=False); json.dump(q, open(qp, 'w'), indent=2, ensure_ascii=False)
    json.dump(memes, open(mp, 'w'), indent=1, ensure_ascii=False)
    print(json.dumps({'queued': done, 'memeLeft': sum(1 for x in memes if x.get('approved') and not x.get('used'))}))

if __name__ == '__main__':
    main()
