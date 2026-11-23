'''Pinned-standard browser driving through the black-box runtime's GUI operations (record only).

Controls are found in a fresh snapshot of the runtime and operated by reference, exactly as the model and the evaluator
can. Every operation returns a new snapshot and renews the control references: a reference of an older snapshot is
refused, so each lookup takes a snapshot first. Names, labels and routes belong to the pinned standard; they are never a
candidate requirement.
'''
import re
import time

from evaluation.broker import BrokerError

SESSION = {'session': 'main'}
WAIT = 8.0
# A neutral spot of the page behind a dialog: clicking it moves the focus out of a form that saves when it loses it.
OUTSIDE = (400, 110)


def accessible(control):
    '''The names a user would know a control by.'''
    return [x for x in (control.get('aria'), control.get('label'), control.get('text'), control.get('title'),
                        control.get('placeholder')) if x]


def action_pattern(name):
    # A numeric badge may follow an action name; never another word.
    return re.compile(r'^' + re.escape(name) + r'(?:\s+(?:\d+|\(\d+\)))?\s*$', re.I)


def same(value, wanted):
    return isinstance(value, str) and value.strip().lower() == wanted.lower()


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
        '''Open a page; when the page is navigating itself, let that finish and open again.'''
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
        return self.snapshot()['url']

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
    @staticmethod
    def match(snap, tag=None, type=None, name=None, label=None, aria=None, prefix=None, placeholder=None, text=None,
              role=None, href=None, title=None, enabled=False, nth=0, has=None):
        '''The nth control of a snapshot that has all the given properties (text allows a badge counter after it).'''
        found = []
        for c in snap['controls']:
            if title is not None and not same(c.get('title'),title):
                continue
            if tag and c.get('tag') != tag:
                continue
            if type and c.get('type') != type:
                continue
            if role and c.get('role') != role:
                continue
            if name is not None and c.get('name') != name:
                continue
            if label is not None and not same(c.get('label'), label):
                continue
            if aria is not None and not same(c.get('aria'), aria):
                continue
            if prefix is not None and not (c.get('aria') or '').lower().startswith(prefix.lower()):
                continue
            if placeholder is not None and placeholder.lower() not in (c.get('placeholder') or '').lower():
                continue
            if text is not None and not action_pattern(text).search((c.get('text') or '').strip()):
                continue
            if href is not None and c.get('href') != href:
                continue
            if has is not None and has not in (c.get('text') or ''):
                continue
            if enabled and c.get('disabled'):
                continue
            found.append(c)
        try:
            return found[nth]
        except IndexError:
            return None

    def control(self, timeout=3.0, **criteria):
        deadline = time.monotonic() + timeout
        while True:
            found = self.match(self.snapshot(), **criteria)
            if found:
                return found
            if time.monotonic() > deadline:
                raise AssertionError('visible control missing: ' + str(criteria))
            time.sleep(0.2)

    def act(self, op, criteria, **fields):
        control = self.control(**criteria)
        self.call(op, target={'ref': control['ref']}, **fields)
        return control

    # -- operating controls ----------------------------------------------------------------------------------------
    def fill(self, value, **criteria):
        self.act('fill', criteria, value=value)

    def click(self, **criteria):
        return self.act('click', criteria)

    def press(self, key, **criteria):
        '''A key on the named control, or on whatever has the focus when no control is named.'''
        if criteria:
            self.act('press', criteria, key=key)
        else:
            self.call('press', key=key)

    def type_text(self, value):
        self.call('type', value=value)

    def select(self, value, **criteria):
        self.act('select', criteria, value=value)

    def tick(self, wanted, **criteria):
        '''Set a checkbox. Several checkboxes of the page have no size of their own: they are operated by the space key.'''
        control = self.control(**criteria)
        if bool(control.get('checked')) != wanted:
            self.call('check', target={'ref':control['ref']}, checked=wanted)

    def button(self, *names, timeout=3.0, index=0):
        '''A visible enabled action whose accessible name is one of names; buttons rank before links.'''
        patterns = [action_pattern(n) for n in names]
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snapshot()
            for pattern in patterns:
                matches = [c for c in snap['controls'] if c.get('tag') in ('button', 'a') and not c.get('disabled')
                           and any(pattern.search(n.strip()) for n in accessible(c))]
                matches.sort(key=lambda c: 0 if c['tag'] == 'button' else 1)
                if len(matches) > index:
                    return matches[index]
            if time.monotonic() > deadline:
                raise AssertionError('visible action missing: ' + str(names))
            time.sleep(0.2)

    def click_button(self, *names, **kwargs):
        control = self.button(*names, **kwargs)
        self.call('click', target={'ref': control['ref']})
        return control

    def editor(self, value, **criteria):
        '''Replace the content of a rich text editor (an editable block, not a form field).'''
        # Every operation renews the control references: look the editor up again before each step.
        self.click(**criteria)
        self.press('ControlOrMeta+a', **criteria)
        self.type_text(value)

    def choose(self, value, arrow=True, **criteria):
        '''Type into a search box and take its first suggestion with the keyboard.'''
        self.fill(value, **criteria)
        # Some search boxes expose their suggestions as options and others do not: give the search time to answer.
        time.sleep(1.5)
        if arrow:
            self.press('ArrowDown', **criteria)
        self.press('Enter', **criteria)

    def blur(self):
        '''Move the focus out of a form that saves its values when it loses it.'''
        self.call('pointer', action='click', x=OUTSIDE[0], y=OUTSIDE[1])

    def sign_in(self, user, password):
        self.goto('/login')
        # The reference schedules username focus after 500 ms. Wait for that
        # ordinary UI initialization before filling either field.
        self.call('wait', seconds=.75)
        self.fill(user, name='username')
        self.wait(lambda snap: self.match(snap,name='username').get('value')==user, 'username was not retained')
        self.fill(password, label='Password')
        self.click_button('OK')
        self.wait(lambda s: not s['url'].startswith('/login'), 'sign-in did not complete')
