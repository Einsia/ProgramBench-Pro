"""Deterministic routes for the pinned upstream desktop, using only public runtime operations.

These routes are private record recipes, not constraints on a candidate's interface.
"""
import time


def reference(ctx):
    if 'reference' not in ctx.state:
        ctx.state['reference'] = Reference(ctx)
    return ctx.state['reference']


def begin(ctx, checkpoint):
    reference(ctx).settle()


def execute(ctx, checkpoint):
    reference(ctx).run(checkpoint.get('recipe', []))


def collect(ctx, checkpoint):
    reference(ctx).settle()


class Reference:
    def __init__(self, ctx):
        self.ctx = ctx
        self.rpc = ctx.broker.call

    def call(self, op, **kw):
        return self.rpc({'op': op, **kw})

    def observe(self):
        return self.call('observe', tree=True)

    def settle(self):
        self.call('wait', seconds=.4)

    def key(self, key, repeat=1):
        for _ in range(repeat):
            self.call('press', key=key)

    def nodes(self, role=None, name=None, dialog=False):
        nodes = self.observe()['nodes']
        by_ref = {n['ref']: n for n in nodes}

        def inside(n):
            for _ in range(30):
                if n['role'] in ('dialog', 'alert', 'file chooser'):
                    return True
                if n.get('parent') not in by_ref:
                    return False
                n = by_ref[n['parent']]
            return False
        return [n for n in nodes if (role is None or n['role'] == role)
                and (name is None or n.get('name') == name) and (not dialog or inside(n))]

    def click(self, role, name, nth=0, count=1):
        nodes = self.nodes(role, name)
        assert len(nodes) > nth, f'missing {role} {name!r}'
        self.call('click', target=nodes[nth]['ref'], click_count=count)

    def button(self, name):
        candidates = self.nodes('button', name, dialog=True) or self.nodes('button', name)
        assert candidates, f'missing button {name}'
        self.call('click', target=candidates[-1]['ref'])
        self.settle()

    def menu(self, *path):
        for i, label in enumerate(path):
            self.call('click', target={'role': 'menu' if i < len(path)-1 else 'menu item',
                                       'name': label, 'exact': True})
            self.call('wait', seconds=.15)
        self.settle()

    def field(self, value, index=0, role='text', name=None):
        candidates = self.nodes(role, name, dialog=True)
        if role == 'text':
            candidates = [n for n in candidates if 'editable' in n.get('states', [])]
        assert len(candidates) > index, f'missing dialog field {role} {name} #{index}'
        self.call('fill', target=candidates[index]['ref'], value=str(value))

    def check(self, name, checked=True):
        self.call('check', target={'role': 'check box', 'name': name, 'exact': True}, checked=checked)

    def node(self, name, nth=0):
        self.menu('Tree', 'Expand All Nodes')
        self.click('table cell', name, nth)
        self.settle()

    def editor(self):
        candidates = [n for n in self.nodes('text') if n['bounds'][0] >= 100 and n['bounds'][2] > 350 and n['bounds'][3] > 200]
        assert candidates, 'no main editor'
        return max(candidates, key=lambda n: n['bounds'][2]*n['bounds'][3])

    def select(self, text=None, node='Inbox', start=None, length=None):
        if node:
            self.node(node)
        editor = self.editor()
        content = editor.get('text', '')
        if text is not None:
            assert text in content, f'{text!r} not in editor {content!r}'
            start, length = content.index(text), len(text)
        self.call('click', target=editor['ref'])
        self.key('Control+Home')
        before = content[:start or 0]
        self.key('Down', before.count('\n'))
        self.key('Home')
        column = len(before.rsplit('\n', 1)[-1])
        self.key('Right', column)
        selected = content[start or 0:(start or 0)+(length or 0)]
        if selected and '\n' in selected and column == 0:
            self.key('Shift+Down', selected.count('\n'))
            if selected.rsplit('\n', 1)[-1]: self.key('Shift+End')
        elif selected and ((start or 0)+len(selected) == len(content) or
                           content[(start or 0)+len(selected):(start or 0)+len(selected)+1] == '\n'):
            self.key('Shift+End')
        else:
            self.key('Shift+Right', length or 0)

    def save(self):
        self.key('Control+S')
        self.settle()
        assert not self.nodes('file chooser'), 'saving an existing document unexpectedly opened a chooser'
        assert not self.nodes('alert'), 'saving left an unresolved alert'

    def location(self, path, reopen):
        # The chooser can still be taking focus when its first shortcut arrives.
        # Confirm the actual path entry instead of typing into GTK's search box.
        for _ in range(3):
            assert self.nodes('file chooser'), 'no file chooser for the location'
            if self.nodes('text', 'Search', dialog=True):
                # GTK can leave its folder model unusable after switching out
                # of search; recreate this chooser through the same export UI.
                self.run(reopen)
            self.key('Control+L')
            self.settle()
            fields = [n for n in self.nodes('text', dialog=True)
                      if 'editable' in n.get('states', []) and n.get('name') != 'Search']
            if len(fields) == 1:
                self.call('fill', target=fields[0]['ref'], value=path)
                current = self.nodes('text', dialog=True)
                if any(n['ref'] == fields[0]['ref'] and n.get('text') in (path, path + '/') for n in current):
                    return
            self.settle()
        raise AssertionError('the file chooser did not expose the requested location')

    def file(self, path, save=False, verify_location=False, reopen=()):
        if not path.startswith('/'):
            area, _, name = path.partition('/')
            path = self.ctx.state['inbox' if area == 'inputs' else 'outbox'] + '/' + name
        self.settle()
        if save:
            self.field(path)
        elif verify_location:
            self.location(path, reopen)
            self.key('Return')
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                self.settle()
                if not self.nodes('file chooser'):
                    return
                buttons = [n for n in self.nodes('button', dialog=True)
                           if n.get('name') in ('Open', 'Select') and 'disabled' not in n.get('states', [])]
                if buttons:
                    self.call('click', target=buttons[-1]['ref'])
            raise AssertionError('the verified folder chooser did not finish')
        else:
            self.key('Control+L')
            self.call('type', value=path)
        for label in ('Save', 'Open', 'Select', 'Create'):
            if self.nodes('button', label, dialog=True):
                self.button(label)
                break
        else:
            self.key('Return')
        self.settle()

    def properties(self, name=None, syntax=None, tags=None, checks=()):
        if name is not None:
            self.field(name, 0)
        if syntax:
            self.click('radio button', syntax)
        if tags is not None:
            self.field(tags, 1)
        for label, value in checks:
            self.check(label, value)
        self.button('OK')
        if self.nodes('button', 'Yes', dialog=True):
            self.button('Yes')

    def save_as(self, path, fmt='ctd', password='cherry-7z'):
        labels = {'ctd': 'Single XML File (.ctd)', 'ctb': 'Single SQLite File (.ctb)',
                  'ctz': 'Single XML File, 7-zip Encrypted and Password Protected (.ctz)',
                  'ctx': 'Single SQLite File, 7-zip Encrypted and Password Protected (.ctx)',
                  'folder': 'Multiple Files in Hierarchical Folder Structure'}
        self.key('Control+Shift+S')
        self.click('radio button', labels[fmt])
        if fmt in ('ctz', 'ctx'):
            self.field(password, 0, 'password text')
            self.field(password, 1, 'password text')
        self.button('OK')
        self.file(path, save=True)
        if self.nodes('button', 'Replace', dialog=True): self.button('Replace')

    def color(self, value, background=False):
        self.menu('Format', 'Text Color Background' if background else 'Text Color Foreground')
        candidates = [n for n in self.nodes('button', '', dialog=True) if 'disabled' not in n.get('states', [])]
        assert candidates, 'custom color button missing'
        self.call('click', target=candidates[0]['ref'])
        self.field(value, name='Color Name')
        self.button('Select')

    def find(self, text, replacement=None, multiple=False, names=False, options=(), first=False):
        command = ('Find in Nodes Names and Tags...' if names else
                   ('Find' if replacement is None else 'Replace') +
                   (' in Multiple Nodes...' if multiple else ' in Node Content...'))
        self.menu('Search', command)
        self.field(text, 0)
        if replacement is not None: self.field(replacement, 1)
        for label, value in options: self.check(label, value)
        if first: self.click('radio button', 'First in All Range')
        self.check('Show Iterated Find/Replace Dialog', False)
        self.button('OK')

    def import_file(self, path, label, parent='Root'):
        self.menu('File', 'Import', label)
        self.file(path)
        if self.nodes('dialog', 'Who is the Parent?'):
            if parent == 'Root':
                self.click('radio button', 'The Tree Root')
            else:
                self.click('radio button', 'The Selected Node')
            self.button('OK')
        self.settle()

    def export_file(self, kind, path, scope='Selected Node Only', single=False, include=True):
        self.menu('File', 'Export', {'txt':'Export to Plain Text', 'html':'Export To HTML',
                                    'pdf':'Export To PDF', 'ctd':'Export To CherryTree'}[kind])
        self.click('radio button', scope)
        if self.nodes('check box', 'Single File', dialog=True): self.check('Single File', single)
        if self.nodes('check box', 'Include Node Name', dialog=True): self.check('Include Node Name', include)
        self.button('OK')
        if kind == 'ctd':
            self.click('radio button', 'Single XML File (.ctd)')
            self.button('OK')
        self.file(path, save=kind in ('pdf', 'ctd') or (kind=='txt' and (single or scope in ('Selected Text Only','Selected Node Only'))))
        if self.nodes('file chooser'): self.key('Return')
        if self.nodes('button', 'OK', dialog=True): self.button('OK')

    def link(self, target, kind='web', anchor=None):
        self.key('Control+L')
        if kind == 'web':
            self.click('radio button', 'To WebSite')
            self.field(target)
        elif kind == 'node':
            self.click('radio button', 'To Node')
            candidates = self.nodes('table cell', target, dialog=True)
            assert candidates, 'link destination missing'
            self.call('click', target=candidates[-1]['ref'])
            if anchor: self.field(anchor, -1)
        self.button('OK')

    def object_icon(self):
        editor=self.editor()
        icons=[n for n in self.nodes('icon') if n['bounds'][0]>=editor['bounds'][0]
               and n['bounds'][1]>=editor['bounds'][1] and n['bounds'][2]>20 and n['bounds'][3]>20]
        assert icons, 'no embedded object'
        return icons[0]

    def image_edit(self, turn=None, width=None, flip=None):
        self.node('Image')
        self.call('click',target=self.object_icon()['ref'],click_count=2)
        if turn or flip:
            label=('Rotate '+turn) if turn else ('Flip '+flip)
            n=next(n for n in self.nodes('button',dialog=True) if n.get('description')==label)
            self.call('click',target=n['ref'])
        if width is not None:self.field(width,role='spin button')
        self.button('OK')

    def reparent(self, parent):
        self.menu('Tree','Node Move','Node Change Parent...')
        candidates=self.nodes('table cell',parent,dialog=True)
        assert candidates, 'new parent missing'
        self.call('click',target=candidates[-1]['ref'])
        self.button('OK')

    def run(self, actions):
        for a in actions:
            op = a['op']
            if op == 'node': self.node(a['name'], a.get('nth', 0))
            elif op == 'key': self.key(a['key'], a.get('repeat', 1))
            elif op == 'menu': self.menu(*a['path'])
            elif op == 'select': self.select(**{k: v for k, v in a.items() if k != 'op'})
            elif op == 'type': self.call('type', value=a['value'])
            elif op == 'button': self.button(a['name'])
            elif op == 'click': self.click(a['role'], a['name'], a.get('nth', 0), a.get('count', 1))
            elif op == 'field': self.field(a['value'], a.get('index', 0), a.get('role', 'text'), a.get('name'))
            elif op == 'check': self.check(a['name'], a.get('checked', True))
            elif op == 'save': self.save()
            elif op == 'file': self.file(a['path'], a.get('save', False), a.get('verify_location', False), a.get('reopen', ()))
            elif op == 'properties': self.properties(**{k: v for k, v in a.items() if k != 'op'})
            elif op == 'save-as': self.save_as(a['path'], a.get('format', 'ctd'), a.get('password', 'cherry-7z'))
            elif op == 'color': self.color(a['value'], a.get('background', False))
            elif op == 'find': self.find(**{k:v for k,v in a.items() if k!='op'})
            elif op == 'import': self.import_file(a['path'], a['label'], a.get('parent', 'Root'))
            elif op == 'export': self.export_file(**{k:v for k,v in a.items() if k!='op'})
            elif op == 'link': self.link(**{k:v for k,v in a.items() if k!='op'})
            elif op == 'image-edit': self.image_edit(a.get('turn'),a.get('width'),a.get('flip'))
            elif op == 'object-menu':
                self.node(a['node'])
                self.call('click',target=self.object_icon()['ref'],button='right')
                self.menu(a['command'])
            elif op == 'description':
                n=next(n for n in self.nodes(a.get('role','button'),dialog=True) if n.get('description')==a['value'])
                self.call('click',target=n['ref'])
            elif op == 'reparent':self.reparent(a['parent'])
            elif op == 'language':
                self.click('radio button','Automatic Syntax Highlighting')
                buttons=[n for n in self.nodes('button',dialog=True) if n.get('name') not in ('OK','Cancel')]
                self.call('click',target=buttons[0]['ref'])
                self.key('Home')
                self.call('type',value=a['name'])
                self.key('Return')
                self.settle()
            elif op == 'control':
                target = {'role': a['role'], 'text': a.get('text', '')}
                if a.get('link'):
                    editor = self.editor()
                    x, y, w, h = editor['bounds']
                    self.call('click', x=x+35, y=y+13)
                else:
                    self.call('click', target=target)
            elif op == 'open':
                if a.get('folder'): self.menu('File', 'Open Folder...')
                else: self.key('Control+O')
                self.file(a['path'])
                if self.nodes('password text', dialog=True):
                    self.field(a.get('password', 'cherry-7z'), role='password text')
                    self.button('OK')
            elif op == 'browse':
                path=a['path']
                if path=='outputs':path=self.ctx.state['outbox']
                elif path.startswith('outputs/'):path=self.ctx.state['outbox']+'/'+path[8:]
                self.select(node=a.get('node','Projects'))
                self.menu('Insert', 'Insert File...')
                self.key('Control+L')
                self.call('type',value=path+'/')
                self.key('Return')
                self.settle()
                if not self.nodes('file chooser'):
                    # GTK may accept a folder entry by closing rather than navigating.
                    # Its next chooser starts in the accepted folder.
                    self.menu('Insert', 'Insert File...')
                self.call('move',x=1200,y=850)
                names=[n.get('name','') for n in self.nodes('table cell')]
                assert any(name.endswith(('.txt','.html','.pdf','.ctd','.csv','.cfg','.png')) for name in names), 'no exported files visible'
            elif op == 'dismiss':
                for _ in range(4):
                    if self.nodes('button', 'Close', dialog=True): self.button('Close')
                    elif self.nodes('button', 'OK', dialog=True): self.button('OK')
                    else: self.key('Escape')
            elif op == 'add':
                self.key('Control+Shift+N' if a.get('child') else 'Control+N')
                self.properties(a['name'], a.get('syntax'))
                if a.get('text'): self.call('type', value=a['text'])
            elif op == 'confirm':
                if self.nodes('button', a['name'], dialog=True): self.button(a['name'])
            elif op == 'wait': self.call('wait', seconds=a.get('seconds', .5))
            elif op == 'end':
                self.select(node=a.get('node', 'Inbox'))
                self.key('Control+End')
            elif op == 'last-object':
                self.select(node=a.get('node', 'Inbox'))
                self.key('Control+End')
                self.key('Shift+Left')
            elif op == 'edit-icon':
                editor = self.editor()
                icons = [n for n in self.nodes('icon') if n['bounds'][0] >= editor['bounds'][0]
                         and n['bounds'][1] >= editor['bounds'][1] and n['bounds'][2] > 20 and n['bounds'][3] > 20]
                assert icons, 'no embedded image icon'
                self.call('click', target=icons[-1]['ref'], click_count=2)
                self.settle()
            elif op == 'history':
                for _ in range(20):
                    if self.editor().get('text', '').startswith(a['prefix']): break
                    self.menu('Edit', 'Redo' if a.get('redo') else 'Undo')
                assert self.editor().get('text', '').startswith(a['prefix']), 'history did not reach the requested text'
            elif op == 'assert-editor':
                value=self.editor().get('text','')
                assert a.get('contains','') in value and (not a.get('absent') or a['absent'] not in value), 'visible editor state differs from the goal'
            else: raise ValueError('unknown recipe operation ' + op)
