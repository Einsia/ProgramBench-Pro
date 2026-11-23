# Joplin coverage

Task 1.0.0 uses the unmodified Joplin 3.7.21 release. The executable
specification and frozen manifest define 70 episodes (59 GUI, 11 program),
831 checkpoints, 196 frontend and 1,583 backend assertions.

The table maps document, menu and local Data API behavior to executable episodes.

| Document/menu/API feature | Episodes and observations |
| --- | --- |
| Note creation, exact text, updates, field selection, explicit IDs and conflicts | `protocol-notes` preserves user Markdown verbatim, metadata, partial updates and read-only fields; `protocol-options` checks supplied IDs, duplicate rejection and all conflict/trash inclusion combinations. `note-create`, `note-duplicate`, `note-move`, `note-trash` cover the corresponding desktop operations. Duplicate naming is not prescribed. |
| HTML clipping | `protocol-clipping` covers 30 HTML forms saved as Markdown or HTML and read back. `protocol-options/relative-link-*` covers relative, absolute, parent, root and fragment links with base_url. Generated Markdown is compared as structured document content, including heading levels, emphasis, code, links and tables. |
| Notebook trees and trash | `protocol-folders` checks actual recursive containment, parent IDs, two populated roots, a grandchild, branch/note moves, metadata, trash and permanent deletion. `notebook-create/tree` cover nesting and navigation in the desktop. `archive-jex/raw/markdown` check complete sub-notebook trees after import. |
| Tags and note relationships | `protocol-tags` covers tag creation, Unicode/case, association changes in both directions, idempotence, renaming, detachment and deletion. Each relationship operation compares its actual before/after change. `tags-edit/navigation` cover the UI. |
| Resources and reverse links | `protocol-resources` checks uploaded bytes, MIME/metadata, replacement, association and deletion. `protocol-options/resource-notes` associates one image with two notes and checks the reverse endpoint. `note-attachments`, `pdf-attachment` and archive/import episodes cover GUI resources. |
| Image clipping geometry | `protocol-resources/clip-image-*` uses an image varying in both axes: whole, center, top-left, bottom and right-edge non-square regions. Expected pixel bytes are independently cropped from the input; a wrong x or y cannot match. |
| Pagination, sorting and projection | `protocol-lists` covers notes, notebooks, tags, resources and linked collections, page boundaries, ascending/descending order, equal-key groups and selected fields. `protocol-history` covers revision pages and cursor continuation across the event endpoint's fixed 100-row boundary. |
| To-dos and alarms | `protocol-todos`, `todo-create-complete/convert/alarm` cover conversion, completion, reopening, alarm values, trash restoration, associations and restart persistence. `note-sorting` uses ordinary notes to isolate title ordering from the independent to-do pinning preference. |
| Search text, filters, scope and dates | `protocol-search` covers positive/negative terms, phrases, any, title/body/tags/notebooks, MIME resources, geography, source and dates, Unicode, basic search, pagination and sorting. `protocol-search-edges` adds parent/child scope, notebook OR, ID filters, relative dates, wildcard/negation and invalid-filter controls. Setup waits for the full text and resource indices separately. `global-search`, `goto-anything` and `local-find` cover desktop search/navigation. |
| Editing, clipboard and matching modes | `note-edit-history`, `editor-lines`, `editor-commands` and `editor-replace` check undo/redo, copying, cutting/pasting, line duplication/deletion/indentation, sorting/swapping and exact replacement boundaries. Whole-word/case-sensitive and regular-expression replacements have contrasting corpus terms. `formatting-toolbar` requires combined strong/em formatting and its undo. |
| Core Markdown | `markdown-inline/blocks/tables/checklist` cover paragraphs, headings, links, literal escaping, code, quotations, lists, tables and checkbox changes; `internal-link` checks note links. User-entered Markdown remains an exact text check. |
| Built-in rendering extensions | `markdown-extended` covers math, footnotes and Mermaid. `markdown-builtins` covers TOC, mark, mhchem and ABC music. `markdown-options` toggles sub/sup, emoji, insert and typographer; `markdown-additional` covers definition lists, abbreviation expansion, Fountain and merged table cells. These are shipped renderer options, not installation of executable plugins. |
| Rich text editing | `rich-text` covers editor switching and replacement; `rich-editing` covers combined formatting and conversion back to Markdown; `rich-table` edits cells, appends a row and preserves table structure across editor switching. |
| Imports | `import-markdown/text/html/front-matter/enex-markdown/enex-html` cover the individual formats. `import-enex-complete` has two pages, distinct authors/dates/tags, a note link and embedded image bytes. `import-onenote` uses a small unmodified licensed upstream `.one` fixture; `inputs/SOURCE.json` records its source and digest. |
| Exports and complete document roundtrips | `roundtrip-jex/raw/markdown/front-matter/html/html-directory` cover each format, including modifying/removing the working note before RAW restore. Front Matter requires parseable YAML with title, author, user dates and tags, and checks these after import. `archive-jex/raw` additionally preserve a two-level notebook, two notes, nondefault metadata, to-do/alarm, tags, two attachments and internal links as a graph. `archive-markdown` covers nested directory import, images and internal note relationships, without requiring unsupported YAML metadata in plain Markdown. `pdf-attachment` checks PDF text and attachment bytes through public channels. |
| Revisions, change feed and restoration | `protocol-history` creates, reads, updates, pages and clears revisions, checks create/update/delete events, follows cursors and exercises API errors/authentication. `history-restore` previews a prepared historical revision and restores a separate note while preserving the current one. |
| Whiteboard editing and graph structure | `whiteboard` creates/edits text cards, groups and existing-note cards. `whiteboard-graph` creates an edge, labels it, changes arrowheads, flips endpoints, deletes it and promotes a card to a real note. JSONCanvas observations map generated node IDs to content and inspect edges and note relationships. |
| Workspace, dialogs and preferences | `workspace-layout`, `workspace-preferences`, `note-sorting`, `note-properties/statistics`, `theme-persistence` and `todo-alarm` cover panes, menu visibility, title ordering/detailed list, note information, document counts, themes and persisted state after restart. |
| Error paths and API boundary | Program episodes include missing IDs, invalid requests, authentication, pagination bounds and deletion reads. Runtime help exposes every setup/check channel: local Data API, upload/list_files/download, clipboard, restart and reset. |

