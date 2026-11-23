'''Instrument coverage of the product command line on generated projects.

Every point renders one generated project with one to three instrument tracks through cli render and decodes the
written file with the verifier FFmpeg. The exit status never decides; the written file does. Instruments and settings
whose output is not reproducible between runs of the reference (white noise wave, sid, organic, chord creator,
arpeggiator) are left out. A point returns its signal class and the signal projection of the render (format, length,
level per channel, level per window and spectrum), so key, length, volume, panning, pitch, waveform and modulation
each change the observation.
'''
from __future__ import annotations

import base64
import math
import struct

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
HELD = [(0, 96, 57), (0, 96, 61), (0, 96, 64)]
OVERLAP = [(i * 36, 96, 52 + 3 * i) for i in range(5)]
INSTRUMENTS = ('tripleoscillator', 'kicker', 'lb302', 'sfxr', 'papu')
# The Game Boy instrument reads its wave pattern without checking that the project has one, so its points write it.
DEFAULTS = {'papu': {'sampleShape': px.GAMEBOY_WAVE}}

def _wave(length=220):
    raw = b''.join(struct.pack('<f', math.sin(2 * math.pi * i / length)) for i in range(length))
    return base64.b64encode(raw).decode('ascii')


WATSYN_WAVE = base64.b64encode(b''.join(struct.pack('<f', 1.0 if i < 110 else -1.0) for i in range(220))).decode('ascii')
EXTRA_INSTRUMENTS = {
    'bitinvader': ({'sampleLength': 64, 'sampleShape': _wave(64)},),
    'vibedstrings': ({'active0': 1},),
    'watsyn': ({'a1_wave': WATSYN_WAVE, 'a2_wave': WATSYN_WAVE, 'b1_wave': WATSYN_WAVE, 'b2_wave': WATSYN_WAVE},),
}
KEYS = (('tripleoscillator', (36, 48, 60, 72, 84)), ('lb302', (36, 60, 84)))
WAVES = ('sine', 'triangle', 'saw', 'square', 'moog-saw', 'exponential')
KICKER = (('start-300', {'startfreq': 300}), ('end-80', {'endfreq': 80}), ('decay-150', {'decay': 150}),
          ('decay-900', {'decay': 900}), ('gain-half', {'gain': 0.5}), ('no-distortion', {'dist': 0, 'distend': 0}))


def signed(value):
    return ('minus-' if value < 0 else '') + str(abs(value))


def single(key, length=96, volume=100, pan=0):
    return [(0, length, key, volume, pan)]


def track(plugin='tripleoscillator', params=None, notes=SEQUENCE, **options):
    def build(ctx):
        return px.instrument_track(plugin, plugin, params=params, notes=notes, **options)
    return build


