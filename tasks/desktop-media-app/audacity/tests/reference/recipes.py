"""Pinned-standard GUI implementation of the reviewed functional goals (record only).

These deterministic drivers operate the real Audacity 2.4.2 through the
black-box runtime's own desktop operations (the ones the model and the
evaluator have): menus, dialogs, file choosers and keyboard and, where the
product exposes no accessible object (track control panel, label text,
preferences tree), positions of its own layout. They never touch a candidate
and are not the candidate's frontend contract.
"""
import time

CHOOSER = 'file chooser'
WINDOWS = ('frame', 'window', 'dialog', 'alert', CHOOSER)
# Layout of the maximized 1440x900 main window (used where the product exposes no object).
TRACK_TOP = 164          # first track's vertical ruler top
TRACK_HEIGHT = 150       # default height of a mono wave track
WAVE_LEFT, WAVE_RIGHT = 134, 1425   # x of 0 s and of the end of a 1.0 s project after zoom-to-fit
LABEL_TEXT_BELOW = 163   # label text row of a label track below one audio track, from that track's top
SELECTION = {'Start': (330, 861), 'End': (485, 861)}
# Where the pointer rests before evidence is captured: empty track area, no tooltip.
NEUTRAL = (1000, 800)


# -- runtime operations ------------------------------------------------------------------------------------
def act(ctx, op, **fields):
    return ctx.broker.call({'op': op, **fields})


def snapshot(ctx):
    return ctx.broker.call({'op': 'observe', 'tree': True})


def nodes(snap):
    return snap.get('nodes', [])


def click_at(ctx, x, y, count=1):
    act(ctx, 'click', x=int(x), y=int(y), **({'click_count': count} if count != 1 else {}))


def click_node(ctx, node):
    act(ctx, 'click', target={'ref': node['ref']})


def press(ctx, key):
    act(ctx, 'press', key=key)


def type_text(ctx, text):
    act(ctx, 'type', value=text)


def wait(seconds):
    time.sleep(min(float(seconds), 5))


def menu(ctx, *labels):
    """Open menus and choose an item by its visible labels (the accessible default action, as a user's click)."""
    for label in labels:
        deadline = time.monotonic()+5
        last = None
        while time.monotonic() < deadline:
            try:
                act(ctx, 'activate', target={'name': label})
                break
            except Exception as exc:
                last = exc
                time.sleep(.15)
        else:
            raise AssertionError(f'visible menu {label} unavailable: {last}')
        wait(.1)


# -- observation helpers -----------------------------------------------------------------------------------
# Waiting uses the window list (windows) and clicks use object targets, which the runtime resolves privately;
# a public observe happens only where geometry or refs are needed, once the window it reads is open, so a
# record makes the same observations every time.
def window_titles(ctx):
    return [str(w.get('title', '')) for w in ctx.broker.call({'op': 'windows'}).get('windows', [])]


def wait_until(predicate, seconds=10, message='expected visible state was not reached'):
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.15)
    raise AssertionError(message)


def wait_window(ctx, title, seconds=10):
    wait_until(lambda: any(title.casefold() in t.casefold() for t in window_titles(ctx)), seconds, title+' did not open')
    wait(.5)


def wait_closed(ctx, title, seconds=20):
    wait_until(lambda: all(title.casefold() not in t.casefold() for t in window_titles(ctx)), seconds,
               f'{title} did not close')


def wait_extra_window(ctx, seconds=8, message='no dialog opened'):
    """A dialog or file chooser opened over the single project window."""
    wait_until(lambda: len(window_titles(ctx)) >= 2, seconds, message)
    wait(.5)


def wait_single_window(ctx, seconds=15, message='a dialog did not close'):
    wait_until(lambda: len(window_titles(ctx)) == 1, seconds, message)


def chooser_open(snap):
    return any(node.get('role') == CHOOSER for node in nodes(snap))


def window(snap, title):
    found = [n for n in nodes(snap) if n.get('role') in WINDOWS and title.casefold() in str(n.get('name', '')).casefold()]
    assert found, f'{title} window was not visible'
    return found[-1]


def dialog_nodes(snap, title):
    ref = window(snap, title)['ref']
    return [node for node in nodes(snap) if node.get('window') == ref]


def chooser_nodes(snap):
    """Nodes inside the open file chooser (its dialog and any chooser widget nested in it)."""
    by_ref = {n.get('ref'): n for n in nodes(snap)}

    def inside(node):
        seen = set()
        while node is not None and node.get('ref') not in seen:
            if node.get('role') == CHOOSER:
                return True
            seen.add(node.get('ref'))
            node = by_ref.get(node.get('parent'))
        return False
    return [node for node in nodes(snap) if inside(node)]


def editable(node):
    return node.get('role') in ('text', 'entry') and 'editable' in node.get('states', [])


