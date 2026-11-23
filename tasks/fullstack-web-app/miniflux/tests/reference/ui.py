"""Pinned-standard browser driving through the black-box runtime's GUI operations (record only).

Controls are found in the runtime's own snapshot (form field names, labels, accessible names) and operated by
ref, exactly as the model and the evaluator can. Names and form fields belong to the pinned standard; they are
never a candidate requirement.
"""
import re
import time

from evaluation.broker import BrokerError

SESSION = {'session': 'main'}
WAIT = 8.0


def accessible(control):
    """The names a user (or a locator) would know a control by."""
    return [x for x in (control.get('aria'), control.get('label'), control.get('text'), control.get('title'),
                        control.get('placeholder'), control.get('value') if control.get('type') in ('submit', 'button')
                        else None) if x]


def action_pattern(name):
    # A counter may follow an action name; never another word (Star must not match Unstar).
    return re.compile(r'^' + re.escape(name) + r'(?:\s+(?:\d+|\(\d+\)))?\s*$', re.I)


class UI:
    def __init__(self, broker):
        self.broker = broker
        self.snap = None

    def call(self, op, **fields):
        answer = self.broker.call({'op': op, **SESSION, **fields})
        if isinstance(answer, dict) and 'controls' in answer:
            self.snap = answer
        return answer

    def snapshot(self):
        return self.call('snapshot')

    def goto(self, path):
        for attempt in range(4):
            try:
                self.call('open', path=path)
                return self.snap
            except BrokerError as exc:
                if attempt == 3 or 'interrupted by another navigation' not in exc.detail:
                    raise
                time.sleep(1.0)

    def reload(self):
        self.call('reload')

    @property
    def url(self):
        return (self.snap or self.snapshot())['url']

    def text(self):
        return self.snapshot()['text']

    def wait(self, predicate, what, timeout=WAIT):
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snapshot()
            found = predicate(snap)
            if found:
                return found
            if time.monotonic() > deadline:
                raise AssertionError(what + ' (at ' + snap['url'] + ')')
            time.sleep(0.2)

    def require(self, *texts, timeout=WAIT):
        for text in texts:
            self.wait(lambda s, t=text: t in s['text'], 'visible text absent: ' + repr(text), timeout)

    def field(self, name, timeout=3.0):
        """A visible form control by its form field name."""
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snapshot()
            for control in snap['controls']:
                if control.get('name') == name and control['tag'] in ('input', 'textarea', 'select') \
                        and not control.get('disabled'):
                    return control
            if time.monotonic() > deadline:
                raise AssertionError('visible form field missing: ' + name)
            time.sleep(0.2)

    def fill(self, name, value):
        self.call('fill', target={'ref': self.field(name)['ref']}, value=value)

    def check(self, name, value=True):
        self.call('check', target={'ref': self.field(name)['ref']}, checked=value)

    def select(self, name, value):
        self.call('select', target={'ref': self.field(name)['ref']}, value=value)

    def button(self, *names, timeout=3.0, within=None):
        """A visible action control whose accessible name is one of names (counters allowed)."""
        patterns = [action_pattern(n) for n in names]
        deadline = time.monotonic() + timeout
        self.snapshot()

        def rank(control):
            """Buttons before links and menu entries."""
            if control['tag'] == 'button' or control.get('type') in ('submit', 'button') or control.get('role') == 'button':
                return 0
            if control['tag'] in ('a', 'summary') or control.get('role') in ('link', 'menuitem', 'option', 'tab'):
                return 1
            return None
        while True:
            for pattern in patterns:
                matches = [c for c in self.snap['controls'] if rank(c) is not None and not c.get('disabled')
                           and not c.get('offscreen') and any(pattern.search(n) for n in accessible(c))
                           and (within is None or within(c))]
                if not matches:
                    matches = [c for c in self.snap['controls'] if rank(c) is not None and not c.get('disabled')
                               and any(pattern.search(n) for n in accessible(c)) and (within is None or within(c))]
                if matches:
                    return min(matches, key=rank)
            if time.monotonic() > deadline:
                raise AssertionError('visible action missing: ' + str(names))
            time.sleep(0.2)
            self.snapshot()

    def click(self, *names, **kwargs):
        control = self.button(*names, **kwargs)
        self.call('click', target={'ref': control['ref']})
        return control

    def click_ref(self, control):
        self.call('click', target={'ref': control['ref']})

    def link(self, href):
        """Click the visible link to an exact product path."""
        snap = self.snapshot()
        for control in snap['controls']:
            if control['tag'] == 'a' and control.get('href') == href:
                self.call('click', target={'ref': control['ref']})
                return control
        raise AssertionError('link missing: ' + href)

    def sign_in(self, user, password):
        if self.url.split('?')[0] != '/':
            self.goto('/')
        self.fill('username', user)
        self.fill('password', password)
        self.click('Login')
        self.wait(lambda s: s['url'].split('?')[0] != '/', 'sign-in did not complete')
