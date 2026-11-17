#!/usr/bin/env python3
"""Generates the feature test deck (a Claude Slides-artifact layout: deck.json, deck.css, slides/*.html, assets/).
One slide per translation rule, each sweeping a range of values, so the Google round trip shows which values are wrong.
Run: python3 generate.py   (output is committed; regenerate after editing)"""
import json, os, math
from PIL import Image, ImageDraw
H = os.path.dirname(os.path.abspath(__file__)); os.makedirs(H + '/slides', exist_ok=True); os.makedirs(H + '/assets', exist_ok=True)
FACES = {'inter': {'family': 'Inter', 'href': 'https://fonts.googleapis.com/css2?family=Inter:wght@100..900&display=swap'},
         'bricolage-grotesque': {'family': 'Bricolage Grotesque', 'href': 'https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@200..800&display=swap'}}
slides = {}
def box(x, y, w, extra, text, h=None):
    return '<div style="position:absolute;left:%dpx;top:%dpx;width:%dpx;%s%s">%s</div>' % (x, y, w, ('height:%dpx;' % h) if h else '', extra, text)
def label(x, y, t): return box(x, y, 300, 'font:500 16px Inter;color:#888', t)
def slide(name, body): slides[name] = '<section id="%s">\n%s\n</section>' % (name, '\n'.join(body))

# 1 font size sweep (two families)
b = []; y = 30
for i, fs in enumerate([12, 16, 20, 28, 40, 56, 80, 120]):
    b.append(box(40, y, 880, 'font:400 %dpx/1.2 Inter;white-space:nowrap' % fs, 'Hxg Sphinx %d' % fs)); b.append(box(980, y, 900, 'font:700 %dpx/1.2 \'Bricolage Grotesque\';white-space:nowrap' % fs, 'Hxg Sphinx %d' % fs)); y += int(fs * 1.2) + 14
slide('font-size', b)
# 2 line height sweep: 7 columns x 2 families, 3 lines each
b = []
for fi, fam in enumerate(['Inter', "'Bricolage Grotesque'"]):
    for ci, lh in enumerate([0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 2.0]):
        b.append(box(40 + ci * 265, 60 + fi * 500, 240, 'font:400 40px/%s %s' % (lh, fam), 'Eh<br>Eh<br>Eh')); b.append(label(40 + ci * 265, 20 + fi * 500, 'lh %s' % lh))
slide('line-height', b)
# 3 weights
b = []
for fi, fam in enumerate(['Inter', "'Bricolage Grotesque'"]):
    for wi, w in enumerate([100, 200, 300, 400, 500, 600, 700, 800, 900]):
        b.append(box(40 + fi * 960, 30 + wi * 112, 900, 'font:%d 64px/1.2 %s;white-space:nowrap' % (w, fam), 'Weight %d Hamburg' % w))
slide('weights', b)
# 4 letter spacing
b = []
for i, ls in enumerate([-4, -2, -1, 0, 1, 2, 4, 8, 12]):
    b.append(box(40, 30 + i * 112, 1800, 'font:600 56px/1.2 Inter;letter-spacing:%dpx;white-space:nowrap' % ls, 'Spacing %d px, then some more' % ls))
slide('letter-spacing', b)
# 5 alignment in boxes (with visible edges via border)
b = []
for ri, al in enumerate(['left', 'center', 'right']):
    for ci, w in enumerate([400, 700, 1000]):
        b.append(box(40 + ci * 620, 60 + ri * 330, w if w < 600 else 560, 'font:500 36px/1.3 Inter;text-align:%s;border:2px solid #c33;padding:20px' % al, 'Aligned %s in a box. The quick brown fox jumps over the lazy dog.' % al))
slide('alignment', b)
# 6 wrapping edge cases
b = [label(40, 10, 'near-miss: box width = text width +/- px'),]
for i, d in enumerate([-6, -2, 0, 2, 6, 14]):
    b.append(box(40, 40 + i * 70, 560 + d, 'font:500 32px/1.2 Inter;border-right:2px solid #c33', 'Measured to fit exactly'))
