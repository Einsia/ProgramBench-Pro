#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
image="Darktable-5.6.2-x86_64.AppImage"
expected="4b0d1c737a2a18c7d8afb81aa3daaf25930bbe541dda98e6354dabd5c2e4dc36"

# Install the pinned upstream runtime and its launch configuration.
actual="$(sha256sum "$package_dir/$image" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "reference darktable AppImage checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
mkdir -p "$destination"
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 0644 "$package_dir/NOTICE" "$package_dir/LICENSE" "$package_dir/darktable-5.6.2.tar.xz" "$destination/"

install -d -m 0755 "$destination/LICENSES"
cp -a "$package_dir/LICENSES/." "$destination/LICENSES/"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp "$package_dir/$image" "$work/darktable.AppImage"
chmod 0755 "$work/darktable.AppImage"
# --appimage-extract needs no FUSE: it unpacks the embedded squashfs into ./squashfs-root.
(cd "$work" && ./darktable.AppImage --appimage-extract > /dev/null)
mv "$work/squashfs-root" "$destination/runtime"

# Lua runs only from the product's start-up script share/darktable/luarc, whose single job is to load the bundled
# script manager (the "scripts" module, which installs, edits and runs Lua scripts). That script is replaced by an
# empty one, so the product starts with Lua but without scripts; the executables and libraries are unmodified.
share="$destination/runtime/usr/share/darktable"
printf -- '-- scripts are not available in this installation\n' > "$share/luarc"
rm -rf "$share/lua-scripts"
mkdir "$share/lua-scripts"
chmod -R u+rwX,go+rX,go-w "$destination/runtime"
chmod 0755 "$destination/start.sh" "$destination/launch.py" "$destination/runtime/usr/bin/darktable" \
  "$destination/runtime/usr/bin/darktable-cli"
printf 'Installed darktable 5.6.2 reference package (%s)\n' "$actual"
