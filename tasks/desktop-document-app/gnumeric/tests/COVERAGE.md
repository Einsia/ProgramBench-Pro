# Gnumeric coverage

Task **1.0.0**, Gnumeric **1.12.62** and GOffice
**0.10.62**. There are **99 episodes** (82 GUI, 17 program),
377 checkpoints, **193 frontend** and **2,396 backend** assertions.
The task score is the fraction of episodes whose points all pass. `suite.build()` is the executable source of
these counts; `data/manifest.json` is the complete frozen record.

## Feature map

| Feature | Frontend | Backend | Observable behavior |
| --- | ---: | ---: | --- |
| editing | 5 | 6 | Text/numeric entry, clear contents, dependent recalculation |
| persistence | 2 | 1 | Save, restart and reopen edited workbooks |
| history | 3 | 3 | Undo and redo cell changes |
| formulas | 3 | 6 | Relative and absolute references, horizontal and vertical fill |
| clipboard | 7 | 8 | Copy, cut, text clipboard, transpose, value paste and multiply |
| structure | 13 | 5 | Insert/delete rows and columns, hide/show, width/height and autofit |
| formatting | 11 | 12 | Text emphasis, numeric toolbar formats, alignment, indent and merged cells |
| sorting | 3 | 3 | Row sorting while preserving records and dependent totals |
| view | 5 | 0 | Formula display, zoom, grid display and frozen panes |
| sheets | 5 | 5 | Rename, duplicate, cross-sheet formulas and independent edits |
| fill | 3 | 3 | Linear, growth and automatic series |
| search | 5 | 3 | Find results, replacement, case matching and undo |
| analysis | 2 | 2 | Goal Seek and continued formula recalculation |
| import | 2 | 0 | CSV import with quoted delimiters and numeric use |
| statistics | 20 | 244 | Formula statistics plus ten native report generators and report recalculation |
| cell-formatting | 11 | 14 | Custom formats, text wrap/rotation/fonts, saved comments and clear formats |
| charts | 8 | 4 | Scatter, column, line and pie charts, source updates and saved objects |
| objects | 4 | 0 | Rectangle, ellipse, arrow and object undo |
| metadata | 2 | 1 | Authored title, subject, author and comments, saved and reopened |
| preferences | 4 | 1 | Default sheets/zoom, normal quit and restart persistence |
| calculation | 3 | 2 | Saved manual mode, volatile formula recalculation and automatic mode |
| printing | 2 | 0 | Persistent orientation, centering, grid and row/column-heading settings |
| input-errors | 2 | 0 | Malformed document error and subsequent valid open |
| validation | 3 | 2 | Whole-number limits, Stop rejection, discard and valid recovery |
| filtering | 2 | 0 | Auto Filter selection and restoring all records |
| outlining | 2 | 0 | Grouped rows, collapse and expansion |
| conditional-formatting | 2 | 1 | Threshold-based font styling and changes crossing the threshold |
| names | 2 | 2 | Named range definition, formula use and source changes |
| optimization | 2 | 2 | Native linear Solver result and retained variable/formula behavior |
| consolidation | 2 | 2 | Position-based SUM and AVERAGE across two independent regions |
| text-to-columns | 2 | 2 | Separated text with quoted delimiters and empty fields; numeric use after splitting |
| data-table | 2 | 2 | One- and two-variable tables using real input-cell substitution |
| tabulate-dependency | 1 | 2 | Coordinate dependency tabulation with explicit min/max/step and model restoration |
| fill-merge | 2 | 3 | Template replication for each input row and undo |
| advanced-filter | 2 | 2 | AND/OR criteria, extracted records and preserved source |
| scenarios | 3 | 2 | Capture two input scenarios, switch, persist and reopen |
| simulation | 2 | 0 | Ten-iteration constant-input simulation, summary statistics and changed inputs |
| statistical-generators | 20 | 20 | Mean/sign/Wilcoxon, paired and unequal/equal t, F, two-factor ANOVA, contingency independence, PCA; source edits |
| histogram | 1 | 1 | Calculated cutoff intervals with explicit outer-bound conventions |
| sampling | 2 | 2 | Periodic selection and source-linked update |
| frequency-tables | 2 | 2 | Predetermined exact categories and changing counts |
| survival-analysis | 2 | 2 | Time-attributed Kaplan-Meier probabilities, risk population and errors |
| chart-editing | 3 | 3 | Axis bounds, title, legend, reopen, and native SVG/PNG/PDF export |
| sheet-management | 5 | 6 | Reorder, delete, undo, hide/show and cross-sheet reference effects |
| internal-navigation | 2 | 1 | Create and follow a workbook-local hyperlink; reopen persistence |
| image-objects | 2 | 1 | Independent PNG insertion, sizing and reopen persistence |
| dates | 0 | 159 | Calendar arithmetic, serial dates, leap/year/week boundaries and calendars |
| distributions | 0 | 122 | Density, cumulative/tail and inverse distribution parameters |
| domain-errors | 0 | 66 | Invalid domains and typed spreadsheet errors |
| engineering | 0 | 187 | Unit conversions, complex arithmetic, bit/base operations and special functions |
| finance | 0 | 167 | Cash flows, payments, rates, depreciation, securities and day-count bases |
| logical | 0 | 111 | Boolean/type behavior, error classification and conditional expressions |
| math | 0 | 361 | Arithmetic, transcendental functions, rounding, combinatorics and number theory |
| references | 0 | 75 | Lookups, arrays, database criteria, references and time-series functions |
| text | 0 | 128 | Unicode, slicing, searching, replacement, conversion and formatting functions |
| file-formats | 0 | 499 | Fourteen actual export/reimport paths; values, styles and rich structure |
| text-formats | 0 | 12 | Delimiter, quoting, newline, encoding, formula and sheet export choices |
| native-tools | 0 | 46 | ssgrep patterns/flags, ssindex terms and ssdiff changes |
| conversion-options | 0 | 15 | ssconvert assignments, merges, per-sheet export and invalid inputs/options |
| excel-compatibility | 0 | 32 | XLSX import and recalculation of 32 Excel function spellings |
| legacy-imports | 0 | 24 | Independent SC, Oleo, SpreadsheetML 2003 and dBase documents |
| document-export | 0 | 9 | PDF content/paper/selected sheet, HTML variants, LaTeX and TROFF tables |

