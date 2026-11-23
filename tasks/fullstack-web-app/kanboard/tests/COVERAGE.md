# Kanboard coverage

Version 1.0.0, pinned standard Kanboard 1.2.56. Exact counts and budgets come from `data/manifest.json`:
77 episodes (16 program and 61 GUI) with 1,591 checkpoints and 1,685 scoring points, 124 frontend and 1,561 backend (1,467 protocol checks and 94
independent checks of GUI checkpoints).

| Coverage | Behavior |
| --- | --- |
| JSON-RPC protocol/authentication | GUI (3 episodes): sign-in with the last logins and persistent connections pages, a refused password followed by the right one, sign-out after the signed-in dashboard. Protocol (71 points): request ids, notifications, batches and malformed envelopes with their error codes, named and positional parameters (missing, extra, unknown, defaults, type coercion), the application token of the user jsonrpc and user credentials, anonymous and wrong credentials, the lockout counter, user-only procedures, the health check and the application information procedures (time zone, colours, default colour, roles) |
| Users/groups | GUI (5 episodes): user creation and the duplicate-username refusal, editing and disabling (a disabled account cannot authenticate), removal, CSV user import (lower-cased usernames, roles, a duplicate skipped, the imported password signs in), groups with members. Protocol (117 points): creation with every optional field and each validation rule, reads, the sorted collection, updates, disabling and enabling, removal and what it unassigns, LDAP creation without a directory, groups and memberships |
| Profile | GUI (4 episodes): own profile (name and email, password change read back by signing in with the new password, personal API token that authenticates), interface language, personal public access (the personal Atom feed and iCalendar read back with the token), avatar image |
| Projects | GUI (8 episodes): team and personal projects, editing, closing and reopening, public access (public board, public task page, disabling), removal, duplication, the overview page, importing the tasks and the automatic actions of another project. Protocol (145 points): creation and validation, lookups by id, name, identifier and email, updates, status, public access tokens, removal, personal projects, metadata, project files and the activity procedures |
| Board | GUI (4 episodes): columns (add with limit and description, rename, hide its tasks on the dashboard, remove), swimlanes (add, move a task into one, task limit, disable), categories (add with colour, assign), collapsed cards and a hidden column. Protocol (95 points): column, swimlane and category creation, update, ordering and removal with their effect on tasks, work-in-progress limits, the board structure with tasks in their cells |
| Tasks | GUI (13 episodes): creation on the board with Markdown description, colour, assignee, priority and complexity; editing (category, due date, reference, tag); drag and drop between columns and the transitions it records; Move position; closing and reopening; removal; duplication and moving to another project; bulk move and bulk edit from the list view; bulk creation; closing a whole column; Assign to me and Start now; recurrence on close; predefined descriptions. Protocol (132 points): creation with every field and validation, date formats, reads, updates of each field, tags, closing and reopening, positions, moves between columns, swimlanes and projects, duplication, removal, overdue lists, recurring tasks |
| Subtasks/comments/links/files/tags | GUI (7 episodes): sub-tasks (add with assignee, status change, convert into a task), comments with Markdown (add, edit, remove) and their order (newest first), internal links (both directions) and an external web link, attachments (upload, remove), project and global tags. Protocol (257 points): subtasks with time tracking totals and per-user timers (52), comments with visibility levels and author-only changes (42), link labels, internal and external links (83), task files and metadata (42), project and global tags (38) |
| Automatic actions | GUI (1 episode): an action configured in the settings closes a task moved into Done. Protocol (116 points): the catalogue of actions and events, compatible events, creation and its validation, listing and removal, and for each action one point that makes its event happen (a task change or the daily job started through the cron job URL) and reads its effect |
| Activity/notifications | GUI (2 episodes): the project activity stream; notification settings, then web notifications from another user's change and from a mention. Protocol (45 points): the event each kind of change records (name, title with the names it mentions, author, task) for task, subtask, comment, file and link changes and moves between columns, positions, swimlanes and projects; no event for changes made with the application token; the project stream and a member's stream |
| Permissions | GUI (3 episodes): project permissions (add a member, change the role), a project viewer (board without task creation, settings unavailable; the refusal is bound to the positive board point), a custom role with a project restriction and a column exception (no task creation except in one column) and their effect on its member's board, where the member creates a task in the allowed column. Protocol (343 points): every project-scoped procedure at the boundary of its access level (viewer, member, manager), membership through a group, administrators and application managers outside the project, application roles for the application-level procedures |
| Search/views | GUI (7 episodes): board filters, list view filter, global search of tasks and of the activity stream, custom filters, dashboard (my tasks, my projects), task distribution and user repartition analytics, CSV exports of tasks, sub-tasks, task transitions and the daily project summary (rows read from the downloads), CSV task import. Protocol (82 points): every documented search attribute including the date ranges, relative and absolute dates, several values, quoting, combinations, results compared as sets of titles |
| Settings | GUI (4 episodes): link labels with their opposite, default columns and default categories for new projects, disabling personal projects (also refused through the API), application date format and a user's time zone, resetting the API token (the previous token is refused) |
| Feeds | Protocol (16 points): the project Atom feed and iCalendar (events, times, attendees, linked tasks, the date window of the calendar) with the public-access token, unknown and wrong tokens, changes, the former token after disabling, a new token after re-enabling |
| Persistence | Protocol (48 points): users, groups, projects, columns, swimlanes, categories, tasks with every field, subtasks, comments, links, files, metadata, actions and permissions read back after a restart with the same DATA_DIR; the user-specific procedures for signed-in users and their refusal for the application token |

