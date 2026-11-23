#!/usr/bin/env bash
set -euo pipefail
solution_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec python3 -B -I "$solution_dir/launch.py"
