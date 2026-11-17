"""Derive a design system (colour, type scale, grid, spacing, radii, shadows,
layouts) from an existing deck.

Two adapters feed one normalised model, so every derivation is shared:
  * PPTX            (`from_pptx`)   - python-pptx
  * Google Slides   (`from_gslides`) - presentations.get JSON (field-masked)

Normalised element (all geometry in px on a 1920-wide canvas):
  {slide, kind: text|shape|image|line, x, y, w, h, fill, radius, shadow,
   stroke, runs: [{font, px, bold, color, n}], ph}

Everything here is *measured*; nothing is guessed. Each token set carries the
evidence (counts, fit error) so a reader can judge how much to trust it.
"""
from __future__ import annotations
import json, math, re
from collections import Counter, defaultdict

W = 1920.0


def hexcol(r, g, b):
    return '#%02X%02X%02X' % tuple(int(round(max(0, min(1, v)) * 255)) for v in (r, g, b))


# --------------------------------------------------------------------------
# adapters
# --------------------------------------------------------------------------
def from_gslides(slides_json, masters_json=None):
    """slides_json / masters_json: dicts as returned by presentations.get."""
    content = slides_json.get('content', slides_json)
    mc = (masters_json or {}).get('content', masters_json or {})
    scheme = {}
    for m in mc.get('masters', []):
        for c in m.get('pageProperties', {}).get('colorScheme', {}).get('colors', []):
            rgb = c.get('color', {})
            scheme.setdefault(c['type'], hexcol(rgb.get('red', 0), rgb.get('green', 0), rgb.get('blue', 0)))
    # TEXT1/BACKGROUND1 alias DARK1/LIGHT1 etc.
    alias = {'TEXT1': 'DARK1', 'BACKGROUND1': 'LIGHT1', 'TEXT2': 'DARK2', 'BACKGROUND2': 'LIGHT2'}
    for k, v in alias.items():
        scheme.setdefault(k, scheme.get(v))

    def col(c):
        if not c:
            return None
        c = c.get('color', c)
        if 'rgbColor' in c:
            r = c['rgbColor']
            return hexcol(r.get('red', 0), r.get('green', 0), r.get('blue', 0))
        if 'themeColor' in c:
            return scheme.get(c['themeColor'])
        return None

    scale = W / 9144000.0
    page_w = content.get('pageSize', {}).get('width', {}).get('magnitude', 9144000)
    scale = W / page_w
    pt = W / (page_w / 12700.0)  # px per point

    def elems(pe, si, out, base=(1, 0, 0, 1, 0, 0)):
        for e in pe:
            t = e.get('transform', {})
            a, d = t.get('scaleX', 1), t.get('scaleY', 1)
            sz = e.get('size', {})
            w = sz.get('width', {}).get('magnitude', 0) * a * scale
            h = sz.get('height', {}).get('magnitude', 0) * d * scale
            x = t.get('translateX', 0) * scale
            y = t.get('translateY', 0) * scale
            if 'elementGroup' in e:
                # children carry their own absolute-ish transforms relative to group
                kids = e['elementGroup'].get('children', [])
                for k in kids:  # approximate: apply group translate
                    kt = k.setdefault('transform', {})
                    kt['translateX'] = kt.get('translateX', 0) * a + t.get('translateX', 0)
                    kt['translateY'] = kt.get('translateY', 0) * d + t.get('translateY', 0)
                    kt['scaleX'] = kt.get('scaleX', 1) * a
                    kt['scaleY'] = kt.get('scaleY', 1) * d
                elems(kids, si, out)
                continue
            el = dict(slide=si, x=x, y=y, w=w, h=h, fill=None, radius=0, shadow=False,
                      stroke=None, runs=[], ph=None, kind='shape')
            if 'image' in e:
                el['kind'] = 'image'
            elif 'line' in e:
                el['kind'] = 'line'
                lp = e['line'].get('lineProperties', {})
                el['stroke'] = dict(color=col(lp.get('lineFill', {}).get('solidFill')),
                                    w=lp.get('weight', {}).get('magnitude', 0) * scale)
            elif 'shape' in e:
                s = e['shape']
                sp = s.get('shapeProperties', {})
                el['fill'] = col(sp.get('shapeBackgroundFill', {}).get('solidFill'))
                el['alpha'] = sp.get('shapeBackgroundFill', {}).get('solidFill', {}).get('alpha', 1.0)
                ol = sp.get('outline', {})
                if ol and ol.get('outlineFill', {}).get('solidFill'):
                    el['stroke'] = dict(color=col(ol['outlineFill']['solidFill']),
                                        w=ol.get('weight', {}).get('magnitude', 0) * scale)
                el['shadow'] = False  # presentations.get returns a shadow stub on every shape; not evidence
                st = s.get('shapeType', '')
                if st == 'ROUND_RECTANGLE':
                    el['radius'] = min(w, h) * 0.1667
                elif st == 'ELLIPSE':
                    el['radius'] = min(w, h) / 2
                el['ph'] = (s.get('placeholder') or {}).get('type')
                for te in s.get('text', {}).get('textElements', []):
                    tr = te.get('textRun')
                    if not tr or not tr.get('content', '').strip():
                        continue
                    stl = tr.get('style', {})
                    fs = stl.get('fontSize', {}).get('magnitude')
                    if not fs:
                        continue
                    el['runs'].append(dict(font=stl.get('fontFamily'), px=fs * pt,
                                           bold=bool(stl.get('bold')),
                                           color=col(stl.get('foregroundColor')),
                                           n=len(tr['content'].strip())))
                if el['runs']:
                    el['kind'] = 'text'
            out.append(el)

    out = []
    for si, sl in enumerate(content.get('slides', [])):
        elems(sl.get('pageElements', []), si, out)
    layouts = []
    for lay in mc.get('layouts', []):
        items = []
        tmp = []
        elems(lay.get('pageElements', []), 0, tmp)
        for e, raw in zip(tmp, lay.get('pageElements', [])):
            items.append(e)
        layouts.append(dict(name=lay.get('layoutProperties', {}).get('displayName'),
                            master=lay.get('layoutProperties', {}).get('masterObjectId'),
                            items=[i for i in tmp if i['ph'] or i['kind'] != 'shape' or i['fill']]))
    bgs = []
    for lay in mc.get('layouts', []) + mc.get('masters', []):
        f = lay.get('pageProperties', {}).get('pageBackgroundFill', {}).get('solidFill')
        if f and col(f):
            bgs.append(col(f))
    return dict(elements=out, layouts=layouts, nslides=len(content.get('slides', [])), backgrounds=bgs,
                theme=scheme, canvas=(W, page_h(content, scale)))


