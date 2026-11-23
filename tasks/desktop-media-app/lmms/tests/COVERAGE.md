# LMMS coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
56 episodes (25 program, 31 GUI) with 1,171 checkpoints and 1,303 scoring
points, 84 frontend and 1,219 backend (1,087 program checks and 132 independent
checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Render options | Program `render` of a sample clip, a resampled sample, synth notes and a mix of both: default options, 32 bit float, sample rates 48000 to 192000 Hz, oversampling 1, 4 and 8, loop, Ogg Vorbis and MP3 at several bitrates, MP3 stereo mode, a 48 kHz sample played at 44.1 kHz |
| Sample tracks | Verifier-made samples (tones, square, ramp, impulse, stereo pair, 48000 and 22050 Hz): start position, clip length, track volume and panning, muted track and muted clip, overlapping and consecutive clips, mixing, tempo, master volume and master pitch, with grids of further positions, lengths, levels, tempos and mixes |
| Instruments | Instrument tracks with one to three instruments: key, length, volume, panning, pitch, waveform and modulation; the sound chips sfxr, NES and Game Boy with every knob, switch and channel routing; lb302, kicker, Monstro and OPL2 with every knob, switch and wave; BitInvader embedded waveforms, short tables, interpolation and normalization; Vibed waveform, stiffness, pick/pickup, harmonic, detuning, level, panning, impulse and two strings; Watsyn waveforms, tuning, panning, level, A/B mix, modulation, crosstalk and mix envelope; ZynAddSubFX default voice at three pitches and as a chord |
| Sound shaping | TripleOscillator filter types, cutoff and resonance, volume, cutoff and resonance envelopes, LFO settings |
| Effects | One effect or a chain of two on an instrument or sample track (gain, panning, filters, bass booster, delay, stereo effects); the equalizer (low shelf, four peak bands, high shelf, high-pass and low-pass filters of 12, 24 and 48 dB per octave, input and output gain); waveshaper and dynamics processor with verifier-made curves; bitcrusher, flanger, reverb and crossover equalizer; multitap echo (step length, dry gain, lowpass steps, swapped inputs, wet mix, chain behind an amplifier) and the muted peak controller |
| Beat patterns | Beat/Bassline patterns of 16 steps placed by clips in the song: step sets, clip placement, kicker settings, synth steps, tempo |
| Automation | Master volume, tempo, and the volume and panning of a sample or instrument track, with linear, discrete and cubic progressions, several points, zigzags and late starts |
| Mixer | Routes of tracks to mixer channels, channel volume and mute, sends between channels, channel and master effect chains, master volume |
| Upgrade and dump | Projects saved by versions from 0.4.0-20080408 to 1.3.0, a project in the format of LMMS 0.2.1, compressed and plain XML containers, dump of a compressed and of an old project, damaged, empty and missing inputs |
| Command line errors | Render to a format the help text lists but the product rejects, rejected and accepted sample rates, oversampling and bitrates, all four interpolation methods, a missing output folder, an empty project, a missing project, a folder instead of a project |
| Per-track rendering | `rendertracks` of one to three tracks, names with a space, an ampersand or non-ASCII characters, a beat pattern, a muted track, a sample track, lowered volume and panning |
| GUI project and toolbar | Versioned save, default template persistence across restart, New from template; Tempo from 60 to 300 through the Tempo dialog, master volume, master pitch and time signature wheels turned up and down to the ends of their ranges, Save As, restart and reopen of a saved project |
| GUI tracks | Adding Beat/Bassline, sample and automation tracks, mute and solo, renaming tracks, replacing an instrument or adding tracks by dragging Kicker, AudioFileProcessor, sfxr, Monstro, LB302 or Watsyn from the Instrument Plugins list |
| GUI clips and notes | Clips on instrument, Beat/Bassline and sample rows at chosen bars, steps of the Beat+Bassline Editor on and off the beat, Piano Roll notes with undo and redo |
| GUI audio file processor | Loading a sample, reversing it, enabling the loop |
| GUI export | Export Tracks to the confined output directory with independent Low/High WAV projections; export of a sample clip, of two sample clips, of Piano Roll notes and of a beat pattern at the default settings, then after a changed master volume, a raised master pitch, fewer steps or a slower tempo |
| GUI notes and settings | Project notes text saved with the project; Setup dialog switches confirmed with OK and cancelled, shown in the reopened dialog and read from the settings file |
| MIDI and Hydrogen import/export | A deterministic two-note MIDI document is imported, saved and exported as MIDI; the verifier compares imported musical notes and normalized MIDI timing/velocity/tempo. A generated Hydrogen song imports an uploaded sample and three notes of different pitches, levels and positions, then exports its audio |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the
  same code that serves the reference to the model: `cli` (the product command
  line), `upload` (input documents), `list_files` and `download` (files the
  product wrote), `settings` (the application settings), `observe` (the
  accessible desktop) and the lifecycle operations `restart` and `reset`.
  Rendered and exported audio is decoded by the verifier's own FFmpeg; the
  expected values come from the frozen record of the standard answer.
- The exit status of `render` and `rendertracks` is never scored: a complete
  render sometimes exits abnormally, so the written file decides. `dump` and
  `upgrade` exit with 0 even for unreadable input, so a rejection is observed
  through the returned body, the written file and whether a message was printed.
  A message counts only where it names no private path.
- A point returns a tolerance class together with its observation. `linear`
  (sample playback) allows a few LSB, `signal` (synthesized or resampled content)
  compares the level per window and the spectrum within a few percent, and
  `lossy` (Ogg Vorbis and MP3) also allows the encoder delay and padding as a
  frame slack. Exported audio of GUI checkpoints is compared with the same
  classes and a declared frame slack. The bounds allow 24-bit rounding, low-level noise, a small gain difference
  and a one-frame onset difference within the declared comparison class.
- Kicker noise is checked over 32 notes using frame count, format, DC and RMS
  per channel and time window, plus the RMS of adjacent-sample differences
  divided by the signal RMS. This measures its high-frequency content over the
  whole render without freezing random peaks or a few short FFT samples. It
  uses the `signal` bounds; repeated noise renders must agree while
  renders with a missing or incorrect noise amount must fail.
- Projects of program points are generated by the verifier (no factory file),
  and the settings of an instrument or effect are written the way the product
  saves them, so what is not given is the product default. Points with equivalent observations are represented once.
- Points that only verify that an input was rejected count together (`requires`)
  with the point that shows the same command accepting a valid project.
- GUI checkpoints end with something the product wrote: a project saved under a
  new name, an export, or the settings file. The independent checks read only
  that: a file that exists, exported audio, elements of a saved project chosen by
  an xpath (ids and window geometry dropped, document folders replaced by
  tokens), the text of the project notes, and named attributes of one settings
  section. The Setup dialog writes every switch of its page when it is confirmed,
  so a check names only the attributes of the switch under test.
- Beat/Bassline clips compare only position, length, mute and style state; their
  display color is ignored. The sample-loading goal accepts a clip length of
  72–120 ticks around half a bar. The empty-clip placement goal checks position
  and mute state without imposing a default length. Missing required fields and
  out-of-range sample lengths fail rather than collapsing to an "other" value.
- MIDI export observations pair note-on/off events and express positions and
  durations in quarter notes. Empty tracks, format 0 versus 1, tick resolution,
  and repeated identical tempo events are ignored; notes and tempo remain checked.
- Each program episode holds at most 120 points and starts from a fresh
  instance; a failed preparation blocks only its own episode.

## Not covered

| Left out | Reason |
| --- | --- |
| White noise waves, the random LFO wave, the noise of the bitcrusher and the flanger, SID, Organic, chord creator, arpeggiator | The output of the reference differs between runs |
| OPL2 level scaling and the percussive switch of operator 1, sfxr change, repeat and vibrato depth alone | No observable effect on the rendered audio |
| Multitap echo amplitude pattern, tap position and lowpass stage count | The renders of different patterns, positions and stage counts are indistinguishable at the signal tolerance, so a point would not tell a correct implementation from a wrong one |
| Peak controller as a controller source, spectrum analyzer | Both pass the signal through (the render equals that of a bare amplifier); the controller value reaches nothing observable without a connection |
| The first 1024 frames of each CLI or GUI per-track render | The product writes a click of a few samples there, in a different track file on each run |
| Exit status of `render`, `rendertracks`, `dump` and `upgrade` | It varies between runs or is 0 for unreadable input |
| An audio file through File, Import | The product answers with a setup alert and an import error and imports nothing; no episode needs it, samples are covered through sample clips and the audio file processor |
| Vibed string length/oversampling above 1 and nonzero fuzziness | The string model chooses a random sample phase and noise; repeated output can exceed the signal bounds. Other string controls use length 1 and zero fuzziness. |
| PatMan audio | Requires a separately supplied GUS patch; the reference has no default patch and the runtime does not accept `.pat` documents. Rendering the unconfigured instrument is silent and cannot form a positive behavior check. |
| SF2 Player audio | Requires an external SoundFont bank; the clean reference has no default SoundFont. MIDI import conversion, note persistence and MIDI export are covered without a bank; sample-bank synthesis is not scored. |
| ZynAddSubFX remote editor and external presets | The helper-process editor is closed by the runtime's plugin-host restriction. The local default synthesizer is covered through CLI rendering; external preset libraries are not fixtures. |
| Factory samples, presets and soundfonts | Files of the application's own library are not part of the task |
| External plugin hosting (VeSTige, LADSPA, Carla, GIG), live recording, audio and MIDI devices, network services | Out of scope of the black-box runtime |

## Interface and budgets

The evaluator operates the desktop through the runtime's input operations (click,
fill, type, press, scroll, drag, zoom and wait) and observes it through the runtime's
`observe` (windows and accessible controls with refs, roles, names, states,
values and bounds) and `screenshot` (1440x900, or a magnified rectangle after zoom). Input documents are uploaded into
the runtime's input folder before the first checkpoint; goals name them, and
requested outputs, by absolute paths in the runtime's input, output and project
folders, which the evaluator types in file dialogs. The Export Tracks directory chooser accepts only the output folder already provided by the runtime. GUI budgets scale with the
checkpoint count of an episode and are recorded in `data/manifest.json`; program
episodes run without a model.

`reference/` contains deterministic recipes for the pinned standard only: they
drive it through the same runtime operations (menus, dialogs and file choosers
through the accessible tree, and fixed positions of the reference layout where
the product exposes no object: the step cells of the Beat+Bassline Editor, track
switches, the Piano Roll grid, the Instrument Plugins list and the switches of
the Setup dialog). They are never the candidate's frontend contract.
