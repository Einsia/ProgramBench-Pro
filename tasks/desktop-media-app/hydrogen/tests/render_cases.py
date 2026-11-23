"""Rendering through the product command line: verifier-made songs exported by h2cli and decoded independently.

Every scored row builds one song from the verifier sample library (absolute sample paths in the input area), uploads
it, exports it with `cli export` and compares the decoded file's projection: format, frame count, per-channel levels
in time windows, and where the row is about timing, pitch or spectrum, the onsets, the dominant frequency or the
band shares. The setup row of each scenario uploads the sample library. Rows are independent of each other.
"""
from __future__ import annotations

import songs as S
from harness import audio_observation
import fixtures

TPB = 48  # ticks per quarter note


def upload_samples(ctx):
    base, names = fixtures.catalog()
    for name in sorted(names):
        ctx.upload(name, (base / name).read_bytes())


def instrument(ctx, sample, iid=0, name=None, layers=None, components=None, **options):
    if components is None:
        if layers is None:
            layers = [S.Layer(ctx.inputs(sample))]
        components = [S.Component(layers)]
    return S.Instrument(iid, name or f'Instrument {iid + 1}', components, **options)


def layer(ctx, sample, **options):
    return S.Layer(ctx.inputs(sample), **options)


def notes(*positions, **options):
    return [S.Note(p, **options) for p in positions]


class Render:
    """One scored render: a song builder, export options and the projection to compare."""

    def __init__(self, song, *, options=None, suffix='.wav', spec=None, tolerance=None, expect_file=True):
        self.song, self.options, self.suffix = song, dict(options or {}), suffix
        self.spec, self.tolerance, self.expect_file = dict(spec or {}), tolerance, expect_file

    def __call__(self, ctx):
        stem = ctx.unique('render', '')
        document = self.song(ctx)
        text = document if isinstance(document, str) else document.xml()
        ctx.upload(stem + '.h2song', text)
        reply = ctx.cli('export', song=stem + '.h2song', output=stem + self.suffix, **self.options)
        path = 'outputs/' + stem + self.suffix
        if not self.expect_file:
            written = [d for d in reply.get('downloads', []) if d.get('path') == path and d.get('size')]
            return {'exit_code': reply['exit_code'], 'audio_written': bool(written)}
        data = ctx.take(path, reply.get('downloads'))
        info, frames = ctx.decode(data, stem + self.suffix)
        return audio_observation(info, frames, self.spec, self.tolerance)


EXACT = ('timing', 'gain', 'pan', 'layers', 'components', 'groove')


def add(suite, scenario, step, render, description, requires=()):
    if scenario in EXACT and render.tolerance is None:
        render.tolerance = LINEAR
    return suite.add('render-' + scenario, scenario, step, render, description=description, requires=requires)


def silent(scenario, step):
    """A render expected to be silent counts together with an audible row of the same scenario."""
    return (f'backend.render-{scenario}.{scenario}.{step}',)


def single(sample, note_list, *, size=192, bpm=120.0, song=None, **inst):
    """A song with one instrument playing one pattern once."""
    def build(ctx):
        return S.Song([instrument(ctx, sample, **inst)], [S.Pattern('Pattern 1', list(note_list), size=size)], bpm=bpm,
                      **(song or {}))
    return build


ONSETS = {'onsets': 0.02}
# Sample playback scaled, panned and placed in time is exact arithmetic: an equivalent implementation matches the
# reference to rounding (16-bit quantization), so levels compare within 5e-4 absolute or 0.5 %.
LINEAR = {'level': (0.0005, 0.005), 'onsets': 2}


