"""Patch a deck that is already in Google Slides, without re-exporting it.

Once someone has edited the Slides deck, a fresh export would overwrite their work. Per-block offsets measured by `fit-text`
(corrections.json: {'slide id:item index': {dy, dx, dw}} in px, Google minus browser) are therefore applied in place:
one updatePageElementTransform (ABSOLUTE) per block, moved by (-dx, -dy). Width (dw) is not patched: Slides re-wraps text.

Blocks are found in the live deck by geometry, not by id: the item's centre (cx, cy) and size (w, h) from slides.json against each
element's transform and size on page p<slide index + 1> (the page ids the PPTX import gives). A block is skipped, and reported, when
no element or more than one element matches, so a moved or resized element is never patched by mistake.

Live deck input: read_presentation with fields
  ['slides.objectId', 'slides.pageElements(objectId,size,transform)'] saved as JSON.
"""
from .config import EMU_PER_PX

def _centre(el):
    t = el.get('transform') or {}; s = el.get('size') or {}
    if abs(t.get('shearX', 0)) > 1e-6 or abs(t.get('shearY', 0)) > 1e-6: return None        # rotated: not patched
    w = s['width']['magnitude'] * t.get('scaleX', 1); h = s['height']['magnitude'] * t.get('scaleY', 1)
    return (t.get('translateX', 0) + w / 2) / EMU_PER_PX, (t.get('translateY', 0) + h / 2) / EMU_PER_PX, w / EMU_PER_PX, h / EMU_PER_PX

def plan(slides, live, corrections, min_px=2, tol_c=14, tol_s=0.06):
    """-> (requests, report). report rows: (key, status, detail)."""
    pages = {p['objectId']: p for p in live.get('slides', [])}; by_id = {s['id']: s for s in slides}
    reqs, rep = [], []
    for key, c in sorted(corrections.items()):
        sid, idx = key.rsplit(':', 1); s = by_id.get(sid)
        if not s: rep.append((key, 'skipped', 'slide not in this export')); continue
        dx, dy = float(c.get('dx', 0)), float(c.get('dy', 0))
        if max(abs(dx), abs(dy)) < min_px: continue
        it = s['items'][int(idx)]; page = pages.get('p%d' % (s['i'] + 1))
        if not page: rep.append((key, 'skipped', 'page missing in live deck')); continue
        hits = []
        for el in page.get('pageElements', []):
            g = _centre(el)
            if not g: continue
            if abs(g[0] - it['cx']) <= tol_c and abs(g[1] - it['cy']) <= tol_c and abs(g[2] - it['w']) <= tol_s * it['w'] + 4 and abs(g[3] - it['h']) <= tol_s * it['h'] + 4:
                hits.append(el)
        if len(hits) != 1: rep.append((key, 'skipped', '%d elements match' % len(hits))); continue
        el = hits[0]; t = dict(el['transform']); t['translateX'] = t.get('translateX', 0) - dx * EMU_PER_PX; t['translateY'] = t.get('translateY', 0) - dy * EMU_PER_PX; t['unit'] = 'EMU'
        reqs.append({'updatePageElementTransform': {'objectId': el['objectId'], 'applyMode': 'ABSOLUTE', 'transform': t}})
        rep.append((key, 'patched', '%s by dx %.1f dy %.1f px' % (el['objectId'], -dx, -dy)))
    return reqs, rep
