# Xournal++ coverage

Version 1.0.0, reference Xournal++ 1.3.8. 104 episodes (16 program / 88 GUI), 338 checkpoints, **1740 backend / 198 frontend points**.
Exact episode IDs, dependencies and budgets are frozen in `data/manifest.json`.

| Feature family | Episodes | Backend | Frontend |
| --- | ---: | ---: | ---: |
| background-options | 1 | 212 | 0 |
| clipboard | 2 | 9 | 4 |
| compatibility | 1 | 77 | 0 |
| documents | 1 | 8 | 2 |
| drawing | 5 | 12 | 12 |
| drawing-guides | 1 | 4 | 2 |
| eraser | 3 | 9 | 6 |
| errors | 1 | 2 | 2 |
| export | 4 | 16 | 8 |
| history | 1 | 4 | 3 |
| image-background | 1 | 50 | 0 |
| images | 2 | 9 | 4 |
| input-errors | 1 | 8 | 0 |
| layer-ranges | 1 | 52 | 0 |
| layers | 7 | 23 | 15 |
| lifecycle | 6 | 10 | 12 |
| mouse-mapping | 1 | 2 | 2 |
| native-references | 1 | 122 | 0 |
| navigation | 3 | 3 | 10 |
| object-order | 4 | 8 | 8 |
| option-errors | 1 | 5 | 0 |
| page-ranges | 1 | 64 | 0 |
| page-templates | 1 | 9 | 3 |
| pages | 4 | 18 | 9 |
| palettes | 1 | 2 | 2 |
| paper | 5 | 16 | 13 |
| pdf | 5 | 15 | 9 |
| pdf-background | 1 | 288 | 0 |
| pdf-import | 1 | 28 | 0 |
| pdf-navigation | 1 | 0 | 2 |
| png-resolution | 1 | 64 | 0 |
| preferences | 1 | 0 | 2 |
| progressive-layers | 1 | 20 | 0 |
| render-backgrounds | 1 | 81 | 0 |
| render-images | 1 | 30 | 0 |
| render-strokes | 1 | 114 | 0 |
| render-text | 1 | 270 | 0 |
| search | 1 | 0 | 2 |
| selection | 7 | 21 | 14 |
| shapes | 9 | 34 | 26 |
| snapping | 2 | 8 | 4 |
| stabilization | 1 | 3 | 2 |
| text | 3 | 9 | 6 |
| toolbar-customization | 1 | 1 | 2 |
| view | 4 | 0 | 9 |
| view-layout | 1 | 0 | 3 |

## Document and command-line coverage

Program episodes cover pen and highlighter rendering, pressure-encoded strokes,
line caps, named/custom dash patterns, fills, clipping, named colors, eraser
strokes, text families/styles/sizes, multiline and international text, embedded
PNG/JPEG images and transparency, paper ruling and background configuration.
The same distinct inputs exercise PDF, PNG and SVG exports. PDF text checks
separately inspect content, placement, size, face flags and colors. Other page
content is compared by rendering; page count and overall geometry are scored
once per artifact, without multiplying identical checks over every page.

Other program episodes cover page expressions and ordering, duplicate and open
ranges, invalid ranges, layer selection, progressive layer buildup, background
and ruling suppression, PNG DPI/width/height and precedence, native legacy/plain
formats, image-extension fallback and unknown-tool fallback. Image backgrounds
use absolute, relative and cloned references. PDF import/conversion and annotated
background export cover mixed/fractional sizes, rotation, crops, raster content,
navigation-bearing PDFs and both Cairo and qpdf export backends. Invalid files,
missing inputs, invalid numeric options and read-only output errors are checked
as independent commands. The pinned release rejects the native ZIP container
with its documented MIME marker; that observed rejection is covered.

Every command begins with a runtime reset independent of the candidate command.
A command failure therefore does not poison later cases. Outputs are fetched
through `list_files` and `download`. Return codes must indicate success for
positive exports; missing, empty or unreadable artifacts fail. Rejection cases
have one observation each rather than repeated copies of the same failure.

## Desktop coverage

