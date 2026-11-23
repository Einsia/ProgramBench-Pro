#!/usr/bin/env python3
"""Start the pinned CherryTree release binary with the task's configuration recipe and confinement.

- First start of a data directory: CherryTree's own configuration file is written with three settings that differ
  from the release defaults (no timed autosave, no start dialog, no online version check) and the embedded
  terminal's shell set to /usr/bin/true; every other setting keeps its default and the user can change these in
  Preferences.
- The process is confined with Landlock before the binary runs: it may execute only the CherryTree binary itself and
  /usr/bin/true (so code execution, the embedded terminal and external openers run nothing) and may write only in
  its data directory and the exchange folders given by the runtime. The product does not start without Landlock.
"""
import ctypes
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
BINARY = HERE / 'cherrytree' / 'usr' / 'bin' / 'cherrytree'
CONFIG = '''[misc]
autosave_on=false
show_start_dialog=false
check_version=false

[editor]
vte_shell=/usr/bin/true
'''

# Landlock ABI (linux/landlock.h)
CREATE_RULESET, ADD_RULE, RESTRICT_SELF = 444, 445, 446
RULE_PATH_BENEATH = 1
EXECUTE, WRITE_FILE, READ_FILE, READ_DIR = 1, 2, 4, 8
REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK, MAKE_FIFO, MAKE_BLOCK, MAKE_SYM = (
    1 << i for i in range(4, 13))
REFER, TRUNCATE = 1 << 13, 1 << 14


class RulesetAttr(ctypes.Structure):
    _fields_ = [('handled_access_fs', ctypes.c_uint64)]


class PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [('allowed_access', ctypes.c_uint64), ('parent_fd', ctypes.c_int32)]


def confine(writable):
    libc = ctypes.CDLL(None, use_errno=True)
    abi = libc.syscall(CREATE_RULESET, None, 0, 1)
    if abi < 1:
        raise SystemExit('Landlock is not available; the CherryTree runtime refuses to start unconfined')
    handled = (1 << 13) - 1 | (REFER if abi >= 2 else 0) | (TRUNCATE if abi >= 3 else 0)
    file_rights = EXECUTE | WRITE_FILE | READ_FILE | (TRUNCATE if abi >= 3 else 0)
    attr = RulesetAttr(handled)
    ruleset = libc.syscall(CREATE_RULESET, ctypes.byref(attr), ctypes.sizeof(attr), 0)
    if ruleset < 0:
        raise SystemExit('Landlock ruleset could not be created')

    def allow(path, access):
        try:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            return
        try:
            if not os.path.isdir(path):
                access &= file_rights
            rule = PathBeneath(access & handled, fd)
            if libc.syscall(ADD_RULE, ruleset, RULE_PATH_BENEATH, ctypes.byref(rule), 0) != 0:
                raise SystemExit(f'Landlock rule for {path} failed')
        finally:
            os.close(fd)

    # The reference image makes the executable execute-only for the product user.
    # Only desktop resources, system libraries and the instance's own files are readable.
    # In particular, solution metadata, broker state and process-memory files are not exposed.
    for path in ('/usr/lib', '/usr/lib64', '/lib', '/lib64', '/usr/share', '/etc/fonts',
                 '/etc/gtk-3.0', '/etc/xdg', '/etc/mime.types', '/etc/passwd', '/etc/group',
                 '/etc/localtime', '/etc/locale.alias', '/etc/ld.so.cache'):
        allow(os.path.realpath(path), READ_FILE | READ_DIR)
    allow(str(HERE / 'cherrytree' / 'usr' / 'share'), READ_FILE | READ_DIR)
    allow(str(BINARY), EXECUTE | READ_FILE)
    # The embedded terminal's shell is /usr/bin/true (it exits at once and runs nothing): the release aborts when
    # the terminal's shell cannot be started at all.
    allow(os.path.realpath('/usr/bin/true'), EXECUTE | READ_FILE)
    for loader in ('/lib64/ld-linux-x86-64.so.2', '/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'):
        allow(os.path.realpath(loader), EXECUTE | READ_FILE)
    allow('/dev', WRITE_FILE | READ_FILE | READ_DIR)
    changing = handled & ~EXECUTE
    for path in writable:
        allow(path, changing)
    if libc.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
        raise SystemExit('no_new_privs could not be set')
    if libc.syscall(RESTRICT_SELF, ruleset, 0) != 0:
        raise SystemExit('Landlock could not be enforced')
    os.close(ruleset)


def main():
    data = Path(os.environ['DATA_DIR']).resolve()
    config = Path(os.environ.get('XDG_CONFIG_HOME', data / 'config')) / 'cherrytree' / 'config.cfg'
    if not config.exists():
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(CONFIG)
    writable = [str(data)]
    for key in ('PBP_INBOX', 'PBP_OUTBOX'):
        value = os.environ.get(key)
        if value and os.path.isdir(value):
            writable.append(os.path.realpath(value))
    confine(writable)
    os.execv(str(BINARY), [str(BINARY), *sys.argv[1:]])


if __name__ == '__main__':
    main()
