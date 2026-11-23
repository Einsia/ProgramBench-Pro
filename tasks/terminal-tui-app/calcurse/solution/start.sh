#!/usr/bin/env bash
# Standard-answer entry point: runs the unmodified calcurse 4.8.2 program in the foreground, in the terminal the
# black-box runtime provides, or, for the runtime's cli channel, once with the command-line arguments given.
# calcurse's home and working directory are DATA_DIR, so its files are DATA_DIR/.local/share/calcurse (apts, todo,
# notes/) and DATA_DIR/.config/calcurse (conf, keys), its default locations, and relative file names resolve against
# DATA_DIR. pbsandbox.so (LD_PRELOAD) confines the process before calcurse starts: Landlock limits it to the
# instance and the system data it reads, and a seccomp filter stops it from creating other processes.
set -Eeuo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data"

export HOME="$data"
unset XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME
export TERM="${TERM:-xterm-256color}"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export TZ="${TZ:-UTC}"
rw="$data:/dev/null:/dev/tty:/dev/pts"
if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then rw="$rw:$TMPDIR"; fi
export PBSANDBOX_RW="$rw"
export PBSANDBOX_RO=/usr/share/terminfo:/usr/lib/terminfo:/etc/terminfo:/usr/lib/locale:/usr/share/zoneinfo:/dev/urandom

cd "$data"
LD_PRELOAD="$solution_dir/calcurse/lib/pbsandbox.so${LD_PRELOAD:+ $LD_PRELOAD}" \
  exec "$solution_dir/calcurse/bin/calcurse" "$@"
