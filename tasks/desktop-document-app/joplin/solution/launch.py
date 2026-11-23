#!/usr/bin/env python3
'''Launch the pinned Joplin desktop product from the standard delivery package.

The Joplin profile lives in DATA_DIR/profile. Before every start the launcher writes what the runtime needs into
the profile's settings.json: the Web Clipper service (Joplin's Data API) starts with the application, listens on
PORT and accepts the token given in PBP_API_TOKEN. On the first start it also turns the update check and optical
character recognition off (both would need the network). It then launches the Electron executable:
no Welcome notebook (--no-welcome), no Chromium sandbox (the container has no user namespaces) and the renderer's
accessibility tree enabled for the desktop session. A small foreground supervisor
forwards signals and retries one clean exit before any window was created. Any
other setting stays the product default.
'''
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

FIRST_START = {'autoUpdateEnabled': False, 'ocr.enabled': False}
FLAGS = ('--no-sandbox', '--force-renderer-accessibility', '--no-welcome')


def settings(profile: Path) -> None:
    path = profile / 'settings.json'
    values = {}
    if path.exists():
        try:
            values = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            values = {}
    if not isinstance(values, dict) or not values:
        values = dict(FIRST_START)
    values.update({'clipperServer.autoStart': True, 'api.port': int(os.environ['PORT']),
                   'api.token': os.environ['PBP_API_TOKEN']})
    temporary = path.with_name('settings.json.start')
    temporary.write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def main() -> None:
    package = Path(__file__).resolve().parent
    executable = package / 'runtime' / 'opt' / 'Joplin' / 'joplin'
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise SystemExit(f'Joplin executable is unavailable: {executable}')
    profile = Path(os.environ['DATA_DIR']) / 'profile'
    profile.mkdir(parents=True, exist_ok=True)
    settings(profile)
    # The upstream profile IPC server also uses this default directory, even
    # when --profile points elsewhere.
    (Path(os.environ['HOME']) / '.config' / 'joplin-desktop').mkdir(parents=True, exist_ok=True)
    arguments = [sys.executable, '-I', '-B', str(package / 'product.py'), str(executable),
                 *FLAGS, '--profile', str(profile), *sys.argv[1:]]
    stopping = False
    child = None

    def stop(signum, _frame):
        nonlocal stopping
        stopping = True
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    # After a process-group stop, Joplin's own profile-lock check can perform
    # one immediate clean exit while releasing the previous session's lock.
    # Retry that startup once; no database or product code is changed.
    for attempt in range(2):
        started = time.monotonic()
        child = subprocess.Popen(arguments)
        had_window = False
        while child.poll() is None:
            if not had_window:
                windows = subprocess.run(['wmctrl', '-lp'], capture_output=True, text=True, timeout=3)
                had_window = any(len(row.split()) > 2 and row.split()[2] == str(child.pid)
                                 for row in windows.stdout.splitlines())
            time.sleep(.1)
        code = child.returncode
        if stopping or had_window or code != 0 or time.monotonic() - started >= 15 or attempt:
            raise SystemExit(code)
        time.sleep(.5)


if __name__ == '__main__':
    main()
