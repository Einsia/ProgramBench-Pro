# drawDB coverage

Version 1.0.0, reference drawDB 1.8.2. Exact counts and budgets come from `data/manifest.json`:
79 episodes (36 program, 43 GUI) with 386 checkpoints and 1399 scoring points, 225 frontend and 1174 backend
(928 program checks and 246 independent checks of GUI checkpoints). The count comes from distinct behaviours
only: equivalent parametrisations of one mechanism are not counted twice. SQL exporters get one point
per statement and one per column rendering that the same exporter has not already shown (each column type, size,
default and clause combination once), so the six dialects and the six conversions of a generic diagram are
covered type by type.

## Coverage

| Family | Program episodes (no evaluator) | GUI episodes (goal + program companions) |
| --- | --- | --- |
| SQL export of a dialect's own diagram | `sql-export-mysql`, `-mariadb`, `-postgresql`, `-sqlite`, `-mssql`, `-oracle`: tables with every column clause (types with size and precision, defaults by type, NOT NULL, UNIQUE, auto increment and identity, unsigned, checks, comments), enum and composite types (PostgreSQL), arrays, inheritance, indices (unique and multi-column), foreign keys with update and delete actions, composite and self references, views (joins of each kind, conditions, aliases, materialized, comments), descriptions and comments per dialect, statement order; additional type fixtures cover the remaining choices, including PostgreSQL VECTOR, HALFVEC and SPARSEVEC with dimensions/defaults/array usage and Oracle VECTOR | `gui-export-sql` (export dialog and download of a MySQL and a PostgreSQL diagram), `gui-sql-tools` (copy the script and paste it into the import dialog, import a pasted script) |
| SQL export of a generic diagram | `sql-convert-mysql`, `-postgresql`, `-sqlite`, `-mariadb`, `-mssql`, `-oracle`: type mapping of every generic type, including NUMERIC, NUMBER, VARCHAR2, CLOB and NCLOB, enums and sets (CHECK constraints, domains, enum types), composite types, views, indices, foreign keys | `gui-export-sql` (one goal per dialect) |
| SQL import | `sql-import-<dialect>` (into a diagram of the dialect and into a generic diagram: tables, columns, keys, indices, unique constraints, comments, relationships, enums and types), `sql-import-options` (append, overwrite, refused script) | `gui-import` (MySQL, PostgreSQL and SQLite scripts, keep or replace the diagram, refused script) |
| JSON and legacy DDB diagram files | `json-roundtrip`, `json-properties` (database, title, keys of the file), `json-import-checks` (ready and overwrite messages, replacing the diagram, not JSON, missing tables, database mismatch, relationship to a missing table or column); `ddb-import` (legacy tables, fields, relationships and title, default generic database, malformed/missing properties and database mismatch with a populated diagram retained) | `gui-import` (import, mismatching database, cancel a pending replacement of a populated diagram), `gui-export` (download) |
| DBML, Mermaid, Markdown | `dbml-export`, `dbml-import` (generic and PostgreSQL diagrams, refused file), `mermaid-export`, `markdown-export` (title, summary, database, table structure, relationships, types and enums) | `gui-import` (DBML file, refused file), `gui-export`, `gui-dbml` (the live DBML code view: add a column, a table, a reference; rename a table) |
| Quoting, Unicode and significant whitespace | `text-boundaries`: JSON round trip of mixed-case and spaced identifiers, Unicode names/defaults, multiline comments; SQL import of quoted/reserved-word identifiers and strings with repeated spaces | |
| Images | `images` (PNG, JPEG, SVG, PDF and copy as image: actual decoded/rendered diagram names and fields in a legible two-table fixture) | `gui-images` (a second diagram with different names and an excluded hidden table; decoded/rendered contents checked in all four formats) |
| Tables and columns | `edit-actions` (duplicate, delete, cut, copy, paste of tables, notes and areas from the clipboard, invalid clipboard content, clear, new tables per database, undo through the menu) | `gui-tables`, `gui-tables-2`, `gui-tables-3` (add, rename, delete, comment, hide and show, lock and unlock (a locked table stays in place), move, duplicate, collapse and expand, search, a table with typed columns, width), `gui-fields-1` to `gui-fields-4` (add, type, nullable, primary key, delete, default, size, precision, unique, auto increment, check, comment, unsigned, enum values, order, rename, ENUM type, a column with several properties, CURRENT_TIMESTAMP), `gui-postgresql` (array, inheritance, JSONB) |
| Indices and constraints | `sql-export-*` | `gui-indexes`, `gui-indexes-2` (add, unique, rename, delete, columns, second index; unique constraints: add, rename, columns, delete) |
| Relationships | `auto-connect` (automatic foreign keys) | `gui-relationships-1` to `-3` (drag to connect, refused connection of different types, connection to a unique column, self reference, cardinality, update and delete actions, rename, swap, delete, many-side label, colour, composite key), `gui-arrange` (automatic foreign keys) |
| Subject areas, notes, views, types, enums | `edit-actions` (paste) | `gui-areas`, `gui-notes` (add, rename, content, delete, move, resize, lock), `gui-views` to `gui-views-3` (add, columns, aliases, joins and their kind, conditions and operators, OR, removal, base table, materialized, comment, rename, delete, hide, move, lock and resistance to dragging), `gui-types`, `gui-types-2`, `gui-enums` (add, columns and their types, comment, rename, delete, use as a column type, values one by one and several at once), `gui-colors` (tables, notes, areas, views) |
| Editing and history | `edit-actions` | `gui-history` (undo, redo, undo of a move and of a deletion, timeline), `gui-clipboard`, `gui-clipboard-2` (copy, cut and paste of tables, notes, areas and views; duplicates), `gui-arrange` (automatic arrangement, clear, snap to grid, moving several tables) |
| Problems | `problems` (every message of the problems panel, one fixture per group of problems; strict mode off; a clean diagram) | `gui-problems` (show the list, fix a duplicate column, a missing primary key, an enum without values; strict mode) |
| Diagrams, templates, storage | `persistence` (reload, restart, fresh profile, rename, save as, open, open recent, delete, flush storage, autosave on and off, saving by hand, export of saved data), `templates` (the six default templates, title, blank diagram, own templates) | `gui-diagrams` (rename, save as, open, new diagram of a database, delete and cancel a pending deletion), `gui-templates` (from the editor and from the templates page, own templates: save, use, open, delete), `gui-settings` (language, autosave, custom data types, flush storage), `gui-custom-types` (rename propagation, delete fallback, colour saved across reload, unsaved rename cancelled, database scope and filtering), `gui-saved-tools` (case-insensitive name search, database and combined filters, clearing filters, ascending/descending name and size sorting), `gui-export` (saved data) |
| View and display | `display` (default display, data types, relationship labels, comments, debug coordinates, menu bar, side panel, problems panel, settings kept across a reload, language), `view-transform` (zoom in and out, pan, reset, menu zoom) | `gui-panels` (menu bar, side panel, problems panel, DBML view, presentation mode), `gui-display-1`, `gui-display-2` (data types, comments, cardinality, labels, grid, debug coordinates, dark theme, column details and their display toggle), `gui-zoom` (zoom in, out, preset, custom value, fit, reset, pan) |
| Pages | `templates` (templates page) | `gui-pages` (home page to editor and to templates, not-found page, exit, bug report page) |

