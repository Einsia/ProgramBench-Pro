"""Rendering matrices: one sampler parameter varied over values that each give a different sound.

Like render_cases, every row uploads a verifier song, exports it with the product command line and compares the
decoded file. Where the playback is exact arithmetic (gains, pans, positions) levels compare within the linear
tolerance; pitched, filtered and enveloped results use the default signal tolerance. Values are chosen so that
neighbouring rows differ beyond their tolerance.
"""
from __future__ import annotations

import songs as S
from render_cases import LINEAR, ONSETS, PITCH, Render, instrument, layer, notes, single, upload_samples

ENVELOPE = {'window': 2048, 'limit': 60}
BANDS = {'bands': True}


def add(suite, scenario, step, render, description, requires=()):
    return suite.add('render-' + scenario, scenario, step, render, description=description, requires=requires)


def exact(build, spec=None):
    return Render(build, spec=spec, tolerance=LINEAR)


def keys(suite):
    suite.setup('render-keys', 'keys', upload_samples, 'Upload the verifier sample library')
    for key in ('C0', 'Cs0', 'D0', 'Ef0', 'E0', 'F0', 'G0', 'Af0', 'A0', 'Bf0', 'B0', 'A-3', 'A-2', 'A1', 'A2',
                'A3', 'Cs-1', 'Ef2'):
        add(suite, 'keys', f'key-{key}', Render(single('tone440.wav', notes(0, key=key)), spec=PITCH),
            f'Export a 440 Hz sample played as note {key} (C0 plays the sample as recorded)')
    for fine in (-0.5, -0.25, 0.25):
        add(suite, 'keys', f'note-fine-{fine:g}', Render(single('tone440.wav', notes(0, pitch=fine)), spec=PITCH),
            f'Export a note with a fine pitch of {fine:g} semitones')
    for offset in (-24.0, -12.5, -7.0, -1.0, 1.0, 12.0, 24.0):
        add(suite, 'keys', f'instrument-offset-{offset:g}',
            Render(single('tone440.wav', notes(0), pitch_offset=offset), spec=PITCH),
            f'Export with the instrument pitch offset at {offset:g} semitones')
    for value in (-24.0, -7.0, 5.0, 24.0):
        add(suite, 'keys', f'layer-pitch-{value:g}',
            Render(lambda ctx, v=value: S.Song([instrument(ctx, '', layers=[layer(ctx, 'tone440.wav', pitch=v)])],
                                               [S.Pattern('P', notes(0))]), spec=PITCH),
            f'Export with the sample layer pitched by {value:g} semitones')
    add(suite, 'keys', 'all-sources', Render(lambda ctx: S.Song(
        [instrument(ctx, '', layers=[layer(ctx, 'tone440.wav', pitch=1.0)], pitch_offset=-4.0)],
        [S.Pattern('P', notes(0, key='D1', pitch=-0.25))]), spec=PITCH),
        'Export note D1 with fine pitch -0.25 on an instrument pitched -4 with a layer pitched +1')
    add(suite, 'keys', 'two-keys-overlap', Render(lambda ctx: S.Song(
        [instrument(ctx, 'long440.wav')], [S.Pattern('P', [S.Note(0, key='C0'), S.Note(48, key='G0')])]),
        spec={'pitch': (1.2, 1.6), 'window': 2048, 'limit': 40}),
        'Export two overlapping notes C0 and G0 of a long tone on one instrument')


