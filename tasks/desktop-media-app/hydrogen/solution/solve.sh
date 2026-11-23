#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"

# Install the pinned upstream runtime and its launch configuration.
archive="$package_dir/Hydrogen-1.2.7-x86_64.AppImage"
expected="4fa9e8e2f506f8380fc0b511a36c4ae72cbe0dc8b0ecd0fc0f7518443750b1bf"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "reference Hydrogen AppImage checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/isolation.py" "$destination/isolation.py"
install -m 0644 "$package_dir/SOURCE.json" "$package_dir/NOTICE" "$package_dir/LICENSE" "$destination/"
install -d -m 0755 "$destination/LICENSES"
cp -a "$package_dir/LICENSES/." "$destination/LICENSES/"

work="$(mktemp -d -p "$destination" .extract-XXXXXX)"
trap 'rm -rf "$work"' EXIT
cp "$archive" "$work/hydrogen.AppImage"
chmod 755 "$work/hydrogen.AppImage"
(cd "$work" && ./hydrogen.AppImage --appimage-extract >/dev/null)
mv "$work/squashfs-root" "$destination/runtime"
rm -f "$work/hydrogen.AppImage"
chmod -R u=rwX,go=rX "$destination/runtime"
chmod 755 "$destination/runtime/usr/bin/hydrogen" "$destination/runtime/usr/bin/h2cli" "$destination/runtime/usr/bin/h2player"
printf 'Installed Hydrogen 1.2.7 reference package (%s)\n' "$actual"
