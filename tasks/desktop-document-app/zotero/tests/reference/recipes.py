"""Pinned-standard GUI implementation of the reviewed functional goals, through the black-box runtime.

Recipes drive only the installed standard answer during record, with the same
runtime GUI operations that the evaluator and the model use (observe, click,
fill, type, press, drag, scroll, wait, windows, focus_window). Controls are
found by their accessible role and name in fresh observations; an operation on
a control that is not shown yet is retried until it appears. The routes and
controls belong to the pinned standard only; they are never a candidate
requirement.
"""
import time

from evaluation.broker import BrokerError

WAIT = 10.0
ENTRIES = ('menu item', 'check menu item', 'radio menu item')


class Recipe:
    def __init__(self, ctx, checkpoint):
        self.ctx = ctx
        self.checkpoint = checkpoint
        self.folders = {}

    # Runtime operations ----------------------------------------------------------------------------------------
    def call(self, request, timeout=None):
        return self.ctx.broker.call(request, **({'timeout': timeout} if timeout else {}))

    def retry(self, request, seconds=WAIT, settle=0.25):
        """Send a GUI operation (or the one a function builds), retrying while its target is not shown yet."""
        deadline = time.monotonic() + seconds
        while True:
            try:
                result = self.call(request() if callable(request) else request)
                time.sleep(settle)
                return result
            except BrokerError as exc:
                if time.monotonic() >= deadline or exc.error == 'Refused':
                    raise AssertionError(f'{request} failed: {exc.error}: {exc.detail}') from None
                time.sleep(0.3)

    def nodes(self):
        return self.call({'op': 'observe', 'tree': True})['nodes']

    def windows(self):
        return self.call({'op': 'windows'})['windows']

    def wait_window(self, title, seconds=WAIT, present=True):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            found = [w for w in self.windows() if (w['title'] == title or w['title'].startswith(title))]
            if bool(found) == present:
                return found[0] if found else None
            time.sleep(0.25)
        raise AssertionError(f'window {title!r} did not {"appear" if present else "close"}')

    def wait_node(self, predicate, seconds=WAIT, message='expected control did not appear'):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            for node in self.nodes():
                if predicate(node):
                    return node
            time.sleep(0.25)
        raise AssertionError(message)

    # Paths ---------------------------------------------------------------------------------------------------
    def folder(self, area):
        if area not in self.folders:
            listed = self.call({'op': 'list_files', 'area': area})
            paths = [f['path'] for f in listed.get('files', []) if not f.get('read_only')]
            if paths:
                self.folders[area] = paths[0].rsplit('/', 1)[0]
            else:
                help_notes = ' '.join(self.call({'op': 'help'}).get('notes', []))
                marker = f'{area} '
                start = help_notes.index(marker) + len(marker)
                self.folders[area] = help_notes[start:].split()[0].rstrip(',')
        return self.folders[area]

    def path(self, value):
        area, _, name = value.partition('/')
        return f'{self.folder(area)}/{name}'

    # Steps ---------------------------------------------------------------------------------------------------
    def row(self, tree, title):
        """A row of the main window's Collections or Items tree: the first whose name is the title, or starts with
        it (item rows are named 'Title. Item Type. Creators'), or contains it."""
        deadline = time.monotonic() + WAIT
        while True:
            nodes = self.nodes()
            by_ref = {n['ref']: n for n in nodes}
            rows = []
            for node in nodes:
                if node['role'] != 'tree item':
                    continue
                parent = by_ref.get(node.get('parent'))
                while parent is not None and parent['role'] != 'tree':
                    parent = by_ref.get(parent.get('parent'))
                if parent is not None and parent.get('name') == tree:
                    rows.append(node)
            for test in (lambda name: name == title, lambda name: name.startswith(title + '.'),
                         lambda name: name.startswith(title), lambda name: title in name):
                found = next((n for n in rows if test(n.get('name') or '')), None)
                if found is not None:
                    return found
            if time.monotonic() >= deadline:
                raise AssertionError(f'the {tree} tree shows no row {title!r}')
            time.sleep(0.3)

    def target(self, target):
        """A broker target; {'item': title} and {'collection': name} stand for rows of the main window's trees."""
        if isinstance(target, dict) and set(target) == {'item'}:
            return lambda: self.row('Items', target['item'])['ref']
        if isinstance(target, dict) and set(target) == {'collection'}:
            return lambda: self.row('Collections', target['collection'])['ref']
        return lambda: target

    def click(self, target, **extra):
        resolve = self.target(target)
        return self.retry(lambda: dict({'op': 'click', 'target': resolve()}, **extra))

    def entry(self, label, roles, parent=None):
        """An entry of an open menu (a plain, check or radio item, or a submenu), below the menu named parent.
        Gecko keeps the entries of closed menus in the accessibility tree; entries of the open menu come first."""
        deadline = time.monotonic() + WAIT
        while True:
            nodes = self.nodes()
            by_ref = {n['ref']: n for n in nodes}
            found = []
            for node in nodes:
                if node['role'] not in roles or node.get('name') != label:
                    continue
                menu = by_ref.get(node.get('parent'))
                while menu is not None and menu['role'] != 'menu':
                    menu = by_ref.get(menu.get('parent'))
                if parent is not None and (menu is None or menu.get('name') != parent):
                    continue
                states = set(menu.get('states', ())) if menu else set()
                found.append((not (states & {'expanded', 'focused'} or menu is not None and not menu.get('name')),
                              node))
            if found:
                found.sort(key=lambda pair: pair[0])
                return found[0][1]
            if time.monotonic() >= deadline:
                raise AssertionError(f'menu entry {label!r} is not shown')
            time.sleep(0.3)

    def menu(self, labels):
        """Open a menu bar menu and follow its submenu path."""
        first, *rest = labels
        self.click({'role': 'menu', 'name': first})
        parent = first
        for label in rest[:-1]:
            self.click(self.entry(label, ('menu',), parent)['ref'])
            parent = label
        if rest:
            self.click(self.entry(rest[-1], ENTRIES, parent)['ref'])

    def context(self, target, labels):
        """Right-click a control and follow the context menu path."""
        self.click(target, button='right')
        parent = None
        for label in labels[:-1]:
            self.click(self.entry(label, ('menu',), parent)['ref'])
            parent = label
        self.click(self.entry(labels[-1], ENTRIES, parent)['ref'])

    def library(self):
        self.collection('My Library')

    def collection(self, name):
        self.click({'collection': name})
        time.sleep(0.5)

    def item(self, title, **extra):
        self.click({'item': title}, **extra)
        time.sleep(0.4)

    def field(self, label, value, commit='Return'):
        """Edit one field of the item pane: click it, replace its text, commit."""
        self.click({'role': 'entry', 'name': label})
        self.retry({'op': 'press', 'key': 'Control+a'})
        if value:
            self.retry({'op': 'type', 'value': value})
        else:
            self.retry({'op': 'press', 'key': 'BackSpace'})
        if commit:
            self.retry({'op': 'press', 'key': commit})
        time.sleep(0.4)

    def type(self, value):
        self.retry({'op': 'type', 'value': value})

    def show_field(self, name):
        """Leave the observed field visible without changing it."""
        self.retry({'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': -5000})
        for _ in range(25):
            found = [n for n in self.nodes() if n['role'] == 'entry' and n.get('name') == name]
            if any(130 < n.get('bounds', [0, 0, 0, 0])[1] < 780 for n in found):
                return
            self.retry({'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': 160})
        raise AssertionError(f'field {name!r} did not become visible')

    def key(self, key, times=1):
        for _ in range(times):
            self.retry({'op': 'press', 'key': key})

    def file_open(self, value):
        """Answer an Open file dialog with a path in the exchange folders."""
        self.wait_node(lambda n: n['role'] == 'file chooser')
        self.key('Control+l')
        self.type(self.path(value))
        self.key('Return')
        time.sleep(1.0)

    def file_save(self, value):
        """Answer a Save file dialog with a full path in the outbox."""
        deadline = time.monotonic() + WAIT
        node = None
        while node is None:
            nodes = self.nodes()
            choosers = {n['ref'] for n in nodes if n['role'] == 'file chooser'}
            node = next((n for n in nodes if n['role'] == 'text' and 'editable' in n.get('states', ())
                         and n.get('window') in choosers), None)
            if node is None:
                if time.monotonic() > deadline:
                    raise AssertionError('the Save dialog\'s name field did not appear')
                time.sleep(0.3)
        self.retry({'op': 'fill', 'target': node['ref'], 'value': self.path(value)})
        self.key('Return')
        time.sleep(1.0)

    def window_ref(self, title, seconds=WAIT):
        """Ref (in the latest observation) of a top-level window whose title starts with title."""
        deadline = time.monotonic() + seconds
        while True:
            for node in self.nodes():
                if node.get('depth') == 1 and (node.get('name') or '').startswith(title):
                    return node['ref']
            if time.monotonic() > deadline:
                raise AssertionError(f'window {title!r} did not appear')
            time.sleep(0.3)

    def confirm(self, button, seconds=WAIT):
        """Answer the confirmation dialog that opens: click its button."""
        if not self.confirm_if(button, seconds):
            raise AssertionError(f'no dialog with the button {button!r} opened')

    def confirm_if(self, button, seconds=3.0):
        """Answer a confirmation dialog if one opens: click its button."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            nodes = self.nodes()
            dialogs = [n for n in nodes if n.get('depth') == 1 and n['role'] in ('dialog', 'alert')
                       or (n.get('depth') == 1 and 'modal' in n.get('states', ()))]
            for dialog in dialogs:
                if any(n['role'] == 'push button' and n.get('name') == button and n.get('window') == dialog['ref']
                       for n in nodes):
                    self.click({'role': 'push button', 'name': button, 'within': dialog['ref']})
                    time.sleep(0.6)
                    return True
            time.sleep(0.3)
        return False

    def pane_row(self, header_suffix, role='push button', name=None):
        """A control on the row of an item pane section header (for example the Add button of 'N Related')."""
        self.retry({'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': 2500})
        time.sleep(0.6)
        nodes = self.nodes()
        header = next((n for n in nodes if n['role'] == 'push button' and n['bounds'][0] > 900
                       and (n.get('name') or '').endswith(header_suffix)), None)
        if header is None:
            raise AssertionError(f'item pane section {header_suffix!r} is not shown')
        y = header['bounds'][1]
        control = next((n for n in nodes if n['role'] == role and (name is None or n.get('name') == name)
                        and abs(n['bounds'][1] - y) <= 4 and n['bounds'][0] > header['bounds'][0] + 100), None)
        if control is None:
            raise AssertionError(f'no {name or role} on the {header_suffix!r} row')
        return control

    def section_add(self, section):
        control = self.pane_row(section, name='Add')
        self.click(control['ref'])
        time.sleep(1.0)

    def choose(self, name, role='list item'):
        """Click an entry of a scrolled list, first scrolling the list until the entry lies inside it."""
        for _ in range(30):
            nodes = self.nodes()
            by_ref = {n['ref']: n for n in nodes}
            entry = next((n for n in nodes if n['role'] == role and n.get('name') == name), None)
            if entry is None:
                raise AssertionError(f'the list has no entry {name!r}')
            box = by_ref.get(entry.get('parent'))
            while box is not None and box['role'] not in ('list box', 'list', 'tree', 'tree table'):
                box = by_ref.get(box.get('parent'))
            if box is None:
                raise AssertionError(f'the entry {name!r} is not in a list')
            x, y, w, h = box['bounds']
            top, bottom = entry['bounds'][1], entry['bounds'][1] + entry['bounds'][3]
            if top >= y and bottom <= y + h:
                self.click(entry['ref'])
                return
            self.retry({'op': 'scroll', 'x': x + w // 2, 'y': y + h // 2, 'delta_y': -120 if top < y else 120})
            time.sleep(0.3)
        raise AssertionError(f'the entry {name!r} could not be scrolled into view')

    def select_items(self, title):
        frame = self.window_ref('Select Items')
        self.click({'role': 'tree item', 'text': title, 'within': frame})
        self.click({'role': 'push button', 'name': 'Select', 'within': frame})
        time.sleep(1.0)

    def remove_related(self, title):
        self.retry({'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': 2500})
        time.sleep(0.6)
        nodes = self.nodes()
        row = next(n for n in nodes if n['role'] == 'push button' and n.get('name') == title and n['bounds'][0] > 900)
        self.retry({'op': 'move', 'target': row['ref'], 'seconds': 0.4})
        nodes = self.nodes()
        remove = next(n for n in nodes if n['role'] == 'push button' and n.get('name') == 'Remove'
                      and abs(n['bounds'][1] - row['bounds'][1]) <= 4)
        self.click(remove['ref'])
        time.sleep(1.0)

    def merge_fields(self, values):
        for label, value in values.items():
            self.click({'role': 'push button', 'name': f'Select version of {label} field'})
            self.click({'role': 'menu item', 'name': value})
            time.sleep(0.4)

    def open_child(self, title, child_text):
        """Show a child item of the selected parent: expand the row, then select the child."""
        self.item(title)
        self.key('Right')
        time.sleep(0.5)
        self.item(child_text)
        time.sleep(1.5)

    def note_append(self, text, bold=False):
        paragraphs = [n for n in self.nodes() if n['role'] == 'paragraph' and 'editable' in n.get('states', ())]
        if not paragraphs:
            raise AssertionError('no editable note paragraph is shown')
        self.click(paragraphs[-1]['ref'])
        self.key('Control+End')
        self.key('Return')
        if bold:
            self.key('Control+b')
        self.type(text)
        time.sleep(1.5)

    def remove_tag(self, tag):
        self.retry({'op': 'scroll', 'x': 1080, 'y': 600, 'delta_y': 2500})
        time.sleep(0.6)
        nodes = self.nodes()
        entry = next((n for n in nodes if n['role'] == 'entry' and n.get('name') == 'Tag' and n.get('text') == tag),
                     None)
        if entry is None:
            raise AssertionError(f'the tag {tag!r} is not shown in the item pane')
        self.retry({'op': 'move', 'target': entry['ref'], 'seconds': 0.4})
        nodes = self.nodes()
        remove = next(n for n in nodes if n['role'] == 'push button' and n.get('name') == 'Remove'
                      and abs(n['bounds'][1] - entry['bounds'][1]) <= 4)
        self.click(remove['ref'])
        time.sleep(1.0)

    def on_row(self, nodes, role, name, y):
        return next((n for n in nodes if n['role'] == role and n.get('name') == name
                     and abs(n['bounds'][1] - y) <= 6), None)

    def condition(self, row, condition, operator, value=None, choice=None):
        """Set one row of the advanced search: condition, operator and value (text or a choice)."""
        rows = sorted((n for n in self.nodes() if n['role'] == 'combo box' and n.get('name') == 'Search condition'),
                      key=lambda n: n['bounds'][1])
        y = rows[row]['bounds'][1]
        self.click(rows[row]['ref'])
        self.click({'role': 'menu item', 'name': condition})
        time.sleep(0.6)
        combo = self.on_row(self.nodes(), 'combo box', 'Operator', y)
        self.click(combo['ref'])
        self.click({'role': 'menu item', 'name': operator})
        time.sleep(0.5)
        nodes = self.nodes()
        if value is not None:
            entry = self.on_row(nodes, 'entry', 'Value', y)
            self.click(entry['ref'])
            self.key('Control+a')
            self.type(value)
            self.key('Escape')
        if choice is not None:
            combo = self.on_row(nodes, 'combo box', 'Value', y)
            self.click(combo['ref'])
            self.click({'role': 'menu item', 'name': choice})
        time.sleep(0.5)

    def highlight(self, text):
        """Drag across a sentence shown on the PDF page (with the highlight or underline tool selected); the same
        sentence on pages scrolled out of view is skipped."""
        node = self.wait_node(lambda n: n['role'] == 'section' and (n.get('text') or '').strip() == text
                              and n['bounds'][2] > 0 and 133 <= n['bounds'][1] <= 880 - n['bounds'][3],
                              message=f'the text {text!r} is not shown')
        x, y, w, h = node.get('visible') or node['bounds']
        self.retry({'op': 'drag', 'x': x + 1, 'y': y + h // 2, 'to_x': x + w - 1, 'to_y': y + h // 2, 'seconds': 1.0})
        time.sleep(1.0)

    def sidebar(self):
        """The reader's annotation sidebar is open."""
        if not any(n['role'] == 'page tab' and n.get('name') == 'Show Annotations' for n in self.nodes()):
            self.click({'role': 'push button', 'name': 'Toggle Sidebar'})
            time.sleep(1.0)

    def annotation_comment(self, page, text):
        self.sidebar()
        self.click({'role': 'list item', 'name': page})
        time.sleep(0.6)
        self.click({'role': 'entry', 'name': 'Annotation comment'})
        self.type(text)
        time.sleep(0.6)
        self.key('Escape')
        time.sleep(1.0)

    def sidebar_tab(self, name):
        """A page of the reader's sidebar (Show Thumbnails, Show Annotations, Show Outline)."""
        if not any(n['role'] == 'page tab' and n.get('name') == name for n in self.nodes()):
            self.click({'role': 'push button', 'name': 'Toggle Sidebar'})
            time.sleep(1.0)
        self.click({'role': 'page tab', 'name': name})
        time.sleep(1.0)

    def annotation_menu(self, page, entry):
        """Choose an entry of the menu of the (only) annotation on a page in the reader's annotation list."""
        self.sidebar()
        self.click({'role': 'list item', 'name': page})
        time.sleep(0.6)
        card = self.wait_node(lambda n: n['role'] == 'list item' and n.get('name') == page)
        self.click({'role': 'push button', 'name': 'Open annotation menu', 'within': card['ref']})
        time.sleep(0.6)
        self.click({'role': 'push button', 'name': entry})
        time.sleep(1.0)

    def note_end(self):
        """Put the cursor at the end of the note shown in the note editor."""
        blocks = [n for n in self.nodes() if n['role'] in ('paragraph', 'heading')
                  and 'editable' in n.get('states', ())]
        if not blocks:
            raise AssertionError('no note is open in the editor')
        self.click(max(blocks, key=lambda n: n['bounds'][1])['ref'])
        self.key('Control+End')
        time.sleep(0.3)

    def reader_page(self, page):
        self.retry({'op': 'fill', 'target': {'role': 'entry', 'name': 'Page'}, 'value': str(page)})
        self.key('Return')
        time.sleep(1.5)

    def reader_click(self, page):
        """Click into the upper part of the shown PDF page."""
        landmark = self.wait_node(lambda n: n['role'] == 'landmark' and (n.get('name') or '').startswith('Page')
                                  and n['bounds'][1] < 600 and n['bounds'][1] + n['bounds'][3] > 400)
        x, y, w, h = landmark['bounds']
        self.retry({'op': 'click', 'x': x + w // 2, 'y': max(y, 140) + 180})
        time.sleep(1.0)

    def reader_region(self, text):
        node = self.wait_node(lambda n: n['role'] == 'section' and n.get('text') == text
                             and 140 < n['bounds'][1] < 800)
        x, y, w, h = node['bounds']
        self.retry({'op': 'drag', 'x': x - 4, 'y': y - 5, 'to_x': x + w + 5, 'to_y': y + h + 5,
                    'seconds': 1.0})
        self.key('Escape')

    def reader_ink(self):
        self.retry({'op': 'drag', 'x': 750, 'y': 650, 'via': [[800, 700], [850, 650]],
                    'to_x': 900, 'to_y': 700, 'seconds': 1.0})
        self.key('Escape')

    def run(self, steps):
        for step in steps:
            op = step['op']
            if op == 'library':
                self.library()
            elif op == 'collection':
                self.collection(step['name'])
            elif op == 'item':
                self.item(step['title'], **{k: step[k] for k in ('modifiers', 'click_count') if k in step})
            elif op == 'menu':
                self.menu(step['path'])
            elif op == 'context':
                self.context(step['target'], step['path'])
            elif op == 'click':
                self.click(step['target'], **{k: v for k, v in step.items() if k in ('button', 'click_count',
                                                                                    'modifiers')})
            elif op == 'field':
                self.field(step['label'], step['value'], step.get('commit', 'Return'))
            elif op == 'show-field':
                self.show_field(step['name'])
            elif op == 'type':
                self.type(step['value'])
            elif op == 'key':
                self.key(step['key'], step.get('times', 1))
            elif op == 'wait':
                time.sleep(step.get('seconds', 1.0))
            elif op == 'window':
                self.wait_window(step['title'], present=step.get('present', True))
            elif op == 'node':
                wanted = step['target']
                self.wait_node(lambda n: all(n.get(k) == v for k, v in wanted.items()))
            elif op == 'open-file':
                self.file_open(step['path'])
            elif op == 'save-file':
                self.file_save(step['path'])
            elif op == 'drag':
                self.retry({k: v for k, v in step.items() if k != 'op'} | {'op': 'drag'})
            elif op == 'raw':
                self.retry(step['request'])
            elif op == 'fill':
                self.retry({'op': 'fill', 'target': step['target'], 'value': step['value']})
            elif op == 'check':
                self.retry({'op': 'check', 'target': step['target'], 'checked': step.get('checked', True)})
            elif op == 'confirm':
                self.confirm(step['button'])
            elif op == 'confirm-if':
                self.confirm_if(step['button'], step.get('seconds', 3.0))
            elif op == 'section-add':
                self.section_add(step['section'])
            elif op == 'choose':
                self.choose(step['name'], step.get('role', 'list item'))
            elif op == 'select-items':
                self.select_items(step['title'])
            elif op == 'add-related':
                self.section_add('Related')
                self.select_items(step['title'])
            elif op == 'remove-related':
                self.remove_related(step['title'])
            elif op == 'merge-fields':
                self.merge_fields(step['values'])
            elif op == 'open-child':
                self.open_child(step['title'], step['child'])
            elif op == 'note-append':
                self.note_append(step['text'], step.get('bold', False))
            elif op == 'remove-tag':
                self.remove_tag(step['tag'])
            elif op == 'condition':
                self.condition(step['row'], step['condition'], step['operator'], step.get('value'), step.get('choice'))
            elif op == 'highlight':
                self.highlight(step['text'])
            elif op == 'annotation-comment':
                self.annotation_comment(step['page'], step['text'])
            elif op == 'annotation-menu':
                self.annotation_menu(step['page'], step['entry'])
            elif op == 'sidebar-tab':
                self.sidebar_tab(step['name'])
            elif op == 'note-end':
                self.note_end()
            elif op == 'reader-page':
                self.reader_page(step['page'])
            elif op == 'reader-click':
                self.reader_click(step['page'])
            elif op == 'reader-region':
                self.reader_region(step['text'])
            elif op == 'reader-ink':
                self.reader_ink()
            else:
                raise AssertionError('unknown recipe step ' + op)
        time.sleep(0.8)


def begin(ctx, checkpoint):
    """Before each checkpoint: no menu left open from earlier operations."""
    try:
        ctx.broker.call({'op': 'wait', 'seconds': 0.3})
    except BrokerError:
        pass


def execute(ctx, checkpoint):
    steps = checkpoint.get('recipe')
    if steps is None:
        raise NotImplementedError('no recipe for ' + checkpoint['id'])
    Recipe(ctx, checkpoint).run(steps)
