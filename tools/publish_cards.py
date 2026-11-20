#!/usr/bin/env python3
"""Wendling FX: makes today's result cards and queues them for Telegram (telegram.json) and TikTok (queue.json).
Run from the repo root at about 00:30 UTC: python3 tools/publish_cards.py [--dry]
Then commit media/ (cards and card videos), telegram.json and queue.json and push to main. Prints what it queued.
"""
import json, os, random, subprocess, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = os.path.join(ROOT, 'media', 'cards')
MUSIC = os.path.join(ROOT, 'tools', 'music')

def card_video(png, mp4, seed):
    """TikTok gets the card as an 8 s video with a slow push-in and music (photo posts via Buffer go out silent).
    Frame 0 is the card itself, so the cover is the card."""
    tracks = sorted(f for f in os.listdir(MUSIC) if f.endswith('.m4a'))
    music = os.path.join(MUSIC, random.Random(seed).choice(tracks)); tmp = mp4 + '.tmp.mp4'
    vf = ("scale=2160:3840,zoompan=z='1+0.0002*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=240:s=1080x1920:fps=30,format=yuv420p")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-framerate', '30', '-i', png, '-i', music, '-filter_complex', f'[0:v]{vf}[v]',
                    '-map', '[v]', '-map', '1:a', '-t', '8', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p',
                    '-af', 'afade=t=out:st=6.3:d=1.7', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', tmp], check=True)
    os.replace(tmp, mp4)

TAGS = {'mindset': '#tradingmindset #forex #discipline', 'day': '#forex #trading #dailyclose', 'week': '#forex #trading #copytrading', 'month': '#forex #trading #copytrading'}

def jload(p):
    try: return json.load(open(p))
    except Exception: return []

def main():
    dry = '--dry' in sys.argv
    os.makedirs(CARDS, exist_ok=True)
    out = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_card.py'), 'auto', CARDS] + (['--dry'] if dry else []), capture_output=True, text=True, check=True).stdout
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
            vid = r['file'].replace('.png', '.mp4')
            if not dry: card_video(os.path.join(CARDS, r['file']), os.path.join(ROOT, 'media', vid), r['period'])
            first = r['caption'].split('\n')[0]
            text = (first + ' No trades today. ' if r['kind'] == 'mindset' else first + ' Verified on Myfxbook. ') + TAGS[r['kind']]
            q.append({'id': cid, 'file': vid, 'noTelegram': True, 'due': tt_due, 'text': text})
        done.append({'queued': cid, 'telegram': tg_due, 'tiktok': tt_due})
    if not dry:
        json.dump(tg, open(tgp, 'w'), indent=2, ensure_ascii=False)
        json.dump(q, open(qp, 'w'), indent=2, ensure_ascii=False)
    for d in done: print(json.dumps(d))

if __name__ == '__main__':
    main()
