#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
package="Joplin-3.7.21.deb"
expected="14de2d5524e45341de5f0b68a1e78191b796a6c9817949c49b80afe5cd6ab965"

# Verify the official release archive before unpacking it into the installation.
actual="$(sha256sum "$package_dir/$package" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "Joplin package checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing release runtime: $destination/runtime" >&2
  exit 1
fi
mkdir -p "$destination"
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# dpkg-deb -x only unpacks the data archive: the maintainer scripts (a /usr/bin link, sandbox helper permissions,
# MIME, desktop and AppArmor registration) are not run and are not needed by the product.
dpkg-deb -x "$package_dir/$package" "$work/root"
mv "$work/root" "$destination/runtime"

# The two bundled default plug-ins are not installed: the product finds no default plug-in directory and starts
# with no plug-in at all. The executable, its resources and libraries are unmodified.
rm -rf "$destination/runtime/opt/Joplin/resources/build/defaultPlugins"
chmod -R u+rwX,go+rX,go-w "$destination/runtime"
chmod 0755 "$destination/start.sh" "$destination/launch.py" "$destination/runtime/opt/Joplin/joplin"
printf 'Installed Joplin 3.7.21 release package (%s)\n' "$actual"

install -m 644 "$package_dir/confinement.py" "$destination/confinement.py"
install -m 644 "$package_dir/product.py" "$destination/product.py"
