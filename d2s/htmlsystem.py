"""Rationalise a hand-styled (freestyle) HTML deck into a small design system.

Input: the census of computed styles (js/census.cjs). The deck's own declared roles (class names) are kept; every value the
deck uses is snapped to a short scale, and the report says how much of the deck already sat on that scale, which values were
merged, and where a slide breaks its own rule. Nothing here is specific to one deck: scales are inputs, defaults are generic.
"""
from __future__ import annotations
import json, re, collections

TYPE_SCALE = [20, 24, 28, 40, 56, 88, 120, 220]
RADIUS_SCALE = [4, 12, 20, 28, 40, 9999]
SPACE_SCALE = [4, 8, 12, 16, 24, 32, 48, 80]


def snap(v, scale, up_below=24):
    """Nearest scale step. A tie goes up for small values (legibility, touch) and down for large ones."""
    best = min(scale, key=lambda s: (abs(s - v), -s if v <= up_below else s))
    return best


def _rgb(s):
    n = [float(x) for x in re.findall(r'[\d.]+', s)]
    return n


def hexof(s):
    n = _rgb(s)
    if len(n) < 3:
        return None
    return '#%02x%02x%02x' % tuple(int(round(x)) for x in n[:3])


def alpha(s):
    n = _rgb(s)
    return n[3] if len(n) == 4 else 1.0


def scale_report(values, scale, up_below=24, label='px'):
    """values: Counter of raw value -> uses. Returns the mapping, share already on scale and per-step merged values."""
    total = sum(values.values())
    on = sum(c for v, c in values.items() if v in scale)
    merged = collections.defaultdict(list)
    for v, c in sorted(values.items()):
        merged[snap(v, scale, up_below)].append((v, c))
    return dict(total=total, on_scale=round(on / total, 3) if total else 1, distinct=len(values),
                steps={str(k): [dict(value=v, uses=c) for v, c in vs] for k, vs in sorted(merged.items())})


def analyse(rows, deck):
    text = [r for r in rows if r['text']]
    sizes = collections.Counter()
    for r in text:
        sizes[r['size']] += 1
    radii = collections.Counter()
    for r in rows:
        m = re.match(r'([\d.]+)(px|%)', r['radius'])
        if m and float(m.group(1)) > 0:
            radii[9999 if m.group(2) == '%' else round(float(m.group(1)))] += 1
    gaps = collections.Counter(round(r['gap']) for r in rows if r['gap'])
    out = dict(
        type=scale_report(sizes, TYPE_SCALE), radius=scale_report(radii, RADIUS_SCALE, up_below=0), spacing=scale_report(gaps, SPACE_SCALE),
        families=dict(collections.Counter(r['font'] for r in text).most_common()),
        inline_share=round(sum(1 for r in rows if r['inline']) / max(1, len(rows)), 3),
        elements=len(rows), text_elements=len(text), slides=len(deck['order']))
    # type role table: (font, weight, snapped size) -> uses, with the classes that carry it
    roles = collections.defaultdict(lambda: dict(uses=0, classes=collections.Counter(), raw=collections.Counter(), sample=''))
    for r in text:
        k = (r['font'], r['weight'], snap(r['size'], TYPE_SCALE))
        e = roles[k]
        e['uses'] += 1
        e['raw'][r['size']] += 1
        for c in (r['cls'] or '').split():
            e['classes'][c] += 1
        e['sample'] = e['sample'] or r['text']
    out['roles'] = [dict(font=k[0], weight=k[1], size=k[2], uses=v['uses'], classes=dict(v['classes'].most_common(4)),
                         raw=dict(sorted(v['raw'].items())), sample=v['sample'])
                    for k, v in sorted(roles.items(), key=lambda kv: (-kv[0][2], -kv[1]['uses']))]
    # colours
    tc, bc = collections.Counter(), collections.Counter()
    for r in rows:
        if r['text'] and hexof(r['color']):
            tc[hexof(r['color'])] += len(r['text'])
        if r['tag'] != 'img' and alpha(r['bg']) > 0:
            bc[(hexof(r['bg']), round(alpha(r['bg']), 2))] += r['w'] * r['h'] // 1000
    out['text_colours'] = tc.most_common(20)
    out['fills'] = [dict(hex=h, alpha=a, area=n) for (h, a), n in bc.most_common(24)]
    sh = collections.Counter(r['shadow'] for r in rows if r['shadow'] != 'none')
    out['shadows'] = sh.most_common(14)
    # titles: each slide's largest heading against the rule
    heads = {}
    for r in rows:
        if r['tag'] in ('h1', 'h2') and r['slide'] not in heads:
            heads[r['slide']] = r
    out['titles'] = {s: dict(size=h['size'], y=h['y'], x=h['x'], inline=h['inline']) for s, h in heads.items()}
    return out


def claude_tokens(name, spec):
    """spec: authored, rationalised system (colours with roles, type styles, shadows, ...) -> Claude Design System tokens.json."""
    fam = spec['families']
    groups = []
    by = collections.OrderedDict()
    for s in spec['type']:
        by.setdefault(s['family'], []).append(dict(name=s['name'], fontSize='%dpx' % s['size'], fontWeight=s['weight'],
                                                   lineHeight=s['lh'], usage=s['usage']))
    labels = spec.get('family_labels', {})
    for k, sty in by.items():
        groups.append(dict(name=labels.get(k, k.title()), family=k, styles=sty))
    out = dict(name=name, version=1,
               color=dict(themes=spec.get('themes', [dict(id='light', name='Light')]), tokens=spec['colors']),
               type=dict(fonts=[], families=fam, groups=groups),
               spacing=dict(tokens=[dict(name='space-%d' % s, value='%dpx' % s, usage=spec['space_usage'].get(str(s), 'Spacing step.')) for s in spec.get('space', SPACE_SCALE)]),
               radius=dict(tokens=spec['radius']),
               shadow=dict(tokens=spec['shadows']))
    return out