def timing(suite):
    suite.setup('render-timing', 'timing', upload_samples, 'Upload the verifier sample library')
    add(suite, 'timing', 'beats', Render(single('click.wav', notes(0, 48, 96, 144)), spec=ONSETS),
        'Export four quarter-note clicks of a 4/4 pattern at 120 BPM')
    add(suite, 'timing', 'offbeat-ticks', Render(single('click.wav', notes(1, 7, 13, 25, 47, 95, 191)), spec=ONSETS),
        'Export clicks at odd tick positions (1, 7, 13, 25, 47, 95 and 191 of 192)')
    for bpm in (40.0, 75.0, 133.33, 300.0, 400.0):
        add(suite, 'timing', f'bpm-{bpm:g}', Render(single('click.wav', notes(0, 48, 96, 144), bpm=bpm), spec=ONSETS),
            f'Export the four-click pattern at {bpm:g} BPM')
    for bpm in (5.0, 650.0):
        add(suite, 'timing', f'bpm-out-of-range-{bpm:g}', Render(single('click.wav', notes(0, 96), bpm=bpm),
                                                                  spec=ONSETS),
            f'Export a song whose tempo is stored as {bpm:g} BPM, outside the product range')
    for size in (48, 96, 144, 240, 384):
        add(suite, 'timing', f'size-{size}', Render(single('click.wav', notes(0, size - 24), size=size), spec=ONSETS),
            f'Export a pattern of {size} ticks with notes on its first tick and half a beat before its end')

    def repeated(ctx):
        return S.Song([instrument(ctx, 'click.wav')], [S.Pattern('Bar', notes(0, 96))], sequence=[['Bar']] * 3)
    add(suite, 'timing', 'three-columns', Render(repeated, spec=ONSETS),
        'Export a song that plays the same two-note pattern in three song columns')

    def gap(ctx):
        return S.Song([instrument(ctx, 'click.wav')], [S.Pattern('Bar', notes(0, 96))],
                      sequence=[['Bar'], [], ['Bar']])
    add(suite, 'timing', 'empty-column', Render(gap, spec=ONSETS),
        'Export a song whose middle column is empty')

    def stacked(ctx):
        return S.Song([instrument(ctx, 'click.wav'), instrument(ctx, 'tone880.wav', 1)],
                      [S.Pattern('Long', notes(0, 288), size=384), S.Pattern('Short', notes(48, instrument=1), size=96)],
                      sequence=[['Long', 'Short'], ['Short']])
    add(suite, 'timing', 'stacked-lengths', Render(stacked, spec=dict(ONSETS, window=2048)),
        'Export a column that holds a 384-tick and a 96-tick pattern, followed by a column with the short one')

    def different(ctx):
        return S.Song([instrument(ctx, 'click.wav'), instrument(ctx, 'tone440.wav', 1)],
                      [S.Pattern('A', notes(0, 48)), S.Pattern('B', notes(0, 144, instrument=1), size=192)],
                      sequence=[['A'], ['B'], ['A', 'B']])
    add(suite, 'timing', 'pattern-order', Render(different, spec=dict(ONSETS, window=2048)),
        'Export three columns: pattern A, pattern B, then both together')


