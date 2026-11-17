# deck2slides

Converts a Claude **Slides-artifact deck** (`deck.json`, `deck.css`, `slides/*.html`) into a native, editable **Google Slides**
deck: text is text, cards/pills/circles are shapes, pictures are pictures, clips are GIFs. Nothing is flattened.

How: lay every slide out in headless Chromium at 1920x1080 (`js/extract.cjs`) -> write a small PowerPoint with native shapes
(`d2s/pptx_build.py`) -> Drive converts it to Google Slides on upload -> pictures are swapped in by Slides from URLs
(`d2s/gslides.py` builds the requests) -> compare Google's slide images with the browser render (`d2s/imgdiff.py`).

## Status (read this first)

Verified against Google in the last session (Inter and Bricolage Grotesque for the feature deck; Bricolage, Instrument Sans, Inter and
Fredoka for the pitch deck regression). Numbers are in "Test results" below. **Not verified:** other fonts, animated GIF playback,
GIFs over 0.85 MB (link route), inline SVG pictures, the pitch deck with its real pictures (only text and shapes were compared),
slides 1-5, 8-9, 12-14, 17-23, 25-26, 28 of the pitch deck after the final code change (they were compared on an earlier build only).

Offline regression: the pitch deck (28 slides) rebuilt with this package plus `examples/pitch-legacy-calibration.json` gives 819 shapes,
803 identical to the old build in position, size, text and line spacing.

**Known constraint:** file-reference uploads (Drive `create_file` with `base64Content = sha256:<hash>:<absolute path>`) work in some
sessions and not others; when they do not, a session that has them must do the upload. When they work, the file must sit **inside the
session's working directory** (a path outside it was refused with "either does not exist or can't be sent by reference"), and be under
about 0.85 MB. Hand-typed base64 is not dependable.

**Other measured constraints:** the Slides MCP rate-limits thumbnail reads ("Expensive read requests per minute", about 27 in a
minute); do them in batches of about 14. Thumbnail URLs are long: copy them into a file by script, not by hand (hand copies of 200-character URLs went wrong
several times; check every download is a valid PNG).

## What works, what does not (route A, plain version)

**Works and was checked against Google:** text (position, size, colour, weights 100-900, letter spacing, alignment, line height, mixed runs, links);
cards, pills, circles, ellipses and rounded boxes with text inside (radii up to 90 px checked); fills with transparency; solid, dashed and dotted borders;
box shadows; rotation; pictures with cover/contain, rounded corners and shadow; a small GIF as its first frame inside a rounded mask. Everything stays editable.

**Works with a catch:**
- Text wraps by the box width in Google. Single lines and most paragraphs are fine; a multi-line text that exactly fills a coloured box can wrap one word differently, and a single word longer than its box gets broken.
- Fonts: only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have been compared. Another font needs a calibration run first (`calib-deck`, upload, `calib-fit`) and may not have all weight names in Google.
- Pictures need a second step (upload the picture bundle, read its URLs, send `replaceImage`). They are time-limited links, about 30 minutes.
- GIFs over 0.85 MB cannot go through the connector; they need a Drive folder shared by link (manual).

**Does not work (lost in the export; the converter prints a warning for each):** gradients (linear and radial backgrounds), `clip-path` shapes, blur filters,
blend modes, double borders (drawn solid), `overflow:hidden` clipping of a child (the child shows in full), group opacity (applied per child, so overlaps look darker),
**picture opacity** (comes out fully opaque), animation and transitions (not attempted).

**Not tested, so unknown:** other fonts; GIF playback (only the first frame was seen); inline SVG (it should become a transparent picture, not run);
real pitch-deck pictures; the pitch deck slides not re-measured on the final build; tables or charts built from HTML; speaker notes; Claude's own PowerPoint exporter (route B);
re-templating into company layouts (route C).

**Not possible in this approach at all:** real placeholders and master/theme linkage (nothing in the Claude deck says which box is a title), so a layout change in Slides will not re-flow text.

## Ways of working (pick one per deck)

What each route gives you, and what was tested. "Tested" means run end to end in the last session; everything else is stated as untested.

