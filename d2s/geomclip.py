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

def band_poly(it):
    """One side of a non-uniform border on a rounded box, as CSS paints it: the ring between the outer rounded box and the
    inner one (inset by each side's width, radius less that width), cut where the sides meet (outer corner to inner corner)."""
    b = it['band']; k, bw, r = b['k'], b['bw'], b['r']
    x0, y0, x1, y1 = _box(it)
    ring = rrect(x0, y0, x1, y1, r).difference(rrect(x0 + bw['l'], y0 + bw['t'], x1 - bw['r'], y1 - bw['b'], max(0.0, r - max(bw.values()))))
    ix0, iy0, ix1, iy1 = x0 + bw['l'], y0 + bw['t'], x1 - bw['r'], y1 - bw['b']
    # CSS splits each corner along the line from the outer corner to the inner corner; a side keeps the part of the ring on
    # its own side of both its corner lines (a corner whose two widths are 0 has no line).
    def half(px, py, qx, qy, ref):
        dx, dy = qx - px, qy - py
        if abs(dx) < 1e-9 and abs(dy) < 1e-9: return None
        n = (-dy, dx); L = 1e5; sgn = 1 if (ref[0] - px) * n[0] + (ref[1] - py) * n[1] >= 0 else -1
        a, b = (px - dx * L, py - dy * L), (px + dx * L, py + dy * L)
        return Polygon([a, b, (b[0] + sgn * n[0] * L, b[1] + sgn * n[1] * L), (a[0] + sgn * n[0] * L, a[1] + sgn * n[1] * L)]).buffer(0)
    corners = {'tl': (x0, y0, ix0, iy0), 'tr': (x1, y0, ix1, iy0), 'bl': (x0, y1, ix0, iy1), 'br': (x1, y1, ix1, iy1)}
    sides = {'t': (('tl', 'tr'), ((x0 + x1) / 2, y0)), 'b': (('bl', 'br'), ((x0 + x1) / 2, y1)),
             'l': (('tl', 'bl'), (x0, (y0 + y1) / 2)), 'r': (('tr', 'br'), (x1, (y0 + y1) / 2))}
    def wedge(j):
        w = sbox(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
        for c in sides[j][0]:
            hp = half(*corners[c], sides[j][1])
            if hp is not None: w = w.intersection(hp)
        return w
    poly = ring.intersection(wedge(k))
    # adjacent sides are settled by the corner lines; opposite sides (corner lines meeting beyond the box) split at the midline
    opp = {'t': 'b', 'b': 't', 'l': 'r', 'r': 'l'}[k]
    if bw[opp] > 0:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        poly = poly.intersection({'t': sbox(x0 - 1, y0 - 1, x1 + 1, my), 'b': sbox(x0 - 1, my, x1 + 1, y1 + 1),
                                  'l': sbox(x0 - 1, y0 - 1, mx, y1 + 1), 'r': sbox(mx, y0 - 1, x1 + 1, y1 + 1)}[k])
    return poly

def cust_for(it):
    """-> None (use the normal preset geometry) | 'empty' (item is fully clipped away) | list of sub-paths."""
    if it.get('band'):
        poly = band_poly(it)
        for a in (it.get('ovclip') or []): poly = poly.intersection(rrect(a['x0'], a['y0'], a['x1'], a['y1'], a.get('r', 0)))
        return (_subpaths(poly, it) or 'empty') if not poly.is_empty else 'empty'
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
