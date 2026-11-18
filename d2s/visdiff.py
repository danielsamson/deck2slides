"""Visual comparison sheets: Claude render | Google render | overlay, one PNG per slide.

The overlay puts the browser render in the red channel and the Google render in green and blue. Where the two agree the picture is
neutral grey. Red means the Claude render is BRIGHTER than Google at that pixel, cyan means Google is brighter. For dark text on a light
ground that makes Claude-only ink cyan and Google-only ink red; for light text on a dark ground it is the other way round. Shifted text
shows as a red fringe on one edge and a cyan fringe on the opposite edge: read the direction off which fringe is on which side."""
import os, json
import numpy as np
from PIL import Image, ImageDraw

def _load(p, w, h): return Image.open(p).convert('RGB').resize((w, h), Image.LANCZOS)

def overlay(a, g):
    A = np.asarray(a.convert('L'), dtype=np.float32); G = np.asarray(g.convert('L'), dtype=np.float32)
    out = np.stack([A, G, G], 2); return Image.fromarray(out.clip(0, 255).astype('uint8'))

def sheet(ref_path, goog_path, out, label, w=640, h=360):
    a, g = _load(ref_path, w, h), _load(goog_path, w, h); o = overlay(a, g)
    S = Image.new('RGB', (w * 3 + 40, h + 44), 'white'); d = ImageDraw.Draw(S)
    for i, (im, t) in enumerate(((a, 'Claude render'), (g, 'Google Slides'), (o, 'overlay: red = Claude brighter, cyan = Google brighter'))):
        S.paste(im, (i * (w + 20), 36)); d.text((i * (w + 20) + 4, 12), t, fill='black')
    d.text((w * 3 + 40 - 260, 2), label, fill='black'); S.save(out); return out

def run(work, thumbs, outdir, slides=None, worst=0, ref='full'):
    rows = json.load(open('%s/report_%s.json' % (work, os.path.basename(thumbs.rstrip('/')))))
    if worst: rows = sorted(rows, key=lambda r: -r['pct'])[:worst]
    elif slides: rows = [r for r in rows if r['id'] in slides or str(r['slide']) in slides]
    os.makedirs(outdir, exist_ok=True); made = []
    for r in rows:
        n = r['slide']; rp = '%s/%s_%02d.png' % (work, ref, n); gp = '%s/p%d.png' % (thumbs, n)
        if os.path.exists(rp) and os.path.exists(gp):
            made.append(sheet(rp, gp, '%s/v%03d_%s.png' % (outdir, n, r['id']), '%d %s  diff %.1f%%  max text offset %dpx' % (n, r['id'], r['pct'], r['max_off'])))
    return made
