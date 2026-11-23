#!/bin/bash
# Install the drawDB 1.8.2 reference build and static server.
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/drawdb-1.8.2-dist.tar.gz" "$pbp_package/drawdb-1.8.2-source.tar.gz" "$pbp_package/server.py" \
  "$pbp_package/start.sh" "$pbp_package/SOURCE.json" "$pbp_package/NOTICE" "$pbp_package/LICENSE" /app/solution/
rm -rf /app/solution/LICENSES
cp -r "$pbp_package/LICENSES" /app/solution/LICENSES
chmod 755 /app/solution/start.sh
