"""Driving and observation helpers over the task black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: GUI operations (key/keys/type/wait) and the
screen observation for the interactive terminal; the application's command line (the task operation) for setup and
backend checks; and the lifecycle operations (status/reset/restart). No product internals are touched. The Screen
parser turns a settled terminal snapshot into semantic facts (the tasks listed in the report in display order, the
selected and marked tasks, the prompt, the report and context names, the task details, popups and the other views).
It relies on the reference's screen conventions, which the instruction makes part of the contract: the top bar with
the "report [context]" label at its right end, the report's header row and the selection and mark indicators in the
first two columns, the full-width rule above the details pane, the prompt title and input line as the last two rows,
and rounded boxes with their title in the top border; it never relies on colours.
"""
from __future__ import annotations

import json
import re

from evaluation.broker import BrokerError

try:
    from wcwidth import wcwidth
except ImportError:  # the verifier image provides wcwidth; plain text without it
    wcwidth = None


class Session:
    """Thin convenience wrapper over ctx.broker for recipes, setup and checks."""

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

    def resize(self, columns, rows):
        return self.broker.call({'op': 'resize', 'columns': columns, 'rows': rows})

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

    # -- the application's command line --------------------------------------------------------------------
    def task(self, args, stdin=None):
        request = {'op': 'task', 'args': list(args)}
        if stdin is not None:
            request['stdin'] = stdin
        return self.broker.call(request)

    def export(self):
        """All tasks as the application's command line exports them (a JSON array)."""
        done = self.task(['rc.json.array=on', 'rc.verbose=nothing', 'export'])
        if done.get('exit_code') != 0:
            raise AssertionError('task export failed with status %r: %s' % (done.get('exit_code'),
                                                                            (done.get('stderr') or '')[-300:]))
        try:
            value = json.loads(done.get('stdout') or '')
        except ValueError:
            raise AssertionError('task export did not print a JSON array: ' + (done.get('stdout') or '')[:200]) from None
        if not isinstance(value, list) or not all(isinstance(t, dict) for t in value):
            raise AssertionError('task export did not print a JSON array of task objects')
        return value


# -- screen semantics ----------------------------------------------------------------------------------------------
SEPARATOR = re.compile(r'^\s*[─━-]{20,}\s*$')
HISTORY = re.compile(r'\s*\[\s*\d+\s*/\s*\d+\s*\]\s*$')
BOX_TOP = re.compile(r'╭([^─╮]*)─')
SELECT_GLYPHS = ('•', '⦿', '⦾')
MARK_GLYPHS = ('✔', '⦿')
VIEWS = (('Projects', re.compile(r'^\s*Project\s+Remaining\s+Avg age\s+Complete\b')),
         ('Timesheet', re.compile(r'^\s*Wk\s+Date\s+Day\s+ID\s+Action\b')),
         ('Calendar', re.compile(r'\b(?:Su Mo Tu We Th Fr Sa|Mo Tu We Th Fr Sa Su)\b')))


def rows_of(obs):
    """The raw screen rows without the runtime's 'NN|' row-number prefix."""
    out = []
    for line in obs.get('screen', []):
        out.append(line.split('|', 1)[1] if '|' in line[:4] else line)
    return out


def squash(text):
    return ' '.join(str(text).split())


def char_width(char):
    """Terminal columns of one character as the runtime's screen rows hold it: a wide character is one character of
    the row text but takes two columns."""
    return 2 if wcwidth is not None and wcwidth(char) == 2 else 1


def display_columns(text):
    """The terminal column at which each character of a screen row starts."""
    out, column = [], 0
    for char in text:
        out.append(column)
        column += char_width(char)
    return out


def display_slice(text, start, end=None):
    """The characters of a screen row that start in terminal columns [start, end)."""
    return ''.join(char for char, column in zip(text, display_columns(text))
                   if column >= start and (end is None or column < end))


