from evaluation.contract import files_path
'''Reviewed user goals, acceptance conditions and independent checks for the LMMS GUI.

Reference recipes (reference/recipes.py) implement these specifications for the pinned standard; goals are authored
here and never translated from a click trace. An episode's input documents are uploaded into the runtime's input area
before its first checkpoint (setup item documents), so file dialogs accept them by name; requested projects and
exports are typed by name in the File name field of the dialogs and land in the runtime's project or output area.
LMMS has no scripting pipe: every assessed operation is a GUI goal, and state is read only from files the GUI wrote
(a saved project, exported audio) and from the settings file.
'''
import json
from document_fixtures import DESCRIPTIONS as DOCUMENTS

FILES = {
    'tone-440.wav': 'mono, 44,100 Hz, 1.0 s: steady 440 Hz sine, peak amplitude 0.5',
    'tone-880.wav': 'mono, 44,100 Hz, 1.0 s: steady 880 Hz sine, peak amplitude 0.4',
    'square-220.wav': 'mono, 44,100 Hz, 1.0 s: 220 Hz square wave, amplitude 0.25',
    'stereo-pair.wav': 'stereo, 44,100 Hz, 1.0 s: left channel 440 Hz sine (amplitude 0.3), right channel 880 Hz sine (amplitude 0.2)',
    'tone12.mid': 'Standard MIDI format 0: two notes, middle C and E, at 96 ticks per quarter note',
}
FILES.update(DOCUMENTS)
EQUIVALENTS = ['Menus, toolbar buttons, keyboard shortcuts, context menus and dialogs are equivalent routes to a product command.',
               'Any precise way of setting a numeric value is acceptable (typing it, the mouse wheel, a dialog); layout, wording and widget types may differ from any reference.',
               'Enter the given document paths in the File name field of a file dialog, then confirm with Return or with the Open or Save button of the dialog.']
BYPASSES = ['Do not use terminals, other applications or private files to perform a goal.',
            'Do not recreate a missing product command by other means, for example by loading a pre-edited file.']

# The runtime's document areas of one episode (they sit beside the product's instance directory).


def area(name):
    '''The document area an episode document belongs to: uploaded inputs, saved projects, or new outputs.'''
    if name in FILES:
        return 'inputs'
    return 'projects' if name.casefold().endswith(('.mmp', '.mmpz')) else 'outputs'


def path(episode, name):
    '''Documents are named by absolute paths in the runtime's document areas (file dialogs take them as typed).'''
    return files_path(area(name), name)


def step(key, goal, acceptance, recipe, checks=(), depends=(), lifecycle=None, visible=(), requires=None):
    '''requires maps an assertion of this checkpoint (visible or state-N) to the points it counts together with
    (state-N of this checkpoint or checkpoint/point).'''
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': list(recipe), 'checks': list(checks),
             'preparation': [], 'visible': list(visible), 'depends_on': list(depends), 'requires': dict(requires or {})}
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, documents, steps, *, start='the default new project'):
    items = []
    if documents:
        items.append({'id': 'documents', 'op': 'documents', 'files': list(documents)})
    for cp in steps:
        for action in cp.get('recipe') or []:
            if isinstance(action, dict) and 'file' in action:
                action['file'] = path(key, action['file'])
        companions = cp.pop('requires')
        cp['depends_on'] = ['setup:' + item['id'] for item in items] + cp['depends_on']
        cp['assertions'] = [{'id': key + '/' + cp['id'] + '/visible', 'channel': 'frontend', 'method': 'agent',
                             'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key + '/' + cp['id'] + f'/state-{i + 1}', 'channel': 'backend', 'method': 'program',
                'requirement': check.get('description', 'The independently read product file or setting matches the requested checkpoint.'),
                'check': check})
        for assertion in cp['assertions']:
            point = assertion['id'].rsplit('/', 1)[1]
            if point in companions:
                assertion['requires'] = [key + '/' + (r if '/' in r else cp['id'] + '/' + r) for r in companions[point]]
    files = {name: FILES[name] for name in documents}
    prepared = 'The application starts with ' + start + '.'
    inputs = {'documents': {path(key, name): description for name, description in files.items()},
              'outputs': 'Save requested projects and exports at the exact paths given; type the path in the File name field of the dialog.'}
    if files:
        inputs['how'] = 'These documents are files the application can open: type the absolute path in the File name field of its file dialog and confirm.'
    return {'id': key, 'feature': feature, 'execution': 'gui', 'scripting': False, 'documents': list(documents),
            'initial_state': 'Fresh application process, private desktop session and empty DATA_DIR. ' + prepared,
            'setup': items, 'inputs': inputs,
            'session': 'Operate the visible desktop application only. ' + prepared,
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            'budget': budget(len(steps), key),
            'checkpoints': steps}


