"""Structural component and layout extraction from Google Slides page JSON (the full presentations.get slides).

A component is an arrangement that recurs: a container with things inside it, or a block of text, rules and pictures that
sit close together, with the same members in the same relative places on at least three slides. Text that varies between
instances becomes a slot, named by its place in the type hierarchy; text that never varies stays fixed.

Pipeline: flatten each slide (groups resolved) -> separate master chrome (identical on many slides) -> cluster the rest
(containers first, then proximity) -> describe each cluster by a signature of member roles and relative geometry ->
group clusters across slides -> name, find slots -> preview from the first instance, rendered by gslides2claude.
Slide layouts are the same idea one level up: slides grouped by what they contain.

Every threshold is a constant below so the behaviour can be tuned against a deck, not guessed."""
from __future__ import annotations
import copy, json, html
from collections import Counter, defaultdict
from . import gslides2claude as G

PX = G.PX
PT = G.PT
MIN_INSTANCES = 3          # a pattern must recur at least this often to be a component
PROXIMITY = 40             # px: free elements closer than this belong to one block
CHROME_SHARE = 0.25        # an element identical on this share of slides is master chrome
REL_TOL = 0.12             # relative position tolerance inside a cluster (fraction of its size)
SIZE_TOL = 0.18            # cluster size tolerance between instances
MAX_COMPONENTS = 10
BIG_SLIDE = 0.8            # a cluster covering this share of the slide is the slide body, not a component


# ------------------------------------------------------------------ flatten
def _compose(parent, child):
    ps, cs = parent, child
    out = dict(cs)
    out['scaleX'] = cs.get('scaleX', 0) * ps.get('scaleX', 0)
    out['scaleY'] = cs.get('scaleY', 0) * ps.get('scaleY', 0)
    out['translateX'] = cs.get('translateX', 0) * ps.get('scaleX', 0) + ps.get('translateX', 0)
    out['translateY'] = cs.get('translateY', 0) * ps.get('scaleY', 0) + ps.get('translateY', 0)
    return out


def flatten(slide):
    out = []

    def walk(pes, parent=None):
        for e in pes:
            e = copy.deepcopy(e)
            if parent:
                e['transform'] = _compose(parent, e.get('transform', {}))
            if 'elementGroup' in e:
                walk(e['elementGroup'].get('children', []), e.get('transform', {}))
                continue
            out.append(e)
    walk(slide.get('pageElements', []))
    return out


def _col(c):
    if not c:
        return None
    c = c.get('opaqueColor', c.get('color', c))
    r = c.get('rgbColor')
    if r is not None:
        return '#%02x%02x%02x' % tuple(int(round(r.get(k, 0) * 255)) for k in ('red', 'green', 'blue'))
    return c.get('themeColor')