def levels(suite):
    suite.setup('render-levels', 'levels', upload_samples, 'Upload the verifier sample library')
    for velocity in (0.1, 0.2, 0.5, 0.9):
        add(suite, 'levels', f'velocity-{velocity:g}', exact(single('dc.wav', notes(0, velocity=velocity))),
            f'Export a constant-level sample played with note velocity {velocity:g}')
    for volume in (0.1, 0.8, 1.2):
        add(suite, 'levels', f'instrument-volume-{volume:g}', exact(single('dc.wav', notes(0), volume=volume)),
            f'Export with the instrument volume at {volume:g}')
    for value in (0.1, 1.5, 3.5):
        add(suite, 'levels', f'instrument-gain-{value:g}', exact(single('dc.wav', notes(0), gain=value)),
            f'Export with the instrument gain at {value:g}')
    for value in (0.5, 1.5):
        add(suite, 'levels', f'layer-gain-{value:g}',
            exact(lambda ctx, v=value: S.Song([instrument(ctx, '', layers=[layer(ctx, 'dc.wav', gain=v)])],
                                              [S.Pattern('P', notes(0))])),
            f'Export with the sample layer gain at {value:g}')
    audible = None
    for value in (1.2, 0.0):
        case = add(suite, 'levels', f'component-gain-{value:g}',
                   exact(lambda ctx, v=value: S.Song([instrument(ctx, '', components=[
                       S.Component([layer(ctx, 'dc.wav')], gain=v)])], [S.Pattern('P', notes(0))])),
                   f'Export with the instrument component gain at {value:g}',
                   requires=(audible,) if value == 0.0 else ())
        audible = audible or case
    for value in (0.6, 1.2):
        add(suite, 'levels', f'component-volume-{value:g}',
            exact(single('dc.wav', notes(0), song={'components': ((0, 'Main', value),)})),
            f'Export with the drumkit component volume at {value:g}')
    for value in (0.3, 0.75):
        add(suite, 'levels', f'master-{value:g}', exact(single('dc.wav', notes(0), song={'volume': value})),
            f'Export with the song (master) volume at {value:g}')
    add(suite, 'levels', 'velocity-and-volume', exact(single('dc.wav', notes(0, velocity=0.4), volume=0.5, gain=2.0)),
        'Export a note of velocity 0.4 on an instrument with volume 0.5 and gain 2')
    add(suite, 'levels', 'three-instruments', exact(lambda ctx: S.Song(
        [instrument(ctx, 'dc.wav', 0, volume=0.2), instrument(ctx, 'dc.wav', 1, volume=0.3, pan=-0.5),
         instrument(ctx, 'dc.wav', 2, volume=0.25, pan=0.5)],
        [S.Pattern('P', [S.Note(0, 0), S.Note(0, 1), S.Note(0, 2)])])),
        'Export three constant-level instruments with different volumes and pans sounding together')


def panning(suite):
    suite.setup('render-panning', 'panning', upload_samples, 'Upload the verifier sample library')
    for value in (-0.25, 0.1, 0.5, 0.8):
        add(suite, 'panning', f'instrument-{value:g}', exact(single('dc.wav', notes(0), pan=value)),
            f'Export with the instrument pan at {value:g}')
    for value in (-1.0, -0.3, 0.9, 1.0):
        add(suite, 'panning', f'note-{value:g}', exact(single('dc.wav', notes(0, pan=value))),
            f'Export a note panned to {value:g}')
    for inst, note in ((0.5, 0.5), (-0.5, 0.5), (0.9, -0.9), (-0.2, -0.7)):
        add(suite, 'panning', f'instrument-{inst:g}-note-{note:g}',
            exact(single('dc.wav', notes(0, pan=note), pan=inst)),
            f'Export a note panned to {note:g} on an instrument panned to {inst:g}')
    for law in S.PAN_LAWS:
        add(suite, 'panning', f'law-{law.lower()}-0.85',
            exact(single('dc.wav', notes(0), pan=0.85, song={'pan_law': law, 'k_norm': 1.33333})),
            f'Export with the pan law {law} and the instrument panned to 0.85')
    for law in ('RATIO_CONST_POWER', 'LINEAR_CONST_SUM', 'POLAR_STRAIGHT_POLYGONAL', 'QUADRATIC_CONST_K_NORM'):
        add(suite, 'panning', f'law-{law.lower()}-note',
            exact(single('dc.wav', notes(0, pan=-0.4), pan=0.2, song={'pan_law': law, 'k_norm': 2.0})),
            f'Export with the pan law {law} (k 2), a note panned to -0.4 on an instrument panned to 0.2')


