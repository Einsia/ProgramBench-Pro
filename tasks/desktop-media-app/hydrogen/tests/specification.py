from evaluation.contract import files_path
"""Reviewed user goals, acceptance conditions, public setup and program checks for the GUI.

Reference recipes (reference/recipes.py) implement these specifications for the pinned standard; goals are authored
here and never translated from a click trace. An episode's input documents are uploaded into the runtime's input area
before its first checkpoint (setup item "documents"); public OSC then opens the episode's starting song (setup item
"song"). Requested outputs are typed as absolute paths in the product's file dialogs and path fields and land in the
runtime's output or project area. Every assessed operation is a GUI goal; OSC prepares only non-target state.
"""
import json

FILES = {
    'ramp.wav': 'mono 44,100 Hz, 0.5 s linear ramp from -0.5 to +0.5',
    'editing.h2song': 'Song Editing: Tone (tone440.wav) at beats 1 and 2, High (tone880.wav) at beat 3 of Melody; '
                      'four repeated bars of Melody, 120 BPM, song mode',
    'samples.h2song': 'Song Samples: Ramp (ramp.wav) on beat 1 and Tone (tone440.wav) on beat 3 of Samples, 120 BPM',
    'pair.h2playlist': 'Playlist with first.h2song then second.h2song',
    'kick.wav': 'drum sample (mono, 44,100 Hz, 0.4 s): a decaying 60 Hz kick drum',
    'snare.wav': 'drum sample (mono, 44,100 Hz, 0.25 s): a decaying noise burst',
    'hat.wav': 'drum sample (mono, 44,100 Hz, 0.08 s): a short noise tick',
    'click.wav': 'drum sample (mono, 44,100 Hz): a short click',
    'tone220.wav': 'mono, 44,100 Hz, 0.5 s: a 220 Hz sine tone',
    'tone440.wav': 'mono, 44,100 Hz, 0.5 s: a 440 Hz sine tone',
    'tone880.wav': 'mono, 44,100 Hz, 0.5 s: an 880 Hz sine tone',
    'pad.wav': 'mono, 44,100 Hz, 1.5 s: a sustained chord of 330 Hz and 495 Hz sine tones',
    'beat.h2song': 'Hydrogen song "Beat" (120 BPM, pattern mode). Instruments, top to bottom: Kick, Snare, Hat and '
                   'Clap (playing kick.wav, snare.wav, hat.wav and click.wav). Patterns Verse and Fill, both 4/4 and '
                   'empty. The song plays Verse in bar 1.',
    'groove.h2song': 'Hydrogen song "Groove" (120 BPM, song mode). Instruments, top to bottom: Kick, Snare, Hat and '
                     'Clap (playing kick.wav, snare.wav, hat.wav and click.wav). Pattern Verse (4/4): Kick on beats 1 '
                     'and 3, Snare on beats 2 and 4, Hat on every eighth note. Pattern Fill (4/4): Kick on beat 1 and '
                     'Snare on the four sixteenth notes of beat 4. Pattern Ending (4/4, empty). The song plays Verse '
                     'in bars 1 to 3 and Fill in bar 4.',
    'demo.h2song': 'Hydrogen song "Demo Song" by "Verifier" (96 BPM). Instruments Low (tone220.wav) and High '
                   '(tone880.wav). Pattern Intro (3/4): Low on beat 1. Pattern Main (4/4): Low on beats 1 and 3, High '
                   'on beats 2 and 4. The song plays Intro in bar 1 and Main in bars 2 and 3.',
    'midi.h2song': 'Song "Mapped rhythm", 105 BPM with a 135 BPM marker at bar 2: a 3/4 pattern followed by a '
                   '4/4 pattern. Kick, Snare and Hat use different MIDI channels (2, 6, 10) and notes (36, 40, 46), '
                   'with different note velocities, lengths and simultaneous notes.',
    'first.h2song': 'Hydrogen song "First" (one instrument playing tone440.wav, one pattern)',
    'second.h2song': 'Hydrogen song "Second" (one instrument playing tone880.wav, one pattern)',
    'roll.h2pattern': 'Hydrogen pattern file with the pattern "Roll" (4/4): notes for the second instrument of a kit '
                      '(Snare in the song Groove) on the eight sixteenth notes of beats 3 and 4',
    'verifier.h2drumkit': 'Hydrogen drum kit archive of the kit "Verifier Kit": instruments Kick, Snare and Hat with '
                          'their samples',
}
SAMPLES = ('kick.wav', 'snare.wav', 'hat.wav', 'click.wav')
EQUIVALENTS = ['Menus, toolbar buttons, keyboard shortcuts, context menus and dialogs are equivalent routes to a '
               'product command; notes may be entered one by one or with a fill command.',
               'Any precise way of setting a value is acceptable (typing it into a field, a knob or a fader, spin '
               'buttons, menus); layout, wording and widget types may differ from any reference.',
               'Enter the given document paths in file dialogs (the File name field) and in the application\'s own '
               'file or folder fields; then confirm with Return or the dialog\'s Open/Save/Export button.']
BYPASSES = ['Do not use terminals, OSC, the command line, other applications or private files to perform a goal.',
            'Do not recreate a missing product command by other means, for example by opening a pre-edited file.']

# The runtime's document areas of one episode (they sit beside the product's instance directory).
# Layout used to describe positions: 48 ticks per quarter note.
QUARTER = 48


def path(episode, name, area=None):
    """Documents are named by absolute paths in the runtime's document areas (file dialogs take them as typed)."""
    if area is None:
        area = 'inputs' if name in FILES else 'outputs'
    return files_path(area, name)


def folder(episode, area):
    return files_path(area)


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    return '"' + value + '"'


