'''Reviewed user goals, acceptance conditions and program checks for the GUI.

Reference recipes (reference/recipes.py) implement these specifications for the pinned standard; goals are authored here and never translated from a click trace. MuseScore Studio has no scripting channel and its menus, buttons and score canvas are not in the accessibility snapshot, so every acceptance condition names only what a screenshot shows (window title, tab name, status bar text, notes and signs on the staff, dialog content) and every program check reads a file the goal makes the application write (a saved project, an exported score) or the window titles. The input documents of an episode are uploaded before its first checkpoint (setup item documents); requested outputs are typed by absolute path in the save and export dialogs. Every episode is native: its first checkpoint opens the score through the Open dialog and carries its own edit, so no point only repeats the opening of a score.
'''
import json
from evaluation.contract import files_path

FILES = {
    'scale-c.musicxml': 'MusicXML score: one Piano staff, two measures in 4/4 at 120 beats per minute, quarter notes C4 D4 E4 F4 in measure 1 and G4 A4 B4 C5 in measure 2',
    'titled.musicxml': 'MusicXML score: one Flute staff, work title Test Piece, composer A. Composer, copyright Copyright 2026 Test; measure 1 holds the quarter notes A4 B4 C5 D5, measure 2 one whole note E5',
    'clarinet-bb.musicxml': 'MusicXML score: one Clarinet in B flat staff (a transposing instrument written a major second above its sound), two measures in 4/4 with a written key signature of two sharps, written quarter notes D4 E4 F sharp 4 G4 in measure 1 and A4 B4 C sharp 5 D5 in measure 2',
}
EQUIVALENTS = ['Menus, toolbar buttons, keyboard shortcuts and dialogs are equivalent routes to a product command.',
               'Any precise way of selecting a note or setting a value is acceptable; layout, wording and widget types may differ from any reference.',
               'Enter the given document paths in file dialogs: in an open dialog after Control+L, in a save or export dialog in its file-name field; then confirm with Return or the dialog Open/Save button.']
BYPASSES = ['Do not use terminals, other applications or private files to perform a goal.',
            'Do not recreate a missing product command by other means, for example by importing a pre-edited file.']
HOME = 'MuseScore Studio'
SCALE_FIRST = ['quarter:60', 'quarter:62', 'quarter:64', 'quarter:65']
SCALE_SECOND = ['quarter:67', 'quarter:69', 'quarter:71', 'quarter:72']
SCALE = [SCALE_FIRST, SCALE_SECOND]
UP5_NOTES = [['quarter:76', 'quarter:78', 'quarter:79', 'quarter:81'], ['whole:83']]
TITLED_NOTES = [['quarter:69', 'quarter:71', 'quarter:72', 'quarter:74'], ['whole:76']]
TITLED_TAGS = {'workTitle': 'Test Piece', 'composer': 'A. Composer', 'copyright': 'Copyright 2026 Test'}
SCALE_VISIBLE = ('The application shows the score in a window titled scale-c.musicxml: one Piano staff with two measures in 4/4 '
                 'holding the quarter notes C D E F and G A B C (from middle C up to the C above), tempo 120.')


def area(name):
    '''The document area an episode document belongs to: uploaded inputs or new outputs.'''
    return 'inputs' if name in FILES else 'outputs'


def path(episode, name):
    '''Documents are named by absolute paths in the runtime document areas (file dialogs take them as typed).'''
    return files_path(area(name), name)


def step(key, goal, acceptance, recipe, checks=(), depends=(), requires=None, titles=None, lifecycle=None):
    '''requires maps an assertion of this checkpoint (visible or state-N) to the points it counts together with.'''
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': list(recipe), 'checks': list(checks),
             'preparation': [], 'visible': [], 'depends_on': list(depends), 'requires': dict(requires or {})}
    if titles is not None:
        value['titles'] = list(titles)
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, documents, steps, *, start='the Home page without an open score'):
    items = [{'id': 'documents', 'op': 'documents', 'files': list(documents)}] if documents else []
    for cp in steps:
        for action in cp['recipe']:
            if 'file' in action:
                action['file'] = path(key, action['file'])
        companions = cp.pop('requires')
        cp['depends_on'] = ['setup:' + item['id'] for item in items] + cp['depends_on']
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + '/state-%d' % (i + 1), 'channel': 'backend', 'method': 'program',
                                     'requirement': check.get('description', 'The independently read file or window state matches the requested checkpoint.'),
                                     'check': check})
        for assertion in cp['assertions']:
            point = assertion['id'].rsplit('/', 1)[1]
            if point in companions:
                assertion['requires'] = [key + '/' + (r if '/' in r else cp['id'] + '/' + r) for r in companions[point]]
    files = {name: FILES[name] for name in documents}
    prepared = 'The application starts with ' + start + '.'
    inputs = {'documents': {path(key, name): description for name, description in files.items()},
              'outputs': 'Save or export requested outputs at the exact paths given; type the path in the dialog file-name field.'}
    if files:
        inputs['how'] = ('These documents are files the application can open: press Control+O, then Control+L, type the absolute '
                         'path and confirm.')
    return {'id': key, 'feature': feature, 'execution': 'gui', 'scripting': False, 'documents': list(documents),
            'initial_state': 'Fresh application process, private desktop session and empty DATA_DIR. ' + prepared,
            'setup': items, 'inputs': inputs, 'session': 'Operate the visible desktop application only. ' + prepared,
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            # Each call carries a full-screen screenshot, so tokens scale with calls.
            'budget': budget(len(steps)), 'checkpoints': steps}


