#!/usr/bin/env python3
"""Wendling FX: Monday MARKET / LEVELS. Run from the repo root on Monday morning (Sao Paulo).
Charts for XAUUSD, EURUSD and USDCAD (tools/make_levels.py) into media/levels/; Telegram gets the 3 images, TikTok gets one
12 s video with the 3 charts and music. Both at 11:00 UTC. Then commit media, telegram.json and queue.json."""
import datetime as dt, json, os, random, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def jl(p):
    try: return json.load(open(p))
    except Exception: return []
def main():
    d = dt.datetime.now(dt.timezone.utc).date().isoformat(); outd = os.path.join(ROOT, 'media', 'levels')
    res = [json.loads(x) for x in subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'make_levels.py'), outd], capture_output=True, text=True, check=True).stdout.splitlines()]
    res = [r for r in res if 'file' in r]
    if not res: print(json.dumps({'skipped': 'no charts'})); return
    tgp, qp = os.path.join(ROOT, 'telegram.json'), os.path.join(ROOT, 'queue.json'); tg, q = jl(tgp), jl(qp)
    for i, r in enumerate(res):
        cid = f"levels-{r['sym'].lower()}-{d}"
        if cid not in {x.get('id') for x in tg}:
            tg.append({'id': cid, 'due': f'{d}T11:0{i}:00Z', 'type': 'photo', 'file': 'media/levels/' + r['file'], 'caption': r['caption'] + '\n\nLevels on the chart, not trade signals.'})
    music = os.path.join(ROOT, 'tools', 'music', random.Random(d).choice(sorted(f for f in os.listdir(os.path.join(ROOT, 'tools', 'music')) if f.endswith('.m4a'))))
    vid = f'wendlingfx-{d}-levels.mp4'; out = os.path.join(ROOT, 'media', vid); args = ['ffmpeg', '-y', '-loglevel', 'error']
    for r in res: args += ['-loop', '1', '-framerate', '30', '-t', '4', '-i', os.path.join(outd, r['file'])]
    args += ['-i', music]
    zp = "scale=2160:3840,zoompan=z='1+0.0003*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=120:s=1080x1920:fps=30,format=yuv420p"
    fc = ''.join(f'[{i}:v]{zp}[v{i}];' for i in range(len(res))) + ''.join(f'[v{i}]' for i in range(len(res))) + f'concat=n={len(res)}:v=1:a=0[v]'
    total = 4 * len(res)
    args += ['-filter_complex', fc, '-map', '[v]', '-map', f'{len(res)}:a', '-t', str(total), '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
             '-af', f'afade=t=out:st={total - 1.7}:d=1.7', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out + '.tmp.mp4']
    subprocess.run(args, check=True); os.replace(out + '.tmp.mp4', out)
    vidid = f'levels-{d}'
    if vidid not in {x.get('id') for x in q}:
        q.append({'id': vidid, 'file': vid, 'noTelegram': True, 'due': f'{d}T11:00:00Z',
                  'text': 'Levels on the chart this week: ' + ', '.join(r['sym'] for r in res) + '. Last week high and low, yesterday high and low, week open. #forex #gold #eurusd #trading'})
    json.dump(tg, open(tgp, 'w'), indent=2, ensure_ascii=False); json.dump(q, open(qp, 'w'), indent=2, ensure_ascii=False)
    print(json.dumps({'charts': [r['file'] for r in res], 'video': vid}))
if __name__ == '__main__':
    main()
