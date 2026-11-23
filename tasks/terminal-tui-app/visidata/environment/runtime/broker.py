#!/usr/bin/env python3
"""VisiData terminal runtime.

One instance drives one application directory in an emulated xterm-256color
pseudo-terminal. Other channels expose workspace files, input history and
command-line batch operations on that instance.
"""

from __future__ import annotations

import base64
import codecs
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import pty
import re
import select
import shlex
import stat
import struct
import subprocess
import sys
import termios
import threading
import time
import unicodedata

import http.server
import socketserver

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blackbox_runtime as runtime  # noqa: E402
from commands import run_bounded  # noqa: E402
import workspace_files as safe_files  # noqa: E402

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

import datetime  # noqa: E402

PRODUCT = 'visidata'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_PLACED = 512
MAX_STYLES = 600
MAX_CLI_ARGS = 64
MAX_CLI_ARG = 4096
RPC_TIMEOUT_SEC = 90
QUIET = 0.3
SETTLE_MAX = 4.0
RESPONSE_WAIT = 1.5  # how long settle waits for the first output after input before quiet can count
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
ORIGIN = '/workspace'
CLI_TIMEOUT = 60
STATE_FILES = ('input_history',)
DATE_FORMAT = '%Y-%m-%d'


SIMPLE = {'enter': '\r', 'return': '\r', 'escape': '\x1b', 'esc': '\x1b', 'tab': '\t', 'backspace': '\x7f',
          'bs': '\x7f', 'space': ' ', 'colon': ':', 'slash': '/'}


CURSOR = {'up': 'A', 'down': 'B', 'right': 'C', 'left': 'D', 'home': 'H', 'end': 'F'}


TILDE = {'insert': 2, 'delete': 3, 'pageup': 5, 'pagedown': 6, 'f5': 15, 'f6': 17, 'f7': 18, 'f8': 19, 'f9': 20,
         'f10': 21, 'f11': 23, 'f12': 24}


SS3_FUNCTION = {'f1': 'P', 'f2': 'Q', 'f3': 'R', 'f4': 'S'}


ALIASES = {'arrowup': 'up', 'arrowdown': 'down', 'arrowleft': 'left', 'arrowright': 'right', 'del': 'delete',
           'ins': 'insert', 'pgup': 'pageup', 'pgdn': 'pagedown', 'page_up': 'pageup', 'page_down': 'pagedown',
           'return': 'enter'}


MODIFIERS = {'control': 'ctrl', 'ctrl': 'ctrl', 'alt': 'alt', 'meta': 'alt', 'option': 'alt', 'shift': 'shift'}


KEY_NAMES = ['Enter', 'Escape', 'Tab', 'Backspace', 'Space', 'Up', 'Down', 'Left', 'Right', 'Home', 'End',
             'PageUp', 'PageDown', 'Insert', 'Delete'] + [f'F{i}' for i in range(1, 13)]


KEY_HELP = ('One key: a single printable character (for example j, :, / or Q), or a name: ' + ', '.join(KEY_NAMES) +
            ' (case-insensitive), optionally combined with Control+, Alt+ or Shift+ (for example Control+U, '
            'Alt+f, Shift+Tab).')


def split_key(name):
    if len(name) == 1:
        return set(), name
    if '+' in name[:-1]:
        parts = name.split('+')
        if parts[-1] == '' and name.endswith('++'):
            parts = parts[:-2] + ['+']
    else:
        match = re.fullmatch(r'(?i)((?:(?:control|ctrl|alt|meta|option|shift)-)+)(.+)', name)
        parts = (match.group(1).split('-')[:-1] + [match.group(2)]) if match else [name]
    mods = set()
    for part in parts[:-1]:
        if part.lower() not in MODIFIERS:
            raise ValueError(f'unknown modifier {part!r} in key {name!r}')
        mods.add(MODIFIERS[part.lower()])
    return mods, parts[-1]