Excluded, with the reason:

| Excluded | Reason |
| --- | --- |
| Share, versions (history of shared diagrams), cloud diagrams and the migration notice, import with AI, sending a bug report, clearing the shared-diagram cache | they need drawDB's backend or third-party services, which the release image leaves unconfigured (`/config.js` has no backend) and the task runs offline; the bug report page itself is covered |
| Links to the documentation, the shortcut list, Discord, GitHub and the authors' sites | external sites, unreachable offline |
| Fullscreen | the page keeps its 1280x900 viewport, so entering fullscreen has no observable effect; presentation mode is covered |
| New window | it opens the editor again, which the runtime shows in place of the current page: the same as opening the editor |
| Edit > Edit (Control+E) | it only opens the side-panel editor of the selection, which every side-panel goal reaches |
| Translated texts of the other interface languages | each translation is the same mechanism; switching the language is covered |
| SQL import forms the reference reads wrongly: any foreign key in MSSQL scripts; CREATE INDEX, column-level REFERENCES, table-level primary keys and non-numeric defaults in Oracle scripts; checks that call functions or name columns (PostgreSQL, MySQL); named indices in SQLite scripts | defects of the reference's importers (they drop the statement, fail or store an object instead of text), so there is no behaviour to require; the import fixtures use the forms each importer reads. The error message the import dialog keeps showing after importing SQLite, MSSQL, MariaDB or Oracle scripts into a generic diagram is not checked (the imported diagram is) |
| Exact table positions after automatic arrangement, exact image pixels, and PDF internal object layout | layout and encoding may differ in an equivalent implementation; checks require spread-out tables or valid decoded exports with the specified visible table names/fields. Raster, SVG foreignObject/text and vector/raster PDF rendering are accepted; hidden table names must be absent |
| Generated ids and names (`table_<id>`), timestamps (last saved, export file names) | random or time-dependent; observations leave them out |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime: its GUI operations (clicks, fields,
  menus, the keyboard, pointer gestures), file-chooser uploads, product downloads, the clipboard, the visible page
  (snapshot) and its lifecycle operations (reset, restart). Nothing reads candidate files, browser storage or
  processes.
