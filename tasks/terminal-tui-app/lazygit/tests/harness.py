'''Driving and observation helpers over the lazygit black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: the GUI operations (key, keys, type, wait) and the
screen observation for the interactive terminal; the git, workspace, state, clipboard and command-line channels for
setup and backend checks; and the lifecycle operations (status, reset, restart, setup). No product internals are
touched. The Screen parser turns a settled terminal snapshot into layout-independent semantic facts: the panels of
the left column with their items, the selected item and its position, the focused panel, the title and text of the
main view and any open popup. Checks assert meaning, never exact columns or colours.
'''
from __future__ import annotations

import re
import time

from evaluation.broker import BrokerError

# Box-drawing glyphs: rounded, square, heavy and double borders are all accepted.
TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT = '╭┌┏╔', '╮┐┓╗', '╰└┗╚', '╯┘┛╝'
HORIZONTAL, VERTICAL = '─━═', '│┃║'
PANEL_NUMBER = re.compile(r'^\[([0-9])\] ?')
POSITION = re.compile('([0-9]+) of ([0-9]+)')
VERSION_TAIL = re.compile('( +Donate +Ask Question)? +[0-9]+[.][0-9]+[.][0-9]+ *$')


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

    def screen_raw(self):
        return self.broker.call({'op': 'screen'})

    def screen(self):
        return Screen(self.screen_raw())

    # -- lifecycle and preparation -------------------------------------------------------------------------
    def status(self):
        return self.broker.call({'op': 'status'})

    def reset(self):
        return self.broker.call({'op': 'reset'})

    def restart(self):
        return self.broker.call({'op': 'restart'})

    def setup(self, steps):
        return self.broker.call({'op': 'setup', 'steps': steps}, timeout=240)

    # -- non-GUI read channels -----------------------------------------------------------------------------
    def git(self, argv, repo=None, remote=None):
        request = {'op': 'git', 'argv': list(argv)}
        if repo is not None:
            request['repo'] = repo
        if remote is not None:
            request['remote'] = remote
        return self.broker.call(request)

    def workspace(self, action='list', path='/workspace'):
        return self.broker.call({'op': 'workspace', 'action': action, 'path': path})

    def state(self):
        return self.broker.call({'op': 'state'})

    def clipboard(self):
        return self.broker.call({'op': 'clipboard'})

    def cli(self, option):
        return self.broker.call({'op': 'cli', 'option': option})

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


def _squash(text):
    for glyph in HORIZONTAL + TOP_LEFT + TOP_RIGHT + BOTTOM_LEFT + BOTTOM_RIGHT:
        text = text.replace(glyph, ' ')
    return ' '.join(text.split())


