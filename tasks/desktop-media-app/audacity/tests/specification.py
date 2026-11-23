"""Reviewed user goals, acceptance conditions, public setup and program checks for the GUI.

Reference recipes (reference/recipes.py) implement these specifications for the
pinned standard; goals are authored here and never translated from a click
trace. An episode's input documents are uploaded into the runtime's input area
before its first checkpoint (setup item "documents"), so file dialogs accept
them by name; requested outputs are typed by name in save and export dialogs
and land in the runtime's output or project area. Public scripting prepares
only non-target state (imports, prepared selections; setup item "project" and
per-checkpoint preparation); every assessed operation is a GUI goal. Native
episodes use no scripting at all.
"""
import json

FILES = {
    'tone-440.wav': 'mono, 44,100 Hz, 1.0 s: steady 440 Hz sine, peak amplitude 0.375',
    'tone-880.wav': 'mono, 44,100 Hz, 1.0 s: steady 880 Hz sine, peak amplitude 0.375',
    'ramp.wav': 'mono, 44,100 Hz, 1.0 s: a straight line rising from -0.5 at the start to +0.5 at the end',
    'segments.wav': ('mono, 44,100 Hz, 1.0 s, four sections: 0-0.25 s 440 Hz sine (amplitude 0.35), 0.25-0.375 s silence, '
                     '0.375-0.75 s 880 Hz sine (amplitude 0.25), 0.75-1.0 s 220 Hz square wave (amplitude 0.2)'),
    'stereo-pair.wav': 'stereo, 44,100 Hz, 1.0 s: left channel 440 Hz sine (amplitude 0.3), right channel 880 Hz sine (amplitude 0.2)',
    'chirp.wav': 'mono, 44,100 Hz, 1.0 s: sine sweep from 100 Hz to 2,000 Hz, amplitude 0.375',
    'dc-positive.wav': 'mono, 44,100 Hz, 1.0 s: a constant level of +0.125 (a flat line above zero)',
    'rate-48000.wav': 'mono, 48,000 Hz, 1.0 s: steady 440 Hz sine, peak amplitude 0.375',
    '剪辑 空间.wav': 'mono, 44,100 Hz, 1.0 s: same content as segments.wav; the file name is Chinese with a space',
    'invalid-not-audio.wav': 'a plain text file named like a WAV file; it contains no audio',
    'encoded-flac.flac': 'FLAC, mono, 44,100 Hz, 1.0 s: steady 440 Hz sine, peak amplitude 0.375',
    'encoded-mp3.mp3': 'MP3 (128 kbit/s), mono, 44,100 Hz, about 1.0 s: steady 440 Hz sine, peak amplitude 0.375',
}
EQUIVALENTS = ['Menus, toolbar buttons, keyboard shortcuts, context menus and dialogs are equivalent routes to a product command.',
               'Any precise way of setting a selection, time or numeric value is acceptable (time controls, typed values, '
               'menus); layout, wording and widget types may differ from any reference.',
               'Enter the given document paths in file dialogs: in an open dialog after Control+L, in a save or '
               'export dialog in its file-name field; then confirm with Return or the dialog\'s Open/Save button.']
BYPASSES = ['Do not use terminals, the scripting pipe, other applications, or private files to perform a goal.',
            'Do not recreate a missing product command by other means, for example by importing a pre-edited file.']
EXACT = 1/32768+1e-7
GAIN = 2/32768


# The runtime's document areas of one episode (they sit beside the product's instance directory).
from evaluation.contract import files_path


def area(name):
    """The document area an episode document belongs to: uploaded inputs, saved projects, or new outputs."""
    if name in FILES:
        return 'inputs'
    return 'projects' if name.casefold().endswith(('.aup', '.aup3')) else 'outputs'


def path(episode, name):
    """Documents are named by absolute paths in the runtime's document areas (file dialogs take them as typed)."""
    return files_path(area(name), name)


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    if '\n' not in value:
        return '"'+value+'"'
    ending = ' It ends with a line break.' if value.endswith('\n') else ''
    return 'exactly the lines between the ``` fences (the line breaks are part of the text).'+ending+'\n```\n'+value.removesuffix('\n')+'\n```\n'


def step(key, goal, acceptance, recipe, checks=(), setup=(), depends=(), lifecycle=None, visible=(), requires=None):
    """requires maps an assertion of this checkpoint ('visible' or 'state-N') to the points it counts together
    with ('state-N' of this checkpoint or '<checkpoint>/<point>')."""
    value = {'id': key, 'goal': goal, 'acceptance': acceptance, 'recipe': list(recipe), 'checks': list(checks),
             'preparation': list(setup), 'visible': list(visible), 'depends_on': list(depends),
             'requires': dict(requires or {})}
    if lifecycle:
        value['lifecycle'] = lifecycle
    return value


def episode(key, feature, documents, setup, steps, *, scripting=True, start='an empty project'):
    items = []
    if documents:
        items.append({'id': 'documents', 'op': 'documents', 'files': list(documents)})
    if setup:
        items.append({'id': 'project', 'op': 'scripted', 'operations': list(setup)})
    for cp in steps:
        for action in cp.get('recipe') or []:
            if isinstance(action, dict) and 'file' in action:
                action['file'] = path(key, action['file'])
        companions = cp.pop('requires')
        cp['depends_on'] = ['setup:'+item['id'] for item in items]+cp['depends_on']
        cp['assertions'] = [{'id': key+'/'+cp['id']+'/visible', 'channel': 'frontend', 'method': 'agent', 'requirement': cp['acceptance']}]
        for i, check in enumerate(cp['checks']):
            cp['assertions'].append({'id': key+'/'+cp['id']+f'/state-{i+1}', 'channel': 'backend', 'method': 'program',
                'requirement': check.get('description', 'The independently read product state or exported artifact matches the requested checkpoint.'),
                'check': check})
        for assertion in cp['assertions']:
            point = assertion['id'].rsplit('/', 1)[1]
            if point in companions:
                assertion['requires'] = [key+'/'+(r if '/' in r else cp['id']+'/'+r) for r in companions[point]]
    files = {name: FILES[name] for name in documents}
    prepared = ('Before the first checkpoint the framework prepared: '+start+'.') if setup else 'The application starts with '+start+'.'
    inputs = {'documents': {path(key, name): description for name, description in files.items()},
              'outputs': 'Save requested outputs at the exact paths given; type the path in the save or export '
                         'dialog\'s file-name field.'}
    if files:
        inputs['how'] = ('These documents are files the application can open: type the absolute path in its file '
                         'dialog (in an open dialog press Control+L first) and confirm.')
    return {'id': key, 'feature': feature, 'execution': 'gui', 'scripting': scripting, 'documents': list(documents),
            'initial_state': 'Fresh application process, private desktop session and empty DATA_DIR. '+prepared,
            'setup': items, 'inputs': inputs,
            'session': 'Operate the visible desktop application only. '+prepared,
            'allowed_equivalents': EQUIVALENTS, 'forbidden_bypasses': BYPASSES,
            # Desktop calibration: each call carries a full-screen screenshot and the
            # accessible controls (about 10-15k tokens), so tokens scale with calls.
            'budget': budget(len(steps)),
            'checkpoints': steps}


