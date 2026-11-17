"""Experiment decks for the gaps list (README, 'What works, what does not').
Writes to test-decks/scratch/exp/:
  exp-main.pptx      slides: 1 gradients, 2 freeform + clipped picture placeholder, 3 double border, 4 real embedded pictures
                     (opacity, shadow, rounded mask), 5 explicit placeholder text for the check below
  exp-big.pptx       about 2 MB (upload size cap test)
  exp-template.pptx  custom master/layout (coloured background, named layout, title placeholder) + one slide using it
Run: python3 make_experiments.py
"""
import io, os, random, copy
from lxml import etree
from pptx import Presentation
from pptx.util import Emu, Pt
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), '..', 'scratch', 'exp'); os.makedirs(OUT, exist_ok=True)
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
PX = 4762.5   # EMU per 1920-wide px

def px(v): return int(round(v * PX))
def new_pres():
    p = Presentation(); p.slide_width = Emu(9144000); p.slide_height = Emu(5143500); return p
def blank(p): return p.slides.add_slide(p.slide_layouts[6])
def x(xml): return etree.fromstring(xml)

def shape(slide, x0, y0, w, h, prst='rect'):
    from pptx.enum.shapes import MSO_SHAPE
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(x0), px(y0), px(w), px(h))
    for st in s._element.findall(qn('p:style')): s._element.remove(st)
    sp = s._element.spPr
    for ch in list(sp):
        if ch.tag not in (qn('a:xfrm'),): sp.remove(ch)
    g = x('<a:prstGeom xmlns:a="%s" prst="%s"><a:avLst/></a:prstGeom>' % (A, prst)); sp.append(g); return s, sp

def label(slide, x0, y0, text):
    tb = slide.shapes.add_textbox(px(x0), px(y0), px(700), px(40)); r = tb.text_frame.paragraphs[0].add_run(); r.text = text; r.font.size = Pt(10)

def set_fill(sp, xml):
    for t in ('solidFill', 'gradFill', 'noFill'):
        for e in sp.findall(qn('a:' + t)): sp.remove(e)
    prst = sp.find(qn('a:prstGeom')) if sp.find(qn('a:prstGeom')) is not None else sp.find(qn('a:custGeom'))
    prst.addnext(x(xml.replace('<a:', '<a:', 1)))

def grad(stops, lin=None, path=None):
    gs = ''.join('<a:gs pos="%d"><a:srgbClr val="%s">%s</a:srgbClr></a:gs>' % (pos * 1000, c, ('<a:alpha val="%d"/>' % (al * 1000) if al < 100 else '')) for pos, c, al in stops)
    tail = ('<a:lin ang="%d" scaled="0"/>' % (lin * 60000)) if lin is not None else ('<a:path path="circle"><a:fillToRect l="50000" t="50000" r="50000" b="50000"/></a:path>')
    return '<a:gradFill xmlns:a="%s" rotWithShape="1"><a:gsLst>%s</a:gsLst>%s</a:gradFill>' % (A, gs, tail)

def png(w, h, fn):
    im = Image.new('RGB', (w, h), (108, 91, 255)); d = ImageDraw.Draw(im)
    for i in range(0, w, 40): d.line([(i, 0), (i, h)], fill=(130, 115, 255))
    d.line([(0, 0), (w, h)], fill='white', width=6); d.line([(w, 0), (0, h)], fill='white', width=6)
    d.ellipse([w / 2 - h / 5, h / 2 - h / 5, w / 2 + h / 5, h / 2 + h / 5], outline=(180, 240, 0), width=8)
    d.rectangle([0, 0, w - 1, h - 1], outline=(255, 74, 28), width=8); im.save(fn); return fn

