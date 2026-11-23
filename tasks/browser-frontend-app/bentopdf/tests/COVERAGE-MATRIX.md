# Pinned documentation traceability

Source: the 115 files under `docs/tools/` in BentoPDF v2.8.10, included in the
distributed source archive. Each row below identifies concrete tested behavior
and its observation. These are checkpoint-level mappings, not claims that an
entire page or every option is covered. The branch map and limits in
[COVERAGE.md](COVERAGE.md) explain representative parameters and exclusions.

## docs/tools/add-attachments.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `attachments/add-text` | Attach notes.txt to report.pdf and download the PDF with the embedded attachment. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-attachments |
| `attachments/add-json` | Attach data.json to report.pdf and download the PDF with the embedded attachment. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-attachments |

## docs/tools/add-blank-page.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `blank-duplex/blank-front` | Insert two blank pages before the first page of report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `blank-duplex/blank-middle` | Insert one blank page after page 2 of mixed.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `blank-duplex/blank-end` | Append three blank pages after page 4 of report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/add-page-labels.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `page-labels/roman-lower` | Apply roman lower page labels to all pages of report.pdf, starting at 1. | pdf-labels, pdf-count, pdf-text, pdf-raster |
| `page-labels/roman-upper` | Apply roman upper page labels to all pages of report.pdf, starting at 1. | pdf-labels, pdf-count, pdf-text, pdf-raster |
| `page-labels/letters-lower` | Apply letters lower page labels to all pages of report.pdf, starting at 1. | pdf-labels, pdf-count, pdf-text, pdf-raster |
| `page-labels/letters-upper` | Apply letters upper page labels to all pages of report.pdf, starting at 1. | pdf-labels, pdf-count, pdf-text, pdf-raster |
| `page-labels/prefix` | Apply decimal page labels with prefix "HBR-" and start value 10 to all pages of report.pdf. | pdf-labels, pdf-count, pdf-text, pdf-raster |

## docs/tools/add-stamps.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `stamps/image` | Place stamp.png in the blank middle of single.pdf using the image-stamp tool, then save the stamped PDF and reopen the exported file in Form Filler to inspect the result. | pdf-count, pdf-size, pdf-text, pdf-mark |

## docs/tools/add-watermark.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `watermarks/center` | Add the text watermark "HARBOR" at center on every page of report.pdf, with size 36, opacity 0.6 and angle 0. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-change |
| `watermarks/top-left` | Add the text watermark "HARBOR" at top left on every page of report.pdf, with size 36, opacity 0.6 and angle 0. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-change |
| `watermarks/bottom-right` | Add the text watermark "HARBOR" at bottom right on every page of report.pdf, with size 36, opacity 0.6 and angle 0. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-change |
| `watermarks/tiled` | Add a tiled text watermark "DRAFT" on report.pdf, using size 32, opacity 0.4 and the default -45 degree angle. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-change |
| `watermarks/range` | Add the text watermark "REVIEW" only to pages 2-3 of report.pdf, using size 32, angle 0 and opacity 0.8. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-change |
| `image-watermarks/single` | Apply stamp.png as a centered single image watermark on single.pdf, with scale 60% and opacity 0.7. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-mark |
| `image-watermarks/tiled` | Apply stamp.png as a tiled image watermark on single.pdf, with scale 60% and opacity 0.7. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-mark |
| `image-watermarks/flatten` | Apply stamp.png as a flattened centered single image watermark on single.pdf, with scale 60% and opacity 0.7. | pdf-count, pdf-size, pdf-raster, pdf-mark, pdf-rasterized |

## docs/tools/adjust-colors.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `color-tone/brightness` | On color.pdf, set the brightness adjustment to 25, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-tone/contrast` | On color.pdf, set the contrast adjustment to 30, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-tone/saturation` | On color.pdf, set the saturation adjustment to -70, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-tone/hue-shift` | On color.pdf, set the hue shift adjustment to 45, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-balance/temperature` | On color.pdf, set the temperature adjustment to 30, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-balance/tint` | On color.pdf, set the tint adjustment to 25, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-balance/gamma` | On color.pdf, set the gamma adjustment to 1.5, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |
| `color-balance/sepia` | On color.pdf, set the sepia adjustment to 70, leaving other adjustments at their defaults, and apply. | pdf-count, pdf-size, pdf-raster, pdf-color-grid |

## docs/tools/alternate-merge.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `alternate-and-package/alternate` | Select chapter-a.pdf and chapter-b.pdf together, in that order, and interleave their pages. Keep all remaining pages when one input ends. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `alternate-and-package/alternate-labels` | Interleave labels.pdf and chapter-b.pdf, preserving original page labels. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-labels |

## docs/tools/background-color.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `document-colors/background` | Change the background of color.pdf to pale blue #cce5ff. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |

## docs/tools/bates-numbering.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `header-bates/bates` | Add Bates numbers to report.pdf, starting from 125 with the default six-digit style. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-added-text |
| `header-bates/bates-batch` | Add sequential Bates numbers across chapter-a.pdf and chapter-b.pdf, starting at 97 and using the four-digit Bates style. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `header-bates/bates-custom` | Number report.pdf using the custom Bates template "HBR-[BATES]-[PAGE]", starting at 10, placed in the header right with Courier font at 14 points. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |

