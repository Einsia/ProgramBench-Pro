#!/usr/bin/env bash
set -Eeuo pipefail

# Installs the reference installation: the official Money Manager Ex 1.9.4 package for Ubuntu 24.04, unpacked unchanged under
# /app/solution/mmex (the product finds its resources relative to its executable), its launcher, and the preloaded guard
# (mmex_guard.c). The libraries it needs come with the image.
package="mmex_1.9.4-Ubuntu.24.04.noble_amd64.deb"
sha256=f410d50eeecb0a4b61578b048a2b3d501fcc69bac3eddd6a0a4b391f13332a34

solution_package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ -e /app/solution/mmex ]; then
  echo 'Refusing to overwrite an existing implementation.' >&2
  exit 1
fi
echo "$sha256  $solution_package/$package" | sha256sum -c -
mkdir -p /app/solution/bin
mkdir -p /app/solution/lib
# These two product dependencies are absent from the development image. Carry
# them in the installed reference installation so it also runs with --target self.
cp "$solution_package"/lib/* /app/solution/lib/
dpkg-deb -x "$solution_package/$package" /app/solution/mmex
# The package also carries the development files of a library it links statically.
rm -rf /app/solution/mmex/usr/include /app/solution/mmex/usr/lib
for file in start.sh solve.sh mmex_guard.c seed.py SOURCE.json LICENSE NOTICE; do
  cp "$solution_package/$file" "/app/solution/$file"
done
cp "$solution_package/uname" /app/solution/bin/uname
# Built where it is installed, from a relative path, so every build yields the same library.
(cd /app/solution && gcc -O2 -shared -fPIC -s -o mmex_guard.so mmex_guard.c -ldl)
chmod -R u+rwX,go+rX,go-w /app/solution/mmex
chmod 755 /app/solution/start.sh /app/solution/solve.sh /app/solution/bin/uname
chmod 644 /app/solution/mmex_guard.c /app/solution/mmex_guard.so /app/solution/seed.py \
  /app/solution/SOURCE.json /app/solution/LICENSE /app/solution/NOTICE

mkdir -p /app/solution/LICENSES
cp "$solution_package"/LICENSES/*.txt /app/solution/LICENSES/