def gain(suite):
    suite.setup('render-gain', 'gain', upload_samples, 'Upload the verifier sample library')
    for velocity in (1.0, 0.75, 0.33, 0.05, 0.0):
        add(suite, 'gain', f'velocity-{velocity:g}', Render(single('dc.wav', notes(0, velocity=velocity))),
            f'Export a constant-level sample played with note velocity {velocity:g}',
            requires=silent('gain', 'velocity-1') if velocity == 0.0 else ())
    add(suite, 'gain', 'velocity-ignored', Render(single('dc.wav', notes(0, velocity=0.3), apply_velocity=False)),
        'Export a note of velocity 0.3 on an instrument that does not apply velocity')
    for volume in (0.42, 1.5, 0.0):
        add(suite, 'gain', f'instrument-volume-{volume:g}', Render(single('dc.wav', notes(0), volume=volume)),
            f'Export with the instrument volume at {volume:g}',
            requires=silent('gain', 'instrument-volume-0.42') if volume == 0.0 else ())
    for value in (0.5, 2.0, 5.0):
        add(suite, 'gain', f'instrument-gain-{value:g}', Render(single('dc.wav', notes(0), gain=value)),
            f'Export with the instrument gain at {value:g}')
    for value in (0.25, 3.0):
        add(suite, 'gain', f'layer-gain-{value:g}',
            Render(lambda ctx, v=value: S.Song([instrument(ctx, '', layers=[layer(ctx, 'dc.wav', gain=v)])],
                                               [S.Pattern('P', notes(0))])),
            f'Export with the sample layer gain at {value:g}')
    for value in (0.6, 2.5):
        add(suite, 'gain', f'component-gain-{value:g}',
            Render(lambda ctx, v=value: S.Song([instrument(ctx, '', components=[
                S.Component([layer(ctx, 'dc.wav')], gain=v)])], [S.Pattern('P', notes(0))])),
            f'Export with the instrument component gain at {value:g}')
    for value in (0.3, 1.5):
        add(suite, 'gain', f'component-volume-{value:g}',
            Render(single('dc.wav', notes(0), song={'components': ((0, 'Main', value),)})),
            f'Export with the drumkit component volume at {value:g}')
    for value in (0.1, 1.0, 1.5):
        add(suite, 'gain', f'master-{value:g}', Render(single('dc.wav', notes(0), song={'volume': value})),
            f'Export with the song (master) volume at {value:g}')
    add(suite, 'gain', 'all-factors', Render(lambda ctx: S.Song(
        [instrument(ctx, '', components=[S.Component([layer(ctx, 'dc.wav', gain=0.8)], gain=1.25)],
                    volume=0.9, gain=1.1)], [S.Pattern('P', notes(0, velocity=0.6))],
        volume=0.7, components=((0, 'Main', 0.85),))),
        'Export with velocity, layer gain, component gain and volume, instrument volume and gain and master volume '
        'all different from 1')
    add(suite, 'gain', 'sum-clips', Render(lambda ctx: S.Song(
        [instrument(ctx, 'dc.wav', 0), instrument(ctx, 'dc.wav', 1), instrument(ctx, 'dc.wav', 2)],
        [S.Pattern('P', [S.Note(0, instrument=i, velocity=1.0) for i in range(3)])], volume=1.0)),
        'Export three full-level instruments sounding together, louder than full scale')
    add(suite, 'gain', 'two-voices', Render(lambda ctx: S.Song(
        [instrument(ctx, 'tone440.wav', 0), instrument(ctx, 'tone660.wav', 1, volume=0.5)],
        [S.Pattern('P', [S.Note(0, instrument=0), S.Note(48, instrument=1)])]), spec={'window': 2048}),
        'Export two instruments with different volumes that overlap in time')


def pan(suite):
    suite.setup('render-pan', 'pan', upload_samples, 'Upload the verifier sample library')
    for value in (-1.0, -0.5, 0.25, 1.0):
        add(suite, 'pan', f'instrument-{value:g}', Render(single('dc.wav', notes(0), pan=value)),
            f'Export with the instrument pan at {value:g}')
    for value in (-0.8, 0.6):
        add(suite, 'pan', f'note-{value:g}', Render(single('dc.wav', notes(0, pan=value))),
            f'Export a note panned to {value:g}')
    add(suite, 'pan', 'instrument-and-note', Render(single('dc.wav', notes(0, pan=0.3), pan=-0.4)),
        'Export a note panned to 0.3 on an instrument panned to -0.4')
    add(suite, 'pan', 'hard-instrument-note', Render(single('dc.wav', notes(0, pan=-1.0), pan=1.0)),
        'Export a note panned hard left on an instrument panned hard right')
    add(suite, 'pan', 'legacy-pair', Render(single('dc.wav', notes(0), legacy_pan=(0.4, 1.0))),
        'Export a song whose instrument pan is stored as the pair pan_L 0.4, pan_R 1.0')
    add(suite, 'pan', 'legacy-note-pair', Render(single('dc.wav', [S.Note(0, legacy_pan=(1.0, 0.25))])),
        'Export a note whose pan is stored as the pair pan_L 1.0, pan_R 0.25')
    add(suite, 'pan', 'stereo-sample', Render(single('stereo.wav', notes(0), pan=0.5), spec={'pitch': (0.05, 0.45)}),
        'Export a stereo sample (440 Hz left, 660 Hz right) on an instrument panned to 0.5')
    for law in S.PAN_LAWS:
        for value in (-0.6, 0.35):
            add(suite, 'pan', f'law-{law.lower()}-{value:g}',
                Render(single('dc.wav', notes(0), pan=value, song={'pan_law': law, 'k_norm': 1.33333})),
                f'Export with the pan law {law} and the instrument panned to {value:g}')
    for law in ('LINEAR_CONST_K_NORM', 'POLAR_CONST_K_NORM', 'RATIO_CONST_K_NORM', 'QUADRATIC_CONST_K_NORM'):
        for k in (1.0, 3.0):
            add(suite, 'pan', f'k-norm-{law.lower()}-{k:g}',
                Render(single('dc.wav', notes(0), pan=-0.5, song={'pan_law': law, 'k_norm': k})),
                f'Export with the pan law {law}, k {k:g} and the instrument panned to -0.5')
    add(suite, 'pan', 'unknown-law', Render(single('dc.wav', notes(0), pan=0.5, song={'pan_law': 'NO_SUCH_LAW'})),
        'Export a song that names an unknown pan law, instrument panned to 0.5')