## docs/tools/bmp-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/bmp` | Convert chart.bmp to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/bookmark.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `bookmarks/add` | Add a bookmark named "Harbor overview" pointing to page 1 of report.pdf, then save the PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmarks/page-target` | Add a bookmark "Coral station" pointing to page 3 of report.pdf, then save. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmarks/extract-save` | Load the existing bookmarks from bookmarks.pdf into the editor and save the PDF with that hierarchy. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmark-files/csv` | Extract the existing bookmark hierarchy of bookmarks.pdf and export it as CSV. | csv |
| `bookmark-files/json` | Extract the existing bookmark hierarchy of bookmarks.pdf and export it as JSON. | bookmark-json |
| `bookmark-editing/rename` | Load the existing bookmarks in bookmarks.pdf. Rename Introduction to "Harbor Introduction". Save the PDF. Reopen the saved PDF in the bookmark tool and display its bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks, pdf-bookmark-style |
| `bookmark-editing/style` | Load the existing bookmarks in bookmarks.pdf. Make Introduction blue and bold italic. Save the PDF. Reopen the saved PDF in the bookmark tool and display its bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks, pdf-bookmark-style |
| `bookmark-editing/import-csv` | Open report.pdf, import bookmark-import.csv, then save the PDF with the imported bookmark hierarchy. Reopen the saved PDF in the bookmark tool and display its bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks, pdf-bookmark-style |
| `bookmark-editing/import-json` | Open report.pdf, import bookmark-import.json, then save the PDF with the imported bookmark hierarchy. Reopen the saved PDF in the bookmark tool and display its bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks, pdf-bookmark-style |
| `bookmark-editing/search` | Load the existing bookmarks from bookmarks.pdf and search them for "North". | Visible result only |
| `bookmark-editing/child` | Load the existing bookmarks in bookmarks.pdf, add a child bookmark named "Dock notes" beneath Introduction, pointing to page 1, and save. Reopen the saved PDF in the bookmark tool and display its bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmark-structure/destination` | Change the Introduction bookmark in bookmarks.pdf to point to page 3, retaining the other bookmarks. Save the PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmark-structure/reorder` | Move the North Shore bookmark and its child ahead of Introduction in bookmarks.pdf, keeping their existing hierarchy and page targets. Save. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmark-structure/batch-style` | Make every bookmark in bookmarks.pdf green and italic using batch editing, then save. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmark-style |
| `bookmark-structure/delete` | Delete Introduction from the existing bookmarks of bookmarks.pdf and save, preserving the other bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `bookmark-structure/undo` | Delete Introduction from the existing bookmarks of bookmarks.pdf, undo that deletion, then save the restored hierarchy. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |

## docs/tools/cbz-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `ebooks-to-pdf/comic` | Convert comic.cbz to PDF. | pdf-count, pdf-size, pdf-raster |

## docs/tools/change-permissions.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `permissions/print` | Set owner password "harbor-owner" for report.pdf and disable only allow printing, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |
| `permissions/copy` | Set owner password "harbor-owner" for report.pdf and disable only allow copying text, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |
| `permissions/modify` | Set owner password "harbor-owner" for report.pdf and disable only allow modifying, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |
| `permissions/annotate` | Set owner password "harbor-owner" for report.pdf and disable only allow annotating, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |
| `permissions/forms` | Set owner password "harbor-owner" for report.pdf and disable only allow filling forms, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |
| `permissions/assembly` | Set owner password "harbor-owner" for report.pdf and disable only allow document assembly, leaving the other permission switches enabled and the opening password empty. | pdf-permissions, pdf-encryption, pdf-text, pdf-raster |

## docs/tools/combine-single-page.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `divide-combine/combine-vertical` | Combine all pages of mixed.pdf into one vertical continuous page with zero spacing. | pdf-count, pdf-size, pdf-raster |
| `divide-combine/combine-horizontal` | Combine all pages of report.pdf into one horizontal page with 20 pixels of spacing and separator lines. | pdf-count, pdf-size, pdf-raster |

## docs/tools/compare-pdfs.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `compare-pdfs/side-by-side` | Compare chapter-a.pdf with chapter-b.pdf side by side, then export a split-view PDF of the comparison. | pdf-count, pdf-size, pdf-raster |
| `compare-pdfs/alternating` | Compare chapter-a.pdf with chapter-b.pdf and export the comparison as alternating pages. | pdf-count, pdf-size, pdf-raster |
| `compare-pdfs/left` | Compare chapter-a.pdf with chapter-b.pdf, then export the left document from the comparison. | pdf-count, pdf-size, pdf-raster |
| `comparison-navigation/search` | Compare chapter-a.pdf and chapter-b.pdf. Search the change list for "Alpha" and leave its matching change visible. | Visible result only |
| `comparison-navigation/overlay` | Compare chapter-a.pdf and chapter-b.pdf in Overlay view, then navigate to the next page of differences. | Visible result only |
| `comparison-navigation/filter` | Compare chapter-a.pdf and chapter-b.pdf on the first page, then hide the Headers category in the difference list. | Visible result only |

## docs/tools/compress-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `compression/light` | Compress photo.pdf using the Condense algorithm at the light level. | pdf-count, pdf-size, pdf-raster, pdf-image-size, pdf-compressed, pdf-image-quality |
| `compression/balanced` | Compress photo.pdf using the Condense algorithm at the balanced level. | pdf-count, pdf-size, pdf-raster, pdf-image-size, pdf-compressed, pdf-image-quality |
| `compression/aggressive` | Compress photo.pdf using the Condense algorithm at the aggressive level. | pdf-count, pdf-size, pdf-raster, pdf-image-size, pdf-compressed, pdf-image-quality |
| `compression/extreme` | Compress photo.pdf using the Condense algorithm at the extreme level. | pdf-count, pdf-size, pdf-raster, pdf-image-size, pdf-compressed, pdf-image-quality |
| `compression-options/photon` | Compress photo.pdf using the Photon algorithm and Balanced level. | pdf-count, pdf-size, pdf-raster, pdf-rasterized, pdf-image-size, pdf-image-quality |
| `compression-options/custom` | Compress photo.pdf with Condense, custom output quality 40, target DPI 100 and processing threshold 120 DPI. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-image-size, pdf-image-quality |
| `compression-options/gray` | Compress photo.pdf with Condense at Balanced level and convert to grayscale. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-image-color |

## docs/tools/crop-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `crop/margin` | Crop single.pdf using the initial crop selection (remove the outer ten percent on every edge), then download it. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `crop/flat` | Try cropping single.pdf with Flattening Crop enabled, using the initial selection. | no-download |
| `crop/all` | Crop every page of report.pdf using the initial crop selection, applying it to all pages. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/csv-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `documents-to-pdf/csv` | Convert data.csv to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/delete-pages.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-delete/delete` | Delete pages 2 and 4 from report.pdf and download the remainder. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `extract-delete/delete-range` | Delete pages 2-4 from mixed.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/deskew-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `optimization/deskew` | Straighten the tilted scan in skewed.pdf using the default deskew settings. | pdf-count, pdf-size, pdf-raster, pdf-deskew-angle |

