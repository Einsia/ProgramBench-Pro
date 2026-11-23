"""The product's OSC interface: commands, their effect on the song and settings, and the feedback they send.

Each scenario starts from a fresh instance (runtime reset), and where it needs one, a verifier song opened through
OSC and checked before the first scored row. A scored row sends its OSC messages and observes the result the way a
user of the interface can: the song saved with /Hydrogen/SAVE_SONG_AS (reduced to the parts the command changes),
the settings file after /Hydrogen/SAVE_PREFERENCES, files the command wrote, and the feedback messages the
application sent back. Rows that only show that a message was ignored count together with a row of the same
episode that shows the command working.
"""
from __future__ import annotations

import time

import songs as S
from harness import MissingDependency
from render_cases import instrument, notes, upload_samples

FAMILY = 'osc-commands'


def part(projection, *path):
    value = projection
    for key in path:
        value = value[key]
    return value


def instruments(projection, key, count=None):
    rows = [i[key] for i in projection['instruments']]
    return rows if count is None else rows[:count]


def feedback_set(messages, prefix=''):
    """Feedback as a sorted set of (address, arguments): repetitions and order are not part of the behavior."""
    seen = {(m['address'], tuple(m['args'])) for m in messages if m['address'].startswith(prefix)}
    return sorted([address, list(args)] for address, args in seen)


def fresh(ctx):
    """A fresh instance whose OSC client registration (and the state feedback it triggers) happened in setup."""
    ctx.fresh()
    ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)


def kit_song(ctx):
    kit = (('Kick', 'kick.wav'), ('Snare', 'snare.wav'), ('Hat', 'hat.wav'), ('Tone', 'tone440.wav'))
    instruments_ = [S.Instrument(i, name, [S.Component([S.Layer(ctx.inputs(sample))])], volume=0.8 - 0.1 * i,
                                 pan=(-0.5, 0.0, 0.5, 0.25)[i]) for i, (name, sample) in enumerate(kit)]
    groove = [S.Note(0, 0), S.Note(48, 1), S.Note(96, 0), S.Note(144, 1)] + \
        [S.Note(p, 2, velocity=0.5) for p in range(0, 192, 24)] + [S.Note(72, 3, key='G0')]
    fill = [S.Note(p, 1, velocity=0.9) for p in range(96, 192, 12)]
    return S.Song(instruments_, [S.Pattern('Groove', groove), S.Pattern('Fill', fill), S.Pattern('Empty', [])],
                  sequence=[['Groove'], ['Groove', 'Fill']], name='Kit song', mode='song', bpm=110.0, volume=0.6)


def opened(builder, filename):
    """Setup: a fresh instance with the verifier samples and a song opened through OSC, checked by saving it."""
    def prepare(ctx):
        ctx.fresh()
        upload_samples(ctx)
        song = builder(ctx)
        ctx.upload(filename, song.xml())
        ctx.osc('/Hydrogen/SELECT_INSTRUMENT', 0.0, wait=1.0)
        ctx.open_song(filename)
        state = ctx.song()
        if state['song']['name'] != song.name:
            raise MissingDependency('the song did not open through OSC')
    return prepare


class Step:
    """One scored row: OSC messages, then the observed parts of the saved song (and feedback when asked)."""

    def __init__(self, messages, observe, *, feedback=None, settle=0.0, indices=None):
        self.messages, self.observe, self.feedback, self.settle = messages, observe, feedback, settle
        self.indices = indices

    def __call__(self, ctx):
        before = self.observe(ctx.song()) if self.indices is not None else None
        replies = []
        for message in self.messages:
            address, *args = message
            replies += ctx.osc(address, *args)
        if self.settle:
            time.sleep(self.settle)
        state = self.observe(ctx.song())
        if self.indices is not None:
            assert isinstance(state, list) and len(state) == len(before), 'the instrument count changed'
            result = {'state': [state[i] for i in self.indices],
                      'others_unchanged': all(state[i] == before[i] for i in range(len(state))
                                              if i not in self.indices)}
            assert result['others_unchanged'], 'an unrelated instrument changed'
        else:
            result = {'state': state}
        if self.feedback is not None:
            result['feedback'] = feedback_set(replies, self.feedback)
        return result


