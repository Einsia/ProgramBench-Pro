'''Command line error paths and per-track rendering of the product command line on generated projects.

Every point uploads a generated project document and runs cli render or cli rendertracks on it. The exit status of a
render that succeeds is never scored (a complete render sometimes exits abnormally); a rejected input is observed
through whether a file was written, whether the product printed a message and, where the message names no private
path, its text. A rejection counts only together with the point that shows the same command rendering a valid project.
Per-track rendering returns the names of the files the product wrote and the signal projection of each.
'''
from __future__ import annotations

from pathlib import Path

import projectxml as px
from harness import signal_projection
from semantic import decode_audio

BPM = 140
SEQUENCE = [(i * 48, 48, 57 + 2 * i) for i in range(4)]
VALID = 'backend.cli-error.valid-render.result'
# rendertracks writes a click of a few samples within the first 128 frames of one track file per run, and which file it
# hits differs between runs; the observation of a track file starts after this many frames.
CLICK_FRAMES = 1024


def lead(name='Lead', shift=0, **options):
    def build(ctx):
        notes = [(pos, length, key + shift) for pos, length, key in SEQUENCE]
        return px.instrument_track(name, 'tripleoscillator', notes=notes, **options)
    return build


def drums(name='Kick 01'):
    def build(ctx):
        return px.beat_track(tracks=[px.instrument_track(name, 'kicker', steps=[0, 4, 8, 12])])
    return build


def sampler(name='Sampler'):
    def build(ctx):
        path, _audio = ctx.sample('tone-440')
        return px.sample_track(name=name, clips=[(0, 192, path)])
    return build


def document(ctx, builders):
    project = px.Project(bpm=BPM)
    for build in builders:
        project.add(build(ctx))
    return project.xml()


def plain(ctx):
    return document(ctx, [lead()])


def private(ctx, text):
    # The message without the instance document folder, which differs between the reference and a candidate.
    root = ctx.areas()['inputs'].rsplit('/', 1)[0]
    return text.replace(root, '<files>')


def decode(ctx, data, name):
    ctx.serial += 1
    path = ctx.scratch / 'renders' / ('x%05d%s' % (ctx.serial, Path(name).suffix))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    try:
        return decode_audio(path)
    finally:
        path.unlink(missing_ok=True)


def outcome(ctx, reply, name, message):
    produced = Path(name).name
    # A render that wrote its file is observed by the file alone: whether it also printed text varies between runs.
    value = {'wrote': produced in reply['files']}
    if value['wrote']:
        audio = decode(ctx, reply['files'][produced], produced)
        value.update(sample_rate=audio.sample_rate, channels=audio.channels, frames=audio.frames)
    else:
        value['reported'] = bool(reply['output'].strip())
        value['exit_code'] = reply['exit_code']
        value['message'] = private(ctx, reply['output'].strip())
    return value


def rejection(suite, scenario, description, content=plain, source=None, output=None, message=False, **options):
    def action(ctx):
        name = output(ctx) if callable(output) else output or scenario + '.wav'
        project = source(ctx) if source else ctx.project(scenario + '.mmp', content(ctx))
        return outcome(ctx, ctx.cli('render', project, output=name, **options), name, message)
    suite.add('cli-error', scenario, 'result', action, description=description, requires=(VALID,))


def valid(ctx):
    rendered = ctx.render(document(ctx, [lead()]), 'valid-render')
    assert rendered.audio is not None, 'the render wrote no audio file'
    return {'tol': 'signal', 'slack': 0, 'signal': signal_projection(rendered.audio)}


def interpolation(ctx):
    results = {}
    for method in ('linear', 'sincfastest', 'sincmedium', 'sincbest'):
        name = 'interpolation-' + method + '.wav'
        project = ctx.project('interpolation-' + method + '.mmp', plain(ctx))
        results[method] = outcome(ctx, ctx.cli('render', project, output=name, interpolation=method), name, False)
    return results