def describe(e):
    """Compact facts about one page element, geometry in px."""
    t = e.get('transform', {})
    sz = e.get('size', {})
    W, H = sz.get('width', {}).get('magnitude', 0), sz.get('height', {}).get('magnitude', 0)
    if 'line' in e:
        ends = [((t.get('scaleX', 0) * px + t.get('shearX', 0) * py + t.get('translateX', 0)) * PX,
                 (t.get('shearY', 0) * px + t.get('scaleY', 0) * py + t.get('translateY', 0)) * PX) for px, py in ((0, 0), (W, H))]
        x, y = min(p[0] for p in ends), min(p[1] for p in ends)
        w, h = abs(ends[1][0] - ends[0][0]), abs(ends[1][1] - ends[0][1])
        lp = e['line'].get('lineProperties', {})
        return dict(kind='line', x=x, y=y, w=w, h=h, fill=None, stroke=_col(lp.get('lineFill', {}).get('solidFill')),
                    weight=round(lp.get('weight', {}).get('magnitude', 9525) * PX, 1), runs=[], text='', radius=0, raw=e)
    x, y = t.get('translateX', 0) * PX, t.get('translateY', 0) * PX
    w, h = W * abs(t.get('scaleX', 0)) * PX, H * abs(t.get('scaleY', 0)) * PX
    d = dict(kind='shape', x=x, y=y, w=w, h=h, fill=None, stroke=None, weight=0, runs=[], text='', radius=0, raw=e, shapetype='')
    if 'image' in e:
        d['kind'] = 'image'
        return d
    if 'table' in e:
        d['kind'] = 'table'
        return d
    sh = e.get('shape')
    if not sh:
        d['kind'] = 'other'
        return d
    sp = sh.get('shapeProperties', {})
    st = sh.get('shapeType', '')
    d['shapetype'] = st
    bg = sp.get('shapeBackgroundFill', {})
    if bg.get('propertyState') != 'NOT_RENDERED' and bg.get('solidFill'):
        d['fill'] = _col(bg['solidFill'])
    ol = sp.get('outline', {})
    if ol and ol.get('propertyState') != 'NOT_RENDERED' and ol.get('outlineFill', {}).get('solidFill'):
        d['stroke'] = _col(ol['outlineFill']['solidFill'])
        d['weight'] = round(ol.get('weight', {}).get('magnitude', 9525) * PX, 1)
    d['radius'] = {'ROUND_RECTANGLE': min(w, h) / 6.0, 'ELLIPSE': min(w, h) / 2.0}.get(st, 0)
    for te in sh.get('text', {}).get('textElements', []):
        tr = te.get('textRun')
        if not tr or not tr.get('content', '').strip():
            continue
        s = tr.get('style', {})
        wf = s.get('weightedFontFamily', {})
        d['runs'].append(dict(text=tr['content'].strip(), px=round(s.get('fontSize', {}).get('magnitude', 12) * PT, 1),
                              weight=wf.get('weight', 400), colour=_col(s.get('foregroundColor')),
                              font=wf.get('fontFamily') or s.get('fontFamily')))
    d['text'] = ' '.join(r['text'] for r in d['runs'])
    if d['runs']:
        d['kind'] = 'text' if not (d['fill'] or d['stroke']) else 'panel'
    elif d['fill'] or d['stroke']:
        d['kind'] = 'box'
    else:
        d['kind'] = 'empty'
    return d


def _sizeclass(px):
    return int(round(px / 4.0) * 4)


def _role(d):
    """What a member is, independent of position and wording."""
    if d['kind'] in ('text', 'panel'):
        r = max(d['runs'], key=lambda r: len(r['text']))
        return ('T', _sizeclass(r['px']), r['weight'], r['colour'], d['fill'] if d['kind'] == 'panel' else None)
    if d['kind'] == 'line':
        return ('L', d['weight'], d['stroke'])
    if d['kind'] == 'box':
        return ('B', d['shapetype'], d['fill'], d['stroke'], int(d['radius'] > 0))
    return (d['kind'],)


# ------------------------------------------------------------------ chrome
def find_chrome(slides_desc, n):
    """Elements that repeat identically (same place, same text) on many slides are master chrome."""
    c = Counter()
    for sd in slides_desc:
        seen = set()
        for d in sd:
            k = (d['kind'], round(d['x'] / 8), round(d['y'] / 8), round(d['w'] / 8), round(d['h'] / 8), d['text'])
            if k not in seen:
                c[k] += 1
                seen.add(k)
    chrome = {k for k, v in c.items() if v >= max(3, CHROME_SHARE * n) and k[5] != ''}
    return chrome


def _is_chrome(d, chrome):
    return (d['kind'], round(d['x'] / 8), round(d['y'] / 8), round(d['w'] / 8), round(d['h'] / 8), d['text']) in chrome


