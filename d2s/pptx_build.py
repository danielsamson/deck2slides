"""Builds an editable PowerPoint from slides.json (written by js/extract.cjs). Every piece is native: text is text,
cards/pills/circles are shapes, pictures are separate pictures, clips are animated GIFs. The file is made to be
converted by Google Slides, so type is written the way Google reads it; every number is in config.py."""
import json, math, sys, os
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.util import Emu
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.oxml.ns import qn

from . import config as C
from .units import emu, hexc, rot_vec
from .fonts import FontDB
from . import geomclip
PT = C.PT_PER_PX
FDB = FontDB({})          # replaced in build()
CORR = {}; CUR = [None]; CROPDIR = ['crops']    # per-block corrections measured on a previous export (see imgdiff.fit_text); CUR = 'slide id:item index'

A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
def E(tag, parent=None, **attrs):
    el = etree.SubElement(parent, qn(tag)) if parent is not None else etree.Element(qn(tag))
    for k, v in attrs.items(): el.set(k, str(v))
    return el
def color(parent, c, op=1.0):
    sf = E('a:solidFill', parent); s = E('a:srgbClr', sf, val=hexc(c)); a = c.get('a', 1) * op
    if a < 0.999: E('a:alpha', s, val=int(round(a * 100000)))
    return sf
def gradfill(parent, g, op=1.0):
    gf = E('a:gradFill', parent, rotWithShape='1'); gl = E('a:gsLst', gf)
    for st in g['stops']:
        gs = E('a:gs', gl, pos=int(round(max(0, min(100, st['pos'])) * 1000))); sc = E('a:srgbClr', gs, val=hexc(st['c']))
        a = st['c'].get('a', 1) * op
        if a < 0.999: E('a:alpha', sc, val=int(round(a * 100000)))
    if g['kind'] == 'linear': E('a:lin', gf, ang=int(round(((g['angle'] - 90) % 360) * 60000)), scaled='0')
    else: pth = E('a:path', gf, path='circle'); E('a:fillToRect', pth, l=50000, t=50000, r=50000, b=50000)
    return gf

def shadow(spPr, sh, op=1.0):
    if not sh or not sh['c'] or sh['c']['a'] * op <= 0: return
    ef = E('a:effectLst', spPr)
    o = E('a:outerShdw', ef, blurRad=emu(sh['blur']), dist=emu(math.hypot(sh['x'], sh['y'])), dir=int(round((math.degrees(math.atan2(sh['y'], sh['x'])) % 360) * 60000)), algn='ctr', rotWithShape='0')
    s = E('a:srgbClr', o, val=hexc(sh['c'])); E('a:alpha', s, val=int(round(sh['c']['a'] * op * 100000)))
def custgeom(spPr, subpaths):
    S = 100000
    for g in spPr.findall(qn('a:prstGeom')): spPr.remove(g)
    cg = E('a:custGeom'); E('a:avLst', cg); E('a:gdLst', cg); E('a:ahLst', cg); E('a:cxnLst', cg); E('a:rect', cg, l='0', t='0', r='r', b='b'); pl = E('a:pathLst', cg)
    pt = lambda parent, x, y: E('a:pt', parent, x=int(round(x * S)), y=int(round(y * S)))
    for sp in subpaths:
        path = E('a:path', pl, w=S, h=S)
        for c in sp:
            if c[0] == 'M': pt(E('a:moveTo', path), c[1], c[2])
            elif c[0] == 'L': pt(E('a:lnTo', path), c[1], c[2])
            elif c[0] == 'C': cb = E('a:cubicBezTo', path); pt(cb, c[1], c[2]); pt(cb, c[3], c[4]); pt(cb, c[5], c[6])
            else: E('a:close', path)
    spPr.find(qn('a:xfrm')).addnext(cg); return cg

def geom(spPr, w, h, radius, ell=False, cust=None):
    if cust: return custgeom(spPr, cust)
    for g in spPr.findall(qn('a:prstGeom')): spPr.remove(g)
    m = min(w, h)
    if radius <= 0.5: g = E('a:prstGeom', None, prst='rect'); E('a:avLst', g)
    elif ell or (radius >= m / 2 - 0.5 and abs(w - h) < 1): g = E('a:prstGeom', None, prst='ellipse'); E('a:avLst', g)
    else:
        g = E('a:prstGeom', None, prst='roundRect'); av = E('a:avLst', g)
        E('a:gd', av, name='adj', fmla='val %d' % int(round(min(C.MAX_RADIUS_FRACTION, radius / m) * 100000)))
    xf = spPr.find(qn('a:xfrm')); xf.addnext(g); return g
def strip(sp):
    for st in sp._element.findall(qn('p:style')): sp._element.remove(st)
    spPr = sp._element.spPr
    for ch in list(spPr):
        if ch.tag not in (qn('a:xfrm'), qn('a:prstGeom')): spPr.remove(ch)
    return spPr

