#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${DATA_DIR:?DATA_DIR must name the persistent application directory}"
exec python3 "$PWD/seed.py" --root "$PWD" --data "$DATA_DIR" --host "${HOST:-0.0.0.0}" --port "${PORT:-3000}" --start
