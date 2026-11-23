#!/bin/bash
# Serve the unmodified SVG-edit 7.4.2 editor offline on HOST:PORT (entry page /).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 "$PWD/server.py"