def text_body(sp, it, ins, forced):
    t = it['text']; txBody = sp._element.find(qn('p:txBody'))
    if txBody is None: txBody = E('p:txBody', sp._element)
    for ch in list(txBody): txBody.remove(ch)
    nowrap = C.WRAP_NONE_TIGHT and (t.get('nowrap') or t.get('over', 0) > 0.5 or (t.get('tight') and (t['lines'] == 1 or forced)))
    bp = E('a:bodyPr', txBody, wrap='none' if nowrap else 'square', lIns=emu(ins[0]), tIns=emu(ins[1]), rIns=emu(ins[2]), bIns=emu(ins[3]), anchor='ctr' if t['anchor'] == 'middle' else 't', rtlCol='0')
    if any(r.get('stroke') and r['color']['a'] <= 0.01 for r in t['runs'] if not r.get('br')):
        wp = E('a:prstTxWarp', bp, prst='textPlain'); E('a:avLst', wp)      # outline text as WordArt: Slides keeps it editable, with its outline
    E('a:lstStyle', txBody); p = E('a:p', txBody)
    pPr = E('a:pPr', p, algn={'left': 'l', 'center': 'ctr', 'right': 'r'}[t['align']])
    ls = E('a:lnSpc', pPr); E('a:spcPct', ls, val=int(round(FDB.spc_pct(t['fam'], t['lh']) * 100000)))
    sb = E('a:spcBef', pPr); E('a:spcPts', sb, val=0); sa = E('a:spcAft', pPr); E('a:spcPts', sa, val=0)
    runs = [dict(r) for r in t['runs']]
    def rpr(parent, r, tag='a:rPr'):
        at = dict(lang='en-GB', sz=int(round(r['fs'] * PT * 100)), b='1' if FontDB.bold(r['w']) else '0')
        if r.get('it'): at['i'] = '1'
        if r.get('ul'): at['u'] = 'sng'
        lsv = r.get('ls') or 0; cl = FDB.cell(r['fam'], r['fs'], t['lh'], r['w'], lsv)
        if cl: lsv -= cl[6]            # measured advance drift per character (Google minus browser)
        lsv -= t.get('_spc', 0)        # and this block's own measured width residual
        if abs(lsv) > 0.04: at['spc'] = int(round(lsv * PT * 100))
        e = E(tag, parent, **at)
        if r.get('stroke'):               # outline text: a:ln first, then no fill when the fill is transparent
            ln = E('a:ln', e, w=emu(r['stroke']['w'])); color(ln, r['stroke']['c'], it.get('op', 1))
            if r['color']['a'] <= 0.01: E('a:noFill', e)
            else: color(e, r['color'], it.get('op', 1))
        else: color(e, r['color'], it.get('op', 1))
        face = FontDB.face(r['fam'], r['w'])
        for k in (('a:latin', 'a:ea', 'a:cs') if C.EMIT_EA_CS else ('a:latin',)): E(k, e, typeface=face)
        return e
    last = None; out = []
    for r in runs:                       # flatten to (text | break) pieces
        if r.get('br'): out.append(('br', last)); continue
        parts = r['t'].split('\x0b'); last = r
        for i, part in enumerate(parts):
            if i: out.append(('br', r) if forced else ('t', r, ' '))
            if part: out.append(('t', r, part))
    # tidy spaces around breaks and at the ends
    clean = []
    for o in out:
        if o[0] == 't':
            s = o[2]
            if not clean or clean[-1][0] == 'br': s = s.lstrip(' ')
            if clean and clean[-1][0] == 't' and clean[-1][2].endswith(' ') and s.startswith(' '): s = s[1:]
            if s: clean.append(('t', o[1], s))
        else:
            if clean and clean[-1][0] == 't': clean[-1] = ('t', clean[-1][1], clean[-1][2].rstrip(' '))
            clean.append(o)
    while clean and clean[-1][0] == 't' and not clean[-1][2].strip(): clean.pop()
    if clean and clean[-1][0] == 't': clean[-1] = ('t', clean[-1][1], clean[-1][2].rstrip(' '))
    first = next((o[1] for o in clean if o[1]), runs[0])
    for o in clean:
        if o[0] == 'br': b = E('a:br', p); rpr(b, o[1] or first)
        else: r = E('a:r', p); rpr(r, o[1]); tt = E('a:t', r); tt.text = o[2]
    rpr(p, first, 'a:endParaRPr')
    return ''.join(o[2] for o in clean if o[0] == 't')

try: WORDART_CAL = json.load(open(os.path.join(os.path.dirname(__file__), 'wordart_cal.json')))
except Exception: WORDART_CAL = {}

