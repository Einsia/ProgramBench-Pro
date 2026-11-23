'''Product-independent desktop helpers of the Zim reference recipes (record only).

The only dependency is ctx.ui, the runtime GUI interface of reference/recipes.py. Helpers locate controls by their visible
accessible names and send ordinary input; they never read application state. Their routes belong to the pinned standard and are
never a candidate requirement.
'''
import time

DIALOG_ROLES = {'dialog', 'file chooser', 'alert'}
BUTTON_ROLES = {'push button', 'button', 'toggle button'}
FIELD_ROLES = {'text', 'entry', 'spin button', 'password text', 'combo box'}
ITEM_ROLES = {'menu item', 'check menu item', 'radio menu item'}
MENU_ROLES = {'menu'} | ITEM_ROLES


def _ui(ctx):
    return getattr(ctx, 'ui', ctx)


def norm(value):
    '''A control name without mnemonics, trailing dots and case, for comparisons.'''
    text = str(value or '').replace('_', '').strip()
    for tail in ('...', chr(8230), ':'):
        text = text.removesuffix(tail)
    return ' '.join(text.casefold().split())


def nodes(ctx):
    return list(_ui(ctx).observe().get('nodes', ()))


def names(node):
    return [str(node.get(key)) for key in ('name', 'text', 'description') if node.get(key)]


def find(items, labels, roles=(), exact=True):
    wanted = {norm(label) for label in labels}
    for node in items:
        if roles and node.get('role') not in roles:
            continue
        values = [norm(value) for value in names(node)]
        if any((value in wanted) if exact else any(w in value for w in wanted) for value in values):
            return node
    return None


def wait_for(ctx, predicate, timeout=8, message='expected visible UI did not appear'):
    '''Poll fresh observations until the predicate returns something true; there is no cache across input.'''
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate(nodes(ctx))
        if value:
            return value
        time.sleep(.1)
    raise AssertionError(message)


def descendants(items, ref):
    inside, result = {ref}, []
    for node in items:
        if node.get('ref') == ref or node.get('parent') in inside:
            inside.add(node['ref'])
            result.append(node)
    return result


def dialogs(items):
    return [n for n in items if n.get('role') in DIALOG_ROLES and 'showing' in n.get('states', ())]


def dialog_scope(items):
    '''The controls of the newest showing dialog window (empty without a dialog); a file chooser widget inside a dialog belongs to it.'''
    outer = []
    for node in dialogs(items):
        if not any(node in descendants(items, o['ref']) for o in outer):
            outer.append(node)
    return descendants(items, outer[-1]['ref']) if outer else []


def click(ctx, *labels, roles=(), dialog=False):
    def locate(items):
        scope = dialog_scope(items) if dialog else items
        return find(scope, labels, roles=roles)
    node = wait_for(ctx, locate, message='visible control ' + repr(labels) + ' was not found')
    _ui(ctx).click({'ref': node['ref']})
    return node


def accept(ctx, *buttons):
    '''Press an enabled button of the newest dialog (OK, Cancel, Close, Save, Forward ...).'''
    wanted = buttons or ('OK',)

    def ready(items):
        node = find(dialog_scope(items), wanted, roles=BUTTON_ROLES)
        return node if node is not None and 'enabled' in node.get('states', ()) else None
    node = wait_for(ctx, ready, message='dialog button ' + repr(wanted) + ' did not become enabled')
    _ui(ctx).click({'ref': node['ref']})