GUI goals cover freehand pens and widths, line styles, highlighting, rectangle,
ellipse, arrows, coordinate axes, straight lines, filled shapes, splines, shape
recognition, eraser modes, drawing guides and the default tool. Text goals create,
edit and format text, including Unicode and multiple lines. Images are inserted
from ordinary files. Selection goals move, resize, rotate, recolor, lasso, delete,
copy and paste content; clipboard text and PNG are checked as public outputs.
History goals exercise undo, redo and a new edit after undo. Vertical-space
editing shifts lower content.

Pages can be inserted before/after/at end, duplicated, removed and reordered.
Paper goals cover standard/custom sizes, orientation, colors, backgrounds and
new-page templates. Layer goals add above/below, rename, delete, merge, hide/show,
transfer selections and undo ordinary layer edits. Multi-layer selection locates
objects on a non-active layer; the product chooses the highest visible layer
containing selected content, rather than selecting all layers simultaneously.

PDF goals open and annotate documents, append PDF pages, find text, copy PDF
text, highlight, underline and strike through selections. GUI exports cover PDF,
PNG, SVG and legacy Xournal documents, followed by viewing the exported content.
Lifecycle goals save/reopen across restart, recover unsaved content and cancel
replacement of an unsaved document. View goals cover navigation, zoom,
fullscreen, paired pages, presentation, sidebar and toolbar layouts.
Preferences persist across restart.

## Additional offline feature mappings

| Feature | Episodes and distinguishing observations |
| --- | --- |
| Object stacking | `gui-stack-front`, `gui-stack-forward`, `gui-stack-backward`, `gui-stack-back`: three overlapping colored objects; each arrange command and its Undo export visibly different intersections. Median RGB colors at four interior overlap locations tolerate 10/255 per channel, so small overlap changes cannot disappear under a whole-page threshold. |
| Grid and rotation snapping | `gui-snapping-grid`, `gui-snapping-rotation`: off/on comparisons, 1 cm grid and explicit near-horizontal input; saved geometry establishes grid alignment and angle. |
| Input stabilization | `gui-input-stabilization`: identical zigzag motion with None versus Arithmetic mean / Buffersize 40; relative path roughness must decrease. |
| Drawing guides | `gui-guides-drawing`: setsquare line straightness and compass arc circularity/half-circle extent. `gui-drawing-guides` covers guide visibility. |
| Palette data | `gui-palette-data`: select supplied GPL palette, draw Forest and Berry strokes across restart; compare requested tool/color semantics. |
| Toolbar management | `gui-toolbar-custom`: copy a layout, remove Print, restart, use retained Text control. `gui-toolbar-layout` covers built-in layouts. |
| Mouse mappings | `gui-mouse-button-map`: right button draws a highlighter stroke, left button remains Pen; unspecified color and width are not compared. |
| PDF navigation | `gui-pdf-internal-navigation`: nested bookmark to Destination 2 and internal link to Destination 4. |
| Annotation and layer navigation | `gui-annotated-navigation`: next/previous annotated pages and Go to Page; `gui-layer-navigation`: previous/next/top layers with distinct text on each. |
| Other selection modes | `gui-selection-alternatives`, `gui-multilayer-lasso`, `gui-pdf-rectangle-copy`: object selection, multilayer region deletion/Undo, rectangular PDF text selection and public clipboard. |
| Page layout | `gui-layout-directions`: two columns, reversed horizontal ordering, single horizontal row. Existing view episodes cover zoom/fullscreen/presentation/sidebar. |
| Template files | `gui-template-file`: define fixed size/color/grid, save/load XOPT, create pages and retain the template across restart. `gui-page-template` covers copying current-page settings. |
| Lifecycle boundaries | `gui-overwrite`, `gui-discard-recent`, `gui-save-on-quit`: refuse/confirm replacement, discard unsaved edits and reopen Recent, save while quitting and reopen after restart. The exit assertion requires the positive saved-content assertion; the next checkpoint restarts the application and visibly reopens that saved content. |
| Native PDF resources | `cli-native-references`: absolute/relative paths with both inherited and repeated attributes, attached, identical basenames in different exchange areas, missing file and invalid page. Successful files are exported and checked for actual PDF page content. |
| Image alpha | `gui-image-transparency`: insert on colored grid, save/reopen; native image content and transparent/partial alpha fractions remain. `cli-render-images` and `cli-image-background` independently cover export compositing. |
| Independent drawing history | Six basic `gui-shape-*` episodes plus `gui-spline` and `gui-shape-recognition` each check a removed drawing before checking Redo restoration. Undo granularity is not part of the user acceptance. |

