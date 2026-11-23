#!/usr/bin/env python3
"""Process sandbox for Taskwarrior and taskwarrior-tui, separate from the upstream programs.

usage: python3 -I sandbox.py PROGRAM [ARGUMENT ...]

Restricts this process with an unprivileged Landlock ruleset and then executes PROGRAM, which must be one of the two
programs of this directory (bin/taskwarrior-tui or bin/task). The ruleset is inherited by every process the program
starts. Allowed: executing those two programs (and the dynamic loader they need); reading the system configuration,
shared libraries, time zone data and the runtime's clock library; reading and writing the instance directories the
runtime supplies (DATA_DIR, HOME, TMPDIR, XDG_CACHE_HOME, XDG_CONFIG_HOME); using the terminal devices. Everything
else is refused by the kernel, so the product features that would start other programs (the shell prompt, the
external editor, shortcut scripts, background processes, hooks, Taskwarrior's execute command) cannot run anything.
Without Landlock support the sandbox refuses to start the program.
"""
import ctypes
import os
import stat
import struct
import sys
import shutil
import tempfile

HERE = os.path.dirname(os.path.realpath(__file__))
PROGRAMS = (os.path.join(HERE, 'bin', 'taskwarrior-tui'), os.path.join(HERE, 'bin', 'task'))
(EXECUTE, WRITE_FILE, READ_FILE, READ_DIR, REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK,
 MAKE_FIFO, MAKE_BLOCK, MAKE_SYM, REFER, TRUNCATE) = (1 << n for n in range(15))
READ = READ_FILE | READ_DIR
WRITE = READ | WRITE_FILE | REMOVE_DIR | REMOVE_FILE | MAKE_DIR | MAKE_REG | MAKE_SYM | MAKE_FIFO | REFER | TRUNCATE
FILE_RIGHTS = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE
CREATE_RULESET, ADD_RULE, RESTRICT_SELF = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
RULE_PATH_BENEATH = 1

libc = ctypes.CDLL(None, use_errno=True)
libc.syscall.restype = ctypes.c_long


def syscall(number, *args):
    result = libc.syscall(number, *args)
    if result < 0:
        raise OSError(ctypes.get_errno(), f'Landlock system call {number} failed')
    return result


def buffer(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def executable_copies():
    """Use execute-only instance copies while keeping the installed files immutable."""
    cache = os.path.join(os.environ['TMPDIR'], 'application-programs')
    os.makedirs(cache, mode=0o700, exist_ok=True)
    copies = []
    for source in PROGRAMS:
        target = os.path.join(cache, os.path.basename(source))
        try:
            info = os.lstat(target)
        except FileNotFoundError:
            fd, pending = tempfile.mkstemp(dir=cache)
            try:
                with os.fdopen(fd, 'wb') as output, open(source, 'rb') as original:
                    shutil.copyfileobj(original, output)
                    output.flush()
                    os.fchmod(output.fileno(), 0o111)
                os.replace(pending, target)
            finally:
                if os.path.lexists(pending):
                    os.unlink(pending)
        else:
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o111 or info.st_size != os.stat(source).st_size:
                raise OSError('invalid application program cache')
        copies.append(target)
    return tuple(copies)


def rules(programs):
    system = ['/etc', '/usr/lib/x86_64-linux-gnu', '/usr/share/zoneinfo', '/usr/local/lib/faketime']
    result = [(path, READ) for path in system]
    result.append(('/dev', READ | WRITE_FILE))
    instance = [os.environ.get(name) for name in ('DATA_DIR', 'HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME')]
    result += [(path, WRITE) for path in instance if path]
    loader = os.path.realpath('/lib64/ld-linux-x86-64.so.2')
    result.append((loader, READ_FILE | EXECUTE))
    result += [(path, READ_FILE | EXECUTE) for path in programs]
    return result


def confine(programs):
    abi = syscall(CREATE_RULESET, None, 0, 1)
    handled = (1 << 13) - 1
    if abi >= 2:
        handled |= REFER
    if abi >= 3:
        handled |= TRUNCATE
    ruleset = syscall(CREATE_RULESET, buffer(struct.pack('<Q', handled)), 8, 0)
    for path, rights in rules(programs):
        try:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            continue
        try:
            allowed = rights & handled
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                allowed &= FILE_RIGHTS
            syscall(ADD_RULE, ruleset, RULE_PATH_BENEATH, buffer(struct.pack('<Qi', allowed, fd)), 0)
        finally:
            os.close(fd)
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
    syscall(RESTRICT_SELF, ruleset, 0)
    os.close(ruleset)


def main(argv):
    if not argv or os.path.realpath(argv[0]) not in PROGRAMS:
        sys.exit('usage: sandbox.py PROGRAM [ARGUMENT ...] (PROGRAM: bin/taskwarrior-tui or bin/task)')
    try:
        programs = executable_copies()
        program = programs[PROGRAMS.index(os.path.realpath(argv[0]))]
        os.environ['TASKWARRIOR_TUI_TASKWARRIOR_CLI'] = programs[1]
        confine(programs)
    except OSError as exc:
        sys.exit(f'sandbox: Landlock is not available ({exc}); refusing to start the program')
    os.execv(program, [program, *argv[1:]])


if __name__ == '__main__':
    main(sys.argv[1:])
