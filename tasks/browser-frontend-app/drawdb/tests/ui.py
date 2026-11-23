"""Scripted use of the application through the black-box runtime (checkpoint preparation and program checks).

The harness operates the application as a user does, with the runtime's GUI operations only. It finds controls by
the visible names the reference shows (menu titles and entries, dialog buttons, field placeholders), compared without
regard to letter case and spacing; a menu entry may carry its keyboard shortcut after its name. It accepts the
equivalent routes an implementation may take: menus that open on click or on hover, files supplied through a file
chooser, a file input or a drop, and exports that download at once or from a dialog. Where one name appears more
than once, the control that the previous action revealed is used. Nothing here reads the application's internals.
"""
import base64
import json
import re
import time

from evaluation.broker import BrokerError

WAIT = 6.0
SHORTCUT = re.compile(r'(ctrl|control|alt|shift|cmd|meta|del|delete|enter|return|esc)\b[\w+()/ .-]*$', re.I)
DATABASES = {'generic': 'Generic', 'mysql': 'MySQL', 'postgresql': 'PostgreSQL', 'sqlite': 'SQLite',
             'mariadb': 'MariaDB', 'transactsql': 'MSSQL', 'oraclesql': 'Oracle SQL'}
NEUTRAL = (1272, 6)  # a point of the page that no control of the reference covers
OUTSIDE = (4, 600)  # beside the left edge of the page, outside the panels and sheets that open over it
UPLOAD_WORDS = ('click to upload', 'drag and drop', 'upload', 'choose file', 'browse', 'select file', 'select document')
# Functional synonyms, not a required vocabulary. Dialogs also support their unique affirmative action,
# native choice controls, immediate completion and file-input/drop routes.
ALIASES = {
    'confirm': ('ok', 'continue', 'create', 'create diagram', 'apply', 'accept', 'done'),
    'cancel': ('close', 'dismiss', 'back'),
    'file': ('document', 'diagram', 'files'),
    'import from': ('import', 'open from', 'load from'),
    'export as': ('export', 'download as', 'save as format'),
    'import from sql': ('import sql', 'load sql', 'open sql'),
    'export sql': ('download sql', 'save sql', 'generate sql'),
    'import': ('load', 'open', 'upload', 'apply', 'ok', 'confirm'),
    'export': ('download', 'save', 'save file', 'generate', 'ok', 'confirm'),
    'open': ('open diagram', 'open saved diagram', 'saved diagrams', 'load diagram'),
    'save': ('save diagram', 'save changes', 'apply', 'ok'),
    'save as': ('save a copy', 'duplicate diagram', 'save diagram as'),
    'rename': ('change name', 'rename diagram', 'apply', 'ok'),
    'delete': ('remove', 'delete diagram', 'remove diagram', 'confirm', 'ok'),
    'name': ('title', 'diagram name', 'diagram title', 'file name'),
    'search': ('search...', 'search diagrams', 'find diagrams', 'filter by name'),
    'upload file': ('from file', 'file upload', 'choose file', 'file'),
    'generic': ('generic sql', 'database agnostic', 'unspecified'),
    'postgresql': ('postgres', 'pg'), 'mssql': ('sql server', 'microsoft sql server', 'transact-sql'),
    'oracle sql': ('oracle',), 'json': ('json diagram', 'diagram json', 'json file'),
    'dbml': ('dbml file', 'dbml diagram'), 'markdown': ('markdown document', 'markdown documentation', 'md'),
}


class HarnessError(RuntimeError):
    """The application did not offer a step the harness needs (the checkpoint's preparation or check fails)."""


def norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def names(control):
    return [control.get(k) for k in ('text', 'aria', 'title', 'label', 'placeholder') if control.get(k)]


def labelled(control, wanted, prefix_ok=True):
    """Whether a control is named `wanted` (its name may be followed by a shortcut, as in menus)."""
    want = norm(wanted)
    alternatives = (want, *ALIASES.get(want, ()))
    for name in names(control):
        have = norm(name)
        if have in alternatives:
            return True
        if prefix_ok and any(have.startswith(w + ' ') and SHORTCUT.fullmatch(have[len(w) + 1:])
                             for w in alternatives):
            return True
    return False


