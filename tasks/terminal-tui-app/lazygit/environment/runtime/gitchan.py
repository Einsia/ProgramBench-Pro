'''Git channels of the lazygit black-box runtime (terminal surface).

git is the back end of lazygit, so the repository is the observable state of the product. Two non-GUI channels
reach it, both for preparation and checking only:

- read_git: one read-only git command (an allow-listed subcommand with allow-listed flags), run in the workspace
  repository or in a repository below it;
- apply: setup input preparation while the application is stopped (files, local bare remotes, allow-listed git steps).

Every git process runs as the product user under the Landlock helper (confine.py): it can write only below the
instance directories and cannot execute scripts or repository hooks. It gets the same neutralising and determinism
environment as the product (git_env), so hooks, global configuration and prompts never take part.
'''
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
import blackbox_runtime as runtime

ORIGIN = '/workspace'
HERE = Path(__file__).resolve().parent
CONFINE = HERE / 'confine.py'
GIT = '/usr/bin/git'
MAX_OUTPUT = 1024 * 1024
MAX_ARGS = 64
MAX_ARG = 4096
MAX_STEPS = 200
GIT_TIMEOUT = 40
BASE_TIME = 1704110400  # 2024-01-01T12:00:00Z
STEP_SECONDS = 60
HIDDEN = ('.git', 'lazygit.yml', '.lazygit.yml')
REMOTE_NAME = re.compile('[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
IDENTITY = (('NAME', 'Ada Lovelace'), ('EMAIL', 'ada@example.com'))
CONFIG = (('core.hooksPath', '/nonexistent'), ('core.fsmonitor', 'false'), ('protocol.file.allow', 'always'),
          ('protocol.ext.allow', 'never'), ('init.defaultBranch', 'main'), ('commit.gpgsign', 'false'),
          ('tag.gpgsign', 'false'))

READ_PLAIN = ('log', 'show', 'diff', 'status', 'blame', 'describe', 'rev-parse', 'rev-list', 'ls-files', 'ls-tree',
              'cat-file', 'for-each-ref', 'merge-base', 'name-rev', 'shortlog', 'show-ref', 'count-objects',
              'diff-tree', 'diff-files', 'diff-index')
# subcommand -> (allowed first arguments, may be called without one)
READ_SUB = {'stash': (('list', 'show'), False), 'worktree': (('list',), False), 'submodule': (('status',), False), 'bisect': (('log',), False),
            'reflog': (('show',), True), 'remote': (('-v', 'get-url'), True)}
LISTING = {'branch': ('-a', '-r', '-v', '-vv', '--all', '--remotes', '--list', '-l', '--show-current', '--contains',
                      '--no-contains', '--merged', '--no-merged', '--points-at', '--format', '--sort', '--verbose',
                      '--abbrev', '--no-abbrev'),
           'tag': ('-l', '--list', '-n', '--contains', '--no-contains', '--merged', '--no-merged', '--points-at',
                   '--format', '--sort')}
LIST_MODE = ('--list', '-l', '--contains', '--no-contains', '--merged', '--no-merged', '--points-at')
CONFIG_GETTERS = ('--get', '--get-all', '--get-regexp', '--list', '-l')
CONFIG_FLAGS = CONFIG_GETTERS + ('--local', '--null', '-z', '--name-only')
DENIED = ('--output', '--ext-diff', '--textconv', '--git-dir', '--work-tree', '--exec-path', '--upload-pack',
          '--receive-pack', '--open-files-in-pager', '--exec', '--no-index', '--contents', '--ignore-revs-file',
          '--exclude-from', '--exclude-per-directory', '-X', '--paginate', '--config-env')
LONG_DENIED = tuple(flag for flag in DENIED if flag.startswith('--'))
# Short read options that name a file to read (-O orderfile, -X exclude file); blame's -S also reads a file.
SHORT_DENIED = 'OX'


def _options(spec):
    '''"-q --quiet -m= --track?" -> {option: kind}; = takes a value, ? takes an optional value after =.'''
    table = {}
    for word in spec.split():
        if word.endswith('='):
            table[word[:-1]] = 'value'
        elif word.endswith('?'):
            table[word[:-1]] = 'optional'
        else:
            table[word] = 'flag'
    return table


# Setup steps: each subcommand accepts only the options listed here, spelled out in full (git's abbreviations of long
# options are not accepted) and one short option per argument. None of them runs a program or names a configuration.
SETUP_OPTIONS = {name: _options(spec) for name, spec in {
    'init': '-q --quiet -b= --initial-branch= --bare',
    'clone': '-q --quiet -b= --branch= --bare --no-checkout -n --origin= -o= --single-branch --no-tags',
    'add': '-A --all -u --update -f --force -N --intent-to-add --chmod=',
    'rm': '-q --quiet -r -f --force --cached',
    'mv': '-f --force -k',
    'commit': '-q --quiet -m= --message= -a --all --allow-empty --allow-empty-message --amend --no-edit --author= '
              '--date= --fixup= --squash= -n --no-verify -s --signoff --reset-author -C= --reuse-message=',
    'branch': '-q --quiet -f --force -d -D --delete -m -M --move -c -C --copy -u= --set-upstream-to= --unset-upstream '
              '--track? --no-track',
    'checkout': '-q --quiet -b= -B= -f --force --detach --orphan= -t --track? --no-track -m --merge --ours --theirs',
    'switch': '-q --quiet -c= --create= -C= --force-create= -d --detach --orphan= -f --force --discard-changes -t '
              '--track? --no-track',
    'restore': '-q --quiet -S --staged -W --worktree -s= --source= --ours --theirs',
    'tag': '-a --annotate -m= --message= -f --force -d --delete',
    'merge': '-q --quiet --no-ff --ff --ff-only --squash --no-squash --commit --no-commit -m= --no-edit --abort '
             '--continue --quit --allow-unrelated-histories',
    'stash': '-q --quiet -m= --message= -u --include-untracked -a --all -k --keep-index --no-keep-index -S --staged '
             '--index',
    'reset': '-q --quiet --hard --soft --mixed --merge --keep',
    'cherry-pick': '-n --no-commit -x -m= --mainline= --allow-empty --continue --abort --skip --quit --ff',
    'revert': '-n --no-commit --no-edit -m= --mainline= --continue --abort --skip --quit',
    'rebase': '-q --quiet --onto= --continue --abort --skip --quit --autosquash --no-autosquash --keep-base --root -f '
              '--force-rebase --no-ff --update-refs --no-update-refs',
    'remote': '-f -t= -m= --tags --no-tags --push --add --delete -a --auto -d',
    'submodule': '-q --quiet -b= --branch= -f --force --name= --init --recursive -N --no-fetch --remote --checkout '
                 '--merge --rebase --all',
    'worktree': '-q --quiet -b= -B= -f --force --detach --no-checkout --checkout --lock --reason= --track --no-track '
                '--guess-remote --no-guess-remote',
    'fetch': '-q --quiet --all -p --prune -t --tags -n --no-tags -f --force',
    'push': '-q --quiet -u --set-upstream -f --force --force-with-lease? --tags --all -d --delete --no-verify '
            '--follow-tags --prune -n --dry-run',
    'pull': '-q --quiet -r --rebase? --no-rebase --ff --no-ff --ff-only --squash --no-commit --autostash '
            '--no-autostash --no-edit -t --tags -p --prune',
}.items()}
SETUP_COMMANDS = tuple(SETUP_OPTIONS)
# Subcommands of the setup commands that take one; a stash step may omit it (push).
SETUP_SUBCOMMANDS = {'stash': ('push', 'save', 'pop', 'apply', 'drop', 'clear', 'branch'),
                     'remote': ('add', 'remove', 'rm', 'rename', 'set-url', 'set-head'),
                     'submodule': ('add', 'init', 'update', 'deinit', 'status', 'sync', 'set-url', 'set-branch',
                                   'absorbgitdirs'),
                     'worktree': ('add', 'remove', 'move', 'prune', 'lock', 'unlock', 'repair')}
# Commands whose repository or URL arguments may only be relative paths, remote names or @remotes/NAME.
LOCAL_ONLY = ('clone', 'remote', 'submodule', 'fetch', 'push', 'pull', 'worktree')


def allowed_read():
    return sorted(set(READ_PLAIN) | set(READ_SUB) | set(LISTING) | {'config'})


# -- environment -----------------------------------------------------------------------------------------------
def git_env(when=None):
    '''The neutralising and determinism environment of every git process: the runtime gives it to the product (and
    so to the git commands lazygit runs) and to its own git channels.'''
    env = {}
    for who in ('AUTHOR', 'COMMITTER'):
        for field, value in IDENTITY:
            env['GIT_%s_%s' % (who, field)] = value
    stamp = '%d +0000' % (BASE_TIME if when is None else when)
    env.update(GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp, GIT_CONFIG_GLOBAL='/dev/null',
               GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT=str(len(CONFIG)))
    for index, (key, value) in enumerate(CONFIG):
        env['GIT_CONFIG_KEY_%d' % index] = key
        env['GIT_CONFIG_VALUE_%d' % index] = value
    return env


def command_env(base, when=None):
    env = {key: base[key] for key in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'USER', 'LOGNAME')
           if key in base}
    env.update(PATH='/usr/bin:/bin', LANG='C.UTF-8', LC_ALL='C.UTF-8', TZ='UTC', GIT_PAGER='cat', PAGER='cat',
               GIT_EDITOR=':', GIT_SEQUENCE_EDITOR=':', GIT_MERGE_AUTOEDIT='no')
    env.update(git_env(when))
    return env


