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
# Check the product-specific library boundary.
python3 - "$(image agent)" <<'PY_CHECK'
import subprocess, sys
agent = sys.argv[1]
probe = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'sh', agent, '-c',
                        'ldconfig -p | grep -c -E "libQt5Core|libQt5Widgets|libhydrogen-core" || true'],
                       capture_output=True, text=True)
if probe.stdout.strip() not in ('', '0'):
    raise SystemExit(f'{agent} carries the standard runtime libraries')
PY_CHECK

python3 "$task_root/environment/verify-images.py" "$task_root" \
  "$(image verifier)" "$(image reference)" "$(image agent)"
