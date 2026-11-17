"""Pictures of a Google Slides deck, prepared for artifacts: key (the placeholder IMG:<key>) -> a web-sized file.
Index comes from the connector's contentUrl list (downloaded while the signed links are fresh, they last minutes)."""
import json, os, hashlib
from PIL import Image


def placeholder_portrait(path):
    """A generic grey silhouette, drawn here, standing in for portraits of real people."""
    from PIL import ImageDraw
    im = Image.new('RGB', (512, 512), (58, 58, 58))
    d = ImageDraw.Draw(im)
    d.ellipse((176, 110, 336, 270), fill=(112, 112, 112))             # head
    d.ellipse((96, 300, 416, 660), fill=(112, 112, 112))              # shoulders, cropped by the frame
    im.save(path, quality=90)
    return os.path.abspath(path)


def build_map(images_dir, outdir, max_w=1600, skip_squares=(512,)):
    idx = json.load(open(os.path.join(images_dir, 'index.json')))
    os.makedirs(outdir, exist_ok=True)
    out = {}
    ph = placeholder_portrait(os.path.join(outdir, 'placeholder-portrait.jpg'))
    out['placeholder-portrait'] = ph
    for k, base in idx['links'].items():
        kind, slide, oid = k.split('|')
        f = idx['files'].get(base)
        if not f:
            continue
        key = ('bg%s' % slide) if kind == 'bg' else oid
        im = Image.open(os.path.join(images_dir, f['file']))
        if im.width == im.height and im.width in skip_squares:
            out[('bg%s' % slide) if kind == 'bg' else oid] = ph   # portraits of real people stay out of generated systems: the placeholder stands in
            continue
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
