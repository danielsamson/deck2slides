#!/usr/bin/env python3
"""deck2slides command line. Everything except the Google connector calls runs here. See README.md.

  d2s.py convert <deck dir> <work dir> [--assets map.json] [--gifs dir] [--calibration file] [--picture-mode mask|shape]
        extract + build + pack in one go: writes <work>/deck.pptx, manifest.json, pack/pack_NN.pptx, pack/list.txt
  d2s.py calib-deck <deck dir> <work dir>          make + build the calibration deck for the fonts <deck dir> uses -> <work>/calib/calib.pptx
  d2s.py calib-fit <work dir> <google image dir> [-o calibration.json]
  d2s.py pdf2png <file.pdf> <out dir>              Google's PDF export -> p1.png, p2.png ... (1920 px wide)
  d2s.py requests <work dir> <tags.json> <urls.json> [--ids-only]    replaceImage request list for update_presentation
  d2s.py report <work dir> <google image dir> [--ref noimg|full] [--ignore-pictures] [--only id,id] [--diffs dir]
"""
import argparse, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from d2s import config as C, fonts as F, pptx_build, bundles, gslides, imgdiff, calibrate, pptx2claude, tokens, dsbuild, components, componentsheet

def extract(deck, work, assets=None, gifs=None):
    os.makedirs(work, exist_ok=True)
    env = dict(os.environ)
    if 'NODE_PATH' not in env: env['NODE_PATH'] = subprocess.run(['npm', 'root', '-g'], capture_output=True, text=True).stdout.strip()
    cmd = ['node', HERE + '/js/extract.cjs', '--src', deck, '--out', work] + (['--assets', assets] if assets else []) + (['--gifs', gifs] if gifs else [])
    subprocess.run(cmd, check=True, env=env)

def font_db(deck, work, calibration=None):
    table = F.font_table(os.path.join(deck, 'deck.json'), work + '/fonts.json', work + '/fontcache')
    json.dump(table, open(work + '/font_table.json', 'w'), indent=1, default=float)
    cal = json.load(open(calibration)) if calibration and os.path.exists(calibration) else None
    return F.FontDB(table, cal), table, bool(cal)

