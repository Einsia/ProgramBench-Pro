#!/usr/bin/env python3
"""micro terminal runtime.

One instance drives the editor in a pseudo-terminal and exposes terminal input,
workspace files, configuration and native command-line output.
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
import stat
import struct
import subprocess
import sys
import termios
import threading
import time
import unicodedata
from urllib.parse import quote

import http.server
import socketserver

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import blackbox_runtime as runtime  # noqa: E402
import workspace_files as safe_files  # noqa: E402
from commands import run_bounded  # noqa: E402

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

PRODUCT = 'micro'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
MAX_REQUEST_BYTES = 512 * 1024
MAX_FILE_BYTES = 1024 * 1024
MAX_HASH_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 20_000
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_PLACED = 512
MAX_ARGS = 16
MAX_STYLES = 400
RPC_TIMEOUT_SEC = 90
QUIET = 0.3
FIRST_OUTPUT = 1.5
SETTLE_MAX = 6.0
KEY_GAP = 0.01
ESCAPE_GAP = 0.15
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
MOUSE_MODES = {1000 << 5, 1002 << 5, 1003 << 5}  # X11 mouse reporting (press/release, button motion, any motion)
MOUSE_SGR = 1006 << 5
BRACKETED_PASTE = 2004 << 5
ORIGIN = '/workspace'
CLI_TIMEOUT = 20
CLI_OPTIONS = ('-version', '-options', '-help')
CONFIG_FILES = ('settings.json', 'bindings.json')
# Runtime files micro reads from its configuration directory that are data, not code: colour schemes, syntax
# definitions and help pages. Lua (init.lua, plug/) is not placeable.
CONFIG_DIRS = {'colorschemes': '.micro', 'syntax': '.yaml', 'help': '.md'}
# micro 2.0.15 options, as listed by `micro -options`; each may be given on the command line as `-name value`.
OPTION_NAMES = frozenset('''autoindent autosave autosu backup backupdir basename clipboard colorcolumn colorscheme
    cursorline detectlimit diffgutter divchars divreverse encoding eofnewline fakecursor fastdirty fileformat filetype
    helpsplit hlsearch hltaberrors hltrailingws ignorecase incsearch indentchar infobar keepautoindent keymenu
    lockbindings matchbrace matchbraceleft matchbracestyle mkparents mouse multiopen pageoverlap parsecursor paste
    permbackup pluginchannels pluginrepos readonly relativeruler reload rmtrailingws ruler savecursor savehistory
    saveundo scrollbar scrollbarchar scrollmargin scrollspeed showchars smartpaste softwrap splitbottom splitright
    statusformatl statusformatr statusline sucmd syntax tabhighlight tabmovement tabreverse tabsize tabstospaces
    truecolor useprimary wordwrap xterm'''.split())


# -- keys ------------------------------------------------------------------------------------------------------
SIMPLE = {'enter': '\r', 'return': '\r', 'escape': '\x1b', 'esc': '\x1b', 'tab': '\t', 'backspace': '\x7f',
          'bs': '\x7f', 'space': ' '}
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
KEY_HELP = ('One key: a single printable character (for example a, >, / or Q), or a name: ' + ', '.join(KEY_NAMES) +
            ' (case-insensitive), optionally combined with Control+, Alt+ or Shift+ (for example Control+S, '
            'Alt+Shift+Up, Shift+Tab, Control+Shift+Right, Alt+Backspace).')


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


# -- mouse (xterm SGR reporting, which micro enables) ----------------------------------------------------------
MOUSE_ACTIONS = ('click', 'double', 'triple', 'drag', 'scroll')
MOUSE_BUTTONS = {'left': 0, 'middle': 1, 'right': 2}
WHEEL = {'up': 64, 'down': 65, 'left': 66, 'right': 67}
MOUSE_MODIFIERS = {'shift': 4, 'alt': 8, 'control': 16}


def mouse_sequences(data, columns, rows, sgr=True):
    """The mouse reports of one mouse operation, as (text, pause-after) pairs: SGR reports (DECSET 1006), or the
    legacy X10 encoding when the application has not asked for SGR. The presses of a double or triple click (also
    the clicks that start a drag) go out in one write, so the application sees them as one gesture however busy
    the machine is."""
    def cell(row, column):
        if not (isinstance(row, int) and isinstance(column, int) and 0 <= row < rows and 0 <= column < columns):
            raise ValueError(f'mouse positions must be screen cells: rows 0-{rows - 1}, columns 0-{columns - 1}')
        return column + 1, row + 1
    action = data['action']
    mods = 0
    for name in data.get('modifiers', []):
        if not isinstance(name, str) or name.lower() not in MOUSE_MODIFIERS:
            raise ValueError('modifiers are Control, Alt and Shift')
        mods |= MOUSE_MODIFIERS[name.lower()]
    def report(code, x, y, release=False):
        if sgr:
            return f'\x1b[<{code};{x};{y}{"m" if release else "M"}'
        # X10/normal encoding: a release is button 3; coordinates are offset by 32 (at most 223).
        code = (3 | (code & ~3)) if release else code
        return '\x1b[M' + chr(32 + code) + chr(32 + min(x, 223)) + chr(32 + min(y, 223))
    x, y = cell(data['row'], data['column'])
    if action == 'scroll':
        direction = data.get('direction', 'down')
        if direction not in WHEEL:
            raise ValueError('scroll direction is up, down, left or right')
        return [(report(WHEEL[direction] | mods, x, y), 0.05)]
    button = MOUSE_BUTTONS.get(data.get('button', 'left'))
    if button is None:
        raise ValueError('button is left, middle or right')
    code = button | mods
    press, release = report(code, x, y), report(code, x, y, release=True)
    if action in ('click', 'double', 'triple'):
        return [((press + release) * {'click': 1, 'double': 2, 'triple': 3}[action], 0.05)]
    if 'to_row' not in data or 'to_column' not in data:
        raise ValueError('drag needs to_row and to_column')
    clicks = data.get('clicks', 1)
    if not (isinstance(clicks, int) and 1 <= clicks <= 3):
        raise ValueError('clicks is 1, 2 or 3')
    tx, ty = cell(data['to_row'], data['to_column'])
    steps = max(abs(tx - x), abs(ty - y), 1)
    steps = min(steps, 24)
    out = [((press + release) * (clicks - 1) + press, 0.05)]
    for i in range(1, steps + 1):
        mx, my = x + round((tx - x) * i / steps), y + round((ty - y) * i / steps)
        out.append((report(code | 32, mx, my), 0.02))
    out.append((report(code, tx, ty, release=True), 0.05))
    return out


# -- terminal emulation ----------------------------------------------------------------------------------------
ALTERNATE_SCREEN = {47, 1047, 1049}


class XtermScreen(pyte.Screen):
    """pyte 0.8.2 plus the xterm-256color behaviour curses-style applications rely on."""

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


def blank_look(style):
    """What a blank cell of this style looks like: the colour it shows (its background, or its foreground when
    reversed; the terminal's default foreground and background are different colours) and underline."""
    fg, bg, _bold, _italics, underscore, reverse = style
    shown = (fg if fg != 'default' else 'default-fg') if reverse else (bg if bg != 'default' else 'default-bg')
    return shown, bool(underscore)


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

    def modes(self):
        with self.lock:
            return set(self.screen.mode)

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
                    # A blank cell shows only its look (background, reverse, underline): one that looks like the
                    # run it follows continues that run instead of splitting it on an invisible foreground.
                    if current and (current[2] == style or (not cell.data.strip()
                                                           and blank_look(style) == blank_look(current[2]))):
                        current[1] = x + 1
                    else:
                        current = [x, x + 1, style]
                        row.append(current)
                spans.append(row)

            def text(y, start, end):
                return ''.join(self.screen.buffer[y][x].data for x in range(start, end))
            # The base style covers the most cells (normally the editing area's background), so the status line,
            # the cursor line, selections and highlights are the runs that stand out from it.
            weight = {}
            for y, row in enumerate(spans):
                for start, end, style in row:
                    weight[style] = weight.get(style, 0) + end - start
            base = max(weight, key=weight.get) if weight else None
            styles = []
            for y, row in enumerate(spans):
                for start, end, style in row:
                    value = text(y, start, end)
                    if style == base or (base is None and not flags(style)):
                        continue
                    # Blank cells show only their background, reverse video and underline (a highlighted space,
                    # a selection over blanks); blank runs that look like the base style are left out.
                    if not value.strip() and (base is None or blank_look(style) == blank_look(base)):
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
    """start.sh as the controlling-terminal session of a pseudo-terminal, in the working directory."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log, env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC'})
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()
        self.args = []

    @property
    def data(self):
        return Path(self.directories['DATA_DIR'])

    @property
    def workspace(self):
        return self.data / 'workspace'

    @property
    def config_dir(self):
        return self.data / 'config'

    def environment(self):
        env = super().environment()
        env.update(COLUMNS=str(COLUMNS), LINES=str(ROWS))
        return env

    def ensure_workspace(self):
        with safe_files.directory(self, self.data, ['workspace'], create=True):
            pass
        return self.workspace

    def start(self, fresh=False, args=None):
        self.stop()
        self.prepare(fresh)
        if args is not None:
            self.args = list(args)
        self.ready, self.starts = False, self.starts + 1
        self.terminal = Terminal(COLUMNS, ROWS)
        script = self.solution / 'start.sh'
        if not script.is_file():
            self.detail = 'start.sh does not exist in the solution directory'
            self.log.note(self.detail)
            return False
        cwd = self.ensure_workspace()
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', ROWS, COLUMNS, 0, 0))
        kwargs = {}
        if self.switching():
            account = self.account()
            os.fchown(slave, account.pw_uid, account.pw_gid)
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        try:
            self.proc = subprocess.Popen(['setsid', '--ctty', str(script), *self.args], cwd=str(cwd),
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
        self.log.note(f'start {self.starts}: pid {self.proc.pid}, terminal {COLUMNS}x{ROWS}, {len(self.args)} arguments')
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


# -- command line ----------------------------------------------------------------------------------------------
def printable(value, field, limit):
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f'{field} must be printable text of at most {limit} characters')
    return value


def check_args(args):
    """micro's command line as a user in the working directory gives it: files (relative paths inside the
    working directory), +LINE[:COL], +/REGEX, and -option value pairs for micro's options."""
    if not isinstance(args, list) or len(args) > MAX_ARGS:
        raise ValueError(f'args must be a list of at most {MAX_ARGS} strings')
    expect_value = False
    for value in args:
        printable(value, 'each argument', 1024)
        if expect_value:
            expect_value = False
            continue
        if not value:
            raise ValueError('arguments must not be empty')
        if value.startswith('-'):
            if value[1:] not in OPTION_NAMES:
                raise ValueError(f'{value} is not an option of the editor that this interface accepts; '
                                 'options are -name value pairs of micro options (see help)')
            expect_value = True
            continue
        if re.fullmatch(r'\+\d+(?::\d+)?', value) or (value.startswith('+/') and len(value) > 2):
            continue
        if not components(value, 'a file argument'):
            raise ValueError('a file argument must name a path below ' + ORIGIN)
    if expect_value:
        raise ValueError('an option flag needs a value')
    return args


