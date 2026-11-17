"""How much of a deck does the system explain? Each element of sampled slides is classed as furniture, media, pattern, role or
unexplained. A text element counts as a role only if its size is one of the system's text styles AND it sits where a recipe puts that
style (so a role is not explained just because a size exists); anything else stays unexplained."""
import json, random
from collections import Counter
from . import components as C, recipes as R


def classify(slide_desc, tk, spec, atoms_keys, patterns, chrome):
    styles = spec['styles']
    sizes = {round(s['px']) for s in styles.values()}
    # expected positions of text slots from every recipe
    slots = []
    for r in spec['recipes']:
        for el in r.get('slots', []):
            if el['type'] in ('text', 'figure'):
                slots.append((R.xpos(el['x'], tk), el['y'], styles.get(el.get('style'), {}).get('px')))
        for rp in r.get('repeats', []):
            for i in range(rp['max']):
                r_, c_ = divmod(i, rp['per_row'])
                for el in rp['slots']:
                    if el['type'] in ('text', 'figure'):
                        slots.append((R.xpos(el['x'], tk) + c_ * rp['x_step'], el['y'] + r_ * rp['y_step'], styles.get(el.get('style'), {}).get('px')))
    in_pattern = set()
    for members in patterns:
        for si, g in members:
            if si == slide_desc['_i']:
                in_pattern.update(id(d) for d in g)
    out = Counter()
    for d in slide_desc['els']:
        if d['kind'] in ('empty', 'other') or C._is_chrome(d, chrome):
            continue
        k = C.atom_key(d)
        if id(d) in in_pattern:
            out['pattern'] += 1
        elif d['kind'] == 'image' or (d['kind'] == 'box' and d['w'] > 0.9 * 1920):
            out['media'] += 1
        elif k in atoms_keys:
            out['furniture'] += 1
        elif d['kind'] in ('text', 'panel') and d['runs']:
            px = d['runs'][0]['px']
            near = any(abs(d['x'] - x) < 60 and abs(d['y'] - y) < 60 and (sp is None or abs(sp - px) < 2) for x, y, sp in slots)
            out['role' if near else 'unexplained text'] += 1
        else:
            out['unexplained other'] += 1
    return out
