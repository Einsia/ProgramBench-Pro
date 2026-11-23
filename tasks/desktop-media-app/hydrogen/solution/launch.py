#!/usr/bin/env python3
'''Launch the pinned Hydrogen 1.2.7 product from the installed runtime.

Without arguments this entry point
starts the desktop application in the foreground, its OSC server listening on UDP PORT. With arguments it runs the
product's own command line (h2cli) with those arguments in the same environment and exits with the product's status.

Both use the product's ordinary user folder ~/.hydrogen (settings file hydrogen.conf and the user library in data/).
The first start writes hydrogen.conf: the product's default settings with OSC enabled, autosave off, English as the
interface language (the desktop's C locale names no language, and the preferences dialog would otherwise switch to the
first translation it lists) and the mixer window closed. The command line reads a copy of the settings in TMPDIR, so it never rewrites the settings of the
desktop application.
'''
from __future__ import annotations

import os
import importlib.util

# The installation root is traversable but not listable; load the known helper path directly.
_isolation_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'isolation.py')
_isolation_spec = importlib.util.spec_from_file_location('application_isolation', _isolation_path)
_isolation = importlib.util.module_from_spec(_isolation_spec)
_isolation_spec.loader.exec_module(_isolation)
confine = _isolation.confine
import re
import shutil
import sys
from pathlib import Path

# Settings that differ from hydrogen.default.conf: (element path, value).
SEED = (('oscEnabled', 'true'), ('autosavesPerHour', '0'), ('preferredLanguage', 'en'))


def seed(default):
    text = default
    for name, value in SEED:
        text, count = re.subn(rf'<{name}>[^<]*</{name}>', f'<{name}>{value}</{name}>', text, count=1)
        if count != 1:
            raise SystemExit(f'default settings lack {name}')
    # The mixer opens as a window of its own; the fresh profile starts with it closed.
    text, count = re.subn(r'(<mixer_properties>\s*<visible>)true(</visible>)', r'\g<1>false\g<2>', text, count=1)
    if count != 1:
        raise SystemExit('default settings lack the mixer window properties')
    return text


def main():
    package = Path(__file__).resolve().parent
    # External effect libraries are unavailable, including when a settings dialog changes a search path.
    os.environ['LADSPA_PATH'] = str(package / 'runtime' / 'disabled-ladspa')
    usr = package / 'runtime' / 'usr'
    gui, cli = usr / 'bin' / 'hydrogen', usr / 'bin' / 'h2cli'
    for binary in (gui, cli):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise SystemExit(f'reference Hydrogen binary is unavailable: {binary}')
    home = Path(os.environ.get('HOME') or Path(os.environ.get('DATA_DIR', '/app/state')) / 'home').resolve()
    profile = home / '.hydrogen'
    profile.mkdir(parents=True, exist_ok=True)
    settings = profile / 'hydrogen.conf'
    if not settings.exists():
        settings.write_text(seed((usr / 'share' / 'hydrogen' / 'data' / 'hydrogen.default.conf').read_text()))
    files = os.environ.get('PBP_FILES_DIR')
    if files and Path(files).is_dir():
        os.chdir(files)
    arguments = sys.argv[1:]
    if arguments:
        scratch = Path(os.environ.get('TMPDIR') or '/tmp') / f'h2cli-{os.getpid()}'
        scratch.mkdir(parents=True, exist_ok=True)
        copy = scratch / 'hydrogen.conf'
        shutil.copyfile(settings, copy)
        confine(cli, package)
        os.execv(str(cli), [str(cli), '--config', str(copy), *arguments])
    command = [str(gui), '--nosplash']
    port = os.environ.get('PORT', '')
    if port.isdigit():
        command += ['--osc-port', port]
    confine(gui, package)
    os.execv(str(gui), command)


if __name__ == '__main__':
    main()