def center(node):
    x, y, w, h = node['bounds']
    return x+w//2, y+h//2


def labelled_text(snap, title, label):
    candidates = dialog_nodes(snap, title)
    targets = [n for n in candidates if editable(n)]
    labels = [n for n in candidates if n.get('role') == 'label' and label.casefold() in str(n.get('name', n.get('text', ''))).casefold()]
    assert labels and targets, f'{title} field {label} unavailable'
    ax, ay, aw, ah = labels[0]['bounds']

    def distance(node):
        x, y, w, h = node['bounds']
        return abs((y+h/2)-(ay+ah/2))*10+abs(x-(ax+aw))
    return min(targets, key=distance)


def fill_node(ctx, node, value):
    act(ctx, 'fill', target={'ref': node['ref']}, value=str(value))


def click_button(ctx, name, seconds=8):
    """Click a push button by its name (the runtime resolves it in its current window set)."""
    deadline = time.monotonic()+seconds
    while True:
        try:
            act(ctx, 'click', target={'role': 'button', 'name': name})
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise AssertionError(f'button {name} unavailable: {exc}') from None
            time.sleep(.2)


def acknowledge(ctx, titles, seconds=6):
    """Confirm product messages (for example an orphan-file notice) with their default choice."""
    deadline = time.monotonic()+seconds
    while time.monotonic() < deadline:
        hit = [t for t in window_titles(ctx) if any(k.casefold() in t.casefold() for k in titles)]
        if hit:
            wait(.5)
            if 'orphan' in hit[0].casefold():
                act(ctx, 'click', target={'name': 'Continue without deleting; ignore the extra files this session',
                                          'role': 'radio button'})
            click_button(ctx, 'OK')
            wait_closed(ctx, hit[0])
            return True
        time.sleep(.2)
    return False


def written(ctx, document):
    """The product wrote this document into the runtime's document areas (seen by list_files)."""
    name = document.rsplit('/', 1)[-1]
    return any(item.get('filename') == name for item in ctx.broker.call({'op': 'list_files'}).get('downloads', []))


# -- goal steps --------------------------------------------------------------------------------------------
def open_file(ctx, step):
    if step.get('via') == 'import':
        menu(ctx, 'File', 'Import', 'Audio...')
    else:
        menu(ctx, 'File', 'Open...')
    wait_extra_window(ctx, 8, 'Open/Import did not show a file chooser')
    press(ctx, 'Control+l')
    wait(.3)
    type_text(ctx, step['file'])
    press(ctx, 'Return')
    wait(.4)
    if step.get('expect_error'):
        wait_window(ctx, step['expect_error'], 15)
        if step.get('leave_open'):
            wait(.4)
            return
        click_button(ctx, 'OK')
        wait_closed(ctx, step['expect_error'])
    if step.get('dismiss'):
        acknowledge(ctx, step['dismiss'])
    wait_single_window(ctx, 15, 'file chooser did not complete the operation')
    wait(.8)


def choose_format(ctx, combo, value):
    """Choose the file type in the chooser's file-type list; the list scrolls when the item is below the screen."""
    if combo.get('name') == value:
        return
    click_node(ctx, combo)
    wait(.5)
    x, y = center(combo)
    for _ in range(10):
        try:
            act(ctx, 'click', target={'role': 'menu item', 'name': value})
            wait(.5)
            return
        except Exception:
            # The list opens over its combo box; turn the wheel there to bring lower items on screen.
            act(ctx, 'scroll', x=x, y=y, delta_y=300)
            wait(.3)
    raise AssertionError(f'file type {value} was not reachable in the list')


def chooser_save(ctx, document, fmt=None):
    """Enter a document path in a visible save chooser and confirm; acknowledge follow-up product dialogs."""
    wait_extra_window(ctx, 8, 'save chooser was not visible')
    inside = chooser_nodes(snapshot(ctx))
    if fmt:
        combo = max((n for n in inside if n.get('role') == 'combo box'), key=lambda n: n['bounds'][1])
        choose_format(ctx, combo, fmt)
    entries = [n for n in inside if editable(n) and str(n.get('name', '')).rstrip(':').casefold() != 'search']
    assert entries, 'save chooser has no filename entry'
    fill_node(ctx, entries[0], document)
    press(ctx, 'Return')
    deadline = time.monotonic()+30
    while time.monotonic() < deadline:
        titles = window_titles(ctx)
        metadata = [t for t in titles if 'metadata' in t.casefold()]
        if metadata:
            wait(.5)
            click_button(ctx, 'OK')
            wait_closed(ctx, metadata[0])
        elif len(titles) == 1 and written(ctx, document):
            return
        time.sleep(.25)
    raise AssertionError('save/export did not write '+document)


