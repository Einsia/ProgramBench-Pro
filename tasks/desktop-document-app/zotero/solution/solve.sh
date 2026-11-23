#!/usr/bin/env bash
# Install the reference installation: the unmodified Zotero 10.0.6 Linux x86_64 release and its launcher.
set -Eeuo pipefail

solution_package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
archive=Zotero-10.0.6_linux-x86_64.tar.xz
echo "246c2574a9ac526abeaf3027ffd22fc45536a5ab25f227bb1df932fca9cedd63  $solution_package/$archive" | sha256sum -c -
mkdir -p /app/solution
if [ -e /app/solution/zotero ]; then
  echo 'Refusing to overwrite an existing implementation.' >&2
  exit 1
fi
work="$(mktemp -d)"
tar -xJf "$solution_package/$archive" -C "$work"
mv "$work/Zotero_linux-x86_64" /app/solution/zotero
rmdir "$work"
install -m 755 "$solution_package/start.sh" /app/solution/start.sh
install -m 644 "$solution_package/launch.py" /app/solution/launch.py
install -m 644 "$solution_package/SOURCE.json" "$solution_package/NOTICE" "$solution_package/LICENSE" /app/solution/

mkdir -p /app/solution/LICENSES
cp "$solution_package"/LICENSES/*.txt /app/solution/LICENSES/

mkdir -p /app/solution/zotero/defaults/pref
install -m 644 "$solution_package/reference.cfg" /app/solution/zotero/reference.cfg
install -m 644 "$solution_package/reference-prefs.js" /app/solution/zotero/defaults/pref/reference.js
