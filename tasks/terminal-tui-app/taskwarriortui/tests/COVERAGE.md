# taskwarrior-tui coverage

Version 1.0.0. The reference is unmodified upstream **taskwarrior-tui
0.27.0** on **Taskwarrior 3.3.0**. Exact counts and budgets come from
`data/manifest.json`: **141 episodes (71 program, 70 GUI)** with **973
checkpoints** and **1,284 scoring points — 1,184 backend and 100 frontend** —
across 22 features. Backend points are deterministic program checks; each GUI
episode carries frontend goals with backend companions. Points are binary;
The task score is the fraction of episodes whose points all pass.

## Counting principle (what makes a point)

Each point maps to one **distinct rule or value** of the reference, never a
repeated parametrisation of the same rule:

- **Keys and prompts** — each key binding of the task report, the prompts, the
  menus, the views and the help, and each remapped key of the key
  configuration. The navigation keys and their aliases (j and Down, g and Home,
  J and PageDown, …) are separate points, since an implementation can bind one
  and miss the other; the wrap-around at both ends is one point for the line
  keys and one for the page keys. The line-editing aliases of the prompts (Left
  and Control+B, …) are exercised together in one point each.
- **Command syntax** — each Taskwarrior date expression, attribute, attribute
  modifier, virtual tag and filter form the prompts accept (the `add-*`,
  `modify*`, `filter-expressions*` episodes), each rejected input with its error.
  Date expressions of the same family are kept only where they resolve
  differently from the fixed clock (today's weekday, month and day, a year
  boundary).
- **Reports and columns** — each built-in report as taskwarrior-tui shows it
  (labelled columns with content, tasks in the report's filter and order,
  filter line), each column type it renders, a custom report; the report name
  in the top bar is checked where the report changes (menu, switching back).
- **Settings** — each `uda.taskwarrior-tui.*` setting value with an observable
  effect, and the Taskwarrior settings the interface exposes (contexts,
  defaults, user-defined attributes, priority values, date format, urgency
  coefficients, the due window, case sensitivity).
- **State** — the task data after each action (`task export` projections:
  status, dates, project, tags, priority, dependencies, recurrence fields,
  annotations, urgency), what survives a restart and a reset, undo of each action.
- **Command line** — every command of the `task` program except the excluded
  ones below: the text reports (built-in and custom), `information`, the
  commands that change tasks with their feedback (`add`, `modify`, `annotate`,
  `denotate`, `append`, `prepend`, `start`, `stop`, `done`, `delete`,
  `duplicate`, `log`, `purge`, `undo`, `import`), their confirmations (refused
  without an answer, answered on standard input per task, `all`, `quit`, the
  recurrence question), `config`, `context` and its subcommands, `export` with
  filters and reports, `count`, `_get`, the metadata listings (`tags`,
  `projects`, `summary`, `udas`, `columns`, `show`, `reports`, `commands`,
  `stats`, `help`, `version`), the charts (`history.*`, `ghistory.*`,
  `burndown.*`), `calendar`, `timesheet`, `calc`, `ids`, `uuids` and the helper
  commands (`_ids`, `_projects`, `_tags`, `_unique`, `_urgency`, `_uuids`,
  `_zsh*`, `_aliases`, `_columns`, `_commands`, `_config`, `_context`, `_udas`,
  `_show`, `_version`).
- **User goals (frontend)** — distinct evaluator-judged tasks, each with an
  objective backend companion.

## What is covered (per feature: backend / frontend points)

| feature | backend | frontend |
| --- | --- | --- |
| add | 180 | 14 |
| filter | 156 | 11 |
| cli | 143 | 0 |
| reports | 111 | 9 |
| actions | 96 | 15 |
| settings | 59 | 0 |
| modify | 49 | 9 |
| details | 50 | 3 |
| views | 41 | 6 |
| context | 41 | 4 |
| navigation | 38 | 3 |
| taskwarrior | 39 | 0 |
| selection | 24 | 9 |
| urgency | 31 | 0 |
| history | 22 | 5 |
| completion | 24 | 2 |
| persistence | 21 | 0 |
| editing | 18 | 2 |
| log | 12 | 2 |
| annotate | 10 | 3 |
| help | 10 | 3 |
| data | 9 | 0 |
| **total** | **1184** | **100** |

## Exclusions

- **Features that start other programs** are disabled in the reference by its
  sandbox and are not scored: the shell command prompt (`!`), opening a task in
  the external editor (`e`, and the `edit` command), user-defined shortcuts
  (`0`–`9`, `uda.taskwarrior-tui.shortcuts.*`), the periodic background process,
  Taskwarrior hooks and its `execute` command. Their keys only produce the
  reference's own error or nothing.
- **Command-line options of taskwarrior-tui** (`-r`, `--data`, `--config`,
  `--taskdata`, `--taskrc`) and its **environment variables** cannot be reached:
  the runtime starts `start.sh` without arguments.
- **Taskwarrior synchronisation** (`synchronize`, sync servers) needs a network
  service.
- **`import-v2`** reads the data directory of an older Taskwarrior from a path;
  the black-box interface offers no files to import from.
- **`news`, `logo`, `colors` and `diagnostics`**: the release notes are static
  text that waits for Enter, `logo` and `colors` only draw colours, and
  `diagnostics` reports the build and platform of the installed binary.
