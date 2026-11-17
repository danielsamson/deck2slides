import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from d2s import units, fonts, config as C, gslides, clips

def test_units():
    assert units.emu(1920) == 9144000 and units.emu(1) == 4762 or units.emu(1) == 4763
    assert abs(units.pt(1920) - 720) < 1e-9 and units.sz100(40) == 1500
    x, y = units.rot_vec(1, 0, 90); assert abs(x) < 1e-9 and abs(y - 1) < 1e-9

def test_fontdb_line_spacing_is_relative_to_natural():
    db = fonts.FontDB({'Bricolage Grotesque': dict(natural=1.2)})
    assert abs(db.spc_pct('Bricolage Grotesque', 0.98) - 0.98 / 1.2) < 1e-9       # the measured rule: 0.98 on 1.2 -> 82%
    assert abs(db.spc_pct('Unknown', None) - 1.0) < 1e-9

def test_calibration_overrides_natural_and_interpolates_dy():
    cal = {'fonts': {'F': {'natural': 1.1, 'dy': [[1.0, -0.02], [1.4, 0.02]]}}}
    db = fonts.FontDB({'F': dict(natural=1.2)}, cal)
    assert db.natural('F') == 1.1
    assert abs(db.dy('F', 1.2, 60) - 0.0) < 1e-9 and abs(db.dy('F', 0.5, 100) - 2.0) < 1e-9 and abs(db.dy('F', 9, 100) + 2.0) < 1e-9

def test_weight_face_names():
    assert fonts.FontDB.face('Inter', 600) == 'Inter SemiBold' and fonts.FontDB.face('Inter', 700) == 'Inter' and fonts.FontDB.bold(700) and not fonts.FontDB.bold(800)
    assert fonts.FontDB.face('Arial', 600) == 'Arial'

def test_image_requests():
    els = [dict(tag='a.0.k', key='k', method='CENTER_CROP', transparency=0.5), dict(tag='b.0.k', key='k', method='CENTER_INSIDE', transparency=0)]
    reqs, missing = gslides.replace_image_requests(els, {'a.0.k': 'o1'}, {'k': 'http://u'})
    assert missing == ['b.0.k'] and reqs[0]['replaceImage']['imageObjectId'] == 'o1' and len(reqs) == 1   # opacity is not sent: the API refuses to update image transparency

def test_gif_delays_sum_exactly():
    assert sum(clips.delays(15, 15)) == 100 and sum(clips.delays(12, 12)) == 100
    assert clips.fps_for(500) == C.GIF_FPS and clips.fps_for(1500) == C.GIF_FPS_LONG

def test_font_file_metrics_match_browser_if_cached():
    p = '/tmp/fc/Inter.woff2'
    if os.path.exists(p): assert abs(fonts.natural_from_file(p) - 1.21) < 0.005
