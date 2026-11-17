"""Packs the deck's pictures into small PowerPoint bundles (one picture per slide, named by its asset key) so they can go
through the size-limited Drive upload. Slides then reads each picture's temporary URL from the bundle and copies it in."""
import json, os, hashlib
from PIL import Image
from pptx import Presentation
from pptx.util import Emu
from . import config as C

def prepare(assets, outdir, limit):
    items = []
    for key, a in sorted(assets.items()):
        f = a['file']
        if f.lower().endswith('.gif'):          # animated clips go as they are, when they fit; otherwise by link (README)
            items.append((key, f, os.path.getsize(f), os.path.getsize(f) + 30000 > limit)); continue
        im = Image.open(f); want = int(round(a['maxw'] * C.MAX_PIC_WIDTH_FACTOR))
        if im.width > want * 1.15 or os.path.getsize(f) > limit:
            im = im.convert('RGBA') if im.mode in ('RGBA', 'LA', 'P') else im.convert('RGB')
            if im.width > want: im = im.resize((want, max(1, int(round(im.height * want / im.width)))), Image.LANCZOS)
            alpha = im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] < 255
            out = os.path.join(outdir, key + ('.png' if alpha else '.jpg'))
            if alpha:
                im.save(out, optimize=True)
                if os.path.getsize(out) > limit: im.quantize(256, method=Image.FASTOCTREE, dither=Image.FLOYDSTEINBERG).save(out, optimize=True)
            else:
                q = 92
                while True:
                    im.convert('RGB').save(out, quality=q, subsampling=0, optimize=True)
                    if os.path.getsize(out) <= limit or q <= 70: break
                    q -= 4
            f = out
        items.append((key, f, os.path.getsize(f), False))
    return items

def pack(workdir, limit_kb=C.BUNDLE_LIMIT_KB):
    """Writes <workdir>/pack/pack_NN.pptx, packs.json and list.txt (sha256 file references for the Drive connector).
    Returns (packs, too_big) where too_big lists assets that cannot travel through the connector (GIFs over the limit)."""
    LIM = limit_kb * 1024; m = json.load(open(workdir + '/manifest.json')); out = os.path.join(workdir, 'pack'); os.makedirs(out, exist_ok=True)
    items = prepare(m['assets'], out, LIM); too_big = [i[0] for i in items if i[3]]; items = [i for i in items if not i[3]]
    items.sort(key=lambda x: -x[2]); bins = []
    for it in items:
        for b in bins:
            if sum(x[2] for x in b) + it[2] + 3000 * (len(b) + 1) <= LIM: b.append(it); break
        else: bins.append([it])
    packs = []
    for i, b in enumerate(bins):
        prs = Presentation(); prs.slide_width = Emu(C.SLIDE_EMU[0]); prs.slide_height = Emu(C.SLIDE_EMU[1])
        for key, f, sz, _ in b:
            s = prs.slides.add_slide(prs.slide_layouts[6]); im = Image.open(f); w = 3000000; h = int(w * im.height / im.width)
            if h > 5000000: h = 5000000; w = int(h * im.width / im.height)
            pic = s.shapes.add_picture(f, 0, 0, w, h); pic.name = key; pic._element.nvPicPr.cNvPr.set('descr', key)
        p = '%s/pack_%02d.pptx' % (out, i + 1); prs.save(p); packs.append(dict(file=os.path.abspath(p), keys=[x[0] for x in b], kb=os.path.getsize(p) // 1024))
    json.dump(dict(packs=packs, too_big=too_big), open(out + '/packs.json', 'w'), indent=1)
    open(out + '/list.txt', 'w').write(''.join('%02d  sha256:%s:%s  keys=%s\n' % (i + 1, hashlib.sha256(open(o['file'], 'rb').read()).hexdigest(), o['file'], ','.join(o['keys'])) for i, o in enumerate(packs)))
    return packs, too_big
