# deck2slides

Converts a Claude **Slides-artifact deck** (`deck.json`, `deck.css`, `slides/*.html`) into a native, editable **Google Slides**
deck: text is text, cards/pills/circles are shapes, pictures are pictures, clips are GIFs. Nothing is flattened.

How: lay every slide out in headless Chromium at 1920x1080 (`js/extract.cjs`) -> write a small PowerPoint with native shapes
(`d2s/pptx_build.py`) -> Drive converts it to Google Slides on upload -> pictures are swapped in by Slides from URLs
(`d2s/gslides.py` builds the requests) -> compare Google's slide images with the browser render (`d2s/imgdiff.py`).

## Status (read this first)

Built and checked **offline** in the session that wrote it: extraction, build, font metrics, bundling, GIF prep, request builders,
unit tests (`python3 -m pytest tests`), and an offline regression (below). **Not yet verified against Google** in this session:
the Drive connector refused file-reference uploads (`File references can't be used here`) and inline base64 of a 17 KB file got
corrupted in transit, so none of the Google round trips (calibration, feature decks, thumbnails, `replaceImage` mask behaviour)
have been run. Every rule in the table below marked *carried over* comes from the earlier hand-measured conversion of the pitch deck;
*unverified* means the test deck exists but has not been through Google yet.

Offline regression: the pitch deck (28 slides) rebuilt with this package plus `examples/pitch-legacy-calibration.json` (the old
hand table in the new calibration format) gives 819 shapes, 803 identical to the old build in position, size, text and line spacing;
the other 16 differ only in the picture tag name. Max geometry difference 0.08 px. The pixel-diff regression against Google
(20 of 28 slides clean) still has to be run with the checklist below.

## Install and run

```
pip install -r requirements.txt          # python-pptx Pillow lxml numpy scipy fonttools brotli pytest
npm i -g playwright                      # Chromium is needed; export NODE_PATH=$(npm root -g)
apt-get install -y gifsicle ffmpeg poppler-utils   # clips and PDF -> PNG only

python3 d2s.py convert <deck dir> <work dir> [--assets map.json] [--gifs dir] [--calibration calibration.json] [--picture-mode mask|shape]
```

`convert` writes `<work>/deck.pptx`, `slides.json`, `manifest.json`, `font_table.json`, and `pack/pack_NN.pptx` (picture bundles) with
`pack/list.txt`. Work dirs go in `test-decks/scratch/` (git-ignored). Test decks live in `test-decks/<name>/`.

Pictures in the deck can be `/_blob/<id>` (resolved through `--assets` map `{id: path}` relative to the map file, or `<deck>/blobs/<id>.*`),
relative paths, `http(s)` URLs or `data:` URIs. `x-icon` names resolve through `js/icons.json`. Fonts come from `deck.json` `faces`.

## Calibration (replaces the hand-measured first-line table)

```
python3 d2s.py calib-deck <deck dir> <work>                # -> <work>/calib/calib.pptx  (one slide per font, one cell per line height)
# upload calib.pptx to Drive, export PDF or fetch thumbnails -> <dir>/p1.png ... (python3 d2s.py pdf2png file.pdf <dir>)
python3 d2s.py calib-fit <work> <dir> -o calibration.json  # dy per font and line height, and the line pitch Google really used
python3 d2s.py convert ... --calibration calibration.json
```

## Agent checklist for a conversion (connector steps)

1. `d2s.py convert` as above. Note `deck.pptx` and `pack/`.
2. Drive `create_file`, `contentMimeType: application/vnd.openxmlformats-officedocument.presentationml.presentation`
   (converts to Google Slides), `parentId` = the test/output folder. Preferred: `base64Content` as a file reference
   `sha256:<hash>:<absolute path>`. **That was refused in the last session**; if it is refused, the file has to be uploaded by hand
   or inline (only dependable for files of a few KB).
3. `read_presentation` with `fields` = `gslides.READ_ELEMENTS_MASK` -> save the JSON; `gslides.ids_by_tag` gives picture object ids.
4. For each `pack_NN.pptx`: upload it, `read_presentation` with `READ_IMAGES_MASK`, `gslides.bundle_urls` -> urls (valid ~30 min), then
   `d2s.py requests <work> tags.json urls.json` and send the list in one `update_presentation` with
   `writeControl.requiredRevisionId` from a fresh read. Finish a bundle before starting the next.
5. Images: PDF export through Drive `download_file_content` (`exportMimeType: application/pdf`) + `pdf2png`, or one
   `read_slide_page_thumbnail` (LARGE) per slide saved as `pN.png`.
