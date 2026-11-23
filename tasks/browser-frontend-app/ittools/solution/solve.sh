#!/bin/bash
# Install the IT-Tools reference release, corresponding source and static server.
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/it-tools-2024.10.22-7ca5933.zip" "$pbp_package/it-tools-v2024.10.22-7ca5933-source.tar.gz" \
  "$pbp_package/server.py" "$pbp_package/start.sh" \
  "$pbp_package/SOURCE.json" "$pbp_package/NOTICE" "$pbp_package/LICENSE" /app/solution/
chmod 755 /app/solution/start.sh
