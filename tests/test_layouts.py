import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from d2s import layouts as L, components as C
from test_components import _tb


def _descs(slides):
    return [[C.describe(e) for e in C.flatten(s)] for s in slides]


def _slide(title_x, with_body=True, i=0):
    els = [_tb('t%d' % i, title_x, 600000, 5000000, 800000, 'Headline %d' % i, 40, 700)]
    if with_body:
        els.append(_tb('b%d' % i, title_x, 1800000, 4000000, 600000, 'Body text %d' % i, 14, 400))
    return {'objectId': 's%d' % i, 'pageProperties': {}, 'pageElements': els}


def test_agreeing_slides_verify_and_a_different_one_does_not():
    slides = [_slide(600000, True, i) for i in range(4)] + [_slide(4000000, False, 9)]
    descs = _descs(slides)
    v = L.verify({'name': 'x', 'slides': [1, 2, 3, 4], 'exemplar': 1}, descs, set())
    assert v['mean'] == 1.0 and v['status'] == 'verified'
    v2 = L.verify({'name': 'x', 'slides': [1, 5], 'exemplar': 1}, descs, set())
    assert v2['mean'] < 1.0                      # the odd slide lowers the score


def test_refine_splits_a_mixed_group_and_reports_outliers():
    slides = [_slide(600000, True, i) for i in range(3)] + [_slide(4200000, True, 5 + i) for i in range(3)] + [_slide(2400000, False, 20)]
    descs = _descs(slides)
    subs, out = L.refine(list(range(1, 8)), descs, set())
    assert len(subs) == 2 and out == [7]


def test_status_needs_families_of_three():
    slides = [_slide(600000, True, i) for i in range(2)]
    descs = _descs(slides)
    cat = {'layouts': [{'name': 'Pair', 'usage': 'u', 'variants': [{'label': 'a', 'exemplar': 1, 'slides': [1, 2]}]}]}
    res = L.build_catalogue(cat, descs, set())
    assert res[0]['variants'][0]['status'] == 'pair' and res[0]['status'] != 'verified'
