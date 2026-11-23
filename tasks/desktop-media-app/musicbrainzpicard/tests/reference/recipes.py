"""Deterministic recipes that drive the pinned standard through the runtime's GUI operations (record only).

Recipes use the same runtime operations as the evaluator and the model: menus, dialogs and file dialogs through the
accessible tree, keys, and, for the product's popup context menus (which are not in the accessible tree), the
keyboard. They are never the candidate's frontend contract; goals and acceptance conditions in specification.py
are.
"""
import time

from evaluation.broker import BrokerError


def call(ctx, request, retries=0):
    for attempt in range(retries+1):
        try:
            return ctx.broker.call(request)
        except BrokerError:
            if attempt == retries:
                raise
            time.sleep(1)


def nodes(ctx):
    return ctx.broker.call({'op': 'observe'}).get('nodes', [])


def windows(ctx):
    return [w.get('title', '') for w in ctx.broker.call({'op': 'windows'}).get('windows', [])]


def wait_window(ctx, title, present=True, seconds=10):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if any(title in t for t in windows(ctx)) == present:
            return True
        time.sleep(.3)
    raise RuntimeError(f'window {title!r} did not {"appear" if present else "close"}')


def menu(ctx, path):
    for index, name in enumerate(path):
        call(ctx, {'op': 'click', 'target': {'role': 'menu item', 'name': name}}, retries=2)
        time.sleep(.4)


def metadata_row(ctx, tag):
    """The New Value cell of a metadata view row by its tag name (the cells of one row share a y position)."""
    found = nodes(ctx)
    names = [n for n in found if n['role'] == 'table cell' and n.get('name') == tag and n['bounds'][0] < 50
             and n['bounds'][1] > 600]
    if not names:
        raise RuntimeError('no metadata row '+tag)
    y = names[0]['bounds'][1]
    cells = sorted((n for n in found if n['role'] == 'table cell' and n['bounds'][1] == y), key=lambda n: n['bounds'][0])
    return cells[-1]


def edit_tag(ctx, tag, value):
    cell = metadata_row(ctx, tag)
    call(ctx, {'op': 'click', 'target': cell['ref'], 'click_count': 2})
    time.sleep(.4)
    call(ctx, {'op': 'press', 'key': 'Control+a'})
    call(ctx, {'op': 'type', 'value': value})
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(.4)


def add_tag(ctx, tag, value):
    """Metadata view > Add New Tag: the tag name in the dialog's name field, one value, OK."""
    cell = metadata_row(ctx, 'Title') if any(n.get('name') == 'Title' for n in nodes(ctx)) else None
    if cell is not None:
        call(ctx, {'op': 'click', 'target': cell['ref']})
    call(ctx, {'op': 'press', 'key': 'Alt+Shift+a'})
    wait_window(ctx, 'Edit Tag')
    call(ctx, {'op': 'type', 'value': tag})
    # The name field's completion list covers the value buttons until focus moves on.
    call(ctx, {'op': 'press', 'key': 'Tab'})
    time.sleep(.3)
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Edit value'}})
    time.sleep(.3)
    call(ctx, {'op': 'type', 'value': value})
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(.3)
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'OK'}})
    wait_window(ctx, 'Edit Tag', present=False)


def remove_tag(ctx, tag):
    found = nodes(ctx)
    names = [n for n in found if n['role'] == 'table cell' and n.get('name') == tag and n['bounds'][0] < 50
             and n['bounds'][1] > 600]
    if not names:
        raise RuntimeError('no metadata row '+tag)
    call(ctx, {'op': 'click', 'target': names[0]['ref']})
    call(ctx, {'op': 'press', 'key': 'Alt+Shift+r'})
    time.sleep(.5)


def select_cell(ctx, text, exact=False, modifiers=None):
    target = {'role': 'table cell', 'name': text} if exact else {'role': 'table cell', 'text': text}
    request = {'op': 'click', 'target': target}
    if modifiers:
        request['modifiers'] = modifiers
    call(ctx, request, retries=2)
    time.sleep(.3)


def save(ctx, confirm=True):
    call(ctx, {'op': 'press', 'key': 'Control+s'})
    time.sleep(1)
    if confirm and any('File Save Warning' in t for t in windows(ctx)):
        call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'OK'}})
        time.sleep(.5)
    time.sleep(1.5)


def context_keys(ctx, target, keys):
    """Open the product's popup context menu on a control and choose an entry with the keyboard."""
    call(ctx, {'op': 'click', 'target': target, 'button': 'right'})
    time.sleep(.6)
    for key in keys:
        call(ctx, {'op': 'press', 'key': key})
        time.sleep(.25)
    time.sleep(.8)


