'''Terminal emulation and key encoding for the lazygit black-box runtime (terminal surface).

The key encoding and the xterm-256color emulator follow the terminal runtime of the ranger task. The lazygit
additions at the end are: an emulator that ignores the terminal queries lazygit sends at start-up (pyte 0.8.2
raises on private status queries), capture of the OSC 52 sequence that the lazygit clipboard command writes, and
normalisation of the relative ages that lazygit and git print (they follow the real clock and are normalized for stable display).
'''
from __future__ import annotations

import base64
import codecs
import functools
import re
import threading
import time
import unicodedata

import pyte
from pyte.screens import Margins
from wcwidth import wcwidth

COLUMNS, ROWS = 120, 36
TERM = 'xterm-256color'
ESC = chr(27)
BEL = chr(7)
MAX_STYLES = 400
DECCKM = 1 << 5  # pyte stores private mode n as n << 5


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


# -- lazygit additions -------------------------------------------------------------------------------------------
MAX_CLIPBOARD = 4096
MAX_OSC = 65536
ST = ESC + chr(92)
OSC_CLIPBOARD = ESC + ']52;'


def _tolerant(method):
    '''Ignore a private or unsupported variant of a control sequence instead of failing: a terminal without the
    feature does the same, and lazygit starts without an answer to its queries.'''
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except TypeError:
            kwargs.pop('private', None)
            try:
                return method(self, *args, **kwargs)
            except TypeError:
                return None
    return wrapper


for _name in dir(XtermScreen):
    _member = getattr(XtermScreen, _name)
    if not _name.startswith('_') and callable(_member) and _name != 'draw':
        setattr(XtermScreen, _name, _tolerant(_member))
del _name, _member

UNITS = 'seconds?|minutes?|hours?|days?|weeks?|months?|years?'
AGE_COLUMN = re.compile('^(│)([0-9]{1,3}[smhdwMy])( +)')
AGO_TEXT = re.compile('[0-9]+ (?:' + UNITS + ')(?:, [0-9]+ (?:' + UNITS + '))* ago')


def normalize_ages(text):
    '''Replace the clock-dependent ages: the recency column of the side panels keeps its width but loses its
    digits and unit, and git relative dates become a fixed token of the same length.'''
    text = AGE_COLUMN.sub(lambda m: m.group(1) + '~' * len(m.group(2)) + m.group(3), text)
    return AGO_TEXT.sub(lambda m: '<age>'.ljust(len(m.group(0))), text)


def normalize_patch_log(observation):
    '''Hide generated patch filenames in the command log, including a wrapped filename whose prefix is offscreen.

    Only the log box is affected; patch contents and user filenames elsewhere remain observable. Replacing the whole
    log entry also removes the variable amount of text visible when a random temporary directory changes length.
    '''
    rows = [line.partition('|')[2] for line in observation['screen']]
    changed = set()
    for top, row in enumerate(rows):
        title = row.find('Command log')
        if title < 0:
            continue
        left = max((row.rfind(c, 0, title) for c in '╭┌┏╔'), default=-1)
        right = next((i for i in range(title, len(row)) if row[i] in '╮┐┓╗'), -1)
        if left < 0 or right < 0:
            continue
        for index in range(top + 1, len(rows)):
            if rows[index][left:left + 1] in '╰└┗╚':
                break
            body = rows[index][left + 1:right]
            if re.search(r'lazygit-[0-9]+|[0-9]+(?:\.[0-9]+)+\.patch', body):
                rows[index] = (rows[index][:left + 1] + '[temporary patch]'.ljust(right - left - 1)
                               + rows[index][right:])
                changed.add(index)
    observation['screen'] = [f'{i:02d}|{row}' for i, row in enumerate(rows)]
    for span in observation.get('styles', []):
        if span['row'] in changed:
            start, end = span['columns']
            span['text'] = rows[span['row']][start:end]
    return observation


class LazygitTerminal(Terminal):
    '''The emulated terminal, plus the text lazygit most recently copied to the clipboard through OSC 52.'''

    def __init__(self, columns, rows):
        super().__init__(columns, rows)
        self.clipboard = None
        self.copies = 0
        self.carry = ''

    def feed(self, data):
        with self.lock:
            text = self.decoder.decode(data)
            self.capture(text)
            self.stream.feed(text)
            self.last_output = time.monotonic()
            self.received += len(data)

    def capture(self, text):
        buffer, self.carry = self.carry + text, ''
        while True:
            start = buffer.find(OSC_CLIPBOARD)
            if start < 0:
                for size in range(len(OSC_CLIPBOARD) - 1, 0, -1):
                    if buffer.endswith(OSC_CLIPBOARD[:size]):
                        self.carry = OSC_CLIPBOARD[:size]
                        break
                return
            ends = [e for e in (buffer.find(BEL, start), buffer.find(ST, start)) if e >= 0]
            if not ends:
                if len(buffer) - start <= MAX_OSC:
                    self.carry = buffer[start:]
                return
            end = min(ends)
            body = buffer[start + len(OSC_CLIPBOARD):end]
            buffer = buffer[end + 1:]
            payload = body.partition(';')[2]
            if payload and payload != '?':
                try:
                    value = base64.b64decode(payload).decode('utf-8', 'replace')
                except ValueError:
                    continue
                self.clipboard = value[:MAX_CLIPBOARD]
                self.copies += 1
