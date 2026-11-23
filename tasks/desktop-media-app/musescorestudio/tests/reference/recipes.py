'''Pinned-standard GUI implementation of the reviewed goals (record only).

These deterministic drivers operate the real MuseScore Studio 4.7.6 through the black-box runtime desktop operations (the ones the model and the evaluator have): keyboard shortcuts and positions of its own layout, because its menus, buttons and score canvas are not in the accessibility snapshot. Coordinates are those of the maximized 1440x900 window at the 100 percent page view. They never touch a candidate and are not the candidate frontend contract.
'''
import base64
import subprocess
import time

NEUTRAL = (390, 700)
FILE_MENU = (18, 33)
TOOLS_MENU = (239, 33)
FIRST_NOTE = (643, 368)
HOME = 'MuseScore Studio'
FIELDS = {'Work title': 259, 'Subtitle': 293, 'Composer': 327, 'Arranger': 361, 'Lyricist': 395, 'Translator': 429,
          'Work number': 557, 'Movement title': 591}
# Rows of the export format list that were measured on the standard.
FORMATS = {'MusicXML': 669, 'MIDI': 639, 'MEI': 729}


def act(ctx, op, **fields):
    return ctx.broker.call({'op': op, **fields})


def titles(ctx):
    return [str(w.get('title', '')) for w in act(ctx, 'windows').get('windows', [])]


def wait(seconds):
    time.sleep(min(float(seconds), 6))


def wait_until(predicate, seconds=10, message='expected visible state was not reached'):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.25)
    raise AssertionError(message)


def click_at(ctx, x, y):
    act(ctx, 'click', x=int(x), y=int(y))


def press(ctx, key, pause=.6):
    act(ctx, 'press', key=key)
    wait(pause)


def type_text(ctx, text):
    act(ctx, 'type', value=text)


def written(ctx, document):
    name = document.rsplit('/', 1)[-1]
    return any(item.get('filename') == 'outputs/' + name for item in act(ctx, 'list_files').get('downloads', []))


def open_file(ctx, step):
    press(ctx, 'Control+o', 1.5)
    wait_until(lambda: 'Open' in titles(ctx), 8, 'Open did not show a file chooser')
    press(ctx, 'Control+l', .4)
    type_text(ctx, step['file'])
    wait(.4)
    press(ctx, 'Return', .5)
    # A further score opens in a window of its own beside the open one.
    expected = sorted(step.get('windows', [step['title']]))
    wait_until(lambda: sorted(titles(ctx)) == expected, 20, 'the score did not open')
    wait(2.5)


def save_as(ctx, step):
    press(ctx, 'Control+Shift+S', 1.5)
    wait_until(lambda: 'Save score' in titles(ctx), 8, 'Save as did not show a file chooser')
    press(ctx, 'Control+a', .3)
    type_text(ctx, step['file'])
    wait(.4)
    press(ctx, 'Return', 1.0)
    wait_until(lambda: titles(ctx) == [step['title']], 20, 'the save did not complete')
    wait_until(lambda: written(ctx, step['file']), 15, 'the project was not written')
    wait(.8)


def select_note(ctx, step):
    # The viewport may finish centering the paper at either horizontal offset.
    # Locate its visible edge instead of assuming one fixed screen coordinate.
    snapshot = act(ctx, 'screenshot')
    raster = subprocess.run(['convert', 'png:-', '-depth', '8', 'rgb:-'],
                            input=base64.b64decode(snapshot['png_base64']),
                            capture_output=True, check=True, timeout=10).stdout
    width, height = 1440, 900
    assert len(raster) == width * height * 3, 'unexpected desktop screenshot dimensions'
    spans, start = [], None
    for x in range(350, width):
        offset = (700 * width + x) * 3
        white = min(raster[offset:offset + 3]) >= 240
        if white and start is None:
            start = x
        if start is not None and (not white or x == width - 1):
            end = x if not white else x + 1
            spans.append((end - start, start))
            start = None
    assert spans and max(spans)[0] > 600, 'the score paper is not visible'
    page_left = max(spans)[1]
    click_at(ctx, page_left + FIRST_NOTE[0] - 487, FIRST_NOTE[1])
    wait(.8)
    for _ in range(step.get('index', 0)):
        press(ctx, 'Right', .3)


