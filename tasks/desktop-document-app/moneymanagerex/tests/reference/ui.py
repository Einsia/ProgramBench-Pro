"""Desktop helpers for the pinned standard answer, on top of the runtime's GUI operations.

Controls are located through the accessibility tree: dialogs by title, fields by the label beside them, buttons by name.
The navigator tree and the transaction lists are drawn by the toolkit and have no accessible children, so they are
operated by screen position. These routes belong to the pinned standard only; they are never a candidate requirement.
"""
import time

DIALOG_ROLES = ('frame', 'dialog', 'alert', 'file chooser', 'window')
FIELD_ROLES = ('text', 'combo box', 'spin button', 'push button', 'toggle button', 'check box')
SECOND = 1.0


class UIError(AssertionError):
    """The recipe could not find what it expected on the pinned standard answer."""


class UI:
    def __init__(self, broker):
        self.broker = broker

    def call(self, request):
        """One runtime request; a dialog that has just been centered is observed once more."""
        for attempt in range(6):
            try:
                return self.broker.call(request)
            except Exception as exc:
                if 'has just been centered' not in str(exc) or attempt == 5:
                    raise
                time.sleep(.2)
                self.broker.call({'op': 'observe'})
                if 'target' in request and isinstance(request['target'], str):
                    raise UIError('stale control after a dialog moved') from None

    # Observation ---------------------------------------------------------------------------------------------
    def tree(self):
        return self.call({'op': 'observe', 'tree': True})

    def window_titles(self):
        return [w['title'] for w in self.call({'op': 'windows'})['windows']]

    def wait(self, seconds=.3):
        time.sleep(seconds)

    def top_window(self, observation=None):
        """Title of the active window."""
        observation = observation or self.tree()
        for window in observation.get('windows', ()):
            if window.get('active'):
                return window['title']
        return None

    def wait_window(self, title, timeout=15.0):
        """Wait until a window whose title contains the text is present; returns its Window helper."""
        deadline = time.monotonic() + timeout
        while True:
            observation = self.tree()
            for node in observation['nodes']:
                if node['role'] in DIALOG_ROLES and title in node['name'] and node.get('depth', 0) <= 1:
                    return self.stable_window(node['name'], node['bounds'])
            if time.monotonic() > deadline:
                names = [n['name'] for n in observation['nodes'] if n['role'] in DIALOG_ROLES]
                raise UIError(f'window {title!r} did not appear; windows: {names}')
            time.sleep(.15)

    def stable_window(self, name, bounds, role=None):
        """The toolkit sizes a new dialog after mapping it and the runtime then centers it: wait for its final place."""
        last, stable = bounds, 0
        for _ in range(20):
            time.sleep(.15)
            now = next((n['bounds'] for n in self.tree()['nodes'] if n['name'] == name and n['role'] in DIALOG_ROLES and n.get('depth', 0) <= 1), None)
            if now == last:
                stable += 1
                if stable >= 2:
                    break
            else:
                last, stable = now, 0
        return Window(self, name, role=role)

    def wait_gone(self, title, timeout=15.0):
        deadline = time.monotonic() + timeout
        while any(title in name for name in self.window_titles()):
            if time.monotonic() > deadline:
                raise UIError(f'window {title!r} did not close')
            time.sleep(.15)

    def wait_alert(self, timeout=10.0):
        deadline = time.monotonic() + timeout
        while True:
            observation = self.tree()
            for node in observation['nodes']:
                if node['role'] == 'alert':
                    return self.stable_window(node['name'], node['bounds'], role='alert')
            if time.monotonic() > deadline:
                raise UIError('no message box appeared')
            time.sleep(.15)

    def has_alert(self):
        return any(n['role'] == 'alert' for n in self.tree()['nodes'])

    def alert_text(self):
        observation = self.tree()
        return [n['name'] for n in observation['nodes'] if n['role'] == 'label' and
                any(a['role'] == 'alert' for a in self._lineage(observation['nodes'], n))]

    @staticmethod
    def _lineage(nodes, node):
        by_ref = {n['ref']: n for n in nodes}
        chain = [node]
        while chain[-1].get('parent') in by_ref:
            chain.append(by_ref[chain[-1]['parent']])
        return chain

    def settle(self, timeout=8.0, quiet=1.0):
        """Until the accessibility snapshot stops changing."""
        import json
        deadline = time.monotonic() + timeout
        last, since = None, time.monotonic()
        while time.monotonic() < deadline:
            key = json.dumps(self.call({'op': 'observe'}), sort_keys=True)
            now = time.monotonic()
            if key != last:
                last, since = key, now
            elif now - since >= quiet:
                return
            time.sleep(.2)

    def park(self):
        """Rest the pointer on the status bar, so no hover tooltip or highlight depends on timing."""
        self.call({'op': 'move', 'x': 640, 'y': 893, 'seconds': .1})

    # Input ---------------------------------------------------------------------------------------------------
    def click(self, x, y, button=None, count=None, modifiers=None):
        request = {'op': 'click', 'x': x, 'y': y}
        if button:
            request['button'] = button
        if count:
            request['click_count'] = count
        if modifiers:
            request['modifiers'] = list(modifiers)
        return self.call(request)

    def press(self, key):
        return self.call({'op': 'press', 'key': key})

    def type(self, value):
        return self.call({'op': 'type', 'value': value})

    def menu(self, *path):
        """Open a menu path by name, for example menu('Tools', 'Database', 'Optimize Database…')."""
        self.call({'op': 'click', 'target': {'role': 'menu', 'name': path[0]}})
        time.sleep(.3)
        for name in path[1:-1]:
            self.call({'op': 'click', 'target': {'role': 'menu', 'name': name}})
            time.sleep(.15)
            self.press('Right')
            time.sleep(.3)
        self.click_menu_item(path[-1])

    def click_menu_item(self, name, timeout=5.0):
        deadline = time.monotonic() + timeout
        while True:
            for node in self.tree()['nodes']:
                if node['role'] in ('menu item', 'check menu item', 'radio menu item') and node['name'].strip() == name.strip():
                    return self.call({'op': 'click', 'target': node['ref']})
            if time.monotonic() > deadline:
                raise UIError(f'menu item {name!r} is not shown')
            time.sleep(.15)

    def context_menu(self, x, y, *path):
        self.click(x, y, button='right')
        time.sleep(.3)
        for name in path[:-1]:
            self.call({'op': 'click', 'target': {'role': 'menu', 'name': name}})
            time.sleep(.15)
            self.press('Right')
            time.sleep(.3)
        self.click_menu_item(path[-1])

    def file_dialog(self, path, title=None, timeout=15.0):
        """Answer the open file dialog with a full path."""
        deadline = time.monotonic() + timeout
        while True:
            observation = self.tree()
            choosers = [n for n in observation['nodes'] if n['role'] == 'file chooser' and n.get('depth', 0) <= 1]
            if choosers:
                break
            if time.monotonic() > deadline:
                raise UIError('no file dialog appeared')
            time.sleep(.15)
        entries = [n for n in observation['nodes'] if n['role'] == 'text' and 'editable' in n.get('states', ())
                   and any(a['role'] == 'file chooser' for a in self._lineage(observation['nodes'], n))]
        if not entries:
            self.press('Control+l')
            time.sleep(.3)
            observation = self.tree()
            entries = [n for n in observation['nodes'] if n['role'] == 'text' and 'editable' in n.get('states', ())
                       and any(a['role'] == 'file chooser' for a in self._lineage(observation['nodes'], n))]
        self.call({'op': 'fill', 'target': entries[0]['ref'], 'value': path})
        time.sleep(.2)
        self.press('Return')
        time.sleep(.5)