# ------------------------------------------------------------------ clusters
def clusters_for(slide_desc, canvas=(1920, 1080)):
    """Containers with their contents, then proximity blocks for what is left."""
    area = canvas[0] * canvas[1]
    els = [d for d in slide_desc if d['kind'] not in ('empty', 'other')]
    # containers: a filled or outlined box/panel big enough to hold something
    cont = [d for d in els if d['kind'] in ('box', 'panel') and d['w'] >= 100 and d['h'] >= 40 and d['w'] * d['h'] < BIG_SLIDE * area]
    cont.sort(key=lambda d: d['w'] * d['h'])
    owner = {}
    for i, e in enumerate(els):
        cx, cy = e['x'] + e['w'] / 2, e['y'] + e['h'] / 2
        for c in cont:
            if c is e:
                continue
            if c['x'] <= cx <= c['x'] + c['w'] and c['y'] <= cy <= c['y'] + c['h'] and (e['w'] * e['h'] < c['w'] * c['h']):
                owner[id(e)] = c
                break      # smallest container wins (list is sorted by area)
    groups = defaultdict(list)
    for e in els:
        o = owner.get(id(e))
        if o is not None:
            groups[id(o)].append(e)
    out = []
    for c in cont:
        mem = groups.get(id(c))
        if mem:
            out.append(dict(kind='container', members=[c] + mem))
        elif c['kind'] == 'panel':
            out.append(dict(kind='container', members=[c]))     # a panel holding its own text
    # free elements: proximity blocks
    free = [e for e in els if id(e) not in owner and not (e in cont)]
    seen, comp = set(), []
    for i, a in enumerate(free):
        if i in seen:
            continue
        stack, blob = [i], []
        seen.add(i)
        while stack:
            j = stack.pop()
            blob.append(free[j])
            b = free[j]
            for k, c in enumerate(free):
                if k in seen:
                    continue
                if (c['x'] < b['x'] + b['w'] + PROXIMITY and c['x'] + c['w'] > b['x'] - PROXIMITY and
                        c['y'] < b['y'] + b['h'] + PROXIMITY and c['y'] + c['h'] > b['y'] - PROXIMITY):
                    seen.add(k)
                    stack.append(k)
        comp.append(blob)
    for blob in comp:
        if len(blob) >= 2:
            out.append(dict(kind='block', members=blob))
    res = []
    for c in out:
        m = c['members']
        x0, y0 = min(e['x'] for e in m), min(e['y'] for e in m)
        x1, y1 = max(e['x'] + e['w'] for e in m), max(e['y'] + e['h'] for e in m)
        c['bbox'] = (x0, y0, x1 - x0, y1 - y0)
        if c['bbox'][2] * c['bbox'][3] >= BIG_SLIDE * area or c['bbox'][2] < 40 or c['bbox'][3] < 20:
            continue
        res.append(c)
    return res


def signature(c):
    x0, y0, W, H = c['bbox']
    mem = sorted(c['members'], key=lambda e: (round(e['y'] / 12), e['x']))
    c['ordered'] = mem
    roles = tuple(sorted(str(_role(e)) for e in mem))
    rel = [((e['x'] - x0) / max(W, 1), (e['y'] - y0) / max(H, 1), e['w'] / max(W, 1), e['h'] / max(H, 1)) for e in mem]
    return roles, rel


def _similar(a, b):
    (ra, la), (rb, lb) = a, b
    if ra != rb:
        return False
    ca, cb = a_c(a), a_c(b)
    return True


def a_c(x):
    return x


def group_clusters(items):
    """items: [(slide_no, cluster)]. Same member roles, similar size, similar relative layout."""
    by_role = defaultdict(list)
    for sn, c in items:
        roles, rel = signature(c)
        c['rel'], c['roles'], c['slide'] = rel, roles, sn
        by_role[roles].append(c)
    groups = []
    for roles, cs in by_role.items():
        placed = []
        for c in cs:
            for g in placed:
                r = g[0]
                if (abs(c['bbox'][2] - r['bbox'][2]) <= SIZE_TOL * max(r['bbox'][2], 1) + 8 and
                        abs(c['bbox'][3] - r['bbox'][3]) <= SIZE_TOL * max(r['bbox'][3], 1) + 8 and
                        all(max(abs(p - q) for p, q in zip(a, b)) <= REL_TOL for a, b in zip(c['rel'], r['rel']))):
                    g.append(c)
                    break
            else:
                placed.append([c])
        groups += placed
    return groups


