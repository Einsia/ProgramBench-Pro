# VisiData coverage

Version 1.0.0. The reference uses upstream **VisiData 3.4** with the launcher policy described in `../solution/NOTICE`
(GPL-3.0-only) with its dependencies python-dateutil and six. Exact counts and budgets come from
`data/manifest.json`: **171 episodes (51 program, 120 GUI)** with **1224 checkpoints** and
**1432 scoring points — 1308 backend and 124 frontend** — across 17 features. Backend points are
deterministic program checks; each GUI episode carries evaluator-judged frontend goals plus backend
companions. Points are binary. The task score is the fraction of episodes whose points all pass.

## Counting principle (what makes a point)

Each point maps to one **distinct rule or value** of VisiData 3.4, never a repeated parametrization of
the same observation. A point is kept only if a plausible wrong implementation would observe something
different from the reference on it: families that apply one rule to many inputs give every input its own
column, pattern, expression, row position, format or file, and points whose observation equals another
point's, or the unchanged input, are not included. The few points that share an observation on purpose
(for example the three input encodings, which decode to the same table through different decoders) fail
independently when their own code path is missing. The distinct rule categories are:

- **Loaders, savers and their options** (`conv-*`, `vr-convert`, `sh-savers`, `mx-saving`, `mx-roundtrip`, `more-formats`):
  each input format, each output format, each option that changes what is read or written (delimiters,
  quoting, encodings, indentation, skipped lines and header rows) and each save-and-reload round trip.
- **Commands** (`cmd-*`, `mx-*`, `sh-*`, `vr-*`, `ex-*`, `more-*`): each replayable command, replayed from a command log
  placed in the workspace, and each of its distinct arguments and value shapes: sort keys and directions on
  untyped and typed columns, selection by regular expression or expression, computed columns, column
  types and their display formats, aggregators, frequency tables, pivots, joins, per-column and per-row
  edits and slides, cell clearing and pasting, unpivoting and unfolding nested values, error paths.
- **Keys** (`tui-*`): the default key map as a user types it, with the visible result: cursor movement,
  selection, search, typing and sorting, editing, sheet navigation, command log saving and the input history.
- **Value shapes**: one rule applied to columns whose cells differ in sign, thousands separators, exponents,
  SI suffixes, currency signs, date formats, unparsable values and empty cells (`sh-*`).
- **User goals (frontend)** (`gui-*`): distinct evaluator-judged tasks, each with an objective backend
  companion that reads the resulting screen facts or files.

| group | episodes | checkpoints | points |
| --- | ---: | ---: | ---: |
| conv-* (loaders, savers, options) | 3 | 64 | 65 |
| cmd-* (command logs by feature) | 9 | 138 | 139 |
| tui-* (keys) | 9 | 82 | 116 |
| mx-* (rule matrices) | 9 | 278 | 278 |
| sh-* (value shapes) | 6 | 129 | 129 |
| vr-* (per column, row and format variants) | 4 | 217 | 217 |
| ex-* (further commands) | 6 | 113 | 113 |
| more-* (further formats, sheets and bulk commands) | 5 | 79 | 80 |
| gui-* (frontend goals) | 120 | 124 | 295 |
| **total** | **171** | **1224** | **1432** |

## What is covered (per feature: backend / frontend points)

| feature | backend | frontend |
| --- | ---: | ---: |
| selection | 156 | 20 |
| sorting | 139 | 18 |
| columns | 137 | 17 |
| conversion | 154 | 0 |
| analysis | 148 | 0 |
| rows | 145 | 0 |
| expressions | 106 | 0 |
| sheets | 80 | 16 |
| types | 77 | 7 |
| editing | 40 | 17 |
| navigation | 38 | 16 |
| search | 41 | 7 |
| saving | 18 | 0 |
| files | 8 | 4 |
| errors | 9 | 0 |
| session | 7 | 2 |
| history | 5 | 0 |
| **total** | **1308** | **124** |

## Exclusions

