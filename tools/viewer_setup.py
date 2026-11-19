"""Assemble a local copy of the Claude Slides viewer plus a deck, ready for tools/viewer_render.js.

Inputs (all saved by the Artifact tool's `read` action under one folder, e.g. <scratch>/artifact-files/<id>/):
  artifact-type/{app.js,app.css,capture.js,capture.css,editor.js,woff2.js,video.js,read-worker.js,export.js}
  project/{deck.json,deck.css,slides/*.html}
  the artifact's page HTML (read with page:true; the tool prints where it saved it)
Output: <out>/ with index.html (capture mode on), artifact-type/, project/ and _files.json.

    python tools/viewer_setup.py <artifact-files dir> <page.html> <out dir>
    # then: python tools/blobs_map.py ... (picture id -> local file) and
    #       NODE_PATH=$(npm root -g) node tools/viewer_render.js <out> <shots dir> <blobs.json> 4
"""
import hashlib, json, os, shutil, sys

NEEDED = ['app.js', 'app.css', 'capture.js', 'capture.css', 'editor.js', 'woff2.js', 'video.js', 'read-worker.js', 'export.js']

def main(src, page, out):
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out + '/artifact-type'); missing = []
    for f in NEEDED:
        p = os.path.join(src, 'artifact-type', f)
        if os.path.exists(p): shutil.copy(p, out + '/artifact-type/' + f)
        else: missing.append(f)
    for sub in ('fonts', 'thumbnail'):
        d = os.path.join(src, 'artifact-type', sub)
        if os.path.isdir(d): shutil.copytree(d, out + '/artifact-type/' + sub)
    shutil.copytree(os.path.join(src, 'project'), out + '/project')
    h = open(page).read(); tag = 'data-thumb-defer>'
    assert tag in h, 'page html has no data-thumb-defer on <html>: wrong file?'
    open(out + '/index.html', 'w').write(h.replace(tag, 'data-thumb-defer data-frame-capture>', 1))
    files = []
    for dp, _, fs in os.walk(out):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), out)
            if rel == '_files.json': continue
            b = open(os.path.join(dp, f), 'rb').read(); files.append(dict(path=rel, size=len(b), sha256=hashlib.sha256(b).hexdigest(), contentType='text/plain'))
    json.dump(files, open(out + '/_files.json', 'w'))
    deck = json.load(open(out + '/project/deck.json')); have = set(os.listdir(out + '/project/slides'))
    gaps = [i for i in deck['order'] if i + '.html' not in have]
    print('viewer root %s: %d files; missing code files: %s; slides in deck.json without a file: %d %s' % (out, len(files), missing or 'none', len(gaps), gaps[:5]))
    return 1 if missing or gaps else 0

if __name__ == '__main__': sys.exit(main(*sys.argv[1:4]))