def page_h(content, scale):
    return content.get('pageSize', {}).get('height', {}).get('magnitude', 5143500) * scale


def from_pptx(path):
    from pptx import Presentation
    from pptx.util import Emu
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    prs = Presentation(path)
    scale = W / prs.slide_width
    pt = W / (prs.slide_width / 12700.0)
    out = []

    from pptx.enum.dml import MSO_FILL

    def rgb(fill):
        try:
            if fill.type == MSO_FILL.SOLID:
                return '#' + str(fill.fore_color.rgb)
        except Exception:
            pass
        return None

    def walk(shapes, si, dx=0, dy=0):
        for sh in shapes:
            if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
                walk(sh.shapes, si, dx, dy)
                continue
            if sh.left is None:
                continue
            el = dict(slide=si, x=(sh.left + dx) * scale, y=(sh.top + dy) * scale,
                      w=sh.width * scale, h=sh.height * scale, fill=None, radius=0,
                      shadow=False, stroke=None, runs=[], ph=None, kind='shape')
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                el['kind'] = 'image'
            else:
                try:
                    el['fill'] = rgb(sh.fill)
                    m_a = re.search(r'<a:solidFill><a:srgbClr val="[0-9A-Fa-f]{6}"><a:alpha val="(\d+)"', sh._element.spPr.xml)
                    el['alpha'] = int(m_a.group(1)) / 100000.0 if m_a else 1.0
                except Exception:
                    pass
                try:
                    if sh.line.fill.type == MSO_FILL.SOLID:
                        el['stroke'] = dict(color='#' + str(sh.line.color.rgb), w=sh.line.width * scale)
                except Exception:
                    pass
                xml = sh._element.xml
                m = re.search(r'prst="roundRect".*?<a:gd name="adj" fmla="val (\d+)"', xml, re.S)
                if m:
                    el['radius'] = min(el['w'], el['h']) * int(m.group(1)) / 100000.0
                elif 'prst="roundRect"' in xml:
                    el['radius'] = min(el['w'], el['h']) * 0.1667
                elif 'prst="ellipse"' in xml:
                    el['radius'] = min(el['w'], el['h']) / 2
                el['shadow'] = 'outerShdw' in xml
                if sh.is_placeholder:
                    el['ph'] = str(sh.placeholder_format.type).split('.')[-1].split(' ')[0]
                if sh.has_text_frame:
                    for p in sh.text_frame.paragraphs:
                        for r in p.runs:
                            if not r.text.strip() or not r.font.size:
                                continue
                            c = None
                            try:
                                c = '#' + str(r.font.color.rgb)
                            except Exception:
                                pass
                            el['runs'].append(dict(font=r.font.name, px=r.font.size.pt * pt,
                                                   bold=bool(r.font.bold), color=c, n=len(r.text.strip())))
                    if el['runs']:
                        el['kind'] = 'text'
            out.append(el)

    bgs = []
    for si, s in enumerate(prs.slides):
        walk(s.shapes, si)
        m_bg = re.search(r'<p:bg>.*?<a:srgbClr val="([0-9A-Fa-f]{6})"', s._element.xml, re.S)
        if m_bg:
            bgs.append('#' + m_bg.group(1).upper())
    layouts = []
    for lay in prs.slide_layouts:
        items = []
        for sh in lay.placeholders:
            if sh.left is None or sh.width is None:
                continue
            items.append(dict(ph=str(sh.placeholder_format.type).split('.')[-1].split(' ')[0],
                              x=sh.left * scale, y=sh.top * scale, w=sh.width * scale, h=sh.height * scale))
        layouts.append(dict(name=lay.name, master=None, items=items))
    return dict(elements=out, layouts=layouts, nslides=len(prs.slides), theme={}, backgrounds=bgs,
                canvas=(W, prs.slide_height * scale))


# --------------------------------------------------------------------------
# derivations
# --------------------------------------------------------------------------
def _lum(h):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _dist(a, b):
    return sum((int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) ** 2 for i in (1, 3, 5)) ** 0.5


