#!/bin/bash
# Mealie 3.29.0 installation: the official image's Python runtime, application and data, unpacked by solve.sh.
# Configuration is Mealie's own environment settings; the product starts with its default initial state.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${DATA_DIR:?DATA_DIR must name the persistent application directory}"
root=$PWD/mealie
export LD_LIBRARY_PATH="$root/lib:$root/python/lib" NLTK_DATA="$root/nltk_data"
export PRODUCTION=true TESTING=false API_HOST="${HOST:-0.0.0.0}" API_PORT="${PORT:-3000}" TZ=UTC
exec "$root/python/bin/python3.14" -I -B -m mealie.main
