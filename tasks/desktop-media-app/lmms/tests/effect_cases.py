'''Effect coverage of the product command line on generated projects.

Every point renders one generated project whose instrument or sample track carries one effect (or a chain of two)
through cli render and decodes the written file with the verifier FFmpeg. The exit status never decides; the written
file does. Effects whose controls need data the verifier cannot invent (waveshaper and dynamics processor curves, EQ
band models, the peak controller) are not covered here. A point returns its signal class and the signal projection of
the render (format, length, level per channel, level per window and spectrum), so each control changes the
observation: gain and panning through levels, filters and the bass booster through the spectrum, the delay through
the window levels, the stereo effects through the levels of the two channels.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
SAW = {'wavetype0': 2, 'wavetype1': 2, 'wavetype2': 2}


def signed(value):
    return ('minus-' if value < 0 else '') + str(abs(value)).replace('.', '-')


def fx(name, controls, params, **options):
    return dict(name=name, controls=controls, params=params, wet=options.get('wet', 1.0), on=options.get('on', True))


def amplifier(**params):
    return fx('amplifier', 'AmplifierControls', {'volume': 100, 'pan': 0, 'left': 100, 'right': 100, **params})


def matrix(**params):
    return fx('stereomatrix', 'stereomatrixcontrols', {'l-l': 1, 'l-r': 0, 'r-l': 0, 'r-r': 1, **params})


def bass(**params):
    return fx('bassbooster', 'bassboostercontrols', {'freq': 125, 'gain': 1, 'ratio': 5.6, **params})


def dual(**params):
    return fx('dualfilter', 'DualFilterControls',
              {'enabled1': 1, 'filter1': 0, 'cut1': 800, 'res1': 0.5, 'gain1': 100, 'enabled2': 0, 'filter2': 0,
               'cut2': 7000, 'res2': 0.5, 'gain2': 100, 'mix': -1, **params})


def delay(**params):
    return fx('delay', 'Delay', {'DelayTimeSamples': 0.25, 'FeebackAmount': 0.5, 'LfoFrequency': 2, 'LfoAmount': 0,
                                 'OutGain': 0, **params})


def width(value):
    return fx('stereoenhancer', 'stereoenhancercontrols', {'width': value})


def point(suite, scenario, description, source, *specs, requires=()):
    def action(ctx):
        effects = [px.effect(s['name'], controls=s['controls'], params=s['params'], wet=s['wet'], on=s['on'])
                   for s in specs]
        project = px.Project(bpm=BPM)
        if source == 'synth':
            project.add(px.instrument_track('Lead', 'tripleoscillator', params=SAW, notes=SEQUENCE, effects=effects))
        else:
            path, _audio = ctx.sample('stereo-pair')
            project.add(px.sample_track(clips=[(0, 192, path)], effects=effects))
        rendered = ctx.render(project.xml(), 'effect-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('effect', scenario, 'render', action, description=description, requires=requires)


def build(suite):
    for volume in (0, 50, 150):
        point(suite, f'amplifier-volume-{volume}', f'Amplify a saw synth by {volume} percent with the amplifier effect',
              'synth', amplifier(volume=volume))
    for pan in (-100, -50, 50, 100):
        point(suite, f'amplifier-pan-{signed(pan)}', f'Pan a stereo sample to {pan} with the amplifier effect',
              'stereo', amplifier(pan=pan))
    for left, right in ((50, 200), (200, 50)):
        point(suite, f'amplifier-left-{left}-right-{right}',
              f'Set the amplifier left gain to {left} and the right gain to {right} on a stereo sample', 'stereo',
              amplifier(left=left, right=right))
    point(suite, 'amplifier-half-wet', 'Mix half of the amplified signal with the dry signal', 'synth',
          dict(amplifier(volume=50), wet=0.5))
    point(suite, 'amplifier-disabled', 'A switched-off amplifier leaves the signal untouched', 'synth',
          dict(amplifier(volume=50), on=False), requires=('backend.effect.amplifier-volume-50.render',))
    for label, params in (('swap', {'l-l': 0, 'l-r': 1, 'r-l': 1, 'r-r': 0}),
                          ('left-to-both', {'l-l': 1, 'l-r': 1, 'r-l': 0, 'r-r': 0}),
                          ('left-only', {'l-l': 1, 'l-r': 0, 'r-l': 0, 'r-r': 0}),
                          ('mono', {'l-l': 0.5, 'l-r': 0.5, 'r-l': 0.5, 'r-r': 0.5})):
        point(suite, 'stereomatrix-' + label, f'Route a stereo sample through the stereo matrix: {label}', 'stereo',
              matrix(**params))
    for label, params in (('low-60', {'freq': 60}), ('high-250', {'freq': 250}), ('gain-3', {'gain': 3}),
                          ('gain-3-ratio-1', {'gain': 3, 'ratio': 1})):
        point(suite, 'bassbooster-' + label, f'Boost the bass of a saw synth: {label}', 'synth', bass(**params))
    for cut in (300, 1000, 3000):
        point(suite, f'dualfilter-lowpass-{cut}', f'Low-pass a saw synth at {cut} Hz with the dual filter', 'synth',
              dual(cut1=cut))
    for kind in (1, 2, 3, 4):
        point(suite, f'dualfilter-type-{kind}', f'Filter a saw synth at 1000 Hz with filter type {kind}', 'synth',
              dual(filter1=kind, cut1=1000))
    point(suite, 'dualfilter-resonance', 'Filter a saw synth at 800 Hz with a high resonance', 'synth', dual(res1=3.0))
    point(suite, 'dualfilter-gain', 'Lower the output gain of the first dual filter', 'synth', dual(gain1=50))
    point(suite, 'dualfilter-mix', 'Blend a low-pass and a high-pass filter of the dual filter', 'synth',
          dual(enabled2=1, filter2=1, cut1=800, cut2=1000, mix=0))
    for seconds in (0.1, 0.25, 0.5):
        point(suite, f'delay-time-{signed(seconds)}', f'Echo a saw synth after {seconds} seconds', 'synth',
              delay(DelayTimeSamples=seconds))
    for feedback in (0, 0.8):
        point(suite, f'delay-feedback-{signed(feedback)}', f'Echo a saw synth with a feedback of {feedback}', 'synth',
              delay(FeebackAmount=feedback))
    point(suite, 'delay-output-gain', 'Lower the output gain of the delay', 'synth', delay(OutGain=-6))
    point(suite, 'delay-modulated', 'Modulate the delay time with the low frequency oscillator', 'synth',
          delay(LfoAmount=0.05, LfoFrequency=4))
    for value in (0, 50, 150):
        point(suite, f'stereoenhancer-width-{value}', f'Set the stereo width of a stereo sample to {value}', 'stereo',
              width(value))
    point(suite, 'chain-amplifier-lowpass', 'Chain an amplifier and a low-pass filter', 'synth', amplifier(volume=70),
          dual(cut1=1500))
