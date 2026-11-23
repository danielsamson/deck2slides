"""Fixes found on the Magic Circle deck (README: 'What a real deck exposed')."""
import os, shutil, subprocess
import pytest
from lxml import etree
from d2s import geomclip as G, pptx_build as PB, config as C, fonts as F, loops

BOX = dict(cx=165, cy=175, w=330, h=350, rot=0)

def ring(bw, r):
    return G.rrect(0, 0, 330, 350, r).difference(G.rrect(bw['l'], bw['t'], 330 - bw['r'], 350 - bw['b'], max(0, r - max(bw.values()))))

@pytest.mark.parametrize('bw', [dict(l=0, r=0, t=8, b=0), dict(l=6, r=0, t=8, b=0), dict(l=4, r=4, t=12, b=4), dict(l=0, r=3, t=0, b=10)])
def test_bands_tile_the_ring_exactly(bw):
    sides = [k for k in 'tlrb' if bw[k] > 0]
    polys = [G.band_poly(dict(BOX, band=dict(k=k, bw=bw, r=22))) for k in sides]
    assert abs(sum(p.area for p in polys) - ring(bw, 22).area) < 1.0
    for i in range(len(polys)):
        for j in range(i + 1, len(polys)): assert polys[i].intersection(polys[j]).area < 0.5

def test_top_band_follows_the_corners():
    p = G.band_poly(dict(BOX, band=dict(k='t', bw=dict(l=0, r=0, t=8, b=0), r=22)))
    assert p.bounds[1] == 0 and 21 < p.bounds[3] <= 22.01            # runs down the corner curves, not just 8 px

def test_band_shape_is_custom_geometry():
    sub = G.cust_for(dict(BOX, band=dict(k='t', bw=dict(l=0, r=0, t=8, b=0), r=22)))
    assert isinstance(sub, list) and sub and sub[0][0][0] == 'M'

def test_rrect_clamps_radius_like_css():
    assert abs(G.rrect(0, 0, 128, 128, 256).area - 3.14159 * 64 * 64) < 30   # a 256 px radius on a 128 px box is a circle

def _stops(g):
    el = etree.Element('x'); PB.gradfill(el, g)
    gs = el.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}gs')
    path = el.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}fillToRect')
    return [int(x.get('pos')) for x in gs], path

def test_radial_closest_side_ends_on_the_ellipse():
    stops = [dict(c=dict(r=1, g=2, b=3, a=0.9), pos=0), dict(c=dict(r=1, g=2, b=3, a=0), pos=100)]
    pos, _ = _stops(dict(kind='radial', angle=180, stops=stops, size='closest-side', at=[50, 50]))
    assert pos[1] == 70711 and pos[-1] == 100000                      # 1/sqrt(2) of the way to the corner, then held
    pos2, _ = _stops(dict(kind='radial', angle=180, stops=stops))
    assert pos2 == [0, 100000]                                        # farthest-corner (CSS default) unchanged

def test_radial_position_becomes_fill_centre():
    stops = [dict(c=dict(r=1, g=2, b=3, a=1), pos=0), dict(c=dict(r=1, g=2, b=3, a=0), pos=100)]
    _, path = _stops(dict(kind='radial', angle=180, stops=stops, size='closest-side', at=[50, 55]))
    assert path.get('t') == '55000' and path.get('b') == '45000'

def test_display_alias_is_a_known_face():
    fam, w = C.FACE_ALIAS['Google Sans Display']
    assert F.FontDB.face(fam, w) == 'Google Sans' and F.FontDB.bold(w)

def test_local_face_file(tmp_path):
    (tmp_path / 'ds' / 'x' / 'fonts').mkdir(parents=True); f = tmp_path / 'ds' / 'x' / 'fonts' / 'A-400.woff2'; f.write_bytes(b'x')
    (tmp_path / 'blobs').mkdir(); (tmp_path / 'blobs' / 'abc123.woff2').write_bytes(b'y')
    dj = str(tmp_path / 'deck.json')
    assert F.local_face_file(dj, 'project/ds/x/fonts/A-400.woff2') == str(f)
    assert F.local_face_file(dj, '/_blob/abc123').endswith('abc123.woff2')
    assert F.local_face_file(dj, 'project/missing.woff2') is None

@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='needs ffmpeg')
def test_gif_encode_fits_budget_and_is_cached(tmp_path):
    from PIL import Image
    fr = tmp_path / 'f'; fr.mkdir()
    for i in range(12):
        im = Image.new('RGB', (200, 120), (240, 243, 250)); im.paste((60, 120, 240), (10 + i * 10, 40, 50 + i * 10, 80)); im.save(fr / ('f_%05d.png' % i))
    up, hq = loops.both(str(fr / 'f_%05d.png'), 12, str(tmp_path / 'g'), 'x', 200)
    assert up['frames'] > 1 and up['kb'] <= C.GIF_UPLOAD_KB and os.path.exists(hq['file'])
    t = os.path.getmtime(up['file']); up2, _ = loops.both(str(fr / 'f_%05d.png'), 12, str(tmp_path / 'g'), 'x', 200)
    assert os.path.getmtime(up2['file']) == t                          # second call came from the cache