# -- paths and arguments ---------------------------------------------------------------------------------------
def printable(value, field, limit):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('%s must be printable text of at most %d characters' % (field, limit))
    return value


def components(value, field='path'):
    value = printable(value, field, 4096)
    if value in ('', '.', ORIGIN):
        return []
    if value.startswith(ORIGIN + '/'):
        value = value[len(ORIGIN) + 1:]
    if value.startswith('/') or chr(92) in value:
        raise ValueError('%s must stay inside %s' % (field, ORIGIN))
    parts = [part for part in value.split('/') if part not in ('', '.')]
    if any(part == '..' for part in parts):
        raise ValueError('%s must stay inside %s' % (field, ORIGIN))
    if any(len(part.encode('utf-8')) > 255 for part in parts):
        raise ValueError('%s has a component longer than 255 bytes' % field)
    return parts


def locate(workspace, value, field='repo'):
    path = Path(workspace)
    for part in components(value, field):
        path = path / part
        if part == '.git' or path.is_symlink() or not path.is_dir():
            raise ValueError('%s must name a directory of the workspace' % field)
    return path


def arguments(value, field='argv'):
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_ARGS:
        raise ValueError('%s must list 1-%d strings' % (field, MAX_ARGS))
    return [printable(item, field + ' item', MAX_ARG) for item in value]


