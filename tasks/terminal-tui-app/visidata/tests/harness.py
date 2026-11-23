'''Driving and observation helpers over the task black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: GUI operations (key, keys, type, wait) and the
screen observation for the interactive terminal; the workspace inspector, the input-history state file and the
command-line channel for setup and backend checks; and the lifecycle operations (status, reset, restart, place).
No product internals are touched. The Screen parser turns a settled terminal snapshot into layout-independent
semantic facts about the table that is shown (column names, cell values, the cursor, selected rows, sort and type
markers, the sheet stack and the row count), never colours or exact column widths. The only styling it reads is
reverse video for the cursor row and the cursor column header in the reference terminal display.
'''
from __future__ import annotations

import re
import time

from evaluation.broker import BrokerError

SORT_ASC, SORT_DESC = '↑↟⇞⇧⇑', '↓↡⇟⇩⇓'
TYPE_CHARS = '#%@$&~♯'
NOTE = re.compile(r'[ ]{2,}[#%@$&~♯]$')
SEPARATORS = '│║'
SELECTED = '•'
HEADER_ROW, FIRST_ROW = 1, 2


class Session:
    '''Thin convenience wrapper over ctx.broker for recipes, setup and checks.'''

    def __init__(self, broker):
        self.broker = broker

    def call(self, request, **kw):
        return self.broker.call(request, **kw)

    # -- GUI operations ------------------------------------------------------------------------------------
    def key(self, name):
        return self.broker.call({'op': 'key', 'key': name})

    def keys(self, names):
        return self.broker.call({'op': 'keys', 'keys': list(names)})

    def type(self, text):
        return self.broker.call({'op': 'type', 'text': text})

    def wait(self, seconds=0.5):
        return self.broker.call({'op': 'wait', 'seconds': seconds})

    def ask(self, keys, text=None):
        '''Press the keys that open a prompt, then type the answer and confirm it with Enter.'''
        obs = self.keys(keys) if isinstance(keys, (list, tuple)) else self.key(keys)
        if text is None:
            return obs
        if text:
            self.type(text)
        return self.key('Enter')

    def open(self, name):
        return self.ask('o', name)

    def command(self, longname):
        return self.ask('Space', longname)

    def screen_raw(self):
        return self.broker.call({'op': 'screen'})

    def screen(self):
        return Screen(self.screen_raw())

    # -- lifecycle -----------------------------------------------------------------------------------------
    def status(self):
        return self.broker.call({'op': 'status'})

    def reset(self):
        return self.broker.call({'op': 'reset'})

    def restart(self):
        return self.broker.call({'op': 'restart'})

    def place(self, files):
        return self.broker.call({'op': 'place', 'files': files})

    # -- non-GUI read channels -----------------------------------------------------------------------------
    def workspace(self, action='list', path='/workspace'):
        return self.broker.call({'op': 'workspace', 'action': action, 'path': path})

    def tree(self, path='/workspace'):
        return self.broker.call({'op': 'workspace', 'action': 'tree', 'path': path})

    def read_file(self, path):
        return self.broker.call({'op': 'workspace', 'action': 'read', 'path': path})

    def read_state(self, file='input_history'):
        return self.broker.call({'op': 'state', 'file': file})

    def cli(self, args):
        return self.broker.call({'op': 'cli', 'args': list(args)})

    def ready(self, timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.status().get('ready'):
                    return True
            except BrokerError:
                pass
            time.sleep(0.3)
        return False


class Screen:
    '''Layout-independent semantic view of a settled VisiData terminal snapshot.

    Row 0 is the menu line, row 1 the header of the table, the rows below it the data rows, and the last row the
    status line (or an input prompt). A recent-messages box is drawn over the right of the lower rows. Cells are
    cut from each row at the separator positions of the header, so tables with wide (double-width) characters or
    many columns reaching under the message box are not read here.'''

    def __init__(self, obs):
        self.obs = obs
        self.rows = [line.split('|', 1)[1] if '|' in line else line for line in obs['screen']]
        self.height = len(self.rows)
        self.styles = obs.get('styles', [])
        self.process = obs.get('process')
        self._bounds = self._find_bounds()

    # -- table ---------------------------------------------------------------------------------------------
    def _find_bounds(self):
        '''Column start and stop offsets of the header, the offset of the end bar and the number of key columns.
        The table ends at the last double bar that is followed only by one-character slots (they indicate columns
        beyond the screen); a table wider than the screen has no end bar and its last column is cut at the screen
        edge. A double bar before the end separates the key columns from the others. Returns the column starts and
        stops, the end offset, the number of key columns and whether the end bar exists.'''
        if self.height <= FIRST_ROW:
            return None
        header = self.rows[HEADER_ROW].rstrip()
        if not header:
            return None
        seps = [i for i, ch in enumerate(header) if ch in SEPARATORS]
        end, closed = len(header), False
        for i in reversed([i for i in seps if header[i] == '║']):
            if all(len(part) <= 1 for part in re.split('[│║]', header[i + 1:])):
                end, closed = i, True
                break
        inner = [i for i in seps if i < end]
        keys = 0
        for position, i in enumerate(inner):
            if header[i] == '║':
                keys = position + 1
                break
        return [0] + [i + 1 for i in inner], inner + [end], end, keys, closed

    def columns(self):
        '''Columns as {name, sort, type, key}: sort is asc, desc or empty; type is the type character or empty.'''
        if not self._bounds:
            return []
        starts, stops, end, keys, closed = self._bounds
        header = self.rows[HEADER_ROW]
        out = []
        for index, (a, b) in enumerate(zip(starts, stops)):
            cell = header[a:b]
            mark, body = cell[:1], cell[1:]
            kind = body[-1] if body and body[-1] in TYPE_CHARS else ''
            name = (body[:-1] if kind else body).strip()
            sort = 'asc' if mark and mark in SORT_ASC else 'desc' if mark and mark in SORT_DESC else ''
            out.append({'name': name, 'sort': sort, 'type': kind, 'key': index < keys})
        return out

    def _scan(self):
        '''The displayed data rows as lists of cell texts, and the indexes of the selected ones.'''
        if not self._bounds:
            return [], []
        starts, stops, end, keys, closed = self._bounds
        marks = stops[:-1] + ([end] if closed else [])
        reach = stops if closed else stops[:-1] + [None]
        table, selected = [], []
        for text in self.rows[FIRST_ROW:self.height - 1]:
            if not text.strip() or (marks and (len(text) <= max(marks) or any(text[p] not in SEPARATORS for p in marks))):
                break
            cells = [text[a:b] for a, b in zip(starts, reach)]
            if cells and cells[0][:1] == SELECTED:
                selected.append(len(table))
                cells[0] = cells[0][1:]
            table.append([NOTE.sub('', c.strip()) for c in cells])
        return table, selected

    def table(self):
        return self._scan()[0]

    def selected_rows(self):
        '''Indexes of the displayed rows that carry the selection bullet in their first character.'''
        return self._scan()[1]

    # -- cursor (reverse video) ----------------------------------------------------------------------------
    def cursor_row(self):
        '''Index of the displayed data row drawn in reverse video, or None.'''
        count = len(self.table())
        for s in self.styles:
            row = s.get('row')
            if row is not None and FIRST_ROW <= row < FIRST_ROW + count and 'reverse' in s.get('style', []):
                return row - FIRST_ROW
        return None

    def cursor_column(self):
        '''Index of the column whose header is drawn in reverse video, or None.'''
        if not self._bounds:
            return None
        starts, stops = self._bounds[0], self._bounds[1]
        for s in self.styles:
            if s.get('row') == HEADER_ROW and 'reverse' in s.get('style', []):
                start = s['columns'][0]
                for index, (a, b) in enumerate(zip(starts, stops)):
                    if a <= start < b:
                        return index
        return None

    def cursor(self):
        '''The cursor cell as {column, value}, or None when the cursor row or column cannot be told.'''
        row, col = self.cursor_row(), self.cursor_column()
        columns, table = self.columns(), self.table()
        if row is None or col is None or col >= len(columns) or row >= len(table):
            return None
        return {'column': columns[col]['name'], 'value': table[row][col]}

    # -- status line, prompt and messages -----------------------------------------------------------------
    def status_line(self):
        return self.rows[self.height - 1].rstrip()

    def _status(self):
        '''(text before the bar that ends the sheet list, text after it); (None, whole line) while a prompt is up.'''
        line = self.status_line()
        found = re.match(r'(.*?)[|] {2,}(.*)$', line)
        if not found:
            return None, line
        return found.group(1), found.group(2)

    def stack(self):
        '''Names of the sheets listed at the left of the status line, or None while a prompt is active. Metasheets
        (columns, sheets, options and so on) are not listed there.'''
        left, _ = self._status()
        if left is None:
            return None
        names = []
        for entry in left.split(' | '):
            found = re.match(r'[0-9]+(.)(.*)$', entry.strip())
            names.append(found.group(2) if found else entry.strip())
        return names

    def sheet(self):
        '''The last sheet named in the status line (the data sheet shown, unless a metasheet is on top).'''
        names = self.stack()
        return names[-1] if names else None

    def count(self):
        '''(number, noun) shown at the right of the status line, for example (5, rows), or None.'''
        _, right = self._status()
        found = re.findall(r'([0-9]+) ([a-z]+)', right)
        return (int(found[-1][0]), found[-1][1]) if found else None

    def selected_count(self):
        '''The number after the selection bullet in the status line (0 when nothing is selected).'''
        _, right = self._status()
        found = re.search(r'•([0-9]+)', right)
        return int(found.group(1)) if found else 0

    def prompt(self):
        '''The text of the input prompt on the last line, without the input field fill, or None.'''
        if self._status()[0] is not None:
            return None
        return re.split(' {2,}', self.status_line())[0].rstrip('_').rstrip() or None

    def messages(self):
        '''Lines of the recent-messages box drawn with block characters near the lower right corner.'''
        out = []
        for text in self.rows:
            if '▐' in text and '▌' in text:
                inner = text[text.index('▐') + 1:text.rindex('▌')].strip()
                if inner and set(inner) != {'█'}:
                    out.append(inner)
        return out

    def last_message(self):
        found = self.messages()
        return found[-1] if found else None

    def lines(self):
        return [row.rstrip() for row in self.rows if row.strip()]


def difference(a, b):
    '''Short description of the first difference between two JSON-able observations.'''
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'
    return f'{a!r} != {b!r}'