def add(suite, scenario, step, action, description, needs=None, requires=()):
    return suite.add(FAMILY, scenario, step, action, description=description, needs=needs, requires=requires)


def after(*steps):
    return tuple(steps)


def tempo(suite):
    suite.setup(FAMILY, 'tempo', fresh, 'Fresh instance with the default song')
    bpm = lambda p: part(p, 'song', 'bpm')
    first = None
    for value in (133.7, 9.0, 10.5, 401.0, -5.0, 400.0):
        case = add(suite, 'tempo', f'bpm-{value:g}', Step([('/Hydrogen/BPM', value)], bpm),
                   f'Send /Hydrogen/BPM {value:g} and read the song tempo')
        first = first or case
    add(suite, 'tempo', 'bpm-increase', Step([('/Hydrogen/BPM', 100.0), ('/Hydrogen/BPM_INCR', 3.0)], bpm),
        'Set 100 BPM, then send /Hydrogen/BPM_INCR 3')
    add(suite, 'tempo', 'bpm-decrease-fraction', Step([('/Hydrogen/BPM', 100.0), ('/Hydrogen/BPM_DECR', 7.6)], bpm),
        'Set 100 BPM, then send /Hydrogen/BPM_DECR 7.6')
    add(suite, 'tempo', 'bpm-decrease-below-minimum', Step([('/Hydrogen/BPM', 20.0), ('/Hydrogen/BPM_DECR', 50.0)],
                                                           bpm),
        'Set 20 BPM, then send /Hydrogen/BPM_DECR 50')
    add(suite, 'tempo', 'bpm-increase-above-maximum', Step([('/Hydrogen/BPM', 390.0), ('/Hydrogen/BPM_INCR', 25.0)],
                                                           bpm),
        'Set 390 BPM, then send /Hydrogen/BPM_INCR 25')
    add(suite, 'tempo', 'bpm-increase-zero', Step([('/Hydrogen/BPM', 150.0), ('/Hydrogen/BPM_INCR', 0.0)], bpm),
        'Set 150 BPM, then send /Hydrogen/BPM_INCR 0', requires=(first,))


def unregistered(ctx):
    """A fresh instance that has received no OSC message yet, with the kit song uploaded."""
    ctx.fresh()
    upload_samples(ctx)
    ctx.upload('feedback.h2song', kit_song(ctx).xml())


def registration(ctx):
    """The first message of a new sender: the application answers with its mixer state."""
    return feedback_set(ctx.osc('/Hydrogen/OPEN_SONG', 'feedback.h2song', wait=2.0))


def master(suite):
    suite.setup(FAMILY, 'registration', unregistered, 'Fresh instance that has received no OSC message yet')
    suite.add(FAMILY, 'registration', 'state-feedback', registration,
              description='Send the first OSC message (opening the kit song) and read the state feedback it triggers')
    suite.setup(FAMILY, 'master', fresh, 'Fresh instance with the default song')
    volume = lambda p: part(p, 'song', 'volume')
    for value in (0.0, 0.33, 1.5, 2.0, -1.0):
        add(suite, 'master', f'absolute-{value:g}', Step([('/Hydrogen/MASTER_VOLUME_ABSOLUTE', value)], volume,
                                                         feedback='/Hydrogen/MASTER'),
            f'Send /Hydrogen/MASTER_VOLUME_ABSOLUTE {value:g}; read the master volume and the feedback')
    for value in (1.0, 10.0, -20.0, 0.0):
        add(suite, 'master', f'relative-{value:g}', Step([('/Hydrogen/MASTER_VOLUME_ABSOLUTE', 0.5),
                                                          ('/Hydrogen/MASTER_VOLUME_RELATIVE', value)], volume),
            f'Set the master volume to 0.5, then send /Hydrogen/MASTER_VOLUME_RELATIVE {value:g}')


