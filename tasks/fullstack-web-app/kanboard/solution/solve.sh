#!/bin/bash
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/router.php" "$pbp_package/php.ini" "$pbp_package/seed.php" "$pbp_package/start.sh" \
  "$pbp_package/SOURCE.json" "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
cp -R "$pbp_package/LICENSES" /app/solution/
# The unmodified Kanboard 1.2.56 release archive and the PHP 8.5.12 runtime it runs on.
rm -rf /app/solution/kanboard /app/solution/php
mkdir -p /app/solution/kanboard
tar -xzf "$pbp_package/kanboard-1.2.56.tar.gz" -C /app/solution/kanboard --strip-components=1 --no-same-owner
tar -xzf "$pbp_package/php-runtime-8.5.12.tar.gz" -C /app/solution --strip-components=1 --no-same-owner opt/php
chmod 755 /app/solution/start.sh /app/solution/php/bin/php
chmod -R u=rwX,go=rX /app/solution/kanboard /app/solution/php
