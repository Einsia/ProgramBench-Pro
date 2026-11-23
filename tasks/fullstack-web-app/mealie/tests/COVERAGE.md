# Mealie coverage

Task version 1.0.0, reference Mealie 3.29.0. The executable
specification and frozen `data/manifest.json` define 61 episodes
(18 program and 43 GUI), 1367 checkpoints and
1467 assertions: 115 frontend and 1352 backend. The backend
comprises 1252 protocol assertions and 100 independent public-state checks
of GUI actions.

| Feature family | Covered behavior |
| --- | --- |
| Recipe lifecycle | Create and slug collisions, Unicode names, complete replacement and partial updates, bulk writes, duplicate, deletion, ingredients, instructions, section/step summaries, notes, nutrition, yield/time/source, extra data and recipe settings |
| Organizers | Categories, tags and tools: CRUD, slug lookup, search, filtering, ordering, pagination, merge with source/target recipe associations and deduplication, unused entries; GUI CRUD and category merge with recipe readback |
| Ingredient data | Foods, aliases, labels, substitutions, units, plural forms, standard conversion metadata, merges with recipe/shopping references; household On Hand membership; GUI food/unit/label CRUD, On Hand and JSON downloads |
| Cooking and discovery | Recipe searches and category/tag/tool filters with distractors; scaling servings/quantities and cooking mode; suggestions distinguish matching, missing foods/tools and food substitutions, inventory included/ignored and restart persistence; GUI Recipe Finder; favorites, ratings, last-made and public explore routes |
| Recipe activity | Comment CRUD, timeline events and decoded images, private share tokens, public/private visibility, bulk actions; GUI comments, ratings, favorites, cooking history, share creation/guest viewing/revocation and public/private switching |
| Planning | Note and recipe meals, entry types, dates, filters, ordering, rules before random selection with one matching recipe and a distractor, iCalendar feed; half/double recipeScale and shopping quantities; GUI dinner/lunch, Friday rules, changing plan servings and adding a day/full plan to shopping |
| Shopping | Lists and items, quantities, checked states, ordering, labels, recipe ingredients and references, merge operations and household scope; GUI creation, addition, bulk check/uncheck, checked-item cleanup, deletion and adding a recipe |
| Cookbooks | Saved filters select distinct recipe subsets, slugs, visibility, positions and bulk reorder; GUI create/browse/rename/delete |
| Accounts and administration | Username/email login, stable failed-session behavior, logout/refresh, successful local password reset, new/old passwords and token reuse, independent per-user ratings and aggregate changes, profiles, decoded user images, API tokens, invitations, membership and administrative CRUD; GUI profiles/tokens/preferences/users/groups/households and reset/login |
| Permissions | Anonymous, restricted member, another household, privileged member and administrator act on 11 resource families using independent existing targets and owner reads before/after mutations; two groups with same-name data test list/ID/read/update/delete scope; webhook/notifier household isolation; GUI group isolation |
| Integration configuration | Stored webhooks, event notifiers and recipe actions; provider CRUD, group boundaries, default/audio/image selections and settings; no outgoing service is needed for stored configuration |
| Local data exchange | Correct single-recipe ZIP, bulk and shared exports; parsed JSON and decoded media content; actual downloaded recipe archive re-upload/import and business/media readback; HTML/JSON-LD and streamed import, assets, parsers, seeders; ten migration formats; GUI recipe ZIP and foods/units JSON downloads |
| Maintenance and backups | Product/about/theme/startup/statistics/storage, temporary/image/folder cleanup, backup create/list/download/upload/delete/restore; actual downloaded backup bytes re-uploaded and restored after recipe deletion, then recipe/media readback; GUI backup create/delete |
| Persistence | Process replacement preserves recipes/media, reference data, activity, favorites, plans/rules, lists, cookbooks, preferences, accounts and authorization tokens; GUI description survives restart |

| Program episode | Backend assertions |
| --- | ---: |
| `protocol-organizers` | 118 |
| `protocol-ingredients` | 86 |
| `protocol-recipes` | 60 |
| `protocol-mealplans` | 61 |
| `protocol-shopping` | 63 |
| `protocol-cookbooks` | 36 |
| `protocol-accounts` | 92 |
| `protocol-social` | 91 |
| `protocol-files` | 83 |
| `protocol-extras` | 78 |
| `protocol-access` | 269 |
| `protocol-persistence` | 27 |
| `protocol-configuration` | 45 |
| `protocol-interchange` | 36 |
| `protocol-scope` | 47 |
| `protocol-roundtrip` | 14 |
| `protocol-discovery` | 30 |
| `protocol-identity` | 16 |

GUI episodes include `inventory-finder`, `scaled-plan-shopping`,
`download-foods`, `download-units`, `download-recipe`, `merge-category`,
`password-reset`, `recipe-sharing`, `recipe-publicity` and `group-isolation`.

## Public channels and comparison

