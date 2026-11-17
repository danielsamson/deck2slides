"""PPTX (as written by this tool, or exported by Google Slides) -> a Claude Slides deck in the real format
(deck.json v5 with `format`, one shared deck.css, one <section> per slide in project/slides/<id>.html, images as /_blob/<id>).

Everything is pinned (position:absolute, px on the 1920 x 1080 canvas), because a PPTX only knows positions: text becomes <p> inside a
flex <div> (painted when the shape is), ellipses become <x-shape kind="ellipse">, lines <x-connector>, pictures <img> with object-fit,
radius (capped at 256 by the format) and box-shadow, custom geometry an inline <svg>. The first-line shift, rounded-text inset, stroke
inset and widening that pptx_build applies are undone, so a deck made by this tool comes back to its original CSS positions.
What the format cannot hold is reported in the warnings list rather than silently dropped.

Images are written to assets/ and referenced as /_blob/<sha1 prefix>; upload them and replace the ids (blobs.json lists id -> file)."""
import json, os, re, math, hashlib, html as _html
from collections import OrderedDict
from lxml import etree
from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from . import config as C, fonts as F

NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
A = '{%s}' % NS['a']; P = '{%s}' % NS['p']; R = '{%s}' % NS['r']
WEIGHT_BY_SUFFIX = {s.strip(): w for w, s in C.WEIGHT_SUFFIX.items() if s.strip()}
SCHEME_FALLBACK = {'tx1': '000000', 'dk1': '000000', 'bg1': 'FFFFFF', 'lt1': 'FFFFFF', 'tx2': '44546A', 'dk2': '44546A', 'bg2': 'E7E6E6', 'lt2': 'E7E6E6'}
ROUND_INSET_ELL = 0.1464

def esc(t): return _html.escape(t, quote=False)
def num(v): return ('%.2f' % v).rstrip('0').rstrip('.')
def px(v): return num(v) + 'px'

class Ctx:
    def __init__(self, prs, outdir, calibration):
        self.k = 1080.0 / prs.slide_height                  # px per EMU (16:9: 1920 / 9144000)
        self.W = round(prs.slide_width * self.k); self.H = 1080
        self.outdir = outdir; self.warns = []; self.blobs = OrderedDict(); self.styles = OrderedDict(); self.faces = OrderedDict()
        self.theme = self._theme(prs); self.cache = os.path.join(outdir, 'fontcache'); self.natural_cache = {}
        self.cal = calibration or {}; self.db = None
    def warn(self, slide, msg): self.warns.append('slide %s: %s' % (slide, msg))
    def _theme(self, prs):
        out = {}
        try:
            th = etree.fromstring(prs.slide_master.part.part_related_by(RT.THEME).blob)
            cs = th.find('.//a:clrScheme', NS)
            for e in cs:
                c = e[0]; out[etree.QName(e).localname] = c.get('val') or c.get('lastClr')
        except Exception: pass
        return out
    def natural(self, fam):
        if fam in self.natural_cache: return self.natural_cache[fam]
        n = None
        fp = F.fetch_family_file(fam, 'https://fonts.googleapis.com/css2?family=' + fam.replace(' ', '+'), self.cache)
        if fp:
            try: n = F.natural_from_file(fp)
            except Exception: n = None
        if n is None: n = C.NATURAL_FALLBACK; self.warns.append('font %r: natural line height unknown (not on Google Fonts?), using %.2f' % (fam, n))
        self.natural_cache[fam] = round(n, 4); return self.natural_cache[fam]
    def shift(self, fam, lh, fs):
        if not self.cal: return 0.0
        if self.db is None: self.db = F.FontDB({}, self.cal)
        return self.db.dy(fam, lh, fs)

def color_of(ctx, parent):
    """a:solidFill / color element -> (hex, alpha) or None"""
    if parent is None: return None
    c = parent.find('a:srgbClr', NS)
    hexv = None
    if c is not None: hexv = c.get('val')
    else:
        c = parent.find('a:schemeClr', NS)
        if c is not None: v = c.get('val'); hexv = ctx.theme.get(v) or ctx.theme.get({'tx1': 'dk1', 'bg1': 'lt1', 'tx2': 'dk2', 'bg2': 'lt2'}.get(v, v)) or SCHEME_FALLBACK.get(v, '000000')
        else:
            c = parent.find('a:sysClr', NS)
            if c is not None: hexv = c.get('lastClr') or '000000'
    if hexv is None: return None
    al = c.find('a:alpha', NS); a = int(al.get('val')) / 100000.0 if al is not None else 1.0
    return hexv.upper(), a