def envelopes(suite):
    suite.setup('render-envelopes', 'envelopes', upload_samples, 'Upload the verifier sample library')
    for attack in (1000, 10000, 22050):
        add(suite, 'envelopes', f'attack-{attack}', Render(single('long440.wav', notes(0), attack=attack),
                                                           spec=ENVELOPE),
            f'Export a 3 s tone with an attack of {attack} frames')
    for decay, sustain in ((4410, 0.6), (44100, 0.1), (2205, 0.9)):
        add(suite, 'envelopes', f'decay-{decay}-sustain-{sustain:g}',
            Render(single('long440.wav', notes(0), decay=decay, sustain=sustain), spec=ENVELOPE),
            f'Export a 3 s tone with a decay of {decay} frames to a sustain level of {sustain:g}')
    for release in (1000, 4410, 44100):
        add(suite, 'envelopes', f'release-{release}',
            Render(single('long440.wav', notes(0, length=24), release=release), spec={'window': 1024, 'limit': 100}),
            f'Export a 24-tick note of a 3 s tone with a release of {release} frames')
    add(suite, 'envelopes', 'full-adsr', Render(single('long440.wav', notes(0, length=96), attack=4410, decay=8820,
                                                       sustain=0.4, release=8820), spec={'window': 1024, 'limit': 100}),
        'Export a 96-tick note with attack 4410, decay 8820, sustain 0.4 and release 8820 frames')
    for length in (6, 48, 96, 192):
        add(suite, 'envelopes', f'length-{length}',
            Render(single('long440.wav', notes(0, length=length), release=1000), spec={'window': 1024, 'limit': 120}),
            f'Export a note {length} ticks long of a 3 s tone with a release of 1000 frames')


def cutoffs(suite):
    suite.setup('render-cutoffs', 'cutoffs', upload_samples, 'Upload the verifier sample library')
    for cutoff in (0.8, 0.45, 0.2, 0.05):
        add(suite, 'cutoffs', f'cutoff-{cutoff:g}',
            Render(single('noise.wav', notes(0), filter_active=True, filter_cutoff=cutoff), spec=BANDS),
            f'Export white noise through the active instrument filter at cutoff {cutoff:g}')
    for resonance in (0.2, 0.7):
        add(suite, 'cutoffs', f'resonance-{resonance:g}',
            Render(single('noise.wav', notes(0), filter_active=True, filter_cutoff=0.5, filter_resonance=resonance),
                   spec=BANDS),
            f'Export white noise through the filter at cutoff 0.5 and resonance {resonance:g}')
    for cutoff in (0.15, 0.4):
        add(suite, 'cutoffs', f'tone-{cutoff:g}',
            Render(single('tone880.wav', notes(0), filter_active=True, filter_cutoff=cutoff), spec={'window': 2048}),
            f'Export an 880 Hz tone through the filter at cutoff {cutoff:g}')


def tempos(suite):
    suite.setup('render-tempos', 'tempos', upload_samples, 'Upload the verifier sample library')
    for bpm in (60.0, 90.0, 100.0, 150.0, 200.0, 250.0):
        add(suite, 'tempos', f'bpm-{bpm:g}', exact(single('click.wav', notes(0, 48, 96, 144), bpm=bpm), ONSETS),
            f'Export the four-click pattern at {bpm:g} BPM')
    grids = (('triplets', (0, 16, 32, 48, 64, 80)), ('thirty-seconds', (0, 6, 12, 18, 24, 30)),
             ('sixty-fourths', (0, 3, 6, 9)), ('scattered', (5, 50, 100, 150, 187)))
    for label, positions in grids:
        add(suite, 'tempos', f'grid-{label}', exact(single('click.wav', notes(*positions)), ONSETS),
            f'Export clicks at ticks {", ".join(map(str, positions))}')
    for size in (24, 72, 120, 168, 288):
        add(suite, 'tempos', f'size-{size}', exact(single('click.wav', notes(0, size - 12), size=size), ONSETS),
            f'Export a pattern of {size} ticks with notes on its first tick and a sixteenth before its end')
    for leadlag in (-0.7, 0.2, 0.8):
        add(suite, 'tempos', f'leadlag-{leadlag:g}', exact(single('click.wav', [S.Note(48, leadlag=leadlag),
                                                                               S.Note(144)]), ONSETS),
            f'Export a click with lead/lag {leadlag:g} on beat two and a plain click on beat four')
    for swing in (0.1, 0.5, 1.0):
        add(suite, 'tempos', f'swing-{swing:g}', exact(single('click.wav', notes(0, 12, 24, 36, 48, 60),
                                                              song={'swing': swing}), ONSETS),
            f'Export sixteenth-note clicks with a swing factor of {swing:g}')
    add(suite, 'tempos', 'swing-and-leadlag', exact(single('click.wav', [S.Note(12, leadlag=-0.5), S.Note(36)],
                                                           song={'swing': 0.4}), ONSETS),
        'Export swung sixteenths of which the first also has a lead/lag of -0.5')