All setup and program checks use the public `api` operation of the same runtime
that serves exploration and drives the candidate. File bytes travel through
multipart requests, product media/download responses and the documented browser
upload/download operations. Restarts use `restart`; no check reads private
files, databases or processes. GUI checks read only the state directly caused
by their goals. Setup is unscored, accepts any successful response and declares
its dependent checkpoints. Each program fixture request is a separate setup
item; `dependencies.py` explicitly names the earlier fixtures and scored state
changes each case needs, including fixed slugs, bulk effects and readbacks.
No module-wide fixture gate or inferred candidate dependency is used.
Unscored sign-in accepts any successful 2xx with a usable token; dedicated
authentication assertions still compare protocol status. Scored cases are never replayed as setup. Crashed
candidates are restarted by the shared driver.

UUIDs and generated meal-plan/API-token integer identities are compared through
consistent bijections; integer identity types remain distinct. Pagination links
compare canonical paths and sorted query parameters. Generated instants, backup
names, random image cache keys, secret tokens and compressed site sizes are
normalized; fixed dates supplied by the cases remain literal values. Meal-plan
dates intentionally relative to the run retain their relative offsets. Recipe
organizer sets are sorted by semantic content. Equal values of an explicitly
requested top-level ordering key are compared as unordered groups. Responses are projected onto
behavioral fields; extra response object fields are allowed, and required
fields must exist. Numeric values use a small JSON representation tolerance.
Errors compare HTTP status and validation categories rather than prose.

Image responses are decoded with Pillow in the verifier, then compared by
dimensions and four interior RGB region averages (absolute per-channel tolerance
12 for normal image re-encoding). Uploaded patterns have distinct quadrants.
ZIP responses must parse and pass CRC checks; JSON members retain normalized
business data, media use the image comparison, and other members retain byte
digests. Secret/password material and generated values are normalized. Actual
download/upload/import/restore episodes establish that the downloaded bytes
are usable through the public product interfaces. Backup fixtures upload a fixed
patterned user image through the public API before export, so the product's
random default avatar does not become a frozen expectation. The generated image
cache suffix in exported user records is normalized; the decoded image is still compared.

Each frontend assertion describes a functional result. Different navigation,
labels and layout are accepted. Reference recipes use only the runtime's GUI
operations. The reference's public state is checked before after-evidence is
captured. Rejection goals bind a successful sign-in companion. References to
controls are derived from their visible semantics, and volatile evidence
includes generated identities, tokens, timestamps and backup names. Screenshots
may differ in relative date text, avatars, focus or hover state.

## Interface and budgets

Chromium uses a 1280×900 viewport, English locale, UTC and reduced motion.
The shared runtime provides browser navigation, semantic control actions,
pointer/keyboard input, scrolling, uploads, snapshots and screenshots. Tooltip
names are included in snapshots, and pointer movement can reveal them. Product
API/static documents never open as pages. The browser reports the reachable
local product connection as online while all external requests stay blocked.

For a GUI episode with n checkpoints the evaluator budget is min(400, 120 + 60n) calls,
600 + 240n active seconds and 600,000 + 250,000n cumulative input/output tokens.
The inventory-finder episode has 2,000,000 tokens for its longer filter and inventory flow.
The evaluator is Kimi K3 with high reasoning effort,
configured by the host bridge. Program episodes make no model calls.

Every episode gets fresh solution and data directories. Program wall limits
are max(900 seconds, five times measured record duration). GUI wall limits add
the active-seconds budget to max(600 seconds, five times record duration).
The verifier timeout is at least 86,400 seconds and is set from the total limits
with at least 10% margin when the frozen bundle is adopted.

## Exclusions and boundaries

- Network services: URL scraping (single, bulk and streaming), remote image/asset
  fetch, AI generation/transcription/image recognition, provider connectivity
  tests/debug calls, SMTP delivery and emailed invitations, outgoing webhook/
  notifier execution, OAuth/native OAuth, LDAP and reverse-proxy authentication.
  Their successful execution requires external servers. Provider, notifier,
  webhook and recipe-action configuration remains covered offline.
- Browser/host services: actual printer output, clipboard interoperability,
  system wake locks, mobile camera capture, push delivery and multiple offline
  browser devices. These depend on host services, hardware or external clients.
  Desktop Chromium recipe views, cooking/scaling, imports and attachments are
  covered. The offline shopping UI is driven with a reachable local connection.
- Database deployment alternatives: the reference uses SQLite. PostgreSQL
  deployment, infrastructure/environment setup and server version checks are
  outside the reconstructed product's user interface contract.
- Runtime restrictions: file exchanges use basenames and bounded bytes;
  downloads use a product-file suffix allowlist. File-token downloads require
  unchanged tokens issued through this runtime. Arbitrary paths, code execution,
  source/static browsing and external navigation are unavailable. Rejected
  runtime requests are not scored as product behavior.
- Unhandled upstream errors are not contracts: unknown category/tag slug or
  update (including cross-group category/tag updates), invalid nonempty group deletion, and a member modifying another
  user's comment can raise server errors in this release. Successful paths,
  supported missing-resource errors and other permission combinations remain
  covered. Malformed query filters that cause upstream server errors are omitted.
