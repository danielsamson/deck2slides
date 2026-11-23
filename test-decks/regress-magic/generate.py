"""Regression deck for the fixes found on the Magic Circle deck (README: 'What a real deck exposed'). One slide per fix.
python3 test-decks/regress-magic/generate.py   (pictures are drawn here; the two Inter files are fetched from Google Fonts, OFL)."""
import json, os, re, urllib.request
from PIL import Image, ImageDraw, ImageFilter
D = os.path.dirname(os.path.abspath(__file__)); os.makedirs(D + '/slides', exist_ok=True); os.makedirs(D + '/assets', exist_ok=True); os.makedirs(D + '/fonts', exist_ok=True)

def photo(path, w, h, seed):
    im = Image.new('RGB', (w, h)); dr = ImageDraw.Draw(im)
    for y in range(h): dr.line([(0, y), (w, y)], fill=(80 + seed * 30 % 120, 60 + y * 120 // h, 140 - seed * 20 % 80))
    for i in range(12): dr.ellipse([(i * 97 + seed * 31) % w, (i * 53) % h, (i * 97 + seed * 31) % w + 80, (i * 53) % h + 80], fill=(240, 200 - i * 10, 120 + i * 8))
    im.save(path)
photo(D + '/assets/a.png', 400, 400, 1); photo(D + '/assets/bg.png', 1920, 1080, 2)
frames = []
for i in range(8):                                   # an 8-frame animated WebP: a dot crossing a gradient
    im = Image.open(D + '/assets/bg.png').resize((480, 270)); ImageDraw.Draw(im).ellipse([20 + i * 50, 100, 80 + i * 50, 160], fill=(255, 255, 255)); frames.append(im)
frames[0].save(D + '/assets/loop.webp', save_all=True, append_images=frames[1:], duration=100, loop=0)

def gfont(weight):
    p = D + '/fonts/InterLocal-%d.woff2' % weight
    if os.path.exists(p): return
    ua = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'}
    css = urllib.request.urlopen(urllib.request.Request('https://fonts.googleapis.com/css2?family=Inter:wght@%d&display=swap' % weight, headers=ua)).read().decode()
    url = re.findall(r'/\* latin \*/\s*@font-face\s*{[^}]*?url\(([^)]+)\)', css)[0]
    open(p, 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers=ua)).read())
gfont(400); gfont(700)