def edit_menu_history(ctx, prefix):
    """Edit > Undo/Redo: the item's name carries the action (for example "Undo Amplify")."""
    menu(ctx, 'Edit')
    wait(.3)
    act(ctx, 'activate', target={'role': 'menu item', 'name': prefix, 'exact': False})
    wait(.4)


def time_digits(seconds):
    milliseconds = round(seconds*1000)
    whole, ms = divmod(milliseconds, 1000)
    minutes, sec = divmod(whole, 60)
    hours, minute = divmod(minutes, 60)
    return f'{hours:02d}{minute:02d}{sec:02d}{ms:03d}'


def scripting(ctx):
    return ctx.episode.get('scripting', True)


def boxes(ctx):
    return ctx.state['c'].info('Boxes') if scripting(ctx) else []


def selection_toolbar(ctx, start, end):
    """Selection toolbar Start/End time controls (the reference's custom digit fields)."""
    rows = boxes(ctx)
    for label, value in (('Start', start), ('End', end)):
        x, y = SELECTION[label]
        box = next((r['box'] for r in rows if r.get('label') == label), None)
        if box:
            x, y = (box[0]+box[2])//2, (box[1]+box[3])//2
        click_at(ctx, x, y)
        press(ctx, 'Home')
        type_text(ctx, time_digits(value))
        press(ctx, 'Return')
        wait(.2)


def track_top(ctx, index):
    """Top of a wave track's controls, from the public Boxes layout when scripting is available."""
    if scripting(ctx):
        c = ctx.state['c']
        tracks = c.info('Tracks')
        rulers = sorted(box['box'][1] for box in c.info('Boxes') if box.get('label') == 'VRuler')
        position = 0
        for i, track in enumerate(tracks):
            if i == index:
                assert track.get('kind') == 'wave' and position < len(rulers), 'track controls unavailable'
                return rulers[position]
            if track.get('kind') == 'wave':
                position += int(track.get('channels', 1))
    return TRACK_TOP+TRACK_HEIGHT*index


def dialog(ctx, step):
    menu(ctx, *step['menu'])
    wait_window(ctx, step['title'])
    snap = snapshot(ctx) if step.get('fields') or step.get('choices') else None
    for label, value in step.get('fields', []):
        fill_node(ctx, labelled_text(snap, step['title'], label), value)
        press(ctx, 'Tab')
    for label, value in step.get('choices', []):
        choose(ctx, snap, step['title'], label, value)
    buttons = step.get('button', 'OK')
    for button in ([buttons] if isinstance(buttons, str) else buttons):
        # A realtime-capable effect applies with Apply and stays open until Close.
        click_button(ctx, button)
        wait(1)
    wait_closed(ctx, step['title'], step.get('seconds', 30))
    wait(.5)


def choose(ctx, snap, title, label, value):
    """Select a combo-box entry next to a visible label."""
    candidates = dialog_nodes(snap, title)
    labels = [n for n in candidates if n.get('role') == 'label' and label.casefold() in str(n.get('name', '')).casefold()]
    combos = [n for n in candidates if n.get('role') == 'combo box']
    assert labels and combos, f'{title} choice {label} unavailable'
    ax, ay = labels[0]['bounds'][:2]
    combo = min(combos, key=lambda n: abs(n['bounds'][1]-ay)*10+abs(n['bounds'][0]-ax))
    if combo.get('name') == value:
        return
    click_node(ctx, combo)
    wait(.4)
    act(ctx, 'click', target={'name': value, 'role': 'menu item'})
    wait(.3)


def text_dialog(ctx, title, value):
    wait_window(ctx, title)
    fields = [n for n in dialog_nodes(snapshot(ctx), title) if editable(n)]
    assert fields, title+' has no text field'
    fill_node(ctx, fields[0], value)
    click_button(ctx, 'OK')
    wait_closed(ctx, title)
    wait(.4)


def preference(ctx, step):
    menu(ctx, 'Edit', 'Preferences...')
    wait_window(ctx, 'Preferences')
    x, y = window(snapshot(ctx), 'Preferences')['bounds'][:2]
    # The category tree is pixel-only; its rows sit at fixed offsets in the dialog.
    rows = {'Tracks': (54, 158)}
    dx, dy = rows[step['page']]
    click_at(ctx, x+dx, y+dy)
    wait_window(ctx, 'Preferences: '+step['page'])
    fill_node(ctx, labelled_text(snapshot(ctx), 'Preferences', step['label']), step['value'])
    click_button(ctx, step.get('button', 'OK'))
    wait_closed(ctx, 'Preferences')
    wait(.4)


