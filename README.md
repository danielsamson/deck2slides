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
session's working directory** (a path outside it was refused with "either does not exist or can't be sent by reference"), and, per the experiment below, a 3.03 MB file uploaded fine and a 6 MB one was refused by the connector (4.2 MB per call); the old 0.85 MB figure was a root-upload artefact (see next paragraph). Hand-typed base64 is not dependable.

**Root vs folder uploads (measured again, 18 Nov, TOAST deck):** the 0.85 MB cap that shows up in some sessions is not a size cap. A Drive `create_file` **without a `parentId`** (My Drive root) refused every file over about 0.7 MB with `Requested entity was not found` (700 KB uploaded, 1 MB and 2 MB did not, same directory, same file-reference form). The same 2.6 MB deck uploaded and converted at once with `parentId` set to a scratch **folder**. So: always pass `parentId` of a folder (create one with `create_file`, `mimeType application/vnd.google-apps.folder`, if there is none). The real ceiling is the connector's 4.2 MB per call (about 3.1 MB of files). Do not shrink pictures or split into many small bundles to dodge a limit that was never there: that cost this session about 16 bundles and 200 hand-copied image requests for a deck that fits in one upload and 5 bundles.

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

**Google Slides or PowerPoint to Claude Slides: `d2s.py pptx2claude` (tier 1, built and tested).** Does Claude already import PowerPoint? Searching the Slides artifact type's own code and references (read-worker, export, app, SKILL.md and the reference pages) found a PowerPoint **export** (its Download menu) and **no PowerPoint import**; the only `presentationml` mention is a list of file types accepted as attachments. Whether claude.ai offers an importer elsewhere could not be checked from here.

```
python3 d2s.py pptx2claude deck.pptx <outdir> [--calibration calibration.json]
# writes deck.json (v5, format), deck.css (shared classes), slides/s1.html ..., assets/ (images) and assets-map.json, convert-report.json (warnings)
# upload assets/* to the Slides artifact, replace the /_blob/<sha> ids with the returned ones (blobs list: convert-report.json), publish under project/
```

What it does: everything is pinned on the 1920 x 1080 canvas (a PPTX only knows positions): text becomes `<p>` classes in a flex `<div>` (painted when the shape is), ellipses `<x-shape kind="ellipse">`, lines `<x-connector>`,
pictures `<img>` with object-fit/`data-crop`, radius (capped at 256), box-shadow and opacity, freeform shapes an inline `<svg>`, a full-slide backdrop becomes the section background, gradients/dashes/double borders map back to CSS, repeated text styles become shared classes, notes become `<aside>`.
It undoes what the exporter does (first-line shift, rounded-text inset, stroke inset), so a deck this tool exported comes back at its original CSS positions. Anything the format cannot hold is a warning (custom clip on a picture, mixed faces inside a paragraph, elliptical mask over 512 px, radius over 256, over 200 elements, over 4 families).

Measured (`examples/five-page/round-trip.png`; the converted deck is in `examples/five-page/from-google/`): the five-page deck exported **from Google Slides** as PPTX, converted, and rendered again against the original render: **0.00% pixel difference on all five slides**, text boxes identical to the pixel (dx 0, dy 0).
The type's own reader reads the five generated slides with **0 drops, 0 unsupported, 0 warnings, 0 refused**. A harder input (the Google export of the first, non-conforming version) converts with the one expected warning (circular clip on a picture).
**Not tested / not covered:** decks not made by this tool (placeholders and inherited text styles from layouts and masters, tables, charts, SmartArt, WordArt, grouped shapes with rotation, bullets and numbering, autofit), images over the format's limits, the generated deck opened in the live viewer or published with real uploaded asset ids (the closed loop used the original image ids), and PowerPoint-authored files in general (only Google and this tool's PPTX were used). The output is positioned boxes, not a semantic layout.

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

**Measured with the type's own reader (`read-worker.js`, run headless on test slides):** a picture's `border-radius` is stored clamped to 256 whatever you write (`420px`, `412px`, `50%` all become 256). So a square picture is a true circle only up to 512 px (radius = half the side); at 700 or 824 px square it is stored as a rounded square (radius 256). `<x-shape kind="ellipse">` keeps its exact size and shape but holds no picture. The type's own PPTX exporter writes an ellipse mask only when the picture is square and the radius reaches half the side, so it cannot export a bigger circular crop either. Larger circular photos have no native route in this format.

