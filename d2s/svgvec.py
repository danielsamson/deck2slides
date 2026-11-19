"""Inline SVG drawings (icons) as native freeform shapes.

A drawing made of paths, circles, rects, lines, polylines and polygons is turned into one PowerPoint freeform (a:custGeom) with a
stroke. Google Slides imports it as a real vector shape: no resampling, so position, size and line weight match the browser exactly,
and the icon stays recolourable. Anything else (transforms, masks, filters, gradients, mixed stroke widths) returns None and the
caller keeps the old route (a transparent picture).

extract.cjs supplies the description (`it.vec`): the viewBox, and for each drawing element its attributes and computed style.
"""
import math, re

_NUM = re.compile(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
_ARGS = dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7, Z=0)

def parse_colour(s):
    """'rgb(1, 2, 3)' / 'rgba(1, 2, 3, .5)' -> {'r','g','b','a'}; None for 'none' or anything we cannot read (url(#grad), ...)."""
    if not s or s == 'none': return None
    m = re.match(r'rgba?\(\s*([\d.]+)[ ,]+([\d.]+)[ ,]+([\d.]+)(?:[ ,/]+([\d.]+%?))?\s*\)', s)
    if not m: return False
    a = 1.0
    if m.group(4): a = float(m.group(4)[:-1]) / 100 if m.group(4).endswith('%') else float(m.group(4))
    return dict(r=float(m.group(1)), g=float(m.group(2)), b=float(m.group(3)), a=a)

def arc_to_beziers(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    """SVG endpoint arc -> list of cubic segments ((c1x, c1y), (c2x, c2y), (x, y))."""
    if (x1, y1) == (x2, y2): return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0: return [((x1, y1), (x2, y2), (x2, y2))]
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2; x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = x1p ** 2 / rx ** 2 + y1p ** 2 / ry ** 2
    if lam > 1: rx *= math.sqrt(lam); ry *= math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2; den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    co = math.sqrt(max(0, num / den)) * (-1 if fa == fs else 1) if den else 0
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry); dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0: dt -= 2 * math.pi
    elif fs and dt < 0: dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2) - 1e-9))); d = dt / n; k = 4 / 3 * math.tan(d / 4); out = []
    pt = lambda a: (cx + rx * math.cos(a) * cp - ry * math.sin(a) * sp, cy + rx * math.cos(a) * sp + ry * math.sin(a) * cp)
    dv = lambda a: (-rx * math.sin(a) * cp - ry * math.cos(a) * sp, -rx * math.sin(a) * sp + ry * math.cos(a) * cp)
    for i in range(n):
        a0, a1 = t1 + i * d, t1 + (i + 1) * d; p0, p1 = pt(a0), pt(a1); d0, d1 = dv(a0), dv(a1)
        out.append(((p0[0] + k * d0[0], p0[1] + k * d0[1]), (p1[0] - k * d1[0], p1[1] - k * d1[1]), p1))
    return out

def parse_path(d):
    """Path data -> absolute ('M', x, y) / ('L', x, y) / ('C', x1, y1, x2, y2, x, y) / ('Z',) commands. None on anything unreadable."""
    toks = re.findall(r'[MmLlHhVvCcSsQqTtAaZz]|' + _NUM.pattern, d or '')
    out = []; i = 0; cmd = None; x = y = sx = sy = 0.0; last = None; lc = None   # lc: last control point for S/T
    def num():
        nonlocal i
        v = float(toks[i]); i += 1; return v
    def flag():
        nonlocal i
        t = toks[i]
        if len(t) > 1 and t[0] in '01' and not t.startswith(('0.', '1.')):      # packed flags: "a1 1 0 011 1"
            toks[i] = t[1:]; return int(t[0])
        i += 1; return int(float(t))
    while i < len(toks):
        if re.match(r'[A-Za-z]', toks[i]): cmd = toks[i]; i += 1
        elif cmd is None: return None
        c = cmd.upper(); rel = cmd.islower()
        if c == 'Z': out.append(('Z',)); x, y = sx, sy; lc = None; last = 'Z'; cmd = None if i >= len(toks) else cmd; continue
        try:
            if c == 'M':
                nx, ny = num(), num()
                if rel: nx += x; ny += y
                x, y = nx, ny; sx, sy = x, y; out.append(('M', x, y)); cmd = 'l' if rel else 'L'; lc = None
            elif c == 'L':
                nx, ny = num(), num()
                if rel: nx += x; ny += y
                x, y = nx, ny; out.append(('L', x, y)); lc = None
            elif c == 'H':
                nx = num() + (x if rel else 0); x = nx; out.append(('L', x, y)); lc = None
            elif c == 'V':
                ny = num() + (y if rel else 0); y = ny; out.append(('L', x, y)); lc = None
            elif c in 'CS':
                if c == 'C':
                    x1, y1 = num(), num()
                    if rel: x1 += x; y1 += y
                else: x1, y1 = (2 * x - lc[0], 2 * y - lc[1]) if lc and last == 'C' else (x, y)
                x2, y2, nx, ny = num(), num(), num(), num()
                if rel: x2 += x; y2 += y; nx += x; ny += y
                out.append(('C', x1, y1, x2, y2, nx, ny)); lc = (x2, y2); x, y = nx, ny; last = 'C'; continue
            elif c in 'QT':
                if c == 'Q': qx, qy = num(), num()
                else: qx, qy = (2 * x - lc[0], 2 * y - lc[1]) if lc and last == 'Q' else (x, y)
                nx, ny = num(), num()
                if rel:
                    if c == 'Q': qx += x; qy += y
                    nx += x; ny += y
                out.append(('C', x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y), nx + 2 / 3 * (qx - nx), ny + 2 / 3 * (qy - ny), nx, ny)); lc = (qx, qy); x, y = nx, ny; last = 'Q'; continue
            elif c == 'A':
                rx, ry, phi = num(), num(), num(); fa = flag(); fs = flag(); nx, ny = num(), num()
                if rel: nx += x; ny += y
                for c1, c2, p in arc_to_beziers(x, y, rx, ry, phi, fa, fs, nx, ny): out.append(('C', c1[0], c1[1], c2[0], c2[1], p[0], p[1]))
                x, y = nx, ny; lc = None
            else: return None
        except (IndexError, ValueError): return None
        last = c
    return out

