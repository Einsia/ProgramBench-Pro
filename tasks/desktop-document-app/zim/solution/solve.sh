#!/usr/bin/env bash
set -Eeuo pipefail

solution_package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p /app/solution
if [ -e /app/solution/zim-src ]; then
  echo 'Refusing to overwrite an existing implementation.' >&2
  exit 1
fi
cp "$solution_package/start.sh" /app/solution/start.sh
echo "5561bed05a5fe4208da2ef8d5f8747ebc49e8cb32b46df2559cc73fb11fa65eb  $solution_package/zim-0.77.2.tar.gz" | sha256sum -c -
tar -xzf "$solution_package/zim-0.77.2.tar.gz" -C /app/solution
install -m 644 "$solution_package/SOURCE.json" "$solution_package/NOTICE" "$solution_package/LICENSE" /app/solution/
mv /app/solution/zim-0.77.2 /app/solution/zim-src
chmod 755 /app/solution/start.sh

mkdir -p /app/solution/LICENSES
cp "$solution_package"/LICENSES/*.txt /app/solution/LICENSES/

install -m 644 "$solution_package/launch.py" "$solution_package/exec_guard.c" /app/solution/
gcc -O2 -shared -fPIC -s -o /app/solution/exec_guard.so "$solution_package/exec_guard.c"
