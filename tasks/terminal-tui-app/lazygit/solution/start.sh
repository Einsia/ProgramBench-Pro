#!/usr/bin/env bash
# Standard-answer entry point. Runs the upstream lazygit product in the foreground, in the pseudo-terminal the
# black-box runtime provides, against the instance's workspace (a git repository). All persistent state lives
# under DATA_DIR.
set -Eeuo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/workspace"

export HOME="${HOME:-$data/home}"
mkdir -p "$HOME"
export TERM="${TERM:-xterm-256color}"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export TZ="${TZ:-UTC}"

cd "$data/workspace"
exec python3 -I -B "$solution_dir/launch.py"