| | Route | Result in Google Slides | Good for | Status |
|---|---|---|---|---|
| A | **Build in Claude, export with this tool** (`d2s.py convert`, upload the PPTX to Drive with conversion, swap pictures in with `replaceImage`) | Native, editable deck: text is text, cards/pills are shapes, pictures are pictures with their rounded masks, shadows kept. All slides sit on the blank layout: no placeholders, no master, no theme fonts or colours | A deck that should look like the Claude version, with no drag and drop | **Tested** on the 20-slide feature deck and (text and shapes) the 28-slide pitch deck. Limits: README rule table, rows 5, 10a, 14 |
| B | **Build in Claude, export to PowerPoint with Claude's own exporter, upload to Drive, finish in Slides** | A converted deck. Fidelity depends on that exporter, which was not tested here, so how close it is to the Claude version is unknown | Starting from a PowerPoint file you already have, or when you want PowerPoint as the intermediate copy | **Not tested** in this project. Uploading a PPTX to Drive with conversion is what route A also does, so that step works |
| C | **Route A or B, then bring it into the company layouts by hand in Slides** | Same as A or B, then you apply the template yourself (copy slides into the template deck with "keep source formatting" off, or change theme and layout) | Decks that must follow a master, theme fonts or placeholders | **Manual and not tested here.** The converter does not produce placeholders, so text will not flow into a layout's title or body boxes on its own; expect to retype or re-link titles |
| D | **Build everything in Slides by hand**, or script it through the Slides API | Full control, real layouts and masters | Decks that are mostly template and little custom design | The API route was measured and rejected for design fidelity: shadow writes are ignored (stored as `NOT_RENDERED`), `ROUND_RECTANGLE` radius is fixed at about 1/6 of the short side, `letterSpacing` is rejected, there is no picture mask and image transparency cannot be updated. It is fine for plain text, rectangles and pictures |

**Choosing.** If the look comes from Claude and the deck is one-off, use A. If the deck has to live inside an existing template, either build it in D, or use A and accept the manual re-templating in C. Do not expect A to map onto layouts automatically: the pipeline knows positions and styles, not which box is a "title".

**Mixing.** A and C combine well: export with A, then change only the slides that need template furniture (cover, section dividers, footers) and leave the rest. Changing a slide's layout in Slides does not move the exported shapes, so nothing is lost, but nothing is re-flowed either.

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
   `sha256:<hash>:<absolute path>` (worked in the last session for files under the working directory). If it is refused, a session
   that has file references must upload it (see Known constraint above).
3. `read_presentation` with `fields` = `gslides.READ_ELEMENTS_MASK` -> save the JSON; `gslides.ids_by_tag` gives picture object ids.
4. For each `pack_NN.pptx`: upload it, `read_presentation` with `READ_IMAGES_MASK`, `gslides.bundle_urls` -> urls (valid ~30 min), then
   `d2s.py requests <work> tags.json urls.json` and send the list in one `update_presentation` with
   `writeControl.requiredRevisionId` from a fresh read. Finish a bundle before starting the next.
5. Images: PDF export through Drive `download_file_content` (`exportMimeType: application/pdf`) + `pdf2png`, or one
   `read_slide_page_thumbnail` (LARGE) per slide saved as `pN.png`.
6. `d2s.py report <work> <dir> [--ref noimg|full] [--ignore-pictures] [--diffs <outdir>]`.
7. Name every test file `TEST deck-to-slides ...` and keep them in a Drive folder (`deck2slides-tests/{calibration,features,regression,scratch}`).

## Rule table

Status: **verified** = measured against Google in the last session (fonts: see Status); *carried over* = from the earlier hand
measurement, not re-measured; *failed* = tried and does not work.