class Screen:
    """Semantic view of a settled taskwarrior-tui terminal snapshot."""

    def __init__(self, obs):
        self.obs = obs
        self.rows = rows_of(obs)
        self.height = len(self.rows)
        self.width = (obs.get('size') or [120, 36])[0]
        self.styles = obs.get('styles', [])
        self.process = obs.get('process')

    # -- frame -------------------------------------------------------------------------------------------
    def top(self):
        return self.rows[0] if self.rows else ''

    def label(self):
        """The report name and context shown at the right of the top bar ('next [none]')."""
        match = re.search(r'(\S+)\s+\[([^\]]*)\]\s*$', self.top())
        return {'report': match.group(1), 'context': match.group(2)} if match else None

    def view(self):
        """The view on screen, from its content: Taskwarrior's project summary (Projects), its timesheet table
        (Timesheet), month grids (Calendar), otherwise the task report under its header row (Tasks); None when
        nothing is drawn below the top bar."""
        body = self.rows[1:self.height - 2]
        for name, pattern in VIEWS:
            if any(pattern.search(row) for row in body):
                return name
        return 'Tasks' if self.height > 1 and self.rows[1].strip() else None

    def prompt(self):
        """The prompt title (without the history position) and its input line: the last two rows."""
        if self.height < 2:
            return None
        title = self.rows[-2].rstrip()
        return {'title': HISTORY.sub('', title).strip(), 'line': self.rows[-1].rstrip()}

    def history_position(self):
        if self.height < 2:
            return None
        match = re.search(r'\[\s*(\d+)\s*/\s*(\d+)\s*\]\s*$', self.rows[-2])
        return [int(match.group(1)), int(match.group(2))] if match else None

    def body(self):
        """Rows between the top bar and the prompt."""
        return self.rows[1:self.height - 2]

    # -- popups ------------------------------------------------------------------------------------------
    def boxes(self):
        """Rounded boxes drawn over the screen: [{title, top, left, right, lines}] (lines are the box interior)."""
        out = []
        for y, row in enumerate(self.rows):
            for match in re.finditer('╭', row):
                left = match.start()
                right = row.find('╮', left)
                if right < 0:
                    continue
                title = row[left + 1:right].strip('─').strip()
                title = re.sub('─+.*$', '', title).strip()
                lines = []
                for yy in range(y + 1, self.height):
                    line = self.rows[yy]
                    if len(line) > left and line[left] == '╰':
                        break
                    if len(line) > left and line[left] == '│':
                        lines.append(line[left + 1:right].rstrip())
                    else:
                        break
                out.append({'title': title, 'top': y, 'left': left, 'right': right, 'lines': lines})
        return out

    def popup(self, title=None):
        for box in self.boxes():
            if title is None or box['title'].startswith(title):
                return box
        return None

    def error(self):
        """The text of an error popup (a box titled Error), joined to one line; without such a box, the screen text
        when the prompt title says Error; otherwise None."""
        box = self.popup('Error')
        if box is not None:
            return squash(' '.join(line.strip() for line in box['lines']))
        prompt = self.prompt()
        if prompt and prompt['title'].startswith('Error'):
            return squash(' '.join(self.rows))
        return None

    def menu(self, title):
        """A switcher menu (title 'Context' or 'Report'): its search text, its entries as [name, description,
        active] in display order, and the highlighted entry."""
        boxes = self.boxes()
        search = next((b for b in boxes if b['title'].startswith(title)), None)
        if search is None:
            return None
        below = [b for b in boxes if b['top'] > search['top'] and b['left'] == search['left']]
        text = search['lines'][0].strip() if search['lines'] else ''
        entries, selected = [], None
        if below:
            table = below[0]['lines']
            started = False
            for line in table:
                if not started:
                    if line.strip().startswith('Name'):
                        started = True
                    continue
                if not line.strip():
                    continue
                marker, body = line[:2].strip(), line[2:]
                parts = body.split()
                if not parts:
                    continue
                name, active = parts[0], parts[-1] if len(parts) > 1 else ''
                description = squash(' '.join(parts[1:-1]))
                entries.append([name, description, active])
                if marker:
                    selected = name
        return {'search': text, 'entries': entries, 'selected': selected}

    def layout(self):
        """Where the task details are shown: 'bottom' (below a full-width rule), 'right' (a 'Name Value' header in
        the right half) or 'none'."""
        if self.separator_row() is not None:
            return 'bottom'
        half = self.width // 2
        for row in self.rows[1:self.height - 2]:
            right = row[half - 10:] if len(row) > half - 10 else ''
            if re.search(r'\bName\s+Value\b', right):
                return 'right'
        return 'none'

    # -- task report -------------------------------------------------------------------------------------
    def separator_row(self):
        for y in range(1, self.height - 2):
            if SEPARATOR.match(self.rows[y]):
                return y
        return None

    def report_rows(self):
        """Rows of the task report: the non-blank rows after the header row (row 1) and before the details
        separator or the prompt. Each item is (row index, text)."""
        end = self.separator_row() or self.height - 2
        out = []
        for y in range(2, end):
            if self.rows[y].strip():
                out.append((y, self.rows[y]))
        return out

    def headers(self):
        return self.rows[1].split() if self.height > 1 else []

    @staticmethod
    def match_description(text, descriptions):
        """The longest known description that occurs in the row as a whole-word run, or None."""
        best = None
        for description in descriptions:
            if not description:
                continue
            start = text.find(description)
            while start >= 0:
                end = start + len(description)
                before = text[start - 1] if start > 0 else ' '
                after = text[end] if end < len(text) else ' '
                if before in ' …' and after in ' …[':
                    if best is None or len(description) > len(best):
                        best = description
                    break
                start = text.find(description, start + 1)
        return best

    def listed(self, descriptions, glyphs=SELECT_GLYPHS + MARK_GLYPHS):
        """[(description or '?', indicator)] for each report row in display order."""
        out = []
        for _, text in self.report_rows():
            indicator = text[:2].strip()
            name = self.match_description(text[2:], descriptions)
            out.append((name if name is not None else '?' + squash(text[2:])[:40], indicator))
        return out

    def rows_listed(self, descriptions):
        return [name for name, _ in self.listed(descriptions)]

    def selected(self, descriptions, glyphs=SELECT_GLYPHS):
        names = [name for name, indicator in self.listed(descriptions) if indicator[:1] in glyphs and indicator]
        return names[0] if len(names) == 1 else (names or None)

    def marked(self, descriptions, glyphs=MARK_GLYPHS):
        return sorted(name for name, indicator in self.listed(descriptions) if indicator and indicator[:1] in glyphs)

    def indicators(self, descriptions):
        return {name: indicator for name, indicator in self.listed(descriptions)}

    def columns(self):
        """Header labels with their start columns (labels are separated by at least one space), in terminal
        columns."""
        header = self.rows[1] if self.height > 1 else ''
        starts = display_columns(header)
        return [(m.group(0), starts[m.start()]) for m in re.finditer(r'\S+', header)]

    def cells(self, label, descriptions):
        """{description: cell text} of the column headed `label` for each report row."""
        cols = self.columns()
        names = [name for name, _ in cols]
        if label not in names:
            return None
        index = names.index(label)
        start = cols[index][1]
        end = cols[index + 1][1] if index + 1 < len(cols) else None
        out = {}
        for (_, text), (name, _) in zip(self.report_rows(), self.listed(descriptions)):
            cell = display_slice(text, start, end)
            out[name] = re.sub('[\u2500-\u259f]', '', cell).strip()   # without the scrollbar of the last column
        return out

    # -- task details --------------------------------------------------------------------------------------
    def details_rows(self):
        sep = self.separator_row()
        if sep is None:
            return []
        return self.rows[sep + 1:self.height - 2]

    def details(self):
        """The first Name/Value table of the details pane as an ordered list of [name, value]. The dashed rule under
        the header gives the column boundary; a line with an empty name continues the previous value."""
        rows = [row.rstrip() for row in self.details_rows()]
        out = []
        for index, row in enumerate(rows):
            if not (row.strip().startswith('Name') and 'Value' in row and index + 1 < len(rows)):
                continue
            rule = rows[index + 1]
            groups = [m.start() for m in re.finditer(r'-+', rule)]
            if len(groups) < 2:
                continue
            start = groups[1]
            for line in rows[index + 2:]:
                if not line.strip():
                    break
                name, value = line[:start].strip(), line[start:].strip()
                if name:
                    out.append([name, value])
                elif out:
                    out[-1][1] = (out[-1][1] + ' ' + value).strip()
            break
        return out

    def details_text(self):
        return [row.rstrip() for row in self.details_rows() if row.strip()]

    # -- other views --------------------------------------------------------------------------------------
    def content(self):
        """Non-blank rows below the top bar (other views), whitespace squashed."""
        return [squash(row) for row in self.rows[1:] if row.strip()]
