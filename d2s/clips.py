"""Clip GIF preparation from an MP4: frame limit, still areas held still, a settled first frame (the poster, because Slides
thumbnails and PDF exports show the first frame). The GIF stays a plain rectangle: roundness comes from the picture mask in the
deck (replaceImage keeps it), so corners are always right. Needs ffmpeg and gifsicle."""
import os, shutil, subprocess
import numpy as np
from PIL import Image
from . import config as C

def frames_of(mp4, w, aspect, fps, tmp):
    shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp4, '-vf', 'fps=%d,scale=%d:-2:flags=lanczos' % (fps, w), tmp + '/%05d.png'], check=True)
    fr = [np.asarray(Image.open(tmp + '/' + f).convert('RGB')) for f in sorted(os.listdir(tmp))]; shutil.rmtree(tmp)
    H, Wd = fr[0].shape[:2]; th = int(round(Wd / aspect))                    # object-fit: cover
    if th < H: t = (H - th) // 2; fr = [f[t:t + th] for f in fr]
    elif th > H: tw = int(round(H * aspect)); l = (Wd - tw) // 2; fr = [f[:, l:l + tw] for f in fr]
    return fr

def hold_still(fr, thr=C.GIF_STILL_THRESHOLD):
    """A pixel only changes when it really changes (and its 4-neighbours with it), so the GIF stores motion only."""
    res = [fr[0].astype(np.int16)]
    for a in fr[1:]:
        a = a.astype(np.int16); p = res[-1]; ch = np.abs(a - p).max(2) > thr
        g = ch.copy(); g[1:] |= ch[:-1]; g[:-1] |= ch[1:]; g[:, 1:] |= ch[:, :-1]; g[:, :-1] |= ch[:, 1:]
        res.append(np.where(g[..., None], a, p))
    return [r.astype(np.uint8) for r in res]

def delays(n, fps):   # whole centiseconds that add up exactly: 7,7,6,7,7,6 at 15 fps
    return [int(round((i + 1) * 100 / fps)) - int(round(i * 100 / fps)) for i in range(n)]

def fps_for(n_frames_at_default):
    """Largest fps that keeps the GIF under the frame limit (+1 for the poster frame)."""
    return C.GIF_FPS if n_frames_at_default + 1 <= C.GIF_MAX_FRAMES else C.GIF_FPS_LONG

def make_gif(mp4, poster_png, aspect, out, width=C.GIF_WIDTH, tmp='/tmp/d2s_frames'):
    fps = C.GIF_FPS; fr = frames_of(mp4, width, aspect, fps, tmp)
    if len(fr) + 1 > C.GIF_MAX_FRAMES: fps = C.GIF_FPS_LONG; fr = frames_of(mp4, width, aspect, fps, tmp)
    assert len(fr) + 1 <= C.GIF_MAX_FRAMES, 'clip too long even at %d fps' % fps
    fr = hold_still(fr); h, w = fr[0].shape[:2]
    if poster_png:
        im = Image.open(poster_png).convert('RGB'); iw, ih = im.size; th = round(iw / aspect)
        im = im.crop((0, (ih - th) // 2, iw, (ih - th) // 2 + th)) if th <= ih else im.crop(((iw - round(ih * aspect)) // 2, 0, (iw - round(ih * aspect)) // 2 + round(ih * aspect), ih))
        first = np.asarray(im.resize((w, h), Image.LANCZOS))
    else: first = fr[-1]                                                      # no poster given: the last frame is the most settled
    allf = [first] + fr
    sample = np.concatenate(allf[::max(1, len(allf) // 40)], axis=1); pal_im = Image.fromarray(sample).quantize(256, method=Image.MEDIANCUT, dither=Image.NONE)
    pal = pal_im.getpalette()[:768]; pref = Image.new('P', (1, 1)); pref.putpalette(pal)
    fp = [np.asarray(Image.fromarray(f).quantize(palette=pref, dither=Image.NONE)) for f in allf]
    dl = [C.GIF_POSTER_CS] + delays(len(fr), fps); mf, md = [fp[0]], [dl[0]]
    for f, d in zip(fp[1:], dl[1:]):
        if np.array_equal(f, mf[-1]): md[-1] += d
        else: mf.append(f); md.append(d)
    ims = []
    for f in mf: im = Image.fromarray(f, 'P'); im.putpalette(pal); ims.append(im)
    ims[0].save(out + '.raw.gif', save_all=True, append_images=ims[1:], duration=[x * 10 for x in md], disposal=1, loop=0, optimize=False)
    subprocess.run(['gifsicle', '-O3', out + '.raw.gif', '-o', out], check=True); os.remove(out + '.raw.gif')
    chk = Image.open(out); assert chk.n_frames < 1000, chk.n_frames
    return dict(file=out, frames=chk.n_frames, fps=fps, kb=os.path.getsize(out) // 1024)
