import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from d2s import tokens

PPTX = os.path.join(os.path.dirname(__file__), '..', 'examples', 'five-page', 'five-page.pptx')


def test_five_page_ground_truth():
    d = tokens.derive(tokens.from_pptx(PPTX))
    g = d['grid']
    assert (g['columns'], g['gutter'], g['column_width'], g['margin_left'], g['margin_right']) == (12, 16.0, 124.0, 128.0, 128.0)
    roles = d['colour']['roles']
    assert roles['ink'] == '#14142E' and roles['paper'] == '#F5F2EA' and roles['accent-1'] == '#6B5BFF'
    assert [s['px'] for s in d['type']['sizes']][:3] == [144, 96, 56]


def test_blind_grid_finds_columns_and_margin():
    m = tokens.from_pptx(PPTX)
    m['no_guides'] = True
    m['elements'] = [e for e in m['elements'] if not (e['h'] >= 860 and e['kind'] == 'shape' and not e['runs'])]
    g = tokens.derive(m)['grid']
    assert g['columns'] == 12 and g['margin_left'] == 128


def test_split_font():
    assert tokens.split_font('Inter SemiBold') == ('Inter', 600)
    assert tokens.split_font('Roboto', True) == ('Roboto', 700)