b += [label(40, 480, 'shrink-wrapped multi-line: box exactly as wide as longest line'),
      '<div style="position:absolute;left:40px;top:510px;font:600 44px/1.15 Inter;display:inline-block;background:#eef">Two short lines<br>then a longer final line here</div>',
      label(1000, 10, 'nowrap, long word, centred wrap'),
      box(1000, 40, 300, 'font:500 28px/1.2 Inter;white-space:nowrap', 'nowrap text overflowing its box'),
      box(1000, 120, 300, 'font:500 28px/1.2 Inter;border:2px solid #c33', 'Supercalifragilisticexpialidocious word'),
      box(1000, 300, 560, 'font:500 36px/1.25 Inter;text-align:center;border:2px solid #c33', 'A centred paragraph that wraps over several lines in a fixed width box, to check the break points.')]
slide('wrapping', b)
# 7 corner radius + text inside
b = []
for i, r in enumerate([0, 8, 24, 48, 90, 140]):
    b.append(box(40 + i * 305, 40, 280, 'font:600 28px/1.2 Inter;background:#14142E;color:#fff;border-radius:%dpx;padding:40px 30px;text-align:center' % r, 'Radius %d' % r, 280))
    b.append(box(40 + i * 305, 400, 280, 'font:600 28px/1.2 Inter;background:#B4F000;border-radius:%dpx;padding:30px 24px' % r, 'Left aligned text in radius %d' % r, 240))
