"""More OSC rows: the value-taking commands over further strips and values, song files and kit loading.

Rows follow osc_cases: messages through the runtime's osc operation, then the parts of the song saved with
/Hydrogen/SAVE_SONG_AS that the command changes (and the feedback where the product sends one). Independent setting rows compare their target fields and non-target invariance against their own before state.
Operations that build on an earlier result declare that checkpoint as a dependency.
"""
from __future__ import annotations

import songs as S
from osc_cases import Step, after, fresh, instruments, kit_song, opened, part

FAMILY = 'osc-matrix'


def add(suite, scenario, step, action, description, needs=None, requires=()):
    return suite.add(FAMILY, scenario, step, action, description=description, needs=needs, requires=requires)


def values(suite):
    suite.setup(FAMILY, 'values', fresh, 'Fresh instance with the default song (18 instruments)')
    bpm = lambda p: part(p, 'song', 'bpm')
    for value in (30.0, 60.5, 99.99, 180.0, 222.2, 333.0):
        add(suite, 'values', f'bpm-{value:g}', Step([('/Hydrogen/BPM', value)], bpm),
            f'Send /Hydrogen/BPM {value:g} and read the song tempo')
    volume = lambda p: part(p, 'song', 'volume')
    for value in (0.1, 0.75, 1.25):
        add(suite, 'values', f'master-{value:g}', Step([('/Hydrogen/MASTER_VOLUME_ABSOLUTE', value)], volume),
            f'Send /Hydrogen/MASTER_VOLUME_ABSOLUTE {value:g} and read the master volume')
    volumes = lambda p: instruments(p, 'volume')
    for strip, value in ((4, 0.05), (5, 0.6), (6, 1.1), (7, 1.45), (8, 0.0)):
        add(suite, 'values', f'strip-volume-{strip}-{value:g}',
            Step([(f'/Hydrogen/STRIP_VOLUME_ABSOLUTE/{strip}', value)], volumes, indices=(strip - 1,)),
            f'Send /Hydrogen/STRIP_VOLUME_ABSOLUTE/{strip} {value:g}; read the instrument volumes')
    for value in (1.0, -1.0):
        add(suite, 'values', f'strip-volume-relative-{value:g}',
            Step([('/Hydrogen/STRIP_VOLUME_ABSOLUTE/2', 0.9), ('/Hydrogen/STRIP_VOLUME_RELATIVE/2', value)],
                 lambda p: instruments(p, 'volume')[1]),
            f'Set strip 2 to 0.9, then send /Hydrogen/STRIP_VOLUME_RELATIVE/2 {value:g}')
    pans = lambda p: instruments(p, 'pan')
    for strip, value in ((11, 0.1), (12, 0.35), (13, 0.6), (14, 0.8), (15, 1.0)):
        add(suite, 'values', f'strip-pan-{strip}-{value:g}', Step([(f'/Hydrogen/PAN_ABSOLUTE/{strip}', value)], pans, indices=(strip - 1,)),
            f'Send /Hydrogen/PAN_ABSOLUTE/{strip} {value:g}; read the instrument pans')
    for strip, value in ((16, 0.9), (17, -0.6)):
        add(suite, 'values', f'strip-pan-symmetric-{strip}-{value:g}',
            Step([(f'/Hydrogen/PAN_ABSOLUTE_SYM/{strip}', value)], pans, indices=(strip - 1,)),
            f'Send /Hydrogen/PAN_ABSOLUTE_SYM/{strip} {value:g}; read the instrument pans')
    for strip, value in ((12, 32.0), (13, 100.0)):
        add(suite, 'values', f'cutoff-{strip}-{value:g}',
            Step([(f'/Hydrogen/FILTER_CUTOFF_LEVEL_ABSOLUTE/{strip}', value)],
                 lambda p, s=strip: instruments(p, 'filter')[s - 1]),
            f'Send /Hydrogen/FILTER_CUTOFF_LEVEL_ABSOLUTE/{strip} {value:g}; read that instrument filter')
    offsets = lambda p: instruments(p, 'pitch_offset')
    for index, value in ((1, 12.0), (3, -24.0), (6, 0.5), (8, -7.0)):
        add(suite, 'values', f'instrument-pitch-{index}-{value:g}',
            Step([('/Hydrogen/INSTRUMENT_PITCH', float(index), value)], offsets, indices=(index,)),
            f'Send /Hydrogen/INSTRUMENT_PITCH {index} {value:g}; read the instrument pitch offsets')
    muted = lambda p: instruments(p, 'muted')
    soloed = lambda p: instruments(p, 'soloed')
    first = add(suite, 'values', 'mute-strips', Step([('/Hydrogen/STRIP_MUTE_TOGGLE/7',),
                                                      ('/Hydrogen/STRIP_MUTE_TOGGLE/12',)], muted, indices=(6, 11)),
                'Toggle mute on strips 7 and 12; read which instruments are muted')
    add(suite, 'values', 'mute-strip-off', Step([('/Hydrogen/STRIP_MUTE_TOGGLE/7',)], muted, indices=(6,)),
        'Toggle mute on strip 7 again', needs=after(first))
    add(suite, 'values', 'solo-last-strip', Step([('/Hydrogen/STRIP_SOLO_TOGGLE/18',)], soloed, indices=(17,)),
        'Toggle solo on strip 18; read which instruments are soloed')


