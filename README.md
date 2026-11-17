# deck2slides

Converts a Claude **Slides-artifact deck** (`deck.json`, `deck.css`, `slides/*.html`) into a native, editable **Google Slides**
deck: text is text, cards/pills/circles are shapes, pictures are pictures, clips are GIFs. Nothing is flattened.

How: lay every slide out in headless Chromium at 1920x1080 (`js/extract.cjs`) -> write a small PowerPoint with native shapes
(`d2s/pptx_build.py`) -> Drive converts it to Google Slides on upload -> pictures are swapped in by Slides from URLs
(`d2s/gslides.py` builds the requests) -> compare Google's slide images with the browser render (`d2s/imgdiff.py`).

## Status (read this first)

Verified against Google in the last session (Inter and Bricolage Grotesque for the feature deck; Bricolage, Instrument Sans, Inter and
Fredoka for the pitch deck regression). Numbers are in "Test results" below. **Not verified:** other fonts, animated GIF playback,
GIFs over the upload cap (link route), inline SVG pictures, the pitch deck with its real pictures (only text and shapes were compared),
(all 28 pitch slides were measured on the final code).

Offline regression: the pitch deck (28 slides) rebuilt with this package plus `examples/pitch-legacy-calibration.json` gives 819 shapes,
803 identical to the old build in position, size, text and line spacing.

**Known constraint:** file-reference uploads (Drive `create_file` with `base64Content = sha256:<hash>:<absolute path>`) work in some
sessions and not others; when they do not, a session that has them must do the upload. When they work, the file must sit **inside the
session's working directory** (a path outside it was refused with "either does not exist or can't be sent by reference"), and, per the experiment below, a 3.03 MB file uploaded fine and a 6 MB one was refused by the connector (4.2 MB per call); the old 0.85 MB figure was wrong. Hand-typed base64 is not dependable.

**Other measured constraints:** the Slides MCP rate-limits thumbnail reads ("Expensive read requests per minute", about 27 in a
minute); do them in batches of about 14. Thumbnail URLs are long: copy them into a file by script, not by hand (hand copies of 200-character URLs went wrong
several times; check every download is a valid PNG).

## What works, what does not (route A, plain version)

**Works and was checked against Google:** text (position, size, colour, weights 100-900, letter spacing, alignment, line height, mixed runs, links);
cards, pills, circles, ellipses and rounded boxes with text inside (radii up to 90 px checked); solid fills, **linear and radial gradients**; solid, dashed, dotted and
**double** borders; box shadows; rotation; **pictures** (embedded: cover/contain, rounded corners, shadow, **opacity**, polygon/circle/ellipse/inset clips, clipping by an
`overflow:hidden` parent); `clip-path` shapes. Everything stays editable, and picture crops are Google's own crop settings.

**Works with a catch:**
- Text wraps by the box width in Google. A multi-line text that exactly fills a coloured box can wrap one word differently, and a single word longer than its box gets broken.
- Fonts: only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have been compared. Another font needs a calibration run first and may not have all weight names.
- Pictures beyond the upload budget (about 2.7 MB of images per deck) are placeholders filled by `replaceImage` (second step, 30-minute links) and lose opacity and clip fit.
- GIFs always go through the placeholder route; over the cap they need a Drive folder shared by link (manual).

**Drawn as a picture instead of natively (warned; its text is no longer editable):** blur, and group opacity over overlapping children.

**Does not work (lost in the export; the converter prints a warning for each):** blend modes over anything but a flat colour,
`background-image` other than a single gradient, rounded `inset()` clips, animation and transitions (not attempted).

**Not tested, so unknown:** other fonts; GIF playback (only the first frame was seen); inline SVG; real pitch-deck pictures; 
gradient text, off-centre radial gradients; tables or charts built from HTML; speaker notes; Claude's own PowerPoint exporter (route B); re-templating into company layouts (route C: see 'Using a company template').

**Needs a template and tags:** real placeholders and master/theme linkage (nothing in a plain Claude deck says which box is a title): use `--template` with `data-layout` and `data-role` (see above).

## Using a company template (route A + C in one step)

```
python3 d2s.py convert <deck> <work> --template company.pptx
```

`company.pptx` is your template exported from PowerPoint or Slides (File > Download > .pptx). The build opens it instead of a blank deck, keeps its master, theme and
**all** layouts, drops its sample slides, and gives each slide the layout named in the HTML:

