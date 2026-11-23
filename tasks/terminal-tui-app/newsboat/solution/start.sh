#!/usr/bin/env bash
# Application entry point: runs the unmodified Newsboat 2.45 binary in the foreground, in the terminal the
# black-box runtime provides (or, for the runtime's cli channel, with the command-line arguments given). Newsboat's
# home directory is DATA_DIR, so all of its files live in DATA_DIR/.newsboat and every relative path it is given
# resolves against DATA_DIR. pbsandbox.so (LD_PRELOAD) confines the process before Newsboat starts: Landlock
# limits it to instance files and terminal devices, and a seccomp filter refuses to start other programs.
set -Eeuo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/.newsboat"
mkdir -p "$data/.terminal/x"
cp /usr/share/terminfo/x/xterm-256color "$data/.terminal/x/xterm-256color"
export TERMINFO="$data/.terminal"
mkdir -p "$data/.temporary"
export TMPDIR="$data/.temporary"

export HOME="$data"
unset XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME
export TERM="${TERM:-xterm-256color}"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export TZ="${TZ:-UTC}"
rw="$data:/dev/null:/dev/tty:/dev/pts"
if [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ]; then rw="$rw:$TMPDIR"; fi
export PBSANDBOX_RO=/dev/urandom
export PBSANDBOX_RW="$rw"

cd "$data"
LD_PRELOAD="$solution_dir/newsboat/lib/pbsandbox.so" exec "$solution_dir/newsboat/bin/newsboat" "$@"
