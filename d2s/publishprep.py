"""Prepare a generated system for an artifact: resolve IMG:<key> placeholders.
Preview cards get the picture inline as a data: URI (the type allows it and it does not depend on the preview frame loading /_blob/ links;
a preview file is capped at 256 KB, so pictures are shrunk to fit); example slides get /_blob/<id> after the pictures are uploaded."""
import base64, io, os, re
from PIL import Image


def data_uri(path, max_w=1000, quality=72):
    im = Image.open(path)
    alpha = im.mode in ('RGBA', 'LA')
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)))
    buf = io.BytesIO()
    if alpha:
        im.save(buf, 'PNG', optimize=True)
        mime = 'image/png'
    else:
        im.convert('RGB').save(buf, 'JPEG', quality=quality, optimize=True)
        mime = 'image/jpeg'
    return 'data:%s;base64,%s' % (mime, base64.b64encode(buf.getvalue()).decode())


def resolve_preview(text, imgmap, limit=250000):
    """Inline every picture of one preview file, shrinking until the whole file fits."""
    for max_w, q in ((1000, 72), (800, 65), (600, 60), (420, 55)):
        def sub(m):
            p = imgmap.get(m.group(1))
            return ('src="%s"' % data_uri(p, max_w, q)) if p and os.path.exists(p) else 'data-missing="1"'
        out = re.sub(r'src="IMG:([^"]+)"', sub, text)
        if len(out.encode()) <= limit:
            return out
    return out