def add_shape(slide, it):
    t = it.get('text'); op = it.get('op', 1)
    if t and all(r.get('br') or (r['color']['a'] * op <= 0 and not r.get('stroke')) for r in t['runs']): t = None
    _pad, _bw = it.get('pad') or {}, it.get('bw') or {}
    _inner_h = it['h'] - sum(_pad.get(k, 0) + _bw.get(k, 0) for k in ('t', 'b'))
    if t and t.get('lines') == 1 and t.get('lh') and t['lh'] > C.DY_EXTRAP_MAX_LH and abs(_inner_h - t['lh'] * t['fs']) < 3:
        # 'line-height equals the box height' centring idiom: centre one natural-height line instead (does not depend on calibration at large line heights)
        t = dict(t, lh=None, anchor='middle'); it = dict(it, text=t)
    fill, stroke, grd = it.get('fill'), it.get('stroke'), it.get('grad')
    if not (fill or stroke or t or grd): return None
    cust = geomclip.cust_for(it)
    if cust == 'empty': return None
    cx, cy, w, h, rot = it['cx'], it['cy'], it['w'], it['h'], it['rot']
    pad, bw = it.get('pad') or dict(l=0, r=0, t=0, b=0), it.get('bw') or dict(l=0, r=0, t=0, b=0)
    ins = [pad['l'] + bw['l'], pad['t'] + bw['t'], pad['r'] + bw['r'], pad['b'] + bw['b']]
    radius = it.get('radius', 0)
    if stroke: s = stroke['w']; w -= s; h -= s; radius = max(0, radius - s / 2); ins = [max(0, v - s / 2) for v in ins]
    forced = False; wa_geom = None
    if t and t.get('wa') and any(r.get('stroke') and r['color']['a'] <= 0.01 for r in t['runs'] if not r.get('br')):
        wa = t['wa']; word = ''.join(r.get('t', '') for r in t['runs'] if not r.get('br')); cal = WORDART_CAL.get(word)
        if not cal: print('WARNING wordart not calibrated: %r (run d2s/wordart_cal.py gen/fit); using the average ratios' % word); cal = dict(rx=1.16, ry=1.11, ox=-0.002, oy=-0.005)
        bw, bh = wa['w'] / cal['rx'], wa['h'] / cal['ry']; wa_geom = (wa['x'] - cal['ox'] * bw + bw / 2, wa['y'] - cal['oy'] * bh + bh / 2, bw, bh); rot = 0
        _wc = CORR.get(CUR[0])
        if _wc: wa_geom = (wa_geom[0] - _wc.get('dx', 0), wa_geom[1] - _wc.get('dy', 0), wa_geom[2] - _wc.get('dw', 0) / cal['rx'], wa_geom[3] - _wc.get('dh', 0) / cal['ry'])     # WordArt: Slides sizes the word by its box, ink = box x (rx, ry), measured per word
    if t:
        forced = bool(t.get('risky') or (t.get('tight') and t.get('wraps')) or any(r.get('ls') for r in t['runs'] if not r.get('br')))
        if it.get('ell'): kx, ky = 0.1464 * w, 0.1464 * h; ins = [max(0, ins[0] - kx), max(0, ins[1] - ky), max(0, ins[2] - kx), max(0, ins[3] - ky)]
        else: k = C.ROUND_TEXT_INSET * min(radius, min(w, h) / 2); ins = [max(0, v - k) for v in ins]
        r0 = next((r for r in t['runs'] if not r.get('br')), None)
        shift = FDB.dy(t['fam'], t['lh'], t['fs'], r0['w'] if r0 else None, (r0 or {}).get('ls') or 0)
        cell = FDB.cell(t['fam'], t['fs'], t['lh'], r0['w'] if r0 else None, (r0 or {}).get('ls') or 0) if r0 else None
        hx = -cell[5] if cell and t['align'] == 'left' else 0         # measured left-edge drift of tracked text (Google minus browser)
        cr = CORR.get(CUR[0])
        if cr:                                                          # residual of this very block, measured on the last export
            shift -= cr.get('dy', 0)
            if t['align'] == 'left': hx -= cr.get('dx', 0)
            t = dict(t, _spc=cr.get('dw', 0) / max(1, sum(len(r.get('t', '')) for r in t['runs'] if not r.get('br')) - 1)); it = dict(it, text=t)
        ls_min = min([r.get('ls', 0) for r in t['runs'] if not r.get('br')] + [0])
        single = t['lines'] == 1
        extra = 0
        if single or forced or t.get('tight'): extra = max(C.WIDEN_MIN_PX, C.WIDEN_FRACTION * (w - ins[0] - ins[2])) + (-ls_min * t['maxChars'] if ls_min < 0 else 0)
        elif not fill and not stroke and not grd: extra = C.WIDEN_MULTILINE_PX
        if t.get('over', 0) > 0.5: extra += t['over']          # text sticks out of its box in the browser (nowrap, long word): Google would wrap it
        if fill or stroke or grd:      # keep the shape; make room inside it
            if t['anchor'] == 'middle':
                if shift > 0: ins[1] += 2 * shift
                else: ins[3] += -2 * shift
            else: ins[1] = max(0, ins[1] + shift)
            if hx: ins[0] = max(0, ins[0] + hx)
            if extra:       # use the padding as slack. (Negative insets for the rest were tested: Google ignores them.)
                if t['align'] == 'center': ins[0] = ins[2] = 0
                elif t['align'] == 'left': ins[2] = 0
                else: ins[0] = 0
        else:                   # free text: move and widen the box itself
            ox = {'left': extra / 2, 'center': 0, 'right': -extra / 2}[t['align']]
            dx, dyy = rot_vec(ox + hx, shift, rot); cx += dx; cy += dyy; w += extra
    if wa_geom: cx, cy, w, h = wa_geom; ins = [0, 0, 0, 0]
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(cx - w / 2), emu(cy - h / 2), max(1, emu(w)), max(1, emu(h)))
    if abs(rot) > 0.01: sp.rotation = rot
    spPr = strip(sp); geom(spPr, w, h, radius, it.get('ell', False), cust)
    if grd: gradfill(spPr, grd, op)
    elif fill: color(spPr, fill, op)
    else: E('a:noFill', spPr)
    ln = E('a:ln', spPr)
    if stroke:
        ln.set('w', str(emu(stroke['w']))); color(ln, stroke['c'], op)
        if stroke.get('cmpd'): ln.set('cmpd', stroke['cmpd'])
        if stroke.get('dash'): E('a:prstDash', ln, val='dash' if stroke['dash'] == 'dash' else 'sysDot')
    else: E('a:noFill', ln)
    if fill or grd: shadow(spPr, it.get('shadow'), op)
    txt = ''
    if t:
        txt = text_body(sp, dict(it, text=t), ins, forced)
        if t.get('link'): sp.click_action.hyperlink.address = t['link']
    else:
        tb = sp._element.find(qn('p:txBody'))
        if tb is not None:
            for ch in list(tb): tb.remove(ch)
            E('a:bodyPr', tb); E('a:lstStyle', tb); E('a:p', tb)
    sp.name = (txt[:40] or ('Card' if fill else 'Outline')) if not it.get('bg') else 'Background'
    return sp