def budget(checkpoints):
    calls = min(180, 50+30*checkpoints)
    return {'calls': calls, 'seconds': min(2400, 600+240*checkpoints), 'tokens': min(2_500_000, 14_000*calls)}


def frozen_form(value):
    """The manifest is compared with its JSON-frozen copy: use JSON types only."""
    return json.loads(json.dumps(value, ensure_ascii=False))


# ------------------------------------------------------------------ helpers
def imported(*names):
    ops = [{'op': 'import', 'file': name} for name in names]
    # Cosmetic: show the whole project, as File > Open does. Ignored when unsupported.
    return ops+[{'op': 'command', 'command': 'FitInWindow', 'optional': True}]


def select(start, end, track=0, count=1):
    return {'op': 'select', 'start': start, 'end': end, 'track': track, 'count': count}


def select_time(start, end):
    return {'op': 'command', 'command': 'SelectTime', 'params': {'Start': start, 'End': end}}


def audio(source, ops=(), channels=1, description=None, **extra):
    value = {'kind': 'audio', 'channels': channels, 'expect': {'source': source, 'ops': [list(o) for o in ops]}, **extra}
    if description:
        value['description'] = description
    return value


def measured(channels=1, description=None, **extra):
    """Effects without a closed form: frozen projection of the decoded export."""
    value = {'kind': 'audio', 'channels': channels, 'projection': True, **extra}
    if description:
        value['description'] = description
    return value


def exported(name, source, ops=(), channels=1, fmt='wav', description=None, **extra):
    value = {'kind': 'file-audio', 'path': name, 'format': {'container': fmt}, 'channels': channels,
             'expect': {'source': source, 'ops': [list(o) for o in ops]}, 'tolerance': GAIN, **extra}
    if description:
        value['description'] = description
    return value


def exported_segment(name, source, start, end, channels=1, description=None):
    """A GUI-made selection: exact interior samples, boundaries within 2 ms of the request."""
    value = {'kind': 'file-audio', 'path': name, 'format': {'container': 'wav'}, 'channels': channels, 'tolerance': GAIN,
             'segment': {'source': source, 'start': start, 'end': end, 'within': .002}}
    if description:
        value['description'] = description
    return value


def tracks(*rows, fields=('kind', 'channels', 'start', 'end'), description=None, within=None):
    value = {'kind': 'tracks', 'fields': list(fields), 'expect': list(rows)}
    if within is not None:
        value['within'] = within
    if description:
        value['description'] = description
    return value


def wave(channels=1, start=0.0, end=1.0, **extra):
    return {'kind': 'wave', 'channels': channels, 'start': float(start), 'end': float(end), **extra}


def dialog(menu, title, fields=(), button='OK', **extra):
    return {'op': 'dialog', 'menu': list(menu), 'title': title, 'fields': [list(f) for f in fields], 'button': button, **extra}


CUT_END = 38587/44100        # segments.wav after cutting 0.25-0.375 s (11025..16538)


