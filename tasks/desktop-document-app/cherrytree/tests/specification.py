"""User goals, observable acceptance criteria and saved-document checks for desktop episodes."""
import fixtures

from evaluation.contract import files_path


def inbox(key):
    return files_path('inbox', instance=False)


def outbox(key):
    return files_path('outbox', instance=False)


HINTS = ('Work on the goals in order. Use the application commands; equivalent menus, shortcuts and pointer '
         'operations are accepted. When a goal asks to save, save the current document in place unless another '
         'path is given. Enter full paths in file dialogs. Exact stored text, formatting and objects are checked '
         'separately; judge the visible result without measuring small typographic differences. '
         'Select the named node before editing its content. Do not undo or redo just to gather evidence. '
         'A modal dialog should remain open only when a goal asks to inspect it.')


def action(op, **values):
    return {'op': op, **values}


def key(name, repeat=1):
    return action('key', key=name, repeat=repeat)


def menu(*path):
    return action('menu', path=list(path))


def node(name, nth=0):
    return action('node', name=name, nth=nth)


def select(text, name='Inbox'):
    return action('select', text=text, node=name)


def typed(value):
    return action('type', value=value)


def saved(aspects=('content:Inbox',), path='notebook.ctd', **fields):
    return [{'kind': 'document', 'path': path, 'aspect': aspect,
             'description': f'{path}: {aspect} matches the requested edit, with document structure and content normalized.',
             **fields} for aspect in aspects]


def step(cid, goal, acceptance, recipe, checks=(), depends=(), lifecycle=None, requires=None):
    cp = {'id': cid, 'goal': goal, 'acceptance': [acceptance] if isinstance(acceptance, str) else list(acceptance),
          'recipe': recipe, 'checks': checks, 'depends_on': list(depends), 'requires': requires or {}}
    if lifecycle: cp['lifecycle'] = lifecycle
    return cp


def episode(key_, feature, steps, *, document='notebook', fmt='ctd', opened=True, inputs=(), empty=False):
    setup = []
    if not empty:
        setup.append({'id': 'document', 'op': 'upload', 'area': 'outbox',
                      'files': [{'document': document, 'format': fmt, 'as': 'notebook'}]})
    if opened and not empty:
        setup.append({'id': 'open', 'op': 'open', 'document': f'{outbox(key_)}/notebook{fixtures.EXTENSION[fmt]}'})
    if inputs:
        setup.append({'id': 'inputs', 'op': 'upload', 'area': 'inbox', 'files': list(inputs)})
    for index, cp in enumerate(steps):
        # Independent edits begin from a new copy of the source document. A point never
        # inherits an unrelated earlier formatting defect through a whole-document check.
        if index and not cp['depends_on'] and opened and not empty:
            ident = 'fresh-' + cp['id']
            setup.extend([
                {'id': ident, 'op': 'upload', 'area': 'outbox', 'before': cp['id'],
                 'files': [{'document': document, 'format': fmt, 'as': 'notebook'}]},
                {'id': ident+'-open', 'op': 'open', 'before': cp['id'],
                 'document': f'{outbox(key_)}/notebook{fixtures.EXTENSION[fmt]}'},
            ])
            cp['depends_on'] += ['setup:'+ident, 'setup:'+ident+'-open']
            cp['goal'] = 'The supplied document has been reopened from its original contents. ' + cp['goal']
        cp['depends_on'] = (['setup:open'] if opened and not empty else []) + cp['depends_on']
        cp['assertions'] = []
        for i, text in enumerate(cp.pop('acceptance')):
            cp['assertions'].append({'id': f'{key_}/{cp["id"]}/visible-{i+1}', 'channel': 'frontend',
                                      'method': 'agent', 'requirement': text})
        for c in cp.pop('checks'):
            cp['assertions'].append({'id': f'{key_}/{cp["id"]}/{c["aspect"]}', 'channel': 'backend',
                                      'method': 'program', 'requirement': c['description'], 'check': c})
        assert any(a['channel']=='frontend' for a in cp['assertions']) or not cp['recipe'], \
            'GUI actions require a frontend checkpoint in the shared kit'
        for suffix, companions in cp.pop('requires').items():
            p = next(a for a in cp['assertions'] if a['id'].endswith('/'+suffix))
            p['requires'] = [f'{key_}/{x}' for x in companions]
    n = len(steps)
    token_limits = {'headings-small': 3_000_000, 'insert-anchor': 2_400_000,
                    'import-plain-folder': 3_000_000, 'import-markdown-folder': 2_000_000,
                    'search-multiple': 3_500_000, 'preferences-import': 2_500_000}
    return {'id': key_, 'feature': feature, 'execution': 'gui',
            'initial_state': 'Fresh application and data directory; uploaded files are listed in inputs. '
                             + ('The supplied document has already been opened through the public restart operation.'
                                if opened and not empty else 'No document has been opened.'),
            'setup': setup,
            'inputs': {'input_folder': inbox(key_), 'output_folder': outbox(key_),
                       'document': f'{outbox(key_)}/notebook{fixtures.EXTENSION[fmt]}',
                       'files': list(inputs)},
            'session': ('The supplied document is already open. ' if opened and not empty else 'The application is empty. ')+HINTS,
            'allowed_equivalents': ['Any visible application route that achieves the requested behavior is accepted.'],
            'forbidden_bypasses': ['Do not use a terminal, other applications, private files or hidden state.'],
            'budget': {'calls': 200 if key_ == 'import-plain-folder' else 80+45*n,
                       'tokens': token_limits.get(key_, 600000+300000*n),
                       'seconds': 2400 if key_ == 'headings-small' else 600+240*n},
            'checkpoints': steps}