PITCH = {'pitch': (0.02, 0.2)}


def pitch(suite):
    suite.setup('render-pitch', 'pitch', upload_samples, 'Upload the verifier sample library')
    for key in ('C1', 'C-1', 'Fs0', 'Bf-1', 'C2', 'D-2', 'B3'):
        add(suite, 'pitch', f'key-{key}', Render(single('tone440.wav', notes(0, key=key)), spec=PITCH),
            f'Export a 440 Hz sample played as note {key} (C0 plays the sample as recorded)')
    add(suite, 'pitch', 'key-unknown-name', Render(single('tone440.wav', notes(0, key='F#1')), spec=PITCH),
        'Export a note whose stored key F#1 uses a note name the product does not spell that way')
    add(suite, 'pitch', 'note-fine', Render(single('tone440.wav', notes(0, pitch=0.5)), spec=PITCH),
        'Export a note with a fine pitch of +0.5 semitones')
    for offset in (7.0, -5.0, 0.25):
        add(suite, 'pitch', f'instrument-{offset:g}', Render(single('tone440.wav', notes(0), pitch_offset=offset),
                                                             spec=PITCH),
            f'Export with the instrument pitch offset at {offset:g} semitones')
    for value in (2.0, -12.0):
        add(suite, 'pitch', f'layer-{value:g}',
            Render(lambda ctx, v=value: S.Song([instrument(ctx, '', layers=[layer(ctx, 'tone440.wav', pitch=v)])],
                                               [S.Pattern('P', notes(0))]), spec=PITCH),
            f'Export with the sample layer pitched by {value:g} semitones')
    add(suite, 'pitch', 'combined', Render(lambda ctx: S.Song(
        [instrument(ctx, '', layers=[layer(ctx, 'tone440.wav', pitch=-2.0)], pitch_offset=3.0)],
        [S.Pattern('P', notes(0, key='E0'))]), spec=PITCH),
        'Export note E0 on an instrument pitched +3 with a layer pitched -2')
    for mode in range(5):
        add(suite, 'pitch', f'interpolation-{mode}',
            Render(single('square110.wav', notes(0, key='G0')), options={'interpolation': mode},
                   spec={'excerpt': (2000, 400), 'window': 2048}),
            f'Export a 110 Hz square wave raised by 7 semitones with interpolation mode {mode}')
    for name in ('tone440-48k.wav', 'tone440-22k.wav', 'tone440-96k.wav'):
        add(suite, 'pitch', f'rate-{name[8:-4]}', Render(single(name, notes(0)), spec=PITCH),
            f'Export a 440 Hz sample recorded at another rate ({name})')
    add(suite, 'pitch', 'export-rate', Render(single('tone440.wav', notes(0, 48)), options={'rate': 48000},
                                             spec=PITCH),
        'Export a 44.1 kHz sample to a 48 kHz file')
    add(suite, 'pitch', 'export-rate-cubic', Render(single('square110.wav', notes(0)),
                                                    options={'rate': 32000, 'interpolation': 3},
                                                    spec={'excerpt': (3000, 300)}),
        'Export a square-wave sample to a 32 kHz file with cubic interpolation')


