"""Song documents round trip, one field at a time: open a verifier song that differs from the defaults in one value,
save it again with /Hydrogen/SAVE_SONG_AS and read that value back from the saved song.

Each row isolates one element of the song format (song properties, instrument and layer settings, note and pattern
fields, the arrangement and timeline), so a reader or writer that loses or alters that element fails that row only.
"""
from __future__ import annotations

import songs as S
from render_cases import instrument, layer, notes
from songfile_cases import Load, base, prepare

FAMILY = 'songfile-roundtrip'


def add(suite, scenario, step, action, description):
    suite.add(FAMILY, scenario, step, action, description=description)


def song_fields(suite):
    suite.setup(FAMILY, 'song', prepare, 'Fresh instance with the verifier samples')
    rows = (
        ('bpm', 73.25), ('bpm', 250.0), ('bpm', 33.3), ('volume', 0.25), ('volume', 1.3), ('muted', True),
        ('metronome_volume', 0.9), ('metronome_volume', 0.05), ('name', 'Réunion du «Groupe»'),
        ('name', '鼓机 ドラム'), ('author', "O'Brien & Sons"), ('author', 'Анна'),
        ('notes', 'Tempo: 120\n\nEnd.'), ('notes', '<b>bold</b> & "quoted"'), ('license', 'GPL'),
        ('license', 'CC0'), ('license', 'All rights reserved'), ('license', 'Custom licence text'),
        ('loop', True), ('mode', 'pattern'), ('timeline', True), ('k_norm', 0.5), ('k_norm', 2.0),
        ('humanize_time', 0.3), ('humanize_velocity', 0.7), ('swing', 0.45), ('swing', 0.9), ('action_mode', 1))
    projection = {'humanize_time': 'humanize', 'humanize_velocity': 'humanize', 'swing': 'swing'}
    for index, (field, value) in enumerate(rows):
        key = projection.get(field, field)
        add(suite, 'song', f'{field}-{index:02d}', Load(lambda ctx, f=field, v=value: base(ctx, **{f: v}).xml(),
                                                        [('song', (key,))]),
            f'Open a song whose {field.replace("_", " ")} is {value!r} and save it again')
    for law in ('LINEAR_CONST_POWER', 'POLAR_CONST_SUM', 'QUADRATIC_STRAIGHT_POLYGONAL', 'RATIO_CONST_K_NORM',
                'LINEAR_CONST_K_NORM', 'QUADRATIC_CONST_POWER'):
        add(suite, 'song', 'pan-law-' + law.lower(), Load(lambda ctx, l=law: base(ctx, pan_law=l).xml(),
                                                          [('song', ('pan_law',))]),
            f'Open a song whose pan law is {law} and save it again')


def instrument_fields(suite):
    suite.setup(FAMILY, 'instrument', prepare, 'Fresh instance with the verifier samples')

    def one(options):
        def build(ctx):
            values = dict(options)
            name = values.pop('name', 'Solo')
            return base(ctx, instruments=[instrument(ctx, 'tone440.wav', 0, name=name, **values)],
                        patterns=[S.Pattern('P', notes(0))]).xml()
        return build
    rows = (
        ('name', {'name': 'Floor Tom (left)'}), ('name', {'name': 'Tambourin ☆'}),
        ('volume', {'volume': 0.35}), ('volume', {'volume': 1.4}), ('muted', {'muted': True}),
        ('soloed', {'soloed': True}), ('pan', {'pan': -0.65}), ('pan', {'pan': 0.4}), ('pan', {'pan': 1.0}),
        ('pitch_offset', {'pitch_offset': -11.5}), ('pitch_offset', {'pitch_offset': 23.0}),
        ('random_pitch', {'random_pitch': 0.35}), ('gain', {'gain': 0.2}), ('gain', {'gain': 4.0}),
        ('apply_velocity', {'apply_velocity': False}),
        ('filter', {'filter_active': True, 'filter_cutoff': 0.15, 'filter_resonance': 0.85}),
        ('filter', {'filter_active': False, 'filter_cutoff': 0.5, 'filter_resonance': 0.3}),
        ('adsr', {'attack': 12345, 'decay': 6789, 'sustain': 0.42, 'release': 33333}),
        ('adsr', {'attack': 0, 'decay': 0, 'sustain': 0.0, 'release': 256}),
        ('mute_group', {'mute_group': 0}), ('mute_group', {'mute_group': 7}),
        ('midi_out', {'midi_channel': 0, 'midi_note': 0}), ('midi_out', {'midi_channel': 15, 'midi_note': 127}),
        ('midi_out', {'midi_channel': 9, 'midi_note': 60}), ('stop_note', {'stop_note': True}),
        ('selection', {'selection': 'ROUND_ROBIN'}), ('selection', {'selection': 'RANDOM'}),
        ('hihat', {'hihat': 1, 'lower_cc': 30, 'higher_cc': 100}), ('hihat', {'hihat': 0, 'lower_cc': 0, 'higher_cc': 64}),
        ('fx', {'fx': (0.5, 0.0, 0.0, 1.0)}))
    for index, (field, options) in enumerate(rows):
        add(suite, 'instrument', f'{field}-{index:02d}', Load(one(options), [('instruments', (field,))]),
            f'Open a song whose instrument has {", ".join(f"{k} {v!r}" for k, v in options.items())} and save it '
            'again')