## docs/tools/digital-sign-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `signatures/digital` | Digitally sign single.pdf with harbor.p12 (certificate password "harbor-pass"). Use reason "Harbor approval", location "Cedar Station" and contact "ada@example.org". Keep the visible signature disabled. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-digital-signature |
| `signatures/bad-certificate-password` | Try to unlock harbor.p12 with the incorrect certificate password "wrong-pass" after loading single.pdf. | no-download |
| `inserted-graphics/visible-digital` | Digitally sign single.pdf with harbor.p12 (password harbor-pass), reason "Harbor approval". Enable the visible signature using the default signer-name text and first-page placement. Download the signed PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-digital-signature, pdf-added-text |

## docs/tools/divide-pages.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `divide-combine/vertical` | Divide every page of report.pdf into left and right halves. | pdf-count, pdf-size, pdf-raster |
| `divide-combine/horizontal` | Divide every page of report.pdf into top and bottom halves. | pdf-count, pdf-size, pdf-raster |
| `divide-combine/selected` | Divide only pages 2-3 of report.pdf into left and right halves, keeping other pages. | pdf-count, pdf-size, pdf-raster |

## docs/tools/duplex-collate.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `blank-duplex/duplex-reversed` | Collate report.pdf as a duplex scan with the front block ending after page 2 and the back block reversed. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `blank-duplex/duplex-kept` | Collate report.pdf as a duplex scan split after page 2, keeping the back block in its existing order. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/edit-attachments.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `edit-attachments/remove-all` | Remove all attachments from attachments.pdf and save the updated PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-attachments |

## docs/tools/edit-metadata.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `metadata-fields/title` | Set the title of report.pdf to "Harbor Archive" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |
| `metadata-fields/author` | Set the author of report.pdf to "Ada Finch and Sam Reed" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |
| `metadata-fields/subject` | Set the subject of report.pdf to "Winter coastal survey" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |
| `metadata-fields/keywords` | Set the keywords of report.pdf to "harbor, winter, research" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |
| `metadata-fields/creator` | Set the creator of report.pdf to "Harbor Studio" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |
| `metadata-fields/producer` | Set the producer of report.pdf to "Archive Pipeline" and save the updated PDF. | pdf-metadata, pdf-text, pdf-raster, pdf-count |

## docs/tools/edit-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `editor-shapes/rectangle` | Open single.pdf in the PDF Editor. Add one rectangle annotation in the blank middle area of the page, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-annotation-details |
| `editor-shapes/circle` | Open single.pdf in the PDF Editor. Add one circle annotation in the blank middle area of the page, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-annotation-details |
| `editor-shapes/line` | Open single.pdf in the PDF Editor. Add one line annotation in the blank middle area of the page, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-annotation-details |
| `editor-shapes/arrow` | Open single.pdf in the PDF Editor. Add one arrow annotation in the blank middle area of the page, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-annotation-details |
| `annotations-more/ink` | Add one freehand ink stroke in the blank middle of single.pdf, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-annotation-details |
| `annotations-more/ink-highlight` | Add one freehand highlighter stroke in the blank middle of single.pdf, then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-annotation-details |
| `annotations-more/comment` | Place a comment in the blank middle of single.pdf with the exact text "Inspect the eastern dock", then download the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-comment-content |
| `annotations-more/free-text` | Add a text annotation reading "Dock inspected" in the blank middle of single.pdf, then download it. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-added-text |
| `inserted-graphics/editor-image` | Insert stamp.png as an image in the blank middle of single.pdf using the PDF editor, then download the edited document. | pdf-count, pdf-size, pdf-text, pdf-mark, pdf-base-preserved |

## docs/tools/email-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `documents-to-pdf/email` | Convert mail.eml to PDF with the default settings. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `format-branches/msg` | Convert harbor.msg to PDF, preserving the message headers and body. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/epub-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `ebooks-to-pdf/epub` | Convert book.epub to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/excel-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `documents-to-pdf/xlsx` | Convert stations.xlsx to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `format-branches/xls` | Convert harbor.xls to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/extract-attachments.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-data/attachments` | Extract both embedded attachments from attachments.pdf. | archive, archive-names, text-contains |
| `attachments/extract-batch` | Extract attachments from attachments.pdf and binary-attachments.pdf together, including the embedded PNG. | archive, archive-names, attachment-bytes |

## docs/tools/extract-images.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-data/images` | Extract the embedded images from color.pdf and download all extracted images as a ZIP. | image-size, image-content, archive |

## docs/tools/extract-pages.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-delete/extract` | Extract pages 2 and 4 from report.pdf using the Extract Pages tool. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `extract-delete/extract-range` | Extract pages 2-5 from mixed.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `validation/valid` | Extract page 2 of report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `validation/outside-range` | Try to extract page 99 from the four-page report.pdf. | no-download |
| `validation/malformed` | Try to open broken.pdf, which is an incomplete PDF file. | no-download |

## docs/tools/extract-tables.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-data/tables` | Extract the table from table.pdf with the default output format. | text-contains, archive |
| `table-formats/csv` | Extract the table in quoted-table.pdf as CSV, preserving quoted text, commas and the empty cargo cell. | table-cells |
| `table-formats/json` | Extract the table in quoted-table.pdf as JSON, preserving quoted text, commas and the empty cargo cell. | table-cells |
| `table-formats/markdown` | Extract the table in quoted-table.pdf as Markdown, preserving quoted text, commas and the empty cargo cell. | table-cells |

