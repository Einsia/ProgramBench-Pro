#!/usr/bin/env python3
"""Drive a terminal calendar, home-directory file exchange, command-line runs and user documentation."""
from __future__ import annotations

import base64
import codecs
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
import selectors
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

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

PRODUCT = 'calcurse'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
HOME = '~'                      # how DATA_DIR (calcurse's home directory) is shown in every answer
CLOCK = '2026-03-18 09:30:00'   # the frozen wall clock (UTC) the application sees; a Wednesday
FAKETIME_LIBRARY = '/usr/local/lib/faketime/libfaketime.so.1'
ESCDELAY_MS = 50
MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_PLACED = 256
MAX_STYLES = 600
MAX_CLI_ARGS = 48
MAX_ARG = 1024
RPC_TIMEOUT_SEC = 120
QUIET = 0.3
SETTLE_MAX = 4.0
ESCAPE_PAUSE = 0.15
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
CLI_TIMEOUT = 30
DOCS = HERE / 'docs'


# -- keys ------------------------------------------------------------------------------------------------------
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
KEY_HELP = ('One key: a single printable character (for example a, ?, + or Q), or a name: ' + ', '.join(KEY_NAMES) +
            ' (case-insensitive), optionally combined with Control+, Alt+ or Shift+ (for example Control+A, '
            'Control+G, Shift+Tab).')


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


# -- terminal emulation ----------------------------------------------------------------------------------------
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
    """xterm honours G0/G1 designations (ESC ( 0, the DEC line-drawing set used by curses for boxes) and SI/SO in
    UTF-8 mode as well; pyte ignores them while use_utf8 is set. The input is already decoded text, so use_utf8
    only governs those designations here."""
    csi = dict(pyte.Stream.csi, S='scroll_up', T='scroll_down', b='repeat_character')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_utf8 = False

    def select_other_charset(self, code):
        self.use_utf8 = False


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
            # Styled runs are reported relative to the terminal's default style (default colours, no attributes),
            # so every highlighted run (borders, titles, the selected day and item, key names) is listed.
            styles = []
            for y, row in enumerate(spans):
                for start, end, style in row:
                    value = text(y, start, end)
                    if not flags(style) or not value.strip():
                        continue
                    styles.append({'row': y, 'columns': [start, end], 'text': redact(value), 'style': flags(style)})
            cursor = self.screen.cursor
            result = {'size': [self.columns, self.rows],
                      'cursor': {'row': cursor.y, 'column': min(cursor.x, self.columns - 1),
                                 'hidden': bool(cursor.hidden)},
                      'screen': [f'{y:02d}|{line}' for y, line in enumerate(lines)],
                      'styles': styles[:MAX_STYLES]}
            if len(styles) > MAX_STYLES:
                result['styles_truncated'] = True
        result['process'] = process
        return result


def blank_observation(process):
    return {'size': [COLUMNS, ROWS], 'cursor': {'row': 0, 'column': 0, 'hidden': False},
            'screen': [f'{y:02d}|' for y in range(ROWS)], 'styles': [], 'process': process}


# -- product in a pseudo-terminal ------------------------------------------------------------------------------
def clock_environment():
    return {'LD_PRELOAD': FAKETIME_LIBRARY, 'FAKETIME': CLOCK, 'FAKETIME_DONT_FAKE_MONOTONIC': '1'}