ASSETS = {}   # key -> dict(file, mime); written to manifest.json. Pictures are added by Slides itself from a URL
              # (the upload channel only takes small files), so the PowerPoint carries a tagged placeholder per picture.
def asset_for(it, path, cw, ch, outdir):
    import hashlib, os
    fit = it.get('fit', 'fill'); radius = it.get('radius', 0); op = it.get('op', 1)
    with Image.open(path) as im: nw, nh = im.size
    crop = fit == 'cover' and (abs(1 - (cw / ch) / (nw / nh)) > 0.005)
    if radius <= 0.5 and not crop and op >= 0.999:
        key = 'im' + hashlib.sha1(open(path, 'rb').read()).hexdigest()[:10]
        ASSETS.setdefault(key, dict(file=path, mime='image/gif' if path.lower().endswith('.gif') else 'image/jpeg' if path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'))
        return key, nw, nh
    key = 'im' + hashlib.sha1(('%s|%s|%.4f|%.4f|%.3f' % (path, fit, cw / ch, radius / min(cw, ch), op)).encode() + open(path, 'rb').read()).hexdigest()[:10]
    out = os.path.join(outdir, 'assets', key + '.png')
    if key not in ASSETS:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im = Image.open(path).convert('RGBA')
        if fit == 'cover':
            s = max(cw / nw, ch / nh); vw, vh = cw / s, ch / s; l, t = (nw - vw) / 2, (nh - vh) / 2
            im = im.crop((int(round(l)), int(round(t)), int(round(l + vw)), int(round(t + vh))))
        if im.width > 2400: im = im.resize((2400, int(round(im.height * 2400 / im.width))), Image.LANCZOS)
        if radius > 0.5:
            from PIL import ImageDraw, ImageChops
            k = 4; m = Image.new('L', (im.width * k, im.height * k), 0); r = radius / cw * im.width * k
            ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), r, fill=255)
            im.putalpha(ImageChops.multiply(im.getchannel('A'), m.resize(im.size, Image.LANCZOS)))
        if op < 0.999: im.putalpha(im.getchannel('A').point(lambda v: int(v * op)))
        im.save(out, optimize=True); ASSETS[key] = dict(file=out, mime='image/png')
    with Image.open(out) as im2: return key, im2.width, im2.height

def add_picture_shape(slide, it, path, outdir):
    cx, cy, rot = it['cx'], it['cy'], it['rot']
    pad, bw = it.get('pad') or dict(l=0, r=0, t=0, b=0), it.get('bw') or dict(l=0, r=0, t=0, b=0)
    cw, ch = it['w'] - pad['l'] - pad['r'] - bw['l'] - bw['r'], it['h'] - pad['t'] - pad['b'] - bw['t'] - bw['b']
    if cw <= 0 or ch <= 0: return None
    ox, oy = (pad['l'] + bw['l'] - pad['r'] - bw['r']) / 2, (pad['t'] + bw['t'] - pad['b'] - bw['b']) / 2
    dx, dyy = rot_vec(ox, oy, rot); cx += dx; cy += dyy
    key, nw, nh = asset_for(it, path, cw, ch, outdir)
    if it.get('fit') == 'contain': s = min(cw / nw, ch / nh); pw, ph = nw * s, nh * s
    else: pw, ph = cw, ch
    ASSETS[key]['maxw'] = max(ASSETS[key].get('maxw', 0), pw)
    if it.get('shadow'):      # the shadow sits on its own shape behind the picture
        c = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(cx - pw / 2 + C.SHADOW_INSET_PX), emu(cy - ph / 2 + C.SHADOW_INSET_PX), emu(pw - 2 * C.SHADOW_INSET_PX), emu(ph - 2 * C.SHADOW_INSET_PX))
        if abs(rot) > 0.01: c.rotation = rot
        spPr = strip(c); geom(spPr, pw - 2 * C.SHADOW_INSET_PX, ph - 2 * C.SHADOW_INSET_PX, max(0, it.get('shadow_radius', it.get('radius', 0)) - C.SHADOW_INSET_PX)); color(spPr, dict(r=255, g=255, b=255, a=1)); ln = E('a:ln', spPr); E('a:noFill', ln)
        shadow(spPr, it['shadow'], it.get('op', 1)); c.name = 'Shadow'
        tb = c._element.find(qn('p:txBody'))
        for chd in list(tb): tb.remove(chd)
        E('a:bodyPr', tb); E('a:lstStyle', tb); E('a:p', tb)
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(cx - pw / 2), emu(cy - ph / 2), max(1, emu(pw)), max(1, emu(ph)))
    if abs(rot) > 0.01: sp.rotation = rot
    spPr = strip(sp); E('a:noFill', spPr); ln = E('a:ln', spPr); E('a:noFill', ln)
    tb = sp._element.find(qn('p:txBody'))
    for chd in list(tb): tb.remove(chd)
    E('a:bodyPr', tb, wrap='none', lIns='0', tIns='0', rIns='0', bIns='0'); E('a:lstStyle', tb); p = E('a:p', tb); r = E('a:r', p)
    rp = E('a:rPr', r, lang='en-GB', sz='100'); color(rp, dict(r=160, g=160, b=160, a=1)); t = E('a:t', r); t.text = '{{%s}}' % key
    if it.get('clip'): CLIPS.append(dict(key=key, clip=it['clip'], gif=it.get('gif')))
    return sp
