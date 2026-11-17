import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from d2s import gslides2claude as G


def test_missing_scale_is_zero_so_a_turned_line_is_vertical():
    cv = G.Conv({}, tempfile.mkdtemp())
    # Google omits zero values: this is a 90-degree line (scaleX, shearY absent -> 0; shearX and scaleY present)
    e = {'objectId': 'l', 'size': {'width': {'magnitude': 3000000}, 'height': {'magnitude': 3000000}},
         'transform': {'scaleY': 1.0, 'shearX': 0.0, 'translateX': 1000000, 'translateY': 500000},
         'line': {'lineProperties': {'weight': {'magnitude': 9525}, 'lineFill': {'solidFill': {'color': {'rgbColor': {}}}}}}}
    out = cv.element(e, 1)
    assert 'x1="210.0"' in out and 'x2="210.0"' in out      # same x at both ends: vertical


def test_runs_with_different_sizes_become_separate_blocks():
    cv = G.Conv({}, tempfile.mkdtemp())
    cv.nat['DM Sans'] = 1.3
    run = lambda txt, pt: {'textRun': {'content': txt, 'style': {'fontSize': {'magnitude': pt}, 'weightedFontFamily': {'fontFamily': 'DM Sans', 'weight': 400}}}}
    e = {'objectId': 't', 'size': {'width': {'magnitude': 3000000}, 'height': {'magnitude': 3000000}},
         'transform': {'scaleX': 1, 'scaleY': 0.1, 'translateX': 0, 'translateY': 0},
         'shape': {'shapeType': 'TEXT_BOX', 'shapeProperties': {}, 'text': {'textElements': [
             {'paragraphMarker': {'style': {}}}, run('Big ', 20), run('small\n', 7)]}}}
    html = cv.element(e, 1)
    assert html.count('<p ') == 2
