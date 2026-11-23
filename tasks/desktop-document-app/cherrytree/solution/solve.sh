#!/usr/bin/env bash
# Install the reference application: the CherryTree 1.7.2 release package unpacked under /app/solution/cherrytree.
set -Eeuo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
deb=cherrytree_1.7.2-2.Debian13_amd64.deb
mkdir -p "$destination"
if [ -e "$destination/cherrytree" ]; then
  echo 'Refusing to overwrite an existing implementation.' >&2
  exit 1
fi
echo "116fc2d99dfb4395fcaafdbc982f83ef82750d68aee324b366c036601d5051fb  $package_dir/$deb" | sha256sum -c -
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0644 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 0644 "$package_dir/NOTICE" "$destination/NOTICE"
dpkg-deb -x "$package_dir/$deb" "$destination/cherrytree"
echo "Installed CherryTree 1.7.2 release package"
