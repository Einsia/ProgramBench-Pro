"""Pinned-standard GUI implementation of the reviewed functional goals (record only).

These deterministic drivers operate the real Hydrogen 1.2.7 through the black-box runtime's own desktop operations
(the ones the model and the evaluator have): menus, dialogs, file choosers, the keyboard and, where the product
exposes no accessible object (the pattern and song grids, context menus, the timeline ruler), positions of its own
layout in the maximized 1440x900 main window. They never touch a candidate and are not the candidate's frontend
contract.
"""
import time

# Layout of the maximized main window (where the product exposes no object).
ROW_Y0, ROW_H = 450, 21          # centre of the first instrument row of the pattern editor, row height
GRID_X0, TICK_PX = 203, 3        # x of tick 0 in the pattern editor grid, pixels per tick (48 ticks a quarter)
NAME_X, MUTE_X, SOLO_X = 60, 155, 173
PAT_Y0, PAT_H = 155, 18          # centre of the first pattern row of the song editor, row height
BAR_X0, BAR_W = 211, 16          # centre of bar 1 in the song editor grid, pixels per bar
RULER_Y = {'tempo': 104, 'tag': 115}
# Where the pointer rests before evidence is captured: empty editor area, no tooltip.
NEUTRAL = (950, 640)
KNOB_SECONDS = 2.3               # typed knob values are taken when no key follows within two seconds
OPEN_WINDOWS = ('Mixer', 'Playlist Browser')


# -- runtime operations ------------------------------------------------------------------------------------
def act(ctx, op, **fields):
    return ctx.broker.call({'op': op, **fields})


def snapshot(ctx):
    return ctx.broker.call({'op': 'observe', 'tree': True})


def nodes(snap):
    return snap.get('nodes', [])


def click_at(ctx, x, y, count=1, button='left'):
    extra = {'click_count': count} if count != 1 else {}
    if button != 'left':
        extra['button'] = button
    act(ctx, 'click', x=int(x), y=int(y), **extra)


def click_node(ctx, node, count=1):
    x, y = center(node)
    if count == 1:
        act(ctx, 'click', target={'ref': node['ref']})
    else:
        click_at(ctx, x, y, count)


def press(ctx, key):
    act(ctx, 'press', key=key)


def type_text(ctx, text):
    act(ctx, 'type', value=text)


def wait(seconds):
    time.sleep(min(float(seconds), 5))


def retry(action, message, seconds=6):
    deadline = time.monotonic() + seconds
    while True:
        try:
            return action()
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise AssertionError(f'{message}: {exc}') from None
            time.sleep(0.2)


def menu(ctx, *labels):
    """Open menus and choose an item by its visible labels (an item named like its menu is the second match)."""
    for i, label in enumerate(labels):
        target = {'role': 'menu item', 'name': label, **({'nth': 1} if label in labels[:i] else {})}
        retry(lambda: act(ctx, 'click', target=target), f'menu {label} unavailable', 5)
        wait(0.4)


# -- observation helpers -----------------------------------------------------------------------------------
def window_titles(ctx):
    return [str(w.get('title', '')) for w in ctx.broker.call({'op': 'windows'}).get('windows', [])]


def wait_until(predicate, seconds=10, message='expected visible state was not reached'):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.15)
    raise AssertionError(message)


def has_window(ctx, title):
    """A window with this title (dialogs titled "Hydrogen" are not the main window "Hydrogen 1.2.7 - ...")."""
    return any(t.startswith(title) and not t.startswith('Hydrogen 1.2.7') for t in window_titles(ctx))


def wait_window(ctx, title, seconds=10):
    wait_until(lambda: has_window(ctx, title), seconds, title + ' did not open')
    wait(0.5)


def wait_closed(ctx, title, seconds=20):
    wait_until(lambda: not has_window(ctx, title), seconds, title + ' did not close')
    wait(0.3)


