"""Driving and observation helpers over the task black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: GUI operations (key/keys/type/paste/mouse/wait)
and the screen observation for the interactive terminal; the workspace inspector, micro's configuration files and
the command-line channel for setup and backend checks; and the lifecycle operations (status/reset/restart/place/
modify). No product internals are touched. The Screen parser turns a settled terminal snapshot into semantic facts
(the status line fields of each pane, the message line, the tab bar, the line numbers in the gutter, the style of
a token), so checks assert meaning rather than exact layout, except where the layout is the behaviour under test.
"""
from __future__ import annotations

import re
import time


class Session:
    """Thin convenience wrapper over ctx.broker for recipes, setup and checks."""

    def __init__(self, broker):
        self.broker = broker
        self.snapshots = {}  # screen observations taken in the middle of a checkpoint's steps, by name

    def call(self, request, **kw):
        return self.broker.call(request, **kw)

    # -- GUI operations ------------------------------------------------------------------------------------
    def key(self, name):
        return self.call({'op': 'key', 'key': name})

    def keys(self, names):
        return self.call({'op': 'keys', 'keys': list(names)})

    def type(self, text):
        return self.call({'op': 'type', 'text': text})

    def paste(self, text):
        return self.call({'op': 'paste', 'text': text})

    def mouse(self, spec):
        return self.call(dict(spec, op='mouse'))

    def wait(self, seconds=0.5):
        return self.call({'op': 'wait', 'seconds': seconds})

    def resize(self, columns, rows):
        return self.call({'op': 'resize', 'columns': columns, 'rows': rows})

    def command(self, text, enter=True):
        """Open micro's command bar (Control+E), type a command and run it with Enter."""
        self.key('Control+E')
        if text:
            self.type(text)
        return self.key('Enter') if enter else self.screen_raw()

    def screen_raw(self):
        return self.call({'op': 'screen'})

    def screen(self):
        return Screen(self.screen_raw())

    @staticmethod
    def sync(fraction=0.2):
        """Wait for the start of a wall-clock second: micro groups undo history by the second in which an edit
        happened, so a burst of edits that must form one undo step starts early in a second."""
        while time.time() % 1.0 > fraction:
            time.sleep(0.01)

    # -- lifecycle -----------------------------------------------------------------------------------------
    def status(self):
        return self.call({'op': 'status'})

    def reset(self, args=None):
        request = {'op': 'reset'}
        if args is not None:
            request['args'] = list(args)
        return self.call(request)

    def restart(self, args=None):
        request = {'op': 'restart'}
        if args is not None:
            request['args'] = list(args)
        return self.call(request)

    def place(self, files=None, config=None, args=None):
        request = {'op': 'place'}
        if files:
            request['files'] = files
        if config:
            request['config'] = config
        if args is not None:
            request['args'] = list(args)
        return self.call(request)

    def modify(self, path, text=None, base64=None):
        request = {'op': 'modify', 'path': path}
        if base64 is not None:
            request['base64'] = base64
        else:
            request['text'] = text
        return self.call(request)

    # -- non-GUI read channels ------------------------------------------------------------------------------
    def read(self, path):
        return self.call({'op': 'workspace', 'action': 'read', 'path': path})

    def workspace(self, action='list', path='/workspace'):
        return self.call({'op': 'workspace', 'action': action, 'path': path})

    def config(self, file):
        return self.call({'op': 'config', 'file': file})

    def cli(self, option):
        return self.call({'op': 'cli', 'option': option})


def _cell_rows(obs):
    """Strip the 'NN|' row-number prefix the runtime adds, returning the raw screen rows."""
    return [line.split('|', 1)[1] if '|' in line else line for line in obs['screen']]


