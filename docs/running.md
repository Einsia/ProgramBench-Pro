# Benchmark setup

This page covers ProgramBench Pro's environment, evaluator, and result requirements. Follow the [Harbor documentation](https://harborframework.com/docs) for installation, agent configuration, model providers, and job execution. The paper uses Harbor 0.24.0. Run the commands below with Python 3.12 or newer; check `python3 --version` in the active shell, since Harbor can use a different Python installation from the system default.

## Resources and compatibility

| Component | Requirements or configured resources |
| --- | --- |
| Host | Linux x86_64, Python 3.12+, Docker Engine 23+, Docker Compose v2 or newer, and Docker Buildx supporting named build contexts and `--no-cache-filter` |
| Kernel | Landlock enabled, ABI 1 or newer; 20 tasks use it. ABI 2 supports cross-directory rename/link operations within permitted paths; ABI 3 adds file-truncation restrictions. |
| Solving agent | 4 vCPUs, 16 GiB RAM, 20 GiB configured storage, 28,800 seconds per task |
| Reference | Separate container during solving; for example, Gitea is capped at 2 CPUs / 8 GiB RAM. Inspect the task's `environment/docker-compose.yaml`. |
| Verifier | Separate container with a task-specific time limit; 4 CPUs with 8 GiB RAM for 36 tasks and 12 GiB for BentoPDF. Each parallel lane adds another verifier. |
| Disk | The tracked source tree is approximately 1.33 GB. Images, downloads, staged build contexts, candidate copies, and evidence need additional space. |
| Evaluator | HTTPS Chat Completions endpoint supporting the task's observations, tool calls, and the selected reasoning parameters; browser/desktop tasks include image input |

The eight-hour limit covers the solving phase. Building images and running the verifier take additional time. For example, Gitea's configured verifier timeout is 98,400 seconds. GPU hardware is needed only if you choose to host model inference yourself.

A kernel version alone does not establish that Landlock is enabled. On the required Linux x86_64 platform, this checks the host ABI:

```bash
python3 - <<'PY'
import ctypes
import os
import platform

if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
    raise SystemExit('Use a Linux x86_64 host.')
libc = ctypes.CDLL(None, use_errno=True)
abi = libc.syscall(444, None, 0, 1)
if abi < 1:
    raise SystemExit('Landlock unavailable: ' + os.strerror(ctypes.get_errno()))
print('Landlock ABI:', abi)
PY
```

Landlock must also be usable inside Docker. The [program-only smoke test](smoke-test.md) checks the container ABI and a reference episode without model API calls. Stop if a prerequisite fails; do not disable the task's isolation. A successful image build alone does not establish that the reference application can run.

## Build images

From the benchmark repository root:

```bash
TASK_DIR=tasks/terminal-tui-app/micro
RUN_DIR="$(mktemp -d /tmp/programbench-pro.XXXXXXXX)"
mkdir -p "$RUN_DIR/tmp"
export TMPDIR="$RUN_DIR/tmp" PYTHONDONTWRITEBYTECODE=1
bash "$TASK_DIR/environment/build.sh"
```

The build fetches downloads listed in `solution/SOURCE.json`, checks their SHA-256 hashes, and creates `program-bench-micro-{base,agent,reference,verifier}:1.0.0`. It then verifies runtime consistency and checks that the agent image excludes the reference implementation. Repeat the build for each task you intend to run.

Task images preinstall Codex CLI 0.162.1 and Claude Code 2.1.296. Configure Harbor to use the matching installed version. Provider-side web search must be disabled: it executes outside the container and can bypass the offline task boundary. For strict runs, use a model endpoint that pins the selected model and rejects provider-side tools.

Keep credentials, temporary directories, jobs, and evaluation artifacts outside the checkout. Preserve the source revision and image identities with reported results. System packages installed from apt can change between builds even when the base image digest is fixed.

## Frontend evaluator

The evaluator is separate from the solving model. It judges frontend checkpoints while the candidate runs in an offline container. A host-side bridge holds the evaluator credential and relays requests through a private directory; the candidate cannot access that credential, hidden tests, or evaluator logs.

Choose one of the two existing integrations:

- **Default task verifier:** start a bridge for each assessment and expose its directory through the task-specific environment variable below.
- **ParallelVerifier adapter:** configure this repository's custom Harbor verifier with the task, image, endpoint, and credential file. It starts and cleans up the bridges itself. See [the adapter configuration](../tools/README.md#harbor-integration).

For the default verifier, use the `TASK_DIR` and `RUN_DIR` from the build example. In Bash, create a raw key file outside the checkout and provide the endpoint interactively:

```bash
umask 077
KEY_FILE="$RUN_DIR/evaluator.key"
read -r -s -p "Evaluator API key: " evaluator_key
printf '\n'
printf '%s\n' "$evaluator_key" > "$KEY_FILE"
unset evaluator_key
chmod 600 "$KEY_FILE"
read -r -p "Evaluator HTTPS base URL (include /v1 if needed): " EVAL_BASE_URL
MODEL_RPC_DIR="$RUN_DIR/model-rpc"
printf 'Evaluator bridge directory: %s\n' "$MODEL_RPC_DIR"
```

Start the bridge in a terminal that remains open during the assessment:

```bash
python3 "$TASK_DIR/tests/evaluation/bridge.py" \
  --spool "$MODEL_RPC_DIR" \
  --api-key-file "$KEY_FILE" --base-url "$EVAL_BASE_URL" \
  --model kimi-k3 --effort high --protocol openai-chat
```

