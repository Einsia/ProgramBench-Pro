#!/usr/bin/env bash
# Install the pinned upstream static binary and the separate launcher.
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$dest"

archive_name=micro-2.0.15-linux64-static.tar.gz
expected=267d238eac1e26ed053d13d4d48bd421b87f9eb538b604f0b2f74a85598b6cc2
binary_sha=2027f2e4698fa4e826523ad16b95c724bf808de479f10ec769cdd200437701b3
actual="$(sha256sum "$package/$archive_name" | awk '{print $1}')"
if [ "$actual" != "$expected" ]; then
  echo "micro archive checksum mismatch: $actual" >&2
  exit 1
fi
if [ -e "$dest/micro" ]; then
  echo "refusing to overwrite an existing implementation: $dest/micro" >&2
  exit 1
fi

install -m 0555 "$package/start.sh" "$dest/start.sh"
for name in launch.py SOURCE.json NOTICE LICENSE; do
  install -m 0444 "$package/$name" "$dest/$name"
done
# The archive is micro-2.0.15/{micro,LICENSE,...}; install only the binary, unmodified.
mkdir -p "$dest/LICENSES"
install -m 0444 "$package"/LICENSES/*.txt "$dest/LICENSES/"
tar -xzf "$package/$archive_name" -O micro-2.0.15/micro > "$dest/micro"
chmod 0555 "$dest/micro"
if [ "$(sha256sum "$dest/micro" | awk '{print $1}')" != "$binary_sha" ]; then
  echo "extracted micro binary checksum mismatch" >&2
  exit 1
fi
echo "Installed upstream micro 2.0.15 ($actual)"
