#!/usr/bin/env python3
"""Launcher for the reference application: the unmodified upstream micro 2.0.15 binary, confined by operating-system
means only (no patch, no wrapper inside the editor).

Order:
  1. Lay out the instance: the working directory (DATA_DIR/workspace) and micro's configuration directory
     (DATA_DIR/config, given to micro as MICRO_CONFIG_HOME). micro loads Lua code from two places in that
     directory, init.lua and plug/, at start and on `reload`. Before every start both names are replaced by
     dangling symbolic links into a directory that does not exist: micro then sees neither (a missing init.lua, an
     empty plugin directory) and none of its file operations can create, replace or remove them, so no user code
     is ever loaded. The built-in plugins, which are part of the binary, keep working.
  2. Refuse the command-line options that write outside the instance or change what is loaded (-config-dir,
     -debug, -profile, -plugin, -clean).
  3. Confine the process: an unprivileged Landlock ruleset (the editor can reach only the working directory, its
     configuration directory, its temporary directory and its terminal; it may execute only its own binary; no TCP)
     and a seccomp filter denying execve. Shell commands, terminal panes, text filters, external linters and
     clipboard programs therefore fail as they would on a system without them.
  4. Execute an unchanged, mode-0111 copy in the private temporary directory through its file descriptor.
     The installed binary remains root-owned and mode 0555; Landlock keeps the editor away from it, while
     the copy's execute-only permissions prevent reading its implementation as data.
"""
import ctypes
import os
import struct
import sys
import shutil
import stat
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BINARY = HERE / 'micro'
BLOCKED = '/nonexistent/micro-user-code'
REFUSED_FLAGS = frozenset(('config-dir', 'debug', 'profile', 'plugin', 'clean'))

LIBC = ctypes.CDLL(None, use_errno=True)
SYS_LANDLOCK_CREATE_RULESET, SYS_LANDLOCK_ADD_RULE, SYS_LANDLOCK_RESTRICT_SELF = 444, 445, 446
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


def guard_config(config):
    """Replace init.lua and plug/ by dangling links (see the module description)."""
    config.mkdir(parents=True, exist_ok=True)
    for name in ('init.lua', 'plug'):
        path = config / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            for child in sorted(path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
                if child.is_dir() and not child.is_symlink():
                    child.rmdir()
                else:
                    child.unlink()
            path.rmdir()
        os.symlink(BLOCKED + '/' + name, path)
    if os.path.lexists(BLOCKED) or os.path.exists(BLOCKED):
        raise SystemExit('micro launcher: ' + BLOCKED + ' must not exist')


def executable_copy(tmp):
    """Prepare an execute-only instance copy of the immutable installed binary."""
    target = tmp / 'micro-program'
    try:
        info = target.lstat()
    except FileNotFoundError:
        fd, pending = tempfile.mkstemp(dir=tmp)
        try:
            with os.fdopen(fd, 'wb') as output, BINARY.open('rb') as source:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fchmod(output.fileno(), 0o111)
            os.replace(pending, target)
        finally:
            if os.path.lexists(pending):
                os.unlink(pending)
    else:
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o111 or info.st_size != BINARY.stat().st_size:
            raise OSError('invalid application program cache')
    return target


def confine(read_write, devices, executable):
    """Landlock: only the listed paths are reachable, only the editor's own binary can be executed, and no TCP.
    Fails closed: a kernel without Landlock stops the start."""
    version = _call(SYS_LANDLOCK_CREATE_RULESET, None, 0, 1)
    handled = (1 << (13 + (version >= 2) + (version >= 3) + (version >= 5))) - 1
    attr = struct.pack('=QQ', handled, NET_TCP) if version >= 4 else struct.pack('=Q', handled)
    ruleset = _call(SYS_LANDLOCK_CREATE_RULESET, _buffer(attr), len(attr), 0)
    rules = [(str(executable), EXECUTE | READ_FILE)]
    rules += [(path, handled & ~EXECUTE) for path in read_write]
    rules += [(path, READ_FILE | WRITE_FILE | IOCTL_DEV) for path in devices]
    try:
        for path, rights in rules:
            try:
                handle = os.open(path, os.O_PATH | os.O_CLOEXEC)
            except OSError:
                continue
            try:
                allowed = rights & handled
                if not os.path.isdir(path):
                    allowed &= FILE_RIGHTS
                _call(SYS_LANDLOCK_ADD_RULE, ruleset, 1, _buffer(struct.pack('=Qi', allowed, handle)), 0)
            finally:
                os.close(handle)
        if LIBC.prctl(38, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
        _call(SYS_LANDLOCK_RESTRICT_SELF, ruleset, 0)
    finally:
        os.close(ruleset)


class _Filter(ctypes.Structure):
    _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte), ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]


class _Program(ctypes.Structure):
    _fields_ = [('len', ctypes.c_ushort), ('filter', ctypes.POINTER(_Filter))]


def deny_execve():
    """seccomp: execve fails with EPERM (x86_64). execveat stays available for the launcher's own exec of the
    binary; Landlock allows executing nothing else."""
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, 0xC000003E), (0x06, 0, 0, 0x7FFF0000), (0x20, 0, 0, 0),
            (0x15, 0, 1, 59), (0x06, 0, 0, 0x00050001), (0x06, 0, 0, 0x7FFF0000)]
    program = (_Filter * len(rows))(*[_Filter(*row) for row in rows])
    if LIBC.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
    if LIBC.prctl(22, 2, ctypes.byref(_Program(len(rows), program)), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_SECCOMP) failed')


def main():
    arguments = sys.argv[1:]
    for argument in arguments:
        if argument.startswith('-') and argument.lstrip('-').split('=', 1)[0] in REFUSED_FLAGS:
            sys.stderr.write('micro: the option %s is not available here\n' % argument)
            sys.exit(2)
    data = Path(os.environ['DATA_DIR']).resolve()
    workspace = data / 'workspace'
    config = data / 'config'
    workspace.mkdir(parents=True, exist_ok=True)
    guard_config(config)
    temporary_root = Path(os.environ.get('TMPDIR') or (data / 'tmp'))
    temporary_root.mkdir(parents=True, exist_ok=True)
    tmp = temporary_root / 'files'
    tmp.mkdir(parents=True, exist_ok=True)
    environment = {
        'PATH': '/usr/bin:/bin', 'HOME': str(workspace), 'MICRO_CONFIG_HOME': str(config), 'TMPDIR': str(tmp),
        'TERM': os.environ.get('TERM', 'xterm-256color'), 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
    }
    for name in ('COLUMNS', 'LINES', 'USER', 'LOGNAME'):
        if os.environ.get(name):
            environment[name] = os.environ[name]
    executable = executable_copy(temporary_root)
    binary = os.open(executable, os.O_PATH | os.O_CLOEXEC)
    os.chdir(workspace)
    confine([str(workspace), str(config), str(tmp)], ['/dev/tty', '/dev/null'], executable)
    deny_execve()
    os.execve(binary, ['micro'] + arguments, environment)


if __name__ == '__main__':
    main()
