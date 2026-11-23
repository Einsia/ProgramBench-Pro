# Tig coverage

Version **1.0.0**, unmodified upstream **tig 2.6.1**.
The executable specification defines **272 episodes**
(**179 program**, **93 GUI**),
**582 checkpoints**, **1064 backend points** and
**124 frontend points**. The frozen manifest is authoritative.

## Counting and result semantics

Each point checks a distinct product field, input path, operation result or
visible goal. Native view-column configuration is checked through complete
specifications, individual assignments and loading user configuration. A second
restart with the same unchanged configuration is not counted again. Restart
coverage instead changes an in-memory option or binding first and verifies that
the saved user configuration wins in the next process, or exports, clears,
reloads and operates the saved configuration.

Program operations and observations use the same public runtime as exploration.
Git fixture construction and the inspector's own calculations receive no
points. Scored repository mutations are performed by Tig. Selected commits use
Tig's documented echo variables and the current repository log to associate an
ID with its logical commit, independent of highlight color or layout. Split
views are checked by their history content and associated commit in the diff,
not literal view titles. No private memory or save-view debug state is read.

Historical content checks distinguish complete original lines from later
versions. History filters compare included and excluded commit sets; ordering
checks first show the existing main history alone when a GUI may have left
another pane visible. This preserves revision arguments and excludes text in
unrelated refs or diff panes from the history projection. History ordering
compares logical entries, and author sorting compares groups while permitting
arbitrary ordering inside a tied group. Pure graph appearance, word-diff
presentation and diff-line-number appearance are frontend-only judgments.
Index checks compare mode, stage, binary bytes and symbolic-link targets.
Cherry-pick checks the new HEAD message and parent relation, committed tree,
index contents and clean working state; merely copying files cannot pass.

Color exports are compared as foreground, background and attribute flags;
attribute order is ignored, normal contributes no flags, and replacing a rule
with normal alone clears the previous attributes. Configuration
exports use unique filenames because upstream refuses overwrites. Formatting,
comments and unrelated exported properties are ignored. Fixed fixture dates,
content-derived mtimes and TEST_TIME_NOW make results deterministic; generated
commit IDs are dynamically associated with logical content rather than frozen
as required literal values.

## Counts by feature

| Feature | Backend | Frontend |
| --- | ---: | ---: |
| blame | 4 | 2 |
| cli | 2 | 0 |
| color-configuration | 61 | 0 |
| column-configuration | 489 | 0 |
| commits | 2 | 0 |
| configuration | 59 | 0 |
| configuration-effects | 10 | 0 |
| configuration-format | 5 | 0 |
| console | 16 | 1 |
| diff | 7 | 6 |
| display | 9 | 11 |
| export | 1 | 0 |
| git-configuration | 11 | 0 |
| grep | 16 | 6 |
| help | 1 | 2 |
| history | 6 | 5 |
| history-filters | 35 | 4 |
| key-configuration | 75 | 1 |
| mouse | 3 | 1 |
| navigation | 33 | 5 |
| pager | 11 | 3 |
| partial-staging | 20 | 10 |
| persistence | 13 | 0 |
| reflog | 7 | 2 |
| refresh | 2 | 1 |
| refs | 8 | 6 |
| reverting | 7 | 4 |
| search | 30 | 1 |
| staging | 69 | 14 |
| stash | 10 | 10 |
| tree | 4 | 8 |
| validation | 15 | 0 |
| view-details | 14 | 16 |
| views | 9 | 5 |
| **Total** | **1064** | **124** |

## Documented feature map

