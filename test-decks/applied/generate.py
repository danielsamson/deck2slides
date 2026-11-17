#!/usr/bin/env python3
"""Apply a derived design system to a fictional three-slide deck in the Claude Slides format.
Every colour, size, radius, shadow, margin and gutter comes from the system's tokens.json (via CSS variables); the script
only decides layout. Usage: python3 generate.py [path/to/project/tokens.json] [out-dir]"""
import json, os, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from d2s import dsbuild
H = os.path.dirname(os.path.abspath(__file__))
TK = sys.argv[1] if len(sys.argv) > 1 else H + '/../../examples/tokens/decka/system/project/tokens.json'
OUT = sys.argv[2] if len(sys.argv) > 2 else H
tk = json.load(open(TK))
tok = {t['name']: t['value'] for fam in ('spacing', 'radius', 'grid') for t in tk.get(fam, {}).get('tokens', [])}
cname = {t['name']: t for t in tk['color']['tokens']}
acc = [n for n in cname if n.startswith('accent-')] or ['ink']
A = lambda i: acc[i % len(acc)]
ON = lambda n: 'on-' + n if 'on-' + n in cname else 'ink'
RAD = sorted([n for n in tok if n.startswith('radius-') and tok[n].endswith('px') and float(tok[n][:-2]) < 999], key=lambda k: float(tok[k][:-2]))
R = 'var(--%s)' % RAD[0] if RAD else '0'
SH = ('var(--%s)' % tk['shadow']['tokens'][-1]['name']) if tk.get('shadow') else 'none'
themes = [t['id'] for t in tk['color']['themes']]
DARK = 'dark' if 'dark' in themes else None
MUTE = 'mute' if 'mute' in cname else 'ink'
sz = {st['name']: float(st['fontSize'][:-2]) for g in tk['type']['groups'] for st in g['styles']}
px = lambda n: float(tok[n][:-2])
M, G, N = px('grid-margin'), px('grid-gutter'), int(tok['grid-columns'])
if 'space-8' in tok and G < 0.5 * px('space-8'):
    G = px('space-8')   # a measured gutter of ~0 (low-confidence grid) would butt cards together; fall back to the spacing scale
COL = (1920 - 2 * M - 5 * G) / 6                           # six blocks across the inner width, separated by the system's gutter (aligns with any column count divisible by 6)
cx = lambda i: M + i * (COL + G)
span = lambda n: n * COL + (n - 1) * G
pin = lambda x, y, w=None, extra='': 'position:absolute;left:%.1fpx;top:%dpx;%s%s' % (x, y, 'width:%.1fpx;' % w if w else '', extra)

slides, order = {}, []
def section(name, cls, body, note):
    order.append(name)
    slides[name] = '<section id="%s" class="%s">\n%s\n<aside>%s</aside>\n</section>' % (name, cls, '\n'.join(body), note)

def foot(n, cls=''):
    return '<p class="cap %s" style="%s">Fictional example · %02d</p>' % (cls, pin(M, 984), n)

TITLE_CLS = 'th-dark' if DARK else 'field'
PLAIN = 'th-light' if 'light' in themes and len(themes) > 1 else 'plain'
title_px = 176 if sz.get('display-xl', 0) < 120 else min(sz['display-xl'], 176)   # the title may exceed the system's largest style when that is small (a choice, not a measurement)
PAL = acc[1:] if (TITLE_CLS == 'field' and len(acc) > 1) else acc   # blocks must differ from the field they sit on
PB = lambda i: PAL[i % len(PAL)]
# 1 title: dark theme (or accent field), big name, three satellite blocks
section('title', TITLE_CLS, [
    '<p class="micro" style="%s">NEW FEATURE · FICTIONAL EXAMPLE</p>' % pin(M, 96),
    '<h1 class="display-xl title" style="%s">Trend Pulse</h1>' % pin(M, 300, span(5)),
    '<p class="h2 lead" style="%s">A weekly read on what people are searching for, in plain language.</p>' % pin(M, 520, span(3)),
    '<div class="blk" style="%s;background:var(--%s)"></div>' % (pin(cx(4) + 40, 96, span(2) - 40, 'height:420px'), PB(0)),
    '<div class="blk" style="%s;background:var(--%s)"></div>' % (pin(cx(4) + 40, 540, span(1) - 20, 'height:340px'), PB(1) if len(PAL) > 1 else 'mute'),
    '<div class="blk" style="%s;background:var(--%s)"></div>' % (pin(cx(5) + 20, 540, span(1) - 20, 'height:340px'), PB(2) if len(PAL) > 2 else 'ink'),
    foot(1, 'on')], 'Title. ' + ('Dark theme.' if DARK else 'Accent-1 field, text in its on- colour.'))

# 2 three cards on the grid
cards = [('1', 'See the shift', 'Searches that jumped this week, grouped by topic.'),
         ('2', 'Know the why', 'A short note on what is behind each rise.'),
         ('3', 'Plan around it', 'Export a one-page summary for your next meeting.')]