## Public channels and independent projections

Every setup, observation and artifact check uses the public runtime's GUI,
clipboard, upload, list_files, download, cli or lifecycle operations. There is
no private workbook inspector. GUI recipes operate normal menus, dialogs and
keys. Candidate designs and routes may differ; goals state content, parameters
and output paths. Generated copy names are not frozen: the duplicate episode
asks for the user-specified name North copy, and Fill Merge checks generated
sheets by their contents.

The ten formula episodes contain 1,600 distinct expressions from documented
help examples and independent boundary cases. Each returns a typed scalar;
ordinary examples must be nonblank and nonerror. Invalid-domain examples
explicitly require a spreadsheet error other than an unknown function.
Floating point comparison uses relative tolerance 1e-8 and absolute tolerance
1e-10. Complex-valued mathematical functions are parsed into finite real and
imaginary components with the same tolerance. Their i/j unit is retained when
the imaginary component is nonzero. Ordinary text, including leading zeros,
is not coerced to complex or numeric values.

The format episode has 499 assertions across 14 output formats. The first
export is downloaded and independently validated before the candidate is ever
asked to reopen it: compressed/uncompressed native XML, ODS ZIP MIME/content,
XLSX relationships/workbook/sheets/styles, OLE plus BIFF5/8 stream headers,
SYLK records, DIF sections and CSV parsing. The two XLSX editions are distinguished
by the actual thin left/start border from the fixture. Rich formats also
require real formula records in the first document and recalculate after three
source values change, including named and cross-sheet dependencies. Cached
scalar values in XLSX, ODS and XLS are read directly with independent readers;
other cases also require valid first-format structure before reimport.

Styles, merges, names, additional sheets and geometry are independently
projected from actual documents. Geometry permits one point/unit of variation.
HTML table tokens and PDF normalize equivalent numeric minus signs. LaTeX and
TROFF compare authored table label/value pairs, without freezing renderer
macros or generated preambles. Text export tests cover delimiters, quoting,
line endings, encodings, formula output and sheet selection. Native CLI tests
include cell assignments, merges, per-sheet output, pattern files, fixed/case
matching, index terms, XML differences, highlight files and style changes.

## Statistical semantics and observed limits

Report comparisons retain the relationship between each sample/series,
statistic and value. Correlation/covariance retain both matrix axes; time
series retain sample order; rank output retains source observation identifiers;
ANOVA/regression retain factor, coefficient and metric labels. Equivalent
label aliases and table relocation are accepted. PCA compares ordered
eigenvalues and eigenvector outer products, which permit the arbitrary sign
of an eigenvector. Swapping Mean and Minimum under unchanged labels fails.
The report update checks require changed results during reference recording.

The pinned native generators sometimes emit only a partial output for a
small input. The task measures the result actually generated and explicitly
does not count absent portions as covered:

| Generator | Checked native output | Unavailable portion in this fixture |
| --- | --- | --- |
| Moving Average | A single Sales series, including initial undefined windows and ordered computed means | Final Sales window is absent even with a larger output selection |
| Fourier | Ordered real coefficients from one eight-observation Sales series | Imaginary output and trailing coefficients are absent in this native report |
| Ranks and Percentiles | Observation IDs, Sales values/ranks/percentiles and available Cost values | Final observations and remaining Cost columns are absent |
| Variance F test | Available Sales summary, variance ratio and critical/tail statistics | Separate Cost summary column and remaining tail rows are absent |
| Frequency Table | North/South/East category counts and updates | Final supplied category West is absent |
| Kaplan-Meier | Ordered times with at-risk, deaths, probabilities and standard errors | Last event and requested median section are absent |
| Histogram | Four ordered intervals from three authored cutoffs | Native output contains no frequency column; no frequency accuracy is claimed |
| Risk Simulation | Actual dialog summary, iteration count, variable min/mean/max and changed inputs | Sheet export emits a header/summary label without statistics; it also contains a generated local-file citation, so report statistics are judged through the complete visible dialog |