def strips(suite):
    suite.setup(FAMILY, 'strips', fresh, 'Fresh instance with the default song (18 instruments)')
    volumes = lambda p: instruments(p, 'volume')
    pans = lambda p: instruments(p, 'pan')
    positive = None
    for strip, value in ((1, 0.25), (2, 1.5), (3, 2.0), (18, 0.1)):
        case = add(suite, 'strips', f'volume-{strip}-{value:g}',
                   Step([(f'/Hydrogen/STRIP_VOLUME_ABSOLUTE/{strip}', value)], volumes, feedback='/Hydrogen/STRIP', indices=(strip - 1,)),
                   f'Send /Hydrogen/STRIP_VOLUME_ABSOLUTE/{strip} {value:g}; read the instrument volumes and feedback')
        positive = positive or case
    add(suite, 'strips', 'volume-beyond-last', Step([('/Hydrogen/STRIP_VOLUME_ABSOLUTE/19', 0.7)], volumes,
                                                    feedback='/Hydrogen/STRIP', indices=()),
        'Send /Hydrogen/STRIP_VOLUME_ABSOLUTE/19 0.7 to a song with 18 instruments', requires=(positive,))
    for value in (5.0, -20.0, 0.0):
        add(suite, 'strips', f'volume-relative-{value:g}', Step([('/Hydrogen/STRIP_VOLUME_ABSOLUTE/9', 0.5),
                                                                 ('/Hydrogen/STRIP_VOLUME_RELATIVE/9', value)],
                                                                lambda p: instruments(p, 'volume')[8]),
            f'Set strip 9 to 0.5, then send /Hydrogen/STRIP_VOLUME_RELATIVE/9 {value:g}')
    for strip, value in ((1, 0.0), (2, 0.25), (3, 1.0), (4, 0.5), (5, 0.9)):
        add(suite, 'strips', f'pan-{strip}-{value:g}', Step([(f'/Hydrogen/PAN_ABSOLUTE/{strip}', value)], pans,
                                                            feedback='/Hydrogen/PAN', indices=(strip - 1,)),
            f'Send /Hydrogen/PAN_ABSOLUTE/{strip} {value:g}; read the instrument pans and feedback')
    for strip, value in ((6, -1.0), (7, 0.4), (8, -0.25)):
        add(suite, 'strips', f'pan-symmetric-{strip}-{value:g}',
            Step([(f'/Hydrogen/PAN_ABSOLUTE_SYM/{strip}', value)], pans, feedback='/Hydrogen/PAN', indices=(strip - 1,)),
            f'Send /Hydrogen/PAN_ABSOLUTE_SYM/{strip} {value:g}; read the instrument pans and feedback')
    for value in (1.0, -3.0):
        add(suite, 'strips', f'pan-relative-{value:g}', Step([('/Hydrogen/PAN_ABSOLUTE/10', 0.5),
                                                              ('/Hydrogen/PAN_RELATIVE/10', value)],
                                                             lambda p: instruments(p, 'pan')[9]),
            f'Centre strip 10, then send /Hydrogen/PAN_RELATIVE/10 {value:g}')
    for value in (0.0, 64.0, 127.0, 300.0):
        add(suite, 'strips', f'cutoff-{value:g}', Step([('/Hydrogen/FILTER_CUTOFF_LEVEL_ABSOLUTE/11', value)],
                                                       lambda p: instruments(p, 'filter')[10]),
            f'Send /Hydrogen/FILTER_CUTOFF_LEVEL_ABSOLUTE/11 {value:g}; read the filter of instrument 11')


