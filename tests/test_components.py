import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from d2s import components as C


def _tb(oid, x, y, w, h, text, pt, weight=400, colour=(0, 0, 0)):
    return {'objectId': oid, 'size': {'width': {'magnitude': w}, 'height': {'magnitude': h}},
            'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': x, 'translateY': y},
            'shape': {'shapeType': 'TEXT_BOX', 'shapeProperties': {}, 'text': {'textElements': [
                {'paragraphMarker': {'style': {}}},
                {'textRun': {'content': text + '\n', 'style': {'fontSize': {'magnitude': pt}, 'weightedFontFamily': {'fontFamily': 'DM Sans', 'weight': weight},
                                                               'foregroundColor': {'opaqueColor': {'rgbColor': {'red': colour[0], 'green': colour[1], 'blue': colour[2]}}}}}}]}}}


def _deck(tmp, n=4):
    slides = []
    people = [('Ada Lovelace', 'Engineer'), ('Alan Turing', 'Researcher'), ('Grace Hopper', 'Admiral'), ('Linus Torvalds', 'Maintainer')]
    for i in range(n):
        n_, r_ = people[i % 4]
        # same 'name and role' pair at a different place on each slide, plus an unrelated big headline
        slides.append({'objectId': 's%d' % i, 'pageProperties': {'pageBackgroundFill': {'solidFill': {'color': {'rgbColor': {'red': 1, 'green': 1, 'blue': 1}}}}},
                       'pageElements': [_tb('a%d' % i, 600000 + i * 300000, 1200000 + i * 100000, 2000000, 300000, n_, 14, 500),
                                        _tb('b%d' % i, 600000 + i * 300000, 1500000 + i * 100000, 2000000, 250000, r_, 9, 400),
                                        _tb('h%d' % i, 600000, 200000, 5000000, 600000, 'Heading %d' % i, 40, 700)]})
    p = os.path.join(tmp, 's.json')
    json.dump({'content': {'slides': slides}}, open(p, 'w'))
    return p


def test_recurring_pair_becomes_a_component_with_slots():
    r = C.extract(_deck(tempfile.mkdtemp()), None)
    names = [c['name'] for c in r['components']]
    assert 'Name and role' in names
    c = next(c for c in r['components'] if c['name'] == 'Name and role')
    assert c['instances'] == 4 and c['n_slides'] == 4
    slots = {s['role']: s for s in c['slots']}
    assert not slots['title']['fixed'] and not slots['body']['fixed'] and 'Ada Lovelace' in slots['title']['examples']


def test_identical_text_on_many_slides_is_chrome_not_a_component():
    tmp = tempfile.mkdtemp()
    p = _deck(tmp)
    d = json.load(open(p))
    for s in d['content']['slides']:
        s['pageElements'].append(_tb('f' + s['objectId'], 100000, 4800000, 1500000, 200000, 'Company 2026', 9, 400))
    json.dump(d, open(p, 'w'))
    r = C.extract(p, None)
    assert r['chrome'] >= 1