def key_bytes(name, application_cursor=False):
    """Terminal input of one key or chord, as an xterm sends it."""
    if not isinstance(name, str) or not name or len(name) > 32:
        raise ValueError('each key must be a key name or one character')
    mods, base = split_key(name)
    if not base:
        raise ValueError(f'invalid key {name!r}')
    code = 1 + ('shift' in mods) + 2 * ('alt' in mods) + 4 * ('ctrl' in mods)
    if len(base) == 1:
        if not base.isprintable():
            raise ValueError(f'{name!r} is not a printable key; use a key name such as Enter or Tab')
        char = base
        if 'shift' in mods:
            if not char.isalpha():
                raise ValueError(f'Shift is only supported with letters and named keys: {name!r}')
            char = char.upper()
        if 'ctrl' in mods:
            if char.isalpha():
                char = chr(ord(char.upper()) & 0x1f)
            elif char in '@[\\]^_ ':
                char = chr(ord(char) & 0x1f) if char != ' ' else '\x00'
            elif char == '?':
                char = '\x7f'
            else:
                raise ValueError(f'unsupported control chord {name!r}')
        return ('\x1b' if 'alt' in mods else '') + char
    key = ALIASES.get(base.lower(), base.lower())
    if key in SIMPLE:
        sequence = SIMPLE[key]
        if mods - {'alt'}:
            if mods == {'shift'} and key == 'tab':
                return '\x1b[Z'
            if mods == {'ctrl'} and key == 'space':
                return '\x00'
            if mods == {'ctrl'} and key == 'backspace':
                return '\x08'
            raise ValueError(f'unsupported chord {name!r}')
        return ('\x1b' if 'alt' in mods else '') + sequence
    if key in CURSOR:
        if code > 1:
            return f'\x1b[1;{code}{CURSOR[key]}'
        return ('\x1bO' if application_cursor else '\x1b[') + CURSOR[key]
    if key in SS3_FUNCTION:
        return f'\x1b[1;{code}{SS3_FUNCTION[key]}' if code > 1 else '\x1bO' + SS3_FUNCTION[key]
    if key in TILDE:
        return f'\x1b[{TILDE[key]};{code}~' if code > 1 else f'\x1b[{TILDE[key]}~'
    raise ValueError(f'unknown key {name!r}; see help for key names')


ALTERNATE_SCREEN = {47, 1047, 1049}


class XtermScreen(pyte.Screen):
    """pyte 0.8.2 plus the xterm-256color behaviour curses applications rely on."""

    def __init__(self, columns, lines):
        super().__init__(columns, lines)
        self.last_graphic = None
        self.saved_primary = None

    def draw(self, data):
        run = []
        for char in data:
            width = wcwidth(char)
            if width > 0 or (width == 0 and unicodedata.combining(char)):
                run.append(char)
                continue
            if run:
                super().draw(''.join(run))
                self.last_graphic = run[-1]
                run = []
            if width == 0:
                self.join_previous(char)
        if run:
            super().draw(''.join(run))
            self.last_graphic = run[-1]

    def join_previous(self, char):
        line = self.buffer[self.cursor.y]
        x = min(self.cursor.x, self.columns)
        for column in (x - 1, x - 2):
            if column >= 0 and line[column].data:
                line[column] = line[column]._replace(data=line[column].data + char)
                return

    def scroll_up(self, count=None, *rest, **_):
        if rest:
            return
        top, bottom = self.margins or Margins(0, self.lines - 1)
        for _ in range(min(max(count or 1, 1), self.lines)):
            for y in range(top, bottom):
                self.buffer[y] = self.buffer[y + 1]
            self.buffer.pop(bottom, None)
        self.dirty.update(range(self.lines))

    def scroll_down(self, count=None, *rest, **_):
        if rest:
            return
        top, bottom = self.margins or Margins(0, self.lines - 1)
        for _ in range(min(max(count or 1, 1), self.lines)):
            for y in range(bottom, top, -1):
                self.buffer[y] = self.buffer[y - 1]
            self.buffer.pop(top, None)
        self.dirty.update(range(self.lines))

    def repeat_character(self, count=None, *rest, **_):
        if self.last_graphic and not rest:
            self.draw(self.last_graphic * min(max(count or 1, 1), self.columns * self.lines))

    def set_mode(self, *modes, **kwargs):
        if kwargs.get('private') and ALTERNATE_SCREEN & set(modes) and self.saved_primary is None:
            self.saved_primary = ({y: dict(line) for y, line in self.buffer.items()}, self.cursor.x, self.cursor.y)
            self.buffer.clear()
            self.dirty.update(range(self.lines))
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get('private') and ALTERNATE_SCREEN & set(modes) and self.saved_primary is not None:
            lines, x, y = self.saved_primary
            self.saved_primary = None
            self.buffer.clear()
            for row, cells in lines.items():
                if row < self.lines:
                    self.buffer[row].update(cells)
            self.cursor.x, self.cursor.y = min(x, self.columns), min(y, self.lines - 1)
            self.dirty.update(range(self.lines))
        super().reset_mode(*modes, **kwargs)