def toggles(suite):
    suite.setup(FAMILY, 'toggles', fresh, 'Fresh instance with the default song')
    muted = lambda p: instruments(p, 'muted', 6)
    soloed = lambda p: instruments(p, 'soloed', 6)
    first = add(suite, 'toggles', 'mute-strip', Step([('/Hydrogen/STRIP_MUTE_TOGGLE/3',)], muted,
                                                     feedback='/Hydrogen/STRIP_MUTE', indices=(2,)),
                'Send /Hydrogen/STRIP_MUTE_TOGGLE/3; read which instruments are muted and the feedback')
    second = add(suite, 'toggles', 'mute-strip-again', Step([('/Hydrogen/STRIP_MUTE_TOGGLE/3',)], muted,
                                                            feedback='/Hydrogen/STRIP_MUTE', indices=(2,)),
                 'Send /Hydrogen/STRIP_MUTE_TOGGLE/3 a second time', needs=after(first))
    add(suite, 'toggles', 'mute-strip-argument', Step([('/Hydrogen/STRIP_MUTE_TOGGLE/5', 0.0)], muted, indices=(4,)),
        'Send /Hydrogen/STRIP_MUTE_TOGGLE/5 with the argument 0', needs=after(second))
    solo = add(suite, 'toggles', 'solo-strip', Step([('/Hydrogen/STRIP_SOLO_TOGGLE/2',)], soloed,
                                                    feedback='/Hydrogen/STRIP_SOLO', indices=(1,)),
               'Send /Hydrogen/STRIP_SOLO_TOGGLE/2; read which instruments are soloed and the feedback')
    add(suite, 'toggles', 'solo-second-strip', Step([('/Hydrogen/STRIP_SOLO_TOGGLE/4',)], soloed, indices=(3,)),
        'Solo strip 4 as well', needs=after(solo))
    master = lambda p: part(p, 'song', 'muted')
    mute = add(suite, 'toggles', 'master-mute', Step([('/Hydrogen/MUTE',)], master, feedback='/Hydrogen/MUTE'),
               'Send /Hydrogen/MUTE; read whether the song output is muted and the feedback')
    unmute = add(suite, 'toggles', 'master-unmute', Step([('/Hydrogen/UNMUTE',)], master),
                 'Send /Hydrogen/UNMUTE', needs=after(mute))
    add(suite, 'toggles', 'master-mute-toggle', Step([('/Hydrogen/MUTE_TOGGLE',), ('/Hydrogen/MUTE_TOGGLE',),
                                                      ('/Hydrogen/MUTE_TOGGLE',)], master),
        'Send /Hydrogen/MUTE_TOGGLE three times', needs=after(unmute))

    def metronome(ctx):
        replies = ctx.osc('/Hydrogen/TOGGLE_METRONOME')
        ctx.osc('/Hydrogen/SAVE_PREFERENCES', wait=0.8)
        time.sleep(0.5)
        text = ctx.settings()
        value = text.split('<use_metronome>')[1].split('</use_metronome>')[0] if '<use_metronome>' in text else None
        return {'use_metronome': value, 'feedback': feedback_set(replies, '/Hydrogen/TOGGLE')}
    add(suite, 'toggles', 'metronome', metronome,
        'Send /Hydrogen/TOGGLE_METRONOME and /Hydrogen/SAVE_PREFERENCES; read the metronome setting and feedback')


def pitch(suite):
    suite.setup(FAMILY, 'pitch', fresh, 'Fresh instance with the default song')
    offsets = lambda p: instruments(p, 'pitch_offset')
    positive = None
    for index, value in ((2, 5.5), (0, -30.0), (17, 30.0), (4, -0.75)):
        case = add(suite, 'pitch', f'instrument-{index}-{value:g}', Step([('/Hydrogen/INSTRUMENT_PITCH', index, value)],
                                                                         offsets, indices=(index,)),
                   f'Send /Hydrogen/INSTRUMENT_PITCH {index} {value:g}; read the instrument pitch offsets')
        positive = positive or case
    add(suite, 'pitch', 'instrument-out-of-range', Step([('/Hydrogen/INSTRUMENT_PITCH', 18, 3.0)], offsets, indices=()),
        'Send /Hydrogen/INSTRUMENT_PITCH to instrument 18 of a song with 18 instruments (numbered from 0)',
        requires=(positive,))


