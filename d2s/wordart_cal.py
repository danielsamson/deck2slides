"""WordArt calibration. Slides sizes a WordArt word by its BOX (the font size is ignored) and the word's ink comes out rx x the box
width and ry x the box height, offset by (ox, oy) of the box. rx, ry, ox, oy are measured per word: `gen` writes one slide per word
(box 1000 x 300 at 100, 100); upload it, save a LARGE thumbnail per slide as <dir>/w<N>.png; `fit` measures them -> wordart_cal.json."""
import json, sys, numpy as np
from PIL import Image
BOX = (100, 100, 1000, 300)

def gen(words, out):
    from pptx import Presentation
    from pptx.util import Emu
    from pptx.enum.shapes import MSO_SHAPE
    from . import pptx_build as pb
    from .units import emu
    prs = Presentation(); prs.slide_width = Emu(9144000); prs.slide_height = Emu(5143500)
    for w in words:
        s = prs.slides.add_slide(prs.slide_layouts[6])
        sp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, emu(BOX[0]), emu(BOX[1]), emu(BOX[2]), emu(BOX[3])); spPr = pb.strip(sp); pb.E('a:noFill', spPr); ln = pb.E('a:ln', spPr); pb.E('a:noFill', ln)
        tb = sp._element.find(pb.qn('p:txBody'))
        if tb is not None: sp._element.remove(tb)
        tb = pb.E('p:txBody', sp._element); bp = pb.E('a:bodyPr', tb, wrap='none', lIns=0, tIns=0, rIns=0, bIns=0); wp = pb.E('a:prstTxWarp', bp, prst='textPlain'); pb.E('a:avLst', wp)
        pb.E('a:lstStyle', tb); p = pb.E('a:p', tb); r = pb.E('a:r', p); rp = pb.E('a:rPr', r, lang='en-GB', sz=7500, b='0')
        l2 = pb.E('a:ln', rp, w=emu(4)); sf = pb.E('a:solidFill', l2); pb.E('a:srgbClr', sf, val='000000'); pb.E('a:noFill', rp); pb.E('a:latin', rp, typeface='Inter ExtraBold')
        t = pb.E('a:t', r); t.text = w
    prs.save(out)

def fit(words, d, out):
    cal = {}; k = 1920 / 1600
    for i, w in enumerate(words, 1):
        im = np.array(Image.open('%s/w%d.png' % (d, i)).convert('L')); ys, xs = np.where(im < 128)
        x0, x1, y0, y1 = xs.min() * k, (xs.max() + 1) * k, ys.min() * k, (ys.max() + 1) * k
        cal[w] = dict(rx=(x1 - x0) / BOX[2], ry=(y1 - y0) / BOX[3], ox=(x0 - BOX[0]) / BOX[2], oy=(y0 - BOX[1]) / BOX[3])
    json.dump(cal, open(out, 'w'), indent=1); return cal