# -- workspace inspector (the working directory; read-only, confined, NOFOLLOW) ---------------------------------
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


def inspect(product, data, redact=str, aliases=()):
    try:
        return safe_files.inspect(product.workspace, components(data.get('path', ORIGIN)),
                                  data.get('action', 'list'), origin=ORIGIN, read_limit=MAX_FILE_BYTES,
                                  hash_limit=MAX_HASH_BYTES, tree_limit=MAX_TREE_ENTRIES,
                                  redact=redact, aliases=aliases)
    except FileNotFoundError:
        raise ValueError('no such entry in the workspace') from None


# -- placing files (setup) and changing one on disk (while the editor runs) ------------------------------------
def content_of(value, field):
    if isinstance(value, str):
        return value.encode('utf-8'), None, None
    if not isinstance(value, dict) or set(value) - {'base64', 'mode', 'mtime'} or 'base64' not in value:
        raise ValueError(f'{field}: a file is UTF-8 text or an object {{"base64", "mode"?, "mtime"?}}')
    try:
        body = base64.b64decode(value['base64'], validate=True)
    except (ValueError, TypeError):
        raise ValueError(f'{field}: base64 is not valid') from None
    mode, mtime = value.get('mode'), value.get('mtime')
    if mode is not None and not (isinstance(mode, int) and not isinstance(mode, bool) and 0 <= mode <= 0o777):
        raise ValueError(f'{field}: mode must be an integer permission set (0-0o777)')
    if mtime is not None and not (isinstance(mtime, (int, float)) and not isinstance(mtime, bool)
                                  and 0 <= mtime < 2 ** 33):
        raise ValueError(f'{field}: mtime must be a time in seconds')
    return body, mode, mtime


