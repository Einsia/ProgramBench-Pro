'''Waveshaper and dynamics processor coverage of the product command line on generated projects.

Every point renders one generated project whose track carries one of the two effects through cli render and decodes
the written file with the verifier FFmpeg. The exit status never decides; the written file does. Both effects keep a
curve of 200 values that the verifier writes into the project the way the product saves it (little-endian floats as
base64): the waveshaper maps the level of every sample through the curve, the dynamics processor maps the tracked
level to a gain. Loud and quiet notes alternate in the dynamics sources so that the tracked level changes, and the
stereo mode points use a stereo sample whose two channels differ in level. A point returns its signal class and the
signal projection of the render (format, length, level per channel, level per window and spectrum), so each curve,
gain, time and mode changes the observation.
'''
from __future__ import annotations

import math

import effect_cases as base
import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
DYNAMIC = [(0, 48, 57, 100), (48, 48, 57, 40), (96, 48, 57, 100), (144, 48, 57, 40)]
NOTES = {'synth': SEQUENCE, 'dynamic': DYNAMIC}
SAW = {'wavetype0': 2, 'wavetype1': 2, 'wavetype2': 2}
LEVELS = [(i + 1) / 200 for i in range(200)]
SHAPES = {
    'linear': lambda x: x,
    'soft-clip': lambda x: math.tanh(3 * x) / math.tanh(3),
    'hard-clip': lambda x: min(1.0, 2 * x),
    'half': lambda x: 0.5 * x,
    'square': lambda x: x * x,
    'root': lambda x: math.sqrt(x),
    'inverted': lambda x: 1 - x,
    'fold': lambda x: 1 - abs(2 * x - 1),
    'gate': lambda x: 0.0 if x < 0.3 else x,
    'stairs': lambda x: round(x * 4) / 4,
}
GAINS = {
    'linear': lambda x: x,
    'limit-10': lambda x: min(x, 0.1),
    'limit-20': lambda x: min(x, 0.2),
    'compress': lambda x: x if x < 0.15 else 0.15 + 0.3 * (x - 0.15),
    'expand': lambda x: x * x,
    'gate-20': lambda x: 0.0 if x < 0.2 else x,
    'boost': lambda x: min(1.0, 2 * x),
}
SHAPER_COMPANION = 'backend.effect.waveshaper-curve-hard-clip.render'
DYNAMICS_COMPANION = 'backend.effect.dynamics-curve-limit-20.render'


def label(value):
    return str(value).replace('.', '-')


def table(function):
    return px.curve([function(level) for level in LEVELS])


def shaper(curve='linear', **params):
    return base.fx('waveshaper', 'waveshapercontrols',
                   {'inputGain': 1, 'outputGain': 1, 'clipInput': 0, 'waveShape': table(SHAPES[curve]), **params})


def dynamics(curve='linear', **params):
    return base.fx('dynamicsprocessor', 'dynamicsprocessor_controls',
                   {'inputGain': 1, 'outputGain': 1, 'attack': 10, 'release': 100, 'stereoMode': 0,
                    'waveShape': table(GAINS[curve]), **params})


def point(suite, scenario, description, source, spec, requires=()):
    def action(ctx):
        effects = [px.effect(spec['name'], controls=spec['controls'], params=spec['params'], wet=spec['wet'],
                             on=spec['on'])]
        project = px.Project(bpm=BPM)
        if source == 'stereo':
            path, _audio = ctx.sample('stereo-pair')
            project.add(px.sample_track(clips=[(0, 192, path)], effects=effects))
        else:
            project.add(px.instrument_track('Lead', 'tripleoscillator', params=SAW, notes=NOTES[source],
                                            effects=effects))
        rendered = ctx.render(project.xml(), 'dynamics-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('effect', scenario, 'render', action, description=description, requires=requires)


def build(suite):
    for name in SHAPES:
        if name == 'linear':
            continue
        point(suite, 'waveshaper-curve-' + name, f'Shape a saw synth with the {name} curve of the waveshaper', 'synth',
              shaper(name))
    for gain in (0.5, 2, 4):
        point(suite, 'waveshaper-input-gain-' + label(gain),
              f'Drive the soft-clip waveshaper with an input gain of {gain}', 'synth', shaper('soft-clip', inputGain=gain))
    for gain in (0.5, 2):
        point(suite, 'waveshaper-output-gain-' + label(gain),
              f'Set the output gain of the soft-clip waveshaper to {gain}', 'synth', shaper('soft-clip', outputGain=gain))
    point(suite, 'waveshaper-unclipped-input', 'Drive the linear waveshaper with an input gain of 3 and an output of 0.4, unclipped',
          'synth', shaper('linear', inputGain=3, outputGain=0.4))
    point(suite, 'waveshaper-clipped-input', 'Drive the linear waveshaper with an input gain of 3 and an output of 0.4, clipping the input',
          'synth', shaper('linear', inputGain=3, outputGain=0.4, clipInput=1))
    point(suite, 'waveshaper-half-wet', 'Mix half of the soft-clipped signal with the dry signal', 'synth',
          dict(shaper('soft-clip', inputGain=3), wet=0.5))
    point(suite, 'waveshaper-disabled', 'A switched-off waveshaper leaves the signal untouched', 'synth',
          dict(shaper('hard-clip'), on=False), requires=(SHAPER_COMPANION,))
    for name in ('root', 'square'):
        point(suite, 'waveshaper-stereo-' + name, f'Shape a stereo sample with the {name} curve of the waveshaper',
              'stereo', shaper(name))
    for name in GAINS:
        if name == 'linear':
            continue
        point(suite, 'dynamics-curve-' + name, f'Process loud and quiet notes with the {name} curve of the dynamics '
              'processor', 'dynamic', dynamics(name))
    for gain in (0.5, 2, 4):
        point(suite, 'dynamics-input-gain-' + label(gain),
              f'Limit loud and quiet notes at 0.2 with an input gain of {gain}', 'dynamic',
              dynamics('limit-20', inputGain=gain))
    for gain in (0.5, 2):
        point(suite, 'dynamics-output-gain-' + label(gain),
              f'Limit loud and quiet notes at 0.2 with an output gain of {gain}', 'dynamic',
              dynamics('limit-20', outputGain=gain))
    for attack in (1, 100, 400):
        point(suite, f'dynamics-attack-{attack}', f'Limit loud and quiet notes at 0.2 with an attack of {attack} ms',
              'dynamic', dynamics('limit-20', attack=attack))
    for release in (1, 300, 500):
        point(suite, f'dynamics-release-{release}',
              f'Limit loud and quiet notes at 0.2 with a release of {release} ms', 'dynamic',
              dynamics('limit-20', release=release))
    for mode, name in enumerate(('maximum', 'average', 'unlinked')):
        point(suite, 'dynamics-stereo-' + name, f'Limit a stereo sample at 0.1 with the {name} stereo mode', 'stereo',
              dynamics('limit-10', stereoMode=mode))
    point(suite, 'dynamics-half-wet', 'Mix half of the limited signal with the dry signal', 'dynamic',
          dict(dynamics('limit-20'), wet=0.5))
    point(suite, 'dynamics-disabled', 'A switched-off dynamics processor leaves the signal untouched', 'dynamic',
          dict(dynamics('limit-20'), on=False), requires=(DYNAMICS_COMPANION,))