# ------------------------------------------------------------------ naming and slots
def name_group(g, taken):
    c = g[0]
    mem = c['ordered']
    kinds = Counter(e['kind'] for e in mem)
    texts = [e for e in mem if e['kind'] in ('text', 'panel')]
    rounded = any(e['radius'] > 0 and e['kind'] in ('box', 'panel') for e in mem)
    nums = [e for e in texts if len(e['text']) <= 4 and e['runs'][0]['px'] >= 48]
    if c['kind'] == 'container' and kinds['panel'] and not kinds['text'] and len(mem) == 1:
        nm = 'Pill' if rounded and c['bbox'][3] <= 120 else 'Button' if c['bbox'][3] <= 120 else 'Panel'
    elif c['kind'] == 'container' and texts:
        nm = 'Stat card' if nums else ('Card' if rounded else 'Boxed text')
    elif kinds['box'] and len(texts) == 1 and len(mem) == 2 and min(e['w'] for e in mem if e['kind'] == 'box') < 60:
        nm = 'Key item'
    elif kinds['line'] and texts and not kinds['box']:
        nm = 'Titled block' if len(texts) >= 2 else 'Labelled rule'
    elif kinds['image'] and texts:
        nm = 'Image with text'
    elif len(texts) >= 3:
        nm = 'Text stack'
    elif len(texts) == 2 and not kinds['box'] and not kinds['image'] and not kinds['line']:
        a, b = sorted(texts, key=lambda e: -e['runs'][0]['px'])
        short = lambda e: len(e['text']) <= 18
        if a['runs'][0]['px'] >= 1.6 * b['runs'][0]['px'] and short(a) and any(ch.isdigit() for ch in a['text']):
            nm = 'Stat'
        elif short(a) and short(b):
            nm = 'Name and role' if a['runs'][0]['weight'] >= b['runs'][0]['weight'] else 'Label and value'
        else:
            nm = 'Heading and text'
    elif kinds['image'] and not texts:
        nm = 'Avatar' if any(e['kind'] == 'box' and e['radius'] > 0.4 * min(e['w'], e['h']) for e in mem) else 'Picture frame'
    elif kinds['box'] and not texts and len(mem) <= 3:
        nm = 'Swatch' if all(e['kind'] == 'box' for e in mem) else 'Shape group'
    else:
        nm = 'Block'
    base, i = nm, 2
    while nm in taken:
        nm, i = '%s %d' % (base, i), i + 1
    taken.add(nm)
    return nm


def slots(g):
    """For each member position: the texts it holds across instances. Varying text is a slot."""
    c0 = g[0]['ordered']
    out = []
    mx = max([e['runs'][0]['px'] for e in c0 if e['runs']] or [0])
    for i, m in enumerate(c0):
        if not m['runs']:
            continue
        vals = []
        for inst in g:
            o = inst['ordered']
            if i < len(o):
                vals.append(o[i]['text'])
        px = m['runs'][0]['px']
        role = 'title' if px >= mx * 0.9 else 'caption' if px <= mx * 0.55 else 'body'
        out.append(dict(index=i, role=role, px=px, fixed=len(set(vals)) == 1, examples=vals[:3],
                        colour=m['runs'][0]['colour'], weight=m['runs'][0]['weight']))
    return out


# ------------------------------------------------------------------ preview
def preview_html(c, conv):
    """Render the first instance's members with the gslides2claude converter, re-based to the cluster origin."""
    x0, y0, W, H = c['bbox']
    parts = []
    for m in c['ordered']:
        e = copy.deepcopy(m['raw'])
        t = e.setdefault('transform', {})
        t['translateX'] = t.get('translateX', 0) - x0 / PX
        t['translateY'] = t.get('translateY', 0) - y0 / PX
        parts.append(conv.element(e, 0))
    body = '\n'.join(p for p in parts if p).replace('<img src="IMG:', '<img data-missing="IMG:')
    return W, H, body


# ------------------------------------------------------------------ layouts
def slide_layout_key(sd, bg, clusters, chrome):
    texts = [d for d in sd if d['kind'] in ('text', 'panel') and not _is_chrome(d, chrome)]
    biggest = max([r['px'] for d in texts for r in d['runs']] or [0])
    pics = sum(1 for d in sd if d['kind'] == 'image')
    full_pic = any(d['kind'] == 'image' and d['w'] * d['h'] > 0.5 * 1920 * 1080 for d in sd)
    return (bg, 'photo' if (full_pic or pics >= 2) else 'img' if pics else 'noimg',
            'xl' if biggest >= 200 else 'l' if biggest >= 100 else 'm' if biggest >= 40 else 's',
            min(len(texts), 4), min(len(clusters), 3))


def layout_name(k):
    bg, pic, big, ntext, ncl = k
    face = {'photo-bg': 'photo background', 'dark': 'dark', 'light': 'light'}[bg]
    pics = {'photo': 'with pictures', 'img': 'with one picture', 'noimg': 'text only'}[pic]
    size = {'xl': 'huge headline', 'l': 'large headline', 'm': 'medium text', 's': 'small text'}[big]
    return '%s, %s, %s, %d text block%s%s' % (face.capitalize(), pics, size, ntext, '' if ntext == 1 else 's',
                                               (', %d component%s' % (ncl, '' if ncl == 1 else 's')) if ncl else '')