def resampling(suite):
    suite.setup('render-resampling', 'resampling', upload_samples, 'Upload the verifier sample library')
    # Third and Hermite interpolation give the same samples in this product; one of them is enough here.
    for mode in range(4):
        add(suite, 'resampling', f'down-{mode}',
            Render(single('square110.wav', notes(0, key='F-1')), options={'interpolation': mode},
                   spec={'excerpt': (2000, 400), 'window': 2048}),
            f'Export a 110 Hz square wave lowered by 7 semitones with interpolation mode {mode}')
        add(suite, 'resampling', f'rate-{mode}',
            Render(single('square110.wav', notes(0)), options={'interpolation': mode, 'rate': 48000},
                   spec={'excerpt': (2000, 400), 'window': 2048}),
            f'Export a 44.1 kHz square wave to a 48 kHz file with interpolation mode {mode}')
    add(suite, 'resampling', 'sample-48k-rate-22050',
        Render(single('tone440-48k.wav', notes(0)), options={'rate': 22050}, spec=PITCH),
        'Export a 440 Hz sample recorded at 48 kHz to a 22050 Hz file')


def arrangement(suite):
    suite.setup('render-arrangement', 'arrangement', upload_samples, 'Upload the verifier sample library')

    def song(patterns, sequence, **values):
        def build(ctx):
            return S.Song([instrument(ctx, 'click.wav'), instrument(ctx, 'tone880.wav', 1)], patterns, sequence=sequence,
                          **values)
        return build
    a, b, c = (S.Pattern('A', notes(0, 48), size=96), S.Pattern('B', notes(0, 96, 144)),
               S.Pattern('C', notes(24, instrument=1), size=144))
    add(suite, 'arrangement', 'mixed-sizes', exact(song([a, b, c], [['A'], ['B'], ['C'], ['A', 'C']]),
                                                  dict(ONSETS, window=2048)),
        'Export four columns of patterns 96, 192 and 144 ticks long, the last combining two of them')
    add(suite, 'arrangement', 'trailing-empty', exact(song([a, b], [['A'], [], [], ['B']]), dict(ONSETS, window=2048)),
        'Export a song with two empty columns between its first and last')
    add(suite, 'arrangement', 'virtual-of-virtual', exact(song(
        [a, b, c, S.Pattern('V', []), S.Pattern('W', [])], [['W']],
        virtual=(('V', ('A', 'B')), ('W', ('V', 'C')))), dict(ONSETS, window=2048)),
        'Export a column that plays a virtual pattern whose members include another virtual pattern')
    for markers in (((0, 60.0), (2, 180.0)), ((1, 90.0),)):
        label = '-'.join(f'{c}x{bpm:g}' for c, bpm in markers)
        add(suite, 'arrangement', f'tempo-markers-{label}', exact(song([b], [['B']] * 3, timeline=True,
                                                                        tempo_markers=markers), ONSETS),
            'Export three columns with the timeline active and tempo markers ' +
            ', '.join(f'{bpm:g} BPM at column {c}' for c, bpm in markers))
    for points, label in ((((0.0, 1.0), (1.0, 0.5), (2.0, 1.0)), 'dip'), (((0.0, 0.0), (1.0, 1.0)), 'from-silence')):
        add(suite, 'arrangement', f'velocity-path-{label}',
            Render(lambda ctx, p=points: S.Song([instrument(ctx, 'dc.wav')], [S.Pattern('A', notes(0, 96))],
                                                sequence=[['A']] * 3, velocity_path=p), spec={'window': 4096}),
            f'Export three columns with a velocity automation path ({label})')
    for volume in (0.3, 1.0):
        add(suite, 'arrangement', f'playback-volume-{volume:g}',
            Render(lambda ctx, v=volume: S.Song([instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 96))],
                                                playback_track=ctx.inputs('pad.wav'), playback_enabled=True,
                                                playback_volume=v), spec={'window': 2048}),
            f'Export a song with the playback track pad.wav enabled at volume {volume:g}')

    def mixer(first=None, second=None):
        def build(ctx):
            return S.Song([instrument(ctx, 'tone440.wav', 0, **(first or {})),
                           instrument(ctx, 'tone660.wav', 1, **(second or {}))],
                          [S.Pattern('A', [S.Note(0, instrument=0), S.Note(48, instrument=1)])])
        return build
    both = add(suite, 'arrangement', 'both-soloed', Render(mixer({'soloed': True}, {'soloed': True}),
                                                           spec={'window': 2048}),
               'Export a song in which both instruments are soloed')
    add(suite, 'arrangement', 'muted-and-soloed', Render(mixer({'soloed': True, 'muted': True}),
                                                         spec={'window': 2048}),
        'Export a song in which the first instrument is soloed and muted at the same time', requires=(both,))


