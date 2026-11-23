# calcurse coverage

Version **1.0.0**, unmodified upstream **calcurse 4.8.2**.
The manifest contains **123 episodes (72 program, 51 GUI)**,
**720 checkpoints**, and **1326 points: 1206 backend and 120 frontend**.
Each point is binary. The task score is the fraction of episodes whose points all pass.

## Counting and comparison

A program point compares one meaningful operation result, field projection, or
state transition. Queries cover selection, date ranges, limits and ordering;
filters cover type unions, regular expressions, hash prefixes, inclusive and
exclusive time boundaries, conjunctions, priority and completion. Formatting
checks combine related duration/time conversions in one assertion per boundary
fixture, avoiding repeated credit for constant zero fields. Recurrence cases
exercise distinct generation rules on all-day and timed items, near and far from
the origin, plus native and iCalendar serialization. Import cases distinguish
parsing, persistence, linked text and export. Notes are scored separately only
when the input actually carries text properties. Invalid mixed imports include
valid surrounding components, so ignoring all input cannot satisfy them.

Public text records are compared as multisets of nonblank lines; record order is
not frozen. CLI query order and requested formatting are observable behavior.
Source-code locations, process IDs and getopt's executable prefix in diagnostics
are normalized. iCalendar comparisons validate VCALENDAR, VERSION:2.0 and paired
component boundaries before selecting public data. Property/component order,
RRULE part and list order, explicit INTERVAL=1/WKST=MO, equivalent duration/end
forms and irrelevant extension metadata do not affect equality. Duplicated items,
text, dates, recurrence limits/exceptions, and alarm ACTION/TRIGGER remain
significant. UID is compared only when explicitly requested. The parser accepts
the reference's all-day EXDATE midnight suffix and does not demand UID, DTSTAMP
or alarm DESCRIPTION fields that upstream does not emit. No hidden product state
or fixed screen coordinates are checked.

The daily, weekly, monthly and yearly GUI recurrence goals normalize redundant
default constraints. In particular a weekly DTSTART weekday, monthly DTSTART
day, and yearly DTSTART day/month are equivalent to their simple forms. Genuine
weekday/day/month expansions, intervals, until dates and exceptions remain
significant. CLI/native serialization checks retain their specified format.
Visible text checks require their positive content to exist before a value can
be recorded. Cancellation cases first perform a successful creation through the
same interface. Errors and missing state fail the affected point, not the run.

GUI checkpoints describe user results with exact inputs, and accept equivalent
application operations. Their backend companions check directly resulting data,
settings, or visible content. State dependencies are explicit; prerequisites use
backend outcomes when available. Independent program scenarios reset the runtime
and place their own small fixtures before each checkpoint. The shared driver
recovers a crashed application before continuing.

## Feature map

| Feature | Backend | Frontend |
| --- | ---: | ---: |
| appointments | 15 | 15 |
| configuration | 44 | 18 |
| display | 0 | 1 |
| editing | 23 | 0 |
| events | 9 | 9 |
| filters | 190 | 0 |
| formatting | 62 | 0 |
| icalendar | 227 | 3 |
| keybindings | 10 | 4 |
| navigation | 15 | 17 |
| notes | 5 | 3 |
| notifications | 15 | 6 |
| persistence | 33 | 4 |
| queries | 46 | 0 |
| recurrence | 427 | 26 |
| search | 9 | 0 |
| todos | 14 | 14 |
| validation | 62 | 0 |
| **Total** | **1206** | **120** |

- Appointments and events: timed, punctual and all-day creation; compact and
  duration time input; overnight/multiday spans; Unicode descriptions; changing
  description, start, end and duration-preserving moves; copy/paste; deletion.
- Recurrence: daily/weekly/monthly/yearly intervals, until/count, exceptions,
  weekday/month/month-day filters, ordinal and negative ordinals, month ends,
  leap days, week origins, distant queries, editing, navigation and deletion of
  one occurrence or a complete series.
- Todos: priorities 0–9, completed/uncompleted selection, description edits,
  priority changes, completion/reopening, deletion, ordering and attached notes.
- iCalendar: DATE/DATE-TIME, UTC/TZID, end/duration, recurrence and exceptions,
  alarms, descriptions/location/comments, folded/escaped/Unicode text, todos,
  invalid component recovery, export properties, UID, filtered export and pcal.
