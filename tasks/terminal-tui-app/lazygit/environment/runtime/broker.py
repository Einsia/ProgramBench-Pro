#!/usr/bin/env python3
"""Drive a terminal Git client, repository setup and inspection, workspace files and clipboard observations."""
from __future__ import annotations

import fcntl
import http.server
import json
import os
import pty
import select
import stat
import socketserver
import struct
import subprocess
import sys
import termios
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blackbox_runtime as runtime  # noqa: E402
import fschan  # noqa: E402
import gitchan  # noqa: E402
import termemu  # noqa: E402
from termemu import COLUMNS, ROWS, TERM, KEY_NAMES, KEY_HELP, key_bytes  # noqa: E402

PRODUCT = 'lazygit'
ORIGIN = gitchan.ORIGIN
MAX_REQUEST_BYTES = 512 * 1024
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
RPC_TIMEOUT_SEC = 90
QUIET = 0.3
SETTLE_MAX = 4.0
PRODUCT_TIME = gitchan.BASE_TIME + 86400  # commits made in the application come after every setup input commit
CONFIG_NAMES = ('lazygit.yml', '.lazygit.yml')


# -- product in a pseudo-terminal ------------------------------------------------------------------------------
class TerminalProduct(runtime.Product):
    '''start.sh as the controlling-terminal session of a pseudo-terminal.'''

    def __init__(self, config, *, log):
        env = {'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'PYTHONHASHSEED': '0'}
        env.update(gitchan.git_env(PRODUCT_TIME))
        super().__init__(config, log=log, env=env)
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()

    @property
    def data(self):
        return Path(self.directories['DATA_DIR'])

    @property
    def workspace(self):
        return self.data / 'workspace'

    def run_account(self):
        return self.account() if self.switching() else None

    def environment(self):
        env = super().environment()
        env.update(COLUMNS=str(COLUMNS), LINES=str(ROWS))
        return env

    def start(self, fresh=False):
        self.stop()
        self.prepare(fresh)
        self.ready, self.starts = False, self.starts + 1
        self.terminal = termemu.LazygitTerminal(COLUMNS, ROWS)
        script = self.solution / 'start.sh'
        if not script.is_file():
            self.detail = 'start.sh does not exist in the solution directory'
            self.log.note(self.detail)
            return False
        try:
            gitchan.ensure_repository(self.workspace, self.data, self.environment(), self.run_account())
        except (ValueError, OSError) as exc:
            self.detail = 'the workspace repository could not be prepared: ' + str(exc)[:300]
            self.log.note(self.detail)
            return False
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLUMNS, 0, 0))
        kwargs = {}
        if self.switching():
            account = self.account()
            os.fchown(slave, account.pw_uid, account.pw_gid)
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        try:
            self.proc = subprocess.Popen(['setsid', '--ctty', str(script)], cwd=str(self.workspace),
                                         env=self.environment(), stdin=slave, stdout=slave, stderr=slave,
                                         umask=0o022, **kwargs)
        except OSError as exc:
            os.close(master)
            os.close(slave)
            self.proc = None
            self.detail = f'start.sh could not be executed ({type(exc).__name__}: {exc.strerror or exc})'
            self.log.note(self.detail)
            return False
        os.close(slave)
        os.set_blocking(master, False)
        self.master = master
        self.closing = threading.Event()
        self.reader = threading.Thread(target=self.pump, args=(master, self.terminal, self.closing), daemon=True)
        self.reader.start()
        self.log.note(f'start {self.starts}: pid {self.proc.pid}, terminal {COLUMNS}x{ROWS}')
        self.detail = 'starting'
        return True

    def pump(self, fd, terminal, closing):
        while not closing.is_set():
            try:
                ready, _, _ = select.select([fd], [], [], 0.2)
            except (OSError, ValueError):
                return
            if not ready:
                continue
            try:
                data = os.read(fd, 65536)
            except BlockingIOError:
                continue
            except OSError:
                return
            if not data:
                return
            terminal.feed(data)
            self.log.write(data)

    def stop(self, grace=10.0):
        super().stop(grace)
        self.closing.set()
        if self.reader is not None:
            self.reader.join(2.0)
            self.reader = None
        if self.master is not None:
            try:
                os.close(self.master)
            except OSError:
                pass
            self.master = None

    def write(self, data):
        if not self.running() or self.master is None:
            raise ValueError('the application is not running; restart it to continue')
        view = memoryview(data.encode('utf-8'))
        deadline = time.monotonic() + 5
        while view:
            try:
                view = view[os.write(self.master, view[:4096]):]
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ValueError('the application does not read its terminal input') from None
                time.sleep(0.01)
            except OSError as exc:
                raise ValueError('terminal input failed: ' + (exc.strerror or str(exc))) from None

    def resize(self, columns, rows):
        if not self.running() or self.master is None:
            raise ValueError('the application is not running; restart it to continue')
        self.terminal.resize(columns, rows)
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, columns, 0, 0))

    def process(self):
        if self.proc is None:
            return 'not started'
        code = self.proc.poll()
        return 'running' if code is None else f'exited with status {code}'