The reference disables every route that would run an external program, arbitrary code or a plugin, or
reach the network; these features are **not implemented by the candidate**: the Python, shell and system
commands and keys (expression evaluation of Python statements, `exec-python`, `exec-shell`, the
REPL and debugger, importing Python objects, `open-url`, the system clipboard commands `syscopy-*` and
`syspaste-*`, opening cells or rows in an external editor or viewer `sysedit-*` and `sysopen-*`), plugins and
the plugin installer, the version check, the message of the day, remote and cloud loaders, process and
network sheets, and loaders that need an optional package that is not installed (Excel, YAML, HTML, pandas,
psutil and similar). Expressions use the arithmetic, string, date, math and JSON functions that VisiData
offers inside the guarded evaluator. The commands `capture-col` and `split-col` are deprecated since
VisiData 3.0 and only print a message, and `setcol-fill` has no effect; none of them is scored.
Interactive SQL query sheets opened by `exec-sql` are available but are not scored.

Also out of scope as non-deterministic or environment-specific: wall-clock values (the directory sheet shows
modification times, so no check reads it; the runtime also shows a date equal to the current or previous UTC
date as `[today]`), commands that use unseeded random numbers (`random-rows`, `select-random`), plots and the
canvas, the mouse, the options sheets (they show private runtime locations), the thread, memory and process
sheets, wide metasheets such as the describe sheet in screen checks (their layout depends on the terminal),
the command line options `--row-delimiter`, `--csv-dialect` with `excel-tab` and `--tsv-delimiter`, the exact
colours and menu texts of the terminal, and the exact wording of messages unless a point asserts it. The
refusals of the guarded expression evaluator are specific to the reference and are not scored.

## Formats and commands (scored or excluded)

Every loader and saver of VisiData 3.4, with points or the reason for having none:

| format | read | write |
| --- | --- | --- |
| csv, tsv, psv, lsv, usv | points | points |
| json, jsonl (ndjson), jsonla | points | points |
| sqlite | points | points |
| fixed width, rec, vd, vdj, vds | points | points |
| txt | points | writes the same text as tsv |
| md, html | md has no loader; html needs lxml (not installed) | points |
| jira | no loader | points |
| gz, bz2, xz compressed input | points | no saver |
| zip | points (listing and members) | the member time stamp is the current time |
| tar | points | no saver |
| toml, eml, mbox, org, geojson, jrnl, grep | points | org, geojson and jrnl savers fail in the reference; others have no saver |
| vdx | vdx saving fails, so there is no file to read | fails in the reference (AttributeError) |
| xd, dot, png | xd needs xdfile | fail in the reference on a table sheet |
| vcf, xml, html tables, xlsx, xls, ods, yaml, parquet, arrow, hdf5, pandas, pdf, shp, sas, spss, dta, npy | optional package not installed | optional package not installed |
| directory sheet | shows modification times (wall clock) | no saver |
| remote and cloud (http, s3, gsheets, airtable, reddit, zulip, git) | network and external programs disabled | disabled |

The reference lists 389 commands under `reference_controls`. Points reach **215** of them, by name in a command
log or prompt, or by a key that types them. The other 174 are excluded for these reasons:

| reason | commands |
| --- | --- |
| plots, canvases and the mouse (excluded: layout, colours and mouse input) | `dive-visible`, `draw-refline-x`, `draw-refline-y`, `erase-refline-x`, `erase-refline-y`, `erase-reflines-x`, `erase-reflines-y`, `go-mouse`, `go-mouse-1`, `move-canvas`, `move-cursor`, `plot-column`, `plot-numerics`, `plot-row`, `plot-rows`, `plot-selected`, `plot-sheet`, `plot-source-selected`, `remake-cursor`, `resize-cursor-doubleheight`, `resize-cursor-doublewide`, `resize-cursor-halfheight`, `resize-cursor-halfwide`, `resize-cursor-max`, `resize-cursor-min`, `resize-cursor-min-height`, `resize-cursor-min-width`, `resize-cursor-shorter`, `resize-cursor-taller`, `resize-cursor-thinner`, `resize-cursor-wider`, `resize-x-input`, `select-top-cursor`, `set-aspect`, `slide-bottom-obj`, `slide-down-obj`, `slide-left-obj`, `slide-leftmost-obj`, `slide-right-obj`, `slide-rightmost-obj`, `slide-top-obj`, `slide-up-obj`, `start-cursor`, `start-move`, `stoggle-visible`, `toggle-all`, `toggle-top-cursor`, `unselect-top-cursor`, `visibility`, `zoom-all`, `zoom-all-y`, `zoom-cursor`, `zoomin-cursor`, `zoomin-mouse`, `zoomout-mouse` |
| menus (excluded: exact menu texts of the terminal) | `menu-column`, `menu-data`, `menu-edit`, `menu-file`, `menu-help`, `menu-plot`, `menu-row`, `menu-system`, `menu-view` |
| split windows and the sidebar (layout depends on the terminal size) | `open-sidebar`, `sidebar-cycle`, `sidebar-toggle`, `splitwin-close`, `splitwin-half`, `splitwin-input`, `splitwin-swap`, `splitwin-swap-pane` |
| threads and processes (excluded: timing dependent, process sheets) | `cancel-all`, `cancel-row`, `cancel-rows`, `cancel-sheet`, `cancel-thread`, `kill-process`, `kill-selected`, `signal-process`, `signal-selected`, `threads-all`, `threads-sheet` |
| macros and memos (stored in the private VisiData directory, not observable) | `macro-record`, `macro-sheet`, `memo-aggregate`, `memo-cell`, `open-memos` |
| help, options, version, profiler, status history, replay control and no-ops (private locations or no data effect; the input history is read through state) | `check-version`, `exec-longname-simple`, `help-commands`, `help-commands-all`, `no-op`, `open-input-history`, `open-statuses`, `options-global`, `options-sheet`, `redraw`, `replay-all`, `replay-row`, `replay-stop`, `save-profile`, `show-version` |
| error sheets: Python tracebacks of the reference, and errors-all is empty in batch mode | `error-recent`, `errors-all` |
| viewport, paging and automatic widths (depend on the terminal size; no effect in batch mode) | `go-down-small`, `go-left-page`, `go-left-small`, `go-right-page`, `go-right-small`, `go-up-small`, `resize-col-half`, `resize-col-max`, `resize-cols-max`, `resize-height-input`, `resize-height-max`, `scroll-cells-bottom`, `scroll-cells-down`, `scroll-cells-left`, `scroll-cells-leftmost`, `scroll-cells-right`, `scroll-cells-rightmost`, `scroll-cells-top`, `scroll-cells-up`, `scroll-down`, `scroll-middle`, `scroll-up`, `toggle-multiline` |
| extract-* (write nothing usable in batch mode) | `extract-file`, `extract-file-to`, `extract-part`, `extract-part-selected`, `extract-selected`, `extract-selected-to` |
| sheet stack jumps and reopens (the saved sheet equals the unchanged source) | `jump-first`, `jump-sheet-1`, `jump-sheet-10`, `jump-sheet-2`, `jump-sheet-3`, `jump-sheet-4`, `jump-sheet-5`, `jump-sheet-6`, `jump-sheet-7`, `jump-sheet-8`, `jump-sheet-9`, `open-source`, `open-source-next`, `open-source-prev`, `quit-sheet-free` |
| open-new gives an empty sheet; the others act on the directory sheet, which shows modification times | `open-dir-parent`, `open-new`, `open-row-filetype`, `open-rows` |
| join variants (the same rows as the scored join-sheets-all and join cases) | `join-selected`, `join-sheets-top2` |
| join from the columns sheet (a further entry to the scored join) | `join-sheets-cols` |
| no visible effect here (reload-rows reloads the whole sheet in batch, reload-selected changes nothing in the output, cache-cols equals the uncached result, commit-sheet is not enabled for csv sheets and asks to confirm overwriting its source, which batch mode refuses, and empty csv cells are not null for the null moves) | `cache-cols`, `commit-sheet`, `go-next-null`, `go-prev-null`, `reload-rows`, `reload-selected` |
| contract variants (depth variants equal contract-col and contract-cols; contract-source-cols gives error cells) | `contract-col-depth`, `contract-cols-depth`, `contract-source-cols` |
| only on sheets of loaders that are not installed or disabled (html, xml, hdf5, Python objects) | `addcol-selector`, `addcol-xmlattr`, `dive-metadata`, `hide-hidden`, `scrape-cells` |
| no effect in VisiData 3.4 | `setcol-fill` |
| fails in the reference (TypeError in openCell) | `dive-selected-cells` |
| the interactive chooser of a prompt (no data effect) | `choose-rows-selected` |
| opens the file a cell names, the same loader path as open-file | `open-cell-file` |

