# CherryTree coverage

Task version 1.0.0, pinned reference CherryTree 1.7.2. The executable manifest
(`data/manifest.json`) is authoritative for counts and budgets.

The suite has 109 episodes (87 GUI and 22 program episodes), 279 checkpoints, 184 frontend and
1,095 backend assertions. Program episodes independently exercise the real command-line exporter on
verifier-written input documents; GUI episodes exercise editing and save/export through normal
visible controls. No inspector reads application-private configuration, database or process state.

| Family | Coverage |
| --- | --- |
| Document storage | XML, SQLite, hierarchical multiple files, encrypted XML and encrypted SQLite; reading and GUI Save As/reopening; rich-text, plain-text and code nodes, child order, shared nodes, bookmarks, Unicode and punctuation |
| Rich text | Bold, italic, underline, strike-through, monospace, small text, subscript, superscript, six heading levels (small headings also create visible TOC entries), colors, alignment, indentation, clearing formatting and undo; Format Clone/Latest; exact formatting spans on repeated identical phrases |
| Lists and editing | Bulleted, numbered and to-do lists, continuation, case conversion, row duplication/movement/deletion, replacement, undo/redo, plain-text copy/paste and cut, removal of trailing whitespace, tab-to-space conversion and fixed-clock timestamp insertion |
| Tree management | Root/child creation, renaming, tags, bold names, plain-text conversion, read-only editing rejection and unlock, movement up/left/right, explicit reparenting, branch copy/paste, sibling/whole-tree sorting, child syntax inheritance, branch duplication/deletion, shared nodes and bookmarks |
| Objects | Code-box creation, content copy/paste, file loading/saving, language/dimensions/line-number settings and conversion to plain text; table CSV import/export, row/column insertion/deletion/movement, row cut/copy/paste/sort, width and lightweight mode; image rotation/scaling/flip/PNG save and undo/redo; attachment extraction; rich text with image/code/table cut/copy/paste; LaTeX source; anchors, links, TOC insertion and header collapse/expand |
| Search and navigation | Current-node search/replacement; explicit regex with multiple whitespace lengths and nonmatching controls; multi-node whole-word/case-sensitive replacement, subtree scope, respecting/overriding search exclusions; node name search, result lists, quick selection, navigation history and tree visibility |
| Import | All 18 native entries: CherryTree file/folder; indented lists; plain-text, HTML and Markdown file/folder; Gnote, Tomboy, KeepNote, Leo, Mempad, NoteCase, RedNotebook, Treepad Lite and Zim |
| Export | GUI selection/single-node/all-tree TXT scopes with node-name inclusion choices, subtree exports to TXT, HTML, PDF and CherryTree; CLI per-node and single-file TXT/HTML plus PDF; repeated output numbering, overwriting, retained earlier output, file names with spaces, protected inputs with correct/wrong/missing passwords, malformed and empty inputs |
| Application state | Preferences changed/exported/imported and retained across restart; line numbers and wrapping; new XML document creation; tree information; unsaved-change question/cancellation and discard followed by reopen |

The program corpus distinguishes paragraph and character attributes, heading levels, nested lists,
node types, excluded/read-only/tagged nodes, icons, shared nodes, depth and sibling order, filename
escaping and long names, code languages and code-box dimensions, table shapes/lightweight tables,
images, attachments, anchors and links, and multilingual text. These are reader/exporter inputs, not
claims that readonly or search-exclusion behavior is exercised by text export. Dedicated GUI
episodes test those behaviors. Each file format exercises an independent native reader. Each export
is observed once; independent semantic aspects are scored separately without repeating an
observation as several points.