def css_color(c):
    h, a = c; return '#' + h if a >= 0.999 else 'rgba(%d,%d,%d,%s)' % (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), num(a))

def fill_css(ctx, spPr):
    """-> css background value or None (no fill)"""
    if spPr is None: return None
    sf = spPr.find('a:solidFill', NS)
    if sf is not None:
        c = color_of(ctx, sf); return css_color(c) if c else None
    gf = spPr.find('a:gradFill', NS)
    if gf is not None:
        stops = []
        for gs in gf.findall('a:gsLst/a:gs', NS):
            c = color_of(ctx, gs)
            if c: stops.append('%s %s%%' % (css_color(c), num(int(gs.get('pos')) / 1000.0)))
        if len(stops) < 2: return None
        lin = gf.find('a:lin', NS)
        if lin is not None: return 'linear-gradient(%sdeg,%s)' % (num((int(lin.get('ang')) / 60000.0 + 90) % 360), ','.join(stops))
        return 'radial-gradient(circle,%s)' % ','.join(stops)
    return None

def shadow_css(ctx, spPr):
    if spPr is None: return None
    sh = spPr.find('a:effectLst/a:outerShdw', NS)
    if sh is None: return None
    c = color_of(ctx, sh) or ('000000', 0.3)
    d = int(sh.get('dist', 0)) * ctx.k; ang = math.radians(int(sh.get('dir', 0)) / 60000.0); blur = int(sh.get('blurRad', 0)) * ctx.k
    return '%s %s %s %s' % (px(round(d * math.cos(ang), 1)), px(round(d * math.sin(ang), 1)), px(round(blur, 1)), css_color(c))

def line_css(ctx, spPr):
    """-> (width_px, css color, style, cmpd) or None"""
    if spPr is None: return None
    ln = spPr.find('a:ln', NS)
    if ln is None or ln.find('a:noFill', NS) is not None: return None
    c = color_of(ctx, ln.find('a:solidFill', NS))
    if c is None: return None
    w = int(ln.get('w', 12700)) * ctx.k; dash = ln.find('a:prstDash', NS); style = 'solid'
    if dash is not None: style = {'solid': 'solid', 'dot': 'dotted', 'sysDot': 'dotted'}.get(dash.get('val'), 'dashed')
    if ln.get('cmpd') in ('dbl', 'thickThin', 'thinThick'): style = 'double'
    return w, css_color(c), style

def xfrm_of(el, ctx, group=None):
    xf = el.find('.//a:xfrm', NS) if el.tag != P + 'grpSp' else el.find('p:grpSpPr/a:xfrm', NS)
    if xf is None: return None
    off, ext = xf.find('a:off', NS), xf.find('a:ext', NS)
    x, y, w, h = int(off.get('x')) * ctx.k, int(off.get('y')) * ctx.k, int(ext.get('cx')) * ctx.k, int(ext.get('cy')) * ctx.k
    if group: x, y, w, h = group(x, y, w, h)
    return x, y, w, h, int(xf.get('rot', 0)) / 60000.0, xf.get('flipH') == '1', xf.get('flipV') == '1'

def typeface_to_face(tf, bold):
    """'Inter SemiBold' -> ('Inter', 600); 'Bricolage Grotesque' + b -> ('Bricolage Grotesque', 700)"""
    if not tf: return C.FALLBACK_FAMILY, 700 if bold else 400
    parts = tf.rsplit(' ', 1)
    if len(parts) == 2 and parts[1] in WEIGHT_BY_SUFFIX and tf not in ('Segoe UI Semibold',): return parts[0], WEIGHT_BY_SUFFIX[parts[1]]
    return tf, 700 if bold else 400

def style_class(ctx, props):
    key = json.dumps(props, sort_keys=True)
    if key not in ctx.styles: ctx.styles[key] = ('t%d' % (len(ctx.styles) + 1), props)
    return ctx.styles[key][0]