def window(snap, title):
    found = [n for n in nodes(snap) if n.get('parent') is None and str(n.get('name', '')).startswith(title)]
    assert found, f'{title} window was not visible'
    return found[-1]


def window_nodes(snap, title):
    """The nodes of one top-level window (by the observation's window field, or by the parent chain for windows
    the observation does not mark, such as the mixer)."""
    ref = window(snap, title)['ref']
    marked = [node for node in nodes(snap) if node.get('window') == ref]
    if marked:
        return marked
    parents = {node['ref']: node.get('parent') for node in nodes(snap)}

    def inside(node):
        seen, current = set(), node.get('parent')
        while current is not None and current not in seen:
            if current == ref:
                return True
            seen.add(current)
            current = parents.get(current)
        return False
    return [node for node in nodes(snap) if inside(node)]


def center(node):
    x, y, w, h = node['bounds']
    return x + w // 2, y + h // 2


def editable(node):
    return node.get('role') in ('text', 'entry') and 'editable' in node.get('states', []) and \
        'disabled' not in node.get('states', [])


def editable_texts(members):
    return sorted((n for n in members if editable(n)), key=lambda n: (n['bounds'][1], n['bounds'][0]))


def label_node(members, label):
    labels = [n for n in members if n.get('role') == 'label' and str(n.get('name', '')).strip().rstrip(':') ==
              label.rstrip(':')]
    assert labels, f'label {label} is not visible'
    return labels[0]


def near(members, label, roles, side=None):
    """The control of one of the roles closest to a label; side ('left', 'right', 'above', 'below') says where the
    control sits relative to its label."""
    anchor = label_node(members, label)
    lx, ly, lw, lh = anchor['bounds']
    ax, ay = center(anchor)
    candidates = [n for n in members if n.get('role') in roles and n is not anchor]
    if side == 'left':
        candidates = [n for n in candidates if n['bounds'][0] + n['bounds'][2] <= lx + 4 and abs(center(n)[1] - ay) < 12]
    elif side == 'right':
        candidates = [n for n in candidates if n['bounds'][0] >= lx + lw - 4 and abs(center(n)[1] - ay) < 12]
    elif side == 'above':
        candidates = [n for n in candidates if n['bounds'][1] + n['bounds'][3] <= ly + 4]
    elif side == 'below':
        candidates = [n for n in candidates if n['bounds'][1] >= ly + lh - 4]
    assert candidates, f'no {roles} near {label}'

    def distance(node):
        x, y = center(node)
        return abs(x - ax) + abs(y - ay)
    return min(candidates, key=distance)


def described(members, label):
    """A knob, fader or other drawn control whose accessible description starts with the label."""
    found = [n for n in members if str(n.get('description', '')).startswith(label)]
    assert found, f'control {label} is not visible'
    return found[0]


def fill_node(ctx, node, value):
    act(ctx, 'fill', target={'ref': node['ref']}, value=str(value))
    wait(0.2)


def click_button(ctx, name, seconds=8):
    retry(lambda: act(ctx, 'click', target={'role': 'push button', 'name': name}), f'button {name} unavailable',
          seconds)
    wait(0.4)


def written(ctx, document):
    """The product wrote this document into the runtime's document areas (seen by list_files)."""
    name = document.rsplit('/', 1)[-1]
    return any(item.get('filename') == name for item in ctx.broker.call({'op': 'list_files'}).get('downloads', []))


def main_title(ctx):
    return next((t for t in window_titles(ctx) if t.startswith('Hydrogen 1.2.7')), '')


# -- goal steps --------------------------------------------------------------------------------------------
def file_name_fields(ctx):
    return [n for n in nodes(snapshot(ctx)) if editable(n) and str(n.get('name', '')).rstrip(':') == 'File name']