```html
<section id="intro" data-layout="Title Slide">
  <h1 data-role="title">Deck title</h1>
  <p data-role="subtitle">Subtitle</p>
  <div class="card">Ordinary shapes and text stay as they are</div>
</section>
```

- `data-layout` = the layout's name in the template; unknown or missing -> the template's Blank layout (warning for unknown names).
- `data-role` = `title`, `subtitle`, `body` (or `caption`, mapped to body). The text goes into the layout's placeholder of that type, so **position, font and colour come from the template**, not from the HTML. No free placeholder of that type -> an ordinary text box (warning).
- Untagged elements are drawn as usual (shapes, text, pictures); the template's background replaces the HTML's slide background.
- The template's slide size must match the deck (16:9, 10 x 5.625 in); the build warns if it does not.

**Verified** (`test-decks/template-demo`, a synthetic template made with python-pptx: custom layout name, cream master background, a bar on the layout, a title placeholder): after conversion in Google
the layout name is kept, all 11 layouts are present, the slide's layout is the named one, the master background and layout bar render, the title is a real `TITLE` placeholder bound to the layout
(`parentObjectId` set), and the card stays live text. **Not verified:** a real company template (theme fonts, several masters, footers and slide numbers, placeholders other than title), `subtitle`/`body` fill,
and what happens when the deck's text is longer than the placeholder (Google does not shrink it).

## Writing a Claude deck so it exports well (for the deck author)

Most gaps disappear if the deck is written with the export in mind:
1. One element per visual thing: card = `div` with `background`, `border-radius`, `border`, `box-shadow`; text inside the card element, not as a sibling on top (the text then stays inside its shape).
2. Prefer `linear-gradient`/`radial-gradient` (centred), `clip-path: polygon/circle/ellipse/inset`, solid or `double` borders, and `opacity` on a single element or picture: all native.
3. Avoid `filter`, `mix-blend-mode`, several background layers and `background-image: url()`; use `<img>` for pictures. Blur and overlapping group opacity become pictures (their text stops being editable).
4. Give single-line labels room: a few pixels of free width, or `white-space: nowrap`; text that exactly fills a coloured box may wrap one word differently in Google.
5. Keep to one font family list per deck from the calibrated set (Inter, Bricolage Grotesque, Instrument Sans, Fredoka) or run `calib-deck` for new ones.
6. With a company template: tag titles, subtitles and body text with `data-role`, set `data-layout` on each slide, and keep decorative shapes untagged.
7. Total picture weight: about 2.7 MB of images fits in the uploaded file; beyond that pictures fall back to the second step (no opacity or clip fit), GIFs always do.

## The five-page test piece (same deck in three apps)

`test-decks/five-page/` is a complete deck **in the real Claude Slides format** (deck.json v5 with `format`, shared `deck.css`, one `<section>` per slide, `h1`/`p` text, nothing under 24 px, uploaded `/_blob/` images; it was
published unchanged as a private Slides artifact and accepted without refusals). Title page, grid and principles, image and text split, type and colour system, closing page.
Its system: 1920 x 1080, **12 columns of 124 px, 16 px gutters, 128 px margins** (140 px per column step, which divides the 1664 px content width exactly), 8 px baseline; Bricolage Grotesque for display and headings,
Inter for text, scale 144 / 96 / 56 / 40 / 32 / 24 px; public-domain NASA pictures from Wikimedia Commons (credits in `assets/CREDITS.md`); native gradients, rounded and circular picture masks, shadows.
Every coordinate comes from the grid constants in `generate.py`. (A first version used a 120 px margin, text under 24 px and relative image paths; it was replaced because it was not in the format.)

```
python3 test-decks/five-page/generate.py
python3 d2s.py convert test-decks/five-page <work> --assets test-decks/five-page/assets-map.json --calibration <calibration.json>
# upload deck.pptx to Drive (converts to Google Slides), export it as PDF (download_file_content, application/pdf), pdftoppm, compare with <work>/full_NN.png
```