def fill(ctx, label, value, dialog=True):
    '''Replace the text of a labelled entry: the entry that follows the label on the same row of the dialog, else the entry right below it.'''
    def locate(items):
        scope = dialog_scope(items) if dialog else items
        direct = find(scope, (label,), roles=FIELD_ROLES)
        if direct is not None:
            return direct
        caption = find(scope, (label,), roles={'label'})
        if caption is None:
            return None
        x, y, w, h = [caption['bounds'][k] for k in ('x', 'y', 'width', 'height')]
        row = [n for n in scope if n.get('role') in FIELD_ROLES and abs(n['bounds']['y'] + n['bounds']['height'] / 2 - (y + h / 2)) <= max(h, 20)
               and n['bounds']['x'] >= x + w - 2]
        if row:
            return min(row, key=lambda n: n['bounds']['x'])
        below = [n for n in scope if n.get('role') in FIELD_ROLES and 0 <= n['bounds']['y'] - (y + h) <= 30 and abs(n['bounds']['x'] - x) <= 40]
        return min(below, key=lambda n: n['bounds']['y']) if below else None
    node = wait_for(ctx, locate, message='field ' + repr(label) + ' was not found')
    _ui(ctx).fill({'ref': node['ref']}, value)
    return node


def key(ctx, chord, pause=.3):
    _ui(ctx).press(chord)
    time.sleep(pause)


def type_text(ctx, value, pause=.3):
    _ui(ctx).type(value)
    time.sleep(pause)


def menu(ctx, *labels):
    '''Run a menu bar command: click its menu, then each item in turn (File, Export; Insert, Image ...).'''
    if len(labels) < 2:
        raise ValueError('menu needs a menu and an item')
    ui = _ui(ctx)
    for _ in range(3):
        ui.press('Escape')
    top = wait_for(ctx, lambda items: find(items, labels[:1], roles={'menu'}), message='menu ' + repr(labels[0]) + ' was not found')
    ui.click({'ref': top['ref']})
    clicked = {top['ref']}
    for label in labels[1:]:
        # An item may carry the name of its menu (Search, Search...): skip what was clicked and prefer items to sub menus.
        def locate(items, label=label):
            rest = [n for n in items if n.get('ref') not in clicked]
            return find(rest, (label,), roles=ITEM_ROLES) or find(rest, (label,), roles={'menu'})
        item = wait_for(ctx, locate, message='menu item ' + repr(label) + ' was not found')
        ui.click({'ref': item['ref']})
        clicked.add(item['ref'])
        ui.wait(.15)
    time.sleep(.2)


def wait_idle(ctx, timeout=12):
    '''Wait until the editor can take another action: no dialog or open menu, a main window and an editable page text.'''
    def idle(items):
        if dialogs(items) or any(n.get('role') in ITEM_ROLES for n in items):
            return False
        if not any(n.get('role') in ('frame', 'window') for n in items):
            return False
        if any('busy' in n.get('states', ()) for n in items):
            return False
        return any(n.get('role') == 'text' and 'editable' in n.get('states', ()) for n in items)
    return wait_for(ctx, idle, timeout=timeout, message='the editor remained busy after the user action')


def chooser_path(ctx, path):
    '''Enter an absolute path in the location field of a file dialog and read the field back (bounded retyping).'''
    requested, last = str(path), ()
    for _ in range(3):
        key(ctx, 'Control+L', .1)
        key(ctx, 'Control+A', .1)
        key(ctx, 'BackSpace', .1)
        type_text(ctx, requested, .2)
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            entries = [n for n in dialog_scope(nodes(ctx)) if n.get('role') in ('text', 'entry') and 'editable' in n.get('states', ())]
            last = tuple(str(n.get('text') or '') for n in entries)
            if requested in last:
                return
            time.sleep(.2)
    raise AssertionError('the visible file dialog path differs from the requested path: ' + repr(last))


def files_dialog(ctx, path, *buttons):
    '''Complete an open or save dialog: type the path and press the affirmative button.'''
    wait_for(ctx, dialogs, message='the file dialog did not appear')
    chooser_path(ctx, path)
    key(ctx, 'Tab', .1)
    accept(ctx, *(buttons or ('Save', 'Open', 'Select', 'OK')))
    wait_for(ctx, lambda items: not dialogs(items), message='the file dialog did not close')


__all__ = ['norm', 'nodes', 'find', 'wait_for', 'dialogs', 'dialog_scope', 'click', 'accept', 'fill', 'key', 'type_text', 'menu',
           'wait_idle', 'chooser_path', 'files_dialog']
