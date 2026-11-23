"""Pinned-standard browser driving through the black-box runtime's GUI operations (record only).

Controls are found in the runtime's own snapshot (form field names, labels,
accessible names) and operated by ref, exactly as the model and the evaluator
can. Names and form fields belong to the pinned standard; they are never a
candidate requirement.
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
    # A numeric badge may follow an action name; never another word (Star must not match Unstar).
    return re.compile(r'^' + re.escape(name) + r'(?:\s+(?:\d+|\(\d+\)))?\s*$', re.I)


def label_pattern(label):
    return re.compile(r'^' + re.escape(label) + r'(?:\s*[:*∗]\s*|\s*\((?:required|optional)\)\s*)*\s*$', re.I)


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
        """Open a page; when the page is navigating itself (for example reloading after an asynchronous action),
        let that navigation finish and open again."""
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

    # -- finding controls ------------------------------------------------------------------------------------------
    def find(self, *, name=None, labels=(), roles=(), tags=(), types=(), predicate=None, onscreen=False):
        snap = self.snap or self.snapshot()
        patterns = [label_pattern(x) if isinstance(x, str) else x for x in labels]
        for control in snap['controls']:
            if tags and control['tag'] not in tags:
                continue
            if types and control.get('type') not in types:
                continue
            if roles and control.get('role') not in roles:
                continue
            if onscreen and control.get('offscreen'):
                continue
            if name is not None and control.get('name') == name:
                return control
            if patterns and any(p.search(n) for p in patterns for n in accessible(control)):
                if predicate is None or predicate(control):
                    return control
            if predicate is not None and name is None and not patterns and predicate(control):
                return control
        return None

    def field(self, name, labels=(), timeout=3.0):
        self.snapshot()
        deadline = time.monotonic() + timeout
        while True:
            control = self.find(name=name, tags=('input', 'textarea', 'select')) or \
                (self.find(labels=labels, tags=('input', 'textarea', 'select')) if labels else None)
            if control:
                return control
            if time.monotonic() > deadline:
                raise AssertionError('visible form field missing: ' + name)
            time.sleep(0.2)
            self.snapshot()

    def fill(self, name, value, labels=()):
        self.call('fill', target={'ref': self.field(name, labels)['ref']}, value=value)

    def check(self, name, value=True, labels=()):
        self.call('check', target={'ref': self.field(name, labels)['ref']}, checked=value)

    def button(self, *names, timeout=3.0, within=None):
        """A visible action control whose accessible name is one of names (badge counters allowed)."""
        patterns = [action_pattern(n) for n in names]
        deadline = time.monotonic() + timeout
        self.snapshot()
        def rank(control):
            """Buttons before links and menu entries (a page header may repeat a form's action as a link)."""
            if control['tag'] == 'button' or control.get('type') in ('submit', 'button') or control.get('role') == 'button':
                return 0
            if control['tag'] in ('a', 'summary') or control.get('role') in ('link', 'menuitem', 'option', 'tab'):
                return 1
            return None
        while True:
            for pattern in patterns:
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

    def submit(self, *names, **kwargs):
        """Click a form submit; the runtime waits for the navigation it starts."""
        before = self.url
        self.click(*names, **kwargs)
        return before

    def sign_in(self, user, password):
        if self.url.split('?')[0] != '/user/login':
            self.goto('/user/login')
        self.fill('user_name', user)
        self.fill('password', password)
        self.submit('Sign In')
        self.wait(lambda s: not s['url'].startswith('/user/login'), 'sign-in did not complete')

    def editor(self, text):
        """Replace the content of the code editor (Monaco exposes an accessible textbox)."""
        control = self.wait(lambda s: next((c for c in s['controls'] if c['tag'] == 'textarea' and any(
            re.search(r'Editor content|File content|^Content$|^Code$', n, re.I) for n in accessible(c))), None),
            'visible code editor textbox missing')
        target = {'ref': control['ref']}
        self.call('press', target=target, key='ControlOrMeta+a')
        self.call('press', key='Backspace')
        self.call('type', value=text)
