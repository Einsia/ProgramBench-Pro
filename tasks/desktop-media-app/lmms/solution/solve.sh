#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"

# Install the pinned upstream runtime and its launch configuration.
archive="$package_dir/lmms-1.2.2-linux-x86_64.AppImage"
expected="6cdc45a0699b8cd85295c49bcac03fcce6f3d8ffd7da23d646d0cb4258869b76"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "reference LMMS AppImage checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/isolation.py" "$destination/isolation.py"
install -m 0644 "$package_dir/lmms_cpus.so" "$destination/lmms_cpus.so"
install -m 0644 "$package_dir/lmms_cpus.c" "$destination/lmms_cpus.c"
install -m 0644 "$package_dir/SOURCE.json" "$package_dir/NOTICE" "$package_dir/LICENSE" "$destination/"
install -d -m 0755 "$destination/LICENSES"
cp -a "$package_dir/LICENSES/." "$destination/LICENSES/"

work="$(mktemp -d -p "$destination" .extract-XXXXXX)"
trap 'rm -rf "$work"' EXIT
cp "$archive" "$work/lmms.AppImage"
chmod 755 "$work/lmms.AppImage"
(cd "$work" && ./lmms.AppImage --appimage-extract >/dev/null)
mv "$work/squashfs-root" "$destination/runtime"
rm -f "$work/lmms.AppImage"
# These optional hosts load arbitrary external libraries; internal synthesizers and effects remain installed.
rm -f "$destination/runtime/usr/lib/lmms/libvestige.so" \
      "$destination/runtime/usr/lib/lmms/libcarlabase.so" \
      "$destination/runtime/usr/lib/lmms/libcarlarack.so" \
      "$destination/runtime/usr/lib/lmms/libcarlapatchbay.so" \
      "$destination/runtime/usr/lib/lmms/libladspaeffect.so"
chmod -R u=rwX,go=rX "$destination/runtime"
chmod 755 "$destination/runtime/usr/bin/lmms.real"
printf 'Installed LMMS 1.2.2 reference package (%s)\n' "$actual"
