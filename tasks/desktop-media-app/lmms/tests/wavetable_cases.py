'''Built-in wavetable and string synthesis from complete verifier-generated presets.

Wave buffers are embedded in the normal project format, never copied from a
factory preset. Every case renders through the public command-line channel.
'''
import base64
import math
import struct

import projectxml as px
from harness import signal_projection

NOTES = [(0, 60, 48), (72, 48, 55), (132, 36, 64)]


def wave(shape, length, amplitude=1.0):
    def value(i):
        phase = i / length
        if shape == 'sine':
            return math.sin(2 * math.pi * phase)
        if shape == 'square':
            return 1.0 if phase < .3 else -1.0
        if shape == 'saw':
            return 2 * phase - 1
        if shape == 'triangle':
            return 1 - 4 * abs(phase - .5)
        if shape == 'harmonics':
            return .65 * math.sin(2 * math.pi * phase) + .35 * math.sin(6 * math.pi * phase)
        raise ValueError(shape)
    return base64.b64encode(b''.join(struct.pack('<f', amplitude * value(i)) for i in range(length))).decode()


def bit(shape='harmonics', length=64, amplitude=.5):
    return dict(sampleLength=length, sampleShape=wave(shape, length, amplitude),
                interpolation=0, normalize=0)


def string(shape='saw', **params):
    values = dict(active0=1, volume0=70, stiffness0=0, pick0=.01, pickup0=.04, octave0=2,
                  length0=1, pan0=0, detune0=0, slap0=0, impulse0=0, graph0=wave(shape, 128))
    values.update(params)
    return values


def wat(**params):
    values = dict(abmix=-100, amod=0, bmod=0, xtalk=0, envAmt=0, envAtt=0, envHold=0, envDec=0)
    for oscillator, shape in [('a1', 'harmonics'), ('a2', 'sine'), ('b1', 'triangle'), ('b2', 'saw')]:
        values.update({oscillator + '_wave': wave(shape, 220), oscillator + '_vol': 80 if oscillator == 'a1' else 0,
                       oscillator + '_mult': 8, oscillator + '_pan': 0,
                       oscillator + '_ltune': 0, oscillator + '_rtune': 0})
    values.update(params)
    return values


def configurations():
    yield 'bit-harmonics', 'bitinvader', bit(), NOTES
    yield 'bit-saw', 'bitinvader', bit('saw'), NOTES
    yield 'bit-triangle', 'bitinvader', bit('triangle'), NOTES
    yield 'bit-pulse', 'bitinvader', bit('square'), NOTES
    yield 'bit-short-table', 'bitinvader', bit('saw', 8), [(0, 96, 84)]
    yield 'bit-interpolated', 'bitinvader', {**bit('saw', 8), 'interpolation': 1}, [(0, 96, 84)]
    yield 'bit-quiet', 'bitinvader', bit(amplitude=.2), NOTES
    yield 'bit-normalized', 'bitinvader', {**bit(amplitude=.2), 'normalize': 1}, NOTES
    for name, params in [
        ('base', {}), ('triangle', {'graph0': wave('triangle', 128)}),
        ('stiffness', {'stiffness0': .025}), ('pick', {'pick0': .04}),
        ('pickup', {'pickup0': .015}), ('harmonic', {'octave0': 4}),
        ('detune', {'detune0': .08}), ('pan-left', {'pan0': -.7}),
        ('volume', {'volume0': 35}),
        ('impulse', {'impulse0': 1}),
    ]:
        yield 'vibed-' + name, 'vibedstrings', string(**params), NOTES
    pair = string()
    pair.update({k[:-1] + '1': v for k, v in string('triangle', octave0=5, pan0=.5, volume0=50).items()})
    yield 'vibed-two-strings', 'vibedstrings', pair, NOTES
    for name, params in [
        ('base', {}), ('pulse', {'a1_wave': wave('square', 220)}),
        ('frequency', {'a1_mult': 16}), ('pan', {'a1_pan': 65}),
        ('detune-left', {'a1_ltune': -100}), ('volume', {'a1_vol': 40}),
        ('mix-b', {'abmix': 20, 'b1_vol': 90, 'b1_mult': 12}),
        ('mod-am', {'amod': 1, 'a2_vol': 65, 'a2_mult': 12}),
        ('mod-ring', {'amod': 2, 'a2_vol': 65, 'a2_mult': 12}),
        ('mod-phase', {'amod': 3, 'a2_vol': 65, 'a2_mult': 12}),
        ('crosstalk', {'xtalk': 65, 'abmix': 70, 'b1_vol': 70, 'b2_vol': 70, 'b2_mult': 4}),
        ('mix-envelope', {'abmix': -70, 'b1_vol': 90, 'b1_mult': 16, 'envAmt': 100, 'envAtt': 250, 'envHold': 100, 'envDec': 200}),
    ]:
        yield 'watsyn-' + name, 'watsyn', wat(**params), NOTES
    for key in (48, 60, 72):
        yield 'zyn-key-' + str(key), 'zynaddsubfx', {}, [(0, 144, key)]
    yield 'zyn-chord', 'zynaddsubfx', {}, [(0, 96, 48), (0, 96, 52), (0, 96, 55)]


def build(suite):
    for scenario, plugin, params, notes in configurations():
        def action(ctx, scenario=scenario, plugin=plugin, params=params, notes=notes):
            project = px.Project(bpm=120)
            project.add(px.instrument_track(plugin, plugin, params=params, notes=notes,
                                           vol=100 if plugin == 'zynaddsubfx' else 50))
            rendered = ctx.render(project.xml(), scenario)
            assert rendered.audio is not None, 'the synthesizer wrote no audio'
            return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
        suite.add('instrument', scenario, 'render', action,
                  description='Render the generated ' + plugin + ' preset: ' + scenario)