## How points are checked

- Every check reaches the candidate through the task's black-box runtime, the same code that serves the reference to the model: its api operation
  (JSON-RPC API, feeds, cron job URL, health check), its download operation for exports and its lifecycle operations (restart, status). Nothing reads
  candidate files, databases or processes.
- Program episodes are the protocol modules, one isolated episode each. Their cases run in declared order on one fresh instance, so later cases build on
  the state of earlier ones exactly as a client would; a scored case is never replayed as setup. The modules' fixture cases are unscored setup items that
  accept any successful answer; the checkpoints that need a fixture declare it, so a failed fixture blocks only them.
- Refused attempts and edge cases act on subjects of their own (a checks project, task, label, group or account in the module), and shared lists read
  back only the records of the ordinary cases: accepting or refusing one edge case changes only its own points, never the positions, lists and reads the
  ordinary cases observe. Reads that check that refused requests stored nothing report which refused records exist next to an anchor record, and they do
  not gate the ordinary steps.
- GUI episodes have projects, tasks or accounts of their own from unscored public setup (API calls with ids). Their goals describe user outcomes; the acceptance describes what the reference after page shows. Independent backend points read the
  public state after the browser step (94 in all), naming the referenced columns, swimlanes, categories, users and projects instead of ids. Where another
  user acts during an episode (a task assigned by the administrator, a mention), the change is made through the API right before the checkpoint.
- A goal cannot carry a placeholder, so the viewer episode names the address /project/1/edit: the setup creates the first project of the fresh
  application, which is number 1 in the reference.
