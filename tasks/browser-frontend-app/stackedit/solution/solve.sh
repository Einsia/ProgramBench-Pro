#!/bin/bash
set -euo pipefail
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p /app/solution
cp "$pbp_package/docker-build-layer.tar.gz" "$pbp_package/server.py" "$pbp_package/start.sh" \
   "$pbp_package/SOURCE.json" "$pbp_package/NOTICE" "$pbp_package/LICENSE" /app/solution/
cp -r "$pbp_package/LICENSES" /app/solution/
chmod 755 /app/solution/start.sh
