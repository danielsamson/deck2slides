"""Build a complete Claude "Design System" artifact tree (project/...) from a derived deck:
tokens.json (line heights, weights, shadows, on-colours, fonts), README.md (usage rules),
fonts/, component previews found in the deck, and the Cover.

Everything is derived from measurements in d2s.tokens; where the deck holds no evidence
(components, shadows) nothing is invented, and the report says what was left out."""
from __future__ import annotations
import json, os, re, datetime
from collections import Counter, defaultdict
from . import tokens as T, fonts as F

PROJECT = 'project'


# ---------------------------------------------------------------- colour maths
def _rgb(h):
    return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def rel_lum(h):
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = [f(c) for c in _rgb(h)]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _rgba(h, a):
    r, g, b = [int(round(c * 255)) for c in _rgb(h)]
    return 'rgba(%d,%d,%d,%g)' % (r, g, b, a)


# ---------------------------------------------------------------- fonts
def natural_lh(font, cache):
    if not font:
        return 1.2
    fp = F.fetch_family_file(font, 'https://fonts.googleapis.com/css2?family=' + font.replace(' ', '+'), cache)
    try:
        return F.natural_from_file(fp) if fp else 1.2
    except Exception:
        return 1.2


def fetch_font_files(wanted, outdir, cache):
    """wanted: {(family, weight)}. Returns ({(family, weight): relpath}, [missing])."""
    got, missing = {}, []
    os.makedirs(os.path.join(outdir, 'fonts'), exist_ok=True)
    for fam, w in sorted(wanted):
        rel = 'fonts/%s-%d.woff2' % (re.sub(r'\W+', '', fam), w)
        dest = os.path.join(outdir, rel)
        try:
            css = F._get('https://fonts.googleapis.com/css2?family=%s:wght@%d&display=swap' % (fam.replace(' ', '+'), w))
            blocks = re.findall(r'/\*\s*([\w-]+)\s*\*/\s*@font-face\s*{[^}]*?src:\s*url\(([^)]+)\)', css)
            url = next((u for n, u in blocks if n == 'latin'), blocks[0][1] if blocks else None)
            if not url:
                raise RuntimeError('no face')
            # open-licence Google Fonts live under /s/<family>/; a /l/font?kit= URL is a proxied face whose licence and
            # identity we cannot check (e.g. 'Helvetica Neue'), so it is reported, not bundled
            if 'fonts.gstatic.com/s/' not in url:
                raise RuntimeError('kit url')
            open(dest, 'wb').write(F._get(url, True))
            got[(fam, w)] = rel
        except Exception:
            missing.append('%s %d' % (fam, w))
    return got, missing


