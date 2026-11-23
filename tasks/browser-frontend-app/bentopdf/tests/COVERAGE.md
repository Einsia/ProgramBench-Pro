# BentoPDF coverage

Task 1.0.0, BentoPDF 2.8.10 Simple. There are 94 GUI
episodes, 346 checkpoints and 1700 assertions:
**346 frontend and 1354 backend**. The executable
`suite.build()` and frozen `data/manifest.json` are authoritative.

[COVERAGE-MATRIX.md](COVERAGE-MATRIX.md) maps the pinned version's 115 tool
documents to concrete checkpoint goals and program observations. The detailed
branch map below distinguishes subfeatures on a shared page; having a tool
entry alone is not treated as coverage of every documented option. Parameters
are sampled at distinct behaviors and boundaries rather than at every possible
value or Cartesian combination.

## Feature map

| Family | Episodes | Checkpoints |
| --- | --- | ---: |
| annotation | `page-numbers`, `header-footer`, `header-bates`, `watermarks`, `image-watermarks` | 23 |
| color | `document-colors`, `color-tone`, `color-balance`, `scanner-effect` | 14 |
| conversion | `pdf-images`, `image-options`, `tiff`, `images-to-pdf`, `documents-to-pdf`, `ebooks-to-pdf`, `text-to-pdf`, `markdown`, `open-document-formats`, `more-formats`, `export-documents`, `heic`, `pdf-json-roundtrip`, `mobi`, `format-branches` | 52 |
| editing | `editor-shapes`, `edit-text-replace`, `edit-text-style`, `layers`, `stamps`, `annotations-more`, `viewer-annotations`, `text-edit-history`, `inserted-graphics` | 27 |
| extraction | `extract-text`, `ocr`, `extract-data`, `table-formats` | 13 |
| forms | `fill-forms`, `create-forms`, `more-form-fields`, `form-properties`, `form-roundtrip`, `form-editing`, `xfa-forms` | 28 |
| geometry | `n-up`, `page-size`, `divide-combine`, `poster`, `booklet`, `pdf-overlay`, `pdf-underlay`, `crop` | 29 |
| inspection | `page-dimensions`, `compare-pdfs`, `comparison-navigation` | 10 |
| metadata | `metadata-fields`, `metadata-cleanup`, `page-labels`, `bookmarks`, `bookmark-files`, `attachments`, `table-of-contents`, `edit-attachments`, `bookmark-editing`, `bookmark-structure` | 35 |
| optimization | `compression`, `optimization`, `rasterize`, `archival`, `compression-options` | 17 |
| organize | `merge`, `split`, `extract-delete`, `rotate`, `blank-duplex`, `organizer`, `multi-tool`, `alternate-and-package`, `blank-removal` | 38 |
| preferences | `language` | 1 |
| security | `passwords`, `permissions`, `sanitize-flatten`, `signatures`, `password-errors`, `signature-inputs` | 24 |
| validation | `validation` | 3 |
| workflow | `workflow-processing-1`, `workflow-processing-2`, `workflow-processing-3`, `workflow-files`, `workflow-composition`, `workflow-errors`, `workflow-templates` | 32 |

Every product action and observation uses the public runtime. No public HTTP
processing API or stable public JavaScript automation object exists in this
version. Backend checks therefore accompany GUI episodes and parse public
downloads or copied data. Workflow JSON is the product's actual import/export
format. Reference recipes may locate the pinned controls; candidate operations
are selected by the evaluator and may take any equivalent visible route.

## Documented branches

