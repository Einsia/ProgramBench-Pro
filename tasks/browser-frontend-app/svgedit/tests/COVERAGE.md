# SVG-edit coverage

Version 1.0.0, reference SVG-edit 7.4.2. Exact counts and budgets come from `data/manifest.json`:
51 episodes (14 program, 37 GUI) with 445 checkpoints and 838 scoring points, 236 frontend and 602 backend
(318 program checks and 284 independent checks of GUI checkpoints). The count comes from distinct behaviours
only: equivalent parametrisations of one mechanism are not counted twice; GUI goals cover each option
of the editor's choices (font families, dash patterns, joins, caps, anchors, markers, shape categories, canvas sizes,
units, context-menu commands) one goal per option.

## Coverage

| Family | Program episodes (no evaluator) | GUI episodes (goal + program companions) |
| --- | --- | --- |
| Import and normalisation | `import-structure`: layers (titled layer groups, plain groups and Inkscape layers wrapped into "Layer 1", hidden and transformed layers, equal and missing layer titles), document size (cm, mm, in, pt, pc, viewBox only, viewBox with outer size, no size, invalid size), style declarations to attributes, number rounding per attribute kind (polygon points unrounded), ids (assigned, duplicates renamed), document title/description/metadata, used and unused gradients, gradient inheritance, user-space gradients and gradient transforms, nested svg, xlink:href, transforms, zero-size shapes, root attribute whitelist, group paint inheritance, display versus visibility, arcs, relative image references, Unicode text, malformed and non-SVG input refused; `import-elements`: every supported element kind with its attribute whitelist, filter primitives, style element; `import-content`: removal of scripts, event handlers, animation, embedded HTML content and external references; kept HTML text, data attributes and MathML | Open and import of files through the file chooser (`gui-files`), Edit Source apply/invalid/cancel (`gui-source`) |
| Keyboard editing | `keyboard-move` (arrow keys on every element kind, and on rotated, scaled, matrix-transformed and translated elements and groups: the move and how it is written; user-space gradients following the shape; lengths in absolute units and percentages rewritten in user units), `keyboard-rotate`, `keyboard-edit` (duplicate, Alt+arrow, delete, z-order, select all in the current layer, multi-selection, copy/cut/paste, the clipboard across a reload), `keyboard-group` (group, ungroup with transform push-down, opacity multiplied and blur passed on to the children), `keyboard-undo` (undo and redo of ten kinds of change, steps, redo cleared), `text-keys` (bold, italic, typing, Backspace, Delete, cursor keys, selection replace, editing existing text) | |
| Drawing | `draw-tools` (rectangle, square, ellipse, circle, line with angle snap, reversed drags, pencil, closed/curved/open paths, path segments snapped with Shift, Escape, tool return and Alt keeping the tool, zoom-dependent size, drawing outside the page) | `gui-draw-shapes`, `gui-draw-lines` (including text and image tools, an image by address), `gui-polystar` (stars and polygons with point/side counts, pointiness, radial shift), `gui-shape-library` and `gui-shape-library-2` (all fourteen categories) |
| Selection and pointer | `pointer-edit` (topmost pick, Shift+click to add and to remove, selection box, deselect, Shift+O cycling and wrap, drag move, group context, rotated group child, path node drag, eyedropper); `pointer-resize` (selection grips: corner, side, opposite-corner and past-the-edge resizes, Shift keeping proportions, images keeping their aspect unless Shift, how each element kind writes a resize: rectangle, ellipse, circle staying a circle, line, path, polygon, symbol instance, group; rotated elements resized along their axes; the rotation grip with and without 45-degree snapping) | `gui-selection`, `gui-eyedropper`, `gui-arrange`, `gui-context-menu` (cut, copy and paste, delete, group, ungroup, bring to front, send to back), `gui-clipboard` (duplicate, delete, cut/paste, paste in place, multi-duplicate, undo/redo buttons) |
| Paint and style | | `gui-paint-fill` (hex, palette, none, alpha, RGB, HSV), `gui-paint-stroke` (hex, palette, none, alpha, width), `gui-gradients` (linear, radial, spread reflect and repeat, vector, radius), `gui-stroke-style` (one goal per dash pattern, solid, each join and each cap), `gui-effects` (opacity, blur, corner radius, rotation angle, group opacity), `gui-markers` (start/mid/end markers, one goal per marker kind, removing a marker) |
| Geometry and identity fields | | `gui-geometry` (position, size, circle, ellipse, line end, image, path and group position: one point per field), `gui-identity` (id, class, group label, text position) |
| Text | `text-keys` | `gui-font-family` (one goal per font family, eight), `gui-text-font` (size, bold, italic, each decoration), `gui-text-layout` (each anchor, letter and word spacing, text length with both adjust modes, editing content) |
| Arrange | | `gui-align` (six alignments relative to the selection), `gui-align-relative` (page, largest, smallest, distribute, single-element alignment to the page), `gui-flip-convert` (flips of a group and of a single shape in both directions, conversion of seven kinds to paths, reorient), `gui-links` (make, edit, remove a link, break a symbol instance) |
| Paths | `pointer-edit` (node drag) | `gui-path-edit` (node coordinates, segment type to curve and to straight, clone, delete, close, drag) |
| Layers | `keyboard-edit` (select all per layer) | `gui-layers` (new, rename, delete, up, down), `gui-layers-more` (hide, show, move selection, duplicate, merge down, merge all, draw into the current layer) |
| Document, preferences, view | | `gui-document` (title, size, each predefined size, fit to content, image embedding), `gui-preferences` (snapping for drawing and arrow keys, base units cm/mm/in/pt/pc and the document size written in the base unit, background, language), `gui-view` (wireframe, zoom field, grid, layer view, zoom tool) |
| Files and persistence | `drop-import` (SVG, PNG, JPEG, other files, id clashes), `save-persist` (Save with S, image embedding, reload, restart, fresh profile, undo history after reload) | `gui-files` (new, open, import SVG/PNG/JPEG, refusals), `gui-save` (save, save as), `gui-export` (PNG, JPEG with quality, BMP, WEBP, PDF; size, content and transparency per format; hidden layers left out, images included; portrait PDF, PDF title), `gui-persistence` (reload, the four storage choices), `gui-errors` (invalid field values, duplicate layer name, invalid canvas size) |

