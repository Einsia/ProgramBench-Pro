#!/usr/bin/env python3
"""Confine the desktop product before replacing this process with it."""
import os
from pathlib import Path
import sys

directory = Path(__file__).resolve().parent
import importlib.util
module_spec = importlib.util.spec_from_file_location('confinement', directory / 'confinement.py')
confinement = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(confinement)

executable = directory / 'runtime/opt/Joplin/joplin'
if len(sys.argv) < 2 or Path(sys.argv[1]) != executable:
    raise SystemExit('unexpected application entry point')
confinement.apply_jail(str(executable.parent))
os.chdir(os.environ.get('PBP_EXPORTS', os.environ['DATA_DIR']))
os.execv(executable, [str(executable), *sys.argv[2:]])