def derive_colours(model, merge=10):
    area, chars = Counter(), Counter()
    cw, ch = model['canvas']
    for e in model['elements']:
        a = min(e['w'], cw) * min(e['h'], ch)
        if e['fill'] and a > 40 * 40 and e.get('alpha', 1.0) >= 0.5:
            area[e['fill']] += a
        if e['stroke'] and e['stroke'].get('color'):
            area[e['stroke']['color']] += 1
        for r in e['runs']:
            if r['color']:
                chars[r['color']] += r['n']

    def cluster(counter):
        out = []
        for c, n in counter.most_common():
            for o in out:
                if _dist(c, o['hex']) <= merge:
                    o['n'] += n
                    o['members'].append(c)
                    break
            else:
                out.append(dict(hex=c, n=n, members=[c]))
        return out

    bg = Counter(model.get('backgrounds', []))
    fills, texts = cluster(area), cluster(chars)
    tot_a = sum(o['n'] for o in fills) or 1
    tot_c = sum(o['n'] for o in texts) or 1
    return dict(
        fills=[dict(hex=o['hex'], share=round(o['n'] / tot_a, 4)) for o in fills[:16]],
        text=[dict(hex=o['hex'], share=round(o['n'] / tot_c, 4)) for o in texts[:10]],
        backgrounds=[dict(hex=h, n=n) for h, n in bg.most_common(4)],
    )


def name_colours(cols):
    """Give roles: paper = most common light fill, ink = most common text,
    accents = saturated remaining fills ordered by share."""
    fills = cols['fills']
    text = cols['text']
    roles = {}
    # ink = darkest text colour that carries >=10% of characters; mute = next most used
    dark = sorted([t for t in text if t['share'] >= 0.10], key=lambda t: _lum(t['hex']))
    if dark:
        roles['ink'] = dark[0]['hex']
    elif text:
        roles['ink'] = text[0]['hex']
    rest = [t for t in text if t['hex'] != roles.get('ink')]
    if rest:
        roles['mute'] = rest[0]['hex']
    if cols.get('backgrounds'):
        roles['paper'] = cols['backgrounds'][0]['hex']
    else:
        light = [f for f in fills if _lum(f['hex']) > 0.85]
        if light:
            roles['paper'] = light[0]['hex']
    n = 0
    seen = set(roles.values())
    surf = [f for f in fills if _lum(f['hex']) > 0.97 and f['hex'] not in seen]
    if surf:
        roles['surface'] = surf[0]['hex']
        seen.add(surf[0]['hex'])
    for f in fills + text:
        h = f['hex']
        if h in seen:
            continue
        r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        sat = max(r, g, b) - min(r, g, b)
        if sat > 0.25:
            n += 1
            roles['accent-%d' % n] = h
        seen.add(h)
    return roles


WEIGHTS = {'Thin': 100, 'ExtraLight': 200, 'Light': 300, 'Medium': 500, 'SemiBold': 600,
           'ExtraBold': 800, 'Black': 900}


def split_font(name, bold=False):
    """'Inter SemiBold' -> ('Inter', 600). Mirrors config.WEIGHT_SUFFIX."""
    if not name:
        return name, 700 if bold else 400
    for suf, w in WEIGHTS.items():
        if name.endswith(' ' + suf):
            return name[: -len(suf) - 1], w
    return name, 700 if bold else 400