CLIPS = []
ELEMENTS = []   # mask mode: one entry per picture element on a slide


_PLACEHOLDER = None
def _placeholder_png():
    global _PLACEHOLDER
    if _PLACEHOLDER is None:
        import io; b = io.BytesIO(); Image.new('RGBA', (1, 1), (255, 255, 255, 0)).save(b, 'PNG'); _PLACEHOLDER = b.getvalue()
    return _PLACEHOLDER

def opos_frac(opos):
    """CSS object-position (computed, e.g. '0% 50%') -> (fx, fy) in 0..1. Percentages only; anything else is centred."""
    try:
        v = (opos or '50% 50%').split()
        f = [float(x[:-1]) / 100 if x.endswith('%') else 0.5 for x in v[:2]]
        return (f + [0.5, 0.5])[:2]
    except Exception: return [0.5, 0.5]

def _embed_data(path, pw, ph, method, scale, opos=None):
    """-> (bytes, mime, srcRect (l,t,r,b fractions) or None) for a picture shown in a pw x ph box, or None (GIFs stay placeholders)."""
    if path.lower().endswith('.gif'): return None
    import io
    with Image.open(path) as im0:
        im = im0.convert('RGBA') if (im0.mode in ('RGBA', 'LA') or 'transparency' in im0.info or im0.mode == 'P') else im0.convert('RGB'); W, H = im.size
    crop = None; cw, ch = W, H
    if method == 'CENTER_CROP' and abs((pw / ph) / (W / H) - 1) > 0.005:
        fx, fy = opos_frac(opos)
        if (pw / ph) > (W / H): ch = W * ph / pw; t = (H - ch) * fy; crop = (0.0, t / H, 0.0, (H - ch - t) / H)
        else: cw = H * pw / ph; l = (W - cw) * fx; crop = (l / W, 0.0, (W - cw - l) / W, 0.0)
    k = min(1.0, pw * scale / cw)
    if k < 0.999: im = im.resize((max(1, round(W * k)), max(1, round(H * k))), Image.LANCZOS)
    b = io.BytesIO()
    if im.mode == 'RGBA' and im.getchannel('A').getextrema()[0] < 255: im.save(b, 'PNG', optimize=True); mime = 'image/png'
    else: im.convert('RGB').save(b, 'JPEG', quality=C.EMBED_JPEG_QUALITY, optimize=True); mime = 'image/jpeg'
    return b.getvalue(), mime, crop

def plan_embeds(data, picture_mode):
    """Which picture items are embedded in the PPTX: set of (slide id, item index). Pictures that need opacity come first, then the
    smallest; stops when UPLOAD_BUDGET_BYTES - UPLOAD_RESERVE_BYTES would be exceeded (same picture at the same size is counted once)."""
    if picture_mode not in ('auto', 'embed'): return set(), 1.0
    budget = C.UPLOAD_BUDGET_BYTES - C.UPLOAD_RESERVE_BYTES; cands = []
    for d in data:
        for i, it in enumerate(d['items']):
            if it['type'] in ('img', 'svg') and it.get('src') and os.path.exists(it['src']) and not it['src'].lower().endswith('.svg'):
                cands.append((d['id'], i, it))
    def sizes(scale):
        out = []
        for sid, i, it in cands:
            fit = 'fill' if it['type'] == 'svg' else it.get('fit', 'fill'); method = 'CENTER_CROP' if fit in ('cover', 'fill') else 'CENTER_INSIDE'
            e = _embed_data(it['src'], it['w'], it['h'], method, scale, it.get('opos'))
            if e: out.append(((it['src'], round(it['w']), round(it['h']), method), len(e[0]), it.get('op', 1) < 0.999, sid, i))
        return out
    scale = C.EMBED_SCALE
    if picture_mode == 'embed':
        while scale > 0.15:
            sz = sizes(scale); tot = sum({k: n for k, n, *_ in sz}.values())
            if tot <= budget: break
            scale *= 0.8
        return {(sid, i) for *_, sid, i in sz}, scale
    sz = sizes(scale); _cnt = {}
    for r in sz: _cnt[r[0]] = _cnt.get(r[0], 0) + 1
    sz = sorted(sz, key=lambda r: (not r[2], -_cnt[r[0]] / max(1, r[1]))); chosen = set(); seen = {}; total = 0
    for key, n, needs, sid, i in sz:
        add = 0 if key in seen else n
        if total + add <= budget: total += add; seen[key] = n; chosen.add((sid, i))
    return chosen, scale

def add_svg_shape(slide, it, path):
    """An SVG file as one native custom-geometry shape (vector, editable in Slides). The viewBox is stretched to the item's box."""
    from . import svgshape
    info = svgshape.load(path); subs = svgshape.fractions(info)
    if not subs: return None
    w, h, cx, cy, rot, op = it['w'], it['h'], it['cx'], it['cy'], it.get('rot', 0), it.get('op', 1)
    sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(cx - w / 2), emu(cy - h / 2), max(1, emu(w)), max(1, emu(h)))
    if abs(rot) > 0.01: sp.rotation = rot
    spPr = strip(sp); custgeom(spPr, subs)
    if info['fill']: color(spPr, info['fill'], op)
    else: E('a:noFill', spPr)
    ln = E('a:ln', spPr)
    if info['stroke'] and info['sw'] > 0:
        ln.set('w', str(emu(info['sw'] * w / info['vb'][0]))); color(ln, info['stroke'], op); E('a:round', ln)
    else: E('a:noFill', ln)
    sp.name = 'Vector'
    tb = sp._element.find(qn('p:txBody'))
    if tb is not None: sp._element.remove(tb)
    return sp

