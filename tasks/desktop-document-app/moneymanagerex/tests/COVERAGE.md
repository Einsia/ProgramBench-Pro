# Money Manager Ex coverage

Task 1.0.0, reference Money Manager Ex 1.9.4.
The executable manifest defines **93 episodes: 3 program and 90 GUI**, with
**1,882 backend points and 175 frontend points**, across 178 checkpoints.

## Feature map

The map follows the public File, Accounts, Tools, View and Help menus and the
bundled manual's account, transaction, reconciliation, import/export, scheduling,
budget, investment, asset, custom-field, backup and reporting chapters.
Episode prefixes below identify the corresponding executable specifications.

| Menu/manual family | Scored behavior and episodes |
| --- | --- |
| File: new/open/save, lifecycle | `database-new`, `database-upgrade`, `database-encryption`, `database-optimize`: new wizard, base currency/user, account creation, separate saved copy, legacy format upgrade, authenticated encrypted save, incorrect-password rejection, correct reopen and decryption, reclamation of real unused pages while retaining records. All document episodes use ordinary opening and persistence. |
| Database Backup / Other preferences | `database-backups`: startup backup and changed-database close backup, triggered by switching between two ordinary ledgers and read back as ordinary documents; `deleted-retention`: expired, exact 10-day boundary and recent deleted entries across restart. |
| Accounts: new/edit/change type/delete | `account-*`: checking, card, term, investment and loan creation; balance/date, currency, contact, favorite, statement and credit preferences; closing/reopening/renaming and reference propagation; Checking/Term and Cash/Checking conversion, cancellation, empty account deletion and removal of referenced transactions/schedules. |
| Reconcile dialog | `account-reconcile`: cancellation, selecting part of a statement, Finish later, resuming with Done, then both directions of transfers. Checks opening/reconciled states and selected/unselected transactions against independently computed 1100, 1260 and 1230 balances. |
| Transaction entry and management | `trx-*`: deposits/withdrawals, same/cross-currency transfers and destination amounts, expressions, payee creation/defaults, Save and New, fields and notes, split amounts/categories/tags, status keys, bulk edit/status, duplicate, clipboard copy/paste across accounts, moving, delete/restore. |
| Tools managers and Merge | `payee-*`, `category-*`, `tag-*`, `merge-*`: add/edit/rename/hide/delete and used-entry protection, category hierarchy, payee patterns/default categories, merge propagation through transactions, splits, schedules and defaults; category budget removal. |
| Currency Manager | `currency-*`: symbols, decimal/group separators, precision, conversion rate and historical rates. Rate and quote values preserve input precision. Online refresh is unavailable. |
| Date Range Manager / checking filters | `date-range-manager`: create previous-month range, change it to previous-quarter range, apply each to account activity, remove it and inspect the saved manager. `view-*` and transaction-report episodes cover category/status filters, text search and payee reports. |
| Scheduled Transactions | `scheduled-manual`: create/skip/enter/delete. Three `scheduled-auto-*` program episodes cover all 17 frequencies, overdue catch-up, finite completion, future preservation, month/year/business-day/leap boundaries, separate posting/due dates, both account amounts, status/reference, tags and splits. |
| Budget Planner | `budget-periods`, `budget-edit`: annual/monthly creation/copy/delete, amount/frequency/notes and income/expense views. `budget-frequencies-annual/monthly`: all nine budget frequencies, including None, calculated for yearly and monthly reports with actual expenses. |
| Budget reporting/preferences | `report-budget-*`: performance and category summary; monthly selection, monthly override of annual budget, monthly deduction from annual budget, July financial-year boundary, transfer inclusion with an actual 125 transfer and a budget category. Estimates/actuals come from ordinary HTML exports. |
| Stocks, lots and investment cash | `stock-purchase-sale`: fractional purchase, net cash/commission, manual quote, partial and full sale. `stock-multiple-lots`: two purchases of the same symbol, distinct quantities/dates, moving one lot to another investment account while retaining the other. `investment-cash-ledger`: dividend and separate brokerage fee. `stock-history`, stock reports: dated quote insertion/update and holdings/history. |
| Asset management | `asset-depreciation`, `asset-create-delete`: creation, type/date/value, appreciation/depreciation, rate edits, associated account, deletion. Asset value and portfolio totals also participate in reports. |
| Built-in Reports | `report-*`: daily/monthly/transaction cash flow; monthly/category summary and spending/income; forecast; income-versus-expense summary/monthly; payees; monthly/yearly account balances; budgets; stock charts/holdings. `report-date-accounts` selects June/Main Checking then credit cards; `report-future-policy` includes future activity, saves the exclusion preference, restarts, and applies the year-through-current-week range to exclude July activity. Fixtures include different currencies, fiscal/month boundaries, future, void and deleted activity. |
| File export | `export-csv/json/qif/xml`: complete transaction sets and counts, business-key samples, semantic accounts/relationships, tags and splits. JSON resolves every foreign reference; QIF carries source accounts and unordered tags; XML ignores row/split order and IDs. |
| CSV and XML import | `import-csv-*`: headers/footers, delimiter/date/decimal/sign conventions, Unicode/quotes and partial invalid rows. `import-xml-preset` and `import-csv-preset`: reordered columns, separate withdrawal/deposit values, empty/zero fields, Unicode and tags; save/reuse a mapping on a second document. XML Spreadsheet 2003 uses its first worksheet, as the product does. |
| QIF and OFX import / format roundtrip | `import-qif`, `import-ofx`: splits, statuses, duplicate skipping, OFX account/payee selection. `qif-roundtrip`: complete export and import into an empty target account, including Unicode, quoted notes, tags, splits, values and dates. |
| Custom Field Manager / values | `custom-field-manage`, `custom-field-types`, `custom-field-extended`: definition/default/tooltip/rename and values for String, Integer, Decimal, Boolean, SingleChoice, Date, Time and MultiChoice; RegEx acceptance/rejection, UDFC column mapping, exact-value bulk replacement with nonmatching preservation, deletion of definitions and stored values. MultiChoice order is normalized. |
| Attachments | `transaction-attachments`: archive location, attach and describe, change description, delete. Reads actual archived bytes through recursive list/download after add/edit, and checks payload removal. |
| Settings / View | `settings-*`: user/date/fiscal preferences, restart persistence, default status, duplicate date and recording time. Budget/future/deleted-transaction view preferences are covered above. Toolbar/navigation/full-screen layout, tooltips, translated labels, icons and monetary tips are presentation choices, not separate pixel requirements; the shared screenshot/AT-SPI surface remains available. |
| Help / discovery | The bundled help is available through the product's normal desktop; it is a discovery source for the observable behaviors above. About/version text, recent-file shortcuts and alternative menu/toolbar/keyboard routes do not create distinct business outputs. |