def run_script(ctx, target, entry=1):
    """File view node > context menu > Run scripts > the entry-th script. From the end of a node's menu the
    entries are Select all, Collapse all, Expand all (clusters only), then Run scripts."""
    ups = 4 if target in ('Unclustered Files', 'Clusters') or target.startswith('cluster:') else 2
    target = target.split(':', 1)[1] if target.startswith('cluster:') else target
    context_keys(ctx, {'role': 'table cell', 'text': target}, ['Up']*ups+['Right']+['Down']*(entry-1)+['Return'])


def find(ctx, role, name=None, text=None, nth=0):
    found = [n for n in nodes(ctx) if n['role'] == role and (name is None or n.get('name') == name)
             and (text is None or text in str(n.get('text', '')))]
    if len(found) <= nth:
        raise RuntimeError(f'no {role} {name or text!r}')
    return found[nth]


def options_page(ctx, page):
    """Options > Options..., then the page in the dialog's page list."""
    if not any(t == 'Options' for t in windows(ctx)):
        menu(ctx, ['Options', 'Options…'])
        wait_window(ctx, 'Options')
        time.sleep(.5)
    call(ctx, {'op': 'click', 'target': {'role': 'table cell', 'name': page}}, retries=2)
    time.sleep(.5)


def set_check(ctx, name, value=True, role='check box'):
    """Check boxes (also checkable group boxes) and radio buttons through their accessible action."""
    node = find(ctx, role, name)
    if ('checked' in node.get('states', [])) != value:
        call(ctx, {'op': 'activate', 'target': node['ref']})
        time.sleep(.3)


def tag_name_cell(ctx, tag):
    found = [n for n in nodes(ctx) if n['role'] == 'table cell' and n.get('name') == tag and n['bounds'][0] < 50
             and n['bounds'][1] > 600]
    if not found:
        raise RuntimeError('no metadata row '+tag)
    return found[0]


def add_value(ctx, tag, value):
    """Metadata view > Edit... on a tag row: one more value in the Edit Tag dialog."""
    call(ctx, {'op': 'click', 'target': tag_name_cell(ctx, tag)['ref']})
    call(ctx, {'op': 'press', 'key': 'Alt+Shift+e'})
    wait_window(ctx, 'Edit Tag')
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Add value'}})
    time.sleep(.3)
    call(ctx, {'op': 'type', 'value': value})
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(.3)
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'OK'}})
    wait_window(ctx, 'Edit Tag', present=False)


def use_original(ctx, tag):
    """Metadata view context menu (Edit..., Add to "Preserve Tags" List, Remove, Use Original Value, ...)."""
    call(ctx, {'op': 'click', 'target': tag_name_cell(ctx, tag)['ref'], 'button': 'right'})
    time.sleep(.6)
    for key in ['Down']*4+['Return']:
        call(ctx, {'op': 'press', 'key': key})
        time.sleep(.2)
    time.sleep(.5)


def tag_menu(ctx, tag, keys):
    """A metadata view row's popup context menu (Edit…, Add to "Preserve Tags" List, Remove, ...), by keyboard."""
    call(ctx, {'op': 'click', 'target': tag_name_cell(ctx, tag)['ref'], 'button': 'right'})
    time.sleep(.6)
    for key in keys:
        call(ctx, {'op': 'press', 'key': key})
        time.sleep(.2)
    time.sleep(.5)


def tags_from_names(ctx, expression, underscores):
    call(ctx, {'op': 'press', 'key': 'Control+Shift+t'})
    wait_window(ctx, 'Convert File Names to Tags')
    field = next(n for n in nodes(ctx) if n['role'] == 'text' and 'editable' in n.get('states', [])
                 and '%' in str(n.get('text', '')))
    set_text(ctx, field['ref'], expression)
    if underscores:
        set_check(ctx, 'Replace underscores with spaces')
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Preview'}})
    time.sleep(.5)
    call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'OK'}})
    wait_window(ctx, 'Convert File Names to Tags', present=False)


def editor_texts(ctx, left):
    """Editable text fields of a dialog area, top to bottom."""
    return sorted((n for n in nodes(ctx) if n['role'] == 'text' and 'editable' in n.get('states', [])
                   and 'disabled' not in n.get('states', []) and n['bounds'][0] >= left and n['bounds'][1] > 100),
                  key=lambda n: (n['bounds'][1], n['bounds'][0]))


