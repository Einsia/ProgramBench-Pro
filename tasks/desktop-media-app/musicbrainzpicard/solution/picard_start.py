#!/usr/bin/env python3
"""Launch MusicBrainz Picard using the supplied private profile."""
from __future__ import annotations

import os
import ctypes
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent
SOURCE = PACKAGE / 'picard-3.0.3'

# A new configuration starts after Picard's first-run guidance: no warning
# dialog, setup wizard or tutorial tips (the product's own settings for them).
INITIAL_CONFIG = """[setting]
show_new_user_dialog=false
[persist]
setup_wizard_completed=true
tutorial_disabled=true
"""


def main() -> None:
    mode, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ('gui', [])
    if not (SOURCE / 'picard' / '__init__.py').is_file():
        raise SystemExit(f'Picard source tree is unavailable: {SOURCE}')
    state = Path(os.environ.get('DATA_DIR', '/app/state')).resolve()
    config_home, data_home = state / 'config', state / 'share'
    for path in (config_home / 'MusicBrainz', data_home):
        path.mkdir(parents=True, exist_ok=True)
    config = config_home / 'MusicBrainz' / 'Picard.ini'
    if not config.exists():
        config.write_text(INITIAL_CONFIG)
    # Picard keeps its configuration, sessions and data under the XDG directories.
    os.environ['XDG_CONFIG_HOME'] = str(config_home)
    os.environ['XDG_DATA_HOME'] = str(data_home)
    # As in Picard's frozen release builds, error reports and logs name files and lines of
    # tracebacks without quoting source text.
    import linecache
    import traceback
    linecache.getline = lambda *_args, **_kwargs: ''
    linecache.getlines = lambda *_args, **_kwargs: []
    sys.excepthook = lambda kind, value, tb: traceback.print_exception(kind, value, tb)
    os.environ['GST_REGISTRY_FORK'] = 'no'
    boundary = ctypes.CDLL(str(PACKAGE / 'process_guard.so'), use_errno=True)
    boundary.protect_application.argtypes = [ctypes.c_char_p]
    boundary.protect_application.restype = ctypes.c_int
    if boundary.protect_application(None) != 0:
        raise SystemExit('application process isolation is unavailable')
    sys.path.insert(0, str(SOURCE))
    if mode == 'cli':
        sys.argv = ['picard-cli', *args]
        from picard.cli import main as cli_main
        cli_main()
        return
    # Plug-ins are not part of this installation (they are installed from git repositories).
    sys.argv = ['picard', '--no-plugins', *args]
    from picard import register_excepthook
    register_excepthook()
    from picard.tagger import main as picard_main
    picard_main(autoupdate=False)


if __name__ == '__main__':
    main()
