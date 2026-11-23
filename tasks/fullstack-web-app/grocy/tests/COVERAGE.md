# Grocy coverage

Task **1.0.0**, upstream **Grocy 4.7.1**. The executable manifest
contains **52 episodes**, **130 frontend assertions** and **1,817 backend
assertions**: 42 GUI episodes and 10 program episodes. Setup is unscored.
Every check reaches the application through the same runtime available for
exploration; no database, private file, DOM source or application source is read.

## Feature coverage

| Feature | Program episodes | Browser episodes |
| --- | --- | --- |
| Locations, stores, product groups, task categories, quantity units and meal sections | entities: creation, defaults, field changes, deletion, filters, ordering, pagination | master-data create, edit and delete |
| Products and inventory settings | entities, stock, advanced: product fields, parent products, default quantities, due dates, tare weight, units | product creation, minimum quantities and default due days |
| Stock purchases and batches | stock, advanced: multiple batches, fractions, prices, explicit/default dates, notes, shops, entry editing | purchase, stock entries, stock journal |
| Consumption, opening, transfer and inventory | stock, advanced: expiry/FIFO selection, opened stock, spoilage, partial quantities, location selection, corrections, booking and transaction undo | consumption, opening, spoilage, undo, transfer and inventory correction |
| Parent products and quantity conversion | advanced: aggregate stock, child substitution, global/product conversions, reverse and transitive conversion | product unit selection; converted behavior also checked by program |
| Shopping lists | entities, stock, advanced: list CRUD, partial additions/removals, done state, notes, automatic missing/overdue/expired products, clearing | adding product and note items, editing, marking done, filters and clearing |
| Recipes and ingredients | entities, recipes: scaling, costs, fulfillment, shopping coverage, optional ingredients, conversion, nesting, copy, consume and self production | recipe preparation, ingredients, scaling, cooking and missing ingredients |
| Meal planning and calendar | recipes, extensions: recipe/product/note entries, dates, sections, deletion, iCalendar content and sharing scope | meal planning and calendar inspection |
| Chores | entities, household, advanced: manual/hourly/daily/weekly/monthly/yearly/adaptive schedules, intervals, date-only tracking, rollover, reschedule, executions, skip, undo, merge, product use and assignments | tracking, journal, undo, reschedule, master data |
| Batteries | entities, household: intervals, charge cycles, leap dates, history, undo and inactive items | tracking, next charge, journal, undo and master data |
| Tasks | entities, household: due dates, categories, assignees, completion and undo | creation, completion, undo, editing, deletion |
| Users, permissions and preferences | users and coverage: login, invalid credentials, profiles, passwords, aggregate settings, incremental permission grants, setting isolation, reset to defaults, leaf/parent permission grants and denials | account creation, editing, login/logout, six preference pages |
| API credentials and sessions | credentials: successful header/query authentication, distinct keys, account ownership, live permission changes, revocation, browser session listing/revocation/relogin/logout; extensions: calendar token scope | create distinct keys, retain one while revoking another |
| Userfields and custom entities | entities, extensions: all 14 field types, values, updates, deletion, named entities and objects | custom entity master data and equipment field definition/value |
| Equipment and files | entities, extensions: manuals, all five file groups, exact bytes, duplicate uploads, fully decoded patterned image resizing, concurrent namespaces and deletion | equipment master data, manual attachment and notes |
| Stock reports and views | stock, advanced, coverage: current and volatile stock, locations and prices, aggregate fulfillment and change notification | search, expired/below-minimum filters, location contents, product/store/group spending totals, date filters, journal summary and product filter |
| Offline barcode lookup | advanced: upstream demo plugin success, registered barcode, not-found and plugin error | keyboard barcode selection and visible generated Grocycodes |
| System and interface documentation | extensions and coverage: clock/offset arithmetic, configured feature flags, OpenAPI, aggregate recipe fulfillment, date change notification and query pagination | normal pages, visible account state and documented date shorthands (MMDD, YYYYMMDD, month-end, relative, never) |
| Persistence | persistence: objects, files, settings and inventory after restart, reset freshness | saved stock after a process restart |
| Date fields and unit forms | saved task dates through public API; explicit stock-entry sorting | 17 shorthand/arrow/Shift cases across month/year/leap boundaries; singular and plural unit rendering |
| Aggregate/public API coverage | coverage: all-recipe fulfillment filters/order/pagination, incremental permissions, aggregate preferences and database-change notification | API pages are covered by program assertions |

## Check semantics

Program episodes are executable scenarios, not a matrix of identical status
checks. Mutations are paired with related public reads; real stocked products,
nonempty file bytes, distinguishable records and explicit dates make outcomes
observable. Named fixtures accept any successful HTTP status. Dependencies and
positive companion assertions are declared in the manifest; failed candidate
requests affect their points, and the shared driver restarts a crashed process.