- Native data and persistence: queries/grep, purge/legacy filter, read-only mode,
  note collection, save/write/quit, restart, reload, cancellation, line editing
  and custom key actions. Standard output, help and version are public CLI
  observations; startup readiness does not rely on them.
- Configuration and display: date input/output formats, time/day headings,
  completed-task view, month/week view, default panels, multiple-day display,
  autosave/autogc/periodic-save settings, confirmations, week start, compact
  panels, empty-day text, calendar navigation and complete item descriptions.

## Public-function mapping

| Offline function | Episodes and observation |
| --- | --- |
| Short/long search entry points, regex errors, Unicode and query combinations | `search-entrypoints`, `search-invalid`: actual CLI selection and diagnostics |
| Interactive iCalendar/pcal export | `gui-export-files`: visible success and semantic files; `export-replace-cancel`: overwrite, cancellation and import round trip |
| Key menu add/remove/conflict and persistence | `gui-key-configuration`: public key bindings plus actual save after restart; `key-binding-conflict`: conflict warning, retained mapping and behavior of removed/retained aliases |
| Editing existing recurrence | `edit-recurrence-rules`, `gui-edit-recurrence-rule`: interval, until, weekday/month/day sets and exception edits, checked by near and distant occurrence queries |
| Notification bar's static configuration | `gui-notification-display`, `notification-settings`: display toggle, live date/time format, warning interval and notifyall options via conf and visible fixed-time output |
| Configuration effects and reload choices | `configuration-effects`: confirm-delete/quit and autogc on/off with real data; `gui-reload-choice` and `reload-persistence`: retaining/discarding an unsaved edit |

Upstream's export filename prompt overwrites existing files directly; there is
no overwrite-confirmation dialog to test. Cancellation is covered at that actual
prompt and bound to a successful prior export. The key-configuration tests
exercise actions after changing bindings, rather than only comparing the keys
file. Note-import assertions select only top-level item text properties (and
TZID metadata), require nonempty notes, and compare the stored records that link
them; an alarm DESCRIPTION is not an item note.

## Exclusions and environment

The reference is the real upstream executable. A launch-time Landlock/seccomp
policy confines it to its instance and read-only terminal/locale/time-zone data;
it cannot launch another process. Consequently external note editors/viewers,
help pagers, pipe-to-command, notification commands, hooks, merge tools and the
background daemon are unavailable. The `docs` channel serves the upstream help
and manuals that the external help pager would otherwise show. Note files,
links, import/export and collection remain covered through native product data.
The companion CalDAV/synchronization scripts require external services and are
not part of the interactive executable evaluated here.

The runtime keeps the locale at C.UTF-8 and the time zone at UTC, with wall time
fixed at 2026-03-18 09:30:00; real-time passage, timed reminders, periodic timer
firing and other locales/time zones are not exercised. Their relevant stored
settings and deterministic formatting remain covered. The interface does not
expose command-line overrides of the data/config root or background daemon.
Exact colours, panel geometry, separators, terminal glyphs and notification
animation are not acceptance criteria: implementations may choose their visual
design. Functional views, navigation, contents and configurable values are
checked. Platform date limits and malformed native files that only abort startup
are not separately scored; malformed CLI arguments and recoverable import errors
cover rejection without turning crashes into a compatibility requirement.
The terminal observation's hidden cursor coordinates can vary with asynchronous
redraws; no program check or frontend acceptance depends on those coordinates.

## Runtime and evaluator budgets

Every setup, action and observation uses `environment/runtime/broker.py`:
`place`, `files`, `cli`, terminal operations and lifecycle operations are all
advertised by `help`. The evaluator sees only `key`, `keys`, `type`, `wait` and
the settled `screen` observation, in a 120×36 xterm-256color terminal. It cannot
use the setup/checking channels. Each GUI episode has one evaluator session.

For n checkpoints, budgets are calls min(160, 100 + 30n), tokens
min(1600000, 900000 + 250000n), and active seconds min(1800, 600 + 300n).
The longer key-configuration and recurrence-rule editing episodes allow 240
calls, 2400000 tokens and 1800 active seconds for their multi-prompt operations.
Budgets are checked against the standard-answer oracle; calls and token peak
must stay within 40% of the allowed amount. Program wall limits are
max(900 seconds, five times the recorded duration); GUI limits add their active
budget to max(600 seconds, five times the recording). The verifier timeout in
`task.toml` includes all episode limits plus startup margin.
