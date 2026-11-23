# Newsboat coverage

Task 1.0.0, unmodified upstream Newsboat 2.45. The manifest contains
**161 episodes (134 program, 27 GUI), 865 checkpoints, 1,227 backend assertions and 117 frontend assertions**. The task score is the fraction of episodes whose points all pass.

## Coverage map

| Feature | Backend | Frontend |
| --- | ---: | ---: |
| appearance | 9 | 0 |
| cache-updates | 42 | 0 |
| cli | 9 | 0 |
| configuration | 266 | 0 |
| deletion | 5 | 5 |
| dialogs | 12 | 5 |
| exports | 16 | 5 |
| feed-parsing | 151 | 0 |
| filters | 170 | 10 |
| flags | 5 | 5 |
| formatting | 78 | 11 |
| history | 7 | 0 |
| html-rendering | 43 | 3 |
| http-feeds | 36 | 0 |
| keybindings | 14 | 0 |
| killfiles | 48 | 0 |
| navigation | 48 | 28 |
| opml | 68 | 0 |
| persistence | 24 | 0 |
| podcasts | 20 | 0 |
| query-feeds | 19 | 0 |
| reading | 13 | 13 |
| search | 20 | 6 |
| settings | 54 | 0 |
| sorting | 20 | 20 |
| subscriptions | 18 | 0 |
| tags | 12 | 6 |
| **Total** | **1227** | **117** |

## Distinct rules and inputs

- `spec_parsing.py`: RSS 0.91, 0.92, 1.0/RDF and 2.0; Atom; title/author/content
  fallbacks and precedence; HTML versus text content; CDATA, entities, Unicode,
  whitespace; absolute and relative links and bases; GUID fallbacks; fixed dates,
  timezone offsets, leap dates and epoch boundaries; enclosure/media metadata;
  feed language and right-to-left state. Each assertion isolates one field rule
  or an inseparable related field group, not every field on every input.
- `spec_filters.py`: feed and article attributes; equality, regex and negated
  comparisons, numeric boundaries, inclusive ranges, word membership, Boolean
  precedence and parentheses; malformed expressions; query feeds; download and
  display killfiles with global, URL and regex scopes; tags and scoped search.
  Filter fixtures have both matching and nonmatching items, read/unread states,
  flags, authors, tags and enclosures.
- `spec_config.py`: distinct local configuration defaults, live assignments,
  resetting values, Boolean/integer syntax, invalid arguments, includes, source,
  comments and quoting, effective configuration export, custom key bindings,
  multi-key bindings, internal macros and saved filters.
- `spec_ui.py`: navigation, feed/article reading, source and link views, read
  states, flags, deletion and purge, tag selection, filters, search, sorting,
  article saves, enclosure queueing, contextual help and dialog switching.
- `spec_rendering.py`: semantic HTML-to-text output including blocks, lists,
  headings, tables, quotes, preformatted text, images, relative/duplicate links,
  ignored script/style/comment content, entities, whitespace and malformed HTML;
  feed/article/tag/title format identifiers, conditionals, alignment, date
  formats; long lists and articles, visible formatting and rich article reading.
- `spec_storage.py`: OPML 1/2 imports and exports, nested folders, naming/tag
  attributes, duplicate URLs, missing fields, malformed documents, read-GUID
  import/export, restart/reload persistence, article updates and cache cleanup,
  retention limits, podcast filename expansions, automatic queueing and CLI
  alternate input/config/cache files.
- `spec_behavior.py`: state-dependent configuration effects, confirmation and
  cancellation, read-on-hover, unread navigation, wrapping, one eligible random
  choice, hard quit, persistent command/search histories and history limits,
  alternate history files, configured colours/highlights, title/hint visibility,
  subscription aliases/hidden feeds/comments/duplicates and query writes through
  to original articles. The mark-feed-read jump setting is exercised in the
  article list, its documented context, with a fully read intervening feed.
- `spec_local.py`: batch saves and existing/duplicate/Unicode filenames;
  closing and activating dialogs, next/previous dialogs; nested search history
  and opening an original feed; half-page and unread boundary navigation;
  changed/unchanged content with scoped reset-unread rules; fixed old/future
  articles with different retention flags; startup refresh and internal commands;
  query prepopulation; visible-feed-only reload; description/content precedence;
  same-process subscription additions, removals, aliases, order and tag changes;
  configuration continuation, escaping, multiple includes/source and reloading
  exported configuration; shared binding prefixes/cancellation, local overrides,
  unbinding and internal macros; query origin fields, right alignment, text
  width, scrolloff, file/directory titles; BOM and actual Latin-1 bytes, empty
  feeds, duplicate GUIDs and inherited Atom bases; duplicate, absent-enclosure
  and query-feed podcast queue behavior.
- `spec_http.py`: a public offline loopback HTTP fixture serves 200 and
  301/302/307/308 redirects, ETag/Last-Modified validators and 304, cached data
  surviving 404/500, changed/new articles, empty-response retries with different
  attempt limits, custom User-Agent and persisted cookies. Requests and resulting
  product state are both observed; no external service is involved.

GUI checkpoints are authored user goals; their companion checks concern only
those goals. Each independent scenario is prepared in a fresh home through
public runtime operations. A preceding scored case is never replayed as setup.
Checks that intentionally accumulate state declare dependencies. Program cases
recover from an exited process through the shared driver and restore the
episode's unscored preparation before the next independent checkpoint; scenario preparation
uses runtime reset, independently of the application's command handling.

## Observation and comparison

