#!/bin/bash
# Install the Piskel production assets and static server.
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/piskel-0.15.0-prod.tar.gz" "$pbp_package/server.py" "$pbp_package/start.sh" \
  "$pbp_package/SOURCE.json" "$pbp_package/NOTICE" "$pbp_package/LICENSE" /app/solution/
rm -rf /app/solution/LICENSES
cp -r "$pbp_package/LICENSES" /app/solution/LICENSES
chmod 755 /app/solution/start.sh