**Circle photo options, tested end to end** (`test-decks/circle-test`, sheet `examples/five-page/circle-options.png`): (1) a 512 px square picture with radius 256 and (2) the same picture centred on an 824 px `<x-shape kind="ellipse">`, either as a filled disc or as an outline ring (`border:12px solid`). The type's reader accepts all three and stores the ellipse at full size; the exporter writes true `ellipse` geometry for the picture mask and for the shapes; Google Slides matches the browser render at **0.43%** pixel difference on each, LibreOffice at 0.58-0.60%. Both options work; the photo stays a native, adjustable picture, only the surround is a separate shape.

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

## Patching a deck after export: where the diff is decides how it is fixed

The Claude deck is the source. The Google deck is a copy, and it stops being a copy the moment anyone edits it. Read `d2s.py report` (per slide) and `d2s.py fit-text` (per text block) and sort every difference into one of these:

| Where the diff is | What it means | Fix | Re-export? |
| --- | --- | --- | --- |
| The same font, size or word is off on many slides (display type high, outline words stretched) | A calibration gap | Calibrate: `calib-deck` / `calib-fit` for text, `wordart_cal.py gen/fit` for outline words; commit `calibration.json` / `d2s/wordart_cal.json` | Yes, **only if the Google deck has not been edited** |
| A few blocks on a few slides are off by more than 4 px | Per-block error | `fit-text` writes `corrections.json`; `convert --corrections` applies it | Yes, same condition |
| The Google deck has been edited by a person | Re-export would overwrite their work | **Patch in place.** Read the live deck (`read_presentation`, fields `slides.objectId,slides.pageElements(objectId,size,transform)`), run `d2s.py patch <work> live.json corrections.json`, send the printed requests with `update_presentation`. Blocks that match zero or several elements are skipped and listed, never guessed | No |
| Pictures wrong or missing | Bundle or placeholder problem | `replaceImage` on the tagged elements (skill, step 6) | No |
| Shadows, letter-spacing, masks, blur, transitions, animation | The Slides API cannot set them | Do not patch. Change the source design if it matters, otherwise list it for the user | No |

Rules: (1) before hand-off, fix systematic gaps at the source and re-export; (2) after hand-off, never re-export over the user's deck: patch, or export to a new deck and say so; (3) patch only what the tool can match unambiguously; (4) after any patch or re-export, run `report` again and give the numbers; (5) write the new calibration or corrections back into the repo so the next deck starts better.

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

The same steps, with the traps, are in `.claude/skills/export-to-google-slides/SKILL.md` (a skill for agents using the Drive and Slides MCP connectors). Read it before the first upload.


1. `d2s.py convert` as above. Note `deck.pptx` and `pack/`.
2. Drive `create_file`, `contentMimeType: application/vnd.openxmlformats-officedocument.presentationml.presentation`
   (converts to Google Slides), `parentId` = **a Drive folder, always** (without one, files over ~0.7 MB fail with `Requested entity was not found`; see "Root vs folder uploads" above). Preferred: `base64Content` as a file reference
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
| 15 | Upload size: a 3.03 MB PPTX uploads; a 6 MB one is refused by the connector (4.2 MB per call, about 3.1 MB for files). The old 0.85 MB figure was an upload to My Drive root without a `parentId`, not a size cap | cap tests | **verified** |
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

- Drive connector: upload size (about 3.1 MB of files per call, file inside the working directory, **`parentId` must be a folder**: root uploads fail above ~0.7 MB); only sees files it created; no bulk trash.
- Still manual: GIFs over the cap (shared-folder link), opacity on placeholder pictures, blur, blend modes, group opacity.
- Only Inter, Bricolage Grotesque, Instrument Sans and Fredoka have ever been compared with Google. Do not assume other fonts; run calibration.
- Weight names for other families may not exist in Google's font list; check the `weights` slide.
- Dashed lines use Google's longer dash; inline SVG becomes pictures; GIFs over the cap must go in by a shared-folder link.
- Slides outside the 1920x1080 frame are not supported.

## Deriving a design system from an existing deck (`d2s.py tokens`)

```
python d2s.py tokens deck.pptx out/                      # PPTX
python d2s.py tokens slides.json out/ --masters m.json   # Google Slides presentations.get JSON
```