## docs/tools/fb2-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `ebooks-to-pdf/fb2` | Convert book.fb2 to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/fix-page-size.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `page-size/a4` | Resize all pages of mixed.pdf to A4, using portrait orientation and Fit mode. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `page-size/letter` | Resize all pages of mixed.pdf to Letter, using landscape orientation and Fit mode. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `page-size/legal` | Resize all pages of mixed.pdf to Legal, using portrait orientation and Fit mode. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `page-size/a3` | Resize all pages of mixed.pdf to A3, using landscape orientation and Fit mode. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `page-size/a5` | Resize all pages of mixed.pdf to A5, using auto orientation and Fit mode. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `page-size/fill` | Resize all pages of mixed.pdf to A4 portrait using Fill (Crop) mode. | pdf-count, pdf-size, pdf-raster |

## docs/tools/flatten-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `sanitize-flatten/flatten` | Flatten the form fields of forms.pdf into static page content. | pdf-forms, pdf-count, pdf-size, pdf-raster |

## docs/tools/font-to-outline.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `optimization/font-outline` | Convert fonts in report.pdf into outlines. | pdf-count, pdf-size, pdf-raster, pdf-fonts-outlined |

## docs/tools/form-creator.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `create-forms/text` | Open single.pdf in the form creator. Add one text field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-field-types, pdf-base-preserved |
| `create-forms/checkbox` | Open single.pdf in the form creator. Add one checkbox field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-field-types, pdf-base-preserved |
| `create-forms/dropdown` | Open single.pdf in the form creator. Add one dropdown field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-field-types, pdf-base-preserved |
| `create-forms/date` | Open single.pdf in the form creator. Add one date field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-field-types, pdf-base-preserved |
| `more-form-fields/radio` | Open single.pdf in the form creator. Add one radio field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-field-types |
| `more-form-fields/list` | Open single.pdf in the form creator. Add one list field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-field-types |
| `more-form-fields/button` | Open single.pdf in the form creator. Add one button field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-field-types |
| `more-form-fields/signature` | Open single.pdf in the form creator. Add one signature field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-field-types |
| `more-form-fields/image` | Open single.pdf in the form creator. Add one image field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-field-types |
| `more-form-fields/barcode` | Open single.pdf in the form creator. Add one barcode field in the blank middle of the page and download the PDF form, then reopen the exported file in Form Filler to inspect the field. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-barcode-content |
| `form-properties/default` | Open single.pdf, add a text field named "visitor", set its default value to "Cedar Harbor", and download the form. Reopen the saved form in Form Filler. | pdf-count, pdf-size, pdf-widget-state, pdf-base-preserved |
| `form-properties/required` | Open single.pdf, add a text field named "visitor", make it required, and download the form. Reopen the saved form in Form Filler. | pdf-count, pdf-size, pdf-widget-state, pdf-base-preserved |
| `form-properties/readonly` | Open single.pdf, add a text field named "visitor", set its value to "Read-only note" and make it read-only, and download the form. Reopen the saved form in Form Filler. | pdf-count, pdf-size, pdf-widget-state, pdf-base-preserved |
| `form-properties/length` | Open single.pdf, add a text field named "visitor", limit its text to 12 characters, and download the form. Reopen the saved form in Form Filler. | pdf-count, pdf-size, pdf-widget-state, pdf-base-preserved |
| `form-properties/appearance` | Open single.pdf, add a text field named "visitor", use font size 18, text color #2244aa and centered alignment, and download the form. Reopen the saved form in Form Filler. | pdf-count, pdf-size, pdf-widget-state, pdf-base-preserved |
| `form-properties/options` | Open single.pdf and add a dropdown named "port" with exactly the options Cedar, Maple and Elm, defaulting to Maple. Download the form and reopen it in Form Filler. | pdf-widget-state, pdf-base-preserved |
| `form-roundtrip/fill-created` | Create a text field named visitor (tooltip Visitor) on single.pdf. Save the form, reopen its download in Form Filler, enter "Ada Finch" in that field and save the filled form. | pdf-field-value, pdf-base-preserved |
| `form-roundtrip/blank` | Create a new A5 PDF form with two pages, add one text field on the second page, and download it. | pdf-count, pdf-size, pdf-widget-pages |
| `form-editing/existing` | Edit the existing visitor field in forms.pdf: set its value to "Ada Finch" and make it read-only. Keep the other fields, save the form and reopen it in Form Filler. | pdf-widget-state, pdf-base-preserved |
| `form-editing/multiline` | Create a text field named notes on single.pdf and enable Multi-line, then save and reopen the form in Form Filler. | pdf-widget-state, pdf-base-preserved |
| `form-editing/radio-group` | Create a radio group named travel on single.pdf with exactly two options, Boat and Bus. Select Bus as the default, save and reopen the form in Form Filler. | pdf-radio-group, pdf-base-preserved |

## docs/tools/form-filler.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `fill-forms/name` | Open forms.pdf. Fill Visitor name with "Sam Reed". Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `fill-forms/date` | Open forms.pdf. Fill Visit date with "2026-01-15". Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `fill-forms/notes` | Open forms.pdf. Fill Notes with exactly two lines: "Arriving by boat." and "Two passengers.". Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `fill-forms/member` | Open forms.pdf. Check the Member checkbox. Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `fill-forms/destination` | Open forms.pdf. Choose Maple as the Destination. Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `fill-forms/travel` | Open forms.pdf. Choose Bus as the Travel mode. Save the filled form as PDF. | pdf-forms, pdf-count, pdf-size, pdf-raster |
| `viewer-annotations/highlight` | In the viewer, highlight the word "Harbor" in the heading of single.pdf in yellow, then save the PDF. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-highlight-text |
| `viewer-annotations/blue-highlight` | Highlight the word "Harbor" in the heading of single.pdf in blue, then save. | pdf-count, pdf-size, pdf-text, pdf-base-preserved, pdf-highlight-text |
| `viewer-annotations/search` | Find the word "Harbor" in single.pdf and leave the search matches visible. | Visible result only |
| `xfa-forms/fill` | Open harbor-xfa.pdf, fill Visitor name with "Ada Finch", and save the completed XFA form. | pdf-xfa-value |