All inputs and observations pass through the runtime: `place`, `update_inputs`, `home`, `cache`,
`cli`, `http_source`/`http_requests`, terminal input and screen snapshots, plus
lifecycle operations. The live-input channel only replaces subscription,
configuration and feed inputs; it does not edit product outputs. HTTP fixtures
serve caller-provided responses and never fetch URLs or serve files. Cache
checks project named, product-visible columns and omit database row IDs,
last-modified bookkeeping and other incidental data. The observer takes a
consistent bounded snapshot including committed WAL data and supports tables
without an implicit rowid. Missing cache tables or
expected output files fail instead of becoming a successful empty observation.
No test reads the candidate's private implementation directly.

Screen checks extract fixture labels, selection, counts, requested text and
format expansions. They do not compare whole screens. A selection may occupy
any width and use a distinct background or reverse video; no specific colour is
required outside explicit colour-setting cases. Sort comparisons treat equal
keys as unordered groups. Feed sorting fixtures give different orders for
names, tags, total counts, unread counts and most recent unread dates; no pair
of fields has identical or reversed orders. Article date/link/GUID permutations
are independent. Each scored sort starts from the opposite ordering. GUI paging goals name visible
content or a selected article, avoiding a requirement on candidate row heights.

OPML checks parse XML rather than compare bytes and ignore unknown extra
attributes and descriptive head titles; categories are normalized. Read-state exports compare sorted GUIDs.
Configuration export checks normalize recognized Boolean and integer representations
and reject missing values, extra values and invalid Boolean strings. Empty screen
results require a live application and a recognizable view; normal exit means
status zero. Focus detection considers only target list rows, excluding unrelated
colored notices. Message checks depend on their same-checkpoint state companions.
Article exports compare semantic text; renderer cases retain meaningful block
and indentation structure with trailing whitespace normalized. Layout is checked
only when an explicit format/alignment setting is the behavior under test.
Title-content goals accept cosmetic separators between the required ordered
phrases; a colon between the prefix and feed name is not a semantic difference.

Feed and tag counts are compared as numeric fields, accepting both parenthesized
counts and labeled counts. Flag display checks require the actual flag letters,
without imposing a literal label prefix. Feed-sort scenarios verify their loaded
counts during unscored preparation so an incomplete cache cannot be frozen as a
successful sorting result.

Publication dates are fixed in the feed documents. Retention cases use 2024 and
2099 dates, far from the one-day cutoff; age-based clock boundaries,
feed download timestamps and wall-clock timers are not frozen. Output paths are
logical home paths, and runtime observations redact private instance roots.
Sources and runtime are hashed into the frozen bundle.

## Exclusions and reference limitations

- Internet services and authentication backends (Feedbin, FeedHQ, FreshRSS,
  Inoreader, Miniflux, NewsBlur, ownCloud News, The Old Reader and TT-RSS), proxy
  authentication, certificate trust and online full-page downloads are excluded.
  TLS/proxy integration needs additional services and trust material unavailable
  through the confined public surface. Local HTTP redirects, validators, retries,
  failures and cookies are covered separately. OPML uses local files.
- External browser/editor/pager/player execution, bookmark/notification commands,
  pipes, `exec:` and `filter:` feeds and shell expansion are unavailable under the
  reference process sandbox. Internal application macros and configuration
  includes confined to the home remain available and are covered.
- Podboat is a separate downloader/player executable with network and external
  playback requirements. Newsboat's enclosure selection, queue creation,
  duplicate prevention and filename generation are covered.
- Uncontrolled random orders, real-time age cutoffs, periodic timer scheduling,
  beep/terminal-notification effects, mouse/terminal escape protocols beyond the
  public keyboard surface and external terminal emulators are outside the stable
  observable interface. Random unread selection is tested with one eligible item.
- In this upstream release, feed descriptions and feed publication dates are
  discarded when parsed feeds are reconstituted from cache. Positive filtering
  and display of those unavailable values is therefore not asserted. Article
  descriptions, dates and all retained feed fields are covered. Configuration
  export in 2.45 does not preserve every escaped backslash on reload; the suite
  records the actual parsed value and the actual reloaded value. A nonempty
  opml-url is supplied because this release exports its empty default without
  the argument needed to parse it again.
- Exact default colours, incidental spaces, status wording in frontend judgments,
  invisible cursor bookkeeping, tie order, scrollbar geometry and animation are
  not frontend requirements. Explicit format-string and colour configuration
  effects are program checks.

## Interface and budgets

The terminal is 120×36 with xterm-256color, C.UTF-8 and UTC. Evaluator tools are
`key`, `keys`, `type`, `wait`; observations contain numbered screen rows and
visible style runs. Setup and program channels are the same ones documented in
runtime help. The agent image also carries the runtime for `--target self`.

Readiness requires a painted alternate terminal screen or two seconds of stable
visible screen content (repeated identical redraws are accepted) for applications using a plain terminal. Startup diagnostics alone
must not allow preparation to interrupt the reference's cache initialization.

Each GUI episode has 180 calls and 1,800,000 tokens. The default time limit is
1,800 active seconds. `gui-navigation-3`, `gui-reading-2`, `gui-search-1`,
`gui-sorting-1`, `gui-sorting-3` and `gui-sorting-4` have 10,800 seconds because
the evaluator forecasts later checkpoint costs from recent round-trip latency,
including model-request retries. The
reference's observed call count and token peak must remain below 40% of these
limits. CLI output is streamed with a 1 MiB limit per stream and a 60-second
timeout; exceeding either returns candidate failure while the broker survives.
The frozen record stores episode durations; the runner computes wall limits
from these measurements, and the verifier timeout covers their sum with margin.
The model and endpoint are selected by the host bridge (Kimi K3, high effort),
not frozen into the task.

