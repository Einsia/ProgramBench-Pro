'''Grids of positions, lengths, levels, tempos, beat steps and automation of the product command line on generated projects.

The points reuse the builders of sample_cases and arrangement_cases with other values. Every point renders one
generated project through cli render and decodes the written file with the verifier FFmpeg. The exit status never
decides; the written file does. One beat is 48 ticks, which at 140 beats per minute is almost exactly one observation
window (0.43 s), so positions, lengths, beat steps and automation times lie on that grid and every point changes the
level of whole windows. A point returns its signal class and the signal projection of the render (format, length,
level per channel, level per window and spectrum).
'''
from __future__ import annotations

import arrangement_cases as arr
import sample_cases as smp

MIX_PAIRS = (('tone-440', 'square-220'), ('tone-880', 'ramp'), ('ramp', 'impulse'), ('stereo-pair', 'tone-440'),
             ('square-220', 'impulse'))
OTHER_SAMPLES = ('tone-880', 'square-220', 'ramp', 'impulse', 'stereo-pair')
# Steps on beat boundaries only: the four steps of one beat fall into one observation window.
BEAT_SETS = (('beats-0-2', (0, 8)), ('beats-1-3', (4, 12)), ('beats-0-1', (0, 4)), ('beats-2-3', (8, 12)),
             ('beats-1-2', (4, 8)), ('beats-0-3', (0, 12)), ('beats-0-1-2', (0, 4, 8)), ('beats-1-2-3', (4, 8, 12)),
             ('beats-0-2-3', (0, 8, 12)), ('beats-0-1-3', (0, 4, 12)), ('beat-1', (4,)), ('beat-2', (8,)),
             ('beat-3', (12,)))
CLIP_SETS = (('repeat-3', ((0, 192), (192, 192), (384, 192))), ('second-bar', ((192, 192),)),
             ('spaced', ((0, 192), (576, 192))), ('quarter-bar', ((0, 48),)), ('three-quarter-bar', ((0, 144),)))
TARGETS = (('master-volume', 'song', 'mastervol', 90, 30), ('sample-volume', 'sample', 'vol', 80, 10),
           ('sample-pan', 'sample', 'pan', 100, -100), ('instrument-volume', 'instrument', 'vol', 60, 150),
           ('instrument-pan', 'instrument', 'pan', 100, -50), ('tempo', 'song', 'bpm', 180, 90))
SHAPES = (('linear-48', 1, 48), ('linear-192', 1, 192), ('discrete-96', 0, 96), ('cubic-96', 2, 96))
ZIGZAG = ('master-volume', 'sample-volume', 'instrument-volume', 'sample-pan')
LATE = ('sample-volume', 'instrument-pan')


def sample_grids(suite):
    point, clip, track, signed = smp.point, smp.clip, smp.track, smp.signed
    for pos in (72, 120, 144, 240, 288, 336):
        point(suite, f'grid-position-{pos}', f'Start the tone-440 clip at tick {pos}', [track(clip('tone-440', pos=pos))])
    for length in (36, 60, 72, 84):
        point(suite, f'grid-length-{length}', f'Cut the tone-440 clip to {length} ticks',
              [track(clip('tone-440', length=length))])
    for vol in (10, 75, 125, 175):
        point(suite, f'grid-track-volume-{vol}', f'Set the volume of the sample track to {vol}',
              [track(clip('tone-440'), vol=vol)])
    for pan in (-75, -25, 25, 75):
        point(suite, f'grid-track-pan-{signed(pan)}', f'Set the panning of the sample track to {pan}',
              [track(clip('tone-440'), pan=pan)])
    for key in ('tone-880', 'square-220', 'ramp'):
        for vol in (50, 150):
            for pan in (-50, 50):
                point(suite, f'grid-{key}-volume-{vol}-pan-{signed(pan)}',
                      f'Play the {key} track at volume {vol} and panning {pan}', [track(clip(key), vol=vol, pan=pan)])
    for bpm in (80, 120, 160, 240):
        point(suite, f'grid-tempo-{bpm}', f'Render the clip at {bpm} beats per minute', [track(clip('tone-440'))],
              bpm=bpm)
    for volume in (20, 60, 110, 160):  # not the track volumes: a master volume acts like the volume of the only track
        point(suite, f'grid-master-volume-{volume}', f'Set the master volume to {volume}',
              [track(clip('tone-440'))], mastervol=volume)
    for first, second in MIX_PAIRS:
        point(suite, f'grid-mix-{first}-{second}', f'Mix the {first} and {second} samples on two tracks',
              [track(clip(first)), track(clip(second))])
    for key in OTHER_SAMPLES:
        point(suite, f'grid-volume-75-{key}', f'Play the {key} sample at track volume 75', [track(clip(key), vol=75)])
        point(suite, f'grid-late-{key}', f'Start the {key} clip at tick 96', [track(clip(key, pos=96))])
        point(suite, f'grid-half-{key}', f'Cut the {key} clip to 96 ticks', [track(clip(key, length=96))])


