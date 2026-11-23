# MusicBrainz Picard coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
48 episodes (5 program, 43 GUI) with 242 checkpoints and
1,107 scoring points, 92 frontend and 1,015 backend (150 program checks and
865 independent checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Loading | GUI Add Files and Add Folder (sub-folders included, documents that are not audio skipped), loading with hidden files and an ignore expression excluded; program `LOAD` of files, folders, `file://` URLs, missing paths, repeated loads, with and without sub-folders, hidden files and ignore expressions |
| Remote commands | Program matrix of `LOAD`, `CLUSTER`, `REMOVE`, `REMOVE_ALL`, `REMOVE_UNCLUSTERED`, `REMOVE_SAVED`, `FROM_FILE` (nested, circular and stopping command files), `QUIT` (also inside a command file), `WRITE_LOGS`, `CLEAR_LOGS`, the `help` command list, unknown and differently cased commands; the session written on exit |
| Clustering | Program clustering matrix (album and album-artist spellings, artist fallback, Various Artists name, folder names, `Artist - Album` and disc sub-folders, punctuation, accents, CJK, compilations, repeated clustering); GUI Cluster, editing a cluster's album and saving its files, moving a file between clusters |
| Option profiles and `picard-cli` | Program `profiles list/export/import` matrix (share and backup exports, enabling, replacing, naming and tagger scripts, validation, old setting names, refused documents and options, help and version output); GUI profile export, import and creation |
| Viewing | Metadata view of one file and of a multiple selection, the Info dialog and its artwork page, the item filter, a custom column of the file list, showing a further column and sorting by a column, the error/debug log, the activity history, toolbar labels and the View panes |
| Editing | Title change, new tag, removed tag, multi-value tag, MP3 edit with ID3 rewrite, unsaved change kept in the session, one edit applied to several files, metadata copy and paste, restoring the original value; tags from file names (folder patterns, replaced underscores) |
| Reading tag formats | 90 tag layouts of Vorbis comments (FLAC, Ogg Vorbis, Opus, Speex, Ogg FLAC), ID3 (v2.3, v2.4, ID3v1, MP3, MP2, TrueAudio, AIFF, WAVE with RIFF INFO, DSF, DSDIFF), MP4 (AAC and ALAC), ASF and APEv2 (WavPack, Monkey's Audio, Musepack, OptimFROG, TAK, AAC, AC-3), each saved again with existing tags cleared (duplicate keys merged, genre references resolved, unknown atoms dropped, picture and key forms rewritten) |
| Writing tag formats | The tag plan (104 cases: every tag alone, number/total pairs, dates, descriptions, languages, performer roles, multi-values) written to MP3 ID3v2.4, MP4 and ASF, which map almost every tag in their own way; for FLAC, MP3 ID3v2.3 and APEv2, whose cases mostly follow one rule (the upper-cased tag name, the ID3v2.4 frames, the tag name as key), the 17, 19 and 34 cases that depart from it and representatives of the rule; one combined case written to every further container |
| Tag options | ID3 version, text encoding, multi-value join, ID3v1 and iTunes grouping (GUI and settings), ID3 removed from FLAC and APEv2 from MP3, WAVE RIFF INFO writing, removal and encoding, APEv2 in AAC and AC-3, date sanitization per format, clearing existing tags, tag writing turned off, preserved modification times, empty FLAC seek tables, track number and title guessed from file names |
| Cover art | A local image added through the cover art area, replacing a front cover, appended as a second front cover, and given up again for the original cover art; embedding only one front image; cover images saved as image files (fixed name, type as name, content) instead of or besides embedding, and removed from the tags |
| File naming | Renaming and moving through the options, the naming presets, a new script in the naming script editor and a script package imported there, the compatibility options (spaces, non-ASCII, directory separators, Windows compatibility and its replacement table), additional files moved along, emptied folders removed; 198 naming-script probes of the script language's text, logic, arithmetic, comparison, multi-value, variable, date and file-information functions, escapes and file-name rules |
| Tagger scripts | Scripting options page (new script, enable), Run scripts on a selection, 42 probes of setting, unsetting, deleting, copying and merging tags, hidden variables, tag names with descriptions and script functions; script packages exported and imported |
| Sessions | Save Session As with unsaved changes, Save Session again to the same file, New Session, Load Session, the last session loaded again on startup after a restart; the session written on exit |
| Settings and setup | Setup wizard file organization, quick settings, configuration backups (a changed option, the preserved-tags list extended from the metadata view, the top tags of the metadata view), settings kept across restarts (profiles imported with `picard-cli` and used after a restart) |
| Removing | Removing files from the list and moving them to the trash |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the same code that serves the reference
  to the model: `command` (`start.sh -e` remote commands), `cli` (`picard-cli`), `upload` (input documents),
  `list_files` and `download` (files the product wrote, saved, renamed or moved), and the lifecycle operations
  `restart` and `reset`. Saved audio files are read by the verifier's own tag reader (mutagen) into a normalized
  dump (frames or keys with their values, pictures reduced to type, MIME type, description, SHA-256 and pixel size;
  frame order, padding and key order ignored); paths of documents are compared relative to the document folders.
- Loaded files and clusters are observed through the session the product saves when it quits (the `QUIT` remote
  command; the session folder is the output folder), sorted by path, with locations and cluster names; the
  application is started again afterwards with the same data. When a command file already made the application
  quit, no further `QUIT` is sent and the session it saved is read.
- Exported profiles are compared as parsed TOML, script packages as parsed YAML (title, script and metadata
  fields), configuration backups by the INI keys the goal changed (string lists as lists, whether written as
  comma-separated items or as a variant list), profile lists by the lines of `picard-cli profiles list` that name
  the profiles in question, `picard-cli` messages by exit status and message lines (Python tracebacks left out),
  saved cover image files by SHA-256 and pixel size, logs written by `WRITE_LOGS` by whether they mention the folder
  an earlier `LOAD` named, the `help` command list by its command names; UUIDs and dates are normalized.
- Each program scenario prepares its own state (fresh instance, a settings profile imported with `picard-cli`
  and a restart, uploaded documents) in a setup item right before its scored step; a failed preparation blocks
  only that scenario.
- GUI episodes prepare non-target state through the same channels (input documents, a settings profile, files
  loaded with `LOAD`); checkpoints that need other settings import their own profile and load their own folder
  before the evaluator operates. Every assessed operation is a GUI goal; there is no program channel for saving
  unmatched files, so format, naming and option matrices are checked on the files a GUI save wrote.
- Saved files of the format matrices are read where the save moved them (an unsaved file is not there). Points
  that only show that nothing was written (a tag a format does not store, an unchanged modification time, a
  naming-script result that is empty) count together (`requires`) with a positive point of the same checkpoint.
- Custom columns are checked by a frontend point only: the product stores them in the settings as a binary Qt
  variant, a form no contract defines, and they appear in no profile or other document.
- Dependent GUI checkpoints run when the prerequisite's backend points passed (or its frontend points when it has
  none); most GUI checkpoints depend only on their setup.

## Interface and budgets

The evaluator operates the desktop through the runtime's input operations (click, activate, fill, type, press,
check, move, drag, scroll, zoom, focus_window, maximize, wait) and observes it through `observe` (windows and
accessible controls with refs, roles, names, states, values and bounds) and `screenshot` (1440x900, or a magnified
rectangle after zoom); popup context menus (Run scripts, the cover art area, the metadata view, the list headers)
are visible in screenshots only. `observe` lists a bounded number of controls, so long file lists appear in part;
scrolling a list, or typing a file's name in it, reaches the other rows. Input documents are uploaded into the runtime's input folder before the first checkpoint;
goals name them, and requested outputs, by absolute paths in the input and output folders, which the evaluator
types in file dialogs (paths outside those folders are refused). GUI budgets scale with checkpoint count n: calls
min(180, 50+30n), seconds min(3000, 600+300n) and tokens 15,000 per call (at most 2.5 million).
The configuration-backup episode has 250 calls, 5 million tokens and 1,500 active seconds to accommodate
its three settings and export goals. Program episodes run without a model.

`reference/` contains deterministic recipes for the pinned standard only: they drive it through the same runtime
operations (menus, dialogs and file dialogs through the accessible tree, and the keyboard for the product's popup
context menus and list search). They are never the candidate's frontend contract.
