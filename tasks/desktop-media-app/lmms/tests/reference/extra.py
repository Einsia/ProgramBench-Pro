'''Further reference operations of the pinned standard (record only).

Toolbar wheels, track switches, the Instrument Plugins sidebar, clips of the Song-Editor, the instrument window of the
audio file processor and the export dialog, driven through the runtime's desktop operations like the operations of
reference/recipes.py. Positions are those of the maximized 1440x900 main window with the default project: the track
rows of the Song-Editor are 32 px apart from y 209, a bar of the song grid is 16 px wide from x 341, and the
Instrument Plugins panel lists its entries at x 150 and y 245 + 30 * index.
'''
import time

from reference import recipes as base

MASTER_VOLUME = (476, 73)
MASTER_PITCH = (532, 73)
TIME_SIGNATURE = (410, 52)
ROW_TOP, ROW_STEP = 209, 32
MUTE_X, SOLO_X = 91, 108
CLIP_X, BAR = 345, 16
PANEL_TAB = 'Instrument Plugins'
PLUGINS = ('AudioFileProcessor', 'BitInvader', 'FreeBoy', 'GIG Player', 'Kicker', 'LB302', 'Mallets', 'Monstro',
           'Nescaline', 'OpulenZ', 'Organic', 'PatMan', 'Sf2 Player', 'sfxr', 'SID', 'TripleOscillator',
           'Vibed', 'Watsyn', 'ZynAddSubFX')
ENTRY_X, ENTRY_Y0, ENTRY_STEP = 150, 245, 30
WINDOW_X = 1040    # an instrument window opens right of this x
MAX_TRACKS_BEFORE_DRAG = 5


def describe(node):
    return node.get('name') or node.get('description') or ''


def find(ctx, text, x0=0):
    for node in base.nodes(base.snapshot(ctx)):
        if describe(node) == text and node['bounds'][0] >= x0:
            return node
    return None