def split_arguments(rest):
    flags, positional, literal = [], [], False
    for item in rest:
        if literal:
            positional.append(item)
        elif item == '--':
            literal = True
        elif item.startswith('-') and item != '-':
            flags.append(item)
        else:
            positional.append(item)
    return flags, positional


def denied_read_flag(name, flag):
    '''Whether a read flag could reach a denied option: git also accepts any unambiguous prefix of a long option, so a
    long flag that is a prefix of a denied option is refused, and short-option groups are checked letter by letter.'''
    base = flag.split('=', 1)[0]
    if base.startswith('--'):
        return any(denied.startswith(base) for denied in LONG_DENIED)
    letters = base[1:]
    return any(c in letters for c in SHORT_DENIED) or (name == 'blame' and 'S' in letters)


def check_read(argv):
    argv = arguments(argv)
    name, rest = argv[0], argv[1:]
    flags, positional = split_arguments(rest)
    for flag in flags:
        if denied_read_flag(name, flag):
            raise ValueError('the flag %s is not available through the git channel' % flag.split('=', 1)[0])
    if name in READ_PLAIN:
        return argv
    if name in READ_SUB:
        allowed, bare = READ_SUB[name]
        if (rest and rest[0] in allowed) or (not rest and bare):
            return argv
        raise ValueError('git %s takes %s' % (name, ' or '.join(allowed) + (' or nothing' if bare else '')))
    if name in LISTING:
        for flag in flags:
            if flag.split('=', 1)[0] not in LISTING[name]:
                raise ValueError('git %s accepts only listing flags: %s' % (name, ' '.join(LISTING[name])))
        if positional and not any(flag.split('=', 1)[0] in LIST_MODE for flag in flags):
            raise ValueError('git %s with arguments needs --list or a listing filter such as --contains' % name)
        return argv
    if name == 'config':
        names = [flag.split('=', 1)[0] for flag in flags]
        if not any(n in CONFIG_GETTERS for n in names) or any(n not in CONFIG_FLAGS for n in names):
            raise ValueError('git config is read-only here: use --get, --get-all, --get-regexp or --list')
        return argv
    raise ValueError('git %s is not available through the git channel; use one of: %s'
                     % (name, ', '.join(allowed_read())))


