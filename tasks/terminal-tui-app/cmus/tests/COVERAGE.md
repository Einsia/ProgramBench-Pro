# cmus coverage

Task version 1.0.0; unmodified cmus 2.13.0. The executable specification has
**192 episodes (126 program, 66 GUI), 1250 checkpoints,
1410 backend points and 133 frontend points**. The task score is the fraction of episodes whose points all pass.

| Feature | Backend | Frontend |
| --- | ---: | ---: |
| bindings | 68 | 3 |
| browser | 9 | 4 |
| cli | 3 | 0 |
| configuration | 3 | 0 |
| console | 19 | 0 |
| decoding | 38 | 0 |
| display | 38 | 4 |
| editing | 16 | 0 |
| errors | 40 | 0 |
| filters | 174 | 21 |
| format | 178 | 0 |
| library | 8 | 3 |
| metadata | 75 | 0 |
| navigation | 36 | 14 |
| persistence | 43 | 0 |
| playback | 94 | 16 |
| playlists | 57 | 10 |
| queue | 16 | 12 |
| search | 11 | 11 |
| selection | 24 | 9 |
| settings | 370 | 18 |
| sorting | 90 | 8 |
| **Total** | **1410** | **133** |

## Public observation and counting

Every setup, operation and observation uses a channel documented in runtime help: `remote` (the native cmus
Unix socket protocol), `state`, `workspace`, `upload`, `cli`, terminal keys/screen/resize, or lifecycle operations.
No assertion reads product internals. Each point represents a separate behavior, field, configuration rule,
operator, boundary, or state transition. Negative checks use populated before states and positive companions
where appropriate. Repeated equivalent aliases are exercised without multiplying identical observations.

Initial media are independently authored audio, mostly silence with deliberately different metadata. The file-output fixture carries four nonzero PCM levels in a known sequence, so generating silence cannot pass its decoded-sample check. The sorting fixtures
assign modification times in a permutation that conflicts with filename order. Integer format comparisons probe
constants below, equal to, and above the actual value in one assertion for each operator. Explicit filter grouping
is chosen to produce different members from the ungrouped expression. Compound sorts group by the entire key tuple,
so permutations within equal-key groups are accepted. These properties are necessary to distinguish faulty rules.

## Command and interaction matrix

The command names below come from the supplied upstream `cmus` and `cmus-remote` manuals. Prefixes name the
corresponding episodes in the executable specification and frozen manifest; each episode enumerates the exact
assertion IDs. Exclusions are explicit, not inferred from absence in this table.

