#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${DATA_DIR:?DATA_DIR must name the persistent application directory}"
# Kanboard reads DATA_DIR and its other settings from the environment, as in the official Docker image (URL rewriting on).
export LD_LIBRARY_PATH="$PWD/php/lib" ENABLE_URL_REWRITE=true
php=("$PWD/php/bin/php" -c "$PWD/php.ini")
[ -f "$DATA_DIR/baseline.ready" ] || "${php[@]}" "$PWD/seed.php"
export PHP_CLI_SERVER_WORKERS=4
exec "${php[@]}" -S "${HOST:-0.0.0.0}:${PORT:-3000}" -t "$PWD/kanboard" "$PWD/router.php"