# ------------------------------------------------------------------ main
def extract(slides_json, masters_json, outdir=None, canvas=(1920, 1080)):
    data = json.load(open(slides_json))['content']['slides']
    masters = json.load(open(masters_json))['content'] if masters_json else {}
    scheme = {}
    for mm in masters.get('masters', []):
        for c in mm.get('pageProperties', {}).get('colorScheme', {}).get('colors', []):
            rgb = c.get('color', {})
            scheme.setdefault(c['type'], '#%02x%02x%02x' % tuple(int(round(rgb.get(k, 0) * 255)) for k in ('red', 'green', 'blue')))
    n = len(data)
    descs = [[describe(e) for e in flatten(s)] for s in data]
    chrome = find_chrome(descs, n)
    conv0 = G.Conv(scheme, '/tmp/d2s-fontcache')
    slide_bg = []
    for sl in data:
        f = sl.get('pageProperties', {}).get('pageBackgroundFill', {})
        slide_bg.append(conv0.col(f['solidFill']) if 'solidFill' in f else None)
    items, per_slide = [], []
    for i, sd in enumerate(descs):
        keep = [d for d in sd if not _is_chrome(d, chrome)]
        cl = clusters_for(keep, canvas)
        per_slide.append(cl)
        items += [(i, c) for c in cl]
    groups = [g for g in group_clusters(items) if len({c['slide'] for c in g}) >= MIN_INSTANCES or len(g) >= MIN_INSTANCES]
    groups = [g for g in groups if len({c['slide'] for c in g}) >= 2 or len(g) >= 4]   # recurs across slides, or many times on one
    groups.sort(key=lambda g: (-len({c['slide'] for c in g}), -len(g)))
    taken, comps = set(), []
    conv = G.Conv(scheme, '/tmp/d2s-fontcache')
    for g in groups[:MAX_COMPONENTS]:
        nm = name_group(g, taken)
        sl = slots(g)
        w, h, body = preview_html(g[0], conv)
        comps.append(dict(example_slide=g[0]['slide'] + 1, bbox=[round(v) for v in g[0]['bbox']], name=nm, all_slides=sorted({x['slide'] + 1 for x in g}), bg=slide_bg[g[0]['slide']] or '#ffffff', instances=len(g), slides=sorted({c['slide'] + 1 for c in g})[:12], n_slides=len({c['slide'] for c in g}),
                          members=len(g[0]['members']), size=[round(w), round(h)], slots=sl, preview_body=body,
                          roles=[list(map(str, r)) if isinstance(r, tuple) else r for r in g[0]['roles']]))
    # layouts: slides grouped by what they contain
    lay = defaultdict(list)
    for i, sd in enumerate(descs):
        fill = data[i].get('pageProperties', {}).get('pageBackgroundFill', {})
        bg = 'photo-bg' if 'stretchedPictureFill' in fill else ('dark' if _lum_bg(fill, scheme) < 0.35 else 'light')
        lay[slide_layout_key(sd, bg, per_slide[i], chrome)].append(i + 1)
    layouts = sorted(([dict(name=layout_name(k), key=list(k), slides=v, count=len(v)) for k, v in lay.items() if len(v) >= 3]), key=lambda x: -x['count'])
    atoms = find_atoms(descs, chrome, slide_bg, scheme, conv)
    return dict(slides=n, chrome=len(chrome), slide_bg=slide_bg, components=comps, atoms=atoms, layouts=layouts,
                coverage=dict(clustered=sum(len(c) for c in per_slide), grouped=sum(len(g) for g in groups)))


def _lum_bg(fill, scheme):
    f = fill.get('solidFill')
    if not f:
        return 1.0
    c = f.get('color', {})
    r = c.get('rgbColor')
    if r is None:
        return 1.0 if c.get('themeColor') in ('LIGHT1', 'BACKGROUND1', 'LIGHT2') else 0.0
    return 0.2126 * r.get('red', 0) + 0.7152 * r.get('green', 0) + 0.0722 * r.get('blue', 0)