def transpose(ctx, step):
    click_at(ctx, *TOOLS_MENU)
    wait(1.2)
    click_at(ctx, 293, 69)
    wait_until(lambda: 'Transpose' in titles(ctx), 8, 'the Transpose dialog did not open')
    wait(1.0)
    click_at(ctx, 513, 347)
    wait(.8)
    click_at(ctx, 616, 386)
    wait(1.0)
    for _ in range(step['interval']):
        press(ctx, 'Down', .12)
    press(ctx, 'Return', .8)
    if step.get('direction') == 'down':
        click_at(ctx, 733, 409)
        wait(.5)
    if step.get('keysig', True) is False:
        click_at(ctx, 513, 448)
        wait(.4)
    click_at(ctx, 882, 723)
    wait_until(lambda: 'Transpose' not in titles(ctx), 10, 'the Transpose dialog did not close')
    wait(1.5)


def project_properties(ctx, step):
    click_at(ctx, *FILE_MENU)
    wait(1.2)
    click_at(ctx, 98, 423)
    wait_until(lambda: 'Project properties' in titles(ctx), 8, 'Project properties did not open')
    wait(1.0)
    click_at(ctx, 790, FIELDS[step['field']])
    wait(.5)
    press(ctx, 'Control+a', .3)
    type_text(ctx, step['value'])
    wait(.5)
    click_at(ctx, 1009, 729)
    wait_until(lambda: 'Project properties' not in titles(ctx), 10, 'Project properties did not close')
    wait(1.0)


def export(ctx, step):
    click_at(ctx, *FILE_MENU)
    wait(1.2)
    click_at(ctx, 65, 390)
    wait_until(lambda: 'Export' in titles(ctx), 8, 'the Export dialog did not open')
    wait(1.2)
    click_at(ctx, 944, 361)
    wait(1.0)
    click_at(ctx, 810, FORMATS[step['format']])
    wait(1.0)
    click_at(ctx, 1055, 697)
    wait_until(lambda: titles(ctx).count('Export') == 2, 10, 'the export file chooser did not open')
    wait(.5)
    press(ctx, 'Control+a', .3)
    type_text(ctx, step['file'])
    wait(.4)
    press(ctx, 'Return', 1.0)
    wait_until(lambda: 'Export' not in titles(ctx), 20, 'the export did not complete')
    wait_until(lambda: written(ctx, step['file']), 15, 'the exported file was not written')
    wait(.8)


def show_properties(ctx, step):
    '''Open Project properties and leave it open: the evidence shows the stored fields (hooks.collect closes it).'''
    click_at(ctx, *FILE_MENU)
    wait(1.2)
    click_at(ctx, 98, 423)
    wait_until(lambda: 'Project properties' in titles(ctx), 8, 'Project properties did not open')
    wait(1.0)


def dismiss_session(ctx, step):
    '''After a restart with a score open the product asks whether to restore the previous session: answer No.'''
    if len(titles(ctx)) < 2:
        return
    click_at(ctx, 684, 528)
    wait_until(lambda: len(titles(ctx)) == 1, 10, 'the restore dialog did not close')
    wait(.8)


PALETTE_HEADERS = {'clefs': (57, 230), 'key': (90, 260), 'time': (94, 290), 'tempo': (62, 320), 'accidentals': (79, 380),
                   'dynamics': (73, 410), 'articulations': (83, 440), 'repeats': (97, 530), 'barlines': (68, 560)}
PALETTE_CELLS = {('key', 'sharp-1'): (35, 296), ('time', '3/4'): (77, 326), ('tempo', 'Allegro'): (54, 501),
                 ('clefs', 'bass'): (267, 274), ('accidentals', 'double-sharp'): (122, 414), ('dynamics', 'f'): (36, 468),
                 ('articulations', 'staccato'): (124, 469), ('barlines', 'double'): (92, 595),
                 ('repeats', 'end-repeat'): (221, 729)}