def selection(suite):
    rows = (
        ('clear-instrument-1', [('/Hydrogen/CLEAR_INSTRUMENT', 1.0)],
         'Send /Hydrogen/CLEAR_INSTRUMENT 1 (the snare, used in both patterns)'),
    )
    view = lambda p: [{'name': x['name'], 'notes': [[n['position'], n['instrument']] for n in x['notes']]}
                      for x in p['patterns']]
    for step, messages, description in rows:
        scenario = 'selection-' + step
        suite.setup(FAMILY, scenario, opened(kit_song, 'kit-song.h2song'),
                    'Fresh instance with the verifier kit song opened through OSC')
        add(suite, scenario, 'result', Step(messages, view), description + ' on the opened kit song')


def files(suite):
    scenario = 'files'
    suite.setup(FAMILY, scenario, opened(kit_song, 'kit-song.h2song'),
                'Fresh instance with the verifier kit song opened through OSC')

    def save_current(ctx):
        """Save the kit song as a project, change its tempo, save it in place and read the project file."""
        ctx.osc('/Hydrogen/SAVE_SONG_AS', 'current.h2song', wait=0.5)
        ctx.take('projects/current.h2song')
        ctx.osc('/Hydrogen/BPM', 87.0)
        ctx.osc('/Hydrogen/STRIP_VOLUME_ABSOLUTE/2', 0.45)
        ctx.osc('/Hydrogen/SAVE_SONG', wait=0.5)
        saved = S.song_projection(ctx.take('projects/current.h2song'), ctx.places())
        return {'bpm': saved['song']['bpm'], 'volumes': [i['volume'] for i in saved['instruments']]}
    stored = add(suite, scenario, 'save-in-place', save_current,
                 'Save the song as current.h2song, change tempo and a volume, send /Hydrogen/SAVE_SONG and read the file')

    def new_song(ctx):
        ctx.osc('/Hydrogen/NEW_SONG', 'blank.h2song', wait=1.0)
        ctx.osc('/Hydrogen/SAVE_SONG', wait=0.8)
        saved = S.song_projection(ctx.take('projects/blank.h2song'), ctx.places())
        return {'name': saved['song']['name'], 'bpm': saved['song']['bpm'],
                'instruments': [i['name'] for i in saved['instruments']],
                'patterns': [p['name'] for p in saved['patterns']], 'sequence': saved['sequence']}
    add(suite, scenario, 'new-song', new_song,
        'Send /Hydrogen/NEW_SONG blank.h2song, then /Hydrogen/SAVE_SONG; read the file written', needs=after(stored))


