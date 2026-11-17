#!/usr/bin/env python3
"""Five-slide test piece for deck2slides: a Claude Slides-artifact deck (deck.json, deck.css, slides/*.html, assets/).
Grid: 1920 x 1080, 12 columns of 118 px, 24 px gutters, 120 px side margins, 8 px baseline.
Type: Bricolage Grotesque (display, headings) + Inter (body). Scale: 160 / 96 / 56 / 36 / 28 / 20 px.
Images: NASA, public domain (see assets/CREDITS.md). Run: python3 generate.py"""
import json, os
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(H + '/slides', exist_ok=True)

MARGIN, COL, GUT = 120, 118, 24
def cx(i): return MARGIN + i * (COL + GUT)                 # left edge of column i (0-based)
def span(n): return n * COL + (n - 1) * GUT                # width of n columns

INK, PAPER, ACCENT, VIOLET, LIME, MUTE, RULE = '#14142E', '#F5F2EA', '#FF4A1C', '#6B5BFF', '#B4F000', '#5B5F73', '#D8D3C4'
slides = {}

def box(x, y, w, h, style='', inner='', cls=''):
    return '<div%s style="position:absolute;left:%dpx;top:%dpx;width:%dpx;%s%s">%s</div>' % (' class="%s"' % cls if cls else '', x, y, w, 'height:%dpx;' % h if h else '', style, inner)
def text(x, y, w, cls, t, style=''): return box(x, y, w, 0, style, t, cls)
def img(x, y, w, h, src, style=''):
    return '<img src="assets/%s" style="position:absolute;left:%dpx;top:%dpx;width:%dpx;height:%dpx;object-fit:cover;%s">' % (src, x, y, w, h, style)
def footer(n, dark=False):
    c = '#8A8CA8' if dark else MUTE; rule = '#34345A' if dark else RULE
    return [box(MARGIN, 996, span(12), 2, 'background:%s' % rule),
            text(MARGIN, 1020, 200, 'cap', '%02d' % n, 'color:%s' % c),
            text(cx(6), 1020, span(6), 'cap', 'deck2slides test piece', 'color:%s;text-align:right' % c)]
def section(name, body, bg=PAPER):
    slides[name] = '<section id="%s" style="background:%s">\n%s\n</section>' % (name, bg, '\n'.join(body))

# ---- 1 title page (dark)
b = [box(cx(6) + 12, 120, 840, 840, 'overflow:hidden;border-radius:50%;background:#000', img(-70, -70, 980, 980, 'apollo17.jpg').replace('position:absolute;left:-70px;top:-70px', 'position:absolute;left:-70px;top:-70px')),
     text(MARGIN, 120, 600, 'eyebrow', 'Test piece · 2026', 'color:%s' % LIME),
     text(MARGIN, 232, span(6), 'display', 'Same deck,<br>three apps.', 'color:%s;font-size:144px;line-height:136px' % PAPER),
     text(MARGIN, 600, span(5), 'body', 'One grid, one type system, public-domain images. Built in Claude, shown in Google Slides and PowerPoint.', 'color:#C9CADB'),
     box(MARGIN, 920, 220, 56, 'background:%s;border-radius:999px;color:#fff;font:700 22px/56px Inter;text-align:center;letter-spacing:2px' % ACCENT, 'CLAUDE CODE')] + footer(1, True)
section('title', b, INK)

# ---- 2 grid + principles (the 12 columns are drawn faintly)
b = [box(cx(i), 0, COL, 1080, 'background:rgba(107,91,255,0.07)') for i in range(12)]
b += [text(MARGIN, 120, 600, 'eyebrow', '01 — System', 'color:%s' % VIOLET),
      text(MARGIN, 176, span(9), 'h1', 'Twelve columns on an 8 px rhythm.')]
cards = [('01', 'Grid', 'Every block starts on a column edge and ends on one. Gutters are 24 px, margins 120 px.', '#fff', INK, MUTE),
         ('02', 'Type', 'Two families, six sizes. Headings in Bricolage Grotesque, text in Inter on a 40 px line.', '#fff', INK, MUTE),
         ('03', 'Image', 'Pictures keep their own crop, mask and shadow, so they stay editable after export.', None, '#fff', '#E6E3FF')]
for i, (n, t, d, bg, fg, mc) in enumerate(cards):
    x = cx(i * 4); w = span(4)
    st = ('background:%s;' % bg) if bg else 'background:linear-gradient(135deg,%s 0%%,%s 100%%);' % (VIOLET, ACCENT)
    b.append(box(x, 520, w, 400, st + 'border-radius:32px;box-shadow:0 24px 48px rgba(20,20,46,0.14)'))
    b.append(text(x + 48, 568, w - 96, 'h2', n, 'color:%s' % (ACCENT if bg else LIME)))
    b.append(text(x + 48, 664, w - 96, 'h3', t, 'color:%s' % fg))
    b.append(text(x + 48, 720, w - 96, 'body', d, 'color:%s;font-size:24px;line-height:32px' % mc))
b += footer(2)
section('grid', b)

