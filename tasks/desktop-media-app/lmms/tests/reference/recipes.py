'''Pinned-standard GUI implementation of the reviewed goals (record only).

These deterministic drivers operate the real LMMS 1.2.2 through the black-box runtime's own desktop operations (the
ones the model and the evaluator have): menus, the Qt file dialogs, the Tempo dialog and, where the product exposes
no accessible object (the step cells of the Beat+Bassline Editor), positions of its own layout. They never touch a
candidate and are not the candidate's frontend contract.
'''
import time

# Layout of the maximized 1440x900 main window, used where the product exposes no accessible object.
TEMPO_DISPLAY = (270, 52)
SONG_BUTTONS = (100, 125, 215, 180)    # x0, y0, x1, y1 of the Song-Editor toolbar, whose buttons add tracks
ADD = {'beat': 'Add beat/bassline', 'sample': 'Add sample-track', 'automation': 'Add automation-track'}
EDITOR_BUTTON = 'Show/hide Beat+Bassline Editor (F6)'
CELL_LEFT, CELL_WIDTH = 946, 23.4      # left edge of the first step cell of a Beat+Bassline Editor row, width of a step
ROW_TOP, ROW_HEIGHT = 191, 32          # vertical centre of the first row, distance between two rows
NEUTRAL = (1100, 700)                  # where the pointer rests before evidence is captured


def act(ctx, op, **fields):
    return ctx.broker.call({'op': op, **fields})


def snapshot(ctx):
    return ctx.broker.call({'op': 'observe', 'tree': True})


def nodes(snap):
    return snap.get('nodes', [])


def titles(ctx):
    return [str(w.get('title', '')) for w in ctx.broker.call({'op': 'windows'}).get('windows', [])]


def wait(seconds):
    time.sleep(min(float(seconds), 5))


def wait_until(predicate, seconds=10, message='expected visible state was not reached'):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError(message)


def wait_title(ctx, word, seconds=15):
    wait_until(lambda: any(word.casefold() in t.casefold() for t in titles(ctx)), seconds, word + ' did not appear')


def wait_gone(ctx, word, seconds=15):
    wait_until(lambda: all(word.casefold() not in t.casefold() for t in titles(ctx)), seconds, word + ' did not close')


def menu(ctx, top, item, tries=3):
    # A click on the menu bar right after a click elsewhere sometimes leaves the menu closed: close any menu and retry.
    for attempt in range(tries):
        act(ctx, 'click', target={'role': 'menu item', 'name': top})
        wait(1)
        try:
            act(ctx, 'click', target={'role': 'menu item', 'name': item})
            break
        except Exception:
            if attempt == tries - 1:
                raise
            act(ctx, 'press', key='Escape')
            wait(.8)
    wait(1.5)


def stem(document):
    return document.rsplit('/', 1)[-1].rsplit('.', 1)[0]


def shortcut_dialog(ctx, key, title):
    # Use the product's documented keyboard route and wait for its result before typing into a dialog.
    for attempt in range(3):
        act(ctx, 'press', key=key)
        try:
            wait_title(ctx, title, 10)
            return
        except AssertionError:
            if attempt == 2:
                raise


def written(ctx, document):
    name = document.rsplit('/', 1)[-1]
    return any(item.get('filename') == name for item in act(ctx, 'list_files').get('downloads', []))


def enter_path(ctx, word, document):
    # The Qt file dialogs take the absolute path in their File name field.
    wait_title(ctx, word)
    wait_until(lambda: any(n.get('role') == 'text' and n.get('name') == 'File name:'
                          and 'editable' in n.get('states', []) for n in nodes(snapshot(ctx))),
               message='the file name field is not ready')
    for attempt in range(4):
        act(ctx, 'fill', target={'role': 'text', 'name': 'File name:'}, value=document)
        try:
            # A moving/opening dialog can lose the focus or select-all event. Never confirm partial input.
            wait_until(lambda: any(n.get('role') == 'text' and n.get('name') == 'File name:'
                                   and n.get('text') == document for n in nodes(snapshot(ctx))),
                       seconds=3, message='the file name field did not retain the complete document path')
            break
        except AssertionError:
            if attempt == 3:
                raise
            wait(.4)
    act(ctx, 'press', key='Return')


def click_button(ctx, name, seconds=8):
    deadline = time.monotonic() + seconds
    while True:
        try:
            act(ctx, 'click', target={'role': 'button', 'name': name})
            return
        except Exception as exc:
            if time.monotonic() >= deadline:
                raise AssertionError('button ' + name + ' unavailable: ' + str(exc)) from None
            time.sleep(.2)


def save_project(ctx, step):
    shortcut_dialog(ctx, 'Control+Shift+s', 'Save Project')
    enter_path(ctx, 'Save Project', step['file'])
    wait_gone(ctx, 'Save Project', 20)
    wait_title(ctx, stem(step['file']) + ' - LMMS', 20)
    wait_until(lambda: written(ctx, step['file']), 20, 'the project file was not written')
    wait(.8)


