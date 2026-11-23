"""Audible sample transformations using the pinned product's built-in Rubber Band library."""
import songs as S
from render_cases import Render, instrument, layer, upload_samples


def build(suite):
    suite.setup('render-stretch', 'stretch', upload_samples, 'Upload deterministic tones and transients')
    # Each row changes an audible aspect: duration independent of pitch, transposition independent of duration,
    # tempo-relative stretching, or transient processing. These are not merely XML round trips.
    cases = (
        ('half-beat', 'tone440.wav', 0.5, 0, 4, 120),
        ('two-beats', 'tone440.wav', 2, 0, 4, 120),
        ('four-beats', 'tone440.wav', 4, 0, 4, 120),
        ('octave-up', 'tone440.wav', 1, 12, 4, 120),
        ('octave-down', 'tone440.wav', 1, -12, 4, 120),
        ('fifth-long', 'tone440.wav', 2, 7, 4, 120),
        ('fine-pitch', 'tone440.wav', 1, 0.5, 4, 120),
        ('slow-tempo', 'tone440.wav', 1, 0, 4, 75),
        ('fast-tempo', 'tone440.wav', 1, 0, 4, 180),
        ('soft-transient', 'click.wav', 1, 0, 0, 120),
        ('crisp-transient', 'click.wav', 1, 0, 5, 120),
        ('pitched-transient', 'click.wav', 0.5, -7, 4, 120),
        ('chord-long', 'pad.wav', 4, 5, 4, 120),
        ('noise-short', 'snare.wav', 0.25, 0, 4, 120),
    )
    for label, sample, beats, pitch, crispness, bpm in cases:
        def document(ctx, sample=sample, beats=beats, pitch=pitch, crispness=crispness, bpm=bpm):
            # A layer's end frame is the original sample length, before stretching.
            from fixtures import sample as sample_bytes
            info, frames = ctx.decode(sample_bytes(sample), sample)
            voice = instrument(ctx, '', layers=[layer(ctx, sample, modified=True, endframe=len(frames),
                                                       rubber=1, rubberdivider=beats, rubberpitch=pitch,
                                                       rubbersettings=crispness)])
            return S.Song([voice], [S.Pattern('Transform', [S.Note(0)])], bpm=bpm)
        suite.add('render-stretch', 'stretch', label,
                  Render(document, spec={'window': 2205, 'pitch': (0.05, 0.2), 'bands': True, 'onsets': 0.02},
                         tolerance={'frames': 1024, 'level': (0.012, 0.08), 'onsets': 220, 'bands': 0.05}),
                  description=f'Render {sample} stretched to {beats:g} beats at {bpm:g} BPM, pitch {pitch:g} '
                              f'semitones and crispness {crispness}; compare its duration, envelope and spectrum')
