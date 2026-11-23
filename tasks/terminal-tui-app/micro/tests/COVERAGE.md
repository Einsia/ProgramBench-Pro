# micro coverage

Version 1.0.0. The reference is the unmodified upstream **micro 2.0.15** release binary. Exact counts and
budgets come from `data/manifest.json`: **225 episodes (106 program, 119 GUI)** with **1112 checkpoints** and
**1421 scoring points — 1295 backend and 126 frontend** — across 24 features. Backend points are deterministic
program checks; each GUI episode carries evaluator-judged frontend goals bound to backend companions. Points are
binary; The task score is the fraction of episodes whose points all pass.

## Counting principle (what makes a point)

Each point maps to one **distinct rule or value** of micro 2.0.15 with its default configuration, never a repeated
parametrisation of the same rule, and each case is chosen so that a plausible wrong implementation observes
something different. The rule categories are:

- **Default keys** (`keys-*`): each default binding of the editing pane, in the situations where its rule shows (word
  boundaries with punctuation runs and underscores, line wrap at both ends, column memory across short lines and
  tabs, toggling keys, paragraph and page movement, auto-indentation, line joins, clipboard accumulation of repeated
  line cuts, overwrite mode, selection collapse); the saved file, the cursor position and the message are separate
  facts of one keypress.
- **Bindable actions and binding syntax** (`act-*`, `cmd-bind`, `cmd-showkey`): each action without a default key,
  bound in `bindings.json`; chains with `,` `|` `&`, key sequences, the `buffer`/`command` groups, case rules of
  `Alt-`/`Ctrl-`, `lua:` and `command:` bindings, `None`, broken files and unknown actions; `bind`, `unbind`,
  `showkey` (also with key sequences) and what they write to `bindings.json`.
- **Commands** (`cmd-*`): every offline command of `help commands` with its arguments and error paths (`set`,
  `setlocal`, `toggle`, `togglelocal`, `reset`, `show`, `goto`, `jump`, `save`, `quit`, `open`, `reopen`, `vsplit`,
  `hsplit`, `tab`, `tabmove`, `tabswitch`, `help`, `log`, `raw`, `cd`, `pwd`, `retab`, `eval`, `replace`,
  `replaceall`, `comment`, `reload` of edited `settings.json` and `bindings.json`, `plugin list`), quoting rules and
  unknown commands.
- **Options** (`opt-*`, `cmd-set`, `cmd-toggle`): the effect of each option that works offline (editing, searching,
  display, status line directives, files and encodings, splits, reloading, mouse, clipboard) and the rules of
  `settings.json` (what is written for `set`, defaults left out, glob and `ft:` sections, JSON5, broken files,
  unknown keys kept, command-line options kept out); encodings include UTF-16, Shift JIS, Windows-1252 and GBK.
- **Find and replace** (`find-*`, `replace-*`, `regex-*`): regular-expression and literal search, case rules,
  wrap-around, find next and previous, the prefilled prompt and its history; character classes, counted, lazy and
  greedy repetition, groups and inline flags, including how the default case-insensitive search treats them; replace
  with every answer, flag, template form, selection and message.
- **Editing machinery** (`undo-*`, `multi-*`, `macro-*`, `complete-*`): undo grouping by second, redo and its
  clearing, the modified flag after undo; every multiple-cursor key and how edits, movement, clipboard and undo apply
  to all cursors; macro recording and playback; word completion and its cycling.
- **Plugins** (`plug-*`): the comment syntax of 38 filetypes and the comment plugin's line, selection, indentation and
  toggling rules; autoclose pairs, skipping, deletion and brace expansion; ftoptions; diff gutter markers.
- **Filetypes and highlighting** (`filetype-*`, `syntax-*`, `syntax-more-*`): detection of 94 file names,
  extensions, headers and ambiguous extensions (content signatures), how far `detectlimit` lets a signature be
  searched, and whether keywords, strings and comments of 25 languages are drawn differently from plain text.
- **User runtime files** (`usersyntax-*`, `usercolors-*`, `userhelp-*`, `userdefault-*`): syntax files in the
  configuration directory (a new filetype, detection by file name, header and signature, pattern rules, regions with
  skip patterns, embedded languages, replacing a built-in syntax and the default one), colorschemes (attributes,
  `include`, unlinked groups, subgroup fallback), help topics, and their Tab completion.
- **Panes, view, command bar, command line, persistence, mouse and text** (`view-*`, `prompt-*`, `cmdkey-*`, `cli-*`,
  `mouse-*`, `text-*`): split and tab keys, the view following the cursor, prompt editing and Tab completion (with
  the offered lists of commands, colour schemes, filetypes and help topics), the command bar's own key map (cursor,
  word, selection, deletion, clipboard, undo, overwrite, history and abort keys) and its bracket autoclose,
  `-version`, `-options`, `-help` and every argument form, what survives a restart (settings, bindings, history,
  cursor, undo, backups and their recovery), clicks, double/triple clicks, drags (also starting with a double click)
  and divider drags, wide and combining characters, tabs, empty and unterminated files, byte-order marks, NUL bytes
  and mixed line endings.
- **User goals (frontend)**: distinct evaluator-judged tasks, each with an objective backend companion.

## What is covered (per feature: episodes and points)

