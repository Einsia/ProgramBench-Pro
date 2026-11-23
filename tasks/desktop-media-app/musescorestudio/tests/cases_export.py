'''Program cases: audio renderings and refused runs of the product command line.

Audio scenarios render one fixture in every sound format and compare the decoded audio as music (format facts exactly; length, onsets, pitches per note and relative levels within the rules of semantic.audio_compare). Error scenarios drive the command line into each failure the converter reports and observe the exit status plus the kinds of files left behind. No scenario needs setup: a fixture is uploaded on first use.
'''
import fixtures

CATALOG = fixtures.catalog()
AUDIO = ('scale-c.musicxml', 'rhythms.musicxml', 'dynamics-tempo.musicxml', 'two-parts.musicxml', 'repeats.musicxml',
         'ties.musicxml', 'melody.mid', 'two-track.mid', 'tempo-change.mid', 'waltz.mid')
SOUNDS = (('wav', '.wav', 'WAV'), ('flac', '.flac', 'FLAC'), ('ogg', '.ogg', 'Ogg Opus'), ('mp3', '.mp3', 'MP3'))
SOURCE = 'scale-c.musicxml'
assert all(name in CATALOG for name in AUDIO + (SOURCE,)), 'unknown fixture in cases_export'


def sound_action(fixture, suffix):
    def action(ctx):
        _reply, data = ctx.produce(ctx.fixture(fixture), suffix)
        return ctx.audio('audio' + suffix, data)
    return action


def damaged(ctx):
    if 'damaged.mscz' not in ctx.uploaded:
        ctx.document('damaged.mscz', b'this is not a project archive')
    return 'damaged.mscz'


def missing_input(ctx):
    return ctx.refusal(ctx.convert('absent.musicxml', '-o', ctx.name('absent', '.mid')))


def unknown_suffix(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '-o', ctx.name('score', '.xyz')))


def no_suffix(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '-o', ctx.name('score', '')))


def missing_folder(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '-o', ctx.area('outputs') + '/absent-folder/score.mid'))


def damaged_project(ctx):
    return ctx.refusal(ctx.convert(damaged(ctx), '-o', ctx.name('damaged', '.mid')))


def damaged_project_meta(ctx):
    return ctx.refusal(ctx.convert(damaged(ctx), '--score-meta'))


def empty_transpose(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '--transpose', '{}', '-o', ctx.name('score', '.mid')))


def empty_score_transpose(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '--score-transpose', '{}'))


def page_beyond_end(ctx):
    return ctx.refusal(ctx.convert(ctx.fixture(SOURCE), '-r', '72', '--page', '5', '-o', ctx.name('score', '.png')))


COMPANION = 'backend.errors.baseline.meta'


def baseline(ctx):
    return ctx.stdout_projection('meta', ctx.convert(ctx.fixture(SOURCE), '--score-meta'))


ERRORS = (
    ('missing-input', 'A document that does not exist is refused with the recorded exit status and leaves no file', missing_input),
    ('unknown-suffix', 'An output name with an unknown suffix is refused with the recorded exit status', unknown_suffix),
    ('no-suffix', 'An output name without a suffix is refused with the recorded exit status', no_suffix),
    ('missing-folder', 'An output in a folder that does not exist is refused with the recorded exit status', missing_folder),
    ('damaged-project', 'A damaged project archive is refused on export with the recorded exit status', damaged_project),
    ('damaged-project-meta', 'A damaged project archive is refused by the metadata listing with the recorded exit status', damaged_project_meta),
    ('empty-transpose', 'An empty transposition option is refused with the recorded exit status', empty_transpose),
    ('empty-score-transpose', 'An empty score transposition option is refused with the recorded exit status', empty_score_transpose),
    ('page-beyond-end', 'Asking for a page past the end of the score ends as recorded and leaves the recorded kinds of files', page_beyond_end),
)


def build(suite):
    for fixture in AUDIO:
        stem, _dot, kind = fixture.rpartition('.')
        source = 'MusicXML' if kind == 'musicxml' else 'MIDI'
        for step, suffix, label in SOUNDS:
            suite.add('audio', stem, step, sound_action(fixture, suffix),
                      description='The ' + source + ' fixture ' + stem + ' rendered as ' + label + ' sounds as recorded')
    suite.add('errors', 'baseline', 'meta', baseline,
              description='The fixture scale-c read directly by the metadata listing reports the recorded metadata')
    for step, description, run in ERRORS:
        suite.add('errors', step, 'refused', run, description=description, requires=(COMPANION,))
