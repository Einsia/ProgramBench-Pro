#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
image="MuseScore-Studio-4.7.6.261022093-x86_64.AppImage"
expected="5fcbd1f292270eca5c3867d56b767c31a173a155216a415f5caee22553f8e7a6"

actual="$(sha256sum "$package_dir/$image" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "MuseScore Studio AppImage checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
mkdir -p "$destination"
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/musescore_start.py" "$destination/musescore_start.py"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 0644 "$package_dir/process_guard.c" "$destination/process_guard.c"
cc -O2 -Wall -Wextra -Werror -shared -fPIC "$package_dir/process_guard.c" -o "$destination/process_guard.so" -ldl
install -m 0644 "$package_dir/LICENSE" "$destination/LICENSE"
install -m 0644 "$package_dir/NOTICE" "$destination/NOTICE"
mkdir -p "$destination/LICENSES"
install -m 0644 "$package_dir"/LICENSES/*.txt "$destination/LICENSES/"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
cp "$package_dir/$image" "$work/musescore.AppImage"
chmod 0755 "$work/musescore.AppImage"
# --appimage-extract needs no FUSE: it unpacks the embedded squashfs into ./squashfs-root.
(cd "$work" && ./musescore.AppImage --appimage-extract > /dev/null)
mv "$work/squashfs-root" "$destination/runtime"

# The bundled example plug-ins, extensions and test scripts are not installed: the product starts with empty
# directories there (its Plugins page then lists nothing). The executable and its libraries are unmodified.
share="$destination/runtime/share/mscore4portable-4.7"
for name in plugins extensions autobotscripts; do
  rm -rf "$share/$name"
  mkdir "$share/$name"
done
chmod -R u+rwX,go+rX,go-w "$destination/runtime"
chmod 0755 "$destination/start.sh" "$destination/musescore_start.py" "$destination/runtime/AppRun" "$destination/runtime/bin/mscore4portable"
printf 'Installed MuseScore Studio 4.7.6 package (%s)\n' "$actual"