css = """section { padding: 128px; box-sizing: border-box; background: #f2f4f8; color: #121317; font-family: 'Inter Local', Arial, sans-serif; font-size: 32px; }
h2 { margin: 0; font-size: 48px; font-weight: 700; }
@keyframes breathe { 0%, 100% { transform: scale(0.95); opacity: 0.6; } 50% { transform: scale(1.05); opacity: 1; } }
.breathe { transform-box: fill-box; transform-origin: center; animation: breathe 2s ease-in-out infinite; }
"""
S = {}
S['imgborder'] = """<section id="imgborder"><h2>Picture circles with their own border</h2>
<img src="assets/a.png" alt="A sunset over the sea" style="position:absolute; left:400px; top:400px; width:128px; height:128px; border:4px solid #ffffff; border-radius:256px; box-shadow:0 16px 40px #0000008c">
<img src="assets/a.png" alt="A second picture, cropped" style="position:absolute; left:700px; top:400px; width:128px; height:128px; border:4px solid #ea4335; border-radius:256px; object-fit:cover; box-shadow:0 16px 40px #0000008c">
<div style="position:absolute; left:1000px; top:400px; width:128px; height:128px; border:4px solid #ffffff; border-radius:256px; overflow:hidden; box-sizing:border-box"><img src="assets/a.png" alt="" style="width:200px; height:200px"></div>
<aside>Notes for the picture slide: say why the borders matter.</aside>
</section>"""
S['band'] = """<section id="band" style="background:#121317"><h2 style="color:#fff">Rounded cards with a coloured top border</h2>
<div style="position:absolute; left:300px; top:400px; width:330px; height:350px; background:#fff; border-radius:22px; border-top:8px solid #4285f4; transform:rotate(-7deg); box-sizing:border-box; padding:24px"><p style="margin:0">The world, so far</p></div>
<div style="position:absolute; left:800px; top:400px; width:330px; height:350px; background:#fff; border-radius:22px; border-top:12px solid #fbbc04; border-left:6px solid #34a853; box-sizing:border-box; padding:24px"><p style="margin:0">Two sides</p></div>
</section>"""
S['radial'] = """<section id="radial"><h2>Soft radial glows end softly</h2>
<div style="position:absolute; left:600px; top:250px; width:960px; height:800px; border-radius:50%; background:radial-gradient(closest-side at 50% 55%, rgba(49,134,255,0.45), rgba(49,134,255,0) 100%)"></div>
<div style="position:absolute; left:-200px; top:600px; width:900px; height:600px; border-radius:50%; background:radial-gradient(closest-side, rgba(226,216,250,0.9) 0%, rgba(226,216,250,0) 100%)"></div>
</section>"""
S['glass'] = """<section id="glass"><img src="assets/bg.png" alt="" style="position:absolute; left:0; top:0; width:1920px; height:1080px">
<div style="position:absolute; left:400px; top:380px; width:1120px; height:320px; box-sizing:border-box; border-radius:40px; background:linear-gradient(135deg, rgba(60,64,78,0.55) 0%, rgba(18,19,23,0.62) 100%); border:1.5px solid rgba(255,255,255,0.28); box-shadow:0 30px 90px rgba(0,0,0,0.45); backdrop-filter:blur(28px); padding:60px"><p style="margin:0; color:#fff; font-size:56px; font-weight:700">Text in a child of the panel</p></div>
<p style="position:absolute; left:400px; top:780px; width:400px; box-sizing:border-box; margin:0; padding:24px; border-radius:28px; background:rgba(19,19,20,0.45); backdrop-filter:blur(16px); color:#fff">Text in the panel itself</p>
</section>"""
S['hyphen'] = """<section id="hyphen"><h2>Breaks after a hyphen</h2>
<p style="width:525px; margin-top:80px; font-size:44px">Then it found the close-up and the cut.</p>
</section>"""
S['loop'] = """<section id="loop"><h2>Loops become GIFs</h2><p style="width:600px">Text before the drawing stays editable above its ground.</p>
<div style="position:absolute; left:960px; top:200px; width:700px; height:700px"><svg aria-label="A breathing blue ring" width="700" height="700" viewBox="0 0 700 700">
<defs><radialGradient id="rg"><stop offset="0.6" stop-color="#4ea0ff" stop-opacity="0"/><stop offset="1" stop-color="#4ea0ff" stop-opacity="0.6"/></radialGradient></defs>
<circle class="breathe" cx="350" cy="350" r="300" fill="url(#rg)"/><circle cx="350" cy="350" r="300" fill="none" stroke="#4285f4" stroke-width="3"/></svg></div>
<img src="assets/loop.webp" alt="" style="position:absolute; left:128px; top:600px; width:480px; height:270px; object-fit:cover">
</section>"""
S['bold'] = """<section id="bold"><h2>Uploaded regular and bold files</h2>
<p style="width:700px; font-weight:700">Bold text is measured in the real bold, so it wraps where Google wraps it.</p>
</section>"""
order = list(S)
for k, v in S.items(): open(D + '/slides/%s.html' % k, 'w').write(v)
open(D + '/deck.css', 'w').write(css)
json.dump({'v': 5, 'lists': 'css', 'format': {'v': 1, 'shared': ['project/deck.css']}, 'title': 'Regression: Magic Circle fixes', 'order': order,
           'faces': {'inter-local': {'family': 'Inter Local', 'src': 'project/fonts/InterLocal-400.woff2'}}}, open(D + '/deck.json', 'w'), indent=1)
print('wrote', len(order), 'slides')
