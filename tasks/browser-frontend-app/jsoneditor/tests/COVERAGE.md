# JSON Editor coverage

Task 1.0.0, JSON Editor 10.4.3. 128 episodes (77 program, 51 GUI), 1044 checkpoints, 275 frontend and 2251 backend points. The executable manifest and frozen `data/manifest.json` are authoritative for counts and budgets.

## Covered behavior

| Family | Coverage |
| --- | --- |
| Documents and API | All JSON root types, nested structures, escaping, Unicode, numeric boundaries, special keys, set/update, text parsing, malformed text, automatic repair, transitions among all six modes (resulting mode and document), invalid mode errors; direct constructor falsy and nonempty roots |
| Schema validation | Pinned JSON Schema Test Suite draft-7 inputs and optional supported formats through the editor's setSchema/validate behavior; type, enum, const, numeric/string/object/array constraints, combinators, dependencies, local references, conditionals, format boundaries; exact duplicate inputs and unconditional cases removed |
| State preservation | Every tree/form/view update and updateText case also checks a previously expanded branch; tree checks the selected path and updated value. Separate set/setText cases verify expansion reset. |
| Expansion API | Shallow versus recursive expand, withPath, collapse, preserved child expansion across collapse/reopen; all tree modes. setName() without arguments clears an existing root name. |
| Validation diagnostics | Forty nested schema violations across tree/text/code/preview compare error paths, keywords and error types; four fixed custom-validator cases check their paths and types. Error ordering and wording are ignored. |
| Configuration | Natural sortObjectKeys; explicit indentation 0/4/8; history on/off with a structural edit; search/sort/transform enable switches; main/navigation/status bars; custom translation label. |
| Tree and form | Scalar edits, field renames, automatic type detection, explicit string/object/array type changes, insert/append position and content, duplication/removal, extraction, nested document expansion, search and pagination; multiselection copy/delete/move; dragging across parent boundaries with limitDragging on/off |
| Text and code | Replacement editing, formatting, compaction, repair of quotes, comments, commas, truncated input, Python literals, JSONP, fenced JSON and multiple values; public text selection |
| History | Undo/redo of value, field, structure, type, sort and transform operations; preview undo |
| Sort and transform | Numeric/string arrays, object keys, nested property sorting in both directions; JMESPath projections, filters, nested flattening, mapping, slices, order, aggregates and functions; tree and preview modes; wizard filtering, sorting, projection and combinations without query editing |
| Examples and callbacks | Fixed/dynamic autocomplete, separate display/value completions, multiple searchable fields, templates, custom editability, custom Ace, asynchronous and synchronous custom validators, validation callback output, translations, synchronized values and expanded nodes |
| Files | Upstream load/save example, JSON roots and Unicode round trips, supplied filename extension behavior; malformed import preserves the existing document and cancelled saving adds no download relative to its before state |
| Display | Root modes, expansion, search highlights plus next/previous/wrap/clear navigation, color picker, timestamp annotation and Unicode escaping |
| Read-only boundaries | View values, form keys and structural removal, protected fields in example 05, read-only text/code in example 09. Every refusal is tied to a positive editable companion. |

All preparation and checks use channels exposed in runtime help: the documented constructor/methods, visible controls and pointer/keyboard operations, upload/download and lifecycle. Program episodes are independent of reference control names. GUI recipes use reference controls; the evaluator can use any equivalent visible route. Program companions read JSON data, downloads and rendered text exposed by snapshot, never internal state. Expanded-state checks inspect unique document values in the visible snapshot; they do not inspect classes or DOM source.

Schema inputs are redistributed under the MIT license in `fixtures/SCHEMA-LICENSE`, with source revision and checksum in `fixtures/SCHEMA-SOURCE.json`. Expectations reflect the pinned editor, including its Ajv version, rather than assuming every newer conformance expectation applies. The format checks deliberately exercise reference behavior on both accepted and rejected data. Unsupported internationalized formats and remote schemas are omitted; local references are covered.

## Boundaries and exclusions

| Excluded | Reason |
| --- | --- |
| User-defined JavaScript callbacks, custom query executor, arbitrary libraries/plugins | Executable code cannot cross the reference isolation boundary. Existing safe callbacks are exercised through the shipped examples |
| Advanced JSONPath autocomplete example 13 | Its user-controlled query evaluator accepts executable expressions; excluded with the custom JavaScript query example under isolation policy |
| New-window integration example 24, external links, online demo | Single-page isolated browser and offline operation; the component's editable modes are covered on the other upstream pages |
| React/AMD embedding scaffolding | These are alternative library loading mechanisms, not additional end-user behavior; the official standalone examples expose the same component |
| Third-party Ace extensions or languages not included by the released examples | Arbitrary library loading is disabled; the shipped JSON code editor and pinned custom Ace example are covered |
| Custom callbacks whose only output is developer-console logging | The runtime does not reveal console/network logs because they can carry implementation content; data-changing and visibly rendered callbacks are covered |
| Arbitrary DOM elements as anchors and functions as configuration values | Constructor transport accepts JSON data only; underlying menu, popup and modal behavior is exercised by visible interaction |
| 500 MiB preview capacity and performance benchmarking | Bounded runtime transport and shared resource limits; preview semantics and document transformations are covered at representative sizes |
| Remote JSON schemas and newer schema drafts | No network; the product bundles an older Ajv implementation. Draft-7 and local references cover its supported validation engine |
| Native file-chooser cancellation | The public browser runtime can supply bytes to file inputs but has no native chooser-cancel operation; malformed import and native save-prompt cancellation are covered. |
| Noncontiguous node selection | The released tree editor supports contiguous sibling ranges and common-parent selections; it has no independent disjoint-node selection API. Contiguous multiple operations and nested ranges are covered. |
| Autosave or server-side persistence | Not provided by these upstream examples. Reload restores the original example; restart preserves the live browser page |

## Comparison, recovery and budgets

JSON comparisons keep booleans distinct from numbers, preserve array order and compare integer-valued data exactly, including all safe-integer boundaries (1 and 1.0 are equivalent); nonintegral JSON numbers use 1e-12 relative/absolute serialization tolerance. Object order is ignored except for object sorting and explicitly positional insert/append, where getText exposes the requested order. The same observations also retain full JSON content to protect key/value associations. Sorting and sort-history fixtures use explicit JSON text so freezing object keys does not change their initial order. Color picker results compare RGBA channels with a one-unit tolerance, accepting equivalent hex and RGB notation. Text formatting permits equivalent Unicode escaping and indentation. Public selection results are projected to documented fields. Download references are derived from filename and content. The dialog_action request field is distinct from pointer.action in evaluator tools. Native-dialog messages remain observable after automatic dismissal until the next input action. Upload goals have declared input files; save goals check their requested output names and distinct nonempty object, array and Unicode contents. Error wording, DOM nodes and implementation bookkeeping are not frozen. Parse errors must be explicit product responses. Each schema case performs its own input mutation and validation; each new group constructs an independent editor. A failed preparation blocks only its checkpoint. Undo assertions require a positive sort or redo data result; type-change frontend assertions require their data result. Template insertion permits either placement beside the existing array item; both exact template content and preservation of the original item are checked. Automatic duplicate-field names are not prescribed; insertion goals supply an explicit name and a value that distinguishes auto from string type. The driver restarts crashed candidate processes before continuing.

GUI budgets are 40 + 40 calls, 500,000 + 600,000 tokens and 300 + 300 active seconds per checkpoint group (the per-checkpoint quantities are multiplied by its checkpoint count). The protected-fields episode has 4500 active seconds. Episode wall-clock limits and verifier timeout are derived from measured reference durations.