def edits(suite):
    suite.setup('render-edits', 'edits', upload_samples, 'Upload the verifier sample library')

    def edited(**options):
        def build(ctx):
            values = dict(options)
            sample = values.pop('sample', 'ramp.wav')
            values.setdefault('modified', True)
            return S.Song([instrument(ctx, '', layers=[layer(ctx, sample, **values)])], [S.Pattern('P', notes(0))])
        return build
    frames = 22050
    add(suite, 'edits', 'start-end-late', Render(edited(startframe=2000, loopframe=2000, endframe=20000),
                                                 spec={'window': 512, 'limit': 60, 'excerpt': (0, 64)}),
        'Export a ramp sample edited to play frames 2000 to 20000')
    add(suite, 'edits', 'loop-three', Render(edited(startframe=0, loopframe=16538, endframe=frames, loops=3),
                                             spec={'window': 1024, 'limit': 80}),
        'Export a ramp sample whose last quarter loops three times forward')
    add(suite, 'edits', 'reverse-loops', Render(edited(smode='reverse', startframe=0, loopframe=11025, endframe=frames,
                                                       loops=2), spec={'window': 1024, 'limit': 80}),
        'Export a ramp sample whose second half loops twice in reverse')
    add(suite, 'edits', 'pingpong-two', Render(edited(smode='pingpong', startframe=0, loopframe=5512, endframe=frames,
                                                      loops=2), spec={'window': 1024, 'limit': 100}),
        'Export a ramp sample whose last three quarters loop back and forth twice')
    add(suite, 'edits', 'volume-ramp', Render(edited(sample='dc.wav', startframe=0, endframe=frames,
                                                     volume_envelope=((0, 0), (841, 100))),
                                              spec={'window': 512, 'limit': 50}),
        'Export a constant sample with a volume envelope rising from silence')
    add(suite, 'edits', 'pan-right-left', Render(edited(sample='dc.wav', startframe=0, endframe=frames,
                                                        pan_envelope=((0, 100), (420, 50), (841, 0))),
                                                 spec={'window': 512, 'limit': 50}),
        'Export a constant sample with a pan envelope from right through centre to left')


def chokes(suite):
    suite.setup('render-chokes', 'chokes', upload_samples, 'Upload the verifier sample library')

    def three(groups):
        def build(ctx):
            return S.Song([instrument(ctx, 'long440.wav', 0, mute_group=groups[0]),
                           instrument(ctx, 'tone880.wav', 1, mute_group=groups[1]),
                           instrument(ctx, 'tone660.wav', 2, mute_group=groups[2])],
                          [S.Pattern('P', [S.Note(0, 0), S.Note(48, 1), S.Note(96, 2)])])
        return build
    for groups in ((2, 2, 2), (2, 3, 2)):
        add(suite, 'chokes', 'groups-' + '-'.join(map(str, groups)),
            Render(three(groups), spec={'window': 2048, 'limit': 80}),
            f'Export three instruments in mute groups {groups} entering one beat apart')
    add(suite, 'chokes', 'stop-note-velocities', Render(single('long440.wav', notes(0, velocity=1.0) +
                                                                notes(48, velocity=0.3), stop_note=True),
                                                         spec={'window': 2048, 'limit': 80}),
        'Export a loud and a soft note of a long tone on an instrument with Auto-Stop Note')
    for beat in (1, 3):
        add(suite, 'chokes', f'note-off-beat-{beat}',
            Render(single('long440.wav', [S.Note(0), S.Note(48 * beat, note_off=True, velocity=0.0)], release=4410),
                   spec={'window': 2048, 'limit': 100}),
            f'Export a long tone followed by a note-off event {beat} beat(s) later')