class XtermStream(pyte.Stream):
    csi = dict(pyte.Stream.csi, S='scroll_up', T='scroll_down', b='repeat_character')


def flags(style):
    fg, bg, bold, italics, underscore, reverse = style
    names = [n for n, v in (('bold', bold), ('italic', italics), ('underline', underscore), ('reverse', reverse)) if v]
    return names + (['fg=' + str(fg)] if fg != 'default' else []) + (['bg=' + str(bg)] if bg != 'default' else [])


class Terminal:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.screen = XtermScreen(columns, rows)
        self.stream = XtermStream(self.screen)
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.lock = threading.Lock()
        self.last_output = time.monotonic()
        self.received = 0

    def feed(self, data):
        with self.lock:
            self.stream.feed(self.decoder.decode(data))
            self.last_output = time.monotonic()
            self.received += len(data)

    def resize(self, columns, rows):
        with self.lock:
            self.columns, self.rows = columns, rows
            self.screen.resize(rows, columns)

    def application_cursor(self):
        with self.lock:
            return DECCKM in self.screen.mode

    def line(self, y):
        row, out, skip = self.screen.buffer[y], [], False
        for x in range(self.columns):
            if skip:
                skip = False
                continue
            data = row[x].data or ' '
            out.append(data)
            skip = wcwidth(data[0]) == 2
        return ''.join(out).rstrip()

    def drawn(self):
        with self.lock:
            return any(self.line(y).strip() for y in range(self.rows))

    def observe(self, process, redact):
        with self.lock:
            lines = [redact(self.line(y)) for y in range(self.rows)]
            spans = []
            for y in range(self.rows):
                row, current = [], None
                for x in range(self.columns):
                    cell = self.screen.buffer[y][x]
                    style = (cell.fg, cell.bg, cell.bold, cell.italics, cell.underscore, cell.reverse)
                    if current and current[2] == style:
                        current[1] = x + 1
                    else:
                        current = [x, x + 1, style]
                        row.append(current)
                spans.append(row)

            def text(y, start, end):
                return ''.join(self.screen.buffer[y][x].data for x in range(start, end))
            weight = {}
            for y, row in enumerate(spans):
                for start, end, style in row:
                    visible = len(text(y, start, end).strip())
                    if visible:
                        weight[style] = weight.get(style, 0) + visible
            base = max(weight, key=weight.get) if weight else None
            styles = []
            for y, row in enumerate(spans):
                for start, end, style in row:
                    value = text(y, start, end)
                    if style == base or not value.strip() or (base is None and not flags(style)):
                        continue
                    styles.append({'row': y, 'columns': [start, end], 'text': redact(value),
                                   'style': flags(style) or ['default']})
            cursor = self.screen.cursor
            result = {'size': [self.columns, self.rows],
                      'cursor': {'row': cursor.y, 'column': min(cursor.x, self.columns - 1),
                                 'hidden': bool(cursor.hidden)},
                      'screen': [f'{y:02d}|{line}' for y, line in enumerate(lines)],
                      'styles': styles[:MAX_STYLES]}
            if len(styles) > MAX_STYLES:
                result['styles_truncated'] = True
            if base is not None and flags(base):
                result['base_style'] = flags(base)
        result['process'] = process
        return result