def check_files(files):
    if not isinstance(files, dict):
        raise ValueError('files must be an object of path -> content')
    if len(files) > MAX_PLACED:
        raise ValueError(f'at most {MAX_PLACED} files can be placed at once')
    for name, value in files.items():
        if not components(name, 'file path'):
            raise ValueError('a placed file needs a path below the workspace')
        if value is not None:
            content_of(value, name)


def config_target(name):
    """A placeable configuration file: settings.json, bindings.json, or a colour scheme, syntax definition or
    help page in its runtime-file directory."""
    printable(name, 'config file name', 255)
    if name in CONFIG_FILES:
        return [name]
    parts = name.split('/')
    if len(parts) == 2 and parts[0] in CONFIG_DIRS and parts[1].endswith(CONFIG_DIRS[parts[0]]) \
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,100}', parts[1]):
        return parts
    raise ValueError('config files are settings.json, bindings.json, colorschemes/NAME.micro, '
                     'syntax/NAME.yaml or help/NAME.md')


def check_config(config):
    if not isinstance(config, dict) or len(config) > 32:
        raise ValueError('config must be an object of at most 32 file name -> content')
    for name, value in config.items():
        config_target(name)
        content_of(value, name)


def place(product, files, config):
    """Write workspace and configuration inputs through held directory descriptors."""
    with safe_files.directory(product, product.data, ['workspace'], create=True) as root_fd:
        for name, value in (files or {}).items():
            parts = components(name, 'file path')
            with safe_files.directory(product, root_fd, parts[:-1], create=True) as parent:
                if value is None:
                    with safe_files.directory(product, parent, parts[-1:], create=True):
                        pass
                else:
                    body, mode, mtime = content_of(value, name)
                    safe_files.write(product, parent, parts[-1], body,
                                     mode=0o644 if mode is None else mode, mtime=mtime)
    if config:
        with safe_files.directory(product, product.data, ['config'], create=True) as config_fd:
            for name, value in config.items():
                parts = config_target(name)
                with safe_files.directory(product, config_fd, parts[:-1], create=True) as parent:
                    body, mode, mtime = content_of(value, name)
                    safe_files.write(product, parent, parts[-1], body,
                                     mode=0o644 if mode is None else mode, mtime=mtime)


