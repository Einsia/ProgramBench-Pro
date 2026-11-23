# Coverage

Piskel **0.15.0**, task **1.0.0**. The executable manifest contains 91 episodes
(41 program, 50 GUI), 536 checkpoints, 216 frontend assertions and 1278 backend assertions.
The task score is the fraction of episodes whose points all pass.

| Feature | Episodes | Frontend | Backend |
| --- | ---: | ---: | ---: |
| colours | 8 | 33 | 64 |
| drawing | 22 | 49 | 150 |
| export | 9 | 16 | 96 |
| file-format | 6 | 0 | 352 |
| frames | 4 | 11 | 35 |
| history | 2 | 6 | 17 |
| import | 6 | 15 | 124 |
| layers | 3 | 14 | 49 |
| persistence | 6 | 8 | 37 |
| preferences | 4 | 13 | 21 |
| resize | 2 | 7 | 97 |
| save | 3 | 3 | 64 |
| selection | 3 | 10 | 17 |
| transforms | 10 | 14 | 155 |
| view | 3 | 17 | 0 |

## Covered behavior

- Drawing: pen sizes and interpolation, mirror axes, eraser, straight and constrained strokes, rectangles and
  ellipses, flood fill connectivity, global color replacement, lighten/darken, dithering, color picking,
  primary/secondary color entry and swapping, move with clipping/wrapping and frame/layer modifier scope.
- Selection and history: rectangular, connected-shape and lasso selections; copy, cut, paste, moving content,
  cross-frame/cross-layer paste, replacement selections and moving selection outlines, undo/redo and discarded redo histories.
- Animation: insertion, duplication, deletion, selection limits, reordering, preview exclusions, frame rate,
  onion skin and preview scale.
- Layers: creation, cloning, naming, Unicode, deletion, ordering, merging, opacity boundaries and current-layer
  targeting. Transformations cover vertical/horizontal flips, both rotation directions, centering, cloning
  across frames, content/selection cropping, non-square images and frame/layer scope.
- Resizing: grow, crop, scale, stretch, single-row/column bounds, all nine anchors, maintained aspect ratio and
  persistent default dimensions.
- Formats: `.piskel` v0/v1/v2, legacy unchunked v2, vertical/separate/reordered chunks, multiple layers/frames,
  names, description, FPS, opacity, hidden preview frames, exact layer/frame counts, padded two-dimensional atlases, reordered chunks, indexed PNG depths and color-key transparency, tiny/non-square/large dimensions, round trips and
  malformed input with a surviving current document. Only meaningful document projections are compared.
- Import: PNG, BMP, JPEG, GIF, `.piskel`; chooser and drag/drop; resizing with/without smoothing; spritesheets,
  offsets, combining existing/new frames, canvas expansion/cropping and placement anchors. Bounded multi-file drops cover file order and first/middle/last timeline insertion; all resulting frames are read back.
- Export: PNG sheets with column layouts, selected-frame PNG, scale, composite opacity, animated GIF pixels,
  timing/looping/transparency, frame ZIPs with layer splitting/naming, PixiJS metadata with external/inline PNG,
  C pixel arrays with their dimensions, PNG data-URI output and explicit fractional resolution scaling, and saved `.piskel` files. PixiJS checks preserve frame-to-image correspondence and distinguish embedded from external PNGs; GIF checks distinguish finite, infinite and single playback.
- Storage: browser save/load/overwrite across reload and process restart, custom palette and preference persistence,
  automatic backup recovery, selective archive/session deletion, cancellation and persistence of the surviving data. View settings cover zoom, pan, fit, tiled mode, layer previews, grid and background; grid color and other-layer preview opacity have persistence checks.
- Palettes: GPL, PAL, Paint.NET TXT and image import; use, cycling, creation, color editing/addition/removal, renaming, deletion, GPL export;
  HSV/RGB component editing, bounded component input and canceling edits; keyboard shortcut reference, custom remapping, persistence and restoration of defaults.

## Interfaces and comparison

All preparation, stimuli and observations use the runtime in `environment/runtime/`. The only document reads are
`api/getPiskel`; document preparation uses `api/loadPiskel`. The runtime help describes the real Piskel methods
that implement both operations and the sprite-coordinate mapping. Tests never read the product's files or private
state, execute arbitrary page scripts, or use a separate automation interface.

Program stimuli use keyboard, sprite-coordinate gestures, visible controls, upload/drop and lifecycle operations.
GUI recipes use the same operations except file drops (covered by program episodes) and are reference-only routes. Program stimuli and GUI preparation locate controls from visible names, group context, editability and focus; they do not require HTML tags, text-input types, arbitrary field ordinals or icon-internal opacity coordinates. Each checkpoint resets the browser and loads
its own fixture; explicit setup dependencies are local to that episode. Broad coverage is in program episodes;
GUI companions check only the immediate goal result. Fine pixel geometry belongs to program observations, while
frontend assertions describe visible functional outcomes and permit equivalent interfaces.

PNG bytes and compression are not compared: files are decoded to RGBA, with invisible RGB discarded. GIFs are
decoded to composed frames; frame delays allow one GIF time unit. Sprite images and lossless exports compare
pixels, layer order, frame order and dimensions. The GUI mirror-pen freehand drag alone permits a one-pixel
Manhattan path difference caused by pointer event sampling, while retaining exact color, canvas size, stroke
extent, mirror symmetry and bounded painted area; its program episode remains pixel-exact. Numeric opacity has tolerance 0.001. Timestamps, JSON formatting,
object key order and random palette identifiers are not scored. Generated layer names need only be nonempty; explicitly entered names and the existing layer names remain exact. C integer constants may use equivalent hexadecimal or decimal notation. Legal v2 unchunked and padded chunk layouts decode to the same ordered layers/frames/RGBA projection; incomplete or out-of-bounds layouts are rejected. Download names are compared only where a naming
option is the subject; saved-project timestamps are ignored. Format-error points have positive companions.

## Budgets and determinism

GUI episodes allow 400 calls, 8,000,000 tokens and 12,000 active seconds each. The call and token ceilings include visible group context and exploration.
The pinned interface is Chromium, 1280 by 900, en-US, UTC. Actions wait for meaningful DOM changes and pending file
operations. Import episodes wait for the visible current-colors palette to finish loading before opening the wizard;
this prevents the asynchronous palette from making a populated sprite follow the empty-canvas import route.
Every episode is serial within its verifier. Program wall limits are max(900 seconds, five times
measured reference duration); GUI limits add the interaction budget to max(600 seconds, five times measured reference duration).
`task.toml` sets the verifier timeout from the sum of these limits with overhead, never below 86,400 seconds.

## Exclusions

Online gallery/login/sharing, remote GIF upload and release-note navigation require external services and are
unavailable offline. New-sprite links that open the online editor in another window are outside the single-page
runtime. Desktop NW.js filesystem integration is not part of this browser distribution. Hardware/OS clipboard
image capture, multi-monitor and mobile behavior are outside the headless browser interface. The pinned import wizard accepts only a single selected image/project; it does not implement multi-file chooser import. Batch image input is covered through its native multi-file drop behavior, using the same bounded public runtime channel. Actual desktop shell drag integration is outside the headless browser interface. No scripts, plugins or arbitrary-path operations are exposed.

Reference evidence can include current save/backup dates, generated palette IDs, and the animated preview phase; these are not scoring observations.