Groups of points that share an observation on purpose: the three compressions (gzip, bzip2 and xz decode the
same table through different decoders), the three input encodings, json and jsonl inputs of the same rows, and the
tsv, psv and delimiter variants of one table. Each one fails alone when its own decoder or option is missing.

## How points are checked

Every check reaches the application through the task's black-box runtime, the same code that serves the
reference to the model:

- `cli` runs the product once without a terminal with the arguments of `vd` (`-b IN -o OUT` converts a file,
  `-b -p LOG.vdj` replays a command log) in the workspace; the exit status and output are asserted only where
  a point names them (the error paths).
- `workspace` reads the files the run wrote: names, sizes, bytes and, per point, one projection of the content
  (text, TSV, CSV, JSON, JSON lines, command log fields, bytes or the tables of a SQLite file).
- `state` reads the input history (`input_history.jsonl`) that prompts append to.
- `screen` facts are layout-independent semantic readings of the current sheet: the cursor row and column, the
  selected rows, the column names with their type and sort marks, key columns, table cells, the sheet name,
  the sheet stack, the row count, the prompt text, the last message, a text anywhere on the screen, and whether
  the application exited. The cursor is read from the reference display's reverse-video style, the
  selection from the bullet that starts a selected row. Colours are never compared, the parser never relies on
  fixed column positions, and cell or header text cut off at a column edge is not compared; the width that the
  Columns sheet lists for each column is product data and is compared like any other cell.

The backend points use these check kinds: file 1017, screen 278, run 9, state 2, tree 2.

- Each program episode starts a fresh instance with its own fixtures placed through the runtime. A checkpoint
  that types keys restarts the application, opens a data file by its name with the `o` key and reads the
  screen facts or the files and the input history the product wrote. A batch checkpoint writes its own output
  file and reads it back. Frozen observations hold only the asserted projection, never a whole-screen snapshot.
- Points that only verify a no-change or a bound companion use `requires` to tie to a positive point of the
  same episode; a GUI frontend goal binds to its backend companions, so an inert shell cannot pass.
- Dependent checkpoints run only when the prerequisite's backend points passed (or its frontend points when it
  has none). Input files are setup items that only the checkpoints using them declare.
- A crashed or exited application is restarted with the same data before the next checkpoint, so one crash
  costs only its own checkpoint's points.

Frontend goals give exact inputs; the reference keys and commands are public inputs (the same text is in the
runtime's `help` under `reference_controls`). Equivalent keys, menu entries and commands are accepted, but the
cursor row must be identifiable in reverse video. `reference/` contains the deterministic drivers for the
pinned standard only; its screen parser is never the candidate contract.

## Interface and budgets

The evaluator operates the application through the runtime's GUI operations (`key`, `keys`, `type`, `wait`)
in a **120x36** `xterm-256color` pseudo-terminal and observes the runtime's `screen` snapshot: rows with their
row numbers, the cursor, the style runs that differ from the base style (cursor, selection, key columns) and
the process state. `resize` and the lifecycle steps are framework operations. GUI episodes use the budget
formula scaled by checkpoint count `n`: calls `min(160, 130 + 30n)`, active seconds `min(1800, 720 + 240n)`,
tokens `min(1500000, 1000000 + 250000n)`. In this task a GUI episode has
160 calls, 1250000 to 1500000 tokens and 960 to 1680 active seconds.