- **Colours** of rows, the navigation bar, the prompt, the calendar's due-date
  highlighting and the alternate row style are not scored (the `style.*` and
  `use-alternate-style` settings). The selection-style settings
  (`selection.bold/italic/reverse`) are, through the selected row's text
  attributes. `selection.dim` and `selection.blink`, the scroll bar glyphs,
  `tick-rate` and `task-detail-prefetch` have no other observable effect and are
  not scored.
- **Emoji and other characters beyond U+FFFF** are not asserted: the reference's
  interface draws them as replacement characters. Wide characters below that
  range are (`details-wide`, `add-attributes`).
- **Automatic refresh after changes made outside the application** is not
  asserted: with the fixed clock the reference only shows them after a refresh
  (`r`), which is what the refresh points check.
- **`K` in the Calendar view** is not asserted (the reference's help describes it
  as a decade back, but the key does not change the year there); `J`, `j`, `k`,
  Up and Down are.
- **The order among tasks of equal sort key** is not asserted where a report's
  sort ties (the `long` report, whose sort key `modified` is the same for every
  imported task, and lists with a recurring template and its instance): those
  checks compare the listed tasks as a set. The command-line
  helpers that list tasks in storage order (`_urgency`, `_zshids`, `_zshuuids`)
  are compared as sorted lines.
- **Random and installation values** are never compared: UUIDs that the
  application generates (tasks added, duplicated or created by recurrence during
  an episode) are masked in the details pane and in command output and are not
  part of any export projection; fixture UUIDs are fixed and compared. They are
  the only values that differ between records of the reference, in the screens
  the evaluator sees as reference evidence. The data location in `_show` and the
  undo and sync transaction counts in `stats` depend on the installation and are
  left out.

## How points are checked

- Every check reaches the application through the task's black-box runtime, the
  same code that serves the reference to the model: `task` (the application's
  Taskwarrior command line: `task export` for the tasks, the output of the
  other commands, `_get`, `count`, `config` and `context` results for the
  configuration), and `screen` facts.
- **Screen facts are parsed from the reference's terminal display**. A report
  row is identified by the
  task description it contains (fixture and episode descriptions are unique);
  the report is the rows between the header row under the top bar and the
  full-width rule above the details pane; the **selected** task is the row
  whose first columns carry the selection indicator (`•`, or `⦿`/`⦾` while tasks
  are marked), **marked** tasks carry `✔`/`⦿`; the report and context names are
  read from the `report [context]` label at the right end of the top bar; the
  prompt is the title and input line in the last two rows (a completion
  suggestion drawn after the input in a style of its own — any colour or text
  attribute different from the typed text — is not part of the input); the
  details pane is parsed as Taskwarrior's Name/Value table (column boundary from
  its dashed rule); popups and menus are rounded boxes with their title in the
  top border; report columns are read under their header label; the active view
  is recognised by its content (the task report under its header row,
  Taskwarrior's project summary, the timesheet table, month grids), and the
  Projects, Timesheet and Calendar views are compared as their text rows with
  whitespace squashed. Colours are never compared; text attributes only in the
  selection-style points.
- Command-line output is compared as its lines with whitespace squashed;
  generated UUIDs are masked. Text output is requested for 120 columns and 40
  rows (`rc.defaultwidth`, `rc.defaultheight`), since the command runs without a
  terminal.
- Export projections compare only behaviour: dates in Taskwarrior's UTC form
  whatever the separators, tags as sets, dependencies and parent tasks by
  description, annotations by text in date order, urgency within 0.011.
- Setup imports the fixture tasks (`task import`) and applies settings
  (`task config`) through the application's own command line and restarts it.
  Setup never counts; a failed setup blocks only the checkpoints that declare
  it.
- **Every program checkpoint starts from a known state**: its own fresh fixture
  (a reset first), or a restart of the application on the same data, which
  clears popups, prompt text, the live filter, the view, the selection and the
  marks. A checkpoint that continues from the screen or data the checkpoint
  before left declares that checkpoint as a dependency, so one defect costs its
  own points and those of the checkpoints that build on it, not unrelated ones.
- Where a check could pass for an application that does nothing (an unchanged
  task after a rejected input, a closed menu, an application that is no longer
  running, an empty history), the point is bound with `requires` to a positive
  point of the same rule, or the action and its undo are separate checkpoints
  with a declared dependency.
- Dependent checkpoints run only when the prerequisite's backend points passed
  (or its frontend points when it has none). A crashed or exited application is
  restarted with the same data before the next checkpoint, so one crash costs
  only its own checkpoint's points.

Frontend goals give exact inputs and the visible result; equivalent keys,
prompts, menus and layouts are accepted. In frontend judgements, colours, exact
messages, column widths and the screen layout are not scored; the backend
points above compare the screen conventions and the command line exactly.

`reference/` contains the deterministic drivers for the pinned standard only;
its recipes are never the candidate contract.

## Interface and budgets

The evaluator operates the application through the runtime's GUI operations
(`key`, `keys`, `type`, `wait`) in a **120x36** `xterm-256color`
pseudo-terminal and observes the runtime's `screen` snapshot: rows with their
row numbers, the cursor, the style runs that differ from the base style, and the
process state. `resize`, the command line and the lifecycle steps are framework
operations. GUI episodes use the budget formula scaled by checkpoint count `n`:
calls `min(150, 120 + 30n)`, tokens `min(1400000, 1000000 + 200000n)`, active
seconds `min(1800, 600 + 240n)`.
