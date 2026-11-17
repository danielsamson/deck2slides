"""Slide recipes: a small spec per slide type (what is on it, in grid units, in token styles) plus a renderer, an extractor and a
recreate-and-compare test.

A recipe says: theme, furniture and slots (text, rule, box, picture), where each sits (a grid column and offset, a y in px, a
width in columns), which named text style it uses, how much it can hold, and which source slides it was derived from.
`render(recipe, content)` turns a recipe plus content into a slide section in the Claude Slides format.
`extract(recipe, slide)` reads the content of a source slide that follows the recipe back out, so the recipe can be rendered with
the original words and compared with the original slide: that comparison is the test of a recipe."""
from __future__ import annotations
import html, json
from . import components as C, gslides2claude as G

PT = G.PT


def grid(tokens):
    g = {t['name']: float(t['value'].rstrip('px')) for t in tokens.get('grid', {}).get('tokens', []) if t['value'].endswith('px')}
    return g['grid-margin'], g['grid-gutter'], g['grid-column']


def xpos(spec, tk):
    m, gut, col = grid(tk)
    if 'px' in spec:
        return spec['px']
    return m + spec['col'] * (col + gut) + spec.get('dx', 0)


def width(el, tk):
    m, gut, col = grid(tk)
    if 'w' in el:
        return el['w']
    return el['w_cols'] * (col + gut) - gut + el.get('dw', 0)


def colour(c, recipe, tk):
    """A colour reference to CSS: a token name, 'hex:#rrggbb', or ink/paper which follow the theme."""
    if c.startswith('hex:'):
        return c[4:]
    return 'var(--%s)' % c


def text_box(el, recipe, tk, runs_html, x, y):
    st = recipe['styles'][el['style']]
    w = width(el, tk)
    jc = {'top': 'flex-start', 'middle': 'center', 'bottom': 'flex-end'}[el.get('valign', 'top')]
    return ('<div style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;box-sizing:border-box;padding:6.0px 8.0px;'
            'display:flex;flex-direction:column;justify-content:%s">%s</div>') % (x, y, w, el['h'], jc, runs_html)


def para(p_runs, st, recipe, tk, align='left', default_colour=None):
    spans = ''.join('<span style="color:%s">%s</span>' % (colour(r.get('c') or default_colour or st['colour'], recipe, tk), html.escape(r['t'])) for r in p_runs)
    return ('<p style="margin:0px 0 0px;font-family:\'%s\',Arial,sans-serif;font-size:%.1fpx;line-height:%.1fpx;font-weight:%d;color:%s;text-align:%s">%s</p>'
            % (recipe['font'], st['px'], st['px'] * st['lh'], st['weight'], colour(default_colour or st['colour'], recipe, tk), align, spans))


def render_element(el, recipe, tk, content, ox=0.0, oy=0.0):
    x, y = xpos(el['x'], tk) + ox, el['y'] + oy
    t = el['type']
    if t == 'text':
        st = recipe['styles'][el['style']]
        paras = content or []
        inner = ''.join(para(p['runs'], st, recipe, tk, el.get('align', 'left'), p.get('c')) for p in paras)
        return text_box(el, recipe, tk, inner, x, y) if paras else ''
    if t == 'figure':          # a big value with a smaller unit on the same baseline
        st, us = recipe['styles'][el['style']], recipe['styles'][el['unit_style']]
        if not content:
            return ''
        row = '<div style="display:flex;align-items:baseline;gap:%.0fpx">%s%s</div>' % (
            0.33 * st['px'], para([{'t': content['value']}], st, recipe, tk), para([{'t': content['unit']}], us, recipe, tk) if content.get('unit') else '')
        return text_box(el, recipe, tk, row, x, y)
    if t == 'rule':
        return '<hr style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;border:0;border-top:%.1fpx solid %s;margin:0">' % (x, y, width(el, tk), el.get('weight', 2), colour(el['colour'], recipe, tk))
    if t == 'box':
        return '<div style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;box-sizing:border-box;background:%s;border-radius:%.0fpx"></div>' % (
            x, y, width(el, tk), el['h'], colour(el['colour'], recipe, tk), el.get('radius', 0))
    if t == 'image':
        src = ('src="IMG:%s" ' % content) if isinstance(content, str) else ''
        return '<img %salt="%s" style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;object-fit:cover;%s">' % (
            src, html.escape(el.get('alt', 'Picture')), x, y, width(el, tk), el['h'], ('border-radius:%.0fpx' % el['radius']) if el.get('radius') else '')
    return ''


