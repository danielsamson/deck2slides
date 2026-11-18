"""Visual comparison of Google's slide images with the browser render: whole-slide pixel difference and per-text-block ink offsets."""
import json, os
import numpy as np
from PIL import Image, ImageFilter, ImageDraw
from scipy import ndimage
from . import config as C

W, H = 1600, 900
def load(path, size=(1920, 1080)): return np.asarray(Image.open(path).convert('RGB').resize(size, Image.LANCZOS)).astype(int)

def slide_diff(ref_png, google_png, ignore_boxes=(), out_png=None):
    """-> dict(pct, regions[(x0,y0,x1,y1,area,max)] in 1920 scale). Regions inside ignore_boxes (picture/clip areas) are skipped."""
    a = Image.open(ref_png).convert('RGB').resize((W, H), Image.LANCZOS); g = Image.open(google_png).convert('RGB').resize((W, H), Image.LANCZOS)
    A = np.asarray(a.filter(ImageFilter.GaussianBlur(C.DIFF_BLUR))).astype(int); G = np.asarray(g.filter(ImageFilter.GaussianBlur(C.DIFF_BLUR))).astype(int)
    diff = np.abs(A - G).max(2); mask = diff > C.DIFF_THRESHOLD; ign = np.zeros((H, W), bool); k = W / 1920
    for x0, y0, x1, y1 in ignore_boxes: ign[max(0, int(y0 * k)):int(y1 * k) + 1, max(0, int(x0 * k)):int(x1 * k) + 1] = True
    m = mask & ~ign; lab, _ = ndimage.label(ndimage.binary_dilation(m, iterations=6)); boxes = []
    for sl in ndimage.find_objects(lab):
        y, x = sl; area = int(m[sl].sum())
        if area >= C.DIFF_MIN_REGION_PX: boxes.append((int(x.start / k), int(y.start / k), int(x.stop / k), int(y.stop / k), area, int(diff[sl].max())))
    boxes.sort(key=lambda b: -b[4])
    if out_png:
        hm = np.asarray(g).copy(); hm[m] = [255, 0, 255]; hm = Image.fromarray(hm); dr = ImageDraw.Draw(hm)
        for b in boxes: dr.rectangle([v * k for v in (b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3)], outline=(255, 0, 0), width=3)
        sheet = Image.new('RGB', (W * 3 + 16, H), 'black'); sheet.paste(a, (0, 0)); sheet.paste(g, (W + 8, 0)); sheet.paste(hm, (W * 2 + 16, 0)); sheet.resize((1500, int(H * 1500 / (W * 3 + 16)))).save(out_png)
    return dict(pct=100.0 * m.mean(), regions=boxes)

def ink_bbox(I, box, color, tol=90):
    x0, y0, x1, y1 = box; reg = np.abs(I[y0:y1, x0:x1] - color).sum(2) < tol
    if reg.sum() < 12: return None
    ys = np.where(reg.any(1))[0]; xs = np.where(reg.any(0))[0]; return x0 + xs[0], y0 + ys[0], x0 + xs[-1], y0 + ys[-1]

def text_offsets(slide, ref_png, google_png, margin=14, ignore=()):
    """For each unrotated, opaque text block: how far the ink moved (Google minus browser): (dL, dT, dR, dB) in 1920 px."""
    A, G = load(ref_png), load(google_png); rows = []
    for x0, y0, x1, y1 in ignore:      # picture areas (embedded or not) are blanked in both images so they cannot be mistaken for ink
        for I in (A, G): I[max(0, int(y0)):int(y1) + 1, max(0, int(x0)):int(x1) + 1] = 255
    for ix, it in enumerate(slide['items']):
        t = it.get('text')
        if not t or abs(it['rot']) > 0.01: continue
        r = next((r for r in t['runs'] if not r.get('br')), None)
        if not r or r['color']['a'] < 0.9: continue
        c = np.array([r['color']['r'], r['color']['g'], r['color']['b']])
        box = (int(max(0, it['cx'] - it['w'] / 2 - margin)), int(max(0, it['cy'] - it['h'] / 2 - margin)), int(min(1920, it['cx'] + it['w'] / 2 + margin)), int(min(1080, it['cy'] + it['h'] / 2 + margin)))
        a, g = ink_bbox(A, box, c), ink_bbox(G, box, c)
        rows.append(dict(idx=ix, n=len(''.join(x.get('t', '|') for x in t['runs'])), text=''.join(x.get('t', '|') for x in t['runs'])[:26], fam=t['fam'], fs=t['fs'], lh=t['lh'], lines=t['lines'], d=None if not a or not g else (g[0] - a[0], g[1] - a[1], g[2] - a[2], g[3] - a[3])))
    return rows