# ---------------------------------------------------------------- tokens.json
def build_tokens(d, name, cache, outdir, fetch=True):
    tk = T.to_claude_ds(d, name)
    ty = d['type']
    by_px = {s['px']: s for s in ty['sizes']}
    warn = []
    # line height + weight on every style
    nat = {}
    for grp in tk['type']['groups']:
        for st in grp['styles']:
            px = float(st['fontSize'][:-2])
            s = by_px.get(px) or by_px.get(round(px * 2) / 2)
            if not s:
                continue
            fam = s['fonts'][0] if s['fonts'] else None
            if s.get('weight'):
                st['fontWeight'] = s['weight']
            if s.get('lh_mult') and fam:
                nat.setdefault(fam, natural_lh(fam, cache))
                st['lineHeight'] = round(s['lh_mult'] * nat[fam], 2)
    # shadows
    sh = d['shape'].get('shadows', [])
    if sh:
        tk['shadow'] = {'tokens': [{'name': 'shadow-%d' % (i + 1),
                                    'value': '%dpx %dpx %dpx %s' % (x['dx'], x['dy'], x['blur'], _rgba(x['color'], x['alpha'])),
                                    'usage': 'Measured drop shadow, used on %d element%s of the source.' % (x['n'], '' if x['n'] == 1 else 's')}
                                   for i, x in enumerate(sh)]}
    # contrast: notes on text colours, on-colours for accents
    cols = {t['name']: t for t in tk['color']['tokens']}
    tids = [t['id'] for t in tk['color']['themes']]
    val = lambda tok, th: (tok['value'][th] if isinstance(tok['value'], dict) else tok['value']) if tok else None
    paper, surface = cols.get('paper'), cols.get('surface')
    fails = []
    for role in ('ink', 'mute'):
        if role in cols:
            parts = []
            for th in tids:
                for gn, gt in (('paper', paper), ('surface', surface)):
                    gv, rv = val(gt, th), val(cols[role], th)
                    if gv:
                        c = contrast(rv, gv)
                        parts.append('%.1f:1 on `%s`%s' % (c, gn, (' (%s)' % th) if len(tids) > 1 else ''))
                        if c < 4.5:
                            fails.append('%s on %s in %s %.1f:1' % (role, gn, th, c))
            cols[role]['usage'] = cols[role]['usage'].rstrip('.') + '. Contrast ' + ', '.join(parts) + '.'
    # text colours to try on an accent: every ink and paper value the system has (so black counts on a gold accent
    # when black is the paper of one theme), never colours outside the palette
    cands = []
    for nm in ('ink', 'paper'):
        for th in tids:
            v = val(cols.get(nm), th)
            if v and v not in cands:
                cands.append(v)
    ink = cands[0] if cands else '#000000'
    on = []
    for t in list(tk['color']['tokens']):
        if t['name'].startswith('accent-'):
            best = max(cands or ['#000000'], key=lambda c: contrast(t['value'], c))
            bc = contrast(t['value'], best)
            on.append({'name': 'on-' + t['name'], 'value': best,
                       'usage': 'Text and icons on `%s`: %s, %.1f:1%s.' % (
                           t['name'], best, bc, '' if bc >= 4.5 else ' (below 4.5:1, use at 24px or larger only)')})
            if bc < 3:
                fails.append('%s best text %.1f:1' % (t['name'], bc))
            if paper:
                t['usage'] += ' ' + ', '.join('%.1f:1 against `paper`%s' % (contrast(t['value'], val(paper, th)), (' (%s)' % th) if len(tids) > 1 else '') for th in tids) + '.'
    tk['color']['tokens'] += on
    # fonts
    SYSTEM = {'Arial', 'Helvetica', 'Georgia', 'Times New Roman', 'Verdana', 'Tahoma', 'Courier New', 'Trebuchet MS', 'Calibri', 'Cambria', 'Segoe UI'}
    wanted = {(f, w['weight']) for w in ty.get('weights', []) for f in [w['font']] if f and f not in SYSTEM and w['share'] >= 0.01}   # a face under 1% of the text is not worth a file
    files, missing = ({}, []) if not fetch else fetch_font_files(wanted, outdir, cache)
    tk['type']['fonts'] = [{'family': f, 'file': p, 'weight': str(w)} for (f, w), p in sorted(files.items())]
    if missing:
        warn.append('not bundled (not on Google Fonts, or served from a proxied kit URL with an unchecked licence): ' + ', '.join(missing))
    return tk, files, missing, fails, warn


# ---------------------------------------------------------------- components
def find_components(model, d, tk):
    """Recurring filled shapes with the same size, fill and radius become components."""
    cw, ch = model['canvas']
    groups = defaultdict(list)
    for e in model['elements']:
        sq = e['w'] < 200 and 0.8 <= e['w'] / max(e['h'], 1) <= 1.25 and not e['runs']  # colour swatches
        if e['kind'] in ('shape', 'text') and e['fill'] and e.get('alpha', 1) >= 0.5 and e['w'] >= 80 and e['h'] >= 40 \
                and e['h'] < 0.8 * ch and e['w'] < cw * 0.9 and not sq:
            groups[(round(e['w'] / 8), round(e['h'] / 8), e['fill'], round(e['radius'] / 4))].append(e)
    comps = {}
    for key, els in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        slides = {e['slide'] for e in els}
        if len(els) < 2:
            continue
        e = els[0]
        pill = e['radius'] >= min(e['w'], e['h']) / 2 - 1 and e['h'] <= 160
        nm = 'Pill' if pill else 'Card'
        if nm in comps:
            continue
        comps[nm] = dict(w=round(e['w']), h=round(e['h']), fill=e['fill'], radius=round(e['radius']), n=len(els),
                         slides=len(slides), shadow=e.get('shadow_spec'), text=any(r for r in e['runs']))
    return comps


def _tok_for(hex_, tk):
    best = None
    for t in tk['color']['tokens']:
        v = t['value']
        if isinstance(v, str) and v.startswith('#') and len(v) == 7:
            dist = sum(abs(int(v[i:i + 2], 16) - int(hex_[i:i + 2], 16)) for i in (1, 3, 5))
            if best is None or dist < best[0]:
                best = (dist, t['name'])
    return best[1] if best else None