def beat_grids(suite):
    beat = arr.beat_point
    for label, steps in BEAT_SETS:
        beat(suite, 'grid-steps-' + label, f'Play the {label} steps of a kicker pattern',
             [lambda steps=steps: arr.kicker(steps)])
    for value in (80, 220, 500):
        beat(suite, f'grid-kicker-start-{value}', f'Start the kicker sweep at {value} Hz instead of the note',
             [lambda value=value: arr.kicker(arr.QUARTERS, startnote=0, startfreq=value)])
    for value in (20, 100, 200):
        beat(suite, f'grid-kicker-end-{value}', f'End the kicker sweep at {value} Hz from 300 Hz',
             [lambda value=value: arr.kicker(arr.QUARTERS, startnote=0, startfreq=300, endfreq=value)])
    for value in (100, 300, 700, 1500):
        beat(suite, f'grid-kicker-length-{value}', f'Play the pattern with a kicker length of {value} ms',
             [lambda value=value: arr.kicker(arr.QUARTERS, decay=value)])
    for value in (0.3, 2):
        beat(suite, 'grid-kicker-gain-' + str(value).replace('.', '-'), f'Play the pattern with a kicker gain of {value}',
             [lambda value=value: arr.kicker(arr.QUARTERS, gain=value)])
    for value in (0, 60):
        beat(suite, f'grid-kicker-distortion-{value}', f'Play the pattern with a kicker distortion of {value}',
             [lambda value=value: arr.kicker(arr.QUARTERS, dist=value, distend=value)])
    for bpm in (80, 120, 160):
        beat(suite, f'grid-tempo-{bpm}', f'Play the pattern at {bpm} beats per minute',
             [lambda: arr.kicker(arr.QUARTERS)], bpm=bpm)
    for label, clips in CLIP_SETS:
        beat(suite, 'grid-clips-' + label, f'Place the beat clips in the song: {label}',
             [lambda: arr.kicker(arr.QUARTERS)], clips=clips)
    beat(suite, 'grid-lead-quarters', 'Play a synth on every beat of the pattern', [lambda: arr.lead(arr.QUARTERS)])
    beat(suite, 'grid-lead-and-kicker-offset', 'Play a kicker on beats 1 and 3 and a synth on beats 0 and 2',
         [lambda: arr.kicker((4, 12)), lambda: arr.lead((0, 8))])
    beat(suite, 'grid-two-kickers', 'Play two kickers with different settings in one pattern',
         [lambda: arr.kicker((0, 8), startnote=0, startfreq=300), lambda: arr.kicker((4, 12), decay=150)])


def automation_grids(suite):
    lookup = {row[0]: row for row in TARGETS}
    for name, target, key, start, end in TARGETS:
        words = name.replace('-', ' ')
        for label, prog, span in SHAPES:
            arr.automation_point(suite, f'grid-{name}-{label}', f'Move the {words} from {start} to {end} ({label})',
                                 target, key, ((0, start), (span, end)), prog=prog)
    for name in ZIGZAG:
        _name, target, key, start, end = lookup[name]
        words = name.replace('-', ' ')
        arr.automation_point(suite, f'grid-{name}-zigzag', f'Move the {words} up and down between {start} and {end}',
                             target, key, ((0, start), (48, end), (96, start), (144, end)))
    for name in LATE:
        _name, target, key, start, end = lookup[name]
        words = name.replace('-', ' ')
        arr.automation_point(suite, f'grid-{name}-late-start', f'Start the {words} automation at tick 96',
                             target, key, ((0, start), (48, end)), pos=96)


def build(suite):
    sample_grids(suite)
    beat_grids(suite)
    automation_grids(suite)