def step(key, goal, acceptance, recipe, checks=(), setup=(), depends=(), lifecycle=None, visible=(), requires=None,
         windows=()):
    """requires maps an assertion of this checkpoint ('visible' or 'state-N') to the points it counts together
    with ('state-N' of this checkpoint or '<checkpoint>/<point>')."""
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': list(recipe), 'checks': list(checks),
             'preparation': list(setup), 'visible': list(visible), 'depends_on': list(depends),
             'requires': dict(requires or {})}
    if windows:
        value['windows'] = list(windows)
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, documents, opened, steps, *, start):
    items = []
    if documents:
        items.append({'id': 'documents', 'op': 'documents', 'files': list(documents)})
    if opened:
        items.append({'id': 'song', 'op': 'scripted', 'operations': [{'op': 'open-song', 'file': opened}]})
    for cp in steps:
        for action in cp.get('recipe') or []:
            for field in ('file', 'folder'):
                if isinstance(action, dict) and isinstance(action.get(field), (list, tuple)):
                    action[field] = path(key, *action[field]) if field == 'file' else folder(key, action[field][0])
        companions = cp.pop('requires')
        cp['depends_on'] = ['setup:' + item['id'] for item in items] + cp['depends_on']
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + f'/state-{i + 1}', 'channel': 'backend',
                                     'method': 'program', 'requirement': check.get(
                                         'description', 'The independently read song state or written file matches '
                                                        'the requested checkpoint.'), 'check': check})
        for assertion in cp['assertions']:
            point = assertion['id'].rsplit('/', 1)[1]
            if point in companions:
                assertion['requires'] = [key + '/' + (r if '/' in r else cp['id'] + '/' + r) for r in companions[point]]
    files = {name: FILES[name] for name in documents}
    prepared = 'The application starts with ' + start + '.'
    inputs = {'documents': {path(key, name): description for name, description in files.items()},
              'outputs': 'Save requested outputs at the exact paths given: type the path in the file dialog\'s File '
                         'name field or in the application\'s own file or folder field.'}
    if files:
        inputs['how'] = ('These documents are files the application can open or import: type the absolute path in '
                         'its file dialog and confirm.')
    return {'id': key, 'feature': feature, 'execution': 'gui', 'documents': list(documents),
            'initial_state': 'Fresh application process, private desktop session and empty DATA_DIR. ' + prepared,
            'setup': items, 'inputs': inputs,
            'session': 'Operate the visible desktop application only. ' + prepared + ' After each checkpoint the '
                       'framework saves a copy of the current song in the project folder (as check-NNNN.h2song) to '
                       'read it; the window title may then show that file name.',
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            # Desktop calibration: each call carries a full-screen screenshot and the accessible controls (about
            # 10-15k tokens), so tokens scale with calls.
            'budget': budget(len(steps)),
            'checkpoints': steps}


def budget(checkpoints):
    calls = min(180, 50 + 30 * checkpoints)
    return {'calls': calls, 'seconds': min(2400, 600 + 240 * checkpoints), 'tokens': min(2_500_000, 14_000 * calls)}


def frozen_form(value):
    """The manifest is compared with its JSON-frozen copy: use JSON types only."""
    return json.loads(json.dumps(value, ensure_ascii=False))


# ------------------------------------------------------------------ program checks of GUI checkpoints
def song(*fields, description=None):
    return {'kind': 'song', 'fields': list(fields),
            'description': description or 'The saved song has the requested ' + ', '.join(fields) + '.'}


def notes(*patterns, fields=(), description=None):
    return {'kind': 'pattern-notes', 'patterns': list(patterns), 'fields': list(fields),
            'description': description or 'The notes of ' + ', '.join(patterns) + ' are exactly the requested ones.'}


def patterns(*fields, unordered=False, description=None):
    value = {'kind': 'patterns', 'fields': list(fields) or ['name'],
             'description': description or 'The song\'s pattern list is the requested one.'}
    if unordered:
        # Where a new pattern lands in the list is not part of the goal.
        value['unordered'] = True
    return value


def sequence(description=None):
    return {'kind': 'sequence', 'description': description or 'The song arrangement is the requested one.'}


def instruments(*names, fields=(), description=None):
    return {'kind': 'instruments', 'names': list(names), 'fields': list(fields),
            'description': description or ('The instrument settings are the requested ones.' if names else
                                           'The song has exactly the requested instruments.')}


def output(kind, name, area='outputs', description=None, **extra):
    return {'kind': kind, 'path': area + '/' + name, **extra,
            'description': description or f'The application wrote {name} with the requested content.'}


# ------------------------------------------------------------------ recipe helpers (positions of the layout)
def note(row, tick):
    """A click in the pattern editor grid: instrument row (from the top) and position in ticks."""
    return {'op': 'note', 'row': row, 'tick': tick}


def cell(row, bar):
    """A click in the song editor grid: pattern row (from the top) and bar (from 1)."""
    return {'op': 'cell', 'row': row, 'bar': bar}


def menu(*labels):
    return {'op': 'menu', 'path': list(labels)}


def context(area, row, keys):
    """Right-click an instrument ('instrument') or pattern ('pattern') name and choose with the keyboard."""
    return {'op': 'context', 'area': area, 'row': row, 'keys': list(keys)}


def knob(label, value):
    """A knob or fader (named by the start of its accessible description) set by typing its value."""
    return {'op': 'knob', 'label': label, 'value': str(value)}