def _radius_tok(px, tk):
    toks = tk.get('radius', {}).get('tokens', [])
    for t in toks:
        if t['value'] == '%gpx' % px:
            return t['name']
    return None


def component_files(comps, tk):
    out = {}
    body = next((s['name'] for g in tk['type']['groups'] for s in g['styles'] if s['name'] == 'body'), None)
    for nm, c in comps.items():
        fill = _tok_for(c['fill'], tk)
        rad = _radius_tok(c['radius'], tk)
        on = 'on-' + fill if fill and fill.startswith('accent-') else 'ink'
        shadow_tok = None
        if c['shadow'] and tk.get('shadow'):
            sp = '%dpx %dpx %dpx %s' % (c['shadow']['dx'], c['shadow']['dy'], c['shadow']['blur'], _rgba(c['shadow']['color'], c['shadow']['alpha']))
            shadow_tok = next((t['name'] for t in tk['shadow']['tokens'] if t['value'] == sp), None)
        radius = 'var(--%s)' % rad if rad else '%dpx' % c['radius']
        css = '.%s{width:%dpx;height:%dpx;background:var(--%s);color:var(--%s);border-radius:%s;%s display:flex;align-items:center;justify-content:center;box-sizing:border-box}' % (
            nm.lower(), c['w'], c['h'], fill or 'surface', on, radius,
            ('box-shadow:var(--%s);' % shadow_tok) if shadow_tok else '')
        out['components/%s/preview.html' % nm] = (
            '<!-- @dsCard group="Shapes" height=%d width=%d subtitle="Measured from %d elements" -->\n'
            '<style>body{margin:0;padding:32px;background:var(--paper,#fff);font-family:var(--font-body)}%s</style>\n'
            '<div class="%s"><span class="%s">%s</span></div>\n' % (
                min(c['h'] + 96, 600), c['w'] + 64, c['n'], css, nm.lower(), body or '', nm))
        out['components/%s/README.md' % nm] = (
            '%s is a %dx%d px %s shape, filled `%s`%s%s, found %d times (%d slide%s) in the source.\n\n'
            'Use it as a container. The consumer provides the content; text on it uses `%s`. '
            'Keep its proportions when scaling and place it on a column of the grid.\n\n'
            '- Do: reuse the fill, radius and shadow tokens above.\n- Do not: add a coloured edge or a different radius.\n' % (
                nm, c['w'], c['h'], 'pill-shaped' if nm == 'Pill' else 'rectangular', fill or c['fill'],
                (', radius `%s`' % rad) if rad else (', radius %dpx' % c['radius'] if c['radius'] else ''),
                (', shadow `%s`' % shadow_tok) if shadow_tok else '', c['n'], c['slides'], '' if c['slides'] == 1 else 's', on))
    return out


# ---------------------------------------------------------------- cover
def _name_size(name, display_ratio=0.6):
    lines = [name]
    words = re.split(r'(?<=[ -])', name)
    for size in range(120, 63, -4):
        if len(name) * size * display_ratio <= 440:
            return size, [name]
    # two lines at a space or hyphen
    if len(words) > 1:
        best = None
        for i in range(1, len(words)):
            a, b = ''.join(words[:i]).rstrip(), ''.join(words[i:]).strip()
            m = max(len(a), len(b))
            if best is None or m < best[0]:
                best = (m, [a, b])
        for size in range(120, 63, -4):
            if best[0] * size * display_ratio <= 440 and 2 * size * 0.95 + 80 <= 288:
                return size, best[1]
    return 64, [name]


