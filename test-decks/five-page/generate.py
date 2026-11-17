#!/usr/bin/env python3
"""Five-slide test piece in the real Claude Slides format (deck.json v5 + deck.css + one <section> per slide, uploaded /_blob/ images).
Grid: 1920 x 1080, 12 columns of 124 px, 16 px gutters, 128 px side margins (so 140 px per column step), 8 px baseline.
Type: Bricolage Grotesque (display, headings) + Inter (text). Scale: 144 / 96 / 56 / 40 / 32 / 24 px (nothing under 24 px, as the format requires).
Images: NASA, public domain (assets/CREDITS.md), uploaded to the artifact; ids in blobs.json. Run: python3 generate.py"""
import json, os, datetime
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(H + '/slides', exist_ok=True)

MARGIN, COL, GUT = 128, 124, 16
def cx(i): return MARGIN + i * (COL + GUT)                 # left edge of column i (0-based)
def span(n): return n * COL + (n - 1) * GUT                # width of n columns

BLOBS = json.load(open(H + '/blobs.json'))                 # name -> {"id": ..., "file": local file the id stands for}
def src(name): return '/_blob/' + BLOBS[name]['id']
slides = {}; order = []

def pin(x, y, w=None, style=''): return 'position:absolute;left:%dpx;top:%dpx;%s%s' % (x, y, 'width:%dpx;' % w if w else '', style)
def footer(n, dark=False):
    return '<div class="foot%s" style="%s"><p>%02d</p><p>deck2slides test piece</p></div>' % (' dark' if dark else '', pin(MARGIN, 992, span(12)), n)
def section(name, cls, body, bg=None):
    order.append(name)
    style = ' style="background:%s"' % bg if bg else ''
    slides[name] = '<section id="%s" class="%s"%s>\n%s\n<aside>%s</aside>\n</section>' % (name, cls, style, '\n'.join(body), NOTES[name])

NOTES = {'title': 'Title page. One grid, one type system, public-domain images.',
         'grid': 'The twelve columns are drawn behind the cards. Cards span four columns each.',
         'image': 'A real picture element: rounded corners, a soft shadow and a crop you can adjust.',
         'system': 'The type scale and the palette this deck uses.',
         'close': 'Closing page with image credits.'}

# ---- 1 title page (dark)
section('title', 'dark', [
    '<x-shape kind="ellipse" style="%s"></x-shape>' % pin(cx(7) - 140, 128, 824, 'height:824px;box-sizing:border-box;border:12px solid #B4F000'),
    '<img src="%s" alt="The Earth seen from Apollo 17" style="%s">' % (src('apollo17_disk.jpg'), pin(cx(7) + 16, 284, None, 'width:512px;height:512px;object-fit:cover;border-radius:256px')),
    '<div class="col" style="%s">' % pin(MARGIN, 128, span(6), 'height:824px'),
    '<div class="stack"><p class="eyebrow lime">Test piece · 2026</p><h1 class="display">Same deck,<br>three apps.</h1></div>',
    '<div class="stack"><p class="body soft">One grid, one type system, public-domain images. Built in Claude, shown in Google Slides and PowerPoint.</p><p class="pill">CLAUDE CODE</p></div>',
    '</div>', footer(1, True)])

# ---- 2 grid + principles (the 12 columns are drawn faintly)
cols = ''.join('<div class="gcol" style="position:absolute;left:%dpx;top:0px;width:%dpx;height:1080px"></div>' % (cx(i), COL) for i in range(12))
cards = [('01', 'Grid', 'Every block starts on a column edge and ends on one. Gutters are 16 px, margins 128 px.', ''),
         ('02', 'Type', 'Two families, six sizes. Headings in Bricolage Grotesque, text in Inter on a 44 px line.', ''),
         ('03', 'Image', 'Pictures keep their own crop, mask and shadow, so they stay editable after export.', ' grad')]
body = ['<div style="position:absolute;left:0px;top:0px;width:1920px;height:1080px">%s</div>' % cols,
        '<p class="eyebrow violet" style="%s">01 — System</p>' % pin(MARGIN, 128, 800),
        '<h1 class="h1" style="%s">Twelve columns on an 8 px rhythm.</h1>' % pin(MARGIN, 184, span(9))]