def paragraphs(ctx, txBody, sid, shape_name):
    """-> list of (class, inner html, plain text) for the non-empty paragraphs, plus first-run font facts for shifts"""
    out = []; facts = None
    for p in txBody.findall('a:p', NS):
        runs = []; first = None
        pPr = p.find('a:pPr', NS); algn = {'l': 'left', 'ctr': 'center', 'r': 'right', 'just': 'left'}.get(pPr.get('algn') if pPr is not None else 'l', 'left')
        lnspc = pPr.find('a:lnSpc', NS) if pPr is not None else None
        for e in p:
            if e.tag == A + 'br': runs.append(('br', None)); continue
            if e.tag not in (A + 'r', A + 'fld'): continue
            t = ''.join(e.find('a:t', NS).itertext()) if e.find('a:t', NS) is not None else ''
            if not t: continue
            rPr = e.find('a:rPr', NS); runs.append(('t', (t, rPr)))
            if first is None: first = rPr
        if not runs or all(k == 'br' or not v[0].strip() for k, v in runs if k == 't') and all(k == 'br' for k, v in runs if k != 't'):
            if not runs or all(k == 'br' for k, _ in runs): continue
        rp0 = first if first is not None else p.find('a:endParaRPr', NS)
        sz = int(rp0.get('sz', 1800)) / 100.0 / C.PT_PER_PX if rp0 is not None else 24
        lat = rp0.find('a:latin', NS) if rp0 is not None else None
        fam, w = typeface_to_face(lat.get('typeface') if lat is not None else None, rp0 is not None and rp0.get('b') == '1')
        col = color_of(ctx, rp0.find('a:solidFill', NS)) if rp0 is not None else None
        spc = int(rp0.get('spc', 0)) / 100.0 / C.PT_PER_PX if rp0 is not None else 0
        nat = ctx.natural(fam)
        if lnspc is not None and lnspc.find('a:spcPct', NS) is not None: lh = int(lnspc.find('a:spcPct', NS).get('val')) / 100000.0 * nat
        elif lnspc is not None and lnspc.find('a:spcPts', NS) is not None: lh = int(lnspc.find('a:spcPts', NS).get('val')) / 100.0 / C.PT_PER_PX / sz
        else: lh = nat
        props = {'family': fam, 'size': round(sz, 2), 'weight': w, 'italic': rp0 is not None and rp0.get('i') == '1', 'color': css_color(col) if col else '#000000',
                 'ls': round(spc, 2), 'lh': round(lh * sz, 1), 'align': algn}
        if facts is None: facts = dict(fam=fam, lh=lh, fs=sz, align=algn)
        ctx.faces.setdefault(fam, set()).add(w)
        inner = ''; plain = ''
        for k, v in runs:
            if k == 'br': inner += '<br>'; plain += '\n'; continue
            t, rPr = v; s = esc(t)
            if rPr is not None:
                lat2 = rPr.find('a:latin', NS); f2, w2 = typeface_to_face(lat2.get('typeface') if lat2 is not None else None, rPr.get('b') == '1')
                sz2 = int(rPr.get('sz', int(round(sz * C.PT_PER_PX * 100)))) / 100.0 / C.PT_PER_PX
                if (f2, w2) != (fam, w) and not (w2 != w and f2 == fam and abs(w2 - w) in (0,)) :
                    if f2 != fam or abs(sz2 - sz) > 0.6: ctx.warn(sid, '%s: mixed face or size inside one paragraph (%s %s/%s): the format keeps only colour, bold, italic, underline inline; using the first run' % (shape_name, f2, w2, num(sz2)))
                c2 = color_of(ctx, rPr.find('a:solidFill', NS))
                if rPr.get('u') in ('sng', 'dbl'): s = '<u>' + s + '</u>'
                if rPr.get('i') == '1' and not props['italic']: s = '<i>' + s + '</i>'
                if w2 > w and w2 >= 700 and w < 600 and f2 == fam: s = '<b>' + s + '</b>'
                if c2 and css_color(c2) != props['color']: s = '<span style="color:%s">%s</span>' % (css_color(c2), s)
            inner += s; plain += t
        out.append((style_class(ctx, props), inner, plain))
    return out, facts