Excluded, with the reason:

| Excluded | Reason |
| --- | --- |
| URL parameters (`url`, `source`, `extensions`, `lang`, `dimensions`, `initFill`, ...) other than `storagePrompt` | `url` and `extensions` fetch content or load code (isolation); the others cannot be discovered through the editor; the runtime opens only the entry page |
| Content or images loaded from outside addresses, the home-page link | offline; same-origin and data addresses still work |
| The connector tool | in 7.4.2 it never completes a connection (it leaves a degenerate polyline), so there is no reference behavior to require |
| Key combinations the editor does not act on (Control+Shift+arrows, Control+Shift+[ / ], Shift+P) | product shortcut normalisation never fires them or maps them to another tool; the corresponding buttons and menus are covered |
| Translated texts of the 22 other interface languages | each translation is the same mechanism; switching the language is covered |
| Icon size | SVG-edit 7.4.2 has no icon-size preference |
| The grid-colour and "Show rulers" preferences | in 7.4.2 neither has a visible effect (the grid stays grey, the rulers stay shown, also after a reload) |
| Selecting the first node of an open path with a plain click | 7.4.2 selects it only when the pointer moves between press and release; the node goals use other nodes |
| Tab and Shift+Tab selection cycling, the top-centre resize grip | Tab also moves the browser focus, so the result depends on focus state; the top grip lies under the rotation grip's connector (the bottom, side and corner grips are covered) |
| Resizing text with the grips; the first child of a blurred group | text grips depend on font metrics; on ungroup SVG-edit drops the group blur from the first child without its own blur (a defect; the other children are checked) |
| Panning, wheel zoom, overview window (disabled upstream), ruler numbers, the "link control points" toggle | view-only details that cannot be judged reliably or have no observable result in the drawing |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime: its api operation (the editor's
  `window.svgEditor.loadFromString` and `svgCanvas.getSvgString`), its keyboard, pointer (document coordinates
  through `svgCanvas.getSvgContent().getScreenCTM()`, or pixels inside the drawing surface `canvas0`), drop, upload
  and download operations, and its lifecycle operations (reset, restart). Nothing reads candidate files or
  processes.