def build():
    episodes = []

    def add(*a, **kw):
        episodes.append(frozen_form(episode(*a, **kw)))

    # ------------------------------------------------------------ import
    key = 'import-stereo-second-cancel'
    add(key, 'import', ['stereo-pair.wav', 'rate-48000.wav'], [], [
        step('stereo', f'Import the audio file {path(key, "stereo-pair.wav")} into the empty project.',
             'One stereo track named stereo-pair, about 1.0 s long, is shown: the upper channel holds the larger 440 Hz wave '
             '(amplitude 0.3), the lower channel the smaller 880 Hz wave (amplitude 0.2).',
             [{'op': 'open', 'file': 'stereo-pair.wav', 'via': 'import'}],
             [tracks(wave(2)), audio('stereo-pair.wav', channels=2, description='Exporting the project gives exactly the samples of stereo-pair.wav.')]),
        step('second', f'Import the audio file {path(key, "rate-48000.wav")} into the same project as an additional track.',
             'The project now shows two tracks: stereo-pair and below it a mono track named rate-48000, also about 1.0 s long.',
             [{'op': 'open', 'file': 'rate-48000.wav', 'via': 'import'}],
             [tracks(wave(2), wave(1), description='GetInfo lists the stereo track and a second 1.0 s mono track.')], depends=['stereo']),
        step('cancelled', 'Start importing another audio file, then cancel the file dialog without choosing a file.',
             'The file dialog is closed and the project still shows exactly the same two tracks.',
             [{'op': 'cancel-chooser', 'menu': ['File', 'Import', 'Audio...']}],
             [tracks(wave(2), wave(1), description='The cancelled import left the two tracks unchanged.')], depends=['second'],
             requires={'visible': ['second/state-1'], 'state-1': ['second/state-1']})])

    key = 'import-unicode-name'
    add(key, 'import', ['剪辑 空间.wav'], [], [
        step('imported', f'Import the audio file {path(key, "剪辑 空间.wav")} into the empty project.',
             'One mono track, about 1.0 s long, shows the four sections of the signal; its displayed track name is 剪辑 空间.',
             [{'op': 'open', 'file': '剪辑 空间.wav', 'via': 'import'}],
             [{'kind': 'visible-name', 'text': '剪辑 空间', 'description': 'The Unicode track name is published in the accessible desktop or public track metadata.'},
              audio('剪辑 空间.wav', description='Exporting the project gives exactly the imported samples.')])])

    key = 'import-damaged-file'
    add(key, 'import', ['tone-440.wav', 'invalid-not-audio.wav'], imported('tone-440.wav'), [
        step('rejected', f'Try to import {path(key, "invalid-not-audio.wav")} into the current project. If the application reports '
                         'a problem, leave its message open on the screen.',
             'A message on the screen reports that the file could not be imported as audio; the project behind it still '
             'contains only the unchanged tone-440 track.',
             [{'op': 'open', 'file': 'invalid-not-audio.wav', 'via': 'import', 'expect_error': 'Error Importing', 'leave_open': True}],
             [tracks(wave(1)), audio('tone-440.wav', description='The project audio is still exactly tone-440.wav.')],
             requires={'state-1': ['visible'], 'state-2': ['visible']})], start='tone-440.wav imported as one track')

    key = 'import-compressed-files'
    add(key, 'import', ['encoded-flac.flac', 'encoded-mp3.mp3'], [], [
        step('flac', f'Import the FLAC file {path(key, "encoded-flac.flac")} into the empty project.',
             'One mono track named encoded-flac, about 1.0 s long, shows a steady sine wave of amplitude about 0.375.',
             [{'op': 'open', 'file': 'encoded-flac.flac', 'via': 'import'}],
             [tracks(wave(1)), audio('encoded-flac.flac', description='The imported FLAC audio exports to exactly its decoded samples.')]),
        step('mp3', f'Import the MP3 file {path(key, "encoded-mp3.mp3")} into the same project as an additional track.',
             'A second mono track named encoded-mp3 appears below the first, about 1.0 s long, with a similar steady wave.',
             [{'op': 'open', 'file': 'encoded-mp3.mp3', 'via': 'import'}],
             [tracks(wave(1), wave(1, end=1.0), within=.06, description='Two mono tracks of about 1.0 s (MP3 padding tolerated).')],
             depends=['flac'])])

    # ------------------------------------------------------------ export
    key = 'export-formats'
    add(key, 'export', ['stereo-pair.wav'], imported('stereo-pair.wav'), [
        step('flac', f'Export the whole project as a FLAC file named {path(key, "stereo.flac")}.',
             'The export completes without an error message; the project is unchanged.',
             [{'op': 'export', 'menu': ['File', 'Export', 'Export Audio...'], 'format': 'FLAC Files', 'file': 'stereo.flac'}],
             [exported('stereo.flac', 'stereo-pair.wav', channels=2, fmt='flac', tolerance=EXACT,
                       description='stereo.flac is FLAC and decodes to exactly the stereo samples.')],
             requires={'visible': ['state-1']}),
        step('ogg', f'Export the whole project as an Ogg Vorbis file named {path(key, "stereo.ogg")}.',
             'The export completes without an error message; the project is unchanged.',
             [{'op': 'export', 'menu': ['File', 'Export', 'Export as OGG'], 'file': 'stereo.ogg'}],
             [{'kind': 'file-audio', 'path': 'stereo.ogg', 'format': {'container': 'ogg'}, 'channels': 2, 'sample_rate': 44100,
               'lossy': 'stereo-pair.wav', 'description': 'stereo.ogg is Ogg Vorbis, stereo 44,100 Hz, recognisably the same two signals.'}],
             requires={'visible': ['state-1']}),
        step('mp3', f'Export the whole project as an MP3 file named {path(key, "stereo.mp3")}.',
             'The export completes without an error message; the project is unchanged.',
             [{'op': 'export', 'menu': ['File', 'Export', 'Export as MP3'], 'file': 'stereo.mp3'}],
             [{'kind': 'file-audio', 'path': 'stereo.mp3', 'format': {'container': 'mp3'}, 'channels': 2, 'sample_rate': 44100,
               'lossy': 'stereo-pair.wav', 'description': 'stereo.mp3 is MP3, stereo 44,100 Hz, recognisably the same two signals.'}],
             requires={'visible': ['state-1']})], start='stereo-pair.wav imported as one stereo track')

    key = 'export-selected-range'
    add(key, 'export', ['ramp.wav'], imported('ramp.wav'), [
        step('selected', 'Select the time range from 0.200 s to 0.700 s of the track, each boundary within 1 ms (for example a '
                         'selection shown as 0.200-0.700 s or 0.201-0.699 s is fine).',
             'The selection highlight covers 0.2-0.7 s of the ramp, and any displayed selection times read 0.200 s and 0.700 s.',
             [{'op': 'selection', 'start': .2, 'end': .7}],
             [{'kind': 'selected-audio', 'channels': 1, 'tolerance': GAIN,
               'segment': {'source': 'ramp.wav', 'start': .2, 'end': .7, 'within': .002},
               'description': 'The current selection exports as the ramp samples from 0.2 s to 0.7 s (boundaries within 2 ms).'}]),
        step('exported', 'Export only the selected audio (the Export Selected Audio command; Export Audio and its '
                         f'shortcut Ctrl+Shift+E would write the whole track) as a WAV file named {path(key, "part.wav")}.',
             'The export completes without an error message; the 0.2-0.7 s selection is still shown.',
             [{'op': 'export', 'menu': ['File', 'Export', 'Export Selected Audio...'], 'file': 'part.wav'}],
             [exported_segment('part.wav', 'ramp.wav', .2, .7, description='part.wav holds the ramp samples from 0.2 s to 0.7 s (boundaries within 2 ms).')],
             depends=['selected'], requires={'visible': ['state-1']})], start='ramp.wav imported as one track')

    key = 'project-rate-export'
    add(key, 'project', ['tone-440.wav'], imported('tone-440.wav'), [
        step('rate', 'Change the project sample rate to 22050 Hz.',
             'The project rate control shows 22050 Hz; the track itself is unchanged.',
             [{'op': 'project-rate', 'value': '22050'}]),
        step('exported', f'Export the whole project as a WAV file named {path(key, "resampled.wav")}.',
             'The export completes without an error message.',
             [{'op': 'export', 'file': 'resampled.wav'}],
             [{'kind': 'file-audio', 'path': 'resampled.wav', 'format': {'container': 'wav'}, 'channels': 1, 'sample_rate': 22050,
               'frames': 22050, 'signal': {'dominant_hz': {'value': 440, 'within': 22}},
               'description': 'resampled.wav is 22,050 Hz, 1.0 s, still a 440 Hz tone.'}], depends=['rate'],
             requires={'visible': ['state-1']})], start='tone-440.wav imported as one track')

    # ------------------------------------------------------------ native (no scripting)
    key = 'native-ramp-reverse-export'
    add(key, 'native-episode', ['ramp.wav'], [], [
        step('opened', f'Open the audio file {path(key, "ramp.wav")} in the application.',
             'One mono audio track named ramp is shown, about 1.0 s long; its waveform rises steadily from about -0.5 to about +0.5.',
             [{'op': 'open', 'file': 'ramp.wav'}]),
        step('reversed', 'Apply the Reverse effect to the whole track.',
             'The track still lasts about 1.0 s, and its waveform now falls steadily from about +0.5 to about -0.5.',
             [{'op': 'press', 'key': 'Ctrl+a'}, {'op': 'menu', 'path': ['Effect', 'Reverse']}], depends=['opened']),
        step('exported', f'Export the whole project as a WAV file named {path(key, "reversed.wav")} (16-bit PCM is fine). '
                         'Confirm any follow-up dialog of the export with its default button.',
             'The export finishes without an error message and the project still shows the falling (reversed) waveform.',
             [{'op': 'export', 'file': 'reversed.wav'}],
             [exported('reversed.wav', 'ramp.wav', [('reverse',)], sample_rate=44100,
                       description='reversed.wav decodes to every sample of ramp.wav in reverse order, mono 44,100 Hz.')],
             depends=['reversed'], requires={'visible': ['state-1']}),
        step('restored', 'Restore the state before the Reverse effect with the real Undo command, then export the whole project '
                         f'as a WAV file named {path(key, "restored.wav")}.',
             'The waveform rises again from about -0.5 to about +0.5, and the export finishes without an error message.',
             [{'op': 'undo'}, {'op': 'export', 'file': 'restored.wav'}],
             [exported('restored.wav', 'ramp.wav', description='restored.wav decodes to the original ramp samples.')],
             depends=['exported'])], scripting=False)

    key = 'native-stereo-delete-history'
    add(key, 'native-episode', ['stereo-pair.wav'], [], [
        step('opened', f'Open the audio file {path(key, "stereo-pair.wav")} in the application.',
             'One stereo track named stereo-pair is shown, about 1.0 s long, with the larger 440 Hz wave above the smaller 880 Hz wave.',
             [{'op': 'open', 'file': 'stereo-pair.wav'}]),
        step('deleted', 'Select from 0.500 s (within 1 ms) to the end of the track at 1.000 s and delete that audio.',
             'The track now ends at about 0.5 s; both channels keep their waves up to that point.',
             [{'op': 'selection', 'start': .5, 'end': 1.0}, {'op': 'menu', 'path': ['Edit', 'Delete']}], depends=['opened']),
        step('exported', f'Export the whole project as a WAV file named {path(key, "first-half.wav")}.',
             'The export finishes without an error message; the 0.5 s track is still shown.',
             [{'op': 'export', 'file': 'first-half.wav'}],
             [exported_segment('first-half.wav', 'stereo-pair.wav', 0, .5, channels=2,
                               description='first-half.wav holds the first 0.5 s of both channels (boundary within 2 ms).')], depends=['deleted'],
             requires={'visible': ['state-1']}),
        step('undone', 'Restore the deleted audio with the real Undo command, then export the whole project as a WAV file named '
                       f'{path(key, "undone.wav")}.',
             'The track is about 1.0 s long again and the export finishes without an error message.',
             [{'op': 'undo'}, {'op': 'export', 'file': 'undone.wav'}],
             [exported('undone.wav', 'stereo-pair.wav', channels=2, description='undone.wav holds the full original stereo audio.')],
             depends=['exported']),
        step('redone', 'Re-apply the deletion with the real Redo command, then export the whole project as a WAV file named '
                       f'{path(key, "redone.wav")}.',
             'The track ends at about 0.5 s again and the export finishes without an error message.',
             [{'op': 'redo'}, {'op': 'export', 'file': 'redone.wav'}],
             [exported_segment('redone.wav', 'stereo-pair.wav', 0, .5, channels=2,
                               description='redone.wav holds the first 0.5 s again (boundary within 2 ms).')], depends=['undone'])], scripting=False)

    # ------------------------------------------------------------ editing
    key = 'edit-segments-cut-paste-history'
    add(key, 'editing', ['segments.wav'], imported('segments.wav'), [
        step('cut-gap', 'The framework selected 0.25-0.375 s of the track (the silent section). Cut the selected audio.',
             'The silent section is gone: the 880 Hz section now follows the 440 Hz section directly and the track ends at about 0.875 s.',
             [{'op': 'menu', 'path': ['Edit', 'Cut']}], [audio('segments.wav', [('cut', .25, .375)])],
             setup=[select(.25, .375)]),
        step('paste-end', 'The framework placed the cursor at the end of the track (about 0.875 s). Paste the audio you cut there.',
             'The track is about 1.0 s long again and ends with the 0.125 s silent section after the square-wave section.',
             [{'op': 'menu', 'path': ['Edit', 'Paste']}], [audio('segments.wav', [('cut', .25, .375), ('paste', 'end', .25, .375)])],
             setup=[select(CUT_END, CUT_END)], depends=['cut-gap']),
        step('undo-cut', 'Restore the state before the cut with the real Undo command (undo the paste and the cut).',
             'The original layout is back: 440 Hz section, silence at 0.25-0.375 s, 880 Hz section, square-wave section, about 1.0 s in total.',
             [{'op': 'undo'}, {'op': 'undo'}], [audio('segments.wav')], depends=['paste-end']),
        step('redo-cut', 'Use the real Redo command to re-apply only the cut (not the paste).',
             'The silent section is removed again and the track ends at about 0.875 s.',
             [{'op': 'redo'}], [audio('segments.wav', [('cut', .25, .375)])], depends=['undo-cut'])], start='segments.wav imported as one track')

    key = 'edit-ramp-silence-delete-trim'
    add(key, 'editing', ['ramp.wav'], imported('ramp.wav'), [
        step('silenced', 'The framework selected 0.25-0.5 s of the track. Replace the selected audio with silence, keeping the track length.',
             'Between 0.25 s and 0.5 s the waveform is a flat line at zero; the rest of the ramp is unchanged and the track still lasts 1.0 s.',
             [{'op': 'menu', 'path': ['Edit', 'Remove Special', 'Silence Audio']}],
             [audio('ramp.wav', [('silence', .25, .5)])], setup=[select(.25, .5)]),
        step('deleted', 'The framework selected 0.75-1.0 s of the track. Delete the selected audio.',
             'The track now ends at about 0.75 s; the silent section is still at 0.25-0.5 s.',
             [{'op': 'menu', 'path': ['Edit', 'Delete']}],
             [audio('ramp.wav', [('silence', .25, .5), ('cut', .75, 1.0)])], setup=[select(.75, 1.0)], depends=['silenced']),
        step('trimmed', 'The framework selected 0.1-0.6 s of the track. Keep only the selected audio and remove everything outside it.',
             'Only the audio from 0.1 s to 0.6 s remains (including part of the silent section); nothing remains before 0.1 s or after 0.6 s.',
             [{'op': 'menu', 'path': ['Edit', 'Remove Special', 'Trim Audio']}],
             [audio('ramp.wav', [('silence', .25, .5), ('cut', .75, 1.0), ('trim', .1, .6)])], setup=[select(.1, .6)], depends=['deleted'])], start='ramp.wav imported as one track')

    key = 'edit-clips-split-join'
    add(key, 'editing', ['segments.wav'], imported('segments.wav'), [
        step('split', 'The framework selected 0.25-0.75 s. Split the clip at the boundaries of the selected region without removing any audio.',
             'The track is divided into three clips with visible boundaries at 0.25 s and 0.75 s; all audio is still present.',
             [{'op': 'menu', 'path': ['Edit', 'Clip Boundaries', 'Split']}],
             [{'kind': 'clips', 'expect': [[0, 0, .25], [0, .25, .75], [0, .75, 1.0]]}, audio('segments.wav')],
             setup=[select(.25, .75)]),
        step('split-delete', 'The framework selected 0.5-0.6 s. Remove the selected audio but leave an empty gap in its place, so that the '
                             'later audio keeps its time position (a split delete; an ordinary delete would close the gap).',
             'An empty gap without audio appears from 0.5 s to 0.6 s; the track is not shortened and the square-wave section still ends at 1.0 s.',
             [{'op': 'menu', 'path': ['Edit', 'Remove Special', 'Split Delete']}],
             [{'kind': 'clips', 'expect': [[0, 0, .25], [0, .25, .5], [0, .6, .75], [0, .75, 1.0]]}, audio('segments.wav', [('silence', .5, .6)])],
             setup=[select(.5, .6)], depends=['split']),
        step('joined', 'The framework selected the whole track. Join the clips into one clip.',
             'The track shows a single clip from 0 s to 1.0 s without clip boundaries; the former gap is silence inside it.',
             [{'op': 'menu', 'path': ['Edit', 'Clip Boundaries', 'Join']}],
             [{'kind': 'clips', 'expect': [[0, 0, 1.0]]}, audio('segments.wav', [('silence', .5, .6)])],
             setup=[select(0, 1)], depends=['split-delete'])], start='segments.wav imported as one track')

    key = 'edit-duplicate-split-new'
    add(key, 'editing', ['tone-440.wav'], imported('tone-440.wav'), [
        step('duplicated', 'The framework selected 0.25-0.75 s. Duplicate the selected audio into a new track.',
             'A second track appears that contains audio only from 0.25 s to 0.75 s; the original track is unchanged.',
             [{'op': 'menu', 'path': ['Edit', 'Duplicate']}],
             [tracks(wave(1), wave(1, .25, .75))], setup=[select(.25, .75)]),
        step('split-new', 'The framework selected 0-0.25 s of the first track. Move the selected audio into a new track of its own, '
                          'leaving a gap in the first track (Split New).',
             'A third track contains audio from 0 s to 0.25 s, and the first track now starts with a gap until 0.25 s.',
             [{'op': 'menu', 'path': ['Edit', 'Clip Boundaries', 'Split New']}],
             [tracks(wave(1, .25, 1.0), wave(1, .25, .75), wave(1, 0, .25))], setup=[select(0, .25)], depends=['duplicated'])], start='tone-440.wav imported as one track')

    key = 'history-three-edits'
    add(key, 'history', ['segments.wav'], imported('segments.wav'), [
        step('amplified', 'The framework selected the whole track. Apply the Amplify effect with an amplification of exactly -6 dB.',
             'All four sections keep their shape but are about half as tall as before.',
             [dialog(['Effect', 'Amplify...'], 'Amplify', [('Amplification', '-6')])],
             [audio('segments.wav', [('gain', -6)], tolerance=GAIN)], setup=[select(0, 1)]),
        step('silenced', 'The framework selected 0.75-1.0 s (the square-wave section). Replace the selected audio with silence.',
             'The square-wave section at 0.75-1.0 s is now a flat line at zero; the track still lasts 1.0 s.',
             [{'op': 'menu', 'path': ['Edit', 'Remove Special', 'Silence Audio']}],
             [audio('segments.wav', [('gain', -6), ('silence', .75, 1.0)], tolerance=GAIN)], setup=[select(.75, 1.0)],
             depends=['amplified']),
        step('deleted', 'The framework selected 0-0.25 s (the 440 Hz section). Delete the selected audio.',
             'The track now starts with the silent section, is about 0.75 s long and ends with the flat (silenced) part.',
             [{'op': 'menu', 'path': ['Edit', 'Delete']}],
             [audio('segments.wav', [('gain', -6), ('silence', .75, 1.0), ('cut', 0, .25)], tolerance=GAIN)], setup=[select(0, .25)],
             depends=['silenced']),
        step('undone', 'Restore the original imported audio with the real Undo command: undo the deletion, the silencing and the '
                       'amplification, but keep the imported track.',
             'The original four full-height sections are shown again over 1.0 s.',
             [{'op': 'undo'}, {'op': 'undo'}, {'op': 'undo'}], [audio('segments.wav')], depends=['deleted']),
        step('redone', 'Re-apply all three edits with the real Redo command.',
             'The track is again about 0.75 s long: half-height silence-gap, 880 Hz and flat sections.',
             [{'op': 'redo'}, {'op': 'redo'}, {'op': 'redo'}],
             [audio('segments.wav', [('gain', -6), ('silence', .75, 1.0), ('cut', 0, .25)], tolerance=GAIN)], depends=['undone'])], start='segments.wav imported as one track')

    # ------------------------------------------------------------ effects
    key = 'effect-amplify-cancel-apply'
    add(key, 'effects', ['tone-440.wav'], imported('tone-440.wav')+[select(0, 1)], [
        step('cancelled', 'Open the Amplify effect for the selected audio, enter an amplification of -6 dB, then cancel the dialog.',
             'The Amplify dialog is closed and the waveform is unchanged (peak still about 0.375).',
             [dialog(['Effect', 'Amplify...'], 'Amplify', [('Amplification', '-6')], 'Cancel')],
             [audio('tone-440.wav')], requires={'visible': ['amplified/state-1'], 'state-1': ['amplified/state-1']}),
        step('amplified', 'The framework selected the whole track. Apply the Amplify effect with an amplification of exactly -6 dB.',
             'The waveform is visibly smaller: its peak is about half of the original (about 0.19 instead of 0.375).',
             [dialog(['Effect', 'Amplify...'], 'Amplify', [('Amplification', '-6')])],
             [audio('tone-440.wav', [('gain', -6)], tolerance=GAIN)], setup=[select(0, 1)], depends=['cancelled'])], start='tone-440.wav imported as one track and fully selected')

    key = 'effect-normalize-dc'
    add(key, 'effects', ['dc-positive.wav'], imported('dc-positive.wav')+[select(0, 1)], [
        step('normalized', 'Apply the Normalize effect to the selected audio with DC offset removal enabled and the peak amplitude normalized to -1.0 dB.',
             'The flat line moves from +0.125 to 0: the track is now silent at the zero line and still lasts 1.0 s.',
             [dialog(['Effect', 'Normalize...'], 'Normalize', [])],
             [audio('dc-positive.wav', [('silence', 0, 1.0)])])], start='dc-positive.wav imported as one track and fully selected')

    key = 'effect-fades'
    add(key, 'effects', ['tone-440.wav'], imported('tone-440.wav'), [
        step('fade-in', 'The framework selected 0-0.5 s. Apply a Fade In to the selected audio exactly once (a second '
                        'application would bend the straight ramp into a curve).',
             'The waveform grows linearly from zero amplitude at 0 s to full amplitude at 0.5 s (about half amplitude at '
             '0.25 s); the second half is unchanged.',
             [{'op': 'menu', 'path': ['Effect', 'Fade In']}], [measured()], setup=[select(0, .5)]),
        step('fade-out', 'The framework selected 0.5-1.0 s. Apply a Fade Out to the selected audio exactly once (a second '
                         'application would bend the straight ramp into a curve).',
             'The waveform now also shrinks linearly from full amplitude at 0.5 s to zero at 1.0 s (about half amplitude at '
             '0.75 s), a symmetric diamond-like envelope.',
             [{'op': 'menu', 'path': ['Effect', 'Fade Out']}], [measured()], setup=[select(.5, 1.0)], depends=['fade-in'])], start='tone-440.wav imported as one track')

    key = 'effect-change-speed'
    add(key, 'effects', ['tone-440.wav'], imported('tone-440.wav')+[select(0, 1)], [
        step('faster', 'Apply the Change Speed effect to the selected audio with a percent change of exactly +25 (25% faster).',
             'The track becomes shorter, about 0.8 s long, with a visibly denser (higher-pitched) wave.',
             [dialog(['Effect', 'Change Speed...'], 'Change Speed', [('Percent Change', '25')])],
             [measured(signal={'dominant_hz': {'value': 550, 'within': 25}})])], start='tone-440.wav imported as one track and fully selected')

    key = 'effect-repeat'
    add(key, 'effects', ['ramp.wav'], imported('ramp.wav')+[select(0, 1)], [
        step('repeated', 'Apply the Repeat effect to the selected audio so that 2 repeats are added after it.',
             'The track is now about 3.0 s long and shows the same rising ramp three times in a row.',
             [dialog(['Effect', 'Repeat...'], 'Repeat', [('Number of repeats', '2')]), {'op': 'fit'}],
             [audio('ramp.wav', [('repeat', 2)])])], start='ramp.wav imported as one track and fully selected')

    key = 'effect-echo'
    add(key, 'effects', ['segments.wav'], imported('segments.wav')+[select(0, 1)], [
        step('echoed', 'Apply the Echo effect to the selected audio with a delay time of 0.25 seconds and a decay factor of 0.5.',
             'Echoes appear: the formerly silent section at 0.25-0.375 s now contains a quieter copy of the 440 Hz section; the track still lasts 1.0 s.',
             [dialog(['Effect', 'Echo...'], 'Echo', [('Delay time', '0.25'), ('Decay factor', '0.5')])], [measured()])], start='segments.wav imported as one track and fully selected')

    key = 'effect-low-pass'
    add(key, 'effects', ['chirp.wav'], imported('chirp.wav')+[select(0, 1)], [
        step('filtered', 'Apply a low-pass filter to the selected audio with a cutoff frequency of 500 Hz and a roll-off of 24 dB per octave.',
             'The sweep keeps its low-frequency start, while its higher-frequency remainder becomes much quieter; the track still lasts 1.0 s.',
             [dialog(['Effect', 'Plug-in 1 to 15', 'Low-Pass Filter...'], 'Low-Pass Filter', [('Frequency', '500')],
                     choices=[('Roll-off', '24 dB')])],
             [measured()])], start='chirp.wav imported as one track and fully selected')

    # ------------------------------------------------------------ generation
    key = 'generate-tone'
    add(key, 'generation', [], [select_time(0, 2.0)], [
        step('tone', 'The framework selected 0-2.0 s in the empty project. Generate a sine tone of 880 Hz with amplitude 0.5 that lasts 2.0 s.',
             'A new mono track with a steady sine wave appears; it lasts about 2.0 s and reaches about ±0.5.',
             [dialog(['Generate', 'Tone...'], 'Tone', [('Frequency', '880'), ('Amplitude', '0.5')])],
             [{'kind': 'audio', 'channels': 1, 'frames': 88200, 'signal': {'peak': {'value': .5, 'within': .002},
               'dominant_hz': {'value': 880, 'within': 22}}, 'description': 'The project exports as 2.0 s mono with an 880 Hz peak-0.5 sine.'}])], start='an empty project with the time range 0-2.0 s selected')

    key = 'generate-noise-in-selection'
    add(key, 'generation', ['tone-440.wav'], imported('tone-440.wav'), [
        step('noise', 'The framework selected 0.25-0.75 s. Replace the selected audio with white noise of amplitude 0.2.',
             'The middle section from 0.25 s to 0.75 s now shows noise instead of the tone; the tone before and after is unchanged.',
             [dialog(['Generate', 'Noise...'], 'Noise', [('Amplitude', '0.2')], choices=[('Noise type', 'White')])],
             [{'kind': 'audio', 'channels': 1, 'frames': 44100, 'expect': {'source': 'tone-440.wav', 'ops': []},
               'mask': [[.25, .75]], 'region': {'start': .25, 'end': .75, 'rms': [.09, .14]},
               'description': 'Outside 0.25-0.75 s the export equals tone-440.wav; inside it is white noise of RMS about 0.115.'}],
             setup=[select(.25, .75)])], start='tone-440.wav imported as one track')

    # ------------------------------------------------------------ labels
    key = 'labels-unicode-edit-export'
    add(key, 'labels', ['segments.wav'], imported('segments.wav'), [
        step('region-label', 'The framework selected 0.25-0.375 s. Create a region label from this selection, so that it covers exactly '
                             '0.25-0.375 s, with the text '+text_value('第二章 café')+'.',
             'A label track shows one region label spanning about 0.25-0.375 s with the text 第二章 café.',
             [{'op': 'label', 'text': '第二章 café'}], setup=[select(.25, .375)]),
        step('point-label', 'The framework placed the cursor at 0.75 s. Create a point label at exactly that cursor position with the text '
                            +text_value('Square wave')+'.',
             'A second label, a single point at about 0.75 s, shows Square wave; the first label is unchanged.',
             [{'op': 'label', 'text': 'Square wave'}], setup=[select(.75, .75)], depends=['region-label']),
        step('renamed', 'Change the text of the label "Square wave" to exactly '+text_value('Square section')+'.',
             'The point label at 0.75 s now reads Square section; the 第二章 café label is unchanged.',
             [{'op': 'label-edit', 'old': 'Square wave', 'text': 'Square section', 'at': .75}], depends=['point-label']),
        step('exported', f'Export the labels to a text file named {path(key, "labels.txt")}.',
             'The export completes without an error message and both labels are still shown.',
             [{'op': 'export', 'menu': ['File', 'Export', 'Export Labels...'], 'file': 'labels.txt'}],
             [{'kind': 'label-file', 'path': 'labels.txt', 'expect': [[.25, .375, '第二章 café'], [.75, .75, 'Square section']],
               'description': 'labels.txt is UTF-8 with the two labels (0.25-0.375 第二章 café, 0.75 Square section).'},
              audio('segments.wav', description='The labels left the audio unchanged.')], depends=['renamed'],
             requires={'visible': ['state-1']})], start='segments.wav imported as one track')

    # ------------------------------------------------------------ tracks
    key = 'tracks-add-rename-remove'
    add(key, 'tracks', [], [], [
        step('added', 'Add a new mono audio track, then a new stereo audio track, then a new label track.',
             'Three empty tracks are listed in this order: a mono audio track, a stereo audio track and a label track.',
             [{'op': 'menu', 'path': ['Tracks', 'Add New', 'Mono Track']}, {'op': 'menu', 'path': ['Tracks', 'Add New', 'Stereo Track']},
              {'op': 'menu', 'path': ['Tracks', 'Add New', 'Label Track']}],
             [tracks({'kind': 'wave', 'channels': 1}, {'kind': 'wave', 'channels': 2}, {'kind': 'label'}, fields=('kind', 'channels'))]),
        step('renamed', 'Rename the stereo audio track to '+text_value('Music bed')+'.',
             'The stereo track displays the name Music bed; the other tracks keep their names.',
             [{'op': 'track-name', 'track': 1, 'text': 'Music bed'}],
             [tracks({'kind': 'wave', 'channels': 1}, {'kind': 'wave', 'channels': 2, 'name': 'Music bed'}, {'kind': 'label'},
                     fields=('kind', 'channels', 'name'))], depends=['added']),
        step('removed', 'Remove the mono audio track from the project.',
             'Only the stereo track Music bed and the label track remain.',
             [{'op': 'track-close', 'track': 0}],
             [tracks({'kind': 'wave', 'channels': 2, 'name': 'Music bed'}, {'kind': 'label'}, fields=('kind', 'channels', 'name'))],
             depends=['renamed'])])

    key = 'tracks-mute-solo-gain'
    add(key, 'mixing', ['tone-440.wav', 'tone-880.wav'], imported('tone-440.wav', 'tone-880.wav'), [
        step('muted', 'Mute the tone-880 track (with the Mute button in its track header, or Shift+U while that track has '
                      'keyboard focus).',
             'The tone-880 track is muted: its Mute control is shown switched on; tone-440 is not muted (its Mute '
             'control is off). A muted track may also be drawn dimmed, but colour is not required.',
             [{'op': 'track-button', 'track': 1, 'button': 'Mute'}],
             [tracks({'mute': 0}, {'mute': 1}, fields=('mute',)),
              audio('tone-440.wav', description='The exported mix contains only the audible tone-440 track.')]),
        step('soloed', 'Unmute the tone-880 track, then solo it (the Mute and Solo buttons in its track header, or Shift+U '
                       'and Shift+S while that track has keyboard focus).',
             'The tone-880 track is soloed: its Solo control is shown switched on and its Mute control is off again; '
             'tone-440 is neither soloed nor muted by its own controls. Tracks that are not audible may also be drawn '
             'dimmed, but colour is not required.',
             [{'op': 'track-button', 'track': 1, 'button': 'Mute'}, {'op': 'track-button', 'track': 1, 'button': 'Solo'}],
             [tracks({'solo': 0}, {'solo': 1}, fields=('solo',)),
              audio('tone-880.wav', description='The exported mix contains only the soloed tone-880 track.')], depends=['muted']),
        step('unsoloed', 'Turn solo off for the tone-880 track so that both tracks are audible again.',
             'No track is soloed or muted: all Mute and Solo controls are shown switched off.',
             [{'op': 'track-button', 'track': 1, 'button': 'Solo'}],
             [tracks({'mute': 0, 'solo': 0}, {'mute': 0, 'solo': 0}, fields=('mute', 'solo')),
              audio('tone-440.wav', [('mix', 'tone-880.wav')], tolerance=GAIN,
                    description='The exported mix contains both tones again.')], depends=['soloed']),
        step('gain', 'Set the gain of the tone-440 track to exactly -6 dB.',
             'The tone-440 track\'s gain control shows -6 dB (for example a gain slider set left of its 0 dB centre, or a '
             'displayed value of -6.0 dB); no track is muted or soloed.',
             [{'op': 'track-gain', 'track': 0, 'value': '-6'}],
             [tracks({'solo': 0, 'gain': .501}, {'solo': 0, 'gain': 1.0}, fields=('solo', 'gain'), within=.002),
              audio('tone-440.wav', [('gain', -6), ('mix', 'tone-880.wav')], tolerance=GAIN,
                    description='The exported mix is tone-440 at -6 dB plus tone-880.')], depends=['unsoloed'])], start='tone-440.wav and tone-880.wav imported as two tracks')

    key = 'tracks-mix-and-render'
    add(key, 'mixing', ['tone-440.wav', 'tone-880.wav'], imported('tone-440.wav', 'tone-880.wav')+[select(0, 1, 0, 2)], [
        step('rendered', 'Both tracks are selected. Mix and render them into a single track.',
             'Only one track remains; its waveform is the combination of both tones (a beating pattern), about 1.0 s long.',
             [{'op': 'menu', 'path': ['Tracks', 'Mix', 'Mix and Render']}],
             [tracks(wave(1)), audio('tone-440.wav', [('mix', 'tone-880.wav')], tolerance=GAIN)])], start='tone-440.wav and tone-880.wav imported as two tracks, both selected')

    key = 'tracks-stereo-to-mono'
    add(key, 'mixing', ['stereo-pair.wav'], imported('stereo-pair.wav')+[select(0, 1)], [
        step('downmixed', 'Mix the selected stereo track down to a single mono track.',
             'The track is now mono (a single waveform) combining both tones, about 1.0 s long.',
             [{'op': 'menu', 'path': ['Tracks', 'Mix', 'Mix Stereo Down to Mono']}],
             [tracks(wave(1)), audio('stereo-pair.wav', [('downmix',)], tolerance=GAIN)])], start='stereo-pair.wav imported as one stereo track, selected')

    # ------------------------------------------------------------ persistence
    key = 'project-save-reopen'
    add(key, 'persistence', ['segments.wav'], imported('segments.wav'), [
        step('labelled', 'The framework selected 0.25-0.375 s. Create a region label from this selection, so that it covers exactly '
                         '0.25-0.375 s, with the text '+text_value('Gap')+'.',
             'A label track shows the region label Gap at about 0.25-0.375 s.',
             [{'op': 'label', 'text': 'Gap'}], [{'kind': 'labels', 'expect': [[.25, .375, 'Gap']]}], setup=[select(.25, .375)]),
        step('saved', f'Save the project as {path(key, "session.aup")}.',
             'The project is saved under the name session (for example shown in the window title) without an error message.',
             [{'op': 'save-project', 'file': 'session.aup'}],
             [{'kind': 'file-exists', 'path': 'session.aup', 'description': 'The project file session.aup was written.'}],
             depends=['labelled']),
        step('reopened', f'The application was restarted and shows an empty project. Open the saved project {path(key, "session.aup")}.',
             'The saved project is back: the segments audio track and the label Gap at about 0.25-0.375 s are shown.',
             [{'op': 'open', 'file': 'session.aup', 'dismiss': ['Orphan']}],
             [{'kind': 'labels', 'expect': [[.25, .375, 'Gap']]}, audio('segments.wav')],
             lifecycle='restart', depends=['saved'])], start='segments.wav imported as one track')

    key = 'preferences-track-name'
    add(key, 'preferences', [], [], [
        step('changed', 'In the application preferences, set the default audio track name (the name that a newly added empty '
                        'audio track receives; not a naming option for recordings) to '+text_value('Take one')+' and confirm with OK. '
                        'The setting is on the page of the "Tracks" category itself (select "Tracks" in the category list, '
                        'not its "Tracks Behaviors" or "Spectrograms" sub-pages).',
             'The preferences dialog is closed after confirming the change.',
             [{'op': 'preference', 'page': 'Tracks', 'label': 'Default audio track name', 'value': 'Take one'}],
             [{'kind': 'preference', 'name': '/GUI/TrackNames/DefaultTrackName', 'value': 'Take one'}],
             requires={'visible': ['state-1']}),
        step('cancelled', 'Open the preferences again, change the same default audio track name to '+text_value('Discarded')+', then cancel the dialog.',
             'The preferences dialog is closed after cancelling and the main window is shown again.',
             [{'op': 'preference', 'page': 'Tracks', 'label': 'Default audio track name', 'value': 'Discarded', 'button': 'Cancel'}],
             [{'kind': 'preference', 'name': '/GUI/TrackNames/DefaultTrackName', 'value': 'Take one'}], depends=['changed'],
             requires={'visible': ['state-1'], 'state-1': ['changed/state-1']}),
        step('new-track', 'The application was restarted. Add a new mono audio track.',
             'The new mono track is named Take one.',
             [{'op': 'menu', 'path': ['Tracks', 'Add New', 'Mono Track']}],
             [tracks({'kind': 'wave', 'channels': 1, 'name': 'Take one'}, fields=('kind', 'channels', 'name'))],
             lifecycle='restart', depends=['cancelled'])])
    return episodes