for i, (n, t, d, g) in enumerate(cards):
    body.append('<div class="card%s" style="%s"><p class="num">%s</p><h3 class="h3">%s</h3><p class="body small">%s</p></div>' % (g, pin(cx(i * 4), 520, span(4)), n, t, d))
body.append(footer(2))
section('grid', 'paper', body)

# ---- 3 image + text split
section('image', 'paper', [
    '<img src="%s" alt="Mars, Valles Marineris" style="%s">' % (src('mars.jpg'), pin(MARGIN, 128, span(6), 'height:824px;object-fit:cover;border-radius:40px;box-shadow:0 32px 64px rgba(20,20,46,0.25)')),
    '<div class="col" style="%s">' % pin(cx(7), 128, span(5), 'height:824px'),
    '<div class="stack"><p class="eyebrow violet">02 — Imagery</p><h2 class="h2">Open images, native crops.</h2><p class="body">The photograph is a real picture element: rounded corners, a soft shadow and a crop you can adjust in Slides or PowerPoint.</p></div>',
    '<div class="quote"><div class="bar"></div><h3 class="h3">“A pixel-faithful copy is a picture. A native one stays a deck.”</h3></div>',
    '<p class="cap">Valles Marineris, Mars. NASA / USGS, public domain, via Wikimedia Commons.</p>', '</div>', footer(3)])

# ---- 4 type + colour system
rows = [('Display · Bricolage 800 · 144 / 136', 'display', 'Space'), ('H1 · Bricolage 700 · 96 / 96', 'h1', 'Headline'), ('H2 · Bricolage 700 · 56 / 64', 'h2', 'Subheading'),
        ('H3 · Inter 600 · 40 / 44', 'h3', 'Section title'), ('Body · Inter 400 · 32 / 44', 'body', 'Body copy sits on a 44 px line.'), ('Caption · Inter 500 · 24 / 32', 'cap', 'Caption and credit lines, in muted ink.')]
tag = {'display': 'p', 'h1': 'h1', 'h2': 'h2', 'h3': 'h3', 'body': 'p', 'cap': 'p'}
b = ['<p class="eyebrow violet" style="%s">03 — Type and colour</p>' % pin(MARGIN, 128, 800),
     '<div class="specimen" style="%s">%s</div>' % (pin(MARGIN, 184, span(7)), ''.join('<div class="row"><p class="tag">%s</p><%s class="%s">%s</%s></div>' % (lab, tag[c], c, smp, tag[c]) for lab, c, smp in rows))]
sw = [('#14142E', 'Ink', 'Text, dark pages'), ('#F5F2EA', 'Paper', 'Page ground'), ('#FF4A1C', 'Signal', 'Accent, pills'), ('#6B5BFF', 'Violet', 'Labels, links'), ('#B4F000', 'Lime', 'Highlights'), ('#5B5F73', 'Mute', 'Secondary text')]
b.append('<div class="swatches" style="%s">%s</div>' % (pin(cx(8), 184, span(4)), ''.join('<div class="sw"><div class="chip" style="background:%s"></div><div><h3 class="h3">%s</h3><p class="cap">%s · %s</p></div></div>' % (c, n, c, u) for c, n, u in sw)))
b.append('<p class="cap" style="%s">12 columns · 124 px · 16 px gutters · 128 px margins · 8 px baseline</p>' % pin(MARGIN, 912, span(12)))
b.append(footer(4))
section('system', 'paper', b)

# ---- 5 closing title page (gradient section)
section('close', 'dark', [
    '<img src="%s" alt="Buzz Aldrin on the Moon, Apollo 11" style="%s">' % (src('aldrin.jpg'), pin(cx(7), 128, span(5), 'height:824px;object-fit:cover;border-radius:40px;box-shadow:0 32px 64px rgba(0,0,0,0.35)')),
    '<div class="col" style="%s">' % pin(MARGIN, 128, span(6), 'height:824px'),
    '<div class="stack"><p class="eyebrow lime">04 — Close</p><h1 class="display">Thank you.</h1><p class="body soft">Questions on the grid, the type scale or the export route: this deck is the test piece for all three.</p></div>',
    '<div class="stack credits"><p class="cap white">Images (public domain, via Wikimedia Commons)</p><p class="cap soft">Earth: NASA / Apollo 17 · Mars: NASA / USGS · Buzz Aldrin: NASA / Neil Armstrong, Apollo 11</p></div>',
    '</div>', footer(5, True)], bg='linear-gradient(135deg,#6B5BFF 0%,#14142E 62%)')