# ------------------------------------------------------------------ atoms
ATOM_MIN_SLIDES = 4        # an atom is a single element used on at least this many slides in the same style and place
CANVAS = (1920, 1080)


def place_bin(d):
    return (int(d['x'] / CANVAS[0] * 8), int(d['y'] / CANVAS[1] * 8))


def atom_key(d):
    """The style of one element, without where it sits; elements with the same key are the same atom, placements are recorded apart."""
    if d['kind'] in ('text', 'panel') and d['runs']:
        r = max(d['runs'], key=lambda r: len(r['text']))
        return ('T', _sizeclass(r['px']), r['weight'], r['colour'])
    if d['kind'] == 'line':
        return ('L', round(d['weight']), d['stroke'], 'h' if d['w'] >= d['h'] else 'v')
    if d['kind'] == 'image':
        return ('I', int(d['w'] / 60), int(d['h'] / 60))
    if d['kind'] == 'box':
        return ('B', d['shapetype'], d['fill'], d['stroke'], int(d['w'] / 24), int(d['h'] / 24))
    return None


def atom_name(key, d, ink_like):
    k = key[0]
    W, H = CANVAS
    if k == 'T':
        px, colour = key[1], key[3]
        if d['y'] < 0.14 * H and px <= 32 and colour not in ink_like:
            return 'Eyebrow'
        if d['y'] > 0.8 * H and px <= 32:
            return 'Footnote'
        if px >= 200:
            return 'Display figure'
        if px >= 100:
            return 'Display headline'
        if len(d['text']) <= 4 and d['x'] < 0.25 * W:
            return 'Marker'
        if px >= 56:
            return 'Headline'
        if px >= 36:
            return 'Title'
        return 'Body text' if px >= 24 else 'Small text'
    if k == 'L':
        if key[3] == 'v':
            return 'Vertical rule'
        return 'Hairline rule' if d['weight'] <= 3 and d['w'] >= 0.5 * W else 'Progress rule' if d['weight'] >= 4 else 'Short rule'
    if k == 'I':
        if d['w'] >= 0.9 * W and d['h'] >= 0.9 * H:
            return 'Full-bleed picture'
        return 'Logo' if d['w'] <= 300 and d['h'] <= 300 and d['y'] < 0.2 * H and d['x'] < 0.2 * W else 'Picture'
    if k == 'B':
        if d['w'] >= 0.9 * W and d['h'] >= 0.9 * H:
            return 'Backdrop'
        return 'Dot' if d['radius'] >= 0.45 * min(d['w'], d['h']) else 'Swatch' if d['w'] < 120 and d['h'] < 120 else 'Panel shape'
    return 'Element'


def find_atoms(descs, chrome, slide_bg, scheme, conv):
    by = defaultdict(list)
    for si, sd in enumerate(descs):
        for d in sd:
            if _is_chrome(d, chrome) or d['kind'] in ('empty', 'other', 'table'):
                continue
            if not (0 <= d['x'] + d['w'] / 2 <= CANVAS[0] and 0 <= d['y'] + d['h'] / 2 <= CANVAS[1]):
                continue
            k = atom_key(d)
            if k:
                by[k].append((si, d))
    cnt = Counter(k[3] for k, v in by.items() if k[0] == 'T' for _ in v)
    def grey(c):
        try:
            r, g, b = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
            return max(r, g, b) - min(r, g, b) < 24
        except Exception:
            return False
    ink_like = {c for c, _ in cnt.most_common(1)} | {c for c in cnt if c and grey(c)}   # the main text colour and every grey; a saturated colour is an accent
    atoms, taken = [], set()
    for k, v in sorted(by.items(), key=lambda kv: -len({s for s, _ in kv[1]})):
        slides = {s for s, _ in v}
        if len(slides) < ATOM_MIN_SLIDES:
            continue
        pl = Counter(place_bin(d) for _, d in v)
        (mb, mc), = pl.most_common(1)
        if k[0] == 'T' and mc / len(v) < 0.5:
            continue   # text that moves around is just a type style, already a token; an atom is something placed by convention
        modal = next((si, d) for si, d in v if place_bin(d) == mb)
        si, d = modal
        nm = atom_name(k, d, ink_like)
        base, i = nm, 2
        while nm in taken:
            nm, i = '%s %d' % (base, i), i + 1
        taken.add(nm)
        e = copy.deepcopy(d['raw'])
        t = e.setdefault('transform', {})
        t['translateX'] = 0
        t['translateY'] = 0
        body = conv.element(e, 0).replace('<img src="IMG:', '<img data-missing="IMG:')
        examples = sorted({x['text'] for _, x in v if x['text']})[:3]
        places = [dict(bin=list(b), n=c, x=round(next(x['x'] for _, x in v if place_bin(x) == b)), y=round(next(x['y'] for _, x in v if place_bin(x) == b))) for b, c in pl.most_common(6)]
        atoms.append(dict(example_slide=si + 1, bbox=[round(d['x']), round(d['y']), round(d['w']), round(max(d['h'], 4))], name=nm, key=k, bg=slide_bg[si] or '#ffffff', instances=len(v), n_slides=len(slides), all_slides=sorted(s + 1 for s in slides),
                          members=1, size=[round(d['w']), round(max(d['h'], 4))], preview_body=body, kind='atom', places=places,
                          place=(places[0]['x'], places[0]['y']), consistent=round(mc / len(v), 2), examples=examples,
                          slots=[dict(role='text', px=d['runs'][0]['px'], weight=d['runs'][0]['weight'], colour=d['runs'][0]['colour'], fixed=len(examples) <= 1, examples=examples)] if d['runs'] else []))
    return atoms


