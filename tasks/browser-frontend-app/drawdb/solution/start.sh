#!/bin/bash
# Serve the unmodified drawDB 1.8.2 web application offline on HOST:PORT.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 "$PWD/server.py"