| Documented command or interaction | Observable coverage or exact exclusion |
| --- | --- |
| `add -l/-p/-q/-Q`, `clear -l/-p/-q`, `load -l` | `playlist-import-*`, `playlist-roundtrip-*`, `duplicates-*`, `add-filter-*`, `gui-library-edit`; exact complete membership, order and duplicate rules |
| `pl-create`, `pl-rename`, `pl-delete`, `pl-delete -a` | `playlist-management`, `named-playlist-io/delete-all`, `gui-playlist-*`; names and actual contents |
| `pl-import` with M3U/PLS, duplicate names, omitted browser path | `named-playlist-io`, `gui-native-import`; selected playlist contents and native collision names |
| `pl-export`, overwrite confirmation | `named-playlist-io/export,overwrite`; exported file bytes parsed as playlist paths |
| `save`, `w`, `save -e`, filtered `save -L` | `playlist-roundtrip-*`, `extended-export`, `native-command-aliases/write-alias`, `filter-expression-*` |
| `bind`, `unbind`, `showbind`, contextual overrides and forced replacement | `keybindings-*`, `binding-edit-*`, `settings-editor`, `gui-custom-binding` |
| `push`, command entry, editing, cancellation, history | `native-command-aliases/push-binding`, `console-editing`, `console-completion` |
| Tab completion of command, option, binding context, ordinary/spaced filename | `console-completion`; executed result checked through native queries and playlist exports |
| `filter`, `live-filter`, `fset`, `factivate`, named negation and replacement | `filter-expression-*`, `live-filters-*`, `named-filters-*`, `filter-editor`, `gui-filter-*`, `gui-live-*`, `gui-named-filter` |
| `mark`, `unmark`, `invert` | `edit-queue-*`, `edit-playlist-*`, `copy-marked-*`, `selection-queue-copy`, `gui-marked-edit-*`; exact edited/copied subsets |
| `view` tree/sorted/playlist/queue/browser/filters/settings | `gui-view-*` judges visible semantic content; `startup-views` reads actual native saved view after startup |
| `left-view`, `right-view`, no-cycle flags, `prev-view` | `navigation-search-*`, `paging-navigation/previous-*`; native resume view identity, independent of title location |
| `win-top`, `win-bottom`, `win-up`, `win-down`, boundaries | `navigation-search-*`, `gui-search-*`, `gui-view-2`, `gui-paging`; selected file via native `echo {}` |
| `win-page-up/down`, `win-half-page-up/down` | `paging-navigation`, `gui-paging`; page-relative movement, including a resized terminal and list ends |
| `win-page-top/middle/bottom`, `win-scroll-up/down` | `paging-navigation`; visible numbered tracks and selection relative to the current viewport |
| `win-next`, tree expansion, track-pane focus | `gui-view-1`, playlist/selection episodes; visual judgment carries the expansion/focus requirement |
| `win-sel-cur` | `paging-navigation/current`; selected entry returns to the playing track |
| `win-activate`, `win-toggle` in views 1–7 | Library/playlist playback and marks; `browser-navigation-update`, `filter-editor`, `settings-editor`, and GUI counterparts |
| `win-remove` in track lists, browser, Filters and Settings | `edit-*`, `browser-delete`, `filter-editor`, `settings-editor`; confirmation and cancellation use terminal events |
| `win-mv-before/after` | `edit-queue-*`, `edit-playlist-*`; selected and marked sequence edits |
| `win-add-l/p/q/Q`, default movement and `-n` | `copy-marked-*`, `selection-queue-copy`, `gui-marked-edit-*`; append vs prepend and cursor movement are distinct |
| `browser-up`, `cd`, `pwd`, hidden entries, directory activation | `browser-navigation-update`, `gui-browser`, `browser-delete` |
| `win-update`, `win-update-cache`, `update-cache`, forced and selected updates | `selective-cache`, `metadata-cache`, `browser-navigation-update`; changed/unchanged mtime, other cached entries and deleted media |
| `player-play`, `player-pause`, `player-pause-playback`, `player-stop` | `player-controls-*`, `gui-play-*`; native state and selected track |
| `player-next/prev`, album navigation and rewind threshold | `player-controls-*`; actual next/previous file and paused seek position |
| `seek` seconds/minutes/HH:MM:SS, signed and absolute, bounds | `player-controls-*`; paused positions with one-second tolerance |
| `vol`, stereo channels, relative/percentage/clamped values, `mute` | `volume-*`, `gui-volume`, `restart-content/volume`; active channels and restoration |
| `rand`, `reshuffle` | `random-order-effects`; changed permutations with full membership, auto-reshuffle disabled for the explicit reshuffle check |
| `tqueue`, `lqueue`, explicit/default counts | `random-queue`; count and valid membership, album order within a single-album filter |
| `refresh` | Exercised after paging and terminal resize in `paging-navigation/small-terminal`; an idempotent redraw receives no separate duplicate score |
| `set`, `toggle` | `defaults-*`, `booleans-*`, `enums-*`, `numeric-*`, `display-settings-*`; valid values, cycles, range boundaries and invalid values |
| `source` of a workspace command file | `source-config`; running options and active filter reflect the file |
| `quit`, `quit -i`, `wq` | Lifecycle preservation plus `native-command-aliases`; confirm/cancel and save completion |
| `help`, `version`, CLI `--help/--version/--plugins` | `native-information`, `command-line`; native user-help, version and plugin declarations |
| native `status`, `format_print` | Metadata/playback/format episodes use real native output; multi-argument format output is covered |
| `run`, `shell`, external status-display processes | Disabled by OS process restrictions: executing arbitrary external code is outside the reference isolation boundary |
| `raise-vte`, MPRIS/D-Bus | Require a desktop/session integration not provided by this PTY deployment |
| TCP password, network streams, proxy, Icecast and CDDB | Require external network services; reference and verifier are offline |
| Mouse events | No mouse-event transport in the keyboard PTY runtime; equivalent keyboard operations are covered |

## State, options, files and formats matrix