def execute(ctx, checkpoint):
    for step in checkpoint['recipe']:
        op = step['op']
        if op == 'open':
            open_file(ctx, step)
        elif op == 'menu':
            menu(ctx, *step['path'])
            wait(step.get('wait', .6))
        elif op == 'undo':
            edit_menu_history(ctx, 'Undo')
        elif op == 'redo':
            edit_menu_history(ctx, 'Redo')
        elif op == 'press':
            press(ctx, step['key'])
            wait(.3)
        elif op == 'dialog':
            dialog(ctx, step)
        elif op == 'fit':
            # View > Track Size > Fit to Width shows the whole project.
            press(ctx, 'Control+f')
            wait(.6)
        elif op == 'export':
            menu(ctx, *step.get('menu', ('File', 'Export', 'Export as WAV')))
            chooser_save(ctx, step['file'], step.get('format'))
            wait(.5)
        elif op == 'save-project':
            menu(ctx, 'File', 'Save Project', 'Save Project As...')
            chooser_save(ctx, step['file'])
            wait(.8)
        elif op == 'label':
            menu(ctx, 'Edit', 'Labels', 'Add Label at Selection')
            wait(.4)
            type_text(ctx, step['text'])
            press(ctx, 'Return')
            wait(.4)
        elif op == 'label-edit':
            x = WAVE_LEFT+round(step['at']*(WAVE_RIGHT-WAVE_LEFT))+60
            click_at(ctx, x, track_top(ctx, 0)+LABEL_TEXT_BELOW)
            wait(.4)
            press(ctx, 'End')
            for _ in step['old']:
                press(ctx, 'BackSpace')
            type_text(ctx, step['text'])
            press(ctx, 'Return')
            wait(.4)
        elif op == 'selection':
            selection_toolbar(ctx, step['start'], step['end'])
            wait(.3)
        elif op == 'project-rate':
            # The rate combo's list; typing into its text keeps the old digits.
            snap = snapshot(ctx)
            field = next(n for n in nodes(snap) if n.get('role') == 'text' and 'editable' in n.get('states', [])
                         and str(n.get('text', '')).isdigit() and n['bounds'][1] > 600)
            combo = next(n for n in nodes(snap) if n.get('role') == 'combo box' and n['bounds'][0] <= field['bounds'][0]
                         and abs(n['bounds'][1]-field['bounds'][1]) < 8)
            x, y, w, h = combo['bounds']
            click_at(ctx, x+w-10, y+h//2)
            wait(.6)
            act(ctx, 'click', target={'name': step['value'], 'role': 'menu item'})
            wait(.5)
            assert any(n.get('text') == step['value'] for n in nodes(snapshot(ctx)) if n.get('role') == 'text'), \
                'project rate not set'
        elif op == 'track-name':
            top = track_top(ctx, step['track'])
            click_at(ctx, 55, top+7)
            wait(.8)
            act(ctx, 'click', target={'name': 'Name...', 'role': 'menu item'})
            text_dialog(ctx, 'Set Track Name', step['text'])
        elif op == 'track-close':
            top = track_top(ctx, step['track'])
            click_at(ctx, 16, top+8)
            wait(.6)
        elif op == 'track-button':
            top = track_top(ctx, step['track'])
            click_at(ctx, {'Mute': 30, 'Solo': 77}[step['button']], top+25)
            wait(.5)
        elif op == 'track-gain':
            top = track_top(ctx, step['track'])
            click_at(ctx, 54, top+51, count=2)
            text_dialog(ctx, 'Gain', step['value'])
        elif op == 'preference':
            preference(ctx, step)
        elif op == 'cancel-chooser':
            menu(ctx, *step['menu'])
            wait_extra_window(ctx, 8, 'file chooser was not visible')
            click_button(ctx, 'Cancel')
            wait_single_window(ctx, 8, 'Cancel did not close the chooser')
        elif op == 'wait':
            wait(step.get('seconds', 1))
        else:
            raise ValueError('unknown reference operation '+op)
    verify(ctx, checkpoint)
    # Evidence without a tooltip over the controls the acceptance names.
    act(ctx, 'move', x=NEUTRAL[0], y=NEUTRAL[1])
    wait(.6)


def verify(ctx, checkpoint):
    """The checkpoint's expected visible state: only the project window (or the message the goal leaves open)."""
    titled = [t for t in window_titles(ctx) if t]
    if any(step.get('leave_open') for step in checkpoint['recipe']):
        assert len(titled) == 2, 'the expected message window is not the only extra window: '+str(titled)
    else:
        assert len(titled) == 1, 'a dialog remained open after the reference recipe: '+str(titled)
    if not checkpoint.get('visible'):
        return
    snap = snapshot(ctx)
    for text in checkpoint.get('visible', []):
        assert any(text in t for t in titled) or \
            any(text in str(n.get('name', ''))+str(n.get('text', '')) for n in nodes(snap)), \
            f'expected visible text {text!r} is absent'
