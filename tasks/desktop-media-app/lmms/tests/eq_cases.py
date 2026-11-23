'''Equalizer coverage of the product command line on generated projects.

Every point renders one generated project whose saw synth track carries the equalizer through cli render and decodes
the written file with the verifier FFmpeg. The exit status never decides; the written file does. The equalizer has a
low shelf, four peak bands, a high shelf and a high-pass and a low-pass filter of 12, 24 or 48 dB per octave. Every
band has an active switch, a frequency and a gain (shelves and filters a resonance, peak bands a bandwidth) and the
whole has an input and an output gain in dB; the analyser is switched off. A point returns its signal class and the
signal projection of the render (format, length, level per channel, level per window and spectrum), so each band
setting changes the spectrum or the level.
'''
from __future__ import annotations

import effect_cases as base

DEFAULT = {'Inputgain': 0, 'Outputgain': 0, 'Lowshelfgain': 0, 'HighShelfgain': 0, 'HPres': 0.707, 'LPres': 0.707,
           'LowShelfres': 1.4, 'HighShelfres': 1.4, 'HPfreq': 31, 'LPfreq': 18000, 'LowShelffreq': 80,
           'Highshelffreq': 12000, 'HPactive': 0, 'LPactive': 0, 'Lowshelfactive': 0, 'Highshelfactive': 0,
           'LP12': 0, 'LP24': 0, 'LP48': 0, 'HP12': 0, 'HP24': 0, 'HP48': 0, 'LP': 0, 'HP': 0, 'AnalyseIn': 0,
           'AnalyseOut': 0}
for number, frequency in enumerate((120, 250, 2000, 4000), 1):
    DEFAULT.update({f'Peak{number}gain': 0, f'Peak{number}bw': 0.3, f'Peak{number}freq': frequency,
                    f'Peak{number}active': 0})
LOW = {'active': 'Lowshelfactive', 'gain': 'Lowshelfgain', 'freq': 'LowShelffreq', 'res': 'LowShelfres'}
HIGH = {'active': 'Highshelfactive', 'gain': 'HighShelfgain', 'freq': 'Highshelffreq', 'res': 'HighShelfres'}
# Slope switches (12, 24, 48 dB per octave) and the type value that goes with each.
ORDERS = {12: (1, 0, 0, 0), 24: (0, 1, 0, 1), 48: (0, 0, 1, 2)}
PEAKS = ((1, 300), (2, 600), (3, 1200), (4, 2400))
PEAK = 'backend.effect.eq-peak-1-12.render'


def label(value):
    return str(value).replace('.', '-')


def shelf(keys, frequency, gain, resonance=None):
    values = {keys['active']: 1, keys['gain']: gain, keys['freq']: frequency}
    if resonance is not None:
        values[keys['res']] = resonance
    return values


def peak(number, frequency, gain, bandwidth=None):
    values = {f'Peak{number}active': 1, f'Peak{number}gain': gain, f'Peak{number}freq': frequency}
    if bandwidth is not None:
        values[f'Peak{number}bw'] = bandwidth
    return values


def cut(side, frequency, order=12, resonance=None):
    first, second, third, kind = ORDERS[order]
    values = {side + 'active': 1, side + 'freq': frequency, side + '12': first, side + '24': second,
              side + '48': third, side: kind}
    if resonance is not None:
        values[side + 'res'] = resonance
    return values


def spec(*parts):
    values = dict(DEFAULT)
    for part in parts:
        values.update(part)
    return base.fx('eq', 'Eq', values)


def add(suite, scenario, description, *parts, requires=()):
    base.point(suite, 'eq-' + scenario, description, 'synth', spec(*parts), requires=requires)


def build(suite):
    for gain in (-12, -6, 3):
        add(suite, 'input-gain-' + base.signed(gain), f'Set the equalizer input gain to {gain} dB', {'Inputgain': gain})
    for gain in (-9, -3, 1):
        add(suite, 'output-gain-' + base.signed(gain), f'Set the equalizer output gain to {gain} dB',
            {'Outputgain': gain})
    for frequency in (100, 300):
        for gain in (-12, 12):
            add(suite, f'low-shelf-{frequency}-{base.signed(gain)}',
                f'Shape the low end with a low shelf at {frequency} Hz and {gain} dB', shelf(LOW, frequency, gain))
    for resonance in (0.55, 3):
        add(suite, 'low-shelf-resonance-' + label(resonance),
            f'Boost a low shelf at 200 Hz by 12 dB with a resonance of {resonance}', shelf(LOW, 200, 12, resonance))
    for number, frequency in PEAKS:
        for gain in (-12, 12):
            add(suite, f'peak-{number}-{base.signed(gain)}',
                f'Shape a saw synth with peak band {number} at {frequency} Hz and {gain} dB',
                peak(number, frequency, gain))
    for bandwidth in (0.1, 1, 3):
        add(suite, 'peak-bandwidth-' + label(bandwidth),
            f'Boost peak band 2 at 600 Hz by 12 dB with a bandwidth of {bandwidth}', peak(2, 600, 12, bandwidth))
    for frequency in (1000, 4000):
        for gain in (-12, 12):
            add(suite, f'high-shelf-{frequency}-{base.signed(gain)}',
                f'Shape the high end with a high shelf at {frequency} Hz and {gain} dB', shelf(HIGH, frequency, gain))
    for resonance in (0.55, 3):
        add(suite, 'high-shelf-resonance-' + label(resonance),
            f'Boost a high shelf at 2000 Hz by 12 dB with a resonance of {resonance}',
            shelf(HIGH, 2000, 12, resonance))
    for frequency in (100, 300, 1000, 3000):
        add(suite, f'high-pass-{frequency}', f'High-pass a saw synth at {frequency} Hz with the equalizer',
            cut('HP', frequency))
    for order in (24, 48):
        add(suite, f'high-pass-1000-{order}-db', f'High-pass a saw synth at 1000 Hz with {order} dB per octave',
            cut('HP', 1000, order))
    for resonance in (2, 8):
        add(suite, 'high-pass-1000-resonance-' + label(resonance),
            f'High-pass a saw synth at 1000 Hz with a resonance of {resonance}', cut('HP', 1000, 12, resonance))
    for frequency in (300, 1000, 3000, 6000):
        add(suite, f'low-pass-{frequency}', f'Low-pass a saw synth at {frequency} Hz with the equalizer',
            cut('LP', frequency))
    for order in (24, 48):
        add(suite, f'low-pass-1000-{order}-db', f'Low-pass a saw synth at 1000 Hz with {order} dB per octave',
            cut('LP', 1000, order))
    for resonance in (2, 8):
        add(suite, 'low-pass-1000-resonance-' + label(resonance),
            f'Low-pass a saw synth at 1000 Hz with a resonance of {resonance}', cut('LP', 1000, 12, resonance))
    add(suite, 'peak-switched-off', 'A peak band that is switched off leaves the saw synth untouched',
        {'Peak1gain': 12, 'Peak1freq': 300}, requires=(PEAK,))
    add(suite, 'smile-curve', 'Boost the low and high ends and cut the middle with a shelf pair and a peak band',
        shelf(LOW, 100, 9), shelf(HIGH, 4000, 9), peak(3, 1000, -9))
    add(suite, 'telephone-band', 'Limit a saw synth to a telephone band with a 24 dB high-pass and low-pass',
        cut('HP', 300, 24), cut('LP', 3000, 24))
    add(suite, 'all-peaks-up', 'Raise all four peak bands by 6 dB', *[peak(n, f, 6) for n, f in PEAKS])
