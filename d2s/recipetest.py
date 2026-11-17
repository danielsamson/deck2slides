"""Recreate-and-compare: render each recipe with the content of each of its evidence slides, render the source slide the same way,
and report how many pixels differ. The converter's own render of the source slide is the reference (it matched Google's thumbnails
within about 2 to 4 percent on text slides)."""
import json, os, re, subprocess, tempfile
from . import components as C, gslides2claude as G, recipes as R, dsbuild


def css(tk):
    root = [l for l in dsbuild.compile_css(tk).split('\n') if not l.startswith('@font-face')]
    th = ''.join('section.th-%s{%sbackground:var(--paper);color:var(--ink)}\n' % (t['id'], ''.join('--%s:%s;' % (c['name'], c['value'][t['id']]) for c in tk['color']['tokens'] if isinstance(c['value'], dict))) for t in tk['color']['themes'])
    return '\n'.join(root) + '\nsection{position:relative;width:1920px;height:1080px;overflow:hidden;font-family:var(--font-body)}\n' + th


def page(section, tk, imgmap=None):
    section = G.resolve_images(section, {k: 'file://' + os.path.abspath(v) for k, v in (imgmap or {}).items()})
    section = re.sub(r'<img ([^>]*)>', r'<div style="background:#888;\1"></div>', section) if False else section
    return ('<html><head><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap"><style>*{margin:0;box-sizing:border-box}%s</style></head><body>%s</body></html>' % (css(tk), section))


def shoot(files, outdir):
    js = os.path.join(outdir, 'shots.cjs')
    open(js, 'w').write("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1920,height:1080}});"
                        "for(const f of process.argv.slice(2)){await p.goto('file://'+f);await p.waitForTimeout(500);await p.screenshot({path:f.replace('.html','.png')});}await b.close();})();")
    subprocess.run(['node', js] + files, check=True, env=dict(os.environ, NODE_PATH='/opt/node-tools/node_modules'))


def run(recipes_json, slides_json, masters_json, tokens_json, outdir, imgmap=None):
    from PIL import Image
    import numpy as np
    outdir = os.path.abspath(outdir)
    spec = json.load(open(recipes_json))
    tk = json.load(open(tokens_json))
    data = json.load(open(slides_json))['content']['slides']
    descs = [[C.describe(e) for e in C.flatten(s)] for s in data]
    os.makedirs(outdir, exist_ok=True)
    need = {n - 1 for r in spec['recipes'] for n in r['evidence']}
    work = tempfile.mkdtemp()
    G.convert(slides_json, masters_json, work, only=need)
    jobs, report = [], []
    for r in spec['recipes']:
        r = dict(r, font=spec['font'], styles=spec['styles'])
        for n in r['evidence']:
            content = R.extract(r, descs[n - 1], tk, n)
            rec = R.render(r, content, tk)
            src = open('%s/project/slides/s%03d.html' % (work, n)).read()
            src = src.replace('<section id="s%03d"' % n, '<section class="th-%s"' % r['theme'], 1) if False else src
            # the source section carries its own background; give both the theme class so ink and paper variables resolve
            src = re.sub(r'<section id="s\d+" style="background:([^"]*)">', r'<section class="th-%s" style="background:\1">' % r['theme'], src)
            a = os.path.join(outdir, '%s-%d-src.html' % (r['id'], n))
            b = os.path.join(outdir, '%s-%d-rec.html' % (r['id'], n))
            open(a, 'w').write(page(src, tk, imgmap))
            open(b, 'w').write(page(rec, tk, imgmap))
            jobs += [a, b]
            report.append((r['id'], n, a, b))
    shoot(jobs, outdir)
    out = {}
    for rid, n, a, b in report:
        ia = np.asarray(Image.open(a.replace('.html', '.png')).convert('RGB')).astype(int)
        ib = np.asarray(Image.open(b.replace('.html', '.png')).convert('RGB')).astype(int)
        out.setdefault(rid, {})[n] = round(float((abs(ia - ib).sum(axis=2) > 60).mean() * 100), 2)
    return out
