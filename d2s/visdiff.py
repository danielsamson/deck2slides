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


def _edges(path):
    a = np.asarray(Image.open(path).convert('L'), dtype=np.float32); gy, gx = np.gradient(a); return np.hypot(gx, gy)

def _best_shift(R, G, box, S):
    """Where Google's content sits relative to the browser's inside `box` (x0, y0, x1, y1) -> (dx, dy, score). Normalised cross-correlation
    of edge maps over +-S px. dx, dy are Google minus browser, the sign `convert --corrections` expects."""
    from scipy.signal import fftconvolve
    x0, y0, x1, y1 = box; H, W = R.shape
    gx0, gy0, gx1, gy1 = max(0, x0 - S), max(0, y0 - S), min(W, x1 + S), min(H, y1 + S)
    r = R[y0:y1, x0:x1]; g = G[gy0:gy1, gx0:gx1]
    if r.shape[0] < 20 or r.shape[1] < 20 or r.max() < 1: return 0, 0, 0.0
    num = fftconvolve(g, r[::-1, ::-1], mode='valid')
    den = np.sqrt(fftconvolve(g * g, np.ones_like(r), mode='valid') * (r * r).sum()) + 1e-6
    c = num / den; oy, ox = np.unravel_index(int(c.argmax()), c.shape)
    return int(gx0 + ox - x0), int(gy0 + oy - y0), float(c.max())

def fit_blocks(work, thumbs, min_fs=88, search=60, ref='full', min_score=0.3, min_px=2, prev=None):
    """Closed-loop corrections for big text and outline words, measured on whatever sits behind them (photos included).
    -> {'slide id:item index': {dx, dy}} added to `prev`."""
    out = {k: dict(v) for k, v in (prev or {}).items()}; slides = json.load(open(work + '/slides.json'))
    for s in slides:
        n = s['i'] + 1; rp = '%s/%s_%02d.png' % (work, ref, n); gp = '%s/p%d.png' % (thumbs, n)
        if not (os.path.exists(rp) and os.path.exists(gp)): continue
        R, G = _edges(rp), _edges(gp)
        for idx, it in enumerate(s['items']):
            t = it.get('text')
            if not t or (t.get('fs', 0) < min_fs and not t.get('wa')): continue
            b = t['wa'] if t.get('wa') else dict(x=it['cx'] - it['w'] / 2, y=it['cy'] - it['h'] / 2, w=it['w'], h=it['h'])
            box = (int(max(0, b['x'] - 6)), int(max(0, b['y'] - 6)), int(min(1920, b['x'] + b['w'] + 6)), int(min(1080, b['y'] + b['h'] + 6)))
            dx, dy, sc = _best_shift(R, G, box, search)
            if sc < min_score or max(abs(dx), abs(dy)) < min_px: continue
            e = out.setdefault('%s:%d' % (s['id'], idx), {}); e['dx'] = float(e.get('dx', 0) + dx); e['dy'] = float(e.get('dy', 0) + dy)
    return out