Each public mutation is executed once per checkpoint. Multiple assertions share
its captured response, but each field has its own extraction and validation.
An invalid/missing field does not replace valid sibling fields with its error.
GUI autosave waiting keeps the most recent observation and checks each aspect
independently. Whole-object transport or parse failures affect observations that
need that object. Dependencies describe required object/state predecessors;
independent tag changes do not depend on an earlier cumulative membership list.

Generated identities and bookkeeping timestamps are normalized, while explicit
user dates remain exact. Equal sort keys are unordered within their tie group.
Generated Markdown comparisons retain semantic structure rather than requiring
a particular delimiter spelling; user-authored Markdown retains textual
fidelity. Backups compare documents, folder edges, tags, explicit metadata,
attachment bytes and links independently, ignoring archive record order and
newly assigned IDs. File/API checks wait for asynchronous saves and imports.
Frontend requirements concern observable functions, not pixel layout.

The runtime supplies a private 1280×900 desktop. All episodes run serially with
fresh solution copies and data profiles. The core GUI budgets are
min(400, 220+45n) model calls, 1,000,000+250,000n tokens and 1,200+240n seconds for
n checkpoints. `whiteboard` has a 2,500,000-token allowance. The
additional offline episodes in `gui_more.py` each allow 400 calls, 3,000,000
tokens and 2,700 seconds. The executable manifest is authoritative for these budgets. Program wall limits and recorded
reference durations are managed by the episode runner.

## Scope boundaries

| Facility or variant | Boundary or reason |
| --- | --- |
| Sync targets, shared notebooks, collaboration, publishing, updates, connected AI | Require external accounts/services or outbound network; both reference and verifier are offline. |
| OCR downloads, microphone/camera input, OS notification delivery and hardware printing | Require model downloads, hardware or integration with a host session. Stored alarms and local image/PDF attachments remain tested. |
| External editors/apps, executable plugins, developer tools, arbitrary profile/path selection | Cross the runtime's code/file boundary. Built-in renderer extensions remain enabled and tested through the ordinary Options page. |
| Local file URLs, remote media and external embeds | Would leave the document exchange or network boundary. Uploaded media, internal resource links and internal whiteboard note cards remain covered. |
| Multi-device encryption/sync conflict production | Requires multiple peers and synchronization. Local conflict flags and inclusion queries are covered without manufacturing a synchronization service. |
| Automatic history expiry and notification scheduling over days | Require elapsed histories outside a bounded isolated episode. Public revision records and a real GUI preview/restore are covered directly. |
| OneNote `.onepkg` Windows conversion, Windows-only embedded objects and handwriting recognition | The pinned importer documents platform-specific conversion. The portable textual `.one` path is exercised on Linux; no Windows converter or handwriting recognizer is emulated. |
| Unspecified fonts, exact music glyph geometry, arbitrary imported HTML styling and localization | Platform-dependent presentation is not an exact acceptance rule. Distinct headings, emphasis, diagrams, sheet music, tables, document text and multilingual content are checked. |
| Free-form whiteboard geometry, minimap/zoom trajectories, viewport positions and drag coordinates | No canonical geometry is prescribed by the document goals. Card content, groups, connections, direction, labels, deletion and promotion provide stable structural checks; viewer pixel geometry is not compared. |
| Text attachments reimported through a plain Markdown directory | The pinned importer treats `.txt` files as notes. The directory episode therefore uses an image and an internal note link; JEX/RAW separately require arbitrary attachment bytes to remain attachments. |
| Every toolbar/shortcut synonym, cosmetic theme/font/date permutations and all rich-text autoformat triggers | Equivalent routes to the covered editing/rendering operations are allowed. Representative saved preferences, direct formatting, tables and editor conversion are tested rather than duplicating the same observable operation for every gesture or appearance setting. |

Public IDs, focus/caret state and modification timestamps may vary in screenshots
and are not exact visual requirements. The reference uses the same public GUI
operations as the evaluator. Any source/runtime change requires a fresh complete
record before the frozen bundle is used for acceptance.