def laws(suite):
    suite.setup('render-laws', 'laws', upload_samples, 'Upload the verifier sample library')
    # (At -0.9 the constant-power laws of the ratio, linear and polar families give their straight-polygonal values.)
    same = {'RATIO_CONST_POWER', 'LINEAR_CONST_POWER', 'POLAR_CONST_POWER'}
    for value in (-0.9, 0.15):
        for law in S.PAN_LAWS:
            if value == -0.9 and law in same:
                continue
            add(suite, 'laws', f'{law.lower()}-{value:g}',
                exact(single('dc.wav', notes(0), pan=value, song={'pan_law': law, 'k_norm': 1.33333})),
                f'Export with the pan law {law} and the instrument panned to {value:g}')


def registers(suite):
    suite.setup('render-registers', 'registers', upload_samples, 'Upload the verifier sample library')
    for key in ('C-3', 'E-2', 'G-1', 'D1', 'F2', 'C3'):
        add(suite, 'registers', f'key-{key}', Render(single('tone220.wav', notes(0, key=key)), spec=PITCH),
            f'Export a 220 Hz sample played as note {key}')
    for key, layer_pitch in (('A0', -9.0), ('E-1', 4.5), ('Bf1', -12.0), ('Fs-2', 7.0)):
        add(suite, 'registers', f'key-{key}-layer-{layer_pitch:g}',
            Render(lambda ctx, k=key, lp=layer_pitch: S.Song(
                [instrument(ctx, '', layers=[layer(ctx, 'tone220.wav', pitch=lp)])], [S.Pattern('P', notes(0, key=k))]),
                spec=PITCH),
            f'Export note {key} of a 220 Hz layer pitched by {layer_pitch:g} semitones')


def stacking(suite):
    suite.setup('render-stacking', 'stacking', upload_samples, 'Upload the verifier sample library')
    add(suite, 'stacking', 'same-tick-twice', exact(single('dc.wav', [S.Note(0, velocity=0.5), S.Note(0, velocity=0.3)])),
        'Export two notes of the same instrument on the same tick (velocities 0.5 and 0.3)')
    add(suite, 'stacking', 'beyond-pattern', exact(single('click.wav', notes(0, 96, 200), size=192), ONSETS),
        'Export a 192-tick pattern whose third note lies at tick 200, beyond its end')
    add(suite, 'stacking', 'tail-past-end', Render(single('long440.wav', notes(168)), spec={'window': 2048}),
        'Export a 3 s tone that starts on the last eighth of a one-bar song')

    def two_layers(velocities):
        def build(ctx):
            layers = [layer(ctx, 'layer220.wav', min=0.0, max=0.5), layer(ctx, 'layer770.wav', min=0.5, max=1.0)]
            return S.Song([instrument(ctx, '', layers=layers)],
                          [S.Pattern('P', [S.Note(48 * i, velocity=v) for i, v in enumerate(velocities)])])
        return build
    add(suite, 'stacking', 'layer-edge-below', Render(two_layers((0.49, 0.2)), spec={'window': 2048}),
        'Export notes of velocity 0.49 and 0.2 on an instrument with layers for 0-0.5 and 0.5-1')
    add(suite, 'stacking', 'layer-edge-above', Render(two_layers((0.51, 0.95)), spec={'window': 2048}),
        'Export notes of velocity 0.51 and 0.95 on an instrument with layers for 0-0.5 and 0.5-1')

    def robin(ctx):
        layers = [layer(ctx, name) for name in ('layer220.wav', 'layer550.wav', 'layer770.wav')]
        return S.Song([instrument(ctx, '', layers=layers, selection='ROUND_ROBIN')],
                      [S.Pattern('P', [S.Note(32 * i, velocity=0.7) for i in range(6)])])
    add(suite, 'stacking', 'round-robin-three', Render(robin, spec={'window': 2048}),
        'Export six equal notes on an instrument whose three layers alternate round-robin')