def picture_boxes(slide, pad=0.0):
    out = []
    for it in slide['items']:
        if it['type'] in ('img', 'clip', 'svg'):
            r = max(it['w'], it['h']) / 2 * 1.08 if abs(it['rot']) > 0.01 else None
            out.append((it['cx'] - r, it['cy'] - r, it['cx'] + r, it['cy'] + r) if r else (it['cx'] - it['w'] / 2, it['cy'] - it['h'] / 2, it['cx'] + it['w'] / 2, it['cy'] + it['h'] / 2))
    return out

def report(workdir, thumbdir, ref='noimg', out_dir=None, only=None, ignore_pictures=False):
    """Per-slide table: pixel diff % + regions, text offset stats. ref: 'noimg' (pictures hidden) or 'full'."""
    data = json.load(open(workdir + '/slides.json')); res = []
    for s in data:
        n = s['i'] + 1; tp = '%s/p%d.png' % (thumbdir, n)
        if not os.path.exists(tp) or (only and s['id'] not in only): continue
        rp = '%s/%s_%02d.png' % (workdir, ref, n)
        d = slide_diff(rp, tp, picture_boxes(s) if ignore_pictures else (), out_png=(out_dir and '%s/d%02d_%s.png' % (out_dir, n, s['id'])))
        offs = [r for r in text_offsets(s, rp, tp, ignore=picture_boxes(s) if ignore_pictures else ()) if r['d']]
        mx = [max(abs(v) for v in r['d']) for r in offs]
        res.append(dict(slide=n, id=s['id'], pct=round(d['pct'], 3), regions=len(d['regions']), blocks=len(offs), max_off=max(mx) if mx else 0,
                        mean_off=round(float(np.mean(mx)), 2) if mx else 0, bad=sum(1 for v in mx if v > 4), top=[r for r in d['regions'][:3]]))
    return res


def fit_text(workdir, thumbdir, prev=None, ref='noimg', min_px=2):
    """Closed-loop correction. Measures every clean text block of an export against the browser render and returns
    {'slide id:item index': {dy, dx, dw}} (px, Google minus browser), added to `prev` so a second pass refines the first.
    A block is 'clean' when its ink box is not polluted by a neighbour: top and bottom offsets agree within 2 px."""
    data = json.load(open(workdir + '/slides.json')); out = {k: dict(v) for k, v in (prev or {}).items()}; n = 0
    for s in data:
        k_ = s['i'] + 1; tp = '%s/p%d.png' % (thumbdir, k_); rp = '%s/%s_%02d.png' % (workdir, ref, k_)
        if not os.path.exists(tp): continue
        for r in text_offsets(s, rp, tp, ignore=picture_boxes(s)):
            d = r['d']
            if not d or abs(d[1] - d[3]) > 2 or max(abs(v) for v in d) < min_px: continue
            e = out.setdefault('%s:%d' % (s['id'], r['idx']), {}); n += 1
            e['dy'] = round(float(e.get('dy', 0) + (d[1] + d[3]) / 2), 1)
            if r['lines'] == 1:
                e['dx'] = round(float(e.get('dx', 0) + d[0]), 1)
                dw = d[2] - d[0]
                gap = abs(dw) / max(1, r['n'] - 1)
                if abs(dw) >= 3 and (gap <= 0.07 * r['fs'] or (abs(d[0]) <= 3 and gap <= 0.25 * r['fs'])): e['dw'] = round(float(e.get('dw', 0) + (d[2] - d[0])), 1)
    print('corrected blocks:', n); return out