class Window:
    """One top-level window of the product, by its title."""

    def __init__(self, ui, title, role=None):
        self.ui, self.title, self.role = ui, title, role

    def nodes(self):
        observation = self.ui.tree()
        roots = [n for n in observation['nodes'] if n['name'] == self.title and n['role'] in DIALOG_ROLES and n.get('depth', 0) <= 1
                 and (self.role is None or n['role'] == self.role)]
        if not roots:
            raise UIError(f'window {self.title!r} is not open')
        root = roots[-1]
        inside = {root['ref']}
        result = []
        for node in observation['nodes']:
            if node.get('parent') in inside:
                inside.add(node['ref'])
                result.append(node)
        return result

    def find(self, role=None, name=None, nth=0, text=None):
        found = [n for n in self.nodes() if (role is None or n['role'] == role) and (name is None or n['name'] == name)
                 and (text is None or text in (n.get('text') or ''))]
        if nth >= len(found):
            raise UIError(f'{self.title}: no {role} named {name!r} (nth {nth}); have ' +
                          str([(n['role'], n['name']) for n in self.nodes() if n['name']][:40]))
        return found[nth]

    def button(self, name, nth=0):
        return self.ui.call({'op': 'click', 'target': self.find('push button', name, nth)['ref']})

    def check(self, name, value=True, nth=0):
        return self.ui.call({'op': 'check', 'target': self.find('check box', name, nth)['ref'], 'checked': bool(value)})

    def toggle(self, name):
        return self.ui.call({'op': 'click', 'target': self.find(None, name)['ref']})

    def radio(self, name):
        return self.ui.call({'op': 'click', 'target': self.find('radio button', name)['ref']})

    def tab(self, name):
        node = self.find('page tab', name)
        result = self.ui.call({'op': 'click', 'target': node['ref']})
        time.sleep(.3)
        return result

    def field(self, label, roles=('text',), nth_label=0, below=False):
        """The control beside (or below) a label."""
        nodes = self.nodes()
        labels = [n for n in nodes if n['role'] in ('label', 'check box') and n['name'].strip().rstrip(':').casefold() == label.strip().rstrip(':').casefold()]
        if nth_label >= len(labels):
            raise UIError(f'{self.title}: no label {label!r}; have ' + str([n['name'] for n in nodes if n['role'] == 'label'][:40]))
        x, y, w, h = labels[nth_label]['bounds']
        middle = y + h / 2
        candidates = []
        for node in nodes:
            if node['role'] not in roles or node['bounds'][2] <= 0:
                continue
            nx, ny, nw, nh = node['bounds']
            if not below and ny - 6 <= middle <= ny + nh + 6 and nx >= x + w - 4:
                candidates.append((nx - x - w, node))
            elif below and ny >= y + h - 4 and nx + nw >= x:
                candidates.append((ny - y - h + abs(nx - x), node))
        if not candidates:
            raise UIError(f'{self.title}: no {roles} beside label {label!r}')
        return min(candidates, key=lambda item: item[0])[1]

    def fill(self, label, value, below=False, commit=False):
        node = self.field(label, below=below)
        result = self.ui.call({'op': 'fill', 'target': node['ref'], 'value': str(value)})
        if commit:
            self.ui.press('Tab')
        return result

    def choose(self, label, value, below=False):
        """Pick an item of the drop-down list beside a label."""
        node = self.field(label, roles=('combo box',), below=below)
        return self.pick(node, value)

    def pick(self, combo, value):
        self.ui.call({'op': 'click', 'target': combo['ref']})
        deadline = time.monotonic() + 15
        searched_top = False
        while True:
            for node in self.ui.tree()['nodes']:
                if node['role'] == 'menu item' and node['name'] == value:
                    self.ui.call({'op': 'click', 'target': node['ref']})
                    time.sleep(.25)
                    return
            if not searched_top:
                self.ui.press('Home')
                searched_top = True
            else:
                self.ui.press('Down')
            if time.monotonic() > deadline:
                self.ui.press('Escape')
                raise UIError(f'{self.title}: no list item {value!r}')
            time.sleep(.15)

    def close(self, button='OK', timeout=15.0):
        before = self.ui.window_titles().count(self.title)
        self.button(button)
        deadline = time.monotonic() + timeout
        while self.ui.window_titles().count(self.title) >= before:
            if time.monotonic() > deadline:
                raise UIError(f'window {self.title!r} did not close')
            time.sleep(.15)