def tracks_point(suite, scenario, description, builders):
    def action(ctx):
        project = ctx.project(scenario + '.mmp', document(ctx, builders))
        reply = ctx.cli('rendertracks', project, output='tracks-' + scenario, format='wav')
        rows = {}
        for name, data in sorted(reply['files'].items()):
            audio = decode(ctx, data, name)
            assert audio.frames > 2 * CLICK_FRAMES, 'a track file is too short'
            rows[name] = signal_projection(audio.slice(CLICK_FRAMES, audio.frames))
        assert rows, 'no track file was written'
        return {'tol': 'signal', 'slack': 0, 'signal': rows}
    suite.add('rendertracks', scenario, 'result', action, description=description)


def build(suite):
    suite.add('cli-error', 'valid-render', 'result', valid, description='Render a valid generated project')
    suite.add('cli-error', 'interpolation-modes-accepted', 'result', interpolation,
              description='Render a valid project with each of the four interpolation methods')
    rejection(suite, 'format-flac', 'Render to flac, a format the help text lists but the product rejects', message=True,
              format='flac')
    rejection(suite, 'samplerate-1000', 'Render at a sample rate of 1000 Hz', message=True, samplerate=1000)
    rejection(suite, 'samplerate-22050', 'Render at a sample rate of 22050 Hz', samplerate=22050)
    rejection(suite, 'samplerate-200000', 'Render at a sample rate of 200000 Hz', samplerate=200000)
    rejection(suite, 'oversampling-3', 'Render with an oversampling of 3', message=True, oversampling=3)
    rejection(suite, 'oversampling-16', 'Render with an oversampling of 16', message=True, oversampling=16)
    rejection(suite, 'bitrate-5000-ogg', 'Render Ogg Vorbis at 5000 KBit/s', message=True, format='ogg', bitrate=5000)
    rejection(suite, 'bitrate-1-ogg', 'Render Ogg Vorbis at 1 KBit/s', message=True, format='ogg', bitrate=1)
    rejection(suite, 'output-folder-missing', 'Render into a folder that does not exist',
              output=lambda ctx: ctx.path('outputs', 'nodir/x.wav'))
    rejection(suite, 'empty-project', 'Render a project without any track',
              content=lambda ctx: px.Project().xml())
    rejection(suite, 'project-missing', 'Render a project file that does not exist',
              source=lambda ctx: ctx.path('inputs', 'absent.mmp'))
    rejection(suite, 'project-is-folder', 'Render a folder instead of a project file',
              source=lambda ctx: ctx.areas()['outputs'])
    tracks_point(suite, 'single-track', 'Render the tracks of a project with one instrument track', [lead()])
    tracks_point(suite, 'two-instruments', 'Render the tracks of a project with two instrument tracks',
                 [lead('Lead'), lead('Bass', shift=-12)])
    tracks_point(suite, 'three-tracks', 'Render the tracks of a project with three instrument tracks',
                 [lead('Lead'), lead('Pad', shift=7), lead('Bass', shift=-12)])
    tracks_point(suite, 'name-with-space', 'Render tracks whose names contain a space',
                 [lead('Main Lead'), lead('Low End', shift=-12)])
    tracks_point(suite, 'name-with-ampersand', 'Render a track whose name contains an ampersand', [lead('A & B')])
    tracks_point(suite, 'unicode-name', 'Render a track whose name is not ASCII', [lead('主音 lead')])
    tracks_point(suite, 'instrument-and-beat', 'Render the tracks of a project with a synth and a beat pattern',
                 [lead(), drums()])
    tracks_point(suite, 'muted-track', 'Render the tracks of a project in which one track is muted',
                 [lead(muted=True), lead('Bass', shift=-12)])
    tracks_point(suite, 'sample-and-instrument', 'Render the tracks of a project with a sample track and a synth',
                 [sampler(), lead()])
    tracks_point(suite, 'volume-and-pan', 'Render tracks with a lowered volume and a panning',
                 [lead('Quiet', vol=50), lead('Left', pan=-100)])
