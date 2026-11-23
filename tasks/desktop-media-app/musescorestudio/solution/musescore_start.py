#!/usr/bin/env python3
"""Launch MuseScore Studio using the supplied private profile."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

SETTINGS = '''[application]
hasCompletedFirstLaunchSetup=true
welcomeDialogShowOnStartup=false
welcomeDialogLastShownVersion=4.7.6
checkForUpdate=false
devModeEnabled=false

[project]
autoSaveEnabled=false
createBackupBeforeSaving=false
shouldAskSaveLocationType=false
lastUsedSaveLocationType=1
showCloudIsNotAvailableWarning=false
'''
# A crash this soon after a desktop start is a start-up crash (the product shows its window after about 3 s).
STARTUP_SECONDS = 20
RETRIES = 1


def desktop(launcher: Path) -> int:
    child: subprocess.Popen | None = None

    def forward(signum, _frame):
        if child is not None and child.poll() is None:
            child.send_signal(signum)

    for name in ('SIGTERM', 'SIGINT', 'SIGHUP'):
        signal.signal(getattr(signal, name), forward)
    for attempt in range(RETRIES + 1):
        began = time.monotonic()
        child = subprocess.Popen([str(launcher)])
        status = child.wait()
        fatal_signal = -status if status < 0 else status - 128
        crashed = fatal_signal in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS)
        if not (crashed and time.monotonic() - began < STARTUP_SECONDS and attempt < RETRIES):
            return 128 - status if status < 0 else status
        print(f'musescore_start: the product died of signal {fatal_signal} during start-up; starting it again',
              file=sys.stderr, flush=True)
    return 1


def main() -> None:
    package = Path(__file__).resolve().parent
    launcher = package / 'runtime' / 'AppRun'
    if not launcher.is_file() or not os.access(launcher, os.X_OK):
        raise SystemExit(f'MuseScore Studio launcher is unavailable: {launcher}')
    home = Path(os.environ.get('HOME') or '/tmp')
    config_home = Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config')
    ini = config_home / 'MuseScore' / 'MuseScore4.ini'
    if not ini.exists():
        ini.parent.mkdir(parents=True, exist_ok=True)
        ini.write_text(SETTINGS)
    os.environ.setdefault('QT_QUICK_BACKEND', 'software')
    os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
    os.environ['LD_PRELOAD'] = str(package / 'process_guard.so')
    if sys.argv[1:]:
        os.execv(str(launcher), [str(launcher), *sys.argv[1:]])
    raise SystemExit(desktop(launcher))


if __name__ == '__main__':
    main()
