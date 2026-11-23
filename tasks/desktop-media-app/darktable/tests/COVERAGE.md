# darktable coverage

Task version 1.0.0, upstream darktable 5.6.2. The executable manifest
contains 80 episodes (41 GUI and 39 program), 1,369 checkpoints and 1,446
assertions: 103 frontend and 1,343 backend. The backend consists of 1,266
program assertions and 77 assertions checking direct products of GUI goals.

## Feature-to-episode map

The map follows the [5.6 manual](https://docs.darktable.org/usermanual/5.6/en/),
the native menus and the exporter options. A family includes its listed
behaviors; the suite does not enumerate every combination of controls.

| Public feature | Episodes and observable results |
| --- | --- |
| Import, selection and labels | `library-rating`, `library-labels`, `library-filter`, `collection-sort`: native import, selection, inversion, star ratings, multiple color labels, label filtering, restoring collections and filename sorting in both directions |
| Local files | `library-copy-import`, `library-file-transfer`, `library-remove-delete`: copy-and-import with a destination and rename pattern; library copy and move; remove while retaining the source; reimport; delete from disk. Current document inventories and original bytes distinguish these operations |
| Versions and grouping | `library-duplicate`, `library-grouping`: duplicate versions with individual XMP sidecars; group/collapse, expand and ungroup with an unrelated third image |
| Collections | `collection-rules`, `collection-sort`, `library-filter`: filename matching, union and exclusion rules, color-label criteria, ascending/descending sort and selection inversion. Equal sort keys are not ordered by an implementation-specific tie-breaker |
| Metadata and tags | `library-metadata`, `library-tags`, `program-metadata-01`: title, creator, rights, description, hierarchical and Unicode tags, attachment/detachment, exported descriptive metadata and ratings |
| Editing and history | `edit-*`, `history-lifecycle`, `program-history-01`, `program-module-order-01`: native parameter editing/reset, orientation/crop, undo/redo, history copy/paste/discard/compression, disabled/truncated/last-entry histories, effective multiple instances and noncommuting module order |
| Styles | `styles-create`, `styles-lifecycle`: create from an exposure edit, export and parse name/description/parameters, re-export after restart, import a public dtstyle, apply it to a different image, edit its description, export the revision and remove the style |
| Persistence and settings | `library-rating`, `library-tags`, `styles-create`, `preferences-persistence`: retained images, rating, tags, style usability and the milliseconds display preference after restart. Files are reread after restart rather than recovered from a verifier cache |
| Views and navigation | `library-culling`, `snapshot-restore`, `view-assistance`, `view-raw-clipping`: comparison/grid views, snapshots, split comparison and restoration, 400% zoom and fit, focus peaking, processed/raw clipping warnings and soft proofing |
| Processing parameters | `program-processing-01` through `13`: public XMP histories for 65 modules, scalar/enumeration controls and real built-in preset parameter sets. `program-compositing-01` through `04` cover six blend families and opacity. The 886 retained documents have distinct semantic outputs within their module/input group |
| Deterministic repair | `program-repair-01`, `program-liquify-01`: circular/elliptical clone, heal, blur and fill at distinct locations; discrete liquify displacement, expansion and contraction with different radii |
| Masks and local assets | `program-masks-01`, `program-raster-masks-01`, `program-composite-01`, `program-lookup-tables-01`, `program-watermarks-01`: circle/ellipse/gradient and parametric masks, upstream raster-mask reuse/inversion, external raster image channels, image overlay, local LUTs and text watermarks |
| RAW and sensor processing | `program-raw-01`, `program-raw-denoise-01`, `program-compatibility-01`: synthetic Bayer DNG demosaicing, color smoothing, highlight reconstruction, hot pixels, black/white levels, sensor denoising, raw chromatic-aberration correction, rotated sensor pixels and non-square pixel correction |
| Legacy processing and lens correction | `program-compatibility-01`: old local contrast, fill light, zone-system anchors, legacy spot cloning, stored color mapping and fixed-chroma transfer clusters, and manual lens vignette correction. Neutral or near-duplicate variants are omitted |
| Size and quality | `program-resize-01/02`, `program-resize-quality-01`: width/height bounds, aspect ratio, upscale/downscale, one-pixel rejection and interpolation. HQ uses large detailed images processed with resolution-sensitive modules; opposite HQ settings produce distinct outputs |
| Color profiles | `program-color-management-01`: sRGB, Adobe RGB, linear Rec.709/2020, XYZ and Display P3, including HDR input; an uploaded non-default linear Rec.2020 ICC profile. Ignoring the uploaded profile changes the observed pixels |
| Containers and inputs | `program-formats-01`, `program-input-formats-01`, `export-*`: JPEG, PNG, TIFF, WebP, AVIF, HEIF, JPEG XL/2000, OpenEXR, PPM/PFM, PDF and XCF, precision/compression/quality settings, independent pixel decoding and supported format reimport. GUI output containers are identified from bytes |
| Export behavior | `program-export-behavior-01`, `program-filename-patterns-01`, `export-*`: unique/replacement filenames, batch export, extension override, filename/date/metadata variables, GUI exports and resizing |
| Location and invalid input | `geotag-track`, `program-errors-01`: offline GPX correlation, empty/malformed/truncated documents and rejected outputs; malformed files must not create an export |

## Processing-module mapping

The parameter-document group covers `agx`, `ashift`, `atrous`, `basecurve`,
`basicadj`, `bilat`, `bilateral`, `bloom`, `blurs`, `borders`, `cacorrectrgb`,
`censorize`, `channelmixer`, `channelmixerrgb`, `clipping`, `colisa`,
`colorbalance`, `colorbalancergb`, `colorchecker`, `colorcontrast`,
`colorcorrection`, `colorequal`, `colorharmonizer`, `colorize`,
`colorreconstruct`, `colorzones`, `crop`, `defringe`, `denoiseprofile`,
`diffuse`, `dither`, `enlargecanvas`, `equalizer`, `exposure`, `filmic`,
`filmicrgb`, `flip`, `globaltonemap`, `graduatednd`, `grain`, `hazeremoval`,
`highpass`, `invert`, `levels`, `lowlight`, `lowpass`, `monochrome`,
`negadoctor`, `nlmeans`, `primaries`, `profile_gamma`, `rgbcurve`,
`rgblevels`, `shadhi`, `sharpen`, `sigmoid`, `soften`, `splittoning`,
`temperature`, `tonecurve`, `toneequal`, `tonemap`, `velvia`, `vibrance`
and `vignette`.

| Additional module names | Direct mapping |
| --- | --- |
| `demosaic`, `highlights`, `hotpixels`, `rawprepare` | `program-raw-01` |
| `rawdenoise` | `program-raw-denoise-01` |
| `retouch`, `liquify` | `program-repair-01`, `program-liquify-01` |
| `rasterfile`, `overlay` | `program-raster-masks-01`, `program-composite-01` |
| `lut3d`, `watermark` | `program-lookup-tables-01`, `program-watermarks-01` |
| `cacorrect`, `clahe`, `colormapping`, `colortransfer`, `lens`, `relight`, `rotatepixels`, `scalepixels`, `spots`, `zonesystem` | `program-compatibility-01` |
| `overexposed`, `rawoverexposed` | `view-assistance`, `view-raw-clipping` |
| `colorin`, `colorout`, `gamma` | Input/format roundtrips, color-management cases and every independently decoded image export |
| `finalscale`, `mask_manager` | Export size cases and public drawn/raster-mask documents respectively; these are pipeline helpers, not separately scored duplicate effects |

## Observation and comparison

Setup and checks use only the documented runtime operations: `upload`,
`mkdir`, `cli`, `documents`, `read_file`, `list_files`, `download`, `observe`
and lifecycle operations. No check reads a library database, private
configuration, process memory or hidden implementation state. The current
inventory and reread operations expose ordinary exchange documents even when
they have not changed since their previous download. A missing or replaced
file cannot be satisfied with cached bytes.

Images are independently decoded using Python/NumPy, ImageMagick,
imagecodecs (JPEG XL), OpenEXR, PDFium or the XCF tile parser. Projections
include dimensions, channels, an 8 by 6 grid of channel means, global
mean/standard deviation/percentiles and adjacent-pixel variation. Normalized
channel values allow 0.012 absolute error, with identical dimensions required.
One image projection is one assertion. Legacy color transfer uses a zero-variance
single source cluster: this retains luminance-distribution and chroma transfer
while eliminating the random target-cluster estimate from the result. Twelve
independent repeats per retained color agree; omitting the module or using the
opposite chroma differs materially. PDF pages must contain visible image
content; container metadata alone does not establish a valid export.

ExifTool identifies actual containers and their requested encoding properties.
JPEG quantization allows the greater of one quantizer unit or 20 percent;
WebP lossy/lossless coding is distinguished. Tests ignore optional absent
container fields, metadata ordering, timestamps, database IDs, compressed byte
streams, ICC creation dates and implementation paths. XMP checks retain the
requested metadata/module fields. Compression checks concern superseded
entries for the explicitly edited modules, not incidental history bookkeeping.
Style checks parse exported dtstyle documents and applied XMP parameters;
a typed search string cannot establish that a style exists.

GUI collection membership, selection, preferences and style-list presentation
are frontend outcomes. Backend checks do not require a particular accessible
role, label location or reference tooltip. Reference recipes can use upstream
controls; they are not requirements on independent implementations.

Before paired GUI observations, preparation waits for stable public
accessibility content. Reference recording fails if that state does not settle.
Focus flags and scrollbar numeric positions are omitted, and visible event-time
labels are normalized. Import/change/export/print timestamps, their derived
control references, transient notifications and scrolling geometry are
non-behavioral evidence fields; screenshots may differ in these details. Input
file times and synthetic capture times are fixed. Product startup retains the
shared generic AT-SPI readiness criterion.

Most GUI episodes allow 220 model calls, 3,000,000 tokens and 2,400 seconds of
non-provider wall time. Style creation, history lifecycle, auxiliary viewing
and collection rules allow 300 calls, 4,500,000 tokens and 3,000 seconds. The
style lifecycle allows 400 calls, 6,000,000 tokens and 3,600 seconds. Recorded
durations determine episode wall limits. The host bridge selects Kimi K3
with high effort; model identity is independent of the frozen bundle.

## Boundaries

Camera tethering, live capture, scanning, physical printing, colorimeter/monitor
calibration and device-specific GPU/OpenCL execution require hardware absent
from the offline environment. Network map tiles, online galleries, email,
cloud delivery and updater/download integrations require external services.
Neural restoration and AI object segmentation require external model weights
and inference runtimes. These dependencies are excluded; offline GPX,
portable PDF, deterministic masks and local repair remain covered.

Lua execution, arbitrary plug-in/library loading and external helper programs
are closed by the runtime contract. Paths are confined to the exchange folder.
Private-cache maintenance, physical removable-media loss and camera-specific
lens/sensor calibration catalogs are not substituted with synthetic private
state checks. Manual lens correction and synthetic sensor transforms are
covered without those catalogs. Proprietary camera photographs and every
camera-model style preset are not enumerated; all image inputs are generated.
Continuous tablet-pressure sampling is not an input channel; stored discrete
repair shapes, liquid-deformation control points and raster masks are covered.
