#!/usr/bin/env bash
# Application entry point. Runs the upstream VisiData product in the foreground, in the pseudo-terminal the black-box runtime provides, against the instance's workspace. All persistent state lives under DATA_DIR.
set -Eeuo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/workspace"
home="${HOME:-$data/home}"
mkdir -p "$home"

# A clean environment: nothing the caller exported can reach the interpreter (PYTHON* variables, search paths),
# and the hash seed is fixed so that output is repeatable.
environment=(
  PATH=/usr/bin:/bin
  "HOME=$home"
  "TERM=${TERM:-xterm-256color}"
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  TZ=UTC
  "COLUMNS=${COLUMNS:-120}"
  "LINES=${LINES:-36}"
  "DATA_DIR=$data"
  "TMPDIR=${TMPDIR:-/tmp}"
  PYTHONHASHSEED=0
  PYTHONDONTWRITEBYTECODE=1
  PYTHONNOUSERSITE=1
  PYTHONUNBUFFERED=1
)
cd "$data/workspace"
exec /usr/bin/env -i "${environment[@]}" /usr/bin/python3 -P -s "$solution_dir/launch.py"
