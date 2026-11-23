#!/bin/bash
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/start.sh" "$pbp_package/SOURCE.json" "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
tar -xOzf "$pbp_package/navidrome_0.64.2_linux_amd64.tar.gz" navidrome > /app/solution/navidrome
chmod 755 /app/solution/start.sh /app/solution/navidrome