def naming_editor(ctx, title, script):
    """The file naming script editor after Script > Add a new script: title field, then the script text."""
    title_field, script_field = editor_texts(ctx, 250)[:2]
    set_text(ctx, title_field['ref'], title)
    set_text(ctx, script_field['ref'], script)
    # The script field's completion popup takes the next click: click the title field first.
    for _ in range(2):
        call(ctx, {'op': 'click', 'target': {'role': 'text', 'text': title}})
        time.sleep(.3)


def tagger_script(ctx, title, script):
    """Options > Scripting (enabled): the script list starts with one empty script after enabling; rename the last
    entry (adding one if the list is empty), then set its script text."""
    def entries():
        return [n for n in nodes(ctx) if n['role'] == 'list item' and 495 < n['bounds'][0] < 520]
    if not entries():
        call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': 'Add'}})
        time.sleep(.5)
    item = entries()[-1]
    call(ctx, {'op': 'click', 'target': item['ref'], 'click_count': 2})
    time.sleep(.4)
    call(ctx, {'op': 'press', 'key': 'Control+a'})
    call(ctx, {'op': 'type', 'value': title})
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(.3)
    field = next(n for n in nodes(ctx) if n['role'] == 'text' and 'editable' in n.get('states', [])
                 and n['bounds'][0] > 700 and n['bounds'][3] > 200)
    set_text(ctx, field['ref'], script)


def set_text(ctx, target, value):
    call(ctx, {'op': 'click', 'target': target})
    time.sleep(.2)
    call(ctx, {'op': 'press', 'key': 'Control+a'})
    call(ctx, {'op': 'type', 'value': value})
    time.sleep(.3)


def close_windows(ctx):
    """Close message boxes and dialogs left open by the previous checkpoint (OK, Close, then Escape)."""
    for _ in range(6):
        titles = windows(ctx)
        if len(titles) <= 1:
            return
        for name in ('OK', 'Close', 'Cancel'):
            try:
                ctx.broker.call({'op': 'click', 'target': {'role': 'push button', 'name': name}})
                break
            except BrokerError:
                continue
        else:
            call(ctx, {'op': 'press', 'key': 'Escape'})
        time.sleep(.5)


def dismiss(ctx):
    """Confirm a message box that an action may show (its OK or Yes button), if one is open."""
    time.sleep(.5)
    found = [n for n in nodes(ctx) if n['role'] == 'alert']
    if found:
        for name in ('OK', 'Yes'):
            try:
                ctx.broker.call({'op': 'click', 'target': {'role': 'push button', 'name': name}})
                break
            except BrokerError:
                continue
        time.sleep(.5)


def rename_selected(ctx, value):
    item = next(n for n in nodes(ctx) if n['role'] == 'list item' and 'selected' in n.get('states', []))
    call(ctx, {'op': 'click', 'target': item['ref'], 'click_count': 2})
    time.sleep(.4)
    call(ctx, {'op': 'press', 'key': 'Control+a'})
    call(ctx, {'op': 'type', 'value': value})
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(.4)


def cover_menu(ctx, keys):
    """The cover art area's popup context menu (not in the accessible tree), by keyboard."""
    image = next(n for n in nodes(ctx) if n['role'] == 'image' and n['bounds'][0] > 1290 and n['bounds'][2] >= 100)
    call(ctx, {'op': 'click', 'target': image['ref'], 'button': 'right'})
    time.sleep(.6)
    for key in keys:
        call(ctx, {'op': 'press', 'key': key})
        time.sleep(.25)
    time.sleep(.6)


def find_file(ctx, name):
    """Select a file by typing the start of its name in the file list (the view's type-ahead search), after a click
    on a row of the list: long lists show only part of their rows in the accessible tree."""
    for _ in range(3):
        rows = sorted((n for n in nodes(ctx) if n['role'] == 'table cell' and n['bounds'][0] < 260
                       and 110 < n['bounds'][1] < 590), key=lambda n: n['bounds'][1])
        call(ctx, {'op': 'click', 'target': rows[0]['ref']})
        time.sleep(.8)
        call(ctx, {'op': 'type', 'value': name})
        time.sleep(1.2)
        if any(n['role'] == 'table cell' and 'selected' in (n.get('states') or [])
               and str(n.get('name', '')).startswith(name) for n in nodes(ctx)):
            return
    raise RuntimeError('the file '+name+' could not be selected')