## docs/tools/header-footer.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `header-footer/header-left` | Add the text "Harbor Survey" in the header left of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-footer/header-center` | Add the text "Cedar Station" in the header center of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-footer/header-right` | Add the text "Archive Copy" in the header right of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-footer/footer-left` | Add the text "Prepared by Ada" in the footer left of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-footer/footer-center` | Add the text "Internal Review" in the footer center of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-footer/footer-right` | Add the text "End of Notes" in the footer right of every page in report.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-position |
| `header-bates/selected` | Add "Harbor Survey" in the header center and "Archive Copy" in the footer right of only pages 2-3 of report.pdf, using size 16 and blue #2244aa. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |

## docs/tools/heic-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `heic/convert` | Convert chart.heic to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/image-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `more-formats/gif` | Convert chart.gif to PDF with the default settings. | pdf-count, pdf-size, pdf-raster |
| `more-formats/ppm` | Convert chart.ppm to PDF with the default settings. | pdf-count, pdf-size, pdf-raster |
| `format-branches/jpeg2000` | Convert stamp.jp2 followed by chart.png to one PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/index.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `language/french` | Switch the application interface to French and leave the tools catalog visible. | Visible result only |

## docs/tools/invert-colors.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `document-colors/invert` | Invert the colors in color.pdf. | pdf-count, pdf-size, pdf-raster |

## docs/tools/jpg-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/jpg` | Convert chart.jpg to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/json-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-json-roundtrip/import` | Convert pdf-structure.json, a PDF exported as JSON, back into a PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/linearize-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `optimization/linearize` | Linearize report.pdf for fast web viewing. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-linearized |

## docs/tools/markdown-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `markdown/document` | Import notes.md into the Markdown editor and export it as PDF. | pdf-count, pdf-size, pdf-raster, pdf-word-layout |
| `markdown/typed` | Replace the Markdown with the exact text below and export as PDF. ```markdown # Cedar Harbor **42 boats** arrived at noon. - Timber - Grain ``` | pdf-count, pdf-size, pdf-raster, pdf-word-layout |

## docs/tools/merge-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `merge/documents` | Merge chapter-a.pdf followed by chapter-b.pdf into one PDF, using all pages. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `merge/ranges` | Merge pages 2-3 of chapter-a.pdf followed by page 1 of chapter-b.pdf into one PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |
| `merge/labels` | Merge labels.pdf followed by chapter-b.pdf and preserve original page labels. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-labels |
| `merge/fonts` | Merge font-1.pdf and font-2.pdf with duplicate-font removal enabled. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-font-reuse |

## docs/tools/mobi-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `mobi/ebook` | Convert raven.mobi to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/n-up-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `n-up/two` | Place two pages per sheet from report.pdf on Letter paper, with the default automatic orientation. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `n-up/four-landscape` | Place four pages per sheet from mixed.pdf on A4 paper in landscape orientation. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `n-up/nine` | Place nine pages per sheet from mixed.pdf on A3 paper. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `n-up/borders` | Create a four-up PDF from report.pdf on Letter paper with borders around the placed pages. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-line-layout, pdf-word-layout |
| `n-up/no-margins` | Create a four-up PDF from report.pdf on Letter paper with margins disabled. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-word-layout, pdf-line-layout |

## docs/tools/ocr-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `ocr/english-text` | Run English OCR on scan.pdf with default resolution, then download the recognized text. | text-contains, download-format |
| `ocr/searchable` | Run English OCR on scan.pdf, then download the searchable PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-rasterized |

## docs/tools/odg-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `open-document-formats/odg` | Convert drawing.odg to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/odp-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `open-document-formats/odp` | Convert slides.odp to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/ods-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `open-document-formats/ods` | Convert stations.ods to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/odt-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `open-document-formats/odt` | Convert report.odt to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/organize-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `organizer/duplicate` | Duplicate page 2 of report.pdf and save the result. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `organizer/delete` | Delete page 2 of report.pdf in the organizer and save the result. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `organizer/reorder` | Reorder report.pdf to pages 4, 1, 3, 2 and save. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `organizer/repeat-order` | Set the page order of report.pdf to 2, 2, 4, 1, repeating page 2, and save. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/page-dimensions.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `page-dimensions/points` | Inspect mixed.pdf page dimensions in points, then export the measurements as CSV. | csv |
| `page-dimensions/inches` | Inspect mixed.pdf page dimensions in inches, then export the measurements as CSV. | csv |
| `page-dimensions/millimeters` | Inspect mixed.pdf page dimensions in millimeters, then export the measurements as CSV. | csv |
| `page-dimensions/pixels` | Inspect mixed.pdf page dimensions in pixels, then export the measurements as CSV. | csv |

## docs/tools/page-numbers.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `page-numbers/bottom-center` | Add page numbers to report.pdf at bottom center, with the default font and number-only format. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-number-layout |
| `page-numbers/top-left` | Add page numbers to report.pdf at top left, with the default font and number-only format. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-number-layout |
| `page-numbers/top-right` | Add page numbers to report.pdf at top right, with the default font and number-only format. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-number-layout |
| `page-numbers/bottom-right` | Add page numbers to report.pdf at bottom right, with the default font and number-only format. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-number-layout |
| `page-numbers/total` | Add bottom-center page numbers to report.pdf in the format current page / total pages, with 18-point text colored #cc2222. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style, pdf-number-layout |

## docs/tools/pdf-booklet.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `booklet/standard` | Create a 1×2 booklet from report.pdf on Letter paper with no pre-rotation. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-word-layout |
| `booklet/a4` | Create a 1×2 booklet from bookmarks.pdf on A4 paper. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `booklet/clockwise` | Preview report.pdf as a Letter booklet with pages pre-rotated clockwise by 90 degrees. | Visible result only |
| `booklet/four-up` | Create a 2×2 booklet layout from bookmarks.pdf on A3 paper. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/pdf-layers.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `layers/add` | Load layers.pdf, add a layer named "Review", and download the modified PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-layers |
| `layers/hide` | Load layers.pdf, hide only the Survey markers layer, then download the modified PDF. | pdf-count, pdf-size, pdf-raster, pdf-layer-state |

