"""Converts the regression deck and checks each Magic Circle fix in slides.json and the PPTX XML (offline, no Google).
python3 test-decks/regress-magic/check.py [workdir]   -> one PASS/FAIL line per check, exit 1 on any FAIL."""
import json, os, re, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
W = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'test-decks/scratch/regress-magic')
if not os.path.exists(os.path.join(HERE, 'deck.json')): subprocess.run([sys.executable, os.path.join(HERE, 'generate.py')], check=True)
subprocess.run([sys.executable, os.path.join(ROOT, 'd2s.py'), 'convert', HERE, W], check=True, cwd=ROOT)
S = {s['id']: s for s in json.load(open(W + '/slides.json'))}; order = [s for s in json.load(open(HERE + '/deck.json'))['order']]
Z = zipfile.ZipFile(W + '/deck.pptx'); X = {sid: Z.read('ppt/slides/slide%d.xml' % (i + 1)).decode() for i, sid in enumerate(order)}
fails = 0
def check(name, ok, detail=''):
    global fails; fails += 0 if ok else 1; print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(detail)) if detail and not ok else ''))

it = S['imgborder']['items']; pics = [i for i in it if i['type'] == 'img']
check('img: border recorded on the <img>', all(p.get('border') and p['border']['w'] == 4 for p in pics[:2]))
check('img: radius clamped to half the box', all(p['radius'] <= min(p['w'], p['h']) / 2 + 0.01 for p in pics))
check('img: border drawn as a shape behind', X['imgborder'].count('name="Picture border"') == 2, X['imgborder'].count('Picture border'))
check('img: picture masked as an ellipse', X['imgborder'].count('prst="ellipse"') >= 2)
bands = [i for i in S['band']['items'] if i.get('band')]
check('band: one-sided borders on rounded boxes are bands', len(bands) == 3, len(bands))
check('band: bands are custom geometry', X['band'].count('<a:custGeom>') >= 3)
rad = [i for i in S['radial']['items'] if i.get('grad') and i['grad']['kind'] == 'radial']
check('radial: size keyword and position read', rad and rad[0]['grad'].get('size') == 'closest-side' and rad[0]['grad'].get('at') == [50, 55], rad and rad[0]['grad'])
check('radial: stops compressed to the inscribed ellipse', 'pos="70711"' in X['radial'])
check('radial: position becomes the fill centre', 't="55000"' in X['radial'] and 'b="45000"' in X['radial'])
gl = [i for i in S['glass']['items'] if i['type'] == 'img' and 'raster' in str(i.get('src')) and '/g_' in str(i.get('src'))]
check('glass: two panels captured with their backdrop', len(gl) == 2, len(gl))
txt = [i for i in S['glass']['items'] if i['type'] == 'shape' and i.get('text')]
own = [i for i in txt if 'panel itself' in ''.join(r.get('t', '') for r in i['text']['runs'])]
check('glass: text in the panel itself stays a text box', bool(own) and own[0].get('fill') is None and own[0].get('shadow') is None)
check('glass: text in a child stays a text box', any('child of the panel' in ''.join(r.get('t', '') for r in i['text']['runs']) for i in txt))
hy = [i for i in S['hyphen']['items'] if i.get('text') and 'close-' in ''.join(r.get('t', '') for r in i['text']['runs'])]
check('hyphen: break after "close-" kept', bool(hy) and any('close-\x0bup' in r.get('t', '') for r in hy[0]['text']['runs']), hy and hy[0]['text']['runs'])
lp = S['loop']['items']; svg = [i for i in lp if i['type'] == 'svg']; webp = [i for i in lp if i['type'] == 'img' and str(i.get('src')).endswith('.webp')]
check('loop: SVG loop recorded', bool(svg) and svg[0].get('loop', {}).get('frames', 0) > 1)
check('loop: SVG loop has a GIF and an HQ GIF', bool(svg) and os.path.exists(svg[0].get('gif', '')) and os.path.exists(svg[0].get('gif_hq', '')))
gi = [k for k, i in enumerate(lp) if i.get('src') == (svg[0].get('ground') if svg else None)]
check('loop: ground picture sits under the GIF', bool(gi) and gi[0] < lp.index(svg[0]))
tb = [k for k, i in enumerate(lp) if i.get('text') and 'stays editable' in ''.join(r.get('t', '') for r in i['text']['runs'])]
check('loop: earlier text stays above the ground', bool(tb) and bool(gi) and tb[0] > gi[0])
check('loop: animated WebP becomes a GIF', bool(webp) and str(webp[0].get('gif', '')).endswith('.gif'))
ft = json.load(open(W + '/font_table.json')); prev = open(W + '/preview.html').read()
check('font: uploaded face read from its file', 'font file' in ft.get('Inter Local', {}).get('source', ''), ft.get('Inter Local'))
check('font: bold sibling file registered', 'InterLocal-700.woff2' in prev and 'font-weight:700 1000' in prev)
print('%d check(s) failed' % fails if fails else 'all checks passed'); sys.exit(1 if fails else 0)
