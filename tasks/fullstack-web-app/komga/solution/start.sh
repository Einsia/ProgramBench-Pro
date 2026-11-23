#!/usr/bin/env bash
set -euo pipefail
export LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${DATA_DIR:?DATA_DIR is required}"
exec java -Xms128m -Xmx1536m -XX:ActiveProcessorCount=2 -Djava.awt.headless=true -Duser.timezone=UTC \
  -Djava.io.tmpdir="${TMPDIR:-/tmp}" -jar "$PWD/komga.jar" \
  --server.address="${HOST:-0.0.0.0}" --server.port="${PORT:-3000}" \
  --komga.config-dir="$DATA_DIR" --komga.libraries-scan-startup=false \
  --logging.level.root=WARN --logging.file.name="$DATA_DIR/logs/komga.log" \
  --logging.logback.rollingpolicy.total-size-cap=8MB --logging.logback.rollingpolicy.max-file-size=2MB \
  --logging.logback.rollingpolicy.max-history=2 \
  --management.endpoints.web.exposure.include=health,info \
  --spring.main.banner-mode=off --spring.jmx.enabled=false