def envelope(suite):
    suite.setup('render-adsr', 'adsr', upload_samples, 'Upload the verifier sample library')
    for attack in (0, 4410, 44100):
        add(suite, 'adsr', f'attack-{attack}', Render(single('long440.wav', notes(0), attack=attack),
                                                      spec={'window': 2048, 'limit': 60}),
            f'Export a 3 s tone with an attack of {attack} frames')
    add(suite, 'adsr', 'decay-sustain', Render(single('long440.wav', notes(0), decay=22050, sustain=0.3),
                                               spec={'window': 2048, 'limit': 60}),
        'Export a 3 s tone with a decay of 22050 frames to a sustain level of 0.3')
    add(suite, 'adsr', 'sustain-zero', Render(single('long440.wav', notes(0), decay=11025, sustain=0.0),
                                              spec={'window': 2048, 'limit': 60}),
        'Export a 3 s tone that decays over 11025 frames to a sustain level of 0')
    for release in (256, 22050):
        add(suite, 'adsr', f'release-{release}', Render(single('long440.wav', notes(0, length=24), release=release),
                                                        spec={'window': 1024, 'limit': 80}),
            f'Export a 24-tick note of a 3 s tone with a release of {release} frames')
    add(suite, 'adsr', 'release-floor', Render(single('long440.wav', notes(0, length=24), release=10),
                                               spec={'window': 512, 'limit': 60}),
        'Export a 24-tick note whose stored release (10 frames) is shorter than the product minimum')
    add(suite, 'adsr', 'attack-cut', Render(single('long440.wav', notes(0, length=12), attack=44100, release=4410),
                                            spec={'window': 1024, 'limit': 60}),
        'Export a 12-tick note that ends during a one-second attack')
    add(suite, 'adsr', 'length-full', Render(single('long440.wav', notes(0, length=-1), release=4410),
                                             spec={'window': 4096}),
        'Export a note without a length: the whole 3 s sample plays')


def filters(suite):
    suite.setup('render-filter', 'filter', upload_samples, 'Upload the verifier sample library')
    for cutoff in (1.0, 0.6, 0.3, 0.1):
        add(suite, 'filter', f'cutoff-{cutoff:g}',
            Render(single('noise.wav', notes(0), filter_active=True, filter_cutoff=cutoff), spec={'bands': True}),
            f'Export white noise through the active instrument filter at cutoff {cutoff:g}')
    for resonance in (0.5, 0.95):
        add(suite, 'filter', f'resonance-{resonance:g}',
            Render(single('noise.wav', notes(0), filter_active=True, filter_cutoff=0.3, filter_resonance=resonance),
                   spec={'bands': True}),
            f'Export white noise through the filter at cutoff 0.3 and resonance {resonance:g}')
    add(suite, 'filter', 'inactive', Render(single('noise.wav', notes(0), filter_active=False, filter_cutoff=0.1),
                                           spec={'bands': True}),
        'Export white noise with a low cutoff stored but the filter switched off')
    add(suite, 'filter', 'ringing', Render(single('noise.wav', notes(0, length=12), filter_active=True,
                                                  filter_cutoff=0.2, filter_resonance=0.9, release=256),
                                           spec={'window': 512, 'limit': 80}),
        'Export a short noise note through a resonant filter (the filter may ring on after the note)')


def voices(suite):
    suite.setup('render-voices', 'voices', upload_samples, 'Upload the verifier sample library')
    add(suite, 'voices', 'stop-note', Render(single('long440.wav', notes(0, 96), stop_note=True),
                                            spec={'window': 2048, 'limit': 80}),
        'Export two notes of a 3 s tone on an instrument with Auto-Stop Note: the second note stops the first')
    add(suite, 'voices', 'overlap', Render(single('long440.wav', notes(0, 96), stop_note=False),
                                          spec={'window': 2048, 'limit': 80}),
        'Export two notes of a 3 s tone on an instrument without Auto-Stop Note: both keep sounding')
    for group, label in ((1, 'same'), (-1, 'none')):
        def build(ctx, group=group, other=(1 if group == 1 else 2)):
            return S.Song([instrument(ctx, 'long440.wav', 0, mute_group=group),
                           instrument(ctx, 'tone880.wav', 1, mute_group=other if group != -1 else -1)],
                          [S.Pattern('P', [S.Note(0, instrument=0), S.Note(96, instrument=1)])])
        add(suite, 'voices', f'mute-group-{label}', Render(build, spec={'window': 2048, 'limit': 80, 'pitch': (0.1, 1.0)}),
            'Export a long tone followed by a second instrument ' +
            ('in the same mute group' if group == 1 else 'outside any mute group'))
    add(suite, 'voices', 'note-off', Render(single('long440.wav', [S.Note(0), S.Note(48, note_off=True, velocity=0.0)],
                                                  release=2205), spec={'window': 2048, 'limit': 80}),
        'Export a long tone followed by a note-off event of the same instrument one beat later')
    add(suite, 'voices', 'probability', Render(single('click.wav', [S.Note(0, probability=1.0),
                                                                    S.Note(96, probability=0.0)]), spec=ONSETS),
        'Export two clicks, the second with a probability of 0')