# A status line segment as micro's default statusformatl draws it (one per pane; vertical splits put several on
# one row): "NAME [+ |[ro] ][[ovwr] ](LINE,COL) [PASTE ]| ft:TYPE | FORMAT | ENCODING". In a narrow pane the
# right-hand part follows the encoding directly, so the encoding ends at a space, a divider, the end or a capital.
SEGMENT = re.compile(r'(?:^|(?<=\|))(?P<name>[^|()]*?[^|()\s])\s(?P<mod>\+ |\[ro\] )?(?P<ovwr>\[ovwr\] )?'
                     r'\((?P<line>\d+),(?P<col>\d+)\) (?P<paste>PASTE )?\| ft:(?P<ft>\S*?) \| (?P<ff>[a-z]+) \| '
                     r'(?P<enc>[a-z0-9_-]+)')
GUTTER = re.compile(r'^\s*(\d+) ')


class Screen:
    """Semantic view of a settled micro terminal snapshot."""

    def __init__(self, obs):
        self.obs = obs
        self.rows = _cell_rows(obs)
        self.height = len(self.rows)
        self.width = obs.get('size', [0, 0])[0]
        self.styles = obs.get('styles', [])
        self.base_style = obs.get('base_style', [])
        self.process = obs.get('process')

    # -- status lines ----------------------------------------------------------------------------------------
    def segments(self):
        """Every status line segment on the screen, top to bottom and left to right."""
        out = []
        for row, text in enumerate(self.rows[:-1]):
            for match in SEGMENT.finditer(text):
                out.append({'row': row, 'column': match.start('name'), 'name': match.group('name').strip(),
                            'modified': match.group('mod') == '+ ', 'readonly': match.group('mod') == '[ro] ',
                            'overwrite': bool(match.group('ovwr')), 'paste': bool(match.group('paste')),
                            'line': int(match.group('line')), 'col': int(match.group('col')),
                            'filetype': match.group('ft'), 'fileformat': match.group('ff'),
                            'encoding': match.group('enc')})
        return out

    def status(self):
        """The status line of the bottom-left pane (the only pane unless the view is split)."""
        left = [s for s in self.segments() if s['column'] == 0]
        return left[-1] if left else None

    def message(self):
        """The message/command line: the last row of the terminal."""
        return self.rows[-1].rstrip() if self.rows else ''

    # -- tab bar ---------------------------------------------------------------------------------------------
    def tabs(self):
        """The tab bar's names and the active one ('[name]'), or None when no tab bar is drawn."""
        top = self.rows[0] if self.rows else ''
        if '[' not in top or GUTTER.match(top):
            return None
        # Each tab is drawn as '[NAME]' (active) or ' NAME ' followed by two spaces.
        names, active, pos = [], None, 0
        text = top.rstrip()
        while pos < len(text):
            if text[pos] == '[':
                end = text.find(']', pos + 1)
                if end < 0:
                    return None
                active = len(names)
            elif text[pos] == ' ':
                end = text.find('   ', pos + 1)
                end = len(text) if end < 0 else end
            else:
                return None
            names.append(text[pos + 1:end])
            pos = end + 3
        return {'names': names, 'active': active} if names else None

    # -- buffer area -------------------------------------------------------------------------------------------
    def gutter(self, column=0):
        """Line numbers in the ruler of the pane starting at `column`, top to bottom (blank rows skipped)."""
        top = 1 if self.tabs() else 0
        status = self.status()
        bottom = status['row'] if status else self.height - 1
        out = []
        for row in range(top, bottom):
            match = GUTTER.match(self.rows[row][column:])
            if match:
                out.append(int(match.group(1)))
        return out

    def text_rows(self, start, end):
        return [self.rows[r].rstrip() for r in range(start, min(end, self.height))]

    def find(self, token, row=None):
        """(row, column) of the first occurrence of token (in one row, or anywhere above the message line)."""
        rows = [row] if row is not None else range(self.height - 1)
        for r in rows:
            column = self.rows[r].find(token)
            if column >= 0:
                return r, column
        return None

    def style_at(self, row, column):
        for span in self.styles:
            a, b = span.get('columns', [0, 0])
            if span.get('row') == row and a <= column < b:
                return sorted(span.get('style', []))
        return sorted(self.base_style)

    def token_style(self, token, row=None):
        """The style flags of the first cell of a token on the screen, or None if it is not shown."""
        where = self.find(token, row)
        if where is None:
            return None
        return self.style_at(*where)