| feature | program episodes | GUI episodes | backend | frontend |
| --- | ---: | ---: | ---: | ---: |
| keys | 9 | 0 | 160 | 0 |
| filetypes | 10 | 0 | 148 | 0 |
| options | 10 | 20 | 115 | 21 |
| search | 7 | 11 | 88 | 12 |
| files | 6 | 13 | 84 | 14 |
| actions | 10 | 0 | 97 | 0 |
| display | 8 | 1 | 77 | 1 |
| splits-tabs | 4 | 15 | 60 | 17 |
| editing | 0 | 38 | 38 | 38 |
| plugins | 6 | 1 | 70 | 1 |
| command-bar | 6 | 0 | 69 | 0 |
| keybindings | 6 | 4 | 63 | 4 |
| commands | 4 | 0 | 40 | 0 |
| navigation | 2 | 8 | 24 | 8 |
| multicursor | 2 | 2 | 25 | 2 |
| cli | 3 | 0 | 23 | 0 |
| text | 2 | 0 | 23 | 0 |
| undo | 1 | 1 | 18 | 3 |
| mouse | 2 | 0 | 20 | 0 |
| settings | 2 | 0 | 16 | 0 |
| persistence | 3 | 0 | 16 | 0 |
| autocomplete | 1 | 1 | 9 | 1 |
| macros | 1 | 1 | 7 | 1 |
| help | 1 | 3 | 5 | 3 |
| **total** | **106** | **119** | **1295** | **126** |

## Exclusions

The reference cannot run other programs or load user code, so these features are **not part of the evaluation**,
and the reference's behaviour for them (environment-specific errors) is never asserted:

- running programs: `run`, `term` and terminal panes, `textfilter`, the shell prompt (`Ctrl-b`, `ShellMode`), the
  linter plugin and `lint`, saving with `sudo` (`autosu`, `sucmd`), external clipboard tools (the `external`
  clipboard falls back to micro's internal clipboard, which is covered), the git integration of the `diff` and
  `status` plugins (`$(status.branch)`, `$(status.hash)`, the git diff base), and `Suspend`;
- user Lua code: `init.lua`, plugins in `plug/`, `lua:` bindings to user functions, `lockbindings` (it only affects
  Lua code);
- the plugin manager's network commands (`plugin install`, `update`, `search`, `available`, `pluginchannels`,
  `pluginrepos`) and `plugin remove` (only built-in plugins exist, and they cannot be removed); `plugin list` is
  covered;
- options without an observable effect in this terminal: `truecolor` and `xterm` (the terminal is fixed), `-debug`,
  `-profile`, `-clean`, `-config-dir`;
- volatile output: `memusage` (process memory) and the backup-recovery prompt's creation time (the prompt is checked
  through its fixed first lines only);
- the `$(bind:Action)` status directive for actions bound to more than one key (micro picks one of the keys in an
  unspecified order; directives of single-key actions are covered).

Colours are never compared: highlighting is checked as "this cell is drawn differently from that cell" and text
attributes (underline, reverse) without colours, so an implementation may use any palette. Exact colour schemes
other than their highlighting facts are out of scope.

## How points are checked

- Every check reaches the application through the task's black-box runtime, the same code that serves the reference
  to the model: `workspace` (the saved files byte for byte; listings for created directories), `config`
  (`settings.json`/`bindings.json` compared as JSON, so key order and whitespace are free), `cli` (exit status and
  the printed lines; `-options` compared as option names and default values), and screen facts: the fields of the
  status line of micro's default format (name, modified/read-only/overwrite markers, `(line,col)`, filetype, line
  format, encoding), the message line (the last row), the tab bar (names and the active tab), the panes (one status
  segment per pane), the line numbers of the ruler, selected text rows where the layout itself is the behaviour
  (wrapping, tab width, rulers, splits), and cell-style comparisons.
- Messages are compared as micro writes them, except text that comes from a library rather than from micro (Go's
  number, encoding, regular-expression, JSON and file-system errors): there only micro's own words in front of it
  (for example `Invalid argument`, `Error reading settings.json`) or the fact that an error message instead of the
  command prompt is shown are compared.
- Every program checkpoint starts the editor afresh on its own file, with empty `settings.json` and `bindings.json`
  written first; a checkpoint never depends on another checkpoint's state, and a crash or a stuck prompt costs only
  that checkpoint. A message a later save would overwrite is read from the screen captured just before the save.
- Points that only verify a refusal or that nothing changed use `requires` to bind them to a positive point of the
  same episode (for example "Backspace at the start of the buffer changes nothing" binds to a working Backspace).
- A GUI goal that starts from prepared splits or an open help pane checks that starting state after its setup; an
  interface that does not reach it has its setup fail, so the goal's points are blocked instead of being met by
  doing nothing.
- Timing-dependent behaviour is driven deterministically: undo bursts start early in a second and separate undo
  steps are more than a second apart (micro groups undo by second), backups are awaited for ten seconds (micro writes
  them every eight), and the runtime waits for the application to answer each input before reading the screen.
- `reference/` contains the deterministic drivers for the pinned standard only; its screen parser is never the
  candidate contract.

## Interface and budgets

The evaluator operates the application through the runtime's GUI operations (`key`, `keys`, `type`, `paste`, `wait`)
in a **120x36** `xterm-256color` pseudo-terminal and observes the runtime's `screen` snapshot: rows with their row
numbers, the cursor, the style runs that differ from the base style (selections, highlights, the cursor line) and the
process state. `mouse`, `resize`, `place`, `modify` and the lifecycle steps are framework operations of program
episodes and setup. GUI episodes use the budget formula scaled by checkpoint count `n`: calls `min(180, 120 + 30n)`,
active seconds `min(1800, 600 + 200n)`, tokens `min(1500000, 900000 + 200000n)`. They are calibrated on the standard
answer with the real evaluator model, whose per-episode peak stays below 40% of each budget.
