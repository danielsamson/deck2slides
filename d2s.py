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
from d2s import config as C, fonts as F, pptx_build, bundles, gslides, imgdiff, calibrate

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
c = sub.add_parser('report'); c.add_argument('work'); c.add_argument('thumbs'); c.add_argument('--ref', default='noimg'); c.add_argument('--ignore-pictures', action='store_true'); c.add_argument('--only'); c.add_argument('--diffs'); c.set_defaults(f=report)
a = p.parse_args(); a.f(a)
