'''Multitap echo and peak controller coverage of the product command line on generated projects.

Every point renders one generated project whose saw synth track (or, for the stereo points, a stereo sample) carries
the effect through cli render and decodes the written file with the verifier FFmpeg. The exit status never decides; the
written file does. The multitap echo is written the way the product saves it: a controls element with the step length,
the dry gain and two graphs of 16 little-endian floats (the amplitude and the lowpass setting
of every step); what is not given is the product default. The peak controller is observed behind an amplifier
with its mute switch. A point returns its signal class and the signal
projection of the render (format, length, level per channel, level per window and spectrum).
'''
from __future__ import annotations

import base64
import struct

import effect_cases as base

STEPS = 16
FLAT = [0.5] * STEPS
DECAY = [round(0.8 * 0.7 ** i, 4) for i in range(STEPS)]
PEAK = {'effectId': 1, 'base': 0.5, 'amount': 1, 'amountmult': 1, 'attack': 0, 'decay': 0, 'treshold': 0, 'abs': 1,
        'mute': 0}


def graph(values):
    padded = (list(values) + [0.0] * STEPS)[:STEPS]
    return base64.b64encode(struct.pack('<%df' % STEPS, *padded)).decode()


def echo(amp=FLAT, lp=(), wet=1.0, on=True, **params):
    return base.fx('multitapecho', 'multitapechocontrols', {'ampsteps': graph(amp), 'lpsteps': graph(lp), **params},
                   wet=wet, on=on)


def peak(**params):
    return base.fx('peakcontrollereffect', 'peakcontrollereffectcontrols', {**PEAK, **params})


def build(suite):
    point = base.point
    point(suite, 'multitap-flat', 'Echo a saw synth with half amplitude on all 16 steps of the multitap echo', 'synth', echo())
    point(suite, 'multitap-single-tap', 'Echo a stereo sample on the third step of the multitap echo only', 'stereo', echo([0, 0, 0.8], steplength=113))
    for length in (50, 250, 400):
        point(suite, f'multitap-step-length-{length}', f'Space the steps of the multitap echo {length} ms apart', 'synth',
              echo(DECAY, steplength=length))
    for gain in (-12, -60):
        point(suite, f'multitap-dry-gain-minus-{abs(gain)}', f'Set the dry gain of the multitap echo to {gain}', 'synth',
              echo(DECAY, drygain=gain))
    point(suite, 'multitap-lowpass-half', 'Set every lowpass step of the multitap echo to a half', 'synth',
          echo(FLAT, lp=[0.5] * STEPS))
    point(suite, 'multitap-lowpass-full', 'Set every lowpass step of the multitap echo to its full value', 'synth',
          echo(FLAT, lp=[1.0] * STEPS))
    point(suite, 'multitap-half-wet', 'Mix half of the multitap echo with the dry signal', 'synth', echo(DECAY, wet=0.5))
    point(suite, 'multitap-stereo-plain', 'Echo a stereo sample on the fourth step of the multitap echo', 'stereo',
          echo([0, 0, 0, 0.8]))
    point(suite, 'multitap-stereo-swapped', 'Echo a stereo sample on the fourth step with the inputs of the multitap echo swapped',
          'stereo', echo([0, 0, 0, 0.8], swapinputs=1))
    point(suite, 'multitap-disabled', 'A switched-off multitap echo leaves the signal untouched', 'synth', echo(DECAY, on=False),
          requires=('backend.effect.multitap-flat.render',))
    point(suite, 'multitap-chain-amplifier', 'Chain an amplifier and a multitap echo', 'synth', base.amplifier(volume=70),
          echo(DECAY))
    point(suite, 'peakcontroller-muted', 'Mute the peak controller behind the amplifier', 'synth', base.amplifier(volume=70),
          peak(mute=1), requires=('backend.effect.multitap-chain-amplifier.render',))
