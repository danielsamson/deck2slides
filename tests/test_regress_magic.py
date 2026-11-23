"""End-to-end offline check of the Magic Circle fixes (test-decks/regress-magic/check.py). Slow (Chromium, ffmpeg, about 20 s): D2S_SLOW=1."""
import os, subprocess, sys
import pytest

@pytest.mark.skipif(os.environ.get('D2S_SLOW') != '1', reason='set D2S_SLOW=1 (needs Chromium, ffmpeg, network for the Inter files once)')
def test_regress_magic():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = subprocess.run([sys.executable, os.path.join(root, 'test-decks/regress-magic/check.py')], capture_output=True, text=True, cwd=root)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
