"""SVG file -> native custom-geometry shape (Slides keeps it as editable vector).
Subset: <g>/<svg> with fill, fill-opacity, stroke, stroke-width, stroke-opacity; <path d> (M L H V C Q Z, absolute or relative) with
transform="translate(x y) scale(sx sy)"; <circle>; <rect>. That covers font-outline words, numerals and dot maps."""
import re, math
import xml.etree.ElementTree as ET

NUM = re.compile(r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?')
TOK = re.compile(r'([MmLlHhVvCcQqZz])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)')

def parse_color(v):
    if not v or v == 'none': return None
    v = v.strip()
    if v.startswith('#'):
        h = v[1:]; h = ''.join(c * 2 for c in h) if len(h) == 3 else h
        return dict(r=int(h[0:2], 16), g=int(h[2:4], 16), b=int(h[4:6], 16), a=1)
    return None

def parse_transform(t):
    tx = ty = 0.0; sx = sy = 1.0
    if not t: return tx, ty, sx, sy
    m = re.search(r'translate\(\s*([-\d.eE+]+)[ ,]+([-\d.eE+]+)\s*\)', t)
    if m: tx, ty = float(m.group(1)), float(m.group(2))
    m = re.search(r'scale\(\s*([-\d.eE+]+)(?:[ ,]+([-\d.eE+]+))?\s*\)', t)
    if m: sx = float(m.group(1)); sy = float(m.group(2)) if m.group(2) else sx
    return tx, ty, sx, sy

def path_cmds(d):
    """-> list of ('M',x,y) ('L',x,y) ('C',x1,y1,x2,y2,x,y) ('Z',) in absolute coordinates; quadratics become cubics."""
    toks = [(a, b) for a, b in TOK.findall(d)]; i = 0; out = []; cur = (0.0, 0.0); start = (0.0, 0.0); cmd = None
    def nums(n):
        nonlocal i
        v = []
        while len(v) < n and i < len(toks) and toks[i][1]: v.append(float(toks[i][1])); i += 1
        return v if len(v) == n else None
    while i < len(toks):
        if toks[i][0]: cmd = toks[i][0]; i += 1
        if cmd in 'Zz': out.append(('Z',)); cur = start; continue
        rel = cmd.islower(); c = cmd.upper(); ox, oy = cur if rel else (0.0, 0.0)
        if c == 'M':
            v = nums(2)
            if not v: break
            cur = (ox + v[0], oy + v[1]); start = cur; out.append(('M',) + cur); cmd = 'l' if rel else 'L'
        elif c == 'L':
            v = nums(2)
            if not v: break
            cur = (ox + v[0], oy + v[1]); out.append(('L',) + cur)
        elif c == 'H':
            v = nums(1)
            if not v: break
            cur = (ox + v[0], cur[1]); out.append(('L',) + cur)
        elif c == 'V':
            v = nums(1)
            if not v: break
            cur = (cur[0], oy + v[0]); out.append(('L',) + cur)
        elif c == 'C':
            v = nums(6)
            if not v: break
            p = (ox + v[0], oy + v[1], ox + v[2], oy + v[3], ox + v[4], oy + v[5]); cur = (p[4], p[5]); out.append(('C',) + p)
        elif c == 'Q':
            v = nums(4)
            if not v: break
            q1 = (ox + v[0], oy + v[1]); q2 = (ox + v[2], oy + v[3]); p0 = cur
            out.append(('C', p0[0] + 2 / 3 * (q1[0] - p0[0]), p0[1] + 2 / 3 * (q1[1] - p0[1]), q2[0] + 2 / 3 * (q1[0] - q2[0]), q2[1] + 2 / 3 * (q1[1] - q2[1]), q2[0], q2[1])); cur = q2
        else: break
    return out

def circle_cmds(cx, cy, r):
    k = 0.5522847498 * r
    return [('M', cx + r, cy), ('C', cx + r, cy + k, cx + k, cy + r, cx, cy + r), ('C', cx - k, cy + r, cx - r, cy + k, cx - r, cy),
            ('C', cx - r, cy - k, cx - k, cy - r, cx, cy - r), ('C', cx + k, cy - r, cx + r, cy - k, cx + r, cy), ('Z',)]

def _style(el, inherited):
    st = dict(inherited)
    for k in ('fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity'):
        if el.get(k) is not None: st[k] = el.get(k)
    return st

def load(path):
    """-> dict(vb=(w,h), subpaths=[[cmd...]] in viewBox units, fill=color|None, stroke=color|None, stroke_w=viewBox units)"""
    root = ET.parse(path).getroot(); strip = lambda t: t.split('}')[-1]
    vb = [float(x) for x in re.split(r'[ ,]+', root.get('viewBox').strip())] if root.get('viewBox') else [0, 0, float(root.get('width', 100)), float(root.get('height', 100))]
    subs = []; info = dict(fill=None, stroke=None, sw=0.0)
    def walk(el, st):
        st = _style(el, st); tag = strip(el.tag)
        if tag == 'path' and el.get('d'):
            tx, ty, sx, sy = parse_transform(el.get('transform'))
            cm = path_cmds(el.get('d')); out = []
            for c in cm:
                if c[0] == 'Z': out.append(c)
                else: out.append((c[0],) + tuple(v for j, v in enumerate(c[1:])))
            mapped = []
            for c in out:
                if c[0] == 'Z': mapped.append(c); continue
                xs = c[1::2]; ys = c[2::2]
                mapped.append((c[0],) + tuple(sum(([tx + x * sx, ty + y * sy] for x, y in zip(xs, ys)), [])))
            subs.append(mapped); info['sw_scale'] = abs(sx)
            _paint(st, info)
        elif tag == 'circle':
            cm = circle_cmds(float(el.get('cx', 0)), float(el.get('cy', 0)), float(el.get('r', 0))); subs.append(cm); info['sw_scale'] = 1; _paint(st, info)
        elif tag == 'rect':
            x, y, w, h = (float(el.get(k, 0)) for k in ('x', 'y', 'width', 'height')); subs.append([('M', x, y), ('L', x + w, y), ('L', x + w, y + h), ('L', x, y + h), ('Z',)]); info['sw_scale'] = 1; _paint(st, info)
        for ch in el: walk(ch, st)
    walk(root, dict(fill='#000000'))
    # split compound paths into one sub-path per M
    flat = []
    for sp in subs:
        cur = []
        for c in sp:
            if c[0] == 'M' and cur: flat.append(cur); cur = []
            cur.append(c)
        if cur: flat.append(cur)
    info.update(vb=(vb[2], vb[3]), vb0=(vb[0], vb[1]), subpaths=flat); return info

def _paint(st, info):
    f = parse_color(st.get('fill')); s = parse_color(st.get('stroke'))
    if f: f['a'] = float(st.get('fill-opacity', 1))
    if s: s['a'] = float(st.get('stroke-opacity', 1))
    info['fill'] = f; info['stroke'] = s; info['sw'] = float(st.get('stroke-width', 1)) * info.get('sw_scale', 1)

def fractions(info):
    """sub-paths with coordinates as fractions (0..1) of the viewBox"""
    w, h = info['vb']; x0, y0 = info['vb0']; out = []
    for sp in info['subpaths']:
        o = []
        for c in sp:
            if c[0] == 'Z': o.append(c); continue
            v = list(c[1:]); o.append((c[0],) + tuple(((v[j] - x0) / w if j % 2 == 0 else (v[j] - y0) / h) for j in range(len(v))))
        out.append(o)
    return out