def budget(checkpoints):
    calls = min(180, 50 + 30 * checkpoints)
    return {'calls': calls, 'seconds': min(2400, 600 + 240 * checkpoints), 'tokens': min(2_500_000, 14_000 * calls)}


def frozen_form(value):
    '''The manifest is compared with its JSON-frozen copy: use JSON types only.'''
    return json.loads(json.dumps(value, ensure_ascii=False))


# ------------------------------------------------------------------ helpers
def stem(name):
    return name.rsplit('.', 1)[0]


def window(title, description):
    return {'kind': 'window-title', 'titles': [title], 'description': description}


def saved(name, description, **extra):
    return dict({'kind': 'score-file', 'path': 'outputs/' + name, 'description': description}, **extra)


def saved_notes(name, notes, description, title=False):
    '''The notes of a saved project; the window title only where the title itself is what the goal changes.'''
    checks = [saved(name, description, expect={'notes': notes})]
    if title:
        checks.append(window(stem(name), 'The window is titled after the saved project.'))
    return checks


def save_as(name):
    return {'op': 'save-as', 'file': name, 'title': stem(name)}


def opening(name):
    return {'op': 'open', 'file': name, 'title': name}


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(frozen_form(episode(*a, **kw)))

    def single(key, feature, document, sid, goal, acceptance, ops, checks, titles):
        '''One checkpoint that opens the document, performs its edit and checks the written file.'''
        add(key, feature, [document], [step(sid, goal, acceptance, [opening(document)] + list(ops), checks,
                                            requires={'visible': ['state-1']}, titles=titles)])

    # ------------------------------------------------------------ project files
    key = 'open-and-save'
    add(key, 'project-files', ['scale-c.musicxml'], [
        step('opened', 'Open the score %s in the application.' % path(key, 'scale-c.musicxml'), SCALE_VISIBLE,
             [opening('scale-c.musicxml')], [window('scale-c.musicxml', 'The window of the open score is titled scale-c.musicxml.')],
             titles=['scale-c.musicxml']),
        step('saved', 'Save the open score as a MuseScore project at %s.' % path(key, 'scale-c-saved.mscz'),
             'The score is now named scale-c-saved in the window title and in its tab, the tab shows no unsaved-changes asterisk, and the eight notes are unchanged.',
             [save_as('scale-c-saved.mscz')],
             saved_notes('scale-c-saved.mscz', SCALE, 'The saved project holds the eight notes of the opened score.', title=True),
             depends=['opened'], requires={'visible': ['state-1']}, titles=['scale-c-saved'])])

    # ------------------------------------------------------------ note editing
    key = 'edit-sharpen'
    add(key, 'note-editing', ['scale-c.musicxml'], [
        step('sharpened', 'Open the score %s, select its first note and raise it by one semitone, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-sharp.mscz')),
             'The score is open in a window titled edit-sharp; its first note, C4, shows a sharp sign and the status bar reads C sharp 4 when it is selected; the other seven notes are unchanged.',
             [opening('scale-c.musicxml'), {'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Up'}, save_as('edit-sharp.mscz')],
             saved_notes('edit-sharp.mscz', [['quarter:61', 'quarter:62', 'quarter:64', 'quarter:65'], SCALE_SECOND],
                         'The saved project holds C sharp 4 as the first note and the other notes unchanged.'),
             requires={'visible': ['state-1']}, titles=['edit-sharp']),
        step('undone', 'Undo the last change and save the score as a MuseScore project at %s.' % path(key, 'edit-undone.mscz'),
             'The first note is C4 again without a sharp sign and the score is saved as edit-undone.',
             [{'op': 'press', 'key': 'Control+z'}, save_as('edit-undone.mscz')],
             saved_notes('edit-undone.mscz', SCALE, 'The saved project holds the original notes again.'),
             depends=['sharpened'], requires={'visible': ['state-1'], 'state-1': ['sharpened/state-1']}, titles=['edit-undone'])])

    key = 'edit-duration'
    single(key, 'note-editing', 'scale-c.musicxml', 'half',
           'Open the score %s, make its second note a half note (it takes the place of the third note) and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-half.mscz')),
           'The score is open in a window titled edit-half: measure 1 shows a quarter note C, a half note D and a quarter note F (the old third note E is gone), measure 2 is unchanged and the status bar reads Half when the D is selected.',
           [{'op': 'select-note', 'index': 1}, {'op': 'press', 'key': '6'}, save_as('edit-half.mscz')],
           saved_notes('edit-half.mscz', [['quarter:60', 'half:62', 'quarter:65'], SCALE_SECOND],
                       'The saved project holds quarter C, half D and quarter F in measure 1 and an unchanged measure 2.'),
           ['edit-half'])

    key = 'edit-accidental'
    single(key, 'note-editing', 'scale-c.musicxml', 'flat',
           'Open the score %s, select its second note and give it a flat, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-flat.mscz')),
           'The score is open in a window titled edit-flat: the second note shows a flat sign and the status bar reads D flat 4 when it is selected; the other seven notes are unchanged.',
           [{'op': 'select-note', 'index': 1}, {'op': 'click', 'x': 496, 'y': 106}, save_as('edit-flat.mscz')],
           saved_notes('edit-flat.mscz', [['quarter:60', 'quarter:61', 'quarter:64', 'quarter:65'], SCALE_SECOND],
                       'The saved project holds D flat 4 as the second note and the other notes unchanged.'),
           ['edit-flat'])

    key = 'edit-delete'
    single(key, 'note-editing', 'scale-c.musicxml', 'deleted',
           'Open the score %s, select its second note and delete it, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-deleted.mscz')),
           'The score is open in a window titled edit-deleted: the second note has been replaced by a quarter rest (the status bar reads Rest when it is selected) and the other seven notes are unchanged.',
           [{'op': 'select-note', 'index': 1}, {'op': 'press', 'key': 'Delete'}, save_as('edit-deleted.mscz')],
           saved_notes('edit-deleted.mscz', [['quarter:60', 'rest:quarter', 'quarter:64', 'quarter:65'], SCALE_SECOND],
                       'The saved project holds a quarter rest in place of the second note and the other notes unchanged.'),
           ['edit-deleted'])

    key = 'edit-octave'
    single(key, 'note-editing', 'scale-c.musicxml', 'octave',
           'Open the score %s, select its third note and raise it by one octave, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-octave.mscz')),
           'The score is open in a window titled edit-octave: the third note, E4, now sits an octave higher (the status bar reads E5 when it is selected); the other seven notes are unchanged.',
           [{'op': 'select-note', 'index': 2}, {'op': 'press', 'key': 'Control+Up'}, save_as('edit-octave.mscz')],
           saved_notes('edit-octave.mscz', [['quarter:60', 'quarter:62', 'quarter:76', 'quarter:65'], SCALE_SECOND],
                       'The saved project holds E5 as the third note and the other notes unchanged.'),
           ['edit-octave'])

    key = 'edit-append'
    single(key, 'note-editing', 'scale-c.musicxml', 'appended',
           'Open the score %s, add a new empty measure at the end of the score, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-appended.mscz')),
           'The score is open in a window titled edit-appended: after the two measures of notes there is a third measure that holds only a whole-measure rest, the score ends with the final barline after it, and the eight notes are unchanged.',
           [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Escape'}, {'op': 'press', 'key': 'Control+b'}, save_as('edit-appended.mscz')],
           saved_notes('edit-appended.mscz', [SCALE_FIRST, SCALE_SECOND, ['rest:measure']],
                       'The saved project holds the eight notes and a third measure with a whole-measure rest.'),
           ['edit-appended'])

    key = 'edit-lowered'
    single(key, 'note-editing', 'scale-c.musicxml', 'lowered',
           'Open the score %s, select the whole score and lower every note by one semitone, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-lowered.mscz')),
           'The score is open in a window titled edit-lowered and every note is one semitone lower than before: the first note is B3 and the last note is B4; D flat, E flat, G flat, A flat and B flat carry flat signs, E4 and B4 carry natural signs and B3 has no accidental.',
           [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+a'}, {'op': 'press', 'key': 'Down'}, save_as('edit-lowered.mscz')],
           saved_notes('edit-lowered.mscz', [['quarter:59', 'quarter:61', 'quarter:63', 'quarter:64'], ['quarter:66', 'quarter:68', 'quarter:70', 'quarter:71']],
                       'The saved project holds every note one semitone lower.'),
           ['edit-lowered'])

    # ------------------------------------------------------------ transposition
    key = 'transpose-dialog'
    single(key, 'transposition', 'titled.musicxml', 'fifth-up',
           'Open the score %s, transpose the whole score up by a perfect fifth (by interval, with its key signature transposed) and save the score as a MuseScore project at %s.' % (path(key, 'titled.musicxml'), path(key, 'transposed.mscz')),
           'The score is open in a window titled transposed: the notes now sound a perfect fifth higher (the first note A4 is now E5, the whole note E5 is now B5), the staff shows a key signature with one sharp and the title Test Piece is unchanged.',
           [{'op': 'transpose', 'interval': 14, 'direction': 'up'}, save_as('transposed.mscz')],
           [saved('transposed.mscz', 'The saved project holds the notes a perfect fifth higher and a key signature of one sharp.',
                  fields=['notes', 'keys'], expect={'notes': UP5_NOTES, 'keys': [1]}),
            saved('transposed.mscz', 'The saved project keeps the work title, the composer and the copyright of the score.',
                  fields=['tags'], tags=['workTitle', 'composer', 'copyright'], expect={'tags': TITLED_TAGS})],
           ['transposed'])

    key = 'transpose-down'
    single(key, 'transposition', 'scale-c.musicxml', 'fifth-down',
           'Open the score %s, transpose the whole score down by a perfect fifth (by interval, with its key signature transposed) and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'transposed-down.mscz')),
           'The score is open in a window titled transposed-down: the notes now sound a perfect fifth lower (the first note is F3 and the last note F4) and the staff shows a key signature with one flat.',
           [{'op': 'transpose', 'interval': 14, 'direction': 'down'}, save_as('transposed-down.mscz')],
           [saved('transposed-down.mscz', 'The saved project holds the notes a perfect fifth lower and a key signature of one flat.',
                  fields=['notes', 'keys'],
                  expect={'notes': [['quarter:53', 'quarter:55', 'quarter:57', 'quarter:58'], ['quarter:60', 'quarter:62', 'quarter:64', 'quarter:65']], 'keys': [-1]})],
           ['transposed-down'])

    key = 'transpose-keysig-off'
    single(key, 'transposition', 'titled.musicxml', 'fifth-plain',
           'Open the score %s, transpose the whole score up by a perfect fifth (by interval) without transposing its key signature and save the score as a MuseScore project at %s.' % (path(key, 'titled.musicxml'), path(key, 'transposed-plain.mscz')),
           'The score is open in a window titled transposed-plain: the notes now sound a perfect fifth higher (E5, F sharp 5, G5, A5 and a whole note B5) but the staff shows no key signature, so the F sharp carries its own sharp sign.',
           [{'op': 'transpose', 'interval': 14, 'direction': 'up', 'keysig': False}, save_as('transposed-plain.mscz')],
           [saved('transposed-plain.mscz', 'The saved project holds the notes a perfect fifth higher and no key signature.',
                  fields=['notes', 'keys'], expect={'notes': UP5_NOTES, 'keys': []}),
            saved('transposed-plain.mscz', 'The saved project keeps the work title, the composer and the copyright of the score.',
                  fields=['tags'], tags=['workTitle', 'composer', 'copyright'], expect={'tags': TITLED_TAGS})],
           ['transposed-plain'])

    # ------------------------------------------------------------ project properties
    key = 'project-metadata'
    single(key, 'project-properties', 'titled.musicxml', 'retitled',
           'Open the score %s, open the project properties and change the work title to Changed Title, save the score as a MuseScore project at %s, then open the project properties again and leave that dialog open.' % (path(key, 'titled.musicxml'), path(key, 'retitled.mscz')),
           'The score is saved as retitled (window title and tab read retitled, no unsaved-changes asterisk) and a Project properties dialog is open showing the Work title Changed Title, the Composer A. Composer and the Copyright Copyright 2026 Test.',
           [{'op': 'project-properties', 'field': 'Work title', 'value': 'Changed Title'}, save_as('retitled.mscz'), {'op': 'show-properties', 'leave_open': True}],
           [saved('retitled.mscz', 'The saved project holds the new work title and keeps the composer and the copyright.',
                  fields=['tags'], tags=['workTitle', 'composer', 'copyright'],
                  expect={'tags': {'workTitle': 'Changed Title', 'composer': 'A. Composer', 'copyright': 'Copyright 2026 Test'}}),
            saved('retitled.mscz', 'The saved project keeps the notes of the score.', expect={'notes': TITLED_NOTES})],
           ['retitled', 'Project properties'])

    key = 'project-composer'
    single(key, 'project-properties', 'titled.musicxml', 'recomposed',
           'Open the score %s, open the project properties and change the composer to Another Composer, save the score as a MuseScore project at %s, then open the project properties again and leave that dialog open.' % (path(key, 'titled.musicxml'), path(key, 'recomposed.mscz')),
           'The score is saved as recomposed (window title and tab read recomposed, no unsaved-changes asterisk) and a Project properties dialog is open showing the Work title Test Piece, the Composer Another Composer and the Copyright Copyright 2026 Test.',
           [{'op': 'project-properties', 'field': 'Composer', 'value': 'Another Composer'}, save_as('recomposed.mscz'), {'op': 'show-properties', 'leave_open': True}],
           [saved('recomposed.mscz', 'The saved project holds the new composer and keeps the work title and the copyright.',
                  fields=['tags'], tags=['workTitle', 'composer', 'copyright'],
                  expect={'tags': {'workTitle': 'Test Piece', 'composer': 'Another Composer', 'copyright': 'Copyright 2026 Test'}}),
            saved('recomposed.mscz', 'The saved project keeps the notes of the score.', expect={'notes': TITLED_NOTES})],
           ['recomposed', 'Project properties'])

    # ------------------------------------------------------------ export
    key = 'export-musicxml'
    single(key, 'export', 'scale-c.musicxml', 'exported',
           'Open the score %s, export it as a MusicXML file at %s, then open the exported file %s in the application.' % (path(key, 'scale-c.musicxml'), path(key, 'exported.musicxml'), path(key, 'exported.musicxml')),
           'The exported MusicXML file is open in the application (titled exported.musicxml) and shows one Piano staff with the same eight quarter notes C D E F and G A B C.',
           [{'op': 'export', 'format': 'MusicXML', 'file': 'exported.musicxml'},
            {'op': 'open', 'file': 'exported.musicxml', 'title': 'exported.musicxml', 'windows': ['scale-c.musicxml', 'exported.musicxml']}],
           [{'kind': 'file-project', 'path': 'outputs/exported.musicxml', 'description': 'The exported file is a MusicXML score with the content of the open score.'}],
           ['scale-c.musicxml', 'exported.musicxml'])

    key = 'export-midi'
    single(key, 'export', 'scale-c.musicxml', 'exported',
           'Open the score %s, export it as a MIDI file at %s, then open the exported file %s in the application.' % (path(key, 'scale-c.musicxml'), path(key, 'exported.mid'), path(key, 'exported.mid')),
           'The exported MIDI file is open in the application (titled exported.mid) and shows one staff in 4/4 with the eight quarter notes C D E F and G A B C and the tempo 120.',
           [{'op': 'export', 'format': 'MIDI', 'file': 'exported.mid'},
            {'op': 'open', 'file': 'exported.mid', 'title': 'exported.mid', 'windows': ['scale-c.musicxml', 'exported.mid']}],
           [{'kind': 'file-project', 'path': 'outputs/exported.mid', 'description': 'The exported file is a MIDI file with the content of the open score.'}],
           ['scale-c.musicxml', 'exported.mid'])

    # ------------------------------------------------------------ persistence
    key = 'persist-edit'
    add(key, 'persistence', ['scale-c.musicxml'], [
        step('saved', 'Open the score %s, select its last note and raise it by one semitone, then save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'edit-persist.mscz')),
             'The score is open in a window titled edit-persist; its last note, C5, now shows a sharp sign (the status bar reads C sharp 5 when it is selected) and the other seven notes are unchanged.',
             [opening('scale-c.musicxml'), {'op': 'select-note', 'index': 7}, {'op': 'press', 'key': 'Up'}, save_as('edit-persist.mscz')],
             saved_notes('edit-persist.mscz', [SCALE_FIRST, ['quarter:67', 'quarter:69', 'quarter:71', 'quarter:73']],
                         'The saved project holds C sharp 5 as the last note and the other notes unchanged.', title=True),
             requires={'visible': ['state-1']}, titles=['edit-persist']),
        step('reopened', 'The application is restarted (if it asks whether to restore the previous session, answer No). Open the saved project %s again.' % path(key, 'edit-persist.mscz'),
             'After the restart the saved project is open in a window titled edit-persist and shows the edit: its last note carries a sharp sign (C sharp) and the other seven notes are unchanged.',
             [{'op': 'dismiss-session'}, {'op': 'open', 'file': 'edit-persist.mscz', 'title': 'edit-persist'}],
             [window('edit-persist', 'The window of the reopened project is titled edit-persist.')],
             depends=['saved'], requires={'visible': ['state-1']}, lifecycle='restart', titles=['edit-persist'])])
    # ------------------------------------------------------------ palettes
    key = 'palette-key'
    single(key, 'palettes', 'scale-c.musicxml', 'sharp-key',
           'Open the score %s, select its first note, add the key signature with one sharp from the Key signatures palette and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'key-sharp.mscz')),
           'The score is open in a window titled key-sharp: a key signature with one sharp follows the treble clef, the F in measure 1 carries a natural sign and the eight notes keep their pitches.',
           [{'op': 'select-note', 'index': 0}, {'op': 'palette', 'group': 'key', 'cell': 'sharp-1'}, save_as('key-sharp.mscz')],
           [saved('key-sharp.mscz', 'The saved project holds the eight notes unchanged and a key signature of one sharp.', fields=['notes', 'keys'], expect={'notes': SCALE, 'keys': [1]})],
           ['key-sharp'])

    key = 'palette-time'
    single(key, 'palettes', 'scale-c.musicxml', 'three-four',
           'Open the score %s, select its first note, apply the 3/4 time signature from the Time signatures palette and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'time-34.mscz')),
           'The score is open in a window titled time-34: 3/4 follows the treble clef and the notes are regrouped into three measures, C D E, F G A and B C followed by a quarter rest, with the final barline after the third measure.',
           [{'op': 'select-note', 'index': 0}, {'op': 'palette', 'group': 'time', 'cell': '3/4'}, save_as('time-34.mscz')],
           [saved('time-34.mscz', 'The saved project holds a 3/4 time signature and the eight notes regrouped in three measures with a closing quarter rest.', fields=['notes', 'times'],
                  expect={'notes': [['quarter:60', 'quarter:62', 'quarter:64'], ['quarter:65', 'quarter:67', 'quarter:69'], ['quarter:71', 'quarter:72', 'rest:quarter']], 'times': [[3, 4]]})],
           ['time-34'])

    key = 'palette-tempo'
    single(key, 'palettes', 'scale-c.musicxml', 'allegro',
           'Open the score %s, select its first note, add the Allegro tempo marking from the Tempo palette and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'tempo-allegro.mscz')),
           'The score is open in a window titled tempo-allegro: the word Allegro stands above the first note, the tempo display of the toolbar reads 144 beats per minute for the quarter note and the eight notes are unchanged.',
           [{'op': 'select-note', 'index': 0}, {'op': 'palette', 'group': 'tempo', 'cell': 'Allegro'}, save_as('tempo-allegro.mscz')],
           [saved('tempo-allegro.mscz', 'The saved project holds a tempo marking with the text Allegro at 144 beats per minute and the eight notes unchanged.', fields=['notes', 'tempos'],
                  expect={'notes': SCALE, 'tempos': [[2.4, 'Allegro']]})],
           ['tempo-allegro'])

    def edit(key, feature, sid, action, out, acceptance, ops, notes, description, marks=None):
        '''One checkpoint on scale-c: open it, perform one edit, save it as out; the program check reads the notes
        (and the marks of the named kinds) of the saved project.'''
        goal = 'Open the score %s, %s, then save the score as a MuseScore project at %s.' % (
            path(key, 'scale-c.musicxml'), action, path(key, out))
        check = saved(out, description, fields=['notes'] + (['marks'] if marks else []),
                      marks=sorted({kind for kind, _value in marks or []}),
                      expect=dict({'notes': notes}, **({'marks': marks} if marks else {})))
        single(key, feature, 'scale-c.musicxml', sid, goal, acceptance, ops + [save_as(out)], [check], [stem(out)])

    # ------------------------------------------------------------ note input, text and lines
    edit('note-input', 'note-input', 'entered',
         'select its first note and use note input to enter the quarter notes G4, A4 and B4 from there (over the first three notes)',
         'notes-entered.mscz',
         'The score is open in a window titled notes-entered: measure 1 now holds the quarter notes G4, A4 and B4 followed by the unchanged F4, and measure 2 is unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'n'}, {'op': 'press', 'key': '5'}, {'op': 'press', 'key': 'g'},
          {'op': 'press', 'key': 'a'}, {'op': 'press', 'key': 'b'}, {'op': 'press', 'key': 'Escape'}],
         [['quarter:67', 'quarter:69', 'quarter:71', 'quarter:65'], SCALE_SECOND],
         'The saved project holds G4, A4 and B4 in place of the first three notes and the other notes unchanged.')
    edit('lyrics-entry', 'text', 'lyric', 'add the lyric syllable la to its first note', 'lyric-la.mscz',
         'The score is open in a window titled lyric-la: the syllable la stands under the first note C4 and the eight notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+l', 'pause': 1.0}, {'op': 'type', 'value': 'la'},
          {'op': 'press', 'key': 'Escape'}],
         SCALE, 'The saved project holds the lyric la and the eight notes unchanged.', marks=[['Lyrics', 'la']])
    edit('staff-text', 'text', 'dolce', 'add the staff text dolce at its first note', 'text-dolce.mscz',
         'The score is open in a window titled text-dolce: the word dolce stands at the first note and the eight notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+t', 'pause': 1.0}, {'op': 'type', 'value': 'dolce'},
          {'op': 'press', 'key': 'Escape'}],
         SCALE, 'The saved project holds the staff text dolce and the eight notes unchanged.', marks=[['StaffText', 'dolce']])
    edit('tuplet', 'note-editing', 'triplet', 'select its first note and turn it into a triplet', 'triplet.mscz',
         'The score is open in a window titled triplet: a triplet bracket marked 3 spans the first beat, holding an eighth note C4 and two eighth rests; the other notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+3', 'pause': 1.0}, {'op': 'press', 'key': 'Escape'}],
         [['eighth:60', 'rest:eighth', 'rest:eighth', 'quarter:62', 'quarter:64', 'quarter:65'], SCALE_SECOND],
         'The saved project holds a triplet of an eighth C4 and two eighth rests on the first beat and the other notes unchanged.',
         marks=[['Tuplet', '3/2']])
    edit('slur', 'lines', 'slurred', 'select its first note and add a slur from it', 'slurred.mscz',
         'The score is open in a window titled slurred: a slur arc joins the first note C4 to the second note D4 and the eight notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 's', 'pause': 1.0}, {'op': 'press', 'key': 'Escape'}],
         SCALE, 'The saved project holds one slur and the eight notes unchanged.', marks=[['Spanner', 'Slur']])
    edit('tie', 'lines', 'tied', 'select its first note and add a tie to it', 'tied.mscz',
         'The score is open in a window titled tied: the first note C4 is tied to a second C4 on beat 2, which takes the place of the D; the other notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 't', 'pause': 1.0}, {'op': 'press', 'key': 'Escape'}],
         [['quarter:60', 'quarter:60', 'quarter:64', 'quarter:65'], SCALE_SECOND],
         'The saved project holds two tied C4 quarters at the start and the other notes unchanged.', marks=[['Spanner', 'Tie']])

    # ------------------------------------------------------------ structure
    edit('insert-measure', 'structure', 'inserted', 'select its first note and insert an empty measure before the first measure',
         'measure-inserted.mscz',
         'The score is open in a window titled measure-inserted: the score now starts with an empty measure holding a whole-measure rest, followed by the two measures of notes.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Insert', 'pause': 1.2}, {'op': 'press', 'key': 'Escape'}],
         [['rest:measure'], SCALE_FIRST, SCALE_SECOND],
         'The saved project holds an empty first measure followed by the eight notes.')
    edit('remove-range', 'structure', 'removed',
         'select its first note and remove it together with its time (the following notes of the measure close the gap)',
         'range-removed.mscz',
         'The score is open in a window titled range-removed: measure 1 now holds only the quarter notes D4, E4 and F4 (three beats) and measure 2 is unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+Delete', 'pause': 1.2}, {'op': 'press', 'key': 'Escape'}],
         [['quarter:62', 'quarter:64', 'quarter:65'], SCALE_SECOND],
         'The saved project holds D4, E4 and F4 in the first measure and the second measure unchanged.')
    edit('copy-paste', 'structure', 'pasted', 'copy its first note and paste it onto the first note of measure 2',
         'pasted.mscz',
         'The score is open in a window titled pasted: measure 2 now starts with C4 (middle C) in place of G4; the other notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Control+c'}, {'op': 'press', 'key': 'Right', 'times': 4, 'pause': .4},
          {'op': 'press', 'key': 'Control+v', 'pause': 1.0}, {'op': 'press', 'key': 'Escape'}],
         [SCALE_FIRST, ['quarter:60', 'quarter:69', 'quarter:71', 'quarter:72']],
         'The saved project holds C4 as the first note of measure 2 and the other notes unchanged.')
    edit('redo', 'note-editing', 'redone', 'raise its first note by one semitone, undo that change and redo it again',
         'redone.mscz',
         'The score is open in a window titled redone: the first note shows a sharp sign again (C sharp 4) and the other seven notes are unchanged.',
         [{'op': 'select-note', 'index': 0}, {'op': 'press', 'key': 'Up'}, {'op': 'press', 'key': 'Control+z'},
          {'op': 'press', 'key': 'Control+Shift+z', 'pause': 1.0}],
         [['quarter:61', 'quarter:62', 'quarter:64', 'quarter:65'], SCALE_SECOND],
         'The saved project holds C sharp 4 as the first note and the other notes unchanged.')

    # ------------------------------------------------------------ more palettes
    def palette(key, sid, group, cell, label, out, acceptance, notes, marks, description):
        single(key, 'palettes', 'scale-c.musicxml', sid,
               'Open the score %s, select its first note, apply %s from the %s palette and save the score as a MuseScore project at %s.'
               % (path(key, 'scale-c.musicxml'), label, group.capitalize() if group != 'repeats' else 'Repeats & jumps', path(key, out)),
               acceptance, [{'op': 'select-note', 'index': 0}, {'op': 'palette', 'group': group, 'cell': cell}, save_as(out)],
               [saved(out, description, fields=['notes', 'marks'], marks=sorted({kind for kind, _v in marks}),
                      expect={'notes': notes, 'marks': marks})], [stem(out)])

    palette('palette-clef', 'bass-clef', 'clefs', 'bass', 'the bass clef', 'clef-bass.mscz',
            'The score is open in a window titled clef-bass: a bass clef now stands before the first note, so the eight notes, still C4 to C5, are drawn high above the staff on ledger lines.',
            SCALE, [['Clef', 'G'], ['Clef', 'F']], 'The saved project holds a bass clef at the first note and the eight notes unchanged.')
    palette('palette-accidental', 'double-sharp', 'accidentals', 'double-sharp', 'the double sharp', 'double-sharp.mscz',
            'The score is open in a window titled double-sharp: the first note shows a double sharp sign (C double sharp 4, sounding as D4) and the other seven notes are unchanged.',
            [['quarter:62', 'quarter:62', 'quarter:64', 'quarter:65'], SCALE_SECOND], [['Accidental', 'accidentalDoubleSharp']],
            'The saved project holds a double sharp on the first note and the other notes unchanged.')
    palette('palette-dynamic', 'forte', 'dynamics', 'f', 'the dynamic f (forte)', 'dynamic-f.mscz',
            'The score is open in a window titled dynamic-f: the dynamic f stands under the first note and the eight notes are unchanged.',
            SCALE, [['Dynamic', 'f']], 'The saved project holds the dynamic f and the eight notes unchanged.')
    palette('palette-articulation', 'staccato', 'articulations', 'staccato', 'the staccato', 'staccato.mscz',
            'The score is open in a window titled staccato: a staccato dot marks the first note and the eight notes are unchanged.',
            SCALE, [['Articulation', 'articStaccatoBelow']], 'The saved project holds a staccato on the first note and the eight notes unchanged.')
    palette('palette-barline', 'double-barline', 'barlines', 'double', 'the double barline', 'double-barline.mscz',
            'The score is open in a window titled double-barline: a double barline now stands right after the first note, inside measure 1, and the eight notes are unchanged.',
            SCALE, [['BarLine', 'double'], ['BarLine', 'normal']], 'The saved project holds a double barline after the first note and the eight notes unchanged.')
    palette('palette-repeat', 'end-repeat', 'repeats', 'end-repeat', 'the end repeat barline', 'end-repeat.mscz',
            'The score is open in a window titled end-repeat: an end repeat barline (two dots before a thick line) now stands right after the first note, inside measure 1, and the eight notes are unchanged.',
            SCALE, [['BarLine', 'end-repeat'], ['BarLine', 'normal']], 'The saved project holds an end repeat barline after the first note and the eight notes unchanged.')

    # ------------------------------------------------------------ layout, score setup and instruments
    key = 'concert-pitch'
    add(key, 'layout', ['clarinet-bb.musicxml'], [
        step('concert', 'Open the score %s (a B flat clarinet part), switch the score display to concert pitch and save the score as a MuseScore project at %s.' % (path(key, 'clarinet-bb.musicxml'), path(key, 'concert.mscz')),
             'The score is open in a window titled concert with concert pitch turned on: the clarinet staff now shows the sounding pitches, C4 D4 E4 F4 and G4 A4 B4 C5, without a key signature.',
             [opening('clarinet-bb.musicxml'), {'op': 'click', 'x': 1130, 'y': 885, 'pause': 1.5}, save_as('concert.mscz')],
             [saved('concert.mscz', 'The saved project stores concert pitch turned on.', fields=['style'], style=['concertPitch'],
                    expect={'style': {'concertPitch': '1'}})],
             requires={'visible': ['state-1']}, titles=['concert'])])
    key = 'page-landscape'
    single(key, 'layout', 'scale-c.musicxml', 'landscape',
           'Open the score %s, change the page orientation to landscape in the page settings and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'landscape.mscz')),
           'The score is open in a window titled landscape: the page is now wider than it is tall (A4 landscape) and the eight notes are unchanged.',
           [{'op': 'page-landscape'}, save_as('landscape.mscz')],
           [saved('landscape.mscz', 'The saved project stores an A4 landscape page.', fields=['style'], style=['pageWidth', 'pageHeight'],
                  expect={'style': {'pageWidth': '11.69', 'pageHeight': '8.27'}})],
           ['landscape'])
    key = 'new-score'
    add(key, 'score-setup', [], [
        step('created', 'From the Home page create a new score for one Flute with the title Flute Study (keep the other settings of the new score wizard) and save it as a MuseScore project at %s.' % path(key, 'flute-study.mscz'),
             'A new score is open in a window titled flute-study: one Flute staff in 4/4 with empty measures (whole-measure rests) and the title Flute Study at the top of the page.',
             [{'op': 'new-score', 'row': 334, 'title': 'Flute Study'}, save_as('flute-study.mscz')],
             [saved('flute-study.mscz', 'The saved project holds one Flute part and the work title Flute Study.', fields=['parts', 'tags'],
                    tags=['workTitle'], expect={'parts': ['Flute'], 'tags': {'workTitle': 'Flute Study'}})],
             requires={'visible': ['state-1']}, titles=['flute-study'])])
    key = 'add-instrument'
    single(key, 'instruments', 'scale-c.musicxml', 'flute-added',
           'Open the score %s, add a Flute to the score as a second instrument and save the score as a MuseScore project at %s.' % (path(key, 'scale-c.musicxml'), path(key, 'flute-added.mscz')),
           'The score is open in a window titled flute-added: a Flute staff with empty measures now stands below the Piano staff, whose eight notes are unchanged.',
           [{'op': 'add-instrument', 'row': 353}, save_as('flute-added.mscz')],
           [saved('flute-added.mscz', 'The saved project holds the Piano part followed by a Flute part.', fields=['parts'],
                  expect={'parts': ['Piano', 'Flute']})],
           ['flute-added'])

    # ------------------------------------------------------------ export and reopen
    for key, label, out, fmt, acceptance in (
            ('export-mei', 'an MEI file', 'exported.mei', 'MEI',
             'The exported MEI file is open in the application (titled exported.mei) and shows one staff with the same eight quarter notes C D E F and G A B C.'),):
        single(key, 'export', 'scale-c.musicxml', 'exported',
               'Open the score %s, export it as %s at %s, then open the exported file %s in the application.' % (path(key, 'scale-c.musicxml'), label, path(key, out), path(key, out)),
               acceptance, [{'op': 'export', 'format': fmt, 'file': out}, {'op': 'open', 'file': out, 'title': out, 'windows': ['scale-c.musicxml', out]}],
               [{'kind': 'file-project', 'path': 'outputs/' + out, 'description': 'The exported file is an MEI document with the content of the open score.'}],
               ['scale-c.musicxml', out])

    # ------------------------------------------------------------ recent scores across a restart
    key = 'recent-scores'
    add(key, 'persistence', ['scale-c.musicxml'], [
        step('closed', 'Open the score %s, save it as a MuseScore project at %s and close the score.' % (path(key, 'scale-c.musicxml'), path(key, 'recent-a.mscz')),
             'The score is closed and the Home page lists the recently used scores: recent-a and scale-c.musicxml.',
             [opening('scale-c.musicxml'), save_as('recent-a.mscz'), {'op': 'close-score'}],
             saved_notes('recent-a.mscz', SCALE, 'The saved project holds the eight notes of the opened score.'),
             requires={'visible': ['state-1']}, titles=[HOME]),
        step('restarted', 'The application is restarted. Look at the list of recent scores on its Home page.',
             'After the restart the Home page still lists the recently used scores recent-a and scale-c.musicxml.',
             [{'op': 'dismiss-session'}], [], depends=['closed'], lifecycle='restart', titles=[HOME])])
    return episodes
