#!/usr/bin/env python3
"""Apply Landlock before launching the reference product.

The rules below describe the executable, readable and writable resources made
available to the process and its children. The launcher refuses to start if
Landlock cannot be established.
"""
from __future__ import annotations

import ctypes
import os
import stat
import struct
import sys

libc = ctypes.CDLL(None, use_errno=True)

NR_landlock_create_ruleset = 444
NR_landlock_add_rule = 445
NR_landlock_restrict_self = 446
PR_SET_NO_NEW_PRIVS = 38
O_PATH = 0o10000000
O_CLOEXEC = 0o2000000
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1

FS = {
    'EXECUTE': 1 << 0, 'WRITE_FILE': 1 << 1, 'READ_FILE': 1 << 2, 'READ_DIR': 1 << 3,
    'REMOVE_DIR': 1 << 4, 'REMOVE_FILE': 1 << 5, 'MAKE_CHAR': 1 << 6, 'MAKE_DIR': 1 << 7,
    'MAKE_REG': 1 << 8, 'MAKE_SOCK': 1 << 9, 'MAKE_FIFO': 1 << 10, 'MAKE_BLOCK': 1 << 11,
    'MAKE_SYM': 1 << 12, 'REFER': 1 << 13, 'TRUNCATE': 1 << 14, 'IOCTL_DEV': 1 << 15,
}


def _syscall(number, *args):
    ctypes.set_errno(0)
    return libc.syscall(ctypes.c_long(number), *[ctypes.c_long(a) for a in args])


def _abi_version():
    return _syscall(NR_landlock_create_ruleset, 0, 0, LANDLOCK_CREATE_RULESET_VERSION)


def _note(message):
    sys.stderr.write('[jail] ' + message + '\n')
    sys.stderr.flush()


class Landlock:
    def __init__(self, abi):
        self.abi = abi
        # All filesystem access rights we know how to govern, clipped to the ABI.
        handled = (FS['EXECUTE'] | FS['WRITE_FILE'] | FS['READ_FILE'] | FS['READ_DIR'] | FS['REMOVE_DIR']
                   | FS['REMOVE_FILE'] | FS['MAKE_CHAR'] | FS['MAKE_DIR'] | FS['MAKE_REG'] | FS['MAKE_SOCK']
                   | FS['MAKE_FIFO'] | FS['MAKE_BLOCK'] | FS['MAKE_SYM'])
        if abi >= 2:
            handled |= FS['REFER']
        if abi >= 3:
            handled |= FS['TRUNCATE']
        if abi >= 5:
            handled |= FS['IOCTL_DEV']
        self.handled = handled
        attr = struct.pack('<Q', handled)
        buf = ctypes.create_string_buffer(attr, len(attr))
        fd = _syscall(NR_landlock_create_ruleset, ctypes.cast(buf, ctypes.c_void_p).value, len(attr), 0)
        if fd < 0:
            raise OSError(ctypes.get_errno(), 'landlock_create_ruleset failed')
        self.fd = fd

    def allow(self, path, access):
        access &= self.handled
        try:
            pfd = os.open(path, O_PATH | O_CLOEXEC)
        except OSError:
            return False
        try:
            if not stat.S_ISDIR(os.fstat(pfd).st_mode):
                access &= FS['EXECUTE'] | FS['READ_FILE'] | FS['WRITE_FILE'] | FS['TRUNCATE'] | FS['IOCTL_DEV']
            rule = struct.pack('<Qi', access, pfd)
            buf = ctypes.create_string_buffer(rule, len(rule))
            rc = _syscall(NR_landlock_add_rule, self.fd, LANDLOCK_RULE_PATH_BENEATH,
                          ctypes.cast(buf, ctypes.c_void_p).value, 0)
            if rc != 0:
                raise OSError(ctypes.get_errno(), f'landlock_add_rule failed for {path}')
        finally:
            os.close(pfd)
        return True

    def enforce(self):
        if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
        if _syscall(NR_landlock_restrict_self, self.fd, 0) != 0:
            raise OSError(ctypes.get_errno(), 'landlock_restrict_self failed')
        os.close(self.fd)


def _dedup(paths):
    seen, out = set(), []
    for p in paths:
        if not p:
            continue
        rp = os.path.realpath(p)
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def apply_jail(install_dir, *, extra_read=(), extra_execute=()):
    abi = _abi_version()
    if abi < 1:
        raise OSError('Landlock is unavailable on this kernel (ABI < 1); refusing to run the reference unconfined')
    land = Landlock(abi)

    read = FS['READ_FILE'] | FS['READ_DIR']
    read_exec = read | FS['EXECUTE']
    write = (FS['READ_FILE'] | FS['READ_DIR'] | FS['WRITE_FILE'] | FS['REMOVE_FILE'] | FS['REMOVE_DIR']
             | FS['MAKE_REG'] | FS['MAKE_DIR'] | FS['MAKE_SYM'] | FS['MAKE_SOCK'] | FS['MAKE_FIFO']
             | FS['MAKE_CHAR'] | FS['REFER'] | FS['TRUNCATE'])

    # Read-only system locations (no execute: /usr/bin, /bin, /sbin stay non-executable).
    for path in _dedup(['/usr', '/etc', '/sys', '/proc/self', '/proc/thread-self',
                        '/proc/cpuinfo', '/proc/meminfo', '/proc/stat', '/proc/uptime',
                        '/proc/sys/kernel/random/boot_id', '/tmp/.X11-unix']):
        land.allow(path, read)
    # The dynamic loader is executable; other system resources remain read-only.
    for path in _dedup(['/lib64/ld-linux-x86-64.so.2', '/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2']):
        land.allow(path, read_exec)
    # The application's own install tree: read + execute (binary, bundled ripgrep, native modules, .so's).
    land.allow(install_dir, read_exec)
    for path in _dedup(extra_read):
        land.allow(path, read)
    for path in _dedup(extra_execute):
        land.allow(path, read_exec)

    # Writable private state and exchange folders, taken from the runtime environment.
    data_dir = os.environ.get('DATA_DIR', '')
    writable = [data_dir,
                os.environ.get('TMPDIR', ''), os.environ.get('XDG_RUNTIME_DIR', ''),
                os.environ.get('XDG_CACHE_HOME', ''), os.environ.get('XDG_CONFIG_HOME', ''),
                os.environ.get('HOME', ''), os.environ.get('PBP_INBOX', ''), os.environ.get('PBP_OUTBOX', ''),
                os.environ.get('PBP_FIXTURES', ''), os.environ.get('PBP_EXPORTS', ''),
                '/dev/shm']
    for path in _dedup(writable):
        land.allow(path, write)
    # Electron uses shared memory and these devices for ordinary IPC/randomness.
    for path in ('/dev/null', '/dev/zero', '/dev/random', '/dev/urandom'):
        land.allow(path, FS['READ_FILE'] | FS['WRITE_FILE'])

    land.enforce()

