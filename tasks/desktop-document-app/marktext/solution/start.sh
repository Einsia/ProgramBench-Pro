#!/usr/bin/env bash
# Reference application launcher: run the unmodified upstream MarkText release in the
# foreground, keeping all state under DATA_DIR. Extra arguments are file paths to
# open; a second launch while an instance is running hands the paths to it.
#
# The product is launched inside a Landlock sandbox (jail.py) that confines the
# reference installation so it cannot be used to execute arbitrary commands or
# read/exfiltrate its own implementation; this is an isolation measure for the
# reference process.
set -Eeuo pipefail

data="${DATA_DIR:?DATA_DIR is required}"
mkdir -p "$data/home" "$data/cache" "$data/config" "$data/tmp" "$data/userdata"
export HOME="$data/home"
export XDG_CONFIG_HOME="$data/config"
export XDG_CACHE_HOME="$data/cache"
export TMPDIR="$data/tmp"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export TZ="${TZ:-UTC}"
export GTK_MODULES="${GTK_MODULES:-gail:atk-bridge}"
export NO_AT_BRIDGE=0
# Electron needs a writable Electron config path inside the private HOME.
export ELECTRON_OZONE_PLATFORM_HINT="${ELECTRON_OZONE_PLATFORM_HINT:-x11}"

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app="$solution_dir/marktext-app/marktext"

# Headless rendering without a separate GPU process: Chromium's GPU process
# cannot initialize in the offline container, so GPU work runs in-process and a
# crash of a separate GPU process cannot take the window down. The launcher
# first applies the Landlock sandbox (jail.py), which then execs the product.
exec /usr/bin/python3 -I "$solution_dir/jail.py" "$app" \
  --no-sandbox \
  --disable-gpu \
  --in-process-gpu \
  --disable-software-rasterizer \
  --force-renderer-accessibility \
  --user-data-dir="$data/userdata" \
  "$@"
