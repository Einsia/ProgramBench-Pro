#!/usr/bin/env bash
# Install Newsboat 2.45, its shared libraries and the separate process sandbox.
# SOURCE.json and NOTICE describe the pinned build inputs and packaging.
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
archive=newsboat-runtime-2.45.tar.gz
expected=b72a9045b2cb1f8fd107b5acbc96a2fbba5de6250ac18bc17555d3f3be46fcec

actual="$(sha256sum "$package/$archive" | awk '{print $1}')"
if [ "$actual" != "$expected" ]; then
  echo "Newsboat archive checksum mismatch: $actual" >&2
  exit 1
fi
if [ -e "$dest/newsboat" ]; then
  echo "refusing to overwrite an existing implementation: $dest/newsboat" >&2
  exit 1
fi
mkdir -p "$dest/newsboat"
install -m 0755 "$package/start.sh" "$dest/start.sh"
install -m 0644 "$package/SOURCE.json" "$dest/SOURCE.json"
install -m 0644 "$package/LICENSE" "$dest/LICENSE"
install -m 0644 "$package/NOTICE" "$dest/NOTICE"
mkdir -p "$dest/LICENSES"
install -m 0444 "$package"/LICENSES/*.txt "$dest/LICENSES/"
install -m 0444 "$package/pbsandbox.c" "$dest/pbsandbox.c"
tar -xzf "$package/$archive" -C "$dest/newsboat" --no-same-owner
chmod -R u=rwX,go=rX "$dest/newsboat"
echo "Installed Newsboat 2.45 ($actual)"
