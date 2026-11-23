#!/usr/bin/env bash
# Install the reference installation into /app/solution: the official Xournal++ 1.3.8
# Ubuntu 24.04 (noble) x86_64 package, unpacked unmodified except that the
# bundled Lua plug-ins are left out, plus the launcher (start.sh, sandbox.py).
set -Eeuo pipefail
package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
deb="$package/xournalpp-1.3.8-Ubuntu-noble-x86_64.deb"
echo "246f1767ac135f5cda8e4c0518f3a42e4122ae7710d5ae254709bdee32d42ff0  $deb" | sha256sum -c -
if [ -e "$destination/xournalpp" ]; then
  echo 'Refusing to overwrite an existing implementation.' >&2
  exit 1
fi
mkdir -p "$destination"
install -m 755 "$package/start.sh" "$package/sandbox.py" "$destination/"
install -m 644 "$package/SOURCE.json" "$package/NOTICE" "$package/LICENSE" "$package/LIBRARIES.json" "$destination/"
dpkg-deb -x "$deb" "$destination/xournalpp"
echo "81da2382e6d5a0543903150204accd173033071b78f046f00d2afa9eb2d93b37  $package/runtime-libraries.tar.gz" | sha256sum -c -
tar -xzf "$package/runtime-libraries.tar.gz" -C "$destination/xournalpp"
# Lua plug-ins run code; the bundled ones (all disabled by default) are not installed.
rm -rf "$destination/xournalpp/usr/share/xournalpp/plugins"

mkdir -p "$destination"/LICENSES
cp "$package"/LICENSES/*.txt "$destination"/LICENSES/

install -m 644 "$package/exec_guard.c" "$destination/exec_guard.c"
gcc -O2 -shared -fPIC -s -o "$destination/exec_guard.so" "$package/exec_guard.c"
