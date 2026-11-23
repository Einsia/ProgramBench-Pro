# Isolated parallel comparison

An episode is one complete, realistic usage scenario consisting of a sequence of continuous operations and one or more checkpoints.

`parallel_compare.py` is the host entry point for all published tasks. It runs one or
more independent verifier containers using the task's security,
shared-memory and process-limit settings. Each container runs its assigned
episodes serially through the `tests/test.sh` entry point. An episode
is never split across containers. Its candidate copy, application state,
temporary files, exchange directories and evaluator bridge are private.

The host needs Python 3.11+, Docker and Docker Compose v2. Build the verifier
image first using the task's build instructions. The runner pins its image ID;
it does not build images, run a solving agent or mount the Docker socket/model
credential inside a verifier. Generated files belong outside the checkout and
task source directory, in an artifact directory chosen for your environment.

Set `RUN_DIR`, `CANDIDATE_DIR`, `KEY_FILE` and `EVAL_BASE_URL` to your own external
run directory, saved submission, credential file and evaluator endpoint. The
example uses the published frozen bundle in the task's `tests/data`.

```sh
mkdir -p "$RUN_DIR/tmp"
export TMPDIR="$RUN_DIR/tmp" PYTHONDONTWRITEBYTECODE=1
python3 tools/parallel_compare.py \
  --task tasks/browser-frontend-app/piskel \
  --image program-bench-piskel-verifier:1.0.0 \
  --candidate "$CANDIDATE_DIR" \
  --out "$RUN_DIR/compare-01" \
  --parallelism 4 \
  --api-key-file "$KEY_FILE" \
  --base-url "$EVAL_BASE_URL"
```

`--parallelism` accepts **1, 2 or 4**, defaulting to 1. It limits verifier
containers for this invocation, not all invocations on the machine. Account for
other running tasks when choosing it. The default model settings are
`kimi-k3`, `high`, `openai-chat`. Each GUI lane starts its own bridge
with preflight and one request at a time, using the frozen per-episode budgets.
Use `--protocol openai-chat` for standard OpenAI Chat Completions; the configured
`--effort` is sent as `reasoning_effort` in either protocol. The standard protocol
uses `max_completion_tokens` and omits `thinking` and `reasoning_content`.
Pure program lanes make no model calls. The credential stays on the
host. Disk admission thresholds are deployment settings: set
`--root-reserve-gib` and `--data-reserve-gib` for your root and output filesystems.
Both default to 0 (disabled); the runner assumes no host storage size or layout.
When configured, they check free space before copying inputs and admitting each
lane; they do not reserve capacity against unrelated jobs.

Omit `--truth` to use the task's published `tests/data`. Pass `--truth "$TRUTH_DIR"`
to validate a newly recorded external bundle before adopting it. Omit `--episode` to
compare the full suite. Repeating `--episode ID` selects a diagnostic subset:

```sh
# Add to the same command, with a fresh output directory:
--episode resize --episode gui-resize
```

Diagnostic runs never emit a formal task reward, even when all selected
episodes pass. Complete full runs aggregate assertion counts using the task's
own scorer: fully passed episodes divided by all episodes, with equal weight
per episode. An episode passes only when every point
passes. Channel ratios remain diagnostics. Lane rewards are never averaged.
Missing or infrastructure-interrupted episodes
invalidate the run and suppress reward. Exit codes match the serial runner:
0 = all selected assertions pass, 1 = complete with genuine failures,
2 = infrastructure/configuration/incomplete execution.

For **oracle comparison**, install the task's unmodified `solution/solve.sh`
into an external directory using its build environment, then pass that installed
directory as `--candidate`. It follows exactly the same parallel path as a
model's saved candidate. The original directory is copied before use and is
never mounted writable or chowned by the runner. `record` runs serially and
produces the standard-answer bundle. Validate the bundle before placing it in
`tests/data` and building the images. The comparison runner reads frozen truth
without modifying it.

## Resume

Use a fresh `--out`, the same logical inputs and selection, and
`--resume-from "$RUN_DIR/compare-01"`. Parallelism may change, for example
from 4 to 2. The candidate, test/runtime sources, frozen bundle, image ID,
evaluator configuration, container policy and coordinator version must match.
The worker allocation and scheduling hints are deliberately not part of this
identity. `--timings "$PREVIOUS_VERIFIER_DIR"` can supply historic episode durations
for more even allocation; it never supplies verdicts.

Resume refuses a still-running source coordinator or verifier. It retains both
complete passes and complete genuine failures. It only reruns episodes without
a complete valid result, not individual checkpoints. Recorded evidence hashes
are verified before reuse. A killed coordinator can also recover completed
episode outputs from its saved lane plans. Copies and original attempts remain
separate. Results from different input identities cannot be combined, and the
runner does not select the best result across attempts.

SIGINT/SIGTERM stops only this invocation's containers and preserves outputs.
An abrupt host kill can leave containers alive: stop the exact names recorded in
`lanes/*/plan.json` before resume. No global prune or unrelated process cleanup
is performed. `lanes/*/cleanup.json` records container removal. The runner keeps
input snapshots, lane evidence and working directories for diagnosis; clean up
those task-owned artifacts only after their results have been accepted.

## Harbor integration

With Harbor 0.24.0 installed, add this repository's `tools/` to `PYTHONPATH` and
use `harbor_parallel_verifier:ParallelVerifier` as the verifier `import_path`.
Its kwargs are `task_root`, `image`, `api_key_file`, `base_url`, and
`parallelism` (1, 2 or 4). Model defaults remain `kimi-k3/high/openai-chat`.
It reads Harbor's collected `artifacts/app/solution`, keeps the original Harbor
verification deadline across recovery attempts, and returns the full episode
score through Harbor's `VerifierResult`.

Each lane preserves the task's container security settings and the CPU/memory
limits from `task.toml`. Size fleet admission by the sum of episode lanes as
well as the number of assessments; two lanes can consume twice one verifier's
resources. An optional `admission_file` contains `{"episode_parallelism": 2}`
and selects the lane count at verification admission. Active lanes finish at
their admitted count; a subsequent recovery can choose another count through
the standalone runner.

The adapter stores every attempt under `verifier/parallel/`, exposes completed
evidence at the usual Harbor verifier paths, and records live lane metadata in
`verifier/parallel.json`. Only incomplete comparisons are resumed automatically;
completed genuine failures are retained. Source/identity mismatches stop the
run for inspection. Credentials and Docker access stay on the host.

Configure the adapter before starting a Harbor job. Replacing Python source
does not change the verifier class already loaded by a running job.

## Evaluation evidence

`identity.json`, `manifest.json`, `schedule.json`, lane plans and child identities
describe exactly what was assessed. `accepted.json` fingerprints complete
episode evidence. `collection.json` lists missing episodes and reused results.
`summary.json`, `results.jsonl` and (only for valid full comparisons) `reward.*`
are generated by the verifier image's own manifest validation/scoring code.
`summary.json` additionally reports selected episode count and complete
episode pass count; its inherited `counts` describes the full task manifest.

## Shared scoring implementation

`tools/scoring.py` calculates task scores and channel statistics. It is the only
scoring source maintained in the repository. Each task's build script copies it
into an immutable build context, and its verifier Dockerfile installs it as
`/tests/evaluation/scoring.py`. The task source directories contain no scorer
copies. Image verification checks the installed file against this shared source.

Containers use their installed copy and need no host checkout mount. Build tasks from a
complete repository checkout, and rebuild verifier images after changing the
shared scorer. The parallel runner refuses an image whose scorer differs from
the shared source.
