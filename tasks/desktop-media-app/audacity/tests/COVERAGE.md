# Audacity coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
72 episodes (42 program, 30 GUI) with 3,499 checkpoints and 3,576 scoring
points, 70 frontend and 3,506 backend (3,429 program checks and 77 independent
checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Import | GUI open/import of mono, stereo, 48 kHz, Unicode-named, FLAC and MP3 files, cancelled chooser, damaged file reported with the project intact; program import of every PCM and encoded fixture and of malformed inputs |
| Export | GUI WAV, FLAC, Ogg and MP3 export, selected-range export, export at a changed project rate; program format, range and repeated exports with exact or lossy-codec policies |
| Editing/history | GUI cut/paste, delete, silence, trim, split, split delete, join, duplicate, split new, multi-level undo/redo; program edit, clipboard, clip and history matrices with exact PCM; disabled edits on an empty project |
| Effects | GUI Amplify (cancel and apply), Normalize DC removal, fades, Change Speed, Repeat, Echo, Low-Pass Filter, Reverse; program effect matrix (amplitude, EQ, pitch/speed/tempo, dynamics, delay, distortion, filters, modulation, repair, spectral, vocal, crossfades) |
| Generation | GUI tone and noise generation into a selection; program generators |
| Labels | GUI Unicode region label, point label, label text edit, UTF-8 label export; program label text, range and movement matrix, analyzers that create labels, clipping detection |
| Tracks/mixing | GUI add/rename/remove tracks, mute/solo/gain, mix and render, stereo to mono; program gain/pan, mute/solo, envelopes, alignment, mix/render |
| Selection/project | GUI exact time selection; program selection save/restore, project rate and name |
| Persistence | GUI project save, restart and reopen; preference OK/cancel and persistence across restart; program project save/reopen/restart and preference restarts |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the
  same code that serves the reference to the model: `script` (the scripting
  pipe), `upload` (input documents), `list_files` and `download` (files the
  product wrote), `observe` (the accessible desktop, for Unicode names and the
  window title), and the lifecycle operations `restart` and `reset`. Exported
  audio is decoded by the verifier's own FFmpeg; expected audio is computed from
  verifier-private copies of the input fixtures.
- Scripting replies count only by their OK/Failed status, except the bodies of
  the query commands GetInfo and GetPreference: reply text of other commands is
  optional in the contract.
- Each program scenario prepares its own state (scenario reset, imports,
  baseline export) in setup items placed right before its first checkpoint.
  A failed preparation blocks only that scenario; the reset falls back to a
  fresh instance (runtime `reset`) when leftovers of an earlier scenario or a
  missing helper command would make it fail. Within a scenario, a step whose
  earlier step could not run is blocked, and every step records its result
  before comparing it, so one mismatch never fails the following steps.
- A read with no product action of its own is part of the step it observes
  (for example the clip structure after an edit, the re-render of an unchanged
  project, the labels an analyzer created), never a separate point. Delete and
  Split Delete, whose observations equal Cut and Split Cut, use one range per
  fixture; effect variants whose output equals their input are left out.
- Points that only verify that nothing changed or that an input was rejected
  count together (`requires`) with a positive point of the same episode: a
  disabled edit on an empty project with that edit working on audio, a rejected
  malformed import with an ordinary WAV import, a cancelled dialog with the
  completed operation, an unchanged project with the visible import error.
  Frontend points that an inert dialog could satisfy (exports, preferences)
  count with the check of the written file or stored setting.
- Where the evaluator itself sets a time selection, exported audio must be one
  exact input segment whose boundaries match the request within 2 ms (the
  product displays milliseconds); prepared selections and all scripted edits
  stay sample-exact. Floating observations compare within 1.5 LSB or a
  relative 5e-4; zero-crossing counts within 2. Repair output is compared with
  an independent least-squares autoregressive reconstruction of the same
  selection (seven PCM16 quanta, local RMSE three quanta), because Audacity
  2.4.2 adds fresh random dither to its own solution on every run.
- Dependent GUI checkpoints run when the prerequisite's backend points passed
  (or its frontend points when it has none). A crashed application is restarted
  with the same data before the next checkpoint.
- Two native episodes use no scripting at all: they open, edit, undo/redo and
  export through visible controls, and their program points decode only the
  files the GUI exported.

## Interface and budgets

The evaluator operates the desktop through the runtime's input operations
(click, activate, fill, type, press, check, move, drag, scroll, zoom,
focus_window, maximize, wait) and observes it through the runtime's `observe`
(windows and accessible controls with refs, roles, names, states, values and
bounds) and `screenshot` (1440x900, or a magnified rectangle after zoom). Input
documents are uploaded into the runtime's input folder before the first
checkpoint; goals name them, and requested outputs, by absolute paths in the
runtime's input, output and project folders, which the evaluator types in file
dialogs (paths outside those folders are refused). GUI budgets scale with checkpoint count n: calls min(180, 50+30n), seconds
min(2400, 600+240n) and tokens 14,000 per call (each call carries a
full-screen screenshot and the accessible controls), i.e. 80-180 calls,
840-1,800 seconds and 1.12-2.5 million tokens; program episodes run without
a model.

`reference/` contains deterministic recipes for the pinned standard only: they
drive it through the same runtime operations (menus, dialogs and file choosers
through the accessible tree, and fixed positions of the reference layout where
the product exposes no object: track controls, label text, preferences tree).
They are never the candidate's frontend contract.