def modify(product, data):
    """Replace one workspace file while the application is running."""
    parts = components(data['path'], 'path')
    if not parts:
        raise ValueError('path must name a file below ' + ORIGIN)
    value = data['text'] if 'text' in data else {'base64': data['base64']}
    body, _, _ = content_of(value, 'content')
    if len(body) > MAX_FILE_BYTES:
        raise ValueError(f'the content exceeds {MAX_FILE_BYTES} bytes')
    with safe_files.directory(product, product.workspace, parts[:-1]) as parent:
        safe_files.write(product, parent, parts[-1], body)
    return {'path': ORIGIN + '/' + '/'.join(parts), 'size': len(body)}


# -- micro's configuration files and command line -----------------------------------------------------------------
def read_config(product, data):
    which = data['file']
    try:
        content = runtime.read_file(product.data, 'config/' + which, limit=MAX_FILE_BYTES)
    except OSError:
        return {'file': which, 'exists': False, 'text': ''}
    return {'file': which, 'exists': True, 'text': content.decode('utf-8', 'replace')}


def run_cli(product, data):
    """Run the application once with one command-line option that prints and exits, without a terminal."""
    option = data['option']
    if option not in CLI_OPTIONS:
        raise ValueError('option must be one of: ' + ', '.join(CLI_OPTIONS))
    script = product.solution / 'start.sh'
    if not script.is_file():
        raise ValueError('start.sh does not exist in the solution directory')
    cwd = product.ensure_workspace()
    kwargs = {}
    if product.switching():
        account = product.account()
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    try:
        done = run_bounded([str(script), option], env=product.environment(), cwd=str(cwd),
                           stream_limit=MAX_FILE_BYTES, merge_stderr=True, timeout=CLI_TIMEOUT, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError('the command-line run did not finish in time') from None
    except OSError as exc:
        raise ValueError(f'start.sh could not be executed ({type(exc).__name__})') from None
    stdout = done.stdout[:MAX_FILE_BYTES].decode('utf-8', 'replace')
    return {'option': option, 'exit_code': done.returncode, 'stdout': stdout}


# -- RPC interface ---------------------------------------------------------------------------------------------
ARGS_FIELD = {'type': 'array', 'items': {'type': 'string'},
              'description': f'Command-line arguments for the editor (at most {MAX_ARGS}), as a user in the working '
                             'directory would give them: files to open (paths relative to ' + ORIGIN + '), '
                             '+LINE[:COL], +/REGEX, and -option value pairs of micro options. Omitted: the '
                             'arguments of the previous start (none after a reset without args).'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, key names and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'fields': {},
               'summary': 'Whether the application is running and ready, and its exit status once it ended.'},
    'reset': {'kind': 'lifecycle', 'fields': {'args': ARGS_FIELD},
              'summary': 'Restart the application with an empty data directory (its initial state: an empty working '
                         f'directory and configuration) in a fresh {COLUMNS}x{ROWS} terminal.'},
    'restart': {'kind': 'lifecycle', 'fields': {'args': ARGS_FIELD},
                'summary': 'Restart the application with the same data directory in a fresh '
                           f'{COLUMNS}x{ROWS} terminal (for example after quitting it), optionally with other '
                           'command-line arguments.'},
    'screen': {'kind': 'observe', 'fields': {},
               'summary': 'The terminal as a user sees it once output has settled: size [columns, rows]; the '
                          'cursor; screen rows as "NN|text" (NN is the zero-based row number, not part of the '
                          'screen); styles, the runs of text whose colour or attributes differ from the most '
                          'common style (selection, highlights, the cursor line, the status line), with '
                          'base_style; and process: running, or exited with its status.'},
    'key': {'kind': 'gui', 'summary': 'Press one key or chord, then return the settled screen.',
            'fields': {'key': {'type': 'string', 'required': True, 'description': KEY_HELP}}},
    'keys': {'kind': 'gui', 'summary': 'Press several keys or chords in order (validated before any is sent), '
                                       'then return the settled screen.',
             'fields': {'keys': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                 'description': f'1-{MAX_KEY_BATCH} keys, each as for key.'}}},
    'type': {'kind': 'gui', 'summary': 'Type literal text key by key (printable characters only; send Enter, Tab, '
                                       'Escape and other keys with key), then return the settled screen.',
             'fields': {'text': {'type': 'string', 'required': True,
                                 'description': f'Printable UTF-8 text, 1-{MAX_TEXT} characters.'}}},
    'paste': {'kind': 'gui', 'summary': "Paste text through the terminal as a terminal's own paste command sends it "
                                        '(a bracketed paste when the application has enabled bracketed paste), then '
                                        'return the settled screen.',
              'fields': {'text': {'type': 'string', 'required': True,
                                  'description': f'UTF-8 text, 1-{MAX_TEXT} characters; printable characters, '
                                                 'newlines (\\n) and tabs.'}}},
    'mouse': {'kind': 'gui', 'summary': 'Use the mouse on a screen cell: click, double or triple click, drag to another '
                                        'cell (optionally starting with a double or triple click), or scroll the '
                                        'wheel; then return the settled screen. As in a terminal, the application '
                                        'receives xterm mouse reports only while it has mouse reporting enabled.',
              'fields': {'action': {'type': 'string', 'enum': list(MOUSE_ACTIONS), 'required': True,
                                    'description': 'click, double, triple, drag or scroll.'},
                         'row': {'type': 'integer', 'required': True, 'description': 'Screen row (zero-based).'},
                         'column': {'type': 'integer', 'required': True,
                                    'description': 'Screen column (zero-based).'},
                         'to_row': {'type': 'integer', 'description': 'For drag: the row where the button is '
                                                                      'released.'},
                         'to_column': {'type': 'integer', 'description': 'For drag: the column where the button '
                                                                         'is released.'},
                         'clicks': {'type': 'integer', 'description': 'For drag: 1 (default), 2 or 3; with 2 or 3 the '
                                                                      'drag starts with a double or triple click whose '
                                                                      'last press is held down.'},
                         'button': {'type': 'string', 'enum': list(MOUSE_BUTTONS),
                                    'description': 'left (default), middle or right.'},
                         'direction': {'type': 'string', 'enum': list(WHEEL),
                                       'description': 'For scroll: up, down (default), left or right.'},
                         'modifiers': {'type': 'array', 'items': {'type': 'string'},
                                       'description': 'Keys held during the action: Control, Alt, Shift.'}}},
    'wait': {'kind': 'gui', 'summary': 'Wait for asynchronous terminal output, then return the settled screen.',
             'fields': {'seconds': {'type': 'number', 'description': 'Seconds to wait, 0-10; default 0.5.'}}},
    'resize': {'kind': 'gui', 'summary': 'Resize the terminal (the application receives SIGWINCH), then return '
                                         'the settled screen.',
               'fields': {'columns': {'type': 'integer', 'required': True, 'description': 'Columns, 40-240.'},
                          'rows': {'type': 'integer', 'required': True, 'description': 'Rows, 10-80.'}}},
    'workspace': {'kind': 'files', 'summary': "Read-only inspector of the application's working directory "
                  '(where the edited files live): list one directory, tree (recursive), stat one entry, or read a '
                  'regular file. Hidden entries are included; symlinks are reported with their target and never '
                  'followed. A private location inside a file name (micro names backup files after the escaped '
                  'path of the file, / as %2F) is shown by its display name, and such a name is accepted back.',
                  'fields': {'action': {'type': 'string', 'enum': ['list', 'tree', 'stat', 'read'],
                                        'description': 'list, tree, stat or read (at most 1 MiB); default list.'},
                             'path': {'type': 'string',
                                      'description': f'{ORIGIN} or a path below it; default {ORIGIN}.'}}},
    'place': {'kind': 'files', 'summary': 'Setup: write files into the working directory and into micro\'s '
              'configuration directory while the application is stopped, then start it again (optionally with '
              'other command-line arguments). The application restarts with the supplied files.',
              'fields': {'files': {'type': 'object',
                                   'description': 'Working-directory-relative path -> UTF-8 text, '
                                                  '{"base64":..., "mode"?:..., "mtime"?:...}, or null for a '
                                                  f'directory; at most {MAX_PLACED}.'},
                         'config': {'type': 'object',
                                    'description': 'Configuration file -> content as for files: settings.json, '
                                                   'bindings.json, colorschemes/NAME.micro, syntax/NAME.yaml or '
                                                   'help/NAME.md.'},
                         'args': ARGS_FIELD}},
    'modify': {'kind': 'files', 'summary': 'Change one file of the working directory on disk while the application '
               'keeps running, as another program would (creating it if needed); returns its path and size.',
               'fields': {'path': {'type': 'string', 'required': True,
                                   'description': f'A file path below {ORIGIN}.'},
                          'text': {'type': 'string', 'description': 'New content as UTF-8 text.'},
                          'base64': {'type': 'string', 'description': 'New content as base64 (instead of text).'}}},
    'config': {'kind': 'files', 'summary': "Read one of micro's configuration files from its configuration "
               'directory: settings.json or bindings.json.',
               'fields': {'file': {'type': 'string', 'enum': list(CONFIG_FILES), 'required': True,
                                   'description': 'settings.json or bindings.json.'}}},
    'cli': {'kind': 'info', 'summary': 'Run the application once, without a terminal, with one command-line option '
            'that prints and exits, and return its exit status and output: -version, -options or -help.',
            'fields': {'option': {'type': 'string', 'enum': list(CLI_OPTIONS), 'required': True,
                                  'description': 'The command-line option.'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'read_bytes': MAX_FILE_BYTES, 'tree_entries': MAX_TREE_ENTRIES,
          'key_batch': MAX_KEY_BATCH, 'type_characters': MAX_TEXT, 'placed_files': MAX_PLACED, 'args': MAX_ARGS,
          'terminal_columns': [40, 240], 'terminal_rows': [10, 80], 'wait_seconds': 10,
          'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': MAX_STYLES, 'screen': [COLUMNS, ROWS]}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, scrolling regions, colours, wide and combined characters, bracketed paste, SGR mouse '
    'reports); screen shows what a user of a real terminal sees.',
    'key, keys, type, paste, mouse and resize return the screen once the application has answered the input (or '
    'stayed silent for 1.5 s) and its output has settled (no new output for 0.3 s), at most 6 s; screen and wait '
    'wait for settled output the same way. keys sends one key at a time and pauses after a bare Escape so it is '
    'not read as Alt. Observe the settled screen before sending more input.',
    f'The application starts in its working directory ({ORIGIN}), with its command-line arguments. reset and restart '
    'start it in a fresh terminal; restart keeps the data directory (files and configuration). The terminal is '
    "the application's controlling terminal, so it receives SIGWINCH on resize.",
    "workspace, place, modify, config and cli operate independently of the "
    'interactive terminal. workspace reads the working directory (links are reported, never followed); place '
    "writes files and micro's configuration files before a start; modify changes a file on disk while the "
    "application runs; config reads micro's settings.json and bindings.json; cli runs one command-line option that "
    'prints and exits.',
    f'Private runtime locations in screens, answers and errors are shown as {ORIGIN}, [data] or [private]; '
    f'{ORIGIN} is a display name for the working directory, not a path the application can open.',
]


class Refused(ValueError):
    pass


def encoded_roots(pairs):
    """The URL-escaped spelling (/ as %2F) of each deep private root and of its display name: micro names a backup
    file after the escaped absolute path of the file it belongs to."""
    return [(quote(str(Path(p)), safe=''), name.replace('/', '%2F')) for p, name in pairs
            if p and len(Path(p).parts) >= 4]


def make_redactor(pairs):
    """Replace each private filesystem root with its logical name; the working directory becomes /workspace so the
    screen and answers show stable paths. The editor also shows paths relative to its working directory, which
    after `cd /` are the same roots without the leading slash, so those forms are replaced too. Longest first."""
    roots = [(str(Path(p)), name) for p, name in pairs if p and str(Path(p)) != '/']
    # Only deep roots (the instance, data and working directories): a short root such as /reference would turn an
    # ordinary word on the screen into a placeholder.
    roots += [(root[1:], name[1:] if name.startswith('/') else name) for root, name in roots
              if root.startswith('/') and len(Path(root).parts) >= 4]
    roots += encoded_roots(pairs)
    ordered = sorted(roots, key=lambda pair: len(pair[0]), reverse=True)

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
        private = [(self.product.workspace, ORIGIN), (layout['DATA_DIR'], '[data]'), (config.state, '[private]'),
                   (config.solution, '[private]'), (config.work, '[private]'), (config.log_dir, '[private]'),
                   (str(HERE), '[private]'), ('/reference', '[private]'), ('/opt/blackbox', '[private]'),
                   ('/app/solution', '[private]')]
        self.redact = make_redactor(private)
        # Names the inspector shows redacted are accepted back (the working directory's own escaped path).
        self.aliases = [(shown, real) for real, shown in encoded_roots(private[:2])]

    # Lifecycle ----------------------------------------------------------------------------------------------
    def launch(self, fresh, args=None):
        if self.product.start(fresh=fresh, args=args):
            wait_ready(self.product)
            self.settle(0.2)
        status = self.product.status()
        self.log.note('status: ' + json.dumps(status))
        return status

    def start(self):
        with self.lock:
            return self.launch(fresh=True, args=[])

    def close(self):
        self.product.stop()

    def detail(self, exc):
        return self.redact(str(exc))[:600]

    # Observation --------------------------------------------------------------------------------------------
    def settle(self, minimum=0.1, since=None):
        """Wait until the output has settled: no new output for QUIET seconds (at most SETTLE_MAX). After input
        (since = the output count before it was sent) the application must first answer it, or stay silent for
        FIRST_OUTPUT seconds: an application that is briefly busy (for example writing a file) would otherwise look
        settled while the input is still unprocessed."""
        terminal = self.product.terminal
        if terminal is None:
            return
        started = time.monotonic()
        deadline = started + SETTLE_MAX
        while True:
            now = time.monotonic()
            if now >= deadline:
                return
            answered = since is None or terminal.received > since or now - started >= FIRST_OUTPUT
            if answered and now - started >= minimum and now - terminal.last_output >= QUIET:
                return
            time.sleep(0.02)

    def output_count(self):
        terminal = self.product.terminal
        return terminal.received if terminal is not None else 0

    def observe(self, minimum=0.1):
        self.settle(minimum)
        terminal = self.product.terminal
        if terminal is None:
            return blank_observation(self.product.process())
        deadline = time.monotonic() + 1.0
        while self.product.running() and not terminal.drawn() and time.monotonic() < deadline:
            time.sleep(0.05)
        return terminal.observe(self.product.process(), self.redact)

    def send_keys(self, names):
        cursor = self.product.terminal and self.product.terminal.application_cursor()
        sequences = [key_bytes(k, cursor) for k in names]
        before = self.output_count()
        for index, sequence in enumerate(sequences):
            self.product.write(sequence)
            if index < len(sequences) - 1:
                time.sleep(ESCAPE_GAP if sequence == '\x1b' else KEY_GAP)
        if sequences and sequences[-1] == '\x1b':
            time.sleep(ESCAPE_GAP)
        self.settle(0.1, since=before)
        return self.observe(0)

    def send(self, raw, minimum=0.1):
        before = self.output_count()
        self.product.write(raw)
        self.settle(minimum, since=before)
        return self.observe(0)

    def mouse(self, data):
        terminal = self.product.terminal
        if terminal is None or not self.product.running():
            raise ValueError('the application is not running; restart it to continue')
        modes = terminal.modes()
        sequences = mouse_sequences(data, terminal.columns, terminal.rows, sgr=MOUSE_SGR in modes)
        if not MOUSE_MODES & modes:
            # Like a terminal: without mouse reporting enabled by the application, nothing reaches it.
            return self.observe(0)
        before = self.output_count()
        for sequence, pause in sequences:
            self.product.write(sequence)
            time.sleep(pause)
        self.settle(0.1, since=before)
        return self.observe(0)

    # Dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = validate_request(data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'terminal', OPERATIONS, limits=LIMITS, notes=NOTES,
                                         examples=EXAMPLES, key_names=KEY_NAMES, modifiers=['Control', 'Alt', 'Shift'],
                                         editor_options=sorted(OPTION_NAMES))
        if op == 'status':
            return self.redact_value(self.product.status())
        with self.lock:
            if op == 'reset':
                self.product.stop()
                return self.redact_value(self.launch(fresh=True, args=data.get('args', [])))
            if op == 'restart':
                self.product.stop()
                return self.redact_value(self.launch(fresh=False, args=data.get('args')))
            if op == 'screen':
                return self.observe()
            if op == 'key':
                return self.send_keys([data['key']])
            if op == 'keys':
                return self.send_keys(data['keys'])
            if op == 'type':
                return self.send(data['text'])
            if op == 'paste':
                # Like a terminal: line breaks are sent as carriage returns, wrapped in bracketed-paste markers
                # only when the application has enabled bracketed paste.
                text = data['text'].replace('\r\n', '\r').replace('\n', '\r')
                bracketed = self.product.terminal and BRACKETED_PASTE in self.product.terminal.modes()
                return self.send('\x1b[200~' + text + '\x1b[201~' if bracketed else text)
            if op == 'mouse':
                return self.mouse(data)
            if op == 'wait':
                time.sleep(float(data.get('seconds', 0.5)))
                return self.observe(0)
            if op == 'resize':
                self.settle(0)
                before = self.output_count()
                self.product.resize(data['columns'], data['rows'])
                self.settle(0.15, since=before)
                return self.observe(0)
            if op == 'workspace':
                return inspect(self.product, data, self.redact, self.aliases)
            if op == 'place':
                self.product.stop()
                place(self.product, data.get('files'), data.get('config'))
                return self.redact_value(self.launch(fresh=False, args=data.get('args')))
            if op == 'modify':
                return modify(self.product, data)
            if op == 'config':
                return self.redact_value(read_config(self.product, data))
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


