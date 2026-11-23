#!/usr/bin/env python3
"""Launch the pinned Xournal++ binary in a Landlock sandbox (reference launcher, not part of Xournal++).

Xournal++ can run commands that a user types into its preferences (the LaTeX
generator and editor commands, the touchscreen enable/disable commands). The
reference installation therefore runs the unmodified product in a kernel sandbox that
it cannot leave:

- no program may be executed except the Xournal++ binary itself (and its ELF
  loader), so every such command fails inside the product;
- files may only be created, written, renamed or removed in the instance
  directories (DATA_DIR and the HOME, TMPDIR and XDG directories), the desktop
  session's runtime directory and the exchange folders (PBP_INBOX, PBP_OUTBOX);
- no TCP connection may be opened or accepted.

Reading is not restricted. When the kernel offers no Landlock support the
product starts unconfined, unless the marker file below exists (the reference
image creates it): then the launcher refuses to start.

Usage: sandbox.py BINARY [ARG...]
"""
import ctypes
import os
from pathlib import Path
import sys

REQUIRED_MARKER = '/etc/xournal-reference-sandbox'
SYS_CREATE_RULESET, SYS_ADD_RULE, SYS_RESTRICT_SELF = 444, 445, 446  # x86_64
CREATE_RULESET_VERSION = 1
RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38

EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1 << 0, 1 << 1, 1 << 2, 1 << 3
REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR = 1 << 4, 1 << 5, 1 << 6, 1 << 7
MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = 1 << 8, 1 << 9, 1 << 10, 1 << 11, 1 << 12
REFER, TRUNCATE = 1 << 13, 1 << 14
NET_BIND_TCP, NET_CONNECT_TCP = 1 << 0, 1 << 1


class RulesetAttr(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64), ('handled_access_net', ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


def fail(message):
    sys.stderr.write(f'sandbox: {message}\n')
    raise SystemExit(1)


def confine(binary):
    """Restrict this process (and everything it executes) as described above; returns the Landlock ABI."""
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    abi = libc.syscall(SYS_CREATE_RULESET, None, ctypes.c_size_t(0), ctypes.c_uint32(CREATE_RULESET_VERSION))
    if abi < 1:
        raise OSError(ctypes.get_errno(), 'Landlock is not available')
    writes = (WRITE_FILE | REMOVE_DIR | REMOVE_FILE | MAKE_CHAR | MAKE_DIR | MAKE_REG | MAKE_SOCK | MAKE_FIFO
              | MAKE_BLOCK | MAKE_SYM | (REFER if abi >= 2 else 0) | (TRUNCATE if abi >= 3 else 0))
    attr = RulesetAttr(EXECUTE | writes, (NET_BIND_TCP | NET_CONNECT_TCP) if abi >= 4 else 0)
    size = ctypes.sizeof(RulesetAttr) if abi >= 4 else ctypes.sizeof(ctypes.c_uint64)
    ruleset = libc.syscall(SYS_CREATE_RULESET, ctypes.byref(attr), ctypes.c_size_t(size), ctypes.c_uint32(0))
    if ruleset < 0:
        raise OSError(ctypes.get_errno(), 'landlock_create_ruleset')

    def allow(path, access):
        try:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            return
        try:
            rule = PathBeneathAttr(access, fd)
            if libc.syscall(SYS_ADD_RULE, ctypes.c_int(ruleset), ctypes.c_int(RULE_PATH_BENEATH),
                            ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
                raise OSError(ctypes.get_errno(), f'landlock_add_rule {path}')
        finally:
            os.close(fd)

    file_writes = WRITE_FILE | (TRUNCATE if abi >= 3 else 0)
    # The product binary and its ELF loader are the only executables.
    allow(binary, EXECUTE)
    allow(os.path.realpath('/lib64/ld-linux-x86-64.so.2'), EXECUTE)
    roots = {os.environ.get(name) for name in ('DATA_DIR', 'HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
                                               'XDG_DATA_HOME', 'XDG_RUNTIME_DIR', 'PBP_INBOX', 'PBP_OUTBOX')}
    for root in sorted(r for r in roots if r and os.path.isabs(r) and os.path.isdir(r)):
        allow(root, writes)
    # Character devices such as /dev/null may be opened for writing; nothing can be created there.
    allow('/dev', file_writes)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS)')
    if libc.syscall(SYS_RESTRICT_SELF, ctypes.c_int(ruleset), ctypes.c_uint32(0)) != 0:
        raise OSError(ctypes.get_errno(), 'landlock_restrict_self')
    os.close(ruleset)
    return abi


def main(argv):
    if not argv:
        fail('usage: sandbox.py BINARY [ARG...]')
    binary = os.path.realpath(argv[0])
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        fail(f'{Path(argv[0]).name} is not an executable file')
    try:
        confine(binary)
    except OSError as exc:
        if os.path.exists(REQUIRED_MARKER):
            fail(f'the product sandbox could not be set up ({exc}); refusing to start')
        sys.stderr.write(f'sandbox: running without Landlock ({exc})\n')
    guard = Path(__file__).resolve().parent / 'exec_guard.so'
    if not guard.is_file():
        fail('the external-program guard is missing')
    os.environ['LD_PRELOAD'] = str(guard) + (':' + os.environ['LD_PRELOAD'] if os.environ.get('LD_PRELOAD') else '')
    os.execv(binary, [binary, *argv[1:]])


if __name__ == '__main__':
    main(sys.argv[1:])