def composition(desc, atoms, chrome):
    """How one slide is built: atoms used (and whether each sits where that atom usually sits), versus free content."""
    by_key = {a['key']: a for a in atoms}
    used, free = [], []
    for d in desc:
        if _is_chrome(d, chrome) or d['kind'] in ('empty', 'other', 'table'):
            continue
        if not (0 <= d['x'] + d['w'] / 2 <= CANVAS[0] and 0 <= d['y'] + d['h'] / 2 <= CANVAS[1]):
            continue
        k = atom_key(d)
        if k in by_key:
            a = by_key[k]
            usual = any(abs(p['x'] - d['x']) < 0.06 * CANVAS[0] and abs(p['y'] - d['y']) < 0.06 * CANVAS[1] for p in a['places'])
            used.append(dict(atom=a['name'], x=round(d['x']), y=round(d['y']), usual=usual, text=d['text'][:40]))
        elif k:
            free.append(dict(role=d['kind'] if d['kind'] != 'panel' else 'text', x=round(d['x']), y=round(d['y']), w=round(d['w']), h=round(d['h']), text=d['text'][:40]))
    return used, free


# ------------------------------------------------------------------ seeds and curation
def _mkey(d):
    """Role of a member for matching: style, not wording or place."""
    if d['kind'] in ('text', 'panel') and d['runs']:
        r = max(d['runs'], key=lambda r: len(r['text']))
        return ('T', _sizeclass(r['px']), r['weight'], r['colour'])
    if d['kind'] == 'line':
        return ('L', round(d['weight']), d['stroke'], 'h' if d['w'] >= d['h'] else 'v')
    if d['kind'] == 'image':
        return ('I',)
    if d['kind'] == 'box':
        return ('B', d['fill'], d['stroke'], int(d['radius'] > 0))
    return None


def seed_members(descs, slide, bbox):
    x0, y0, x1, y1 = bbox
    out = []
    for d in descs[slide - 1]:
        cx, cy = d['x'] + d['w'] / 2, d['y'] + d['h'] / 2
        if x0 <= cx <= x1 and y0 <= cy <= y1 and _mkey(d):
            out.append(d)
    return out


def find_instances(members, descs, chrome, pos_tol=30, size_tol=0.3):
    """Anchored search: for every element that looks like the seed's anchor, check that the other members sit where the seed says."""
    anchor = max(members, key=lambda d: d['w'] * d['h'])
    akey = _mkey(anchor)
    inst = []
    for si, sd in enumerate(descs):
        used = set()
        for a in sd:
            if _mkey(a) != akey or id(a) in used or _is_chrome(a, chrome):
                continue
            got = [a]
            ok = True
            for m in members:
                if m is anchor:
                    continue
                tx, ty = a['x'] + (m['x'] - anchor['x']), a['y'] + (m['y'] - anchor['y'])
                hit = next((d for d in sd if d not in got and _mkey(d) == _mkey(m) and abs(d['x'] - tx) <= pos_tol and abs(d['y'] - ty) <= pos_tol
                            and abs(d['w'] - m['w']) <= size_tol * max(m['w'], 20) + pos_tol), None)
                if hit is None:
                    ok = False
                    break
                got.append(hit)
            if ok:
                inst.append((si, got))
                used.update(id(g) for g in got)
    return inst


