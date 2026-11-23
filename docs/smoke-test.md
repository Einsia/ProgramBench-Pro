# A program-only oracle smoke test

These commands target the micro task. Run them from the repository root on a Linux x86_64 Docker host with the documented build dependencies. They exercise source fetching, all four images, standard-answer installation, and one deterministic episode. They do not run a solving agent or call an evaluator API. A diagnostic subset intentionally produces no formal benchmark reward.

First check the actual Landlock ABI on the Docker host. A kernel version check is insufficient:

```sh
python3 - <<'PY'
import ctypes, os, platform
if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
    raise SystemExit('This release requires a Linux x86_64 Docker host.')
libc = ctypes.CDLL(None, use_errno=True)
abi = libc.syscall(444, None, 0, 1)
if abi < 1:
    error = ctypes.get_errno()
    raise SystemExit(f'Landlock is unavailable: errno={error} ({os.strerror(error)}). Use a host with Landlock enabled.')
print(f'Landlock ABI {abi}')
PY
```

On a supported host:

```sh
TASK_DIR=tasks/terminal-tui-app/micro
RUN_DIR=$(mktemp -d /tmp/programbench-pro-smoke.XXXXXX)
mkdir -p "$RUN_DIR/tmp"
export TMPDIR="$RUN_DIR/tmp" PYTHONDONTWRITEBYTECODE=1

bash "$TASK_DIR/environment/build.sh"

# Confirm the Docker security policy also allows the ABI query.
docker run --rm --network none --cap-drop ALL \
  --security-opt no-new-privileges:true --entrypoint python3 \
  program-bench-micro-base:1.0.0 -c \
  'import ctypes; c=ctypes.CDLL(None,use_errno=True); a=c.syscall(444,None,0,1); assert a>=1, ("Landlock unavailable inside Docker",ctypes.get_errno()); print("Landlock ABI",a)'

SOLUTION_DIR="$RUN_DIR/oracle" bash "$TASK_DIR/solution/solve.sh"

# The current CLI requires these flags even for program-only lanes.
# This is an intentionally unused placeholder, not an API credential.
printf '%s\n' 'unused-program-only-smoke' > "$RUN_DIR/unused.key"
chmod 600 "$RUN_DIR/unused.key"

python3 tools/parallel_compare.py \
  --task "$TASK_DIR" \
  --image program-bench-micro-verifier:1.0.0 \
  --candidate "$RUN_DIR/oracle" \
  --out "$RUN_DIR/compare" \
  --parallelism 1 \
  --episode cli-print-1 \
  --api-key-file "$RUN_DIR/unused.key" \
  --base-url https://unused.invalid/v1

python3 - "$RUN_DIR/compare/summary.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d['diagnostic'] and not d['infrastructure_error'], d
assert d['episode_passed'] == d['episode_total'] == 1, d
assert d['backend']['passed'] == d['backend']['assertions'] == 4, d
assert d['usage']['model_calls'] == 0, d
assert d['reward'] is None, d
print('Program-only oracle smoke passed; 4/4 assertions, no model calls.')
PY
```

Expected acceptance on a supported host is a passed episode, 4/4 backend assertions, zero model calls and no formal reward. A successful build alone does not establish that the reference application can run. Stop if either Landlock check fails.

[Back to the run guide](running.md)
