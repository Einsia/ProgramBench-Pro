#!/bin/bash
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tar -xJf "$pbp_package/mealie-3.29.0-runtime.tar.xz" -C /app/solution --no-same-owner
cp "$pbp_package/start.sh" "$pbp_package/SOURCE.json" "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
cp -R "$pbp_package/LICENSES" /app/solution/
chmod 755 /app/solution/start.sh