def wait_find(ctx, text, x0=0, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        node = find(ctx, text, x0)
        if node is not None:
            return node
        time.sleep(.3)
    raise AssertionError(text + ' is not visible')


def wheel(ctx, point, notches):
    # One notch is 100 units of delta_y; a positive count of notches turns the wheel up (the value grows).
    left = int(notches)
    while left:
        part = max(-25, min(25, left))
        base.act(ctx, 'scroll', x=point[0], y=point[1], delta_y=-100 * part)
        left -= part
        base.wait(.4)
    base.wait(.4)


def master_volume(ctx, step):
    # X11 can coalesce wheel events under load. Check the accessible value before saving or exporting.
    target = float(wait_find(ctx, 'master volume')['value']) + int(step['notches'])
    for attempt in range(6):
        value = float(wait_find(ctx, 'master volume')['value'])
        if value == target:
            return
        wheel(ctx, MASTER_VOLUME, round(target - value))
    assert float(wait_find(ctx, 'master volume')['value']) == target, 'master volume did not reach ' + str(target)


def master_pitch(ctx, step):
    wheel(ctx, MASTER_PITCH, step['notches'])


def time_signature(ctx, step):
    wheel(ctx, TIME_SIGNATURE, step['notches'])


def track_switch(ctx, step):
    x = {'mute': MUTE_X, 'solo': SOLO_X}[step['switch']]
    base.act(ctx, 'click', x=x, y=ROW_TOP + ROW_STEP * step['row'])
    base.wait(.6)


def side_tab(ctx):
    found = [n for n in base.nodes(base.snapshot(ctx)) if n.get('name') == PANEL_TAB and n.get('role') == 'check box'
             and n['bounds'][0] < 40]
    assert found, 'the Instrument Plugins tab is not visible'
    return found[0]


def panel_open(ctx):
    # The Song-Editor moves right when a sidebar panel is open.
    return any(n.get('name') == 'Song-Editor' and n['bounds'][0] > 100 for n in base.nodes(base.snapshot(ctx)))


def toggle_panel(ctx, want):
    if panel_open(ctx) != want:
        base.act(ctx, 'click', target={'ref': side_tab(ctx)['ref']})
        base.wait(1.5)
    assert panel_open(ctx) == want, 'the Instrument Plugins panel did not ' + ('open' if want else 'close')


def plugin_drag(ctx, step):
    count = int(step['tracks'])
    assert count <= MAX_TRACKS_BEFORE_DRAG, 'the drop area is below the last visible track row'
    toggle_panel(ctx, True)
    y = ENTRY_Y0 + ENTRY_STEP * PLUGINS.index(step['plugin'])
    drop = 195 + ROW_STEP * count + 10
    base.act(ctx, 'drag', x=ENTRY_X, y=y, to_x=450, to_y=drop, seconds=1.5)
    base.wait(2.5)
    toggle_panel(ctx, False)


def clip(ctx, step):
    x = CLIP_X + BAR * step.get('bar', 0)
    base.act(ctx, 'click', x=x, y=ROW_TOP + ROW_STEP * step['row'])
    base.wait(1)


def clip_sample(ctx, step):
    # A double click on a sample clip opens the Open audio file dialog.
    x = CLIP_X + 3 + BAR * step.get('bar', 0)
    # A busy Qt event loop may treat the two presses as separate clicks. Retry only
    # while the chooser is absent; opening it does not alter the clip's content.
    for attempt in range(3):
        if any('Open audio file' in title for title in base.titles(ctx)):
            break
        base.act(ctx, 'click', x=x, y=ROW_TOP + ROW_STEP * step['row'], click_count=2)
        try:
            base.wait_title(ctx, 'Open audio file', 5)
            break
        except AssertionError:
            if attempt == 2:
                raise
    base.enter_path(ctx, 'Open audio file', step['file'])
    base.wait_gone(ctx, 'Open audio file', 20)
    base.wait(1)


def open_instrument(ctx, step):
    found = [n for n in base.nodes(base.snapshot(ctx)) if n.get('name') == step['name'] and n.get('role') == 'check box'
             and 100 <= n['bounds'][0] < 700]
    assert found, 'the track ' + step['name'] + ' is not visible in the Song-Editor'
    base.act(ctx, 'click', target={'ref': found[0]['ref']})
    base.wait(2)


def afp_sample(ctx, step):
    button = wait_find(ctx, 'Open other sample', WINDOW_X)
    base.act(ctx, 'click', target={'ref': button['ref']})
    base.enter_path(ctx, 'Open audio file', step['file'])
    base.wait_gone(ctx, 'Open audio file', 20)
    base.wait(1.5)


def afp_switch(ctx, step):
    box = wait_find(ctx, step['name'], WINDOW_X)
    base.act(ctx, 'click', target={'ref': box['ref']})
    base.wait(.8)


def export(ctx, step):
    # The song needs a clip: an empty song answers with an Empty project alert and no dialog.
    base.shortcut_dialog(ctx, 'Control+e', 'project-export')
    base.enter_path(ctx, 'project-export', step['file'])
    base.wait_title(ctx, 'Export project to', 15)
    base.wait(.5)
    base.click_button(ctx, 'Start')
    base.wait_until(lambda: base.written(ctx, step['file'])
                    and not any(t.startswith(('Rendering', 'Export project')) for t in base.titles(ctx)),
                    120, 'the export did not finish')
    base.wait(1)


OPS = {'master-volume': master_volume, 'master-pitch': master_pitch, 'time-signature': time_signature,
       'track-switch': track_switch, 'plugin-drag': plugin_drag, 'clip': clip, 'clip-sample': clip_sample,
       'open-instrument': open_instrument, 'afp-sample': afp_sample, 'afp-switch': afp_switch, 'export': export}


def export_tracks(ctx, step):
    base.act(ctx, 'press', key='Control+Shift+e')
    base.wait_until(lambda: any(t.startswith(('Select directory for writing', 'Export project to')) for t in base.titles(ctx)), 15)
    if any(t.startswith('Select directory for writing') for t in base.titles(ctx)):
        field = next(n for n in base.nodes(base.snapshot(ctx)) if n.get('role') == 'text'
                     and n.get('name') in ('Directory:', 'Folder:', 'File name:'))
        base.act(ctx, 'fill', target={'ref': field['ref']}, value=step['folder'])
        base.act(ctx, 'press', key='Return')
    base.wait_title(ctx, 'Export project to', 15)
    base.click_button(ctx, 'Start')
    base.wait_until(lambda: base.written(ctx, '1_Low.wav') and base.written(ctx, '2_High.wav')
                   and not any(t.startswith(('Rendering', 'Export project')) for t in base.titles(ctx)), 120,
                   'the track exports did not finish')


def file_menu_item(ctx, text, *, substring=False):
    """Open the native File menu and return a currently visible child item."""
    def find():
        return [n for n in base.nodes(base.snapshot(ctx)) if n.get('role') == 'menu item'
                and (text.casefold() in n.get('name', '').casefold() if substring
                     else n.get('name') == text)]
    for attempt in range(3):
        base.act(ctx, 'press', key='Escape')
        base.act(ctx, 'click', target={'role': 'menu item', 'name': 'File'})
        try:
            base.wait_until(lambda: bool(find()), 5, 'the File menu item did not appear: ' + text)
            return find()[0]
        except AssertionError:
            if attempt == 2:
                raise


def new_version(ctx, step):
    item = file_menu_item(ctx, 'version', substring=True)
    base.act(ctx, 'activate', target={'ref': item['ref']})
    base.wait_until(lambda: base.written(ctx, step['file']), 30, 'the numbered project version was not written')


def default_template(ctx, step):
    base.menu(ctx, 'File', 'Save as default template')
    wait_template(ctx, 'default')


def wait_template(ctx, name):
    """Wait for the public file inventory to show a nonempty, stable template."""
    deadline = time.monotonic() + 20
    size, since = None, time.monotonic()
    while time.monotonic() < deadline:
        files = base.act(ctx, 'list_files').get('downloads', [])
        found = [item for item in files if item.get('filename') == name + '.mpt']
        current = found[-1].get('size') if found else None
        if not isinstance(current, int) or current <= 0 or current != size:
            size, since = current, time.monotonic()
        elif time.monotonic() - since >= 2:
            return
        base.wait(.4)
    raise AssertionError('the template file did not become stable: ' + name)


def from_template(ctx, step):
    def templates():
        return [n for n in base.nodes(base.snapshot(ctx)) if n.get('role') == 'menu item'
                and n.get('name') == step['name']]
    for attempt in range(3):
        item = file_menu_item(ctx, 'New from template')
        base.act(ctx, 'click', target={'ref': item['ref']})
        try:
            base.wait_until(lambda: bool(templates()), 8, 'the saved template is missing from the template menu')
            break
        except AssertionError:
            if attempt == 2:
                raise
    found = templates()
    base.act(ctx, 'activate', target={'ref': found[0]['ref']})
    base.wait(.5)
    buttons = [n for n in base.nodes(base.snapshot(ctx)) if n.get('role') in ('push button', 'button')
               and n.get('name') in ('Discard', "Don't Save", 'No')]
    if buttons:
        base.act(ctx, 'click', target={'ref': buttons[0]['ref']})
    base.wait(1)


OPS.update({'export-tracks': export_tracks, 'new-version': new_version, 'default-template': default_template,
            'from-template': from_template})


# Third batch: the piano roll, undo and redo, renaming, dropping an instrument on a track, the project notes and the
# Setup dialog. Positions come from probes 16 and 17 of the default project.
ROLL_X0, ROLL_Y0 = 102, 323          # left edge of the piano roll grid (1 px per tick), centre of the C5 row (key 60)
ROLL_CLOSE = (882, 121)
NOTES_BUTTON = 'Show/hide project notes (F10)'
NOTES_AREA = (1080, 345)
SETUP_X, SETUP_Y0, SETUP_STEP = 593, 324, 18


def pattern_open(ctx, step):
    x = CLIP_X + 4 + BAR * step.get('bar', 0)
    base.act(ctx, 'click', x=x, y=ROW_TOP + ROW_STEP * step['row'], click_count=2)
    base.wait_until(lambda: any(str(n.get('name', '')).startswith('Piano-Roll') for n in base.nodes(base.snapshot(ctx))), 10, 'the Piano Roll did not open')
    base.wait(.6)


def note(ctx, step):
    x = ROLL_X0 + step['tick'] + 6
    y = ROLL_Y0 - 12 * (step['key'] - 60)
    base.act(ctx, 'click', x=x, y=y)
    base.wait(.8)


def undo(ctx, step):
    base.act(ctx, 'press', key='Control+z')
    base.wait(.8)


def redo(ctx, step):
    base.act(ctx, 'press', key='Control+y')
    base.wait(.8)


def close_roll(ctx, step):
    base.act(ctx, 'click', x=ROLL_CLOSE[0], y=ROLL_CLOSE[1])
    base.wait(1)


def rename_track(ctx, step):
    found = [n for n in base.nodes(base.snapshot(ctx)) if n.get('name') == step['name'] and 100 <= n['bounds'][0] < 700]
    assert found, 'the track ' + step['name'] + ' is not visible in the Song-Editor'
    base.act(ctx, 'click', button='right', target={'ref': found[0]['ref']})
    base.wait(1)
    base.act(ctx, 'press', key='Control+a')
    base.act(ctx, 'type', value=step['text'])
    base.act(ctx, 'press', key='Return')
    base.wait(1.5)


def plugin_drop(ctx, step):
    toggle_panel(ctx, True)
    y = ENTRY_Y0 + ENTRY_STEP * PLUGINS.index(step['plugin'])
    base.act(ctx, 'drag', x=ENTRY_X, y=y, to_x=450, to_y=ROW_TOP + ROW_STEP * step['row'], seconds=1.5)
    base.wait(2.5)
    toggle_panel(ctx, False)


def project_notes(ctx, step):
    button = wait_find(ctx, NOTES_BUTTON)
    base.act(ctx, 'click', target={'ref': button['ref']})
    base.wait(2)
    base.act(ctx, 'click', x=NOTES_AREA[0], y=NOTES_AREA[1])
    base.wait(.5)
    base.act(ctx, 'type', value=step['text'])
    base.wait(1)


def setup_switch(ctx, step):
    base.menu(ctx, 'Edit', 'Settings')
    base.wait_title(ctx, 'Setup LMMS', 10)
    base.wait(1)
    for index in step.get('switches', []):
        base.act(ctx, 'click', x=SETUP_X, y=SETUP_Y0 + SETUP_STEP * index)
        base.wait(.6)
    base.click_button(ctx, step.get('button', 'OK'))
    base.wait(1.5)
    if any('Restart LMMS' in t for t in base.titles(ctx)):
        # The restart warning (shown after changing settings when its own switch is on) is a modal message box.
        base.act(ctx, 'press', key='Return')
        base.wait(1)
    base.wait_gone(ctx, 'Setup LMMS', 10)
    base.wait(1)


OPS.update({'pattern-open': pattern_open, 'note': note, 'undo': undo, 'redo': redo, 'close-roll': close_roll,
            'rename-track': rename_track, 'plugin-drop': plugin_drop, 'project-notes': project_notes,
            'setup-switch': setup_switch})


def focus_roll(ctx, step):
    # Click the title bar of the Piano-Roll window so that its undo and redo shortcuts act.
    base.act(ctx, 'click', x=450, y=121)
    base.wait(.6)


OPS['focus-roll'] = focus_roll


def setup_show(ctx, step):
    # Open the Setup dialog again and leave it open as the evidence of the state of its switches (a leave_open step).
    base.menu(ctx, 'Edit', 'Settings')
    base.wait_title(ctx, 'Setup LMMS', 10)
    base.wait(1.5)


OPS['setup-show'] = setup_show