| Documented behavior | Direct coverage | Observation |
| --- | --- | --- |
| Highlight text and change its color; search PDF text | `viewer-annotations/{highlight,blue-highlight,search}` | Highlighted word and color; visible search results |
| Ink, translucent ink, comments and text insertion | `annotations-more/*` | Annotation type/style/content and inserted text |
| Rectangles, circles, lines and arrows; insert an image | `editor-shapes/*`, `inserted-graphics/editor-image` | Annotation geometry type and added image identity |
| Applied text and area redaction | `workflow-composition/{redact-text,redact-area}` | Target text absent from extraction and decoded streams; other content retained |
| Find all/one, case and whole-word matching; undo; size/color/italic/underline/strike | `edit-text-replace/*`, `text-edit-history/*`, `edit-text-style/*` | Mixed-case and substring distractors; character styles and local decoration geometry |
| Create/extract bookmarks, child nodes, rename, edit page target, reorder peers | `bookmarks/*`, `bookmark-editing/{rename,child}`, `bookmark-structure/{destination,reorder}` | Ordered hierarchy and destinations |
| Bookmark CSV/JSON import/export, search, single and batch style, delete/undo | `bookmark-files/*`, `bookmark-editing/{import-csv,import-json,search,style}`, `bookmark-structure/{batch-style,delete,undo}` | Parsed tree, color/style, visible filtered tree; undo has a deletion companion |
| All ten field tools; blank multipage forms; default/required/read-only/max-length/multiline | `create-forms/*`, `more-form-fields/*`, `form-properties/*`, `form-roundtrip/blank`, `form-editing/multiline` | AcroForm type, flags, defaults and dimensions; actual barcode image |
| Dropdown options, font/color/alignment, existing fields, radio grouping | `form-properties/{options,appearance}`, `form-editing/{existing,radio-group}` | Export/display options normalized; selected radio value and two widgets; changed field properties |
| Create → reopen → fill → save; existing field types; script-free XFA | `form-roundtrip/fill-created`, `fill-forms/*`, `xfa-forms/fill` | Saved values, XFA datasets and preserved base document |
| Condense levels, Photon, custom quality/DPI/threshold, grayscale | `compression/*`, `compression-options/*` | Actual image resolution and lossy quality, rasterization and grayscale |
| PDF/A-1b/2b/3b, duplicate fonts, TIFF LZW/Deflate | `archival/*`, `merge/fonts`, `tiff/*` | Archival identifiers/ICC/fonts/encryption; shared embedded font program; TIFF Compression tag |
| Genuine repair and deskew | `optimization/{repair,deskew}`, `workflow-processing-3/repair` | Damaged-header repair, valid cross-reference structure and residual text skew |
| Single/tiled/ranged text and image watermarks | `watermarks/*`, `image-watermarks/*` | Text or added pattern; image content, opacity/tiling effect and flattening output |
| Typed/drawn/uploaded signatures; flattened signature; visible and invisible cryptographic signing | `signatures/*`, `signature-inputs/*`, `inserted-graphics/visible-digital` | Added pattern identity, no editable annotation after flatten, full ByteRange/CMS verification, signer text |
| Correct/wrong PDF and certificate passwords; tampered signature | `password-errors/*`, `signatures/bad-certificate-password` | Error/validation state with positive companions; decrypted artifact and cryptographic checks |
| Workflow multistep chain, branch, two inputs, cycles and encryption passwords | `workflow-composition/*`, `workflow-errors/*` | Output page semantics per branch; dependency-bound errors |
| Workflow import/export, template save/reload/restart/delete | `workflow-files/*`, `workflow-templates/*` | Canonical graph independent of IDs/order, persistent restored graph, visible deletion |
| Comparison views, exports, pagination, text search, category filtering | `compare-pdfs/*`, `comparison-navigation/*` | Report page semantics and visible differences/filters |
| Copy metadata; attachment batches and binary content; table quoting/null cells | `metadata-cleanup/copy`, `attachments/extract-batch`, `table-formats/*` | Clipboard values, attachment bytes, CSV/JSON/Markdown cells |
| Genuine format branches | `open-document-formats/powerpoint`, `format-branches/*`, `xfa-forms/*` | PPTX, BIFF XLS, Outlook MSG, JPEG2000 mixed with PNG, XFA; additional baseline formats in the matrix |

## Checks and equivalence

PyMuPDF and pypdf inspect page count, effective dimensions, text/order, fields,
annotations, bookmarks, metadata, labels, layers, attachments and permissions.
General raster preservation uses a 6×8 grid at tolerance 16 channel levels
(20 for lossy output). This is only a preservation check: page numbers use
word positions, N-up uses borders and text geometry, posters use colored-region
geometry, underline/strike use local line height, tint uses a finer grid, and
layers use enabled state. Markdown exports compare actual word layout.

PDF/A checks the requested part/conformance identifier, an output ICC profile,
embedded fonts and absence of encryption. This is a targeted structural check,
not a claim of complete ISO validation. Compression checks actual image
dimensions and a quality proxy from JPEG quantization, with 18% relative
tolerance (at least 2 quantization units) rather than exact tables. Its fixtures
cross the processing threshold, and each adjacent compression-level
substitution is rejected. Font deduplication counts embedded program streams,
not the number of harmless font dictionaries referencing a shared stream.

