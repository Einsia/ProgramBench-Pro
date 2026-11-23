#!/usr/bin/env python3
'''In-process launcher for VisiData 3.4 and its pure-Python dependencies.
Upstream files are unchanged; the launcher applies a runtime command and expression policy.

Order:
  1. Import the bundled packages by exact path through a manifest finder (the package directory is root-owned,
     traversable but not listable) and preload everything VisiData needs, so the confinement can stay narrow.
  2. Apply the reference policy in-process: no network, plugins or help sidebars, no commands that load or run
     code, run programs or inspect Python objects, and a guarded expression evaluator (guard.py).
  3. Confine the process: an unprivileged Landlock ruleset (filesystem and TCP) and a seccomp filter denying
     execve and execveat. The product can read and write only its workspace and its own state.
  4. Run VisiData with -N (no rc file, plugin or user code loading): the full-screen interface, or, for the
     runtime's cli channel, one batch invocation whose arguments arrive as a JSON array in PBP_CLI_ARGS.
'''
from __future__ import annotations

import ctypes
import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGES = HERE / 'vdpkg'
TOP_LEVEL = ('visidata', 'dateutil', 'six')
REFUSAL = 'This action is disabled in this environment.'

# Commands that load or run code, run programs, reach the system clipboard or an editor, inspect Python objects
# or stop the process. They are refused by name: VisiData's own command table is edited in memory.
REFUSED_NAMES = frozenset('''exec-python import-python define-command breakpoint open-repl exec-shell
    addcol-shell open-config open-plugins suspend open-syspaste open-url open-ping open-processes open-memstats reload-every toggle-profile'''.split())
REFUSED_PREFIXES = ('pyobj', 'sysedit', 'sysopen', 'syscopy', 'syspaste')
# Options a cli invocation may not set: they change what is loaded at start or need a terminal.
CLI_REFUSED = frozenset('''c config N nothing visidata_dir imports plugins_autoload motd_url i interactive
    profile debug'''.split())
CLI_BATCH = frozenset('b batch v version h help'.split())


# -- 1. manifest finder: import by exact path, never list a directory ----------------------------------------
class ManifestFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root):
        self.root = str(root)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] not in TOP_LEVEL:
            return None
        base = os.path.join(self.root, fullname.replace('.', '/'))
        sourceless = importlib.machinery.SourcelessFileLoader
        for init, loader in ((base + '/__init__.py', None), (base + '/__init__.pyc', sourceless)):
            if os.path.isfile(init):
                return importlib.util.spec_from_file_location(
                    fullname, init, loader=loader(fullname, init) if loader else None,
                    submodule_search_locations=[base])
        for module, loader in ((base + '.py', None), (base + '.pyc', sourceless)):
            if os.path.isfile(module):
                return importlib.util.spec_from_file_location(
                    fullname, module, loader=loader(fullname, module) if loader else None)
        return None


# -- 3. confinement: Landlock and seccomp --------------------------------------------------------------------
LIBC = ctypes.CDLL(None, use_errno=True)
EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1, 2, 4, 8
TRUNCATE, IOCTL_DEV = 1 << 14, 1 << 15
FILE_RIGHTS = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE | IOCTL_DEV
NET_TCP = 3  # bind and connect


def _buffer(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def _call(number, *args):
    result = LIBC.syscall(number, *args)
    if result < 0:
        raise OSError(ctypes.get_errno(), 'syscall %d failed' % number)
    return result


def confine(read_only, read_write):
    '''Landlock: only the listed paths are reachable; everything else, new TCP connections and exec are denied.
    Fails closed: a kernel without Landlock stops the start.'''
    version = _call(444, None, 0, 1)
    handled = (1 << (13 + (version >= 2) + (version >= 3) + (version >= 5))) - 1
    attr = struct.pack('=QQ', handled, NET_TCP) if version >= 4 else struct.pack('=Q', handled)
    ruleset = _call(444, _buffer(attr), len(attr), 0)
    try:
        for paths, rights in ((read_only, READ_FILE | READ_DIR), (read_write, handled & ~EXECUTE)):
            for path in paths:
                try:
                    handle = os.open(path, os.O_PATH | os.O_CLOEXEC)
                except OSError:
                    continue
                try:
                    allowed = rights & handled
                    if not os.path.isdir(path):
                        allowed &= FILE_RIGHTS
                    _call(445, ruleset, 1, _buffer(struct.pack('=Qi', allowed, handle)), 0)
                finally:
                    os.close(handle)
        if LIBC.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
        _call(446, ruleset, 0)
    finally:
        os.close(ruleset)
    return version


class _Filter(ctypes.Structure):
    _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte), ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]


class _Program(ctypes.Structure):
    _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(_Filter))]