# ---- 3 image + text split
b = [img(MARGIN, 120, span(6), 840, 'mars.jpg', 'border-radius:40px;box-shadow:0 32px 64px rgba(20,20,46,0.25)'),
     text(cx(7), 160, span(5), 'eyebrow', '02 — Imagery', 'color:%s' % VIOLET),
     text(cx(7), 216, span(5), 'h2', 'Open images, native crops.'),
     text(cx(7), 368, span(5), 'body', 'The photograph is a real picture element: rounded corners, a soft shadow and a crop you can adjust in Slides or PowerPoint.'),
     box(cx(7), 640, 8, 144, 'background:%s;border-radius:4px' % LIME),
     text(cx(7) + 40, 636, span(5) - 40, 'h3', '“A pixel-faithful copy is a picture. A native one stays a deck.”'),
     text(cx(7), 892, span(5), 'cap', 'Valles Marineris, Mars. NASA / USGS, public domain, via Wikimedia Commons.')] + footer(3)
section('image', b)

# ---- 4 type + colour system
rows = [('Display · Bricolage 800 · 160 / 0.92', 'display', 'Space', 'font-size:120px;line-height:116px', 150),
        ('H1 · Bricolage 700 · 96 / 96', 'h1', 'Headline', '', 300),
        ('H2 · Bricolage 700 · 56 / 64', 'h2', 'Subheading', '', 430),
        ('H3 · Inter 600 · 36 / 44', 'h3', 'Section title', '', 530),
        ('Body · Inter 400 · 28 / 40', 'body', 'Body copy sits on a 40 px line.', '', 620),
        ('Caption · Inter 500 · 20 / 28', 'cap', 'Caption and credit lines, in muted ink.', '', 704)]
b = [text(MARGIN, 80, 600, 'eyebrow', '03 — Type and colour', 'color:%s' % VIOLET)]
for lab, cls, sample, st, y in rows:
    b.append(text(MARGIN, y, span(7), 'cap', lab, 'color:%s' % VIOLET if cls != 'cap' else 'color:%s' % VIOLET))
    b.append(text(MARGIN, y + 28, span(7), cls, sample, st))
sw = [(INK, 'Ink', 'Text, dark pages'), (PAPER, 'Paper', 'Page ground'), (ACCENT, 'Signal', 'Accent, pills'), (VIOLET, 'Violet', 'Labels, links'), (LIME, 'Lime', 'Highlights'), (MUTE, 'Mute', 'Secondary text')]
for i, (c, n, u) in enumerate(sw):
    y = 150 + i * 118
    b.append(box(cx(8), y, 96, 96, 'background:%s;border-radius:24px;border:2px solid %s' % (c, RULE)))
    b.append(text(cx(8) + 128, y + 8, span(4) - 128, 'h3', n))
    b.append(text(cx(8) + 128, y + 52, span(4) - 128, 'cap', '%s · %s' % (c.upper(), u)))
b.append(text(MARGIN, 900, span(12), 'cap', '12 columns · 118 px · 24 px gutters · 120 px margins · 8 px baseline', 'color:%s' % MUTE))
b += footer(4)
section('system', b)

# ---- 5 closing title page (gradient)
b = [box(0, 0, 1920, 1080, 'background:linear-gradient(135deg,%s 0%%,%s 62%%)' % (VIOLET, INK)),
     img(cx(7), 120, span(5), 840, 'aldrin.jpg', 'border-radius:40px;box-shadow:0 32px 64px rgba(0,0,0,0.35)'),
     text(MARGIN, 120, 600, 'eyebrow', '04 — Close', 'color:%s' % LIME),
     text(MARGIN, 232, span(6), 'display', 'Thank you.', 'color:#fff'),
     text(MARGIN, 520, span(6), 'body', 'Questions on the grid, the type scale or the export route: this deck is the test piece for all three.', 'color:#E6E3FF'),
     box(MARGIN, 700, span(6), 2, 'background:rgba(255,255,255,0.35)'),
     text(MARGIN, 732, span(6), 'cap', 'Images (public domain, via Wikimedia Commons)', 'color:#fff;font-weight:600'),
     text(MARGIN, 772, span(6), 'cap', 'Earth: NASA / Apollo 17 · Mars: NASA / USGS · Buzz Aldrin: NASA / Neil Armstrong, Apollo 11', 'color:#E6E3FF')] + footer(5, True)
section('close', b, INK)

for k, v in slides.items(): open('%s/slides/%s.html' % (H, k), 'w').write(v)
faces = json.load(open(H + '/../features/deck.json'))['faces']
json.dump({'v': 5, 'title': 'deck2slides five-page test piece', 'order': list(slides), 'faces': faces, 'designSystems': []}, open(H + '/deck.json', 'w'), indent=1)
open(H + '/deck.css', 'w').write("""*{box-sizing:border-box;margin:0}
section{background:%s;color:%s;font-family:'Inter',Arial,sans-serif;padding:0;display:block}
.eyebrow{font:600 18px/24px Inter;letter-spacing:4px;text-transform:uppercase}
.display{font:800 160px/148px 'Bricolage Grotesque';letter-spacing:-4px}
.h1{font:700 96px/96px 'Bricolage Grotesque';letter-spacing:-2px}
.h2{font:700 56px/64px 'Bricolage Grotesque';letter-spacing:-1px}
.h3{font:600 36px/44px Inter}
.body{font:400 28px/40px Inter}
.cap{font:500 20px/28px Inter;color:%s}
""" % (PAPER, INK, MUTE))
print(len(slides), 'slides:', ' '.join(slides))
