#!/usr/bin/env bash
# Fetch reference downloads, build task images, and verify their contents.
set -euo pipefail
task_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
repo_root=$(cd -- "$task_root/../../.." && pwd)
scoring_source="$repo_root/tools/scoring.py"
if [ ! -f "$scoring_source" ]; then
  echo 'Build from a complete repository checkout containing tools/scoring.py.' >&2
  exit 1
fi
task=$(basename -- "$task_root")
version=1.0.0
export PYTHONDONTWRITEBYTECODE=1
: "${TMPDIR:?Set TMPDIR to an external directory for build contexts and checks.}"
mkdir -p "$TMPDIR"
case "$(realpath -- "$TMPDIR")/" in
  "$task_root/"*) echo 'TMPDIR must be outside the task checkout.' >&2; exit 1 ;;
esac
python3 "$task_root/environment/fetch.py"
case "$(docker info --format '{{.OSType}}/{{.Architecture}}')" in
  linux/x86_64|linux/amd64) ;;
  *) echo 'This task requires a Linux x86_64 Docker daemon.' >&2; exit 1 ;;
esac
docker compose version >/dev/null
image() { echo "program-bench-$task-$1:$version"; }
options=(--network host --build-arg HTTP_PROXY --build-arg HTTPS_PROXY --build-arg NO_PROXY)
for option in "$@"; do
  case "$option" in
    --no-cache|--pull|--progress=auto|--progress=plain|--progress=tty) options+=("$option") ;;
    *) echo "Unsupported build option: $option" >&2; exit 2 ;;
  esac
done
contexts=$(mktemp -d "$TMPDIR/build-$task.XXXXXXXX")
trap 'rm -rf -- "$contexts"' EXIT
# Every image gets its own immutable input directory, including named contexts.
mkdir -p "$contexts"/{base,agent,reference,verifier,verifier-runtime}
cp -a "$task_root/environment/." "$contexts/base/"
cp -a "$task_root/environment/." "$contexts/agent/"
cp -a "$task_root/." "$contexts/reference/"
cp -a "$task_root/tests/." "$contexts/verifier/"
mkdir -p "$contexts/scoring"
cp -a "$scoring_source" "$contexts/scoring/scoring.py"
cp -a "$task_root/environment/runtime/." "$contexts/verifier-runtime/"
# Refreshed staged mtimes prevent BuildKit from reusing a stale file checksum
# after different task archives restore identical path/size/timestamp metadata.
# Only disposable contexts change; source files and frozen contents stay intact.
python3 - "$contexts" <<'PBP_STAMP'
import os
from pathlib import Path
import sys
import time
stamp = time.time_ns()
for path in Path(sys.argv[1]).rglob('*'):
    if path.is_file():
        os.utime(path, ns=(path.lstat().st_atime_ns, stamp), follow_symlinks=False)
PBP_STAMP
docker build "${options[@]}" --target base -t "$(image base)" "$contexts/base"
docker build "${options[@]}" --target agent --no-cache-filter agent -t "$(image agent)" "$contexts/agent"
docker build "${options[@]}" --no-cache -f "$contexts/reference/environment/Dockerfile.reference" \
  -t "$(image reference)" "$contexts/reference"
docker build "${options[@]}" --no-cache --build-context runtime="$contexts/verifier-runtime" --build-context scoring="$contexts/scoring" \
  -t "$(image verifier)" "$contexts/verifier"
# The page policy must hold for the document a navigation lands on, not only for the request that starts it:
# a redirect is followed by the browser itself, so a route handler sees only the first request.
docker run --rm -i --network none --entrypoint python3 "$(image reference)" -B - <<'PY'
import ast
import asyncio
import inspect
import sys

sys.path.insert(0, '/opt/blackbox/runtime')
import broker

broker.origin = 'http://127.0.0.1:3000'
ALLOWED = ['/', '/login', '/stockoverview', '/product/new', '/shoppinglist', '/calendar', '/usersettings']
REFUSED = ['/js/grocy.js', '/css/grocy.css', '/packages/jquery/jquery.js', '/img/grocy_logo.svg', '/api/objects/products', '/api', '/config-dist.php']
failures = []
for path in ALLOWED:
    try:
        broker.landing_path(broker.origin + path)
    except ValueError as error:
        failures.append(f'a landed document at {path} must be readable: {error}')
for path in [*REFUSED, 'http://example.test/']:
    try:
        broker.landing_path(path if path.startswith('http') else broker.origin + path)
        failures.append(f'a landed document at {path} must be refused')
    except ValueError:
        pass


class Frame:
    def __init__(self, url):
        self.url = url

    async def goto(self, url):
        self.url = url


class Page:
    def __init__(self, *urls):
        self.frames = [Frame(url) for url in urls]
        self._blackbox_blocked = None


page = Page(broker.origin + '/js/grocy.js', broker.origin + '/stockoverview')
if asyncio.run(broker.enforce_landing(page)):
    failures.append('a document landed outside the policy must not be reported as readable')
if page.frames[0].url != 'about:blank':
    failures.append('a document landed outside the policy must be replaced by a blank one')
if page.frames[1].url != broker.origin + '/stockoverview':
    failures.append('a document inside the policy must be left in place')
if not (page._blackbox_blocked or {}).get('path', '').startswith('/js/'):
    failures.append('a document landed outside the policy must be reported as a blocked navigation')
page = Page(broker.origin + '/stockoverview')
if not asyncio.run(broker.enforce_landing(page)) or page.frames[0].url == 'about:blank':
    failures.append('a document inside the policy must stay readable')

calls = {}
for node in ast.walk(ast.parse(inspect.getsource(broker))):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        calls[node.name] = {x.func.id for x in ast.walk(node)
                            if isinstance(x, ast.Call) and isinstance(x.func, ast.Name)}
for name, needed in (('snapshot', 'enforce_landing'), ('dispatch', 'enforce_landing'),
                     ('remember_download', 'product_path')):
    if needed not in calls.get(name, ()):
        failures.append(f'{name} no longer applies the policy to the landed document ({needed})')
if failures:
    sys.exit('landed-document policy check failed:\n' + '\n'.join(failures))
print('landed-document policy check passed: redirected navigations, pixels and downloads stay inside the policy')
PY
# Confirm initialization under the final read-only installation permissions.
startup_check=$(mktemp -d "$TMPDIR/startup-$task.XXXXXXXX")
chmod 777 "$startup_check"
docker run --rm -i --network none --user 0 --env PYTHONDONTWRITEBYTECODE=1 \
  --env TMPDIR=/check --mount "type=bind,src=$startup_check,dst=/check" \
  --entrypoint python3 "$(image reference)" -B - < "$task_root/environment/check-start.py"
rmdir "$startup_check"
python3 "$task_root/environment/verify-images.py" "$task_root" \
  "$(image verifier)" "$(image reference)" "$(image agent)"