def setup_positionals(name, rest):
    '''Validate the options of one setup command against its allow-list and return its other arguments.'''
    table, positional, literal, index = SETUP_OPTIONS[name], [], False, 0
    while index < len(rest):
        item = rest[index]
        index += 1
        if literal or item == '-' or not item.startswith('-'):
            positional.append(item)
            continue
        if item == '--':
            literal = True
            continue
        key, equals, _ = item.partition('=')
        kind = table.get(key)
        if kind is None or (not key.startswith('--') and (equals or len(key) != 2)):
            raise ValueError('git %s in setup accepts only these options, in full and one per argument: %s'
                             % (name, ' '.join(sorted(table))))
        if equals and kind == 'flag':
            raise ValueError('the option %s takes no value' % key)
        if kind == 'value' and not equals:
            if index >= len(rest) or rest[index].startswith('-'):
                raise ValueError('the option %s needs a value' % key)
            index += 1
    return positional


def check_setup(argv):
    argv = arguments(argv)
    name, rest = argv[0], argv[1:]
    if name not in SETUP_COMMANDS:
        raise ValueError('git %s is not available in setup; use one of: %s' % (name, ', '.join(SETUP_COMMANDS)))
    positional = setup_positionals(name, rest)
    if name in SETUP_SUBCOMMANDS:
        allowed = SETUP_SUBCOMMANDS[name]
        if positional and positional[0] not in allowed or (not positional and name != 'stash'):
            raise ValueError('git %s in setup takes one of the subcommands: %s' % (name, ', '.join(allowed)))
    if name in LOCAL_ONLY:
        for number, item in enumerate(positional):
            remote_side = name in ('fetch', 'push', 'pull') and number > 0
            if item.startswith('/') or '::' in item or '://' in item or (':' in item and not remote_side):
                raise ValueError('git %s in setup takes relative paths, remote names and @remotes/NAME, not '
                                 'absolute paths or URLs' % name)
    for item in rest:
        if item.rstrip('/').rsplit('/', 1)[-1] in HIDDEN[1:]:
            raise ValueError('lazygit configuration files cannot be created in setup')
    return argv


def expand(argv, data):
    '''Replace the whole-argument token @remotes/NAME with the path of a local bare remote below the data directory.'''
    out = []
    for item in argv:
        if item.startswith('@remotes/'):
            name = item[len('@remotes/'):]
            if not REMOTE_NAME.fullmatch(name):
                raise ValueError('remote names use letters, digits, dot, underscore and dash')
            item = str(Path(data) / 'remotes' / (name + '.git'))
        out.append(item)
    return out


def refuse_hidden(files):
    if not isinstance(files, dict):
        raise ValueError('files must be an object of path -> content')
    for name in files:
        if any(part in HIDDEN for part in components(name, 'file path')):
            raise ValueError('files named .git, lazygit.yml or .lazygit.yml cannot be placed')


def check_step(step):
    if not isinstance(step, dict):
        raise ValueError('each setup step must be an object')
    actions = [key for key in ('files', 'git', 'bare') if key in step]
    if sorted(set(step) - {'files', 'git', 'bare', 'repo', 'date'}) or len(actions) != 1:
        raise ValueError('a setup step has exactly one of files, git and bare, and optionally repo and date')
    date = step.get('date')
    if 'date' in step and (not isinstance(date, int) or isinstance(date, bool) or not 0 <= date <= 4102444800):
        raise ValueError('date must be a unix time in seconds')
    if 'repo' in step:
        components(step['repo'], 'repo')
    if actions[0] == 'git':
        expand(check_setup(step['git']), '/x')
    elif actions[0] == 'bare':
        if not isinstance(step['bare'], str) or not REMOTE_NAME.fullmatch(step['bare']):
            raise ValueError('bare names a local remote: letters, digits, dot, underscore and dash')
    else:
        refuse_hidden(step['files'])


