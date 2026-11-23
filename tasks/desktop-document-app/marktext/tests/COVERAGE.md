# Reviewed MarkText coverage

The suite has 59 episodes (30 program and 29 GUI), 301 checkpoints,
354 backend assertions and 30 frontend assertions, for 384 points.

The quote-rendering episode retries selection and Copy as HTML until the
clipboard changes and settles, within a bounded wait. Identical consecutive
results remain valid; no expected document content is used to detect readiness.

Version 1.0.0. The reference is the unmodified upstream **MarkText
0.23.0** Linux release, launched inside a Landlock sandbox that confines only the
reference installation (see "Reference isolation" below). Exact counts and
budgets come from `data/manifest.json`. Points are binary. The task score is the fraction of episodes whose points all pass.

## What is covered

| Coverage | Behavior |
| --- | --- |
| Serialization round-trip (program) | Open a Markdown document, mark it modified and save it back; the saved file is MarkText's canonical re-serialization. Every fixture is authored in a **non-canonical** form that MarkText normalizes, so the saved document differs from the input: headings (space collapsing, closed-hash stripping, trailing-space/tab trimming, blank lines between adjacent blocks), bullet/ordered/task lists (marker spacing, nesting re-indentation, `[X]`→`[x]`), fenced/indented code (info-string trimming, fence closing, blank-line trimming), block quotes (added `>` spacing, blank separator lines, lazy-continuation fixups), GFM tables (column padding and alignment), and whitespace/structure (blank-line collapsing, leading-blank removal) |
| Copy as Markdown (program) | Open a document, select all and copy; the clipboard holds MarkText's canonical Markdown — the same normalizing fixtures through a different candidate-portable channel (a document that is not re-serialized on copy fails) |
| Copy as HTML / rendering (program) | Open a document, select all and copy as HTML; the clipboard holds the rendered HTML. Covers the rendering of every construct, including those the round-trip preserves verbatim (emphasis, inline code, links and images, thematic breaks, math, raw HTML, hard breaks) as well as headings, lists, tables, code and quotes. The HTML is reduced to a semantic tree (tags, text and meaningful attributes, without ids, styles, classes or editor scaffolding) |
| Editor commands (program) | Inline formatting applied to a selection by keyboard shortcut (bold, italic, underline, strikethrough, inline code, highlight, inline math, clear formatting), heading commands (levels 1–6, upgrade, degrade, join lines) and block commands (bullet/ordered/task list, block quote, code fence), scored on the saved Markdown |
| Editing (GUI) | Making the visible text bold/italic/struck/underlined/highlighted/inline-code/inline-math, turning paragraphs into headings, lists, block quotes and code blocks through the editor, and a multi-step compose goal; scored visibly, with a saved-document companion where the serialization is operation-independent |
| Authoring (GUI) | Typing Markdown that the WYSIWYG editor renders (headings, emphasis, lists) and saving it |
| Files and export (GUI) | Save As to the outbox, Export as HTML (the rendered document body and text) and Export as PDF (the document's page text) |

Canonical serialized and rendered outputs are frozen observations of the pinned
reference. Input documents contain ordinary Markdown.

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the
  same code that serves the reference to the model: `open` (opening an inbox
  document by relaunching the application with its path), GUI operations and
  observations, `upload`, `list_files` and `download` for the exchange folders,
  and `clipboard_text`/`clipboard_html`/`clipboard_image`. Saved Markdown and the
  plain-text clipboard are compared as text with only line endings normalized;
  exported and copied HTML is reduced to a semantic tree and its visible text;
  exported PDF to page sizes and extractable text.
- Program episodes drive the application deterministically (open, select,
  keyboard shortcut, save or copy) with no model; each checkpoint produces and
  scores one artifact. Whether a document opened is enforced by the artifact
  comparison itself — a non-canonical fixture that did not open re-serializes to
  something other than the frozen canonical output — rather than by any window
  label, so the check does not depend on how a faithful editor names the open
  document.
- GUI episodes state a user goal with visible acceptance judged by the evaluator
  agent and, where the serialization is operation-independent, a backend
  companion on the saved or exported document; points that only confirm an
  unchanged document (an export leaves the document in place) are bound
  (`requires`) to the artifact check. Block commands whose saved serialization
  depends on the exact selection/keystrokes (loose-vs-tight lists, a code fence
  around a whole-paragraph selection) are judged visibly only; their
  serialization is covered deterministically by the program episodes instead.
- A crashed application is restarted with the same data before the next
  checkpoint. A candidate defect (a document it will not open, a command it does
  not implement, a crash) costs only the affected points; verifier faults and
  provider outages invalidate the run instead.

## Reference isolation

The reference product is launched through the fail-closed Landlock wrapper
`solution/jail.py`. Its rules cover the application tree, system resources,
private state and exchange directories. The installation is root-owned and
read-only. Native file dialogs also use the runtime's exchange-path validation.
The shared desktop action hooks and session directory layout are supplied by
the runtime.

## Not scored

- **Preferences configuration, its effect on serialization, and settings
  persistence across restart.** MarkText serializes a document in its existing
  source form, so most preferences change only newly editor-generated content,
  not a round-trip; and the settings controls carry no stable accessible names
  (their labels are separate static text), so they cannot be driven as a
  deterministic, observable program episode. This leaves the
  instruction's restart-persistence requirement exercised only indirectly
  (saved documents and a reused data directory survive `restart`).
- Document conversion through pandoc (Import, Convert with Pandoc), image
  uploaders, and the PlantUML/diagram and link-preview network features (the
  reference container has no network and no pandoc, and the sandbox blocks the
  shell-command uploaders), printing, the spell checker, find-in-folder, and
  opening documents or folders in other applications are outside the scored episodes.
- The in-editor view modes whose result the evaluator cannot read as a document
  (focus, typewriter, source-code and read-only mode) are not scored.

## Interface and budgets

The surface is the task runtime's desktop (shared desktop module
`blackbox_desktop.py`): a private 1280×900 Xvfb display, D-Bus and AT-SPI
session per episode, run as the candidate user; one virtual desktop without
background menus or launchers, ordinary windows maximized and dialogs centered.
Observations are the runtime's accessibility snapshot (controls with role, name,
description, value, states and bounds) plus a full-screen screenshot; input is
pointer and keyboard events, accessible default actions, zoom into a screen
rectangle, and window activation. The application's menu is reached through the
accessible "Application Menu" button; native file dialogs are not on the
accessibility bus but are visible in the screenshot and confined to the inbox
and outbox (a typed exchange path confirmed with the button in the dialog's
bottom bar). GUI budgets scale with checkpoint count n: calls min(160, 55+30n),
seconds min(1800, 540+210n), tokens min(1.5M, 500k+250k·n).

reference/ contains the deterministic recipes for the pinned standard only.
They drive the same runtime operations as the evaluator and the model and are
never the candidate's frontend contract.