body = ['<p class="micro mute" style="%s">WHAT IT DOES</p>' % pin(M, 96),
        '<h1 class="display h1x" style="%s">One page. Three jobs.</h1>' % pin(M, 140, span(5))]
for i, (n, t, d) in enumerate(cards):
    a = A(i)
    body.append('<div class="card" style="%s"><p class="num" style="background:var(--%s);color:var(--%s)">%s</p><h3 class="h2">%s</h3><p class="h3 mute">%s</p></div>' % (pin(cx(i * 2), 380, span(2), 'height:520px'), a, ON(a), n, t, d))
body.append(foot(2, 'mute'))
section('cards', PLAIN, body, 'Three cards, two columns each.')

# 3 steps + call to action
steps = [('Monday', 'Pulse reads the week\u2019s search data.'), ('Tuesday', 'You get the top five movers and why.'), ('Any day', 'Share the page with your team.')]
body = ['<p class="micro mute" style="%s">HOW IT WORKS</p>' % pin(M, 96),
        '<h1 class="display h1x" style="%s">Start with one email a week.</h1>' % pin(M, 140, span(4))]
for i, (d, t) in enumerate(steps):
    body.append('<div class="row" style="%s"><span class="dot" style="background:var(--%s)"></span><p class="h2 day">%s</p><p class="h3 mute">%s</p></div>' % (pin(M, 440 + i * 150, span(4)), A(i), d, t))
ca = A(0)
body.append('<div class="panel" style="%s;background:var(--%s);color:var(--%s)"><p class="h2">Try it free for four weeks.</p><p class="cta">Join the waitlist</p></div>' % (pin(cx(4), 440, span(2), 'height:400px'), ca, ON(ca)))
body.append(foot(3, 'mute'))
section('how', PLAIN, body, 'Steps on the left, call to action in the first accent.')

os.makedirs(OUT + '/slides', exist_ok=True)
for k, v in slides.items(): open('%s/slides/%s.html' % (OUT, k), 'w').write(v)
fams = tk['type']['families']
faces = {}
for f in tk['type']['fonts']:
    faces[f['family'].lower().replace(' ', '-')] = {'family': f['family'], 'href': 'https://fonts.googleapis.com/css2?family=%s:wght@400;500;700&display=swap' % f['family'].replace(' ', '+')}
faces = dict(list(faces.items())[:4])
json.dump({'v': 5, 'createdOnFiles': {'v': 1, 'at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, 'lists': 'css',
           'format': {'v': 1, 'shared': ['project/deck.css']}, 'title': 'Trend Pulse (applied design system)', 'order': order,
           'sections': {'s1': {'description': 'A fictional feature, three slides', 'start': 'title'}}, 'faces': faces, 'designSystems': []}, open(OUT + '/deck.json', 'w'), indent=1)
root = [l for l in dsbuild.compile_css(tk).split('\n') if not l.startswith('@font-face')]
# a dark theme becomes a class that re-declares the colour variables it changes
dk = ''
for th in themes:
    if len(themes) > 1:
        dk += 'section.th-%s{' % th + ''.join('--%s:%s;' % (t['name'], t['value'][th]) for t in tk['color']['tokens'] if isinstance(t['value'], dict)) + 'background:var(--paper);color:var(--ink)}\n'
css = '\n'.join(root) + """
body{font-family:var(--font-body);color:var(--ink)}
section{background:var(--paper);color:var(--ink);font-family:var(--font-body)}
section.field{background:var(--accent-1);color:var(--on-accent-1)}
""" + dk + """.micro{font-weight:700;letter-spacing:3px;font-size:24px;line-height:32px}
.mute{color:var(--%s)}
.display-xl.title{font-family:var(--font-display);font-size:%dpx;line-height:%dpx;font-weight:700;letter-spacing:-4px}
.display.h1x{font-family:var(--font-display);font-size:72px;line-height:80px;font-weight:700}
.h2{font-weight:700}.h3{font-weight:400}.lead{font-weight:400;line-height:1.25}
.cap{font-size:24px;line-height:24px;font-weight:500}
.blk{border-radius:%s}
.card{box-sizing:border-box;background:var(--%s);border-radius:%s;box-shadow:%s;padding:48px;display:flex;flex-direction:column;gap:24px;border:2px solid var(--%s)}
.num{width:72px;height:72px;border-radius:36px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:40px;line-height:72px;text-align:center;margin:0 0 24px}
.row{display:flex;gap:32px;align-items:center}
.dot{width:24px;height:24px;border-radius:12px;flex:none}
.day{width:240px}
.panel{box-sizing:border-box;border-radius:%s;padding:64px;display:flex;flex-direction:column;justify-content:space-between}
.cta{font-size:32px;line-height:32px;font-weight:700}
""" % (MUTE, title_px, title_px, R, 'surface' if 'surface' in cname else 'paper', R, SH, MUTE if SH == 'none' else 'paper', R)
open(OUT + '/deck.css', 'w').write(css)
print(len(slides), 'slides, margin %g gutter %g columns %d -> block %.1f px; accents %s; radius %s; shadow %s; dark theme %s' % (M, G, N, COL, acc[:3], R, SH, bool(DARK)))