EXAMPLES = [{'op': 'screen'}, {'op': 'type', 'text': 'hello'}, {'op': 'key', 'key': 'Control+S'},
            {'op': 'keys', 'keys': ['Control+E']}, {'op': 'type', 'text': 'set tabsize 2'},
            {'op': 'restart', 'args': ['notes.txt', '+3:5']},
            {'op': 'place', 'files': {'notes.txt': 'first line\n'}, 'args': ['notes.txt']},
            {'op': 'workspace', 'action': 'read', 'path': '/workspace/notes.txt'},
            {'op': 'config', 'file': 'settings.json'}, {'op': 'cli', 'option': '-version'},
            {'op': 'mouse', 'action': 'click', 'row': 2, 'column': 10}]


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
    elif op == 'paste':
        text = data['text']
        if not 0 < len(text) <= MAX_TEXT or any((ord(c) < 32 and c not in '\n\t') or ord(c) == 127 for c in text):
            raise ValueError(f'paste text must be 1-{MAX_TEXT} printable characters, newlines and tabs')
    elif op == 'mouse':
        mouse_sequences(data, 240, 80)
        for field in ('to_row', 'to_column', 'clicks'):
            if field in data and data['action'] != 'drag':
                raise ValueError(f'{field} only applies to drag')
        if 'direction' in data and data['action'] != 'scroll':
            raise ValueError('direction only applies to scroll')
    elif op == 'resize':
        if not (40 <= data['columns'] <= 240 and 10 <= data['rows'] <= 80):
            raise ValueError('resize needs 40-240 columns and 10-80 rows')
    elif op == 'wait':
        if not (0 <= data.get('seconds', 0.5) <= 10):
            raise ValueError('wait takes 0-10 seconds')
    elif op == 'workspace':
        components(data.get('path', ORIGIN))
    elif op == 'place':
        check_files(data.get('files', {}))
        check_config(data.get('config', {}))
        check_args(data.get('args', []))
    elif op in ('reset', 'restart'):
        check_args(data.get('args', []))
    elif op == 'modify':
        components(data['path'])
        if ('text' in data) == ('base64' in data):
            raise ValueError('modify takes exactly one of text and base64')
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
