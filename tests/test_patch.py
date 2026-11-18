from d2s import patch
from d2s.config import EMU_PER_PX as K

def el(oid, cx, cy, w, h):
    return {'objectId': oid, 'size': {'width': {'magnitude': w * K, 'unit': 'EMU'}, 'height': {'magnitude': h * K, 'unit': 'EMU'}},
            'transform': {'scaleX': 1, 'scaleY': 1, 'translateX': (cx - w / 2) * K, 'translateY': (cy - h / 2) * K, 'unit': 'EMU'}}

SL = [{'id': 'a', 'i': 0, 'items': [{'cx': 500, 'cy': 300, 'w': 400, 'h': 100}]}]

def test_moves_matching_block_by_minus_offset():
    live = {'slides': [{'objectId': 'p1', 'pageElements': [el('p1_i2', 500, 300, 400, 100), el('p1_i3', 900, 900, 50, 50)]}]}
    reqs, rep = patch.plan(SL, live, {'a:0': {'dy': 24.0, 'dx': -6.0}})
    assert len(reqs) == 1 and rep[0][1] == 'patched'
    r = reqs[0]['updatePageElementTransform']
    assert r['objectId'] == 'p1_i2' and r['applyMode'] == 'ABSOLUTE'
    assert abs(r['transform']['translateY'] - (250 - 24) * K) < 1 and abs(r['transform']['translateX'] - (300 + 6) * K) < 1

def test_ambiguous_or_missing_is_skipped_not_guessed():
    twin = {'slides': [{'objectId': 'p1', 'pageElements': [el('x', 500, 300, 400, 100), el('y', 502, 301, 400, 100)]}]}
    assert patch.plan(SL, twin, {'a:0': {'dy': 10}})[0] == []
    none = {'slides': [{'objectId': 'p1', 'pageElements': [el('x', 800, 800, 400, 100)]}]}
    reqs, rep = patch.plan(SL, none, {'a:0': {'dy': 10}})
    assert reqs == [] and rep[0][1] == 'skipped'

def test_small_offsets_and_rotated_elements_are_left_alone():
    live = {'slides': [{'objectId': 'p1', 'pageElements': [el('p1_i2', 500, 300, 400, 100)]}]}
    assert patch.plan(SL, live, {'a:0': {'dy': 1.0}})[0] == []
    rot = el('r', 500, 300, 400, 100); rot['transform']['shearX'] = 0.2
    assert patch.plan(SL, {'slides': [{'objectId': 'p1', 'pageElements': [rot]}]}, {'a:0': {'dy': 10}})[0] == []
