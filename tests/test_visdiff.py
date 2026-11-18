import numpy as np
from PIL import Image
from d2s import visdiff

def img(x):
    a = np.full((90, 160, 3), 255, 'uint8'); a[40:50, x:x + 30] = 0; return Image.fromarray(a)

def test_identical_images_overlay_is_neutral():
    o = np.asarray(visdiff.overlay(img(20), img(20)))
    assert (o[..., 0] == o[..., 1]).all() and (o[..., 1] == o[..., 2]).all()

def test_shift_shows_red_only_and_cyan_only_edges():
    o = np.asarray(visdiff.overlay(img(20), img(26)))          # Google (second) is 6 px to the right
    assert o[45, 21, 0] == 0 and o[45, 21, 1] == 255            # dark ink only in Claude: red channel dark, so the pixel reads cyan
    left = o[45, 21]; right = o[45, 54]
    assert left[0] < left[1] and right[0] > right[1]            # left edge: Claude-only dark ink reads cyan; right edge: Google-only dark ink reads red
