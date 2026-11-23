'''Sound shaping coverage of the product command line on generated projects.

Every point renders one generated project with a TripleOscillator track whose filter, volume envelope, cutoff
envelope, resonance envelope or LFO is set through cli render and decodes the written file with the verifier FFmpeg.
The exit status never decides; the written file does. All three oscillators play a saw wave so that a filter changes
the spectrum, and envelope stages last long enough to change the level of an observation window. The random LFO wave
is left out (not reproducible between runs of the reference). A point returns its signal class and the signal
projection of the render (format, length, level per channel, level per window and spectrum), so every filter type,
cutoff, resonance, envelope stage and LFO setting changes the observation.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
HELD = [(0, 192, 57)]
SHORT = [(0, 24, 57)]
SAW = {'wavetype0': 2, 'wavetype1': 2, 'wavetype2': 2}
FILTERS = ('low-pass', 'high-pass', 'band-pass CSG', 'band-pass CZPG', 'notch', 'all-pass', 'Moog', 'double low-pass',
           'RC low-pass 12 dB', 'RC band-pass 12 dB', 'RC high-pass 12 dB', 'RC low-pass 24 dB', 'RC band-pass 24 dB',
           'RC high-pass 24 dB', 'vocal formant', 'double Moog', 'SV low-pass', 'SV band-pass', 'SV high-pass',
           'SV notch', 'fast formant', 'tripole')
SHAPES = ('sine', 'triangle', 'saw', 'square')
COMPANION = 'backend.sound-shaping.filter-type-00-cut-500.render'
# The band-pass CZPG filter (type 3) renders like the band-pass CSG filter (type 2) within the observation tolerances.
TWINS = (3,)


def label(value):
    return ('minus-' if value < 0 else '') + str(abs(value)).replace('.', '-')


def filtered(kind=0, cut=1000, res=1.0, on=1):
    return {'fwet': on, 'ftype': kind, 'fcut': cut, 'fres': res}


def envelope(**values):
    return {'amt': 1, 'att': 0, 'hold': 0.2, 'dec': 0.4, 'sustain': 0.5, 'rel': 0.2, 'pdel': 0, **values}


def lfo(**values):
    return {'amt': 0, 'lamt': 0.5, 'lspd': 0.4, 'lshp': 0, 'latt': 0, 'lpdel': 0, 'x100': 0, **values}


def point(suite, scenario, description, notes=SEQUENCE, requires=(), **shaping):
    def action(ctx):
        track = px.instrument_track('Lead', 'tripleoscillator', params=SAW, notes=notes, shaping=shaping)
        project = px.Project(bpm=BPM)
        project.add(track)
        rendered = ctx.render(project.xml(), 'shaping-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('sound-shaping', scenario, 'render', action, description=description, requires=requires)


def build(suite):
    point(suite, 'baseline-held', 'Play a held saw note without any sound shaping', notes=HELD)
    for kind, name in enumerate(FILTERS):
        if kind in TWINS:
            continue
        for cut in (500, 3000):
            point(suite, f'filter-type-{kind:02d}-cut-{cut}', f'Filter a saw synth with the {name} filter at {cut} Hz',
                  filter=filtered(kind, cut))
    point(suite, 'filter-disabled', 'A switched-off filter leaves the saw synth untouched', requires=(COMPANION,),
          filter=filtered(0, 500, on=0))
    for cut in (200, 1000, 2000, 5000, 8000):
        point(suite, f'lowpass-cut-{cut}', f'Low-pass a saw synth at {cut} Hz', filter=filtered(0, cut))
    for cut in (200, 1000, 2000, 6000):
        point(suite, f'highpass-cut-{cut}', f'High-pass a saw synth at {cut} Hz', filter=filtered(1, cut))
    for res in (0.5, 2, 4, 6, 10):
        point(suite, f'lowpass-resonance-{label(res)}', f'Low-pass a saw synth at 1000 Hz with a resonance of {res}',
              filter=filtered(0, 1000, res))
    for res in (0.5, 2, 4):
        point(suite, f'moog-resonance-{label(res)}', f'Filter a saw synth at 1000 Hz with the Moog filter and a resonance of {res}',
              filter=filtered(6, 1000, res))
    for res in (1, 4, 8):
        point(suite, f'rc24-resonance-{label(res)}',
              f'Filter a saw synth at 1000 Hz with the RC 24 dB low-pass and a resonance of {res}',
              filter=filtered(11, 1000, res))
    for att in (0.2, 0.4, 0.6, 0.8):
        point(suite, f'volume-attack-{label(att)}', f'Fade in a held saw note with a volume envelope attack of {att}',
              notes=HELD, elvol=envelope(att=att))
    for hold in (0.2, 0.4, 0.5, 0.6):
        point(suite, f'volume-hold-{label(hold)}', f'Hold the volume envelope of a held note for {hold} before it decays',
              notes=HELD, elvol=envelope(hold=hold, dec=0.3, sustain=0.2))
    for dec in (0.2, 0.4, 0.6, 0.8):
        point(suite, f'volume-decay-{label(dec)}', f'Let the volume envelope of a held note decay with a time of {dec}',
              notes=HELD, elvol=envelope(hold=0, dec=dec, sustain=0.2))
    for sustain in (0, 0.25, 0.5, 0.75):
        point(suite, f'volume-sustain-{label(sustain)}', f'Set the sustain level of the volume envelope to {sustain}',
              notes=HELD, elvol=envelope(hold=0, dec=0.3, sustain=sustain))
    for rel in (0.2, 0.4, 0.6, 0.8):
        point(suite, f'volume-release-{label(rel)}', f'Release a short saw note with a volume envelope release of {rel}',
              notes=SHORT, elvol=envelope(hold=0, dec=0, sustain=1, rel=rel))
    for delay in (0.2, 0.4, 0.5):
        point(suite, f'volume-predelay-{label(delay)}', f'Delay the start of the volume envelope of a held note by {delay}',
              notes=HELD, elvol=envelope(pdel=delay, att=0.2))
    for amount in (0.25, 0.5, 0.75):
        point(suite, f'volume-envelope-amount-{label(amount)}', f'Apply the volume envelope with an amount of {amount}',
              notes=HELD, elvol=envelope(amt=amount, att=0.4, dec=0.4, sustain=0.2))
    point(suite, 'volume-envelope-full-sequence', 'Play four notes through a complete volume envelope',
          elvol=envelope(att=0.3, hold=0.2, dec=0.4, sustain=0.3, rel=0.3))
    point(suite, 'volume-envelope-full-held', 'Play a held note through a complete volume envelope', notes=HELD,
          elvol=envelope(att=0.3, hold=0.2, dec=0.4, sustain=0.3, rel=0.3))
    low = filtered(0, 400, 2)
    for amount in (0.5, 1.0, -0.5, -1.0):
        for att in (0.2, 0.5):
            point(suite, f'cutoff-envelope-amount-{label(amount)}-attack-{label(att)}',
                  f'Sweep the cutoff of a low-pass filter with an envelope of amount {amount} and attack {att}',
                  notes=HELD, filter=low, elcut=envelope(amt=amount, att=att, dec=0.4, sustain=0.3))
    for dec in (0.2, 0.5):
        point(suite, f'cutoff-envelope-decay-{label(dec)}',
              f'Sweep the cutoff of a low-pass filter down with an envelope decay of {dec}', notes=HELD, filter=low,
              elcut=envelope(amt=1.0, hold=0, dec=dec, sustain=0.1))
    for shape, name in enumerate(SHAPES):
        for amount in (0.5, 1.0):
            point(suite, f'cutoff-lfo-{name}-amount-{label(amount)}',
                  f'Modulate the cutoff of a low-pass filter with a {name} LFO of amount {amount}', notes=HELD,
                  filter=low, elcut=lfo(lshp=shape, lamt=amount))
    for speed in (0.3, 0.5, 0.6, 0.7):
        point(suite, f'cutoff-lfo-speed-{label(speed)}', f'Modulate the cutoff with a sine LFO of speed {speed}',
              notes=HELD, filter=low, elcut=lfo(lamt=1.0, lspd=speed))
    for amount in (0.5, 1.0):
        for att in (0.0, 0.4):
            point(suite, f'resonance-envelope-amount-{label(amount)}-attack-{label(att)}',
                  f'Sweep the resonance of a low-pass filter with an envelope of amount {amount} and attack {att}',
                  notes=HELD, filter=filtered(0, 800, 1), elres=envelope(amt=amount, att=att, dec=0.4, sustain=0.3))
    for shape, name in enumerate(SHAPES):
        for amount in (0.5, 1.0):
            point(suite, f'volume-lfo-{name}-amount-{label(amount)}',
                  f'Modulate the volume of a held note with a {name} LFO of amount {amount}', notes=HELD,
                  elvol=lfo(lshp=shape, lamt=amount))
    for speed in (0.3, 0.5, 0.7):
        point(suite, f'volume-lfo-speed-{label(speed)}', f'Modulate the volume with a sine LFO of speed {speed}',
              notes=HELD, elvol=lfo(lamt=1.0, lspd=speed))
    for amount in (0.25,):
        point(suite, f'volume-lfo-depth-{label(amount)}', f'Modulate the volume with a sine LFO of amount {amount}',
              notes=HELD, elvol=lfo(lamt=amount))
    for attack in (0.2, 0.5):
        point(suite, f'volume-lfo-attack-{label(attack)}', f'Fade in the volume LFO of a held note with an attack of {attack}',
              notes=HELD, elvol=lfo(lamt=1.0, latt=attack))
    for delay in (0.2, 0.5):
        point(suite, f'volume-lfo-predelay-{label(delay)}', f'Delay the volume LFO of a held note by {delay}', notes=HELD,
              elvol=lfo(lamt=1.0, lpdel=delay))
    point(suite, 'volume-lfo-times-100', 'Multiply the speed range of the volume LFO by one hundred', notes=HELD,
          elvol=lfo(lamt=1.0, lspd=0.3, x100=1))