def wait_ready(product):
    '''Terminal readiness: the interface is drawn on the terminal (no product endpoint is used).'''
    limit = product.config.ready_timeout
    return runtime.wait_until(product, lambda: product.terminal.drawn(), deadline=limit, interval=0.1,
                              failure=f'the application did not draw its interface within {limit:g} s')


def sweep_configuration(data):
    """Remove unsupported local configuration entries without traversing links."""
    removed = 0
    def sweep(fd):
        nonlocal removed
        for name, info in runtime.list_directory(fd):
            if name in CONFIG_NAMES:
                runtime.remove_entry(fd, name)
                removed += 1
            elif stat.S_ISDIR(info.st_mode):
                with runtime.open_relative(fd, name, directory=True) as child:
                    sweep(child)
    with runtime.open_directory(data) as root_fd:
        sweep(root_fd)
    if removed:
        raise ValueError(f'setup produced {removed} unsupported configuration file(s); they were removed')


# -- RPC interface ---------------------------------------------------------------------------------------------
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'fields': {},
             'summary': 'This description of operations, fields, key names, limits and the reference key map and '
                        'disabled features (reference_controls).'},
    'status': {'kind': 'lifecycle', 'fields': {},
               'summary': 'Whether the application is running and ready, and its exit status once it ended.'},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the application with an empty data directory (its initial state: an empty git '
                         f'repository on the branch main) in a fresh {COLUMNS}x{ROWS} terminal.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the application with the same data directory in a fresh '
                           f'{COLUMNS}x{ROWS} terminal (for example after quitting it).'},
    'screen': {'kind': 'observe', 'fields': {},
               'summary': 'The terminal as a user sees it once output has settled: size [columns, rows]; the '
                          'cursor; screen rows as NN|text (NN is the zero-based row number, not part of the '
                          'screen); styles, the runs of text whose colour or attributes differ from the most '
                          'common style (selected line, active panel and similar), with base_style; and process: '
                          'running, or exited with its status.'},
    'key': {'kind': 'gui', 'summary': 'Press one key or chord, then return the settled screen.',
            'fields': {'key': {'type': 'string', 'required': True, 'description': KEY_HELP}}},
    'keys': {'kind': 'gui', 'summary': 'Press several keys or chords in order (validated before any is sent), '
                                       'then return the settled screen.',
             'fields': {'keys': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                 'description': f'1-{MAX_KEY_BATCH} keys, each as for key.'}}},
    'type': {'kind': 'gui', 'summary': 'Type literal text (printable characters only; send Enter, Escape and '
                                       'other keys with key), then return the settled screen.',
             'fields': {'text': {'type': 'string', 'required': True,
                                 'description': f'Printable UTF-8 text, 1-{MAX_TEXT} characters.'}}},
    'wait': {'kind': 'gui', 'summary': 'Wait for asynchronous terminal output, then return the settled screen.',
             'fields': {'seconds': {'type': 'number', 'description': 'Seconds to wait, 0-3; default 0.5.'}}},
    'resize': {'kind': 'gui', 'summary': 'Resize the terminal (the application receives SIGWINCH), then return '
                                         'the settled screen.',
               'fields': {'columns': {'type': 'integer', 'required': True, 'description': 'Columns, 40-240.'},
                          'rows': {'type': 'integer', 'required': True, 'description': 'Rows, 10-80.'}}},
    'workspace': {'kind': 'files',
                  'summary': 'Read-only inspector of the working tree of the repository the application opens '
                             '(the workspace): list one directory, tree (recursive), stat one entry, or read a '
                             'regular file. The .git directory is not listed (use git); symlinks are reported with '
                             'their target and never followed.',
                  'fields': {'action': {'type': 'string', 'enum': ['list', 'tree', 'stat', 'read'],
                                        'description': 'list, tree, stat or read (at most 1 MiB); default list.'},
                             'path': {'type': 'string',
                                      'description': f'{ORIGIN} or a path below it; default {ORIGIN}.'}}},
    'git': {'kind': 'files',
            'summary': 'Run one read-only git command in the workspace repository, in a repository below it or in a '
                       'local bare remote, and return exit_code, stdout and stderr. Allowed: log, show, diff, '
                       'status, blame, describe, rev-parse, rev-list, ls-files, ls-tree, cat-file, for-each-ref, '
                       'merge-base, name-rev, shortlog, show-ref, count-objects, diff-tree, diff-files, '
                       'diff-index, branch and tag (listing forms), config (--get, --get-all, --get-regexp, '
                       '--list), reflog, stash list or show, worktree list, submodule status, bisect log, remote -v or '
                       'get-url. No pager, external diff program or output file is ever used; hooks and global '
                       'git configuration do not take part.',
            'fields': {'argv': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                'description': 'The git command without the leading git, as a list of strings, '
                                               'for example [log, --oneline, -5].'},
                       'repo': {'type': 'string',
                                'description': f'The directory that holds the repository: {ORIGIN} (default) or '
                                               'a directory below it, for example a submodule or a linked '
                                               'worktree.'},
                       'remote': {'type': 'string',
                                  'description': 'Name of a local bare remote created by setup; the command then '
                                                 'runs in that remote instead of the workspace.'}}},
    'setup': {'kind': 'files',
              'summary': 'Preparation: run setup steps in order while the application is stopped, then restart '
                         'it with the same data. The steps are validated first; a step that fails when run leaves '
                         'the earlier steps applied. Files named lazygit.yml or .lazygit.yml cannot be placed.',
              'fields': {'steps': {'type': 'array', 'items': {'type': 'object'}, 'required': True,
                                   'description': 'Steps, each an object with exactly one of: files (an object of '
                                                  'workspace-relative path -> text, or an object with one of text, '
                                                  'base64 or symlink and optionally mode as an octal string, or '
                                                  'null for a directory); git (a list of strings: one git command '
                                                  'without the leading git, from init, clone, add, rm, mv, commit, '
                                                  'branch, checkout, switch, restore, tag, merge, stash, reset, '
                                                  'cherry-pick, revert, rebase, remote, submodule, worktree, fetch, '
                                                  'push, pull; each accepts a fixed list of options, written in '
                                                  'full and one per argument, and an invalid option is answered '
                                                  'with the list); bare (the name of a local bare remote, written in '
                                                  'git commands as the whole argument @remotes/NAME). Optional repo '
                                                  f'(the workspace directory that holds the repository, default '
                                                  f'{ORIGIN}) and date (unix seconds for the commit dates; default '
                                                  '2024-01-01T12:00:00Z plus one minute per step). At most '
                                                  f'{gitchan.MAX_STEPS} steps.'}}},
    'state': {'kind': 'files', 'fields': {},
              'summary': 'Read the state file lazygit keeps (state.yml: recent repositories, the version it last '
                         'ran, command history).'},
    'clipboard': {'kind': 'files', 'fields': {},
                  'summary': 'The text lazygit most recently copied to the clipboard (the copy keys such as '
                             'ctrl+o), with the number of copies since the application started.'},
    'cli': {'kind': 'info', 'summary': 'Run the application once with one documented command-line option that '
                                       'prints and exits, confined to this instance, and return what it prints.',
            'fields': {'option': {'type': 'string', 'enum': list(fschan.CLI_OPTIONS), 'required': True,
                                  'description': 'The command-line option to run.'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'read_bytes': fschan.MAX_FILE_BYTES,
          'tree_entries': fschan.MAX_TREE_ENTRIES, 'key_batch': MAX_KEY_BATCH, 'type_characters': MAX_TEXT,
          'placed_files': fschan.MAX_PLACED, 'setup_steps': gitchan.MAX_STEPS, 'git_arguments': gitchan.MAX_ARGS,
          'git_output_bytes': gitchan.MAX_OUTPUT, 'terminal_columns': [40, 240], 'terminal_rows': [10, 80],
          'wait_seconds': 3, 'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': termemu.MAX_STYLES,
          'screen': [COLUMNS, ROWS]}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, colours, wide and combined characters); screen shows what a user of a real terminal sees. '
    'Ages that follow the real clock (the recency column of the side panels, git relative dates in the log) are '
    'replaced by fixed placeholders: tildes in the column, the text <age> in the log.',
    'key, keys, type, resize and wait return the screen once output has settled (no new output for 0.3 s, at '
    'most 4 s); screen waits the same way. Input sent before the screen settles may be discarded by the '
    'application, so observe the settled screen before sending more keys.',
    'The workspace is the git repository the application opens. A fresh instance starts with an empty repository '
    'on the branch main. Author and committer identity and dates are fixed for the application and for every git '
    'command of the runtime; repository hooks, global git configuration and credential prompts do not take part.',
    'reset and restart start the application in a fresh terminal; restart keeps the data directory.',
    'git, workspace, state, clipboard and cli are for preparation and checking; they are not part of the '
    'interactive terminal. setup stops the application, runs its steps and starts it again.',
    'Private runtime locations in screens and answers are shown as /workspace, [data] or [private].',
]
EXAMPLES = [{'op': 'screen'}, {'op': 'key', 'key': 'Down'}, {'op': 'keys', 'keys': ['2', 'j', 'Space']},
            {'op': 'type', 'text': 'feature-x'}, {'op': 'key', 'key': 'Control+O'},
            {'op': 'git', 'argv': ['log', '--oneline', '--graph', '--all']},
            {'op': 'git', 'argv': ['status', '--porcelain']},
            {'op': 'workspace', 'action': 'tree', 'path': '/workspace'}, {'op': 'clipboard'}, {'op': 'state'},
            {'op': 'setup', 'steps': [{'files': {'notes.txt': 'first'}}, {'git': ['add', '.']},
                                      {'git': ['commit', '-m', 'first commit']}]},
            {'op': 'cli', 'option': '--version'}]