def render(recipe, content, tk):
    """content: {slot_id: paragraphs | {value, unit}}, repeats: {repeat_id: [ {slot_id: ...}, ... ]}. Returns a <section>."""
    parts = []
    if content.get('__bg'):
        parts.append('<img src="IMG:%s" alt="" style="position:absolute;left:0px;top:0px;width:1920px;height:1080px;object-fit:cover">' % content['__bg'])
    for el in recipe.get('furniture', []) + recipe.get('slots', []):
        parts.append(render_element(el, recipe, tk, content.get(el['id'])))
    for rp in recipe.get('repeats', []):
        items = content.get(rp['id'], [])[:rp['max']]
        for i, item in enumerate(items):
            r_, c_ = divmod(i, rp['per_row'])
            ox = c_ * rp['x_step']
            oy = r_ * rp['y_step']
            for el in rp['slots']:
                parts.append(render_element(el, recipe, tk, item.get(el['id']), ox, oy))
    cls = 'th-%s' % recipe['theme']
    bg = ' style="background:%s"' % recipe['background'] if recipe.get('background') else ''
    return '<section id="%s" class="%s"%s>\n%s\n</section>' % (recipe['id'], cls, bg, '\n'.join(p for p in parts if p))


# ------------------------------------------------------------------ extraction (source slide -> content)
def _map_colour(hexc, recipe):
    return recipe.get('colour_map', {}).get((hexc or '').lower())


def _paragraphs(desc, recipe, st):
    conv = G.Conv({}, '/tmp/d2s-fontcache')
    out = []
    for p in conv.paragraphs(desc['raw']['shape']['text']['textElements']):
        runs = []
        for r in p['runs']:
            tx = r.get('content', '').rstrip('\n')
            if not tx.strip():
                continue
            hexc = C._col(r.get('style', {}).get('foregroundColor'))
            c = _map_colour(hexc, recipe)
            runs.append(dict(t=tx, c=c if c and c != st['colour'] else None))
        if runs:
            out.append(dict(runs=runs))
    return out


def _nearest(descs, x, y, kinds, tol=70, used=None):
    best, bd = None, 1e9
    for d in descs:
        if d['kind'] not in kinds or (used is not None and id(d) in used):
            continue
        dd = abs(d['x'] - x) + abs(d['y'] - y)
        if dd < bd:
            best, bd = d, dd
    return best if bd <= tol else None


def extract_element(el, recipe, tk, descs, ox=0.0, oy=0.0, used=None):
    x, y = xpos(el['x'], tk) + ox, el['y'] + oy
    if el['type'] == 'text':
        d = _nearest(descs, x, y, ('text', 'panel'), used=used)
        if not d:
            return None
        used.add(id(d))
        return _paragraphs(d, recipe, recipe['styles'][el['style']])
    if el['type'] == 'figure':
        d = _nearest(descs, x, y, ('text', 'panel'), used=used)
        if not d:
            return None
        used.add(id(d))
        big = [r for r in d['runs'] if r['px'] >= recipe['styles'][el['style']]['px'] * 0.9]
        small = [r for r in d['runs'] if r['px'] < recipe['styles'][el['style']]['px'] * 0.9]
        return dict(value=' '.join(r['text'] for r in big), unit=' '.join(r['text'] for r in small))
    if el['type'] == 'image':
        d = _nearest(descs, x, y, ('image',), tol=60, used=used)
        if d:
            used.add(id(d))
            return d['raw']['objectId']
        return None
    return True if el['type'] in ('rule', 'box') else None


def extract(recipe, slide_desc, tk, slide_no=None):
    used = set()
    content = {}
    if recipe.get('photo_background') and slide_no:
        content['__bg'] = 'bg%d' % slide_no
    for el in recipe.get('furniture', []) + recipe.get('slots', []):
        v = extract_element(el, recipe, tk, slide_desc, used=used)
        if v is not None:
            content[el['id']] = v
    for rp in recipe.get('repeats', []):
        items = []
        for i in range(rp['max']):
            r_, c_ = divmod(i, rp['per_row'])
            item, got = {}, False
            for el in rp['slots']:
                v = extract_element(el, recipe, tk, slide_desc, c_ * rp['x_step'], r_ * rp['y_step'], used)
                if v is not None and v is not True:
                    item[el['id']] = v
                    got = True
            if not got:
                break
            items.append(item)
        content[rp['id']] = items
    return content
