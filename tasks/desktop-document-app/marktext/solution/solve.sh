#!/usr/bin/env bash
# Install the reference application into /app/solution: the launcher (start.sh) and its
# Landlock sandbox wrapper (jail.py), plus the unmodified upstream MarkText 0.23.0
# Linux release, extracted next to them.
set -Eeuo pipefail

solution_package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/solution
cp "$solution_package/start.sh" /app/solution/start.sh
cp "$solution_package/jail.py" /app/solution/jail.py
cp "$solution_package/marktext-linux-0.23.0.tar.gz" /app/solution/marktext.tar.gz
echo 'ed377fe3a2c255212667a083a3e5e645633a5fd760ad7554c3f56785541b9214  /app/solution/marktext.tar.gz' | sha256sum -c -
if [ -e /app/solution/marktext-app ]; then
  echo 'Refusing to overwrite an existing application.' >&2
  exit 1
fi
mkdir -p /app/solution/marktext-app
tar -xzf /app/solution/marktext.tar.gz -C /app/solution/marktext-app --strip-components=1
rm /app/solution/marktext.tar.gz
# The bundled Chromium sandbox helper is unused (we start with --no-sandbox) and
# its set-user-ID bit is dropped so the launcher needs no elevated privileges.
chmod u-s /app/solution/marktext-app/chrome-sandbox 2>/dev/null || true
chmod 755 /app/solution/start.sh
chmod 644 /app/solution/jail.py