def _ellipse(cx, cy, rx, ry):
    k = 0.5522847498
    return [('M', cx + rx, cy), ('C', cx + rx, cy + k * ry, cx + k * rx, cy + ry, cx, cy + ry), ('C', cx - k * rx, cy + ry, cx - rx, cy + k * ry, cx - rx, cy),
            ('C', cx - rx, cy - k * ry, cx - k * rx, cy - ry, cx, cy - ry), ('C', cx + k * rx, cy - ry, cx + rx, cy - k * ry, cx + rx, cy), ('Z',)]

def _rect(x, y, w, h, rx, ry):
    if not rx and not ry: return [('M', x, y), ('L', x + w, y), ('L', x + w, y + h), ('L', x, y + h), ('Z',)]
    rx = min(rx or ry, w / 2); ry = min(ry or rx, h / 2)
    d = 'M%g %gH%gA%g %g 0 0 1 %g %gV%gA%g %g 0 0 1 %g %gH%gA%g %g 0 0 1 %g %gV%gA%g %g 0 0 1 %g %gZ' % (
        x + rx, y, x + w - rx, rx, ry, x + w, y + ry, y + h - ry, rx, ry, x + w - rx, y + h, x + rx, rx, ry, x, y + h - ry, y + ry, rx, ry, x + rx, y)
    return parse_path(d)

def _points(s):
    v = [float(n) for n in _NUM.findall(s or '')]
    return list(zip(v[0::2], v[1::2])) if len(v) >= 4 and len(v) % 2 == 0 else None

def element_cmds(e):
    a = e['at']; f = lambda k, d=0.0: float(a.get(k, d) or d)
    try:
        t = e['t']
        if t == 'path': return parse_path(a.get('d'))
        if t == 'circle': return _ellipse(f('cx'), f('cy'), f('r'), f('r'))
        if t == 'ellipse': return _ellipse(f('cx'), f('cy'), f('rx'), f('ry'))
        if t == 'rect': return _rect(f('x'), f('y'), f('width'), f('height'), f('rx'), f('ry'))
        if t == 'line': return [('M', f('x1'), f('y1')), ('L', f('x2'), f('y2'))]
        if t in ('polyline', 'polygon'):
            pts = _points(a.get('points'))
            if not pts: return None
            return [('M',) + pts[0]] + [('L',) + p for p in pts[1:]] + ([('Z',)] if t == 'polygon' else [])
    except ValueError: return None
    return None

def build(vec, w, h):
    """vec (from extract.cjs) + the drawing's box in px -> spec for pptx_build.add_vector, or None when it cannot be done faithfully.
    spec: {'paths': [{'cmds': [...in 0..1 of the box], 'fill': bool, 'stroke': bool}], 'fill', 'stroke' (colour dicts), 'sw' px, 'cap', 'join'}"""
    if not vec or not vec.get('els'): return None
    vx, vy, vw, vh = vec['vb']
    if vw <= 0 or vh <= 0 or abs((w / h) - (vw / vh)) > 0.02 * (vw / vh): return None      # non-uniform scaling: leave it to the picture route
    sx, sy = 1 / vw, 1 / vh; paths = []; fill = stroke = None; sws = set(); cap = join = None
    for e in vec['els']:
        cmds = element_cmds(e)
        if not cmds: return None
        f = parse_colour(e.get('fill')); s = parse_colour(e.get('stroke'))
        if f is False or s is False: return None                                         # gradients and url() paints
        if e.get('op', 1) < 0.999 or (f and e.get('fo', 1) < 0.999) or (s and e.get('so', 1) < 0.999): return None
        sw = e.get('sw', 0) if s else 0
        if s and sw <= 0: s = None
        if f and fill and f != fill or s and stroke and s != stroke: return None            # two colours in one icon
        fill = fill or f; stroke = stroke or s
        if s: sws.add(round(sw, 3)); cap = cap or e.get('cap'); join = join or e.get('join')
        norm = []
        for c in cmds:
            if c[0] == 'Z': norm.append(c)
            else: norm.append((c[0],) + tuple(((c[i] - (vx if i % 2 == 1 else vy)) * (sx if i % 2 == 1 else sy)) for i in range(1, len(c))))
        paths.append(dict(cmds=norm, fill=bool(f), stroke=bool(s)))
    if len(sws) > 1: return None
    sw = (sws.pop() if sws else 0) * (w / vw)
    return dict(paths=paths, fill=fill, stroke=stroke, sw=sw, cap=cap or 'butt', join=join or 'miter')