def layers(suite):
    suite.setup('render-layers', 'layers', upload_samples, 'Upload the verifier sample library')

    def four(ctx, ranges=((0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.0)), selection='VELOCITY'):
        samples = ('layer220.wav', 'layer330.wav', 'layer550.wav', 'layer770.wav')
        return [layer(ctx, s, min=lo, max=hi) for s, (lo, hi) in zip(samples, ranges)], selection

    def build(velocities, **options):
        def song(ctx):
            layer_list, selection = four(ctx, **options)
            return S.Song([instrument(ctx, '', layers=layer_list, selection=selection)],
                          [S.Pattern('P', [S.Note(48 * i, velocity=v) for i, v in enumerate(velocities)])])
        return song

    for label, velocities in (('inside', (0.1, 0.3, 0.6, 0.9)), ('boundaries', (0.25, 0.5, 0.75, 1.0))):
        add(suite, 'layers', f'velocity-{label}', Render(build(velocities), spec={'window': 2048}),
            f'Export four notes with velocities {velocities} on an instrument with four velocity layers')
    add(suite, 'layers', 'gap', Render(build((0.1, 0.45, 0.6, 0.95), ranges=((0, 0.2), (0.5, 0.7), (0.7, 0.8),
                                                                             (0.9, 1.0))), spec={'window': 2048}),
        'Export notes whose velocities fall inside and outside the ranges of layers that leave gaps')
    add(suite, 'layers', 'overlap', Render(build((0.3, 0.6, 0.6, 0.3), ranges=((0, 0.7), (0.2, 1.0), (0.5, 1.0),
                                                                               (0.0, 0.1))), spec={'window': 2048}),
        'Export notes on layers whose velocity ranges overlap')
    add(suite, 'layers', 'round-robin', Render(build((0.8, 0.8, 0.8, 0.8), ranges=((0, 1), (0, 1), (0, 1), (0, 1)),
                                                     selection='ROUND_ROBIN'), spec={'window': 2048}),
        'Export four equal notes on an instrument whose layers alternate round-robin')


def components(suite):
    suite.setup('render-components', 'components', upload_samples, 'Upload the verifier sample library')

    def build(volumes, gains=(1.0, 1.0)):
        def song(ctx):
            inst = instrument(ctx, '', components=[S.Component([layer(ctx, 'tone440.wav')], id=0, gain=gains[0]),
                                                   S.Component([layer(ctx, 'tone660.wav')], id=1, gain=gains[1])])
            return S.Song([inst], [S.Pattern('P', notes(0))],
                          components=((0, 'Main', volumes[0]), (1, 'Room', volumes[1])))
        return song
    add(suite, 'components', 'two', Render(build((1.0, 1.0))), 'Export an instrument with two components')
    add(suite, 'components', 'volumes', Render(build((0.2, 1.4))),
        'Export two components with drumkit component volumes 0.2 and 1.4')
    add(suite, 'components', 'gains', Render(build((1.0, 1.0), (1.8, 0.25))),
        'Export two components with instrument component gains 1.8 and 0.25')

    def missing(ctx):
        inst = instrument(ctx, '', components=[S.Component([layer(ctx, 'tone440.wav')], id=0),
                                               S.Component([layer(ctx, 'tone660.wav')], id=5)])
        return S.Song([inst], [S.Pattern('P', notes(0))], components=((0, 'Main', 1.0),))
    add(suite, 'components', 'unknown-id', Render(missing),
        'Export an instrument whose second component refers to a component the song does not define')