Behavioral projections omit generated bookkeeping timestamps and map generated
identities through a typed bijection. Numeric strings and JSON numbers are
normalized for numeric fields; floating values use 1e-8 tolerance. Unordered
collections preserve membership and multiplicity. Ordered query cases use unique
sort values. Submitted names, quantities, dates and relationships remain checked.
Files are compared by bytes, resized pictures by decoded dimensions and quadrant color features (24 intensity levels of tolerance at the interior corners), and calendar exports
by event title, occurrence and description, independent of generated UID/DTSTAMP.
Random chore assignments are checked against the configured user set. The demo
lookup's generated product name is not frozen as a required literal.

The application clock starts at 2026-03-10 09:00:00 UTC and advances. Episodes
fit within that day; time tests compare arithmetic between adjacent requests.
Frontend evidence may vary in displayed seconds, relative time, random API keys,
attachment prefixes and generated object IDs. These are observations of the
reference, not required candidate literals.

Frontend goals specify functional outcomes, allow equivalent navigation/layouts,
and use public API checks only for the directly requested state. Reference
recipes use the same visible controls and operations as the evaluator, including
product modal frames. Pure viewing checkpoints do not prescribe pixel styling.

## Deliberate boundaries

- Live external barcode providers, remote image retrieval, LDAP and reverse-proxy
  authentication need external services. The upstream offline demo barcode plugin
  is configured instead; local login and API authentication are covered.
- Physical camera scanning, flashlight, wake locks and hardware printers require
  devices. Label-printer webhooks and thermal printing are disabled by upstream
  configuration; no printer or webhook service exists in the offline environment.
- Deployment administration, arbitrary server paths, custom PHP plugins, custom
  JavaScript/CSS injection, raw implementation resources and debug traces are
  outside the restricted runtime. The reference release is otherwise unmodified.
- Responsive/mobile-specific layout, sounds, pixel styling, and browser/OS-native
  print dialogs are not distinct functional assertions. Corresponding data,
  stock sheets, visible reports and file outputs are inspected through supported
  browser/API channels.
- Localization catalogs and installed PHP/SQLite/OS build strings are metadata,
  not a requirement to reproduce thousands of translation strings or a runtime
  implementation. The task uses the English locale and UTC.
- Nondeterministic assignment is checked by valid membership rather than a
  particular random sequence. Undocumented internal cache rows and generated
  database bookkeeping are not part of behavioral observations.

## Budgets and runtime

Each GUI episode has a ceiling of **240 calls** and **2,400 seconds** of
evaluator work. The four date-input episodes allow **3,000,000 tokens** each;
other GUI episodes allow **2,000,000 tokens** each. Oracle usage is checked so observed calls
and peak episode tokens remain within 40% of these ceilings. Provider waiting
is separately classified by the shared framework. Program episodes use
`max(900 seconds, 5 × measured record duration)`; GUI wall limits add the frozen
budget to `max(600 seconds, 5 × measured record duration)`. The verifier timeout
is calibrated from their sum by the finalization script and is at least 86,400
seconds. Product readiness is generic: `GET /` returns below 500 within 75 seconds.

## Additional offline interfaces

The `protocol-coverage` episode covers `/recipes/fulfillment` with fulfilled and
missing recipes, filters, unique sort values, pagination and invalid ordering;
incremental `POST /users/{id}/permissions` with preserved grants and effective
stock/task/list operations; and aggregate `/user/settings` isolation. Database
change notifications are checked before and after real writes and deletion,
without freezing their absolute times or requiring monotonicity from read-only
session bookkeeping under the configured clock.

`protocol-credentials` creates and uses ordinary keys through visible product
pages and the documented API; it does not read hidden key/session tables.
Generated secrets never enter program observations. The release creates normal
keys expiring at 2999-12-31 and has no UI expiry editor. Both POST and PUT on
`objects/api_keys` are rejected by its public entity policy. Consequently a
valid expired key cannot be constructed through the supported interfaces or
observed within the episode clock horizon; expiry enforcement is excluded.
Successful authentication, permission changes and revocation are tested.

The four `gui-dates-*` episodes cover MMDD with year rollover, YYYYMMDD,
month-end forms, relative days/months/years, never-overdue, all four arrows and
all four Shift-arrow operations. The date cases include leap days and crossing
month/year boundaries. Dates must be persisted as the observed expanded date.
`gui-report-grouping` covers known per-product, store and group arithmetic,
date/product filters and stock journal summary. `gui-preference-effects` checks
that saved purchase/consume defaults actually prefill ordinary forms.

All five file groups contain the same basenames at the same time with distinct
nonempty text and patterned images. Cross-deletion reads prove that other groups
and their resize caches survive. Every field-deletion scenario retains a
second named, nonempty field. Foundation fixtures gate only cases that actually
refer to them; one unsupported entity does not gate independent entity CRUD.
