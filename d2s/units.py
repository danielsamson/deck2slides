"""Unit conversion and small geometry helpers. Pure functions."""
import math
from .config import EMU_PER_PX, PT_PER_PX

def emu(px): return int(round(px * EMU_PER_PX))
def pt(px): return px * PT_PER_PX
def sz100(px): """OOXML font size: hundredths of a point""" ; return int(round(px * PT_PER_PX * 100))
def hexc(c): return '%02X%02X%02X' % (round(c['r']), round(c['g']), round(c['b']))
def rot_vec(dx, dy, deg):
    r = math.radians(deg); return dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
def px_to_emu_box(cx, cy, w, h): return emu(cx - w / 2), emu(cy - h / 2), max(1, emu(w)), max(1, emu(h))