CPDF JSON is independently reconstructed and inspected for content and page
appearance. SVG is parsed and rendered. Empty SVG or token-only fake JSON does
not pass. Signatures/stamps compare added content after normalizing its position
and size; plain input, an unrelated block and another person's name are rejected.
Flattened signatures must also have no editable annotations. Free-placement
fields, ink, comments and inserted images use their requested semantics and
preserved base content without imposing reference coordinates. Text highlighters
saved as Highlight or Ink are equivalent when word, position and color agree. Existing-field editing compares requested changed
attributes and retained field names/types; incidental upstream rewrites of
unrelated defaults or colors are not required.

Generated IDs/dates/object numbering, dictionary order and incidental filenames
are ignored. Numeric CSV cells accept equivalent spellings. Workflow graphs
ignore IDs and array order while retaining typed parameters and connections.
Multiple images use semantic multiset matching independent of filenames.
Choice options normalize equivalent string and export/display pair encoding.
Default geometry tolerance is 1.5 points. Empty business collections really
must be empty, rather than acting as a wildcard. Negative error/no-output cases
have positive companions. Table extraction checks whole row/column content,
including commas, quotes and empty cells, instead of token presence alone.

Each independent checkpoint resets product and browser data; persistence goals
explicitly reload or restart. Setup failures affect their own checkpoint. The
runtime restarts crashed products. After signing/stamping/creating fields, goals
that require visible saved results reopen the exported file using the public
`reuse_download` operation. Exporting via Blob and a same-origin HTTP attachment
are equivalent runtime routes; final document, file type, size and archive
validation still apply.

## Exclusions, upstream limits and representative coverage

- WPD, WPS, Apple Pages, Publisher and Visio conversion did not finish with
  valid upstream LibreOffice fixtures in this pinned WASM build, including
  unrestricted offline Chromium. Successful legacy imports on those routes
  are excluded. DOCX/RTF/XLSX/XLS/PPTX and ODT/ODS/ODP/ODG have direct cases.
- A valid stored CBR/RAR4 input is accepted by an independent archive reader,
  but the product routes it to a CBZ decoder and reports that it cannot
  recognize the archive. Successful CBR conversion is excluded; CBZ succeeds.
- Live TSA, online chain/revocation services, remote document URLs, remote
  resources and hardware-only browser functionality require unavailable peers.
  Offline certificate signing/validation and ordinary English OCR are covered.
- Executable WASM-provider configuration and PDF JavaScript/conditional scripts
  are unavailable under the shared runtime policy. Script-free XFA works and
  is tested; enabling arbitrary document scripts is not part of this task.
- The annotation editor can display a blank page background in the pinned
  upstream build, even without runtime restrictions. Shapes/ink/comments/text
  and images still export and are checked. Text highlights/search use the
  visible PDF.js viewer; applied redaction uses the public workflow builder.
- Booklet pre-rotation affects the preview but is ignored by upstream export.
  The case scores the real rotated preview, without duplicating unchanged
  output checks. Bookmark dragging supports peer reordering only; cross-parent
  dragging is not implemented by the pinned Sortable groups. Child creation
  and imported nested hierarchies are covered instead.
- The documented workflow encryption-order restriction is not enforced after
  localization changes the encryption node label. Placing processing after it
  can produce an empty-content PDF; that defective ordering is not required.
  A terminal encryption node and its missing-password error are tested, along
  with cycle detection. Passwords are intentionally not restored from graphs;
  goals enter them through the ordinary node controls.
- Flattened cropping passes JPEG bytes to a PNG decoder and reports an error
  upstream. Its error has a successful cropping companion; normal crop and
  rasterization succeed separately.
- The size-targeted/email compression pages are aliases for the same tool.
  French covers locale switching; translations and marketing pages are not
  separate semantic points. Ordinary zoom, resize handles, alternate presets,
  fonts and toolbar navigation are exercised by goals as needed, not each
  scored as redundant independent points. Not every import extension, every
  custom page size, every workflow node wrapper or all parameter combinations
  has a separate case; the matrix lists the actual inputs and observations.

## Budgets and execution

Per-episode call, token and active-time limits are defined in the manifest.
Episodes run serially. The verifier timeout covers their wall-clock limits
with startup and cleanup time. Program companions inspect the public output
of each GUI goal.

Third-party input attribution is in `fixtures/THIRD_PARTY.json`; the ebook
includes its license and attribution notice. The remaining inputs are
purpose-built documents and images, separate from the public exploration set.
