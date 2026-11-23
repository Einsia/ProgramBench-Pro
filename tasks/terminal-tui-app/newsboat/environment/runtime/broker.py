#!/usr/bin/env python3
"""Newsboat terminal runtime.

One instance drives one application directory in an emulated xterm-256color
pseudo-terminal. Terminal operations return settled screen text and styles.
Other channels expose the instance's home files, a read-only SQLite snapshot,
local feed inputs and bounded command-line invocations.
"""
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
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
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

PRODUCT = 'newsboat'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
HOME = '~'                      # how DATA_DIR (Newsboat's home directory) is shown in every answer
MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_CACHE_BYTES = 32 * 1024 * 1024
MAX_CACHE_ROWS = 20_000
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_PLACED = 256
MAX_STYLES = 600
MAX_CLI_ARGS = 16
RPC_TIMEOUT_SEC = 120
QUIET = 0.3
SETTLE_MAX = 4.0
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
CLI_TIMEOUT = 60
# The cache files the runtime never overwrites (place) and reads only as tables (cache).
CACHE_FILES = ('cache.db', 'cache.db-journal', 'cache.db-wal', 'cache.db-shm', 'cache.db.lock')


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
        self.observed_content = None
        self.content_since = time.monotonic()

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

    def interface_drawn(self, started):
        """A painted alternate screen, or stable visible content in a plain terminal.

        Startup diagnostics are output, but may precede initialization of the interactive application.
        Alternate-screen entry is a terminal protocol signal, not a product-specific endpoint. Programs
        Repainting identical content does not reset the stability timer.
        """
        with self.lock:
            content = tuple(self.line(y) for y in range(self.rows))
            now = time.monotonic()
            if content != self.observed_content:
                self.observed_content, self.content_since = content, now
            if not any(line.strip() for line in content):
                return False
            return (self.screen.saved_primary is not None or
                    now - max(started, self.content_since) >= 2.0)

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
            # so every highlighted run (title and hint bars, the focused row, unread rows, highlights) is listed.
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
# A fresh data directory is seeded with this starter subscription before the application first starts (Newsboat
# refuses to start without a subscription). It is environment data, written by the runtime for any solution.
STARTER_FEED = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Welcome</title>
<link>https://newsboat.org/</link>
<description>A local starter feed</description>
<item>
<title>Getting started</title>
<link>https://newsboat.org/docs/getting-started</link>
<guid>welcome-1</guid>
<pubDate>Mon, 01 Jan 2024 09:00:00 +0000</pubDate>
<description>&lt;p&gt;Subscribe to feeds by listing their URLs in &lt;b&gt;~/.newsboat/urls&lt;/b&gt;.&lt;/p&gt;</description>
</item>
<item>
<title>Reading articles</title>
<link>https://newsboat.org/docs/reading</link>
<guid>welcome-2</guid>
<pubDate>Tue, 02 Jan 2024 09:00:00 +0000</pubDate>
<description>&lt;p&gt;Press &lt;i&gt;Enter&lt;/i&gt; to open a feed or an article.&lt;/p&gt;</description>
</item>
</channel>
</rss>
'''
STARTER = {'.newsboat/urls': 'file://feeds/welcome.xml\n', 'feeds/welcome.xml': STARTER_FEED}


class TerminalProduct(runtime.Product):
    """start.sh as the controlling-terminal session of a pseudo-terminal."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log,
                         env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC', 'ESCDELAY': '50'})
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

    def own(self, path):
        if self.switching():
            account = self.account()
            os.lchown(path, account.pw_uid, account.pw_gid)

    def seed(self):
        """Write the starter subscription into a fresh data directory."""
        account = self.account()
        with runtime.open_directory(self.home) as home_fd:
            if runtime.list_directory(home_fd):
                return
            for name, text in STARTER.items():
                parent, leaf = name.split('/', 1)
                with runtime.owned_directory(home_fd, parent, uid=account.pw_uid,
                                             gid=account.pw_gid, mode=0o755) as parent_fd:
                    runtime.atomic_write(parent_fd, leaf, text, uid=account.pw_uid,
                                         gid=account.pw_gid, mode=0o644)

    def start(self, fresh=False, args=()):
        self.stop()
        self.prepare(fresh)
        self.seed()
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
            self.proc = subprocess.Popen(['setsid', '--ctty', str(script), *args], cwd=str(self.home),
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
    started = time.monotonic()
    ok = runtime.wait_until(product, lambda: product.terminal.interface_drawn(started), deadline=limit, interval=0.1,
                            failure=f'the application did not draw its interface within {limit:g} s')
    return ok



# -- home directory access (confined, never follows symlinks: every component is opened with O_NOFOLLOW) --------
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
            except (NotADirectoryError, OSError) as exc:
                if isinstance(exc, FileNotFoundError):
                    raise
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
                    result['sha256'] = hashlib.sha256(runtime.read_bounded(fd, limit=MAX_HASH_BYTES)).hexdigest()
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
        if len(parts) == 2 and parts[0] == '.newsboat' and parts[1] in CACHE_FILES:
            raise ValueError('the cache is written only by the application')
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
    runtime.remove_entry(dfd, name)


def place(product, files):
    """Write setup files into the home directory while the application is stopped (never through symlinks)."""
    root = product.home
    account = product.account() if product.switching() else None

    def own_at(dfd, name):
        if account:
            os.chown(name, account.pw_uid, account.pw_gid, dir_fd=dfd, follow_symlinks=False)
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
                mtime = value.get('mtime') if isinstance(value, dict) else None
                ns = (int(mtime * 1_000_000_000),) * 2 if mtime is not None else None
                runtime.set_metadata(fd, mode=0o644, ns=ns,
                                     uid=account.pw_uid if account else None,
                                     gid=account.pw_gid if account else None)
            finally:
                os.close(fd)
        finally:
            os.close(dfd)


# -- the SQLite cache (read-only snapshot of Newsboat's own cache.db) ------------------------------------------
CACHE_TABLES = ('rss_feed', 'rss_item', 'metadata')


def read_cache(product, data, work):
    """Read a consistent SQLite snapshot, including committed WAL frames, without following source links.

    Pause the product while copying the bounded database and journal files into runtime-private scratch.
    SQLite recovers the private copy with its ordinary WAL/journal rules. No source database is opened by
    SQLite, so its automatic sidecar handling cannot follow an application-controlled symlink. The product is
    always resumed before parsing the copy, including on errors.
    """
    table = data['table']
    if table not in CACHE_TABLES:
        raise ValueError('table must be one of: ' + ', '.join(CACHE_TABLES))
    import signal
    paused = False
    captured = {}
    try:
        if product.running():
            os.killpg(product.proc.pid, signal.SIGSTOP)
            paused = True
            # SIGSTOP is asynchronous. Wait until the main process has actually stopped.
            deadline = time.monotonic()+2
            while time.monotonic() < deadline:
                info = Path(f'/proc/{product.proc.pid}/stat').read_text()
                if info.rsplit(')',1)[1].strip().split()[0] in ('T','t'):
                    break
                time.sleep(.005)
            else:
                raise ValueError('the cache writer could not be paused')
        for name in ('cache.db','cache.db-wal','cache.db-journal'):
            try:
                captured[name] = read_beneath(product.home, ['.newsboat',name], MAX_CACHE_BYTES)
            except ValueError as exc:
                if 'no such' not in str(exc):
                    raise
    finally:
        if paused:
            try:
                os.killpg(product.proc.pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
    if 'cache.db' not in captured:
        return {'table':table,'exists':False,'columns':[],'rows':[]}
    scratch = Path(work) / 'cache-snapshot'
    scratch.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as folder:
        for name, content in captured.items():
            (Path(folder)/name).write_bytes(content)
        try:
            conn = sqlite3.connect(str(Path(folder)/'cache.db'), timeout=2)
        except sqlite3.Error as exc:
            raise ValueError(f'the cache is not an SQLite database: {exc}') from None
        try:
            try:
                conn.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
                conn.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)
            except (AttributeError, sqlite3.Error):
                pass
            kind = conn.execute("SELECT type FROM sqlite_master WHERE name = ?", (table,)).fetchone()
            if not kind or kind[0] != 'table':
                return {'table': table, 'exists': False, 'columns': [], 'rows': []}
            conn.execute('PRAGMA trusted_schema=OFF')
            deadline=time.monotonic()+3
            conn.set_progress_handler(lambda: time.monotonic()>deadline,10000)
            cursor = conn.execute(f'SELECT * FROM "{table}" LIMIT {MAX_CACHE_ROWS + 1}')
            columns = [c[0] for c in cursor.description]
            rows = []
            for row in cursor:
                rows.append([v if not isinstance(v, bytes) else base64.b64encode(v).decode() for v in row])
            if len(rows) > MAX_CACHE_ROWS:
                raise ValueError(f'the table has more than {MAX_CACHE_ROWS} rows')
            return {'table': table, 'exists': True, 'columns': columns, 'rows': rows}
        except sqlite3.Error as exc:
            raise ValueError(f'the cache could not be read: {exc}') from None
        finally:
            conn.close()


# -- command line (the product's own options, whitelisted; file arguments are confined to the home directory) --
CLI_FLAGS = {'-e': 'export', '--export-to-opml': 'export', '--export-to-opml2': 'export', '-v': 'info',
             '--version': 'info', '-V': 'info', '-h': 'info', '--help': 'info', '-X': 'vacuum', '--vacuum': 'vacuum',
             '--cleanup': 'cleanup', '-q': None, '--quiet': None}
CLI_FILES = {'-i': 'import', '--import-from-opml': 'import', '-E': 'readinfo', '--export-to-file': 'readinfo',
             '-I': 'readinfo', '--import-from-file': 'readinfo', '-u': None, '--url-file': None, '-c': None,
             '--cache-file': None, '-C': None, '--config-file': None, '--queue-file': None,
             '--search-history-file': None, '--cmdline-history-file': None}
CLI_COMMANDS = ('reload', 'print-unread')
START_FLAGS = {'-r': None, '--refresh-on-start': None, '-q': None, '--quiet': None}
START_FILES = {k: None for k in ('-u', '--url-file', '-c', '--cache-file', '-C', '--config-file', '--queue-file',
                                 '--search-history-file', '--cmdline-history-file')}


def check_args(args, interactive):
    """Validate a command line for the cli channel (one-shot options) or for an interactive start."""
    if not isinstance(args, list) or len(args) > MAX_CLI_ARGS or not all(isinstance(a, str) for a in args):
        raise ValueError(f'args must be a list of at most {MAX_CLI_ARGS} strings')
    flags, files = (START_FLAGS, START_FILES) if interactive else (CLI_FLAGS, CLI_FILES)
    actions, i, out = set(), 0, []
    while i < len(args):
        arg = printable(args[i], 'argument', 512)
        name, _, inline = arg.partition('=') if arg.startswith('--') else (arg, '', '')
        if name in flags and not inline:
            if flags[name]:
                actions.add(flags[name])
            out.append(arg)
            i += 1
            continue
        if name in files:
            if inline or arg.startswith('--') and '=' in arg:
                value = inline
                out.append(arg)
                i += 1
            else:
                if i + 1 >= len(args):
                    raise ValueError(f'{name} needs a file argument')
                value = printable(args[i + 1], 'argument', 512)
                out += [arg, value]
                i += 2
            if not components(value, f'the file of {name}'):
                raise ValueError(f'{name} needs a file inside the home directory')
            if files[name]:
                actions.add(files[name])
            continue
        if not interactive and name in ('-x', '--execute') and not inline:
            commands = []
            i += 1
            while i < len(args) and not args[i].startswith('-'):
                if args[i] not in CLI_COMMANDS:
                    raise ValueError('-x runs these commands: ' + ', '.join(CLI_COMMANDS))
                commands.append(args[i])
                i += 1
            if not commands:
                raise ValueError('-x needs at least one command: ' + ', '.join(CLI_COMMANDS))
            out += ['-x'] + commands
            actions.add('execute')
            continue
        allowed = sorted(set(flags) | set(files) | (set() if interactive else {'-x', '--execute'}))
        raise ValueError(f'unsupported argument {arg!r}; the accepted options are: ' + ', '.join(allowed))
    if not interactive and not actions:
        raise ValueError('a command-line run needs an option that makes the application print or act and exit: '
                         '-e, --export-to-opml2, -i, -E, -I, -x, -X, --cleanup, -v or -h')
    return out


def run_cli(product, args):
    """Run start.sh once with the given options (no terminal, standard input closed) and return its output."""
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
    try:
        proc = subprocess.Popen([str(script), *args], cwd=str(product.home), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, **kwargs)
    except OSError as exc:
        raise ValueError(f'start.sh could not be executed ({exc.strerror or exc})') from None
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    limited, timed_out = False, False
    selector = selectors.DefaultSelector()
    for name in buffers:
        pipe = getattr(proc,name)
        os.set_blocking(pipe.fileno(), False)
        selector.register(pipe,selectors.EVENT_READ,name)
    deadline = time.monotonic()+CLI_TIMEOUT
    try:
        while selector.get_map():
            if time.monotonic() >= deadline:
                timed_out=True
                break
            for key,_ in selector.select(min(.1,max(0,deadline-time.monotonic()))):
                block = os.read(key.fileobj.fileno(),65536)
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                target=buffers[key.data]
                remaining=MAX_FILE_BYTES-len(target)
                target.extend(block[:remaining])
                if len(block)>remaining:
                    limited=True
                    break
            if limited:
                break
        if not (limited or timed_out):
            try:
                proc.wait(max(.001,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out=True
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
              **{name:bytes(value).decode('utf-8','replace') for name,value in buffers.items()}}
    if timed_out:
        result['timed_out'] = True
    if limited:
        result['output_limited'] = True
    return result


# -- RPC interface ---------------------------------------------------------------------------------------------
class LocalFeedHTTP:
    """Offline HTTP feed inputs. Never fetches URLs or serves filesystem paths."""
    PORT = 48081

    def __init__(self):
        self.routes={};self.requests=[];self.positions={};self.lock=threading.Lock()
        source=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.answer(False)
            def do_HEAD(self):self.answer(True)
            def answer(self,head):
                with source.lock:
                    options=source.routes.get(self.path,[{'status':404,'body':'Missing response'}])
                    index=source.positions.get(self.path,0)
                    item=options[min(index,len(options)-1)]
                    source.positions[self.path]=index+1
                    if len(source.requests)<256:
                        source.requests.append({'path':self.path,'method':self.command,'status':item.get('status',200),
                            'headers':{name:self.headers[name] for name in ['If-None-Match','If-Modified-Since','Cookie','User-Agent'] if self.headers.get(name)}})
                body=item.get('body','').encode('utf-8')
                self.send_response(item.get('status',200))
                for name,value in item.get('headers',{}).items():self.send_header(name,value)
                self.send_header('Content-Length',str(len(body)));self.end_headers()
                if not head and body:
                    try:self.wfile.write(body)
                    except (BrokenPipeError,ConnectionResetError):pass
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',self.PORT),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def set(self,routes):
        with self.lock:self.routes=routes;self.requests=[];self.positions={}
        return {'base_url':f'http://127.0.0.1:{self.PORT}','routes':sorted(routes)}

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)


PATH_FIELD = {'type': 'string', 'description': f'{HOME} or a path below it (relative paths are relative to {HOME}); '
                                               f'default {HOME}.'}
ARGS_HELP = ('Command-line arguments, one per list item (an option and its value as two items, or --long=value). '
             'File arguments must be paths inside the home directory.')
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, key names, limits and notes on the '
                                        'reference (reference_controls).', 'fields': {}},
    'status': {'kind': 'lifecycle', 'fields': {},
               'summary': 'Whether the application is running and ready, and its exit status once it ended.'},
    'http_source': {'kind':'files','summary':'Configure an offline loopback feed server at '
                     'http://127.0.0.1:48081. Each path has a response sequence; after the final response it repeats. '
                     'Reconfiguration clears request history. reset clears routes. No external URL is fetched.',
                     'fields':{'routes':{'type':'object','required':True,'description':'Path -> list of response '
                     'objects with optional status (100-599), headers (string map), and body (UTF-8 text). '
                     'At most 32 paths and 16 responses per path, within the RPC request size limit.'}}},
    'http_requests': {'kind':'observe','summary':'Read up to 256 requests to the configured local HTTP feed server: '
                     'path, method, response status and conditional/cookie/user-agent request headers.', 'fields':{}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Restart the application with a fresh home directory (its initial state: the starter '
                         f'subscription only) in a fresh {COLUMNS}x{ROWS} terminal.'},
    'restart': {'kind': 'lifecycle',
                'summary': 'Stop the application if it is running (SIGTERM) and start it again with the same home '
                           f'directory in a fresh {COLUMNS}x{ROWS} terminal, optionally with interactive '
                           'command-line options.',
                'fields': {'args': {'type': 'array', 'items': {'type': 'string'},
                                    'description': ARGS_HELP + ' Accepted: -r/--refresh-on-start, -q/--quiet, '
                                    '-u/--url-file, -c/--cache-file, -C/--config-file, --queue-file, '
                                    '--search-history-file, --cmdline-history-file.'}}},
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
    'home': {'kind': 'files', 'summary': f"Read-only inspector of the application's home directory ({HOME}, which "
             'holds .newsboat/ with urls, config, cache.db, queue and the history files, and any feed files): list '
             'one directory, tree (recursive), stat one entry, or read a regular file. Hidden entries are included; '
             'symlinks are reported, never followed.',
             'fields': {'action': {'type': 'string', 'enum': ['list', 'tree', 'stat', 'read'],
                                   'description': f'list, tree, stat or read (at most {MAX_FILE_BYTES} bytes); '
                                                  'default list.'},
                        'path': PATH_FIELD}},
    'place': {'kind': 'files', 'summary': 'Write files into the home directory (for example feed files, '
              '.newsboat/urls or .newsboat/config) while the application is stopped, then start it again with the '
              'same home directory. The cache files are written only by the application.',
              'fields': {'files': {'type': 'object', 'required': True,
                                   'description': f'path inside {HOME} -> UTF-8 text, {{"base64": ..., "mtime": '
                                                  'seconds}, {"remove": true} to delete a file or directory, or null '
                                                  f'for a directory; at most {MAX_PLACED} entries.'}}},
    'update_inputs': {'kind':'files', 'summary':'Replace subscription/configuration/feed input files while the '
                       'application stays running. This simulates another editor updating local inputs; the '
                       'application decides when to reload them. Only .newsboat/urls, .newsboat/config and '
                       'files under feeds/ are accepted; cache and output files are not accepted.',
                      'fields':{'files':{'type':'object','required':True,'description':'Path -> UTF-8 text or '
                                   '{"base64": ...}; same path and size limits as place.'}}},
    'cache': {'kind': 'files', 'summary': "Read one table of the application's SQLite cache (~/.newsboat/cache.db) "
              'from a consistent snapshot: its column names and rows in storage order.',
              'fields': {'table': {'type': 'string', 'enum': list(CACHE_TABLES), 'required': True,
                                   'description': 'The table to read.'}}},
    'cli': {'kind': 'info', 'summary': 'Run the application once with command-line options that make it act and '
            'exit (as a user does in a shell after quitting it): the interactive application is stopped first '
            '(SIGTERM), start.sh runs with the arguments, no terminal and standard input closed, and its exit code, '
            'standard output and standard error are returned; then the interactive application is started again '
            'with the same home directory.',
            'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                'description': ARGS_HELP + ' Accepted: -e/--export-to-opml, --export-to-opml2, '
                                '-i/--import-from-opml FILE, -E/--export-to-file FILE, -I/--import-from-file FILE, '
                                '-x/--execute with reload and/or print-unread, -X/--vacuum, --cleanup, -v/-V/--version, '
                                '-h/--help, -q/--quiet, -u/--url-file, -c/--cache-file, -C/--config-file, '
                                '--queue-file, --search-history-file, --cmdline-history-file.'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'read_bytes': MAX_FILE_BYTES, 'tree_entries': MAX_TREE_ENTRIES,
          'cache_bytes': MAX_CACHE_BYTES, 'cache_rows': MAX_CACHE_ROWS, 'key_batch': MAX_KEY_BATCH,
          'type_characters': MAX_TEXT, 'placed_files': MAX_PLACED, 'cli_arguments': MAX_CLI_ARGS,
          'cli_seconds': CLI_TIMEOUT, 'terminal_columns': [40, 240], 'terminal_rows': [10, 80], 'wait_seconds': 3,
          'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': MAX_STYLES, 'screen': [COLUMNS, ROWS]}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, scrolling regions, colours, wide and combined characters); screen shows what a user '
    'of a real terminal sees.',
    'key, keys, type, resize and wait return the screen once output has settled (no new output for 0.3 s, at '
    'most 4 s); screen waits the same way. Reloading feeds runs in the background: wait until it has finished '
    'before reading the result.',
    f'The home directory {HOME} is both HOME and DATA_DIR of the application and its working directory. A file:// '
    'URL without a leading slash (for example file://feeds/news.xml) names a file relative to it.',
    'reset starts from a fresh home directory holding only the starter subscription (.newsboat/urls with '
    'file://feeds/welcome.xml); restart, place and cli keep the home directory. The application is stopped with '
    'SIGTERM before restart, place and cli, as a terminated process: what it would only save when quitting is '
    'not saved.',
    'There is no external network: file:// feeds and the loopback HTTP inputs can be loaded. The application cannot start other programs, so '
    'features that run one (a browser, a pager, notify or bookmark commands, exec: and filter: feeds, pipes) '
    'fail as they would when the program cannot be run.',
    f'home, place, cache and cli operate independently of the interactive terminal. '
    f'Private runtime locations in screens, answers and errors are shown as {HOME} (the home directory) or '
    '[private].',
    'The cli channel streams output into bounded buffers (at most 1 MiB per stream). If a command exceeds the '
    'bound it is terminated and the response includes output_limited; a command that exceeds the time limit includes '
    'timed_out. The runtime remains available and restarts the interactive application afterward.',
]
REFERENCE_CONTROLS = {
    'note': "Newsboat 2.45 with its default configuration. In the application, ? opens the key bindings of the "
            'current dialog, : opens the command line, and :dumpconfig FILE writes every setting with its current '
            'value. The official documentation describes the urls file, the config commands, filters, query feeds, '
            'killfiles, macros, tagging, format strings and the command-line options; key names and commands below '
            'are the reference names.',
    'cmdline_commands': ['quit', 'q', 'save <file>', 'set <variable>[=<value>|&|!]', 'tag <tagname>',
                         'goto <substring>', 'source <file> ...', 'dumpconfig <file>', 'exec <operation>', '<number>'],
    'urls_file': 'One feed URL per line, optionally followed by tags; a tag "~Name" renames the feed, a tag "!" '
                 'hides it; "query:Name:<filter expression>" defines a query feed; lines starting with # are '
                 'comments.',
    'filter_language': {
        'syntax': 'ATTRIBUTE OP VALUE, combined with and/or and parentheses. Quote strings with double quotes. '
                  'Operators: = or ==, !=, =~ (case-insensitive POSIX regular expression), !~, <, >, <=, >=, '
                  'between LOWER:UPPER, # (word in a space-separated list), !#.',
        'article_attributes': ['title', 'link', 'author', 'content', 'date', 'guid', 'unread', 'enclosure_url',
                               'enclosure_type', 'flags', 'age', 'articleindex'],
        'feed_attributes': ['feedtitle', 'description', 'feedlink', 'feeddate', 'rssurl', 'unread_count',
                            'total_count', 'tags', 'feedindex', 'latest_article_age'],
        'note': 'Article filters also accept the attributes of their containing feed. F sets a filter; '
                'Control+f clears it; f selects a filter declared with define-filter NAME EXPRESSION.'},
    'configuration': 'Configuration lines are COMMAND ARGUMENTS, with double-quoted strings and # comments. '
                     'dumpconfig exports all current settings and bindings. Config commands include include, '
                     'bind-key KEY OPERATION [DIALOG], unbind-key KEY [DIALOG], bind SEQUENCE DIALOG COMMANDS, '
                     'macro KEY COMMANDS, define-filter NAME EXPRESSION, ignore-article FEED EXPRESSION, '
                     'color ELEMENT FOREGROUND BACKGROUND [ATTRIBUTES], highlight TARGET REGEX FOREGROUND, '
                     'highlight-article EXPRESSION FOREGROUND BACKGROUND and highlight-feed with the same syntax. '
                     'A macro/bind command list uses semicolons; macro-prefix is comma. Ignore mode is download '
                     '(omit matching articles from cache) or display (hide matches when displaying).',
}


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
        self.http_source=None
        layout = self.product.directories
        self.redact = make_redactor([(layout['DATA_DIR'], HOME)] +
                                    [(path, '[private]') for key, path in layout.items() if key != 'DATA_DIR'] +
                                    [(config.state, '[private]'), (config.solution, '[private]'),
                                     (config.work, '[private]'), (config.log_dir, '[private]'),
                                     (str(HERE), '[private]'), ('/reference', '[private]'),
                                     ('/opt/blackbox', '[private]'), ('/app/solution', '[private]')])

    # Lifecycle ----------------------------------------------------------------------------------------------
    def launch(self, fresh, args=()):
        if self.product.start(fresh=fresh, args=args):
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
        if self.http_source is not None:self.http_source.close()

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
                self.product.stop()
                if self.http_source is not None:self.http_source.set({})
                return self.redact_value(self.launch(fresh=True))
            if op == 'http_source':
                if self.http_source is None:self.http_source=LocalFeedHTTP()
                return self.http_source.set(data['routes'])
            if op == 'http_requests':
                if self.http_source is None:return {'requests':[]}
                with self.http_source.lock:return {'requests':list(self.http_source.requests)}
            if op == 'restart':
                args = check_args(data.get('args', []), interactive=True)
                self.product.stop()
                return self.redact_value(self.launch(fresh=False, args=args))
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
            if op == 'home':
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
            if op == 'update_inputs':
                place(self.product,data['files'])
                return {'updated':sorted(data['files']), 'running':self.product.running()}
            if op == 'cache':
                return self.redact_value(read_cache(self.product, data, self.config.work))
            if op == 'cli':
                args = check_args(data['args'], interactive=False)
                self.product.stop()
                try:
                    result = run_cli(self.product, args)
                finally:
                    status = self.launch(fresh=False)
                result['restarted'] = status
                return self.redact_value(result)
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


EXAMPLES = [{'op': 'screen'}, {'op': 'key', 'key': 'Enter'}, {'op': 'keys', 'keys': ['Down', 'Down', 'Enter']},
            {'op': 'key', 'key': ':'}, {'op': 'type', 'text': 'set show-read-feeds no'}, {'op': 'key', 'key': 'R'},
            {'op': 'home', 'action': 'tree'}, {'op': 'home', 'action': 'read', 'path': '~/.newsboat/urls'},
            {'op': 'place', 'files': {'feeds/news.xml': '<rss version="2.0">...</rss>',
                                      '.newsboat/urls': 'file://feeds/news.xml "~News" tech\n'}},
            {'op': 'cache', 'table': 'rss_item'}, {'op': 'cli', 'args': ['-x', 'reload', 'print-unread']},
             {'op': 'cli', 'args': ['--export-to-opml']}, {'op': 'restart', 'args': ['-r']},
             {'op':'update_inputs','files':{'.newsboat/urls':'file://feeds/news.xml\n'}},
             {'op':'http_source','routes':{'/feed':[{'body':'<rss version="2.0">...</rss>'}]}},
             {'op':'http_requests'}]


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
    elif op == 'home':
        components(data.get('path', HOME))
    elif op in ('place','update_inputs'):
        check_files(data['files'])
        if op=='update_inputs':
            for name,value in data['files'].items():
                parts=components(name)
                if parts not in (['.newsboat','urls'],['.newsboat','config']) and not (len(parts)>1 and parts[0]=='feeds'):
                    raise ValueError('update_inputs only replaces subscription, configuration and feed input files')
                if not isinstance(value,str) and not (isinstance(value,dict) and set(value)=={'base64'}):
                    raise ValueError('update_inputs requires text or base64 file contents')
    elif op == 'cli':
        check_args(data['args'], interactive=False)
    elif op == 'restart':
        check_args(data.get('args', []), interactive=True)
    elif op == 'http_source':
        routes=data['routes']
        if len(routes)>32:raise ValueError('at most 32 local HTTP paths')
        for path,items in routes.items():
            printable(path,'HTTP path',512)
            if not path.startswith('/') or not isinstance(items,list) or not 1<=len(items)<=16:
                raise ValueError('HTTP paths start with / and have 1-16 responses')
            for item in items:
                if not isinstance(item,dict) or set(item)-{'status','body','headers'}:raise ValueError('invalid HTTP response fields')
                if not isinstance(item.get('status',200),int) or not 100<=item.get('status',200)<=599:raise ValueError('invalid HTTP status')
                if not isinstance(item.get('body',''),str):raise ValueError('HTTP body must be text')
                headers=item.get('headers',{})
                if not isinstance(headers,dict) or len(headers)>32:raise ValueError('invalid HTTP headers')
                for key,value in headers.items():
                    printable(key,'header name',128);printable(value,'header value',2048)
                    if not re.fullmatch('[A-Za-z0-9-]+',key) or key.lower() in ('content-length','transfer-encoding'):
                        raise ValueError('unsupported HTTP header')
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
