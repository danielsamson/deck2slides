import os, sys, re, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from d2s import tokens, dsbuild

PPTX = os.path.join(os.path.dirname(__file__), '..', 'examples', 'five-page', 'five-page.pptx')


def test_contrast_known_values():
    assert abs(dsbuild.contrast('#000000', '#ffffff') - 21) < 0.01
    assert dsbuild.contrast('#777777', '#ffffff') < 4.6


def test_shadows_measured_from_pptx():
    d = tokens.derive(tokens.from_pptx(PPTX))
    sh = d['shape']['shadows']
    assert {(s['dy'], s['blur']) for s in sh} >= {(24, 48), (32, 64)}


def test_build_tree_no_network():
    m = tokens.from_pptx(PPTX)
    d = tokens.derive(m)
    out = tempfile.mkdtemp()
    rep = dsbuild.build(m, d, 'Five Page', out, fetch=False)
    assert rep['problems'] == []
    assert 'Card' in rep['components']
    cover = open(os.path.join(out, 'project/components/Cover/preview.html')).read()
    assert cover.startswith('<!-- @dsCard height=288 -->')
    assert '9999px' not in cover          # SVG rx of 9999px draws an ellipse
    assert not os.path.exists(os.path.join(out, 'project/components/Cover/README.md'))  # would stop it being the cover
    for f in ('project/README.md', 'project/tokens.json', 'project/design-system.json'):
        assert os.path.exists(os.path.join(out, f))