def layer_fields(suite):
    suite.setup(FAMILY, 'layer', prepare, 'Fresh instance with the verifier samples')

    def with_layers(*layer_options):
        def build(ctx):
            layers = [layer(ctx, options.pop('sample', 'tone440.wav'), **options)
                      for options in (dict(o) for o in layer_options)]
            return base(ctx, instruments=[instrument(ctx, '', layers=layers)],
                        patterns=[S.Pattern('P', notes(0))]).xml()
        return build
    rows = (
        ('range-low', ({'min': 0.2, 'max': 0.6},)), ('range-top', ({'min': 0.9, 'max': 1.0},)),
        ('gain-low', ({'gain': 0.33},)), ('gain-high', ({'gain': 3.0},)), ('pitch-down', ({'pitch': -3.5},)),
        ('pitch-up', ({'pitch': 12.0},)),
        ('three-layers', ({'sample': 'layer550.wav', 'min': 0.6}, {'sample': 'layer220.wav', 'max': 0.3},
                          {'sample': 'layer330.wav', 'min': 0.3, 'max': 0.6})),
        ('edit-reverse', ({'sample': 'ramp.wav', 'modified': True, 'smode': 'reverse', 'startframe': 10,
                          'loopframe': 10, 'endframe': 15000},)),
        ('edit-loops', ({'sample': 'ramp.wav', 'modified': True, 'smode': 'forward', 'startframe': 0,
                        'loopframe': 7000, 'loops': 5, 'endframe': 22050},)),
        ('edit-stretch', ({'sample': 'ramp.wav', 'modified': True, 'rubber': 1, 'rubberdivider': 0.5,
                          'rubbersettings': 1, 'rubberpitch': -2.0, 'endframe': 22050},)),
        ('volume-envelope', ({'sample': 'ramp.wav', 'modified': True, 'endframe': 22050,
                             'volume_envelope': ((0, 0), (100, 100), (500, 30), (841, 0))},)),
        ('pan-envelope', ({'sample': 'ramp.wav', 'modified': True, 'endframe': 22050,
                          'pan_envelope': ((0, 10), (841, 90))},)))
    for step, options in rows:
        add(suite, 'layer', step, Load(with_layers(*options), [('instruments', ('components',))]),
            f'Open a song whose instrument layers are {options!r} and save it again')

    def components(ctx):
        inst = instrument(ctx, '', components=[S.Component([layer(ctx, 'tone440.wav')], id=0, gain=0.7),
                                               S.Component([layer(ctx, 'tone660.wav', gain=1.3)], id=1, gain=1.9)])
        return base(ctx, instruments=[inst], patterns=[S.Pattern('P', notes(0))],
                    components=((0, 'Close', 0.8), (1, 'Ambient room', 1.25))).xml()
    add(suite, 'layer', 'components', Load(components, ['components', ('instruments', ('components',))]),
        'Open a song with two named drumkit components and an instrument using both, and save it again')