def deny_exec():
    '''seccomp: execve and execveat fail with EPERM (x86_64; other architectures rely on the Landlock
    EXECUTE right, which is handled and never granted).'''
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x7FFF0000), (0x20, 0, 0, 0),
            (0x15, 2, 0, 59), (0x15, 1, 0, 322), (0x06, 0, 0, 0x7FFF0000), (0x06, 0, 0, 0x00050001)]
    program = (_Filter * len(rows))(*[_Filter(*row) for row in rows])
    if LIBC.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
    if LIBC.prctl(22, 2, ctypes.byref(_Program(len(rows), program)), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_SECCOMP) failed')


# -- 2. reference policy -------------------------------------------------------------------------------------
def _load_guard():
    spec = importlib.util.spec_from_file_location('vd_guard', str(HERE / 'guard.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_policy(visidata):
    vd = visidata.vd
    for name, value in (('motd_url', ''), ('plugins_autoload', False), ('disp_help_flags', 'nometacols')):
        visidata.options.set(name, value, 'global', cmdlog=False)
    refused = 'fail(%r)' % REFUSAL
    for (longname, _), command in list(vd.commands.iterall()):
        if longname in REFUSED_NAMES or longname.startswith(REFUSED_PREFIXES):
            command.execstr = refused
    _load_guard().install(visidata)
    import traceback
    sys.modules['visidata.main'].stacktrace = lambda: [traceback.format_exc().strip().splitlines()[-1]]


# -- cli channel ---------------------------------------------------------------------------------------------
def cli_arguments(raw):
    '''Validate the JSON array of vd arguments of one batch run.'''
    arguments = json.loads(raw)
    if not isinstance(arguments, list) or not 0 < len(arguments) <= 64:
        raise ValueError('the arguments must be a JSON array of 1-64 strings')
    for argument in arguments:
        if not isinstance(argument, str) or not 0 < len(argument) <= 4096 or chr(0) in argument:
            raise ValueError('each argument must be a non-empty string without NUL, at most 4096 characters')
    names, done = set(), False
    for argument in arguments:
        if done or not argument.startswith('-') or argument == '-':
            continue
        if argument == '--':
            done = True
            continue
        name = argument.lstrip('-').split('=', 1)[0].replace('-', '_')
        if name in CLI_REFUSED:
            raise ValueError('option %s is not available here' % argument)
        names.add(name)
    if not names & CLI_BATCH:
        raise ValueError('only batch runs are available: pass -b (or --version, --help)')
    return arguments


def main():
    raw = os.environ.pop('PBP_CLI_ARGS', None)
    try:
        arguments = cli_arguments(raw) if raw else []
    except ValueError as exc:
        sys.stderr.write('vd: %s%s' % (exc, chr(10)))
        sys.exit(2)
    data = Path(os.environ['DATA_DIR']).resolve()
    workspace = data / 'workspace'
    state = [data / '.local' / 'share', data / '.cache', data / '.config']
    for directory in [workspace] + [path / 'visidata' for path in state]:
        directory.mkdir(parents=True, exist_ok=True)
    os.environ.update(XDG_DATA_HOME=str(state[0]), XDG_CACHE_HOME=str(state[1]), XDG_CONFIG_HOME=str(state[2]),
                      LANG='C.UTF-8', LC_ALL='C.UTF-8')
    os.chdir(workspace)
    sys.meta_path.insert(0, ManifestFinder(PACKAGES))
    import dateutil.parser  # noqa: F401  (preloaded: the confinement allows no later import)
    import dateutil.relativedelta  # noqa: F401
    import dateutil.tz  # noqa: F401
    import dateutil.rrule  # noqa: F401  (tzical imports this lazily)
    import _strptime  # noqa: F401  (datetime strftime and strptime import it and time lazily)
    import time  # noqa: F401
    import visidata
    from visidata.main import vd_cli
    apply_policy(visidata)
    resources = PACKAGES / 'visidata'
    read_only = ['/usr', '/lib', '/lib64', '/bin', '/etc/passwd', '/etc/group', '/etc/nsswitch.conf',
                 '/etc/ld.so.cache', '/etc/localtime', '/etc/terminfo', '/etc/mime.types', '/etc/locale.alias',
                 '/dev/urandom', str(resources / 'guides'), str(resources / 'man'), str(resources / 'ddw')]
    read_write = [str(workspace)] + [str(path) for path in state] + [os.environ.get('TMPDIR') or '/tmp',
                                                                       '/dev/null', '/dev/tty']
    confine(read_only, read_write)
    deny_exec()
    sys.argv = ['vd', '-N'] + arguments
    vd_cli()


if __name__ == '__main__':
    main()