# The reference key map: described in help.
REFERENCE_CONTROLS = {
    'note': 'lazygit 0.66.2 with its default key map, as this environment exposes it. The bottom line of the screen shows the '
            'keys of the focused panel (the question-mark keybindings menu is disabled). The features that start an editor, a shell, '
            'an external program or a browser are disabled and their keys do nothing. These keys are part of '
            'the interface contract; an implementation may also offer additional equivalent keys.',
    'disabled': ['the shell command prompt (:)', 'opening a file in an editor or with the system opener (e, o) and '
                 'editing the config file', 'the external diff tool (ctrl+t)',
                 'committing or rewording with the git editor (C, R)',
                 'creating or opening pull requests and opening commits in a browser (o, O, G)',
                 'git-flow options (i in the branches panel)', 'editing a hunk in an editor (E)',
                 'the keybindings menu (?), which could start the other disabled actions',
                 'the update check (u in the status panel)',
                 'start-up popups, the random tip, automatic fetch and refresh, animations and mouse support'],
    'layout': 'Left column: Status [1], Files - Worktrees - Submodules [2], Local branches - Remotes - Tags [3], '
              'Commits - Reflog [4], Stash [5]. ] and [ cycle the tabs of a panel, 1-5 jump to a panel, 0 focuses '
              'the main view on the right, which shows the diff, log or file content of the selection. The command '
              'log is at the bottom right and the key hints on the bottom line.',
    'keys': 'Navigation: up and down or k and j, left and right or h and l between panels or blocks, < and > top and '
            'bottom, , and . page, / search or filter, v range select, + and _ screen mode, '
            'q quit, esc cancel. Text inputs: ctrl+u clears the input; Tab switches between summary and description '
            'in the commit dialog. Files: space stage, a stage all, c commit, w commit without hooks, '
            'A amend last commit, d discard menu, '
            'D reset menu, s stash, S stash menu, enter focus the diff for hunk and line staging (space stages '
            'the selection, a toggles hunk and line mode, v range), backtick toggle tree view, - and = collapse '
            'and expand all, i ignore, f fetch, M merge conflict menu, ctrl+b status filter. Branches: space '
            'checkout, n new, c checkout by name, - previous branch, F force checkout, d delete menu, r rebase, '
            'M merge menu, f fast-forward, T tag, s sort order, g reset menu, R rename, u upstream menu, enter '
            'view commits, N move unpushed commits to a new branch, w new worktree. Commits: s squash, f fixup, r reword, d drop, i start interactive rebase, p '
            'pick, F create fixup commit, S apply fixup commits, ctrl+j and ctrl+k move down and up, C copy for '
            'cherry-pick, V paste, B mark base commit, A amend with staged changes, a amend attribute, t revert, '
            'T tag, g reset menu, space checkout, n new branch, N move commits to a new branch, w new worktree, y copy attribute, '
            'b bisect menu, ctrl+l log menu, * select the commits of the branch, enter view files. Stash: space '
            'apply, g pop, d drop, n new branch, r rename. Everywhere: P push, p pull, m merge and rebase '
            'options, z undo, Z redo, R refresh, W or ctrl+e diffing menu, ctrl+s filter menu, ctrl+p custom patch '
            'menu, ctrl+r recent repositories, @ command log menu, ctrl+o copy to the clipboard (readable with the '
            'clipboard op), ( and ) rename similarity, { and } diff context, ctrl+w whitespace.',
}


