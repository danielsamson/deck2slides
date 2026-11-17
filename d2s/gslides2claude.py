"""Google Slides (presentations.get / pages.get JSON) -> Claude Slides sections, no PPTX in between.

Why this exists: the PPTX route (pptx2claude) needs a file; Drive could not export the user's decks, but the Slides
connector returns the full page JSON. Same output format as pptx2claude (deck.json v5 + deck.css + slides/*.html).

Geometry: 1 px = 4762.5 EMU on the 1920 canvas. Text: Google's line spacing percentage multiplies the font's natural
line height; its default text insets (7.2 pt sides, 3.6 pt top/bottom) are not in the API and are assumed.
What the API does not give (and so is approximated, listed in the warnings): rounded-rectangle radius (default 1/6 of
the short side), text insets, autofit scale, image crops beyond cropProperties, rotated/skewed elements."""
from __future__ import annotations
import json, os, re, html
from collections import Counter
from . import fonts as F

PX = 1920 / 9144000.0
PT = 1920 / 720.0
import os as _os
INSET_X = float(_os.environ.get('D2S_INSET_X', 8))
INSET_Y = float(_os.environ.get('D2S_INSET_Y', 6))


def hexcol(r, g, b):
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in (r, g, b))


class Conv:
    def __init__(self, scheme, cache):
        self.scheme, self.cache, self.warns, self.nat = scheme, cache, Counter(), {}
        self.classes, self.imgs = {}, []

    def warn(self, msg):
        self.warns[msg] += 1

    def col(self, c):
        if not c:
            return None
        c = c.get('opaqueColor', c.get('color', c))
        if 'rgbColor' in c:
            r = c['rgbColor']
            return hexcol(r.get('red', 0), r.get('green', 0), r.get('blue', 0))
        if 'themeColor' in c:
            return self.scheme.get(c['themeColor'])
        return None

    def natural(self, fam):
        if fam not in self.nat:
            fp = F.fetch_family_file(fam, 'https://fonts.googleapis.com/css2?family=' + fam.replace(' ', '+'), self.cache)
            try:
                self.nat[fam] = F.natural_from_file(fp) if fp else 1.2
            except Exception:
                self.nat[fam] = 1.2
            if not fp:
                self.warn('font %s not on Google Fonts: natural line height assumed 1.2' % fam)
        return self.nat[fam]

    # ---------------------------------------------------------------- geometry
    def box(self, e):
        t = e.get('transform', {})
        sz = e.get('size', {})
        sx, sy = t.get('scaleX', 0), t.get('scaleY', 0)
        if (t.get('shearX') or t.get('shearY')) and 'line' not in e:
            self.warn('rotated or skewed shape placed unrotated')
        w = sz.get('width', {}).get('magnitude', 0) * abs(sx) * PX
        h = sz.get('height', {}).get('magnitude', 0) * abs(sy) * PX
        x = t.get('translateX', 0) * PX
        y = t.get('translateY', 0) * PX
        return x, y, w, h, sx < 0, sy < 0

    # ---------------------------------------------------------------- text
    def paragraphs(self, te):
        paras, cur = [], None
        for el in te:
            if 'paragraphMarker' in el:
                cur = dict(style=el['paragraphMarker'].get('style', {}), runs=[], bullet=el['paragraphMarker'].get('bullet'))
                paras.append(cur)
            elif 'textRun' in el and cur is not None:
                cur['runs'].append(el['textRun'])
        return paras

    def text_html(self, e, box):
        x, y, w, h, _, _ = box
        sh = e['shape']
        sp = sh.get('shapeProperties', {})
        paras = [p for p in self.paragraphs(sh.get('text', {}).get('textElements', []))
                 if ''.join(r.get('content', '') for r in p['runs']).strip()]
        if not paras:
            return ''
        anchor = {'TOP': 'flex-start', 'MIDDLE': 'center', 'BOTTOM': 'flex-end'}.get(sp.get('contentAlignment', 'TOP'), 'flex-start')
        out = []
        for p in paras:
            runs = [r for r in p['runs'] if r.get('content', '') not in ('\n',)]
            if not runs:
                continue

            def key(r):
                st = r.get('style', {})
                wf = st.get('weightedFontFamily', {})
                return (wf.get('fontFamily') or st.get('fontFamily') or 'Arial', wf.get('weight') or (700 if st.get('bold') else 400),
                        st.get('fontSize', {}).get('magnitude', 12))
            groups = []
            for r in runs:   # the format keeps only colour, bold, italic, underline inside a line, so a size or face change becomes its own block
                if groups and key(groups[-1][0]) == key(r):
                    groups[-1].append(r)
                else:
                    groups.append([r])
            inline = len(groups) > 1 and not any('\n' in r.get('content', '').rstrip('\n') or '\x0b' in r.get('content', '') for r in runs)
            if len(groups) > 1:
                self.warn('paragraph with several sizes laid out as a baseline row' if inline else 'paragraph with several sizes split into separate lines')
            row_open = len(out)
            for gi, grp in enumerate(groups):
                fam, wt, sz_pt = key(grp[0])
                size = sz_pt * PT
                ls = p['style'].get('lineSpacing', 100) / 100.0
                lh = round(size * self.natural(fam) * ls, 1)
                if size < 24:
                    self.warn('text below the 24px floor of the format (kept at true size)')
                al = {'START': 'left', 'CENTER': 'center', 'END': 'right', 'JUSTIFIED': 'justify'}.get(p['style'].get('alignment', 'START'), 'left')
                above = p['style'].get('spaceAbove', {}).get('magnitude', 0) * PT if gi == 0 else 0
                below = p['style'].get('spaceBelow', {}).get('magnitude', 0) * PT if gi == len(groups) - 1 else 0
                spans = []
                for r in grp:
                    s_ = r.get('style', {})
                    c = self.col(s_.get('foregroundColor'))
                    txt = html.escape(r['content'].rstrip('\n')).replace('\x0b', '<br>').replace('\n', '<br>')
                    inner = txt
                    if s_.get('bold') and wt < 700:
                        inner = '<b>%s</b>' % inner
                    if s_.get('italic'):
                        inner = '<i>%s</i>' % inner
                    if s_.get('underline'):
                        inner = '<u>%s</u>' % inner
                    spans.append('<span style="color:%s">%s</span>' % (c, inner) if c else inner)
                colour = self.col(grp[0].get('style', {}).get('foregroundColor')) or '#000000'
                style = 'margin:%.0fpx 0 %.0fpx;font-family:\'%s\',Arial,sans-serif;font-size:%.1fpx;line-height:%.1fpx;font-weight:%d;color:%s;text-align:%s' % (
                    above, below, fam, size, lh, wt, colour, al)
                out.append('<p style="%s">%s</p>' % (style, ''.join(spans)))
            if inline:
                blocks = out[row_open:]
                del out[row_open:]
                out.append('<div style="display:flex;align-items:baseline;gap:%.0fpx">%s</div>' % (0.3 * key(groups[0][0])[2] * PT, ''.join(blocks)))
        fill = self.col(sp.get('shapeBackgroundFill', {}).get('solidFill')) if sp.get('shapeBackgroundFill', {}).get('propertyState') != 'NOT_RENDERED' else None
        return ('<div style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;box-sizing:border-box;'
                'padding:%.1fpx %.1fpx;display:flex;flex-direction:column;justify-content:%s">%s</div>') % (
            x, y, w, h, INSET_Y, INSET_X, anchor, ''.join(out))

    # ---------------------------------------------------------------- elements
    def element(self, e, slide_no):
        x, y, w, h, fx, fy = self.box(e)
        if 'elementGroup' in e:
            t = e.get('transform', {})
            kids = []
            for k in e['elementGroup'].get('children', []):
                kt = k.setdefault('transform', {})
                kt['translateX'] = kt.get('translateX', 0) * t.get('scaleX', 0) + t.get('translateX', 0)
                kt['translateY'] = kt.get('translateY', 0) * t.get('scaleY', 0) + t.get('translateY', 0)
                kt['scaleX'] = kt.get('scaleX', 0) * t.get('scaleX', 0)
                kt['scaleY'] = kt.get('scaleY', 0) * t.get('scaleY', 0)
                kids.append(self.element(k, slide_no))
            return '\n'.join(k for k in kids if k)
        if 'image' in e:
            alt = html.escape(e.get('description') or e.get('title') or 'Image')
            n = len(self.imgs)
            self.imgs.append(dict(url=e['image'].get('contentUrl'), slide=slide_no, id=e['objectId']))
            crop = e['image'].get('imageProperties', {}).get('cropProperties')
            if crop:
                self.warn('image crop approximated with object-fit:cover')
            return '<img src="IMG:%d" alt="%s" style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;object-fit:cover">' % (n, alt, x, y, w, h)
        if 'line' in e:
            lp = e['line'].get('lineProperties', {})
            c = self.col(lp.get('lineFill', {}).get('solidFill')) or '#000000'
            wt = max(1, round(lp.get('weight', {}).get('magnitude', 9525) * PX, 1))
            dash = lp.get('dashStyle', 'SOLID')
            bs = 'dashed' if 'DASH' in dash else 'dotted' if 'DOT' in dash else 'solid'
            t = e.get('transform', {})
            W_, H_ = e['size']['width']['magnitude'], e['size']['height']['magnitude']
            ap = lambda px_, py_: ((t.get('scaleX', 0) * px_ + t.get('shearX', 0) * py_ + t.get('translateX', 0)) * PX,
                                   (t.get('shearY', 0) * px_ + t.get('scaleY', 0) * py_ + t.get('translateY', 0)) * PX)
            (x1, y1), (x2, y2) = ap(0, 0), ap(W_, H_)   # a rotated line (a vertical rule is a horizontal one turned 90 degrees) lands on its true endpoints
            x, y, w, h = min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)
            head = 'end' if lp.get('endArrow', 'NONE') != 'NONE' else 'none'
            if h < 1 and w >= 1 and not lp.get('endArrow', 'NONE') != 'NONE':
                return '<hr style="position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;border:0;border-top:%.1fpx %s %s;margin:0">' % (x, y, w, wt, bs, c)
            return '<x-connector x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" head="%s" style="color:%s;border-width:%.1fpx;border-style:%s"></x-connector>' % (x1, y1, x2, y2, head, c, wt, bs)
        if 'table' in e:
            self.warn('table skipped')
            return ''
        sh = e.get('shape')
        if not sh:
            return ''
        sp = sh.get('shapeProperties', {})
        st = sh.get('shapeType', 'TEXT_BOX')
        bgf = sp.get('shapeBackgroundFill', {})
        fill = self.col(bgf.get('solidFill')) if bgf.get('propertyState') != 'NOT_RENDERED' and bgf.get('solidFill') else None
        ol = sp.get('outline', {})
        border = None
        if ol and ol.get('propertyState') != 'NOT_RENDERED' and ol.get('outlineFill', {}).get('solidFill'):
            border = (max(1, round(ol.get('weight', {}).get('magnitude', 9525) * PX, 1)), self.col(ol['outlineFill']['solidFill']))
        parts = []
        if st != 'TEXT_BOX' or fill or border:
            if st in ('RECTANGLE', 'ROUND_RECTANGLE', 'TEXT_BOX', 'ELLIPSE'):
                rad = {'ROUND_RECTANGLE': min(w, h) / 6.0, 'ELLIPSE': min(w, h) / 2.0}.get(st, 0)
                if st == 'ROUND_RECTANGLE':
                    self.warn('rounded rectangle radius assumed 1/6 of the short side (the API does not return it)')
                css = 'position:absolute;left:%.1fpx;top:%.1fpx;width:%.1fpx;height:%.1fpx;box-sizing:border-box;' % (x, y, w, h)
                if fill:
                    css += 'background:%s;' % fill
                if border:
                    css += 'border:%.1fpx solid %s;' % border
                if rad:
                    css += 'border-radius:%.0fpx;' % min(rad, 256)
                if st == 'ELLIPSE' and min(w, h) > 512:
                    parts.append('<x-shape kind="ellipse" style="%s"></x-shape>' % css)
                else:
                    parts.append('<div style="%s"></div>' % css)
            else:
                self.warn('shape %s not converted' % st)
        t = self.text_html(e, (x, y, w, h, fx, fy)) if sh.get('text') else ''
        if t:
            parts.append(t)
        return '\n'.join(parts)


