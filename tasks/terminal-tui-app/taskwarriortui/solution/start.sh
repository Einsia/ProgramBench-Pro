#!/usr/bin/env bash
# Application entry point: the unmodified taskwarrior-tui 0.27.0 program in the foreground, in the
# pseudo-terminal the black-box runtime provides, with Taskwarrior 3.3.0 as its backend. All persistent state lives
# under DATA_DIR, which serves as the home directory of both programs: Taskwarrior's configuration file (.taskrc) and
# data directory (.task), and taskwarrior-tui's history files (.local/share/taskwarrior-tui). Both programs run in the
# sandbox of sandbox.py.
set -Eeuo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data="${DATA_DIR:?DATA_DIR is required}"
export HOME="$data" TASKWARRIOR_TUI_TASKWARRIOR_CLI="$here/bin/task"
unset TASKRC TASKDATA TASKWARRIOR_TUI_DATA XDG_DATA_HOME
cd "$data"
# A fresh instance starts with the configuration file Taskwarrior writes itself on its first run.
if [ ! -e "$data/.taskrc" ]; then
  python3 -B -I "$here/sandbox.py" "$here/bin/task" rc.confirmation=off rc.verbose=nothing _version >/dev/null 2>&1 </dev/null || true
fi
exec python3 -B -I "$here/sandbox.py" "$here/bin/taskwarrior-tui"