def groove(suite):
    suite.setup('render-groove', 'groove', upload_samples, 'Upload the verifier sample library')
    for value in (-1.0, -0.4, 0.5, 1.0):
        add(suite, 'groove', f'leadlag-{value:g}', Render(single('click.wav', [S.Note(48, leadlag=value), S.Note(96)]),
                                                          spec=ONSETS),
            f'Export a click with lead/lag {value:g} on beat two and a plain click on beat three')
    for swing in (0.3, 0.8):
        add(suite, 'groove', f'swing-{swing:g}', Render(single('click.wav', notes(0, 12, 24, 36, 48, 60, 72, 84),
                                                               song={'swing': swing}), spec=ONSETS),
            f'Export sixteenth-note clicks with a swing factor of {swing:g}')
    add(suite, 'groove', 'swing-eighths', Render(single('click.wav', notes(0, 24, 48, 72), song={'swing': 0.6}),
                                                 spec=ONSETS),
        'Export eighth-note clicks with a swing factor of 0.6')


def structure(suite):
    suite.setup('render-song', 'song', upload_samples, 'Upload the verifier sample library')

    def two_columns(**song):
        def build(ctx):
            return S.Song([instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 96)), S.Pattern('B', notes(48))],
                          sequence=[['A'], ['B']], **song)
        return build
    add(suite, 'song', 'pattern-mode', Render(two_columns(mode='pattern'), spec=ONSETS),
        'Export a two-column song that is stored in pattern mode')
    add(suite, 'song', 'loop', Render(two_columns(loop=True), spec=ONSETS),
        'Export a two-column song with loop mode on')

    def virtual(ctx):
        return S.Song([instrument(ctx, 'click.wav'), instrument(ctx, 'tone880.wav', 1)],
                      [S.Pattern('A', notes(0)), S.Pattern('B', notes(96, instrument=1)), S.Pattern('V', [])],
                      sequence=[['V'], ['A']], virtual=(('V', ('A', 'B')),))
    add(suite, 'song', 'virtual-pattern', Render(virtual, spec=dict(ONSETS, window=2048)),
        'Export a song whose first column plays a virtual pattern made of two patterns')
    for active in (True, False):
        add(suite, 'song', f'tempo-marker-{"on" if active else "off"}',
            Render(lambda ctx, a=active: S.Song([instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 96))],
                                                sequence=[['A']] * 3, timeline=a, tempo_markers=((0, 120.0), (1, 60.0),
                                                                                                 (2, 240.0))),
                   spec=ONSETS),
            'Export three columns with tempo markers 120, 60 and 240 BPM while the timeline is ' +
            ('active' if active else 'inactive'))
    for points, label in ((((0.0, 1.0), (1.0, 0.2), (2.0, 0.2)), 'fade'), (((0.0, 0.3), (2.0, 1.0)), 'rise')):
        add(suite, 'song', f'velocity-automation-{label}',
            Render(lambda ctx, p=points: S.Song([instrument(ctx, 'dc.wav')], [S.Pattern('A', notes(0, 96))],
                                                sequence=[['A']] * 3, velocity_path=p), spec={'window': 4096}),
            'Export three columns with a velocity automation path (' + label + ')')
    for enabled in (True, False):
        add(suite, 'song', f'playback-track-{"on" if enabled else "off"}',
            Render(lambda ctx, e=enabled: S.Song([instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 96))],
                                                 playback_track=ctx.inputs('pad.wav'), playback_enabled=e,
                                                 playback_volume=0.6), spec={'window': 2048}),
            'Export a song with a playback track (pad.wav, volume 0.6) ' + ('enabled' if enabled else 'disabled'))

    def mixer(first=None, second=None, song_muted=False):
        def build(ctx):
            return S.Song([instrument(ctx, 'tone440.wav', 0, **(first or {})),
                           instrument(ctx, 'tone660.wav', 1, **(second or {}))],
                          [S.Pattern('A', [S.Note(0, instrument=0), S.Note(48, instrument=1)])], muted=song_muted)
        return build
    add(suite, 'song', 'instrument-muted', Render(mixer(first={'muted': True}), spec={'window': 2048}),
        'Export a song in which the first of two instruments is muted')
    add(suite, 'song', 'instrument-soloed', Render(mixer(second={'soloed': True}), spec={'window': 2048}),
        'Export a song in which the second of two instruments is soloed')
    add(suite, 'song', 'song-muted', Render(mixer(song_muted=True), spec={'window': 2048}),
        'Export a song whose master output is muted', requires=silent('song', 'instrument-muted'))