def open_project(ctx, step):
    act(ctx, 'press', key='Control+o')
    enter_path(ctx, 'Open Project', step['file'])
    wait_gone(ctx, 'Open Project', 20)
    wait_title(ctx, stem(step['file']) + ' - LMMS', 20)
    wait(1)


def import_file(ctx, step):
    # Import has no product shortcut. Read the active popup and click its fresh
    # content-derived ref; a static name target can become stale while Qt
    # rebuilds this menu.
    for attempt in range(3):
        try:
            act(ctx, 'press', key='Escape')
            act(ctx, 'click', target={'role': 'menu item', 'name': 'File'})
            wait(.6)
            item = next(n for n in nodes(snapshot(ctx)) if n.get('role') == 'menu item' and n.get('name') == 'Import...')
            act(ctx, 'click', target={'ref': item['ref']})
            wait_title(ctx, 'Import file', 5)
            break
        except Exception:
            if attempt == 2:
                raise
            act(ctx, 'press', key='Escape')
            wait(.5)
    enter_path(ctx, 'Import file', step['file'])
    wait(.8)
    if any('Setup incomplete' in title for title in titles(ctx)):
        act(ctx, 'press', key='Return')
        wait_gone(ctx, 'Setup incomplete', 12)
    wait_until(lambda: not any("Couldn't import" in title for title in titles(ctx)), 5,
               'the imported document was rejected')


def export_midi(ctx, step):
    # LMMS 1.2.2 labels this Qt chooser "Select file for project-export..."
    # even when its file-type filter is MIDI.
    shortcut_dialog(ctx, 'Control+m', 'Select file for')
    enter_path(ctx, 'Select file for', step['file'])
    wait_gone(ctx, 'Select file for', 20)
    wait_until(lambda: written(ctx, step['file']), 20, 'the MIDI file was not written')


def tempo(ctx, step):
    # The Tempo dialog holds a spin button that the accessibility tree reports as focused but not editable:
    # select its text and type the value.
    act(ctx, 'click', x=TEMPO_DISPLAY[0], y=TEMPO_DISPLAY[1], click_count=2)
    wait_title(ctx, 'Tempo', 10)
    wait(.4)
    act(ctx, 'press', key='Control+a')
    act(ctx, 'type', value=str(step['value']))
    click_button(ctx, 'OK')
    wait_gone(ctx, 'Tempo', 10)
    wait(.6)


def add_track(ctx, step):
    # The Beat+Bassline Editor has buttons of the same names; only those of the Song-Editor toolbar add song tracks.
    name = ADD[step['kind']]
    x0, y0, x1, y1 = SONG_BUTTONS
    found = [n for n in nodes(snapshot(ctx)) if n.get('role') == 'push button' and n.get('name') == name
             and x0 <= n['bounds'][0] <= x1 and y0 <= n['bounds'][1] <= y1]
    assert found, 'the Song-Editor button ' + name + ' is not visible'
    act(ctx, 'click', target={'ref': found[0]['ref']})
    wait(1.5)


def editor_open(ctx):
    return any(n.get('name') == 'Beat selector' for n in nodes(snapshot(ctx)))


def beat_step(ctx, step):
    if not editor_open(ctx):
        act(ctx, 'click', target={'role': 'push button', 'name': EDITOR_BUTTON})
        wait_until(lambda: editor_open(ctx), 10, 'the Beat+Bassline Editor did not open')
        wait(.6)
    x = round(CELL_LEFT + CELL_WIDTH * (step['step'] + 0.5))
    y = ROW_TOP + ROW_HEIGHT * step['row']
    act(ctx, 'click', x=x, y=y)
    wait(.8)


def verify(ctx, checkpoint):
    shown = [t for t in titles(ctx) if t]
    # A step flagged leave_open leaves exactly one window of its own open as the evidence.
    expected = 1 + sum(1 for step in checkpoint.get('recipe', []) if step.get('leave_open'))
    assert len(shown) == expected, 'an unexpected window state after the reference recipe: ' + str(shown)
    if not checkpoint.get('visible'):
        return
    snap = snapshot(ctx)
    for text in checkpoint['visible']:
        assert any(text in t for t in shown) or any(text in str(n.get('name', '')) + str(n.get('text', '')) for n in nodes(snap)), \
            'expected visible text ' + repr(text) + ' is absent'


def execute(ctx, checkpoint):
    for step in checkpoint['recipe']:
        op = step['op']
        if op == 'tempo':
            tempo(ctx, step)
        elif op == 'save-project':
            save_project(ctx, step)
        elif op == 'open-project':
            open_project(ctx, step)
        elif op == 'import-file':
            import_file(ctx, step)
        elif op == 'export-midi':
            export_midi(ctx, step)
        elif op == 'add-track':
            add_track(ctx, step)
        elif op == 'beat-step':
            beat_step(ctx, step)
        elif op == 'wait':
            wait(step.get('seconds', 1))
        else:
            from reference import extra
            if op not in extra.OPS:
                raise ValueError('unknown reference operation ' + op)
            extra.OPS[op](ctx, step)
    verify(ctx, checkpoint)
    act(ctx, 'move', x=NEUTRAL[0], y=NEUTRAL[1])
    wait(.6)
