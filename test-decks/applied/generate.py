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
px = lambda n: float(tok[n][:-2])
M, G, N = px('grid-margin'), px('grid-gutter'), int(tok['grid-columns'])
COL = (1920 - 2 * M - (N - 1) * G) / N                     # columns fill the inner width; margin, gutter, count are the system's
cx = lambda i: M + i * (COL + G)
span = lambda n: n * COL + (n - 1) * G
pin = lambda x, y, w=None, extra='': 'position:absolute;left:%.1fpx;top:%dpx;%s%s' % (x, y, 'width:%.1fpx;' % w if w else '', extra)

slides, order = {}, []
def section(name, cls, body, note):
    order.append(name)
    slides[name] = '<section id="%s" class="%s">\n%s\n<aside>%s</aside>\n</section>' % (name, cls, '\n'.join(body), note)

def foot(n, cls=''):
    return '<p class="cap %s" style="%s">Fictional example · %02d</p>' % (cls, pin(M, 984), n)

# 1 title: accent field, big name, three satellite blocks
section('title', 'field', [
    '<p class="micro" style="%s">NEW FEATURE · FICTIONAL EXAMPLE</p>' % pin(M, 96),
    '<h1 class="display-xl title" style="%s">Trend Pulse</h1>' % pin(M, 300, span(4)),
    '<p class="h2 lead" style="%s">A weekly read on what people are searching for, in plain language.</p>' % pin(M, 520, span(3)),
    '<div class="blk b1" style="%s"></div>' % pin(cx(4) + 40, 96, span(2) - 40, 'height:420px'),
    '<div class="blk b2" style="%s"></div>' % pin(cx(4) + 40, 540, span(1) - 20, 'height:340px'),
    '<div class="blk b3" style="%s"></div>' % pin(cx(5) + 20, 540, span(1) - 20, 'height:340px'),
    foot(1, 'on')], 'Title. Accent-1 field, text in its on- colour.')

# 2 three cards: the Card recipe (surface, radius, shadow) on the 6-column grid
cards = [('1', 'See the shift', 'Searches that jumped this week, grouped by topic.', 'accent-1'),
         ('2', 'Know the why', 'A short note on what is behind each rise.', 'accent-2'),
         ('3', 'Plan around it', 'Export a one-page summary for your next meeting.', 'accent-3')]
body = ['<p class="micro mute" style="%s">WHAT IT DOES</p>' % pin(M, 96),
        '<h1 class="display h1x" style="%s">One page. Three jobs.</h1>' % pin(M, 140, span(5))]
for i, (n, t, d, a) in enumerate(cards):
    body.append('<div class="card" style="%s"><p class="num" style="background:var(--%s);color:var(--on-%s)">%s</p><h3 class="h2">%s</h3><p class="h3 mute">%s</p></div>' % (pin(cx(i * 2), 380, span(2), 'height:520px'), a, a, n, t, d))
body.append(foot(2, 'mute'))
section('cards', 'plain', body, 'Three Card-shaped blocks, two columns each.')

# 3 how it works + call to action
steps = [('Monday', 'Pulse reads the week’s search data.'), ('Tuesday', 'You get the top five movers and why.'), ('Any day', 'Share the page with your team.')]
body = ['<p class="micro mute" style="%s">HOW IT WORKS</p>' % pin(M, 96),
        '<h1 class="display h1x" style="%s">Start with one email a week.</h1>' % pin(M, 140, span(4))]
for i, (d, t) in enumerate(steps):
    y = 440 + i * 150
    body.append('<div class="row" style="%s"><span class="dot" style="background:var(--accent-%d)"></span><p class="h2 day">%s</p><p class="h3 mute">%s</p></div>' % (pin(M, y, span(4)), [1, 2, 3][i], d, t))
body.append('<div class="field panel" style="%s"><p class="h2">Try it free for four weeks.</p><p class="cta">Join the waitlist</p></div>' % pin(cx(4), 440, span(2), 'height:400px'))
body.append(foot(3, 'mute'))
section('how', 'plain', body, 'Steps on the left, call to action on a second accent field.')

os.makedirs(OUT + '/slides', exist_ok=True)
for k, v in slides.items(): open('%s/slides/%s.html' % (OUT, k), 'w').write(v)
fams = tk['type']['families']
faces = {}
for f in tk['type']['fonts']:
    faces[f['family'].lower().replace(' ', '-')] = {'family': f['family'], 'href': 'https://fonts.googleapis.com/css2?family=%s:wght@400;500;700&display=swap' % f['family'].replace(' ', '+')}
json.dump({'v': 5, 'createdOnFiles': {'v': 1, 'at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, 'lists': 'css',
           'format': {'v': 1, 'shared': ['project/deck.css']}, 'title': 'Trend Pulse (applied design system)', 'order': order,
           'sections': {'s1': {'description': 'Intro', 'start': 'title'}}, 'faces': faces, 'designSystems': []}, open(OUT + '/deck.json', 'w'), indent=1)
root = [l for l in dsbuild.compile_css(tk).split('\n') if not l.startswith('@font-face')]
css = '\n'.join(root) + """
body{font-family:var(--font-body);color:var(--ink)}
section{background:var(--paper);color:var(--ink);font-family:var(--font-body)}
section.field{background:var(--accent-1);color:var(--on-accent-1)}
.micro{font-size:var(--micro,24px);font-weight:700;letter-spacing:3px;font-size:24px;line-height:32px}
.mute{color:var(--mute,var(--ink))}
.display-xl.title{font-family:var(--font-display);font-size:176px;line-height:176px;font-weight:700;letter-spacing:-4px}
.display.h1x{font-family:var(--font-display);font-size:72px;line-height:80px;font-weight:700}
.h2{font-weight:700}.h3{font-weight:400}.lead{font-weight:400;line-height:48px}
.cap{font-size:24px;line-height:24px;font-weight:500}.cap.on{color:var(--on-accent-1)}
.blk{border-radius:var(--radius-1)}
.b1{background:var(--accent-6)}.b2{background:var(--accent-3)}.b3{background:var(--accent-7)}
.card{box-sizing:border-box;background:var(--surface);border-radius:var(--radius-1);box-shadow:var(--shadow-4);padding:48px;display:flex;flex-direction:column;gap:24px}
.num{width:72px;height:72px;border-radius:36px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:40px;line-height:72px;text-align:center;margin:0 0 24px}
.row{display:flex;gap:32px;align-items:center}
.dot{width:24px;height:24px;border-radius:12px;flex:none}
.day{width:240px}
.panel{box-sizing:border-box;border-radius:var(--radius-1);padding:64px;background:var(--accent-2);color:var(--on-accent-2);display:flex;flex-direction:column;justify-content:space-between}
.cta{font-size:32px;line-height:32px;font-weight:700}
"""
open(OUT + '/deck.css', 'w').write(css)
print(len(slides), 'slides, margin %g gutter %g columns %d -> column %.1f px' % (M, G, N, COL))
