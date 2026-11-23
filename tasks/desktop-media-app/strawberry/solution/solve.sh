#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"

package="strawberry_1.2.31-noble_amd64.deb"
expected="68a6840d0ee60b22712f9535d07a6ca06780a1433e2f4256f76541b07dce24b0"
actual="$(sha256sum "$package_dir/$package" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "Strawberry package checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/strawberry_start.py" "$destination/strawberry_start.py"
install -m 0644 "$package_dir/schema.sql" "$destination/schema.sql"
install -m 0644 "$package_dir/SOURCE.json" "$destination/SOURCE.json"
install -m 0644 "$package_dir/process_guard.c" "$destination/process_guard.c"
cc -O2 -Wall -Wextra -Werror -shared -fPIC "$package_dir/process_guard.c" -o "$destination/process_guard.so" -ldl
install -m 0644 "$package_dir/NOTICE" "$destination/NOTICE"
mkdir -p "$destination/LICENSES"
install -m 0644 "$package_dir"/LICENSES/*.txt "$destination/LICENSES/"
install -m 0644 "$package_dir/LICENSE" "$destination/LICENSE"
install -m 0644 "$package_dir/strawberry-1.2.31.tar.xz" "$destination/strawberry-1.2.31.tar.xz"
mkdir -p "$destination/runtime"
dpkg-deb -x "$package_dir/$package" "$destination/runtime"
binary="$(sha256sum "$destination/runtime/usr/bin/strawberry" | awk '{print $1}')"
if [[ "$binary" != "c00fea00953bebb9421989b97272690ca548d6f8b1f5dc8b8592db420e381c68" ]]; then
  echo "unpacked Strawberry binary checksum mismatch: $binary" >&2
  exit 1
fi
printf 'Installed Strawberry 1.2.31 package (%s)\n' "$actual"
