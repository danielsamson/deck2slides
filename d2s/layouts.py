"""Layout recipes from a deck's slides: group, pick an exemplar, describe it as slots, and VERIFY the description against
every slide it claims to cover (and against slides it should not cover).

Steps (the split agreed with the user: derive the structure, fill in the meaning, verify the result):
  1. derive   - group slides by what they contain, choose the medoid slide of each group as exemplar, turn it into a recipe
                (slots with role, size, colour and position)
  2. propose  - a catalogue (JSON) naming each layout and writing its usage line, authored by looking at the exemplars;
                it can merge groups and add recipes the derivation missed (`slides` lists the evidence)
  3. verify   - every catalogue entry is scored against its slides: the share of its slots found in each slide, and the
                share of OTHER slides it also matches (a layout that matches everything says nothing)
Each entry carries provenance: derived / proposed, with the slide numbers that back it."""
from __future__ import annotations
import json
from collections import defaultdict
from . import components as C, gslides2claude as G

POS_TOL = 0.07      # slot centre may move this fraction of the canvas
W_RATIO = (0.6, 1.7)
VERIFIED_AT = 0.75  # mean slot match needed to call a layout verified


def _klass(d):
    return {'text': 'text', 'panel': 'text', 'image': 'image', 'line': 'line', 'box': 'box'}.get(d['kind'])


def recipe_of(desc, chrome):
    """Slots of one slide: its non-chrome elements, each with a role."""
    els = [d for d in desc if not C._is_chrome(d, chrome) and _klass(d)
           and 0 <= d['x'] + d['w'] / 2 <= 1920 and 0 <= d['y'] + d['h'] / 2 <= 1080]   # parked off-canvas notes are not part of a layout
    texts = sorted([d for d in els if _klass(d) == 'text'], key=lambda d: -d['runs'][0]['px'])
    top = texts[0]['runs'][0]['px'] if texts else 0
    slots = []
    for d in els:
        role = _klass(d)
        if role == 'text':
            px = d['runs'][0]['px']
            role = 'title' if px >= top * 0.9 else 'caption' if px <= top * 0.45 else 'body'
        slots.append(dict(role=role, klass=_klass(d), x=d['x'], y=d['y'], w=d['w'], h=d['h'],
                          px=d['runs'][0]['px'] if d['runs'] else None, colour=d['runs'][0]['colour'] if d['runs'] else (d['fill'] or d['stroke']),
                          weight=d['runs'][0]['weight'] if d['runs'] else None, text=d['text'][:80]))
    return slots


def _close(s, d, canvas=(1920, 1080)):
    if s['klass'] != _klass(d):
        return False
    scx, scy = s['x'] + s['w'] / 2, s['y'] + s['h'] / 2
    dcx, dcy = d['x'] + d['w'] / 2, d['y'] + d['h'] / 2
    if abs(scx - dcx) > POS_TOL * canvas[0] or abs(scy - dcy) > POS_TOL * canvas[1]:
        return False
    r = d['w'] / max(s['w'], 1)
    return W_RATIO[0] <= r <= W_RATIO[1]


def match(slots, desc, chrome):
    """Share of the recipe's slots a slide fills, and how many of its own elements the recipe leaves unexplained."""
    els = [d for d in desc if not C._is_chrome(d, chrome) and _klass(d)]
    used, hit = set(), 0
    for s in slots:
        for i, d in enumerate(els):
            if i not in used and _close(s, d):
                used.add(i)
                hit += 1
                break
    return (hit / len(slots) if slots else 0.0), (len(els) - len(used))


def medoid(members, descs, chrome):
    best, bs = members[0], -1
    for m in members[:25]:
        rec = recipe_of(descs[m], chrome)
        s = sum(match(rec, descs[o], chrome)[0] for o in members[:25] if o != m) / max(1, min(len(members), 25) - 1)
        if s > bs:
            best, bs = m, s
    return best, bs


def derive(slides_json, masters_json):
    data = json.load(open(slides_json))['content']['slides']
    descs = [[C.describe(e) for e in C.flatten(s)] for s in data]
    chrome = C.find_chrome(descs, len(data))
    res = C.extract(slides_json, masters_json)
    groups = []
    for lay in res['layouts']:
        members = [s - 1 for s in lay['slides']]
        ex, sc = medoid(members, descs, chrome)
        groups.append(dict(name=lay['name'], slides=lay['slides'], exemplar=ex + 1, self_score=round(sc, 2),
                           recipe=recipe_of(descs[ex], chrome)))
    return data, descs, chrome, groups


