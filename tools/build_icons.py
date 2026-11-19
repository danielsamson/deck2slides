"""Rebuild js/icons.json (x-icon name -> svg markup) from the icon font the Claude Slides viewer itself uses.

The viewer draws an x-icon as an SVG with viewBox 0 0 100 100 holding one <text> glyph from its 'anthropicons' font:
x=50, y=54, text-anchor middle, dominant-baseline central, font-size 90 (see artifact-type/app.js in a Slides artifact,
search 'mc-anthropicons'). The font has 300 units per em, ascent 300, descent 0, advance 300. So a glyph point (gx, gy) lands at
  x = 50 + (gx - 150) * 0.3        y = 54 - (gy - 150) * 0.3
Here every icon becomes one filled <path> in those 100-unit coordinates, so the converter draws exactly what the viewer draws
(js/anthropicons.woff2 is the viewer's font, extracted from app.js: the base64 data:font/woff2 after the glyph map).

    python tools/build_icons.py            # rewrites js/icons.json
"""
import json, os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
# the names x-icon accepts (format.md and the viewer's own list)
NAMES = ['Ant', 'Activity', 'Book', 'Chart', 'Chat', 'Check', 'CheckCircle', 'Clock', 'Cloud', 'Code', 'Database', 'Globe', 'GraduationCap', 'Home', 'Key',
         'Lightbulb', 'Lightning', 'Link', 'Lock', 'Owl', 'PaperPlane', 'Play', 'Search', 'Settings', 'Star', 'ThumbsUp', 'Tool', 'Trust', 'Users', 'Verified',
         'Warning', 'Wrench']

def build(font_path=os.path.join(ROOT, 'js', 'anthropicons.woff2')):
    f = TTFont(font_path); gs = f.getGlyphSet(); out = {}; s = 90 / f['head'].unitsPerEm
    assert f['head'].unitsPerEm == 300 and f['hmtx']['Check'][0] == 300
    for n in NAMES:
        if n not in gs: continue
        pen = SVGPathPen(gs, ntos=lambda v: ('%.3f' % v).rstrip('0').rstrip('.'))
        gs[n].draw(TransformPen(pen, (s, 0, 0, -s, 50 - 150 * s, 54 + 150 * s)))
        out[n] = '<svg width="32" height="32" viewBox="0 0 100 100" fill="currentColor"><path d="%s"/></svg>' % pen.getCommands()
    return out

if __name__ == '__main__':
    icons = build(); json.dump(icons, open(os.path.join(ROOT, 'js', 'icons.json'), 'w'), indent=0)
    print(len(icons), 'icons;', sorted(set(NAMES) - set(icons)), 'not in the font')
