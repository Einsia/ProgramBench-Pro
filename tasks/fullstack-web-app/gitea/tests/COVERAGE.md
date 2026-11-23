# Gitea coverage

Version 1.0.0. Exact counts and budgets come from `data/manifest.json`:
61 episodes (14 program, 46 GUI and 1 mixed) with 3,302 checkpoints and 3,377
scoring points, 102 frontend and 3,275 backend (3,200 protocol checks and 75
independent checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| Authentication/accounts | Username/email sessions, rejected password, account registration and duplicate rejection; API identity, profiles, settings, emails, follows, tokens and authorization boundaries |
| Repositories | Public/private, initialized/empty/template creation, metadata and clearing, archive and disabled units; protocol creation, validation, settings, stars, watches, search, derived repositories and missing resources |
| Issues/comments | Text, Unicode, Markdown/sanitization, comments and duplicate multiplicity, title/state transitions, refresh, labels/milestones and filtered/search collections; reactions, subscriptions, deadlines, pins, dependencies |
| Permissions | Anonymous/outsider/read/write/admin representatives in the UI; independent API read/write/revoke checks per role on public and private repositories |
| Files/Git | Browser create/edit/delete, Unicode/nested paths, file history; contents/blob byte integrity, trees, refs, branches, tags, commit pagination, Git smart HTTP clone and push with permission enforcement |
| Pull requests | Diff inspection, approval, rejected-review resolution and merge through the UI; API reviews, filters, merge styles, conflicts, statuses, branch protection and review gates |
| Publishing | Stable/draft/prerelease releases, assets and queries; Wiki create/edit/history in the UI and the Wiki API (pages, revisions, pagination, deletion); package details/filter/version deletion; generic and npm packages, OCI registry, LFS objects, locks and permissions |
| Organizations/teams | Public/private creation, team access, public discovery; API memberships, visibility, team units on a private repository and deletion |
| Profiles/social | Profile fields/clear, repository star/unstar and discovery; API notifications and pagination |
| Persistence | Process restart with the same DATA_DIR: visible issue persistence and protocol reads of repositories, permissions, issues, files, releases, organizations and labels |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the
  same code that serves the reference to the model: its api operation (public
  API, packages, registry, attachments, Git smart HTTP and LFS; a real Git client
  talks to a local relay that forwards each request through that operation) and
  its lifecycle operations (restart, status). Nothing reads candidate files,
  databases or processes.
- Program episodes are the protocol modules, one isolated episode each (the
  releases and the Wiki are separate episodes). Their cases run in declared
  order on one fresh instance, so later cases build on the state of earlier
  ones exactly as a client would; a scored case is never replayed as setup.
  The modules' fixture cases are unscored setup items that accept any success
  status; the checkpoints that need a fixture declare it, so a failed fixture
  blocks only them.
- Observations normalize generated identities (a typed bijection that must stay
  consistent across the episode), wall-clock timestamps, this run's origin,
  line endings and the repository language (computed asynchronously). Response
  objects may carry extra fields; every reference field must be present and
  equal. Data-keyed maps (languages, npm versions and tags, team unit maps, LFS
  actions) stay exact. Error responses are compared by status and must not
  expose protected content.
- Points that a server without the feature passes (an empty list, a denial, a
  "gone" read) are bound (`requires`) to a positive point of the same episode,
  preferably of the same scenario, with the smallest reference observation (a
  status or a short body rather than a full object), so that the companion
  shows the feature exists without repeating unrelated fields; the bindings in
  `bindings.py` connect negative observations to positive behavior in the same
  protocol episode. Frontend
  points that only verify a rejection or an unavailable view are bound to a
  positive point of their episode (the visible repository, the stored setting,
  the account still signing in) and their acceptance names a positive anchor
  (the signed-in identity, the repository page, the sign-in or sign-up form).
- Dependent checkpoints run when the prerequisite's backend points passed (or
  its frontend points when it has none). Wiki API points depend on the creation
  of their page, which also tells whether the Wiki API works at all (the
  reference's API needs the Wiki branch setting that the mixed episode's GUI
  checkpoint sets; an implementation without that quirk does not).
- A crashed application is restarted with the same data before the next
  checkpoint, so one crash costs only the points of its own checkpoint.

## Interface and budgets

The evaluator operates the pages through the runtime's browser operations
(open, reload, back, click, fill, type, select, check, press, pointer, drag,
wheel, scroll, upload, wait) in a 1280×900 Chromium session that starts at
`/user/login`, and observes them through the runtime's snapshot (text, controls
with refs, form names and bounds, scroll position and page size) and viewport
screenshot. Product HTTP interfaces and static assets do not open as pages.
GUI episodes use the budget formula scaled by checkpoint count: calls
min(160, 45 + 25n), active seconds min(1800, 480 + 180n), tokens
min(1,500,000, 350,000 + 180,000n); the mixed Wiki episode has 70 calls, 900
seconds and 650,000 tokens. Unscored public setup prepares repositories,
issues, collaborators, branches and pull requests through the API, and minimal
uploads of the viewed packages and LFS objects through their protocols.

`reference/` contains the deterministic recipes for the pinned standard only;
they drive it through the same runtime operations, and their control names and
routes are never the candidate's frontend contract.
