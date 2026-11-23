#!/bin/bash
set -euo pipefail
package_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"
echo "fec5d7ed2f4c075d4e1d361a1235431f8b55663e99ed2edadd8f7e71ece662d4  $package_dir/gnumeric-runtime-1.12.62.tar.xz" | sha256sum -c -
if [ -e "$destination/upstream" ]; then
  echo 'Refusing to overwrite an existing application.' >&2
  exit 1
fi
for file in start.sh ssconvert ssindex ssgrep ssdiff; do
  install -m 755 "$package_dir/$file" "$destination/$file"
done
install -m 644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 644 "$package_dir/launch.py" "$destination/launch.py"
tar -xf "$package_dir/gnumeric-runtime-1.12.62.tar.xz" -C "$destination"

install -m 644 "$package_dir/confinement.py" "$destination/confinement.py"
