"""Visible-control helpers over the same runtime operations exposed to the evaluator."""
import re
import time


def plain(text):
    return re.split(r'\s+(?:Ctrl|Alt|Shift)\+', text or '')[0].rstrip('.\u2026 ').casefold()


class UI:
    def __init__(self, broker):
        self.broker = broker

    def call(self, op, **kwargs):
        result = self.broker.call({'op': op, **kwargs})
        assert 'error' not in result, str(result)
        return result

    def observe(self):
        return self.call('observe', tree=True)

    def find(self, name=None, role=None, *, exact=True, timeout=15, nth=0):
        deadline = time.monotonic() + timeout
        while True:
            nodes = self.observe()['nodes']
            found = [n for n in nodes if (role is None or n['role'] in ([role] if isinstance(role, str) else role))
                     and (name is None or any(plain(value) == plain(name) if exact else plain(name) in plain(value)
                                              for value in ((n['name'],) if name == '' else (n['name'], n.get('text','')))))]
            if len(found) > nth:
                return found[nth]
            if time.monotonic() >= deadline:
                raise AssertionError('no visible control: ' + repr((name, role)))
            time.sleep(.2)

    def click(self, name=None, role=None, *, exact=True, button='left', nth=0):
        node = self.find(name, role, exact=exact, nth=nth)
        return self.call('click', target=node['ref'], button=button)

    def fill(self, name, value, *, role='entry', exact=True, nth=0):
        node = self.find(name, role, exact=exact, nth=nth)
        return self.call('fill', target=node['ref'], value=value)

    def press(self, key):
        return self.call('press', key=key)

    def menu(self, *names):
        self.click(names[0], 'push button')
        for index, name in enumerate(names[1:]):
            node = self.find(name, ('menu item', 'check menu item', 'radio menu item'), exact=True)
            if index < len(names) - 2:
                self.call('move', target=node['ref'], seconds=.5)
            else:
                self.call('click', target=node['ref'])

    def context(self, target, *names, role='list item'):
        self.click(target, role, exact=False, button='right')
        for index, name in enumerate(names):
            node = self.find(name, ('menu item', 'check menu item', 'radio menu item'))
            self.call('move' if index < len(names)-1 else 'click', target=node['ref'])

    def notebook(self, title):
        self.click(title, 'link', exact=False)

    def note(self, title):
        self.click('Workbench', 'link', exact=False)
        self.click(title, 'list item', exact=False)
        self.find('Note title', 'entry')
        self.notice()

    def notice(self):
        nodes = self.observe()['nodes']
        for node in nodes:
            if node['role'] == 'link' and 'keep it enabled' in node['name'].casefold():
                self.call('click', target=node['ref'])
                break

    def create_note(self, title, body, todo=False):
        self.press('Control+T' if todo else 'Control+N')
        self.notice()
        self.fill('Markdown editor', body)
        self.fill('Note title', title)

    def file(self, path, *, save=False, directory=False):
        self.find(role='file chooser', timeout=20)
        if directory:
            leaf=path.rstrip('/').split('/')[-1]
            nodes=self.observe()['nodes']
            folder=next((n for n in nodes if n['role']=='table cell' and n['name']==leaf),None)
            crumb=next((n for n in nodes if n['role']=='toggle button' and n['name']==leaf),None)
            if folder or crumb:
                self.call('click',target=(folder or crumb)['ref'])
                self.click('Select','push button')
                end=time.monotonic()+20
                while time.monotonic()<end:
                    if not any(n['role']=='file chooser' for n in self.observe()['nodes']):return
                    time.sleep(.2)
                raise AssertionError('the selected directory was not confirmed')
        if save:
            self.fill(None, path, role=('text','entry'))
        else:
            self.press('Control+L')
            self.call('type', value=path)
        self.call('wait', seconds=.5)
        self.press('Return')
        end=time.monotonic()+30
        while time.monotonic()<end:
            nodes=self.observe()['nodes']
            if not any(n['role']=='file chooser' for n in nodes):return
            if directory:
                button=next((n for n in nodes if n['role']=='push button' and n['name'] in ('Select','Open')
                             and 'disabled' not in n.get('states',())),None)
                if button:self.call('click',target=button['ref'])
                else:self.press('Return')
            time.sleep(.4)
        raise AssertionError('the document chooser did not finish')

    def settle(self, seconds=.7):
        self.call('move', x=1274, y=892, seconds=.1)
        self.call('wait', seconds=seconds)

    def visible(self, text, *, role=None):
        self.find(text, role, exact=False)