def add_picture_mask(slide, it, path, slide_id, n, embed_scale=None):
    """Picture element with the right box, rotation and rounded-rectangle mask, holding a 1x1 placeholder. The real
    picture is swapped in by Slides (replaceImage, CENTER_CROP for cover, CENTER_INSIDE for contain) so rounded
    corners, cropping and alpha are the editor's own and the file never needs pre-cut pictures."""
    import io, hashlib
    cx, cy, rot = it['cx'], it['cy'], it['rot']
    pad, bw = it.get('pad') or dict(l=0, r=0, t=0, b=0), it.get('bw') or dict(l=0, r=0, t=0, b=0)
    cw, ch = it['w'] - pad['l'] - pad['r'] - bw['l'] - bw['r'], it['h'] - pad['t'] - pad['b'] - bw['t'] - bw['b']
    if cw <= 0 or ch <= 0: return None
    ox, oy = (pad['l'] + bw['l'] - pad['r'] - bw['r']) / 2, (pad['t'] + bw['t'] - pad['b'] - bw['b']) / 2
    dx, dyy = rot_vec(ox, oy, rot); cx += dx; cy += dyy
    with Image.open(path) as im: nw, nh = im.size
    fit = it.get('fit', 'fill'); radius = it.get('radius', 0)
    if fit == 'contain': s = min(cw / nw, ch / nh); pw, ph = nw * s, nh * s
    else: pw, ph = cw, ch
    method = 'CENTER_CROP' if fit in ('cover', 'fill') and abs(1 - (pw / ph) / (nw / nh)) > 0.005 else 'CENTER_INSIDE'
    emb = _embed_data(path, pw, ph, method, embed_scale, it.get('opos')) if embed_scale else None
    fx, fy = opos_frac(it.get('opos'))
    if not emb and method == 'CENTER_CROP' and (abs(fx - 0.5) > 0.01 or abs(fy - 0.5) > 0.01):
        # Slides' replaceImage can only crop about the centre: cut the picture to the box shape here (object-position honoured), then fit it inside
        import hashlib as _h
        with Image.open(path) as _im:
            _im = _im.convert('RGBA') if _im.mode in ('RGBA', 'LA', 'P') else _im.convert('RGB'); W_, H_ = _im.size
            if (pw / ph) > (W_ / H_): ch_ = W_ * ph / pw; t_ = (H_ - ch_) * fy; box = (0, round(t_), W_, round(t_ + ch_))
            else: cw_ = H_ * pw / ph; l_ = (W_ - cw_) * fx; box = (round(l_), 0, round(l_ + cw_), H_)
            _c = _im.crop(box); os.makedirs(CROPDIR[0], exist_ok=True)
            ext = 'png' if _c.mode == 'RGBA' else 'jpg'
            cp = '%s/crop_%s_%d_%d.%s' % (CROPDIR[0], _h.sha1(open(path, 'rb').read()).hexdigest()[:8], round(fx * 100), round(fy * 100), ext)
            _c.save(cp, quality=95) if ext == 'jpg' else _c.save(cp)
        path = cp; method = 'CENTER_INSIDE'
    key = 'im' + hashlib.sha1(open(path, 'rb').read()).hexdigest()[:10]
    if not emb: a = ASSETS.setdefault(key, dict(file=path, mime='image/gif' if path.lower().endswith('.gif') else 'image/jpeg' if path.lower().endswith(('.jpg', '.jpeg')) else 'image/png', maxw=0))
    if not emb: a['maxw'] = max(a['maxw'], pw)
    if it.get('shadow') and C.PICTURE_SHADOW == 'shape':
        c = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(cx - pw / 2 + C.SHADOW_INSET_PX), emu(cy - ph / 2 + C.SHADOW_INSET_PX), emu(pw - 2 * C.SHADOW_INSET_PX), emu(ph - 2 * C.SHADOW_INSET_PX))
        if abs(rot) > 0.01: c.rotation = rot
        spPr = strip(c); geom(spPr, pw - 2 * C.SHADOW_INSET_PX, ph - 2 * C.SHADOW_INSET_PX, max(0, radius - C.SHADOW_INSET_PX)); color(spPr, dict(r=255, g=255, b=255, a=1)); ln = E('a:ln', spPr); E('a:noFill', ln)
        shadow(spPr, it['shadow'], it.get('op', 1)); c.name = 'Shadow'
        tb = c._element.find(qn('p:txBody'))
        for chd in list(tb): tb.remove(chd)
        E('a:bodyPr', tb); E('a:lstStyle', tb); E('a:p', tb)
    pic = slide.shapes.add_picture(io.BytesIO(emb[0] if emb else _placeholder_png()), emu(cx - pw / 2), emu(cy - ph / 2), max(1, emu(pw)), max(1, emu(ph)))
    if emb and emb[2]:
        sr = E('a:srcRect', None, l=int(emb[2][0] * 100000), t=int(emb[2][1] * 100000), r=int(emb[2][2] * 100000), b=int(emb[2][3] * 100000))
        bf = pic._element.find(qn('p:blipFill')); bf.find(qn('a:blip')).addnext(sr)
    if abs(rot) > 0.01: pic.rotation = rot
    if abs(pw - it['w']) < 1 and abs(ph - it['h']) < 1: cust = geomclip.cust_for(it)
    elif it.get('radius', 0) > 0.5 and abs(rot) < 0.01:      # contain: the picture is smaller than its element; only the element's rounded corners clip it (no preset rounding on the smaller picture)
        radius = 0
        ex, ey = it['cx'], it['cy']; cust = geomclip.cust_for(dict(it, cx=cx, cy=cy, w=pw, h=ph, radius=0, cpath=None, ell=False, ovclip=[dict(x0=ex - it['w'] / 2, y0=ey - it['h'] / 2, x1=ex + it['w'] / 2, y1=ey + it['h'] / 2, r=it['radius'])]))
    else: cust = None
    if cust == 'empty': pic._element.getparent().remove(pic._element); return None
    if isinstance(cust, list) and emb and abs(rot) < 0.01:
        # Google fits a clipped picture to the bounding box of the clip path, not to the picture frame: make the frame that box and crop the image to match
        pts = [(c[i], c[i + 1]) for sp in cust for c in sp if c[0] != 'Z' for i in range(1, len(c) - 1, 2)]
        bx0, bx1, by0, by1 = min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts)
        if bx1 - bx0 > 0.001 and by1 - by0 > 0.001 and (bx0 > 0.002 or by0 > 0.002 or bx1 < 0.998 or by1 < 0.998):
            l0, t0, r0, b0 = emb[2] or (0.0, 0.0, 0.0, 0.0); vw, vh = 1 - l0 - r0, 1 - t0 - b0
            for old in pic._element.find(qn('p:blipFill')).findall(qn('a:srcRect')): old.getparent().remove(old)
            sr = E('a:srcRect', None, l=int((l0 + bx0 * vw) * 100000), t=int((t0 + by0 * vh) * 100000), r=int((r0 + (1 - bx1) * vw) * 100000), b=int((b0 + (1 - by1) * vh) * 100000))
            pic._element.find(qn('p:blipFill')).find(qn('a:blip')).addnext(sr)
            pic.left, pic.top, pic.width, pic.height = emu(cx - pw / 2 + bx0 * pw), emu(cy - ph / 2 + by0 * ph), max(1, emu((bx1 - bx0) * pw)), max(1, emu((by1 - by0) * ph))
            cust = [[(c[0],) + tuple((c[i] - (bx0 if i % 2 else bx0)) / (bx1 - bx0) if i % 2 == 1 else (c[i] - by0) / (by1 - by0) for i in range(1, len(c))) if c[0] != 'Z' else c for c in sp] for sp in cust]
            pw, ph = (bx1 - bx0) * pw, (by1 - by0) * ph
    geom(pic._element.spPr, pw, ph, radius, False, cust)
    if it.get('shadow') and C.PICTURE_SHADOW == 'native': shadow(pic._element.spPr, it['shadow'], it.get('op', 1))
    if (emb or C.PICTURE_ALPHA) and it.get('op', 1) < 0.999:
        blip = pic._element.find('.//' + qn('a:blip')); E('a:alphaModFix', blip, amt=int(round(it['op'] * 100000)))
    tag = '%s.%d.%s' % (slide_id, n, key); pic._element.nvPicPr.cNvPr.set('descr', tag); pic.name = tag
    if not emb: ELEMENTS.append(dict(tag=tag, key=key, slide=slide_id, method=method, transparency=round(1 - it.get('op', 1), 3), w=pw, h=ph, clip=it.get('clip'), gif=path.lower().endswith('.gif')))
    return pic