def point(suite, scenario, description, *tracks, requires=(), **settings):
    def action(ctx):
        project = px.Project(**{'bpm': BPM, **settings})
        for build in tracks:
            project.add(build(ctx))
        rendered = ctx.render(project.xml(), 'instrument-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('instrument', scenario, 'render', action, description=description, requires=requires)


def player(sample, notes=None, **params):
    # An audio file processor track that plays a verifier sample; its src is the absolute document path.
    def build(ctx):
        values = {'src': ctx.sample(sample)[0], **params}
        return px.instrument_track('Player', 'audiofileprocessor', params=values, notes=notes or single(57, 96))
    return build


def build(suite):
    for plugin in INSTRUMENTS:
        point(suite, 'default-' + plugin, f'Play four notes on a {plugin} track', track(plugin, DEFAULTS.get(plugin)))
    descriptions = {'bitinvader': 'a 64-sample sine wavetable', 'vibedstrings': 'its first string powered on',
                    'watsyn': 'four embedded square wavetables'}
    for plugin, variants in EXTRA_INSTRUMENTS.items():
        for index, params in enumerate(variants, 1):
            point(suite, f'{plugin}-behavior-{index}', f'Play four notes on {plugin} with {descriptions[plugin]}',
                  track(plugin, params))
    for plugin, keys in KEYS:
        for key in keys:
            point(suite, f'key-{plugin}-{key}', f'Play note {key} on a {plugin} track', track(plugin, notes=single(key)))
    for length in (12, 24, 96, 192):
        point(suite, f'note-length-{length}', f'Play one note of {length} ticks on a TripleOscillator track',
              track(notes=single(57, length)))
    for volume in (25, 50, 75):
        point(suite, f'note-volume-{volume}', f'Play a note at volume {volume}', track(notes=single(57, 96, volume)))
    for pan in (-100, -50, 50, 100):
        point(suite, f'note-pan-{signed(pan)}', f'Play a note panned to {pan}', track(notes=single(57, 96, 100, pan)))
    for vol in (0, 25, 50, 150, 200):
        point(suite, f'track-volume-{vol}', f'Set the volume of the instrument track to {vol}', track(vol=vol))
    for pan in (-100, -50, 50, 100):
        point(suite, f'track-pan-{signed(pan)}', f'Set the panning of the instrument track to {pan}', track(pan=pan))
    for pitch in (-100, -50, 50, 100):
        point(suite, f'track-pitch-{signed(pitch)}', f'Set the pitch of the instrument track to {pitch} cents',
              track(pitch=pitch))
    for base in (50, 64):
        point(suite, f'base-note-{base}', f'Set the base note of the instrument track to {base}', track(basenote=base))
    for index, wave in list(enumerate(WAVES))[1:]:
        point(suite, f'wave-{wave}', f'Play the {wave} wave on all three oscillators',
              track(params={'wavetype0': index, 'wavetype1': index, 'wavetype2': index}))
    for algo in range(5):
        point(suite, f'modulation-{algo}', f'Combine the oscillators with modulation algorithm {algo}',
              track(params={'wavetype0': 2, 'wavetype1': 3, 'wavetype2': 2, 'modalgo1': algo, 'modalgo2': algo}))
    tuned = {'wavetype0': 0, 'wavetype1': 2, 'wavetype2': 3, 'coarse0': 0, 'coarse1': -12, 'coarse2': 12}
    for label, volumes in (('first-only', (100, 0, 0)), ('second-only', (0, 100, 0)), ('third-only', (0, 0, 100)),
                           ('all-low', (30, 30, 30))):
        point(suite, 'oscillators-' + label, f'Mix the three tuned oscillators: {label}',
              track(params={**tuned, 'vol0': volumes[0], 'vol1': volumes[1], 'vol2': volumes[2]}))
    for coarse in (-12, 12):
        point(suite, f'coarse-{signed(coarse)}', f'Tune the first oscillator by {coarse} semitones',
              track(params={'coarse0': coarse}))
    point(suite, 'held-notes-tripleoscillator', 'Play three notes at the same time on a TripleOscillator track',
          track(notes=HELD))
    point(suite, 'overlap-tripleoscillator', 'Play five overlapping notes on a TripleOscillator track',
          track(notes=OVERLAP))
    point(suite, 'overlap-lb302', 'Play five overlapping notes on a monophonic lb302 track', track('lb302', notes=OVERLAP))
    for label, params in KICKER:
        point(suite, 'kicker-' + label, f'Play the kicker with the setting {label}', track('kicker', params))
    point(suite, 'two-tracks', 'Mix a TripleOscillator track and a kicker track', track('tripleoscillator'), track('kicker'))
    point(suite, 'three-tracks', 'Mix three instrument tracks', track('tripleoscillator'), track('kicker'), track('lb302'))
    point(suite, 'mute-first-track', 'Mute one of two instrument tracks', track('tripleoscillator', muted=True), track('kicker'),
          requires=('backend.instrument.default-kicker.render',))
    for sample in ('ramp', 'impulse'):
        point(suite, f'player-{sample}', f'Play the {sample} sample with the audio file processor', player(sample))
        point(suite, f'player-reversed-{sample}', f'Play the {sample} sample reversed', player(sample, notes=single(57, 192), reversed=1))
    for amp in (50, 200):
        point(suite, f'player-amplification-{amp}', f'Set the amplification of the sample player to {amp}', player('tone-440', amp=amp))
    for start, end in ((25, 100), (0, 50), (25, 75)):
        point(suite, f'player-window-{start}-{end}', f'Play the ramp sample from {start} to {end} percent', player('ramp', sframe=start / 100, eframe=end / 100))
    for note in (50, 64, 69, 76):
        point(suite, f'player-key-{note}', f'Play the square sample at note {note}', player('square-220', notes=single(note, 96)))
    for mode in (0,):
        point(suite, f'player-interpolation-{mode}', f'Resample the square sample by seven semitones with interpolation mode {mode}', player('square-220', notes=single(64, 96), interp=mode))
    point(suite, 'player-looped', 'Hold a long note on the ramp sample with the loop on', player('ramp', notes=single(57, 192), looped=1, lframe=0.5))
    # Both samples hold the same 330 Hz tone, so the 22050 Hz one is played at note 64 to differ from the 48000 Hz one.
    point(suite, 'player-rate-48000', 'Play the rate-48000 sample with the audio file processor', player('rate-48000'))
    point(suite, 'player-rate-22050', 'Play the rate-22050 sample at note 64 with the audio file processor',
          player('rate-22050', notes=single(64, 96)))
    for pitch in (-12, 12):
        point(suite, f'master-pitch-{signed(pitch)}', f'Set the master pitch to {pitch} semitones', track(), masterpitch=pitch)