def cover(d, tk, name, tagline):
    cols = {t['name']: t['value'] for t in tk['color']['tokens']}
    acc = [k for k in cols if k.startswith('accent-')][:4]
    names = ['--%s' % k for k in acc]
    u = (d['spacing']['base_unit'] or 8)
    step = u * 12
    # blocks (x, y, w, h, token) inside x in [480, 960]; multiples of 48 so any base unit divides the box
    spec = [(480, 0, 240, 192, acc[0] if acc else 'ink'),
            (720, 0, 144, 96, acc[1] if len(acc) > 1 else 'mute'),
            (864, 0, 96, 144, acc[2] if len(acc) > 2 else 'ink'),
            (720, 96, 144, 192, 'ink'),
            (864, 144, 96, 144, 'mute' if 'mute' in cols else 'ink'),
            (480, 192, 240, 96, acc[3] if len(acc) > 3 else (acc[0] if acc else 'ink'))]
    rad = tk.get('radius', {}).get('tokens', [])
    finite = [t for t in rad if float(t['value'][:-2]) < 999]  # 9999px would draw an ellipse in SVG
    rtok = finite[-1]['name'] if finite else None
    circles = d['shape'].get('circles', 0) > 0
    big = max([float(s['fontSize'][:-2]) for g in tk['type']['groups'] for s in g['styles']] or [0])
    heavy = any(w['weight'] >= 700 for w in d['type'].get('weights', []))
    if circles or (rad and float(rad[-1]['value'][:-2]) >= 24):
        row, why = 'discs', 'the source uses %s' % ('circles' if circles else 'large radii (%s)' % rad[-1]['value'])
    elif heavy and big >= 90:
        row, why = 'stripes', 'bold display type at %gpx' % big
    else:
        row, why = 'dots', 'no soft shapes in the source, so a technical dot grid at the %gpx unit' % u
    blocks, pat = [], []
    for i, (x, y, w, h, t) in enumerate(spec):
        blocks.append('<rect class="b%d" x="%d" y="%d" width="%d" height="%d"/>' % (i, x, y, w, h))
    pitch = max(u * 3, 24)
    if row == 'dots':
        for yy in range(108, 288, pitch):
            for xx in range(732, 864, pitch):
                pat.append('<circle class="pt" cx="%d" cy="%d" r="3"/>' % (xx, yy))
    elif row == 'discs':
        pat += ['<circle class="pt" cx="600" cy="96" r="72"/>', '<circle class="pt2" cx="792" cy="192" r="48"/>',
                '<circle class="pt" cx="912" cy="216" r="36"/>']
    else:
        for xx in range(480, 720, pitch):
            pat.append('<rect class="pt" x="%d" y="192" width="%d" height="96"/>' % (xx, pitch // 2))
    size, lines = _name_size(name)
    ty = [g for g in tk['type']['groups'] if g['family'] == 'display'] or tk['type']['groups']
    text_y = 288 - 32 - 22 - (len(lines) - 1) * size * 0.95
    tsp = ''.join('<tspan x="32" dy="%s">%s</tspan>' % ('0' if i == 0 else '%.0f' % (size * 0.95), l.replace('&', '&amp;')) for i, l in enumerate(lines))
    fills = ''.join('.b%d{fill:var(--%s);rx:%s}' % (i, t, ('var(--%s)' % rtok) if (rtok and row != 'dots') else '0') for i, (_, _, _, _, t) in enumerate(spec))
    other = '.pt{fill:var(--%s)}.pt2{fill:var(--%s)}' % ('paper' if 'paper' in cols else 'surface', 'surface' if 'surface' in cols else 'paper')
    deriv = ('<!--\nblocks: %s (sizes in multiples of 48; box x=480..960)\narrangement: one tall slab with satellites, bands of unequal size\n'
             'pattern: %s, because %s\nscales: spacing unit %gpx%s%s\n-->' % (
                 ', '.join('%s %dx%d' % (t, w, h) for (_, _, w, h, t) in spec), row, why, u,
                 (', radius token %s' % rtok) if rtok else ', no radius tokens', ''))
    html = ('<!-- @dsCard height=288 -->\n<style>body{margin:0}.c{position:relative;width:960px;height:288px;background:var(--paper,var(--surface,#fff));overflow:hidden}'
            'svg{position:absolute;inset:0}%s%s.n{font-family:var(--font-display);font-size:%dpx;font-weight:%d;fill:var(--ink);letter-spacing:0}'
            '.t{font-family:var(--font-body);font-size:13px;fill:var(--mute,var(--ink))}</style>\n'
            '<div class="c"><svg width="960" height="288" viewBox="0 0 960 288">\n%s\n%s\n%s\n'
            '<text class="n" x="32" y="%.0f">%s</text><text class="t" x="32" y="262">%s</text></svg></div>\n' % (
                fills, other, size, 800 if heavy else 700, deriv, '\n'.join(blocks), '\n'.join(pat), text_y, tsp, tagline.replace('&', '&amp;')))
    return html, dict(row=row, why=why, size=size, lines=lines)


# ---------------------------------------------------------------- README
def readme(d, tk, comps, fails, missing, name, structural=None):
    cols = {t['name']: t['value'] for t in tk['color']['tokens']}
    L = []
    L.append('## Colour\n')
    if 'paper' in cols:
        L.append('- Set slides on `paper`%s.' % ('; put cards and panels on `surface`' if 'surface' in cols else ''))
    if 'ink' in cols:
        L.append('- Set headings and body copy in `ink`%s.' % ('; use `mute` for captions and secondary lines' if 'mute' in cols else ''))
    acc = [k for k in cols if k.startswith('accent-')]
    if acc:
        L.append('- Accents (%s) are ordered by how much of the source they cover; lead with `%s`. Put text on an accent fill in its `on-` token.' % (
            ', '.join('`%s`' % a for a in acc), acc[0]))
    if fails:
        L.append('- Contrast below 4.5:1 in the source palette, kept exact: %s.' % '; '.join(fails))
    L.append('\n## Type\n')
    for g in tk['type']['groups']:
        L.append('- %s styles in %s: %s.' % ('Other' if g['name'].startswith('Extra') else g['name'], tk['type']['families'][g['family']].split(',')[0].strip('"'), ', '.join('`%s` (%s)' % (s['name'], s['fontSize']) for s in g['styles'])))
    if missing:
        L.append('- No font file is bundled for %s; load it from your own licence or fall back to the stack.' % ', '.join(missing))
    g = d['grid']
    L.append('\n## Layout\n')
    cf = d.get('confidence', {})
    if cf.get('grid', {}).get('level') == 'low':
        L.append('- Low confidence: %s. Treat the grid below as a starting point only.' % cf['grid']['why'])
    if g.get('columns'):
        L.append('- Canvas %gx%g px: %d columns, %gpx gutter, %gpx margins (`grid-columns`, `grid-gutter`, `grid-margin`). Start and end blocks on column edges.' % (
            g['canvas'][0], g['canvas'][1], g['columns'], g['gutter'], g['margin_left']))
    else:
        L.append('- Canvas %gx%g px with %gpx side margins (`grid-margin`). The source follows no column grid; align to the margin and the spacing unit.' % (g['canvas'][0], g['canvas'][1], g['margin_left']))
    if d['spacing']['base_unit']:
        L.append('- Space things in multiples of `space-1` (%gpx).' % d['spacing']['base_unit'])
    L.append('\n## Shape\n')
    if tk.get('radius'):
        L.append('- Corner radii: %s. Do not invent others.' % ', '.join('`%s` (%s)' % (t['name'], t['value']) for t in tk['radius']['tokens']))
    if tk.get('shadow'):
        L.append('- Shadows: %s.' % ', '.join('`%s`' % t['name'] for t in tk['shadow']['tokens']))
    else:
        L.append('- The source uses no shadows; do not add any.')
    if structural:
        L.append('\n## Components\n')
        for grp in ('Elements', 'Blocks'):
            items = [c for c in structural['components'] + structural['atoms'] if c.get('group', 'Blocks' if c.get('kind') != 'atom' else 'Elements') == grp]
            if items:
                L.append('%s:' % grp)
                for c in items:
                    L.append('- `%s`: %s' % (''.join(w[:1].upper() + w[1:] for w in c['name'].split()), c.get('usage') or 'recurs %d times on %d slides.' % (c['instances'], c['n_slides'])))
        ls = structural.get('layout_status')
        if ls:
            L.append('\n## Layouts\n')
            L.append('Whole-slide templates are in `Layouts.md`, not components. ' + '; '.join('%s (%s)' % (n, s) for n, s in ls) + '. Use only verified layouts as templates; treat the rest as examples.')
    elif comps:
        L.append('\n## Components\n')
        for nm, c in comps.items():
            L.append('- `%s`: recurring %dx%d px shape. See its guidelines.' % (nm, c['w'], c['h']))
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------- assemble
def structural_files(res, tk):
    """Component previews/READMEs and a Layouts section from d2s.components.extract output."""
    import re as _re
    hexmap = {}
    for t in tk['color']['tokens']:
        if isinstance(t['value'], dict):
            continue        # a themed token (ink, paper) means different colours in different themes: an exemplar's fixed colour must not be bound to it
        hexmap.setdefault(t['value'].lower(), t['name'])

    def tokenise(body):
        return _re.sub(r'(color|background|border-top|border):([^;"]*?)(#[0-9a-fA-F]{6})', lambda m: '%s:%svar(--%s,%s)' % (m.group(1), m.group(2), hexmap[m.group(3).lower()], m.group(3)) if m.group(3).lower() in hexmap else m.group(0), body)
    out = {}
    for c in list(res['components']) + list(res.get('atoms', [])):
        w, h = c['size']
        nm = ''.join(w[:1].upper() + w[1:] for w in c['name'].split())
        atom = c.get('kind') == 'atom'   # components/<Comp> must be an ASCII identifier
        bg = c.get('bg', '#ffffff')
        bgv = 'var(--%s,%s)' % (hexmap[bg.lower()], bg) if bg.lower() in hexmap else bg
        out['components/%s/preview.html' % nm] = (
            '<!-- @dsCard group="%s" height=%d width=%d subtitle="%d instances on %d slides" -->\n<style>body{margin:0;padding:24px;background:%s}'
            '.stage{position:relative;width:%dpx;height:%dpx}</style>\n<div class="stage">\n%s\n</div>\n' % (
                c.get('group') or ('Atoms' if atom else 'Content blocks'), min(h + 48, 900), w + 48, c['instances'], c['n_slides'], bgv, w, h, tokenise(c['preview_body'])))
        sl = c['slots']
        if atom:
            pl = c['places'][0]
            lines = ['%s is a single element, %dx%d px, used %d times on %d slides of the source%s.' % (
                c['name'], w, h, c['instances'], c['n_slides'], (', in the same place %d%% of the time (about x %d, y %d)' % (round(c['consistent'] * 100), pl['x'], pl['y'])) if c['consistent'] >= 0.5 else ' in several places'), '']
            for s in sl:
                lines.append('- Style: %gpx, weight %s, %s. %s' % (s['px'], s['weight'], s['colour'], ('Text is fixed: "%s".' % s['examples'][0][:50]) if s['fixed'] and s['examples'] else 'The consumer provides the text, e.g. %s.' % ', '.join('"%s"' % e[:30] for e in s['examples'])))
            if len(c['places']) > 1:
                lines.append('- Placements seen: ' + '; '.join('x %d, y %d (%d times)' % (p['x'], p['y'], p['n']) for p in c['places'][:4]) + '.')
            if c.get('usage'):
                lines.insert(1, c['usage'])
            if c.get('provenance'):
                lines.append('\n_%s._' % c['provenance'])
            lines += ['', '- Do: use it where the layouts put it.', '- Do not: restyle it or move it off the grid.']
            out['components/%s/README.md' % nm] = '\n'.join(lines) + '\n'
            continue
        lines = ['%s is a %dx%d px block with %d member%s, found %d times on %d slide%s of the source.' % (
            c['name'], w, h, c['members'], '' if c['members'] == 1 else 's', c['instances'], c['n_slides'], '' if c['n_slides'] == 1 else 's'), '']
        if sl:
            lines.append('The consumer provides the text for each slot; fixed text stays as it is in the source.\n')
            for s in sl:
                lines.append('- **%s** (%gpx, weight %s, %s; its box is %dpx wide, about %d characters per line): %s' % (s['role'], s['px'], s['weight'], s['colour'], w, max(1, int(w / (0.55 * s['px']))),
                             ('fixed text, always "%s"' % s['examples'][0][:60]) if s['fixed'] else 'slot; for example %s' % ', '.join('"%s"' % e[:40] for e in s['examples'][:3])))
        if c.get('usage'):
            lines.insert(1, c['usage'])
        if c.get('provenance'):
            lines.append('\n_%s._' % c['provenance'])
        lines += ['', '- Do: keep the members in the same relative places and the type sizes above.', '- Do not: add members or change the type scale.']
        out['components/%s/README.md' % nm] = '\n'.join(lines) + '\n'
    L = ['# Layouts', '', 'Slides grouped by what they contain (background, pictures, headline size, number of text blocks, components). Slide numbers are in the source deck.', '']
    for lay in res['layouts'][:12]:
        L.append('- **%s**: %d slides, e.g. %s' % (lay['name'], lay['count'], ', '.join(str(s) for s in lay['slides'][:5])))
    out['Layouts.md'] = '\n'.join(L) + '\n'
    return out


def layout_files(res, slides_json, masters_json, tk, comps=None):
    """Layouts are templates that arrange components, not components. Each gets a showcase-page preview (the type's `page` flag,
    so it is not listed as a bundle component) and a section in Layouts.md with status, slots and the components it uses."""
    import re as _re, tempfile
    from . import gslides2claude as G
    hexmap = {}
    for t in tk['color']['tokens']:
        if isinstance(t['value'], dict):
            continue
        hexmap.setdefault(t['value'].lower(), t['name'])
    tok = lambda s: _re.sub(r'(color|background):([^;"]*?)(#[0-9a-fA-F]{6})', lambda m: '%s:%svar(--%s,%s)' % (m.group(1), m.group(2), hexmap[m.group(3).lower()], m.group(3)) if m.group(3).lower() in hexmap else m.group(0), s)
    work = tempfile.mkdtemp()
    ex = {v['exemplar'] - 1 for e in res for v in e['variants']}
    G.convert(slides_json, masters_json, work, only=ex)
    out = {}
    L = ['# Layouts', '',
         'A layout is a whole-slide template: where things go and which atoms and content blocks fill it. It is not a component. Each was proposed by Claude from the deck\'s exemplar slides and checked against the slides it claims. '
         '**Verified** means at least 75% of the claimed slides sit in families of three or more that match its recipe; **partly verified** and **unverified** say how little held up. Previews are showcase pages built from an exemplar slide, with placeholder pictures.', '',
         '| Layout | Status | Slides claimed | In verified families | Atoms | Content blocks |', '| --- | --- | --- | --- | --- | --- |']
    detail = []
    for e in res:
        used = []
        for v in e['variants']:
            for c in (comps or []):
                if v['exemplar'] in c.get('all_slides', []) and c['name'] not in used:
                    used.append(c['name'])
        lname = ''.join(w[:1].upper() + w[1:] for w in e['name'].split())
        bv = max(e['variants'], key=lambda v: v['n']) if e['variants'] else None
        an = []
        for a in (bv or {}).get('composition', {}).get('atoms', []):
            if a['atom'] not in an:
                an.append(a['atom'])
        L.append('| %s | %s | %d | %d%% | %s | %s |' % (e['name'], e['status'], e['claimed'], round(e['coverage'] * 100), ', '.join(an) or 'none', ', '.join(used) or 'none'))
        if not e['variants']:
            detail.append('## %s\n\n%s\n\n**Status: %s.** %s. No agreeing family of slides was found, so there is no preview.\n\nClaimed slides: %s.\n' % (e['name'], e['usage'], e['status'], e['provenance'], ', '.join(map(str, e['outliers']))))
            continue
        best = max(e['variants'], key=lambda v: v['n'])
        sec = open('%s/project/slides/s%03d.html' % (work, best['exemplar'])).read()
        sec = _re.sub(r'<img src="IMG:\d+"', '<img data-missing', sec)
        out['components/Layout%s/preview.html' % lname] = '<!-- @dsCard group="Layouts" page height=1080 width=1920 subtitle="%s" -->\n<style>body{margin:0}section{position:relative;width:1920px;height:1080px;overflow:hidden}</style>\n%s\n' % (e['status'], tok(sec))
        d = ['## %s' % e['name'], '', e['usage'], '', '**Status: %s.** %s.' % (e['status'], e['provenance']), '']
        comp = best.get('composition', {})
        at, fr = comp.get('atoms', []), comp.get('free', [])
        if at or fr:
            names = []
            for a in at:
                if a['atom'] not in names:
                    names.append(a['atom'])
            d.append('**Composition.** Atoms: %s. Free content: %s. %d of %d elements are atoms.' % (
                ', '.join(names) or 'none', '; '.join('%s at x %d, y %d' % (f['role'], f['x'], f['y']) for f in fr[:8]) or 'none', len(at), len(at) + len(fr)))
            off = [a['atom'] for a in at if not a['usual']]
            if off:
                d.append('Off their usual place on the exemplar: %s.' % ', '.join(sorted(set(off))))
            d.append('')
        if used:
            d.append('Content blocks used: %s.' % ', '.join(used))
        d.append('Variants checked: ' + '; '.join('%s (exemplar slide %d, %d slides, mean slot match %.2f, same atoms %d%%, %s)' % (v['label'], v['exemplar'], v['n'], v['mean'], round(v.get('comp_agree', 0) * 100), v['status']) for v in e['variants']) + '.')
        if e['outliers']:
            d.append('\nClaimed but not matching any family: slides %s.' % ', '.join(map(str, e['outliers'])))
        if e['weak_discriminator']:
            d.append('\nCaution: the recipe also matches many slides outside this layout, so it describes a sparse pattern more than a distinct layout.')
        d += ['', 'Slots of the exemplar:', '']
        for s in best['recipe']:
            if s['klass'] == 'text':
                d.append('- **%s** at x %d, y %d, width %d (%gpx, weight %s, %s): e.g. "%s"' % (s['role'], s['x'], s['y'], s['w'], s['px'], s['weight'], s['colour'], s['text'][:50]))
            else:
                d.append('- %s at x %d, y %d, %dx%d' % (s['role'], s['x'], s['y'], s['w'], s['h']))
        detail.append('\n'.join(d) + '\n')
    out['Layouts.md'] = '\n'.join(L) + '\n\n' + '\n'.join(detail)
    return out


def build(model, d, name, outdir, tagline=None, fetch=True, structural=None, layouts=None):
    cache = os.path.join(outdir, '.fontcache')
    proj = os.path.join(outdir, PROJECT)
    import shutil
    shutil.rmtree(proj, ignore_errors=True)   # no stale files from an earlier build
    os.makedirs(proj, exist_ok=True)
    tk, files, missing, fails, warn = build_tokens(d, name, cache, proj, fetch)
    problems = T.validate_claude_ds(tk)
    comps = find_components(model, d, tk) if not structural else {}
    cfiles = component_files(comps, tk) if not structural else {k: v for k, v in structural_files(structural, tk).items() if k.startswith('components/')}
    extra = {} if not structural else {k: v for k, v in structural_files(structural, tk).items() if not k.startswith('components/')}
    tag = tagline or '%d colours, %d type sizes, %s.' % (
        len(d['colour']['roles']), len(d['type']['sizes']),
        ('a %d-column grid' % d['grid']['columns']) if d['grid'].get('columns') else 'margins of %gpx' % d['grid'].get('margin_left', 0))
    cov, cinfo = cover(d, tk, name, tag)
    cfiles['components/Cover/preview.html'] = cov
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    idx = {"v": 3, "layout": "files", "createdOnFiles": {"v": 1, "at": now}, "title": name,
           "namespace": re.sub(r'\W+', '', name.title()) or 'Derived', "libraries": [], "sections": {}, "groups": [],
           "assetGroups": {}, "blobs": {}, "docs": {"readme": "project/README.md", "sections": []},
           "lastChange": {"by": "Claude", "at": now, "via": "deck2slides tokens", "note": "Derived from a deck"}}
    out = {'design-system.json': json.dumps(idx, indent=1), 'tokens.json': json.dumps(tk, indent=1, default=float),
           'README.md': readme(d, tk, comps, fails, missing, name, structural)}
    out.update(cfiles)
    out.update(extra)
    if layouts:
        out.update(layouts)
    for rel, text in out.items():
        p = os.path.join(proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, 'w').write(text)
    return dict(confidence=d.get('confidence'), problems=problems, components=list(comps) if not structural else [(c['name'], c['instances'], c['n_slides']) for c in structural['components']], cover=cinfo, contrast_fails=fails, fonts=sorted(files.values()),
                missing_fonts=missing, warnings=warn, files=sorted(list(out) + list(files.values())))


def compile_css(tk):
    """Local stand-in for the page's tokens.css, only to render previews offline."""
    L = [':root{']
    first = tk['color']['themes'][0]['id']
    for t in tk['color']['tokens']:
        v = t['value']
        L.append('--%s:%s;' % (t['name'], v[first] if isinstance(v, dict) else v))
    for fam in ('shadow', 'spacing', 'radius'):
        for t in tk.get(fam, {}).get('tokens', []):
            L.append('--%s:%s;' % (t['name'], t['value']))
    for k, v in tk['type']['families'].items():
        L.append('--font-%s:%s;' % (k, v))
    L.append('}')
    for f in tk['type']['fonts']:
        L.append('@font-face{font-family:"%s";src:url("%s");font-weight:%s}' % (f['family'], f['file'], f['weight']))
    for g in tk['type']['groups']:
        for s in g['styles']:
            L.append('.%s{font-family:var(--font-%s);font-size:%s;font-weight:%s;%s}' % (
                s['name'], g['family'], s['fontSize'], s['fontWeight'], ('line-height:%s' % s['lineHeight']) if 'lineHeight' in s else ''))
    return '\n'.join(L)
