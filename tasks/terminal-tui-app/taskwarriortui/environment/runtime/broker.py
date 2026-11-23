#!/usr/bin/env python3
"""Taskwarrior-tui terminal runtime.

One instance drives one application directory in an emulated xterm-256color
pseudo-terminal. The task entry point provides the application's Taskwarrior
command line on the same instance data. A preloaded clock library fixes wall
time while monotonic clocks keep running.
"""
from __future__ import annotations

import codecs
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pty
import re
import select
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

import pyte  # noqa: E402
from pyte.screens import Margins  # noqa: E402
from wcwidth import wcwidth  # noqa: E402

PRODUCT = 'taskwarrior-tui'
COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
CLOCK = '2026-05-13 10:00:00'
FAKETIME_LIBRARY = '/usr/local/lib/faketime/libfaketime.so.1'
MAX_REQUEST_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_STDIN_BYTES = 512 * 1024
MAX_ARGS = 64
MAX_ARG = 4096
MAX_KEY_BATCH = 256
MAX_TEXT = 4096
MAX_STYLES = 400
RPC_TIMEOUT_SEC = 90
TASK_TIMEOUT = 30
QUIET = 0.3
SETTLE_MAX = 8.0
ESCAPE_GAP = 0.06
DECCKM = 1 << 5  # pyte stores private mode n as n << 5
# Configuration overrides (rc.<name>=<value>) the task operation accepts: output format, confirmations and verbosity.
# Overrides of other settings, and rc:<file>, are refused (use the config command to change the configuration).
OVERRIDES = ('confirmation', 'bulk', 'json.array', 'json.depends.array', 'verbose', 'color', '_forcecolor',
             'defaultwidth', 'defaultheight', 'dependency.confirmation', 'recurrence.confirmation', 'detection')


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
            if char.isalpha() and char.isascii():
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
    """pyte 0.8.2 plus the xterm-256color behaviour full-screen terminal applications rely on."""

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
    """The emulated terminal. `last_change` is the last time the visible state (cells, attributes, cursor) changed:
    output that leaves the screen as it was (for example a periodic redraw that only re-hides the cursor) does not
    count as a change."""

    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.screen = XtermScreen(columns, rows)
        self.stream = XtermStream(self.screen)
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.lock = threading.Lock()
        self.last_change = time.monotonic()
        self.fingerprint = None
        self.received = 0

    def state(self):
        cursor = self.screen.cursor
        digest = hashlib.sha256()
        for y in range(self.rows):
            row = self.screen.buffer[y]
            for x in range(self.columns):
                cell = row[x]
                digest.update(f'{cell.data}\x00{cell.fg}\x00{cell.bg}\x00{cell.bold:d}{cell.italics:d}'
                              f'{cell.underscore:d}{cell.reverse:d}\x01'.encode())
        digest.update(f'{cursor.x},{cursor.y},{bool(cursor.hidden):d}'.encode())
        return digest.digest()

    def feed(self, data):
        with self.lock:
            cursor = self.screen.cursor
            before = (cursor.x, cursor.y, cursor.hidden)
            self.stream.feed(self.decoder.decode(data))
            self.received += len(data)
            cursor = self.screen.cursor
            if self.screen.dirty or before != (cursor.x, cursor.y, cursor.hidden):
                self.screen.dirty.clear()
                fingerprint = self.state()
                if fingerprint != self.fingerprint:
                    self.fingerprint = fingerprint
                    self.last_change = time.monotonic()

    def resize(self, columns, rows):
        with self.lock:
            self.columns, self.rows = columns, rows
            self.screen.resize(rows, columns)
            self.fingerprint = self.state()
            self.last_change = time.monotonic()

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
def clock_environment():
    return {'LD_PRELOAD': FAKETIME_LIBRARY, 'FAKETIME': CLOCK, 'FAKETIME_DONT_FAKE_MONOTONIC': '1'}


class TerminalProduct(runtime.Product):
    """start.sh as the controlling-terminal session of a pseudo-terminal."""

    def __init__(self, config, *, log):
        super().__init__(config, log=log,
                         env={'TERM': TERM, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8', 'TZ': 'UTC',
                              **clock_environment()})
        self.terminal = None
        self.master = None
        self.reader = None
        self.closing = threading.Event()

    @property
    def data_dir(self):
        return Path(self.directories['DATA_DIR'])

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

    def descendants(self):
        """PIDs of the processes the application started (its process tree below the session leader)."""
        if self.proc is None or self.proc.poll() is not None:
            return set()
        parents = {}
        for entry in os.scandir('/proc'):
            if not entry.name.isdigit():
                continue
            try:
                with open(f'/proc/{entry.name}/stat', 'rb') as stream:
                    stat = stream.read()
            except OSError:
                continue
            fields = stat[stat.rfind(b')') + 2:].split()
            if len(fields) > 1:
                parents.setdefault(int(fields[1]), []).append(int(entry.name))
        found, pending = set(), [self.proc.pid]
        while pending:
            for child in parents.get(pending.pop(), ()):
                if child not in found:
                    found.add(child)
                    pending.append(child)
        return found