def convert(slides_json, masters_json, outdir, only=None, cache=None):
    d = json.load(open(slides_json))['content']['slides']
    m = json.load(open(masters_json))['content'] if masters_json else {}
    scheme = {}
    for mm in m.get('masters', []):
        for c in mm.get('pageProperties', {}).get('colorScheme', {}).get('colors', []):
            rgb = c.get('color', {})
            scheme.setdefault(c['type'], hexcol(rgb.get('red', 0), rgb.get('green', 0), rgb.get('blue', 0)))
    for k, v in {'TEXT1': 'DARK1', 'BACKGROUND1': 'LIGHT1', 'TEXT2': 'DARK2', 'BACKGROUND2': 'LIGHT2'}.items():
        scheme.setdefault(k, scheme.get(v))
    cv = Conv(scheme, cache or os.path.join(outdir, '.fontcache'))
    os.makedirs(os.path.join(outdir, 'project', 'slides'), exist_ok=True)
    order, report = [], []
    master_bg = None
    for mm in m.get('masters', []):
        f = mm.get('pageProperties', {}).get('pageBackgroundFill', {}).get('solidFill')
        master_bg = master_bg or cv.col(f)
    lay_bg = {l['objectId']: cv.col(l.get('pageProperties', {}).get('pageBackgroundFill', {}).get('solidFill')) for l in m.get('layouts', [])}
    for i, s in enumerate(d):
        if only is not None and i not in only:
            continue
        sid = 's%03d' % (i + 1)
        fill = s.get('pageProperties', {}).get('pageBackgroundFill', {})
        if 'solidFill' in fill:
            bg = cv.col(fill['solidFill'])
        elif 'stretchedPictureFill' in fill:
            # the picture itself is not reachable from this machine (docs.google.com image URLs are blocked here); stand in a
            # flat colour that keeps the slide's text legible: dark if its text is light, else light
            txt = re.findall(r'"foregroundColor": \{[^}]*?"rgbColor": \{([^}]*)\}', json.dumps(s))
            lum = []
            for t in txt:
                rgb = {k: float(v) for k, v in re.findall(r'"(red|green|blue)": ([\d.]+)', t)}
                lum.append(0.2126 * rgb.get('red', 0) + 0.7152 * rgb.get('green', 0) + 0.0722 * rgb.get('blue', 0))
            bg = '#161616' if lum and sum(lum) / len(lum) > 0.6 else '#e6e6e6'
            cv.warn('picture background replaced by a flat colour (picture unreachable)')
        else:
            bg = lay_bg.get(s.get('slideProperties', {}).get('layoutObjectId')) or master_bg or '#ffffff'
        body = [cv.element(e, i + 1) for e in s.get('pageElements', [])]
        notes = ''
        sec = '<section id="%s" style="background:%s">\n%s\n</section>' % (sid, bg, '\n'.join(b for b in body if b))
        open(os.path.join(outdir, 'project', 'slides', sid + '.html'), 'w').write(sec)
        order.append(sid)
    return order, cv
