'''Render-option coverage of the product command line on generated projects.

Each point renders one generated project with one option through cli render and decodes the written file with the
verifier FFmpeg. The exit status never decides (a complete render sometimes exits abnormally); the written file does.
Projects come from projectxml (no factory file) and verifier-made samples uploaded to the input area. A point returns
its tolerance class: linear (sample playback, a few LSB), signal (synthesized or resampled content: window levels and
spectrum within a few percent) or lossy (encoder delay and padding allowed).
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
RATES = (48000, 88200, 96000, 192000)
OVERSAMPLING = (1, 4, 8)
INTERPOLATION = ('linear', 'sincmedium', 'sincbest')
OGG_BITRATES = (64, 128)
MP3_BITRATES = (64, 128)
STEREO_MODES = ('m',)
LOSSY_SLACK = 4608


def clip_xml(ctx):
    path, _audio = ctx.sample('tone-440')
    project = px.Project(bpm=BPM)
    project.add(px.sample_track(clips=[(0, 192, path)]))
    return project.xml()


def resampled_xml(ctx):
    path, _audio = ctx.sample('rate-48000')
    project = px.Project(bpm=BPM)
    project.add(px.sample_track(clips=[(0, 192, path)]))
    return project.xml()


def notes_xml(ctx):
    project = px.Project(bpm=BPM)
    project.add(px.instrument_track('Lead', 'tripleoscillator', notes=SEQUENCE))
    return project.xml()


def both_xml(ctx):
    path, _audio = ctx.sample('tone-440')
    project = px.Project(bpm=BPM)
    project.add(px.sample_track(clips=[(0, 192, path)]))
    project.add(px.instrument_track('Lead', 'tripleoscillator', notes=SEQUENCE))
    return project.xml()


def highrate_xml(ctx):
    path, _audio = ctx.sample('rate-48000-high')
    project = px.Project(bpm=BPM)
    project.add(px.sample_track(clips=[(0, 192, path)]))
    return project.xml()


FIXTURES = {'clip': clip_xml, 'resampled': resampled_xml, 'notes': notes_xml, 'both': both_xml,
            'highrate': highrate_xml}


def point(suite, fixture, label, description, fmt='wav', tol='linear', slack=0, **options):
    scenario = fixture + '-' + label

    def action(ctx):
        rendered = ctx.render(FIXTURES[fixture](ctx), scenario, fmt=fmt, **options)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': tol, 'slack': slack, 'signal': signal_projection(rendered.audio)}
    suite.add('render-opt', scenario, 'render', action, description=description)


def build(suite):
    for fixture, tol in (('clip', 'linear'), ('resampled', 'signal'), ('notes', 'signal'), ('both', 'signal')):
        point(suite, fixture, 'default', f'Render the {fixture} project with the default options', tol=tol)
        point(suite, fixture, 'float', f'Render the {fixture} project with 32 bit float depth', tol=tol, float=True)
        for rate in RATES:
            point(suite, fixture, f'rate-{rate}', f'Render the {fixture} project at {rate} Hz', tol=tol, slack=64,
                  samplerate=rate)
        for factor in OVERSAMPLING:
            if factor == 4 and fixture in ('clip', 'resampled'):
                continue
            point(suite, fixture, f'oversampling-{factor}', f'Render the {fixture} project with oversampling {factor}',
                  tol=tol, slack=16, oversampling=factor)
        point(suite, fixture, 'loop', f'Render the {fixture} project as a loop', tol=tol, slack=128, loop=True)
    for fixture in ('clip', 'both'):
        for rate in (OGG_BITRATES if fixture == 'clip' else (128,)):
            point(suite, fixture, f'ogg-{rate}', f'Render the {fixture} project as Ogg Vorbis at {rate} KBit/s', fmt='ogg',
                  tol='lossy', slack=LOSSY_SLACK, bitrate=rate)
        for rate in MP3_BITRATES:
            point(suite, fixture, f'mp3-{rate}', f'Render the {fixture} project as MP3 at {rate} KBit/s', fmt='mp3',
                  tol='lossy', slack=LOSSY_SLACK, bitrate=rate)
        for mode in STEREO_MODES:
            point(suite, fixture, f'mp3-128-{mode}', f'Render the {fixture} project as MP3 in stereo mode {mode}',
                  fmt='mp3', tol='lossy', slack=LOSSY_SLACK, bitrate=128, stereo_mode=mode)
    point(suite, 'highrate', 'default', 'Render a 10 kHz sample of 48 kHz at 44.1 kHz with the default interpolation',
          tol='signal')