def add_line(slide, it):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, emu(it['x1']), emu(it['y1']), emu(it['x2']), emu(it['y2']))
    for st in c._element.findall(qn('p:style')): c._element.remove(st)
    spPr = c._element.spPr
    for ch in list(spPr):
        if ch.tag not in (qn('a:xfrm'), qn('a:prstGeom')): spPr.remove(ch)
    ln = E('a:ln', spPr, w=emu(it['w'])); color(ln, it['c'], it.get('op', 1))
    if it.get('dash'): E('a:prstDash', ln, val='dash' if it['dash'] == 'dash' else 'sysDot')
    c.name = 'Line'; return c

def slim(prs):
    """Drop the 10 unused slide layouts of python-pptx's default template (keeps the blank layout every slide uses): the file shrinks
    by ~20 KB, which matters when an upload has to travel inline as base64."""
    used = {s.slide_layout.part.partname for s in prs.slides}
    for lay in list(prs.slide_layouts):
        if lay.part.partname not in used: prs.slide_layouts.remove(lay)

def _slim_master(xml):
    """The default master carries ~10 KB of placeholder text styles no slide uses; keep an empty shape tree and empty text styles."""
    import re
    xml = re.sub(rb'<p:cSld>.*</p:cSld>', b'<p:cSld><p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>', xml, flags=re.S)
    return re.sub(rb'<p:txStyles>.*</p:txStyles>', b'<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>', xml, flags=re.S)

def slim_zip(path, keep_master=False):
    """Remove the template's printer settings and thumbnail (13 KB of nothing) and recompress at maximum."""
    import zipfile, re, shutil
    tmp = path + '.tmp'
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zo:
        for it in zi.infolist():
            if 'printerSettings' in it.filename or it.filename.endswith('thumbnail.jpeg'): continue
            d = zi.read(it.filename)
            if it.filename == 'ppt/slideMasters/slideMaster1.xml' and not keep_master: d = _slim_master(d)
            if it.filename.endswith('.rels'): d = re.sub(rb'<Relationship [^>]*(printerSettings|thumbnail)[^>]*/>', b'', d)
            zo.writestr(it.filename, d)
    shutil.move(tmp, path)