def wait_ready(product):
    """Terminal readiness: the interface is drawn on the terminal (no product endpoint is used)."""
    limit = product.config.ready_timeout
    return runtime.wait_until(product, lambda: product.terminal.drawn(), deadline=limit, interval=0.1,
                              failure=f'the application did not draw its interface within {limit:g} s')


# -- the application's command line --------------------------------------------------------------------------------
def check_arguments(args):
    if not isinstance(args, list) or len(args) > MAX_ARGS:
        raise ValueError(f'args must be an array of at most {MAX_ARGS} strings')
    for arg in args:
        if not isinstance(arg, str) or len(arg) > MAX_ARG or any(ord(c) < 32 or ord(c) == 127 for c in arg):
            raise ValueError(f'each argument must be printable text of at most {MAX_ARG} characters')
        lowered = arg.lower()
        if lowered.startswith(('rc:', 'rc=')):
            raise ValueError('rc:<file> is not accepted: the application always uses its own configuration file')
        if arg.startswith('rc.'):
            separator = re.search('[:=]', arg[3:])
            if separator and arg[3:3 + separator.start()] not in OVERRIDES:
                raise ValueError('configuration overrides are limited to rc.<name>=<value> with name one of: ' +
                                 ', '.join(OVERRIDES) + '; change other settings with the config command')


def run_task(product, data):
    """Run the solution's task program once in this instance and return its exit status and output."""
    args = data.get('args', [])
    check_arguments(args)
    stdin = data.get('stdin', '')
    program = product.solution / 'task'
    if not program.is_file():
        raise ValueError('the solution has no task program')
    env = product.environment()
    env.pop('COLUMNS', None)
    env.pop('LINES', None)
    kwargs = {}
    if product.switching():
        account = product.account()
        kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
    with runtime.open_directory(product.data_dir):
        pass
    try:
        done = run_bounded([str(program), *args], input=stdin.encode('utf-8'), env=env,
                           cwd=str(product.data_dir), stream_limit=MAX_OUTPUT_BYTES,
                           timeout=TASK_TIMEOUT, umask=0o022, **kwargs)
    except subprocess.TimeoutExpired:
        raise ValueError(f'the task program did not finish within {TASK_TIMEOUT} s') from None
    except OSError as exc:
        raise ValueError(f'the task program could not be executed ({type(exc).__name__}: '
                         f'{exc.strerror or exc})') from None
    return {'exit_code': done.returncode, 'stdout': done.stdout[:MAX_OUTPUT_BYTES].decode('utf-8', 'replace'),
            'stderr': done.stderr[:MAX_OUTPUT_BYTES].decode('utf-8', 'replace')}


# -- RPC interface ---------------------------------------------------------------------------------------------
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields, key names and limits.', 'fields': {}},
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
                          'cursor; screen rows as "NN|text" (NN is the zero-based row number, not part of the '
                          'screen); styles, the runs of text whose colour or attributes differ from the most '
                          'common style (bold, reverse video, underline, colours), with base_style; and process: '
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
    'task': {'kind': 'info', 'summary': "Run the application's Taskwarrior command line (the task program) once, "
             'in this instance and with its data, and return its exit status, standard output and standard '
             'error. It runs beside the interactive application, which shows changes made this way after it '
             'refreshes.',
             'fields': {'args': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                 'description': f'The arguments after "task", 0-{MAX_ARGS} strings (no shell '
                                                'quoting), for example ["rc.json.array=on", "export"] or ["add", '
                                                '"Buy milk", "due:tomorrow"]. Configuration overrides are limited '
                                                'to rc.<name>=<value> with name one of: ' + ', '.join(OVERRIDES) +
                                                '.'},
                        'stdin': {'type': 'string',
                                  'description': 'Standard input (UTF-8, at most 512 KiB; default empty), for '
                                                 'example a JSON array for ["import"].'}}},
})
LIMITS = {'request_bytes': MAX_REQUEST_BYTES, 'output_bytes': MAX_OUTPUT_BYTES, 'stdin_bytes': MAX_STDIN_BYTES,
          'task_args': MAX_ARGS, 'task_seconds': TASK_TIMEOUT, 'key_batch': MAX_KEY_BATCH,
          'type_characters': MAX_TEXT, 'terminal_columns': [40, 240], 'terminal_rows': [10, 80], 'wait_seconds': 3,
          'rpc_timeout_seconds': RPC_TIMEOUT_SEC, 'styles': MAX_STYLES, 'screen': [COLUMNS, ROWS]}
