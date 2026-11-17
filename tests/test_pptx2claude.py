from lxml import etree
from d2s import pptx2claude as Q

class Ctx:
    theme = {'dk1': '000000', 'lt1': 'FFFFFF', 'accent1': '123456'}; k = 1080 / 5143500

def el(xml): return etree.fromstring('<r xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">%s</r>' % xml)[0]

def test_typeface_to_face_reverses_the_weight_names():
    assert Q.typeface_to_face('Inter SemiBold', False) == ('Inter', 600)
    assert Q.typeface_to_face('Bricolage Grotesque ExtraBold', False) == ('Bricolage Grotesque', 800)
    assert Q.typeface_to_face('Inter', True) == ('Inter', 700) and Q.typeface_to_face('Inter', False) == ('Inter', 400)

def test_linear_gradient_angle_is_converted_back_to_css():
    sp = etree.fromstring('<p:spPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:gradFill><a:gsLst><a:gs pos="0"><a:srgbClr val="FF0000"/></a:gs><a:gs pos="100000"><a:srgbClr val="0000FF"><a:alpha val="50000"/></a:srgbClr></a:gs></a:gsLst><a:lin ang="2700000" scaled="0"/></a:gradFill></p:spPr>')
    assert Q.fill_css(Ctx, sp) == 'linear-gradient(135deg,#FF0000 0%,rgba(0,0,255,0.5) 100%)'   # ooxml 45deg = css 135deg

def test_round_rect_radius_from_adjust_value():
    g = el('<a:prstGeom prst="roundRect"><a:avLst><a:gd name="adj" fmla="val 10000"/></a:avLst></a:prstGeom>')
    assert abs(Q.radius_of('roundRect', g, 500, 300) - 30) < 1e-9

def test_dash_styles_map_to_css_and_solid_stays_solid():
    for val, want in (('solid', 'solid'), ('dash', 'dashed'), ('lgDash', 'dashed'), ('sysDot', 'dotted'), ('dot', 'dotted')):
        sp = etree.fromstring('<p:spPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:ln w="12700"><a:solidFill><a:srgbClr val="B4F000"/></a:solidFill><a:prstDash val="%s"/></a:ln></p:spPr>' % val)
        assert Q.line_css(Ctx, sp)[2] == want