def modified(suite):
    suite.setup('render-sample', 'sample', upload_samples, 'Upload the verifier sample library')

    def edited(**options):
        def build(ctx):
            values = dict(options)
            sample = values.pop('sample', 'ramp.wav')
            values.setdefault('modified', True)
            return S.Song([instrument(ctx, '', layers=[layer(ctx, sample, **values)])], [S.Pattern('P', notes(0))])
        return build
    frames = 22050
    add(suite, 'sample', 'start-end', Render(edited(startframe=5000, loopframe=5000, endframe=15000),
                                             spec={'window': 512, 'limit': 60, 'excerpt': (0, 64)}),
        'Export a ramp sample edited to play frames 5000 to 15000 only')
    add(suite, 'sample', 'loop-forward', Render(edited(startframe=0, loopframe=11025, endframe=frames, loops=2),
                                                spec={'window': 1024, 'limit': 80}),
        'Export a ramp sample looping its second half twice forward')
    add(suite, 'sample', 'loop-reverse', Render(edited(smode='reverse', startframe=0, loopframe=0, endframe=frames,
                                                       loops=0), spec={'window': 1024, 'limit': 40,
                                                                       'excerpt': (100, 64)}),
        'Export a ramp sample played in reverse')
    add(suite, 'sample', 'loop-pingpong', Render(edited(smode='pingpong', startframe=0, loopframe=11025,
                                                        endframe=frames, loops=1), spec={'window': 1024, 'limit': 80}),
        'Export a ramp sample whose second half loops back and forth once')
    add(suite, 'sample', 'volume-envelope', Render(edited(sample='dc.wav', startframe=0, endframe=frames,
                                                          volume_envelope=((0, 100), (420, 0), (841, 100))),
                                                   spec={'window': 512, 'limit': 50}),
        'Export a constant sample with a volume envelope that dips to zero in the middle')
    add(suite, 'sample', 'pan-envelope', Render(edited(sample='dc.wav', startframe=0, endframe=frames,
                                                       pan_envelope=((0, 0), (841, 100))),
                                                spec={'window': 512, 'limit': 50}),
        'Export a constant sample with a pan envelope from left to right')
    add(suite, 'sample', 'not-modified', Render(edited(modified=False, startframe=5000, endframe=10000),
                                                spec={'window': 512, 'limit': 50}),
        'Export a layer that stores loop frames but is not marked as modified')


def inputs(suite):
    suite.setup('render-input', 'input', upload_samples, 'Upload the verifier sample library')
    for name in ('tone440.flac', 'tone440.ogg', 'tone440.aiff', 'tone440.au', 'tone440.caf', 'tone440.w64',
                 'tone440.mp3', 'tone440-8bit.wav', 'tone440-24bit.wav', 'tone440-32bit.wav', 'tone440-float.wav'):
        add(suite, 'input', 'sample-' + name.replace('.', '-'), Render(single(name, notes(0)), spec=PITCH,
                                                                       tolerance={'frames': 2048}
                                                                       if name.endswith(('.ogg', '.mp3')) else None),
            f'Export a song whose instrument plays the sample document {name}')
    add(suite, 'input', 'relative-sample', Render(lambda ctx: S.Song(
        [S.Instrument(0, 'Relative', [S.Component([S.Layer('./tone440.wav')])])], [S.Pattern('P', notes(0))]),
        spec=PITCH), 'Export a song that names its sample relative to the song file (./tone440.wav)')
    add(suite, 'input', 'missing-sample', Render(lambda ctx: S.Song(
        [instrument(ctx, '', layers=[layer(ctx, 'no-such-sample.wav')]), instrument(ctx, 'click.wav', 1)],
        [S.Pattern('P', [S.Note(0), S.Note(96, instrument=1)])]), spec=ONSETS),
        'Export a song whose first instrument names a sample that does not exist')


def build(suite):
    timing(suite)
    gain(suite)
    pan(suite)
    pitch(suite)
    envelope(suite)
    filters(suite)
    voices(suite)
    layers(suite)
    components(suite)
    groove(suite)
    structure(suite)
    modified(suite)
    inputs(suite)