def chooser(ctx, document, save):
    """A file dialog: type the document path in its File name field and confirm with Return."""
    fields = []

    def opened():
        fields[:] = file_name_fields(ctx)
        return bool(fields)
    wait_until(opened, 10, 'the file dialog did not open')
    wait(0.4)
    fill_node(ctx, fields[-1], document)
    press(ctx, 'Return')
    wait_until(lambda: not file_name_fields(ctx), 20, 'the file dialog did not complete')
    if save:
        wait_until(lambda: written(ctx, document), 20, document + ' was not written')
    wait(0.8)


def dialog(ctx, step):
    title = step['title']
    wait_window(ctx, title)
    members = window_nodes(snapshot(ctx), title)
    texts = editable_texts(members)
    for label, value in step.get('fields', []):
        target = texts[label] if isinstance(label, int) else near(members, label, ('text', 'entry'))
        fill_node(ctx, target, value)
    for label, value in step.get('combos', []):
        combo = near(members, label, ('combo box',), 'below')
        choose(ctx, combo, value)
    click_button(ctx, step.get('button', 'OK'))
    wait_closed(ctx, title)


def choose(ctx, combo, value):
    """Open a combo box and click the entry (the popup is as wide as the combo box; its entries report a wider
    width, so the click uses the combo box's centre line)."""
    if combo.get('name') == value:
        return
    click_node(ctx, combo)
    wait(0.6)
    cx, cy = center(combo)
    items = [n for n in nodes(snapshot(ctx)) if n.get('role') == 'list item' and n.get('name') == value
             and n['bounds'][1] >= 0 and abs(n['bounds'][0] - combo['bounds'][0]) < 12]
    assert items, f'choice {value} unavailable'
    item = min(items, key=lambda n: abs(center(n)[1] - cy))
    click_at(ctx, cx, center(item)[1])
    wait(0.5)
    after = [n for n in nodes(snapshot(ctx)) if n.get('role') == 'combo box' and n['bounds'][:2] == combo['bounds'][:2]]
    assert after and after[0].get('name') == value, f'the combo box did not take {value}'


def knob(ctx, step):
    """Drawn knobs and faders take a typed value after a click (within two seconds)."""
    control = described(nodes(snapshot(ctx)), step['label'])
    x, y = center(control)
    click_at(ctx, x, y)
    type_text(ctx, step['value'])
    wait(KNOB_SECONDS)


def export_song(ctx, step):
    wait_window(ctx, 'Export song')
    members = window_nodes(snapshot(ctx), 'Export song')
    fill_node(ctx, editable_texts(members)[0], step['file'])
    for label, key in (('Format:', 'format'), ('Samplerate in Hz:', 'rate'), ('SampleDepth in Bit:', 'depth'),
                       ('Modus:', 'mode')):
        if step.get(key):
            members = window_nodes(snapshot(ctx), 'Export song')
            choose(ctx, near(members, label, ('combo box',), 'right'), step[key])
    click_button(ctx, 'Export')
    finish_export(ctx, 'Export song', step['file'], step.get('mode') == 'Export to separate tracks')


def outputs(ctx):
    return {item.get('path'): item.get('size') for item in ctx.broker.call({'op': 'list_files'}).get('downloads', [])}


def finish_export(ctx, title, document, tracks=False):
    """Acknowledge license notices; the export is done when the written files stop changing. The dialog stays open
    after an export: close it."""
    deadline = time.monotonic() + 90
    stem = document.rsplit('/', 1)[-1].rsplit('.', 1)[0]
    last, since = None, time.monotonic()
    while time.monotonic() < deadline:
        if acknowledge(ctx):
            continue
        files = {p: size for p, size in outputs(ctx).items() if p and p.rsplit('/', 1)[-1].startswith(stem)}
        if files != last:
            last, since = files, time.monotonic()
        elif files and time.monotonic() - since >= 2.0:
            if has_window(ctx, title) and title != 'Export song':
                click_button(ctx, 'Close')
                wait_closed(ctx, title)
            wait(0.5)
            return
        time.sleep(0.4)
    raise AssertionError(f'{title} did not complete')