Saved documents are decoded into node paths, properties, text runs with exact character spans and
embedded objects, including table widths and code-box properties. IDs and timestamps are normalized,
equivalent adjacent text runs are merged, links to nodes use their logical paths, images use decoded
pixels and attachments use bytes. HTML is parsed as an element tree and reduced to content,
formatting, links, tables, images, list kinds/nesting/numbering and node hierarchy. Equivalent
attribute order, quoting, class tokens, wrappers, direct href navigation and resource renaming are
accepted. File-set assertions compare exported document names only; CSS/JS/navigation assets and
outputs of unrelated formats are omitted. Referenced image/attachment contents are still verified.
PDF checks compare words and link targets without requiring identical fonts, wrapping, metadata or
page object serialization. Text export normalizes line endings and insignificant blank-line runs.
Preferences are read only from the user-exported file and only the two requested settings are
projected. List continuation and separator/symbol insertion ignore optional terminal line breaks;
paragraph boundaries within the note remain significant. Plain-text clipboard goals ignore optional
empty lines at paste/cut boundaries while preserving nonempty line order and formatting; the cut
sentence's clipboard check also ignores an optional terminal line break. Appended
tables ignore terminal newlines around the final block object; rich-object paste ignores terminal
newlines only. Text, formatting positions and object payloads remain checked.

Every frozen program observation is a nonempty {aspect, value} object satisfying the observation schema.

All inputs enter through upload; initial documents are opened through the public
restart-with-document operation. Independent GUI edits reopen an original source copy before their
goal; dependent goals retain the state they need and declare that dependency. Backend checks use
only list_files, download, clipboard_text and export. Rejections and removals have positive
companions where a nonfunctional candidate could otherwise obtain credit. A missing/unreadable file
fails its own assertions; candidate defects do not invalidate the entire verifier.

Record recipes use the same public runtime as exploration and evaluation. Their routes are not
candidate requirements. Additional record-time sanity checks verify formatting locations, exact
text/row/column transformations, independent image rotation/flip pixels, search hit/non-hit sets,
history, objects and imports before freezing; the frozen program observations are produced by the
actual upstream application.

## Interface and budgets

The desktop is a private 1280×900 X11 session with AT-SPI, maximized application windows and
centered dialogs. The runtime is identical in the reference, verifier and agent images. Each
episode has a fresh solution copy and data directory. Exchange paths are explicit; standard file
choosers and local resource references remain inside the exchange folders. The application clock is
fixed at 2024-01-01 12:00:00 UTC while monotonic timers continue normally. Uploaded files have
modification time 2024-01-01 00:00:00 UTC.

For n checkpoints a GUI episode normally has 80+45n evaluator calls, 600,000+300,000n tokens and
600+240n seconds. Token limits are 3,000,000 for small headings, 2,400,000 for anchors,
3,000,000 for plain-text and HTML folder imports, 2,000,000 for Markdown folder import,
3,500,000 for multi-node replacement and 2,500,000 for preference import. Small headings have
2,400 seconds for heading and TOC inspection; plain-text and HTML folder imports have 200 calls,
and HTML folder import has 3,000 seconds. Program episodes use no model. The episode runner derives wall-clock limits from measured
record durations and the declared GUI budgets; the verifier timeout includes all episode limits and
startup margin.

## Environment boundaries

The following require resources outside the offline, confined product environment: network services
(version checks, online documentation and donations), other applications and external link
launchers, executable code/terminal commands, physical printing, system tray/global desktop
integration, translated interfaces and external spell-check dictionaries. These integrations are not
scored. PDF export supplies the document-printing channel. LaTeX source is covered; rendering
through external TeX executables is unavailable. Appearance choices such as exact theme artwork,
toolbar icon size and font rasterization are not required; functional text formatting and document
content are checked.

The reference is the unmodified release package. Its launcher applies a configuration recipe and OS
confinement: no timed autosave/start dialog/online version check, inert embedded-terminal shell,
restricted execution and write locations. The reference installation is root-owned and read-only
for the product user. Runtime upload, local-resource and clipboard checks supplement file-chooser
confinement. These restrictions do not depend on runtime source secrecy; that source is available in
the agent image for self-testing.
