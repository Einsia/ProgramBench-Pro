'''Sample-track coverage of the product command line on generated projects.

Every point renders one generated project that plays verifier-made samples through cli render and decodes the written
file with the verifier FFmpeg. The exit status never decides; the written file does. A point returns its tolerance
class (linear: sample playback within a few LSB; signal: resampled content) and the signal projection of the render
(format, length, level per channel, level per window and spectrum), so position, length, volume, panning,
tempo and mixing each change the observation.
'''
from __future__ import annotations

import projectxml as px
from harness import signal_projection

BPM = 140
TICKS = 192
SAMPLES = ('tone-440', 'tone-880', 'square-220', 'ramp', 'impulse', 'stereo-pair', 'rate-48000', 'rate-22050')
RESAMPLED = ('rate-48000', 'rate-22050')


def signed(value):
    return ('minus-' if value < 0 else '') + str(abs(value))


def clip(key, pos=0, length=TICKS, muted=0):
    return (pos, length, key, muted)


def track(*clips, **options):
    return dict(clips=list(clips), **options)


def project(ctx, tracks, **settings):
    result = px.Project(**{'bpm': BPM, **settings})
    for spec in tracks:
        clips = [(pos, length, ctx.sample(key)[0], *flags) for pos, length, key, *flags in spec['clips']]
        result.add(px.sample_track(clips=clips, **{k: v for k, v in spec.items() if k != 'clips'}))
    return result.xml()


def point(suite, scenario, description, tracks, tol='linear', requires=(), **settings):
    def action(ctx):
        rendered = ctx.render(project(ctx, tracks, **settings), 'sample-' + scenario)
        assert rendered.audio is not None, 'the render wrote no audio file'
        return {'tol': tol, 'slack': 0, 'signal': signal_projection(rendered.audio)}
    suite.add('sample-clip', scenario, 'render', action, description=description, requires=requires)


def build(suite):
    for key in SAMPLES:
        # The 22050 Hz sample holds the same 330 Hz tone as the 48000 Hz one, so it is cut to 96 ticks to differ from it.
        length = 96 if key == 'rate-22050' else TICKS
        point(suite, 'play-' + key, f'Render one clip of the {key} sample from the start of the song', [track(clip(key, length=length))],
              tol='signal' if key in RESAMPLED else 'linear')
    for pos in (24, 48, 96, 192, 384):
        point(suite, f'position-{pos}', f'Start the tone-440 clip at tick {pos}', [track(clip('tone-440', pos=pos))])
    for length in (12, 24, 48, 96):
        point(suite, f'length-{length}', f'Cut the tone-440 clip to {length} ticks',
              [track(clip('tone-440', length=length))])
    for vol in (0, 25, 50, 150, 200):
        point(suite, f'track-volume-{vol}', f'Set the volume of the sample track to {vol}',
              [track(clip('tone-440'), vol=vol)])
    for pan in (-100, -50, 50, 100):
        point(suite, f'track-pan-{signed(pan)}', f'Set the panning of the sample track to {pan}',
              [track(clip('tone-440'), pan=pan)])
    for pan in (-100, 100):
        point(suite, f'stereo-sample-pan-{signed(pan)}', f'Pan the stereo sample track to {pan}',
              [track(clip('stereo-pair'), pan=pan)])
    for key in ('tone-440', 'stereo-pair'):
        for vol in (50, 150):
            for pan in (-50, 50):
                point(suite, f'{key}-volume-{vol}-pan-{signed(pan)}',
                      f'Play the {key} track at volume {vol} and panning {pan}', [track(clip(key), vol=vol, pan=pan)])
    point(suite, 'mute-track', 'Mute one of two sample tracks', [track(clip('tone-440'), muted=1), track(clip('tone-880'))],
          requires=('backend.sample-clip.play-tone-880.render',))
    point(suite, 'mute-clip', 'Mute the first of two clips of one track',
          [track(clip('tone-440', muted=1), clip('tone-880', pos=96))])
    point(suite, 'mix-two-tracks', 'Mix two sample tracks', [track(clip('tone-440')), track(clip('tone-880'))])
    point(suite, 'mix-three-tracks', 'Mix three sample tracks',
          [track(clip('tone-440')), track(clip('tone-880')), track(clip('square-220'))])
    point(suite, 'sequence-one-track', 'Play three different clips one after the other on one track',
          [track(clip('tone-440', length=96), clip('tone-880', pos=96, length=96), clip('square-220', pos=192, length=96))])
    point(suite, 'overlap-one-track', 'Overlap two clips of one track', [track(clip('tone-440'), clip('tone-880', pos=48))])
    for bpm in (60, 90, 200):
        point(suite, f'tempo-{bpm}', f'Render the clip at {bpm} beats per minute', [track(clip('tone-440'))], bpm=bpm)
    # Not the track volume values: on a single track a master volume acts like the volume of that track.
    for volume in (35, 85, 135):
        point(suite, f'master-volume-{volume}', f'Set the master volume to {volume}', [track(clip('tone-440'))],
              mastervol=volume)
    point(suite, 'master-pitch-12', 'A master pitch of 12 does not change a sample clip', [track(clip('tone-440'))],
          masterpitch=12,
          requires=('backend.sample-clip.play-tone-440.render',))
