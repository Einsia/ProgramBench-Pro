#!/usr/bin/env bash
# Application entry point. Runs the upstream micro binary in the foreground, in the pseudo-terminal the
# black-box runtime provides, in the working directory, with the editor's command-line arguments ("$@"), under the
# launcher's confinement. All persistent state lives under DATA_DIR.
set -Eeuo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"

# A clean environment: nothing the caller exported reaches the launcher's interpreter.
environment=(
  PATH=/usr/bin:/bin
  "DATA_DIR=$data"
  "TMPDIR=${TMPDIR:-$data/tmp}"
  "TERM=${TERM:-xterm-256color}"
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  TZ=UTC
  "COLUMNS=${COLUMNS:-120}"
  "LINES=${LINES:-36}"
  "USER=${USER:-agent}"
  "LOGNAME=${LOGNAME:-agent}"
  PYTHONDONTWRITEBYTECODE=1
)
exec /usr/bin/env -i "${environment[@]}" /usr/bin/python3 -B -I "$solution_dir/launch.py" "$@"
