#!/usr/bin/env bash
set -euo pipefail
cmus_package=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cmus_dest=${SOLUTION_DIR:-/app/solution}
mkdir -p "$cmus_dest"
cmus_build=$(mktemp -d "${TMPDIR:-/tmp}/cmus-build.XXXXXX")
trap 'python3 -B -c "import shutil,sys; shutil.rmtree(sys.argv[1])" "$cmus_build"' EXIT
printf '%s  %s\n' 7be478c476f0a9915cdefbf6aade825a40cd202a8ca6b5149399025d3c7fc09b "$cmus_package/cmus-2.13.0.tar.gz" | sha256sum -c -
tar -xzf "$cmus_package/cmus-2.13.0.tar.gz" -C "$cmus_build" --strip-components=1
cd "$cmus_build"
./configure prefix="$cmus_dest/cmus" CONFIG_CDIO=n CONFIG_CDDB=n CONFIG_DISCID=n CONFIG_MPRIS=n CONFIG_JACK=n CONFIG_OSS=n CONFIG_SNDIO=n CONFIG_PULSE=y CONFIG_AO=y
make -j8
make install
cc -shared -fPIC -O2 "$cmus_package/denyexec.c" -o "$cmus_dest/denyexec.so" -ldl -pthread
install -m 0555 "$cmus_package/start.sh" "$cmus_dest/start.sh"
for cmus_file in launch.py SOURCE.json LICENSE NOTICE cmus-2.13.0.tar.gz; do install -m 0444 "$cmus_package/$cmus_file" "$cmus_dest/$cmus_file"; done