The normality test uses twelve values per sample, exceeding the native minimum
of eight, and requires valid statistics rather than only sample count/alpha.
One-mean, t, F, chi-squared and PCA probes were cross-checked with independent
SciPy/NumPy computations. Data table, consolidation, merge, filtering, scenario
and sampling fixtures have small independently calculable results.

## Coverage of additional offline tool families

| Documented/menu family | Episode or constraint |
| --- | --- |
| Text to Columns | text-to-columns; semicolon, quoting, empty field and numeric calculation |
| Consolidate | consolidate; SUM and AVERAGE across two source regions |
| Data Table | data-table; one and two independent input cells |
| Fill Merge | fill-merge; three generated templates, preserved source and undo |
| Tabulate Dependency | tabulate-dependency; coordinates, bounds, step and restored model |
| Advanced Filter | advanced-filter; AND/OR criteria and copied output |
| Scenarios | scenarios; capture, switch and reopen |
| Simulation | risk-simulation; deterministic constant model and changed parameters |
| Sampling | periodic-sampling; nondefault period/size and updated source |
| Frequency Tables | frequency-table and histogram-cutoffs; limitations above |
| Principal Components | analysis-pca; sample summary, ordered spectrum and sign-invariant component directions |
| Kaplan-Meier | kaplan-meier; no censorship, time-indexed estimates and source changes |
| Mean/median/t/F/ANOVA/contingency tools | analysis-one-mean, analysis-sign, analysis-wilcoxon, analysis-paired, analysis-unpaired-equal, analysis-unpaired-unequal, analysis-variance, analysis-anova, analysis-anova-two, analysis-chi-squared |
| Graph customization and native export | chart-edit-export; scale, title, legend, persistence, SVG/PNG/PDF |
| Values-only paste | paste-special; changed source with retained literal target and no copied formulas |
| Workbook-local links | internal-hyperlink; follow the link before and after reopening |
| Worksheet lifecycle | sheet-management; order, delete/undo, visibility and formulas |
| Images and drawing objects | image-object, drawing-objects; insertion, persistence and object undo |

Options within a covered family are sampled with distinct observable results;
this table does not equate a formula function with its GUI report generator.
Application-level source code, algorithm behavior and release binaries are
unmodified.

## Budgets, determinism and boundaries

Every GUI episode has 300 model calls, 5,000,000 tokens and 3,000 seconds.
The episode runner derives additional setup limits from recorded duration; program episodes
use at least 900 seconds or five times their record duration. task.toml keeps
at least 10% headroom over the sum of all episode limits.

The display is 1280×900, English C.UTF-8, UTC, fixed wall clock
2024-06-15 12:00:00 and GNUMERIC_PRNG_SEED=program-bench. Animation and cursor
blinking are disabled. Program checks ignore timestamps, generated IDs and
serializer bookkeeping. Native preferences are flushed by a normal exit.
Every GUI checkpoint carrying operations has a frontend assertion so the
shared driver actually executes its recipe and evaluator goal.

| Excluded behavior | Concrete reason |
| --- | --- |
| Network documents, external data connectors and external applications | Offline process/network boundary; links may navigate within the workbook only |
| User plugins, Python/Perl macros, GDA and component embedding | Code-loading integrations disabled or refused by runtime; compiled optional integrations are absent |
| Physical printer output and device-dependent paper handling | No printer devices; page settings and PDF documents are tested |
| Alternate locale/desktop integration | One English locale and isolated desktop are the execution contract |
| ssindex --encoding | The pinned native option is registered as a no-value flag despite its encoding argument description; supplying an encoding does not produce a valid index. UTF-8 indexing is covered |
| ssgrep --string-table-count | The pinned native process returns no matches even for present strings in the authored workbook; no zero-output assertion is used as a substitute for functional coverage |
| Classic stale-cache manual mode | Native rendering evaluates dirty visible cells even in Manual mode. Saved mode, explicit volatile recalculation and automatic updates are tested instead of asserting nonexistent stale display |
| Encrypted third-party documents | No native encryption writer/GUI export option is exposed by the pinned build; read-side password prompts need a separate encrypted-container fixture generator. This is a remaining format coverage limitation, not an external-secret restriction |
| Obsolete proprietary revisions outside the enumerated import/export matrix | No independent writer/parser or redistributable fixture is supplied for those revisions; listed SC/Oleo/dBase/SpreadsheetML inputs and fourteen maintained exports are independently authored/validated |

