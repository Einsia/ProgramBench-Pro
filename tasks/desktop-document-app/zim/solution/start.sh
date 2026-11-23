#!/usr/bin/env bash
set -Eeuo pipefail

data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/home" "$data/config" "$data/cache" "$data/tmp" "$data/share"
export HOME="$data/home"
export XDG_CONFIG_HOME="$data/config"
export XDG_CACHE_HOME="$data/cache"
export XDG_DATA_HOME="$data/share"
export TMPDIR="$data/tmp"
export LANG="${LANG:-C.UTF-8}"
export LANGUAGE="en"
export GTK_MODULES="gail:atk-bridge"
export NO_AT_BRIDGE=0
export GTK_A11Y=always

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
zim=(/usr/bin/python3 -I -B "$solution_dir/launch.py")
# File dialogs start in the inbox, so the first folder they show is an exchange folder.
cd "${PBP_INBOX:-$data}"
if [ "$#" -gt 0 ]; then
  exec "${zim[@]}" "$@"
fi
notebook="${PBP_NOTEBOOK:-$data/notebook}"
mkdir -p "$notebook"
exec "${zim[@]}" --standalone "$notebook"
