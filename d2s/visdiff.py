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


def _ink_bbox(path, region, rgb, tol=90):
    """Bounding box (x0, y0, x1, y1) of the pixels near colour `rgb` inside `region` (x0, y0, x1, y1), or None."""
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB')).astype(int); x0, y0, x1, y1 = region; sub = a[y0:y1, x0:x1]
    m = (np.abs(sub - np.array(rgb)).sum(axis=2) < tol)
    ys, xs = np.nonzero(m)
    if len(xs) < 50: return None
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()), y0 + int(ys.max())

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
            st = next((r.get('stroke') for r in t['runs'] if r.get('stroke') and r['color']['a'] <= 0.01), None) if t.get('wa') else None
            if st and max(st['c']['r'], st['c']['g'], st['c']['b']) - min(st['c']['r'], st['c']['g'], st['c']['b']) > 100:        # outline word: its ink is one known colour, so measure the ink extent directly (correlating halves of a thin outline locks onto the wrong letter)
                c = st['c']; reg = (max(0, box[0] - 40), max(0, box[1] - 40), min(1920, box[2] + 40), min(1080, box[3] + 40))
                vb = _ink_bbox(rp, reg, (c['r'], c['g'], c['b'])); gb = _ink_bbox(gp, reg, (c['r'], c['g'], c['b']))
                if vb and gb:
                    dh = (gb[3] - gb[1]) - (vb[3] - vb[1])                  # outline words keep the calibration box shape, so the height alone sets the size
                    dx, dy = ((gb[0] + gb[2]) - (vb[0] + vb[2])) / 2.0, gb[1] - vb[1]
                    if max(abs(dx), abs(dy), abs(dh)) < min_px: continue
                    e = out.setdefault('%s:%d' % (s['id'], idx), {}); e['dx'] = float(e.get('dx', 0) + dx); e['dy'] = float(e.get('dy', 0) + dy)
                    if abs(dh) >= min_px: e['dh'] = float(e.get('dh', 0) + dh)
                    continue
            dx, dy, sc = _best_shift(R, G, box, search)
            dw = 0
            cols = np.nonzero(R[box[1]:box[3], box[0]:box[2]].sum(axis=0) > 0)[0]       # ink extent: split it to see drift along the word
            if len(cols) > 120 and not t.get('wa') and t.get('lines', 1) == 1:
                x0, x1 = box[0] + int(cols[0]), box[0] + int(cols[-1]); mid = (x0 + x1) // 2
                lx, ly, ls_ = _best_shift(R, G, (max(0, x0 - 4), box[1], mid, box[3]), search)
                rx, ry, rs_ = _best_shift(R, G, (mid, box[1], min(1920, x1 + 4), box[3]), search)
                if min(ls_, rs_) >= min_score:
                    dw = rx - lx; al = (t.get('align') or 'left') if not t.get('wa') else 'left'
                    dx = lx if al == 'left' else rx if al == 'right' else (lx + rx) / 2; dy = (ly + ry) / 2; sc = max(sc, min(ls_, rs_))
            if sc < min_score or max(abs(dx), abs(dy), abs(dw)) < min_px: continue
            e = out.setdefault('%s:%d' % (s['id'], idx), {}); e['dx'] = float(e.get('dx', 0) + dx); e['dy'] = float(e.get('dy', 0) + dy)
            if abs(dw) >= min_px: e['dw'] = float(e.get('dw', 0) + dw)
    return out
