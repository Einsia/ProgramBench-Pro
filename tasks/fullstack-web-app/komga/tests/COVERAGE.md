# Komga coverage

Task 1.0.0, Komga 1.29.2. Counts are generated from the executable
manifest and frozen in `data/manifest.json`: 67 episodes (28 program and 39 GUI), 123 frontend and 1866 backend assertions.

| Feature and direct checks | Episodes |
| --- | --- |
| First claim, login, accounts, credentials, roles, access keys, revocation | `api-accounts`, `gui-first-account`, `gui-login`, `gui-users`, `gui-api-keys` |
| Self password change, invalid password, old/new authentication, cross-user protection, restart, success/failure authentication activity | `api-account-security`, `gui-self-password` |
| Library settings and validation, scanning, maintenance and deletion | `api-libraries`, `gui-library-create` |
| ComicInfo/EPUB/Mylar import, exclusions, one-shots, format switches, RAR conversion, local artwork | `api-scanner-formats` |
| Transient scans/pages, file import, deletion/restoration, extension repair | `api-file-episodes` |
| Series archive member and byte integrity, COPY/MOVE import source/destination relations | `api-archives-import` |
| Book and series metadata fields, clearing, locking, partial and bulk updates, preservation across restart | `api-books-metadata`, `api-series-metadata`, `gui-edit-book`, `gui-edit-series`, `gui-tags-*`, `gui-series-status`, `gui-series-readingDirection` |
| Mixed-population structured/legacy search, numeric/string/date/boolean predicates, compound queries, sorting and pagination | `api-search-books`, `api-search-series`, `gui-search`, `gui-metadata-filters` |
| Facets, alphabetical groups, latest/new/updated/on-deck discovery | `api-referential`, `api-search-*`, `gui-catalogs` |
| Roles, library sharing, age and label restrictions, independent streaming/download permission, denied mutations | `api-permissions` |
| Reading progress, per-user isolation, whole-series read/unread, next/previous, restart | `api-reading`, `gui-reader`, `gui-reader-incognito`, `gui-mark-*` |
| Readium progression and Mihon series/KOReader protocols | `api-reader-protocols` |
| Cross-series manually ordered list Mihon progress, partial/all read, negative boundary, per-user isolation and restart | `api-list-progress` |
| Collections/readlists CRUD, membership, ordering, summaries, queries, archive download, persistence | `api-collections`, `api-readlists`, `gui-collections`, `gui-readlists`, `gui-create-*` |
| ComicRack XML/CBL exact/multiple/unmatched/ambiguous matching and matched ordered-list creation | `api-comicrack`, `gui-comicrack-import` |
| CBZ/CBR/EPUB/PDF original bytes, pages, thumbnails, JPEG conversion, page indexing, WebPub/EPUB resources | `api-media`, `gui-pdf`, `gui-epub` |
| Book/series/collection/readlist cover upload, selection, invalid selection, deletion, fallback and restart | `api-posters-books`, `api-posters-series`, `api-posters-collections`, `api-posters-readlists`; every episode has `upload-a`, `upload-b`, `list`, `select-b`, `select-a`, `invalid-selection`, `delete-b`, `restart`, `delete-a` |
| Current comic page as book/series poster, persistence after refresh | `gui-poster-from-page-book`, `gui-poster-from-page-series` |
| RTL/vertical/Webtoon reading, mode-specific advance, first/last navigation, single/double layout, width/height fit and thumbnail jump | `gui-reader-r`, `gui-reader-v`, `gui-reader-w`, `gui-reader-layout` |
| Duplicate groups, classification, group removal and targeted single-match removal preserving other books and archives | `api-maintenance`, `api-single-duplicate` |
| Global/user settings, visibility, validation, safe server settings, theme | `api-settings`, `gui-server-settings`, `gui-theme` |
| OPDS 1.2 and 2 catalogs/search/paging/authorization; Kobo initialization/metadata/download/state/sync | `api-opds`, `api-kobo` |
| Media problems and operation history | `api-maintenance`, `gui-media-history` |

## Setup and dependencies

Every setup/check uses documented runtime HTTP, exchange-file or lifecycle
operations. No product databases, processes or private files are read. Account
and fixture creation accepts successful HTTP responses. Common library setup
waits for resources and bounded asynchronous quiescence, never for successful
full-text search or correct imported metadata. Library configuration has a
minimal fixture independent of successful scanning. Search waits occur within
search checks. Search-specific fixtures add varying series sizes (including
ties), EPUB/PDF, corrupted media, a deleted item, a one-shot, empty metadata and
a user-selected poster; every tested discriminator has both populations.

Saved-resource references and actual state dependencies are explicit. A failed
setup blocks only declared dependents. Partial metadata preservation follows
its pair-writing prerequisite; independent list operations do not form one
long dependency chain. Persistence checks compare the state immediately before
and after restart where the entire cumulative object is incidental. The runtime
restarts a crashed product before continuing.

## Behavioral comparison

Short and long IDs are mapped at URL path/query boundaries; business text is
kept literal. Volatile timestamps and loopback origins are normalized.
Unordered metadata uses semantic member matching, allowing additional object
fields without changing membership. Tags/subjects/authors are sets; document
readingOrder, pages and manual list order remain ordered. Sorted API pages
use a secondary name key. OPDS latest groups validate current public timestamps
and permit ties at the page boundary, while checking each returned identity,
title, page count and acquisition/poster links.

Duplicate-page matches are an unordered catalog: their book identities are
normalized before sorting, so generated identifier order does not affect the result.

Images are decoded with Pillow and projected over the whole image to 24×32
RGB values. Dimensions must match; mean absolute channel error is at most 7,
and at most 3.5% of channels may differ by more than 35. Conversion cases also
require the requested actual image encoding and matching Content-Type. PDF
fixtures include contrasting text, borders and multiple colored shapes.
Document byte identity and archive member/content hashes remain exact.
A transient remote HTTP framing error on GET/HEAD is retried once; mutations
are not replayed. Empty data cannot stand in for positive ComicRack matches or image content.

GUI goals name user outcomes and target documents, accept equivalent visible
controls and routes, and are supported by reference screenshots/snapshots.
Reference recipes are recording code, not candidate UI requirements. Media
inputs are original locally generated geometric art, text and standard file
containers. CBL inputs are provided as normal evaluator upload files.

## Interface and budgets

Chromium viewport 1280×900, en-US, UTC. The runtime exposes visible controls,
embedded document text, screenshots, uploads/downloads and normal GUI actions.
GUI budget: calls max(200,50n), tokens max(3,000,000,600,000n), active seconds
max(1800,360n) for n checkpoints. Program wall limits are at least 900 seconds and five times the
measured reference duration; verifier timeout is calibrated from their sum.

## Exclusions

External identity-provider configuration, mail delivery, internet release and
announcement retrieval, Kobo Store proxying and hardware firmware provisioning
require unavailable external systems. Offline Kobo/KOReader/Mihon/OPDS/Readium
interfaces are covered. TLS, reverse proxy and OS-service installation are
deployment tasks. JVM diagnostics, executable converter configuration and
arbitrary host files are restricted by the isolation boundary. Bundled font
assets may render documents but are not exported as implementation files.
Password-protected/multi-volume proprietary archive generation is excluded;
stored RAR/CBR, CBZ/ZIP, EPUB and PDF decoding/conversion remain covered.
Equivalent browser UIs are accepted; the classic and next layouts do not
require duplicate copies of each functional test.
