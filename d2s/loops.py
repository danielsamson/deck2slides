"""Looping GIFs for Slides, which plays animated GIFs but not video loops, CSS animation or animated WebP.

Two sources, both found in slides.json after extract.cjs:
- an <img> whose file is an animated WebP (a short video loop): its own frames and timing;
- an inline <svg> with infinite CSS animations: extract.cjs recorded one period of frames (item['loop']).

GIF has 256 colours a frame, so soft glows band unless dithered: one palette per GIF from all frames, error-diffusion
dither (ffmpeg palettegen/paletteuse), then gifsicle --lossy (about a quarter of the size on dithered glows).
Two files per loop: gifs/<name>.gif fits one Drive connector call (about 3.1 MB of file per call, measured; nothing over
10 MB at all), gifs/hq/<name>.gif is for replacing the picture by hand in Slides (Replace image > Upload; Slides takes up
to 50 MB). Needs ffmpeg; gifsicle is optional but strongly advised."""
import json, os, shutil, subprocess
from PIL import Image
from . import config as C

def is_animated(path):
    try:
        with Image.open(path) as im: return getattr(im, 'n_frames', 1) > 1 and im.format in ('WEBP', 'PNG', 'GIF')
    except Exception: return False

def _encode_once(frame_glob, in_fps, out, w, fps, lossy):
    vf = ("fps=%.4f,scale=%d:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=256:stats_mode=full[p];"
          "[b][p]paletteuse=dither=sierra2_4a:diff_mode=rectangle") % (fps, w)
    raw = out + '.raw.gif'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '%.4f' % in_fps, '-i', frame_glob, '-vf', vf, '-loop', '0', raw], check=True)
    if shutil.which('gifsicle'): subprocess.run(['gifsicle', '-O3'] + (['--lossy=%d' % lossy] if lossy else []) + [raw, '-o', out], check=True); os.remove(raw)
    else: os.replace(raw, out)
    return os.path.getsize(out)

