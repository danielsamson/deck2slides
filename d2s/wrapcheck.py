"""Find text blocks whose line breaks differ between the browser (viewer) and Google Slides.

The browser breaks lines with rules Slides does not have (text-wrap: pretty, a different hyphen rule, sub-pixel widths). The PDF export of the Google deck
carries every word with its position, so we count the lines each block really has there and compare with the lines the browser had (slides.json).
Blocks that differ get explicit line breaks (corrections key `force`), the same route already used for tight and letter-spaced text."""
import json, re, subprocess, sys, xml.etree.ElementTree as ET

def pdf_words(pdf):
    out = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True, check=True).stdout
    out = re.sub(r'<!DOCTYPE[^>]*>', '', out); out = re.sub(r'xmlns="[^"]*"', '', out)
    root = ET.fromstring(out); pages = []
    for pg in root.iter('page'):
        k = 1920 / float(pg.get('width')); ws = []
        for w in pg.iter('word'):
            ws.append((w.text or '', float(w.get('xMin')) * k, float(w.get('yMin')) * k, float(w.get('xMax')) * k, float(w.get('yMax')) * k))
        pages.append(ws)
    return pages

def norm(s): return re.sub(r'\W+', '', s.lower())

def check(slides, pdf):
    """-> [{'key': 'slide id:item index', 'viewer': n, 'google': m, 'text': ...}]"""
    pages = pdf_words(pdf); res = []
    for sl, ws in zip(slides, pages):
        for i, it in enumerate(sl['items']):
            t = it.get('text'); 
            if not t or t.get('wa') or it.get('rot'): continue
            raw = ''.join(('\u000b' if r.get('br') else r.get('t', '')) for r in t['runs'])
            vlines = [[norm(w) for w in ln.split() if norm(w)] for ln in raw.split('\u000b')]; vlines = [l for l in vlines if l]
            words = [w for l in vlines for w in l]
            if len(words) < 2: continue
            x0, x1, y0, y1 = it['cx'] - it['w'] / 2 - 12, it['cx'] + it['w'] / 2 + 12, it['cy'] - it['h'] / 2 - 12, it['cy'] + it['h'] / 2 + 12
            inside = [w for w in ws if x0 <= (w[1] + w[3]) / 2 <= x1 and y0 <= (w[2] + w[4]) / 2 <= y1]
            got = [w for w in inside if norm(w[0]) in set(words)]
            if len(got) < 0.8 * len(words): continue
            got.sort(key=lambda w: ((w[2] + w[4]) / 2, w[1])); glines = [[got[0]]]
            for w in got[1:]:
                if (w[2] + w[4]) / 2 - (glines[-1][-1][2] + glines[-1][-1][4]) / 2 > 0.5 * t['fs']: glines.append([w])
                else: glines[-1].append(w)
            gc = [norm(l[0][0])[:3] for l in glines]; vc = [l[0][:3] for l in vlines]
            if gc != vc: res.append(dict(key='%s:%d' % (sl['id'], i), viewer=vc, google=gc, text=' '.join(words)[:60]))
    return res

if __name__ == '__main__':
    slides = json.load(open(sys.argv[1] + '/slides.json')); r = check(slides, sys.argv[2])
    for x in r: print(x['key'], x['viewer'], x['google'], x['text'])
    print(len(r), 'blocks with different line counts')
