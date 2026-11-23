#!/usr/bin/env bash
set -euo pipefail
cmus_solution=$(cd -- "$(dirname -- "$0")" && pwd)
exec python3 -I "$cmus_solution/launch.py" "$@"