def encode(frame_glob, in_fps, out, max_w, budget_kb, lossy=C.GIF_LOSSY):
    """Best GIF under budget_kb: full width and frame rate first; then narrower (size goes with area, so the width is
    predicted from the last try), and below GIF_MIN_W fewer frames per second. Error-diffusion dither keeps glows smooth."""
    w, fps, tries = max_w, in_fps, 0
    while True:
        sz = _encode_once(frame_glob, in_fps, out, w, fps, lossy); tries += 1
        if sz <= budget_kb * 1024 or tries >= 6: break
        nw = int(w * min(0.95, (budget_kb * 1024 / sz) ** 0.5 * 0.97)) // 2 * 2
        if nw < C.GIF_MIN_W and fps > in_fps / 2 + 0.01: fps = max(in_fps / 2, fps * 2 / 3); continue
        w = max(nw, 160)
    with Image.open(out) as g: n = g.n_frames; gw, gh = g.size
    return dict(file=out, frames=n, size=[gw, gh], fps=round(fps, 2), kb=os.path.getsize(out) // 1024, fits=os.path.getsize(out) <= budget_kb * 1024)

def both(frame_glob, in_fps, out_dir, name, max_w):
    """Upload version (fits the connector: GIF_UPLOAD_KB) and HQ version (for replacing by hand in Slides: GIF_HQ_KB).
    Cached: the same frames and settings give the same files, so a rebuild skips the (slow) encode."""
    import glob, hashlib
    os.makedirs(os.path.join(out_dir, 'hq'), exist_ok=True)
    h = hashlib.sha1(repr((in_fps, max_w, C.GIF_UPLOAD_KB, C.GIF_HQ_KB, C.GIF_LOSSY, C.GIF_LOSSY_HQ, C.GIF_MIN_W)).encode())
    for f in sorted(glob.glob(frame_glob.replace('%05d', '*'))): h.update(open(f, 'rb').read())
    keyf = os.path.join(out_dir, name + '.json'); key = h.hexdigest()
    if os.path.exists(keyf):
        c = json.load(open(keyf))
        if c.get('key') == key and all(os.path.exists(c[k]['file']) for k in ('up', 'hq')): return c['up'], c['hq']
    hq = encode(frame_glob, in_fps, os.path.join(out_dir, 'hq', name + '.gif'), max_w, C.GIF_HQ_KB, C.GIF_LOSSY_HQ)
    up = encode(frame_glob, in_fps, os.path.join(out_dir, name + '.gif'), max_w, C.GIF_UPLOAD_KB)
    json.dump(dict(key=key, up=up, hq=hq), open(keyf, 'w'))
    return up, hq

def _desc(r): return '%dx%d %d frames %.4g fps %d KB' % (r['size'][0], r['size'][1], r['frames'], r['fps'], r['kb'])

def webp_frames(src, dir_):
    """Animated WebP/APNG -> PNG frames at a constant rate; returns fps (from the mean frame duration)."""
    shutil.rmtree(dir_, ignore_errors=True); os.makedirs(dir_)
    with Image.open(src) as im:
        durs = []
        for i in range(im.n_frames):
            im.seek(i); im.load(); durs.append(im.info.get('duration') or 100)
            im.convert('RGB').save(os.path.join(dir_, 'f_%05d.png' % i))
    return 1000.0 / (sum(durs) / len(durs))

def make_all(work, max_w=None):
    """Writes <work>/gifs/*.gif and sets item['gif'] in slides.json. Returns a list of report lines."""
    sj = os.path.join(work, 'slides.json'); data = json.load(open(sj)); out = os.path.join(work, 'gifs'); os.makedirs(out, exist_ok=True)
    rep, done = [], {}
    for sl in data:
        for it in sl['items']:
            if it['type'] == 'svg' and it.get('loop'):
                lp = it['loop']; mw = max_w or C.GIF_LOOP_MAX_W
                r, hq = both(os.path.join(lp['dir'], 'f_%05d.png'), lp['fps'], out, it['id'], mw); it['gif'] = r['file']; it['gif_hq'] = hq['file']
                chg = (' (loop speeds nudged up to %.1f%%: %s ms -> %s ms)' % (lp['max_change_pct'], lp['durations_ms'], [round(x) for x in lp['adjusted_ms']])) if lp['max_change_pct'] else ''
                rep.append('slide %s: looping drawing (%.1f s loop) -> GIF %s; HQ %s%s' % (sl['id'], lp['period_ms'] / 1000, _desc(r), _desc(hq), chg))
            elif it['type'] == 'img' and it.get('src') and os.path.exists(it['src']) and is_animated(it['src']) and not it['src'].lower().endswith('.gif'):
                if it['src'] not in done:
                    key = os.path.splitext(os.path.basename(it['src']))[0]; fdir = os.path.join(work, 'loops', 'img_' + key)
                    fps = webp_frames(it['src'], fdir); mw = max_w or min(C.GIF_VIDEO_MAX_W, int(round(it['w'] * C.GIF_VIDEO_SCALE)))
                    r, hq = both(os.path.join(fdir, 'f_%05d.png'), fps, out, key, mw); done[it['src']] = (r, hq)
                    rep.append('slide %s: video loop (animated %s, %.4g fps) -> GIF %s; HQ %s' % (sl['id'], os.path.splitext(it['src'])[1], fps, _desc(r), _desc(hq)))
                it['gif'], it['gif_hq'] = done[it['src']][0]['file'], done[it['src']][1]['file']
    for sl in data:                      # a looping drawing's ground goes under it (full-slide picture, rendered by the browser)
        items = sl['items']
        for i, it in enumerate(list(items)):
            if it.get('gif') and it.get('ground') and os.path.exists(it['ground']) and not it.get('_grounded'):
                it['_grounded'] = True; k = items.index(it)
                ground = dict(type='img', src=it['ground'], nw=1920, nh=1080, fit='fill', radius=0, shadow=None, op=1, pad=None, bw=None, cpath=None, ovclip=None, cx=960, cy=540, w=1920, h=1080, rot=0)
                before = items[:k]; keep = [x for x in before if not (x['type'] == 'shape' and x.get('text')) and x['type'] not in ('line', 'link')]
                lift = [x for x in before if x not in keep]          # text, lines and links stay above the ground
                sl['items'] = keep + [ground] + lift + items[k:]; items = sl['items']
                rep.append('slide %s: ground picture under the looping drawing (%d text boxes kept above it)' % (sl['id'], sum(1 for x in lift if x.get('text'))))
    json.dump(data, open(sj, 'w'), indent=1)
    return rep