def strip(index, control, value=None):
    return {'op': 'strip', 'index': index, 'control': control, **({'value': str(value)} if value is not None else {})}


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(frozen_form(episode(*a, **kw)))

    beat_docs = list(SAMPLES) + ['beat.h2song']
    groove_docs = list(SAMPLES) + ['groove.h2song']
    BEAT = 'the song beat.h2song opened (pattern Verse shown in the pattern editor, instrument Kick selected)'
    GROOVE = 'the song groove.h2song opened (pattern Verse shown in the pattern editor, instrument Kick selected)'
    DEFAULT = 'its default new song (drum kit GMRockKit)'

    # ------------------------------------------------------------ song
    key = 'song-properties'
    add(key, 'song', [], None, [
        step('properties', 'Open the song properties and set the song name to ' + text_value('Night Drive') +
             ', the author to ' + text_value('Ada Lovelace') + ' and the notes to ' +
             text_value('Two bars of groove') + ', then confirm the dialog.',
             'The song properties dialog is closed after confirming; the application shows the song as Night Drive '
             '(for example in the window title).',
             [menu('Project', 'Song Properties'),
              {'op': 'dialog', 'title': 'Song properties', 'fields': [[0, 'Night Drive'], [1, 'Ada Lovelace'],
                                                                       [2, 'Two bars of groove']]}],
             [song('name', 'author', 'notes')], requires={'visible': ['state-1']}),
        step('license', 'In the song properties, set the license of the song to ' + text_value('CC BY-SA') +
             ' and confirm the dialog, then reopen the properties to display the saved license.',
             'The displayed song properties show the saved license CC BY-SA.',
             [menu('Project', 'Song Properties'),
              {'op': 'dialog', 'title': 'Song properties', 'combos': [['License', 'CC BY-SA']]},
              menu('Project', 'Song Properties')],
             [song('license', 'name')], depends=['properties'], requires={'visible': ['state-1']},
             windows=['Song properties']),
        step('cancelled', 'In the song properties, change the author to ' + text_value('Nobody') +
             ', then cancel and reopen the properties to display the saved author.',
             'The displayed song properties show Ada Lovelace as the author after the edit was cancelled.',
             [{'op': 'dialog', 'title': 'Song properties', 'fields': [[1, 'Nobody']], 'button': 'Cancel'},
              menu('Project', 'Song Properties')],
             [song('author', description='The cancelled change left the author Ada Lovelace.')],
             depends=['license'], requires={'visible': ['state-1'], 'state-1': ['properties/state-1']},
             windows=['Song properties'])],
        start=DEFAULT)

    key = 'song-tempo-modes'
    add(key, 'song', [], None, [
        step('tempo', 'Set the tempo of the song to 137 BPM.',
             'The tempo display shows 137 BPM.',
             [{'op': 'fill', 'target': {'role': 'spin button', 'name': 'Alter the Playback Speed'}, 'value': '137'}],
             [song('bpm')], visible=['137']),
        step('fraction', 'Set the tempo to 92.5 BPM.',
             'The tempo display shows 92.5 BPM.',
             [{'op': 'fill', 'target': {'role': 'spin button', 'name': 'Alter the Playback Speed'}, 'value': '92.5'}],
             [song('bpm')], depends=['tempo']),
        step('song-mode', 'Switch the application from pattern mode to song mode and turn on looping of the song.',
             'Song mode is active (the Song mode control is lit, Pattern is not) and the loop control is switched '
             'on.',
             [{'op': 'check', 'target': {'role': 'check box', 'name': 'Song Mode'}, 'state': True},
              {'op': 'check', 'target': {'role': 'check box', 'name': 'Loop song'}, 'state': True}],
             [song('mode', 'loop')])], start=DEFAULT)

    # ------------------------------------------------------------ pattern editor
    key = 'pattern-notes'
    add(key, 'pattern-editor', beat_docs, 'beat.h2song', [
        step('beats', 'In the pattern Verse, add Kick notes on beats 1 and 3 and a Snare note on beat 2.',
             'The pattern editor shows Verse with Kick notes at the start of beats 1 and 3 and a Snare note at the '
             'start of beat 2, and no other notes.',
             [note(0, 0), note(0, 96), note(1, 48)],
             [notes('Verse')]),
        step('hats', 'Add Hat notes on all eight eighth notes of the bar in Verse.',
             'The Hat row of Verse shows eight evenly spaced notes, one on every eighth note; the Kick and Snare '
             'notes are unchanged.',
             [context('instrument', 2, ['Down', 'Down', 'Right', 'Return'])],
             [notes('Verse')], depends=['beats']),
        step('removed', 'Remove the Kick note on beat 3 from Verse.',
             'The Kick row of Verse shows only the note on beat 1; the Snare and Hat notes are unchanged.',
             [note(0, 96)],
             [notes('Verse')], depends=['hats'])], start=BEAT)

    key = 'pattern-grid'
    add(key, 'pattern-editor', beat_docs, 'beat.h2song', [
        step('sixteenths', 'Change the grid resolution of the pattern editor to sixteenth notes (1/16) and add Snare '
                           'notes on the second and on the fourth sixteenth note of beat 2 of Verse.',
             'The resolution shows 1/16; Verse has two Snare notes inside beat 2, one sixteenth and three '
             'sixteenths after its start.',
             [{'op': 'combo', 'target': {'role': 'combo box', 'name': '1/8 - eighth'}, 'item': '1/16 - sixteenth'},
              note(1, 60), note(1, 84)],
             [notes('Verse')]),
        step('triplets', 'Change the resolution to eighth-note triplets (1/8T) and add Clap notes on the three '
                         'triplet eighth notes of beat 3 of Verse.',
             'The resolution shows 1/8T; the Clap row of Verse has three evenly spaced notes covering beat 3; the '
             'Snare notes are unchanged.',
             [{'op': 'combo', 'target': {'role': 'combo box', 'name': '1/16 - sixteenth'},
               'item': '1/8T - eighth triplet'}, note(3, 96), note(3, 112), note(3, 128)],
             [notes('Verse')], depends=['sixteenths']),
        step('size', 'Change the size of the pattern Verse to 7/8.',
             'The pattern size shows 7/8 and the Verse grid is shorter than a 4/4 bar (seven eighth notes long); '
             'its notes are still shown.',
             [{'op': 'pattern-size', 'numerator': '7', 'denominator': '8'}],
             [notes('Verse', fields=('size', 'denominator'))], depends=['triplets'])], start=BEAT)

    key = 'pattern-properties'
    add(key, 'patterns', beat_docs, 'beat.h2song', [
        step('renamed', 'Change the properties of the pattern Verse: name ' + text_value('Groove A') +
             ', description ' + text_value('Main beat') + ' and category ' + text_value('Rock') + '.',
             'The pattern list of the song editor shows Groove A in place of Verse.',
             [context('pattern', 0, ['Down', 'Down', 'Down', 'Down', 'Return']),
              {'op': 'dialog', 'title': 'Pattern properties', 'fields': [[0, 'Groove A'], [1, 'Main beat'],
                                                                          [2, 'Rock']]}],
             [patterns('name', 'info', 'category')], visible=['Groove A']),
        step('created', 'Create a new pattern named ' + text_value('Break') + '.',
             'The pattern list shows a new pattern Break in addition to Groove A and Fill.',
             [{'op': 'button', 'name': 'Create new pattern'},
              {'op': 'dialog', 'title': 'Pattern properties', 'fields': [[0, 'Break']]}],
             [patterns('name', unordered=True)], depends=['renamed'], visible=['Break']),
        step('deleted', 'Delete the pattern Fill.',
             'The pattern list shows Groove A and Break; Fill is gone.',
             [context('pattern', 2, ['Down', 'Down', 'Return'])],
             [patterns('name', unordered=True)], depends=['created'])], start=BEAT)

    key = 'pattern-copies'
    add(key, 'patterns', groove_docs, 'groove.h2song', [
        step('duplicated', 'Duplicate the pattern Verse and name the copy ' + text_value('Verse 2') + '.',
             'The pattern list shows Verse 2 in addition to Verse, Fill and Ending; Verse 2 has the same notes as '
             'Verse.',
             [context('pattern', 0, ['Down', 'Return']),
              {'op': 'dialog', 'title': 'Pattern properties', 'fields': [[0, 'Verse 2']]}],
             [patterns('name', unordered=True), notes('Verse 2', description='The copy has the notes of Verse.')],
             visible=['Verse 2']),
        step('placed', 'Make the song play the pattern Verse 2 in bars 5 to 8 (and nowhere else).',
             'The song editor shows Verse 2 in bars 5, 6, 7 and 8; Verse still fills bars 1 to 3 and Fill bar 4.',
             [context('pattern', 1, ['Down', 'Down', 'Down', 'Return']),
              {'op': 'fill-dialog', 'mode': 'Fill', 'from': '5', 'to': '8'}],
             [sequence()], depends=['duplicated']),
        step('cleared', 'Remove the pattern Verse 2 from bars 7 and 8 of the song.',
             'The song editor shows Verse 2 only in bars 5 and 6; bars 7 and 8 are empty.',
             [context('pattern', 1, ['Down', 'Down', 'Down', 'Return']),
              {'op': 'fill-dialog', 'mode': 'Clear', 'from': '7', 'to': '8'}],
             [sequence()], depends=['placed'])], start=GROOVE)

    key = 'song-arrangement'
    add(key, 'song-editor', groove_docs, 'groove.h2song', [
        step('cells', 'In the song editor, add the pattern Fill to bar 2 (it plays together with Verse there) and '
                      'remove Verse from bar 3, so that bar 3 is empty.',
             'The song editor shows Verse in bars 1 and 2, Fill in bars 2 and 4, and nothing in bar 3.',
             [cell(1, 2), cell(0, 3)],
             [sequence()]),
        step('virtual', 'Turn the pattern Ending into a virtual pattern made of Verse and Fill (the song editor\'s '
                        'pattern list offers this in the context menu of a pattern name).',
             'Ending is shown as a virtual pattern of Verse and Fill: with Ending selected, the pattern editor shows the '
             'notes of Verse and Fill in it (drawn as virtual notes).',
             [context('pattern', 2, ['Up', 'Return']),
              {'op': 'list-dialog', 'title': 'Select virtual pattern', 'items': ['Verse', 'Fill']}],
             [{'kind': 'virtual', 'description': 'Ending is a virtual pattern of exactly Verse and Fill.'}],
             requires={'visible': ['state-1']})], start=GROOVE)

    key = 'instrument-rows'
    add(key, 'pattern-editor', groove_docs, 'groove.h2song', [
        step('cleared', 'Delete all Hat notes of the pattern Verse; the other instruments keep their notes.',
             'The Hat row of Verse is empty; the Kick and Snare notes of Verse are unchanged.',
             [context('instrument', 2, ['Down', 'Return'])],
             [notes('Verse')]),
        step('quarters', 'Give the Hat row of Verse a note on every quarter note (beats 1, 2, 3 and 4).',
             'The Hat row of Verse shows four notes, one at the start of each beat.',
             [context('instrument', 2, ['Down', 'Down', 'Right', 'Down', 'Return'])],
             [notes('Verse')], depends=['cleared']),
        step('copied', 'Copy the Snare notes of all patterns to the Clap row: in every pattern the Clap row then has '
                       'the same notes as the Snare row, and the Snare notes stay.',
             'The Clap row of Verse shows notes on beats 2 and 4, like the Snare row, which keeps its notes.',
             [context('instrument', 1, ['Down'] * 6 + ['Return']),
              context('instrument', 3, ['Down'] * 7 + ['Return'])],
             [notes('Verse', 'Fill')], depends=['quarters'])], start=GROOVE)

    key = 'undo-redo'
    add(key, 'pattern-editor', beat_docs, 'beat.h2song', [
        step('added', 'In Verse, add a Snare note on beat 2 and then a Snare note on beat 4.',
             'The Snare row of Verse shows notes on beats 2 and 4.',
             [note(1, 48), note(1, 144)],
             [notes('Verse')]),
        step('undone', 'Undo the last change.',
             'Only the Snare note on beat 2 remains in Verse.',
             [menu('Undo', 'Undo')],
             [notes('Verse')], depends=['added']),
        step('redone', 'Redo the change that was undone.',
             'The Snare row of Verse shows notes on beats 2 and 4 again.',
             [menu('Undo', 'Redo')],
             [notes('Verse')], depends=['undone'])], start=BEAT)

    key = 'timeline'
    add(key, 'song-editor', groove_docs, 'groove.h2song', [
        step('marker', 'Turn on the timeline of the song editor and add a tempo marker of 90 BPM at bar 3.',
             'The timeline shows a tempo marker of 90 at bar 3.',
             [{'op': 'check', 'target': {'role': 'check box', 'name': 'Timeline'}, 'state': True},
              {'op': 'ruler', 'row': 'tempo', 'bar': 3},
              {'op': 'fill', 'target': {'role': 'spin button', 'name': 'Set tempo of new tempo marker'},
               'value': '90'},
              {'op': 'button', 'name': 'Ok'}],
             [{'kind': 'timeline', 'fields': ['markers', 'timeline'],
               'description': 'The timeline is active and holds a 90 BPM marker at bar 3.'}]),
        step('tag', 'Add the tag ' + text_value('Chorus') + ' at bar 5 of the timeline.',
             'The timeline shows a tag marker at bar 5.',
             [{'op': 'ruler', 'row': 'tag', 'bar': 5}, {'op': 'tag', 'bar': 5, 'text': 'Chorus'}],
             [{'kind': 'timeline', 'fields': ['tags'], 'description': 'The timeline holds the tag Chorus at bar 5.'}],
             depends=['marker'], requires={'visible': ['state-1']}),
        step('removed', 'Delete the tempo marker at bar 3 again.',
             'The timeline no longer shows a tempo marker at bar 3.',
             [{'op': 'ruler', 'row': 'tempo', 'bar': 3},
              {'op': 'check', 'target': {'role': 'check box', 'name': 'Delete BPM Marker'}, 'state': True}],
             [{'kind': 'timeline', 'fields': ['markers'], 'description': 'No tempo marker is left at bar 3.'}],
             depends=['marker'])], start=GROOVE)

    # ------------------------------------------------------------ instruments
    key = 'instrument-list'
    add(key, 'instruments', beat_docs, 'beat.h2song', [
        step('added', 'Add a new instrument to the song.',
             'A fifth instrument row (named like "New instrument") appears below Clap.',
             [menu('Instruments', 'Add Instrument')],
             [{'kind': 'instrument-count', 'known': ['Kick', 'Snare', 'Hat', 'Clap'],
               'description': 'The song has one instrument more than before; Kick, Snare, Hat and Clap remain.'}]),
        step('renamed', 'Rename the new instrument to ' + text_value('Shaker') + '.',
             'The fifth instrument row is named Shaker.',
             [context('instrument', 4, ['Up', 'Up', 'Return']),
              {'op': 'dialog', 'title': 'Hydrogen', 'fields': [[0, 'Shaker']]}],
             [instruments()], depends=['added'], visible=['Shaker']),
        step('deleted', 'Delete the instrument Clap from the song.',
             'The instrument rows are Kick, Snare, Hat and Shaker; Clap is gone.',
             [context('instrument', 3, ['Up', 'Return'])],
             [instruments()], depends=['renamed'])], start=BEAT)

    key = 'instrument-sound'
    add(key, 'instruments', beat_docs, 'beat.h2song', [
        step('kick', 'Set the gain of the Kick instrument to 1.5 and its pitch (coarse) to -7 semitones.',
             'The instrument editor shows Kick with gain 1.50 and pitch -7.',
             [knob('Instrument gain', 1.5), knob('Pitch offset (Coarse)', -7)],
             [instruments('Kick', fields=('gain', 'pitch_offset'))]),
        step('snare', 'Select the Snare instrument, put it in mute group 1 and turn on Auto-Stop Note for it.',
             'The instrument editor shows Snare with mute group 1 and Auto-Stop Note checked.',
             [{'op': 'select-instrument', 'row': 1},
              {'op': 'fill', 'near': 'Mute Group', 'role': 'spin button', 'side': 'above', 'value': '1'},
              {'op': 'check', 'near': 'Auto-Stop Note', 'role': 'check box', 'side': 'left', 'state': True}],
             [instruments('Snare', fields=('mute_group', 'stop_note'))]),
        step('filter', 'Select the Hat instrument and activate its filter with cutoff 0.5 and resonance 0.25.',
             'The instrument editor shows Hat with the filter switched on (not bypassed), cutoff 0.50 and resonance '
             '0.25.',
             [{'op': 'select-instrument', 'row': 2},
              {'op': 'check', 'target': {'role': 'check box', 'name': 'BYP'}, 'state': False},
              knob('Filter Cutoff', 0.5), knob('Filter resonance', 0.25)],
             [instruments('Hat', fields=('filter',))])], start=BEAT)

    key = 'instrument-envelope'
    add(key, 'instruments', beat_docs, 'beat.h2song', [
        step('envelope', 'Set the envelope of the Kick instrument: attack 0.2, decay 0.4, sustain 0.5 and release '
                         '0.3 (the values of its ADSR knobs).',
             'The instrument editor shows Kick with the knobs attack 0.20, decay 0.40, sustain 0.50 and release '
             '0.30.',
             [knob('Length of Attack phase', 0.2), knob('Length of Decay phase', 0.4),
              knob('Sample volume in Sustain phase', 0.5), knob('Length of Release phase', 0.3)],
             [instruments('Kick', fields=('adsr',))]),
        step('midi', 'Select the Clap instrument and set its MIDI output to channel 10 and note 39.',
             'The instrument editor shows Clap with MIDI output channel 10 and note 39.',
             [{'op': 'select-instrument', 'row': 3},
              {'op': 'fill', 'near': 'Channel', 'role': 'spin button', 'side': 'above', 'value': '10'},
              {'op': 'fill', 'near': 'Note', 'role': 'spin button', 'side': 'above', 'value': '39'}],
             [instruments('Clap', fields=('midi_out',))])], start=BEAT)

    key = 'instrument-mute-solo'
    add(key, 'instruments', groove_docs, 'groove.h2song', [
        step('muted', 'Mute the Hat instrument.',
             'The Hat instrument is shown muted (its mute control is on); no other instrument is muted.',
             [{'op': 'row-button', 'row': 2, 'button': 'M'}],
             [instruments('Kick', 'Snare', 'Hat', 'Clap', fields=('muted', 'soloed'))]),
        step('soloed', 'Unmute Hat and solo the Snare instrument.',
             'Snare is shown soloed (its solo control is on); Hat is no longer muted.',
             [{'op': 'row-button', 'row': 2, 'button': 'M'}, {'op': 'row-button', 'row': 1, 'button': 'S'}],
             [instruments('Kick', 'Snare', 'Hat', 'Clap', fields=('muted', 'soloed'))], depends=['muted'])],
        start=GROOVE)

    key = 'instrument-layers'
    add(key, 'instruments', beat_docs + ['tone440.wav'], 'beat.h2song', [
        step('loaded', f'Select the Clap instrument and load the sample {path(key, "tone440.wav")} into its first '
                       'layer (replacing click.wav).',
             'The layer editor of Clap shows tone440.wav as its first layer, with its waveform.',
             [{'op': 'select-instrument', 'row': 3},
              {'op': 'check', 'target': {'role': 'check box', 'name': 'Layers'}, 'state': True},
              {'op': 'button', 'name': 'Load Layer'},
              {'op': 'browser', 'file': ('tone440.wav',)}],
             [{'kind': 'layers', 'instrument': 'Clap',
               'description': 'The first layer of Clap plays tone440.wav from the input folder.'}]),
        step('layer-values', 'Set the gain of that layer to 0.7 and its pitch (coarse) to +5.',
             'The layer editor shows the layer gain 0.70 and the layer pitch 5.',
             [knob('Layer gain', 0.7), knob('Layer pitch (Coarse)', 5)],
             [{'kind': 'layers', 'instrument': 'Clap',
               'description': 'The layer of Clap has gain 0.7 and pitch +5.'}], depends=['loaded'])], start=BEAT)

    # ------------------------------------------------------------ mixer
    key = 'mixer-strips'
    add(key, 'mixer', groove_docs, 'groove.h2song', [
        step('snare', 'Open the mixer and set the volume of the Snare channel to 0.5 and its pan to -0.6 (left).',
             'The mixer shows the Snare channel with its fader at 0.50 and its pan turned left to -0.60.',
             [{'op': 'mixer', 'show': True}, strip(1, 'volume', 0.5), strip(1, 'pan', -0.6)],
             [instruments('Snare', fields=('volume', 'pan'))]),
        step('mute-solo', 'In the mixer, mute the Hat channel and solo the Kick channel.',
             'The mixer shows Hat muted and Kick soloed (their mute and solo buttons are on).',
             [strip(2, 'mute'), strip(0, 'solo')],
             [instruments('Kick', 'Snare', 'Hat', 'Clap', fields=('muted', 'soloed'))], depends=['snare'])],
        start=GROOVE)

    key = 'mixer-master'
    add(key, 'mixer', groove_docs, 'groove.h2song', [
        step('master', 'Open the mixer and set the master volume to 0.8.',
             'The master fader of the mixer shows 0.80.',
             [{'op': 'mixer', 'show': True}, knob('Master volume', 0.8)],
             [{**song('volume'), 'tolerance': 0.005}]),
        step('groove', 'In the mixer, set the swing to 0.3 and the humanize velocity to 0.2.',
             'The master section of the mixer shows swing 0.30 and humanize velocity 0.20.',
             [knob('16th-note Swing', 0.3), knob('Humanize velocity', 0.2)],
             [song('swing', 'humanize')], depends=['master'])], start=GROOVE)

    # ------------------------------------------------------------ drum kits
    key = 'drumkit-load'
    add(key, 'drumkits', [], None, [
        step('tr808', 'Load the drum kit TR808EmulationKit from the sound library into the song.',
             'The pattern editor lists the instruments of TR808EmulationKit and names it as the loaded kit.',
             [menu('Drumkits', 'Open'), {'op': 'kit-dialog', 'kit': 'TR808EmulationKit (system)'}],
             [{'kind': 'kit', 'description': 'The song uses TR808EmulationKit and its instruments.'}],
             visible=['TR808EmulationKit']),
        step('gmrock', 'Load the drum kit GMRockKit again.',
             'The pattern editor lists the GMRockKit instruments (Kick, Stick, Snare, ...) and names GMRockKit as '
             'the loaded kit.',
             [menu('Drumkits', 'Open'), {'op': 'kit-dialog', 'kit': 'GMRockKit (system)'}],
             [{'kind': 'kit', 'description': 'The song uses GMRockKit and its instruments again.'}],
             depends=['tr808'], visible=['GMRockKit'])], start=DEFAULT)

    key = 'drumkit-import-export'
    add(key, 'drumkits', ['verifier.h2drumkit'], None, [
        step('imported', f'Import the drum kit archive {path(key, "verifier.h2drumkit")} into the sound library and '
                         'load the kit "Verifier Kit" into the song. (If the application reports that the online '
                         'drum kit list is unreachable, dismiss that message.)',
             'The pattern editor lists the instruments Kick, Snare and Hat of Verifier Kit and names Verifier Kit '
             'as the loaded kit.',
             [{'op': 'import-kit', 'file': ('verifier.h2drumkit',)},
              menu('Drumkits', 'Open'), {'op': 'kit-dialog', 'kit': 'Verifier Kit'}],
             [{'kind': 'kit', 'description': 'The song uses the imported Verifier Kit and its instruments.'}],
             visible=['Verifier Kit']),
        step('exported', 'Export the drum kit Verifier Kit as a drum kit archive into the folder ' +
             folder(key, 'outputs') + '. Leave the kit name and destination visible in the export settings.',
             'The export settings visibly identify Verifier Kit and its requested destination folder.',
             [menu('Drumkits', 'Export'), {'op': 'kit-export', 'folder': ('outputs',)}],
             [{'kind': 'file-drumkit', 'folder': 'outputs', 'suffix': '.h2drumkit',
               'description': 'The output folder received a drum kit archive (.h2drumkit) of Verifier Kit with its '
                              'three samples.'}],
             depends=['imported'], requires={'visible': ['state-1']}, windows=['Export Drumkit'])], start=DEFAULT)

    # ------------------------------------------------------------ files
    key = 'song-files'
    add(key, 'files', beat_docs + ['demo.h2song', 'tone220.wav', 'tone880.wav'], 'beat.h2song', [
        step('saved', f'Save the song as {path(key, "session.h2song", "projects")}.',
             'The song is saved under the name session.h2song (for example shown in the window title) without an '
             'error message.',
             [menu('Project', 'Save As...'), {'op': 'save-dialog', 'file': ('session.h2song', 'projects')}],
             [output('file-song', 'session.h2song', 'projects', fields=['name', 'bpm', 'instruments', 'patterns'],
                     description='session.h2song holds the song Beat with its instruments and patterns.')],
             visible=['session.h2song']),
        step('opened', f'Open the song {path(key, "demo.h2song")}.',
             'The application shows the song Demo Song: instruments Low and High, patterns Intro and Main, tempo '
             '96 BPM.',
             [menu('Project', 'Open'), {'op': 'open-dialog', 'file': ('demo.h2song',)}],
             [song('name', 'author', 'bpm', 'instruments', 'patterns', 'sequence')], visible=['Demo Song']),
        step('reopened', f'Open the saved song {path(key, "session.h2song", "projects")} again.',
             'The application shows the song Beat again: instruments Kick, Snare, Hat and Clap, patterns Verse and '
             'Fill.',
             [menu('Project', 'Open'), {'op': 'open-dialog', 'file': ('session.h2song', 'projects')}],
             [song('name', 'bpm', 'instruments', 'patterns')], depends=['saved'])], start=BEAT)

    key = 'song-new'
    add(key, 'files', beat_docs, 'beat.h2song', [
        step('new', 'Start a new, empty song (discarding the open song).',
             'The application shows a new untitled song with the default drum kit and empty patterns.',
             [menu('Project', 'New'), {'op': 'answer', 'title': 'Hydrogen', 'button': 'Discard', 'optional': True}],
             [song('name', 'bpm', 'instruments', 'patterns', 'sequence')])], start=BEAT)

    key = 'pattern-files'
    add(key, 'files', groove_docs + ['roll.h2pattern'], 'groove.h2song', [
        step('exported', f'Export the pattern Verse to {path(key, "verse.h2pattern")}, then open that exported '
                         'file as a new pattern in the song and display its notes.',
             'The exported pattern is loaded as an additional pattern named verse; its visible notes match Verse.',
             [menu('Project', 'Export Pattern As...'), {'op': 'save-dialog', 'file': ('verse.h2pattern',)},
              menu('Project', 'Open Pattern'), {'op': 'open-dialog', 'file': ('verse.h2pattern', 'outputs')}],
             [output('file-pattern', 'verse.h2pattern',
                     description='verse.h2pattern holds the pattern Verse with its notes.')],
             requires={'visible': ['state-1']}),
        step('loaded', f'Load the pattern file {path(key, "roll.h2pattern")} into the song.',
             'The pattern list of the song editor shows the newly loaded Roll pattern.',
             [menu('Project', 'Open Pattern'), {'op': 'open-dialog', 'file': ('roll.h2pattern',)}],
             [{'kind': 'pattern-present', 'name': 'Roll', 'description': 'The loaded pattern Roll is present.'},
              notes('Roll', description='The loaded pattern Roll has the notes of the file.')],
             visible=['Roll'])], start=GROOVE)

    # (The export dialog switches its format whenever the typed path ends like a format suffix, also halfway
    # through typing: the episode name stays clear of such endings, unlike "export-au...".)
    key = 'export-mixdown'
    add(key, 'export', groove_docs, 'groove.h2song', [
        step('flac', f'Export the song as a FLAC file {path(key, "mix.flac")}. Leave the export settings visible.',
             'The export settings visibly show FLAC and the destination mix.flac.',
             [{'op': 'close-if-open', 'title': 'Export song'}, menu('Project', 'Export Song'),
              {'op': 'export-song', 'file': ('mix.flac',), 'format': 'FLAC (Free Lossless Audio Codec)'}],
             [output('file-audio', 'mix.flac', format='flac', summary=True,
                     description='mix.flac contains the song rhythm and timbre: duration, onsets, window levels and spectrum at any rate.')],
             requires={'visible': ['state-1']}, windows=['Export song']),
        step('wav', 'Close the current Export song dialog using its Close button, then reopen Export Song. '
                    f'Export the song as a WAV file {path(key, "mix.wav")} with a sample rate of 48000 Hz and '
                    '24-bit samples. Leave the export settings visible.',
             'The export settings visibly show WAV, 48000 Hz, 24-bit samples and the destination mix.wav.',
             [{'op': 'close-if-open', 'title': 'Export song'}, menu('Project', 'Export Song'),
              {'op': 'export-song', 'file': ('mix.wav',), 'format': 'WAV (Waveform Audio)', 'rate': '48000',
               'depth': '24'}],
             [output('file-audio', 'mix.wav', format='wav', description='mix.wav is a 48000 Hz 24-bit WAV of the song.')],
             requires={'visible': ['state-1']}, windows=['Export song']),
        step('tracks', 'Close the current Export song dialog using its Close button, then reopen Export Song. '
                       f'Export the song to separate tracks, one WAV file for each instrument that plays in the '
                       f'song, using {path(key, "stem.wav")} as the file name (the application adds the instrument '
                       'names to it). Leave the export settings visible.',
             'The export settings visibly show separate tracks in WAV format with the stem.wav destination.',
             [{'op': 'close-if-open', 'title': 'Export song'}, menu('Project', 'Export Song'),
              {'op': 'export-song', 'file': ('stem.wav',), 'format': 'WAV (Waveform Audio)',
               'mode': 'Export to separate tracks'}],
             [{'kind': 'files', 'folder': 'outputs', 'prefix': 'stem',
               'description': 'One file was written for each of Kick, Snare and Hat (named after the instrument).'},
              {'kind': 'file-audio', 'folder': 'outputs', 'prefix': 'stem', 'contains': 'Snare', 'format': 'wav',
               'summary': True, 'description': 'The Snare track holds only the Snare notes: timing, window levels and '
                                               'spectrum at any sample rate and depth.'}],
             requires={'visible': ['state-1']}, windows=['Export song'])], start=GROOVE)

    key = 'export-midi'
    add(key, 'export', list(SAMPLES) + ['midi.h2song'], 'midi.h2song', [
        step('single', f'Export the song as a MIDI file {path(key, "groove.mid")} with all instruments in a single '
                       'track. Reopen the MIDI export settings to display the saved choice.',
             'The MIDI export settings visibly show all instruments in one track and destination groove.mid.',
             [{'op': 'close-if-open', 'title': 'Export midi'}, menu('Project', 'Export MIDI File'),
              {'op': 'export-midi', 'file': ('groove.mid',), 'mode': 'SMF1 single: export all instruments to a single '
                                                                     'track'}, menu('Project', 'Export MIDI File')],
             [output('file-midi', 'groove.mid', description='groove.mid is a standard MIDI file with the song\'s notes '
                                                            'in one track.')],
             requires={'visible': ['state-1']}, windows=['Export midi']),
        step('tracks', f'Export the song again as a MIDI file {path(key, "groove-tracks.mid")}, now with each '
                       'instrument in a track of its own. Reopen the MIDI export settings to display the saved choice.',
             'The MIDI export settings visibly show separate instrument tracks and destination groove-tracks.mid.',
             [{'op': 'close-if-open', 'title': 'Export midi'}, menu('Project', 'Export MIDI File'),
              {'op': 'export-midi', 'file': ('groove-tracks.mid',),
               'mode': 'SMF1 multi: export each instrument to separate track'}, menu('Project', 'Export MIDI File')],
             [output('file-midi', 'groove-tracks.mid', description='groove-tracks.mid has one track per instrument.')],
             requires={'visible': ['state-1']}, windows=['Export midi'])], start='the song midi.h2song opened')

    key = 'export-lilypond'
    add(key, 'export', groove_docs, 'groove.h2song', [
        step('score', f'Export the song as a LilyPond file {path(key, "groove.ly")}, then display the saved file in the '
                     'application’s LilyPond export file browser (do not export it again).',
             'The application’s file browser visibly lists the saved groove.ly file in the requested output folder.',
             [menu('Project', 'Export LilyPond File'), {'op': 'answer', 'title': 'Hydrogen', 'button': 'OK'},
              {'op': 'save-dialog', 'file': ('groove.ly',)}, menu('Project', 'Export LilyPond File'),
              {'op': 'answer', 'title': 'Hydrogen', 'button': 'OK'},
              {'op': 'show-file', 'file': ('groove.ly', 'outputs')}],
             [output('file-text', 'groove.ly', description='groove.ly is the LilyPond score of the song.')],
             requires={'visible': ['state-1']}, windows=['Export LilyPond file'])], start=GROOVE)

    key = 'playlist'
    add(key, 'playlist', ['tone440.wav', 'tone880.wav', 'first.h2song', 'second.h2song'], None, [
        step('saved', f'In the playlist editor, add the songs {path(key, "first.h2song")} and then '
                      f'{path(key, "second.h2song")} to the playlist and save the playlist as '
                      f'{path(key, "set.h2playlist")}.',
             'The playlist editor lists two songs, first.h2song and then second.h2song (long paths may be cut off on '
             'screen), and its window names the playlist set.h2playlist.',
             [menu('View', 'Playlist Editor'),
              {'op': 'playlist-menu', 'item': 'Add song to Playlist'}, {'op': 'open-dialog', 'file': ('first.h2song',)},
              {'op': 'playlist-menu', 'item': 'Add song to Playlist'}, {'op': 'open-dialog', 'file': ('second.h2song',)},
              {'op': 'playlist-menu', 'item': 'Save Playlist as'}, {'op': 'save-dialog', 'file': ('set.h2playlist',),
                                                                     'stays': True}],
             [output('file-playlist', 'set.h2playlist', description='set.h2playlist lists first.h2song and '
                                                                     'second.h2song in this order.')]),
        step('removed', 'Remove first.h2song from the playlist and save the playlist again under the same name.',
             'The playlist editor lists only second.h2song.',
             [{'op': 'playlist-row', 'row': 0}, {'op': 'playlist-menu', 'item': 'Remove selected song from Playlist'},
              {'op': 'playlist-menu', 'item': 'Save Playlist'}],
             [output('file-playlist', 'set.h2playlist', description='set.h2playlist now lists only second.h2song.')],
             depends=['saved'])], start=DEFAULT)

    key = 'playback-track'
    add(key, 'song-editor', groove_docs + ['pad.wav'], 'groove.h2song', [
        step('loaded', f'Show the playback track of the song editor and choose {path(key, "pad.wav")} as the song\'s '
                       'playback track.',
             'The song editor shows the playback track lane, which names pad.wav.',
             [{'op': 'check', 'target': {'role': 'check box', 'name': 'View playback track'}, 'state': True},
              {'op': 'button', 'name': 'Choose playback track'}, {'op': 'browser', 'file': ('pad.wav',)}],
             [song('playback', description='The song\'s playback track is pad.wav from the input folder.')]),
        step('level', 'Unmute the playback track and set its volume to 0.8.',
             'The playback track is not muted and its volume control shows 0.80.',
             [{'op': 'check', 'target': {'role': 'check box', 'name': 'Mute playback track'}, 'state': False},
              knob('Playback track volume', 0.8)],
             [song('playback')], depends=['loaded'])], start=GROOVE)

    key = 'preferences'
    add(key, 'preferences', [], None, [
        step('changed', 'In the preferences, set the maximum number of bars to 300, confirm, then reopen the '
                        'preferences to display the saved value.',
             'The preferences visibly show the saved maximum number of bars as 300.',
             [menu('Options', 'Preferences'),
              {'op': 'fill', 'target': {'role': 'spin button', 'text': '400'}, 'value': '300'},
              {'op': 'button', 'name': 'OK'}, menu('Options', 'Preferences')],
             [{'kind': 'settings', 'keys': ['maxBars'],
               'description': 'The settings file stores 300 as the maximum number of bars.'}],
             requires={'visible': ['state-1']}, windows=['Preferences']),
        step('cancelled', 'In the preferences, change the maximum number of bars to 200, then cancel and reopen '
                          'the preferences to display the saved value.',
             'The preferences visibly show 300 as the maximum number of bars after the edit was cancelled.',
             [{'op': 'fill', 'target': {'role': 'spin button', 'text': '300'}, 'value': '200'},
              {'op': 'button', 'name': 'Cancel'}, menu('Options', 'Preferences')],
             [{'kind': 'settings', 'keys': ['maxBars'],
               'description': 'The cancelled change left 300 in the settings file.'}],
             depends=['changed'], requires={'visible': ['state-1'], 'state-1': ['changed/state-1']},
             windows=['Preferences'])], start=DEFAULT)
    from gui_extended import build as extended
    return episodes + [frozen_form(w) for w in extended()]