def geom_of(el):
    g = el.find('p:spPr/a:prstGeom', NS)
    if g is not None: return g.get('prst'), g
    if el.find('p:spPr/a:custGeom', NS) is not None: return 'cust', el.find('p:spPr/a:custGeom', NS)
    return 'rect', None

def radius_of(prst, g, w, h):
    if prst == 'roundRect':
        adj = 16667
        gd = g.find('a:avLst/a:gd', NS) if g is not None else None
        if gd is not None and gd.get('fmla', '').startswith('val '): adj = int(gd.get('fmla')[4:])
        return min(adj, 50000) / 100000.0 * min(w, h)
    return 0.0

def svg_path(ctx, cg, w, h, fill, stroke):
    """custGeom -> inline <svg> (one opaque graphic); paths scaled to the shape box"""
    paths = []
    for path in cg.findall('a:pathLst/a:path', NS):
        pw, ph = int(path.get('w', 1)) or 1, int(path.get('h', 1)) or 1; sx, sy = w / pw, h / ph; d = []
        def pt(e): return '%s %s' % (num(int(e.get('x')) * sx), num(int(e.get('y')) * sy))
        for c in path:
            t = etree.QName(c).localname
            if t == 'moveTo': d.append('M' + pt(c[0]))
            elif t == 'lnTo': d.append('L' + pt(c[0]))
            elif t == 'cubicBezTo': d.append('C' + ' '.join(pt(p) for p in c))
            elif t == 'close': d.append('Z')
        paths.append(' '.join(d))
    fill_attr = fill if fill and not fill.startswith(('linear', 'radial')) else 'none'
    return paths, fill_attr

def pic_blob(ctx, pic, sid):
    blip = pic.find('p:blipFill/a:blip', NS)
    if blip is None: return None
    rid = blip.get(R + 'embed')
    try: part = pic._rel_part.related_part(rid) if hasattr(pic, '_rel_part') else None
    except Exception: part = None
    return part