def palette(ctx, step):
    '''Expand one palette group and apply one cell to the selection (positions measured on the standard with the other groups collapsed).'''
    click_at(ctx, *PALETTE_HEADERS[step['group']])
    wait(1.5)
    click_at(ctx, *PALETTE_CELLS[(step['group'], step['cell'])])
    wait(1.5)


def page_landscape(ctx, step):
    click_at(ctx, 189, 33)
    wait(1.2)
    click_at(ctx, 217, 101)
    wait_until(lambda: 'Page settings' in titles(ctx), 8, 'Page settings did not open')
    wait(1.0)
    click_at(ctx, 570, 412)
    wait(.8)
    click_at(ctx, 977, 626)
    wait_until(lambda: 'Page settings' not in titles(ctx), 10, 'Page settings did not close')
    wait(1.5)


def new_score(ctx, step):
    '''Home > New score: one instrument from the Woodwinds list, then the title on the second page.'''
    press(ctx, 'Control+n', 2.0)
    wait_until(lambda: 'New score' in titles(ctx), 8, 'New score did not open')
    wait(1.0)
    click_at(ctx, 474, step['row'])
    wait(.8)
    click_at(ctx, 761, 457)
    wait(1.0)
    click_at(ctx, 1006, 726)
    wait(1.5)
    click_at(ctx, 469, 447)
    wait(.5)
    type_text(ctx, step['title'])
    wait(.5)
    click_at(ctx, 1150, 726)
    wait_until(lambda: titles(ctx) == [step['title']], 20, 'the new score did not open')
    wait(2.5)


def add_instrument(ctx, step):
    '''Add or remove instruments (key I): one instrument of the Woodwinds list added below the existing one.'''
    press(ctx, 'i', 2.0)
    wait_until(lambda: 'Add or remove instruments' in titles(ctx), 8, 'the instruments dialog did not open')
    wait(1.0)
    click_at(ctx, 536, step['row'])
    wait(.8)
    click_at(ctx, 823, 465)
    wait(1.0)
    click_at(ctx, 1115, 725)
    wait_until(lambda: 'Add or remove instruments' not in titles(ctx), 10, 'the instruments dialog did not close')
    wait(1.5)


def close_score(ctx, step):
    press(ctx, 'Control+w', 1.5)
    wait_until(lambda: titles(ctx) == [HOME], 10, 'the score did not close')


def execute(ctx, checkpoint):
    for step in checkpoint['recipe']:
        op = step['op']
        if op == 'open':
            open_file(ctx, step)
        elif op == 'save-as':
            save_as(ctx, step)
        elif op == 'select-note':
            select_note(ctx, step)
        elif op == 'press':
            for _ in range(step.get('times', 1)):
                press(ctx, step['key'], step.get('pause', .6))
        elif op == 'click':
            click_at(ctx, step['x'], step['y'])
            wait(step.get('pause', .8))
        elif op == 'type':
            type_text(ctx, step['value'])
            wait(step.get('pause', .6))
        elif op == 'transpose':
            transpose(ctx, step)
        elif op == 'project-properties':
            project_properties(ctx, step)
        elif op == 'export':
            export(ctx, step)
        elif op == 'show-properties':
            show_properties(ctx, step)
        elif op == 'dismiss-session':
            dismiss_session(ctx, step)
        elif op == 'palette':
            palette(ctx, step)
        elif op == 'close-score':
            close_score(ctx, step)
        elif op == 'page-landscape':
            page_landscape(ctx, step)
        elif op == 'new-score':
            new_score(ctx, step)
        elif op == 'add-instrument':
            add_instrument(ctx, step)
        elif op == 'wait':
            wait(step.get('seconds', 1))
        else:
            raise ValueError('unknown reference operation ' + op)
    verify(ctx, checkpoint)
    # Evidence without a tooltip over the controls the acceptance names.
    act(ctx, 'move', x=NEUTRAL[0], y=NEUTRAL[1])
    wait(1.0)


def verify(ctx, checkpoint):
    '''The checkpoint expected windows: only the score window, unless the checkpoint names other titles.'''
    expected = checkpoint.get('titles')
    if expected is not None:
        got = sorted(title for title in titles(ctx) if title)
        assert got == sorted(expected), 'window titles are %r, expected %r' % (got, expected)
