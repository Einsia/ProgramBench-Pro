#!/usr/bin/env python3
'''Launch the pinned LMMS 1.2.2 product from the installed runtime.

Without arguments this entry point
starts the desktop application in the foreground; with arguments it runs the product's own command line (render,
rendertracks, dump, upgrade) in the same environment and exits with the product's status. It only maps the public
DATA_DIR, HOME and PBP_FILES_DIR environment to LMMS's normal configuration (a seeded ~/.lmmsrc.xml that skips the
first-run dialogs, with the LMMS working directory in the document folders) and then execs the bundled product.

LMMS starts one mixer worker per online processor of the host, whatever CPU quota or affinity the process has; under
a container quota the surplus workers spin, the cgroup is throttled, and instruments that register their play handle
while the project loads (lb302, OPL2) are dropped as an overload. The launcher therefore preloads lmms_cpus.so, which
reports at most LMMS_CPUS processors (the CPU quota, the allowed processors and 4, whichever is smallest).
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
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

NL = chr(10)
SUBDIRECTORIES = ('plugins/ladspa', 'plugins/vst', 'presets', 'projects', 'samples/gig', 'samples/soundfonts',
                  'templates')


def element(name, **attributes):
    return '  <' + name + ''.join(' %s=%s' % (key, quoteattr(str(value))) for key, value in attributes.items()) + '/>' + NL


def configuration(work, stk):
    paths = dict(workingdir=work, gigdir=work + 'samples/gig/', sf2dir=work + 'samples/soundfonts/',
                 laddir=work + 'plugins/ladspa/', vstdir=work + 'plugins/vst/', artwork='data:/themes/default/',
                 backgroundartwork='', defaultsf2='', stkdir=stk)
    return ('<?xml version=' + quoteattr('1.0') + '?>' + NL + '<!DOCTYPE lmms-config-file>' + NL
            + '<lmms version=' + quoteattr('1.2.2') + '>' + NL
            + element('app', configured=1, nomsgaftersetup=1, language='en')
            + element('mixer', framesperaudiobuffer=256, hqaudio=0, mididev='Dummy (no MIDI support)',
                      audiodev='SDL (Simple DirectMedia Layer)')
            + element('paths', **paths)
            + element('ui', enableautosave=0, animateafp=0)
            + '</lmms>' + NL)


def processors():
    count = min(4, len(os.sched_getaffinity(0)))
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max':
            count = min(count, max(1, -(-int(quota) // int(period))))
    except (OSError, ValueError):
        pass
    return count


def main():
    package = Path(__file__).resolve().parent
    root = package / 'runtime'
    binary = root / 'usr' / 'bin' / 'lmms.real'
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise SystemExit('reference LMMS binary is unavailable: ' + str(binary))
    state = Path(os.environ.get('DATA_DIR', '/app/state')).resolve()
    state.mkdir(parents=True, exist_ok=True)
    home = Path(os.environ.get('HOME') or state / 'home').resolve()
    home.mkdir(parents=True, exist_ok=True)
    # The LMMS working directory is the runtime's document folder: its projects folder holds the saved projects.
    work = Path(os.environ.get('PBP_FILES_DIR') or state / 'files').resolve()
    for name in SUBDIRECTORIES:
        (work / name).mkdir(parents=True, exist_ok=True)
    config = home / '.lmmsrc.xml'
    if not config.exists():
        config.write_text(configuration(str(work) + '/', str(root / 'usr' / 'share' / 'stk' / 'rawwaves') + '/'))
    libraries = [root / 'usr' / 'lib' / 'lmms' / 'optional', root / 'usr' / 'lib', root / 'usr' / 'lib' / 'lmms']
    preload = ' '.join(filter(None, [str(package / 'lmms_cpus.so'), os.environ.get('LD_PRELOAD')]))
    env = dict(os.environ, LD_LIBRARY_PATH=':'.join(str(path) for path in libraries), QT_X11_NO_NATIVE_MENUBAR='1',
               LD_PRELOAD=preload, LMMS_CPUS=str(processors()))
    # Native file choosers begin in the document workspace, outside the unlistable installation root.
    os.chdir(work)
    confine(binary, package)
    os.execve(str(binary), [str(binary), *sys.argv[1:]], env)


if __name__ == '__main__':
    main()