- The harness (`ui.py`) operates the editor as a user does: it finds menus, menu entries, dialog buttons and fields
  by functional names and synonyms (letter case and spacing ignored, a menu entry may carry its shortcut),
  accepts direct toolbar operations or menus, native choice controls, unambiguous affirmative form actions,
  immediate completion, file choosers/inputs/drops, and exports that download at once or from a dialog.
  Preparation accepts an already usable editor; dialog fields can be located by label, current value, or the
  unique newly opened input. Setup does not require the literal label Confirm. Program episodes use only these named
  controls, keyboard shortcuts and the clipboard; they never locate controls by position.
- Each checkpoint starts from a fresh browser profile on `/editor`, chooses the database of a new diagram and loads
  its diagram through the editor's own JSON import (or a SQL or DBML import), so checkpoints do not depend on each
  other. GUI checkpoints start the same way; the evaluator then pursues one goal with the editor's controls, and the
  program companions read the resulting diagram through its JSON export (or the file the goal downloaded, the
  clipboard or the page) and check only the state the goal changes.
- Observations are projections: diagram files are read with ids resolved to names (tables, columns, relationships
  by their end columns, views by their columns, joins and conditions), so generated ids never matter; SQL is
  compared statement by statement with dialect-aware identifier folding/quoting, numeric-literal normalization
  and lossless string values. Column clauses and table constraints are sets; DBML definitions use lexical names,
  literal values and nested groups with unordered settings, Mermaid separates entities and edges, and Markdown
  compares headings, lists, table cells and code instead of divider lengths or padding;
  index-column order is preserved because it is part of a composite index's definition; moves,
  resizes, zoom and pan are checked by direction against a threshold, and grid snapping by the grid; images by
  decoded format and OCR of rendered table names/fields, including SVG rendering and real PDF parsing.
  Image margins and layout, and the number of internal PDF image objects, do not affect the result. Required
  visible content must be found before recording, and empty, damaged or unrelated images fail. JSON property
  checks require typed functional properties and allow extra metadata.
- Points that only verify a refusal or an unchanged state are bound (`requires`) to a positive point of the same
  episode: the import of a valid file, a valid connection, a save by hand, a template being listed.
- A crashed application is restarted with the same data before the next checkpoint.

## Budgets and time

The manifest defines each episode's call, token, active-time and wall-clock
limits. Episodes run serially; program episodes use no evaluator. The
verifier timeout includes startup and cleanup time in addition to those limits.