ROLE_TYPES = {'title': ('TITLE', 'CENTER_TITLE'), 'subtitle': ('SUBTITLE',), 'body': ('BODY', 'OBJECT'), 'caption': ('BODY',)}
def _layout(prs, name, template):
    if not template: return prs.slide_layouts[6]
    for l in prs.slide_layouts:
        if name and l.name == name: return l
    if name: print('WARNING layout %r not found in the template; using Blank' % name, file=sys.stderr)
    for l in prs.slide_layouts:
        if l.name.lower() == 'blank': return l
    return prs.slide_layouts[-1]

def _fill_placeholder(slide, it, used):
    """role (title/subtitle/body) -> the layout's placeholder of that type: text only, the template supplies position, font and colour."""
    want = ROLE_TYPES.get(it['role'])
    if not want or not it.get('text'): return False
    for ph in slide.placeholders:
        if ph.placeholder_format.idx in used: continue
        if any(t in str(ph.placeholder_format.type) for t in want):
            tf = ph.text_frame; lines = []; cur = ''
            for r in it['text']['runs']:
                if r.get('br'): lines.append(cur); cur = ''; continue
                parts = r['t'].split('\x0b'); cur += parts[0]
                for part in parts[1:]: lines.append(cur); cur = part
            lines.append(cur); tf.text = lines[0]
            for ln in lines[1:]: tf.add_paragraph().text = ln
            used.add(ph.placeholder_format.idx); return True
    print('WARNING no free %s placeholder on layout %r: drawn as an ordinary text box' % (it['role'], slide.slide_layout.name), file=sys.stderr)
    return False

def build(src, out, fdb, picture_mode=C.PICTURE_MODE, only=None, template=None, corrections=None):
    global FDB, CORR; FDB = fdb; CORR = corrections or {}; CROPDIR[0] = os.path.join(os.path.dirname(os.path.abspath(out)), 'crops'); ASSETS.clear(); CLIPS.clear(); ELEMENTS.clear()
    data = json.load(open(src + '/slides.json')); embeds, escale = plan_embeds(data, picture_mode)
    if template:
        prs = Presentation(template)
        for sid in list(prs.slides._sldIdLst): prs.part.drop_rel(sid.rId); prs.slides._sldIdLst.remove(sid)     # keep masters and layouts, drop the template's own slides
        if abs(prs.slide_width - C.SLIDE_EMU[0]) > 2000 or abs(prs.slide_height - C.SLIDE_EMU[1]) > 2000:
            print('WARNING template slide size %dx%d EMU differs from the deck (%dx%d): positions will be scaled wrongly' % (prs.slide_width, prs.slide_height, C.SLIDE_EMU[0], C.SLIDE_EMU[1]), file=sys.stderr)
    else:
        prs = Presentation(); prs.slide_width = Emu(C.SLIDE_EMU[0]); prs.slide_height = Emu(C.SLIDE_EMU[1])
    from pptx.dml.color import RGBColor
    for d in data:
        if only and d['id'] not in only: continue
        layout = _layout(prs, d.get('layout'), template)
        slide = prs.slides.add_slide(layout); npic = 0
        if not template:
            for ph in list(slide.placeholders): ph._element.getparent().remove(ph._element)
        used_ph = set()
        def picture(it, name, force_fit=None, idx=None):
            nonlocal npic
            path = it['src']
            if it['type'] == 'clip' and it.get('gif'): path = it['gif']
            if path.lower().endswith('.svg'): return add_svg_shape(slide, it, path)
            it = dict(it, fit=force_fit or it.get('fit', 'fill'))
            if picture_mode in ('mask', 'auto', 'embed'): p = add_picture_mask(slide, it, path, d['id'], npic, escale if (d['id'], idx) in embeds else None); npic += 1
            else: p = add_picture_shape(slide, it, path, src)
            return p
        for idx, it in enumerate(d['items']):
            CUR[0] = '%s:%d' % (d['id'], idx); ty = it['type']
            if ty == 'shape':
                if it.get('bg') and it.get('grad') and not template: add_shape(slide, it)     # a gradient slide background is a full-slide shape
                elif it.get('bg') and template: pass                      # the template's background stays
                elif template and it.get('role') and _fill_placeholder(slide, it, used_ph): pass
                elif it.get('bg'):
                    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = RGBColor(round(it['fill']['r']), round(it['fill']['g']), round(it['fill']['b']))
                else: add_shape(slide, it)
            elif ty in ('img', 'clip'): picture(it, 'Picture', None, idx)
            elif ty == 'svg': picture(it, 'Drawing', 'fill', idx)
            elif ty == 'line': add_line(slide, it)
            elif ty == 'link':
                sp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(it['cx'] - it['w'] / 2), emu(it['cy'] - it['h'] / 2), emu(it['w']), emu(it['h']))
                spPr = strip(sp); E('a:noFill', spPr); ln = E('a:ln', spPr); E('a:noFill', ln); sp.click_action.hyperlink.address = it['href']; sp.name = 'Link'
    if not template: slim(prs)          # a company template keeps all its layouts and its master untouched
    prs.save(out); slim_zip(out, keep_master=bool(template))
    print('pictures embedded in the PPTX: %d (scale %.2f); left as placeholders for replaceImage: %d' % (len(embeds), escale, len(ELEMENTS)))
    json.dump(dict(mode=picture_mode, assets=ASSETS, elements=ELEMENTS, clips=CLIPS), open(src + '/manifest.json', 'w'), indent=1)
