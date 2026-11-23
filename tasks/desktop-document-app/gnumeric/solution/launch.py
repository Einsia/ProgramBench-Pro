#!/usr/bin/env python3
"""Launch a native tool with a stable resource directory descriptor."""
import os
from pathlib import Path
import sys


def main():
    program, *arguments = sys.argv[1:]
    if program not in {'gnumeric', 'ssconvert', 'ssindex', 'ssgrep', 'ssdiff'}:
        raise SystemExit('unknown application entry point')
    directory = Path(__file__).resolve().parent
    os.chdir(directory)
    descriptor = os.open(directory, os.O_PATH | os.O_DIRECTORY)
    if descriptor != 9:
        os.dup2(descriptor, 9, inheritable=True)
        os.close(descriptor)
    else:
        os.set_inheritable(9, True)
    libraries = os.environ.get('LD_LIBRARY_PATH')
    os.environ['LD_LIBRARY_PATH'] = str(directory / 'upstream/lib') + (':' + libraries if libraries else '')
    os.environ['XDG_DATA_DIRS'] = str(directory / 'upstream/share') + ':/usr/local/share:/usr/share'
    os.environ['LANGUAGE'] = 'en'
    if program in {'gnumeric', 'ssconvert'}:
        config = Path(os.environ['HOME']) / '.gnumericrc'
        if not config.exists():
            config.write_text('[StringLists]\ngnumeric/plugins/active=Gnumeric_fnTimeSeriesAnalysis;\n')
    import importlib.util
    module_spec = importlib.util.spec_from_file_location('confinement', directory / 'confinement.py')
    confinement = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(confinement)
    confinement.apply_jail(str(directory / 'upstream'), extra_execute=('/usr/bin/glpsol', '/usr/bin/lp_solve'))
    if program == 'gnumeric':
        os.chdir(os.environ.get('PBP_EXPORTS', os.environ['DATA_DIR']))
    executable = directory / 'upstream/bin' / program
    os.execv(executable, [str(executable), *arguments])


if __name__ == '__main__':
    main()
