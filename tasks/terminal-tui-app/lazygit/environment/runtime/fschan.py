'''Workspace, state and command-line channels of the lazygit black-box runtime (terminal surface).

All of them are for preparation and checking only, and reach nothing that lazygit itself does not have:

- workspace: a read-only inspector of the instance workspace (the working tree lazygit shows): list one directory,
  tree (recursive), stat one entry or read a regular file. Symlinks are reported with their target and never
  followed. Git directories (.git) are not part of the listing; the git channel reads repository state.
- state: lazygit own persistent state file (recent repositories, the version it last ran);
- cli: the product run once with one documented command-line option that prints and exits.

place writes setup input files into the workspace while the application is stopped (the files step of the setup channel).
'''
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import gitchan
import safe_fs
import blackbox_runtime as runtime
from workspace_links import link_text, validate_links

ORIGIN = gitchan.ORIGIN
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20000
MAX_PLACED = 512
CLI_TIMEOUT = 20
CLI_OPTIONS = ('--version', '--help', '--config', '--print-config-dir')
MODE = re.compile('[0-7]{3,4}')


# -- workspace inspector ---------------------------------------------------------------------------------------
def parts_of(value, field='path'):
    parts = gitchan.components(value, field)
    if '.git' in parts:
        raise ValueError('%s: the .git directory is not part of the workspace listing; use the git op' % field)
    return parts








def inspect_workspace(workspace, data, uid=None):
    try:
        return safe_fs.snapshot(workspace, parts_of(data.get('path', ORIGIN)), data.get('action', 'list'),
                                origin=ORIGIN, max_read=MAX_FILE_BYTES, max_hash=MAX_HASH_BYTES,
                                max_entries=MAX_TREE_ENTRIES, uid=uid, excluded=('.git',))
    except FileNotFoundError:
        raise ValueError('no such entry in the workspace') from None



def symlink_inside(name, target):
    """Validate link syntax; place validates resolved targets against the whole tree."""
    gitchan.components(name, 'file path')
    return link_text(target)


def check_files(files):
    if not isinstance(files, dict):
        raise ValueError('files must be an object of path -> content')
    if len(files) > MAX_PLACED:
        raise ValueError('at most %d files can be placed at once' % MAX_PLACED)
    for name, value in files.items():
        if not gitchan.components(name, 'file path'):
            raise ValueError('a placed file needs a path below the workspace')
        if value is None or isinstance(value, str):
            continue
        kinds = [k for k in ('text', 'base64', 'symlink') if isinstance(value, dict) and k in value]
        if len(kinds) != 1 or set(value) - {'text', 'base64', 'symlink', 'mode'}:
            raise ValueError('a placed file is text, an object with one of text, base64 or symlink (and optionally '
                             'mode), or null for a directory')
        kind = kinds[0]
        if kind == 'symlink':
            if 'mode' in value:
                raise ValueError('a symlink has no mode')
            if not symlink_inside(name, value['symlink']):
                raise ValueError('symlink target must resolve inside ' + ORIGIN)
        elif kind == 'text':
            if not isinstance(value['text'], str):
                raise ValueError('text must be a string')
        else:
            try:
                base64.b64decode(value['base64'], validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise ValueError('base64 content is not valid base64') from None
        if 'mode' in value and not (isinstance(value['mode'], str) and MODE.fullmatch(value['mode'])):
            raise ValueError('mode is an octal string such as 644 or 755')


def place(workspace, files, account=None):
    """Place user files through workspace descriptors after link validation."""
    validate_links(workspace, files)
    safe_fs.place(workspace, files, gitchan.components,
                  uid=account.pw_uid if account else os.geteuid(),
                  gid=account.pw_gid if account else os.getegid(), replace_symlinks=True)


def read_state(data, uid=None):
    try:
        content = safe_fs.read(data, '.lazygit/state.yml', limit=MAX_FILE_BYTES, uid=uid)
    except FileNotFoundError:
        return {'file': 'state.yml', 'exists': False, 'text': ''}
    return {'file': 'state.yml', 'exists': True, 'text': content.decode('utf-8', 'replace')}


# -- restricted command-line channel ---------------------------------------------------------------------------
def run_cli(launcher, env, option, workspace, account=None):
    '''Run the product once with one documented option, confined to the instance, and return its output.'''
    if option not in CLI_OPTIONS:
        raise ValueError('option must be one of: ' + ', '.join(CLI_OPTIONS))
    launcher = Path(launcher)
    if not launcher.is_file():
        raise ValueError('the solution has no launcher to run command-line options')
    env = dict(env)
    env['PBP_CLI_ARGS'] = json.dumps([option])
    kwargs = {}
    if account is not None:
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    try:
        done = subprocess.run([sys.executable, '-I', '-B', str(launcher)], env=env, cwd=str(workspace),
                              stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=CLI_TIMEOUT, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError('the command-line run did not finish in time') from None
    return {'option': option, 'exit_code': done.returncode,
            'stdout': done.stdout.decode('utf-8', 'replace')[:MAX_FILE_BYTES]}