def convert(a):
    extract(a.deck, a.work, a.assets, a.gifs); fdb, table, cal = font_db(a.deck, a.work, a.calibration)
    print('fonts:', {k: (v['natural'], v['source']) for k, v in table.items()}, '| calibration:', 'yes' if cal else 'NONE (first-line offsets uncorrected; run calib-deck/calib-fit)')
    for sl in json.load(open(a.work + '/slides.json')):
        for w in sl.get('warns', []): print('WARNING slide %s: %s' % (sl['id'], w), file=sys.stderr)
    pptx_build.build(a.work, a.work + '/deck.pptx', fdb, a.picture_mode, template=a.template)
    packs, too_big = bundles.pack(a.work)
    print('deck.pptx %d KB; %d bundles %s; too big for the connector (use a shared Drive folder): %s' % (os.path.getsize(a.work + '/deck.pptx') // 1024, len(packs), [p['kb'] for p in packs], too_big or 'none'))

def calib_deck(a):
    tmp = a.work + '/calib'; extract(a.deck, a.work + '/probe', a.assets, None)         # only to learn which fonts the deck uses
    fonts_used = json.load(open(a.work + '/probe/fonts.json')); cells = calibrate.make_deck(os.path.join(a.deck, 'deck.json'), fonts_used, tmp + '/deck')
    extract(tmp + '/deck', tmp + '/out'); table = F.font_table(tmp + '/deck/deck.json', tmp + '/out/fonts.json', a.work + '/fontcache')
    json.dump(table, open(tmp + '/font_table.json', 'w'), indent=1, default=float)
    pptx_build.build(tmp + '/out', tmp + '/calib.pptx', F.FontDB(table, None))
    print('calibration deck:', tmp + '/calib.pptx', len(cells), 'cells,', len({c['fam'] for c in cells}), 'fonts')

def calib_fit(a):
    tmp = a.work + '/calib'; table = json.load(open(tmp + '/font_table.json'))
    cal, rep = calibrate.fit(tmp + '/deck', tmp + '/out', a.thumbs, table)
    out = a.o or a.work + '/calibration.json'; json.dump(cal, open(out, 'w'), indent=1); print(json.dumps(rep, indent=1)); print('wrote', out)

def pdf2png(a):
    os.makedirs(a.out, exist_ok=True)
    subprocess.run(['pdftoppm', '-png', '-scale-to-x', '1920', '-scale-to-y', '1080', a.pdf, a.out + '/pp'], check=True)
    for f in sorted(os.listdir(a.out)):
        if f.startswith('pp-'): os.replace(a.out + '/' + f, '%s/p%d.png' % (a.out, int(f[3:].split('.')[0])))

def requests(a):
    m = json.load(open(a.work + '/manifest.json')); tags = json.load(open(a.tags)); urls = json.load(open(a.urls))
    if m['mode'] in ('mask', 'auto', 'embed'): reqs, missing = gslides.replace_image_requests(m['elements'], tags, urls)
    else: reqs, missing = gslides.replace_shape_requests(urls.keys(), urls), []
    print('missing elements:', missing, file=sys.stderr); print(gslides.dump(reqs))

def tokens_cmd(a):
    import json, os
    if a.src.endswith('.pptx'):
        model = tokens.from_pptx(a.src)
    else:
        model = tokens.from_gslides(json.load(open(a.src)), json.load(open(a.masters)) if a.masters else None, json.load(open(a.extra)) if a.extra else None, json.load(open(a.bg)) if a.bg else None)
    d = tokens.derive(model)
    os.makedirs(a.out, exist_ok=True)
    name = a.name or os.path.basename(a.src)
    json.dump(d, open(os.path.join(a.out, 'measured.json'), 'w'), indent=1, default=float)
    json.dump(tokens.to_tokens_json(d, name), open(os.path.join(a.out, 'tokens.flat.json'), 'w'), indent=1, default=float)
    ds = tokens.to_claude_ds(d, name)
    problems = tokens.validate_claude_ds(ds)
    json.dump(ds, open(os.path.join(a.out, 'tokens.json'), 'w'), indent=1, default=float)
    open(os.path.join(a.out, 'README.md'), 'w').write(tokens.to_markdown(d, name))
    print('Claude Design System tokens.json:', 'reads cleanly' if not problems else problems)
    json.dump(tokens.to_dtcg(d, name), open(os.path.join(a.out, 'tokens.dtcg.json'), 'w'), indent=1, default=float)
    open(os.path.join(a.out, 'tokens.css'), 'w').write(tokens.to_css(d))
    open(os.path.join(a.out, 'DESIGN.md'), 'w').write(tokens.to_markdown(d, name))
    structural = None
    if a.full:
        structural = components.extract(a.full, a.masters)
        json.dump({k: v for k, v in structural.items() if k not in ('components', 'atoms')} | {'components': [{k: v for k, v in c.items() if k != 'preview_body'} for c in structural['components']], 'atoms': [{k: v for k, v in c.items() if k not in ('preview_body', 'key')} for c in structural['atoms']]},
                  open(os.path.join(a.out, 'components.json'), 'w'), indent=1, default=str)
        open(os.path.join(a.out, 'components-sheet.html'), 'w').write(componentsheet.sheet(structural))
    if a.curation and structural:
        D_ = components.flatten  # noqa: keep import used
        data_c = json.load(open(a.full))['content']['slides']
        descs_c = [[components.describe(e) for e in components.flatten(s)] for s in data_c]
        chrome_c = components.find_chrome(descs_c, len(data_c))
        from d2s import gslides2claude as _G
        conv_c = _G.Conv({}, '/tmp/d2s-fontcache')
        curated, dropped, notes = components.curate(structural, json.load(open(a.curation)), descs_c, chrome_c, structural['slide_bg'], conv_c)
        structural['atoms'] = [c for c in curated if c.get('kind') == 'atom']
        structural['components'] = [c for c in curated if c.get('kind') != 'atom']
        structural['curation_notes'] = notes
        print('curation notes:', notes)
    lay_files = None
    if a.catalogue and a.full:
        from d2s import layouts as LY
        data_, descs_, chrome_, _g = LY.derive(a.full, a.masters)
        cat_ = LY.build_catalogue(json.load(open(a.catalogue)), descs_, chrome_, (structural or {}).get('atoms'))
        json.dump(cat_, open(os.path.join(a.out, 'layout-catalogue-verified.json'), 'w'), indent=1, default=str)
        ds_tokens = tokens.to_claude_ds(d, name)
        if structural is not None:
            structural['layout_status'] = [(e['name'], e['status']) for e in cat_]
        lay_files = dsbuild.layout_files(cat_, a.full, a.masters, ds_tokens, (structural or {}).get('components'))
    recipes_spec = None
    if a.recipes and a.full:
        from d2s import recipetest as RT, recipefiles as RF
        ds_tokens = tokens.to_claude_ds(d, name)
        tk_path = os.path.join(a.out, 'tokens-for-recipes.json')
        json.dump(ds_tokens, open(tk_path, 'w'))
        results = RT.run(a.recipes, a.full, a.masters, tk_path, os.path.join(a.out, 'recipe-test'))
        data_r = json.load(open(a.full))['content']['slides']
        descs_r = [[components.describe(e) for e in components.flatten(s)] for s in data_r]
        lay_files = RF.build(a.recipes, results, ds_tokens, descs_r)
        recipes_spec = dict(json.load(open(a.recipes)), results=results)
        recipes_spec['roles'] = json.load(open(a.curation)).get('roles', {}) if a.curation else {}
        json.dump(results, open(os.path.join(a.out, 'recipe-results.json'), 'w'), indent=1)
    if a.build:
        rep = dsbuild.build(model, d, name, os.path.join(a.out, 'system'), a.tagline, fetch=not a.no_fonts, structural=structural, layouts=lay_files, recipes=recipes_spec)
        json.dump(rep, open(os.path.join(a.out, 'build-report.json'), 'w'), indent=1)
        print('design system tree:', os.path.join(a.out, 'system', 'project'))
        print(json.dumps({k: v for k, v in rep.items() if k != 'files'}, indent=1))
        return
    print(tokens.to_markdown(d, name))


def pptx2claude_cmd(a):
    cal = json.load(open(a.calibration)) if a.calibration else None
    warns, n = pptx2claude.convert(a.pptx, a.out, cal)
    print('%d slides written to %s (deck.json, deck.css, slides/, assets/, assets-map.json)' % (n, a.out))
    for w in warns: print('WARNING', w, file=sys.stderr)

def report(a):
    only = set(a.only.split(',')) if a.only else None
    if a.diffs: os.makedirs(a.diffs, exist_ok=True)
    rows = imgdiff.report(a.work, a.thumbs, a.ref, a.diffs, only, a.ignore_pictures)
    print('%-3s %-16s %7s %7s %6s %8s %8s %4s' % ('#', 'slide', 'diff%', 'regions', 'blocks', 'max_off', 'mean_off', '>4px'))
    for r in rows: print('%-3d %-16s %7.2f %7d %6d %8d %8.2f %4d' % (r['slide'], r['id'], r['pct'], r['regions'], r['blocks'], r['max_off'], r['mean_off'], r['bad']))
    clean = sum(1 for r in rows if r['pct'] < C.CLEAN_SLIDE_PCT); print('%d slides, %d clean (<%.2f%% pixels differ), %d text blocks off by more than 4 px' % (len(rows), clean, C.CLEAN_SLIDE_PCT, sum(r['bad'] for r in rows)))
    json.dump(rows, open(a.work + '/report_%s.json' % os.path.basename(a.thumbs.rstrip('/')), 'w'), indent=1, default=float)

p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='cmd', required=True)
c = sub.add_parser('convert'); c.add_argument('deck'); c.add_argument('work'); c.add_argument('--assets'); c.add_argument('--gifs'); c.add_argument('--calibration'); c.add_argument('--template'); c.add_argument('--picture-mode', default=C.PICTURE_MODE, choices=['auto', 'embed', 'mask', 'shape']); c.set_defaults(f=convert)
c = sub.add_parser('calib-deck'); c.add_argument('deck'); c.add_argument('work'); c.add_argument('--assets'); c.set_defaults(f=calib_deck)
c = sub.add_parser('calib-fit'); c.add_argument('work'); c.add_argument('thumbs'); c.add_argument('-o'); c.set_defaults(f=calib_fit)
c = sub.add_parser('pdf2png'); c.add_argument('pdf'); c.add_argument('out'); c.set_defaults(f=pdf2png)
c = sub.add_parser('requests'); c.add_argument('work'); c.add_argument('tags'); c.add_argument('urls'); c.set_defaults(f=requests)
c = sub.add_parser('pptx2claude'); c.add_argument('pptx'); c.add_argument('out'); c.add_argument('--calibration'); c.set_defaults(f=pptx2claude_cmd)
c = sub.add_parser('tokens'); c.add_argument('src'); c.add_argument('out'); c.add_argument('--masters'); c.add_argument('--extra'); c.add_argument('--bg'); c.add_argument('--full'); c.add_argument('--catalogue'); c.add_argument('--recipes'); c.add_argument('--curation'); c.add_argument('--name'); c.add_argument('--build', action='store_true'); c.add_argument('--tagline'); c.add_argument('--no-fonts', action='store_true'); c.set_defaults(f=tokens_cmd)
c = sub.add_parser('report'); c.add_argument('work'); c.add_argument('thumbs'); c.add_argument('--ref', default='noimg'); c.add_argument('--ignore-pictures', action='store_true'); c.add_argument('--only'); c.add_argument('--diffs'); c.set_defaults(f=report)
a = p.parse_args(); a.f(a)