NOTES = [
    f'The application runs in a {COLUMNS}x{ROWS} xterm-256color pseudo-terminal that the runtime emulates '
    '(alternate screen, scrolling regions, colours, wide and combined characters) with LANG and LC_ALL C.UTF-8 and '
    'TZ UTC; screen shows what a user of a real terminal sees.',
    f'The wall clock the application sees stays at {CLOCK} UTC (libfaketime, preloaded by the runtime into the '
    'application and into the task program); monotonic clocks keep running.',
    'key, keys, type, resize and wait return the screen once it has settled: its content has not changed for '
    f'{QUIET:g} s and no program the application started meanwhile is still running (at most {SETTLE_MAX:g} s). '
    'screen waits the same way. A bare Escape inside keys is sent on its own, so it is not read as Alt+key.',
    'reset and restart start the application in a fresh terminal; restart keeps the data directory. The '
    "terminal is the application's controlling terminal, so it receives SIGWINCH on resize.",
    'task runs the application command line independently of the interactive terminal. It runs the program '
    'without a terminal, in the data directory, with the same environment as the application.',
    'Private runtime locations in screens, answers and errors are shown as [data] or [private].',
]
EXAMPLES = [{'op': 'screen'}, {'op': 'key', 'key': 'j'}, {'op': 'keys', 'keys': ['a']},
            {'op': 'type', 'text': 'Buy milk due:tomorrow +errand'}, {'op': 'key', 'key': 'Enter'},
            {'op': 'key', 'key': 'Escape'}, {'op': 'task', 'args': ['rc.json.array=on', 'export']},
            {'op': 'task', 'args': ['rc.confirmation=off', 'import'], 'stdin': '[{"description": "Imported"}]'}]


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
    return apply


def printable(value, field, limit):
    if not isinstance(value, str) or len(value) > limit or any(not c.isprintable() and c != ' ' for c in value):
        raise ValueError(f'{field} must be printable text of at most {limit} characters')
    return value


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
    elif op == 'task':
        check_arguments(data['args'])
        stdin = data.get('stdin', '')
        if not isinstance(stdin, str) or len(stdin.encode('utf-8')) > MAX_STDIN_BYTES:
            raise ValueError(f'stdin must be text of at most {MAX_STDIN_BYTES} bytes')
    return op


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.log = runtime.BoundedLog(config.log_dir)
        self.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        self.product = TerminalProduct(config, log=self.log)
        layout = self.product.directories
        self.redact = make_redactor([(layout['DATA_DIR'], '[data]'), (config.state, '[private]'),
                                     (config.solution, '[private]'), (config.work, '[private]'),
                                     (config.log_dir, '[private]'), (str(HERE), '[private]'),
                                     ('/reference', '[private]'), ('/opt/blackbox', '[private]'),
                                     ('/app/solution', '[private]')])

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
    def settle(self, minimum=0.1, baseline=None):
        """Wait until the screen has not changed for QUIET seconds and no program started since `baseline` (the
        application's processes before the input) is running."""
        terminal = self.product.terminal
        if terminal is None:
            return
        known = set(baseline if baseline is not None else self.product.descendants())
        started = time.monotonic()
        activity = started if baseline is not None else 0.0
        while True:
            now = time.monotonic()
            fresh = self.product.descendants() - known
            if fresh:
                activity = now
            busy = max(terminal.last_change, activity)
            if now - started >= SETTLE_MAX or (now - started >= minimum and now - busy >= QUIET and not fresh):
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

    def send(self, chunks):
        """Write input chunks; a chunk that is a bare Escape is followed by a settle so it is read on its own."""
        baseline = self.product.descendants()
        for index, chunk in enumerate(chunks):
            self.product.write(chunk)
            if chunk == '\x1b' and index < len(chunks) - 1:
                time.sleep(ESCAPE_GAP)
                self.settle(0, baseline)
                baseline = self.product.descendants()
        self.settle(0.1, baseline)
        return self.observe(0)

    def keys(self, names):
        cursor = self.product.terminal and self.product.terminal.application_cursor()
        chunks, pending = [], ''
        for name in names:
            sequence = key_bytes(name, cursor)
            if sequence == '\x1b':
                if pending:
                    chunks.append(pending)
                chunks.append(sequence)
                pending = ''
            else:
                pending += sequence
        if pending:
            chunks.append(pending)
        return self.send(chunks)

    # Dispatch -----------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = validate_request(data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'terminal', OPERATIONS, limits=LIMITS, notes=NOTES,
                                         examples=EXAMPLES, key_names=KEY_NAMES, modifiers=['Control', 'Alt', 'Shift'],
                                         clock={'utc': CLOCK, 'frozen': True})
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
                return self.keys([data['key']])
            if op == 'keys':
                return self.keys(data['keys'])
            if op == 'type':
                return self.send([data['text']])
            if op == 'wait':
                time.sleep(float(data.get('seconds', 0.5)))
                return self.observe(0)
            if op == 'resize':
                self.settle(0)
                self.product.resize(data['columns'], data['rows'])
                self.settle(0.15)
                return self.observe(0)
            if op == 'task':
                return self.redact_value(run_task(self.product, data))
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
