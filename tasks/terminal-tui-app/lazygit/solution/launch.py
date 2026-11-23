#!/usr/bin/env python3
"""In-process launcher for the standard answer: the unmodified upstream lazygit release binary, run under an
isolation layer built from OS means and lazygit's own configuration (no patching of the product).

  1. A Landlock ruleset (unprivileged; inherited by every process the product starts) limits what lazygit and the
     git processes it runs can do: only the listed programs can be executed (git and its helpers, a shell and
     base64 for the clipboard command, basename/sed/uname for Git submodules, and the lazygit binary itself, which git runs as its rebase editor), and
     files can only be written below the instance's own directories. Scripts, other interpreters and repository
     hooks cannot be executed.
  2. lazygit starts in the instance's workspace (a git repository) with a root-owned, read-only system
     configuration (the installed lazygitconf/config.yml): no first-run popups, no update check, no background network work,
     and every key that would start an editor, a shell, an opener, a diff tool or a browser is disabled.

The runtime supplies the git determinism variables (GIT_*); they are passed through unchanged. lazygit keeps its
own state file under DATA_DIR/.lazygit (CONFIG_DIR), so it survives a restart with the same DATA_DIR.
"""
from __future__ import annotations

import ctypes
import json
import os
import stat
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAZYGIT = HERE / 'lazygit'
SYSTEM_CONFIG = str(HERE / 'lazygitconf' / 'config.yml')
PASS_ENV = ('HOME', 'USER', 'LOGNAME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'LANG', 'LC_ALL', 'TZ', 'TERM',
            'COLUMNS', 'LINES')
PRIVATE_DIRS = ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME')

# Landlock filesystem access rights (linux/landlock.h).
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
    """Restrict this process and everything it starts to `rules`, a list of (path, rights); an absent path is skipped."""
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


def ruleset(data):
    """Read access to the system, execute access to the allow-listed programs, write access to the instance only."""
    rules = [('/etc', READ), ('/proc', READ), ('/sys', READ), ('/usr/lib', READ), ('/usr/share', READ),
             ('/lib', READ), ('/lib64', READ), ('/dev', READ | WRITE_FILE),
             ('/usr/lib/git-core', READ | EXECUTE),
             ('/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', READ_FILE | EXECUTE),
             ('/usr/bin/git', READ_FILE | EXECUTE), ('/usr/bin/bash', READ_FILE | EXECUTE),
             ('/usr/bin/dash', READ_FILE | EXECUTE), ('/usr/bin/base64', READ_FILE | EXECUTE),
             ('/usr/bin/basename', READ_FILE | EXECUTE), ('/usr/bin/sed', READ_FILE | EXECUTE),
             ('/usr/bin/uname', READ_FILE | EXECUTE),
             (str(LAZYGIT), READ_FILE | EXECUTE), (SYSTEM_CONFIG, READ_FILE), (str(data), WRITE)]
    rules += [(os.environ[name], WRITE) for name in PRIVATE_DIRS if os.environ.get(name)]
    return rules


def main():
    data = Path(os.environ['DATA_DIR']).resolve()
    workspace = data / 'workspace'
    state = data / '.lazygit'
    workspace.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    env = {name: os.environ[name] for name in PASS_ENV if name in os.environ}
    env.update({name: value for name, value in os.environ.items() if name.startswith('GIT_')})
    env.update(PATH='/usr/local/bin:/usr/bin:/bin', SHELL='/bin/bash', LG_CONFIG_FILE=SYSTEM_CONFIG,
               CONFIG_DIR=str(state))
    # One-shot command-line mode for the runtime's cli channel: PBP_CLI_ARGS is a JSON array of options. The same
    # isolation applies.
    extra = os.environ.get('PBP_CLI_ARGS')
    args = json.loads(extra) if extra else []
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        sys.exit('PBP_CLI_ARGS must be a JSON array of strings')
    for directory, _dirs, files in os.walk(data, followlinks=False):
        if any(name in files for name in ("lazygit.yml", ".lazygit.yml")):
            raise RuntimeError("repository configuration files are not available in this environment")
    confine(ruleset(data))
    os.chdir(workspace)
    os.execve(str(LAZYGIT), [str(LAZYGIT)] + args, env)


if __name__ == '__main__':
    main()
