#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
destination="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$destination"

# Install the pinned product runtime and launcher.
install -m 0755 "$package_dir/start.sh" "$destination/start.sh"
install -m 0755 "$package_dir/launch.py" "$destination/launch.py"
install -m 0644 "$package_dir/isolation.py" "$destination/isolation.py"
install -m 0644 "$package_dir/SOURCE.json" "$package_dir/LICENSE" "$package_dir/NOTICE" "$destination/"
install -d -m 0755 "$destination/LICENSES"
cp -a "$package_dir/LICENSES/." "$destination/LICENSES/"

archive="$package_dir/audacity-runtime-2.4.2.tar.gz"
expected="b9b3015706ade3f59046adeaeabf88297fc723935595ae571d2a00cfd4aadde6"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [[ "$actual" != "$expected" ]]; then
  echo "reference Audacity archive checksum mismatch: $actual" >&2
  exit 1
fi
if [[ -e "$destination/runtime" ]]; then
  echo "refusing to overwrite an existing runtime: $destination/runtime" >&2
  exit 1
fi
mkdir -p "$destination/runtime"
tar -xzf "$archive" -C "$destination/runtime"
# The stock module hardcodes /tmp/audacity_script_pipe.<to|from>.<uid>. The
# documented endpoint contract places the pipes in PBP_AUDIO_PIPE_DIR, which
# isolates simultaneous sessions of one user. Rewrite only the path template
# to a working-directory-relative name; launch.py starts the product
# in that directory. Both module digests are pinned.
python3 - "$destination/runtime/lib/audacity/modules/mod-script-pipe.so" <<'PATCH'
import hashlib, sys
path = sys.argv[1]
data = open(path, 'rb').read()
if hashlib.sha256(data).hexdigest() != '833148e999b25823fa9c710d7bc3bdb6f127a5079b597cabb267b9b1d94e1f82':
    raise SystemExit('unexpected stock mod-script-pipe module')
old, new = b'/tmp/audacity_script_pipe.%s.%d\0', b'audacity_script_pipe.%s.%d\0'
if data.count(old) != 1:
    raise SystemExit('stock pipe template not found exactly once')
data = data.replace(old, new.ljust(len(old), b'\0'))
open(path, 'wb').write(data)
PATCH
patched="$(sha256sum "$destination/runtime/lib/audacity/modules/mod-script-pipe.so" | awk '{print $1}')"
if [[ "$patched" != "628d1bb7bb2b62bf7bb88a61c809ffd9ca38f2dd4503d3c9eae9e27f7371cede" ]]; then
  echo "patched mod-script-pipe checksum mismatch: $patched" >&2
  exit 1
fi
chmod 755 "$destination/start.sh" "$destination/launch.py" "$destination/runtime/bin/audacity"
printf 'Installed Audacity 2.4.2 reference package (%s)\n' "$actual"