b.append(box(40, 720, 520, 'font:700 30px/1 Inter;background:#FF4A1C;color:#fff;border-radius:999px;padding:0 30px;display:flex;align-items:center;justify-content:center', 'Pill label', 90))
b.append(box(640, 700, 140, 'font:700 40px/1 Inter;background:#6B5BFF;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center', '7', 140))
b.append(box(840, 700, 300, 'font:700 40px/1 Inter;background:#6B5BFF;color:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center', 'ellipse', 200))
slide('corner-radius', b)
# 8 borders and dashes
b = []
for i, (st, w) in enumerate([('solid', 1), ('solid', 4), ('solid', 12), ('dashed', 2), ('dashed', 6), ('dotted', 2), ('dotted', 6)]):
    b.append(box(40 + (i % 4) * 460, 40 + (i // 4) * 300, 400, 'border:%dpx %s #14142E;border-radius:%dpx;font:500 24px Inter;padding:20px' % (w, st, 0 if i < 3 else 20), '%s %dpx' % (st, w), 220))
b.append(box(40, 640, 400, 'border-left:8px solid #c33;font:500 24px Inter;padding:20px', 'left only', 100)); b.append(box(500, 640, 400, 'border-bottom:6px solid #c33;border-top:2px solid #36c;font:500 24px Inter;padding:20px', 'top + bottom', 100))
slide('borders', b)
# 9 shadows
b = []
for i, (x, y_, bl, a) in enumerate([(0, 4, 8, .2), (0, 12, 24, .25), (0, 24, 48, .3), (10, 10, 0, .4), (-12, 8, 20, .35), (0, 0, 30, .5), (0, 40, 80, .25), (6, 6, 12, .15)]):
    b.append(box(60 + (i % 4) * 460, 60 + (i // 4) * 460, 340, 'background:#fff;border-radius:%dpx;box-shadow:%dpx %dpx %dpx rgba(20,20,46,%s);font:500 22px Inter;padding:20px' % (0 if i % 2 else 32, x, y_, bl, a), 'shadow %d %d %d a%s' % (x, y_, bl, a), 300))
slide('shadows', b)
# 10 alpha fills and opacity
b = ['<div style="position:absolute;left:0;top:0;width:1920px;height:540px;background:linear-gradient(90deg,#fff 0,#fff 50%,#222 50%)"></div>'.replace('linear-gradient(90deg,#fff 0,#fff 50%,#222 50%)', '#e0e0e0')]
for i, a in enumerate([1, .8, .6, .4, .2, .1]):
    b.append(box(40 + i * 300, 80, 260, 'background:rgba(255,74,28,%s);font:600 24px Inter;padding:20px' % a, 'fill a=%s' % a, 300))
    b.append(box(40 + i * 300, 640, 260, 'background:#14142E;opacity:%s;color:#fff;font:600 24px Inter;padding:20px' % a, 'opacity %s' % a, 300))
slide('alpha', b)
# 11 rotation
b = []
for i, r in enumerate([-30, -15, -5, 0, 5, 15, 30, 90]):
    b.append(box(100 + (i % 4) * 450, 80 + (i // 4) * 480, 300, 'transform:rotate(%ddeg);background:#B4F000;border-radius:24px;font:600 28px/1.2 Inter;padding:30px;text-align:center' % r, 'rotate %d deg', 200).replace('%d deg', '%d deg' % r))
slide('rotation', b)
# 12 pictures
def mkimg(name, w, h):
    im = Image.new('RGB', (w, h), '#6B5BFF'); d = ImageDraw.Draw(im)
    for x in range(0, w, 40): d.line([(x, 0), (x, h)], fill='#8f84ff')
    for yy in range(0, h, 40): d.line([(0, yy), (w, yy)], fill='#8f84ff')
    d.rectangle([0, 0, w - 1, h - 1], outline='#FF4A1C', width=8); d.line([(0, 0), (w, h)], fill='#fff', width=6); d.line([(0, h), (w, 0)], fill='#fff', width=6); d.ellipse([w // 2 - 60, h // 2 - 60, w // 2 + 60, h // 2 + 60], outline='#B4F000', width=8)
    im.save(H + '/assets/' + name)
mkimg('wide.png', 800, 400); mkimg('tall.png', 400, 800); mkimg('square.png', 600, 600)
b = []
for i, (img, fit, r) in enumerate([('wide', 'cover', 0), ('wide', 'contain', 0), ('tall', 'cover', 0), ('tall', 'contain', 0), ('wide', 'cover', 40), ('square', 'cover', 300), ('tall', 'cover', 100), ('square', 'contain', 60)]):
    x, y_ = 40 + (i % 4) * 470, 40 + (i // 4) * 520
    b.append('<img src="assets/%s.png" style="position:absolute;left:%dpx;top:%dpx;width:420px;height:300px;object-fit:%s;border-radius:%dpx;background:#ddd">' % (img, x, y_, fit, r)); b.append(label(x, y_ + 310, '%s %s r%d' % (img, fit, r)))
b.append('<img src="assets/wide.png" style="position:absolute;left:40px;top:1000px;width:10px;height:10px;opacity:0">')
slide('pictures', b[:-1])
# 13 shadows on pictures + opacity
b = ['<img src="assets/square.png" style="position:absolute;left:100px;top:100px;width:360px;height:360px;object-fit:cover;border-radius:48px;box-shadow:0 20px 50px rgba(0,0,0,.35)">',
     '<img src="assets/wide.png" style="position:absolute;left:600px;top:100px;width:500px;height:300px;object-fit:cover;opacity:.5">',
     '<img src="assets/tall.png" style="position:absolute;left:1250px;top:100px;width:300px;height:500px;object-fit:cover;border-radius:150px;transform:rotate(8deg)">']
slide('picture-effects', b)
# 14 gif in a rounded mask
frames = []
for k in range(12):
    im = Image.new('RGB', (480, 270), '#14142E'); d = ImageDraw.Draw(im); x = 40 + k * 32
    d.ellipse([x, 90, x + 90, 180], fill='#B4F000'); d.text((10, 10), 'frame %d' % k, fill='#fff'); frames.append(im)
frames[0].save(H + '/assets/spin.gif', save_all=True, append_images=frames[1:], duration=100, loop=0)
slide('gif', ['<img src="assets/spin.gif" data-video="spin" style="position:absolute;left:100px;top:100px;width:960px;height:540px;border-radius:60px;object-fit:cover">',
              '<img src="assets/spin.gif" data-video="spin" style="position:absolute;left:1200px;top:100px;width:400px;height:400px;border-radius:200px;object-fit:cover">'])
# 15 registration grid: position and scale errors become measurable (1 px lines every 100 px, markers at corners and centre)
b = []
for x in range(0, 1921, 100): b.append('<div style="position:absolute;left:%dpx;top:0;width:%dpx;height:1080px;background:%s"></div>' % (max(0, x - 1) if x else 0, 2 if x % 500 == 0 else 1, '#c33' if x % 500 == 0 else '#9aa'))
for y in range(0, 1081, 100): b.append('<div style="position:absolute;left:0;top:%dpx;width:1920px;height:%dpx;background:%s"></div>' % (max(0, y - 1) if y else 0, 2 if y % 500 == 0 else 1, '#c33' if y % 500 == 0 else '#9aa'))
for x, y in [(0, 0), (1900, 0), (0, 1060), (1900, 1060)]: b.append('<div style="position:absolute;left:%dpx;top:%dpx;width:20px;height:20px;background:#000"></div>' % (x, y))
b.append('<div style="position:absolute;left:860px;top:440px;width:200px;height:200px;border:4px solid #000;border-radius:50%"></div>')
for x in range(200, 1900, 200): b.append(box(x + 4, 4, 90, 'font:500 16px Inter;color:#333', str(x)))
for y in range(200, 1080, 200): b.append(box(4, y + 4, 90, 'font:500 16px Inter;color:#333', str(y)))
slide('grid', b)
# 16 colour accuracy: opaque swatches with their hex, and alpha swatches over white and over black
cols = ['#000000', '#FFFFFF', '#14142E', '#FBFAF8', '#FF4A1C', '#B4F000', '#6B5BFF', '#F3EEDC', '#808080', '#C9CBDA', '#E8458B', '#00A3A3']
b = []
for i, c in enumerate(cols): b.append(box(40 + (i % 6) * 305, 40 + (i // 6) * 250, 280, 'background:%s;border:1px solid #999;font:600 20px Inter;color:%s;padding:16px' % (c, '#fff' if i in (0, 2, 6) else '#000'), c, 220))
b.append('<div style="position:absolute;left:0;top:560px;width:960px;height:520px;background:#fff"></div><div style="position:absolute;left:960px;top:560px;width:960px;height:520px;background:#000"></div>')
for i, a in enumerate([1, .75, .5, .25, .1]): b.append(box(40 + i * 180, 600, 160, 'background:rgba(255,74,28,%s);font:500 16px Inter;padding:10px;color:#888' % a, 'a=%s' % a, 400)); b.append(box(1000 + i * 180, 600, 160, 'background:rgba(180,240,0,%s);font:500 16px Inter;padding:10px;color:#888' % a, 'a=%s' % a, 400))
slide('colour', b)
# 17 text styles: italic, underline, transform, mixed runs in one line, missing glyph, punctuation
b = [box(40, 30, 1800, 'font:italic 400 44px/1.2 Inter', 'Italic Inter, then <b style="font-weight:700">bold</b> and <i>italic inside</i> a normal line'),
     box(40, 120, 1800, 'font:500 44px/1.2 Inter', 'Underlined <u>words in a line</u> and <span style="color:#FF4A1C">coloured</span> <span style="color:#6B5BFF;font-weight:800">mixed weight</span> runs'),
     box(40, 210, 1800, 'font:600 36px/1.2 Inter;text-transform:uppercase;letter-spacing:4px', 'Uppercase with letter spacing'),
     box(40, 290, 1800, 'font:500 44px/1.2 Inter', 'Missing glyph arrow \u2192 and curly \u201cquotes\u201d, an en\u2013dash, an ellipsis\u2026 and \u00a3 \u20ac \u00d7 \u00bd'),
     box(40, 380, 1800, 'font:500 28px/1.2 Inter', 'Small mixed sizes: <span style="font-size:60px;font-weight:700">Big</span> small <span style="font-size:14px">tiny</span> <span style="font-size:44px;font-family:\'Bricolage Grotesque\';font-weight:800">Bricolage</span> back'),
     box(40, 480, 900, 'font:400 30px/1.5 Inter', 'A paragraph with a <a href="https://example.com" style="color:#6B5BFF">hyperlink inside</a>. It wraps over a few lines so the hyperlink and the line breaks can be checked together at 1.5 line height.'),
     box(1000, 480, 880, 'font:400 30px/1.0 Inter;columns:1', 'Tight line height 1.0 paragraph. The quick brown fox jumps over the lazy dog. The quick brown fox jumps over the lazy dog.'),
     box(40, 760, 1800, 'font:700 90px/1 \'Bricolage Grotesque\';letter-spacing:-3px;white-space:nowrap', 'Display headline -3px')]
slide('text-styles', b)
# 18 layering, clipping, opacity
b = ['<div style="position:absolute;left:100px;top:100px;width:400px;height:400px;background:#FF4A1C;border-radius:40px"></div>',
     '<div style="position:absolute;left:300px;top:200px;width:400px;height:400px;background:rgba(107,91,255,.8);border-radius:200px"></div>',
     '<div style="position:absolute;left:500px;top:300px;width:400px;height:400px;background:#B4F000;border:6px solid #14142E;transform:rotate(12deg)"></div>',
     '<div style="position:absolute;left:1100px;top:100px;width:500px;height:300px;overflow:hidden;background:#eef;border-radius:30px"><div style="position:absolute;left:-60px;top:-40px;width:400px;height:400px;background:#FF4A1C;border-radius:200px"></div></div>',
     box(1100, 440, 500, 'font:500 22px Inter;color:#666', 'Left: overlapping shapes (z-order, alpha, rotation). Right: overflow:hidden clips a child (not expressible natively; shows what is lost).'),
     '<div style="position:absolute;left:1100px;top:700px;width:600px;height:200px;opacity:.5"><div style="position:absolute;left:0;top:0;width:300px;height:200px;background:#14142E"></div><div style="position:absolute;left:150px;top:0;width:300px;height:200px;background:#FF4A1C"></div></div>']
slide('layering', b)
# 19 unsupported probes: gradients, filters, clip-path, background images. Documents what silently disappears.
b = ['<div style="position:absolute;left:60px;top:60px;width:500px;height:300px;background:linear-gradient(90deg,#FF4A1C,#6B5BFF);border-radius:30px"></div>',
     '<div style="position:absolute;left:640px;top:60px;width:500px;height:300px;background:radial-gradient(circle,#B4F000,#14142E);border-radius:30px"></div>',
     '<div style="position:absolute;left:1220px;top:60px;width:500px;height:300px;background:#6B5BFF;clip-path:polygon(50% 0,100% 100%,0 100%)"></div>',
     '<div style="position:absolute;left:60px;top:440px;width:500px;height:300px;background:#FF4A1C;filter:blur(8px)"></div>',
     '<div style="position:absolute;left:640px;top:440px;width:500px;height:300px;background:#14142E;mix-blend-mode:multiply;border:3px double #FF4A1C"></div>',
     box(60, 800, 1700, 'font:500 24px Inter;color:#666', 'Probes: linear gradient, radial gradient, clip-path, blur filter, blend mode + double border. Compare with the browser render to see what the converter drops.')]
slide('unsupported', b)
# 20 composite: a realistic slide using several features together
b = ['<div style="position:absolute;left:0;top:0;width:1920px;height:1080px;background:#F3EEDC"></div>',
     box(84, 52, 600, 'font:600 18px Inter;letter-spacing:4px', 'EYEBROW LABEL'),
     box(80, 120, 1100, 'font:800 120px/0.95 \'Bricolage Grotesque\';letter-spacing:-2px', 'A headline that wraps over two lines'),
     box(84, 480, 760, 'font:400 30px/1.4 Inter;color:#464B60', 'Supporting copy in a column. It wraps over several lines at one point four line height, like a typical body paragraph on a slide.'),
     box(84, 720, 300, 'background:#14142E;color:#fff;border-radius:999px;font:700 26px/1 Inter;padding:0 36px;display:flex;align-items:center;justify-content:center', 'Call to action', 80),
     '<div style="position:absolute;left:1000px;top:200px;width:800px;height:640px;background:#fff;border-radius:36px;box-shadow:0 30px 60px rgba(20,20,46,.18)"></div>',
     '<img src="assets/wide.png" style="position:absolute;left:1040px;top:240px;width:720px;height:400px;object-fit:cover;border-radius:24px">',
     box(1040, 670, 720, 'font:700 34px/1.2 Inter', 'Card title'), box(1040, 725, 720, 'font:400 24px/1.4 Inter;color:#464B60', 'Card caption text under the picture, two lines of copy to check wrapping inside a card.'),
     '<div style="position:absolute;left:84px;top:1013px;width:1752px;height:2px;background:#A9ADBD"></div>', box(84, 1030, 900, 'font:600 16px Inter;letter-spacing:3px;color:#464B60', 'FOOTER TEXT'), box(1736, 1026, 100, 'font:700 20px Inter;text-align:right', '12')]
slide('composite', b)
for k, v in slides.items(): open('%s/slides/%s.html' % (H, k), 'w').write(v)
json.dump({'v': 5, 'title': 'deck2slides feature tests', 'order': list(slides), 'faces': FACES, 'designSystems': []}, open(H + '/deck.json', 'w'), indent=1)
open(H + '/deck.css', 'w').write("*{box-sizing:border-box}section{background:#fbfaf8;color:#14142e;font-family:'Inter',Arial,sans-serif;padding:0;display:block}\n")
print(len(slides), 'slides:', ' '.join(slides))
