#!/usr/bin/env bash
set -euo pipefail
package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
dest=${SOLUTION_DIR:-/app/solution}
mkdir -p "$dest"
archive="$package/tig-2.6.1.tar.gz"
printf '%s  %s\n' 5adeabdcd93aa0423d618da8b878b53482bef6e0e9e1fe224acc0f18031fe91e "$archive" | sha256sum -c -
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/tig-build.XXXXXXXX")
trap 'rm -rf "$build_dir"' EXIT
tar -xzf "$archive" -C "$build_dir"
(
  cd "$build_dir/tig-2.6.1"
  ./configure --prefix=/usr/local CFLAGS='-O2 -g0'
  make -j4
)
install -m 0555 "$build_dir/tig-2.6.1/src/tig" "$dest/tig"
cc -shared -fPIC -O2 "$package/confine.c" -o "$dest/confine.so"
chmod 0444 "$dest/confine.so"
install -m 0555 "$package/start.sh" "$dest/start.sh"
install -m 0444 "$package/launch.py" "$package/SOURCE.json" "$package/LICENSE" "$package/NOTICE" "$dest/"
install -m 0444 "$package/confine.c" "$package/solve.sh" "$dest/"
install -m 0444 "$archive" "$dest/tig-2.6.1.tar.gz"
