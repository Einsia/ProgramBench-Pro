#!/usr/bin/env bash
set -Eeuo pipefail

data="${DATA_DIR:?DATA_DIR is required}"
solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$data/home" "$data/config" "$data/cache" "$data/tmp"
export HOME="$data/home"
export XDG_CONFIG_HOME="$data/config"
export XDG_CACHE_HOME="$data/cache"
export TMPDIR="$data/tmp"
export LANG="${LANG:-C.UTF-8}"
export LANGUAGE="en"
export GTK_MODULES="gail:atk-bridge"
export NO_AT_BRIDGE=0
export GTK_A11Y=always

python3 -I -B "$solution_dir/seed.py" "$HOME/.mmex/mmexini.db3"
# The window title shows the output of uname: a fixed text instead of the host's kernel.
export PATH="$solution_dir/bin:$PATH"
export LD_LIBRARY_PATH="$solution_dir/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
# The product runs with a preloaded guard: no Lua libraries, no other programs than its own web content helpers.
export LD_PRELOAD="$solution_dir/mmex_guard.so${LD_PRELOAD:+:$LD_PRELOAD}"
# File dialogs start in the folder of the input documents.
cd "${PBP_INBOX:-$data}"
arguments=(--silent)
if [ -n "${PBP_DATABASE:-}" ]; then
  arguments+=("$PBP_DATABASE")
fi
exec "$solution_dir/mmex/usr/bin/mmex" "${arguments[@]}"