- Program episodes use only keyboard shortcuts the reference acts on, pointer input in document coordinates
  (including drags that start on the selection's grips, which lie at the selection box; the two zoom-shortcut checks
  drag a fixed pixel box inside the drawing surface `canvas0` instead, since document coordinates would scale with
  the zoom) and file drops; they never locate controls by name or position. Each checkpoint starts from a fresh
  browser profile (reset, entry page, the first-visit storage question answered with its OK control: any control
  named OK in any letter case that has a control named Cancel beside it; the question counts as answered when that
  OK is gone within 6 s, and the setup fails only if it stays after the click and one Enter), loads its own drawing
  through the API and is independent of the other checkpoints.
- GUI checkpoints start the same way, with the stated selection made by scripted clicks in document
  coordinates; the evaluator then pursues one goal with the editor's controls. Their program companions read the
  resulting drawing (or the file the goal produced) and check only the state the goal changes.
- Observations are representation-independent projections of the drawing: element kinds, effective outlines in
  document coordinates (own and ancestor transforms applied, relative and absolute path commands alike), effective
  paint after inheritance with SVG defaults, normalised colours and fonts, paint servers by content, gradients by
  their geometry in document coordinates (bounding-box or user units alike), layers by title and content; the
  corners of rectangles, circles and ellipses are compared as a ring, so a mirrored copy matches whether it is
  written with a transform or with plain attributes, and where only a polygon's geometry is checked (star pointiness
  and radial shift) its distinct corners are compared as a ring from any start in either direction. Colours match
  within one unit per channel (colour-picker rounding); a cubic segment whose control points sit on its own end
  points counts as a straight segment; a zero-width stroke counts as no stroke; an image address is read from href
  or xlink:href; converted shapes are measured by the extent of their curves and arcs; imported drawings, broken
  instances and pasted copies are compared by the shapes they draw and by size and style, not by the element that
  wraps them or by where a paste lands. Ids are compared only for elements the drawing already had. "Raw"
  observations (attributes as written) are used only where SVG-edit's rewriting is the behavior: number rounding,
  style declarations becoming attributes, how a move or resize is written into coordinates or transforms, lengths
  with units rewritten in user units, xlink:href becoming href, the document size written in the base unit. Numeric
  tolerance is 0.05 units unless a point states otherwise (exported pixels, drawn lengths, rotations).
- Exports are decoded: image format, pixel size, colour samples at fixed points (including uncovered background,
  which differs per format), JPEG quality from the quantisation table, PDF page count and size.
- Points that only verify a refusal or an unchanged drawing are bound (`requires`) to a positive point of the same
  episode: the loader accepting a drawing, the source editor applying a change, the import of a valid file, a
  layer being added, a field accepting a valid value, the drawing surviving a reload.
- A crashed application is restarted with the same data before the next checkpoint.

## Budgets and time

GUI episodes have call, token and active-time budgets in the manifest (`calls` 30 + 30 per checkpoint, `tokens`
400,000 + 500,000 per checkpoint, `seconds` 300 + 240 per checkpoint), under the bridge ceilings of 400 calls and
8,000,000 tokens per episode (the largest GUI episodes have 11 checkpoints: 360 calls, 5,900,000 tokens). The
standard answer uses at most 40 % of each call and token budget under the evaluator (DeepSeek). Program episodes
need no evaluator.
