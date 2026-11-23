#!/usr/bin/env bash
set -euo pipefail
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p /app/solution
cp "$pbp_package/komga.jar" "$pbp_package/start.sh" "$pbp_package/SOURCE.json" "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
chmod 755 /app/solution/start.sh