def note_fields(suite):
    suite.setup(FAMILY, 'note', prepare, 'Fresh instance with the verifier samples')
    rows = (('velocity', 0.15), ('velocity', 1.0), ('pan', -0.45), ('pan', 1.0), ('leadlag', 0.3), ('leadlag', -0.6),
            ('pitch', 0.35), ('pitch', -0.5), ('key', 'Fs1'), ('key', 'Bf-2'), ('key', 'C3'), ('length', 37),
            ('length', 192), ('note_off', True), ('probability', 0.4), ('probability', 0.0))
    for index, (field, value) in enumerate(rows):
        add(suite, 'note', f'{field}-{index:02d}', Load(lambda ctx, f=field, v=value: base(
            ctx, patterns=[S.Pattern('P', [S.Note(24, 0), S.Note(96, 1, **{f: v})])]).xml(),
            [('patterns', ('notes',))]),
            f'Open a song with a note whose {field.replace("_", " ")} is {value!r} and save it again')


def pattern_fields(suite):
    suite.setup(FAMILY, 'pattern', prepare, 'Fresh instance with the verifier samples')
    rows = (('name', 'Intro – Ä'), ('name', 'Verse/Chorus'), ('info', 'Two lines\nof description'),
            ('info', 'A & B <C>'), ('category', 'Fills'), ('category', 'Rock'), ('size', 96), ('size', 336),
            ('size', 48), ('denominator', 8), ('denominator', 16), ('denominator', 2))
    for index, (field, value) in enumerate(rows):
        def build(ctx, f=field, v=value):
            values = {'name': 'Main', 'notes': [S.Note(0, 0), S.Note(24, 1)], f: v}
            pattern = S.Pattern(**values)
            return base(ctx, patterns=[pattern], sequence=[[pattern.name]]).xml()
        add(suite, 'pattern', f'{field}-{index:02d}', Load(build, [('patterns', ('name', 'info', 'category', 'size',
                                                                                  'denominator'))]),
            f'Open a song with a pattern whose {field} is {value!r} and save it again')


