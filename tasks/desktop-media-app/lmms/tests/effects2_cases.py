'''Bitcrusher, flanger, reverb and crossover equalizer coverage of the product command line on generated projects.

Every point renders one generated project whose saw synth track (or, for the stereo points, a stereo sample) carries
one of the four effects through cli render and decodes the written file with the verifier FFmpeg. The exit status
never decides; the written file does. The input noise of the bitcrusher and the noise of the flanger are left out.
Each effect is written into the project the way the product saves it and what is not given is the product default.
A point returns its signal class and the signal projection of the render (format, length, level per channel, level
per window and spectrum), so the rate, depth, delay, feedback, size, colour, crossover and band gain settings each
change the observation.
'''
from __future__ import annotations

import effect_cases as base

CRUSH = {'ingain': 0, 'innoise': 0, 'outgain': 0, 'outclip': 0, 'rate': 44100, 'stereodiff': 0, 'levels': 256,
         'rateon': 1, 'depthon': 1}
FLANGE = {'DelayTimeSamples': 0.001, 'LfoFrequency': 0.25, 'LfoAmount': 0, 'Feedback': 0, 'WhiteNoise': 0, 'Invert': 0}
REVERB = {'input_gain': 0, 'size': 0.89, 'color': 10000, 'output_gain': 0}
SPLIT = {'xover12': 125, 'xover23': 1250, 'xover34': 5000, 'gain1': 0, 'gain2': 0, 'gain3': 0, 'gain4': 0,
         'mute1': 1, 'mute2': 1, 'mute3': 1, 'mute4': 1}
BANDS = (1, 2, 3, 4)


def label(value):
    return str(value).replace('.', '-')


def crush(wet=1.0, on=True, **params):
    return base.fx('bitcrush', 'bitcrushcontrols', {**CRUSH, **params}, wet=wet, on=on)


def flange(wet=0.5, on=True, **params):
    return base.fx('flanger', 'Flanger', {**FLANGE, **params}, wet=wet, on=on)


def reverb(wet=0.5, on=True, **params):
    return base.fx('reverbsc', 'ReverbSCControls', {**REVERB, **params}, wet=wet, on=on)


def split(wet=1.0, on=True, **params):
    return base.fx('crossovereq', 'crossoevereqcontrols', {**SPLIT, **params}, wet=wet, on=on)


def adder(suite, prefix, make):
    def add(scenario, description, source='synth', requires=(), **settings):
        base.point(suite, f'{prefix}-{scenario}', description, source, make(**settings), requires=requires)
    return add


def bitcrush_points(suite):
    add = adder(suite, 'bitcrush', crush)
    # A rate of 16000 Hz renders like 16 levels within the observation tolerances, so the rates start lower.
    for rate in (1000, 2000, 4000, 8000):
        add(f'rate-{rate}', f'Reduce the sample rate of a saw synth to {rate} Hz with the bitcrusher', rate=rate,
            depthon=0)
    for levels in (2, 3, 4, 16):
        add(f'levels-{levels}', f'Reduce a saw synth to {levels} amplitude levels with the bitcrusher', levels=levels,
            rateon=0)
    add('rate-8000-levels-8', 'Reduce a saw synth to a rate of 8000 Hz and 8 amplitude levels', rate=8000, levels=8)
    for gain in (-6, 6):
        add(f'input-gain-{base.signed(gain)}', f'Set the bitcrusher input gain to {gain} dB at 16 levels', ingain=gain,
            levels=16, rateon=0)
    for gain in (-12, -6):
        add(f'output-gain-{base.signed(gain)}', f'Set the bitcrusher output gain to {gain} dB at a rate of 16000 Hz',
            outgain=gain, rate=16000, depthon=0)
    for clip in (-9, -6, -3):
        add(f'output-clip-{base.signed(clip)}', f'Clip the bitcrusher output at {clip} dB', outclip=clip, rateon=0)
    add('stereo-rate-8000', 'Reduce a stereo sample to a rate of 8000 Hz', 'stereo', rate=8000, depthon=0)
    for diff in (30, 50):
        add(f'stereo-difference-{diff}', f'Reduce a stereo sample to 8000 Hz with a stereo difference of {diff}',
            'stereo', rate=8000, depthon=0, stereodiff=diff)
    add('half-wet', 'Mix half of the rate-reduced signal with the dry signal', rate=8000, depthon=0, wet=0.5)
    add('disabled', 'A switched-off bitcrusher leaves the signal untouched', rate=8000, depthon=0, on=False,
        requires=('backend.effect.bitcrush-rate-8000.render',))