def budget(checkpoints, episode=None):
    '''Desktop budgets include full-screen observations and leave headroom above measured oracle usage.'''
    calls = min(180, 50 + 30 * checkpoints)
    if episode == 'track-rename':
        calls = 150
    return {'calls': calls, 'seconds': min(2400, 600 + 240 * checkpoints), 'tokens': min(2_500_000, 14_000 * calls)}


def frozen_form(value):
    '''The manifest is compared with its JSON-frozen copy: use JSON types only.'''
    return json.loads(json.dumps(value, ensure_ascii=False))


# ------------------------------------------------------------------ checks (what is read; the values are frozen at record)
def written(name, description=None):
    value = {'kind': 'file-exists', 'path': name}
    if description:
        value['description'] = description
    return value


def saved(name, xpath, description=None, shallow=True, fields=None, ranges=None):
    value = {'kind': 'project-file', 'path': name, 'xpath': xpath, 'shallow': shallow}
    if fields is not None:
        value['fields'] = list(fields)
    if ranges:
        value['ranges'] = dict(ranges)
    if description:
        value['description'] = description
    return value


def exported(name, container='wav', tol='signal', slack=0, description=None):
    value = {'kind': 'file-audio', 'path': name, 'format': {'container': container}, 'tol': tol, 'slack': slack}
    if description:
        value['description'] = description
    return value


def setting(section, names, description=None):
    value = {'kind': 'settings', 'section': section, 'names': list(names)}
    if description:
        value['description'] = description
    return value


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(frozen_form(episode(*a, **kw)))

    # ------------------------------------------------------------ project
    key = 'project-tempo-save-reopen'
    target = path(key, 'session.mmpz')
    add(key, 'project', [], [
        step('tempo', 'Set the tempo of the project to 150 beats per minute.',
             'The tempo display of the toolbar reads 150.',
             [{'op': 'tempo', 'value': 150}]),
        step('saved', f'Save the project as {target}.',
             'The project is saved without an error message and its name session is shown in the window title.',
             [{'op': 'save-project', 'file': 'session.mmpz'}],
             [written('session.mmpz', 'The project file session.mmpz was written.'),
              saved('session.mmpz', './head', 'The saved project holds the tempo of 150.')],
             depends=['tempo'], requires={'visible': ['state-1']}),
        step('reopened', f'The application was restarted and shows a fresh default project. Open the saved project {target}.',
             'The tempo display of the toolbar reads 150 again.',
             [{'op': 'open-project', 'file': 'session.mmpz'}], lifecycle='restart', depends=['saved'])])

    # ------------------------------------------------------------ song editor
    key = 'tracks-add-and-save'
    target = path(key, 'tracks.mmpz')
    add(key, 'song-editor', [], [
        step('added', 'Add one more sample track and one more Beat/Bassline track to the project with the track buttons of the Song-Editor window (the window that lists TripleOscillator, Sample track, Beat/Bassline 0 and Automation track).',
             'The Song-Editor lists, below its four default tracks, a second Sample track and a track named Beat/Bassline 1.',
             [{'op': 'add-track', 'kind': 'sample'}, {'op': 'add-track', 'kind': 'beat'}]),
        step('saved', f'Save the project as {target}.',
             'The project is saved without an error message and its name tracks is shown in the window title.',
             [{'op': 'save-project', 'file': 'tracks.mmpz'}],
             [written('tracks.mmpz', 'The project file tracks.mmpz was written.'),
              saved('tracks.mmpz', './song/trackcontainer/track', 'The saved project lists its tracks with their type and name.')],
             depends=['added'], requires={'visible': ['state-1']})])

    # ------------------------------------------------------------ beat editor
    key = 'beat-step-toggle'
    target = path(key, 'beat.mmpz')
    add(key, 'beat-editor', [], [
        step('toggled', 'Open the Beat+Bassline Editor (it is closed in the default project; the main toolbar has a button for it) and switch on the third step, counting from the left, of its first row, the Kicker row.',
             'The Beat+Bassline Editor is open and the third step of the Kicker row is shown switched on; no other step of that row is on.',
             [{'op': 'beat-step', 'row': 0, 'step': 2}]),
        step('saved', f'Save the project as {target}.',
             'The project is saved without an error message and its name beat is shown in the window title.',
             [{'op': 'save-project', 'file': 'beat.mmpz'}],
             [written('beat.mmpz', 'The project file beat.mmpz was written.'),
              saved('beat.mmpz', './/pattern/note', 'The saved project lists the notes of its patterns with position, length and key.')],
             depends=['toggled'], requires={'visible': ['state-1']})])
    import specification_more
    episodes.extend(specification_more.build())
    return episodes
