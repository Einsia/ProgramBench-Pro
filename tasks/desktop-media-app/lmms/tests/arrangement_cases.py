'''Beat pattern and automation coverage of the product command line on generated projects.

Every point renders one generated project through cli render and decodes the written file with the verifier FFmpeg.
The exit status never decides; the written file does. A beat and bassline track plays a pattern of 16 steps (12 ticks
each) through its clips in the song; an automation pattern drives one model (the master volume, the tempo, or the volume
or the panning of a track) over time. A point returns its signal class and the signal projection of the render (format,
length, level per channel, level per window and spectrum), so each step set, clip placement and automation shape
changes the observation.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
SAMPLE = 'tone-2s'
QUARTERS = (0, 4, 8, 12)
STEP_SETS = (('quarters', QUARTERS), ('eighths', tuple(range(0, 16, 2))), ('offbeats', (3, 7, 11, 15)),
             ('single', (0,)), ('all', tuple(range(16))))
CLIPS = (('repeat-2', ((0, 192), (192, 192))), ('gap', ((0, 192), (384, 192))), ('half-bar', ((0, 96),)),
         ('offset', ((96, 192),)))
SHAPES = (('discrete', 0), ('linear', 1), ('cubic', 2))


def kicker(steps, **params):
    return px.instrument_track('Kicker', 'kicker', params=params or None, steps=list(steps))


def lead(steps):
    return px.instrument_track('Lead', 'tripleoscillator', steps=list(steps))


def synth(ctx):
    return px.instrument_track('Lead', 'tripleoscillator', notes=SEQUENCE)


def beat_point(suite, scenario, description, tracks, clips=((0, 192),), extra=(), muted=False, requires=(), **settings):
    def action(ctx):
        project = px.Project(**{'bpm': BPM, **settings})
        project.add(px.beat_track(tracks=[make() for make in tracks], clips=clips, muted=muted))
        for adder in extra:
            project.add(adder(ctx))
        rendered = ctx.render(project.xml(), 'beat-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('beat-pattern', scenario, 'render', action, description=description, requires=requires)


def automation_point(suite, scenario, description, target, key, points, prog=1, pos=0, requires=()):
    def action(ctx):
        project = px.Project(bpm=BPM)
        if target == 'instrument':
            track = project.add(px.instrument_track('Lead', 'tripleoscillator', notes=SEQUENCE))
            owner = track.find('instrumenttrack')
        else:
            path, _audio = ctx.sample(SAMPLE)
            track = project.add(px.sample_track(clips=[(0, 224, path)]))
            owner = project.head if target == 'song' else track.find('sampletrack')
        project.automate(owner, key, points, pos=pos, prog=prog)
        rendered = ctx.render(project.xml(), 'automation-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('automation', scenario, 'render', action, description=description, requires=requires)


def build_beats(suite):
    for label, steps in STEP_SETS:
        beat_point(suite, 'steps-' + label, f'Play the {label} steps of a kicker pattern',
                   [lambda steps=steps: kicker(steps)])
    for label, clips in CLIPS:
        beat_point(suite, 'clips-' + label, f'Place the beat clips in the song: {label}',
                   [lambda: kicker(QUARTERS)], clips=clips)
    beat_point(suite, 'two-instruments', 'Play a kicker and a synth in one pattern',
               [lambda: kicker((0, 8)), lambda: lead((4, 12))])
    beat_point(suite, 'kicker-start-frequency', 'Play the pattern with a kicker that starts at 300 Hz',
               [lambda: kicker(QUARTERS, startfreq=300)])
    beat_point(suite, 'kicker-decay', 'Play the pattern with a short kicker decay',
               [lambda: kicker(QUARTERS, decay=150)])
    for bpm in (100, 200):
        beat_point(suite, f'tempo-{bpm}', f'Play the pattern at {bpm} beats per minute',
                   [lambda: kicker(QUARTERS)], bpm=bpm)
    beat_point(suite, 'next-to-synth-track', 'Play a pattern next to a synth track', [lambda: kicker((0, 8))],
               extra=(synth,))
    beat_point(suite, 'muted-beat-track', 'Mute the beat track next to a synth track', [lambda: kicker((0, 8))],
               extra=(synth,), muted=True, requires=('backend.beat-pattern.next-to-synth-track.render',))


def build_automation(suite):
    for label, prog in SHAPES:
        automation_point(suite, f'master-volume-{label}',
                         f'Move the master volume from 100 to 20 over 96 ticks with a {label} progression', 'song',
                         'mastervol', ((0, 100), (96, 20)), prog=prog)
    automation_point(suite, 'master-volume-rise', 'Raise the master volume from 0 to 100 over 96 ticks', 'song',
                     'mastervol', ((0, 0), (96, 100)))
    automation_point(suite, 'master-volume-valley', 'Dip the master volume to 20 and back', 'song', 'mastervol',
                     ((0, 100), (48, 20), (96, 100)))
    automation_point(suite, 'master-volume-late-start', 'Start the master volume automation at tick 96', 'song',
                     'mastervol', ((0, 100), (48, 20)), pos=96)
    automation_point(suite, 'sample-volume-linear', 'Fade the volume of a sample track to 0', 'sample', 'vol',
                     ((0, 100), (96, 0)))
    automation_point(suite, 'sample-volume-discrete', 'Step the volume of a sample track to 0', 'sample', 'vol',
                     ((0, 100), (96, 0)), prog=0)
    automation_point(suite, 'sample-pan-sweep', 'Sweep the panning of a sample track from left to right', 'sample',
                     'pan', ((0, -100), (96, 100)))
    automation_point(suite, 'instrument-volume', 'Fade the volume of an instrument track to 20', 'instrument', 'vol',
                     ((0, 100), (96, 20)))
    automation_point(suite, 'instrument-pan', 'Sweep the panning of an instrument track from left to right',
                     'instrument', 'pan', ((0, -100), (96, 100)))
    automation_point(suite, 'tempo-slowdown', 'Slow the tempo from 140 to 70 beats per minute', 'song', 'bpm',
                     ((0, 140), (96, 70)))
    automation_point(suite, 'tempo-speedup', 'Speed the tempo up from 100 to 200 beats per minute', 'song', 'bpm',
                     ((0, 100), (96, 200)))


def build(suite):
    build_beats(suite)
    build_automation(suite)
