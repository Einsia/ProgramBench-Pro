#!/usr/bin/env bash
set -Eeuo pipefail
# The pinned Zotero release, configured and started by launch.py (all state under DATA_DIR).
solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 -I -B "$solution_dir/launch.py"
