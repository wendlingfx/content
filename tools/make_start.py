#!/usr/bin/env python3
"""Wendling FX: builds the /start/ guide pages (chooser + one complete page per situation). Run from the repo root."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import make_post as mp
REF = 'https://hub.fusionmarkets.com/en/auth/sign-up?refcode=113969'
STRAT = 'https://app.fusionmarkets.com/copy/strategy/124939?u=LucasWend'
CSS = '''<style>
.paths{display:grid;gap:14px;margin:28px 0}
.paths a{display:flex;gap:18px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:22px;color:var(--text)}
.paths a:hover{text-decoration:none;border-color:#C6FF3D}.paths .n{flex:none;width:52px;height:52px;border-radius:50%;background:#C6FF3D;color:#0A0A0A;font-family:Unbounded,sans-serif;font-weight:700;display:grid;place-items:center;font-size:22px}
.paths b{display:block;font-family:Unbounded,sans-serif;font-size:19px;margin-bottom:4px}.paths span{color:var(--muted);font-size:16px}
.step{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:22px;margin:22px 0}
.step .h{display:flex;gap:14px;align-items:center}.step .k{flex:none;width:40px;height:40px;border-radius:50%;background:#C6FF3D;color:#0A0A0A;font-weight:700;display:grid;place-items:center;font-size:18px}
.step h2{margin:0;font-size:20px}.step p{margin:12px 0 0;color:#ddd}.step img{display:block;width:100%;height:auto;border-radius:12px;border:1px solid var(--line);margin-top:16px}
.cta{display:inline-block;background:#C6FF3D;color:#0A0A0A;border-radius:999px;padding:12px 22px;font-weight:600;margin-top:16px}.cta:hover{text-decoration:none}
.note{border-left:3px solid #C6FF3D;padding:4px 0 4px 16px;margin:24px 0;color:#ccc;font-size:16px}
.back{display:inline-block;margin-top:28px;font-size:15px}
.prog{color:var(--muted);font-size:15px;margin-top:-6px}
</style>'''
def page(path, title, desc, body):
    head = mp.HEAD.format(title=title, desc=desc, canon=f'https://wendlingfx.com/{path}', ogimg='').replace('</head>', CSS + '</head>')
    html = head + body + mp.TG + mp.FOOT
    assert '—' not in html and '–' not in html, path
    os.makedirs(os.path.join('site', path), exist_ok=True)
    open(os.path.join('site', path, 'index.html'), 'w').write(html)
def steps(items):
    out = []
    for i, (t, p, img, btn) in enumerate(items, 1):
        s = f'<div class="step"><div class="h"><div class="k">{i}</div><h2>{t}</h2></div><p>{p}</p>'
        if img: s += f'<img src="/start/img/{img}" alt="{t}" loading="lazy">'
        if btn: s += f'<a class="cta" href="{btn[1]}">{btn[0]}</a>'
        out.append(s + '</div>')
    return '\n'.join(out)
COUNTRY = '<p class="note">Fusion Markets does not accept clients from a few countries, including the United States, Japan, Spain and New Zealand. If that is your case, open a cTrader account with another broker that offers cTrader Copy (for example IC Markets or Pepperstone) and follow the same steps.</p>'
COMMON_END = [
    ('Open the strategy and press Start copying', 'Log in to cTrader, open the WFX strategy and press the green Start copying button.', 'strategy.png', ('Open the WFX strategy', STRAT)),
    ('Choose the amount and confirm', 'Pick your live account, type the amount to allocate (minimum US$500), check the fee (30% of new profit only) and confirm.', 'copyform.png', None),
    ('Set your loss limit', 'In the strategy menu choose Set equity stop loss and type the lowest amount you accept. If your copy account reaches it, copying stops.', 'stoploss.png', None),
]
DONE = '<p class="note">Done. Trades are now copied automatically, sized to your account. You can add or remove funds, change the loss limit or stop copying at any time.</p><p><a class="cta" href="https://t.me/wendlingfx">Questions? Ask on Telegram</a></p><a class="back" href="/start/">Back to the start</a>'
NEW = [
    ('Create your Fusion Markets login', 'Sign up with your email and a password. Fusion Markets is the broker we trade with and it offers cTrader Copy.', 'signup.png', ('Sign up at Fusion Markets', REF)),
    ('Open a live account', 'In the Client Hub choose account type Zero, platform cTrader and currency USD.', 'account.png', None),
    ('Verify your identity', 'Upload a photo ID and a proof of address. Fusion says most accounts are approved within an hour.', 'verify.png', None),
    ('Fund the account', 'Deposit at least US$500. Fusion charges no deposit fee on cards, PayPal, Skrill and Neteller.', 'fund.png', None),
] + COMMON_END
HAVE = [
    ('Check your account type', 'cTrader Copy works with hedging accounts. If yours is netting, open a new hedging account with your broker under the same cTrader login.', 'hedging.png', None),
    ('Find WFX', 'In cTrader, open Copy in the left menu and search for WFX (provider LucasWend). Or use the button while logged in.', 'search.png', ('Open the WFX strategy', STRAT)),
    ('Press Start copying', 'If the strategy shows up, press Start copying. If it does not, your broker does not list it: go to "My broker has cTrader, no Copy".', 'strategy.png', None),
    ('Choose the amount and confirm', 'Pick your live hedging account, type the amount to allocate (minimum US$500), check the fee (30% of new profit only) and confirm.', 'copyform.png', None),
    ('Set your loss limit', 'In the strategy menu choose Set equity stop loss and type the lowest amount you accept. If your copy account reaches it, copying stops.', 'stoploss.png', None),
]
NOCOPY = [
    ('Add a Fusion Markets account', 'You can keep your current broker. Sign up at Fusion with the same email you use for cTrader, so the new account is linked to the same login.', 'signup.png', ('Sign up at Fusion Markets', REF)),
    ('Open a live account', 'In the Client Hub choose account type Zero, platform cTrader and currency USD.', 'account.png', None),
    ('Verify your identity', 'Upload a photo ID and a proof of address. Fusion says most accounts are approved within an hour.', 'verify.png', None),
    ('Fund the account', 'Deposit at least US$500. Fusion charges no deposit fee on cards, PayPal, Skrill and Neteller.', 'fund.png', None),
] + COMMON_END
def main():
    page('start', 'How to start copying', 'Copy the WFX strategy on cTrader Copy: pick your situation and follow the steps.', f'''
<h1>How to start copying</h1>
<p class="dek">Copying runs inside cTrader Copy. Your money stays in an account in your name at a regulated broker. Which one is you?</p>
<div class="paths">
<a href="/start/new/"><div class="n">1</div><div><b>I don't have cTrader</b><span>7 steps. Open an account, verify, fund and copy.</span></div></a>
<a href="/start/have-copy/"><div class="n">2</div><div><b>I have cTrader with Copy</b><span>5 steps. Your broker already offers cTrader Copy.</span></div></a>
<a href="/start/no-copy/"><div class="n">3</div><div><b>My broker has cTrader, no Copy</b><span>7 steps. Add a Fusion account to the same login.</span></div></a>
</div>
<p class="note">Not sure? If you have never opened cTrader, pick 1. If cTrader shows a Copy item in the left menu, pick 2. If it doesn't, pick 3.</p>
''')
    page('start/new', "Start copying: I don't have cTrader", 'Step by step, from opening a Fusion Markets account to copying the WFX strategy.',
         f'<h1>I don\'t have cTrader</h1><p class="prog">7 steps</p>' + steps(NEW) + COUNTRY + DONE)
    page('start/have-copy', 'Start copying: I have cTrader with Copy', 'Copy the WFX strategy from your existing cTrader account.',
         '<h1>I have cTrader with Copy</h1><p class="prog">5 steps</p>' + steps(HAVE) + DONE)
    page('start/no-copy', 'Start copying: my broker has cTrader but no Copy', 'Add a Fusion Markets account to your cTrader login and copy the WFX strategy.',
         '<h1>My broker has cTrader, no Copy</h1><p class="prog">7 steps. You keep your current broker.</p>' + steps(NOCOPY) + COUNTRY + DONE)
    man = json.load(open('server/manifest.json'))
    for pth in ['start', 'start/new', 'start/have-copy', 'start/no-copy']: man[f'site/{pth}/index.html'] = f'{pth}/index.html'
    for f in sorted(os.listdir('site/start/img')): man[f'site/start/img/{f}'] = f'start/img/{f}'
    json.dump(man, open('server/manifest.json', 'w'), indent=2)
if __name__ == '__main__':
    main()