The bridge first checks the endpoint and real checkpoint tool schemas. It writes `config.json` in the spool directory only after the check succeeds. In the shell launching the assessment, enter the absolute bridge directory printed above. For micro:

```bash
read -r -p "Absolute evaluator bridge directory: " MODEL_RPC_DIR
if [[ "$MODEL_RPC_DIR" == /* && -f "$MODEL_RPC_DIR/config.json" ]]; then
  export MICRO_MODEL_RPC_STORAGE="$MODEL_RPC_DIR"
  echo 'Evaluator bridge is ready.'
else
  unset MICRO_MODEL_RPC_STORAGE
  echo 'Bridge is not ready. Check the directory and bridge log before continuing.' >&2
  false
fi
```

Launch the assessment only after this reports that the bridge is ready. For other tasks, replace `MICRO` with the task name in uppercase, keeping only letters and digits: for example `GITEA_MODEL_RPC_STORAGE` or `MUSICBRAINZPICARD_MODEL_RPC_STORAGE`. Each assessment needs its own bridge process and fresh directory. Stop its bridge after the assessment finishes. Concurrent tasks or repeated attempts must not share a spool.

The bridge appends `/chat/completions` to `EVAL_BASE_URL`. It requires HTTPS and rejects credentials, query strings, and fragments in the URL. `openai-chat` sends `reasoning_effort` and `max_completion_tokens`. The alternative `deepseek-chat` dialect also sends `thinking` and carries `reasoning_content` between turns. Endpoint compatibility for the evaluator does not establish compatibility with the solving agent's API.

Use `kimi-k3` / `high` for the paper's evaluator configuration. Changing the evaluator can change scores; report its model, effort, and protocol. The bridge exits after 172,800 idle seconds by default. Increase `--idle-timeout` if the gap before its first request, including solving and preceding program episodes, could exceed that limit.

## Aggregate results

The task scorer reports `episode_passed`, `episode_total`, `episode_rate`, and a six-decimal `reward` in `verifier/summary.json`. The overall score is 100 times the mean of the 37 task episode pass rates. Averaging all checkpoints or averaging the five category means gives a different metric.

Before reporting a full benchmark score, require exactly one selected, complete, valid comparison per task under the same experimental configuration. Keep oracle checks, different solver configurations, and repeated attempts separate. Record the task revision, images, solver/harness, effort, time/resource limits, and evaluator settings.

Check `full_suite`, `diagnostic`, `infrastructure_error`, and `reward` in each summary. Diagnostic subsets and infrastructure failures have no formal reward. Harbor's job mean can treat missing rewards as zero; it is not a substitute for validating all 37 task results. Recover interrupted comparisons before aggregation, preserving valid complete episodes including genuine failures. See [recovery rules](../tools/README.md#resume).

For a directory containing one selected result per task in the standard `verifier/summary.json` layout, the following command validates coverage and calculates the score. It refuses duplicates and incomplete runs; it does not infer the model identity or choose among repeated attempts.

```bash
python3 - "$RUN_DIR" <<'PY'
import json
import math
from pathlib import Path
import sys

expected = {}
for path in Path('tasks').glob('*/*/task.toml'):
    manifest = json.loads((path.parent / 'tests/data/manifest.json').read_text())
    task = path.parent.name
    if task in expected:
        raise SystemExit(f'Duplicate task directory: {task}')
    expected[task] = len(manifest['episodes'])
if len(expected) != 37:
    raise SystemExit('Expected the 37-task release checkout.')
scores = {}
for path in sorted(Path(sys.argv[1]).rglob('verifier/summary.json')):
    result = json.loads(path.read_text())
    task = result.get('task')
    if task not in expected or task in scores:
        raise SystemExit(f'Unknown or duplicate task result: {path}')
    if (result.get('mode') != 'compare' or not result.get('full_suite')
            or result.get('diagnostic') or result.get('infrastructure_error')
            or result.get('reward') is None):
        raise SystemExit(f'Incomplete or invalid comparison: {path}')
    passed, total = result['episode_passed'], result['episode_total']
    if (type(passed) is not int or type(total) is not int
            or total != expected[task] or not 0 <= passed <= total):
        raise SystemExit(f'Invalid episode counts: {path}')
    rate = passed / total
    if (not math.isclose(result['episode_rate'], rate, abs_tol=1e-12)
            or result['reward'] != round(rate, 6)):
        raise SystemExit(f'Inconsistent task reward: {path}')
    scores[task] = rate
missing = expected.keys() - scores.keys()
if missing:
    raise SystemExit('Missing valid tasks: ' + ', '.join(sorted(missing)))
print(f'ProgramBench Pro: {100 * sum(scores.values()) / 37:.1f}% (37/37 tasks)')
PY
```

The command uses the unrounded episode ratio. If aggregating the serialized six-decimal rewards instead, document that choice. Saved candidates can also be evaluated independently with [the parallel comparison runner](../tools/README.md).

## Common problems

| Symptom | What to check |
| --- | --- |
| Reference never becomes healthy | Landlock support inside Docker, task image tags, and reference container logs |
| Bridge preflight fails | HTTPS base URL, raw key file with mode 0600, evaluator model ID, tools, and protocol-specific reasoning fields |
| `compare needs an externally started model bridge` | The private bridge has become ready and its directory is mounted through the correct task-specific environment variable |
| `network_mode='no-network' is not supported` shortly after launch | Harbor's isolation probe can time out on a busy host; inspect the probe before retrying |
| `infrastructure_error` or missing reward | Inspect verifier and bridge logs; recover the comparison before aggregation |

[Back to the README](../README.md)
