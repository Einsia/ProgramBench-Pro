#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"

install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/picard-cli" "$destination/picard-cli"
install -m 0755 "$package_dir/picard_start.py" "$destination/picard_start.py"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 0644 "$package_dir/process_guard.c" "$destination/process_guard.c"
cc -O2 -Wall -Wextra -Werror -shared -fPIC "$package_dir/process_guard.c" -o "$destination/process_guard.so" -ldl
install -m 0644 "$package_dir/LICENSE" "$destination/LICENSE"
install -m 0644 "$package_dir/NOTICE" "$destination/NOTICE"

archive="$package_dir/picard-3.0.3.tar.gz"
expected="e97f5049495e41b55c0da99ea8506d3d5345936bf348aca1ce34d66ad3b52c03"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "Picard archive checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/picard-3.0.3" ]]; then
  echo "refusing to overwrite an existing source tree: $destination/picard-3.0.3" >&2
  exit 1
fi
# The upstream source distribution runs as it is: the launcher puts its
# top-level directory on the module path (no build step, no modified file).
tar -xzf "$archive" -C "$destination" --no-same-owner
chmod -R u=rwX,go=rX "$destination/picard-3.0.3"
printf 'Installed MusicBrainz Picard 3.0.3 package (%s)\n' "$actual"
