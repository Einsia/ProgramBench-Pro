#!/bin/bash
# Serve the unmodified IT-Tools release offline on HOST:PORT (entry page /).
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 "$PWD/server.py"