class Refused(ValueError):
    pass


def make_redactor(pairs):
    '''Replace each private filesystem root with its logical name, longest roots first.'''
    ordered = sorted(((str(Path(p)), name) for p, name in pairs if p and str(Path(p)) != '/'),
                     key=lambda pair: len(pair[0]), reverse=True)

    def apply(text):
        text = str(text)
        for root, name in ordered:
            if root in text:
                text = text.replace(root, name)
        return text
    return apply


def validate_request(data):
    op = runtime.validate(OPERATIONS, data)
    if op == 'key':
        key_bytes(data['key'])
    elif op == 'keys':
        if not 1 <= len(data['keys']) <= MAX_KEY_BATCH:
            raise ValueError(f'keys must list 1-{MAX_KEY_BATCH} keys')
        for key in data['keys']:
            key_bytes(key)
    elif op == 'type':
        gitchan.printable(data['text'], 'text', MAX_TEXT)
        if not data['text']:
            raise ValueError('text must not be empty')
    elif op == 'resize':
        if not (40 <= data['columns'] <= 240 and 10 <= data['rows'] <= 80):
            raise ValueError('resize needs 40-240 columns and 10-80 rows')
    elif op == 'wait':
        if not 0 <= data.get('seconds', 0.5) <= 3:
            raise ValueError('wait takes 0-3 seconds')
    elif op == 'workspace':
        fschan.parts_of(data.get('path', ORIGIN))
    elif op == 'git':
        gitchan.check_read(data['argv'])
        gitchan.components(data.get('repo', ORIGIN), 'repo')
    elif op == 'cli':
        if data['option'] not in fschan.CLI_OPTIONS:
            raise ValueError('unknown command-line option')
    return op


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.log = runtime.BoundedLog(config.log_dir)
        self.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        self.product = TerminalProduct(config, log=self.log)
        layout = self.product.directories
        self.redact = make_redactor([(self.product.workspace, ORIGIN), (layout['DATA_DIR'], '[data]'),
                                     (config.state, '[private]'), (config.solution, '[private]'),
                                     (config.work, '[private]'), (config.log_dir, '[private]'),
                                     (str(HERE), '[private]'), ('/reference', '[private]'),
                                     ('/opt/blackbox', '[private]'), ('/app/solution', '[private]')])
        # The screen also normalises the ages that follow the real clock.
        self.screen_clean = lambda text: termemu.normalize_ages(self.redact(text))

    # Lifecycle ----------------------------------------------------------------------------------------------
    def launch(self, fresh):
        if self.product.start(fresh=fresh):
            wait_ready(self.product)
        status = self.product.status()
        self.log.note('status: ' + json.dumps(status))
        return status

    def start(self):
        with self.lock:
            return self.launch(fresh=True)

    def reset(self):
        with self.lock:
            self.product.stop()
            return self.launch(fresh=True)

    def restart(self):
        with self.lock:
            self.product.stop()
            return self.launch(fresh=False)

    def close(self):
        self.product.stop()

    def detail(self, exc):
        return self.redact(str(exc))[:600]

    # Observation --------------------------------------------------------------------------------------------
    def settle(self, minimum=0.1):
        terminal = self.product.terminal
        if terminal is None:
            return
        started = time.monotonic()
        deadline = started + SETTLE_MAX
        while True:
            now = time.monotonic()
            if now >= deadline or (now - started >= minimum and now - terminal.last_output >= QUIET):
                return
            time.sleep(0.02)

    def observe(self, minimum=0.1):
        self.settle(minimum)
        terminal = self.product.terminal
        if terminal is None:
            return termemu.blank_observation(self.product.process())
        deadline = time.monotonic() + 1.0
        while self.product.running() and not terminal.drawn() and time.monotonic() < deadline:
            time.sleep(0.05)
        return termemu.normalize_patch_log(terminal.observe(self.product.process(), self.screen_clean))

    def send(self, raw, minimum=0.1):
        self.product.write(raw)
        self.settle(minimum)
        return self.observe(0)

    # Preparation --------------------------------------------------------------------------------------------
    def setup(self, steps):
        '''Setup steps run while the application is stopped; it is started again whatever happens.'''
        if not isinstance(steps, list) or not 1 <= len(steps) <= gitchan.MAX_STEPS:
            raise ValueError(f'steps must list 1-{gitchan.MAX_STEPS} setup steps')
        for step in steps:
            gitchan.check_step(step)
            if 'files' in step:
                fschan.check_files(step['files'])
        product = self.product
        product.stop()
        account = product.run_account()
        # Stopping the application can kill a git process it started while that process held the index lock.
        try:
            with runtime.open_relative(product.workspace, '.git', directory=True) as git_fd:
                runtime.unlink_entry(git_fd, 'index.lock', missing_ok=True)
        except FileNotFoundError:
            pass
        try:
            gitchan.ensure_repository(product.workspace, product.data, product.environment(), account)
            result = gitchan.apply(steps, product.workspace, product.data, product.environment(), account,
                                   lambda files: fschan.place(product.workspace, files, account))
            sweep_configuration(product.data)
        finally:
            status = self.launch(fresh=False)
        result['status'] = self.redact_value(status)
        return result

    # Dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = validate_request(data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'terminal', OPERATIONS, limits=LIMITS, notes=NOTES,
                                         examples=EXAMPLES, key_names=KEY_NAMES, modifiers=['Control', 'Alt', 'Shift'],
                                         reference_controls=REFERENCE_CONTROLS)
        if op == 'status':
            return self.redact_value(self.product.status())
        product = self.product
        with self.lock:
            if op == 'reset':
                return self.redact_value(self.reset())
            if op == 'restart':
                return self.redact_value(self.restart())
            if op == 'screen':
                return self.observe()
            if op == 'key':
                cursor = product.terminal and product.terminal.application_cursor()
                return self.send(key_bytes(data['key'], cursor))
            if op == 'keys':
                cursor = product.terminal and product.terminal.application_cursor()
                return self.send(''.join(key_bytes(k, cursor) for k in data['keys']))
            if op == 'type':
                return self.send(data['text'])
            if op == 'wait':
                time.sleep(float(data.get('seconds', 0.5)))
                return self.observe(0)
            if op == 'resize':
                self.settle(0)
                product.resize(data['columns'], data['rows'])
                self.settle(0.15)
                return self.observe(0)
            if op == 'workspace':
                return self.redact_value(fschan.inspect_workspace(product.workspace, data, product.account().pw_uid))
            if op == 'git':
                return self.redact_value(gitchan.read_git(data['argv'], data.get('repo', ORIGIN), product.workspace,
                                                          product.data, product.environment(), product.run_account(),
                                                          data.get('remote')))
            if op == 'setup':
                return self.setup(data['steps'])
            if op == 'state':
                return self.redact_value(fschan.read_state(product.data, product.account().pw_uid))
            if op == 'clipboard':
                terminal = product.terminal
                return self.redact_value({'text': terminal.clipboard if terminal else None,
                                          'copies': terminal.copies if terminal else 0})
            if op == 'cli':
                return self.redact_value(fschan.run_cli(product.solution / 'launch.py', product.environment(),
                                                        data['option'], product.workspace, product.run_account()))
            raise ValueError('Unknown operation; use help')

    def redact_value(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.redact_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.redact_value(v) for k, v in value.items()}
        return value


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *_args):
        pass

    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(404, {'error': 'NotFound', 'detail': 'POST a JSON request to /rpc'})

    def do_POST(self):
        started, op, status = time.monotonic(), None, 200
        rt = self.server.runtime
        try:
            self.connection.settimeout(RPC_TIMEOUT_SEC)
            if self.path != '/rpc':
                status, value = 404, {'error': 'NotFound', 'detail': 'POST a JSON request to /rpc'}
            else:
                length = int(self.headers.get('Content-Length') or 0)
                if self.headers.get('Transfer-Encoding') or not 0 < length <= MAX_REQUEST_BYTES:
                    status, value = 413, {'error': 'RequestTooLarge',
                                          'detail': f'requests carry 1-{MAX_REQUEST_BYTES} bytes'}
                else:
                    data = runtime.strict_json_loads(self.rfile.read(length))
                    op = data.get('op') if isinstance(data, dict) else None
                    value = rt.dispatch(data)
        except Refused as exc:
            status, value = 400, {'error': 'Refused', 'detail': rt.detail(exc)}
        except Exception as exc:
            if not isinstance(exc, (ValueError, KeyError, TypeError)):
                rt.log.note(f'rpc {op}: {type(exc).__name__}: {exc}')
            status, value = 400, {'error': type(exc).__name__, 'detail': rt.detail(exc)}
        try:
            self.reply(status, value)
        finally:
            rt.audit.record(str(op or 'invalid')[:40], status, time.monotonic() - started)


def main(argv=None):
    config = runtime.options(socket_mode='0660', ready_timeout=30.0).parse_args(argv)
    rt = Runtime(config)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    runtime.exit_on_sigterm()
    try:
        rt.start()
        sock = runtime.listen(config.socket, config.socket_mode)
        server = Server(config.socket, Handler, bind_and_activate=False)
        server.socket.close()
        server.socket = sock
        server.runtime = rt
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
    finally:
        rt.close()
        try:
            os.unlink(config.socket)
        except OSError:
            pass


if __name__ == '__main__':
    main()