def kits(suite):
    view = lambda p: {'drumkit': p['song']['drumkit'], 'instruments': [i['name'] for i in p['instruments']],
                      'notes': sorted(n['instrument'] for x in p['patterns'] for n in x['notes'])}
    for flag in (0.0,):
        scenario = f'load-kit-{int(flag)}'
        suite.setup(FAMILY, scenario, opened(kit_song, 'kit-song.h2song'),
                    'Fresh instance with the verifier kit song opened through OSC')
        add(suite, scenario, 'result', Step([('/Hydrogen/LOAD_DRUMKIT', 'TR808EmulationKit', flag)], view,
                                            settle=1.5),
            f'Send /Hydrogen/LOAD_DRUMKIT TR808EmulationKit {flag:g} to the kit song (whose notes use four '
            'instruments); read the kit, the instruments and the instruments the notes use')


def kit_song_rows(suite):
    scenario = 'kit-song'
    suite.setup(FAMILY, scenario, opened(kit_song, 'kit-song.h2song'),
                'Fresh instance with the verifier kit song opened through OSC')
    layout = lambda p: {'patterns': [x['name'] for x in p['patterns']], 'sequence': p['sequence']}
    named = add(suite, scenario, 'new-pattern-unicode', Step([('/Hydrogen/NEW_PATTERN', '鼓 – Pattern ★')], layout),
                'Create a pattern named "鼓 – Pattern ★" in the kit song')
    long_name = add(suite, scenario, 'new-pattern-long', Step([('/Hydrogen/NEW_PATTERN', 'Bridge section with a rather long name '
                                                                              'of sixty-four characters ..')], layout),
        'Create a pattern with a 64-character name', needs=after(named))
    toggled = add(suite, scenario, 'toggle-cells', Step([('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 2.0, 1.0),
                                                         ('/Hydrogen/SONG_EDITOR_TOGGLE_GRID_CELL', 0.0, 0.0)], layout),
                  'Toggle the cells at column 2, row 1 and column 0, row 0 of the kit song', needs=after(long_name))
    add(suite, scenario, 'remove-fill', Step([('/Hydrogen/REMOVE_PATTERN', 1.0)], layout),
        'Remove pattern number 1 (Fill), which is used in columns 1 and 2', needs=after(toggled))
    marker_view = lambda p: {'markers': p['markers'], 'timeline': p['song']['timeline']}
    add(suite, scenario, 'marker', Step([('/Hydrogen/TIMELINE_ACTIVATION', 1.0),
                                         ('/Hydrogen/TIMELINE_ADD_MARKER', 1.0, 75.0)], marker_view),
        'Activate the timeline of the kit song (song mode) and add a 75 BPM marker at column 1')
    add(suite, scenario, 'strip-volume-feedback',
        Step([('/Hydrogen/STRIP_VOLUME_ABSOLUTE/3', 0.33)], lambda p: instruments(p, 'volume'),
             feedback='/Hydrogen/STRIP_VOLUME', indices=(2,)),
        'Set strip 3 of the kit song to 0.33; read the volumes and the feedback')
    add(suite, scenario, 'strip-pan-feedback',
        Step([('/Hydrogen/PAN_ABSOLUTE/4', 0.1)], lambda p: instruments(p, 'pan'), feedback='/Hydrogen/PAN', indices=(3,)),
        'Pan strip 4 of the kit song with /Hydrogen/PAN_ABSOLUTE/4 0.1; read the pans and the feedback')
    add(suite, scenario, 'strip-solo-feedback',
        Step([('/Hydrogen/STRIP_SOLO_TOGGLE/1',)], lambda p: instruments(p, 'soloed'), feedback='/Hydrogen/STRIP_SOLO', indices=(0,)),
        'Solo strip 1 of the kit song; read which instruments are soloed and the feedback')


def build(suite):
    values(suite)
    kit_song_rows(suite)
    selection(suite)
    files(suite)
    kits(suite)
