"""Pictures of a Google Slides deck, prepared for artifacts: key (the placeholder IMG:<key>) -> a web-sized file.
Index comes from the connector's contentUrl list (downloaded while the signed links are fresh, they last minutes)."""
import json, os, hashlib
from PIL import Image


def build_map(images_dir, outdir, max_w=1600, skip_squares=(512,)):
    idx = json.load(open(os.path.join(images_dir, 'index.json')))
    os.makedirs(outdir, exist_ok=True)
    out = {}
    for k, base in idx['links'].items():
        kind, slide, oid = k.split('|')
        f = idx['files'].get(base)
        if not f:
            continue
        key = ('bg%s' % slide) if kind == 'bg' else oid
        im = Image.open(os.path.join(images_dir, f['file']))
        if im.width == im.height and im.width in skip_squares:
            continue                         # portraits of real people stay out of generated systems
        try:
            im.seek(0)                       # an animated gif becomes its first frame
        except Exception:
            pass
        alpha = im.mode in ('RGBA', 'LA') or 'transparency' in im.info
        im = im.convert('RGBA' if alpha else 'RGB')
        if im.width > max_w:
            im = im.resize((max_w, int(im.height * max_w / im.width)))
        name = hashlib.sha1(base.encode()).hexdigest()[:12] + ('.png' if alpha else '.jpg')
        p = os.path.join(outdir, name)
        if not os.path.exists(p):
            im.save(p, optimize=True) if alpha else im.save(p, quality=85, optimize=True)
        out[key] = os.path.abspath(p)
    return out