- Observations normalize generated identities (a typed bijection that must stay consistent across the episode; saved fixtures carry named labels; a
  removed record's name and alias are forgotten, so a store that gives a freed id to a new record is not mistaken for the old one), wall-clock timestamps
  (as days relative to the first day), business dates given as days (compared within 30 minutes, because the product stores the current time of day
  with a date), this run's origin, line endings and the secrets of tokens. Feed and calendar links are compared by the task they lead to, CSV task ids
  by identity, and file storage paths only by being set. Result objects may carry extra fields; every reference field must be present and equal.
  Data-keyed maps and empty objects stay exact. Errors are compared by HTTP status and JSON-RPC code, not by message. Search results, activity events
  of one change and calendar events are compared without order.
- Points that a server without the feature passes (a false, null or empty answer, a refusal or a missing resource) are bound (`requires`) to a positive
  point of the same episode: 406 program points. 249 are declared next to their positive point in the modules (refusals of the permission matrix, gone
  reads, wrong tokens). The other 157, in `bindings.py`, bind each observation to the canonical positive point of
  the same procedure, its first ordinary successful call in the module (154), else of the same family and scenario (3). Validation cases and edge or
  quirk cases (a missing subject, an id-only update, a boundary value, a duplicate, a case variant) are never companions, so a candidate that differs
  from the reference on one edge case does not lose the refusals of the procedure with it. Invalid-params errors and the product's generic error code
  need the procedure itself and are not bound; a point that depends on a positive scored step is not bound either. Frontend points that only verify a
  refusal or an unavailable view are bound to a positive point of their episode, and their acceptance names a positive anchor.

- Dependent checkpoints run when the prerequisite's backend points passed (or its frontend points when it has none).
- A crashed application is restarted with the same data before the next checkpoint, so one crash costs only the points of its own checkpoint.

## Not tested

- Mail delivery (email notifications, Send by email, password reset and invitations by mail): the task runs without network and without a mail server, so
  no delivery can be observed; notifications are tested through the web notifications.
- LDAP, reverse-proxy and external OAuth authentication (and remote users): they need an external directory or identity provider that the offline runtime
  does not have; LDAP account creation is checked only in its refusal without a directory.
- Two-factor authentication: enrollment and sign-in need one-time codes computed from a random secret by an authenticator, which neither the evaluator nor
  the runtime provides.
- The sign-in captcha after repeated failures: it is a random image challenge meant to stop automated clients; the refusal of wrong passwords and the
  failure counter are tested.
- Plugins and the plugin directory: installing plugins loads code into the reference and is disabled there; the directory is empty.
- Outgoing webhooks, third-party integrations and the webhook token reset: delivery needs a reachable external receiver, and the webhook token is the
  credential of that integration (the cron job URL that uses it is tested; resetting a token is tested with the API token).
- Database download, upload and optimization (About page): the deployment does not hand out or replace its database file; the download would be the
  product's own SQLite file, an implementation format rather than product behavior.
- Time-based analytics and settings (cumulative flow diagram, burndown chart, average time per column, lead and cycle time, estimated versus actual time
  over time, the board highlight period and refresh intervals, automatic sub-task time tracking and the timesheet values of timers): they depend on the
  wall-clock time between events and on daily snapshots, so they are not stable to compare; task distribution, user repartition and the daily summary
  export of the fixed day are tested, and the API records of timers are compared with relative times.
- The setting that allows only one sub-task in progress per user: its effect is a dialog in the sub-task status change of the web pages, while the
  sub-task status itself is tested through the pages and the API.
- Drag-and-drop restrictions of custom roles and their other project and column rules: a project restriction with a column exception is tested end to
  end, and the other rules are configured the same way; their effect is a refused drag or a missing control in the restricted member's pages. These
  rules apply to the web pages only (the API does not enforce them).
- Currency rates: no view of the product's core uses them (they serve cost features of plugins).
- Themes: a visual preference without other effect.
- Screenshots pasted from the clipboard: the runtime offers no clipboard to paste an image from; attachments are tested through file upload.
- Keyboard shortcuts: they are alternate routes to features that are tested through visible controls.
- The command-line interface: it is not reachable through the black-box interface.
- Calendar and Gantt views: they are plugins in this version and not part of the standard answer.

## Interface and budgets

The evaluator operates the pages through the runtime's browser operations (open, reload, back, click, fill, type, select, check, press, pointer, drag,
wheel, scroll, upload, wait) in a 1280x900 Chromium session, and observes them through the runtime's snapshot (text, controls with refs, form names and
bounds, scroll position and page size) and viewport screenshot. Product HTTP interfaces and static assets do not open as pages. GUI episodes use the
budget formula scaled by checkpoint count n: calls min(160, 45 + 25n), active seconds min(1800, 480 + 180n), tokens min(1,500,000, 350,000 + 180,000n);
the user creation episode, whose pages carry a long time zone list, has 180,000 more tokens.

`reference/` contains the deterministic recipes for the pinned standard only; they drive it through the same runtime operations, and their control names
and routes are never the candidate's frontend contract.
