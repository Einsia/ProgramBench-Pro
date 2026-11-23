#!/usr/bin/env bash
# Install VisiData 3.4 and its pure-Python dependencies from pinned wheels,
# with the separate in-process launcher and expression guard.
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$dest"

for name in start.sh launch.py guard.py SOURCE.json LICENSE NOTICE; do
  install -m 0444 "$package/$name" "$dest/$name"
done
chmod 0555 "$dest/start.sh"
mkdir -p "$dest/LICENSES"
install -m 0444 "$package"/LICENSES/*.txt "$dest/LICENSES/"

verify() {
  local file="$1" expected="$2" actual
  actual="$(sha256sum "$package/$file" | awk '{print $1}')"
  if [ "$actual" != "$expected" ]; then
    echo "checksum mismatch for $file: $actual" >&2
    exit 1
  fi
}
verify visidata-3.4-py3-none-any.whl 9b88473c7bfb5a1752bea5870cc6edd3474cf529ac16c0e465d3ec0014ea99fb
verify python_dateutil-3.0.0-py2.py3-none-any.whl 3c79630202e4152c6add678446984236efe4f57e84d8e892aab0637bab82e9fd
verify six-1.17.0-py2.py3-none-any.whl 4721f391ed90541fddacab5acf947aa0d3dc7d27b2e1e8eda2be8970586c3274
install -m 0444 "$package/visidata-3.4-py3-none-any.whl" "$dest/visidata-3.4-py3-none-any.whl"

if [ -e "$dest/vdpkg" ]; then
  echo "refusing to overwrite an existing implementation: $dest/vdpkg" >&2
  exit 1
fi
mkdir -p "$dest/vdpkg"

# The wheels carry the packages unmodified. They are byte-compiled in place (legacy layout) from the pinned sources,
# then the sources are removed; every non-source resource (guides, man page, ddw files, sample data) is kept.
/usr/bin/python3 -B -I -W ignore - "$dest" "$package" <<'PY'
import compileall
import sys
import zipfile
from pathlib import Path

dest = Path(sys.argv[1])
package_root = Path(sys.argv[2])
target = dest / 'vdpkg'
wheels = {'visidata-3.4-py3-none-any.whl': ('visidata/',),
          'python_dateutil-3.0.0-py2.py3-none-any.whl': ('dateutil/',),
          'six-1.17.0-py2.py3-none-any.whl': ('six.py',)}
for wheel, prefixes in wheels.items():
    with zipfile.ZipFile(package_root / wheel) as archive:
        members = [n for n in archive.namelist()
                   if n.startswith(prefixes) and '..' not in n.split('/') and not n.endswith('/')]
        if not members:
            sys.exit('no package files found in ' + wheel)
        for name in members:
            archive.extract(name, target)
for package in ('visidata', 'dateutil'):
    if not compileall.compile_dir(str(target / package), quiet=1, legacy=True, optimize=0):
        sys.exit('byte-compilation failed for ' + package)
if not compileall.compile_file(str(target / 'six.py'), quiet=1, legacy=True, optimize=0):
    sys.exit('byte-compilation failed for six')
for path in sorted(target.rglob('*.py')):
    path.unlink()
PY
find "$dest/vdpkg" -type d -exec chmod 0711 {} +
chmod 0755 "$dest/vdpkg/visidata/loaders" "$dest/vdpkg/visidata/features" "$dest/vdpkg/visidata/themes"
find "$dest/vdpkg" -type f -exec chmod 0444 {} +
echo "Installed upstream VisiData 3.4 with python-dateutil 3.0.0 and six 1.17.0, byte-compiled"