## Observations and distinctions

All setup and observation use public `upload`, `download`, `list_files`,
`clipboard_text` or lifecycle operations. Settings files in the private profile
are never read. Files are ordinary exchanged documents. SQLite downloads take a
consistent snapshot including committed WAL transactions while the product is
open; busy rollback-mode writers are retried. Recursive attachment reads remain
within the selected exchange area and do not follow links.

Database and export projections resolve identifiers to business names; generated
IDs, last-update times, JSON object order, tag order and equal-key split order
are not requirements. CSV/XML completeness compares unordered row sets; JSON/QIF
compare complete transactions and relationships. The JSON fixture uses one payee
and activity in every referenced account because this pinned exporter otherwise
omits some payee and destination-account definitions. The fixture therefore
allows meaningful, self-contained relationship validation without inventing
missing export objects.

Money tolerates 0.0051. Rates, share prices and share counts use 0.00000051,
consistent with the six-decimal semantic projections. Integer/status/count fields
compare exactly. Report amounts compare numerically, including multiple numbers
inside a budget-performance cell. Text line endings and permitted whitespace are
normalized. Encryption authenticates the actual SQLCipher 4 page format, rejects
an incorrect key and compares independently decrypted ledger semantics; random
ciphertext bytes are never frozen. Optimization measures a relative reduction
in file bytes and unused pages from a deliberately fragmented valid ledger.

Calendar and budget-frequency expectations are calculated independently from
literal inputs, then checked against actual product results. Catch-up sequences
count as one business-aspect check rather than one point per generated row.
Future schedules must remain present with their date, frequency, remaining count
and transaction fields. GUI points concern the current goal; setup earns no
points. Dependencies identify required previous changes. Rejection assertions
have successful companion operations, including authenticated decryption for
incorrect-password rejection.

## Surface and budgets

Every episode uses a fresh 1280×1024 English desktop and a UTC clock starting
at 2026-06-15 12:00:00. Dialogs/menus use AT-SPI; drawn lists/trees and report
content remain available in screenshots. Upload modification times are fixed.

The evaluator is Kimi K3 with high reasoning effort. Default budgets for n GUI
checkpoints are min(200,55+30n) calls, min(2400,540+240n) seconds and
min(2,000,000,500,000+300,000n) tokens. Mapping imports, OFX and parameterized
budgets have 150–300 calls; reconciliation, backup, custom-field and multi-lot
episodes have explicit 240–300 call budgets. Fractional stock purchase/full sale
has 320 calls, 3600 seconds and 4,000,000 tokens. The account-details episode has
160 calls and 1,800,000 tokens. Spending has 200 calls and 2,500,000 tokens;
budget override has 300 calls and 4,500,000 tokens; QIF roundtrip has 320 calls
and 5,000,000 tokens. The executable manifest contains
the exact per-episode budgets. Oracle calibration requires both calls and tokens
to remain within 40% on the standard answer. Episode and overall wall limits
are computed from measured reference durations by the shared runtime.

## Unavailable interfaces

Online quotes/rates, WebApp synchronization, update/news/community services and
external websites require networking. Printing requires a system/printer.
General Report Manager SQL/Lua/templates, debug SQL, theme/plugin loading and
external attachment viewers can execute code or access private paths and are
restricted by the runtime. Machine diagnostics and usage telemetry describe the
execution environment rather than portable ledger behavior. These restrictions
are applied equally to reference, self-test and evaluation.