def export_midi(ctx, step):
    wait_window(ctx, 'Export midi')
    members = window_nodes(snapshot(ctx), 'Export midi')
    fill_node(ctx, editable_texts(members)[0], step['file'])
    if step.get('mode'):
        members = window_nodes(snapshot(ctx), 'Export midi')
        choose(ctx, near(members, 'Modus:', ('combo box',), 'right'), step['mode'])
    click_button(ctx, 'Export')
    finish_export(ctx, 'Export midi', step['file'])


def import_kit(ctx, step):
    menu(ctx, 'Drumkits', 'Import')
    deadline = time.monotonic() + 15
    while not has_window(ctx, 'Sound Library import'):
        assert time.monotonic() < deadline, 'Sound Library import did not open'
        if 'Hydrogen' in window_titles(ctx):
            # The online kit list cannot be fetched offline: its message comes first.
            wait(0.3)
            click_button(ctx, 'OK')
        time.sleep(0.3)
    wait(0.5)
    click_button(ctx, 'Browse...')
    chooser(ctx, step['file'], save=False)
    click_button(ctx, 'Install')
    wait_until(lambda: 'Hydrogen' in window_titles(ctx), 20, 'the drum kit was not installed')
    wait(0.4)
    click_button(ctx, 'OK')
    wait(0.4)
    click_button(ctx, 'Close')
    wait_closed(ctx, 'Sound Library import')


def kit_dialog(ctx, step):
    wait_window(ctx, 'Open Sound Library')
    members = window_nodes(snapshot(ctx), 'Open Sound Library')
    cells = [n for n in members if n.get('role') == 'table cell' and n.get('name') == step['kit']]
    assert cells, step['kit'] + ' is not listed'
    click_node(ctx, cells[0])
    wait(0.3)
    click_button(ctx, 'Load')
    wait_closed(ctx, 'Open Sound Library', 30)
    wait(1.0)


def acknowledge(ctx):
    """Confirm a notice the product shows over its dialogs (license warnings, completion messages)."""
    titles = window_titles(ctx)
    if not any(t.startswith('License') or t == 'Hydrogen' for t in titles):
        return False
    wait(0.4)
    for name in ('Ok', 'OK'):
        try:
            act(ctx, 'click', target={'role': 'push button', 'name': name})
            break
        except Exception:
            continue
    wait(0.6)
    return True


def kit_export(ctx, step):
    wait_window(ctx, 'Export Drumkit')
    members = window_nodes(snapshot(ctx), 'Export Drumkit')
    fill_node(ctx, editable_texts(members)[0], step['folder'])
    click_button(ctx, 'Export')
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if acknowledge(ctx):
            continue
        if any(item.get('filename', '').endswith('.h2drumkit')
               for item in ctx.broker.call({'op': 'list_files'}).get('downloads', [])):
            wait(0.5)
            if acknowledge(ctx):
                continue
            # The dialog stays open after an export.
            return
        time.sleep(0.3)
    raise AssertionError('the drum kit was not exported')


def browser(ctx, step):
    wait_window(ctx, 'Audio File Browser')
    name = step['file'].rsplit('/', 1)[-1]
    members = window_nodes(snapshot(ctx), 'Audio File Browser')
    cells = [n for n in members if n.get('role') == 'table cell' and n.get('name') == name]
    assert cells, name + ' is not listed in the Audio File Browser'
    click_node(ctx, cells[0])
    wait(0.8)
    click_button(ctx, 'Open')
    wait_closed(ctx, 'Audio File Browser')
    wait(0.8)


def fill_dialog(ctx, step):
    title = 'Fill with selected pattern'
    wait_window(ctx, title)
    act(ctx, 'click', target={'role': 'radio button', 'name': step['mode']})
    members = window_nodes(snapshot(ctx), title)
    texts = editable_texts(members)
    fill_node(ctx, texts[0], step['from'])
    fill_node(ctx, texts[1], step['to'])
    click_button(ctx, 'OK')
    wait_closed(ctx, title)