def build():
    episodes = []
    def add(k, feature, steps, **kw): episodes.append(episode(k, feature, steps, **kw))
    save = action('save')

    add('nodes-create', 'node-tree', [
        step('sibling', 'Create a rich-text root node named Travel after Inbox. Enter "Pack a notebook." as its content and save.',
             ['Travel is a root node following Inbox.', 'Travel is selected and shows "Pack a notebook.".'],
             [node('Inbox'), action('add', name='Travel', text='Pack a notebook.'), save], saved(('tree', 'node:Travel'))),
        step('child', 'Under Travel create a child named Tickets with the text "Train at 09:30." and save.',
             ['Tickets appears beneath Travel as its child.', 'Tickets shows "Train at 09:30.".'],
             [node('Travel'), action('add', name='Tickets', text='Train at 09:30.', child=True), save],
             saved(('tree', 'node:Travel/Tickets')), depends=('sibling',)),
        step('rename', 'Rename Tickets to Reservations while retaining its content. Save.',
             'Reservations replaces the child name Tickets and still shows the train reminder.',
             [node('Tickets'), key('F2'), action('properties', name='Reservations'), save],
             saved(('tree', 'node:Travel/Reservations')), depends=('child',)),
    ])
    add('nodes-properties', 'node-properties', [
        step('tags', 'Set Inbox tags to "home urgent" and make its tree name bold. Save, then leave its properties visible.',
             ['Inbox has the tags home and urgent in its properties.', 'The node name is configured as bold.'],
             [node('Inbox'), key('F2'), action('properties', tags='home urgent', checks=[['Bold', True]]), save, key('F2')],
             saved(('props:Inbox',))),
        step('plain', 'Close properties. Change Archive to a plain-text node, preserving its text, and save.',
             'Archive is a plain-text note showing the old receipts and letters sentence.',
             [key('Escape'), node('Archive'), key('F2'), action('properties', syntax='Plain Text'), save],
             saved(('node:Archive',))),
        step('readonly', 'Make Archive read-only, save, and leave its properties visible.',
             'Archive is marked read-only in its properties.',
             [node('Archive'), menu('Tree', 'Toggle Read Only'), save, key('F2')],
             saved(('props:Archive',)), depends=('plain',)),
    ])
    add('nodes-move', 'node-tree', [
        step('up', 'Move Archive immediately before Projects among the root nodes, then save.',
             'The root order begins Inbox, Archive, Projects.',
             [node('Archive'), menu('Tree', 'Node Move', 'Node Up'), save], saved(('tree',))),
        step('indent', 'Make Archive a child of Inbox and save.',
             'Archive appears under Inbox as its child.',
             [node('Archive'), menu('Tree', 'Node Move', 'Node Right'), save], saved(('tree',)), depends=('up',)),
        step('outdent', 'Move Archive back to the root level immediately after Inbox and save.',
             'Archive is again a root node between Inbox and Projects.',
             [node('Archive'), menu('Tree', 'Node Move', 'Node Left'), save], saved(('tree',)), depends=('indent',)),
    ])
    add('nodes-sort', 'node-tree', [
        step('ascending', 'Sort the whole node tree by name ascending, expanding it so its children are visible. Save.',
             ['The roots are ordered Archive, Inbox, Projects, Script.', 'Projects contains Garden followed by Kitchen.'],
             [menu('Tree', 'Nodes Sort', 'Sort Tree Ascending'), menu('Tree', 'Expand All Nodes'), save], saved(('tree',))),
        step('descending', 'Sort the whole tree by name descending, keep children expanded, and save.',
             ['The roots are ordered Script, Projects, Inbox, Archive.', 'Projects contains Kitchen followed by Garden.'],
             [menu('Tree', 'Nodes Sort', 'Sort Tree Descending'), menu('Tree', 'Expand All Nodes'), save], saved(('tree',))),
    ])
    add('nodes-duplicate', 'node-tree', [
        step('branch', 'Duplicate Projects together with its children. Save and leave the tree expanded.',
             'Two Projects branches are present, each containing Garden and Kitchen.',
             [node('Projects'), menu('Tree', 'Duplicate Node and Subnodes'), menu('Tree', 'Expand All Nodes'), save],
             saved(('tree', 'node:Projects#2', 'node:Projects#2/Garden', 'node:Projects#2/Kitchen'))),
        step('delete', 'Delete the second Projects branch with its children and save.',
             'One Projects branch remains, with Garden and Kitchen, alongside the other original roots.',
             [node('Projects', 1), menu('Tree', 'Delete Node'), action('button', name='Yes'), save],
             saved(('tree',)), depends=('branch',)),
    ])
    add('nodes-bookmarks', 'bookmarks', [
        step('add', 'Bookmark Garden and save. Leave the Bookmarks menu open.',
             'Garden is available as a bookmark.',
             [node('Garden'), menu('Bookmarks', 'Add to Bookmarks'), save,
              action('click', role='menu', name='Bookmarks')], saved(('bookmarks',))),
        step('navigate', 'Visit Archive, then use the Garden bookmark to return to Garden.',
             'Garden is selected and its planting and watering notes are visible.',
             [key('Escape'), node('Archive'), menu('Bookmarks', 'Garden')], depends=('add',)),
        step('remove', 'Remove Garden from bookmarks, save, and leave the Bookmarks menu open.',
             'The menu offers bookmark management and Garden is no longer an entry.',
             [menu('Bookmarks', 'Remove from Bookmarks'), save, action('click', role='menu', name='Bookmarks')],
             saved(('bookmarks',)), depends=('add',), requires={'visible-1':['add/bookmarks']}),
    ])

    font_groups = [
        ('font-emphasis', [('bold', 'bold', 'Control+B'), ('italic', 'italic', 'Control+I'),
                           ('underline', 'underlined', 'Control+U'), ('strike', 'struck through', 'Control+E')]),
        ('font-special', [('mono', 'monospaced', 'Control+M'), ('small', 'small', 'Control+7'),
                          ('sub', 'subscript', 'Control+8'), ('super', 'superscript', 'Control+9')]),
    ]
    for k, settings in font_groups:
        steps = []
        lines = ['Meeting notes', 'Call the plumber tomorrow.', 'Buy milk and eggs.', 'Renew the library card.']
        for (cid, label, shortcut), text in zip(settings, lines):
            steps.append(step(cid, f'In Inbox format only "{text}" as {label}, then save.',
                              f'"{text}" visibly has the requested {label} formatting in the Inbox note.',
                              [select(text), key(shortcut), key('Right'), save], saved()))
        add(k, 'rich-text', steps)
    for k, levels in [('headings-large', [1, 2, 3]), ('headings-small', [4, 5, 6])]:
        steps = []
        for level, text in zip(levels, ['Meeting notes', 'Call the plumber tomorrow.', 'Buy milk and eggs.']):
            goal = f'In Inbox make "{text}" a level-{level} heading and save.'
            acceptance = f'"{text}" is displayed as a heading in Inbox.'
            recipe = [select(text), key(f'Control+{level}'), key('Right'), save]
            requires = None
            if level >= 4:
                goal += ' Insert a table of contents for this node at its end and save again.'
                acceptance = f'The table of contents contains a link to the heading "{text}".'
                recipe = recipe[:-1] + [action('end'), menu('Insert', 'Insert TOC and Headers Collapsors...'),
                                        action('button', name='OK'), save]
                requires = {'visible-1': [f'h{level}/content:Inbox']}
            steps.append(step('h'+str(level), goal, acceptance, recipe, saved(), requires=requires))
        add(k, 'rich-text', steps)
    add('format-history', 'rich-text', [
        step('format', 'Make "Meeting notes" bold and italic in Inbox, then save.',
             'The Inbox heading is both bold and italic.',
             [select('Meeting notes'), key('Control+B'), key('Control+I'), key('Right'), save], saved()),
        step('clear', 'Remove all formatting from "Meeting notes", then save.',
             'The heading is ordinary unstyled text.',
             [select('Meeting notes'), menu('Format', 'Remove Formatting'), key('Right'), save], saved(), depends=('format',)),
        step('undo', 'Undo removal of formatting using Undo, then save.',
             'The heading is bold and italic again.',
             [key('Control+Z'), key('Right'), save], saved(), depends=('clear',)),
    ])
    add('paragraph-layout', 'rich-text', [
        step('center', 'Center the "Meeting notes" paragraph in Inbox and save.',
             'The first paragraph is centered relative to the text area.',
             [select('Meeting notes'), menu('Format', 'Justify', 'Justify Center'), key('Right'), save], saved()),
        step('right', 'Right-align "Call the plumber tomorrow." and save.',
             'The plumber paragraph is aligned to the right of the text area.',
             [select('Call the plumber tomorrow.'), menu('Format', 'Justify', 'Justify Right'), key('Right'), save], saved()),
        step('indent', 'Indent the "Buy milk and eggs." paragraph once and save.',
             'The shopping paragraph begins farther right than the unindented final paragraph.',
             [select('Buy milk and eggs.'), menu('Format', 'Indent Paragraph'), key('Right'), save], saved()),
        step('unindent', 'Remove that indentation from "Buy milk and eggs." and save.',
             'The shopping paragraph again begins at the same left margin as the final paragraph.',
             [select('Buy milk and eggs.'), menu('Format', 'Unindent Paragraph'), key('Right'), save], saved(), depends=('indent',)),
    ])
    for k, label, shortcut in [('list-bullets','bulleted','Shift+Alt+L'), ('list-numbers','numbered','Shift+Alt+N'),
                                ('list-todo','to-do','Shift+Alt+T')]:
        text = 'Call the plumber tomorrow.\nBuy milk and eggs.\nRenew the library card.'
        add(k, 'lists', [
            step('make', f'In Inbox turn the three reminder paragraphs after Meeting notes into a {label} list. Save.',
                 f'The three reminders are displayed as a {label} list beneath the heading.',
                 [select(text), key(shortcut), key('Right'), save], saved()),
            step('append', 'Add "Wash the car." as the next list item and save.',
                 'Wash the car. is a fourth item using the same list style.',
                 [action('end'), key('BackSpace'), key('End'), key('Return'), typed('Wash the car.'), save],
                 saved(ignore_terminal_newlines=True), depends=('make',)),
        ])
    add('text-case', 'text-editing', [
        step('upper', 'Uppercase the words "Meeting notes" in Inbox and save.', 'The heading reads MEETING NOTES.',
             [select('Meeting notes'), key('Control+Shift+W'), key('Right'), save], saved()),
        step('lower', 'Lowercase "Call the plumber tomorrow." and save.', 'The line begins with lowercase call.',
             [select('Call the plumber tomorrow.'), key('Control+W'), key('Right'), save], saved()),
        step('toggle', 'Toggle the case of "Buy milk and eggs." and save.', 'The line reads bUY MILK AND EGGS.',
             [select('Buy milk and eggs.'), key('Control+G'), key('Right'), save], saved()),
    ])
    add('text-rows', 'text-editing', [
        step('duplicate', 'Duplicate the whole "Buy milk and eggs." row in Inbox and save.',
             'The shopping reminder occurs on two consecutive rows.',
             [select('Buy milk and eggs.'), key('Right'), key('Control+D'), save], saved()),
        step('up', 'Move the "Renew the library card." row to the top of Inbox and save.',
             'The library reminder is the first row, above Meeting notes.',
             [select('Renew the library card.'), key('Right'), key('Alt+Up', 4), save], saved(), depends=('duplicate',)),
        step('delete', 'Delete the entire "Call the plumber tomorrow." row and save.',
             'The library reminder, heading and two shopping rows remain; the plumber row is absent.',
             [select('Call the plumber tomorrow.'), menu('Edit', 'Row', 'Delete Row'), save], saved(), depends=('up',)),
    ])
    add('text-clipboard', 'clipboard', [
        step('copy', 'Copy "Call the plumber tomorrow." from Inbox as plain text, then append it on a new line '
             'in Archive using Paste as Plain Text. Save.',
             'Archive shows its original sentence followed by the copied plumber reminder.',
             [select('Call the plumber tomorrow.'), menu('Edit', 'Copy as Plain Text'),
              action('end', node='Archive'), key('Return'), menu('Edit', 'Paste as Plain Text'), save],
             [{'kind':'clipboard','aspect':'text','description':'The clipboard contains exactly the plumber sentence.'}]
             + saved(('content:Archive',), ignore_plain_blank_lines=True), requires={'visible-1':['copy/content:Archive','copy/text']}),
        step('cut', 'Cut "Old receipts and letters." from Archive as plain text and save.',
             'The plumber reminder remains and the old receipts sentence has been removed.',
             [select('Old receipts and letters.', 'Archive'), menu('Edit', 'Cut as Plain Text'), save],
             saved(('content:Archive',), ignore_plain_blank_lines=True)+[{'kind':'clipboard','aspect':'text',
                 'ignore_terminal_newlines':True,'description':'The clipboard holds the cut old receipts sentence, ignoring optional terminal line breaks.'}],
             depends=('copy',)),
    ])
    add('text-undo-redo', 'history', [
        step('edit', 'Replace "Meeting notes" with "Weekly planning" in Inbox and save.',
             'Inbox begins with Weekly planning.', [select('Meeting notes'), typed('Weekly planning'), save], saved()),
        step('undo', 'Undo the replacement until the original heading is restored, leaving the document open.',
             'Inbox begins with Meeting notes again.', [action('history', prefix='Meeting notes')], depends=('edit',)),
        step('redo', 'Redo the replacement and save the document as '+outbox('text-undo-redo')+'/redone.ctd.',
             'Inbox begins with Weekly planning again.',
             [action('history', prefix='Weekly planning', redo=True), action('save-as', path='outputs/redone.ctd')],
             saved(path='redone.ctd'), depends=('undo',)),
    ])
    from gui_extra import build as more
    from gui_state import build as state
    from gui_advanced import build as advanced
    from gui_more import build as additions
    return episodes + more() + state() + advanced() + additions()