## docs/tools/pdf-multi-tool.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `multi-tool/rotate-all` | Rotate all four pages of report.pdf clockwise and export. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `multi-tool/duplicate-all` | Duplicate all four pages of report.pdf and export the eight-page result. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `multi-tool/add-blank` | Add a blank page to report.pdf and export the result. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `multi-tool/undo-redo` | Rotate all pages of report.pdf clockwise, undo the rotation, redo it, then export. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `multi-tool/selected` | Select only page 2 of report.pdf and download the selected page. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/pdf-to-bmp.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-images/bmp` | Convert every page of chapter-b.pdf to BMP images with default settings. | image-format, image-size, image-content, archive |

## docs/tools/pdf-to-cbz.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `image-options/cbz` | Convert chapter-b.pdf into a comic-book CBZ archive with the default settings. | image-format, image-size, image-content, archive |

## docs/tools/pdf-to-csv.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-data/csv` | Convert the table in table.pdf to CSV. | text-contains, archive |

## docs/tools/pdf-to-excel.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `export-documents/excel` | Convert the table in table.pdf to Excel. | office-text, download-format |

## docs/tools/pdf-to-greyscale.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `document-colors/grayscale` | Convert color.pdf to greyscale. | pdf-count, pdf-size, pdf-raster |

## docs/tools/pdf-to-jpg.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-images/jpg` | Convert every page of chapter-b.pdf to JPEG images with default settings. | image-format, image-size, image-content, archive |
| `image-options/jpeg-low` | Convert color.pdf to JPEG with image quality 0.3. | image-format, image-size, image-content, archive |

## docs/tools/pdf-to-json.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `export-documents/json` | Export single.pdf to JSON using the default settings. | json-structure, download-format |

## docs/tools/pdf-to-markdown.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-text/markdown` | Convert report.pdf into Markdown. | text-contains, download-format |

## docs/tools/pdf-to-pdfa.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `archival/pdfa1` | Convert report.pdf using the PDF/A-1b preset. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-archival |
| `archival/pdfa2` | Convert report.pdf using the PDF/A-2b preset. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-archival |
| `archival/pdfa3` | Convert report.pdf using the PDF/A-3b preset. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-archival |

## docs/tools/pdf-to-png.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-images/png` | Convert every page of chapter-b.pdf to PNG images with default settings. | image-format, image-size, image-content, archive |
| `image-options/png-scale` | Convert chapter-b.pdf to PNG images at scale 1. | image-format, image-size, image-content, archive |

## docs/tools/pdf-to-svg.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-text/svg` | Convert each page of chapter-b.pdf to SVG. | archive, svg-content |

## docs/tools/pdf-to-text.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-text/text` | Extract plain text from report.pdf. | text, download-format |
| `extract-text/batch` | Extract text from chapter-a.pdf and chapter-b.pdf together. | text, archive |

## docs/tools/pdf-to-tiff.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `tiff/lzw` | Convert color.pdf to TIFF at 72 DPI with lzw compression and rgb color mode. | image-format, image-size, image-content, image-frames, image-compression |
| `tiff/deflate` | Convert color.pdf to TIFF at 72 DPI with deflate compression and rgb color mode. | image-format, image-size, image-content, image-frames, image-compression |
| `tiff/mono` | Convert color.pdf to TIFF at 72 DPI with ccittfax4 compression and bw color mode. | image-format, image-size, image-content, image-frames, image-compression |
| `tiff/gray` | Convert color.pdf to TIFF at 72 DPI with lzw compression and greyscale color mode. | image-format, image-size, image-content, image-frames, image-compression |

## docs/tools/pdf-to-webp.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-images/webp` | Convert every page of chapter-b.pdf to WebP images with default settings. | image-format, image-size, image-content, archive |
| `image-options/webp-low` | Convert color.pdf to WebP with image quality 0.4. | image-format, image-size, image-content, archive |

## docs/tools/pdf-to-word.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `export-documents/word` | Convert report.pdf to a Word DOCX document. | office-xml, download-format |

## docs/tools/pdf-to-zip.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `alternate-and-package/zip` | Package chapter-a.pdf and chapter-b.pdf together into a ZIP archive. | pdf-count, pdf-size, pdf-text, pdf-raster, archive-names |

## docs/tools/pdf-workflow.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `workflow-processing-1/rotate` | Import workflow-rotate.json, supply mixed.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-1/reverse` | Import workflow-reverse.json, supply mixed.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-1/extract` | Import workflow-extract.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-1/delete` | Import workflow-delete.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-1/blank` | Import workflow-blank.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-1/metadata` | Import workflow-metadata.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-metadata |
| `workflow-processing-2/nup` | Import workflow-nup.json, supply mixed.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-2/watermark` | Import workflow-watermark.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-mark |
| `workflow-processing-2/flatten` | Import workflow-flatten.json, supply forms.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-raster, pdf-forms |
| `workflow-processing-2/annotations` | Import workflow-annotations.json, supply annotated.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-annotations |
| `workflow-processing-2/linearize` | Import workflow-linearize.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-linearized |
| `workflow-processing-2/booklet` | Import workflow-booklet.json, supply bookmarks.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-3/background` | Import workflow-background.json, supply color.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-3/sanitize` | Import workflow-sanitize.json, supply annotated.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-annotations, pdf-links |
| `workflow-processing-3/repair` | Import workflow-repair.json, supply repairable.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-repaired |
| `workflow-processing-3/page-numbers` | Import workflow-page-numbers.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-3/split` | Import workflow-split.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-processing-3/crop` | Import workflow-crop.json, supply report.pdf to its PDF Input node, and run the workflow without changing its processing options. | pdf-count, pdf-size, pdf-raster |
| `workflow-files/roundtrip` | Import workflow-rotate.json and export the loaded workflow as JSON. | workflow-json |
| `workflow-files/crop-roundtrip` | Import workflow-crop.json and export the loaded workflow as JSON. | workflow-json |
| `workflow-files/save-reload` | Import workflow-rotate.json, save it as a template named "Harbor rotation", reload the page, load that template, then export it. | workflow-json |
| `workflow-composition/chain` | Import flow-chain.json, supply report.pdf to its PDF Input node, and execute the graph without changing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-word-layout |
| `workflow-composition/redact-text` | Import flow-redact-text.json, supply single.pdf to its PDF Input node, and execute the graph without changing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-redacted |
| `workflow-composition/redact-area` | Import flow-redact-area.json, supply single.pdf to its PDF Input node, and execute the graph without changing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-redacted |
| `workflow-composition/branch` | Import flow-branch.json, supply report.pdf to its PDF Input node, and execute the graph without changing options. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-word-layout |
| `workflow-composition/merge` | Import flow-merge.json. Supply chapter-a.pdf to the upper PDF Input and chapter-b.pdf to the lower PDF Input. Run the graph. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-errors/valid` | Import workflow-rotate.json, supply report.pdf, and execute it. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `workflow-errors/encrypted` | Import flow-encrypt.json. Set the encryption node user password to "harbor-secret" and owner password to "harbor-owner", supply report.pdf to PDF Input, and run the graph. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |
| `workflow-errors/cycle` | Import flow-cycle.json, supply report.pdf, and try running the graph. | no-download |
| `workflow-errors/missing-password` | Import flow-encrypt.json, supply report.pdf, and try running the graph. Leave the encryption passwords empty. | no-download |
| `workflow-templates/restart` | Import workflow-rotate.json and save it as "Harbor rotation". Restart the application, reopen Workflow Builder, load that template and export it. | workflow-json |
| `workflow-templates/delete` | Import workflow-rotate.json and save it as "Harbor rotation", then delete that saved template. Leave the template list open. | Visible result only |