def blank_observation(process):
    return {'size': [COLUMNS, ROWS], 'cursor': {'row': 0, 'column': 0, 'hidden': False},
            'screen': [f'{y:02d}|' for y in range(ROWS)], 'styles': [], 'process': process}


class TerminalProduct(runtime.Product):
    """start.sh as the controlling-terminal session of a pseudo-terminal."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log,
                         env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
                              'PYTHONHASHSEED': '0'})
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()

    @property
    def workspace(self):
        return Path(self.directories['DATA_DIR']) / 'workspace'

    @property
    def state_dir(self):
        return Path(self.directories['DATA_DIR']) / '.local' / 'share' / 'visidata'

    def environment(self):
        env = super().environment()
        env.update(COLUMNS=str(COLUMNS), LINES=str(ROWS))
        return env

    def start(self, fresh=False):
        self.stop()
        self.prepare(fresh)
        self.ready, self.starts = False, self.starts + 1
        self.terminal = Terminal(COLUMNS, ROWS)
        script = self.solution / 'start.sh'
        if not script.is_file():
            self.detail = 'start.sh does not exist in the solution directory'
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
            self.proc = subprocess.Popen(['setsid', '--ctty', str(script)], cwd=str(self.solution),
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
    """Terminal readiness: the interface is drawn on the terminal (no product endpoint is used)."""
    limit = product.config.ready_timeout
    ok = runtime.wait_until(product, lambda: product.terminal.drawn(), deadline=limit, interval=0.1,
                            failure=f'the application did not draw its interface within {limit:g} s')
    return ok


def printable(value, field, limit):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{field} must be printable text of at most {limit} characters')
    return value


def components(value, field='path'):
    value = printable(value, field, 4096)
    if value == ORIGIN or value in ('', '.'):
        return []
    if value.startswith(ORIGIN + '/'):
        value = value[len(ORIGIN) + 1:]
    if value.startswith('/') or '\\' in value:
        raise ValueError(f'{field} must stay inside {ORIGIN}')
    parts = [p for p in value.split('/') if p not in ('', '.')]
    if any(p == '..' for p in parts):
        raise ValueError(f'{field} must stay inside {ORIGIN}')
    for part in parts:
        if len(part.encode('utf-8')) > 255:
            raise ValueError(f'{field} has a component longer than 255 bytes')
    return parts


def workspace_root(product):
    with runtime.open_directory(product.workspace):
        pass
    return product.workspace


def inspect(product, data):
    return safe_files.inspect(product.workspace, components(data.get('path', ORIGIN)),
                              data.get('action', 'list'), origin=ORIGIN, read_limit=MAX_FILE_BYTES,
                              hash_limit=MAX_HASH_BYTES, tree_limit=MAX_TREE_ENTRIES)


def place(product, files):
    """Place files and metadata through directory descriptors, then validate links."""
    account = product.account()
    try:
        with safe_files.directory(product, product.directories['DATA_DIR'], ['workspace'], create=True) as root:
            for name, value in files.items():
                parts = components(name, 'file path')
                if not parts:
                    raise ValueError('a placed file needs a path below the workspace')
                with safe_files.directory(product, root, parts[:-1], create=True) as parent:
                    leaf = parts[-1]
                    mtime = value.get('mtime') if isinstance(value, dict) else None
                    ns = (int(mtime * 1_000_000_000),) * 2 if mtime is not None else None
                    try:
                        info = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
                    except FileNotFoundError:
                        info = None
                    if info is not None and stat.S_ISLNK(info.st_mode):
                        raise ValueError('cannot replace a symlink: ' + name)
                    if isinstance(value, dict) and 'symlink' in value:
                        if info is not None:
                            runtime.unlink_entry(parent, leaf)
                        os.symlink(value['symlink'], leaf, dir_fd=parent)
                        if product.switching():
                            os.chown(leaf, account.pw_uid, account.pw_gid,
                                     dir_fd=parent, follow_symlinks=False)
                        if ns is not None:
                            os.utime(leaf, ns=ns, dir_fd=parent, follow_symlinks=False)
                    elif value is None or isinstance(value, dict) and value.get('dir'):
                        with safe_files.directory(product, parent, [leaf], create=True) as directory_fd:
                            if ns is not None:
                                runtime.set_metadata(directory_fd, ns=ns)
                    else:
                        content = value.encode('utf-8') if isinstance(value, str) else base64.b64decode(value['base64'], validate=True)
                        mode = value.get('mode', 0o644) if isinstance(value, dict) else 0o644
                        safe_files.write(product, parent, leaf, content, mode=mode, mtime=mtime)
    finally:
        safe_files.drop_escaping_links(product.workspace, origin=ORIGIN, limit=MAX_TREE_ENTRIES)


def _symlink_target_inside(name, target):
    """A placed symlink's target must resolve inside the workspace: reject an absolute target and any relative
    target that climbs above the workspace root with '..'. (Targets that merely do not exist yet are fine -- a
    broken link within the workspace is accepted.) The file preview follows links, so their final targets
    must also stay within the workspace."""
    if not isinstance(target, str) or not target or target[0] == '/' or '\\' in target or '\x00' in target:
        return False
    depth = len(components(name)) - 1          # the symlink's parent directory depth below the workspace root
    for part in target.split('/'):
        if part in ('', '.'):
            continue
        depth += -1 if part == '..' else 1
        if depth < 0:
            return False
    return True


def check_files(files):
    if not isinstance(files, dict):
        raise ValueError('files must be an object of path -> content')
    if len(files) > MAX_PLACED:
        raise ValueError(f'at most {MAX_PLACED} files can be placed at once')
    for name, value in files.items():
        if not components(name, 'file path'):
            raise ValueError('a placed file needs a path below the workspace')
        if value is None or isinstance(value, str):
            continue
        if not isinstance(value, dict):
            raise ValueError('a placed file is UTF-8 text, an object, or null for a directory')
        kinds = set(value) & {'base64', 'symlink', 'dir'}
        if len(kinds) != 1:
            raise ValueError('a file object needs exactly one of base64, symlink or dir')
        kind = next(iter(kinds))
        allowed = {kind, 'mtime'} | ({'mode'} if kind == 'base64' else set())
        if set(value) - allowed:
            raise ValueError('unknown file field')
        if 'mtime' in value:
            stamp = value['mtime']
            if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or not math.isfinite(stamp) or not 0 <= stamp < 2 ** 33:
                raise ValueError('mtime must be finite seconds between 0 and 2**33')
        if 'mode' in value:
            mode = value['mode']
            if isinstance(mode, bool) or not isinstance(mode, int) or not 0 <= mode <= 0o777:
                raise ValueError('mode must be an integer permission set (0-0o777)')
        if kind == 'dir' and value['dir'] is not True:
            raise ValueError('dir must be true')
        if 'symlink' in value:
            if not isinstance(value['symlink'], str):
                raise ValueError('symlink must be a string target')
            if not _symlink_target_inside(name, value['symlink']):
                raise ValueError('symlink target must resolve inside ' + ORIGIN)
            continue
        if 'base64' in value:
            if not isinstance(value['base64'], str):
                raise ValueError('base64 must be encoded text')
            base64.b64decode(value['base64'], validate=True)


def make_redactor(pairs):
    """Replace each private filesystem root with its logical name; the workspace becomes /workspace so the
    screen and answers show stable paths. Longest roots first."""
    ordered = sorted(((str(Path(p)), name) for p, name in pairs if p and str(Path(p)) != '/'),
                     key=lambda pair: len(pair[0]), reverse=True)

    def apply(text):
        text = str(text)
        for root, name in ordered:
            if root in text:
                text = text.replace(root, name)
        return text
    return apply


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
        # The screen also normalises volatile clock fields (the non-GUI channels do not show them).
        self.screen_clean = lambda text: normalize_times(self.redact(text))

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
    def settle(self, minimum=0.1, received=None):
        '''Wait until the terminal has been quiet for QUIET seconds. Quiet time counts from the later of the call
        and the last output, so output from before the input never counts. With received (the byte count before
        the input was written) the application must also have answered, or RESPONSE_WAIT must have passed.'''
        terminal = self.product.terminal
        if terminal is None:
            return
        started = time.monotonic()
        deadline = started + SETTLE_MAX
        while True:
            now = time.monotonic()
            answered = received is None or terminal.received > received or now - started >= RESPONSE_WAIT
            if now >= deadline or (answered and now - started >= minimum and now - max(started, terminal.last_output) >= QUIET):
                return
            time.sleep(0.02)

    def observe(self, minimum=0.1):
        self.settle(minimum)
        terminal = self.product.terminal
        if terminal is None:
            return blank_observation(self.product.process())
        deadline = time.monotonic() + 1.0
        while self.product.running() and not terminal.drawn() and time.monotonic() < deadline:
            time.sleep(0.05)
        return terminal.observe(self.product.process(), self.screen_clean)

    def send(self, raw, minimum=0.1):
        terminal = self.product.terminal
        before = terminal.received if terminal is not None else None
        self.product.write(raw)
        self.settle(minimum, received=before)
        return self.observe(0)

    # Dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = validate_request(data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'terminal', OPERATIONS, limits=LIMITS, notes=NOTES,
                                         examples=EXAMPLES, key_names=KEY_NAMES, modifiers=['Control', 'Alt', 'Shift'],
                                         reference_controls=REFERENCE_CONTROLS)
        if op == 'status':
            return self.redact_value(self.product.status())
        with self.lock:
            if op == 'reset':
                return self.redact_value(self.reset())
            if op == 'restart':
                return self.redact_value(self.restart())
            if op == 'screen':
                return self.observe()
            if op == 'key':
                cursor = self.product.terminal and self.product.terminal.application_cursor()
                return self.send(key_bytes(data['key'], cursor))
            if op == 'keys':
                cursor = self.product.terminal and self.product.terminal.application_cursor()
                return self.send(''.join(key_bytes(k, cursor) for k in data['keys']))
            if op == 'type':
                return self.send(data['text'])
            if op == 'wait':
                time.sleep(float(data.get('seconds', 0.5)))
                return self.observe(0)
            if op == 'resize':
                self.settle(0)
                self.product.resize(data['columns'], data['rows'])
                self.settle(0.15)
                return self.observe(0)
            if op == 'workspace':
                return inspect(self.product, data)
            if op == 'place':
                self.product.stop()
                check_files(data['files'])
                place(self.product, data['files'])
                return self.redact_value(self.launch(fresh=False))
            if op == 'state':
                return self.redact_value(read_state(self.product, data))
            if op == 'cli':
                return self.redact_value(run_cli(self.product, data))
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


from controls import REFERENCE_CONTROLS  # noqa: E402


class Refused(ValueError):
    pass


# Files written during a run carry the wall-clock time and the directory sheet shows it as a date. A date equal to
# the current or the previous UTC date is therefore shown as [today] on the screen; input files get fixed
# modification times through place and keep their dates.
def volatile_dates():
    now = datetime.datetime.now(datetime.timezone.utc)
    days = (now, now - datetime.timedelta(days=1))
    return re.compile('|'.join(day.strftime(DATE_FORMAT) for day in days))


def normalize_times(text):
    return volatile_dates().sub('[today]', text)


# -- the state file VisiData writes itself ------------------------------------------------------------------------
def read_state(product, data):
    which = data['file']
    if which not in STATE_FILES:
        raise ValueError('file must be one of: ' + ', '.join(STATE_FILES))
    try:
        content = runtime.read_file(product.directories['DATA_DIR'],
                                    '.local/share/visidata/' + which + '.jsonl', limit=MAX_FILE_BYTES)
    except OSError:
        return {'file': which, 'exists': False, 'text': ''}
    return {'file': which, 'exists': True, 'text': content.decode('utf-8', 'replace')}


# -- restricted command-line channel ------------------------------------------------------------------------------
def cli_arguments(data):
    arguments = data['args']
    if not isinstance(arguments, list) or not 1 <= len(arguments) <= MAX_CLI_ARGS:
        raise ValueError(f'args must list 1-{MAX_CLI_ARGS} strings')
    for argument in arguments:
        if not isinstance(argument, str) or not 1 <= len(argument) <= MAX_CLI_ARG or chr(0) in argument:
            raise ValueError(f'each argument must be a non-empty string of at most {MAX_CLI_ARG} characters without NUL')
    return arguments


def run_cli(product, data):
    '''Run the product once in batch mode with the given command-line arguments, confined to the instance.'''
    arguments = cli_arguments(data)
    workspace = workspace_root(product)
    launcher = product.solution / 'launch.py'
    if not launcher.is_file():
        raise ValueError('the solution has no launcher to run command-line arguments')
    env = dict(product.environment())
    env['PBP_CLI_ARGS'] = json.dumps(arguments)
    account = product.account() if product.switching() else None
    kwargs = {}
    if account:
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    try:
        done = run_bounded(['/usr/bin/python3', '-P', '-s', str(launcher)], env=env, cwd=str(workspace),
                           stream_limit=MAX_FILE_BYTES, merge_stderr=True, timeout=CLI_TIMEOUT, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError('the command-line run did not finish in time') from None
    output = done.stdout.decode('utf-8', 'replace').replace(chr(13), '')[:MAX_FILE_BYTES]
    return {'args': arguments, 'exit_code': done.returncode, 'output': output}


# -- RPC interface ------------------------------------------------------------------------------------------------
FILE_FIELD = {'type': 'string', 'enum': list(STATE_FILES), 'required': True,
              'description': 'Which persistent state file to read: input_history, the inputs typed at prompts, one JSON '
                             'object per line.'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, key names, limits and the '
                                        'reference key map (reference_controls).', 'fields': {}},
    'status': {'kind': 'lifecycle', 'fields': {},
               'summary': 'Whether the application is running and ready, and its exit status once it ended.'},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the application with an empty data directory (its initial state) in a fresh '
                         f'{COLUMNS}x{ROWS} terminal.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Restart the application with the same data directory in a fresh '
                           f'{COLUMNS}x{ROWS} terminal (for example after quitting it).'},
    'screen': {'kind': 'observe', 'fields': {},
               'summary': 'The terminal as a user sees it once output has settled: size [columns, rows]; the '
                          'cursor; screen rows as NN|text (NN is the zero-based row number, not part of the '
                          'screen); styles, the runs of text whose colour or attributes differ from the most '
                          'common style (reverse video, bold, colour: the cursor cell and row, selected rows, key '
                          'columns), with base_style; and process: running, or exited with its status.'},
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
    'workspace': {'kind': 'files', 'summary': 'Read-only inspector of the application workspace (the directory it '
                  'browses and where it writes files): list one directory, tree (recursive), stat one entry, or '
                  'read a regular file. Hidden entries are included; symlinks are reported with their target and '
                  'never followed.',
                  'fields': {'action': {'type': 'string', 'enum': ['list', 'tree', 'stat', 'read'],
                                        'description': 'list, tree, stat or read (at most 1 MiB); default list.'},
                             'path': {'type': 'string',
                                      'description': f'{ORIGIN} or a path below it; default {ORIGIN}.'}}},
    'place': {'kind': 'files', 'summary': 'Write input files into the workspace while the '
              'application is stopped, then restart it with the same instance data.',
              'fields': {'files': {'type': 'object', 'required': True,
                                   'description': 'workspace-relative path mapped to UTF-8 text, to an object with '
                                                  'base64 (and optionally mode and mtime), to an object with symlink '
                                                  '(a target inside the workspace), or to null or {dir:true} for a directory. '
                                                  'Link and directory objects may include mtime. mode is 0-0777; mtime is '
                                                  'finite seconds from 0 to less than 2**33. Unknown fields are rejected; '
                                                  'at most 512 entries.'}}},
    'state': {'kind': 'files', 'summary': 'Read the persistent state file of the application (its input history) '
              'from its data directory.',
              'fields': {'file': FILE_FIELD}},
    'cli': {'kind': 'info', 'summary': 'Run the application once in batch mode (no interface) with command-line '
            'arguments, confined to this instance, and return its exit status and what it prints. The arguments '
            'are those of vd after the program name: -b IN -o OUT converts a file, -b -p LOG.vdj replays a '
            'command log. The working directory is the workspace, so relative paths are workspace paths.',
            'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                'description': f'1-{MAX_CLI_ARGS} command-line arguments, each a non-empty string of at '
                                               f'most {MAX_CLI_ARG} characters.'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'read_bytes': MAX_FILE_BYTES, 'tree_entries': MAX_TREE_ENTRIES,
          'key_batch': MAX_KEY_BATCH, 'type_characters': MAX_TEXT, 'placed_files': MAX_PLACED,
          'terminal_columns': [40, 240], 'terminal_rows': [10, 80], 'wait_seconds': 3,
          'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': MAX_STYLES, 'screen': [COLUMNS, ROWS],
          'cli_arguments': MAX_CLI_ARGS, 'cli_seconds': CLI_TIMEOUT}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, scrolling regions, colours, wide and combined characters); screen shows what a user '
    'of a real terminal sees.',
    'key, keys, type, resize and wait return the screen once output has settled (no new output for 0.3 s, at '
    'most 4 s); screen waits the same way. Input sent before the screen settles may be discarded by the '
    'application, so observe the settled screen before sending more keys.',
    'reset and restart start the application in a fresh terminal; restart keeps the data directory. The '
    'terminal is the controlling terminal of the application, so it receives SIGWINCH on resize.',
    'workspace, place, state and cli operate independently of the interactive '
    'terminal. workspace reads the files the application browses and writes (links are reported, never '
    'followed). state reads the file the application persists. cli runs the application once in batch mode with '
    'command-line arguments, confined to this instance; files it writes land in the workspace.',
    'Private runtime locations in screens, answers and errors are shown as /workspace, [data] or [private]. On '
    'the screen, a date equal to the current or the previous UTC date is shown as [today], because files written '
    'during a run carry the wall-clock time.',
]
EXAMPLES = [{'op': 'screen'}, {'op': 'key', 'key': 'Down'}, {'op': 'keys', 'keys': ['Shift+F', 'q']},
            {'op': 'type', 'text': 'sample.csv'}, {'op': 'key', 'key': 'Control+D'},
            {'op': 'workspace', 'action': 'tree', 'path': '/workspace'},
            {'op': 'state', 'file': 'input_history'},
            {'op': 'cli', 'args': ['-b', 'sample.csv', '-o', 'out.tsv']}]


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
        printable(data['text'], 'text', MAX_TEXT)
        if not data['text']:
            raise ValueError('text must not be empty')
    elif op == 'resize':
        if not (40 <= data['columns'] <= 240 and 10 <= data['rows'] <= 80):
            raise ValueError('resize needs 40-240 columns and 10-80 rows')
    elif op == 'wait':
        if not (0 <= data.get('seconds', 0.5) <= 3):
            raise ValueError('wait takes 0-3 seconds')
    elif op == 'workspace':
        components(data.get('path', ORIGIN))
    elif op == 'place':
        check_files(data['files'])
    elif op == 'cli':
        cli_arguments(data)
    return op


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