Writes `measured.json` (evidence), `tokens.json` (Claude's Design System artifact shape), `README.md` (its brand-book start), `tokens.dtcg.json` (W3C Design Tokens format, for Style Dictionary / Figma tooling), `tokens.flat.json` (internal flat form), `tokens.css` (`:root` variables for a Claude Slides `deck.css`) and `DESIGN.md`.

Claude's Design System type does **not** read DTCG: it needs lists (`{"tokens":[{name,value,usage}]}`), `color.themes`, and `type.{fonts,families,groups[].styles}`. A DTCG map shows as empty. `tokens.json` follows the list shape and is checked by `tokens.validate_claude_ds`, a local mirror of the grammar in the type's `format.md`. Not verified: how the page itself renders it (its cards are generated in the browser). Added with `--build` (also `--extra` for Slides JSON carrying weights, line spacing and shadows): a full `system/project/` tree for the Design System type: line heights and weights per style, measured shadows, `on-` colours with WCAG contrast notes, real font files fetched from Google Fonts (latin subset), a component for each recurring filled shape (Card, Pill), usage-rule README, and the Cover per the type's brief. Previews rendered locally in Chromium against a stand-in tokens.css (`examples/tokens/covers.png`); the page's own render is unchecked. Components are geometry only (no content), found by recurrence, so a deck with no repeated shape gets none. Slides input needs `slides_extra.json` (field-masked `presentations.get`) for weights, line spacing and shadows; without it they are left out.

Derived: colour roles (ink, mute, paper, surface, accents; translucent fills ignored), type families and size ladder, grid (columns, gutter, margins), spacing unit, radii, strokes, layouts and placeholders.

| Check | Result |
| --- | --- |
| Five-page deck (known truth) | palette, 12 col / 16 gutter / 124 col / 128 margins, 144/96/56 type exact. The grid comes from its drawn guide stripes. |
| Same deck, stripes removed | 12 columns and 128 margin right; gutter wrong (measured 4, truth 16). Treat blind gutters as an estimate. |
| public deck A template (Slides API JSON) | palette, Google Sans/Roboto ladder, 65 px margins read from layout placeholders. Its content does not sit on a column grid (7% hit), and the report says so. |

Not derived yet: shadows from the Slides API (it returns a stub on every shape), custGeom radii, weights from Slides (`weightedFontFamily` not mapped), mapping slides back to layouts. Google Slides input needs the connector JSON saved to disk.

## Applying a derived system ((local, not committed))

`generate.py` builds a fictional three-slide deck (Trend Pulse) in the Claude Slides format from the public deck A system's `tokens.json`: every colour, radius, shadow, margin, gutter and column count reaches the slides as a CSS variable, and the script only chooses layout. (local, not committed) shows it; `trend-pulse.pptx` is the same deck through the normal export (`d2s.py convert`). Observations: the system's body size (22.5 px) is under the format's 24 px text floor, so body copy uses `h3` (29.5 px); the derived 6-column grid is a low-confidence fit, so columns are recomputed to fill the margins using the system's gutter. Not checked: the PPTX in Google Slides (Google Sans and Roboto are not in the calibration set, so text offsets use the extrapolated values), and the deck in the live Claude Slides viewer.

### Second deck: public deck B (150 slides, Google Slides JSON)

(local, not committed) and (local, not committed). Running a second, very different deck (half dark slides, one accent colour, photo backgrounds) exposed bugs in the first run, all fixed and covered by the earlier tests:

- **Text colours were all read as black.** Slides API text colours sit inside `foregroundColor.opaqueColor`; the first run only read the plain form, so public deck A's ink and mute were wrong. Fixed.
- **One paper colour for a two-tone deck.** The deck is black and white slides, so the system now gets one colour theme per common background (here `dark` and `light`), with paper and ink per theme, and contrast checked in each. Per-slide backgrounds need one more field-masked read (`--bg slides_bg.json`); picture backgrounds are counted, not coloured.
- **False grid.** Wide photos and bars were read as drawn guide stripes (25 columns, negative gutter). Stripes now need a plausible, non-overlapping, on-canvas layout. Result: 12 columns, 38 px gutter, 86 px margins, 36% of edges on it.
- **Template margins from unused layouts.** The deck's layouts are Google's defaults and no slide uses them; margins from a layout now count only if at least 20% of slides use it.
- **On-accent colours** are chosen from the palette's own ink/paper values (black on the gold, 8.1:1) instead of ink of the first theme.
- **Type names** keep the largest sizes (a 240 px title was dropped); display and body keys stay correct when one family does both; system fonts (Arial) are not fetched.
- **Applied deck** is theme-aware and grid-agnostic (six blocks across the inner width, the system's gutter), so one script serves both systems.

Still open: the public deck B contrast note (mute 4.5:1) is borderline and kept exact; the Card component found there is a small 111x42 px shape, not a real card.

### Third deck, confidence scores, and Slides JSON straight to Claude Slides

- **Third deck** (public deck C, 161 slides): (local, not committed), (local, not committed). Its display face (Helvetica Neue) is not an open Google font, so it is reported and not bundled; fonts served from a proxied kit URL are never bundled because their licence cannot be checked. Reversed text (light text on photos or dark slides) is no longer called "mute"; a mute colour must reach 3:1 on paper.
- **Confidence per token set** (`derive_confidence`, in `DESIGN.md` and `build-report.json`): grid low/medium/high from how many recurring edges land on it (public deck C: low, 26%), colour from how many slides have photo backgrounds, type from character coverage, spacing from the unit's hit rate. A low-confidence grid adds a caution line to the system README, and the applied-deck generator falls back to the spacing scale when a measured gutter is about zero.
- **`d2s/gslides2claude.py`**: converts the Slides API JSON of a slide directly to a Claude Slides section, with no PPTX. Measured on four public deck B slides against Google's own thumbnails: agenda 1.4%, timeline 1.7%, text-and-rules slide 3.8% of pixels differ (the title slide cannot be compared: its pictures are unreachable from here). Findings: Google omits zero values, so a missing `scaleX` is 0, not 1; text box insets are not in the API (8 px / 6 px fit these slides best, calibrated on three slides only); mixed font sizes in one paragraph must become separate blocks because the format keeps only colour, bold, italic and underline inside a line; rounded-rectangle radius and image crops are not in the API. Output: (local, not committed).

### Structural component and layout extraction (`d2s/components.py`)

Runs on the **full** Slides JSON (`--full slides_full.json`, from `presentations.get` with the slides' `pageElements` unmasked; about 2.5 MB for a 150-slide deck, saved to disk by the connector). It replaces the earlier "any filled shape that repeats" guess.

1. Flatten each slide, resolving groups (Google omits zero values: a missing `scaleX` is 0).
2. Master chrome: an element identical (place and text) on at least 25% of slides is left out.
3. Cluster what remains: a filled or outlined container with what sits inside it, then proximity blocks (elements within 40 px) for the rest. A cluster covering 80% of the slide is the slide body, not a component.
4. Signature per cluster: the multiset of member roles (kind, size class, weight, colour or fill) and each member's position relative to the cluster. Clusters with the same roles, similar size and similar relative layout are one component; one that recurs on at least two slides, or four times, is kept.
5. Name from structure (Stat, Name and role, Heading and text, Avatar, Swatch, Card, Pill, Titled block...), slots from text that varies between instances (named title, body or caption by size), fixed text stays fixed.
6. Preview from the first instance through `gslides2claude`, colours turned into token variables where a token matches. Output: `components/<Name>/preview.html` and `README.md`, a `Layouts.md` section (slides grouped by background, pictures, headline size, text blocks and components), and `components.json`, `components-sheet.html` for judging by eye.

Result on public deck B (150 slides): 7 components (Stat x2, Heading and text x2, Name and role, Avatar, Swatch) from 141 clusters, 48 of which grouped; 14 layout groups of at least three slides. Limits seen: it finds small recurring blocks well and does not find larger composites (a timeline row with its bar and legend differs too much between instances); a component that recurs on only one slide is listed as such; instance order inside a cluster is by position, so a reordered variant becomes a separate component; images are placeholders (unreachable here); the Slides API gives no group semantics beyond `elementGroup`, so designer-made groups are flattened, not respected. Not done: using Slides *layouts* (the template's placeholders) as component evidence, and a similarity threshold learned from data.

### Layout catalogue: derive, propose, verify (`d2s/layouts.py`, `--catalogue`)

The split agreed after the component work: derive the structure, fill in the meaning, then check the result against the deck.

1. **Derive.** Slides are grouped by what they contain; each group's exemplar is its medoid slide, turned into a recipe of slots (role, size, colour, position).
2. **Propose.** (local, not committed) holds names, usage lines and merges written by Claude from looking at the exemplars. Its slide lists are copied from the derived groups, not typed (an earlier draft had hand-typed numbers that were wrong; the verifier exposed it).
3. **Verify.** Each proposal is scored against its slides (share of recipe slots found, position tolerance 7% of the canvas), against slides it should not match (false positives), and split into sub-families that really agree; a layout is **verified** only if at least 75% of the slides it claims sit in agreeing families of three or more. A family of two is a pair, not evidence.

public deck B result (12 proposed layouts): verified Section title (12/12 slides), Contents list (9/9), Statement (13/13, but weak: its recipe also matches 8 to 11 slides outside it, so it describes a sparse slide more than a layout); partly verified Lettered item (12 of 26), Phase columns (3 of 7); pairs only for Photo with caption, Table, Quote and Process step; unverified Big number, Locations, Checklist (their claimed slides differ too much in geometry). A strict direct clustering of all 150 slides at 0.85 agreement finds only 5 families covering 42 slides, so most of this deck's layouts are variations rather than repeats.

A layout is a whole-slide template, not a component, and is kept apart: each gets a showcase-page preview (`@dsCard ... page`, group "Layouts", so it is not a bundle component, and no README beside it) and a section in `Layouts.md` with status, provenance, variants, outliers, slots and the components it uses. `layout-catalogue-verified.json` keeps the scores. Finding: most public deck B layouts use none of the 7 extracted components, because those are content blocks (stat, name and role); what layouts are really made of are single-element pieces (section label, page marker, hairline or progress rule, logo, tick and cross), which the component finder skips because it needs two members. Deriving those atoms and expressing layouts as compositions of them is the next step.

### Atoms and layouts as compositions

Whole slides are not components, and the pairs of text boxes found earlier are content, not what slides are built from. Slides are built from **atoms**: single elements used in the same style and place on many slides (the gold section label top-left, the logo, a marker, a hairline rule, a headline style, a full-bleed picture).

- `components.find_atoms`: elements are keyed by style only (text: size class, weight, colour; line: weight, colour, direction; picture and box: size class), then their placements are counted. A text style that moves around is only a type style (already a token) and is dropped; one placed in the same spot at least half the time is an atom. An atom needs at least four slides. Rules, pictures and shapes are kept whatever their placement.
- public deck B: 24 atoms (Eyebrow 100 uses on 98 slides, 98% in the same place; Logo 23; Marker; Display headline; Hairline rules; Short rules; Vertical rules; Full-bleed picture) next to the 7 content blocks, which now sit in a separate "Content blocks" group.
- `components.composition`: each layout exemplar is expressed as the atoms it uses (and whether each sits in its usual place) plus free content (everything else, with role and position). `Layouts.md` shows, per layout, the composition, how many elements are atoms, and "same atoms" (the share of member slides whose atom set matches the exemplar's); the previews stay showcase pages.
- Limits: atom names come from rules about size, colour and position (Eyebrow, Footnote, Marker...), so a second atom in the same role is numbered ("Display figure 2") and told apart by style in its README; table-heavy slides produce many small-text atoms of little value; full-bleed pictures and backdrops are atoms with unreachable pictures; a layout's free content is not yet typed into slots with fixed positions, so a layout is described, not generated.

### Review of the components, one at a time

The first atom and block lists were mostly noise (24 atoms and 7 blocks, many duplicates, backgrounds and type slots). Each of the 31 items was looked at against its exemplar slide with the element outlined ((local, not committed), `-2.png`) and judged. Result, recorded in `components-curation.json`:

- **Kept (8):** Eyebrow, Logo, Marker, Rule (merging hairline and short rules), Side picture, Stat, Label and value, Heading and text.
- **Dropped:** full-bleed pictures (slide backgrounds), the large display headline, figure and title slots (type styles and layout slots), paragraph text that moves around, vertical rules (chart gridlines and bars), the panel shape (part of the progress rule).
- **Merged:** Avatar, Name and role and Heading and text 2 are one thing, a Team member; Swatch was a keyboard key cap.
- **Missed by the derivation, found by eye and then searched for** (`components.seeded_component`: point at an example, take the elements inside the box, find every place the same elements recur in the same arrangement): Team member (8 on one slide), Link button (2 slides), Key cap (3 on one slide), Progress rule (1 match, loosened for width), Stat column (3 on one slide). Seeds with thin evidence say so in their README.

The derive-then-review split is therefore: derivation finds candidates and repeats, a person (or Claude, looking) says what is a component, and the seeding step turns what the person points at into something verified against the deck. Fifteen components remain, against 31 candidates.

### Designing new pages from a system (`test-decks/composed/compose.py`)

The consumer test: read the system's tokens, take components and layouts from its previews, fill their slots and place them. Nothing is measured from the source deck. (local, not committed) shows two pages (a light page from Eyebrow plus three Stat columns, and a dark page from the verified Statement layout with the Link button). Using the system this way found four defects, all fixed:

1. Previews bound a white background to `var(--ink)`, because white is `ink` in the dark theme and `paper` in the light one. Themed tokens are no longer used to bind an exemplar's fixed colours.
2. The Stat column put its unit ("hrs") on a line below the figure, because a paragraph with two sizes was split into stacked blocks, and the unit then overlapped the label. A paragraph whose sizes change without a line break is now a baseline row.
3. A longer unit ("reviews") ran into the next column, because nothing said how much a slot can hold. Slot lines in each README now give the box width and about how many characters fit.
4. The Link button is white, so it vanishes on a light page: components carry the colours of the slide they came from. The system has no light variant of it; the composed page puts the button on the dark page only. Component variants per theme are not derived yet.

### Recipes instead of layouts (`d2s/recipes.py`, `recipetest.py`, `recipefiles.py`, `coverage.py`)

After the review, the system was reorganised around a page model: **page furniture and media** (Eyebrow, Logo, Marker, Rule, Progress rule, Side picture), **content roles** (type styles used for a purpose, listed in the README, no longer components), **patterns** (Stat column, Team member, Link button, Key cap), and **recipes** for whole-slide types. The layout catalogue and its showcase pages are gone.

- A recipe (`recipes.json`) states theme, furniture, slots and repeats, each with a grid column plus offset, y, width, a named text style, a character limit and notes, and the source slides it came from. Derived geometry and styles, named and bounded by hand.
- `recipes.render(recipe, content)` produces a Claude Slides section; `recipes.extract(recipe, slide)` reads a source slide's content back out. `recipetest.run` recreates each evidence slide from its own words and compares it with the original (the converter's render, itself within about 2 to 4% of Google's). Result on public deck B: Section title 0.6% of pixels differ across 12 slides, Statement 1.1% across 8, Contents list 0.6% across 9, Stat columns 2.8% (1 slide), Team grid 1.7% (1 slide). The last two are checked only against their own exemplar.
- `Recipes.md`, `recipes.json`, one example slide per recipe (`recipes/<id>.html`) and a showcase card per recipe are generated from the one source file.
- **Coverage** (`coverage.py`, 12 random slides): classes each element as furniture, media, pattern, role (a text style used where a recipe puts it) or unexplained. About 45% of the elements on typical slides are explained; two table-like slides (130, 138) explain about 0%, and most of the rest is list text, tables and one-off content the recipes do not claim. That is the honest ceiling of this system on this deck: five recipes, not the whole template.
- Known gaps: the Stat columns unit sits a little closer to the figure than in the source; recipes have no variants yet (2 or 4 columns, light and dark), so the flex is limited to slot counts and text; three recipes are tested on one slide.

### Pictures from Google Slides decks

The connector returns each picture as a signed link on the Google docs host that expires within minutes, and the sandbox's network must allow that host. Download them straight after reading the links, then `images.build_map` turns them into web-sized files (animated GIFs become their first frame, wide pictures are capped at 1600 px, pictures with transparency stay PNG). The converter writes `IMG:<objectId>` placeholders (`IMG:bg<N>` for a slide's photo background, now a full-bleed first picture), and `gslides2claude.resolve_images` swaps in real urls: local `file://` for rendering, `/_blob/<id>` for an artifact after the files are uploaded as assets. Recipes extract pictures and photo backgrounds too, so the recreate-and-compare test now includes them. Two rules keep generated systems clean: pictures that are portraits of real people (square 512 px images) are never mapped, and the recipe slot is marked `placeholder` so the example shows an empty round frame; and downloaded pictures, tokens and generated systems live only in ignored working folders, never in the repository.
