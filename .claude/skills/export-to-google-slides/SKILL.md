---
name: export-to-google-slides
description: Export a Claude Slides-artifact deck (deck.json, deck.css, slides/*.html) to a native Google Slides deck through the Drive and Slides MCP connectors, using d2s.py. Read before any upload. Covers the parentId rule, picture bundles, replaceImage, checks and clean-up.
---

# Export a Claude Slides deck to Google Slides (MCP route)

Use this when asked to "publish", "export" or "put it on Google Slides". Never hand the user a .pptx instead: the point is a native Google Slides deck in their Drive. The README has the rule tables; this page is the order of work and the traps that have cost real time.

## The three rules that were learned the hard way

1. **Always pass `parentId` = a Drive folder to `create_file`.** Without one (My Drive root) every file over ~0.7 MB fails with `Requested entity was not found`. That is not a size cap. The 0.85 MB figure that appears in old notes came from root uploads. With a folder, 2.1 MB, 2.6 MB and 3.03 MB uploaded and converted in one call. Create a folder once (`create_file`, `mimeType application/vnd.google-apps.folder`) and reuse its id. Do not shrink pictures or cut the deck into many small bundles to dodge it.
2. **The real ceiling is 4.2 MB per connector call, about 3.1 MB of files.** Above that you get an explicit "over the 4.2 MB limit" error. Keep `deck.pptx` and each `pack_NN.pptx` under ~2.9 MB (the defaults in `d2s/config.py`: `UPLOAD_BUDGET_BYTES`, `BUNDLE_LIMIT_KB`).
3. **Before changing a limit or a default, read the earlier measurements** (README "Known constraint", "Root vs folder uploads", rule table row 15) and re-test the *same* call shape. Say what was and was not tested.

## Steps

1. **Deck directory.** Needs `deck.json`, `deck.css`, `slides/`. Faces without an `href` (uploaded fonts such as Inter Outline) are accepted by `d2s/fonts.py`; for the extractor give them a local CSS file as `href`. Icons come from `js/icons.json` (add missing names: the converter prints `UNKNOWN ICON`).
2. **Pictures.** `/_blob/<id>` ids need local files: write a `map.json` of `{id: absolute path}` and pass `--assets map.json`. Reading blobs back from the artifact is one call per id; prefer your own source files. `UNMAPPED` lines in the log mean a picture will be blank.
3. **Convert** (needs Chromium; `D2S_CHROMIUM=/opt/pw-browsers/chromium NODE_PATH=$(npm root -g)`):
   `python3 d2s.py convert <deck> <work> --assets map.json`
   Read the end of the output: pictures embedded, placeholders left, `deck.pptx` size, bundles. Warnings (group opacity, blur, WordArt not calibrated) go in the report to the user.
4. **Upload `deck.pptx`** with `create_file`, `contentMimeType application/vnd.openxmlformats-officedocument.presentationml.presentation` (converts to Slides), `base64Content = sha256:<real hash>:<absolute path>`, `parentId = <folder>`. The file must be under the session's working directory. Compute the hash with `sha256sum`; a placeholder hash is refused. Note the new presentation id.
5. **Read the picture tags.** `read_presentation` with `fields ["revisionId","slides.objectId","slides.pageElements(objectId,description)"]`. The result is large and is saved to a file: parse it with Python (`description` → `objectId`, save as `tags.json`).
6. **Bundles.** For each `pack/pack_NN.pptx`: upload (same folder), `read_presentation` with `slides.pageElements(description,image.contentUrl)` to get temporary image URLs (valid ~30 min), then send **one** `update_presentation` of `replaceImage` requests (`imageReplaceMethod` from `manifest.json`: CENTER_INSIDE or CENTER_CROP) for every element of every key in that bundle. Finish a bundle before starting the next, and read the URLs just before using them. Print the elements for a pack from `manifest.json` + `tags.json` rather than working them out by hand.
   - Opacity cannot be set by `replaceImage`; pictures that need it must be embedded in `deck.pptx` (the budget picks opacity pictures first).
   - Many slides reuse the same picture (logos, backgrounds). If the budget is tight, embed the most-repeated pictures first (`plan_embeds` does this).
7. **Calibrate, then check with the repo's own diff tool, every slide.** Do this on every deck, not only when something looks wrong: without it Inter's first line sits 2 to 4 px high and 200 px+ type 25 to 50 px high.
   - Once per deck: `d2s.py calib-deck <deck> <work_cal> --assets map.json`, upload `<work_cal>/calib/calib.pptx` (folder parent), `download_file_content` with `exportMimeType application/pdf`, `d2s.py pdf2png <pdf> <work_cal>/cthumbs`, `d2s.py calib-fit <work_cal> <work_cal>/cthumbs -o calibration.json`, then convert again with `--calibration calibration.json`.
   - Every export: `download_file_content` of the converted deck as `application/pdf` (saved to a file), `d2s.py pdf2png <pdf> <work>/gthumbs`, then `d2s.py report <work> <work>/gthumbs --ref full --diffs <work>/diffs`. It compares every slide with the browser render and writes `report_gthumbs.json` (diff %, text blocks off by more than 4 px, max offset). Report the median, the number of slides over 2% and 5%, and look at the worst few by eye.
   - Measured on the 207-slide TOAST deck: uncalibrated median 2.34% / 482 text blocks off; calibrated median 0.58% / 197 off, 55 slides under 0.15%. Still wrong after calibration: outline words (WordArt not calibrated), the 220 px and 400 px display words (about 25 px high), and animated pages (p3kin). Calibrate those sizes next.
   - `read_slide_page_thumbnail` is only for a quick look at one slide.
   - **Decide how to fix what the report shows** (README, "Patching a deck after export"): systematic gaps → calibrate and re-export (only while the Google deck is unedited); per-block offsets → `fit-text` then `convert --corrections`; once a person has edited the Google deck → `d2s.py patch` in place, never re-export over it.
8. **Clean up.** Trash every helper deck and test file you created (`trash_file`); pictures already placed stay in the deck. Name test files `TEST deck-to-slides ...`.
9. **Report** to the user: link, what was checked, what was not, the converter warnings, and anything that does not carry over (animations, transitions, group opacity, blur, blend modes, other fonts).

## Traps

- Hand-copied 280-character image URLs go wrong; the update call fails on a bad URL, so fix those requests and resend. Copy URLs from the read result, never from memory.
- The connector only sees files it created. Do not look for the user's uploaded .pptx.
- `sleep` loops are blocked in this environment; wait with an `until` loop on a log line.
- The Slides MCP rate-limits thumbnail reads (about 27 a minute).
- Do not leave test files or a half-built deck in the user's Drive without saying so.

## Lessons added later

- Icons and line drawings go out as native freeforms (`d2s/svgvec.py`), never as small pictures: pictures are resampled by Google.
  After an export, zoom into the icons (crop 60x60 at 4x, Claude / Google / overlay) before calling the deck done.
- Never leave `a:prstGeom` beside `a:custGeom` on one shape.
- Reusing bundle decks between exports is fine when the placeholder list (`manifest.json` tags) is unchanged: upload only the new
  `deck.pptx`, re-read the bundles for fresh image URLs, then send `replaceImage`. Send them one bundle per call, so a typo in one
  URL fails only that call.
- Do not stack a correction on one that was never applied: re-measure on the export you are looking at (`fit-blocks --prev` adds the
  residual to what is already in the deck).