def verify(entry, descs, chrome):
    """entry: {name, usage, slides:[1-based evidence], exemplar:1-based}. Scores the recipe built from the exemplar."""
    rec = recipe_of(descs[entry['exemplar'] - 1], chrome)
    scores = {s: match(rec, descs[s - 1], chrome) for s in entry['slides']}
    mean = sum(v[0] for v in scores.values()) / max(1, len(scores))
    full = sum(1 for v in scores.values() if v[0] >= 0.99)
    others = [i for i in range(len(descs)) if (i + 1) not in scores]
    false_pos = [i + 1 for i in others if match(rec, descs[i], chrome)[0] >= 0.99 and abs(len(rec) - len([d for d in descs[i] if not C._is_chrome(d, chrome) and _klass(d)])) <= 1]
    return dict(recipe=rec, mean=round(mean, 2), full=full, n=len(scores), per_slide={k: round(v[0], 2) for k, v in scores.items()},
                extras={k: v[1] for k, v in scores.items()}, false_positives=false_pos[:12], n_false=len(false_pos),
                status='verified' if mean >= VERIFIED_AT else 'unverified')


def families(descs, chrome, min_size=3, thr=0.85):
    """Group slides directly by recipe agreement (both ways, so a sparse slide does not swallow a busy one), greedily taking
    the seed with the most agreeing slides each round. Coarser than a key on counts, and every member provably matches."""
    n = len(descs)
    recs = [recipe_of(d, chrome) for d in descs]
    sc = {}

    def agree(i, j):
        k = (i, j) if i < j else (j, i)
        if k not in sc:
            sc[k] = min(match(recs[i], descs[j], chrome)[0], match(recs[j], descs[i], chrome)[0]) if recs[i] and recs[j] else 0.0
        return sc[k]
    left, out = set(range(n)), []
    while left:
        best = max(left, key=lambda i: sum(1 for j in left if j == i or agree(i, j) >= thr))
        fam = [j for j in left if j == best or agree(best, j) >= thr]
        if len(fam) < min_size:
            break
        out.append(dict(exemplar=best + 1, slides=sorted(j + 1 for j in fam), slots=len(recs[best])))
        left -= set(fam)
    return out, sorted(j + 1 for j in left)


def refine(slides, descs, chrome, thr=0.7, min_size=2):
    """Split one proposed layout's slides into sub-families that really agree (1-based in, 1-based out); the rest are outliers."""
    idx = [s - 1 for s in slides]
    recs = {i: recipe_of(descs[i], chrome) for i in idx}
    left, out = set(idx), []

    def agree(i, j):
        return min(match(recs[i], descs[j], chrome)[0], match(recs[j], descs[i], chrome)[0]) if recs[i] and recs[j] else 0.0
    while left:
        best = max(left, key=lambda i: sum(1 for j in left if j == i or agree(i, j) >= thr))
        fam = [j for j in left if j == best or agree(best, j) >= thr]
        if len(fam) < min_size:
            break
        out.append(dict(exemplar=best + 1, slides=sorted(j + 1 for j in fam)))
        left -= set(fam)
    return out, sorted(j + 1 for j in left)


def build_catalogue(catalogue, descs, chrome, atoms=None):
    """Verify every proposal; split variants that do not hold together; report outliers and look-alikes."""
    res = []
    for e in catalogue['layouts']:
        variants, outliers = [], []
        for v in e['variants']:
            subs, out = refine(v['slides'], descs, chrome)
            outliers += out
            for k, s in enumerate(subs):
                r = verify(dict(name=e['name'], slides=s['slides'], exemplar=s['exemplar']), descs, chrome)
                comp = C.composition(descs[s['exemplar'] - 1], atoms, chrome) if atoms else ([], [])
                ex_set = {a['atom'] for a in comp[0]}
                jac = []
                for sn in s['slides']:
                    st = {a['atom'] for a in C.composition(descs[sn - 1], atoms, chrome)[0]} if atoms else set()
                    jac.append(len(st & ex_set) / max(1, len(st | ex_set)))
                variants.append(dict(comp_agree=round(sum(jac) / max(1, len(jac)), 2), composition=dict(atoms=comp[0], free=comp[1]), label=v['label'] + ('' if len(subs) == 1 else ' %d' % (k + 1)), exemplar=s['exemplar'],
                                     slides=s['slides'], mean=r['mean'], full=r['full'], n=r['n'], false_positives=r['false_positives'],
                                     n_false=r['n_false'], status=r['status'], recipe=r['recipe']))
        claimed = sum(len(v['slides']) for v in e['variants'])
        for v in variants:   # a family of two agreeing slides is a pair, not evidence of a layout
            v['status'] = 'verified' if v['mean'] >= VERIFIED_AT and v['n'] >= 3 else 'pair' if v['mean'] >= VERIFIED_AT else 'unverified'
        solid = sum(v['n'] for v in variants if v['status'] == 'verified')
        pairs = sum(v['n'] for v in variants if v['status'] == 'pair')
        cov = solid / max(claimed, 1)
        weak = any(v['n_false'] > v['n'] for v in variants)
        res.append(dict(name=e['name'], usage=e['usage'], claimed=claimed, coverage=round(cov, 2), weak_discriminator=weak,
                        provenance='Proposed by Claude from exemplar slides; %d of %d claimed slides sit in verified families of 3 or more' % (solid, claimed),
                        variants=variants, outliers=outliers,
                        status='verified' if cov >= 0.75 else 'partly verified' if (solid + pairs) / max(claimed, 1) >= 0.3 else 'unverified'))
    return res
