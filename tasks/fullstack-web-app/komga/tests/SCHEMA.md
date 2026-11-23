# Episode evaluation contract

This protocol is shared by every program-bench task using this framework. Task
identity, version and the black-box runtime configuration are in
`evaluation/task.py`; reviewed coverage and interface specifics are in
`COVERAGE.md`. `suite.build()` defines the authoritative manifest. The JSON
output contract is `result-schema.json`; the frozen oracle contract is
`data/schema.json`.

## Units

An episode is one complete, realistic usage scenario consisting of a sequence of continuous operations and one or more checkpoints.

| Unit | Meaning |
| --- | --- |
| feature | Coverage family; not an execution unit |
| episode | Isolated execution: its own runtime instance (fresh copy of the solution, fresh data directory); one evaluator conversation when it has frontend points |
| checkpoint | Freeze/observation boundary inside an episode |
| assertion | Declared binary check (`frontend`/`agent` or `backend`/`program`); an episode passes only when all its assertions pass |
| setup item | Unscored public preparation of non-target state, with an id |

Episode, checkpoint, assertion, model-call, GUI-action and program-call counts
are distinct metrics and are reported separately. A task has at most 1,000
frontend assertions; backend assertions are unbounded.

## One runtime for exploration and evaluation

The task's black-box runtime (`environment/runtime/`, installed at
`task.RUNTIME`) drives whatever solution directory it is given: the standard
answer in the reference container while the model explores, and the candidate
(or the standard answer during record) in the verifier. The verifier runs
episodes one at a time. For each episode it copies `/app/solution`, starts
the runtime as root against that copy and a fresh instance directory (the
product runs as the candidate user; the runtime's socket is private to root),
and afterwards stops the runtime, kills every process of the candidate user
and deletes the workspace. The reference container also runs its broker as root
and the product as the unprivileged `agent` user. Reference RPC sockets and
broker logs are private to root; product state remains writable by the product.

- The evaluator operates the candidate only through the runtime's GUI
  operations that `task.GUI_OPS` whitelists; its tool is derived from the
  runtime's machine-readable help (`blackbox-v2`) and its observations are the
  runtime's own observation and screenshot operations (`task.OBSERVE`).
  Whatever the model cannot do or see through `blackbox` on the reference, the
  evaluation cannot do or see either.
- Setup and program checks use only channels the runtime also offers the model
  (for example api/http, upload, download, list_files, clipboard, restart,
  reset, status). Checks of internal state are not allowed.
- Readiness is surface-generic and identical for reference and candidate: web,
  an HTTP status below 500 for `GET /` on `PORT`; desktop, an accessible window;
  terminal, the control interface answers and the screen is drawn.

## Manifest

`suite.build()` returns `contract.manifest(episodes)`: task, version, kit,
protocol, reference version, surface, scoring unit, counts and episodes.
The scoring unit is `episode`. The evaluator model is not part of the manifest
(see Frontend).

Episode fields: `id`, `feature`, `execution` (`program`, `gui` or `mixed`),
`initial_state`, `setup` (list of items, each with a unique `id` and an optional
`before` checkpoint id), `inputs`,
`checkpoints`, and for GUI/mixed episodes `session`, `budget` (`calls`,
`tokens`, `seconds`), `allowed_equivalents`, `forbidden_bypasses`.

Checkpoint fields: `id`, `goal`, `assertions`, optional `depends_on` and
`lifecycle: restart` (the product is restarted with the same data before the
checkpoint). Assertion fields: `id`, `channel`, `method`, `requirement`,
optional `requires`.

### Dependencies (gating)

`depends_on` lists prerequisites; each entry is one of:

- a checkpoint id of an earlier checkpoint: passes when every backend
  assertion of that checkpoint passed, or, if it has no backend assertions,
  every frontend assertion;
- an assertion id of an earlier checkpoint of the same episode: passes when
  that assertion passed;
- `setup:<id>`: passes when that setup item succeeded.

A checkpoint whose prerequisites did not all pass is not executed; its points
are `blocked` (`dependency`, or `setup_failure` when only setup items failed).
Gating only decides whether dependents run; every point is scored on its own.

### Companion points

A point that only verifies a rejection or that nothing changed names, in
`requires`, the positive points of the same episode that prove the feature
exists. Such a point passes only if its own check passes and every companion
passes; otherwise it is `fail` with `companion`. Bindings must not form cycles.

### Setup scope

Setup items are unscored. An item runs once after the runtime has started, or,
when it names a checkpoint in `before`, right before that checkpoint (whether or
not the checkpoint itself is blocked), for example a scenario reset in front of
the scenario's first checkpoint. A failed item blocks only the checkpoints that
declare `setup:<id>`; a checkpoint may not depend on an item that runs after it. Per-checkpoint
preparation (task hook `prepare`) that fails blocks only that checkpoint.
Scored cases are never replayed as setup; a task that needs earlier state
prepares it with its own minimal setup items.

## Frontend

One evaluator agent per GUI episode operates the candidate through the
runtime's GUI operations, then judges the checkpoint's frontend assertions. The
model, effort and endpoint are runtime configuration of the host bridge:
recorded in `identity.json` and `summary.json` (`evaluator`), never frozen.
Changing the evaluator model does not require a new record. The prompt
(`agent.PROMPT_VERSION`), tools and this protocol are versioned with the framework.
Every GUI episode has fixed call, cumulative-token and active-time budgets in
the manifest. Active time includes the evaluator model's own inference time and
excludes queueing and provider retries, so a slower evaluator model leaves less
time for operating the application.

The agent receives the functional goals, inputs and acceptance conditions,
never private observations, expected backend objects or program results. It
sees the current observation, bounded recent events, its previous goals,
actions and verdicts, and a framework-kept "Explored so far" list of its last
30 actions with whether the screen changed; older observations are archived on
disk instead of being resent. The prompt has a stop rule: after the goal's
route and the obvious equivalents fail or have no visible effect, the agent
completes the checkpoint as unable and reports fail.

`complete_checkpoint` closes operations. When another operating call would use
the share reserved for later checkpoints or any judging reserve, the framework
closes operations itself. Reserves are sized from the recent per-call cost. In
both cases the framework captures candidate-after evidence, then supplies frozen
reference before/after and candidate before/after evidence and exposes only
`report_checkpoint`. The agent reports each frontend assertion as
pass/fail/unresolved with an explanation and evidence labels, citing
candidate-after and reference-after. A structurally invalid report gets up to
two format-only repair requests (three attempts) that disclose no program result
and reopen no operation. An interface that cannot be observed or stops
answering leaves that checkpoint's frontend points unresolved.

Frontend criteria govern meaning and user-visible behavior. Reference pixels,
widget classes, exact captions and incidental interaction counts are not
candidate requirements. A failed action, an unsupported goal, budget exhaustion
or incomplete evidence cannot become pass by self-reported completion.

## Backend

Program episodes run no evaluator agent. Deterministic observers check public
interfaces, files, media and durable state through the runtime's channels, with
semantic normalization; GUI checkpoints may declare independent program checks
of their resulting state or artifacts. No program result is returned to the
agent. After every checkpoint the driver asks the runtime for the product's
status and restarts a crashed product with the same data, so later checkpoints
are judged on their own.

## Failure kinds and validity

| Status | `failure_kind` | Meaning |
| --- | --- | --- |
| fail | `result_mismatch` | A program check's assertion failed |
| fail | `program_exception` | A program check raised another exception (traceback kept as evidence) |
| fail | `agent_verdict` | The evaluator reported fail |
| fail | `companion` | The point's own check passed, a required companion did not |
| fail | `candidate_timeout` | The point's checkpoint was running when the episode reached its wall-clock limit |
| unresolved | `agent_verdict` | The evaluator reported unresolved |
| unresolved | `budget` | The evaluator budget was exhausted before a verdict |
| unresolved | `observation` | The candidate interface could not be observed or stopped answering |
| unresolved | `report_protocol` | No valid report after three attempts |
| blocked | `dependency` | A declared prerequisite did not pass |
| blocked | `setup_failure` | A declared setup item, or the checkpoint's preparation or restart, failed |
| blocked | `candidate_start` | The application did not become ready |
| blocked | `candidate_missing_start` | The submission has no start.sh |
| blocked | `candidate_timeout` | Not reached before the episode's wall-clock limit |
| blocked | `infrastructure` | Verifier fault; the run is invalid |

Candidate behaviour never invalidates a run: exceptions caused by candidate
output fail the affected point, a missing `start.sh` scores 0, and a slow or
hung candidate hits its wall limit (`candidate_timeout`). Only explicit
verifier faults (runtime unreachable, decoder failure, evidence storage) and a
provider outage make a run invalid; then no reward is written and the run must
be repeated. Other episodes keep running except when the provider is
unavailable.

Wall-clock limit per episode, model waiting excluded: program episodes
max(900 s, 5 × recorded reference duration); GUI episodes budget seconds +
max(600 s, 5 × recorded duration). Recorded durations are in the frozen bundle.
A task's `[verifier].timeout_sec` is at least 1.1 × the sum of these limits
(plus start-up allowance) and at least 86,400 s.

## Record, compare and frozen data

Record drives the installed standard answer with deterministic reference
recipes through the same runtime operations and no model calls, captures
reference evidence with the evaluator's observation function, and publishes a
bundle only when every declared assertion passes. Two records must agree on the
manifest, the program observations and the frontend evidence JSON. Compare validates the executable manifest and the completeness and readability
of reference evidence before launching. Source comments and documentation are
independent of the frozen bundle.

`data/manifest.json` holds all episode definitions and counts.
`data/oracle.json` holds program observations and frontend reference pairs,
whose evidence lives under `data/reference/`. Identical images are stored only
at their first occurrence; subsequent entries refer to that same relative
path, including across episodes. Filenames remain ordinary evidence names.
`data/oracle-meta.json` contains versions, counts, the successful zero-model
record status and per-episode durations. Frozen output contains no source or
asset digests. Record uses the installed reference application without a frozen
file-hash list.

At startup the runner keeps an in-memory snapshot of all `/tests` and installed
runtime entries, including contents, owners and permissions. Before each
worker starts and after it exits, the runner checks that snapshot and probes
private-directory access as the application user. A mismatch invalidates the
whole run and produces no reward. Each episode uses the same fixed neutral `session` directory, cleared before
and after execution. Leftovers are atomically renamed before deletion; cleanup
failure invalidates the run. Specifications use `contract.files_path()` for
exchange paths, with `instance=False` when files live beside the instance. Worker arguments arrive over a private input pipe; runtime state and log
paths contain no episode or checkpoint identifiers.

## Outputs

`results.jsonl` rows identify episode, checkpoint, assertion, feature, channel,
method, status, binary score, reason, evidence IDs and failure kind. Only
`pass` scores 1; `fail`, `unresolved` and `blocked` score 0. `summary.json`
reports fixed denominators, channel ratios, failure-kind counts, usage, the
evaluator configuration, reused episodes and validity. Every episode has equal
weight: it passes only if every declared frontend and backend assertion passes
after gating and companion resolution. Any fail, unresolved or blocked point
makes its episode fail. Setup items remain unscored.

A valid full compare writes `reward.json` and `reward.txt` (rounded to 6 decimals):
fully passed episodes / total episodes. `episode_passed`, `episode_total` and
`episode_rate` expose the numerator, denominator and unrounded ratio. Frontend
and backend ratios are diagnostic metrics. Record, diagnostic (`--episode`)
and infrastructure-invalid runs never emit a reward.

The implementation is maintained in the repository's `tools/scoring.py`.
Each verifier image receives that file during its build and uses it for serial
and parallel result aggregation. The image content check verifies that the
installed copy matches the shared source.

Per-episode evidence, agent traces, actions, runtime and product logs (the
product's output is capped: first and last 2 MB), events and usage stay in the
output directory. `identity.json` binds sources, candidate, manifest, mode,
selected episodes, the diagnostic flag and the evaluator configuration;
`evidence.json` hashes the formal result files and lists reused episodes. An
interrupted run may resume (`--resume-from`) only from a non-diagnostic run
with identical identity, reusing its complete episodes, both successes and
failures.
