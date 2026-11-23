# lazygit coverage

The specification scores 221 episodes (130 program, 91 GUI), 397 checkpoints and 820 points (709 backend, 111 frontend) across 26 features.

| Feature | Episodes | Backend | Frontend |
| --- | ---: | ---: | ---: |
| bisect | 4 | 14 | 2 |
| branches | 29 | 64 | 12 |
| cli | 1 | 4 | 0 |
| clipboard | 6 | 18 | 0 |
| commits | 33 | 85 | 23 |
| conflicts | 8 | 40 | 5 |
| diff | 4 | 9 | 0 |
| discard | 7 | 22 | 6 |
| file-formats | 20 | 114 | 0 |
| files | 13 | 31 | 7 |
| menus | 6 | 61 | 0 |
| navigation | 7 | 21 | 1 |
| patch | 2 | 9 | 0 |
| rebase | 13 | 35 | 9 |
| reflog | 4 | 9 | 2 |
| remotes | 4 | 9 | 2 |
| search | 6 | 23 | 6 |
| staging | 9 | 21 | 6 |
| startup | 1 | 5 | 0 |
| stash | 12 | 27 | 14 |
| state | 2 | 4 | 0 |
| submodules | 4 | 15 | 2 |
| sync | 9 | 20 | 7 |
| tags | 10 | 22 | 5 |
| undo | 3 | 16 | 0 |
| worktrees | 4 | 11 | 2 |
| **Total** | **221** | **709** | **111** |

## Behavior covered

- Files: individual, directory, range, hunk and line staging; unstage and discard; reset modes; ignore rules and exclusions; tracked/untracked filters. File cases distinguish empty and binary content, Unicode, quoting and glob characters in paths, nested paths, symlinks, executable modes, CRLF, missing final newline, tabs, long lines, deletion and rename. Index contents, committed patches and persistence are checked separately.
- Commits: subject and multiline description, Unicode and trailers, rewording with a prefilled body, amend, authors and co-authors, fixup commits, squash versus fixup (including complete messages), reorder, drop, revert, reset, ranges and selecting all branch commits. Custom patches cover copying, removing, reversing, applying, moving to the index and splitting into commits before or after their source.
- Branches and history: create, rename, checkout, forced checkout, invalid names, previous branch, moving unpushed commits, branch sorting, upstream settings, local/remote deletion, merges, rebase and todo actions, bisect, reflog, multi-step undo/redo of drops, resets and checkouts. Conflict fixtures distinguish continue, abort and skip and retain the commits after a conflict; stash-pop conflicts retain the stash.
- Local synchronization: push, pull, fetch, force push, fast-forward, remote branches, lightweight and annotated tags, and local/remote tag deletion. Every remote is a local bare repository.
- Repository management: submodule add, remove, update, enter and return; worktree create, detached worktrees, switching, removal and branch removal. Clipboard checks cover names, paths, hashes, authors, subjects, bodies and patches.
- Interface and persistence: numbered panels, menus, selection, search, page movement, tree expansion and flat view, screen modes, resize, diff context, whitespace, rename similarity and comparisons between refs. The application state exposes recent repositories and the persisted command-log preference. Documented CLI outputs are also checked.

## Exclusions

- External execution is disabled: shell/custom commands, file and hunk editors, configuration editing, editor-based commit/reword, external diff/merge tools, system openers and browsers. The keybindings menu is disabled because it can invoke these actions without a key.
- The shared `e` binding is disabled for external-file editing. Consequently, commit editing that stops a rebase, remote name/URL editing and submodule URL editing through that binding are unavailable too. Rebase todo pick/drop/squash/fixup/reordering and continue/abort/skip remain covered.
- Hosting-service and browser integrations, credential prompts, network transports, update checks and git-flow require unavailable online services or additional software. Push/pull/fetch are exercised with local remotes.
- Themes, icons, keybinding configuration, languages and external diff renderers use the locked system configuration. Startup dialogs, tips, background fetch/refresh, animation and mouse input are disabled for deterministic keyboard operation.
- Relative ages and generated temporary patch paths are normalized. Clipboard paste is unavailable because no clipboard read command is configured. A soft reset to the current HEAD has no observable repository effect; its menu remains covered, and soft reset to another ref has behavioral checks.

## Checks and equivalence

All observations use the public runtime channels. Repository checks project branches, tracking, parents, messages, status, tags, stashes, reflog, remotes and worktrees. Read-only Git output, workspace bytes/modes/link targets, clipboard contents, application state and CLI output supplement those projections. Commit identifiers, private paths and relative ages are normalized.

The screen parser locates numbered boxes from their corners. It accepts rounded, square, heavy and double borders, derives each width from geometry and identifies focus by relative style differences. Selection uses the visible highlight or position indicator. Checks compare panel items, selected items, popup contents and relevant main-view facts; diff checks use hunk headers, changed lines and summaries. Foreground palettes and exact panel widths are not scoring targets. Screen-mode checks explicitly examine which panels are visible.

GUI goals allow equivalent routes and bind every frontend claim to backend results. Clipboard operations are program checks because selecting an item alone does not demonstrate a visible copy result. Identical independent program/GUI observations are consolidated into the GUI companion; program episodes cover distinct states, boundaries and recovery paths. Unchanged or empty results are bound to positive assertions or explicit prerequisite checkpoints.

Program episodes send the public reference keys from `help.reference_controls`. Every episode uses a fresh instance. Independent scenarios reset their repository; dependent steps declare their prerequisites. Candidate errors fail the affected points, while verifier or provider failures invalidate the run.

## Interface and budgets

The evaluator uses `key`, `keys`, `type` and `wait` and reads `screen` in a 120x36 terminal. The framework also uses documented setup, lifecycle, resize and inspection operations; resize scenarios restore the initial dimensions. Printable text is typed separately from Enter/Tab key operations, including multiline message bodies.

File-case recipes wait up to ten seconds for the submitted commit subject to appear through the read-only Git channel before observing the resulting history and patch. This accommodates asynchronous writes after the terminal becomes quiet; the regular assertions still decide whether the operation succeeded.

For a GUI episode with `n` checkpoints, budgets are `min(220, 130 + 30n)` calls, `min(1500, 600 + 120n)` active seconds and `min(1600000, 1000000 + 200000n)` tokens. Episode wall limits derive from recorded durations, and the overall verifier limit exceeds their sum with margin.