for k, v in slides.items(): open('%s/slides/%s.html' % (H, k), 'w').write(v)
json.dump({'v': 5, 'createdOnFiles': {'v': 1, 'at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}, 'lists': 'css', 'format': {'v': 1, 'shared': ['project/deck.css']},
           'title': 'deck2slides five-page test piece', 'order': order,
           'sections': {'s1': {'description': 'Title page', 'start': 'title'}, 's2': {'description': 'Grid, type, colour and imagery', 'start': 'grid'}, 's3': {'description': 'Close and credits', 'start': 'close'}},
           'faces': {'bricolage-grotesque': {'family': 'Bricolage Grotesque', 'href': 'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@400..800&display=swap'},
                     'inter': {'family': 'Inter', 'href': 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'}}, 'designSystems': []}, open(H + '/deck.json', 'w'), indent=1)
open(H + '/deck.css', 'w').write("""body{font-family:'Inter',Arial,sans-serif;color:#14142E}
section{padding:128px;background:#F5F2EA;color:#14142E;font-family:'Inter',Arial,sans-serif}
section.dark{background:#14142E;color:#F5F2EA}
.eyebrow{font-size:24px;line-height:32px;font-weight:600;letter-spacing:4px;text-transform:uppercase}
.display{font-family:'Bricolage Grotesque',Arial,sans-serif;font-size:144px;line-height:136px;font-weight:800;letter-spacing:-4px}
.h1{font-family:'Bricolage Grotesque',Arial,sans-serif;font-size:96px;line-height:96px;font-weight:700;letter-spacing:-2px}
.h2{font-family:'Bricolage Grotesque',Arial,sans-serif;font-size:56px;line-height:64px;font-weight:700;letter-spacing:-1px}
.h3{font-family:Inter,Arial,sans-serif;font-size:40px;line-height:44px;font-weight:600}
.body{font-size:32px;line-height:44px;font-weight:400}
.small{font-size:28px;line-height:36px;color:#5B5F73}
.cap{font-size:24px;line-height:32px;font-weight:500;color:#5B5F73}
.lime{color:#B4F000}.violet{color:#6B5BFF}.soft{color:#C9CADB}.white{color:#FFFFFF}
.col{display:flex;flex-direction:column;justify-content:space-between}
.stack{display:flex;flex-direction:column;align-items:flex-start;gap:32px}
.pill{box-sizing:border-box;background:#FF4A1C;color:#FFFFFF;font-size:24px;line-height:56px;font-weight:700;letter-spacing:2px;padding:0 32px;border-radius:999px}
.gcol{background:rgba(107,91,255,0.07)}
.card{box-sizing:border-box;background:#FFFFFF;border-radius:32px;box-shadow:0 24px 48px rgba(20,20,46,0.14);padding:48px;display:flex;flex-direction:column;gap:16px}
.card.grad{background:linear-gradient(135deg,#6B5BFF 0%,#FF4A1C 100%);color:#FFFFFF}
.card.grad .small{color:#E6E3FF}
.num{font-family:'Bricolage Grotesque',Arial,sans-serif;font-size:56px;line-height:64px;font-weight:700;color:#FF4A1C}
.card.grad .num{color:#B4F000}
.quote{display:flex;gap:32px;align-items:flex-start}
.bar{width:8px;height:132px;background:#B4F000;border-radius:4px}
.specimen{display:flex;flex-direction:column;gap:20px}
.row{display:flex;flex-direction:column}
.tag{font-size:24px;line-height:32px;font-weight:500;color:#6B5BFF}
.swatches{display:flex;flex-direction:column;gap:24px}
.sw{display:flex;gap:32px;align-items:center}
.chip{box-sizing:border-box;width:96px;height:96px;border-radius:24px;border:2px solid #D8D3C4}
.foot{display:flex;justify-content:space-between}
.foot p{font-size:24px;line-height:24px;font-weight:500;color:#5B5F73}
.foot.dark p{color:#8A8CA8}
""")
print(len(slides), 'slides:', ' '.join(order))
