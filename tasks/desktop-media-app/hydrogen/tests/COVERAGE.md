# Hydrogen coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
52 episodes (13 program, 39 GUI) with 1,003 checkpoints and 1,118 scoring
points, 97 frontend and 1,021 backend (906 program checks and 115 independent
checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Rendering | Command-line export of verifier songs and samples: timing (tempo, tick positions, pattern sizes, columns, stacked patterns), note velocity and every gain stage (layer, component, instrument, drumkit component, master), clipping, instrument and note pan under all sixteen pan laws and k norms, legacy pan pairs, pitch from note keys, fine pitch, instrument and layer offsets, sample rates and the five interpolation modes, ADSR envelopes and note lengths, the resonant filter, Auto-Stop Note, mute groups, note-off events, probability 0/1, velocity layers and round robin, components, lead/lag and swing, song and pattern mode, loops, virtual patterns, tempo markers, velocity automation, playback track, mute/solo, edited sample layers (loops, reverse, ping-pong, volume and pan envelopes), sample file formats and depths, relative and missing samples; built-in Rubber Band time stretching, independent pitch shifts, tempo-relative length and crispness of tones, transients, noise and chords |
| Export | WAV/AIFF/AU/CAF/W64/VOC/FLAC depths and rates, Ogg Vorbis, MP3 and Opus with compression levels, refused combinations, drum kit override (-k), playlists, missing and malformed songs, version and help output; GUI export of WAV (48 kHz, 24 bit), FLAC and separate tracks, MIDI (one track and one track per instrument, distinct channels/pitches/velocities/lengths, mixed pattern meters), LilyPond, and theme export/import |
| OSC | Tempo, master and strip volume, pan and filter commands with their feedback and range handling, mute/solo toggles, metronome, instrument pitch, song/loop/timeline modes, tempo markers, pattern creation, removal and song editor cells, clearing notes, saving in place, new songs, drum kit loading, extraction and upgrade, the state feedback of a newly registered client |
| Song and pattern files | Reading and writing every song element one at a time (song properties, instrument, layer, component, note and pattern fields, arrangement, virtual patterns, timeline markers and tags, velocity path), all-field and out-of-range documents, legacy forms (pan pairs, layers directly in the instrument, flat and 0.9.3 sequences, older versions), refused documents, pattern documents (current, legacy, Unicode, unknown instruments) |
| Drum kits | Command-line check and legacy check verdicts, extraction, upgrade and installation of verifier kits (namespaces, legacy, layers, components, licences and images, missing samples, tar/gzip/bzip2/xz, no top folder, broken and wrong documents, kit settings, subfolders, many instruments) with installed kits played by name; GUI load of factory kits, import and load of an archive, save-as with name/author/license/information, export of a library kit including its decoded samples |
| GUI editing | Song properties (OK and Cancel), tempo, song and loop mode, pattern notes on the grid at eighth, sixteenth and triplet resolution, pattern size, fill/clear/copy/paste of instrument rows, undo and redo, pattern properties, new/duplicate/delete patterns, fill/clear of song bars, song editor cells, virtual patterns, timeline tempo markers and tags, playback track, instruments (add, rename, delete, gain, pitch, mute group, Auto-Stop Note, filter, envelope, MIDI output, mute/solo, layer sample, gain and pitch), mixer channels and master section; piano-roll chords, note length and transposition; note velocity/pan/lead-lag/probability editing; selection move/copy/delete; sample regions/reverse loops/volume-pan envelopes/stretching and reopening; graphical automation creation/move/merge; Undo History |
| Files and persistence | GUI save as, open, reopen and new song, pattern export and load, playlist creation and editing, preferences OK/Cancel stored in the settings file; program restarts that keep the last song, saved songs, settings and the library, discard unsaved edits, and resets that discard everything; playlist reorder/reopen/next-song and appearance persistence/theme restoration; Director song identification |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the same code that serves the reference
  to the model: `osc` (one OSC message and the feedback it causes), `cli` (the product command line through
  `start.sh` with arguments: exit status, output and the files it wrote), `upload` (verifier documents),
  `list_files` and `download` (files the product wrote), `settings` (the settings file), and the lifecycle
  operations `restart` and `reset`. The song the application holds is read by saving it with
  `/Hydrogen/SAVE_SONG_AS` into the project area; rendered and exported audio is decoded by the verifier's own
  FFmpeg; samples, songs, patterns, playlists and drum kits are generated by the verifier.
- Projections compare only the parts a point is about: song fields by name, notes as position and instrument (by
  name in GUI checks), patterns and instruments by name, file locations as tokens of the document areas, the
  library or a drum kit folder, numbers of documents within 1e-4. The master fader allows 0.005, matching its
  displayed two-decimal value. Manual note-property values allow 0.03, automation values 0.04 and normalized
  sample-envelope coordinates 0.05. Where a new pattern or instrument lands in a
  list, default names of new objects, file names the product derives for separate tracks or exported kits and the
  location of the program in its own usage text are not compared.
- Audio is compared as format, frame count, per-channel peak and RMS, windowed RMS, onsets and, where relevant,
  dominant frequency, band energies or short excerpts. Exact arithmetic (gains, pans, positions) compares levels
  within 5e-4 absolute or 0.5 %; pitched, filtered and enveloped signals within 0.004 absolute or 3 %; lossy codecs
  within a wider frame and level tolerance.
- MIDI event times are quarter-note beats, with simultaneous events sorted, track grouping retained and labels/empty metadata tracks ignored. LilyPond is tokenized without whitespace, comments, generator tagline or version. Wrong notes, channels, velocities, timing and track grouping remain distinguishable.
- Lossless GUI exports that permit different rates/depths, and archived drumkit samples, are decoded and resampled to 22050 Hz for 50 ms RMS windows, onsets and spectral band shares (0.012 absolute/8% levels, 10 ms onsets, 0.05 band share). Corrupt/empty samples fail decoding. A separate Snare track is checked for its rhythm and spectrum, including silence at other instruments’ onsets.
- Each program scenario prepares its own state (a fresh instance, uploaded samples and documents, an opened song)
  in setup items placed right before its first checkpoint; a failed preparation blocks only that scenario, and a
  row with an explicit `depends_on` runs only after the prerequisite backend assertion passes. Independent strip
  setters compare their target field and non-target invariance against their own before state, preventing unrelated
  failed setters from cascading into later points.
- Points that only show that something was refused, left unchanged or silent count together (`requires`) with a
  positive point of the same episode: refused documents and exports, ignored out-of-range OSC values, cancelled
  dialogs, silent renders. Properties and preferences end with reopened, visible saved values. Export goals show the selected export settings,
  a reloaded pattern or the written file in the product’s file browser; these visible results count together with
  the corresponding independently validated file.
- GUI checks read only the state the goal produces. Dependent GUI checkpoints run when the prerequisite's backend
  points passed (or its frontend point when it has none); a crashed application is restarted with the same data
  before the next checkpoint.

## Manual coverage map

The fixed 1.2.7 manual shipped with the product is the feature inventory. Common commands and their shortcuts
are equivalent routes in every GUI goal, rather than separate duplicate scoring points.

| Manual chapters | Current checks |
| --- | --- |
| 3–4 navigation and main UI | All GUI episodes: menus, keyboard, selection, native file dialogs, scrolling and editor switches |
| 5 preferences | preferences, appearance, program-persistence-01; general limits, cancellation, appearance colors, restart, theme import/export |
| 6 main menu | song-files/new/properties, pattern-files, export-mixdown/midi/lilypond, drumkit-load/import-export/properties, undo-redo/history |
| 7 toolbar | song-tempo-modes, OSC tempo/mode/loop/metronome; offline rendering of mode and tempo effects |
| 8 song editor | pattern-copies, song-arrangement, timeline, playback-track, automation-edit; program arrangement/virtual patterns/markers/automation |
| 9 pattern, note properties, piano roll | pattern-notes/grid/properties, instrument-rows, note-selection, note-properties, piano-roll; pitch/length/pan/velocity/lead-lag/probability rendering |
| 10 sound library | drumkit-load/import-export/properties, pattern-files, program-drumkits and persistence; named factory/user kits, components, library restarts |
| 11 instrument editor | instrument-list/sound/envelope/mute-solo/layers, mixer; program envelopes, filters, gain stages, layers, MIDI mapping |
| 12 sample editor | sample-editor, sample-stretch, program-rendering-05; regions, reverse/forward/ping-pong loops, envelopes, built-in Rubber Band length/pitch/crispness |
| 13 mixer | mixer-strips/master, instrument-mute-solo; program pan laws, components, mute/solo, gain and clipping |
| 14 Director | director; static current-song display, without time-sensitive metronome animation |
| 15 playlists | playlist, playlist-order, CLI playlist export; create/remove/reorder/save/reopen/select next song |
| 16 MIDI | instrument-envelope MIDI mapping, mapped MIDI export, note/pitch rendering; device IO excluded below |
| 17 OSC | program-osc-01/02 and program-drumkits-01; documented commands with observable file/feedback effects |
| 18–22 examples/formats/licenses/shortcuts | Song/pattern/drumkit/theme/playlist documents, licenses, export files and the GUI editing episodes above |

## Not scored

- Stochastic render samples: humanize timing/velocity, random pitch, RANDOM layer selection and probabilities
  strictly between zero and one have no reproducible output. Their persisted parameters are covered by song-file
  round trips, and GUI mixer humanize remains covered. Probability zero and one are rendered and edited.
- Physical audio/MIDI interfaces and realtime synchronization: sound cards, MIDI devices, JACK/ALSA/PortAudio,
  tap-tempo clock timing, live note recording and timing-sensitive transport/metronome animation require external
  devices or a deterministic clock not exposed by this runtime. Static modes, OSC feedback, file MIDI output and
  offline audio effects are covered.
- Program loading: LADSPA effects (no plug-ins installed and uploaded documents cannot name one), playlist scripts
  and external program editors are closed by the runtime. Rubber Band uses the included library and is covered.
- Online drumkit repositories and remote downloads require network access; the runtime is offline.
- Private installation/diagnostic views: Open Demo and filesystem/audio-engine diagnostics expose installation
  paths or device/process-dependent state outside document areas; they have no portable candidate fixture.
- Non-ASCII archive extraction paths depend on unavailable host locales; Unicode kit names are still validated
  and round-tripped. Drumkit property/save-as dialogs are maximized and scrolled through the public runtime.

## Interface and budgets

The evaluator operates the desktop through the runtime's input operations (click, activate, fill, type, press,
check, move, drag, scroll, zoom, focus_window, maximize, wait) and observes it through `observe` (windows and
accessible controls with refs, roles, names, descriptions, values, states and bounds) and `screenshot` (1440x900,
or a magnified rectangle after zoom). Input documents are uploaded into the runtime's input folder before the first
checkpoint and, where an episode starts from a song, the song is opened with public OSC; goals name documents and
requested outputs by absolute paths in the runtime's input, output and project folders. GUI budgets scale with
checkpoint count n: calls min(180, 50+30n), seconds min(2400, 600+240n) and tokens 14,000 per call, i.e. 80-170
calls, 840-1,560 seconds and 1.12-2.38 million tokens; program episodes run without a model.
Calibrated exceptions: note-properties has 7,200 seconds to preserve later-checkpoint reserves during graphical
editing; sample-editor has 3.2 million tokens; playlist-order has 220 calls, 4.5 million tokens and 4,800 seconds.

`reference/` contains deterministic recipes for the pinned standard only: they drive it through the same runtime
operations (menus, dialogs and file dialogs through the accessible tree; the keyboard in context menus; and fixed
positions of the reference layout where the product exposes no object: the pattern and song grids, the timeline
ruler, knobs and faders). They are never the candidate's frontend contract.