## docs/tools/png-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/png` | Convert chart.png to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/posterize-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `poster/two` | Posterize single.pdf into one row and two columns on A4 output pages. | pdf-count, pdf-size, pdf-raster, pdf-color-geometry |
| `poster/four` | Posterize single.pdf into two rows and two columns on Letter pages. | pdf-count, pdf-size, pdf-raster |
| `poster/overlap` | Posterize single.pdf into two columns on A4 pages with 18 points of overlap. | pdf-count, pdf-size, pdf-raster, pdf-color-geometry |
| `poster/selected` | Posterize only page 2 of report.pdf into two rows and one column on A5 pages. | pdf-count, pdf-size, pdf-raster |

## docs/tools/powerpoint-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `open-document-formats/powerpoint` | Convert harbor.pptx to PDF using the PowerPoint conversion tool. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/prepare-pdf-for-ai.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `export-documents/ai` | Extract report.pdf for an AI pipeline using the default format. | json-page-text, download-format |

## docs/tools/protect-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `passwords/encrypt` | Encrypt report.pdf with the opening password "sailboat" and owner password "harbor-owner". | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |
| `passwords/user-only` | Encrypt chapter-b.pdf with the opening password "Cedar-2026" and leave the optional owner password empty. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |

## docs/tools/psd-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `more-formats/psd` | Convert chart.psd to PDF. | pdf-count, pdf-size, pdf-raster |

## docs/tools/pub-to-pdf.md

Successful conversion is excluded after the pinned offline WASM converter did not finish valid legacy inputs. See COVERAGE limits.

## docs/tools/rasterize-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `rasterize/screen` | Rasterize color.pdf at 72 DPI with PNG images. | pdf-count, pdf-size, pdf-raster, pdf-rasterized, pdf-image-size |
| `rasterize/print` | Rasterize color.pdf at 150 DPI with JPEG images. | pdf-count, pdf-size, pdf-raster, pdf-rasterized, pdf-image-size |
| `rasterize/gray` | Rasterize color.pdf at 72 DPI in grayscale. | pdf-count, pdf-size, pdf-raster, pdf-rasterized, pdf-image-size |

## docs/tools/remove-annotations.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `sanitize-flatten/annotations` | Remove annotations from annotated.pdf. | pdf-annotations, pdf-text, pdf-raster, pdf-count |

## docs/tools/remove-blank-pages.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `blank-removal/detected` | Detect blank pages in blank-pages.pdf using the default sensitivity, then remove all detected blank pages. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/remove-metadata.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `metadata-cleanup/remove` | Remove metadata from report.pdf. | pdf-metadata, pdf-text, pdf-raster, pdf-count |

## docs/tools/remove-restrictions.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `passwords/restrictions` | Remove restrictions from restricted.pdf. It has no opening password; its owner password is "harbor-owner" if requested. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |

## docs/tools/repair-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `optimization/repair` | Repair the damaged header and cross-reference offsets of repairable.pdf and download the repaired PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-repaired |

## docs/tools/reverse-pages.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `extract-delete/reverse` | Reverse the page order of mixed.pdf. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/rotate-custom.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `rotate/custom-angle` | Rotate all pages of report.pdf by 30 degrees using custom rotation. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `rotate/custom-negative` | Rotate all pages of single.pdf by -15 degrees using custom rotation. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/rotate-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `rotate/clockwise` | Rotate all pages of mixed.pdf clockwise by 90 degrees. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `rotate/counterclockwise` | Rotate all pages of report.pdf counter-clockwise by 90 degrees. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `rotate/half-turn` | Rotate all pages of report.pdf by 180 degrees. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/rtf-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `documents-to-pdf/rtf` | Convert note.rtf to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/sanitize-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `sanitize-flatten/sanitize-annotations` | Sanitize annotated.pdf with the default options. | pdf-annotations, pdf-links, pdf-metadata, pdf-text, pdf-raster |
| `sanitize-flatten/sanitize-attachments` | Sanitize attachments.pdf with the default options. | pdf-attachments, pdf-metadata, pdf-text, pdf-raster |

## docs/tools/scanner-effect.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `scanner-effect/default` | Apply the default scanner effect to color.pdf. | pdf-count, pdf-size, pdf-raster, pdf-rasterized |
| `scanner-effect/grayscale` | Apply a grayscale scanner effect to color.pdf with the default noise and rotation settings. | pdf-count, pdf-size, pdf-raster, pdf-rasterized |