def modes(suite):
    suite.setup(FAMILY, 'modes', fresh, 'Fresh instance with the default song')
    fields = lambda p: {k: p['song'][k] for k in ('mode', 'timeline')}
    loop = lambda p: p['song']['loop']
    song_on = add(suite, 'modes', 'song-mode', Step([('/Hydrogen/SONG_MODE_ACTIVATION', 1.0)], fields),
                  'Send /Hydrogen/SONG_MODE_ACTIVATION 1')
    loop_on = add(suite, 'modes', 'loop-mode', Step([('/Hydrogen/LOOP_MODE_ACTIVATION', 1.0)], loop),
                  'Send /Hydrogen/LOOP_MODE_ACTIVATION 1')
    timeline = add(suite, 'modes', 'timeline-on', Step([('/Hydrogen/TIMELINE_ACTIVATION', 1.0)], fields),
                   'Send /Hydrogen/TIMELINE_ACTIVATION 1 in song mode', needs=after(song_on))
    pattern_mode = add(suite, 'modes', 'pattern-mode', Step([('/Hydrogen/SONG_MODE_ACTIVATION', 0.0)], fields),
        'Send /Hydrogen/SONG_MODE_ACTIVATION 0 while the timeline is active', needs=after(timeline))
    add(suite, 'modes', 'loop-off', Step([('/Hydrogen/LOOP_MODE_ACTIVATION', 0.0)], loop),
        'Send /Hydrogen/LOOP_MODE_ACTIVATION 0', needs=after(loop_on))
    add(suite, 'modes', 'timeline-in-pattern-mode', Step([('/Hydrogen/TIMELINE_ACTIVATION', 0.0),
                                                          ('/Hydrogen/TIMELINE_ACTIVATION', 1.0)], fields),
        'Switch the timeline off and on again while in pattern mode', needs=after(pattern_mode), requires=(timeline,))


def markers(suite):
    suite.setup(FAMILY, 'markers', fresh, 'Fresh instance with the default song')
    view = lambda p: {'markers': p['markers'], 'bpm': p['song']['bpm']}
    start = add(suite, 'markers', 'add', Step([('/Hydrogen/SONG_MODE_ACTIVATION', 1.0),
                                               ('/Hydrogen/TIMELINE_ACTIVATION', 1.0),
                                               ('/Hydrogen/TIMELINE_ADD_MARKER', 2.0, 90.0),
                                               ('/Hydrogen/TIMELINE_ADD_MARKER', 0.0, 140.0)], view),
                'In song mode with the timeline active, add tempo markers 90 BPM at column 2 and 140 BPM at column 0')
    replace = add(suite, 'markers', 'replace', Step([('/Hydrogen/TIMELINE_ADD_MARKER', 2.0, 95.5)], view),
                  'Add a 95.5 BPM marker at column 2, where a marker already is', needs=after(start))
    fractional = add(suite, 'markers', 'fractional-column', Step([('/Hydrogen/TIMELINE_ADD_MARKER', 4.6, 70.0)], view),
        'Add a marker at column 4.6', needs=after(replace))
    outside = add(suite, 'markers', 'out-of-range-tempo', Step([('/Hydrogen/TIMELINE_ADD_MARKER', 7.0, 900.0)], view),
        'Add a marker of 900 BPM at column 7', needs=after(fractional))
    delete = add(suite, 'markers', 'delete', Step([('/Hydrogen/TIMELINE_DELETE_MARKER', 2.0)], view),
                 'Delete the marker at column 2', needs=after(outside))
    missing = add(suite, 'markers', 'delete-missing', Step([('/Hydrogen/TIMELINE_DELETE_MARKER', 11.0)], view),
        'Delete a marker at column 11, where there is none', needs=after(delete), requires=(delete,))
    add(suite, 'markers', 'bpm-with-timeline', Step([('/Hydrogen/BPM', 150.0)], view),
        'Send /Hydrogen/BPM 150 while the timeline is active', needs=after(missing), requires=(start,))