Result (`examples/five-page/compare.png`; the PPTX and both PDFs are in `examples/five-page/`): pixel difference **browser vs Google Slides 1.06 / 0.72 / 0.07 / 0.59 / 0.26 %** for slides 1-5, the same files rendered by LibreOffice 1.02 / 0.78 / 1.63 / 1.26 / 0.94 %.
To the eye the three columns are identical, and the 12-column grid is exact: the three cards measure x 128-672, 688-1232 and 1248-1792 (columns 1-4, 5-8, 9-12). Limits of this test:
- The first column is **the published deck files rendered in headless Chromium (this repo's extractor), not the live Claude Slides viewer**: the viewer is a private page and cannot be screenshotted from here. The type's own preview recipe is also only an approximation.
- The third column is **LibreOffice, not PowerPoint**. **To close that gap, open `examples/five-page/five-page.pptx` in PowerPoint** (install Inter and Bricolage Grotesque first; fonts are not embedded) and open the deck in Claude Slides.
- A comment left on the artifact ("card escaping its grid column") was a real bug in this deck (card padding was added to the pinned width); fixed with `box-sizing:border-box`.

## The other direction (Google Slides to PowerPoint or Claude Slides)

**Google Slides to PowerPoint: tested (round trip of the five-page piece and of the template demo).** Export with the Drive connector: `download_file_content` with `exportMimeType`
`application/vnd.openxmlformats-officedocument.presentationml.presentation`; the connector saves the .pptx to a file (no base64 pasting), or File > Download > Microsoft PowerPoint (.pptx) by hand.
Measured on the file Google wrote back (2.9 MB for the five-page piece):
- 5 slides, same shape counts per slide (94 shapes and pictures), **geometry identical to the uploaded PPTX: 0 EMU difference on all 94**.
- Gradients (`gradFill`), the circular clip (`custGeom`), rounded rectangles, drop shadows (`outerShdw`), picture crops (`srcRect`) and the three images (same file sizes) all came back; the font face names ("Inter SemiBold", "Bricolage Grotesque ExtraBold") are unchanged; fonts are not embedded.
- Small changes: `Calibri` on empty end-of-paragraph marks (30 of them), an empty `alphaModFix` on pictures, borders written as `cmpd="sng"`.
- Rendered with LibreOffice, the exported file differs from the render of the file we uploaded by **0.00% on all five slides**.
- Template demo: the 11 layouts, the title placeholder (still `type="title"`, still bound to the first layout) and the master background colour came back; the custom layout name was replaced by Google's own type name (`TITLE_ONLY`).
- **Not tested:** how PowerPoint itself opens that file (no PowerPoint here; LibreOffice and XML checks only), and edits made inside Google Slides before exporting.

**PowerPoint to Google Slides:** upload with conversion (what this tool does).

**Google Slides or PowerPoint to Claude Slides:** no converter exists. A Claude Slides deck is HTML (`deck.json`, `deck.css`, `slides/*.html`). A `slides2html` could read a PPTX (python-pptx, already used here; the round trip above shows Google's PPTX
keeps exact geometry, fills, crops and fonts) or the Slides API JSON and write absolutely positioned elements. That would be mostly mechanical for text, shapes and pictures and would give positioned boxes, not a semantic layout (no CSS grid or flow). Feasible, not started.

## Guides and grids

- **The grid is geometry, not metadata.** In the Claude deck the 12-column grid is just where things sit. The export keeps positions to well under a pixel (rule 1, `five-page`), so a grid-aligned deck stays grid-aligned in Google Slides and PowerPoint. The five-page deck also draws its columns as ordinary shapes on slide 2 so the grid is visible.
- **Guides (the draggable lines) are not carried over.** HTML has no guides; the Slides API does not expose them; PowerPoint stores them as a file extension (`p15:sldGuideLst`, per slide or in the master). This tool writes none. Writing them blind was left out on purpose: a malformed extension can make PowerPoint ask to repair the file, and neither app was available to check one. If you want them, the safe route is to put guides into the **company template's master** (see 'Using a company template'), where they are then inherited by every slide.
- **Layout grids in a template** (columns, margins) work the same way: they live in the master and layouts, which the template route keeps intact.

## What the Claude Slides format actually is (read from the Slides artifact type's own instructions)

It is a **specific, versioned dialect of HTML, not generic HTML, and not an open standard** (it belongs to Claude's Slides artifact type; no W3C/ECMA spec). Facts from the type's `SKILL.md`:
- Files: `project/deck.json` (index: `v:5`, `order`, `sections`, `faces` (at most 4 Google Fonts or uploaded faces), `format`, optional `size:"4:3"` = 1440 x 1080), `project/deck.css` (shared rules and `--variables`, no `@import`), and **one file per slide `project/slides/<id>.html` containing exactly one `<section id="<id>">`**, no `html`, `head`, `style`, `link` or `body`. Speaker notes are one `<aside>` as the section's last child.
- Canvas: fixed 1920 x 1080 px, `padding:128px` margins; children flow (flex, grid, column), `position:absolute` pins a child.
- Element set: `h1-h3`, `p` (font-size not under 24 px), `ul/ol/li`, `br`, `b i u a span`, `div`, `img` (width and height set), `table/tr/th/td`, `svg` (52 KB max), `hr`, `x-shape` (kinds rect, rounded, ellipse, diamond, arrows, line), `x-icon`, `x-connector`, pinned `x-embed` (sandboxed live page).
- Limits: at most 200 elements per slide; a `div` with more than 24 absolutely positioned children disappears; images must be `/_blob/<id>` (uploaded) or a design-system path, never a relative path, `data:` or http(s) URL.
- Motion: CSS `@keyframes`, `fragment` click steps, `data-transition`.
- The viewer ships its own exporter (`export.js` in its file list); how its PPTX compares with this tool's was **not tested**.

**Consequences for this project:** (1) the extractor reads computed layout, so flow layouts, flex and grid in real Claude decks are handled; the 28-slide pitch deck is a real Claude deck and converts with no warnings. (2) **`test-decks/features` and `test-decks/five-page` are not strictly in this format** (relative image paths, text in `div`s instead of `h1`/`p`, captions under 24 px, no `format` key, more than 24 absolute children in some containers). (3) So the "Claude Slides" column in `examples/five-page/compare.png` is **this repo's headless Chromium rendering that HTML, not the real Claude Slides viewer**. (4) Not yet tested through the extractor: `table`, `ul/ol` bullets, `x-connector`, `x-shape` kinds other than ellipse, `x-embed`, `fragment` steps. A reverse converter (Slides/PowerPoint to Claude Slides) has to emit this dialect, including uploading images and staying inside the element and count limits.

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
pip install -r requirements.txt          # python-pptx Pillow lxml numpy scipy fonttools brotli pytest shapely
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
| 10 | **Pictures are embedded in the uploaded PPTX** (`--picture-mode auto`, default): downscaled to 1.5x their size, native crop (`srcRect` -> Google crop offsets), rounded/clip mask, shadow, opacity. What does not fit the budget (about 2.7 MB of pictures; GIFs) stays a transparent 1x1 placeholder filled by `replaceImage` (CENTER_CROP cover, CENTER_INSIDE contain) | `pictures` 0.00% and `picture-effects` 0.00% against the full browser render. The roundRect mask, rotation and radii also survive `replaceImage` (checked before embedding existed) | **verified** |
| 10a | Picture opacity: **works for embedded pictures** (`alphaModFix`, read back as `transparency: 0.5`). **Lost for placeholder pictures** that go through `replaceImage` (the API says "transparency cannot be updated", and replace drops it). The builder embeds opacity pictures first | `picture-effects`: 7.09% -> 0.00% | **verified**; placeholder pictures with opacity still lose it |
| 10b | A clipped picture (polygon, circle, overflow clip): Google fits the image to the **bounding box of the clip path**, so the frame is set to that box and the matching part of the image is cropped natively. Contain pictures are not rounded unless the element's own corners reach them | `native-effects` 0.00% (it was 1.9% before the bounding-box fix; the picture was 30% too small) | **verified** |
| 11 | GIF: < 1000 frames, settled first frame, plain rectangle (mask gives the corners), by link if over the upload cap (about 3 MB) | `gif` slide: rounded masks and `replaceImage` work for a small GIF; first frame only, playback not checked | partly verified |
| 12 | Inline SVG is rasterised to a transparent PNG | - | carried over, untested |
| 13 | Shadows, alpha, rotation, colours, borders | slides `shadows`, `alpha`, `rotation`, `colour`: 0.00% pixel difference; `borders` 0.52% (solid/dashed/dotted drawn, not inspected one by one) | **verified** |
| 14 | **Now native (verified):** linear and radial gradients (angle, keywords, px and % stops, alpha stops; radial assumes the centre), `clip-path` polygon / circle / ellipse / inset (square corners), `overflow:hidden` clipping of shapes and pictures (curves become polygons with 32 points per quarter circle, about 0.1 px), double border (`cmpd=dbl`), 50% radius as a true ellipse. **Drawn as a picture (raster island), warned at convert time:** `filter: blur()` and group opacity over overlapping children - the element and its children are rendered alone to a transparent PNG at 2x and embedded, so any text inside them stops being editable. **Still lost, warned:** blend modes (the probe happened to match because it multiplied over a flat colour), `background-image` that is not a single gradient, `inset(... round ...)` (drawn square), radial-gradient positions other than the centre | `unsupported` 19.5% -> 0.00%; `layering` 3.1% -> 0.00%; `native-effects` 0.00% | **verified** |
| 15 | Upload size: a 3.03 MB PPTX uploads; a 6 MB one is refused by the connector (4.2 MB per call, about 3.1 MB for files). The old 0.85 MB figure was wrong | cap tests | **verified** |
| 16 | Text with `line-height` above 2.0 whose box is one line high (the "line-height = box height" centring idiom) is centred as one natural line (`anchor=middle`); other first-line offsets are extrapolated at slope -0.5 per unit line height up to 2.0 | `line-height` slide 0.28% -> 0.00%; the pill probe's text lined up | **verified** to 2.0 |
| 17 | `<img>` with a background colour gets a shape behind it (`contain` letterboxes) | `pictures` | **verified** |

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

**Pitch deck regression** (final code, text and shapes; the real pictures were not available, so 189 dummy grey pictures were embedded and masked out of the comparison; all 28 slides, 2000 px thumbnails):
committed OLD pipeline 27 of 28 slides under 0.15% (worst `toy` 1.20%, pixel difference summed over the deck 1.39), 0 text blocks more than 4 px off; **current code 27 of 28 under 0.15% (worst `toy-cast` 0.28%, sum 0.52), 0 text blocks more than 4 px off**.
Along the way: an earlier "30 blocks off" for the committed NEW file was an artifact (its opaque grey placeholder pictures covered the slides; proved by looking at the render, fixed by making the placeholder transparent),
and a later scare (18 blocks off) was the text-offset measurement not masking embedded dummy pictures (fixed in `imgdiff.text_offsets`; the PPTX text properties were identical). The real deck produces **no warnings**: it uses none of the unsupported CSS.

Code changes made from these tests: true `ellipse` for 50% radius, widening for text that overflows its box, picture shadow on the picture, transparent placeholder,
opacity request removed, 4-line calibration deck, warnings for dropped CSS, `report` JSON fix.

**Second round (feature deck, 21 slides, final build, pixel diff % against the full browser render, text blocks >4 px):**
font-size 0.28 (0), line-height 0.00 (0), weights 0.40 (0), letter-spacing 0.03 (0), alignment 0.00 (0), wrapping 0.51 (3), corner-radius 0.52 (1), borders 0.52 (0),
shadows 0.00, alpha 0.00, rotation 0.00, **pictures 0.00**, **picture-effects 0.00**, gif 31.4 (placeholders not swapped in this run, expected), grid 0.00 (1: 61 px, not investigated),
colour 0.00, text-styles 1.83 (4), layering 1.41 (group opacity), **unsupported 0.91** (blur and blend), **native-effects 0.00**, composite 0.17. 11 of 21 under 0.15%.
Then the raster islands were added and `layering` and `unsupported` re-measured alone: both 0.00% (the other 19 slides were not re-run on that build).
Compare the first round: pictures 0.23, picture-effects 7.09 (opacity), layering 3.06, unsupported 19.50.

## Test decks

`test-decks/features/` (regenerate with `python3 generate.py`): 21 slides (adds `native-effects`), one rule each (see the rule table for what each covered).

## Why PPTX import and not the Slides API (measured)

Tested on a scratch deck through `update_presentation`: the API accepts a shadow write but stores it as `NOT_RENDERED` with zero values
(nothing is drawn); `ROUND_RECTANGLE` has a fixed radius (about 1/6 of the short side) with no way to set it; `letterSpacing` and `spacing`
text styles are rejected; there is no picture mask. Weights (`weightedFontFamily`), line spacing, alpha, outlines, dashes, rotation and
`replaceImage` do work. Anything exact therefore has to go through PPTX import (Drive upload with conversion), which keeps all of those.
The export needs a working Drive upload path (direct API call with credentials, or a connector that accepts file references); an agent pasting
base64 through a chat tool is not dependable beyond a few KB.

## Known limits

- Drive connector: upload size (about 3.1 MB of files per call, file inside the working directory); only sees files it created; no bulk trash.
- Still manual: GIFs over the cap (shared-folder link), opacity on placeholder pictures, blur, blend modes, group opacity.
- Only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have ever been compared with Google. Do not assume other fonts; run calibration.
- Weight names for other families may not exist in Google's font list; check the `weights` slide.
- Dashed lines use Google's longer dash; inline SVG becomes pictures; GIFs over the cap must go in by a shared-folder link.
- Slides outside the 1920x1080 frame are not supported.