# -- running git -----------------------------------------------------------------------------------------------
def text(data):
    return data[:MAX_OUTPUT].decode('utf-8', 'replace')


def write_paths(data, base):
    return [data] + [base[key] for key in ('HOME', 'TMPDIR') if base.get(key)]


def run(argv, cwd, writes, env, account=None, timeout=GIT_TIMEOUT):
    command = [sys.executable, '-I', '-B', str(CONFINE)]
    # Git 2.43 implements submodule as a trusted shell script and uses sh for local transport helpers.
    if argv and argv[0] == 'submodule':
        for name in ('sh', 'dash', 'sed', 'basename', 'uname'):
            command += ['--exec', '/usr/bin/' + name]
    elif argv and argv[0] in ('clone', 'fetch', 'push', 'pull'):
        command += ['--exec', '/usr/bin/sh', '--exec', '/usr/bin/dash']
    for path in writes:
        command += ['--write', str(path)]
    command += ['--', GIT] + list(argv)
    kwargs = {}
    if account is not None:
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    try:
        done = subprocess.run(command, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              timeout=timeout, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError('the git command did not finish in time') from None
    return {'exit_code': done.returncode, 'stdout': text(done.stdout), 'stderr': text(done.stderr)}


def read_git(argv, repo, workspace, data, base, account=None, remote=None):
    '''Run one read-only git command in the workspace repository, or in a local bare remote (DATA_DIR/remotes).'''
    shown = check_read(argv)
    if remote is not None:
        if not isinstance(remote, str) or not REMOTE_NAME.fullmatch(remote):
            raise ValueError('remote names use letters, digits, dot, underscore and dash')
        cwd = Path(data) / 'remotes' / (remote + '.git')
        if cwd.is_symlink() or not cwd.is_dir():
            raise ValueError('no such local remote')
    else:
        cwd = locate(workspace, repo)
    argv = list(shown)
    if argv[0] in ('log', 'show', 'diff'):
        argv[1:1] = ['--no-ext-diff', '--no-textconv']
    env = command_env(base)
    env['GIT_OPTIONAL_LOCKS'] = '0'
    result = run(argv, cwd, write_paths(data, base), env, account)
    result['argv'] = shown
    return result


def apply(steps, workspace, data, base, account, place):
    '''Run setup steps in order while the application is stopped; place(files) writes setup input files.'''
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError('steps must list 1-%d setup steps' % MAX_STEPS)
    for step in steps:
        check_step(step)
    writes = write_paths(data, base)
    for index, step in enumerate(steps):
        if 'files' in step:
            place(step['files'])
            continue
        env = command_env(base, step.get('date', BASE_TIME + (index + 1) * STEP_SECONDS))
        if 'bare' in step:
            argv = ['init', '-q', '--bare', '-b', 'main', expand(['@remotes/' + step['bare']], data)[0]]
            cwd = Path(workspace)
        else:
            argv = expand(step['git'], data)
            cwd = locate(workspace, step.get('repo', ORIGIN))
        result = run(argv, cwd, writes, env, account)
        if result['exit_code'] != 0:
            detail = (result['stderr'] or result['stdout']).strip()
            raise ValueError('setup step %d failed: git %s exited with status %d: %s'
                             % (index + 1, argv[0], result['exit_code'], detail[:300]))
    return {'steps': len(steps)}


def ensure_repository(workspace, data, base, account=None):
    '''A fresh workspace is an empty git repository on the main branch before the application starts.'''
    workspace = Path(workspace)
    with runtime.owned_directory(data, 'workspace', uid=account.pw_uid if account else None,
                                 gid=account.pw_gid if account else None, mode=0o755) as workspace_fd:
        try:
            os.stat('.git', dir_fd=workspace_fd, follow_symlinks=False)
            exists = True
        except FileNotFoundError:
            exists = False
    if not exists:
        result = run(['init', '-q', '-b', 'main'], workspace, write_paths(data, base), command_env(base), account)
        if result['exit_code'] != 0:
            raise ValueError('could not create the workspace repository: ' + result['stderr'].strip()[:300])
