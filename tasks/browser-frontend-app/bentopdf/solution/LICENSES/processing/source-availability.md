# Corresponding processing sources

The unmodified BentoPDF source archive includes the exact dependency lockfile,
WASM build scripts and vendored packages. The exact PDF viewer fork source at
051abe5b72a9 is also included as bentopdf-viewer-source-051abe5b72a9.tar.gz.
Its packages/pdfium build scripts identify the PDFium revision and patches.

Additional upstream sources and build instructions:

- PyMuPDF 1.26.3: https://github.com/pymupdf/PyMuPDF/tree/1.26.3
- BentoPDF PyMuPDF WASM 0.11.16: https://github.com/alam00000/bentopdf-pymupdf-wasm
- Ghostscript 10.06.0 and its WASM wrapper: https://github.com/alam00000/bentopdf-gs-wasm and https://github.com/ArtifexSoftware/ghostpdl/tree/ghostpdl-10.06.0
- CoherentPDF 2.5.5: https://github.com/coherentgraphics/coherentpdf.js (the distributed package includes the JavaScript program and API documentation)
- LibreOffice WASM converter 2.5.0: https://github.com/matbee/wasm-libreoffice (the package and its source/build references are pinned by the BentoPDF dependency lockfile)
- qpdf WASM 0.3.0: https://github.com/neslinesli93/qpdf-wasm
- Tesseract.js and Tesseract.js-core 7.0.0: https://github.com/naptha/tesseract.js and https://github.com/naptha/tesseract.js-core

The full legal notices from the processing packages are preserved in this
folder. Noto font packages are distributed under the SIL Open Font License;
the font package manifests and their license files are recorded separately.