def quick_setting(ctx, index):
    """Options > Quick settings: its entries are check boxes inside the menu (no accessible names); the index-th
    entry from the top."""
    menu(ctx, ['Options', 'Quick settings'])
    entries = sorted((n for n in nodes(ctx) if n['role'] == 'menu item' and not n.get('name')
                      and n['bounds'][0] > 250), key=lambda n: n['bounds'][1])
    call(ctx, {'op': 'click', 'target': entries[index]['ref']})
    time.sleep(.4)
    call(ctx, {'op': 'press', 'key': 'Escape'})
    call(ctx, {'op': 'press', 'key': 'Escape'})
    time.sleep(.3)


def dialog_path(ctx, path):
    call(ctx, {'op': 'type', 'value': path})
    time.sleep(.3)
    call(ctx, {'op': 'press', 'key': 'Return'})
    time.sleep(1)


def expanded(ctx, value):
    """Recipe values name document folders as {inputs} and {outputs}."""
    c = ctx.state['c']
    if isinstance(value, str):
        return value.replace('{inputs}', c.inputs).replace('{outputs}', c.outputs)
    if isinstance(value, list):
        return [expanded(ctx, v) for v in value]
    if isinstance(value, dict):
        return {k: expanded(ctx, v) for k, v in value.items()}
    return value


def execute(ctx, checkpoint):
    for step in checkpoint.get('recipe', []):
        step = expanded(ctx, step)
        op = step['op']
        if op == 'menu':
            menu(ctx, step['path'])
        elif op == 'dialog':
            time.sleep(.5)
            dialog_path(ctx, step['path'])
        elif op == 'select':
            select_cell(ctx, step['text'], step.get('exact', False), step.get('modifiers'))
        elif op == 'edit-tag':
            edit_tag(ctx, step['tag'], step['value'])
        elif op == 'add-tag':
            add_tag(ctx, step['tag'], step['value'])
        elif op == 'remove-tag':
            remove_tag(ctx, step['tag'])
        elif op == 'save':
            save(ctx, step.get('confirm', True))
        elif op == 'options':
            options_page(ctx, step['page'])
        elif op == 'set-check':
            set_check(ctx, step['name'], step.get('value', True), step.get('role', 'check box'))
        elif op == 'set-text':
            set_text(ctx, step['target'], step['value'])
        elif op == 'button':
            call(ctx, {'op': 'click', 'target': {'role': 'push button', 'name': step['name'],
                                                  **({'nth': step['nth']} if 'nth' in step else {})}}, retries=1)
            time.sleep(step.get('pause', .8))
        elif op == 'add-value':
            add_value(ctx, step['tag'], step['value'])
        elif op == 'copy-tag':
            call(ctx, {'op': 'click', 'target': metadata_row(ctx, step['tag'])['ref']})
            call(ctx, {'op': 'press', 'key': 'Control+c'})
            time.sleep(.3)
        elif op == 'paste-tag':
            call(ctx, {'op': 'click', 'target': metadata_row(ctx, step['tag'])['ref']})
            call(ctx, {'op': 'press', 'key': 'Control+v'})
            time.sleep(.5)
        elif op == 'tag-menu':
            tag_menu(ctx, step['tag'], step['keys'])
        elif op == 'use-original':
            use_original(ctx, step['tag'])
        elif op == 'tags-from-names':
            tags_from_names(ctx, step['format'], step.get('underscores', False))
        elif op == 'naming-editor':
            naming_editor(ctx, step['title'], step['script'])
        elif op == 'tagger-script':
            tagger_script(ctx, step['title'], step['script'])
        elif op == 'close-windows':
            close_windows(ctx)
        elif op == 'dismiss':
            dismiss(ctx)
        elif op == 'rename-selected':
            rename_selected(ctx, step['value'])
        elif op == 'cover-menu':
            cover_menu(ctx, step['keys'])
        elif op == 'find-file':
            find_file(ctx, step['name'])
        elif op == 'quick-setting':
            quick_setting(ctx, step['index'])
        elif op == 'run-script':
            run_script(ctx, step['target'], step.get('entry', 1))
        elif op == 'context':
            context_keys(ctx, step['target'], step['keys'])
        elif op == 'wait-window':
            wait_window(ctx, step['title'], step.get('present', True), step.get('seconds', 10))
        elif op == 'sleep':
            time.sleep(step['seconds'])
        elif op in ('click', 'press', 'type', 'fill', 'check', 'activate', 'scroll', 'move', 'wait', 'drag'):
            request = {k: v for k, v in step.items() if k not in ('retries', 'pause')}
            call(ctx, request, retries=step.get('retries', 0))
            time.sleep(step.get('pause', .3))
        else:
            raise ValueError('unknown recipe step '+op)