def derive_type(model):
    by = Counter()
    fam = Counter()
    wts = Counter()
    for e in model['elements']:
        for r in e['runs']:
            f, w = split_font(r['font'], r['bold'])
            key = (round(r['px'] * 2) / 2, f, w >= 600)
            by[key] += r['n']
            fam[f] += r['n']
            wts[(f, w)] += r['n']
    sizes = Counter()
    for (px, f, b), n in by.items():
        sizes[px] += n
    tot = sum(sizes.values()) or 1
    ladder = sorted([s for s, n in sizes.items() if n / tot >= 0.004], reverse=True)
    # estimate modular ratio from adjacent ladder steps (median)
    rat = [ladder[i] / ladder[i + 1] for i in range(len(ladder) - 1) if ladder[i + 1] > 0]
    rat.sort()
    median = rat[len(rat) // 2] if rat else None
    # base = size carrying most characters
    base = max(sizes.items(), key=lambda kv: kv[1])[0] if sizes else None
    return dict(
        families=[dict(font=f, share=round(n / tot, 4)) for f, n in fam.most_common()],
        sizes=[dict(px=s, share=round(sizes[s] / tot, 4),
                    fonts=sorted({f for (p, f, b) in by if p == s and f})[:3],
                    bold_share=round(sum(n for (p, f, b), n in by.items() if p == s and b) / sizes[s], 2))
               for s in ladder],
        weights=[dict(font=f, weight=w, share=round(n / tot, 4)) for (f, w), n in wts.most_common()],
        base_px=base, median_step_ratio=round(median, 3) if median else None)


def _fit_grid(xs_left, xs_right, W_, margin_l, margin_r, widths=()):
    """Brute-force columns N and gutter g so that most edges land on a column
    line. Returns best (score, N, gutter, colw)."""
    best = None
    inner = W_ - margin_l - margin_r
    for n in range(2, 17):
        for g in (0, 8, 12, 16, 20, 24, 32, 40, 48, 64):
            col = (inner - g * (n - 1)) / n
            if col <= 8:
                continue
            lines_l = [margin_l + i * (col + g) for i in range(n)]
            lines_r = [margin_l + i * (col + g) + col for i in range(n)]
            err = 0.0
            for x in xs_left:
                err += min(abs(x - l) for l in lines_l)
            for x in xs_right:
                err += min(abs(x - l) for l in lines_r)
            tot = len(xs_left) + len(xs_right)
            hit = sum(1 for x in xs_left if min(abs(x - l) for l in lines_l) <= 1.5) + \
                sum(1 for x in xs_right if min(abs(x - l) for l in lines_r) <= 1.5)
            hl = sum(1 for x in xs_left if min(abs(x - l) for l in lines_l) <= 1.5) / len(xs_left)
            hw = (sum(1 for w in widths if any(abs(w - (k * col + (k - 1) * g)) <= 1.5 for k in range(1, n + 1))) / len(widths)) if widths else 0
            hr = (hit - hl * len(xs_left)) / max(1, len(xs_right))
            # right edges are often widened by text boxes, so weight left edges 3:1
            score = 0.5 * hl + 0.15 * hr + 0.35 * hw - 0.002 * n - (0.01 if g == 0 else 0)
            if best is None or score > best[0]:
                best = (score, n, g, col, hit / tot, err / tot)
    return best


def detect_guides(model, tol=2):
    """A deck that *draws* its grid (repeated tall stripes, usually translucent)
    states it exactly. Returns {columns, gutter, column_width, margin_left,
    margin_right} or None."""
    cw, ch = model['canvas']
    per = defaultdict(list)
    for e in model['elements']:
        if e['kind'] == 'shape' and not e['runs'] and e['h'] >= 0.8 * ch and e['w'] < cw / 3:
            per[e['slide']].append(e)
    best = None
    for els in per.values():
        groups = defaultdict(list)
        for e in els:
            groups[round(e['w'] / tol)].append(e)
        for g in groups.values():
            if len(g) < 3:
                continue
            g.sort(key=lambda e: e['x'])
            pitch = [g[i + 1]['x'] - g[i]['x'] for i in range(len(g) - 1)]
            if max(pitch) - min(pitch) > 2 * tol:
                continue
            w = sum(e['w'] for e in g) / len(g)
            p = sum(pitch) / len(pitch)
            cand = dict(columns=len(g), gutter=round(p - w, 2), column_width=round(w, 2),
                        margin_left=round(g[0]['x'], 2), margin_right=round(cw - (g[-1]['x'] + w), 2),
                        source='drawn guide stripes')
            if best is None or cand['columns'] > best['columns']:
                best = cand
    return best


def _fit_pitch(lefts_counter, ml, mr, cw):
    """Column pitch = most common spacing between recurring left edges
    (or a divisor of it). N and gutter then follow from the margins:
    inner = N*pitch - gutter, with N integer and gutter a plausible value."""
    xs = sorted(x for x, n in lefts_counter.items() if n >= 2 and ml - 1 <= x <= cw - mr)
    diffs = Counter()
    for i, a in enumerate(xs):
        for b in xs[i + 1:]:
            d = b - a
            if 40 <= d <= 600:
                diffs[round(d)] += 1
    inner = cw - ml - mr
    best = None
    for p, _ in diffs.most_common(40):
        for k in (1, 2, 3):  # pitch may be a multiple of the true one
            pp = p / k
            for n in range(2, 17):
                g = n * pp - inner
                if g < -0.5 or g > 64:
                    continue
                col = pp - g
                if col < 16:
                    continue
                lines = [ml + i * pp for i in range(n)]
                hit = sum(c for x, c in lefts_counter.items() if ml - 2 <= x <= cw - mr and min(abs(x - l) for l in lines) <= 1.5)
                tot = sum(c for x, c in lefts_counter.items() if ml - 2 <= x <= cw - mr) or 1
                # prefer round gutters
                nice = 0.03 if round(g) in (0, 8, 12, 16, 20, 24, 32, 40) else 0
                sc = hit / tot + nice - 0.004 * n
                if best is None or sc > best[0]:
                    best = (sc, n, round(g, 2), round(col, 2), hit / tot)
    return best


def derive_grid(model):
    cw, ch = model['canvas']
    els = [e for e in model['elements']
           if e['kind'] in ('text', 'image', 'shape') and e['w'] > 24 and e['h'] > 12
           and e['w'] < cw * 0.98 and not (e['kind'] == 'shape' and not e['fill'] and not e['runs'])]
    if not els:
        return {}
    lefts = Counter(round(e['x'] / 2) * 2 for e in els)
    rights = Counter(round((e['x'] + e['w']) / 2) * 2 for e in els)
    # margins: the left/right edges used by >=3% of elements at the extremes
    thr = max(3, 0.02 * len(els))
    ml_c = sorted(x for x, n in lefts.items() if n >= thr and x >= 0)
    mr_c = sorted((cw - x) for x, n in rights.items() if n >= thr and x <= cw)
    # margin = the busiest edge within the outer 15% (ties: nearest the page edge)
    outer_l = [(n, -x) for x, n in lefts.items() if 0 <= x <= cw * 0.15]
    outer_r = [(n, -(cw - x)) for x, n in rights.items() if cw * 0.85 <= x <= cw]
    ml = -max(outer_l)[1] if outer_l else min(e['x'] for e in els)
    mr = -max(outer_r)[1] if outer_r else cw - max(e['x'] + e['w'] for e in els)
    # fit columns to recurring edges only (>=2 occurrences) so one-offs don't dominate
    xl = [x for x, n in lefts.items() for _ in range(min(n, 20)) if n >= 2 and ml - 2 <= x <= cw - mr]
    xr = [x for x, n in rights.items() for _ in range(min(n, 20)) if n >= 2 and ml <= x <= cw - mr + 2]
    # right-hand edges are often widened by text boxes, so test both the measured
    # right margin and a symmetric one and keep the better fit
    widths = [round(e['w'], 1) for e in els if e['kind'] == 'image' or (e['fill'] and not e['runs'] and e.get('alpha', 1) >= 0.5)]
    fit = None
    mr_measured = mr
    if xl and xr:
        for cand_mr in sorted({mr, ml}):
            f = _fit_grid(xl, xr, cw, ml, cand_mr, widths)
            if f and (fit is None or f[0] > fit[0]):
                fit, mr = f, cand_mr
    pf = _fit_pitch(lefts, ml, mr, cw) or _fit_pitch(lefts, ml, ml, cw)
    if pf and (fit is None or pf[4] > fit[4]):
        fit = (pf[0], pf[1], pf[2], pf[3], pf[4], 0)
        if _fit_pitch(lefts, ml, mr, cw) is None:
            mr = ml
    guides = None if model.get('no_guides') else detect_guides(model)
    # vertical: top margin & baseline rhythm from text tops
    tops = Counter(round(e['y'] / 2) * 2 for e in els if e['kind'] == 'text')
    # the template's own placeholders state the margins outright
    ph = [i for lay in model['layouts'] for i in lay['items'] if i.get('ph') in ('TITLE', 'BODY', 'CENTERED_TITLE', 'SUBTITLE') and i['w'] > 0.3 * cw]
    tmpl = None
    if ph:
        tl = Counter(round(i['x']) for i in ph).most_common(1)[0][0]
        tr = Counter(round(cw - i['x'] - i['w']) for i in ph).most_common(1)[0][0]
        tmpl = dict(left=tl, right=tr)
        ml, mr = tl, tr
    if guides:
        fit = (1, guides['columns'], guides['gutter'], guides['column_width'], 1.0, 0)
        ml, mr = guides['margin_left'], guides['margin_right']
    return dict(
        source=guides['source'] if guides else 'fitted to recurring element edges',
        margin_right_measured=mr_measured, template_margins=tmpl,
        canvas=[cw, ch], margin_left=ml, margin_right=mr,
        margin_top=min([y for y, n in tops.items() if n >= thr] or [0]),
        columns=fit[1] if fit else None, gutter=fit[2] if fit else None,
        column_width=round(fit[3], 2) if fit else None,
        fit_hit_rate=round(fit[4], 3) if fit else None,
        left_edges=[dict(x=x, n=n) for x, n in lefts.most_common(8)],
        top_edges=[dict(y=y, n=n) for y, n in tops.most_common(6)],
    )


def derive_spacing(model):
    """Gaps between vertically/horizontally adjacent elements on the same slide."""
    gaps = Counter()
    by = defaultdict(list)
    for e in model['elements']:
        if e['kind'] in ('text', 'image') or e['fill']:
            by[e['slide']].append(e)
    for els in by.values():
        for a in els:
            for b in els:
                if a is b:
                    continue
                # vertical neighbour with horizontal overlap
                ov = min(a['x'] + a['w'], b['x'] + b['w']) - max(a['x'], b['x'])
                if ov > 0.3 * min(a['w'], b['w']):
                    g = b['y'] - (a['y'] + a['h'])
                    if 4 <= g <= 200:
                        gaps[round(g)] += 1
                oy = min(a['y'] + a['h'], b['y'] + b['h']) - max(a['y'], b['y'])
                if oy > 0.3 * min(a['h'], b['h']):
                    g = b['x'] - (a['x'] + a['w'])
                    if 4 <= g <= 200:
                        gaps[round(g)] += 1
    # find base unit that explains the most gaps (within 2px)
    tot = sum(gaps.values()) or 1
    rates = {}
    for u in (4, 6, 8, 10, 12, 16, 20, 24):
        rates[u] = sum(n for g, n in gaps.items() if abs(g / u - round(g / u)) * u <= 1 and g >= u) / tot
    top = max(rates.values())
    # the coarsest unit that is nearly as good as the best (4 divides everything 8 does)
    u = max(k for k, v in rates.items() if v >= top - 0.05)
    best = (0, u, rates[u])
    common = [g for g, n in gaps.most_common(12)]
    return dict(base_unit=best[1] if best else None, unit_hit_rate=round(best[2], 3) if best else None,
                common_gaps=sorted(common), samples=tot)


def derive_shape(model):
    rad = Counter(round(e['radius'] / 2) * 2 for e in model['elements'] if e['radius'] and (e['fill'] or e['kind'] == 'image') and e['radius'] < min(e['w'], e['h']) / 2 - 1)
    circles = sum(1 for e in model['elements'] if e['radius'] and e['radius'] >= min(e['w'], e['h']) / 2 - 1 and e['w'] > 24)
    strokes = Counter(round(e['stroke']['w']) for e in model['elements'] if e['stroke'] and e['stroke'].get('w'))
    shadows = sum(1 for e in model['elements'] if e['shadow'])
    return dict(radii=[dict(px=r, n=n) for r, n in rad.most_common(6)],
                strokes=[dict(px=r, n=n) for r, n in strokes.most_common(5)], circles=circles,
                shadow_elements=shadows)


def derive_layouts(model):
    out = []
    cw, ch = model['canvas']
    for lay in model['layouts']:
        its = [dict(role=i.get('ph') or i.get('kind'), x=round(i['x']), y=round(i['y']),
                    w=round(i['w']), h=round(i['h'])) for i in lay['items']
               if i.get('w', 0) > 0]
        out.append(dict(name=lay['name'], items=its))
    # usage: which layout is used by each slide is not in the normalised model;
    # report structural clusters of slides instead (see derive_slide_kinds).
    return out


def derive_slide_kinds(model):
    """Classify slides by structure: counts of text/image/shape and biggest
    type size. Cheap, and enough to show which 'templates' a deck really uses."""
    per = defaultdict(list)
    for e in model['elements']:
        per[e['slide']].append(e)
    kinds = Counter()
    ex = {}
    for si, els in per.items():
        txt = [e for e in els if e['kind'] == 'text']
        img = [e for e in els if e['kind'] == 'image']
        big = max([r['px'] for e in txt for r in e['runs']] or [0])
        words = sum(r['n'] for e in txt for r in e['runs'])
        k = ('divider' if len(txt) <= 3 and big >= 60 and not img else
             'image-led' if img and sum(i['w'] * i['h'] for i in img) > 0.35 * model['canvas'][0] * model['canvas'][1] else
             'text-heavy' if words > 600 else
             'cards/grid' if len([e for e in els if e['fill'] and 80 < e['w'] < 900 and 80 < e['h'] < 700]) >= 4 else
             'standard')
        kinds[k] += 1
        ex.setdefault(k, si)
    return dict(counts=dict(kinds), example_slide_index={k: v for k, v in ex.items()})


def derive(model):
    cols = derive_colours(model)
    return dict(
        slides=model['nslides'], elements=len(model['elements']),
        colour=dict(**cols, roles=name_colours(cols)),
        type=derive_type(model), grid=derive_grid(model),
        spacing=derive_spacing(model), shape=derive_shape(model),
        layouts=derive_layouts(model), slide_kinds=derive_slide_kinds(model))


# --------------------------------------------------------------------------
# outputs: tokens.json (design-system style), deck.css variables, DESIGN.md
# --------------------------------------------------------------------------
def snap_type(t, grid_base=None):
    """Map measured sizes to named steps: display, h1, h2, h3, body, caption."""
    sizes = [s['px'] for s in t['sizes']]
    if not sizes:
        return {}
    base = t['base_px'] or sizes[-1]
    names = {}
    big = [s for s in sizes if s > base * 1.15]
    small = [s for s in sizes if s < base * 0.87]
    names['body'] = base
    heads = ['h3', 'h2', 'h1', 'display', 'display-xl']
    for nm, s in zip(heads, sorted(big)):
        names[nm] = s
    for nm, s in zip(['caption', 'micro', 'nano'], sorted(small, reverse=True)):
        names[nm] = s
    return names


def _ordered_families(t):
    """display = family of the largest measured size, body = family of the base size."""
    sizes = t['sizes']
    order = []
    if sizes:
        order += sizes[0]['fonts'][:1] + [f for f in next((s['fonts'] for s in sizes if s['px'] == t['base_px']), [])][:1]
    order += [f['font'] for f in t['families'] if f['font']]
    out = []
    for f in order:
        if f and f not in out:
            out.append(f)
    return out


def to_tokens_json(d, name='derived'):
    g = d['grid']
    return {
        'name': name,
        'derived': True,
        'colour': d['colour']['roles'],
        'type': {'families': _ordered_families(d['type']),
                 'scale_px': snap_type(d['type']),
                 'measured_sizes_px': [s['px'] for s in d['type']['sizes']]},
        'grid': {k: g.get(k) for k in ('source', 'canvas', 'margin_left', 'margin_right', 'margin_top',
                                       'columns', 'gutter', 'column_width', 'fit_hit_rate')},
        'spacing': {'unit_px': d['spacing']['base_unit'], 'common_gaps_px': d['spacing']['common_gaps']},
        'radius_px': [r['px'] for r in d['shape']['radii']],
        'stroke_px': [r['px'] for r in d['shape']['strokes']],
        'uses_shadows': d['shape']['shadow_elements'] > 0,
    }


def to_css(d, scale_to=1920):
    t = to_tokens_json(d)
    lines = [':root {']
    for k, v in t['colour'].items():
        lines.append('  --c-%s: %s;' % (k, v))
    fams = t['type']['families']
    if fams:
        lines.append('  --font-display: "%s";' % fams[0])
        lines.append('  --font-body: "%s";' % (fams[1] if len(fams) > 1 else fams[0]))
    for k, v in t['type']['scale_px'].items():
        lines.append('  --t-%s: %spx;' % (k, round(v)))
    g = t['grid']
    if g.get('margin_left') is not None:
        lines.append('  --margin: %spx;' % round(g['margin_left']))
    if g.get('columns'):
        lines.append('  --cols: %d;\n  --gutter: %spx;\n  --col: %spx;' % (g['columns'], round(g['gutter']), round(g['column_width'])))
    if t['spacing']['unit_px']:
        lines.append('  --space: %spx;' % t['spacing']['unit_px'])
    if t['radius_px']:
        lines.append('  --radius: %spx;' % round(t['radius_px'][0]))
    lines.append('}')
    return '\n'.join(lines) + '\n'


def to_markdown(d, name):
    t, g, c = d['type'], d['grid'], d['colour']
    L = ['# Design system derived from %s' % name, '',
         '%d slides, %d elements measured. Every number below was measured, not assumed.' % (d['slides'], d['elements']), '',
         '## Colour', '', '| Role | Hex |', '| --- | --- |']
    for k, v in c['roles'].items():
        L.append('| %s | `%s` |' % (k, v))
    L += ['', 'Fills by area share: ' + ', '.join('`%s` %.0f%%' % (f['hex'], f['share'] * 100) for f in c['fills'][:8]), '',
          '## Type', '', 'Families by characters: ' + ', '.join('%s %.0f%%' % (f['font'], f['share'] * 100) for f in t['families']), '',
          '| px | share | fonts | bold |', '| --- | --- | --- | --- |']
    for s in t['sizes']:
        L.append('| %g | %.1f%% | %s | %.0f%% |' % (s['px'], s['share'] * 100, ', '.join(s['fonts']), s['bold_share'] * 100))
    L += ['', 'Base size %s px; median step ratio %s.' % (t['base_px'], t['median_step_ratio']), '',
          '## Grid', '']
    if g:
        L.append('Source: %s.' % g['source'])
        if g.get('template_margins'):
            L.append('Template placeholders set the margins: left %(left)s / right %(right)s px.' % g['template_margins'])
        L.append('Canvas %dx%d. Margins left %s / right %s / top %s px.' % (g['canvas'][0], g['canvas'][1], g['margin_left'], g['margin_right'], g['margin_top']))
        if g.get('columns'):
            L.append('Best-fit grid: **%d columns**, gutter %s px, column %s px. %.0f%% of recurring edges land on it.' % (
                g['columns'], g['gutter'], g['column_width'], g['fit_hit_rate'] * 100))
    sp = d['spacing']
    L += ['', '## Spacing', '', 'Base unit %s px explains %.0f%% of %d measured gaps. Common gaps: %s.' % (
        sp['base_unit'], (sp['unit_hit_rate'] or 0) * 100, sp['samples'], ', '.join(map(str, sp['common_gaps']))), '',
          '## Shape', '', 'Radii: %s. Strokes: %s. Elements with shadows: %d. Circles: %d.' % (
        ', '.join('%gpx x%d' % (r['px'], r['n']) for r in d['shape']['radii']) or 'none',
        ', '.join('%gpx x%d' % (r['px'], r['n']) for r in d['shape']['strokes']) or 'none', d['shape']['shadow_elements'], d['shape'].get('circles', 0)), '',
          '## Slide kinds', '', ', '.join('%s: %d' % kv for kv in d['slide_kinds']['counts'].items()), '',
          '## Layouts (template)', '']
    for lay in d['layouts']:
        L.append('- **%s**: %s' % (lay['name'], ', '.join('%s %dx%d@%d,%d' % (i['role'], i['w'], i['h'], i['x'], i['y']) for i in lay['items']) or 'no placeholders'))
    return '\n'.join(L) + '\n'


def to_dtcg(d, name='derived'):
    """W3C Design Tokens Community Group format ($value/$type, nested groups).
    Dimensions are px strings; typography/shadow composites are left out where
    nothing was measured. Colours use the plain hex form."""
    t = to_tokens_json(d, name)
    out = {'$description': 'Derived by deck2slides from %s. Measured, not authored.' % name}
    out['color'] = {k: {'$type': 'color', '$value': v} for k, v in t['colour'].items()}
    fams = t['type']['families']
    out['font'] = {'family': {('display' if i == 0 else 'body' if i == 1 else 'extra%d' % i):
                              {'$type': 'fontFamily', '$value': f} for i, f in enumerate(fams)},
                   'size': {k: {'$type': 'dimension', '$value': '%gpx' % round(v, 1)}
                            for k, v in t['type']['scale_px'].items()}}
    g = t['grid']
    out['grid'] = {k: {'$type': 'dimension' if k != 'columns' else 'number',
                       '$value': ('%gpx' % g[k]) if k != 'columns' else g[k]}
                   for k in ('margin_left', 'margin_right', 'margin_top', 'columns', 'gutter', 'column_width')
                   if g.get(k) is not None}
    if t['spacing']['unit_px']:
        out['space'] = {'unit': {'$type': 'dimension', '$value': '%gpx' % t['spacing']['unit_px']}}
    out['radius'] = {('r%d' % i): {'$type': 'dimension', '$value': '%gpx' % r} for i, r in enumerate(t['radius_px'])}
    return out


# --------------------------------------------------------------------------
# Claude "Design System" artifact format (tokens.json read by the page)
# Lists, not DTCG maps: {"tokens":[{name,value,usage}]}; type = fonts/families/groups.
# --------------------------------------------------------------------------
_NAME_OK = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$')
_ROLE_USAGE = {
    'ink': 'Primary text. Most legible text colour in the source deck.',
    'mute': 'Secondary text: captions, supporting copy.',
    'paper': 'Slide and page background.',
    'surface': 'Cards and panels sitting on paper.',
}


def to_claude_ds(d, name='derived', source=None):
    t = to_tokens_json(d, name)
    ty = d['type']
    cols = []
    for k, v in t['colour'].items():
        use = _ROLE_USAGE.get(k) or 'Accent colour %s, measured from fills and strokes in the source.' % k.split('-')[-1]
        cols.append({'name': k, 'value': v.lower(), 'usage': use})
    fams = t['type']['families'] or ['system-ui']
    keys = ['display', 'body'] + ['extra%d' % i for i in range(1, 10)]
    families = {keys[i]: '"%s", system-ui, sans-serif' % f for i, f in enumerate(fams[:12])}
    famkey = {f: keys[i] for i, f in enumerate(fams[:12])}
    wmap = {}
    for w in ty.get('weights', []):
        wmap.setdefault(w['font'], []).append(w)
    styles_by_fam = defaultdict(list)
    sizes = {s['px']: s for s in ty['sizes']}
    for nm, px in t['type']['scale_px'].items():
        s = sizes.get(px)
        fam = (s['fonts'][0] if s and s['fonts'] else fams[0])
        weight = 700 if (s and s['bold_share'] >= 0.5) else 400
        styles_by_fam[famkey.get(fam, 'body')].append(
            {'name': nm, 'fontSize': '%gpx' % round(px, 1), 'fontWeight': weight,
             'usage': 'Measured: %.1f%% of characters in the source use this size.' % ((s['share'] if s else 0) * 100)})
    groups = []
    for k, label in (('display', 'Display'), ('body', 'Text')):
        if styles_by_fam.get(k):
            sty = sorted(styles_by_fam[k], key=lambda x: -float(x['fontSize'][:-2]))
            groups.append({'name': label, 'family': k, 'styles': sty})
    for k, sty in styles_by_fam.items():
        if k not in ('display', 'body'):
            groups.append({'name': k.title(), 'family': k, 'styles': sty})
    out = {'name': name, 'version': 1,
           'color': {'themes': [{'id': 'light', 'name': 'Light'}], 'tokens': cols},
           'type': {'fonts': [], 'families': families, 'groups': groups[:12]}}
    u = t['spacing']['unit_px']
    if u:
        out['spacing'] = {'tokens': [{'name': 'space-%d' % m, 'value': '%gpx' % (u * m),
                                      'usage': '%d x the %gpx base unit measured in the source.' % (m, u)}
                                     for m in (1, 2, 3, 4, 6, 8, 12)]}
    rads = [r for r in t['radius_px'] if r > 0]
    rt = [{'name': 'radius-%d' % (i + 1), 'value': '%gpx' % r, 'usage': 'Corner radius used in the source.'}
          for i, r in enumerate(sorted(rads)[:6])]
    if d['shape'].get('circles'):
        rt.append({'name': 'radius-full', 'value': '9999px', 'usage': 'Circles and pills.'})
    if rt:
        out['radius'] = {'tokens': rt}
    g = t['grid']
    gt = []
    if g.get('columns'):
        gt.append({'name': 'grid-columns', 'value': str(g['columns']), 'usage': 'Columns in the canvas grid (%s).' % g.get('source')})
    for k, nm in (('margin_left', 'grid-margin'), ('gutter', 'grid-gutter'), ('column_width', 'grid-column')):
        if g.get(k) is not None:
            gt.append({'name': nm, 'value': '%gpx' % round(g[k], 2), 'usage': 'Measured on a %g px wide canvas.' % g['canvas'][0]})
    if gt:
        out['grid'] = {'note': 'Slide canvas %gx%g px.' % tuple(g['canvas']), 'tokens': gt}
    return out


_LEN = re.compile(r'^(0|-?\d+(\.\d+)?(px|rem|em|%)?)$')
_HEX = re.compile(r'^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$')


def validate_claude_ds(tk):
    """Local mirror of format.md's grammar. Returns a list of problems (empty = reads cleanly)."""
    bad = []
    names = Counter()
    for fam, body in tk.items():
        if fam in ('name', 'version', 'type'):
            continue
        if not isinstance(body, dict) or not isinstance(body.get('tokens'), list):
            bad.append('%s: not {tokens:[...]} (DTCG map?)' % fam)
            continue
        for e in body['tokens']:
            n = e.get('name', '')
            names[n] += 1
            if not _NAME_OK.match(n):
                bad.append('%s/%s: bad name' % (fam, n))
            vals = list(e['value'].values()) if isinstance(e.get('value'), dict) else [e.get('value')]
            for v in vals:
                if fam == 'color':
                    if not (isinstance(v, str) and (_HEX.match(v) or re.match(r'^(rgb|hsl|oklch)a?\(', v) or re.match(r'^\{[\w.-]+\}$', v))):
                        bad.append('color/%s: unreadable value %r' % (n, v))
                elif fam in ('spacing', 'radius'):
                    if not _LEN.match(str(v)):
                        bad.append('%s/%s: bad length %r' % (fam, n, v))
    bad += ['duplicate name %s' % n for n, c in names.items() if c > 1]
    cols = {e['name'] for e in tk.get('color', {}).get('tokens', [])}
    for e in tk.get('color', {}).get('tokens', []):
        v = e['value']
        if isinstance(v, str) and v.startswith('{') and v[1:-1] not in cols:
            bad.append('color/%s: alias of missing token' % e['name'])
    ty = tk.get('type', {})
    if not isinstance(ty.get('families'), dict) or not isinstance(ty.get('groups', []), list):
        return bad + ['type: families must be {key: stack} and groups a list']
    for grp in ty.get('groups', []):
        if grp.get('family') not in ty.get('families', {}):
            bad.append('type group %s: unknown family' % grp.get('name'))
        for s in grp.get('styles', []):
            if not _NAME_OK.match(s['name']) or not _LEN.match(str(s['fontSize'])):
                bad.append('type style %s: bad name/fontSize' % s['name'])
    for k, v in ty.get('families', {}).items():
        if re.search(r'[;{}<>\\()]', v):
            bad.append('type family %s: forbidden character' % k)
    return bad