def patterns(suite):
    suite.setup(FAMILY, 'patterns', fresh, 'Fresh instance with the default song (ten empty patterns)')
    names = lambda p: [x['name'] for x in p['patterns']]
    layout = lambda p: {'patterns': [x['name'] for x in p['patterns']], 'sequence': p['sequence']}
    new = add(suite, 'patterns', 'new', Step([('/Hydrogen/NEW_PATTERN', 'Verse')], names),
              'Send /Hydrogen/NEW_PATTERN Verse')
    duplicate = add(suite, 'patterns', 'new-duplicate', Step([('/Hydrogen/NEW_PATTERN', 'Verse'), ('/Hydrogen/NEW_PATTERN', 'Verse')],
                                                 names), 'Create two more patterns named Verse', needs=after(new))
    unicode_name = add(suite, 'patterns', 'new-unicode', Step([('/Hydrogen/NEW_PATTERN', 'Strophe – Ü 2')], names),
        'Create a pattern named "Strophe – Ü 2"', needs=after(duplicate))
    toggle = add(suite, 'patterns', 'toggle-cells', Step([('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 0.0, 0.0),
                                                          ('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 3.0, 2.0),
                                                          ('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 1.0, 4.0),
                                                          ('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 1.0, 2.0)], layout),
                 'Toggle song editor cells (column, row) (0,0), (3,2), (1,4) and (1,2)', needs=after(unicode_name))
    outside = add(suite, 'patterns', 'toggle-outside', Step([('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 2.0, 40.0)], layout),
        'Toggle the cell at column 2, row 40, below the last pattern', needs=after(toggle), requires=(toggle,))
    remove = add(suite, 'patterns', 'remove-first', Step([('/Hydrogen/REMOVE_PATTERN', 0.0)], layout),
                 'Remove pattern number 0', needs=after(outside))
    removed_used = add(suite, 'patterns', 'remove-used', Step([('/Hydrogen/REMOVE_PATTERN', 1.0)], layout),
        'Remove the pattern now at number 1, which is used in two columns', needs=after(remove))
    add(suite, 'patterns', 'remove-outside', Step([('/Hydrogen/REMOVE_PATTERN', 99.0)], layout),
        'Remove pattern number 99, which does not exist', needs=after(removed_used), requires=(remove,))


def note_editing(suite):
    """Each row opens the kit song in its own scenario: clearing works on the selected pattern and instrument."""
    view = lambda p: [{'name': x['name'], 'notes': [[n['position'], n['instrument']] for n in x['notes']]}
                      for x in p['patterns']]
    rows = (
        ('clear-selected-instrument', [('/Hydrogen/SELECT_INSTRUMENT', 2.0), ('/Hydrogen/CLEAR_SELECTED_INSTRUMENT',)],
         'Select instrument 2, then send /Hydrogen/CLEAR_SELECTED_INSTRUMENT'),
        ('clear-instrument', [('/Hydrogen/CLEAR_INSTRUMENT', 0.0)], 'Send /Hydrogen/CLEAR_INSTRUMENT 0'),
        ('clear-instrument-unused', [('/Hydrogen/CLEAR_INSTRUMENT', 3.0)],
         'Send /Hydrogen/CLEAR_INSTRUMENT 3 (the tone instrument, used once)'),
        ('clear-pattern', [('/Hydrogen/CLEAR_PATTERN',)], 'Send /Hydrogen/CLEAR_PATTERN'),
        ('select-instrument-out-of-range', [('/Hydrogen/SELECT_INSTRUMENT', 9.0), ('/Hydrogen/CLEAR_SELECTED_INSTRUMENT',)],
         'Select instrument 9 of a song with four, then send /Hydrogen/CLEAR_SELECTED_INSTRUMENT'),
    )
    for step, messages, description in rows:
        scenario = 'notes-' + step
        suite.setup(FAMILY, scenario, opened(kit_song, 'kit-song.h2song'),
                    'Fresh instance with the verifier kit song opened through OSC')
        add(suite, scenario, 'result', Step(messages, view), description + ' on the opened kit song')


def build(suite):
    tempo(suite)
    master(suite)
    strips(suite)
    toggles(suite)
    pitch(suite)
    modes(suite)
    markers(suite)
    patterns(suite)
    note_editing(suite)
