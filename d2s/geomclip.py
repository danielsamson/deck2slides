"""Geometry for clip-path and overflow:hidden. Output is a list of sub-paths in fractions of the item's own box, written as custGeom
by pptx_build. Polygon clips stay exact (straight edges); ellipse/circle clips alone are exact cubic Beziers; the result of an
overflow:hidden intersection that contains curves is a polygon with CURVE_STEPS points per quarter circle (an approximation,
about 0.1 px at 500 px size).
sub-path commands: ('M', x, y) ('L', x, y) ('C', x1, y1, x2, y2, x, y) ('Z',)"""
import math
from shapely.geometry import Polygon, box as sbox

KAPPA = 0.5522847498
CURVE_STEPS = 32

def rrect(x0, y0, x1, y1, r):
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    if r <= 0.01: return sbox(x0, y0, x1, y1)
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for i in range(CURVE_STEPS + 1):
            a = math.radians(a0 + 90.0 * i / CURVE_STEPS); pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return Polygon(pts)

def ellipse_poly(cx, cy, rx, ry):
    n = CURVE_STEPS * 4
    return Polygon([(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)])

def _box(it):
    return it['cx'] - it['w'] / 2, it['cy'] - it['h'] / 2, it['cx'] + it['w'] / 2, it['cy'] + it['h'] / 2

def item_poly(it):
    x0, y0, x1, y1 = _box(it); w, h = it['w'], it['h']; cp = it.get('cpath')
    if cp and cp['kind'] == 'poly': return Polygon([(x0 + fx * w, y0 + fy * h) for fx, fy in cp['pts']])
    if cp and cp['kind'] == 'ellipse': return ellipse_poly(x0 + cp['cx'] * w, y0 + cp['cy'] * h, cp['rx'] * w, cp['ry'] * h)
    if it.get('ell'): return ellipse_poly((x0 + x1) / 2, (y0 + y1) / 2, w / 2, h / 2)
    return rrect(x0, y0, x1, y1, it.get('radius', 0))

def _subpaths(poly, it):
    x0, y0, x1, y1 = _box(it); w, h = it['w'], it['h']; out = []
    geoms = list(poly.geoms) if hasattr(poly, 'geoms') else [poly]
    for g in geoms:
        if g.is_empty or g.geom_type != 'Polygon': continue
        pts = list(g.exterior.coords)[:-1]
        if len(pts) < 3: continue
        sp = [('M', (pts[0][0] - x0) / w, (pts[0][1] - y0) / h)] + [('L', (x - x0) / w, (y - y0) / h) for x, y in pts[1:]] + [('Z',)]
        out.append(sp)
    return out

def _bez_ellipse(cx, cy, rx, ry):
    k = KAPPA
    return [[('M', cx + rx, cy), ('C', cx + rx, cy + k * ry, cx + k * rx, cy + ry, cx, cy + ry), ('C', cx - k * rx, cy + ry, cx - rx, cy + k * ry, cx - rx, cy),
             ('C', cx - rx, cy - k * ry, cx - k * rx, cy - ry, cx, cy - ry), ('C', cx + k * rx, cy - ry, cx + rx, cy - k * ry, cx + rx, cy), ('Z',)]]

def cust_for(it):
    """-> None (use the normal preset geometry) | 'empty' (item is fully clipped away) | list of sub-paths."""
    ov = it.get('ovclip'); cp = it.get('cpath'); rot = abs(it.get('rot', 0)) > 0.01
    if ov and not rot:
        base = item_poly(it); poly = base
        for a in ov:
            poly = poly.intersection(rrect(a['x0'], a['y0'], a['x1'], a['y1'], a.get('r', 0)))
            if poly.is_empty: return 'empty'
        x0, y0, x1, y1 = _box(it); poly = poly.intersection(sbox(x0, y0, x1, y1))
        if abs(poly.area - base.area) > 0.5 or cp:
            sp = _subpaths(poly, it); return sp or 'empty'
        if not cp: return None
    if cp:
        if cp['kind'] == 'ellipse': return _bez_ellipse(cp['cx'], cp['cy'], cp['rx'], cp['ry'])
        return _subpaths(item_poly(it), it) if cp['kind'] == 'poly' else None
    return None
