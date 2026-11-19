import math
from d2s import svgvec as V

def ends(cmds): return [(c[-2], c[-1]) for c in cmds if c[0] != 'Z']

def test_parse_relative_and_shorthand():
    c = V.parse_path('M20 6 9 17l-5-5')
    assert c == [('M', 20, 6), ('L', 9, 17), ('L', 4, 12)]
    assert V.parse_path('M0 0H10V5H0z')[-1] == ('Z',)

def test_arc_half_circle_stays_on_circle():
    c = V.parse_path('M0 0A5 5 0 0 1 10 0')
    assert all(x[0] == 'C' for x in c[1:])
    # midpoint of a half circle of radius 5 through (0,0) and (10,0): the arc passes (5, +-5)
    mid = c[1][-2:] if len(c) == 3 else None
    assert abs(math.hypot(c[-1][5] - 5, c[-1][6])) - 5 < 1e-6

def test_arc_flags_packed():
    c = V.parse_path('M12 2a10 10 0 1 0 0 20')
    assert c and c[-1][0] == 'C'

def test_circle_and_rect_closed():
    assert V._ellipse(5, 5, 2, 2)[-1] == ('Z',)
    r = V._rect(0, 0, 10, 10, 2, 2); assert r and r[0] == ('M', 2, 0)

def test_build_normalises_and_scales_stroke():
    vec = dict(vb=[0, 0, 24, 24], els=[dict(t='path', at=dict(d='M20 6 9 17l-5-5'), sw=3, stroke='rgb(255, 255, 255)', fill='none', cap='round', join='round', op=1, fo=1, so=1)], color='rgb(255, 255, 255)')
    s = V.build(vec, 32, 32)
    assert abs(s['sw'] - 4) < 1e-9 and s['cap'] == 'round'
    m = s['paths'][0]['cmds'][0]
    assert m[0] == 'M' and abs(m[1] - 20 / 24) < 1e-9 and abs(m[2] - 6 / 24) < 1e-9 and s['fill'] is None

def test_build_refuses_what_it_cannot_do():
    base = dict(t='path', at=dict(d='M0 0L1 1'), sw=1, stroke='rgb(0, 0, 0)', fill='none', cap='butt', join='miter', op=1, fo=1, so=1)
    assert V.build(dict(vb=[0, 0, 24, 24], els=[dict(base, stroke='url(#g)')]), 24, 24) is None
    assert V.build(dict(vb=[0, 0, 24, 24], els=[base, dict(base, sw=2)]), 24, 24) is None
    assert V.build(dict(vb=[0, 0, 24, 12], els=[base]), 24, 24) is None

def test_vector_shape_has_one_geometry_only():
    """A freeform next to the default rectangle draws the rectangle (seen in Google as filled boxes where icons should be)."""
    from pptx import Presentation
    from pptx.util import Emu
    from pptx.oxml.ns import qn
    from d2s import pptx_build as B
    vec = dict(vb=[0, 0, 24, 24], els=[dict(t='path', at=dict(d='M20 6 9 17l-5-5'), sw=3, stroke='rgb(255, 255, 255)', fill='none', cap='round', join='round', op=1, fo=1, so=1)], color='rgb(255, 255, 255)')
    spec = V.build(vec, 32, 32)
    prs = Presentation(); slide = prs.slides.add_slide(prs.slide_layouts[6])
    sp = B.add_vector(slide, dict(cx=100, cy=100, w=32, h=32), spec)
    spPr = sp._element.spPr
    assert len(spPr.findall(qn('a:custGeom'))) == 1 and not spPr.findall(qn('a:prstGeom'))
    ln = spPr.find(qn('a:ln')); assert ln.get('cap') == 'rnd'