def seeded_component(spec, descs, chrome, slide_bg, conv):
    mem = seed_members(descs, spec['slide'], spec['bbox'])
    if not mem:
        return None
    inst = find_instances(mem, descs, chrome, size_tol=spec.get('size_tol', 0.3))
    if not inst:
        return None
    first = next((g for si, g in inst if si == spec['slide'] - 1), inst[0][1])
    x0, y0 = min(d['x'] for d in first), min(d['y'] for d in first)
    x1, y1 = max(d['x'] + d['w'] for d in first), max(d['y'] + d['h'] for d in first)
    parts = []
    for d in first:
        e = copy.deepcopy(d['raw'])
        t = e.setdefault('transform', {})
        t['translateX'] = t.get('translateX', 0) - x0 / PX
        t['translateY'] = t.get('translateY', 0) - y0 / PX
        parts.append(conv.element(e, 0))
    body = '\n'.join(p for p in parts if p).replace('<img src="IMG:', '<img data-missing="IMG:')
    texts = [d for d in first if d['runs']]
    slots = []
    for i, m in enumerate(sorted(texts, key=lambda d: (d['y'], d['x']))):
        vals = []
        for si, g in inst:
            gt = sorted([d for d in g if d['runs']], key=lambda d: (d['y'], d['x']))
            if i < len(gt):
                vals.append(gt[i]['text'])
        mx = max(d['runs'][0]['px'] for d in texts)
        slots.append(dict(role='title' if m['runs'][0]['px'] >= 0.9 * mx else 'body', px=m['runs'][0]['px'], weight=m['runs'][0]['weight'],
                          colour=m['runs'][0]['colour'], fixed=len(set(vals)) == 1, examples=sorted(set(vals))[:3]))
    sl = sorted({si for si, _ in inst})
    return dict(name=spec['name'], kind='block', group=spec.get('group', 'Blocks'), bg=slide_bg[sl[0]] or '#ffffff', instances=len(inst), n_slides=len(sl),
                all_slides=[s + 1 for s in sl], members=len(first), size=[round(x1 - x0), round(y1 - y0)], preview_body=body, slots=slots,
                example_slide=spec['slide'], bbox=[round(x0), round(y0), round(x1 - x0), round(y1 - y0)],
                provenance='seeded by Claude from slide %d, found %d times on %d slides' % (spec['slide'], len(inst), len(sl)), usage=spec.get('usage', ''))


def curate(result, curation, descs, chrome, slide_bg, conv):
    """Apply a reviewed curation: drop what is not a component, rename and merge what is, add seeded components and verify them."""
    keep, drop, rename = curation.get('keep', []), set(curation.get('drop', [])), curation.get('rename', {})
    out, notes = [], []
    pool = {c['name']: c for c in result['atoms'] + result['components']}
    for nm in keep:
        c = pool.get(nm)
        if not c:
            notes.append('keep: %s not found' % nm)
            continue
        c = dict(c)
        c['provenance'] = 'derived; kept after review' + ('' if nm not in rename else ', renamed from "%s"' % nm)
        c['name'] = rename.get(nm, nm)
        c['group'] = curation.get('groups', {}).get(c['name'], 'Elements' if c.get('kind') == 'atom' else 'Blocks')
        c['usage'] = curation.get('usage', {}).get(c['name'], '')
        out.append(c)
    for spec in curation.get('seeds', []):
        c = seeded_component(spec, descs, chrome, slide_bg, conv)
        if not c:
            notes.append('seed %s: not found' % spec['name'])
            continue
        c['verified'] = c['n_slides'] >= 2 or c['instances'] >= 4
        if not c['verified']:
            c['provenance'] += ' (thin evidence: kept because the pattern is recognisable by eye)'
        out.append(c)
    return out, [dict(name=n, why=w) for n, w in curation.get('drop_reasons', {}).items()], notes
