'''Program cases: MNX and lyrics exports and the re-import of the product's own interchange files.

MNX: every fixture (MusicXML and MIDI) exported as MNX (JSON; semantic.mnx_project renumbers the identifiers the product draws at random).
Lyrics: the fixtures with lyrics exported as LRC. Re-import: the product writes a fixture as MEI, MNX or compressed
MusicXML (setup), then reads that file back as MusicXML (scored). Only the fixtures whose re-import differs from their
direct import are scored (REIMPORT, measured on the standard), so no observation repeats one of cases_import.
'''
from harness import MissingDependency
import fixtures

CATALOG = fixtures.catalog()
LYRICS = ('lyrics.musicxml', 'lyrics-verses.musicxml', 'lyrics-melisma.musicxml')
# Measured on the pinned standard: the fixtures whose re-import through these formats differs from the direct import.
REIMPORT = {'c-minor-eighths.musicxml': ('.mei', '.mnx'), 'chord-symbols.musicxml': ('.mei', '.mnx'),
            'dynamics-tempo.musicxml': ('.mnx',), 'lyrics-melisma.musicxml': ('.mnx',),
            'slurs-hairpins.musicxml': ('.mnx',), 'titled.musicxml': ('.mnx',), 'unicode-title.musicxml': ('.mnx',),
            'segno-coda.musicxml': ('.mnx', '.mxl')}
LABELS = {'.mei': 'MEI', '.mnx': 'MNX', '.mxl': 'compressed MusicXML'}
assert all(name in CATALOG for name in LYRICS + tuple(REIMPORT))


def exported(fixture, suffix):
    def action(ctx):
        _reply, data = ctx.produce(ctx.fixture(fixture), suffix)
        return ctx.project('x' + suffix, data)
    return action


def interchange(fixture, suffix):
    '''Setup: the product writes the fixture in an interchange format into the output area.'''
    def action(ctx):
        ctx.new_scenario(fixture + suffix)
        out = ctx.name(fixture.rpartition('.')[0] + '-interchange', suffix)
        reply = ctx.convert(ctx.fixture(fixture), '-o', out)
        assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
        ctx.take('outputs/' + out, reply)
        ctx.state['written'] = ctx.area('outputs') + '/' + out
        return {'written': True}
    return action


def needs(fixture, suffix):
    def check(ctx):
        if ctx.state.get('scenario') != fixture + suffix or 'written' not in ctx.state.keys():
            raise MissingDependency('the interchange file of ' + fixture + ' was not written')
    return check


def reimported(ctx):
    _reply, data = ctx.produce(ctx.state['written'], '.musicxml')
    return ctx.project('x.musicxml', data)


def build(suite):
    for fixture in sorted(CATALOG):
        stem, _dot, kind = fixture.rpartition('.')
        source = 'MusicXML' if kind == 'musicxml' else 'MIDI'
        suite.add('format-mnx', stem, 'export', exported(fixture, '.mnx'),
                  description='The ' + source + ' fixture ' + stem + ' exported as MNX has the recorded content')
    for fixture in LYRICS:
        stem = fixture.rpartition('.')[0]
        suite.add('format-lrc', stem, 'export', exported(fixture, '.lrc'),
                  description='The MusicXML fixture ' + stem + ' exported as LRC lyrics has the recorded timed lines')
    for fixture, suffixes in REIMPORT.items():
        stem = fixture.rpartition('.')[0]
        for suffix in suffixes:
            label = LABELS[suffix]
            suite.add('format-reimport', stem + '-' + suffix[1:], 'write', interchange(fixture, suffix), channel='setup',
                      description='The product writes the fixture ' + stem + ' as ' + label)
            suite.add('format-reimport', stem + '-' + suffix[1:], 'read-back', reimported, needs=needs(fixture, suffix),
                      description='The fixture ' + stem + ' written by the product as ' + label
                      + ' and read back has the recorded MusicXML')