def flanger_points(suite):
    add = adder(suite, 'flanger', flange)
    for delay in (0.0005, 0.002, 0.005, 0.01, 0.03):
        add(f'delay-{label(delay)}', f'Mix a saw synth with a copy delayed by {delay} s in the flanger',
            DelayTimeSamples=delay)
    for feedback in (0.5, 0.9):
        add(f'feedback-{label(feedback)}', f'Feed the flanger back with an amount of {feedback}',
            DelayTimeSamples=0.003, Feedback=feedback)
        # The invert switch swaps the channels that feed the two delay lines; a centred synth has equal channels, so
        # only a stereo sample with a modulated delay shows it (the LFO gives the two lines other lengths).
        add(f'stereo-feedback-{label(feedback)}', f'Feed the flanger back with an amount of {feedback} on a stereo sample',
            'stereo', DelayTimeSamples=0.003, Feedback=feedback, LfoFrequency=0.5, LfoAmount=0.002)
        add(f'stereo-swapped-feedback-{label(feedback)}',
            f'Feed the flanger back with an amount of {feedback} and the channels swapped, on a stereo sample',
            'stereo', DelayTimeSamples=0.003, Feedback=feedback, Invert=1, LfoFrequency=0.5, LfoAmount=0.002)
    for amount in (0.001, 0.0025):
        add(f'lfo-amount-{label(amount)}', f'Modulate the flanger delay with an LFO amount of {amount} s',
            DelayTimeSamples=0.003, LfoFrequency=0.5, LfoAmount=amount)
    for speed in (0.1, 1, 5):
        add(f'lfo-frequency-{label(speed)}', f'Modulate the flanger delay with an LFO frequency setting of {speed}',
            DelayTimeSamples=0.003, LfoFrequency=speed, LfoAmount=0.002)
    add('wet-full', 'Play only the delayed signal of the flanger', DelayTimeSamples=0.002, wet=1.0)
    add('wet-quarter', 'Mix a quarter of the delayed signal with the dry signal', DelayTimeSamples=0.002, wet=0.25)


def reverb_points(suite):
    add = adder(suite, 'reverb', reverb)
    for size in (0.3, 0.6, 0.89, 0.97):
        add(f'size-{label(size)}', f'Reverberate a saw synth with a room size of {size}', size=size)
    for color in (500, 2000, 6000, 14000):
        add(f'color-{color}', f'Reverberate a saw synth with a colour of {color} Hz', color=color)
    for gain in (-12, 6):
        add(f'input-gain-{base.signed(gain)}', f'Set the reverb input gain to {gain} dB', input_gain=gain)
    # The reverb is linear, so equal input and output gains render alike: the output gains differ from the input gains.
    for gain in (-9, 3):
        add(f'output-gain-{base.signed(gain)}', f'Set the reverb output gain to {gain} dB', output_gain=gain)
    add('wet-full', 'Play only the reverberated signal', wet=1.0)


def crossover_points(suite):
    add = adder(suite, 'crossover', split)
    for band in BANDS:
        for gain in (-12, 12):
            add(f'band-{band}-gain-{base.signed(gain)}',
                f'Set the gain of band {band} of the crossover equalizer to {gain} dB', **{f'gain{band}': gain})
    for band in BANDS:
        add(f'band-{band}-only', f'Play only band {band} of the crossover equalizer',
            **{f'mute{other}': int(other == band) for other in BANDS})
    for band in BANDS:
        add(f'band-{band}-off', f'Switch band {band} of the crossover equalizer off', **{f'mute{band}': 0})
    add('low-crossover-400', 'Raise the first crossover to 400 Hz and cut band 1 by 18 dB', xover12=400, gain1=-18)
    add('middle-crossover-600', 'Lower the second crossover to 600 Hz and cut band 2 by 12 dB', xover23=600, gain2=-12)
    add('high-crossover-2000', 'Lower the third crossover to 2000 Hz and cut band 3 by 12 dB', xover34=2000, gain3=-12)
    add('narrow-middle-band', 'Squeeze band 2 between crossovers at 400 and 800 Hz and cut it by 18 dB', xover12=400,
        xover23=800, gain2=-18)


def build(suite):
    bitcrush_points(suite)
    flanger_points(suite)
    reverb_points(suite)
    crossover_points(suite)
