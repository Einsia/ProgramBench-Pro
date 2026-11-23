"""Driving and observation helpers over the task black-box runtime (terminal surface).

Everything reaches the product through the runtime's channels: GUI operations (key/keys/type/wait) and the
screen observation for the interactive terminal; the home-directory inspector, the SQLite cache tables and the
command line for setup and backend checks; and the lifecycle operations (status/reset/restart/place). No product
internals are touched. The Screen parser turns a settled terminal snapshot into layout-independent facts (the
title bar, the message line, the list rows, which known labels are listed and in which order, which one is
focused), so checks assert meaning rather than exact columns or colours unless the layout itself is the behaviour.
"""
from __future__ import annotations

import re
import time

from evaluation.broker import BrokerError


class Session:
    """Thin convenience wrapper over ctx.broker for recipes, setup and checks."""

    def __init__(self, broker):
        self.broker = broker

    def call(self, request, **kw):
        return self.broker.call(request, **kw)

    def key(self, name):
        return self.broker.call({'op': 'key', 'key': name})

    def keys(self, names):
        return self.broker.call({'op': 'keys', 'keys': list(names)})

    def type(self, text):
        return self.broker.call({'op': 'type', 'text': text})

    def wait(self, seconds=0.5):
        return self.broker.call({'op': 'wait', 'seconds': seconds})

    def screen(self):
        return Screen(self.broker.call({'op': 'screen'}))

    def status(self):
        return self.broker.call({'op': 'status'})

    def restart(self, args=None):
        request = {'op': 'restart'}
        if args:
            request['args'] = list(args)
        return self.broker.call(request)

    def place(self, files):
        return self.broker.call({'op': 'place', 'files': files})

    def home(self, action='list', path='~'):
        return self.broker.call({'op': 'home', 'action': action, 'path': path})

    def cache(self, table):
        return self.broker.call({'op': 'cache', 'table': table})

    def cli(self, args):
        result=self.broker.call({'op': 'cli', 'args': list(args)})
        if result.get('output_limited') or result.get('timed_out'):
            raise AssertionError('the candidate command exceeded its output or time limit')
        return result

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


def _rows(obs):
    """Strip the 'NN|' row-number prefix the runtime adds."""
    return [line.split('|', 1)[1] if '|' in line else line for line in obs.get('screen', [])]


class Screen:
    """Semantic view of a settled Newsboat terminal snapshot (default layout: title bar on the first row, key hints
    on the second-to-last row, messages and prompts on the last row)."""

    def __init__(self, obs):
        self.obs = obs
        self.rows = _rows(obs)
        self.height = len(self.rows)
        self.width = (obs.get('size') or [120, 36])[0]
        self.styles = obs.get('styles') or []
        self.process = obs.get('process')

    # -- regions -------------------------------------------------------------------------------------------
    def title(self):
        return self.rows[0].strip() if self.rows else ''

    def hints(self):
        return self.rows[self.height - 2].strip() if self.height >= 2 else ''

    def message(self):
        return self.rows[self.height - 1].strip() if self.rows else ''

    def body(self):
        """Rows between the title bar and the hint bar, right-stripped; trailing blank rows and the pager's '~'
        filler rows at the end are dropped."""
        rows = [r.rstrip() for r in self.rows[1:self.height - 2]]
        while rows and rows[-1].strip() in ('', '~'):
            rows.pop()
        return rows

    def all_text(self):
        return [r.rstrip() for r in self.rows]

    # -- list semantics ------------------------------------------------------------------------------------
    def highlighted_rows(self, labels=None):
        """Rows with a distinct background/reverse attribute, independent of highlight width or colour."""
        by_style = {}
        for s in self.styles:
            row = s.get('row')
            if row is None or not 0 < row < self.height - 2:
                continue
            if labels is not None and self.label_of(self.rows[row],labels) is None:
                continue
            for flag in s.get('style', []):
                if flag.startswith('bg=') or flag == 'reverse':
                    by_style.setdefault(flag,set()).add(row)
        if len(by_style.get('reverse',())) == 1:
            return sorted(by_style['reverse'])
        return sorted({next(iter(rows)) for rows in by_style.values() if len(rows)==1})

    @staticmethod
    def label_of(row, labels):
        """The longest known label that occurs in the row text (labels are fixture titles, so they are unique)."""
        best = None
        for label in labels:
            if label in row and (best is None or len(label) > len(best)):
                best = label
        return best

    def labels(self, labels):
        """Known labels listed in the body, in display order (each body row contributes at most one)."""
        out = []
        for row in self.body():
            label = self.label_of(row, labels)
            if label is not None:
                out.append(label)
        return out

    def focus(self, labels):
        rows = self.highlighted_rows(labels)
        if len(rows) != 1:
            return None
        return self.label_of(self.rows[rows[0]], labels)

    _COUNT = re.compile(r'\((\d+)/(\d+)\)')

    def counts(self, labels):
        """label -> [unread, total] read from each listed row's "(unread/total)" field."""
        out = {}
        for row in self.body():
            label = self.label_of(row, labels)
            match = self._COUNT.search(row)
            if label is not None and match:
                out[label] = [int(match.group(1)), int(match.group(2))]
            elif label is not None:
                unread = re.search(r'\bunread\s*[:=]?\s*(\d+)\b',row,re.I) or re.search(r'\b(\d+)\s*unread\b',row,re.I)
                total = re.search(r'\btotal\s*[:=]?\s*(\d+)\b',row,re.I) or re.search(r'\b(\d+)\s*total\b',row,re.I)
                if unread and total:
                    out[label] = [int(unread.group(1)),int(total.group(1))]
        return out

    def styled(self, pattern):
        """Style runs whose text matches the regex, as [row text of the run (stripped), sorted style flags]."""
        rx = re.compile(pattern)
        out = []
        for s in self.styles:
            text = (s.get('text') or '').strip()
            if text and rx.search(text):
                out.append([text, sorted(s.get('style', []))])
        return out

    def exited(self):
        if self.process=='running':
            return False
        if self.process!='exited with status 0':
            raise AssertionError('the application crashed or did not start')
        return True

    def require_view(self, view):
        """Check semantic context before accepting an empty list or dialog-specific result."""
        patterns={'list':r'feed|article|search|result|subscription|matching|no (?:items|entries)',
                  'urls':r'\bURLs?\b|links?', 'help':r'help|key.?bindings?',
                  'search':r'search|results?', 'articles':r'articles?|items?',
                  'feeds':r'feeds?|subscriptions?', 'dialogs':r'dialogs?|views?'}
        if self.process!='running' or not re.search(patterns[view],self.title(),re.I):
            raise AssertionError('the expected '+view+' view is not available')
