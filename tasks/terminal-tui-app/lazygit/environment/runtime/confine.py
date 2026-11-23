#!/usr/bin/env python3
'''Run one program under an unprivileged Landlock ruleset (helper of the runtime git channels).

usage: confine.py [--read PATH] [--write PATH] [--exec PATH] ... -- PROGRAM [ARGUMENT ...]

The program can read the system directories and the --read and --write paths, execute git and the few system programs
its helper scripts use (and the --exec paths), and create or change files only below the --write paths. The ruleset is
inherited by every process the program starts: scripts and other interpreters cannot be executed, and nothing can be
written outside the instance.
'''
import ctypes
import os
import stat
import struct
import sys

(EXECUTE, WRITE_FILE, READ_FILE, READ_DIR, REMOVE_DIR, REMOVE_FILE, MAKE_CHAR, MAKE_DIR, MAKE_REG, MAKE_SOCK,
 MAKE_FIFO, MAKE_BLOCK, MAKE_SYM, REFER, TRUNCATE) = (1 << n for n in range(15))
READ = READ_FILE | READ_DIR
WRITE = READ | WRITE_FILE | REMOVE_DIR | REMOVE_FILE | MAKE_DIR | MAKE_REG | MAKE_SYM | MAKE_FIFO | REFER | TRUNCATE
FILE_RIGHTS = EXECUTE | WRITE_FILE | READ_FILE | TRUNCATE
SYS_CREATE, SYS_ADD_RULE, SYS_RESTRICT = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
RULE_PATH_BENEATH = 1

_libc = ctypes.CDLL(None, use_errno=True)
_libc.syscall.restype = ctypes.c_long


def _call(number, *args):
    result = _libc.syscall(number, *args)
    if result < 0:
        raise OSError(ctypes.get_errno(), 'landlock syscall %d failed' % number)
    return result


def _buffer(data):
    return (ctypes.c_char * len(data)).from_buffer_copy(data)


def confine(rules):
    '''Restrict this process and everything it starts to rules, a list of (path, rights); an absent path is skipped.'''
    abi = _call(SYS_CREATE, None, 0, 1)
    handled = (1 << 13) - 1
    if abi >= 2:
        handled |= REFER
    if abi >= 3:
        handled |= TRUNCATE
    ruleset = _call(SYS_CREATE, _buffer(struct.pack('<Q', handled)), 8, 0)
    for path, rights in rules:
        try:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
        except OSError:
            continue
        try:
            rights &= handled
            if not stat.S_ISDIR(os.fstat(fd).st_mode):
                rights &= FILE_RIGHTS
            _call(SYS_ADD_RULE, ruleset, RULE_PATH_BENEATH, _buffer(struct.pack('<Qi', rights, fd)), 0)
        finally:
            os.close(fd)
    if _libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'prctl(PR_SET_NO_NEW_PRIVS) failed')
    _call(SYS_RESTRICT, ruleset, 0)
    os.close(ruleset)


def system_rules():
    rules = [(path, READ) for path in ('/etc', '/proc', '/sys', '/usr/lib', '/usr/share', '/lib', '/lib64', '/usr/lib64')]
    rules.append(('/dev', READ | WRITE_FILE))
    rules.append(('/usr/lib/git-core', READ | EXECUTE))
    rules.append(('/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', READ_FILE | EXECUTE))
    rules.append(('/usr/bin/git', READ_FILE | EXECUTE))
    return rules


def main(argv):
    usage = 'usage: confine.py [--read PATH] [--write PATH] [--exec PATH] -- PROGRAM [ARGUMENT ...]'
    args = list(argv)
    reads, writes, execs = [], [], []
    targets = {'--read': reads, '--write': writes, '--exec': execs}
    while args and args[0] != '--':
        option = args.pop(0)
        if option not in targets or not args:
            sys.exit(usage)
        targets[option].append(args.pop(0))
    if len(args) < 2:
        sys.exit(usage)
    command = args[1:]
    rules = system_rules() + [(p, READ) for p in reads] + [(p, WRITE) for p in writes]
    rules += [(p, READ | EXECUTE) for p in execs]
    confine(rules)
    os.execv(command[0], command)


if __name__ == '__main__':
    main(sys.argv[1:])
