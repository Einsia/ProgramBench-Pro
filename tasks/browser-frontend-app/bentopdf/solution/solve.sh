#!/bin/bash
set -euo pipefail
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p /app/solution
cat "$pbp_package"/bentopdf-2.8.10-offline.zip.chunk* > /app/solution/bentopdf-2.8.10-offline.zip
cp "$pbp_package/bentopdf-2.8.10-source.tar.gz" \
   "$pbp_package/bentopdf-viewer-source-051abe5b72a9.tar.gz" \
   "$pbp_package/server.py" "$pbp_package/start.sh" \
   "$pbp_package/SOURCE.json" "$pbp_package/NOTICE" "$pbp_package/LICENSE" /app/solution/
cp -r "$pbp_package/LICENSES" /app/solution/
chmod 755 /app/solution/start.sh
