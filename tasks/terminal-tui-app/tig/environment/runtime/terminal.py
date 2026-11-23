"""PTY input and xterm screen emulation for the application."""
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

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

PRODUCT = 'tig'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_PLACED = 512
MAX_STYLES = 400
RPC_TIMEOUT_SEC = 90
QUIET = 0.3
SETTLE_MAX = 4.0
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
ORIGIN = '/workspace'
CLI_TIMEOUT = 20
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


# -- product in a pseudo-terminal ------------------------------------------------------------------------------
class TerminalProduct(runtime.Product):
    """start.sh as the controlling-terminal session of a pseudo-terminal."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log,
                         env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
                              'PYTHONHASHSEED': '0', 'NCURSES_NO_UTF8_ACS': '1'})
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()

    @property
    def workspace(self):
        return Path(self.directories['DATA_DIR']) / 'repository'

    def environment(self):
        env = super().environment()
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


