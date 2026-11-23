#!/usr/bin/env bash
# Reference installation launcher: the unmodified Xournal++ 1.3.8 binary with all of its
# settings and documents under DATA_DIR, run through sandbox.py. Command-line
# arguments (for example --create-pdf=out.pdf in.xopp) are passed through.
set -Eeuo pipefail
data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/home" "$data/config" "$data/cache" "$data/tmp"
export HOME="$data/home"
export XDG_CONFIG_HOME="$data/config"
export XDG_CACHE_HOME="$data/cache"
export TMPDIR="$data/tmp"
if [ -n "${PBP_INBOX:-}" ]; then
  mkdir -p "$XDG_CONFIG_HOME/xournalpp"
  # Expose supplied GPL data to the product's documented user-palette loader.
  # The application itself still parses and selects palettes through Preferences.
  if [ ! -e "$XDG_CONFIG_HOME/xournalpp/palettes" ] && [ ! -L "$XDG_CONFIG_HOME/xournalpp/palettes" ]; then
    ln -s "$PBP_INBOX" "$XDG_CONFIG_HOME/xournalpp/palettes"
  fi
fi
export LANGUAGE=en
export GTK_MODULES="gail:atk-bridge"
export NO_AT_BRIDGE=0
export GTK_A11Y=always
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export LD_LIBRARY_PATH="$here/xournalpp/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export XDG_DATA_DIRS="$here/xournalpp/usr/share:/usr/local/share:/usr/share"
if [ -f "$here/xournalpp/usr/share/alsa/alsa.conf" ]; then
  export ALSA_CONFIG_PATH="$here/xournalpp/usr/share/alsa/alsa.conf"
  export ALSA_CONFIG_DIR="$here/xournalpp/usr/share/alsa"
fi
# GUI file dialogs start in the exchange inbox. Command-line runs keep the caller's
# working directory, against which relative file arguments are resolved.
if [ "$#" -eq 0 ]; then
  cd "${PBP_INBOX:-$HOME}"
fi
exec /usr/bin/python3 -I -B "$here/sandbox.py" "$here/xournalpp/usr/bin/xournalpp" "$@"
