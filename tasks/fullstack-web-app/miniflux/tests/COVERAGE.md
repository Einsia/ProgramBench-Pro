# Miniflux coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
65 episodes (21 program, 41 GUI and 3 mixed) with 1,033 checkpoints and 1,111
scoring points, 97 frontend and 1,014 backend (936 protocol checks and 78
independent checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Accounts | Sign-in with a valid and a wrong password, sign-out and protected pages; REST users (create, read, update, delete, administrator rights, validation of every setting, the list sorted by username), `/v1/me`, API keys (create, list, use, delete), the version and health endpoints, CORS preflight; settings pages (appearance, sorting, time zone, custom CSS, language, password and its confirmation, username conflicts, reading behavior, global entry rules, home page) and their effects (newest entries first, keyboard shortcuts turned off, a feed without media player), user administration and its refusal to other accounts, API keys, sessions and the About page in the browser |
| Subscriptions | Direct feeds, site discovery with a choice between feeds, subscription options (category, user agent, original content, credentials), missing and duplicate feeds; REST feed creation with every option and its validation, discovery (alternate links, base element, well-known addresses, YouTube/GitHub canonical addresses, credentials, user agent and cookie), feed settings and their validation, counters, icons, removal |
| Fetching | User agent, conditional requests (ETag, Last-Modified, ignored HTTP cache), errors and their counters, redirects, disabled feeds, refresh of one feed, a category and all due feeds (also from the feeds page in the browser), entry updates and ignored updates, an entry edited by the user across refreshes, the crawler; feed icons (the feed's own image, icon links in page order, root page, `/favicon.ico`, data URLs, reduction of large and refusal of oversized pictures, shared icons, icons that appear later) |
| Feed formats | RSS 2.0 (titles, links, GUIDs, dates, authors, content and descriptions, enclosures, media and iTunes extensions, comments, categories, encodings), Atom 1.0 and 0.3, JSON Feed 1.0 and 1.1, RDF (RSS 1.0) |
| Content processing | Sanitizing (scripts, frames, forms, links, images and their sources, media, tables, unknown tags), rewrite rules and site rules, URL cleaning and rewrite rules, block and keep expressions, entry block and allow rules of feeds and users, the scraper with rules, preview and saving, reading times, the media proxy for images and enclosures with signed addresses |
| Entries | Listing with every filter, order (also by category and by last change), direction and page, search, status and star changes, bookmarks, edits, history flush, enclosures and their progress, category and feed views; in the browser: reading and automatic marking, unread/read/star toggles in lists, mark page, feed, category and everything as read, history and its flush, all entries of a feed, pagination, original content, sharing and the shared list, search with the unread filter, tags, attachments, pictures through the media proxy, keyboard shortcuts |
| Categories and OPML | REST categories (titles, hiding, counts and their alphabetical or unread-count order, entries, feeds, marking, refresh, removal with and without feeds) and OPML export/import (nested outlines, the product's setting attributes, duplicates, invalid documents, round trip); in the browser: category create, duplicate, rename, hide, delete, entries, starred entries, feeds, counts, OPML file and URL import and export |
| Client APIs | Fever (key, groups, feeds, favicons, items with since/max/with ids, unread and saved ids, marking items, feeds, groups and everything) and Google Reader (ClientLogin, tokens, user, subscriptions, tags, stream ids with filters and paging, contents with every id form, tag edits, marking streams, quick add, subscription edits, label rename and removal, errors and the bad-token flag), each enabled by the evaluator in the integration settings |
| Integrations | Webhook (signed save and new-entry events, a feed's own webhook URL), Linkding, Wallabag with its token exchange, Apprise (also a feed's own service URLs) and Slack, each configured by the evaluator; the REST save action and the integration status |
| Persistence | Process restart with the same DATA_DIR: accounts, passwords, categories, feeds and settings, entry states, enclosure progress, API keys, counters, and a visible category in the browser |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the
  same code that serves the reference to the model: its api operation (REST,
  Fever and Google Reader APIs, media proxy addresses, feed icons, health
  checks), its local web operations (resources the product fetches and the
  requests it sends, including webhook and integration deliveries) and its
  lifecycle operations (restart, status). Nothing reads candidate files,
  databases or processes.
- Program episodes are the protocol modules, one isolated episode each. Their
  cases run in declared order on one fresh instance, so later cases build on
  the state of earlier ones exactly as a client would; a scored case is never
  replayed as setup. The modules' fixture cases are unscored setup items that
  accept any success status; the checkpoints that need a fixture declare it, so
  a failed fixture blocks only them. Feed documents, pages and pictures are
  built from fixed data in the test modules, so the product reads the same
  bytes everywhere.
- Three mixed episodes start with browser checkpoints for settings that only
  the web interface offers (the Fever and Google Reader credentials, the
  integrations, a feed's own webhook URL); each has an independent backend check
  that uses the setting (a Fever request, a ClientLogin, a delivery observed in
  the local web), and the program cases that need the setting depend on it.
- Observations normalize generated identities (a typed bijection that must stay
  consistent across the episode: entries, feeds, categories, users, icons,
  enclosures, hashes, share codes, API keys and Google Reader item ids in every
  form), wall-clock timestamps (publication dates near the run are `[now]`),
  this run's origin, media proxy signatures, Google Reader tokens and webhook
  signatures (their presence and form). HTML content is compared as canonical
  markup (attribute order, whitespace-only text). Response objects may carry
  extra fields; every reference field must be present and equal. Error messages
  are the product's own wording; details that libraries append (decoder
  positions, network errors, database messages) are reduced to a marker.
  Build metadata of the version endpoint (dates, commits, toolchain) is not
  compared.
- Orders are compared only where they are the behavior (sorting, paging, the
  order of discovered feeds and of the requests made for an icon); members with
  equal sort keys compare as groups, other collections as multisets. Lists that
  also contain objects of other cases show only the objects of their own
  scenario, and reads of a state that earlier scored cases produced declare
  those cases as dependencies.
- Points that a server without the feature passes (an empty list, a refusal, an
  unchanged state, nothing sent, a document left as it was) are bound
  (`requires`) to a positive point of the same episode, and a bare
  confirmation (an empty 204 or 202, an "OK", the Fever acknowledgement)
  counts only together with the read that shows its effect. Frontend points
  that only verify a refusal or an absence are bound to a positive point of
  their episode (the account still signing in, the stored setting, the created
  category).
- Dependent checkpoints run when the prerequisite's backend points passed (or
  its frontend points when it has none). A crashed application is restarted
  with the same data before the next checkpoint, so one crash costs only the
  points of its own checkpoint.

## Interface and budgets

The evaluator operates the pages through the runtime's browser operations
(open, reload, back, click, fill, type, select, check, press, pointer, drag,
wheel, scroll, upload, wait) in a 1280×900 Chromium session that starts at `/`
(the sign-in page), and observes them through the runtime's snapshot (text,
controls with refs, form names and bounds, scroll position, page size and
pending downloads) and viewport screenshot. Product HTTP interfaces and static
assets do not open as pages. GUI and mixed episodes use the budget formula
scaled by their number of browser checkpoints n: calls min(160, 45 + 25n),
active seconds min(1800, 480 + 180n), tokens min(1,500,000, 350,000 + 180,000n).
Two episodes whose pages make every observation long are calibrated on the
evaluator's usage on the reference (under 40% of the budget): the
appearance settings (tokens 350,000 + 360,000n) and the seven integration
checkpoints (250 calls, 1,740 seconds, 3,500,000 tokens).
Unscored public setup publishes local web resources and prepares accounts,
categories, subscriptions, entry states and settings through the REST API.

`reference/` contains the deterministic recipes for the reference only;
they drive it through the same runtime operations, and their control names and
routes are never the candidate's frontend contract.

## Not covered

| Feature | Reason |
| --- | --- |
| Sign-in through Google or OpenID Connect, passkeys (WebAuthn) | External identity providers and authenticator devices are not available offline. |
| Integrations with fixed public HTTPS endpoints (Pinboard, Instapaper, Notion, Readwise, Raindrop, Telegram, Pushover and its per-feed setting, Archive.org, LinkTaco) | Online services; the local web has no HTTPS. |
| Further third-party services with configurable addresses (Betula, Cubox, Espial, LinkAce, Linkwarden, Nunux Keeper, Omnivore, Karakeep, Readeck, Shiori, Shaarli, Matrix, ntfy and its per-feed setting, Gotify, Discord, RSS-Bridge) | Each speaks the protocol of an external service; the settings-and-delivery mechanism is covered by the webhook, Linkding, Wallabag, Apprise and Slack, and every further service would add a browser configuration by the evaluator without a different product behavior. |
| HTTPS feeds, TLS and HTTP/2 options, per-feed and application proxies other than a refused connection | The local web is plain HTTP behind a single proxy. |
| Custom JavaScript setting | The runtime refuses it: it would run code in the reference browser. |
| Background scheduler, cleanup jobs and their timing (polling frequency, entry retention, archived entry removal) | Long timers outside an episode; refreshes are triggered through the API and the pages instead. |
| Deployment configuration (environment variables, TLS, listening options, metrics, authentication proxy header, maintenance mode) | Fixed by the runtime; not user-visible behavior. |
| Progressive web app installation, offline page, touch gestures and swipes | Need a service worker installation or a touch device that the runtime does not provide; their settings are covered. |
| Bookmarklet | Runs on third-party pages, which the browser cannot open. |
| Media player playback in the page | Headless playback of fixture audio is not observable; enclosure progress is covered through the API. |
| Removing another web session | The evaluator has one browser session, whose removal is a sign-out (covered); the sessions list is covered. |
| The "Save" action in the browser | The same integration delivery as the covered REST save action, without a different visible result. |
| Further interface languages and keyboard shortcuts | Translation data and alternative routes to covered actions; one language change, the shortcut help and a shortcut action are covered. |