class TerminalProduct(runtime.Product):
    """start.sh as the controlling-terminal session of a pseudo-terminal; its home is DATA_DIR."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log,
                         env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
                              'ESCDELAY': str(ESCDELAY_MS), **clock_environment()})
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()

    @property
    def home(self):
        return Path(self.directories['DATA_DIR'])

    def environment(self):
        env = super().environment()
        env.update(COLUMNS=str(COLUMNS), LINES=str(ROWS), HOME=str(self.home))
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
            self.proc = subprocess.Popen(['setsid', '--ctty', str(script)], cwd=str(self.home),
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
    return runtime.wait_until(product, lambda: product.terminal.drawn(), deadline=limit, interval=0.1,
                              failure=f'the application did not draw its interface within {limit:g} s')


# -- the home directory (read-only inspector and setup placement; never through symlinks) ----------------------
def printable(value, field, limit):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{field} must be printable text of at most {limit} characters')
    return value


def components(value, field='path'):
    """A path inside the home directory: '~', '~/a/b' or the relative 'a/b'. Never absolute, never '..'."""
    value = printable(value, field, 4096)
    if value in ('', '.', HOME, HOME + '/'):
        return []
    if value.startswith(HOME + '/'):
        value = value[len(HOME) + 1:]
    if value.startswith('/') or '\\' in value or value.startswith('~'):
        raise ValueError(f'{field} must be a path inside the home directory ({HOME} or a relative path)')
    parts = [p for p in value.split('/') if p not in ('', '.')]
    if any(p == '..' for p in parts):
        raise ValueError(f'{field} must stay inside the home directory')
    for part in parts:
        if len(part.encode('utf-8')) > 255:
            raise ValueError(f'{field} has a component longer than 255 bytes')
    return parts


def logical(parts):
    return HOME + ''.join('/' + p for p in parts)


DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def open_dir(root, parts, create=None):
    """A directory fd for root/parts, opened component by component without following symlinks. With create
    (a callable taking (dir_fd, name)), missing directories are made."""
    with runtime.open_directory(root) as root_fd:
        fd = os.dup(root_fd)
    try:
        for part in parts:
            try:
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if create is None:
                    raise ValueError('no such directory in the home directory') from None
                os.mkdir(part, 0o755, dir_fd=fd)
                create(fd, part)
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError:
                raise ValueError('the path passes through a file or a symlink') from None
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_beneath(root, parts, limit):
    """The bytes of the regular file root/parts (no symlink anywhere on the path), at most limit bytes."""
    if not parts:
        raise ValueError('read needs a file')
    dfd = open_dir(root, parts[:-1])
    try:
        try:
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
        except FileNotFoundError:
            raise ValueError('no such file in the home directory') from None
        except OSError:
            raise ValueError('read needs a regular file (symlinks are never followed)') from None
    finally:
        os.close(dfd)
    try:
        return runtime.read_bounded(fd, limit=limit)
    finally:
        os.close(fd)


def entry(dfd, name, path):
    info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    mode = info.st_mode
    kind = ('symlink' if stat.S_ISLNK(mode) else 'directory' if stat.S_ISDIR(mode) else
            'file' if stat.S_ISREG(mode) else 'other')
    result = {'path': path, 'name': name, 'type': kind, 'size': info.st_size if kind == 'file' else 0,
              'mode': stat.S_IMODE(mode)}
    if kind == 'file':
        result['sha256'] = None
        if info.st_size <= MAX_HASH_BYTES:
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=dfd)
                try:
                    content = runtime.read_bounded(fd, limit=MAX_HASH_BYTES)
                    result['sha256'] = hashlib.sha256(content).hexdigest()
                finally:
                    os.close(fd)
            except (OSError, ValueError):
                pass
    elif kind == 'symlink':
        target = os.readlink(name, dir_fd=dfd)
        result['target'] = target if not target.startswith('/') else '[absolute target]'
    return result


def listing(dfd, parts, recursive, out):
    names = sorted(os.listdir(dfd), key=lambda n: (n.casefold(), n))
    for name in names:
        if len(out) >= MAX_TREE_ENTRIES:
            raise ValueError(f'the home directory tree exceeds {MAX_TREE_ENTRIES} entries')
        item = entry(dfd, name, logical(parts + [name]))
        out.append(item)
        if recursive and item['type'] == 'directory':
            try:
                child = os.open(name, DIR_FLAGS, dir_fd=dfd)
            except OSError:
                continue
            try:
                listing(child, parts + [name], True, out)
            finally:
                os.close(child)
    return out


def inspect(product, data):
    action = data.get('action', 'list')
    parts = components(data.get('path', HOME))
    root = product.home
    if action == 'read':
        content = read_beneath(root, parts, MAX_FILE_BYTES)
        return {'path': logical(parts), 'size': len(content), 'text': content.decode('utf-8', 'replace'),
                'body_base64': base64.b64encode(content).decode()}
    if action == 'stat':
        if not parts:
            return {'path': HOME, 'name': HOME, 'type': 'directory', 'size': 0,
                    'mode': stat.S_IMODE(os.lstat(root).st_mode)}
        dfd = open_dir(root, parts[:-1])
        try:
            return entry(dfd, parts[-1], logical(parts))
        except FileNotFoundError:
            raise ValueError('no such entry in the home directory') from None
        finally:
            os.close(dfd)
    if action not in ('list', 'tree'):
        raise ValueError('action must be list, tree, stat or read')
    dfd = open_dir(root, parts)
    try:
        entries = listing(dfd, parts, action == 'tree', [])
    finally:
        os.close(dfd)
    if action == 'tree':
        entries.sort(key=lambda e: e['path'])
    return {'path': logical(parts), 'entries': entries}


def check_files(files):
    if not isinstance(files, dict) or not files:
        raise ValueError('files must be a non-empty object of path -> content')
    if len(files) > MAX_PLACED:
        raise ValueError(f'at most {MAX_PLACED} files can be placed at once')
    for name, value in files.items():
        parts = components(name, 'file path')
        if not parts:
            raise ValueError('a placed file needs a path below the home directory')
        if value is None or isinstance(value, str):
            continue
        if not isinstance(value, dict) or not (set(value) <= {'base64', 'mtime', 'remove'}):
            raise ValueError('a placed file is UTF-8 text, {"base64": ..., "mtime": ...}, {"remove": true} '
                             'or null for a directory')
        if value.get('remove') is not None and value.get('remove') is not True:
            raise ValueError('remove must be true')
        if 'base64' in value:
            base64.b64decode(value['base64'], validate=True)
        if value.get('mtime') is not None and not isinstance(value['mtime'], (int, float)):
            raise ValueError('mtime must be a number')


def remove_tree(dfd, name):
    info = os.stat(name, dir_fd=dfd, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        os.unlink(name, dir_fd=dfd)
        return
    child = os.open(name, DIR_FLAGS, dir_fd=dfd)
    try:
        for inner in os.listdir(child):
            remove_tree(child, inner)
    finally:
        os.close(child)
    os.rmdir(name, dir_fd=dfd)


def place(product, files):
    """Write setup files into the home directory while the application is stopped (never through symlinks)."""
    root = product.home
    with runtime.open_directory(root):
        pass
    account = product.account() if product.switching() else None

    def own_at(dfd, name):
        if account:
            with runtime.open_relative(dfd, name, directory=True) as child_fd:
                runtime.set_metadata(child_fd, uid=account.pw_uid, gid=account.pw_gid)
    for name, value in files.items():
        parts = components(name, 'file path')
        dfd = open_dir(root, parts[:-1], create=own_at)
        try:
            leaf = parts[-1]
            try:
                info = os.stat(leaf, dir_fd=dfd, follow_symlinks=False)
            except FileNotFoundError:
                info = None
            if isinstance(value, dict) and value.get('remove'):
                if info is not None:
                    remove_tree(dfd, leaf)
                continue
            if value is None:
                if info is not None and not stat.S_ISDIR(info.st_mode):
                    os.unlink(leaf, dir_fd=dfd)
                    info = None
                if info is None:
                    os.mkdir(leaf, 0o755, dir_fd=dfd)
                    own_at(dfd, leaf)
                continue
            if info is not None:
                remove_tree(dfd, leaf)
            content = value.encode('utf-8') if isinstance(value, str) else base64.b64decode(value['base64'])
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o644,
                         dir_fd=dfd)
            try:
                view = memoryview(content)
                while view:
                    view = view[os.write(fd, view):]
                os.fchmod(fd, 0o644)
                if account:
                    os.fchown(fd, account.pw_uid, account.pw_gid)
                mtime = value.get('mtime') if isinstance(value, dict) else None
                if mtime is not None:
                    os.utime(fd, (mtime, mtime))
            finally:
                os.close(fd)
        finally:
            os.close(dfd)


# -- command line (calcurse's own non-interactive options; the data locations stay the instance's own) -----------
# getopt_long tables of calcurse 4.8.2: short options with their argument kind and the long options.
SHORT_OPTIONS = {'P': None, 'F': None, 'g': None, 'G': None, 'h': None, 'v': None, 'n': None, 'N': None, 'a': None,
                 'x': 'optional', 't': 'optional', 'C': 'required', 'd': 'required', 'c': 'required',
                 'r': 'optional', 's': 'optional', 'S': 'required', 'D': 'required', 'i': 'required',
                 'l': 'required', 'q': None, 'Q': None}
LONG_OPTIONS = {
    'appointment': None, 'calendar': 'required', 'conf': 'required', 'confdir': 'required', 'day': 'required',
    'datadir': 'required', 'directory': 'required', 'filter': None, 'gc': None, 'grep': None, 'help': None,
    'import': 'required', 'limit': 'required', 'next': None, 'note': None, 'purge': None, 'range': 'optional',
    'startday': 'optional', 'search': 'required', 'todo': 'optional', 'version': None, 'export': 'optional',
    'quiet': None, 'query': 'optional', 'filter-invert': None, 'filter-type': 'required',
    'filter-hash': 'required', 'filter-pattern': 'required', 'filter-start-from': 'required',
    'filter-start-to': 'required', 'filter-start-after': 'required', 'filter-start-before': 'required',
    'filter-start-range': 'required', 'filter-end-from': 'required', 'filter-end-to': 'required',
    'filter-end-after': 'required', 'filter-end-before': 'required', 'filter-end-range': 'required',
    'filter-priority': 'required', 'filter-completed': None, 'filter-uncompleted': None, 'from': 'required',
    'to': 'required', 'days': 'required', 'format-apt': 'required', 'format-recur-apt': 'required',
    'format-event': 'required', 'format-recur-event': 'required', 'format-todo': 'required', 'export-uid': None,
    'dump-imported': None, 'read-only': None, 'status': None, 'daemon': None, 'input-datefmt': 'required',
    'output-datefmt': 'required'}
SHORT_LONG = {'a': 'appointment', 'c': 'calendar', 'C': 'confdir', 'd': 'day', 'D': 'datadir', 'F': 'filter',
              'g': 'gc', 'G': 'grep', 'h': 'help', 'i': 'import', 'l': 'limit', 'n': 'next', 'N': 'note',
              'P': 'purge', 'r': 'range', 's': 'startday', 'S': 'search', 't': 'todo', 'v': 'version',
              'x': 'export', 'q': 'quiet', 'Q': 'query'}
# The data and configuration locations are the instance's own (a run must not be pointed at other files), and the
# background daemon is not available in this environment.
REFUSED = {'calendar': '-c/--calendar', 'conf': '-C/--confdir', 'confdir': '-C/--confdir',
           'datadir': '-D/--datadir', 'directory': '-D/--datadir', 'daemon': '--daemon'}
# Options that do not by themselves make calcurse act and exit: alone they would start the interactive interface.
MODIFIERS_ONLY = {'quiet', 'read-only', 'limit', 'export-uid', 'dump-imported', 'note'}


def long_name(name):
    """The long option getopt_long resolves name to: an exact name, else a unique prefix (None if ambiguous or
    unknown; calcurse then reports the error itself)."""
    if name in LONG_OPTIONS:
        return name
    matches = [option for option in LONG_OPTIONS if option.startswith(name)]
    return matches[0] if len(matches) == 1 else None


def check_args(args):
    """Validate a command line for the cli channel. Arguments are passed to the application unchanged."""
    if not isinstance(args, list) or not args or len(args) > MAX_CLI_ARGS or not all(isinstance(a, str) for a in args):
        raise ValueError(f'args must be a list of 1-{MAX_CLI_ARGS} strings')
    seen, positional, i = set(), False, 0

    def value_file(option, value):
        if not components(value, f'the file of {option}'):
            raise ValueError(f'{option} needs a file inside the home directory')
    while i < len(args):
        arg = printable(args[i], 'argument', MAX_ARG)
        i += 1
        if arg == '--':
            positional = positional or i < len(args)
            break
        if arg.startswith('--'):
            name, has_value, inline = arg[2:].partition('=')
            option = long_name(name)
            if option is None:
                seen.add('?')
                continue
            if option in REFUSED:
                raise ValueError(f'{REFUSED[option]} is not available here: the application always uses its own '
                                 'files in the home directory')
            seen.add(option)
            kind = LONG_OPTIONS[option]
            if kind == 'required' and not has_value:
                if i >= len(args):
                    seen.add('?')
                    continue
                inline = printable(args[i], 'argument', MAX_ARG)
                i += 1
            if option == 'import' and (has_value or kind == 'required'):
                value_file('--import', inline)
            continue
        if arg.startswith('-') and len(arg) > 1:
            j = 1
            while j < len(arg):
                char = arg[j]
                j += 1
                if char not in SHORT_OPTIONS:
                    seen.add('?')
                    continue
                option = SHORT_LONG[char]
                if option in REFUSED:
                    raise ValueError(f'{REFUSED[option]} is not available here: the application always uses its '
                                     'own files in the home directory')
                seen.add(option)
                kind = SHORT_OPTIONS[char]
                if kind is None:
                    continue
                value = arg[j:]
                if not value and kind == 'required':
                    if i >= len(args):
                        seen.add('?')
                        break
                    value = printable(args[i], 'argument', MAX_ARG)
                    i += 1
                if option == 'import':
                    value_file('-i', value)
                break
            continue
        positional = True
    if not positional and seen and seen <= MODIFIERS_ONLY:
        raise ValueError('a command-line run needs an option that makes calcurse print or act and exit (for example '
                         '-a, -d, -Q, -t, -G, -P, -g, -i, -x, -n, -h, -v or --status); alone, '
                         + ', '.join(sorted(seen)) + ' would start the interactive interface')
    return list(args)


def run_cli(product, args):
    """Run start.sh once with the given options (no terminal, standard input closed) while the interactive
    application keeps running, and return its exit code and output."""
    script = product.solution / 'start.sh'
    if not script.is_file():
        raise ValueError('start.sh does not exist in the solution directory')
    kwargs = {}
    if product.switching():
        account = product.account()
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    env = product.environment()
    env.pop('COLUMNS', None)
    env.pop('LINES', None)
    with runtime.open_directory(product.home):
        pass
    try:
        proc = subprocess.Popen([str(script), *args], cwd=str(product.home), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
                                umask=0o022, **kwargs)
    except OSError as exc:
        raise ValueError(f'start.sh could not be executed ({exc.strerror or exc})') from None
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    limited, timed_out = False, False
    selector = selectors.DefaultSelector()
    for name in buffers:
        pipe = getattr(proc, name)
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe, selectors.EVENT_READ, name)
    deadline = time.monotonic() + CLI_TIMEOUT
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                timed_out = True
                break
            for key, _ in selector.select(min(.1, max(0, deadline - time.monotonic()))):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                target = buffers[key.data]
                remaining = MAX_FILE_BYTES - len(target)
                target.extend(block[:remaining])
                if len(block) > remaining:
                    limited = True
                    break
            if limited:
                break
        if not (limited or timed_out):
            try:
                proc.wait(max(.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        try:
            os.killpg(proc.pid, 9)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait(5)
        selector.close()
        proc.stdout.close()
        proc.stderr.close()
    result = {'args': args, 'exit_code': proc.returncode,
              **{name: bytes(value).decode('utf-8', 'replace') for name, value in buffers.items()}}
    if timed_out:
        result['timed_out'] = True
    if limited:
        result['output_limited'] = True
    return result


# -- the reference's own documentation (calcurse's help topics and manuals, which its ? key shows in an external
# pager that is not available here) -----------------------------------------------------------------------------
def doc_topics():
    return sorted(p.stem for p in DOCS.glob('*.txt'))


def read_doc(data):
    topics = doc_topics()
    topic = data.get('topic')
    if topic is None:
        return {'topics': topics}
    if topic not in topics:
        raise ValueError('topic must be one of: ' + ', '.join(topics))
    return {'topic': topic, 'text': (DOCS / (topic + '.txt')).read_text(encoding='utf-8')}


# -- RPC interface ---------------------------------------------------------------------------------------------
PATH_FIELD = {'type': 'string', 'description': f'{HOME} or a path below it (relative paths are relative to {HOME}); '
                                               f'default {HOME}.'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, key names, limits, the fixed clock '
                                        'and notes on the environment.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'fields': {},
               'summary': 'Whether the application is running and ready, and its exit status once it ended.'},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the application with a fresh, empty home directory (its initial state) in a fresh '
                         f'{COLUMNS}x{ROWS} terminal.'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Stop the application if it is running (SIGTERM) and start it again with the same home '
                           f'directory in a fresh {COLUMNS}x{ROWS} terminal (for example after quitting it).'},
    'screen': {'kind': 'observe', 'fields': {},
               'summary': 'The terminal as a user sees it once output has settled: size [columns, rows]; the '
                          'cursor; screen rows as "NN|text" (NN is the zero-based row number, not part of the '
                          'screen); styles, the runs of text drawn with colours or attributes (bold, reverse, '
                          'underline, foreground and background colours); and process: running, or exited with '
                          'its status.'},
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
    'files': {'kind': 'files', 'summary': f"Read-only inspector of the application's home directory ({HOME}, which "
              'holds calcurse\'s data files .local/share/calcurse/apts, todo and notes/ and its configuration '
              '.config/calcurse/conf and keys, plus any file you place or export there): list one directory, tree '
              '(recursive), stat one entry, or read a regular file. Hidden entries are included; symlinks are '
              'reported, never followed.',
              'fields': {'action': {'type': 'string', 'enum': ['list', 'tree', 'stat', 'read'],
                                    'description': f'list, tree, stat or read (at most {MAX_FILE_BYTES} bytes); '
                                                   'default list.'},
                         'path': PATH_FIELD}},
    'place': {'kind': 'files', 'summary': 'Write files into the home directory (for example calendar files to '
              'import, or calcurse data and configuration files) while the application is stopped, then start it '
              'again with the same home directory.',
              'fields': {'files': {'type': 'object', 'required': True,
                                   'description': f'path inside {HOME} -> UTF-8 text, {{"base64": ..., "mtime": '
                                                  'seconds}, {"remove": true} to delete a file or directory, or null '
                                                  f'for a directory; at most {MAX_PLACED} entries.'}}},
    'cli': {'kind': 'info', 'summary': 'Run the application once more, with command-line options that make it print '
            'or act and exit (as a user does in a second shell): start.sh runs with the arguments, the same home '
            'directory as its home and working directory, no terminal and standard input closed, while the '
            'interactive application keeps running; returns the exit code, standard output and standard error.',
            'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                'description': 'Command-line arguments, one per list item (an option and its value '
                                'as two items, or --long=value, or a short option with its value attached such as '
                                '-r7). calcurse\'s non-interactive options are accepted; -c/--calendar, '
                                '-C/--confdir, -D/--datadir and --daemon are not available, and the file of '
                                '-i/--import must be a path inside the home directory.'}}},
    'docs': {'kind': 'info', 'summary': "The reference's own documentation, as shipped with calcurse 4.8.2: its online "
             'help topics (which its ? key and :help command show in an external pager, not available here), '
             'the manual page (calcurse.1) and the manual. Without topic, the list of topics.',
             'fields': {'topic': {'type': 'string', 'description': 'One topic from the list.'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'read_bytes': MAX_FILE_BYTES, 'tree_entries': MAX_TREE_ENTRIES,
          'key_batch': MAX_KEY_BATCH, 'type_characters': MAX_TEXT, 'placed_files': MAX_PLACED,
          'cli_arguments': MAX_CLI_ARGS, 'cli_argument_characters': MAX_ARG, 'cli_seconds': CLI_TIMEOUT,
          'cli_output_bytes': MAX_FILE_BYTES, 'terminal_columns': [40, 240], 'terminal_rows': [10, 80],
          'wait_seconds': 3, 'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': MAX_STYLES, 'screen': [COLUMNS, ROWS]}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, scrolling regions, the line-drawing character set, colours, wide and combined characters); '
    'screen shows what a user of a real terminal sees.',
    'key, keys, type, resize and wait return the screen once output has settled (no new output for 0.3 s, at '
    'most 4 s); screen waits the same way. Input sent before the screen settles may be discarded by the '
    'application, so observe the settled screen before sending more keys. Within keys, the runtime pauses '
    f'briefly after a lone Escape so that it reaches the application as Escape (ESCDELAY is {ESCDELAY_MS} ms).',
    f'The wall clock the application sees stays at {CLOCK} UTC (libfaketime, preloaded by the runtime into the '
    'application and its command-line runs); monotonic clocks, sleeping and timeouts work normally.',
    f'The home directory {HOME} is both HOME and DATA_DIR of the application and its working directory, so '
    'relative file names (in its prompts and on its command line) name files there.',
    'reset starts from an empty home directory; restart and place keep it. The application is stopped with '
    'SIGTERM before restart and place, as a terminated process: what it would only save when saving or quitting '
    'is not saved. cli runs alongside the interactive application, which only rereads its files when it is told to '
    '(or when it is restarted).',
    'The application cannot start other programs or processes, so the features that run one (the note editor and '
    'pager, the help viewer, piping an item to a command, the notification command, hooks, the merge tool and the '
    'background daemon) do not run anything here; docs serves the documentation the help viewer would show.',
    f'files, place and cli are for preparation and checking; they are not part of the interactive terminal. '
    f'Private runtime locations in screens, answers and errors are shown as {HOME} (the home directory) or '
    '[private].',
]


class Refused(ValueError):
    pass


def make_redactor(pairs):
    """Replace each private filesystem root with its logical name. Longest roots first."""
    ordered = sorted(((str(Path(p)), name) for p, name in pairs if p and str(Path(p)) != '/'),
                     key=lambda pair: len(pair[0]), reverse=True)

    def apply(text):
        text = str(text)
        for root, name in ordered:
            if root in text:
                text = text.replace(root, name)
        return text
    apply.pairs = ordered
    return apply


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.log = runtime.BoundedLog(config.log_dir)
        self.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        self.product = TerminalProduct(config, log=self.log)
        layout = self.product.directories
        self.redact = make_redactor([(layout['DATA_DIR'], HOME)] +
                                    [(path, '[private]') for key, path in layout.items() if key != 'DATA_DIR'] +
                                    [(config.state, '[private]'), (config.solution, '[private]'),
                                     (config.work, '[private]'), (config.log_dir, '[private]'),
                                     (str(HERE), '[private]'), ('/reference', '[private]'),
                                     ('/opt/blackbox', '[private]'), ('/app/solution', '[private]')])

    # Lifecycle ----------------------------------------------------------------------------------------------
    def launch(self, fresh):
        if self.product.start(fresh=fresh):
            wait_ready(self.product)
            self.settle(0.3)
        status = self.product.status()
        self.log.note('status: ' + json.dumps(status))
        return status

    def start(self):
        with self.lock:
            return self.launch(fresh=True)

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
            return blank_observation(self.product.process())
        deadline = time.monotonic() + 1.0
        while self.product.running() and not terminal.drawn() and time.monotonic() < deadline:
            time.sleep(0.05)
        return terminal.observe(self.product.process(), self.redact)

    def send(self, raw, minimum=0.1):
        self.product.write(raw)
        self.settle(minimum)
        return self.observe(0)

    def send_keys(self, keys):
        """Send a key batch; a lone Escape is followed by a pause so that curses does not read it as the start of
        an escape sequence together with the next key."""
        cursor = self.product.terminal and self.product.terminal.application_cursor()
        pending = ''
        for name in keys:
            raw = key_bytes(name, cursor)
            if raw == '\x1b':
                self.product.write(pending + raw)
                pending = ''
                time.sleep(ESCAPE_PAUSE)
                continue
            pending += raw
        if pending:
            self.product.write(pending)
        self.settle(0.1)
        return self.observe(0)

    # Dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = validate_request(data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'terminal', OPERATIONS, limits=LIMITS, notes=NOTES,
                                         examples=EXAMPLES, key_names=KEY_NAMES, modifiers=['Control', 'Alt', 'Shift'],
                                         clock={'utc': CLOCK, 'frozen': True})
        if op == 'status':
            return self.redact_value(self.product.status())
        if op == 'docs':
            return read_doc(data)
        with self.lock:
            if op == 'reset':
                self.product.stop()
                return self.redact_value(self.launch(fresh=True))
            if op == 'restart':
                self.product.stop()
                return self.redact_value(self.launch(fresh=False))
            if op == 'screen':
                return self.observe()
            if op == 'key':
                return self.send_keys([data['key']])
            if op == 'keys':
                return self.send_keys(data['keys'])
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
            if op == 'files':
                result = inspect(self.product, data)
                if 'body_base64' in result:
                    # Files the application writes may hold absolute paths: redact the bytes as well as the text.
                    raw = self.redact_bytes(base64.b64decode(result['body_base64']))
                    result.update(size=len(raw), body_base64=base64.b64encode(raw).decode(),
                                  text=raw.decode('utf-8', 'replace'))
                return self.redact_value(result)
            if op == 'place':
                self.product.stop()
                try:
                    place(self.product, data['files'])
                finally:
                    status = self.launch(fresh=False)
                return self.redact_value(status)
            if op == 'cli':
                return self.redact_value(run_cli(self.product, check_args(data['args'])))
            raise ValueError('Unknown operation; use help')

    def redact_bytes(self, raw):
        for root, name in self.redact.pairs:
            raw = raw.replace(root.encode('utf-8', 'surrogateescape'), name.encode('utf-8'))
        return raw

    def redact_value(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.redact_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.redact_value(v) for k, v in value.items()}
        return value


EXAMPLES = [{'op': 'screen'}, {'op': 'key', 'key': 'Tab'}, {'op': 'keys', 'keys': ['l', 'l', 'j']},
            {'op': 'key', 'key': 'a'}, {'op': 'type', 'text': '10:00'}, {'op': 'key', 'key': 'Enter'},
            {'op': 'files', 'action': 'tree'}, {'op': 'files', 'action': 'read', 'path': '~/.local/share/calcurse/apts'},
            {'op': 'place', 'files': {'import/team.ics': 'BEGIN:VCALENDAR\r\n...\r\nEND:VCALENDAR\r\n'}},
            {'op': 'cli', 'args': ['-Q', '--from', '03/18/2026', '--days', '7']},
            {'op': 'cli', 'args': ['-i', 'import/team.ics']}, {'op': 'cli', 'args': ['-x', 'ical']},
            {'op': 'docs'}, {'op': 'docs', 'topic': 'add'}]


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
    elif op == 'files':
        components(data.get('path', HOME))
    elif op == 'place':
        check_files(data['files'])
    elif op == 'cli':
        check_args(data['args'])
    elif op == 'docs':
        if 'topic' in data and data['topic'] not in doc_topics():
            raise ValueError('topic must be one of: ' + ', '.join(doc_topics()))
    return op


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
