#!/usr/bin/env bash
# Reference application: the unmodified CherryTree 1.7.2 release binary. Without arguments it runs the desktop
# application in the foreground; with arguments they are CherryTree's own command line (for example
# "FILE -t DIR" exports FILE to plain text in DIR).
set -Eeuo pipefail

data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/home" "$data/config" "$data/cache" "$data/tmp" "$data/home/.local/share"
export HOME="$data/home"
export XDG_CONFIG_HOME="$data/config"
export XDG_CACHE_HOME="$data/cache"
export XDG_DATA_HOME="$data/home/.local/share"
export TMPDIR="$data/tmp"
export LANG="${LANG:-C.UTF-8}"
export LANGUAGE="en"
export GTK_MODULES="gail:atk-bridge"
export NO_AT_BRIDGE=0
export GTK_A11Y=always
# The release binary resolves its data folder next to itself when APPIMAGE is set.
export APPIMAGE=1

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$data"
exec /usr/bin/python3 -I "$solution_dir/launch.py" "$@"