class Screen:
    '''Layout-independent semantic view of a settled lazygit terminal snapshot.

    Boxes are found from their corners, whatever the border glyphs and wherever they sit. A box whose top border starts
    with a number in brackets is a view: [1]-[5] are the side panels, whose top border carries the tab names and whose
    bottom border carries the position (n of m), and [0] is the main view. The selected item of a panel is the line drawn
    with a background colour, and the focused view is the one whose top-left corner is drawn in a style that no other
    view shares. An unnumbered box drawn over a view is a popup; other unnumbered boxes (the command log) are ignored.
    Column positions and widths come from the boxes themselves.'''

    def __init__(self, obs):
        self.obs = obs
        self.rows = [line.split('|', 1)[1] if '|' in line else line for line in obs['screen']]
        self.height = len(self.rows)
        self.styles = obs.get('styles', [])
        self.process = obs.get('process')
        boxes = self._boxes()
        views = [b for b in boxes if b['number'] is not None]
        self._infer_right_edges(views)
        self.popups = [self._popup(b) for b in boxes
                       if b['number'] is None and b['right'] is not None and any(self._overlap(b, v) for v in views)]
        self.rows = self._without_popups()
        self.views = {}
        for box in views:
            self.views.setdefault(box['number'], box)
        self.panels = self._panels()

    # -- boxes ---------------------------------------------------------------------------------------------
    def _cell(self, row, column):
        text = self.rows[row] if 0 <= row < self.height else ''
        return text[column] if 0 <= column < len(text) else ''

    def _scan_right(self, row, start, corners):
        '''The column of the first corner in `corners` right of `start` on the row, unless another box starts first.'''
        text = self.rows[row]
        for k in range(start + 1, len(text)):
            ch = text[k]
            if ch in corners:
                return k
            if ch in TOP_LEFT + BOTTOM_LEFT:
                return None
        return None

    def _boxes(self):
        found = []
        for i, row in enumerate(self.rows):
            for k, ch in enumerate(row):
                if ch not in TOP_LEFT:
                    continue
                bottom = None
                for r in range(i + 1, self.height):
                    below = self._cell(r, k)
                    if below in BOTTOM_LEFT:
                        bottom = r
                        break
                    if below in TOP_LEFT or below == '':
                        break
                if bottom is None:
                    continue
                top_right = self._scan_right(i, k, TOP_RIGHT)
                bottom_right = self._scan_right(bottom, k, BOTTOM_RIGHT)
                right = top_right if top_right is not None else bottom_right
                # the title ends at the next corner: the box's own, or a popup's drawn over the top border
                top_end = next((c for c in range(k + 1, len(row)) if row[c] in TOP_LEFT + TOP_RIGHT), len(row))
                title = _squash(row[k + 1:top_end])
                match = PANEL_NUMBER.match(title)
                if not match:
                    # an unnumbered box counts only when all four corners and both side borders are intact, so that
                    # corner glyphs inside content (a commit graph) never read as a box
                    sides = all(self._cell(r, k) in VERTICAL and self._cell(r, top_right) in VERTICAL + '▐'
                                for r in range(i + 1, bottom)) if top_right is not None else False
                    if top_right is None or bottom_right != top_right or not sides or bottom - i < 2:
                        continue
                found.append({'top': i, 'left': k, 'bottom': bottom, 'right': right,
                              'number': int(match.group(1)) if match else None,
                              'title': title[match.end():] if match else title,
                              'raw_title': row[k + 1:top_end]})
        return found

    def _infer_right_edges(self, views):
        '''A view whose right corners are hidden under a popup takes the right edge of a view in the same column.'''
        known = {}
        for box in views:
            if box['right'] is not None:
                known.setdefault(box['left'], []).append(box['right'])
        for box in views:
            if box['right'] is None:
                edges = known.get(box['left'])
                box['right'] = max(set(edges), key=edges.count) if edges else len(self.rows[box['top']]) - 1

    @staticmethod
    def _overlap(a, b):
        return not (a['right'] < b['left'] or b['right'] < a['left'] or a['bottom'] < b['top'] or b['bottom'] < a['top'])

    def _style(self, row, column):
        '''The style flags of the run that covers one cell, as a sorted tuple (empty when the cell is unstyled).'''
        for style in self.styles:
            a, b = style.get('columns') or [0, 0]
            if style.get('row') == row and a <= column < b:
                return tuple(sorted(style.get('style', [])))
        return ()

    def _popup(self, box):
        top, left, bottom, right = box['top'], box['left'], box['bottom'], box['right']
        lines = [self.rows[r][left + 1:right].strip() for r in range(top + 1, bottom)]
        chosen = next((r - top - 1 for r in range(top + 1, bottom) if self._span(r, left + 1, right, 'bg=')), None)
        title = box['raw_title']
        for glyph in HORIZONTAL[1:]:
            title = title.replace(glyph, '─')
        return {'title': title.split('──', 1)[0].strip('─ '), 'lines': lines, 'selected': chosen,
                'box': [top, left, bottom, right]}

    def _without_popups(self):
        '''The rows with every popup box blanked, so that popup text never reads as panel or main view content.'''
        rows = list(self.rows)
        for box in self.popups:
            top, left, bottom, right = box['box']
            for r in range(top, bottom + 1):
                text = rows[r]
                width = max(0, min(right + 1, len(text)) - left)
                rows[r] = text[:left] + ' ' * width + text[right + 1:]
        return rows

    def _span(self, row, lo, hi, *flags):
        '''Whether one style run on the row overlaps columns lo-hi and carries every named flag (prefix match).'''
        for style in self.styles:
            if style.get('row') != row:
                continue
            a, b = style.get('columns') or [0, 0]
            if b <= lo or a >= hi:
                continue
            names = style.get('style', [])
            if all(any(n == f or n.startswith(f) for n in names) for f in flags):
                return True
        return False

    # -- panels --------------------------------------------------------------------------------------------
    def _focused(self):
        '''The number of the view whose top-left corner style no other view shares, or None.'''
        styles = {number: self._style(box['top'], box['left']) for number, box in self.views.items()}
        values = list(styles.values())
        unique = [number for number, style in styles.items() if values.count(style) == 1]
        return unique[0] if len(unique) == 1 and len(values) > 1 else None

    def _panels(self):
        found = {}
        focused = self._focused()
        for number, box in sorted(self.views.items()):
            if number == 0:
                continue
            top, left, bottom, right = box['top'], box['left'], box['bottom'], box['right']
            items, selected = [], None
            for r in range(top + 1, bottom):
                cell = self.rows[r][left + 1:right].strip()
                if not cell:
                    continue
                if selected is None and self._span(r, left + 1, left + 2, 'bg='):
                    selected = len(items)
                items.append(cell)
            where = POSITION.search(self.rows[bottom][left:right + 1])
            if selected is None and where and items and int(where.group(2)) == len(items) and int(where.group(1)) >= 1:
                # a panel that does not have the focus draws no highlight: its position (n of m) names the selection
                selected = int(where.group(1)) - 1
            found[number] = {
                'title': box['title'], 'items': items, 'selected': selected,
                'position': [int(where.group(1)), int(where.group(2))] if where else None,
                'focused': focused == number}
        return found

    def panel(self, number):
        return self.panels.get(number)

    def selected(self, number):
        panel = self.panels.get(number)
        if not panel or panel['selected'] is None:
            return None
        return panel['items'][panel['selected']]

    def focus(self):
        '''The number of the focused view: 1-5 for the side panels, 0 for the main view, None when unclear.'''
        return self._focused()

    # -- main view -----------------------------------------------------------------------------------------
    def main_title(self):
        box = self.views.get(0)
        return box['title'] if box else ''

    def main_lines(self):
        box = self.views.get(0)
        if not box:
            return []
        out = []
        for r in range(box['top'] + 1, box['bottom']):
            out.append(self.rows[r][box['left'] + 1:box['right']].rstrip())
        return out

    def main_text(self):
        return '\n'.join(self.main_lines()).rstrip()

    # -- popups and the bottom line ------------------------------------------------------------------------
    def popup(self):
        return self.popups[0] if self.popups else None

    def popup_text(self):
        return ' '.join(' '.join(line for box in self.popups for line in box['lines']).split())

    def status_line(self):
        return self.rows[self.height - 1].rstrip()

    def hints(self):
        return re.split(' {2,}', VERSION_TAIL.sub('', self.status_line()).strip())[0]

    def banner(self):
        '''The right-aligned label of the bottom line while a merge, rebase or similar is under way; None when the line ends with the version.'''
        parts = re.split(' {2,}', self.status_line().strip())
        tail = parts[-1]
        if len(parts) < 2 or re.fullmatch('[0-9]+[.][0-9]+[.][0-9]+', tail):
            return None
        return tail


def difference(a, b):
    '''Short description of the first difference between two JSON-able observations.'''
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'
    return f'{a!r} != {b!r}'
