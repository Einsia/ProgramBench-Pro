'''Sound chip coverage of the product command line on generated projects.

Every point renders one generated project with one instrument track (sfxr, the NES chip or the Game Boy chip) through
cli render and decodes the written file with the verifier FFmpeg. The exit status never decides; the written file
does. The settings of a point are written into the instrument element the way the product saves them and what is not
given is the product default. The sfxr noise wave is left out (its random source is not reproducible between runs of
the reference). A point returns its signal class and the signal projection of the render (format, length, level per
channel, level per window and spectrum), so every knob, switch and channel routing changes the observation.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
# sfxr knobs as (attribute, name, values); the bipolar knobs are set above zero here and below zero in COMBINATIONS.
SFXR_KNOBS = (
    ('att', 'attack time', (0.2, 0.5)),
    ('hold', 'sustain time', (0.1, 0.6)),
    ('sus', 'sustain punch', (0.3, 0.8)),
    ('dec', 'decay time', (0.1, 0.8)),
    ('startFreq', 'start frequency', (0.15, 0.5, 0.8)),
    ('slide', 'slide', (0.3, 0.7)),
    ('dSlide', 'delta slide', (0.3, 0.7)),
    ('sqrDuty', 'square duty', (0.3, 0.7)),
    ('phaserOffset', 'phaser offset', (0.3, 0.7)),
    ('lpFilCut', 'low-pass cutoff', (0.2, 0.5)),
    ('hpFilCut', 'high-pass cutoff', (0.2, 0.5)),
)
COMBINATIONS = (
    ('slide-down', 'Slide the sfxr pitch down', {'slide': -0.3}),
    ('minimum-frequency-0-2', 'Stop a sliding sfxr pitch at a minimum frequency of 0.2', {'slide': -0.3, 'minFreq': 0.2}),
    ('minimum-frequency-0-28', 'Stop a sliding sfxr pitch at a minimum frequency of 0.28',
     {'slide': -0.3, 'minFreq': 0.28}),
    ('delta-slide-down', 'Accelerate a downward sfxr slide', {'slide': -0.1, 'dSlide': -0.3}),
    ('vibrato-slow', 'Add a slow vibrato to the sfxr pitch', {'vibDepth': 0.5, 'vibSpeed': 0.3}),
    ('vibrato-fast', 'Add a fast vibrato to the sfxr pitch', {'vibDepth': 0.5, 'vibSpeed': 0.8}),
    ('repeat-slide-0-5', 'Restart a sliding sfxr pitch at a repeat speed of 0.5', {'slide': -0.3, 'repeatSpeed': 0.5}),
    ('repeat-slide-0-8', 'Restart a sliding sfxr pitch at a repeat speed of 0.8', {'slide': -0.3, 'repeatSpeed': 0.8}),
    ('vibrato-deep', 'Add a deep vibrato to the sfxr pitch', {'vibDepth': 0.9, 'vibSpeed': 0.5}),
    ('duty-sweep', 'Sweep the sfxr square duty', {'sqrDuty': 0.3, 'sqrSweep': 0.5}),
    ('phaser-sweep', 'Sweep the sfxr phaser', {'phaserOffset': 0.5, 'phaserSweep': 0.4}),
    ('lowpass-sweep', 'Sweep the sfxr low-pass cutoff down', {'lpFilCut': 0.5, 'lpFilCutSweep': -0.3}),
    ('lowpass-resonance', 'Add resonance to the sfxr low-pass filter', {'lpFilCut': 0.5, 'lpFilReso': 0.5}),
    ('highpass-sweep', 'Sweep the sfxr high-pass cutoff up', {'hpFilCut': 0.2, 'hpFilCutSweep': 0.3}),
)


def label(value):
    return ('minus-' if value < 0 else '') + str(abs(value)).replace('.', '-')


def point(suite, scenario, description, plugin, params, notes=SEQUENCE):
    def action(ctx):
        project = px.Project(bpm=BPM)
        project.add(px.instrument_track(plugin, plugin, params=params, notes=notes))
        rendered = ctx.render(project.xml(), 'chip-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('instrument', scenario, 'render', action, description=description)


def solo(channel):
    return {f'on{number}': int(number == channel) for number in (1, 2, 3, 4)}


def sfxr_points(suite):
    for key, name, values in SFXR_KNOBS:
        for value in values:
            point(suite, f'sfxr-{key.lower()}-{label(value)}', f'Set the sfxr {name} to {value}', 'sfxr', {key: value})
    for tag, description, params in COMBINATIONS:
        point(suite, 'sfxr-' + tag, description, 'sfxr', params)
    for index, name in ((1, 'saw'), (2, 'sine')):
        point(suite, 'sfxr-wave-' + name, f'Play the sfxr {name} wave', 'sfxr', {'waveForm': index})


def nes_points(suite):
    def add(scenario, description, **params):
        point(suite, 'nes-' + scenario, description, 'nes', params)

    for volume in (0.5, 1.5):
        add(f'master-volume-{label(volume)}', f'Set the NES master volume to {volume}', vol=volume)
    for channel in (1, 2, 3, 4):
        add(f'channel-{channel}-only', f'Play only NES channel {channel}', **solo(channel))
    # Channel 1 defaults to duty 0 and channel 2 to duty 2, which are the two solo points above.
    for duty in (1, 3):
        add(f'channel-1-duty-{duty}', f'Play NES channel 1 with duty cycle {duty}', **solo(1), dc1=duty)
    for channel in (1, 2, 3):
        for coarse in (-12, 12):
            add(f'channel-{channel}-coarse-{label(coarse)}', f'Detune NES channel {channel} by {coarse} semitones',
                **solo(channel), **{f'crs{channel}': coarse})
        for volume in (4, 9):
            add(f'channel-{channel}-volume-{volume}', f'Set the volume of NES channel {channel} to {volume}',
                **solo(channel), **{f'vol{channel}': volume})
    for channel in (1, 2, 4):
        for length in (4, 10):
            add(f'channel-{channel}-envelope-{length}',
                f'Decay NES channel {channel} with an envelope of length {length}', **solo(channel),
                **{f'envon{channel}': 1, f'envlen{channel}': length})
        add(f'channel-{channel}-envelope-looped', f'Loop the envelope of length 4 of NES channel {channel}',
            **solo(channel), **{f'envon{channel}': 1, f'envlen{channel}': 4, f'envloop{channel}': 1})
    for channel in (1, 2):
        for amount, rate in ((3, 3), (-3, 3), (3, 6)):
            add(f'channel-{channel}-sweep-{label(amount)}-rate-{rate}',
                f'Sweep the pitch of NES channel {channel} by {amount} at rate {rate}', **solo(channel),
                **{f'sweep{channel}': 1, f'swamt{channel}': amount, f'swrate{channel}': rate})
    for frequency in (4, 10, 14):
        add(f'noise-frequency-{frequency}', f'Play the NES noise channel at frequency {frequency}', **solo(4),
            nfreq4=frequency)
    for key, value, name in (('nmode4', 1, 'the short noise mode'), ('nfrqmode4', 1, 'the noise frequency mode'),
                             ('nq4', 0, 'no noise frequency quantization'), ('nswp4', 3, 'a noise sweep up'),
                             ('nswp4', -3, 'a noise sweep down')):
        add(f'noise-{key}-{label(value)}', f'Play the NES noise channel with {name}', **solo(4), nfreq4=8,
            **{key: value})
    for amount in (5, 12):
        add(f'vibrato-{amount}', f'Add a NES vibrato of {amount}', vibr=amount)
    add('all-channels', 'Play all four NES channels together', on4=1)


GAMEBOY = {'sampleShape': px.GAMEBOY_WAVE}
RAMP = px.floats([i // 2 for i in range(32)])
SQUARE = px.floats([15 if i < 16 else 0 for i in range(32)])
PULSE = px.floats([15 if i < 6 else 0 for i in range(32)])
# One channel at a time: the sweep of channel 1 is off and every volume is zero (channel 3: muted).
QUIET = {'st': 0, 'ch1vol': 0, 'ch2vol': 0, 'ch3vol': 0, 'ch4vol': 0}
ROUTE_NOISE = {'ch4so1': 1, 'ch4so2': 1}
# Channels 1 and 2 are the same square generator, so channel 2 is played at other volumes than channel 1.
LEVELS = {1: 15, 2: 11, 3: 3, 4: 15}
VOLUMES = {1: (4, 9), 2: (6, 13)}
START = {1: 8, 2: 10}


def only(channel, **params):
    values = {**QUIET, f'ch{channel}vol': LEVELS[channel]}
    values.update(params)
    return values


def papu_points(suite):
    def add(scenario, description, **params):
        point(suite, 'papu-' + scenario, description, 'papu', {**GAMEBOY, **params})

    add('default', 'Play four notes on a Game Boy track with its default settings and a triangle wave pattern')
    for channel in (1, 2):
        add(f'channel-{channel}-solo', f'Play only Game Boy channel {channel}', **only(channel))
        for duty in (0, 1, 3):
            add(f'channel-{channel}-duty-{duty}', f'Play only Game Boy channel {channel} with duty {duty}',
                **only(channel, **{f'ch{channel}wpd': duty}))
        for volume in VOLUMES[channel]:
            add(f'channel-{channel}-volume-{volume}', f'Play only Game Boy channel {channel} at volume {volume}',
                **only(channel, **{f'ch{channel}vol': volume}))
        for step, rising in ((3, 0), (3, 1), (7, 1), (1, 0)):
            way = 'rise' if rising else 'fall'
            add(f'channel-{channel}-envelope-{way}-{step}',
                f'Let Game Boy channel {channel} start at volume {START[channel]} and {way} with a step length of {step}',
                **only(channel, **{f'ch{channel}vol': START[channel], f'ch{channel}ssl': step, f'ch{channel}vsd': rising}))
    add('channel-3-solo', 'Play only Game Boy channel 3 with a triangle wave pattern', **only(3))
    for volume in (1, 2):
        add(f'channel-3-volume-{volume}', f'Play only Game Boy channel 3 at volume setting {volume}',
            **only(3, ch3vol=volume))
    for name, wave in (('ramp', RAMP), ('square', SQUARE), ('pulse', PULSE)):
        add(f'channel-3-wave-{name}', f'Play only Game Boy channel 3 with a {name} wave pattern', **only(3),
            sampleShape=wave)
    for time, falling, shift in ((2, 1, 4), (4, 1, 2), (7, 1, 1), (3, 0, 6), (1, 0, 7), (5, 0, 5)):
        way = 'down' if falling else 'up'
        add(f'sweep-time-{time}-{way}-shift-{shift}',
            f'Sweep the pitch of Game Boy channel 1 {way} with time {time} and shift {shift}',
            **only(1, st=time, sd=falling, srs=shift))
    add('noise-solo', 'Play only the Game Boy noise channel', **only(4, **ROUTE_NOISE))
    add('noise-volume-8', 'Play only the Game Boy noise channel at volume 8', **only(4, ch4vol=8, **ROUTE_NOISE))
    add('noise-narrow', 'Play only the Game Boy noise channel with the narrow shift register',
        **only(4, srw=1, **ROUTE_NOISE))
    add('noise-envelope-fall', 'Let the Game Boy noise channel fall in volume with a step length of 3',
        **only(4, ch4ssl=3, **ROUTE_NOISE))
    add('noise-envelope-rise', 'Let the Game Boy noise channel rise from volume 6 with a step length of 3',
        **only(4, ch4vol=6, ch4ssl=3, ch4vsd=1, **ROUTE_NOISE))
    for level in (1, 3, 5):
        add(f'output-level-{level}', f'Set both Game Boy output levels to {level} on channel 2',
            **only(2, so1vol=level, so2vol=level))
    for channel in (1, 2, 3):
        for key in ('so1', 'so2'):
            add(f'channel-{channel}-{key}-setting-off',
                f'Play only Game Boy channel {channel} with its {key} routing setting off',
                **only(channel, **{f'ch{channel}{key}': 0}))
    for value in (-80, 100):
        add(f'treble-{label(value)}', f'Set the Game Boy treble to {value}', Treble=value)
    for value in (100, 300):
        add(f'bass-{value}', f'Set the Game Boy bass to {value}', Bass=value)


def build(suite):
    sfxr_points(suite)
    nes_points(suite)
    papu_points(suite)