def convert(pptx, outdir, calibration=None):
    os.makedirs(outdir + '/slides', exist_ok=True); os.makedirs(outdir + '/assets', exist_ok=True)
    prs = Presentation(pptx); ctx = Ctx(prs, outdir, calibration)
    if abs(ctx.W - 1920) > 2 and abs(ctx.W - 1440) > 2: ctx.warns.append('slide aspect %dx%d is neither 16:9 nor 4:3' % (ctx.W, ctx.H))
    size43 = abs(ctx.W - 1440) <= 2
    slides = []; order = []
    for si, slide in enumerate(prs.slides, 1):
        sid = 's%d' % si; order.append(sid)
        part = slide.part; body = []; bg = None
        # slide background
        bgel = slide._element.find('p:cSld/p:bg/p:bgPr', NS)
        if bgel is not None:
            c = fill_css(ctx, bgel)
            if c: bg = c
        items = list(slide._element.find('p:cSld/p:spTree', NS))

        def walk(els, group=None):
            nonlocal bg
            for el in els:
                tag = el.tag
                if tag == P + 'grpSp':
                    gx = el.find('p:grpSpPr/a:xfrm', NS)
                    if gx is None: continue
                    off, ext, co, ce = gx.find('a:off', NS), gx.find('a:ext', NS), gx.find('a:chOff', NS), gx.find('a:chExt', NS)
                    ox, oy, ew, eh = int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))
                    cx0, cy0, cw, ch = int(co.get('x')), int(co.get('y')), int(ce.get('cx')) or 1, int(ce.get('cy')) or 1
                    sx, sy = ew / cw, eh / ch
                    def tf(x, y, w, h, ox=ox, oy=oy, sx=sx, sy=sy, cx0=cx0, cy0=cy0, outer=group):
                        # x,y,w,h arrive in px of the child frame; convert via EMU, then scale into the parent
                        k = ctx.k; nx, ny = (x / k - cx0) * sx + ox, (y / k - cy0) * sy + oy
                        r = (nx * k, ny * k, w * sx, h * sy)
                        return outer(*r) if outer else r
                    walk(list(el)[2:], tf); continue
                if tag not in (P + 'sp', P + 'pic', P + 'cxnSp'): continue
                xf = xfrm_of(el, ctx, group)
                if xf is None: continue
                x, y, w, h, rot, flipH, flipV = xf
                name = (el.find('.//p:cNvPr', NS).get('name') if el.find('.//p:cNvPr', NS) is not None else tag)
                rot_css = 'transform:rotate(%sdeg);' % num(rot) if abs(rot) > 0.01 else ''
                if tag == P + 'cxnSp':
                    ln = line_css(ctx, el.find('p:spPr', NS))
                    if ln is None: continue
                    x1, y1, x2, y2 = x + (w if flipH else 0), y + (h if flipV else 0), x + (0 if flipH else w), y + (0 if flipV else h)
                    dash = ';border-style:%s' % ln[2] if ln[2] != 'solid' else ''
                    body.append('<x-connector x1="%s" y1="%s" x2="%s" y2="%s" head="none" style="color:%s;border-width:%s%s"></x-connector>' % (num(x1), num(y1), num(x2), num(y2), ln[1], px(round(max(ln[0], 1), 1)), dash))
                    continue
                spPr = el.find('p:spPr', NS); prst, g = geom_of(el)
                pin = 'position:absolute;left:%s;top:%s;width:%s;height:%s;' % (px(round(x, 2)), px(round(y, 2)), px(round(w, 2)), px(round(h, 2)))
                if tag == P + 'pic':
                    blip = el.find('p:blipFill/a:blip', NS)
                    rid = blip.get(R + 'embed') if blip is not None else None
                    try: ipart = slide.part.related_part(rid)
                    except Exception: ipart = None
                    if ipart is None: ctx.warn(sid, '%s: picture without an image part' % name); continue
                    data = ipart.blob; sha = hashlib.sha1(data).hexdigest()[:32]; ext = os.path.splitext(ipart.partname)[1].lower() or '.png'
                    fn = 'assets/%s%s' % (sha, ext)
                    if sha not in ctx.blobs: open(os.path.join(outdir, fn), 'wb').write(data); ctx.blobs[sha] = fn
                    from PIL import Image; import io
                    iw, ih = Image.open(io.BytesIO(data)).size
                    sr = el.find('p:blipFill/a:srcRect', NS); l = t = r_ = b = 0.0
                    if sr is not None: l, t, r_, b = [int(sr.get(k, 0)) / 100000.0 for k in 'ltrb']
                    vw, vh = max(1 - l - r_, 1e-6), max(1 - t - b, 1e-6)
                    fit = 'cover'; extra = ''
                    box_ratio = w / h; vis_ratio = (vw * iw) / (vh * ih)
                    if abs(box_ratio / vis_ratio - 1) > 0.03: ctx.warn(sid, '%s: picture is stretched (box %.2f, visible image %.2f); drawn with object-fit:cover' % (name, box_ratio, vis_ratio))
                    s0 = max(w / iw, h / ih); s = w / (vw * iw); zoom = s / s0
                    if zoom > 1.02 or abs(l - r_) > 0.002 and (l + r_) > 0.002 or abs(t - b) > 0.002 and (t + b) > 0.002:
                        px_ = 50 if (l + r_) < 1e-6 else l / (l + r_) * 100; py_ = 50 if (t + b) < 1e-6 else t / (t + b) * 100
                        if zoom > 1.02 or abs(px_ - 50) > 1 or abs(py_ - 50) > 1: extra = ' data-crop="%s %s%% %s%%"' % (num(round(zoom, 3)), num(round(px_, 1)), num(round(py_, 1)))
                    rad = ''
                    if prst == 'ellipse':
                        if abs(w - h) <= 1 and w <= 512.5: rad = 'border-radius:%s;' % px(round(w / 2, 1))
                        else: rad = 'border-radius:256px;'; ctx.warn(sid, '%s: elliptical picture mask %dx%d cannot be written (radius is capped at 256 and square pictures are circles only up to 512 px)' % (name, w, h))
                    elif prst == 'roundRect':
                        rr = radius_of(prst, g, w, h)
                        if rr > 256: ctx.warn(sid, '%s: picture radius %.0f clamped to 256' % (name, rr)); rr = 256
                        rad = 'border-radius:%s;' % px(round(rr, 1)) if rr > 0.5 else ''
                    elif prst == 'cust': ctx.warn(sid, '%s: custom clip on a picture is not expressible (clip-path is dropped by the format); drawn unclipped' % name)
                    sh = shadow_css(ctx, spPr); shs = 'box-shadow:%s;' % sh if sh else ''
                    am = el.find('p:blipFill/a:blip/a:alphaModFix', NS); op = ''
                    if am is not None and am.get('amt') and int(am.get('amt')) < 99900: op = 'opacity:%s;' % num(int(am.get('amt')) / 100000.0)
                    descr = el.find('.//p:cNvPr', NS).get('descr') or name
                    body.append('<img src="/_blob/%s" alt="%s" style="%sobject-fit:%s;%s%s%s%s"%s>' % (sha, esc(descr).replace('"', '&quot;'), pin, fit, rad, shs, op, rot_css, extra))
                    continue
                # ---- p:sp
                fill = fill_css(ctx, spPr); ln = line_css(ctx, spPr); sh = shadow_css(ctx, spPr)
                tb = el.find('p:txBody', NS); paras, facts = ([], None)
                if tb is not None: paras, facts = paragraphs(ctx, tb, sid, name)
                # full-slide backdrop becomes the section background
                if not paras and fill and w >= ctx.W - 2 and h >= ctx.H - 2 and x <= 2 and y <= 2 and not body and bg is None and ln is None: bg = fill; continue
                rr = radius_of(prst, g, w, h); sw = ln[0] if ln else 0.0
                if prst == 'cust':
                    paths, fa = svg_path(ctx, g, w, h, fill, ln)
                    st = ' stroke="%s" stroke-width="%s"' % (ln[1], num(ln[0])) if ln else ''
                    body.append('<svg aria-label="%s" width="%s" height="%s" viewBox="0 0 %s %s" style="%s%s">%s</svg>' % (esc(name).replace('"', '&quot;'), num(w), num(h), num(w), num(h), pin, rot_css,
                                ''.join('<path d="%s" fill="%s"%s/>' % (d, fa if fa != 'none' else (fill if fill else 'none'), st) for d in paths)))
                    if fill and fill.startswith(('linear', 'radial')): ctx.warn(sid, '%s: gradient on a freeform shape drawn flat (inside an svg)' % name)
                    continue
                painted = fill or ln or sh
                cl = ''
                if ln: bw = ln[0]; box = (x - bw / 2, y - bw / 2, w + bw, h + bw); rr = max(0.0, rr + bw / 2)
                else: bw = 0.0; box = (x, y, w, h)
                shp_pin = 'position:absolute;left:%s;top:%s;width:%s;height:%s;box-sizing:border-box;' % tuple(px(round(v, 2)) for v in box)
                paint = ''
                if fill: paint += 'background:%s;' % fill
                if ln: paint += 'border:%s %s %s;' % (px(round(ln[0], 2)), ln[2], ln[1])
                if sh: paint += 'box-shadow:%s;' % sh
                if prst == 'ellipse' and not paras:
                    body.append('<x-shape kind="ellipse" style="%s%s%s"></x-shape>' % (shp_pin, paint, rot_css)); continue
                if rr > 0.5 and prst != 'ellipse':
                    if rr > 256: ctx.warn(sid, '%s: radius %.0f clamped to 256 (format cap)' % (name, rr)); rr = 256
                    paint += 'border-radius:%s;' % px(round(rr, 1))
                if prst == 'ellipse' and paras: ctx.warn(sid, '%s: text inside an ellipse; drawn as a rounded box with radius 256' % name); paint += 'border-radius:256px;'
                if not paras and not painted: continue
                bp = tb.find('a:bodyPr', NS) if tb is not None else None
                ins = [int(bp.get(k, d)) * ctx.k for k, d in (('lIns', 91440), ('tIns', 45720), ('rIns', 91440), ('bIns', 45720))] if bp is not None else [0, 0, 0, 0]
                anchor = bp.get('anchor', 't') if bp is not None else 't'
                if paras:
                    # undo what pptx_build did: round-corner inset, stroke inset, first-line shift
                    kx = ky = 0.0
                    if prst == 'roundRect': kx = ky = C.ROUND_TEXT_INSET * min(rr - bw / 2 if rr else 0, min(w, h) / 2)
                    elif prst == 'ellipse': kx, ky = ROUND_INSET_ELL * w, ROUND_INSET_ELL * h
                    sf = ctx.shift(facts['fam'], facts['lh'], facts['fs']) if facts else 0.0
                    pl, pt_, pr, pb = ins[0] + kx - bw / 2 + 0.0, ins[1] + ky - bw / 2, ins[2] + kx - bw / 2, ins[3] + ky - bw / 2
                    if painted:
                        if anchor == 'ctr':
                            m = min(pt_, pb); pt_ = pb = m
                        else: pt_ -= sf
                    else:
                        pass                      # free text: pptx_build moved the box itself, so the box moves back (below)
                    pad = 'padding:%s %s %s %s;' % tuple(px(round(max(0, v), 2)) for v in (pt_, pr, pb, pl))
                    just = {'t': 'flex-start', 'ctr': 'center', 'b': 'flex-end'}.get(anchor, 'flex-start')
                    inner = ''.join('<p class="%s">%s</p>' % (c, h_) for c, h_, _ in paras)
                    if not painted: shp_pin = 'position:absolute;left:%s;top:%s;width:%s;height:%s;box-sizing:border-box;' % (px(round(x, 2)), px(round(y - sf, 2)), px(round(w, 2)), px(round(h, 2)))
                    body.append('<div style="%s%sdisplay:flex;flex-direction:column;justify-content:%s;%s%s">%s</div>' % (shp_pin, paint, just, pad, rot_css, inner))
                else:
                    body.append('<div style="%s%s%s"></div>' % (shp_pin, paint, rot_css))
        walk(items)
        if len(body) > 200: ctx.warn(sid, '%d elements: the format holds at most 200 per slide' % len(body))
        notes = ''
        try:
            if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip(): notes = '\n<aside>%s</aside>' % esc(slide.notes_slide.notes_text_frame.text.strip())
        except Exception: pass
        style = ' style="background:%s"' % bg if bg else ''
        slides.append((sid, '<section id="%s"%s>\n%s%s\n</section>' % (sid, style, '\n'.join(body), notes)))
    # ---- files
    for sid, htm in slides: open('%s/slides/%s.html' % (outdir, sid), 'w').write(htm)
    css = ["body{font-family:Arial,sans-serif;color:#000000}", "section{padding:0}"]
    for key, (cls, p) in ctx.styles.items():
        css.append(".%s{font-family:'%s',Arial,sans-serif;font-size:%spx;font-weight:%d;%scolor:%s;%stext-align:%s;line-height:%spx}" % (
            cls, p['family'], num(p['size']), p['weight'], 'font-style:italic;' if p['italic'] else '', p['color'], 'letter-spacing:%spx;' % num(p['ls']) if abs(p['ls']) > 0.01 else '', p['align'], num(p['lh'])))
    open(outdir + '/deck.css', 'w').write('\n'.join(css) + '\n')
    faces = OrderedDict()
    for fam, ws in list(ctx.faces.items())[:4]:
        if fam == C.FALLBACK_FAMILY: continue
        faces[fam.lower().replace(' ', '-')] = {'family': fam, 'href': 'https://fonts.googleapis.com/css2?family=%s:wght@%s&display=swap' % (fam.replace(' ', '+'), ';'.join(str(w) for w in sorted(ws)))}
    if len(ctx.faces) > 4: ctx.warns.append('%d font families: the format holds at most 4 (first four declared)' % len(ctx.faces))
    deck = {'v': 5, 'createdOnFiles': {'v': 1, 'at': '2026-01-01T00:00:00Z'}, 'lists': 'css', 'format': {'v': 1, 'shared': ['project/deck.css']}, 'title': os.path.splitext(os.path.basename(pptx))[0],
            'order': order, 'sections': {'s1': {'description': 'Imported deck', 'start': order[0]}}, 'faces': faces, 'designSystems': []}
    if size43: deck['size'] = '4:3'
    json.dump(deck, open(outdir + '/deck.json', 'w'), indent=1)
    json.dump({sha: fn for sha, fn in ctx.blobs.items()}, open(outdir + '/assets-map.json', 'w'), indent=1)
    json.dump({'blobs': {fn: {'id': sha} for sha, fn in ctx.blobs.items()}, 'warnings': ctx.warns}, open(outdir + '/convert-report.json', 'w'), indent=1)
    return ctx.warns, len(slides)
