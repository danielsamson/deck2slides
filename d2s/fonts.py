"""Font facts: natural line height from the font file, line-spacing conversion, weight-to-face-name mapping,
calibration lookup. Works for any font the deck loads (Google Fonts via deck.json "faces", or local files)."""
import json, os, re, urllib.request
from . import config as C

UA_WOFF2 = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'

def _get(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA_WOFF2})
    d = urllib.request.urlopen(req, timeout=30).read(); return d if binary else d.decode('utf8')

def natural_from_file(path, source=C.NATURAL_SOURCE):
    """Line height / em from the font's own tables (what Google multiplies line-spacing percentages by)."""
    from fontTools.ttLib import TTFont
    f = TTFont(path); upm = f['head'].unitsPerEm
    if source == 'typo' and 'OS/2' in f: o = f['OS/2']; return (o.sTypoAscender - o.sTypoDescender + o.sTypoLineGap) / upm
    if source == 'win' and 'OS/2' in f: o = f['OS/2']; return (o.usWinAscent + o.usWinDescent) / upm
    h = f['hhea']; return (h.ascent - h.descent + h.lineGap) / upm

def fetch_family_file(family, href, cache):
    """Download one latin-subset font file for `family` from the Google Fonts CSS at `href`. Returns a path or None."""
    os.makedirs(cache, exist_ok=True); p = os.path.join(cache, re.sub(r'\W+', '_', family) + '.woff2')
    if os.path.exists(p): return p
    try:
        css = _get(href); blocks = re.findall(r'/\*\s*([\w-]+)\s*\*/\s*@font-face\s*{[^}]*?src:\s*url\(([^)]+)\)', css)
        url = next((u for n, u in blocks if n == 'latin'), blocks[0][1] if blocks else None)
        if not url: return None
        open(p, 'wb').write(_get(url, True)); return p
    except Exception as e:
        print('font fetch failed for', family, e); return None

def font_table(deck_json, fonts_json, cache):
    """family -> {natural, natural_browser, source, file}. natural comes from the font file when it can be fetched,
    else from the browser's own measurement of `line-height: normal` (extract.cjs), else NATURAL_FALLBACK."""
    faces = {v['family']: v['href'] for v in json.load(open(deck_json)).get('faces', {}).values()}
    out = {}
    for fam, info in json.load(open(fonts_json)).items():
        e = dict(natural_browser=info.get('naturalBrowser'), weights=info.get('weights', []))
        fp = fetch_family_file(fam, faces[fam], cache) if fam in faces else None
        if fp:
            try: e['natural'] = round(natural_from_file(fp), 4); e['source'] = 'font file (' + C.NATURAL_SOURCE + ')'; e['file'] = fp
            except Exception as ex: print('cannot read', fp, ex)
        if 'natural' not in e:
            e['natural'] = round(e['natural_browser'], 4) if e['natural_browser'] else C.NATURAL_FALLBACK; e['source'] = 'browser line-height:normal' if e['natural_browser'] else 'fallback'
        out[fam] = e
    return out

class FontDB:
    def __init__(self, table, calibration=None):
        self.t = table; self.cal = (calibration or {}).get('fonts', {})
    def natural(self, fam):
        c = self.cal.get(fam, {})
        if c.get('natural'): return c['natural']
        return self.t.get(fam, {}).get('natural') or C.NATURAL_FALLBACK
    def spc_pct(self, fam, css_lh):
        """CSS line-height (multiple of font size) -> Google line spacing (share of the font's own line height)."""
        return (css_lh or self.natural(fam)) / self.natural(fam)
    def dy(self, fam, lh, fs):
        """Px to move text down so Google's first line lands where Chromium's does."""
        tab = self.cal.get(fam, {}).get('dy')
        if not tab: return C.DY_FALLBACK_PER_FS * fs
        tab = sorted(tab); lh = lh or self.natural(fam)
        if lh <= tab[0][0]: d = tab[0][1]
        elif lh >= tab[-1][0]: d = tab[-1][1]
        else:
            for (a, da), (b, db) in zip(tab, tab[1:]):
                if a <= lh <= b: d = da + (db - da) * (lh - a) / (b - a); break
        return -d * fs
    @staticmethod
    def face(fam, weight):
        """Google face name for a family+weight. 700 is the bold flag on the plain family."""
        if fam == C.FALLBACK_FAMILY: return fam
        return fam + C.WEIGHT_SUFFIX.get(int(weight), '')
    @staticmethod
    def bold(weight): return int(weight) == C.BOLD_WEIGHT
