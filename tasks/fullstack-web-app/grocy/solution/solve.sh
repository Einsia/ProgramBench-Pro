#!/bin/bash
set -euo pipefail
mkdir -p /app/solution
pbp_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cp "$pbp_package/router.php" "$pbp_package/seed.py" "$pbp_package/start.sh" "$pbp_package/SOURCE.json" \
  "$pbp_package/LICENSE" "$pbp_package/NOTICE" /app/solution/
cp -R "$pbp_package/LICENSES" /app/solution/
# The unmodified Grocy 4.7.1 release archive and the PHP 8.5.12 command-line runtime it needs.
rm -rf /app/solution/grocy /app/solution/php
python3 -I -B -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' \
  "$pbp_package/grocy_4.7.1.zip" /app/solution/grocy
tar -xzf "$pbp_package/php-runtime-8.5.12.tar.gz" -C /app/solution --strip-components=1 opt/php
chmod 755 /app/solution/start.sh /app/solution/php/bin/php
chmod -R u=rwX,go=rX /app/solution/grocy /app/solution/php