def main():
    p = new_pres()
    # ---- slide 1: gradients
    s = blank(p); label(s, 40, 20, 'GRADIENTS: linear 90, linear 45 3-stop, radial, linear with alpha stops, linear on rounded rect, linear on ellipse')
    specs = [
        ('rect', grad([(0, 'FF4A1C', 100), (100, '6B5BFF', 100)], lin=0)),
        ('rect', grad([(0, 'FF4A1C', 100), (50, 'FFFFFF', 100), (100, '14142E', 100)], lin=45)),
        ('rect', grad([(0, 'B4F000', 100), (100, '14142E', 100)], path=True)),
        ('rect', grad([(0, 'FF4A1C', 100), (100, 'FF4A1C', 0)], lin=0)),
        ('roundRect', grad([(0, '6B5BFF', 100), (100, 'FF4A1C', 100)], lin=90)),
        ('ellipse', grad([(0, 'B4F000', 100), (100, '6B5BFF', 100)], lin=90)),
    ]
    for i, (prst, g) in enumerate(specs):
        sh, sp = shape(s, 60 + (i % 3) * 600, 120 + (i // 3) * 480, 520, 400, prst); set_fill(sp, g)
    # backdrop stripe behind the alpha gradient so transparency is visible
    # ---- slide 2: freeform polygon + clipped picture placeholder
    s = blank(p); label(s, 40, 20, 'FREEFORM: triangle custGeom (solid), triangle custGeom (gradient), polygon-clipped picture placeholder (replaceImage later)')
    def poly(x0, y0, w, h, pts):
        sh, sp = shape(s, x0, y0, w, h)
        for g in sp.findall(qn('a:prstGeom')): sp.remove(g)
        path = ''.join(('<a:moveTo><a:pt x="%d" y="%d"/></a:moveTo>' if i == 0 else '<a:lnTo><a:pt x="%d" y="%d"/></a:lnTo>') % (int(a * 10000), int(b * 10000)) for i, (a, b) in enumerate(pts))
        cg = x('<a:custGeom xmlns:a="%s"><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/><a:pathLst><a:path w="10000" h="10000">%s<a:close/></a:path></a:pathLst></a:custGeom>' % (A, path))
        sp.find(qn('a:xfrm')).addnext(cg); return sh, sp
    sh, sp = poly(60, 120, 520, 400, [(0.5, 0), (1, 1), (0, 1)]); sp.find(qn('a:custGeom')).addnext(x('<a:solidFill xmlns:a="%s"><a:srgbClr val="6B5BFF"/></a:solidFill>' % A))
    sh, sp = poly(660, 120, 520, 400, [(0.5, 0), (1, 0.4), (0.8, 1), (0.2, 1), (0, 0.4)]); sp.find(qn('a:custGeom')).addnext(x(grad([(0, 'FF4A1C', 100), (100, 'B4F000', 100)], lin=90)))
    f = png(800, 600, os.path.join(OUT, 'ph.png'))
    pic = s.shapes.add_picture(f, px(1260), px(120), px(520), px(400)); pic._element.nvPicPr.cNvPr.set('descr', 'clippic')
    sp = pic._element.spPr
    for g in sp.findall(qn('a:prstGeom')): sp.remove(g)
    path = '<a:moveTo><a:pt x="5000" y="0"/></a:moveTo><a:lnTo><a:pt x="10000" y="4000"/></a:lnTo><a:lnTo><a:pt x="8000" y="10000"/></a:lnTo><a:lnTo><a:pt x="2000" y="10000"/></a:lnTo><a:lnTo><a:pt x="0" y="4000"/></a:lnTo><a:close/>'
    sp.find(qn('a:xfrm')).addnext(x('<a:custGeom xmlns:a="%s"><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="0" t="0" r="r" b="b"/><a:pathLst><a:path w="10000" h="10000">%s</a:path></a:pathLst></a:custGeom>' % (A, path)))
    # ---- slide 3: double border + dash variants
    s = blank(p); label(s, 40, 20, 'BORDERS: compound double (cmpd=dbl) 12pt, thin double 4pt, triple (tri), dashed, dotted, solid 12pt')
    for i, (cmpd, w, dash) in enumerate([('dbl', 12, None), ('dbl', 4, None), ('tri', 12, None), (None, 6, 'dash'), (None, 6, 'sysDot'), (None, 12, None)]):
        sh, sp = shape(s, 60 + (i % 3) * 600, 120 + (i // 3) * 480, 520, 400)
        sp.append(x('<a:noFill xmlns:a="%s"/>' % A))
        ln = x('<a:ln xmlns:a="%s" w="%d"%s><a:solidFill><a:srgbClr val="14142E"/></a:solidFill>%s</a:ln>' % (A, int(w * 12700), (' cmpd="%s"' % cmpd) if cmpd else '', ('<a:prstDash val="%s"/>' % dash) if dash else '')); sp.append(ln)
    # ---- slide 4: real embedded pictures, no replaceImage
    s = blank(p); label(s, 40, 20, 'REAL EMBEDDED PICTURES (no replaceImage): opacity 50%, shadow + radius 40, rotated rounded mask, opacity + mask + shadow')
    f = png(800, 600, os.path.join(OUT, 'real.png'))
    def realpic(x0, y0, w, h, prst='rect', adj=None, alpha=None, shadow=False, rot=0):
        pic = s.shapes.add_picture(f, px(x0), px(y0), px(w), px(h)); sp = pic._element.spPr
        for g in sp.findall(qn('a:prstGeom')): sp.remove(g)
        g = x('<a:prstGeom xmlns:a="%s" prst="%s"><a:avLst>%s</a:avLst></a:prstGeom>' % (A, prst, ('<a:gd name="adj" fmla="val %d"/>' % adj) if adj else '')); sp.find(qn('a:xfrm')).addnext(g)
        if shadow: sp.append(x('<a:effectLst xmlns:a="%s"><a:outerShdw blurRad="190500" dist="95250" dir="5400000" algn="ctr" rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="35000"/></a:srgbClr></a:outerShdw></a:effectLst>' % A))
        if alpha: pic._element.find('.//' + qn('a:blip')).append(x('<a:alphaModFix xmlns:a="%s" amt="%d"/>' % (A, alpha * 1000)))
        if rot: pic.rotation = rot
        return pic
    realpic(60, 150, 520, 390, alpha=50)
    realpic(680, 150, 520, 390, 'roundRect', 10000, shadow=True)
    realpic(1300, 150, 420, 300, 'roundRect', 25000, rot=12)
    realpic(60, 600, 520, 390, 'roundRect', 10000, alpha=50, shadow=True)
    p.save(os.path.join(OUT, 'exp-main.pptx'))

    # ---- big file (size cap)
    p = new_pres(); s = blank(p); label(s, 40, 20, 'BIG FILE TEST (about 2 MB)')
    rnd = random.Random(1); im = Image.frombytes('RGB', (900, 800), bytes(rnd.getrandbits(8) for _ in range(900 * 800 * 3))); b = io.BytesIO(); im.save(b, 'PNG')
    s.shapes.add_picture(io.BytesIO(b.getvalue()), px(60), px(120), px(900), px(800)); p.save(os.path.join(OUT, 'exp-big.pptx'))

    # ---- template: custom master + layout + placeholder
    p = new_pres(); lay = p.slide_layouts[5]   # 'Title Only'
    lay._element.cSld.set('name', 'ZZ Company Title Layout')
    m = p.slide_master; bg = x('<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="%s"><p:bgPr><a:solidFill><a:srgbClr val="FFF4C2"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>' % A)
    cs = m._element.cSld
    for old_bg in cs.findall(qn('p:bg')): cs.remove(old_bg)
    cs.insert(0, bg)
    # decorative bar on the LAYOUT (tests that layout furniture survives)
    bar_xml = ('<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="%s"><p:nvSpPr><p:cNvPr id="99" name="LayoutBar"/><p:cNvSpPr/><p:nvPr userDrawn="1"/></p:nvSpPr>'
               '<p:spPr><a:xfrm><a:off x="0" y="%d"/><a:ext cx="9144000" cy="%d"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="6B5BFF"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>') % (A, px(1000), px(80))
    lay._element.cSld.spTree.append(x(bar_xml))
    for ph in lay.placeholders:
        if ph.placeholder_format.type is not None and 'TITLE' in str(ph.placeholder_format.type):
            ph.left, ph.top, ph.width, ph.height = px(100), px(80), px(1500), px(200)
            for r in ph.text_frame.paragraphs[0].runs: pass
    s = p.slides.add_slide(lay); s.shapes.title.text = 'Title from the layout placeholder'
    s.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(40)
    p.save(os.path.join(OUT, 'exp-template.pptx'))
    for n in ('exp-main', 'exp-big', 'exp-template'): print(n, os.path.getsize(os.path.join(OUT, n + '.pptx')) // 1024, 'KB')

if __name__ == '__main__': main()
