"""Export options of the product command line: file formats, sample depths and rates, playlists and failures.

All rows export the same verifier song (two instruments, two columns) with one option changed and compare the
decoded file, or, for exports the product refuses, the exit status and whether an audio file was written. Lossy
formats compare within a wider tolerance (frame slack for encoder delay, levels within 5 %).
"""
from __future__ import annotations

import songs as S
from render_cases import Render, instrument, upload_samples, notes

LOSSY = {'frames': 4096, 'level': (0.01, 0.06)}
EXACT = {'level': (0.0005, 0.005), 'onsets': 2}


def base_song(ctx):
    return S.Song([instrument(ctx, 'click.wav', 0), instrument(ctx, 'tone440.wav', 1, volume=0.6, pan=-0.3)],
                  [S.Pattern('A', notes(0, 96) + [S.Note(48, instrument=1)]), S.Pattern('B', notes(0, 48, 96, 144))],
                  sequence=[['A'], ['B']])


def add(suite, step, render, description):
    return suite.add('export-options', 'options', step, render, description=description)


def build(suite):
    suite.setup('export-options', 'options', upload_samples, 'Upload the verifier sample library')
    spec = {'onsets': 0.02}
    add(suite, 'wav-default', Render(base_song, spec=spec, tolerance=EXACT),
        'Export the reference song to WAV with the default options')
    for bits in (8, 24, 32):
        add(suite, f'wav-{bits}-bit', Render(base_song, options={'bits': bits}, spec=spec, tolerance=EXACT),
            f'Export the reference song to a {bits}-bit WAV file')
    suite.add('export-options', 'options', 'wav-unsupported-depth',
              Render(base_song, options={'bits': 12}, spec=spec, tolerance=EXACT),
              description='Export to WAV with a sample depth of 12 bits, which the format does not offer',
              requires=('backend.export-options.options.wav-default',))
    for rate in (8000, 22050, 32000, 48000, 88200, 96000, 192000):
        add(suite, f'wav-rate-{rate}', Render(base_song, options={'rate': rate}, spec=spec),
            f'Export the reference song at {rate} Hz')
    add(suite, 'wav-rate-unusual', Render(base_song, options={'rate': 1000}, spec={}),
        'Export the reference song at a sample rate of 1000 Hz')
    for suffix in ('.aiff', '.au', '.caf', '.w64', '.voc'):
        add(suite, 'format' + suffix.replace('.', '-'), Render(base_song, suffix=suffix, spec=spec, tolerance=EXACT),
            f'Export the reference song to a {suffix} file')
    add(suite, 'flac-16', Render(base_song, suffix='.flac', spec=spec, tolerance=EXACT),
        'Export the reference song to FLAC')
    add(suite, 'flac-24', Render(base_song, suffix='.flac', options={'bits': 24}, spec=spec, tolerance=EXACT),
        'Export the reference song to 24-bit FLAC')
    add(suite, 'flac-48k', Render(base_song, suffix='.flac', options={'rate': 48000}, spec=spec),
        'Export the reference song to FLAC at 48000 Hz')
    add(suite, 'ogg', Render(base_song, suffix='.ogg', spec={}, tolerance=LOSSY),
        'Export the reference song to Ogg Vorbis')
    add(suite, 'ogg-low-quality', Render(base_song, suffix='.ogg', options={'compression_level': 1.0}, spec={},
                                         tolerance={'frames': 4096, 'level': (0.03, 0.15)}),
        'Export to Ogg Vorbis with the highest compression level')
    add(suite, 'mp3', Render(base_song, suffix='.mp3', spec={}, tolerance=LOSSY),
        'Export the reference song to MP3')
    add(suite, 'opus-48k', Render(base_song, suffix='.opus', options={'rate': 48000}, spec={},
                                  tolerance=dict(LOSSY, frames=8192)),
        'Export the reference song to Opus at 48000 Hz')
    positive = 'backend.export-options.options.wav-default'
    for step, suffix, description in (
            ('opus-44k', '.opus', 'Export to Opus at 44100 Hz, a rate the format does not offer'),
            ('unknown-suffix', '.xyz', 'Export to a file name with an unknown suffix'),
            ('aif-suffix', '.aif', 'Export to a file name with the suffix .aif')):
        suite.add('export-options', 'options', step, Render(base_song, suffix=suffix, expect_file=False),
                  description=description, requires=(positive,))
    for rate in (11025, 16000, 24000, 64000, 176400):
        add(suite, f'wav-rate-{rate}', Render(base_song, options={'rate': rate}, spec=spec),
            f'Export the reference song at {rate} Hz')
    for suffix, bits in (('.aiff', 24), ('.aiff', 8), ('.au', 32), ('.caf', 24), ('.w64', 24)):
        add(suite, f'format{suffix.replace(".", "-")}-{bits}-bit', Render(base_song, suffix=suffix, options={'bits': bits},
                                                                          spec=spec, tolerance=EXACT),
            f'Export the reference song to a {bits}-bit {suffix} file')
    # (16 bits is the default depth of these formats: those exports equal the format rows above.)
    for suffix, bits in (('.aiff', 32), ('.au', 8), ('.au', 24), ('.caf', 8), ('.caf', 32), ('.w64', 8),
                         ('.w64', 32), ('.flac', 8)):
        add(suite, f'format{suffix.replace(".", "-")}-{bits}-bit-depth',
            Render(base_song, suffix=suffix, options={'bits': bits}, spec=spec, tolerance=EXACT),
            f'Export the reference song to a {suffix} file with {bits}-bit samples')
    for suffix, rate in (('.flac', 22050), ('.flac', 96000), ('.ogg', 48000), ('.ogg', 22050), ('.aiff', 48000)):
        lossy = suffix == '.ogg'
        add(suite, f'format{suffix.replace(".", "-")}-rate-{rate}',
            Render(base_song, suffix=suffix, options={'rate': rate}, spec={} if lossy else spec,
                   tolerance=LOSSY if lossy else None),
            f'Export the reference song to a {suffix} file at {rate} Hz')
    for level in (1.0,):
        add(suite, f'mp3-compression-{level:g}', Render(base_song, suffix='.mp3', options={'compression_level': level},
                                                        spec={}, tolerance=LOSSY),
            f'Export the reference song to MP3 with compression level {level:g}')
    add(suite, 'opus-compression-1', Render(base_song, suffix='.opus', options={'rate': 48000, 'compression_level': 1.0},
                                            spec={}, tolerance=dict(LOSSY, frames=8192)),
        'Export the reference song to Opus at 48000 Hz with compression level 1')
    kit_positive = add(suite, 'kit-override', Render(base_song, options={'kit': 'TR808EmulationKit'}, spec=spec),
                       'Export the reference song with the drum kit TR808EmulationKit loaded for the export (-k)')
    suite.add('export-options', 'options', 'kit-override-unknown',
              Render(base_song, options={'kit': 'No Such Kit'}, spec=spec),
              description='Export the reference song with an unknown drum kit name for -k', requires=(kit_positive,))
    add(suite, 'interpolation-out-of-range', Render(
        lambda ctx: S.Song([instrument(ctx, 'square110.wav')], [S.Pattern('P', notes(0, key='G0'))]),
        options={'interpolation': 9}, spec={'excerpt': (2000, 300)}),
        'Export a pitched square wave with an interpolation mode outside 0-4')

    def written(ctx, reply):
        files = [d for d in reply.get('downloads', []) if d.get('size')]
        if not files:
            return {'exit_code': reply['exit_code'], 'audio_written': False}
        info, frames = ctx.decode(ctx.take(files[0]['path'], files), files[0]['filename'])
        return {'exit_code': reply['exit_code'], 'audio_written': True, 'frames': int(frames.shape[0]),
                'silent': bool(abs(frames).max() < 1e-4)}

    def missing_song(ctx):
        return written(ctx, ctx.cli('export', song='no-such-song.h2song', output=ctx.unique('missing', '.wav')))
    suite.add('export-options', 'options', 'missing-song', missing_song, requires=(positive,),
              description='Export a song document that does not exist')

    def broken_song(ctx):
        name = ctx.upload('broken.h2song', '<?xml version="1.0"?>\n<song><bpm>99</bpm>\n')
        return written(ctx, ctx.cli('export', song=name, output=ctx.unique('broken', '.wav')))
    suite.add('export-options', 'options', 'malformed-song', broken_song, requires=(positive,),
              description='Export a song document that is not well-formed XML')

    def playlist(ctx, relative=False):
        first = S.Song([instrument(ctx, 'tone660.wav')], [S.Pattern('A', notes(0, 96))], name='First')
        second = S.Song([instrument(ctx, 'click.wav')], [S.Pattern('A', notes(0, 48, 96, 144))], name='Second')
        ctx.upload('pl-first.h2song', first.xml())
        ctx.upload('pl-second.h2song', second.xml())
        paths = ['pl-first.h2song', 'pl-second.h2song'] if relative else \
            [ctx.inputs('pl-first.h2song'), ctx.inputs('pl-second.h2song')]
        name = ctx.upload('list-relative.h2playlist' if relative else 'list.h2playlist', S.playlist(paths))
        stem = ctx.unique('playlist', '')
        reply = ctx.cli('export', playlist=name, output=stem + '.wav')
        data = ctx.take('outputs/' + stem + '.wav', reply.get('downloads'))
        info, frames = ctx.decode(data, stem + '.wav')
        from harness import audio_observation
        return audio_observation(info, frames, {'pitch': (0.02, 0.3), 'onsets': 0.02})
    suite.add('export-options', 'options', 'playlist', playlist,
              description='Export with a playlist of two songs instead of a song')
    suite.add('export-options', 'options', 'playlist-relative', lambda ctx: playlist(ctx, True),
              description='Export with a playlist whose song paths are relative to the playlist')

    def first_lines(action, count):
        def run(ctx):
            reply = ctx.cli(action)
            # The usage line names the program's own location, which differs between installations.
            from drumkit_cases import without_log
            lines = [line.rstrip() for line in without_log(reply['output']).splitlines()
                     if line.strip() and not line.startswith('Usage:')]
            return {'exit_code': reply['exit_code'], 'lines': lines[:count]}
        return run
    suite.add('export-options', 'options', 'version', first_lines('version', 3),
              description='Run the command line with --version; read the exit status and the first lines it prints')
    suite.add('export-options', 'options', 'help', first_lines('help', 12),
              description='Run the command line with --help; read the exit status and the first lines it prints')
