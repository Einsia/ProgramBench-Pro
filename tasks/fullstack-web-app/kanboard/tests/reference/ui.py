"""Pinned-standard browser driving through the black-box runtime's GUI operations (record only).

Controls are found in the runtime's own snapshot (form field names, labels, accessible names) and operated by ref,
exactly as the model and the evaluator can. Names and form fields belong to the pinned standard; they are never a
candidate requirement.
"""
import re
import time

from evaluation.broker import BrokerError

SESSION = {'session': 'main'}
WAIT = 10.0


def accessible(control):
    """The names a user (or a locator) would know a control by."""
    return [x for x in (control.get('aria'), control.get('label'), control.get('text'), control.get('title'),
                        control.get('placeholder'), control.get('value') if control.get('type') in ('submit', 'button')
                        else None) if x]


def exact(name):
    return re.compile(r'^\s*' + re.escape(name) + r'\s*$', re.I)


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
            time.sleep(0.25)

    def require(self, *texts, timeout=WAIT):
        for text in texts:
            self.wait(lambda s, t=text: t in s['text'], 'visible text absent: ' + repr(text), timeout)

    def absent(self, *texts, timeout=WAIT):
        for text in texts:
            self.wait(lambda s, t=text: t not in s['text'], 'text still visible: ' + repr(text), timeout)

    # -- finding controls ------------------------------------------------------------------------------------------
    def controls(self, predicate=None, onscreen=False):
        snap = self.snap or self.snapshot()
        return [c for c in snap['controls'] if (predicate is None or predicate(c))
                and not (onscreen and c.get('offscreen'))]

    def field(self, name, timeout=5.0, nth=0):
        """A form field by its name attribute (the last matching one: a modal form is appended to the page)."""
        deadline = time.monotonic() + timeout
        while True:
            matches = [c for c in self.snapshot()['controls'] if c.get('name') == name
                       and c['tag'] in ('input', 'textarea', 'select')]
            if matches:
                return matches[-1 - nth]
            if time.monotonic() > deadline:
                raise AssertionError('visible form field missing: ' + name)
            time.sleep(0.25)

    def fill(self, name, value):
        self.call('fill', target={'ref': self.field(name)['ref']}, value=value)

    def select(self, name, value):
        self.call('select', target={'ref': self.field(name)['ref']}, value=value)

    def check(self, name, value=True):
        self.call('check', target={'ref': self.field(name)['ref']}, checked=value)

    def control(self, *names, tags=None, timeout=5.0, last=False):
        """A visible control whose accessible name is exactly one of names."""
        patterns = [exact(n) for n in names]
        deadline = time.monotonic() + timeout
        self.snapshot()
        while True:
            for pattern in patterns:
                matches = [c for c in self.snap['controls'] if not c.get('disabled')
                           and (tags is None or c['tag'] in tags)
                           and any(pattern.search(n) for n in accessible(c))]
                if matches:
                    return matches[-1] if last else matches[0]
            if time.monotonic() > deadline:
                raise AssertionError('visible control missing: ' + str(names) + ' at ' + self.snap['url'])
            time.sleep(0.25)
            self.snapshot()

    def click(self, *names, tags=None, last=False, timeout=5.0):
        control = self.control(*names, tags=tags, last=last, timeout=timeout)
        self.call('click', target={'ref': control['ref']})
        return control

    def click_ref(self, control):
        self.call('click', target={'ref': control['ref']})

    def link(self, href_pattern, timeout=5.0):
        """A visible link whose target matches the pattern."""
        pattern = re.compile(href_pattern)
        deadline = time.monotonic() + timeout
        while True:
            matches = [c for c in self.snapshot()['controls'] if c['tag'] == 'a' and pattern.search(c.get('href') or '')]
            if matches:
                return matches[0]
            if time.monotonic() > deadline:
                raise AssertionError('link missing: ' + href_pattern)
            time.sleep(0.25)

    def save(self, *names):
        """Submit the open form (the modal's or the page's) with its Save-like button and let the page settle."""
        control = self.control(*(names or ('Save',)), tags=('button', 'input'), last=True)
        self.call('click', target={'ref': control['ref']})
        self.call('wait', seconds=1)

    def modal_closed(self, timeout=WAIT):
        self.wait(lambda s: not any(c.get('name') in ('csrf_token',) for c in s['controls']), 'form still open',
                  timeout)

    def sign_in(self, user, password):
        if self.url.split('?')[0] != '/login':
            self.goto('/login')
        self.fill('username', user)
        self.fill('password', password)
        self.click('Sign in', tags=('button',))
        self.wait(lambda s: s['url'].split('?')[0] != '/login', 'sign-in did not complete')
