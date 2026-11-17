from d2s import geomclip as G, pptx_build as P

def box(**kw):
    d = dict(cx=100, cy=100, w=200, h=200, radius=0, rot=0); d.update(kw); return d

def test_overflow_clip_cuts_to_parent_box():
    r = G.cust_for(box(ovclip=[dict(x0=0, y0=0, x1=150, y1=150, r=0)]))
    xs = [c[1] for c in r[0] if c[0] in 'ML']; ys = [c[2] for c in r[0] if c[0] in 'ML']
    assert abs(max(xs) - 0.75) < 1e-9 and abs(max(ys) - 0.75) < 1e-9 and abs(min(xs)) < 1e-9

def test_fully_clipped_item_is_empty_and_unclipped_is_none():
    assert G.cust_for(box(ovclip=[dict(x0=500, y0=500, x1=600, y1=600, r=0)])) == 'empty'
    assert G.cust_for(box(ovclip=[dict(x0=-10, y0=-10, x1=300, y1=300, r=0)])) is None

def test_ellipse_clip_is_four_beziers():
    r = G.cust_for(box(cpath=dict(kind='ellipse', cx=.5, cy=.5, rx=.5, ry=.5)))
    assert [c[0] for c in r[0]] == ['M', 'C', 'C', 'C', 'C', 'Z']

def test_gradient_fill_xml():
    from lxml import etree
    g = dict(kind='linear', angle=135, stops=[dict(c=dict(r=255, g=0, b=0, a=1), pos=0), dict(c=dict(r=0, g=0, b=255, a=.5), pos=100)])
    el = P.gradfill(P.E('a:spPr'), g)
    x = etree.tostring(el).decode()
    assert 'ang="2700000"' in x and 'val="50000"' in x and x.count(':gs pos=') == 2   # css 135deg -> ooxml 45deg

def test_ellipse_extent_of_empty_plan_without_pictures():
    assert P.plan_embeds([dict(id='s', items=[])], 'auto')[0] == set()