| Native feature family | Behavioral coverage |
| --- | --- |
| main/log/diff/reflog/tree/blob/blame/refs/status/stage/stash/grep/pager/help | gui-history, gui-log, gui-diff, gui-tree, gui-blob, gui-blame, gui-refs, gui-reflog, gui-stash-*, gui-grep-*, gui-pager-*, gui-help and gui-detail-* |
| Selection, forward/backward search, next/previous matches, wrap/no-wrap boundaries, case modes, invalid/no match and cancellation | behavior-search, behavior-main-search-*, behavior-search-columns, behavior-search-cancel, navigation-rule-*; native commit/text/file/line variables identify the result |
| Full-page/half-page movement, line/page/half-page viewport scrolling, horizontal movement and first-column restoration, merge jumps | behavior-scrolling, behavior-merge-jumps; logical line movement and visible intervals, not exact terminal coordinates |
| Mouse selection and wheel movement | gui-mouse-selection, behavior-mouse-wheel-* with native cursor-motion results |
| Split, focus-child, send-child-enter, vertical split, maximize, close, close-without-quit and previous view state | gui-split, gui-maximize, gui-detail-back-diff, behavior-focus-*, behavior-send-enter, behavior-keep-parent, behavior-vertical-focus, behavior-close-no-quit, behavior-tree-back, behavior-blame-back |
| Revision count, skip, date, author, committer, message, path, first-parent, merge, ranges, exclusions and combined queries | history-query-rules, behavior-history-combinations, behavior-history-order-*, gui-history-filter-*; includes spaced paths and a branching DAG with different author/committer dates |
| Local/remote branches, lightweight/annotated tags and refs filters | gui-refs, gui-annotated-tag, behavior-refs-branches/tags/remotes |
| Checkout, branch deletion, reflog checkout/reset and cherry-pick | gui-branch-*, behavior-reflog-*, cherry-pick; actual HEAD, file/index and commit-parent state |
| Whole-file stage/unstage/revert, additions/deletions, binary files, symlinks, executable bits, Unicode/spaced/nested names, empty/long/tabbed/CRLF/missing-newline contents | stage/unstage-*, gui-stage/unstage/revert-*, gui-stage-kind-*, behavior-stage-type-*, behavior-root-add, behavior-mixed-index-worktree |
| Hunk/line/part stage and unstage, split chunk, replacement/deletion patches, section batch updates, revert confirmation/cancellation | gui-stage-hunk/line/part, gui-unstage-hunk, gui-revert-hunk, behavior-unstage-*, behavior-split-hunk, behavior-stage-patch-*, behavior-stage-section, behavior-revert-confirmation |
| Stash list/diff/apply/pop/drop and preservation of unrelated edits | gui-stash-*, behavior-stash-preserve; saved entry set and real worktree contents |
| Grep case/word/fixed/extended/inverted/path queries, cached versus worktree, empty matches, open result | grep-rule-*, behavior-empty-grep, gui-grep-*, gui-detail-grep-open. Cached and worktree queries deliberately match different lines of the same file |
| Plain pager, wrapping, page/search/line navigation, native commit-list main/show --stdin and pretty=raw input | gui-pager-*, gui-display-wrap, behavior-stdin-*; stdin commit hashes are drawn from the prepared repository |
| Column fields/enums, colors, native settings and action bindings | columns-*, enum-*, settings-values, colors-*, color-match-*, bindings-*; non-default values and field-specific exported projections |
| Native +=, continuation, comments, quoted strings, repeated assignment; generic/view/search binding priority, none, symbolic/control/UTF-8 keys, internal action aliases | behavior-config-format-*, behavior-bind-*, behavior-search-map. Runtime validates logical lines while retaining original configuration text for the product to parse |
| Git-file Tig set/color/internal-bind configuration, multi-value keys and precedence against user tigrc | behavior-git-config-*, behavior-git-user-priority; every allowed Tig configuration value uses the same policy as configure |
| Configuration effects: hidden changes/untracked files, directory grouping, file/revision filtering, ignore-space, start-on-head, tab stops, relative dates, mailmap, encoding and core.abbrev | behavior-setting-*, behavior-filter-*, behavior-whitespace-*, behavior-start-on-head, behavior-tabs-*, behavior-relative-date-*, behavior-mailmap-*, behavior-git-config-encoding/abbrev |
| Manual and periodic refresh; fixed local external-action refresh | gui-detail-refresh, behavior-periodic-refresh and native refs/stash/cherry-pick operations; refresh-mode/interval values also serialize in settings-values |
| User config export/clear/reload, in-memory precedence across restart, history reload/truncation/deduplication | configuration-roundtrip, behavior-config-precedence, behavior-binding-restart, prompt-history, behavior-history-* |
| Documented browsing variables | repo-variable-*, behavior-context-variables, behavior-stash-variable; commit/head/blob/branch/refname/tag/directory/file/line/text and repository values |
| CLI help/version, screen/options export and native validation errors | command-line, export-display, native-validation and the configuration export families |

The hunk fixture contains adjacent additions; single-line staging must retain
an adjacent addition, while part staging must retain another nearby part of the
same hunk. These yield different required index contents. Reverse line/part
updates and split-hunk-then-stage are separate observable behaviors.

## Boundaries and exclusions

Arbitrary executable commands, scripts, source directives, custom diff filters,
editors, merge tools, plugins and Git hooks are restricted to preserve the
reference boundary. Safe native Tig settings in Git files and commit-list
stdin are available through validated public inputs. The runtime never accepts
executable Git settings, arbitrary configuration includes or general-purpose
Git command extensions. The native dotted action-name spelling advertised by
the documentation is not exposed as an executable fallback: this release does
not resolve it as an internal action. Supported case/dash/underscore and key
aliases are covered through their native actions.

Network transports, remote fetch/push, credentials and signing services,
external clipboard/terminal programs and shell job control require services or
processes outside the offline managed terminal and are excluded. Hardware-
specific terminal sequences, exact colors/glyphs and cosmetic geometry are not
independent scoring requirements. save-view is excluded because it exposes
internal debugging bookkeeping. Runtime control, setup and inspectors add no
product behavior or private testing-only interface.

## Dependencies, failure handling and evaluator budget

Setup declares explicit IDs and only prepares inputs. State chains declare
checkpoint dependencies; independent cases restart/reconfigure or use a fresh
repository. Negative and preservation checks accompany successful operations.
The runner restarts a crashed candidate and classifies missing/malformed output,
blocked startup and action failures as candidate failures. Provider and verifier
faults invalidate a run rather than manufacture a reward.

The evaluator operates key/keys/type/wait/resize/mouse/console/grep and sees the
settled terminal. It does not receive program-check feedback. GUI budgets are
**200 calls**, **2,000,000 cumulative tokens**, **1,800 active seconds** per
episode. The evaluator model and effort are configured by the host bridge.

Program wall limits are max(900 seconds, 5 × measured record duration); GUI
limits additionally include their active budget. Frozen durations determine
the final verifier timeout, which exceeds the sum of limits with at least
10 percent headroom and is at least 86,400 seconds.