## docs/tools/sign-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `signatures/typed` | Add a typed signature "Ada Finch" to the blank middle of single.pdf and save the signed PDF, then reopen the exported file in Form Filler to inspect it. | pdf-count, pdf-size, pdf-text, pdf-mark |
| `signatures/typed-flat` | Add a typed signature "Ada Finch" to single.pdf, enable flattening, and save the signed PDF, then reopen the exported file in Form Filler to inspect it. | pdf-count, pdf-size, pdf-mark, pdf-text |
| `signature-inputs/draw` | Draw a simple V-shaped signature (one stroke down to a low point, then back up), describe it as "Harbor V", add it to single.pdf and save. Reopen the exported PDF in Form Filler. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-mark |
| `signature-inputs/image` | Use stamp.png as an image signature on single.pdf with description "Harbor symbol", save it and reopen the exported PDF in Form Filler. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-mark |

## docs/tools/split-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `split/combined-range` | From report.pdf, extract pages 1-2 and 4 into one combined PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `split/separate-ranges` | Split report.pdf into one PDF for pages 1-2 and another for page 4, delivered together. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `split/all-pages` | Split every page of mixed.pdf into its own PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `split/even-odd` | Extract the even-numbered pages of report.pdf into a new PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `split/bookmarks-all` | Split bookmarks.pdf at bookmarks from every level, including the nested bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |
| `split/bookmarks` | Split bookmarks.pdf at its top-level bookmarks. | pdf-count, pdf-size, pdf-text, pdf-raster, archive |

## docs/tools/svg-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/svg` | Convert chart.svg to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/table-of-contents.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `table-of-contents/default` | Generate a table of contents from bookmarks.pdf with the default settings. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-bookmarks |

## docs/tools/text-color.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `document-colors/text` | Change all text in color.pdf to green #228833. | pdf-count, pdf-size, pdf-raster |

## docs/tools/tiff-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/tiff` | Convert chart.tiff to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/txt-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `text-to-pdf/default` | Convert notes.txt to PDF using font helv, size 12 and A4 paper. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `text-to-pdf/courier` | Convert notes.txt to PDF using font cour, size 16 and Letter paper. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `text-to-pdf/times` | Convert notes.txt to PDF using font times, size 18 and A5 paper. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `text-to-pdf/tiro` | Convert notes.txt to PDF using font tiro, size 14 and Legal paper. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |

## docs/tools/unlock-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `passwords/decrypt` | Unlock encrypted.pdf with its password "sailboat" and download the unencrypted PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |
| `password-errors/correct` | Decrypt encrypted.pdf with password "sailboat". | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-encryption |
| `password-errors/incorrect` | Try to decrypt encrypted.pdf with the incorrect password "wrong-password". | no-download |

## docs/tools/validate-signature-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `signatures/validate` | Inspect the digital signature in signed.pdf using the validation tool. | Visible result only |
| `password-errors/tampered` | Validate tampered.pdf, which has been altered after signing. | Visible result only |

## docs/tools/view-metadata.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `metadata-cleanup/view` | Open report.pdf and inspect its document title, author, subject and keywords. | Visible result only |
| `metadata-cleanup/copy` | Open report.pdf and copy its document metadata as JSON using the application. | clipboard-json |

## docs/tools/vsd-to-pdf.md

Successful conversion is excluded after the pinned offline WASM converter did not finish valid legacy inputs. See COVERAGE limits.

## docs/tools/webp-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `images-to-pdf/webp` | Convert chart.webp to PDF using the default settings. | pdf-count, pdf-size, pdf-raster |

## docs/tools/word-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `documents-to-pdf/docx` | Convert report.docx to PDF. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/wpd-to-pdf.md

Successful conversion is excluded after the pinned offline WASM converter did not finish valid legacy inputs. See COVERAGE limits.

## docs/tools/wps-to-pdf.md

Successful conversion is excluded after the pinned offline WASM converter did not finish valid legacy inputs. See COVERAGE limits.

## docs/tools/xml-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `ebooks-to-pdf/xml` | Convert data.xml to a PDF document. | pdf-count, pdf-size, pdf-text, pdf-raster |

## docs/tools/xps-to-pdf.md

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `more-formats/xps` | Convert drawing.xps to PDF. | pdf-count, pdf-size, pdf-raster |

## Additional shipped tool: /edit-pdf-text.html

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `edit-text-replace/all` | Open single.pdf in Edit PDF Text. Replace every occurrence of "Harbor" with "Cedar". Export the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-replace/whole` | Open search.pdf in Edit PDF Text. Replace every occurrence of "Harbor" with "Bay" with whole-word matching. Export the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-replace/case` | Open search.pdf in Edit PDF Text. Replace every occurrence of "Harbor" with "Port" with case-sensitive matching. Export the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-replace/number` | Open single.pdf in Edit PDF Text. Replace every occurrence of "42" with "63". Export the edited PDF. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-style/size` | Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", set its size to 26, and export. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-style/color` | Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", set its color to #2244aa, and export. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-style/italic` | Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", apply italic, and export. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-text-style |
| `edit-text-style/underline` | Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", apply underline, and export. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-decoration |
| `edit-text-style/strike` | Open single.pdf in Edit PDF Text. Select the heading "Harbor Map", apply strike, and export. | pdf-count, pdf-size, pdf-text, pdf-raster, pdf-decoration |
| `text-edit-history/single` | Replace just the first match of "Harbor" with "Cedar" in search.pdf, using case-sensitive search, and export. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `text-edit-history/undo` | Replace every exact-case "Harbor" with "Cedar" in search.pdf, then undo the replacement and export the restored document. | pdf-count, pdf-size, pdf-text, pdf-raster |

## Additional shipped tool: /overlay-pdf.html

| Checkpoint | Tested behavior | Program observation (frontend for every row) |
| --- | --- | --- |
| `pdf-overlay/all` | Use report.pdf as the base and single.pdf as the overlay. Apply it to every base page, looping the one-page input. | pdf-count, pdf-size, pdf-text, pdf-raster |
| `pdf-underlay/all` | Use report.pdf as the base and single.pdf as the underlay. Apply it to every base page, looping the one-page input. | pdf-count, pdf-size, pdf-text, pdf-raster |

