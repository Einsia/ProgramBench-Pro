'''Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes (reference/recipes.py) implement these goals for the pinned standard answer. Goals are authored here and are never
produced by translating a recorded click trace. Every episode has its own runtime: the fixture notebook is uploaded into the
notebook folder before the first goal (setup item notebook) and the product is restarted so that it opens it. Outputs are written
to the outbox, and goals name exact paths and values.
'''
import json

from evaluation.contract import files_path
NOTEBOOKS = {'core': 'A notebook of seven linked pages whose home page is Home.',
             'links': 'A notebook of five pages that link to each other, three of them in the section Area, whose home page is Home.',
             'formats': 'A notebook whose page Formats uses every heading level, inline markup, lists, checkboxes and links, with a sub page Child; its home page is Home.'}
HINTS = ('The notebook is already open on its home page Home. A dialog counts as finished when it closes without an error message. '
         'Prefer menu items and control refs over guessed coordinates. Pages are saved when Control+S is pressed or a few seconds after the last edit; '
         'the saved page files are checked separately, so there is no need to look for them. Exact page text is measured separately: judge the visible result at a glance.')


def outbox(key):
    return files_path('outbox', instance=False)


def inbox(key):
    return files_path('inbox', instance=False)


def q(value):
    return chr(34) + value + chr(34)


def page(path, description, tail=None):
    return {**({'tail': tail} if tail else {}), 'kind': 'page', 'path': path, 'name': 'page-' + path.replace('/', '-').replace('.', '-'), 'description': description}


def page_list(description):
    return {'kind': 'pages', 'name': 'pages', 'description': description}


def files(folder, description):
    return {'kind': 'files', 'folder': folder, 'name': 'files-' + folder.replace('/', '-'), 'description': description}


def titles(description, match=None):
    return {**({'match': list(match)} if match else {}), 'kind': 'titles', 'name': 'titles', 'description': description}


def config(description):
    return {'kind': 'config', 'name': 'config', 'keys': ['name'], 'description': description}


def export_tree(folder, description):
    return {'kind': 'tree', 'folder': folder, 'name': 'tree-' + folder.replace('/', '-'), 'description': description}


def absent(path, description):
    return {'kind': 'absent', 'path': path, 'name': 'absent-' + path.replace('/', '-').replace('.', '-'), 'description': description}


def kept(name, last):
    return ['The page ' + name + ' still shows its original text above the new last line.', 'The last line of the page ' + name + ' ' + last + '.']