| Feature family | Episodes and observation |
| --- | --- |
| Boolean defaults, setters, toggles; enum values and cycles | `defaults-*`, `booleans-*`, `enums-*`; each actual native option value is queried |
| Numeric range minimum/maximum/interior, invalid numbers | `numeric-*`; error feedback plus preserved active value |
| Color/attribute roles, built-in themes, format configuration slots | `display-settings-*`, `themes-*`; distinct stored setting values and visible formatting goals |
| Actual restart restoration of 23 nondefault settings | `settings-persistence`; query `set OPTION?` after restart, not just the saved file |
| Library, queue, separate named playlist contents, unequal volume, paused track and position | `restart-content`; active exports/status after process replacement |
| `resume`, `start_view` effect | `restart-content`, `startup-views`; all seven actual startup views and enabled/disabled queue restoration |
| `pl_env_vars` path substitutions | `playlist-environment`; variable tokens, loading them, and return to ordinary paths |
| `continue`, `continue_album`, `repeat`, `repeat_current`, `aaa_mode` | `end-*`; real track-end transitions/loop progress with short audio, not only setter values |
| `stop_after_queue`, `play_library`, `play_sorted` | `end-queue-*`, `end-playlist-source`, `end-sorted-order`, `end-tree-order`; conflicting source/order inputs |
| `auto_reshuffle`, `shuffle` | `random-order-effects` plus enum/cycle/display episodes; random identities are never frozen |
| `ignore_duplicates`, `lib_add_filter` | `duplicates-*`, `add-filter-*`; identical tag identities and positive matching/rejected sets |
| Native FLAC tags, Unicode, normalization, compilation, numeric tags and missing fields | `metadata-*`, `metadata-rich`; populated fields from deliberately varied inputs |
| FLAC/MP3/Vorbis/Opus/AAC/AIFF/WavPack and WAV channel/rate/bit-depth variations | `audio-formats-*`, `pcm-formats-*`; file identity, duration, codec; generated silent fixtures |
| CUE subtracks and offsets | `cue-sheet`; two subtrack URLs, titles and independently observed durations |
| Input decoder priorities and fallback | `decoder-priority`; active decoder disabled/enabled with a new uncached input |
| File output through the libao WAV driver | `audio-file-output`; actual decoded PCM channel/rate/width/frame count and four signed signal levels in both channels (two-unit tolerance), plus output counter |
| Hardware output plugins, physical CDDA, hardware mixers and device switching | Excluded: physical devices or other operating systems are unavailable; ordinary playback uses a real PulseAudio null sink |
| Basic and compound library/playlist sort keys | `library-sort-*`, `playlist-sort-*`; full-key ties grouped, mtime permutation differs from filename |
| bitrate, codec/profile, media, ReplayGain and play-count sorts | `sort-media-properties`, `format-extra-grammar/play-count-sort`; conflicting media properties and actual play completion |
| String/integer/boolean filter expressions; short/long syntax, glob/case, operators, grouping | `filter-expression-*`; explicit grouping selects a different set, no-match cases have valid channel evidence |
| Live simple/short filters and valid empty results | `live-filters-*`; native selection traversal rejects error text, negative cases bind to a positive observation |
| Short/long metadata format keys, precision, width/alignment/zero padding, literal characters | `format-fields-*`; rich populated inputs, leading-zero configuration changed for the duration case |
| Numeric format conditions and nesting | `format-conditions-*`; each comparison sees below/equal/above constants, true and false branches |
| Multiple format arguments, absent fields, `%X`, `%=`/`%!`, percentage widths | `format-extra-grammar`; actual counter increment, clipped-priority content, field widths and independent lines |
| Album duration/year aggregate, numeric position/duration, current bitrate/profile | `album-format-aggregates`, `format-current-bitrate`; populated real outputs |
| Exact audio sound quality, rendering colors, terminal pixel geometry, timing of buffers | Excluded as hardware/cosmetic/timing details; codec decoding, files, color settings, visible goals and stable state transitions remain tested |
| `device`, hardware `dsp.*`/`mixer.*`, `pause_on_output_change`, network character encodings | Hardware/network effects excluded as above; local character encoding setting roundtrips and input metadata remain covered |
| User `rc` arbitrary startup commands/plugins | Deployment fixes its own safe `rc`; confined `source` and native autosave/restore are observable and covered |

## Comparison, timing and evaluator budget

Each episode starts with a new solution copy and fresh data. Setup is unscored and explicitly declared. Stateful
checkpoints declare dependencies; visual expansion and marking have no backend proxy that could already pass
before the action. Their later checkpoints depend on the frontend verdict. View goals accept any equivalent layout;
program navigation reads cmus' own saved view after graceful quitting, rather than assuming a title row or substring.

Imports wait for the scenario's exact valid-entry count or complete expected membership. There is no 120 ms
"stable therefore finished" heuristic. Missing files, library de-duplication and filters have separate known
postconditions. Quitting is observed until the process exits, and playback transitions are polled. Crashes and
candidate errors affect the relevant points and the shared driver recovers before proceeding. Malformed or error
responses never count as valid empty selections. Private paths and irrelevant fields are normalized/ignored.

GUI episodes use 120 calls, 800,000 tokens and 1,200 active seconds, except `gui-marked-edit-1`, with 200 calls,
2,000,000 tokens and 2,400 active seconds, and `gui-filter-edit`, with 120 calls, 1,200,000 tokens and 1,200 active seconds. The evaluator is Kimi K3, effort high, using only the public terminal
operations. The final measured calls/token peaks must be at most 40% of the applicable budgets. Frozen record
durations determine per-episode wall limits; verifier timeout includes their sum plus overhead.