Coordinate axes are compared as two straight intersecting lines, independent of stroke segmentation. Line direction tolerates 5 degrees, straightness 4 pt and intersection 3 pt; each axis spans at least 60 pt. Blue pen styles are compared as a set, while Undo still requires a blank page.

Geometry checks use semantic tolerances: snapped points within 0.7 pt of the 1 cm grid, a horizontal snapped line within 0.3 degrees, straight guided strokes within 2 pt, circular arcs within max(2 pt, 4% radius). Shapes and arc size remain free within the stated goals. Stabilization compares the two requested input motions instead of freezing a point sequence. Image alpha fractions tolerate 0.025; white-flattened images fail even when their appearance on white is similar.

## Observations and tolerances

Only public runtime channels are used: desktop operations and observations,
command-line invocation, upload/list/download, clipboard and lifecycle. Saved
notebooks are decoded semantically: previews, creators and bookkeeping are
ignored; no check requires identical gzip bytes or sampled point sequences. Zero-width
point strokes and zero-length butt-cap strokes have no visible content and are ignored. Nonzero round-cap dots are retained.
GUI text placement tolerates 55 points and transformed stroke bounds 40 points
with landscape/portrait orientation checked separately, because goals specify
broad placement, while exact text, named styles, colors,
layer membership and page order remain meaningful. Copy, cut and move goals check the affected text in the upper-right page quadrant; move/copy also preserve the other original objects. Vertical-space editing checks that upper content stays fixed and all lower content moves down together while remaining on the page. The fixed 55-point position tolerance applies only to other broad placement observations; the whiteout goal
accepts any eraser width because that value is not specified. These projections retain text identity and the specified object styles. Paper geometry tolerates
0.8 points and pen/font sizes 0.2 points. Program geometry/font sizes tolerate
0.6 points and text origins 1.5 points. PDF text colors allow 2/255 per RGB channel to accommodate renderer quantization. PDF background references are resolved relative to the notebook, including inherited/repeated attributes and attached resources, then read through public file channels. Their page numbers and actual PDF content must match the input, regardless of path spelling.

PDF and SVG are rendered by verifier-owned libraries; exported bitmaps are
normalized directly. Renders are resized to a maximum side of 360 pixels,
blurred by 0.7 pixels, and compared against foreground ink relative to the
reference background color. At most 16% of
that area may differ by more than 38/255, with an ink-normalized absolute-error
limit of 20 after ignoring differences of up to 6/255. At least 45% of the
reference foreground strength must remain, so a missing fine or white stroke
does not pass on a mostly empty or colored page. This tolerates antialiasing
while detecting missing content,
incorrect geometry, colors or ruling. Alpha fractions tolerate 0.025. SVG XML,
PDF object structure, font subset names, document IDs and timestamps are not
compared.

Setup only uploads inputs. Each GUI checkpoint declares required setup and
prior state explicitly; backend results gate dependent checkpoints when
available. Backend checks read the artifact produced by that goal once and
project its independent aspects. Rendering and semantic decoding exceptions
fail affected assertions, while provider/verifier faults invalidate a run.

## Budgets and boundaries

For n checkpoints, GUI budgets are 400 model calls,
max(4,000,000,1,000,000+1,000,000n) tokens, and max(1800,900+450n) seconds.
Program wall limits are max(900 seconds, five times measured record duration);
GUI wall limits add their budget seconds to max(600 seconds, five times record
duration). `task.toml` reserves at least 110% of all limits and startup margins.
Oracle usage is checked so the standard answer stays below roughly 40% of call
and token budgets.

Excluded boundaries: physical printing; audio devices and recording/playback;
physical stylus/touch/pressure-device interaction (pressure stored in document
files is covered); external LaTeX programs and executable Lua plugins, which
are restricted by the runtime; online help and other external applications;
translated user interfaces. Periodic hidden autosave files depend on a live
minute timer and cannot be downloaded through the exchange interface; autosave
configuration persistence and interrupted-session recovery are covered instead.
