#!/usr/bin/env bash
# Install the standard answer: the unmodified calcurse 4.8.2 program, built from the pinned upstream release (see
# SOURCE.json and NOTICE), and the process sandbox pbsandbox.so (built from pbsandbox.c). Run as root in the
# reference image build and by Harbor's oracle; it only populates /app/solution.
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
archive=calcurse-runtime-4.8.2.tar.gz
expected=336f8b092d7a58165a2179f5db8328d9a7bb387d508cfc08f283ba4d8acb62f0

actual="$(sha256sum "$package/$archive" | awk '{print $1}')"
if [ "$actual" != "$expected" ]; then
  echo "standard calcurse archive checksum mismatch: $actual" >&2
  exit 1
fi
if [ -e "$dest/calcurse" ]; then
  echo "refusing to overwrite an existing implementation: $dest/calcurse" >&2
  exit 1
fi
mkdir -p "$dest/calcurse"
install -m 0755 "$package/start.sh" "$dest/start.sh"
install -m 0644 "$package/SOURCE.json" "$dest/SOURCE.json"
install -m 0644 "$package/LICENSE" "$dest/LICENSE"
install -m 0644 "$package/NOTICE" "$dest/NOTICE"
cp -R "$package/LICENSES" "$dest/LICENSES"
tar -xzf "$package/$archive" -C "$dest/calcurse" --no-same-owner
chmod -R u=rwX,go=rX "$dest/calcurse"
echo "Installed calcurse 4.8.2 ($actual)"
