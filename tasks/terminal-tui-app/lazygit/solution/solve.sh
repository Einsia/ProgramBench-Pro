#!/usr/bin/env bash
# Install the standard answer: the unmodified upstream lazygit 0.66.2 release binary, verified against its pinned
# sha256, plus the launcher. Run as root in the reference image build and by install_standard; it only populates
# /app/solution (the lockdown configuration lives in the image at /app/solution/lazygitconf).
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
mkdir -p "$dest"

archive="$package/lazygit_0.66.2_linux_x86_64.tar.gz"
expected="158efc9ddfa1241fab5fb3526bb442c8dc6c4b1904d73213b9e4e93e03c52034"
actual="$(sha256sum "$archive" | awk '{print $1}')"
if [ "$actual" != "$expected" ]; then
  echo "standard lazygit archive checksum mismatch: $actual" >&2
  exit 1
fi
if [ -e "$dest/lazygit" ]; then
  echo "refusing to overwrite an existing implementation: $dest/lazygit" >&2
  exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# The archive holds lazygit, LICENSE and README.md; only the unmodified binary is installed from it.
tar -xzf "$archive" -C "$work" --no-same-owner lazygit

install -m 0555 "$package/start.sh" "$dest/start.sh"
install -m 0444 "$package/launch.py" "$dest/launch.py"
mkdir -p "$dest/lazygitconf"
install -m 0444 "$package/lazygitconf/config.yml" "$dest/lazygitconf/config.yml"
install -m 0444 "$package/SOURCE.json" "$dest/SOURCE.json"
install -m 0444 "$package/LICENSE" "$dest/LICENSE"
install -m 0444 "$package/NOTICE" "$dest/NOTICE"
install -m 0555 "$work/lazygit" "$dest/lazygit"
echo "Installed upstream lazygit 0.66.2 ($actual)"