| # | Rule | How it was measured | Status |
|---|---|---|---|
| 1 | 1920 px = 10 in; 1 px = 4762.5 EMU; pt = px x 0.375 | arithmetic | exact |
| 2 | Line spacing % = CSS line-height / the font's own line height (hhea). Calibration may override it per font (`natural`) | 4-line pitch on the calibration deck, 2000 px thumbnails: Bricolage 1.000 of hhea; Inter 0.9895 of hhea, stored as natural 1.1973 | **verified** for Inter, Bricolage. Instrument Sans, Fredoka: carried over |
| 3 | First-line offset (`calib-fit`): Google minus Chromium ink top, per font and line height | fit run on a fresh 4-line deck. Values come in 1-px steps (Google snaps text to whole pixels at 1600/2000 px thumbnails), so the table carries about 0.5 px noise | **verified** (procedure); legacy 4-font table kept in `examples/` |
| 4 | Weights 100-900 as face names ("Inter SemiBold"); only 700 uses the bold flag | `weights` slide: nine weights, Inter and Bricolage, widths within +-0.2% of Chromium, vertical offset 0-2 px | **verified** (these two fonts) |
| 5 | Google sets text to the same width as Chromium (ratio 1.000, worst 1.0017 over about 40 rows); boxes are widened by max(12 px, 4%) and tight multi-line text gets soft breaks | width ratios on `font-size`, `weights`, `letter-spacing` slides; `wrapping` slide | **verified** for widths. Still wrong: (a) a multi-line filled box that fits exactly wraps its last word ("here" on `wrapping`); (b) a very long word is broken by Google while Chromium overflows it |
| 5a | Text that overflows its box in the browser (nowrap, long word) widens the box by the overflow | `wrapping` slide: "nowrap text overflowing its box" now stays on one line | **verified** |
| 5b | **Failed:** `wrap="none"` in bodyPr, and negative insets, to widen text inside a filled shape: Google ignores both (slide 6 and 17 numbers identical with and without) | A/B on the `wrapping` and `text-styles` slides | failed; `WRAP_NONE_TIGHT=False`, negative insets removed |
| 6 | Text inside a rounded shape is inset by 0.2929 x radius; a true ellipse (`border-radius:50%` on a non-square box) is emitted as `ellipse` with inset 0.1464 x w/h | `corner-radius` slide: radius 0-90 text matches (max 3 px); ellipse now correct (was a stadium) | **verified** to radius 90; circle r=140 text wraps one line differently (one block 39 px off) |
| 7 | Glyph missing from the web font -> Arial | canvas measurement | carried over |
| 8 | Letter spacing -4 to +12 px is kept (`spc`); widths equal Chromium (ratio 1.000 to 1.0013 on 9 rows) | `letter-spacing` slide | **verified** |
| 9 | Picture shadow: `outerShdw` on the picture itself. Survives `replaceImage` (alpha 0.349, blur 158750 EMU read back). The old "separate rounded shape behind" is no longer needed (`PICTURE_SHADOW='shape'` keeps it) | `picture-effects` slide, read back through the API and compared visually | **verified** |
| 10 | Pictures: rounded picture element with a transparent 1x1 placeholder, filled by `replaceImage` (CENTER_CROP cover, CENTER_INSIDE contain) | `pictures` + `picture-effects`: **the roundRect mask, rotation and radii 0/40/80/150/300 are kept after `replaceImage`**; full-reference diff 0.23% on `pictures` | **verified**; `--picture-mode shape` stays as the fallback |
| 10a | **Picture opacity is not possible in mask mode:** the API says "transparency cannot be updated", and `alphaModFix` on the placeholder is dropped by `replaceImage` (import keeps it, replace removes it). The converter prints nothing for this yet | `picture-effects` slide, API read-back | failed; opacity < 1 on a picture is lost (flag `PICTURE_ALPHA` left off) |
| 11 | GIF: < 1000 frames, settled first frame, plain rectangle (mask gives the corners), by link if over 0.85 MB | `gif` slide: rounded masks and `replaceImage` work for a small GIF; first frame only, playback not checked | partly verified |
| 12 | Inline SVG is rasterised to a transparent PNG | - | carried over, untested |
| 13 | Shadows, alpha, rotation, colours, borders | slides `shadows`, `alpha`, `rotation`, `colour`: 0.00% pixel difference; `borders` 0.52% (solid/dashed/dotted drawn, not inspected one by one) | **verified** |
| 14 | **Dropped, now warned at convert time:** gradients (linear, radial), clip-path, filter blur, mix-blend-mode, double border (drawn solid), `overflow:hidden` clipping a child, group opacity (applied per child, overlaps look darker) | `unsupported` and `layering` slides: 19.5% / 3.1% pixels differ | **verified as lost**; not implemented |

