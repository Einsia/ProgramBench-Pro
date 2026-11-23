#!/usr/bin/env bash
# Install the upstream taskwarrior-tui 0.27.0 release and the local Taskwarrior
# 3.3.0 build, with their launchers, sandbox and licences.
set -Eeuo pipefail

package="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
dest="${SOLUTION_DIR:-/app/solution}"
tui_archive=taskwarrior-tui-x86_64-unknown-linux-gnu.tar.gz
tui_sha256=11656a6c250eb3feaba35133987405ad0e3bc7b48f1b716ab59b70b6f7911974
task_archive=taskwarrior-3.3.0-x86_64-linux-gnu.tar.gz
task_sha256=64f8fce2a3b2a54c42ff65ac8f69a6a3a161ecfff8abb07c18db0069995742f0

check() {
  local actual
  actual="$(sha256sum "$package/$1" | awk '{print $1}')"
  if [ "$actual" != "$2" ]; then
    echo "archive checksum mismatch: $1 $actual" >&2
    exit 1
  fi
}
check "$tui_archive" "$tui_sha256"
check "$task_archive" "$task_sha256"
if [ -e "$dest/bin" ]; then
  echo "refusing to overwrite an existing implementation: $dest/bin" >&2
  exit 1
fi

mkdir -p "$dest/bin"
tar -xzf "$package/$tui_archive" -C "$dest/bin" --no-same-owner taskwarrior-tui
tar -xzf "$package/$task_archive" -C "$dest/bin" --no-same-owner task
chmod 0555 "$dest/bin/taskwarrior-tui" "$dest/bin/task"
install -m 0555 "$package/start.sh" "$dest/start.sh"
install -m 0555 "$package/task" "$dest/task"
for name in sandbox.py SOURCE.json LICENSE NOTICE; do
  install -m 0444 "$package/$name" "$dest/$name"
done
mkdir -p "$dest/LICENSES"
install -m 0444 "$package"/LICENSES/*.txt "$dest/LICENSES/"
echo "Installed taskwarrior-tui 0.27.0 ($tui_sha256) with Taskwarrior 3.3.0 ($task_sha256)"