def list_dialog(ctx, step):
    wait_window(ctx, step['title'])
    for item in step['items']:
        act(ctx, 'click', target={'role': 'list item', 'name': item})
        wait(0.3)
    click_button(ctx, 'OK')
    wait_closed(ctx, step['title'])


def tag(ctx, step):
    wait_window(ctx, 'Tag')
    members = window_nodes(snapshot(ctx), 'Tag')
    header = [n for n in members if n.get('role') == 'table row header' and n.get('name') == str(step['bar'])]
    assert header, f'row {step["bar"]} of the tag table is not visible'
    x, y, w, h = header[0]['bounds']
    click_at(ctx, x + w + 100, y + h // 2, count=2)
    wait(0.4)
    type_text(ctx, step['text'])
    press(ctx, 'Return')
    wait(0.5)
    if has_window(ctx, 'Tag'):
        click_button(ctx, 'Ok')
    wait_closed(ctx, 'Tag')


def mixer_strip(ctx, step):
    members = window_nodes(snapshot(ctx), 'Mixer')
    if step['control'] in ('volume', 'pan'):
        prefix = 'Volume:' if step['control'] == 'volume' else 'Pan:'
        controls = sorted((n for n in members if str(n.get('description', '')).startswith(prefix)
                           and n['bounds'][0] < 1100), key=lambda n: n['bounds'][0])
        x, y = center(controls[step['index']])
        click_at(ctx, x, y)
        type_text(ctx, step['value'])
        wait(KNOB_SECONDS)
        return
    name = 'M' if step['control'] == 'mute' else 'S'
    buttons = sorted((n for n in members if n.get('role') == 'check box' and n.get('name') == name
                      and n['bounds'][0] < 1100), key=lambda n: n['bounds'][0])
    click_node(ctx, buttons[step['index']])
    wait(0.4)


def playlist_row(ctx, step):
    members = window_nodes(snapshot(ctx), 'Playlist Browser')
    rows = sorted((n for n in members if n.get('role') in ('table cell', 'tree item') and n.get('name')
                   and n['bounds'][1] > 130), key=lambda n: (n['bounds'][1], n['bounds'][0]))
    assert rows, 'the playlist lists no song'
    lines = sorted({n['bounds'][1] for n in rows})
    first = [n for n in rows if n['bounds'][1] == lines[step['row']]][0]
    click_node(ctx, first, step.get('count', 1))
    wait(0.4)


def execute(ctx, checkpoint):
    for step in checkpoint['recipe']:
        op = step['op']
        if op == 'menu':
            menu(ctx, *step['path'])
            wait(step.get('wait', 0.6))
        elif op == 'note':
            click_at(ctx, GRID_X0 + TICK_PX * step['tick'], ROW_Y0 + ROW_H * step['row'])
            wait(0.4)
        elif op == 'cell':
            click_at(ctx, BAR_X0 + BAR_W * (step['bar'] - 1), PAT_Y0 + PAT_H * step['row'])
            wait(0.4)
        elif op == 'context':
            y = (ROW_Y0 + ROW_H * step['row']) if step['area'] == 'instrument' else (PAT_Y0 + PAT_H * step['row'])
            click_at(ctx, NAME_X, y, button='right')
            wait(0.6)
            for key in step['keys']:
                press(ctx, key)
                wait(0.25)
            wait(0.6)
        elif op == 'dialog':
            dialog(ctx, step)
        elif op == 'fill':
            if 'near' in step:
                target = near(nodes(snapshot(ctx)), step['near'], (step['role'],), step.get('side'))
                fill_node(ctx, target, step['value'])
            else:
                act(ctx, 'fill', target=step['target'], value=step['value'])
            wait(0.5)
        elif op == 'check':
            if 'near' in step:
                target = {'ref': near(nodes(snapshot(ctx)), step['near'], (step['role'],), step.get('side'))['ref']}
            else:
                target = step['target']
            act(ctx, 'check', target=target, checked=step['state'])
            wait(0.5)
        elif op == 'button':
            click_button(ctx, step['name'])
            wait(0.4)
        elif op == 'combo':
            combo = retry(lambda: next(n for n in nodes(snapshot(ctx)) if n.get('role') == 'combo box'
                                       and n.get('name') == step['target']['name']), 'combo box unavailable')
            choose(ctx, combo, step['item'])
        elif op == 'pattern-size':
            spins = sorted((n for n in nodes(snapshot(ctx)) if n.get('role') == 'spin button'
                            and 380 < n['bounds'][1] < 400 and n['bounds'][0] < 400), key=lambda n: n['bounds'][0])
            fill_node(ctx, spins[0], step['numerator'])
            wait(0.4)
            spins = sorted((n for n in nodes(snapshot(ctx)) if n.get('role') == 'spin button'
                            and 380 < n['bounds'][1] < 400 and n['bounds'][0] < 400), key=lambda n: n['bounds'][0])
            fill_node(ctx, spins[1], step['denominator'])
            wait(0.6)
        elif op == 'fill-dialog':
            fill_dialog(ctx, step)
        elif op == 'list-dialog':
            list_dialog(ctx, step)
        elif op == 'ruler':
            click_at(ctx, BAR_X0 + BAR_W * (step['bar'] - 1), RULER_Y[step['row']])
            wait(0.8)
        elif op == 'tag':
            tag(ctx, step)
        elif op == 'knob':
            knob(ctx, step)
        elif op == 'select-instrument':
            click_at(ctx, NAME_X, ROW_Y0 + ROW_H * step['row'])
            wait(0.6)
        elif op == 'row-button':
            click_at(ctx, MUTE_X if step['button'] == 'M' else SOLO_X, ROW_Y0 + ROW_H * step['row'])
            wait(0.5)
        elif op == 'browser':
            browser(ctx, step)
        elif op == 'mixer':
            if not has_window(ctx, 'Mixer'):
                act(ctx, 'click', target={'role': 'check box', 'name': 'Mixer'})
                wait_window(ctx, 'Mixer')
        elif op == 'strip':
            mixer_strip(ctx, step)
        elif op == 'kit-dialog':
            kit_dialog(ctx, step)
        elif op == 'import-kit':
            import_kit(ctx, step)
        elif op == 'kit-export':
            kit_export(ctx, step)
        elif op in ('save-dialog', 'open-dialog'):
            chooser(ctx, step['file'], op == 'save-dialog')
        elif op == 'show-file':
            wait_until(lambda: bool(file_name_fields(ctx)), 10, 'file browser did not open')
            fill_node(ctx, file_name_fields(ctx)[-1], step['file'].rsplit('/', 1)[0] + '/')
            press(ctx, 'Return')
            wait(0.7)
            name = step['file'].rsplit('/', 1)[-1]
            wait_until(lambda: any(n.get('name') == name for n in nodes(snapshot(ctx))),
                       message='the saved file is not listed')
        elif op == 'close-if-open':
            if has_window(ctx, step['title']):
                click_button(ctx, 'Close')
        elif op == 'answer':
            try:
                wait_window(ctx, step['title'], 6)
            except AssertionError:
                if step.get('optional'):
                    continue
                raise
            click_button(ctx, step['button'])
            wait(0.6)
        elif op == 'export-song':
            export_song(ctx, step)
        elif op == 'export-midi':
            export_midi(ctx, step)
        elif op == 'playlist-menu':
            act(ctx, 'click', target={'role': 'menu item', 'name': 'Playlist'})
            wait(0.5)
            act(ctx, 'click', target={'role': 'menu item', 'name': step['item']})
            wait(0.8)
        elif op == 'playlist-row':
            playlist_row(ctx, step)
        elif op == 'playlist-up':
            choices = [n for n in window_nodes(snapshot(ctx), 'Playlist Browser')
                       if n.get('role') == 'push button' and n.get('description') == 'sort']
            click_node(ctx, min(choices, key=lambda n: n['bounds'][1]))
        elif op == 'press':
            press(ctx, step['key'])
            wait(0.3)
        elif op == 'pointer':
            act(ctx, step.get('action', 'click'), **{k: v for k, v in step.items() if k not in ('op', 'action')})
            wait(0.5)
        elif op == 'sample-editor':
            sample_editor(ctx, step)
        elif op == 'kit-properties':
            wait_window(ctx, 'SoundLibrary Properties')
            act(ctx, 'maximize')
            wait(0.6)
            texts = editable_texts(nodes(snapshot(ctx)))
            for old, new in (('empty', step['name']), ('undefined author', step['author']),
                             ('No information available.', step['info'])):
                control = next(n for n in texts if n.get('text') == old)
                fill_node(ctx, control, new)
            combo = near(nodes(snapshot(ctx)), 'Drumkit License', ('combo box',), 'right')
            choose(ctx, combo, 'CC0 (Public Domain)' if step['license'] == 'CC0' else step['license'])
            act(ctx, 'scroll', x=1431, y=820, delta_y=800)
            wait(0.5)
            act(ctx, 'click', target={'role': 'check box', 'name': 'Save'})
            wait(0.7)
            for _ in range(4):
                if not acknowledge(ctx):
                    break
            wait_closed(ctx, 'SoundLibrary Properties')
        elif op == 'wait':
            wait(step.get('seconds', 1))
        else:
            raise ValueError('unknown reference operation ' + op)
    verify(ctx, checkpoint)
    # Evidence without a tooltip over the controls the acceptance names.
    act(ctx, 'move', x=NEUTRAL[0], y=NEUTRAL[1])
    wait(0.6)


def sample_editor(ctx, step):
    title = 'SampleEditor'
    wait_window(ctx, title)
    # Preserve a valid region while typing into spin boxes that clamp on each change.
    descriptions = {'start': 'Adjust sample start frame', 'end': 'Adjust sample end & loop end frame',
                    'loop': 'Adjust sample loop begin frame', 'loops': 'loops'}
    if any(key in step for key in ('start', 'loop', 'end')):
        fill_node(ctx, described(nodes(snapshot(ctx)), descriptions['start']), 0)
    for key in ('end', 'loop', 'start', 'loops'):
        if key in step:
            fill_node(ctx, described(nodes(snapshot(ctx)), descriptions[key]), step[key])
    for key, label in (('beats', 'Sample length to beat:'), ('crispness', 'Crispness:'), ('mode', 'Loop\nmode')):
        if key in step:
            choose(ctx, near(nodes(snapshot(ctx)), label, ('combo box',), 'right'), str(step[key]))
    if 'pitch' in step:
        fill_node(ctx, described(nodes(snapshot(ctx)), 'Pitch the sample in semitones, cents'), step['pitch'])
    click_button(ctx, 'Apply Changes')
    wait(1.0)


def verify(ctx, checkpoint):
    """The checkpoint ends with the windows specified by its visible goal."""
    titled = [t for t in window_titles(ctx) if t]
    allowed = OPEN_WINDOWS + tuple(checkpoint.get('windows', []))
    extra = [t for t in titled if not t.startswith('Hydrogen 1.2.7') and not t.startswith(allowed)]
    assert not extra, 'a dialog remained open after the reference recipe: ' + str(titled)
    if not checkpoint.get('visible'):
        return
    snap = snapshot(ctx)
    for text in checkpoint.get('visible', []):
        assert any(text in t for t in titled) or \
            any(text in str(n.get('name', '')) + str(n.get('text', '')) + str(n.get('description', ''))
                for n in nodes(snap)), f'expected visible text {text!r} is absent'
