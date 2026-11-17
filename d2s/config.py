"""Every tunable number of the converter, each with how it was measured.
Values marked UNVERIFIED have not been confirmed by tests/decks/features; the README rule table says which.
Change them here, never inline."""

# --- Units ---------------------------------------------------------------------------------------------------
SLIDE_PX = (1920, 1080)        # the browser frame the deck is laid out in (Slides artifacts are 1920x1080)
SLIDE_EMU = (9144000, 5143500) # a Google/PowerPoint 16:9 slide is 10 in x 5.625 in; 914400 EMU per inch
EMU_PER_PX = SLIDE_EMU[0] / SLIDE_PX[0]    # = 4762.5   (exact: 9144000 / 1920)
PT_PER_PX = 72 * 10 / SLIDE_PX[0]          # = 0.375    (10 in = 720 pt across 1920 px)

# --- Fonts ---------------------------------------------------------------------------------------------------
# Google reads lnSpc spcPct as a share of the font's OWN line height. Which metric table counts is chosen here;
# the calibration deck measures the real line pitch and can override the number per font (calibration.json "natural").
NATURAL_SOURCE = 'hhea'        # 'hhea' | 'typo' | 'win'.  Measured: hhea matched Google on the four pitch fonts.
NATURAL_FALLBACK = 1.21        # used only when no font file / measurement is available (Inter's value)
# Weights travel in the family name. Only 700 uses the bold flag (b=1) with the plain family name.
# Names follow Google Fonts' static family naming. Measured on Inter and Bricolage Grotesque only (see features deck, weights slide).
WEIGHT_SUFFIX = {100: ' Thin', 200: ' ExtraLight', 300: ' Light', 400: '', 500: ' Medium', 600: ' SemiBold',
                 700: '', 800: ' ExtraBold', 900: ' Black'}
BOLD_WEIGHT = 700
EMIT_EA_CS = False   # also write the East-Asian / complex-script typeface; off to keep files small (Latin text only needs latin). UNVERIFIED for CJK decks
# A glyph the web font lacks is drawn by the browser from the fallback face; we write it as this family.
FALLBACK_FAMILY = 'Arial'

# --- First-line offset ---------------------------------------------------------------------------------------
# Google puts the first text line some px above/below Chromium. Offset is stored as a fraction of font size and
# interpolated over CSS line-height; produced by `d2s calibrate` per font. Fallback when a font has no table:
DY_FALLBACK_PER_FS = 0.0       # px of shift per px of font size (no correction)

# --- Wrapping ------------------------------------------------------------------------------------------------
# Google sets text ~0.1% narrower than Chromium and always wraps to the box. One-line text and 'tight' boxes get this
# much extra width: max(WIDEN_MIN_PX, WIDEN_FRACTION * inner width). Hand-measured on the pitch deck (UNVERIFIED generally).
WIDEN_MIN_PX = 12
WIDEN_FRACTION = 0.04
WIDEN_MULTILINE_PX = 2         # free multi-line text: small cushion
WRAP_NONE_TIGHT = False        # wrap="none" for nowrap text, text that overflows its box and tight single-line / forced-break text (EXPERIMENT, see README rule 5)
# A wrapped block is forced to soft breaks when a word missed by < RISKY_FRACTION of the box width (extract.cjs).

# --- Rounded shapes ------------------------------------------------------------------------------------------
# Text inside roundRect is inset by (1 - cos 45deg) = 0.2929 x radius per side (the DrawingML text rectangle).
ROUND_TEXT_INSET = 0.2929
MAX_RADIUS_FRACTION = 0.5      # roundRect adj is radius / min(w, h), capped at 0.5

# --- Pictures ------------------------------------------------------------------------------------------------
PICTURE_MODE = 'mask'          # 'mask': rounded picture element + replaceImage; 'shape': tagged text placeholder + replaceAllShapesWithImage
PLACEHOLDER_PNG_BYTES = 70     # a 1x1 PNG; the real picture replaces it in Slides
PICTURE_SHADOW = 'native'      # 'native': outerShdw on the picture itself; 'shape': a separate rounded shape behind it (old way)
PICTURE_ALPHA = False          # alphaModFix on the placeholder picture (the API cannot set image transparency: 'transparency cannot be updated')
SHADOW_INSET_PX = 1            # a picture's shadow shape is this much smaller on each side so its corners never show
MAX_PIC_WIDTH_FACTOR = 2.0     # pictures are bundled at most this many times their on-slide width (connector size limit)
BUNDLE_LIMIT_KB = 850          # Drive connector `create_file` limit is ~0.85 MB per file (measured: 1.1 MB fails)

# --- Clips (GIF) ---------------------------------------------------------------------------------------------
GIF_MAX_FRAMES = 999           # Slides refuses >= 1000 frames ("Internal error" via API; the editor gives the message)
GIF_FPS = 15
GIF_FPS_LONG = 12
GIF_WIDTH = 320
GIF_POSTER_CS = 10             # the settled first frame shows for 0.1 s (thumbnails/PDF show the first frame)
GIF_STILL_THRESHOLD = 10       # pixel change below this is held still

# --- QA ------------------------------------------------------------------------------------------------------
DIFF_BLUR = 2                  # px blur before comparing (anti-aliasing differences are not errors)
DIFF_THRESHOLD = 38            # max channel difference counted as a visible difference
DIFF_MIN_REGION_PX = 60        # smaller differing regions are ignored
CLEAN_SLIDE_PCT = 0.15         # a slide "has no visible difference" below this % of pixels (UNVERIFIED: chosen to match the earlier 20/28 count)
