#!/bin/bash
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/gitea" "$pbp_package/seed.py" "$pbp_package/start.sh" "$pbp_package/SOURCE.json" "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
chmod 755 /app/solution/start.sh /app/solution/gitea
