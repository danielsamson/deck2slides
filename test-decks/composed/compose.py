#!/usr/bin/env python3
"""Design new pages FROM a design system, as a consumer would: read its tokens, take components and layouts from its previews,
fill their slots, place them. Nothing here is measured from the source deck; it only uses what the system published.
Usage: python3 compose.py <system/project dir> <out dir>"""
import json, os, re, sys, datetime
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from d2s import dsbuild
SYS = sys.argv[1] if len(sys.argv) > 1 else '../../examples/tokens/deckb/system/project'
OUT = sys.argv[2] if len(sys.argv) > 2 else '.'
tk = json.load(open(SYS + '/tokens.json'))

def preview(name):
    h = open('%s/components/%s/preview.html' % (SYS, name)).read()
    st = re.search(r'\.stage\{[^}]*width:([\d.]+)px;height:([\d.]+)px', h)
    inner = h.split('<div class="stage">', 1)[1].rsplit('</div>', 1)[0]
    return float(st.group(1)), float(st.group(2)), inner.strip()

def place(name, x, y, **text):
    """A component from the system at x, y, with its slot texts replaced (old text -> new text)."""
    w, h, inner = preview(name)
    for old, new in text.items():
        inner = re.sub(r'>\s*%s\s*<' % re.escape(old), '>%s<' % new, inner)
    return '<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx">%s</div>' % (x, y, w, h, inner)

def layout_slide(name):
    h = open('%s/components/Layout%s/preview.html' % (SYS, name)).read()
    return re.search(r'<section[^>]*>(.*)</section>', h, re.S).group(1)

slides = {}
# 1 Light page from components: Eyebrow + three Stat columns (positions as the system's source slide uses them)
slides['schedule'] = ('th-light', [
    place('Eyebrow', 86, 50, **{'Manual': 'Working schedule'}),
    place('StatColumn', 77, 268, **{'01': '12', 'hrs': 'wks', 'Biweekly Workshop session': 'Build the first slice'}),
    place('StatColumn', 664, 268, **{'01': '03', 'hrs': 'calls', 'Biweekly Workshop session': 'Stakeholder check-ins'}),
    place('StatColumn', 1254, 268, **{'01': '48', 'hrs': 'hrs', 'Biweekly Workshop session': 'Team time per week'}),
], 'Eyebrow plus three Stat columns, placed where the system puts them.')
# 2 Dark page from the verified Statement layout, with the Link button added bottom-right (the button is the white-on-dark one)
body = layout_slide('Statement')
body = body.replace('Design Elements', 'Kickoff').replace('It’s easy', 'Ship the first slice').replace('. Give it a try!', ' in twelve weeks.')
slides['statement'] = ('th-dark', [body, place('LinkButton', 1527, 944, **{'Render Template': 'Read the brief'})],
                       'Statement layout from the system: eyebrow plus a large sentence with the accent phrase; Link button added.')

os.makedirs(OUT + '/slides', exist_ok=True)
order = []
for k, (cls, parts, note) in slides.items():
    order.append(k)
    open('%s/slides/%s.html' % (OUT, k), 'w').write('<section id="%s" class="%s">\n%s\n<aside>%s</aside>\n</section>' % (k, cls, '\n'.join(parts), note))
root = [l for l in dsbuild.compile_css(tk).split('\n') if not l.startswith('@font-face')]
themes = [t['id'] for t in tk['color']['themes']]
cls = ''.join('section.th-%s{%sbackground:var(--paper);color:var(--ink)}\n' % (th, ''.join('--%s:%s;' % (t['name'], t['value'][th]) for t in tk['color']['tokens'] if isinstance(t['value'], dict))) for th in themes)
open(OUT + '/deck.css', 'w').write('\n'.join(root) + "\nbody{font-family:var(--font-body)}\nsection{font-family:var(--font-body)}\n" + cls)
json.dump({'v': 5, 'createdOnFiles': {'v': 1, 'at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, 'lists': 'css',
           'format': {'v': 1, 'shared': ['project/deck.css']}, 'title': 'New pages from the deck B design system', 'order': order,
           'sections': {'s1': {'description': 'Two pages composed from the design system', 'start': order[0]}},
           'faces': {'dm-sans': {'family': 'DM Sans', 'href': 'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap'}}, 'designSystems': []},
          open(OUT + '/deck.json', 'w'), indent=1)
print('composed', order)
