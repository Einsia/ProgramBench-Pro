# Reviewed Zotero coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
115 episodes (71 on the desktop, 44 on the local API) with 319 checkpoints,
138 frontend and 1660 backend points. Every episode starts from a fresh data
directory. Desktop episodes get their starting library written through the
local API with fixed object keys, and their input files uploaded into the inbox;
the evaluator performs the goals in the interface, and program checks read the
resulting library back through the API, the files the application wrote into
the outbox, and the clipboard. Library objects are compared without bookkeeping
(versions, generated timestamps); keys the application generates are compared
by order of first appearance (or as one anonymous value in unordered lists);
exports and formatted citations are parsed by serializer-neutral readers
(entries and fields, records and tags, XML trees, HTML text and inline markup,
RTF text). Program episodes drive the local API without an evaluator, comparing selected
response properties. Their checkpoints contain at most ten points, allowing
recovery after a candidate crash. Fixture writes accept any successful status
and retain the supported objects when a batch is only partly supported; types
and query libraries are separate setup units. Each export or citation checkpoint
depends only on the library it uses.

| Coverage | Behavior |
| --- | --- |
| Items | Create a book and a journal article with several authors; creators (add, reorder, single-field name, remove); item type change; multi-line abstract and Extra, URL, short title, language; dates with parsed forms; duplicate; trash, restore, empty trash; undo and redo; merging duplicates with chosen field versions; related items; editing several items at once; a book section from a book; persistence after restart |
| Notes | Child notes with paragraphs and bold text, standalone notes in a collection, headings with bulleted and numbered lists, a note generated from a PDF's annotations; Markdown and HTML note export |
| Collections | Create and nest, rename, move to the top level, add and remove items, delete with and without items, trash and restore, copy with subcollections, a new collection from an item's menu, items of subcollections, undo; My Publications membership |
| Tags | Add and remove on an item, rename and delete library-wide, colored tags assigned with the number key, tag selector filtering (several tags, filter text), hiding and deleting automatic tags |
| Search | Quick search modes, including a phrase present only in indexed PDF full text; advanced search with conditions, result types (notes, top-level items) and any/all matching; saved searches (save, edit, delete to the trash) |
| Import and export | Import BibTeX (also from the clipboard), RIS, CSL JSON, MODS, MEDLINE, Refer, Zotero RDF and Endnote XML, into a new collection or not; export the library, a collection and a selection as BibTeX, RIS, CSL JSON, Zotero RDF with notes, CFF and Endnote XML |
| Citations | Bibliographies and citations in APA, Chicago author-date and IEEE as RTF, HTML and clipboard text and HTML; quick copy of bibliography entries and citations and its format setting; RTF Scan; item reports; a citation style installed from a file; the setting that adds URLs of paper articles |
| Attachments and reader | Stored and linked files, web links, a standalone file with a manually created parent, renaming files from parent metadata, the filename template and automatic renaming settings, converting linked files to stored files, attachment titles and their normalization; in the PDF reader highlights, comments, note annotations, underline colors and conversion to a highlight, text, image (area) and freehand ink annotations; saving a PDF with embedded annotations; page navigation, find in document, thumbnails and Recently Read |
| View and settings | Columns and sorting, compact density, note font size, stacked layout and interface font size, with layout checked after a restart, the item pane header, the Unfiled Items view hidden and shown again |
| Local API | Schema endpoints (item types, fields and creator types) and all fields of every item type written and read back; validation errors; writes (POST, PUT, PATCH, DELETE) with versions, preconditions and write tokens; key and server ID checks; collections, saved searches, tags, children and trash; collection/search key and version representations and conditional reads; query parameters (sort and direction, limit and start, quick search modes, tag expressions, item types, since); persistence after a restart; 14 export formats and `include`; 15 citation styles with locales and options |

Representative user goals stand in for every item type × field × command
permutation: the desktop episodes use a few fixture libraries (a 26-item query
library with collections, notes and links; small libraries per goal), while
every item type and field is covered program-side through the local API, its
export formats and citation styles. Not scored: online services (sync, groups,
feeds, lookup by identifier, metadata retrieval for PDFs, translator and style
repositories, update and retraction checks, library lookup), word processor
plugins and the browser connector beyond `/connector/ping` (external integration
requires additional applications), printing, read aloud, translated interfaces
and the language preference, plugins and developer tools (these can expose or
execute implementation code),
EPUB/snapshot/SVG viewers and executable or embedded-resource note content
(the reference boundary disables active documents to prevent access to internal
application resources), and the moment at which item-list column layouts are
written (the reference saves them with a delay of up to a minute, so their
persistence across an immediate restart is not a requirement). Read aloud
requires speech services or installed voices; printing and external handlers
leave the confined document interface. Translated interfaces and all language
variants are represented by the fixed English interface. Template creation and
citation locator parameters are not local API endpoints in this release;
item creation and available citation parameters are tested instead. Advanced
search hierarchy options are covered by API searches and representative GUI
result types; view settings use representative column, sorting, layout, density
and font changes rather than scoring each equivalent menu route.

Dependencies and companions. A checkpoint that builds on an earlier result
declares that dependency. Visually silent commands count together with their
produced file or clipboard result. Unchanged GUI objects are bound to the
positive mutation in that checkpoint, and hiding automatic tags is checked
separately from deleting them. API scenarios compare the response properties
relevant to each request; named companions link negative or empty observations
to positive cases where declared. Unrelated mutations are observed through
specific objects or membership checks rather than whole-library counts.

reference/ contains the deterministic recipes for the pinned standard only.
They drive the same runtime operations as the evaluator and are never the
candidate's frontend contract; the interface is judged by its behavior, never
by a required widget tree.

## Interface and budgets

The surface is the task runtime's desktop (shared desktop module
`blackbox_desktop.py`): a private 1280×900 Xvfb display, D-Bus and AT-SPI
session per episode, run as the candidate user; one virtual desktop without
background menus or launchers, ordinary windows maximized and dialogs centered.
Observations are the runtime's accessibility snapshot (controls with role,
name, description, text, value, states, bounds) plus a full-screen screenshot;
input is pointer and keyboard events, accessible default actions, zoom into a
screen rectangle, and window activation. File dialogs are confined to the
episode's inbox and outbox; goals name every file by its absolute path there.
The runtime's `api` operation reaches the application's local HTTP server
(paths under `/api/` and `/connector/ping`) with the local API key the runtime
supplies; the clipboard is read as text and HTML. PDF exports are read with
PyMuPDF for page text and annotation types, pages and comments, without freezing
annotation geometry. Tag sets in exports and saved-search conditions are
unordered; annotation text ignores surrounding and repeated whitespace.
GUI object lookups explicitly page through API results, and collection and
item-result checks omit child items when the goal is about top-level items.
Budgets: calls min(200, 70+40n), seconds min(2400, 900+300n), tokens
min(3M, 1M+500k·n) for n checkpoints, i.e. 110–200 calls, 1200–2100 seconds
and 1,500,000–3,000,000 tokens per episode. Calls and token budgets are
calibrated so the standard answer uses at most 40% of either allowance.