## Test results (last session)

Method: `d2s.py report <work> <thumbs> --ref noimg --ignore-pictures` (2000 px Google thumbnails vs the 1920 px browser render).

**Calibration effect** (feature deck, before = no calibration, 1600 px thumbs; after = fitted calibration, 2000 px thumbs, plus the code fixes below;
the two changes are mixed, so the gain cannot be credited to calibration alone):
text blocks more than 4 px off: 28 -> 11. Mean offset per slide (px): font-size 1.40 -> 0.94, line-height 3.18 -> 1.75, weights 1.89 -> 1.28,
letter-spacing 6.11 -> 1.00, alignment 3.00 -> 0.89. Pixel difference: font-size 1.47 -> 0.28%, letter-spacing 5.56 -> 0.03%, alignment 3.43 -> 0.00%.

**Feature deck, final run (pixel diff %, text blocks >4 px off):** font-size 0.28 (0), line-height 0.28 (2), weights 0.40 (0), letter-spacing 0.03 (0),
alignment 0.00 (0), wrapping 0.51 (3), corner-radius 0.52 (1), borders 0.52 (0), shadows 0.00, alpha 0.00, rotation 0.00, pictures 0.40 (0, with pictures
0.23 vs the full render), picture-effects 0.55 (opacity lost), gif 0.24, grid 0.00 (1 block 61 px: not investigated), colour 0.00,
text-styles 1.83 (4: the mixed-size line wraps in Google), layering 3.06 (clip and group opacity), unsupported 19.50 (dropped features), composite 0.33 (0).
7 of 20 slides under 0.15%.

**Pitch deck regression** (text and shapes only; real pictures were not available): committed OLD pipeline: 27 of 28 slides under 0.15%, 8 blocks >4 px.
Committed NEW pipeline file: 23 of 28 and 30 blocks, but that was caused by its opaque grey placeholder pictures covering the slides in the Google render
(proved by looking at the render), not by text placement. After making the placeholder transparent and rebuilding with the current code, the six
slides re-measured (country, goal, journey, echo, marker-kv, toy) give the **same numbers as OLD** (offsets 5/8/2/9/1/2 px) and `toy` is 0.00% against 1.20% for OLD.
The other 22 slides were not re-measured on the final build.

Code changes made from these tests: true `ellipse` for 50% radius, widening for text that overflows its box, picture shadow on the picture, transparent placeholder,
opacity request removed, 4-line calibration deck, warnings for dropped CSS, `report` JSON fix.

## Test decks

`test-decks/features/` (regenerate with `python3 generate.py`): 20 slides, one rule each (see the rule table for what each covered).

## Why PPTX import and not the Slides API (measured)

Tested on a scratch deck through `update_presentation`: the API accepts a shadow write but stores it as `NOT_RENDERED` with zero values
(nothing is drawn); `ROUND_RECTANGLE` has a fixed radius (about 1/6 of the short side) with no way to set it; `letterSpacing` and `spacing`
text styles are rejected; there is no picture mask. Weights (`weightedFontFamily`), line spacing, alpha, outlines, dashes, rotation and
`replaceImage` do work. Anything exact therefore has to go through PPTX import (Drive upload with conversion), which keeps all of those.
The export needs a working Drive upload path (direct API call with credentials, or a connector that accepts file references); an agent pasting
base64 through a chat tool is not dependable beyond a few KB.

## Known limits

- Drive connector: upload size (~0.85 MB per file via file reference, file inside the working directory); only sees files it created; no bulk trash.
- Still manual: GIFs over 0.85 MB (shared-folder link), picture opacity, anything in rule 14.
- Only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have ever been compared with Google. Do not assume other fonts; run calibration.
- Weight names for other families may not exist in Google's font list; check the `weights` slide.
- Dashed lines use Google's longer dash; inline SVG becomes pictures; GIFs over 0.85 MB must go in by a shared-folder link.
- Slides outside the 1920x1080 frame are not supported.