6. `d2s.py report <work> <dir> [--ref noimg|full] [--ignore-pictures] [--diffs <outdir>]`.
7. Name every test file `TEST deck-to-slides ...` and keep them in a Drive folder (`deck2slides-tests/{calibration,features,regression,scratch}`).

## Rule table

| # | Rule | How it was measured | Where | Status |
|---|---|---|---|---|
| 1 | 1920 px = 10 in; 1 px = 4762.5 EMU; pt = px x 0.375 | arithmetic | `config.py` | exact |
| 2 | Line spacing %: CSS line-height / the font's **own** line height (hhea ascent+descent+gap / upm) | pitch of 2-line text vs Chromium; hhea read with fontTools now equals the browser's `line-height: normal` for Bricolage 1.2, Instrument Sans 1.22, Inter 1.21, Fredoka 1.21 (checked this session) | `fonts.py`, calibration `natural` | metrics verified offline; Google pitch: carried over for those 4 fonts, calibration deck measures any other |
| 3 | First-line offset | `calib-deck` + `calib-fit`: Google minus Chromium ink top per font x line height, stored as fraction of font size | `calibrate.py` | procedure built, **not run**; legacy 4-font table available as example |
| 4 | Weights in face name ("Inter SemiBold"), only 700 uses bold flag | hand test on Inter and Bricolage | `config.WEIGHT_SUFFIX` | carried over; `weights` slide tests 100-900 |
| 5 | Google wraps to the box and sets text ~0.1% narrower: one-line/tight boxes widened by max(12 px, 4%); risky/tight multi-line get soft breaks at the browser's break points | hand tuned on the pitch deck | `config.WIDEN_*`, `extract.cjs` | carried over; `wrapping` slide |
| 6 | Text in a rounded shape is inset by 0.2929 x radius | DrawingML text rectangle of roundRect; measured | `config.ROUND_TEXT_INSET` | carried over; `corner-radius` slide |
| 7 | Glyph missing from the web font -> Arial | detected by canvas measurement, not `document.fonts.check` | `extract.cjs` | carried over |
| 8 | Letter spacing survives; PDF export draws a gap where a word changes colour in a spaced line | observed | - | carried over |
| 9 | Picture shadows need a separate rounded shape behind (inset 1 px) | real bug fixed earlier | `config.SHADOW_INSET_PX` | carried over; `picture-effects` slide |
| 10 | Pictures: rounded picture element with 1x1 placeholder, filled by `replaceImage` (CENTER_CROP for cover, CENTER_INSIDE for contain); opacity via `updateImageProperties` | **design change, untested**: relies on `replaceImage` keeping the roundRect mask | `pptx_build.add_picture_mask` | `--picture-mode shape` is the old proven path (tagged placeholder + `replaceAllShapesWithImage`) |
| 11 | GIF: < 1000 frames, settled first frame, plain rectangle (mask gives the corners), by link if over 0.85 MB | earlier session | `clips.py`, `config.GIF_*` | carried over |
| 12 | Inline SVG is rasterised to a transparent PNG | - | `extract.cjs` | carried over |

## Test decks

`test-decks/features/` (regenerate with `python3 generate.py`): 14 slides, one rule each, each sweeping values: font-size, line-height,
weights, letter-spacing, alignment, wrapping, corner-radius (to pill and circle, text inside), borders (solid/dashed/dotted, one-sided),
shadows, alpha, rotation, pictures (cover/contain, rounded), picture-effects (shadow, opacity, rotation), gif (rounded masks).
They convert and render locally. They have **not** been through Google yet.

## Why PPTX import and not the Slides API (measured)

Tested on a scratch deck through `update_presentation`: the API accepts a shadow write but stores it as `NOT_RENDERED` with zero values
(nothing is drawn); `ROUND_RECTANGLE` has a fixed radius (about 1/6 of the short side) with no way to set it; `letterSpacing` and `spacing`
text styles are rejected; there is no picture mask. Weights (`weightedFontFamily`), line spacing, alpha, outlines, dashes, rotation and
`replaceImage` do work. Anything exact therefore has to go through PPTX import (Drive upload with conversion), which keeps all of those.
The export needs a working Drive upload path (direct API call with credentials, or a connector that accepts file references); an agent pasting
base64 through a chat tool is not dependable beyond a few KB.

## Known limits

- Drive connector: upload size (~0.85 MB per file via file reference); only sees files it created; no bulk trash.
- Only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have ever been compared with Google. Do not assume other fonts; run calibration.
- Weight names for other families may not exist in Google's font list; check the `weights` slide.
- Dashed lines use Google's longer dash; inline SVG becomes pictures; GIFs over 0.85 MB must go in by a shared-folder link.
- Slides outside the 1920x1080 frame are not supported.