def factory(suite):
    """The product's factory drum kits, loaded in place of a verifier song's instruments for the export (-k)."""
    suite.setup('render-factory', 'factory', upload_samples, 'Upload the verifier sample library')

    def slots(velocities=None):
        def build(ctx):
            count = 18
            notes_ = ([S.Note(24 * i, i, velocity=0.8) for i in range(count)] if velocities is None else
                      [S.Note(48 * i, 0, velocity=v) for i, v in enumerate(velocities)])
            return S.Song([instrument(ctx, 'click.wav', i, name=f'Slot {i}') for i in range(count)],
                          [S.Pattern('P', notes_, size=24 * count)])
        return build
    for kit in ('GMRockKit', 'TR808EmulationKit'):
        add(suite, 'factory', f'{kit.lower()}-instruments',
            Render(slots(), options={'kit': kit}, spec={'window': 2048, 'onsets': 0.02}),
            f'Export a song of 18 instrument slots, one note each, with the factory kit {kit} loaded in their place')
    add(suite, 'factory', 'gmrockkit-kick-velocities',
        Render(slots((0.1, 0.3, 0.5, 0.7, 0.95)), options={'kit': 'GMRockKit'}, spec={'window': 2048, 'onsets': 0.02}),
        'Export five notes of the first GMRockKit instrument with rising velocities')