def step(key, goal, acceptance, recipe, checks=(), depends=(), lifecycle=None, modal_end=False):
    cp = {'id': key, 'goal': goal, 'acceptance': [acceptance] if isinstance(acceptance, str) else list(acceptance),
          'recipe': list(recipe), 'checks': list(checks), 'depends_on': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    if modal_end:
        cp['modal_end'] = True
    return cp


# A checkpoint is blocked when the earlier checkpoint whose result it builds on did not pass.
DEPENDS = {
    'page-new': {'export': ['create']},
    'format-heading-remove': {'plain': ['h5']},
    'edit-undo-redo': {'redo': ['undo']},
    'nav-history': {'back': ['jump'], 'forward': ['back']},
    'nav-tree': {'parent': ['jump'], 'next': ['home'], 'previous': ['next']},
    'go-child': {'deeper': ['child']},
    'index-reveal': {'reveal': ['collapse']},
    'plugin-toc': {'again': ['toc']},
    'view-panes': {'zoom': ['hide']},
    'page-delete-keep': {'home': ['delete']},
}


def episode(key, feature, steps, *, notebook='core', budget=None, inputs=()):
    items = [{'id': 'notebook', 'op': 'notebook', 'key': notebook}]
    if inputs:
        items.append({'id': 'inputs', 'op': 'inputs', 'files': list(inputs)})
    for cp in steps:
        cid = cp['id']
        cp['depends_on'] = ['setup:notebook'] + (['setup:inputs'] if inputs else []) + (list(cp['depends_on']) or list(DEPENDS.get(key, {}).get(cid, [])))
        cp['assertions'] = []
        for i, text in enumerate(cp['acceptance']):
            suffix = 'visible' if len(cp['acceptance']) == 1 else f'visible-{i + 1}'
            cp['assertions'].append({'id': f'{key}/{cid}/{suffix}', 'channel': 'frontend', 'method': 'agent', 'requirement': text})
        for check in cp['checks']:
            name = check['name']
            cp['assertions'].append({'id': f'{key}/{cid}/{name}', 'channel': 'backend', 'method': 'program',
                                     'requirement': check['description'], 'check': check})
        if not any(a['channel'] == 'frontend' for a in cp['assertions']):
            raise AssertionError(key + '/' + cid + ' has no frontend assertion: the driver runs a GUI checkpoint only when it has one')
    n = len(steps)
    return {'id': key, 'feature': feature, 'execution': 'gui',
            'initial_state': 'Fresh application process on the fixture notebook (uploaded before the first goal, then the product is restarted), '
                             'an empty DATA_DIR and a private desktop session.',
            'setup': items, 'prepare': [],
            'inputs': {'output_folder': outbox(key), 'notebook': NOTEBOOKS[notebook]},
            'session': 'The application has just started on its notebook. ' + HINTS,
            'allowed_equivalents': ['Menus, toolbar buttons, context menus and keyboard shortcuts that reach the same product command are equivalent.',
                                    'Typing a full path into a file field is equivalent to browsing to it.'],
            'forbidden_bypasses': ['Do not use terminals, other applications, private files or hidden state.'],
            'budget': dict(budget) if budget else {'calls': min(160, 55 + 30 * n), 'seconds': min(1800, 540 + 210 * n), 'tokens': min(1_500_000, 500_000 + 250_000 * n)},
            'checkpoints': steps}


def frozen_form(value):
    '''The manifest is compared with its JSON-frozen copy: use JSON types only.'''
    return json.loads(json.dumps(value, ensure_ascii=False))


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(frozen_form(episode(*a, **kw)))

    k = 'edit-append'
    add(k, 'editing', [
        step('append', 'On the page Home, directly after the current last line and without a blank line in between, add a new last line with the text ' + q('Appended line from the editor') + ' and make sure the page is saved.',
             kept('Home', 'reads Appended line from the editor'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'Appended line from the editor'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the appended line.')])])

    k = 'replace-all'
    add(k, 'search', [
        step('replace', 'On the page Home, replace every occurrence of the word Welcome with Greetings using find and replace, then make sure the page is saved.',
             'The page Home shows Greetings where it read Welcome, and the rest of its text is unchanged.',
             [{'op': 'replace', 'find': 'Welcome', 'with': 'Greetings', 'all': True}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt has Greetings where Welcome stood and is otherwise unchanged.')])])

    k = 'page-new'
    add(k, 'pages', [
        step('create', 'Create the new page Work:Plan (a page Plan below a new section Work), write the line ' + q('Plan text with a tag @urgent') + ' into it and make sure the page is saved.',
             ['The index shows a section Work with a page Plan below it.', 'The open page Plan shows the line Plan text with a tag @urgent.', 'The window title names the page Work:Plan.'],
             [{'op': 'new_page', 'name': 'Work:Plan'}, {'op': 'type', 'text': 'Plan text with a tag @urgent'}, {'op': 'save'}],
             [page('Work/Plan.txt', 'Work/Plan.txt holds the typed line below its heading.'),
              page_list('The notebook has a page Work:Plan next to the original pages.')]),
        step('export', 'Export the complete notebook as HTML with the Default template, one file per page, into the folder ' + outbox(k) + '/gui-export. Stop while the message that the export has completed is still on screen and do not dismiss it.',
             'A message that the export completed is shown on top of the export dialog.',
             [{'op': 'export', 'folder': 'gui-export', 'leave_open': True}, {'op': 'park', 'x': 1000, 'y': 500, 'seconds': 0.8}],
             [export_tree('gui-export', 'The export folder holds the exported text of every page, one HTML file per page, including the new page Work:Plan.')], modal_end=True)])
    k = 'format-bold'
    add(k, 'editing', [
        step('bold', 'On the page Home, directly after the current last line and without a blank line in between, add a new last line with the text ' + q('plain words here') + ', select that whole line, make it bold and make sure the page is saved.',
             kept('Home', 'reads plain words here and is shown in bold'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'plain words here'}, {'op': 'key', 'key': 'Shift+Home'},
              {'op': 'key', 'key': 'Control+B'}, {'op': 'key', 'key': 'End'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the bold line.')])])

    k = 'format-heading'
    add(k, 'editing', [
        step('heading', 'On the page Home, directly after the current last line and without a blank line in between, add a new last line with the text ' + q('Heading line') + ', turn it into a second level heading and make sure the page is saved.',
             kept('Home', 'reads Heading line and is formatted as a heading'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'Heading line'}, {'op': 'key', 'key': 'Control+2'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the heading line.')])])

    k = 'format-list'
    add(k, 'editing', [
        step('bullets', 'On the page Home, directly after the current last line and without a blank line in between, add a new last bulleted list with the two items ' + q('first item') + ' and ' + q('second item') + ', typing it as a list, and make sure the page is saved.',
             ['The page Home still shows its original text above the new list.', 'The page Home ends with a bulleted list of the two items first item and second item.'],
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': '* first item'}, {'op': 'key', 'key': 'Return'},
              {'op': 'type', 'text': 'second item'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the two list items.')])])

    k = 'format-checkbox'
    add(k, 'editing', [
        step('tasks', 'On the page Home, directly after the current last line and without a blank line in between, add two new last lines with checkboxes: the first reads ' + q('open task') + ' and is marked done, the second reads ' + q('other task')
             + ' and is marked as not done (crossed out). Make sure the page is saved.',
             ['The page Home still shows its original text and its second last line is the checkbox line open task with a done mark.', 'The last line of the page Home is the checkbox line other task with a crossed out mark.'],
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': '[] open task'}, {'op': 'key', 'key': 'F12'}, {'op': 'key', 'key': 'Return'},
              {'op': 'type', 'text': 'other task'}, {'op': 'key', 'key': 'Shift+F12'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the two checkbox lines.')])])

    k = 'page-rename'
    add(k, 'pages', [
        step('rename', 'Rename the page Area:First to Renamed so that it stays in the section Area, and let the product update the other pages that link to it.',
             ['The index shows the page Renamed below the section Area and no page First any more.', 'The window title names the page Area:Renamed.', 'The open page shows the heading Renamed above its original text.'],
             [{'op': 'key', 'key': 'Control+J', 'pause': 1.0}, {'op': 'type', 'text': 'Area:First', 'dialog': True}, {'op': 'key', 'key': 'Return', 'pause': 1.0},
              {'op': 'wait', 'seconds': 1.5}, {'op': 'key', 'key': 'F2', 'pause': 1.0}, {'op': 'key', 'key': 'Control+A', 'pause': 0.2}, {'op': 'type', 'text': 'Renamed', 'dialog': True},
              {'op': 'dialog', 'buttons': ['OK']}],
             [page('Area/Renamed.txt', 'The renamed page file holds the original text under its new heading.'),
              absent('Area/First.txt', 'The page file of the old name no longer exists.'),
              page('Area/Second.txt', 'The links to the renamed page in Area/Second.txt point to its new name.'),
              page('Home.txt', 'The link to the renamed page in Home.txt points to its new name.'),
              page('Area.txt', 'The link to the renamed page in the section page points to its new name.'),
              page_list('The notebook has a page Area:Renamed instead of Area:First.')])], notebook='links')

    k = 'page-delete'
    add(k, 'pages', [
        step('delete', 'Delete the page Area:Second, moving it to the trash and letting the links that point to it disappear from the other pages along with the page.',
             'The page Second is no longer listed below the section Area in the index.',
             [{'op': 'key', 'key': 'Control+J', 'pause': 1.0}, {'op': 'type', 'text': 'Area:Second', 'dialog': True}, {'op': 'key', 'key': 'Return', 'pause': 1.0},
              {'op': 'wait', 'seconds': 1.5}, {'op': 'menu', 'path': ['File', 'Delete Page']}, {'op': 'dialog', 'buttons': ['OK']}, {'op': 'key', 'key': 'Control+Home'}, {'op': 'park', 'x': 700, 'y': 600, 'seconds': 1.0}],
             [absent('Area/Second.txt', 'The page file of the deleted page no longer exists.'),
              page('Home.txt', 'The links to the deleted page are removed from Home.txt.'),
              page('Area.txt', 'The link to the deleted page is removed from the section page.'),
              page('Area/First.txt', 'The link to the deleted page is removed from Area/First.txt.'),
              page('Loose.txt', 'The aliased link to the deleted page is removed from Loose.txt.'),
              page_list('The notebook no longer has the page Area:Second.')])], notebook='links',
        budget={'calls': 115, 'seconds': 960, 'tokens': 1000000})

    k = 'link-insert'
    add(k, 'editing', [
        step('link', 'On the page Home, directly after the current last line and without a blank line in between, add a new last line with the text ' + q('target words') + ', turn the whole line into a link to the page Notes with the insert link dialog and make sure the page is saved.',
             kept('Home', 'reads target words and is shown as a link'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'target words'}, {'op': 'key', 'key': 'Shift+Home'},
              {'op': 'key', 'key': 'Control+L', 'pause': 1.0}, {'op': 'type', 'text': 'Notes', 'dialog': True}, {'op': 'dialog_close', 'buttons': ['Link']}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the link line.')])])

    k = 'page-subpage'
    add(k, 'pages', [
        step('create', 'Create the new sub page Child below the page Home, write the line ' + q('Child text with a tag @later') + ' into it and make sure the page is saved.',
             ['The index shows a page Child below Home.', 'The open page Child shows the line Child text with a tag @later.', 'The window title names the page Home:Child.'],
             [{'op': 'new_page', 'name': 'Child', 'sub': True}, {'op': 'type', 'text': 'Child text with a tag @later'}, {'op': 'save'}],
             [page('Home/Child.txt', 'Home/Child.txt holds the typed line below its heading.'),
              page_list('The notebook has a page Home:Child next to the original pages.')])])

    k = 'edit-two-pages'
    add(k, 'editing', [
        step('home', 'On the page Home, directly after the current last line and without a blank line in between, add a new last line with the text ' + q('First added line') + ' and make sure the page is saved.',
             kept('Home', 'reads First added line'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'First added line'}, {'op': 'save'}],
             [page('Home.txt', 'Home.txt keeps its original lines and ends with the first added line.')]),
        step('projects', 'Go to the page Projects, directly after its current last line and without a blank line in between, add a new last line with the text ' + q('Second added line') + ' and make sure the page is saved.',
             kept('Projects', 'reads Second added line'),
             [{'op': 'key', 'key': 'Control+J', 'pause': 1.0}, {'op': 'type', 'text': 'Projects', 'dialog': True}, {'op': 'key', 'key': 'Return', 'pause': 1.0},
              {'op': 'wait', 'seconds': 1.5}, {'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'Second added line'}, {'op': 'save'}],
             [page('Projects.txt', 'Projects.txt keeps its original lines and ends with the second added line.')])])

    LEAD = 'directly after the current last line and without a blank line in between, add a new last line with the text '

    def jump(name):
        return [{'op': 'key', 'key': 'Control+J', 'pause': 1.0}, {'op': 'type', 'text': name, 'dialog': True}, {'op': 'key', 'key': 'Return', 'pause': 1.0}, {'op': 'wait', 'seconds': 1.5}]

    def go(chord):
        return [{'op': 'key', 'key': chord, 'pause': 1.0}]

    def where(name):
        # The first checkpoint edits Home; later checkpoints open another page whose last line ends in plain text, so no checkpoint
        # types onto the line or into the formatting of an earlier one, whatever route a candidate takes to a new line.
        if name == 'Home':
            return 'On the page Home, ', []
        return 'Go to the page ' + name + ', then ', jump(name)

    def pagefile(name):
        return name.replace(':', '/') + '.txt'

    def styled(cid, name, text, how, key, shows, menu=None):
        intro, moves = where(name)
        apply = [{'op': 'menu', 'path': menu}] if menu else [{'op': 'key', 'key': key}]
        return step(cid, intro + LEAD + q(text) + ', select that whole line, ' + how + ' and make sure the page is saved.',
                    kept(name, 'reads ' + text + ' and is ' + shows),
                    moves + [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': text}, {'op': 'key', 'key': 'Shift+Home'}] + apply
                    + [{'op': 'key', 'key': 'End'}, {'op': 'save'}],
                    [page(pagefile(name), 'The last line of ' + pagefile(name) + ' is the line ' + text + ' with its markup.', tail=1)])

    def heading(cid, name, text, level, key):
        intro, moves = where(name)
        return step(cid, intro + LEAD + q(text) + ', turn that line into a heading of level ' + str(level) + ' (level 1 is the largest, level 5 the smallest) and make sure the page is saved.',
                    kept(name, 'reads ' + text + ' and is a level ' + str(level) + ' heading'),
                    moves + [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': text}, {'op': 'key', 'key': key}, {'op': 'key', 'key': 'End'}, {'op': 'save'}],
                    [page(pagefile(name), 'The last line of ' + pagefile(name) + ' is the level ' + str(level) + ' heading ' + text + '.', tail=1)])

    add('format-emphasis', 'editing', [
        styled('italic', 'Home', 'italic words here', 'make it italic', 'Control+I', 'shown in italic'),
        styled('mark', 'Projects', 'marked words here', 'mark it as highlighted text (the mark style)', 'Control+U', 'shown as marked (highlighted) text'),
        styled('strike', 'Projects:Alpha', 'struck words here', 'strike it through', 'Control+K', 'shown struck through')])

    add('format-code-scripts', 'editing', [
        styled('code', 'Home', 'code words here', 'format it as verbatim code text', 'Control+T', 'shown as verbatim code text'),
        styled('subscript', 'Projects', 'low words here', 'make it subscript', 'Control+Shift+B', 'shown as subscript'),
        styled('superscript', 'Projects:Alpha', 'high words here', 'make it superscript', None, 'shown as superscript', menu=['Format', 'Superscript'])])

    add('format-heading-levels', 'editing', [
        heading('h1', 'Home', 'First level heading', 1, 'Control+1'),
        heading('h3', 'Projects', 'Third level heading', 3, 'Control+3'),
        heading('h4', 'Projects:Alpha', 'Fourth level heading', 4, 'Control+4')])

    add('format-heading-remove', 'editing', [
        heading('h5', 'Home', 'Fifth level heading', 5, 'Control+5'),
        step('plain', 'On the page Home, turn the last line, the heading ' + q('Fifth level heading') + ', back into ordinary text and make sure the page is saved.',
             'The last line of the page Home reads Fifth level heading as ordinary text, not as a heading.',
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Format', 'Remove Heading']}, {'op': 'key', 'key': 'End'}, {'op': 'save'}],
             [page('Home.txt', 'The last line of Home.txt is the text Fifth level heading without heading markup.', tail=1)])])

    add('edit-undo-redo', 'editing', [
        step('undo', 'On the page Home, directly after the current last line and without a blank line in between, add the two new lines ' + q('one') + ' and ' + q('two') + '. Then undo the last typing step with the undo command, not by deleting text, so that the new text is only the line one, and make sure the page is saved.',
             'The page Home still shows its original text and now ends with the line one; the line two is gone.',
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': 'one'}, {'op': 'key', 'key': 'Return'}, {'op': 'type', 'text': 'two'}, {'op': 'key', 'key': 'Control+Z'}, {'op': 'save'}],
             [page('Home.txt', 'The last lines of Home.txt are the original last line and the line one after the undo.', tail=2)]),
        step('redo', 'Redo the undone typing with the redo command so that the line two is back below the line one, and make sure the page is saved.',
             'The page Home now ends with the two lines one and two.',
             [{'op': 'key', 'key': 'Control+Y'}, {'op': 'save'}],
             [page('Home.txt', 'The last lines of Home.txt are the line one and the line two after the redo.', tail=2)])])

    add('nav-history', 'pages', [
        step('jump', 'Open the page Area:First.',
             ['The window title names the open page Area:First.', 'The row First below Area is highlighted in the page index.'],
             jump('Area:First'), [titles('The window title names the open page Area:First.')]),
        step('back', 'Go back to the page that was open before.',
             ['The window title names the page Home again.', 'The row Home is highlighted in the page index.'],
             go('Alt+Left'), [titles('The window title names the page Home after going back.')]),
        step('forward', 'Go forward again to the page you came back from.',
             ['The window title names the page Area:First again.', 'The row First below Area is highlighted in the page index again.'],
             go('Alt+Right'), [titles('The window title names the page Area:First after going forward.')])], notebook='links')

    add('nav-tree', 'pages', [
        step('jump', 'Open the page Area:Second.',
             ['The window title names the open page Area:Second.', 'The row Second below Area is highlighted in the page index.'],
             jump('Area:Second'), [titles('The window title names the open page Area:Second.')]),
        step('parent', 'Go to the parent page of the open page, the section that it is in.',
             ['The window title names the page Area.', 'The row Area is highlighted in the page index.'],
             go('Alt+Up'), [titles('The window title names the parent page Area.')]),
        step('home', 'Go to the home page of the notebook.',
             ['The window title names the page Home.', 'The row Home is highlighted in the page index.'],
             go('Alt+Home'), [titles('The window title names the home page Home.')]),
        step('next', 'Go to the next page in the page index, the page listed right below the open page.',
             ['The window title names the page Loose, which the index lists right below Home.', 'The row Loose is highlighted in the page index.'],
             go('Alt+Page_Down'), [titles('The window title names the next page of the index.')]),
        step('previous', 'Go to the previous page in the page index, the page listed right above the open page.',
             ['The window title names the page Home, which the index lists right above Loose.', 'The row Home is highlighted in the page index.'],
             go('Alt+Page_Up'), [titles('The window title names the previous page of the index.')])], notebook='links')

    add('insert-rule', 'editing', [
        step('rule', 'On the page Home, directly after the current last line and without a blank line in between, insert a horizontal line, then type the text ' + q('below the rule') + ' on the line below it, and make sure the page is saved.',
             ['The page Home shows a horizontal line below its original text.',
              'The line below the horizontal line reads below the rule and is the last line of the page.'],
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Insert', 'Horizontal Line']}, {'op': 'type', 'text': 'below the rule'}, {'op': 'save'}],
             [page('Home.txt', 'The last two lines of Home.txt are the horizontal line and the line below the rule.', tail=2)])])

    add('insert-numbered', 'editing', [
        step('numbered', 'Go to the page Projects, then directly after the current last line and without a blank line in between, start a numbered list whose first item is ' + q('first step') + ' and whose second item is ' + q('second step') + ', and make sure the page is saved.',
             ['The page Projects ends with a numbered list whose first item, numbered 1, reads first step.',
              'The second item of the list, numbered 2, reads second step and is the last line of the page.'],
             jump('Projects') + [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Insert', 'Numbered List']}, {'op': 'type', 'text': 'first step'},
                                 {'op': 'key', 'key': 'Return'}, {'op': 'type', 'text': 'second step'}, {'op': 'save'}],
             [page('Projects.txt', 'The last two lines of Projects.txt are the two numbered items.', tail=2)])])

    add('list-indent', 'editing', [
        step('indent', 'On the page Home, directly after the current last line and without a blank line in between, add a bulleted list of three items: ' + q('parent item') + ', then ' + q('child item') + ' indented one level below it, then ' + q('outer item') + ' back on the first level, and make sure the page is saved.',
             ['The page Home ends with a bulleted list whose first item reads parent item.',
              'The item child item is indented one level below parent item.',
              'The last item outer item is back on the first level of the list.'],
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'type', 'text': '* parent item'}, {'op': 'key', 'key': 'Return'}, {'op': 'key', 'key': 'Tab'},
              {'op': 'type', 'text': 'child item'}, {'op': 'key', 'key': 'Return'}, {'op': 'key', 'key': 'Shift+Tab'}, {'op': 'type', 'text': 'outer item'}, {'op': 'save'}],
             [page('Home.txt', 'The last three lines of Home.txt are the list items with their indentation.', tail=3)])])

    add('notebook-rename', 'pages', [
        step('rename', 'Rename the notebook to ' + q('Plans') + ' in the properties of the notebook, then open the page Notes.',
             ['The window title names the open page Notes.', 'The window title names the notebook by its new name Plans.'],
             [{'op': 'menu', 'path': ['File', 'Properties']}, {'op': 'fill', 'label': 'Name', 'value': 'Plans'}, {'op': 'dialog', 'buttons': ['OK']},
              {'op': 'wait', 'seconds': 1.0}] + jump('Notes'),
             [titles('The window title names the page Notes and the new notebook name.'),
              config('The notebook configuration holds the new name Plans.')])])

    add('word-count', 'editing', [
        step('count', 'Show the word count of the page Home with the word count tool of the product and leave its window open.',
             'A word count window is open and shows the numbers of lines, words and characters of the page Home.',
             [{'op': 'menu', 'path': ['Tools', 'Word Count']}, {'op': 'wait', 'seconds': 1.0}, {'op': 'park', 'x': 1000, 'y': 800, 'seconds': 0.8}],
             [], modal_end=True)])

    add('insert-date', 'editing', [
        step('date', 'On the page Home, directly after the current last line and without a blank line in between, insert today' + chr(39) + 's date as a short numeric date of month, day and two digit year with the date insertion of the product, and make sure the page is saved.',
             'The page Home now ends with a line that holds today' + chr(39) + 's date as a short numeric month, day and year.',
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Insert', 'Date and Time']}, {'op': 'dialog', 'buttons': ['Insert']}, {'op': 'save'}],
             [page('Home.txt', 'The last line of Home.txt holds the inserted date.', tail=1)])])

    add('format-clear', 'editing', [
        step('clear', 'Go to the page Notes and remove all inline formatting (bold, italic, mark, strike and verbatim) from its line that begins with ' + q('Plain notes') + ', keeping the words of that line, and make sure the page is saved.',
             'The line of the page Notes that begins with Plain notes shows the words bold, italic, marked, struck and verbatim as ordinary text without any formatting.',
             jump('Notes') + [{'op': 'key', 'key': 'Control+Home'}, {'op': 'key', 'key': 'Down'}, {'op': 'key', 'key': 'Home'}, {'op': 'key', 'key': 'Shift+End'},
                              {'op': 'key', 'key': 'Control+9'}, {'op': 'key', 'key': 'End'}, {'op': 'save'}],
             [page('Notes.txt', 'Notes.txt with the formatting removed from the line that begins with Plain notes.')])])

    add('page-move', 'pages', [
        step('move', 'Move the page Area:First so that it becomes a sub page of Home with the same name First, and let the product update the other pages that link to it.',
             ['The index shows a page First below Home and no page First below Area any more.', 'The window title names the page Home:First.'],
             jump('Area:First') + [{'op': 'key', 'key': 'F2', 'pause': 1.0}, {'op': 'fill', 'label': 'Location', 'value': ':Home'}, {'op': 'dialog_close', 'buttons': ['OK']}, {'op': 'wait', 'seconds': 1.5}],
             [page('Home/First.txt', 'The moved page file holds the original text of the page.'),
              absent('Area/First.txt', 'The page file at the old place no longer exists.'),
              page('Home.txt', 'The link to the moved page in Home.txt points to its new place.'),
              page('Area/Second.txt', 'The links to the moved page in Area/Second.txt point to its new place.'),
              page_list('The notebook has a page Home:First instead of Area:First.')])], notebook='links')

    add('page-delete-keep', 'pages', [
        step('delete', 'Delete the page Loose, moving it to the trash, but keep the links that point to it on the other pages.',
             'The page Loose is no longer an ordinary page in the index: it is listed only as a greyed out placeholder, because other pages still link to it.',
             jump('Loose') + [{'op': 'menu', 'path': ['File', 'Delete Page']}, {'op': 'check', 'label': 'Remove links to Loose', 'value': False}, {'op': 'dialog', 'buttons': ['OK']},
                              {'op': 'key', 'key': 'Control+Home'}, {'op': 'park', 'x': 700, 'y': 600, 'seconds': 1.0}],
             [absent('Loose.txt', 'The page file of the deleted page no longer exists.'),
              page_list('The notebook no longer has the page Loose.')]),
        step('home', 'Open the home page Home.',
             ['The window title names the page Home.', 'The start line of the page Home still shows the link Loose to the deleted page.'],
             go('Alt+Home'), [page('Home.txt', 'Home.txt keeps its link to the deleted page.')])], notebook='links')

    add('copy-line', 'editing', [
        step('copy', 'On the page Home, copy its second line, the one that begins with ' + q('Welcome page') + ', with the copy line command of the product, then paste it '
             'directly after the current last line without a blank line in between, and make sure the page is saved.',
             kept('Home', 'is a copy of its second line, beginning with Welcome page'),
             [{'op': 'key', 'key': 'Control+Home'}, {'op': 'key', 'key': 'Down'}, {'op': 'menu', 'path': ['Edit', 'Copy Line']}, {'op': 'key', 'key': 'Control+End'},
              {'op': 'key', 'key': 'Control+V'}, {'op': 'save'}],
             [page('Home.txt', 'The last line of Home.txt is the copied line with its links.', tail=1),
              {'kind': 'clipboard', 'name': 'clipboard', 'description': 'The clipboard holds the text of the copied line.'}])])

    add('read-only', 'editing', [
        step('lock', 'Switch the page view of the notebook to read only with the editable toggle of the product, so that the page Home can no longer be changed.',
             ['The formatting buttons of the tool bar are greyed out.', 'The page Home still shows its original text.'],
             [{'op': 'menu', 'path': ['View', 'Toggle Editable']}, {'op': 'wait', 'seconds': 1.0}, {'op': 'park', 'x': 100, 'y': 800, 'seconds': 0.5}],
             [], modal_end=True)])

    add('index-reveal', 'pages', [
        step('collapse', 'Open the page Projects:Beta, then collapse the whole page index so that only the top level pages are listed.',
             ['The page index lists only top level pages such as Home, Notes and Projects.', 'No sub page such as Beta or Alpha is listed in the page index.'],
             jump('Projects:Beta') + [{'op': 'menu', 'path': ['View', 'Collapse Page Index']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title names the open page Projects:Beta.')]),
        step('reveal', 'Show the open page in the page index again with the product command that reveals the current page.',
             ['The page index lists Beta below Projects again.', 'The row Beta is highlighted in the page index.'],
             [{'op': 'menu', 'path': ['View', 'Reveal Current Page in Page Index']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title still names the page Projects:Beta.')])])

    add('save-version', 'pages', [
        step('version', 'Save a version of the notebook with the version control of the product (enable it with Git when the product asks, keep the proposed comment), '
             'then open the list of saved versions and leave it open.',
             ['A versions window is open.', 'The versions window lists one saved version of the notebook.'],
             [{'op': 'menu', 'path': ['File', 'Save Version']}, {'op': 'dialog', 'buttons': ['OK']}, {'op': 'wait', 'seconds': 2.0}, {'op': 'dialog', 'buttons': ['Save']},
              {'op': 'wait', 'seconds': 3.0}, {'op': 'menu', 'path': ['File', 'Versions']}, {'op': 'wait', 'seconds': 2.0}, {'op': 'park', 'x': 1000, 'y': 820, 'seconds': 0.8}],
             [], modal_end=True)])

    add('insert-text-file', 'editing', [
        step('insert', 'On the page Home, directly after the current last line and without a blank line in between, insert the text of the file snippet.txt from the folder '
             + inbox('insert-text-file') + ' with the product command that inserts text from a file, and make sure the page is saved.',
             ['The page Home still shows its original text above the inserted lines.', 'The page Home ends with the two lines Snippet line one. and Snippet line two.'],
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Insert', 'Text From File']}, {'op': 'files_dialog', 'area': 'inbox', 'name': 'snippet.txt', 'buttons': ['Open']}, {'op': 'save'}],
             [page('Home.txt', 'The last two lines of Home.txt are the lines of the file.', tail=2)])], inputs=['snippet.txt'])

    add('search-dialog', 'search', [
        step('search', 'Search the notebook for the word ' + q('team') + ' with the search window of the product and leave the window with its results open.',
             ['A search window is open with team as its query.', 'The results list the page Alpha below Projects.', 'The results list the page Beta below Projects.'],
             [{'op': 'menu', 'path': ['Search', 'Search']}, {'op': 'wait', 'seconds': 1.0}, {'op': 'fill_field', 'value': 'team'}, {'op': 'key', 'key': 'Return', 'pause': 2.0},
              {'op': 'park', 'x': 1000, 'y': 820, 'seconds': 0.8}],
             [], modal_end=True)])

    add('go-child', 'pages', [
        step('child', 'Open the page Journal, then go to a child page of it with the go to child command of the product.',
             ['The window title names the page Journal:2026.', 'The row 2026 below Journal is highlighted in the page index.'],
             jump('Journal') + [{'op': 'menu', 'path': ['Go', 'Child']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title names the child page Journal:2026.')]),
        step('deeper', 'Go one level further down to the child page of the open page with the same command.',
             ['The window title names the page Journal:2026:01.', 'The row 01 below 2026 is highlighted in the page index.'],
             [{'op': 'menu', 'path': ['Go', 'Child']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title names the child page Journal:2026:01.')])])

    add('find-bar', 'search', [
        step('find', 'On the page Projects, find the word ' + q('gamma') + ' with the find bar of the product and leave the find bar open.',
             ['A find bar is open below the page view with gamma as its search text.', 'The word gamma in the text of the page Projects is highlighted as the match.'],
             jump('Projects') + [{'op': 'find', 'text': 'gamma'}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title names the page Projects.')])])

    add('import-page', 'pages', [
        step('import', 'Import the file plain.txt from the folder ' + inbox('import-page') + ' into the notebook with the import page command of the product.',
             ['A new page plain is open and shows the heading Imported.', 'The open page shows the line Imported text with alpha and emphasis, with the word emphasis in italic.',
              'The page index lists the new page plain.'],
             [{'op': 'menu', 'path': ['File', 'Import Page']}, {'op': 'files_dialog', 'area': 'inbox', 'name': 'plain.txt', 'buttons': ['Open']}, {'op': 'wait', 'seconds': 1.5}],
             [page('plain.txt', 'The page file of the imported page holds the text of the input file.'),
              page_list('The notebook has the imported page next to the original pages.')])], inputs=['plain.txt'])

    add('new-window', 'pages', [
        step('window', 'Open the page Notes in a second window of the product, keeping the main window open.',
             ['A second window of the product shows the page Notes.', 'The second window shows the line Plain notes with its formatted words.'],
             jump('Notes') + [{'op': 'menu', 'path': ['File', 'Open in New Window']}, {'op': 'wait', 'seconds': 1.5}],
             [titles('A second window names the page Notes.', match=['Notes'])])])

    add('plugin-tasklist', 'plugins', [
        step('tasks', 'Turn on the Task List plugin in the preferences of the product, then open the task list of the notebook and leave it open.',
             ['A task list window is open.', 'The task list shows the open task write the alpha plan.', 'The task list shows the open task check the journal.'],
             [{'op': 'enable_plugin', 'name': 'Task List'}, {'op': 'menu', 'path': ['View', 'Task List']}, {'op': 'wait', 'seconds': 2.0}, {'op': 'park', 'x': 100, 'y': 850, 'seconds': 0.8}],
             [], modal_end=True)], budget={'calls': 145, 'seconds': 1170, 'tokens': 1250000})

    add('plugin-toc', 'plugins', [
        step('toc', 'Turn on the Table of Contents plugin in the preferences of the product, then open the page Formats.',
             ['A table of contents is shown together with the page Formats.', 'The table of contents lists the headings Second level, Third level, Fourth level and Fifth level of the page.'],
             [{'op': 'enable_plugin', 'name': 'Table of Contents'}] + jump('Formats'),
             [titles('The window title names the page Formats.')]),
        step('again', 'Open the page Formats.',
             ['After the restart of the product the table of contents is still shown together with the page Formats.', 'The table of contents still lists the headings Second level, Third level, Fourth level and Fifth level.'],
             jump('Formats'), [titles('The window title names the page Formats after the restart.')], lifecycle='restart')],
        notebook='formats', budget={'calls': 145, 'seconds': 1170, 'tokens': 1250000})

    add('view-panes', 'pages', [
        step('hide', 'Hide the side panes of the main window so that the page uses the whole width of the window.',
             ['The list of pages of the index is no longer shown; at most a narrow Index tab remains at the left edge.', 'The page Home fills the width of the window.'],
             [{'op': 'menu', 'path': ['View', 'Side Panes']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title still names the page Home.')]),
        step('zoom', 'Make the text of the page larger with the zoom in command of the product, two steps.',
             'The text of the page Home is shown larger than before.',
             [{'op': 'menu', 'path': ['View', 'Zoom In']}, {'op': 'wait', 'seconds': 0.5}, {'op': 'menu', 'path': ['View', 'Zoom In']}, {'op': 'wait', 'seconds': 1.0}],
             [titles('The window title still names the page Home after zooming.')])])

    add('insert-symbol', 'editing', [
        step('symbol', 'On the page Home, directly after the current last line and without a blank line in between, insert the symbol ' + q('Æ') + ' with the insert symbol dialog of the product, and make sure the page is saved.',
             kept('Home', 'is the symbol Æ'),
             [{'op': 'key', 'key': 'Control+End'}, {'op': 'menu', 'path': ['Insert', 'Symbol']}, {'op': 'click', 'label': 'Æ', 'roles': ['icon']}, {'op': 'dialog', 'buttons': ['Insert']},
              {'op': 'wait', 'seconds': 0.5}, {'op': 'save'}],
             [page('Home.txt', 'The last line of Home.txt is the inserted symbol.', tail=1)])])

    add('remove-list', 'editing', [
        step('unlist', 'On the page Projects:Beta, turn the list item ' + q('bullet one') + ' back into an ordinary line with the remove list command of the product, and make sure the page is saved.',
             'The line bullet one of the page Beta is shown without a bullet.',
             jump('Projects:Beta') + [{'op': 'key', 'key': 'Control+Home'}, {'op': 'key', 'key': 'Down'}, {'op': 'key', 'key': 'Down'}, {'op': 'menu', 'path': ['Format', 'Remove List']}, {'op': 'save'}],
             [page('Projects/Beta.txt', 'Projects/Beta.txt after the list item bullet one became an ordinary line.')])])

    return episodes