def structure(suite):
    suite.setup(FAMILY, 'structure', prepare, 'Fresh instance with the verifier samples')
    three = [S.Pattern('A', notes(0)), S.Pattern('B', notes(48, instrument=1)), S.Pattern('C', notes(96, instrument=2))]

    def song(**values):
        return lambda ctx: base(ctx, patterns=[S.Pattern(p.name, list(p.notes)) for p in three], **values).xml()
    add(suite, 'structure', 'sequence-gaps', Load(song(sequence=[['A'], [], ['B', 'C'], [], ['A']]), ['sequence']),
        'Open a song whose arrangement has empty columns and a column with two patterns, and save it again')
    add(suite, 'structure', 'sequence-long', Load(song(sequence=[['A', 'B', 'C']] * 2 + [['C']] * 6), ['sequence']),
        'Open a song with eight columns, the first two holding all three patterns, and save it again')
    add(suite, 'structure', 'virtual-two', Load(song(sequence=[['C']], virtual=(('C', ('A', 'B')),)),
                                                ['virtual', 'sequence']),
        'Open a song whose pattern C is a virtual pattern of A and B, and save it again')
    add(suite, 'structure', 'virtual-several', Load(song(sequence=[['A']], virtual=(('A', ('B',)), ('B', ('C',)))),
                                                    ['virtual']),
        'Open a song with two virtual patterns (A of B, B of C) and save it again')
    add(suite, 'structure', 'markers', Load(song(sequence=[['A']] * 4, timeline=True,
                                                 tempo_markers=((0, 96.0), (3, 132.5))), ['markers']),
        'Open a song with tempo markers 96 BPM at column 0 and 132.5 BPM at column 3, and save it again')
    add(suite, 'structure', 'markers-unordered', Load(song(sequence=[['A']] * 4, tempo_markers=((2, 70.0), (1, 80.0))),
                                                      ['markers']),
        'Open a song whose tempo markers are stored out of order, and save it again')
    add(suite, 'structure', 'tags', Load(song(sequence=[['A']] * 4, tags=((0, 'Intro'), (2, 'Refrain – «B»'))),
                                         ['tags']),
        'Open a song with the timeline tags Intro and "Refrain – «B»", and save it again')
    add(suite, 'structure', 'tag-markup', Load(song(sequence=[['A']] * 2, tags=((1, 'A & B <C>'),)), ['tags']),
        'Open a song with a timeline tag holding markup characters, and save it again')
    add(suite, 'structure', 'velocity-path', Load(song(sequence=[['A']] * 3, velocity_path=((0.0, 0.5), (1.5, 1.0),
                                                                                           (3.0, 0.2))),
                                                  ['velocity_path']),
        'Open a song with a velocity automation path of three points, and save it again')
    add(suite, 'structure', 'sequence-thirty-two', Load(song(sequence=[['A'], ['B'], ['C'], ['A', 'C']] * 8),
                                                        ['sequence']),
        'Open a song with 32 columns, and save it again')
    add(suite, 'structure', 'stacked-notes', Load(lambda ctx: base(ctx, patterns=[S.Pattern('P', [
        S.Note(0, 0, velocity=0.4), S.Note(0, 0, velocity=0.9, key='G0'), S.Note(0, 1)])]).xml(),
        [('patterns', ('notes',))]),
        'Open a song with three notes on the same tick, two of them on the same instrument, and save it again')
    for index, (track, enabled, volume) in enumerate((('pad.wav', False, 0.9), ('tone440.wav', True, 1.5),
                                                      ('', False, 0.0))):
        add(suite, 'structure', f'playback-{index}', Load(lambda ctx, t=track, e=enabled, v=volume: base(
            ctx, playback_track=ctx.inputs(t) if t else '', playback_enabled=e, playback_volume=v).xml(),
            [('song', ('playback',))]),
            f'Open a song with the playback track {track or "unset"} ({"enabled" if enabled else "disabled"}, '
            f'volume {volume:g}) and save it again')
    add(suite, 'structure', 'three-components', Load(lambda ctx: base(
        ctx, components=((0, 'Close', 1.0), (1, 'Overhead', 0.7), (2, 'Room', 0.4))).xml(), ['components']),
        'Open a song with three drumkit components, and save it again')
    for index, (kit, lookup) in enumerate((('GMRockKit', 0), ('TR808EmulationKit', 1))):
        add(suite, 'structure', f'instrument-kit-{index}', Load(lambda ctx, k=kit, l=lookup: base(
            ctx, instruments=[instrument(ctx, 'kick.wav', 0, name='Kick', drumkit=k, drumkit_lookup=l)],
            patterns=[S.Pattern('P', notes(0))]).xml(), [('instruments', ('name', 'drumkit'))]),
            f'Open a song whose instrument names the drum kit {kit} (lookup {lookup}), and save it again')
    add(suite, 'structure', 'velocity-path-flat', Load(song(sequence=[['A']], velocity_path=((0.0, 0.8),)),
                                                       ['velocity_path']),
        'Open a song with a one-point velocity automation path, and save it again')


def pattern_documents(suite):
    suite.setup(FAMILY, 'pattern-document', prepare, 'Fresh instance with the verifier samples')

    def into_song(ctx):
        name = ctx.upload('pattern-host.h2song', base(ctx, name='Pattern host').xml())
        ctx.open_song(name)
    rows = (('velocity', 0.35), ('pan', -0.8), ('leadlag', -0.25), ('pitch', 0.2), ('key', 'Ef1'), ('length', 60),
            ('probability', 0.75), ('note_off', True))
    for index, (field, value) in enumerate(rows):
        add(suite, 'pattern-document', f'note-{field}-{index:02d}', Load(
            lambda ctx, f=field, v=value: S.pattern_file(S.Pattern('Loaded', [S.Note(12, 0), S.Note(60, 2, **{f: v})])),
            [('patterns', ('name', 'notes'))], kind='pattern', before=into_song),
            f'Open a pattern document with a note whose {field.replace("_", " ")} is {value!r} into a song and save it')
    for size, denominator in ((144, 4), (84, 16)):
        add(suite, 'pattern-document', f'size-{size}-{denominator}', Load(
            lambda ctx, n=size, d=denominator: S.pattern_file(S.Pattern('Sized', [S.Note(0, 1)], size=n,
                                                                        denominator=d)),
            [('patterns', ('name', 'size', 'denominator'))], kind='pattern', before=into_song),
            f'Open a pattern document of {size} ticks in 1/{denominator} into a song and save it')


def build(suite):
    song_fields(suite)
    instrument_fields(suite)
    layer_fields(suite)
    note_fields(suite)
    pattern_fields(suite)
    structure(suite)
    pattern_documents(suite)
