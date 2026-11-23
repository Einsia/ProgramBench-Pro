#!/bin/bash
set -euo pipefail
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -p /app/solution
cp -a "$pbp_package/LICENSE" "$pbp_package/LICENSES" "$pbp_package/NOTICE" \
  "$pbp_package/SOURCE.json" "$pbp_package/jsoneditor-10.4.3.tgz" "$pbp_package/vendor" \
  "$pbp_package/server.py" "$pbp_package/start.sh" "$pbp_package/solve.sh" /app/solution/
chmod 755 /app/solution/start.sh
