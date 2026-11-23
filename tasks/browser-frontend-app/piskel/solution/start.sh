#!/bin/bash
# Serve the unmodified Piskel 0.15.0 editor offline on HOST:PORT (entry page /).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 "$PWD/server.py"