def combos(suite):
    suite.setup('render-combos', 'combos', upload_samples, 'Upload the verifier sample library')

    def song(instruments, notes_, size=192, **values):
        def build(ctx):
            return S.Song([factory(ctx) for factory in instruments], [S.Pattern('P', list(notes_), size=size)], **values)
        return build
    add(suite, 'combos', 'components-with-layers', Render(lambda ctx: S.Song([instrument(ctx, '', components=[
        S.Component([layer(ctx, 'layer220.wav', max=0.5), layer(ctx, 'layer550.wav', min=0.5)], id=0),
        S.Component([layer(ctx, 'layer330.wav', max=0.5, gain=0.7), layer(ctx, 'layer770.wav', min=0.5)], id=1,
                    gain=0.6)])], [S.Pattern('P', [S.Note(0, velocity=0.3), S.Note(96, velocity=0.8)])],
        components=((0, 'Main', 1.0), (1, 'Room', 0.8))), spec={'window': 2048}),
        'Export two notes on an instrument of two components that each hold two velocity layers')
    add(suite, 'combos', 'stop-note-in-group', Render(song(
        [lambda ctx: instrument(ctx, 'long440.wav', 0, stop_note=True, mute_group=1),
         lambda ctx: instrument(ctx, 'tone880.wav', 1, mute_group=1)],
        [S.Note(0, 0), S.Note(48, 0, velocity=0.5), S.Note(96, 1)]), spec={'window': 2048, 'limit': 80}),
        'Export a long tone with Auto-Stop Note restarted once and then cut by a second instrument of its mute group')
    add(suite, 'combos', 'filter-on-pitched', Render(single('tone440.wav', notes(0, key='G0'), filter_active=True,
                                                            filter_cutoff=0.3), spec={'window': 2048}),
        'Export a 440 Hz sample raised to G0 through the filter at cutoff 0.3')
    add(suite, 'combos', 'attack-on-layers', Render(lambda ctx: S.Song([instrument(ctx, '', layers=[
        layer(ctx, 'layer220.wav', max=0.5), layer(ctx, 'layer770.wav', min=0.5)], attack=4410)],
        [S.Pattern('P', [S.Note(0, velocity=0.2), S.Note(96, velocity=0.9)])]), spec={'window': 1024, 'limit': 60}),
        'Export a soft and a loud note with a 4410-frame attack on an instrument with two velocity layers')
    add(suite, 'combos', 'swing-three-four', exact(single('click.wav', notes(0, 12, 24, 36, 72, 84, 132), size=144,
                                                          song={'swing': 0.7}), ONSETS),
        'Export swung sixteenth notes in a 144-tick (3/4) pattern')
    add(suite, 'combos', 'markers-three-four', exact(lambda ctx: S.Song(
        [instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 48, 96), size=144)], sequence=[['A']] * 3,
        timeline=True, tempo_markers=((1, 160.0), (2, 80.0))), ONSETS),
        'Export three 3/4 bars with tempo markers 160 BPM at bar 2 and 80 BPM at bar 3')
    add(suite, 'combos', 'virtual-mixed-sizes', exact(lambda ctx: S.Song(
        [instrument(ctx, 'click.wav'), instrument(ctx, 'tone880.wav', 1)],
        [S.Pattern('Short', notes(0, 48), size=96), S.Pattern('Long', notes(120, instrument=1)), S.Pattern('V', [])],
        sequence=[['V'], ['Short']], virtual=(('V', ('Short', 'Long')),)), dict(ONSETS, window=2048)),
        'Export a virtual pattern of a 96-tick and a 192-tick pattern, then the short pattern alone')
    for key in ('C1', 'C-1'):
        add(suite, 'combos', f'length-at-{key}', Render(single('long440.wav', notes(0, key=key, length=24),
                                                               release=1000), spec={'window': 1024, 'limit': 80,
                                                                                    'pitch': (0.0, 0.1)}),
            f'Export a 24-tick note of a long tone played as {key}')
    add(suite, 'combos', 'loop-at-key', Render(lambda ctx: S.Song([instrument(ctx, '', layers=[layer(
        ctx, 'ramp.wav', modified=True, startframe=0, loopframe=11025, endframe=22050, loops=1)])],
        [S.Pattern('P', notes(0, key='C1'))]), spec={'window': 1024, 'limit': 60}),
        'Export a looped ramp sample played an octave higher')
    add(suite, 'combos', 'automation-with-markers', Render(lambda ctx: S.Song(
        [instrument(ctx, 'dc.wav')], [S.Pattern('A', notes(0, 96))], sequence=[['A']] * 3, timeline=True,
        tempo_markers=((1, 60.0),), velocity_path=((0.0, 1.0), (3.0, 0.1))), spec={'window': 4096}),
        'Export three columns with a falling velocity path while a tempo marker slows column 2 to 60 BPM')
    for volume, velocity, gain in ((0.5, 0.5, 2.0), (1.2, 0.25, 1.5)):
        add(suite, 'combos', f'levels-{volume:g}-{velocity:g}-{gain:g}',
            exact(lambda ctx, a=volume, b=velocity, c=gain: S.Song(
                [instrument(ctx, '', layers=[layer(ctx, 'dc.wav', gain=c)], volume=a)],
                [S.Pattern('P', notes(0, velocity=b))])),
            f'Export a note of velocity {velocity:g} on an instrument of volume {volume:g} with layer gain {gain:g}')
    add(suite, 'combos', 'pan-and-filter', Render(single('noise.wav', notes(0, pan=0.6), pan=-0.3, filter_active=True,
                                                         filter_cutoff=0.4), spec={'bands': True}),
        'Export panned white noise (instrument -0.3, note 0.6) through the filter at cutoff 0.4')
    add(suite, 'combos', 'reverse-pitched', Render(lambda ctx: S.Song([instrument(ctx, '', layers=[layer(
        ctx, 'ramp.wav', modified=True, smode='reverse', startframe=0, loopframe=0, endframe=22050)])],
        [S.Pattern('P', notes(0, key='G-1'))]), spec={'window': 1024, 'limit': 60}),
        'Export a ramp sample played in reverse and lowered by five semitones')


def build(suite):
    keys(suite)
    registers(suite)
    laws(suite)
    stacking(suite)
    levels(suite)
    panning(suite)
    envelopes(suite)
    cutoffs(suite)
    tempos(suite)
    resampling(suite)
    arrangement(suite)
    edits(suite)
    chokes(suite)
    combos(suite)
    factory(suite)