class UI:
    def __init__(self, broker):
        self.broker = broker
        self.last = None
        self.before = set()
        self.dialog_base = set()

    # -- runtime calls ---------------------------------------------------------------------------------
    def call(self, request, timeout=None):
        answer = self.broker.call(request, timeout=timeout) if timeout else self.broker.call(request)
        if isinstance(answer, dict) and 'controls' in answer:
            self.before = {c['ref'] for c in (self.last or {}).get('controls', [])}
            self.last = answer
        return answer

    def snap(self):
        return self.call({'op': 'snapshot'})

    def wait(self, seconds=0.5):
        return self.call({'op': 'wait', 'seconds': seconds})

    def text(self, snap=None):
        snap = snap or self.last or self.snap()
        lines = [c.get('text', '') for c in snap.get('controls', [])] + snap.get('text', '').split('\n')
        return [line for line in lines if line]

    # -- locating ----------------------------------------------------------------------------------------
    def matches(self, wanted, snap=None, **extra):
        snap = snap or self.last or self.snap()
        if extra.get('startswith'):
            found = [c for c in snap.get('controls', []) if any(norm(n).startswith(norm(wanted)) for n in names(c))]
        else:
            found = [c for c in snap.get('controls', []) if labelled(c, wanted, extra.get('prefix_ok', True))]
        if 'tag' in extra:
            found = [c for c in found if c.get('tag') in extra['tag']]
        if extra.get('enabled'):
            found = [c for c in found if not c.get('disabled')]
        exact = [c for c in found if any(norm(n) == norm(wanted) for n in names(c))]
        found = exact or found
        fresh = [c for c in found if c['ref'] not in self.before]
        return fresh + [c for c in found if c not in fresh]

    def find(self, wanted, snap=None, **extra):
        found = self.matches(wanted, snap, **extra)
        return found[0] if found else None

    def wait_for(self, wanted, timeout=WAIT, **extra):
        deadline = time.monotonic() + timeout
        while True:
            control = self.find(wanted, self.snap(), **extra)
            if control:
                return control
            if time.monotonic() > deadline:
                raise HarnessError(f'no control named "{wanted}" appeared')
            time.sleep(0.25)

    def shown(self, text, snap=None):
        """Whether a text is visible on the page (as a control name or as page text)."""
        want = norm(text)
        return any(norm(line) == want for line in self.text(snap))

    def contains(self, text, snap=None):
        want = norm(text)
        return any(want in norm(line) for line in self.text(snap))

    # -- acting ------------------------------------------------------------------------------------------
    def click(self, wanted, **extra):
        """Click the control named `wanted`; plain page text of that name is clicked when no control has it."""
        control = self.find(wanted, **extra)
        if control is not None:
            return self.call({'op': 'click', 'target': {'ref': control['ref']}})
        alternatives = (wanted, *ALIASES.get(norm(wanted), ()))
        visible = [line for line in self.text() if norm(line) in {norm(a) for a in alternatives}]
        for label in visible or alternatives:
            try:
                return self.call({'op': 'click', 'target': {'text': label}})
            except BrokerError:
                try:
                    return self.call({'op': 'click', 'target': {'text': label, 'exact': False}})
                except BrokerError:
                    continue
        raise HarnessError(f'no action equivalent to "{wanted}" can be clicked') from None

    def away(self):
        """Move the pointer to an empty corner so that menus opened by hovering close."""
        try:
            self.call({'op': 'pointer', 'action': 'move', 'x': NEUTRAL[0], 'y': NEUTRAL[1]})
        except BrokerError:
            pass

    def press(self, key):
        return self.call({'op': 'press', 'key': key})

    def escape(self, times=2):
        for _ in range(times):
            try:
                self.press('Escape')
            except BrokerError:
                pass

    def menu(self, *path, leave=True):
        """Open a menu and choose an entry, through submenus: menu('File', 'Export as', 'JSON'). The pointer then
        leaves the menu (unless leave is false, for an entry that opens a confirmation beside it). When the menu title
        cannot be clicked because a panel left open covers the page, a click beside the page's left edge (outside
        such a panel) closes it first."""
        self.away()
        self.dialog_base = {c['ref'] for c in self.snap().get('controls', [])}
        # A candidate may expose the complete operation directly in a toolbar instead of a submenu.
        direct = ' '.join(path[1:]).replace(' from ', ' ').replace(' as ', ' ')
        if len(path) > 2:
            for title in (direct, direct.replace('Export', 'Download'), direct.replace('Import', 'Load')):
                control = self.find(title)
                if control and control.get('tag') not in ('input', 'textarea'):
                    self.call({'op': 'click', 'target': {'ref': control['ref']}})
                    if leave:
                        self.away()
                    return self.last
        for n, step in enumerate(path):
            try:
                self.click(step)
            except HarnessError:
                if n:
                    raise
                self.call({'op': 'pointer', 'x': OUTSIDE[0], 'y': OUTSIDE[1]})
                self.escape(1)
                self.click(step)
        if leave:
            self.away()
        return self.last

    def fill(self, control, value):
        return self.call({'op': 'fill', 'target': {'ref': control['ref']}, 'value': str(value)})

    def choose_value(self, current, value):
        choices = [c for c in self.snap().get('controls', [])
                   if (c.get('role') in ('combobox', 'listbox') or c.get('tag') == 'select')
                   and (labelled(c, current) or norm(c.get('value')) == norm(current))]
        if not choices:
            raise HarnessError('no choice control currently shows ' + current)
        control = choices[0]
        if control.get('tag') == 'select':
            return self.call({'op': 'select', 'target': {'ref': control['ref']}, 'value': value})
        self.call({'op': 'click', 'target': {'ref': control['ref']}})
        self.click(value)
        self.escape(1)
        return self.last

    # -- application steps -------------------------------------------------------------------------------
    def fresh(self, database='generic', path='/editor'):
        """A fresh browser profile on the editor, with a new diagram of the given database."""
        status = self.call({'op': 'reset'})
        if not status.get('ready'):
            raise HarnessError('the application did not come back after a reset: ' + str(status.get('detail')))
        self.call({'op': 'open', 'path': path})
        self.choose_database(database)
        return self.last

    def choose_database(self, database):
        name = DATABASES[database]
        deadline = time.monotonic() + WAIT
        while not (self.find(name) or self.shown(name)):
            snap = self.snap()
            # Editors that open immediately can receive the checkpoint's database through its diagram import.
            if snap.get('canvases') and not self.find('Confirm', snap) and not self.contains('Choose a database', snap):
                return
            for control in snap.get('controls', []):
                if control.get('tag') == 'select':
                    try:
                        self.call({'op': 'select', 'target': {'ref': control['ref']}, 'value': name})
                        return self.finish_database_choice()
                    except BrokerError:
                        pass
            if time.monotonic() > deadline:
                raise HarnessError(f'the editor offered no choice of the database "{name}"')
            self.wait(0.5)
        self.click(name)
        self.finish_database_choice()

    def finish_database_choice(self):
        confirm = self.action('Confirm', required=False)
        if confirm:
            self.call({'op': 'click', 'target': {'ref': confirm['ref']}})
        deadline = time.monotonic() + WAIT
        while confirm and self.find('Confirm', self.snap()):
            if time.monotonic() > deadline:
                raise HarnessError('the database choice did not close')
            time.sleep(0.25)

    def supply(self, filename, data, mime):
        """Give a file to the open dialog: through its file chooser, a file input, or by dropping it."""
        snap = self.snap()
        payload = {'filename': filename, 'mime_type': mime, 'base64': base64.b64encode(data).decode()}
        if snap.get('file_chooser'):
            return self.call({'op': 'upload', **payload})
        inputs = [c for c in snap.get('controls', []) if c.get('file')]
        if inputs:
            return self.call({'op': 'upload', 'target': {'ref': inputs[0]['ref']}, **payload})
        zones = [c for c in snap.get('controls', []) if c['ref'] not in self.before
                 and any(w in norm(' '.join(names(c))) for w in UPLOAD_WORDS)]
        zones += [c for c in snap.get('controls', []) if c not in zones
                  and any(w in norm(' '.join(names(c))) for w in UPLOAD_WORDS)]
        for zone in zones:
            after = self.call({'op': 'click', 'target': {'ref': zone['ref']}})
            if after.get('file_chooser'):
                return self.call({'op': 'upload', **payload})
        if zones:
            x, y, w, h = zones[0]['bounds']
            return self.call({'op': 'drop', 'x': x + w / 2, 'y': y + h / 2, **payload})
        # A document drop target need not have a particular label or an underlying file input.
        return self.call({'op': 'drop', 'x': 640, 'y': 450, **payload})

    def action(self, wanted, required=True):
        """Find a named action or an unambiguous affirmative button in the newly opened form."""
        snap = self.snap()
        found = self.find(wanted, snap, enabled=True)
        if found:
            return found
        buttons = [c for c in snap.get('controls', [])
                   if c['ref'] not in self.dialog_base and not c.get('disabled')
                   and (c.get('tag') == 'button' or c.get('role') == 'button' or c.get('type') == 'submit')
                   and not any(labelled(c, x) for x in ('Cancel', 'Help', 'Delete', 'Browse'))]
        submits = [c for c in buttons if c.get('type') == 'submit']
        if len(submits) == 1:
            return submits[0]
        if len(buttons) == 1:
            return buttons[0]
        if required:
            return self.wait_for(wanted, enabled=True)
        return None

    def confirm(self, wanted):
        """Press the dialog button `wanted` once it is enabled."""
        button = self.action(wanted)
        return self.call({'op': 'click', 'target': {'ref': button['ref']}})

    def import_json(self, filename, diagram):
        data = diagram if isinstance(diagram, bytes) else json.dumps(diagram, indent=2).encode()
        self.menu('File', 'Import from', 'JSON')
        self.supply(filename, data, 'application/json')
        button = self.action('Import', required=False)
        if button:
            self.call({'op': 'click', 'target': {'ref': button['ref']}})
            self.closed('Import')

    def stage_json(self, filename, data):
        """Open the JSON import dialog and give it a file, without importing it yet."""
        self.menu('File', 'Import from', 'JSON')
        self.supply(filename, data, 'application/json')
        return self.last

    def import_dbml(self, filename, text):
        """Import a DBML file; a refused file leaves the dialog open, which is then closed."""
        self.menu('File', 'Import from', 'DBML')
        self.supply(filename, text.encode(), 'application/octet-stream')
        self.submit('Import')

    def submit(self, wanted):
        """Press the dialog button `wanted` if it is enabled and wait for the dialog to close; a dialog that stays
        open (it refused the input) is closed instead."""
        button = self.wait_for(wanted)
        deadline = time.monotonic() + 2
        while button.get('disabled') and time.monotonic() < deadline:
            time.sleep(0.25)
            button = self.find(wanted, self.snap()) or button
        if not button.get('disabled'):
            self.call({'op': 'click', 'target': {'ref': button['ref']}})
        try:
            self.closed(wanted)
        except HarnessError:
            self.dismiss()

    def import_sql(self, filename, text, dialect=None, overwrite=False):
        """Import SQL from a file; dialect names the submenu entry of a generic diagram. A dialog that stays open (the
        script was refused) is closed; what the import changed is for the checks to observe."""
        path = ['File', 'Import from SQL'] + ([dialect] if dialect else [])
        self.menu(*path)
        self.choose_upload_tab()
        self.supply(filename, text.encode(), 'application/sql')
        if overwrite:
            self.tick('Overwrite existing diagram')
        self.submit('Import')

    def dismiss(self):
        """Close an open dialog: Escape, then its Cancel button."""
        self.escape()
        cancel = self.find('Cancel', self.snap(), enabled=True)
        if cancel is not None:
            self.call({'op': 'click', 'target': {'ref': cancel['ref']}})

    def choose_upload_tab(self):
        tab = self.find('Upload file')
        if tab is not None:
            self.call({'op': 'click', 'target': {'ref': tab['ref']}})

    def tick(self, wanted, checked=True):
        control = self.find(wanted)
        if control is None:
            raise HarnessError(f'no option named "{wanted}"')
        if control.get('checked') is not None and control['checked'] == checked:
            return self.last
        try:
            return self.call({'op': 'check', 'target': {'ref': control['ref']}, 'checked': checked})
        except BrokerError:
            return self.call({'op': 'click', 'target': {'ref': control['ref']}})

    def closed(self, wanted, timeout=WAIT):
        """Wait until the dialog button `wanted` is gone (the dialog closed); a dialog that stays open with the button
        disabled refused the action."""
        deadline = time.monotonic() + timeout
        while True:
            button = self.find(wanted, self.snap())
            if button is None:
                return
            if button.get('disabled') or time.monotonic() > deadline:
                raise HarnessError(f'the dialog stayed open after "{wanted}": ' + ' | '.join(self.text()[-6:])[:400])
            time.sleep(0.25)

    def download(self, before=(), timeout=WAIT):
        """The bytes of a download that appeared after `before` (refs already pending)."""
        deadline = time.monotonic() + timeout
        while True:
            pending = [d for d in (self.last or {}).get('downloads', []) if d['ref'] not in before]
            if pending:
                answer = self.call({'op': 'download', 'ref': pending[-1]['ref']})
                return pending[-1]['filename'], base64.b64decode(answer['body_base64'])
            if time.monotonic() > deadline:
                raise HarnessError('no file was downloaded')
            self.wait(0.5)

    def produced(self, suffixes, timeout=WAIT):
        """(filename, bytes) of the newest pending download whose name ends with one of the suffixes: a file the goal
        itself produced."""
        suffixes = tuple(s.lower() for s in suffixes)
        deadline = time.monotonic() + timeout
        while True:
            pending = [d for d in self.snap().get('downloads', []) if d['filename'].lower().endswith(suffixes)]
            if pending:
                answer = self.call({'op': 'download', 'ref': pending[-1]['ref']})
                return pending[-1]['filename'], base64.b64decode(answer['body_base64'])
            if time.monotonic() > deadline:
                raise AssertionError('no file ending in ' + ' or '.join(suffixes) + ' was downloaded')
            self.wait(0.5)

    def export(self, *path, button='Export', timeout=WAIT):
        """Choose an export menu entry and return (filename, bytes) of the file it produces, pressing the dialog's
        export button when the entry opens a dialog; the dialog is closed afterwards."""
        self.escape()
        pending = {d['ref'] for d in self.snap().get('downloads', [])}
        self.menu(*path)
        if not [d for d in self.last.get('downloads', []) if d['ref'] not in pending]:
            deadline = time.monotonic() + timeout
            while True:
                control = self.action(button, required=False)
                if control is not None:
                    self.call({'op': 'click', 'target': {'ref': control['ref']}})
                    break
                if [d for d in self.last.get('downloads', []) if d['ref'] not in pending]:
                    break
                if time.monotonic() > deadline:
                    raise HarnessError('the export offered neither a file nor an export button')
                time.sleep(0.3)
        result = self.download(pending, timeout)
        self.escape()
        return result

    def export_json(self):
        name, data = self.export('File', 'Export as', 'JSON')
        try:
            return json.loads(data.decode('utf-8'))
        except (UnicodeDecodeError, ValueError) as exc:
            raise AssertionError('the JSON export is not JSON: ' + str(exc)[:200]) from None

    def open_table(self, name):
        """Select a table by its name (the first control named so: its entry in the table list, or the table on the
        canvas)."""
        control = self.find(name, prefix_ok=False)
        if control is None:
            raise HarnessError(f'no table named "{name}" is shown')
        return self.call({'op': 'click', 'target': {'ref': control['ref']}})

    def fill_field(self, step):
        """Fill the text field found by placeholder or label (nth among matches), then commit it with a key."""
        snap = self.snap()
        fields = [c for c in snap.get('controls', []) if c.get('tag') in ('input', 'textarea')
                  and any(labelled(c, step[k]) for k in ('placeholder', 'label') if step.get(k))]
        nth = step.get('nth', 0)
        if len(fields) <= nth:
            raise HarnessError('no field ' + str({k: step[k] for k in ('placeholder', 'label') if k in step}))
        self.fill(fields[nth], step['value'])
        if step.get('commit', 'Tab'):
            self.call({'op': 'press', 'target': {'ref': fields[nth]['ref']}, 'key': step.get('commit', 'Tab')})
        return self.last

    def dialog_fill(self, value, button, placeholder='Name'):
        """Fill the text field the open dialog offers (found by its placeholder) and press the dialog button."""
        snap = self.snap()
        fields = [c for c in snap.get('controls', []) if c.get('tag') in ('input', 'textarea')
                  and labelled(c, placeholder)]
        if not fields:
            fields = [c for c in snap.get('controls', []) if c.get('tag') in ('input', 'textarea')
                      and c['ref'] not in self.dialog_base and c.get('type', 'text') in ('text', 'search')]
        fresh = [c for c in fields if c['ref'] not in self.before]
        if not fields:
            raise HarnessError(f'the dialog offers no field "{placeholder}"')
        self.fill((fresh or fields)[-1], value)
        self.confirm(button)
        self.closed(button)

    def choose(self, path, wanted, button, timeout=WAIT):
        """Open a dialog through the menu path, pick its entry named `wanted` (a list row whose text starts with the
        name, or a tile titled so) once the dialog shows it, and press the dialog button."""
        base = {c['ref'] for c in self.snap().get('controls', [])}
        self.menu(*path)
        want = norm(wanted)
        deadline = time.monotonic() + timeout
        while True:
            snap = self.snap()
            found = [c for c in snap.get('controls', []) if c['ref'] not in base and c.get('text')
                     and (norm(c['text']) == want or norm(c['text']).startswith(want + ' '))]
            found.sort(key=lambda c: norm(c['text']) != want)
            if found:
                self.call({'op': 'click', 'target': {'ref': found[0]['ref']}})
                break
            if self.shown(wanted, snap):
                self.call({'op': 'click', 'target': {'text': wanted, 'nth': self.count_text(wanted, snap) - 1}})
                break
            if time.monotonic() > deadline:
                raise HarnessError(f'the dialog offered no entry "{wanted}"')
            time.sleep(0.3)
        self.confirm(button)

    def saved_names(self, names, timeout=WAIT):
        """Which of the names the list of saved diagrams (File, Open) shows; the list is closed afterwards. A name
        is listed when an entry of the list reads as the name (alone or followed by the entry's other details)."""
        self.editor()
        base = {c['ref'] for c in self.snap().get('controls', [])}
        self.menu('File', 'Open')
        wanted = [norm(n) for n in names]

        def listed(want, found):
            longer = [w for w in wanted if w != want and w.startswith(want)]
            return any((t == want or t.startswith(want + ' ')) and not any(t == w or t.startswith(w + ' ')
                                                                          for w in longer) for t in found)
        deadline = time.monotonic() + timeout
        while True:
            found = [norm(c['text']) for c in self.snap().get('controls', []) if c['ref'] not in base and c.get('text')]
            if any(listed(w, found) for w in wanted) or time.monotonic() > deadline:
                break
            time.sleep(0.3)
        out = {name: listed(want, found) for name, want in zip(names, wanted)}
        self.escape()
        return out

    def count_text(self, text, snap):
        return max(1, sum(1 for line in snap.get('text', '').split('\n') if norm(line) == norm(text)))

    def menu_confirm(self, *path, button='Confirm'):
        """Choose a menu entry that asks for confirmation, and confirm."""
        self.menu(*path, leave=False)
        control = self.wait_for(button, enabled=True)
        self.call({'op': 'click', 'target': {'ref': control['ref']}})
        self.away()

    def editor(self):
        """Make sure the editor page is shown (a goal may have left another page open), with no dialog or side sheet
        open: Escape, then the close buttons of what is still open."""
        snap = self.snap()
        if not str(snap.get('url', '')).startswith('/editor'):
            self.call({'op': 'open', 'path': '/editor'})
        self.escape()
        self.away()
        for _ in range(3):
            closers = [c for c in self.snap().get('controls', []) if 'close' in (norm(c.get('aria')), norm(c.get('title')))]
            if not closers:
                break
            try:
                self.call({'op': 'click', 'target': {'ref': closers[0]['ref']}})
            except BrokerError:
                break
        return self.last
