'''Program cases: the transposition options of the product command line.

Each scenario transposes one fixture with one option set and observes what the product writes: the MusicXML or MIDI export of --transpose, or the score and page structure carried by the standard output of --score-transpose. Invalid option sets are refused with the converter exit status. No expected value is written here: every observation is recorded from the pinned standard answer.

Every matrix owns its base fixture so that no two points share an observation: intervals run on scale-c, diatonic steps on scale-g-34 (a key with a sharp, so the key-aware steps show), target keys on bass-clef (a score in C, so a target key never repeats an interval point of scale-c), and the option and fixture matrices stay off those bases. With a source key of C, the closest octave equals the upward or the downward result for every target but the unison, so the closest points stand in for the upward or downward point they would repeat.
'''
import json
import fixtures

CATALOG = fixtures.catalog()
SOURCE = 'scale-c.musicxml'
DIATONIC = 'scale-g-34.musicxml'
KEYED = 'bass-clef.musicxml'
XML = sorted(name for name in CATALOG if name.endswith('.musicxml'))
MID = sorted(name for name in CATALOG if name.endswith('.mid'))
INTERVALS = (
    'perfect unison', 'augmented unison', 'diminished second', 'minor second', 'major second', 'augmented second',
    'diminished third', 'minor third', 'major third', 'augmented third', 'diminished fourth', 'perfect fourth',
    'augmented fourth', 'diminished fifth', 'perfect fifth', 'augmented fifth', 'diminished sixth', 'minor sixth',
    'major sixth', 'augmented sixth', 'diminished seventh', 'minor seventh', 'major seventh', 'augmented seventh',
    'diminished octave', 'perfect octave')
KEYS = {-7: 'C flat', -6: 'G flat', -5: 'D flat', -4: 'A flat', -3: 'E flat', -2: 'B flat', -1: 'F', 0: 'C', 1: 'G',
        2: 'D', 3: 'A', 4: 'E', 5: 'B', 6: 'F sharp', 7: 'C sharp'}
WORDS = {'up': 'upward', 'down': 'downward', 'closest': 'to the closest octave'}
COVERED = (SOURCE, DIATONIC, KEYED, 'c-minor-eighths.musicxml', 'accidentals.musicxml')
ROSTER = tuple(name for name in XML + MID if name not in COVERED)
# Closest repeats up at -1 and 6 and down at 1 (measured on a score in C); those up and down points are left out.
KEY_POINTS = (tuple(('up', target) for target in range(-7, 8) if target not in (-1, 6))
              + tuple(('down', target) for target in range(-7, 8) if target != 1)
              # Target 0 (closest = the unmodified score) repeats the import point of the same score, so it is not scored.
              + tuple(('closest', target) for target in (-1, 1, 6)))
FIXTURE_SETS = (('p5-up', 'a perfect fifth up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 14}),
                ('m3-down', 'a major third down', {'mode': 'by_interval', 'direction': 'down', 'transposeInterval': 8}),
                ('key-eb', 'to E flat major (to the closest octave)', {'mode': 'to_key', 'direction': 'closest', 'targetKey': -3}))
MIDI_EXPORT = ('scale-c.musicxml', 'rhythms.musicxml', 'ties.musicxml', 'tuplets.musicxml', 'two-parts.musicxml',
               'chords.musicxml', 'melody.mid', 'two-track.mid')
KEY_FIXTURES = ('c-minor-eighths.musicxml', 'scale-g-34.musicxml')
KEY_SETS = (('M2-up', 'a major second up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 4}),
            ('p5-down', 'a perfect fifth down', {'mode': 'by_interval', 'direction': 'down', 'transposeInterval': 14}),
            ('key-d', 'to D major (upward)', {'mode': 'to_key', 'direction': 'up', 'targetKey': 2}),
            ('key-bb', 'to B flat major (to the closest octave)', {'mode': 'to_key', 'direction': 'closest', 'targetKey': -2}))
SHARP_FIXTURE = 'accidentals.musicxml'
SHARP_SETS = (('p5-up', 'a perfect fifth up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 14}),
              ('m3-up', 'a major third up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 8}),
              ('m2-down', 'a minor second down', {'mode': 'by_interval', 'direction': 'down', 'transposeInterval': 3}),
              ('M2-up', 'a major second up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 4}),
              ('key-b', 'to B major (upward)', {'mode': 'to_key', 'direction': 'up', 'targetKey': 5}))
SCORE_FIXTURES = ('scale-c.musicxml', 'accidentals.musicxml', 'c-minor-eighths.musicxml', 'two-parts.musicxml')
SCORE_SETS = (('p5-up', 'a perfect fifth up', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 14}),
              ('m3-down-keys', 'a major third down with its key signature', {'mode': 'by_interval', 'direction': 'down', 'transposeInterval': 8, 'transposeKeySignatures': True}),
              ('key-d-keys', 'to D major (upward) with its key signature', {'mode': 'to_key', 'direction': 'up', 'targetKey': 2, 'transposeKeySignatures': True}),
              ('diatonic-down', 'diatonically downward with interval number 3', {'mode': 'diatonically', 'direction': 'down', 'transposeInterval': 3}))
REFUSED = (('bad-mode', {'mode': 'sideways', 'direction': 'up', 'transposeInterval': 4}, 'an unknown mode'),
           ('bad-direction', {'mode': 'by_interval', 'direction': 'left', 'transposeInterval': 4}, 'an unknown direction'),
           ('interval-26', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 26}, 'an interval number past the table'),
           ('interval-negative', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': -1}, 'a negative interval number'),
           ('interval-missing', {'mode': 'by_interval', 'direction': 'up'}, 'no interval number'),
           ('diatonic-26', {'mode': 'diatonically', 'direction': 'up', 'transposeInterval': 26}, 'a diatonic interval number past the table'),
           ('key-8', {'mode': 'to_key', 'direction': 'up', 'targetKey': 8}, 'a target key above C sharp major'),
           ('key-below', {'mode': 'to_key', 'direction': 'up', 'targetKey': -8}, 'a target key below C flat major'),
           ('key-missing', {'mode': 'to_key', 'direction': 'up'}, 'no target key'),
           ('list', '[]', 'a list instead of an object'))
# Both options share one validator, so the score transposition gets other invalid values (types and missing keys).
SCORE_REFUSED = (('interval-string', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': '4'}, 'an interval number given as a string'),
                 ('interval-float', {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 4.5}, 'a fractional interval number'),
                 ('mode-number', {'mode': 4, 'direction': 'up', 'transposeInterval': 4}, 'a number as mode'),
                 ('mode-empty', {'mode': '', 'direction': 'up', 'transposeInterval': 4}, 'an empty mode'),
                 ('mode-missing', {'direction': 'up', 'transposeInterval': 4}, 'no mode'),
                 ('direction-number', {'mode': 'by_interval', 'direction': 1, 'transposeInterval': 4}, 'a number as direction'),
                 ('direction-missing', {'mode': 'by_interval', 'transposeInterval': 4}, 'no direction'),
                 ('diatonic-negative', {'mode': 'diatonically', 'direction': 'up', 'transposeInterval': -2}, 'a negative diatonic interval number'),
                 ('key-string', {'mode': 'to_key', 'direction': 'up', 'targetKey': '2'}, 'a target key given as a string'),
                 ('key-float', {'mode': 'to_key', 'direction': 'up', 'targetKey': 2.5}, 'a fractional target key'))
# Option sets the product accepts although they are unusual; fixtures that no other matrix transposes this way.
LENIENT = (('two-voices.musicxml', 'closest-interval', 'by interval a major second to the closest octave',
            {'mode': 'by_interval', 'direction': 'closest', 'transposeInterval': 4}),
           ('grace-notes.musicxml', 'extra-field', 'a major second up with an unknown extra option',
            {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 4, 'extra': 1}))
assert len(INTERVALS) == 26 and len(KEYS) == 15 and len(KEY_POINTS) == 30
assert all(name in CATALOG for name in MIDI_EXPORT + KEY_FIXTURES + SCORE_FIXTURES + COVERED + tuple(f for f, *_ in LENIENT))


def text(options):
    return options if isinstance(options, str) else json.dumps(options, sort_keys=True)


def with_keys(options):
    return dict(options, transposeKeySignatures=True)


def transposed(fixture, options, suffix='.musicxml'):
    def action(ctx):
        _reply, data = ctx.produce(ctx.fixture(fixture), suffix, '--transpose', text(options))
        return ctx.project('x' + suffix, data)
    return action


def transposed_score(fixture, options):
    def action(ctx):
        return ctx.stdout_projection('transposed', ctx.convert(ctx.fixture(fixture), '--score-transpose', text(options)))
    return action


def refused(option, options):
    def action(ctx):
        args = [ctx.fixture(SOURCE), option, text(options)]
        if option == '--transpose':
            args += ['-o', ctx.name('score', '.mid')]
        return ctx.refusal(ctx.convert(*args))
    return action


def build(suite):
    for direction in ('up', 'down'):
        for index in range(1, 26):
            options = {'mode': 'by_interval', 'direction': direction, 'transposeInterval': index}
            suite.add('transpose-interval', 'interval-' + direction, 'n%02d' % index, transposed(SOURCE, options),
                      description='The C major scale transposed %s by a %s (interval number %d) exports as the recorded MusicXML'
                      % (direction, INTERVALS[index], index))
    for direction in ('up', 'down'):
        for number in range(1, 26):
            options = {'mode': 'diatonically', 'direction': direction, 'transposeInterval': number}
            suite.add('transpose-diatonic', 'diatonic-' + direction, 'n%02d' % number, transposed(DIATONIC, options),
                      description='The G major fixture scale-g-34 transposed diatonically %s with interval number %d exports as the recorded MusicXML'
                      % (direction, number))
    for direction, target in KEY_POINTS:
        options = {'mode': 'to_key', 'direction': direction, 'targetKey': target}
        step = 'm%d' % -target if target < 0 else 'k%d' % target
        suite.add('transpose-key', 'key-' + direction, step, transposed(KEYED, options),
                  description='The bass clef fixture bass-clef (C major) transposed to %s major (target key %d, %s) exports as the recorded MusicXML'
                  % (KEYS[target], target, WORDS[direction]))
    for fixture in ROSTER:
        stem, _dot, kind = fixture.rpartition('.')
        source = 'MusicXML' if kind == 'musicxml' else 'MIDI'
        for step, label, options in FIXTURE_SETS:
            suite.add('transpose-fixture', stem, step, transposed(fixture, options),
                      description='The ' + source + ' fixture ' + stem + ' transposed ' + label + ' exports as the recorded MusicXML')
    for fixture in MIDI_EXPORT:
        stem, _dot, kind = fixture.rpartition('.')
        source = 'MusicXML' if kind == 'musicxml' else 'MIDI'
        options = {'mode': 'by_interval', 'direction': 'up', 'transposeInterval': 7}
        suite.add('transpose-midi', stem, 'm3-up', transposed(fixture, options, '.mid'),
                  description='The ' + source + ' fixture ' + stem + ' transposed a minor third up exports as the recorded MIDI')
    for fixture in KEY_FIXTURES:
        stem = fixture.rpartition('.')[0]
        for step, label, options in KEY_SETS:
            suite.add('transpose-options', stem + '-keep', step, transposed(fixture, options),
                      description='The fixture ' + stem + ' transposed ' + label + ' keeps its key signature in the recorded MusicXML')
            suite.add('transpose-options', stem + '-keys', step, transposed(fixture, with_keys(options)),
                      description='The fixture ' + stem + ' transposed ' + label + ' with its key signature follows the recorded MusicXML')
    for step, label, options in SHARP_SETS:
        suite.add('transpose-options', 'accidentals-plain', step, transposed(SHARP_FIXTURE, options),
                  description='The fixture accidentals transposed ' + label + ' spells its notes as recorded')
        suite.add('transpose-options', 'accidentals-double', step, transposed(SHARP_FIXTURE, dict(options, useDoubleSharpsFlats=True)),
                  description='The fixture accidentals transposed ' + label + ' with double sharps and flats allowed spells its notes as recorded')
    for fixture in SCORE_FIXTURES:
        stem = fixture.rpartition('.')[0]
        for step, label, options in SCORE_SETS:
            suite.add('transpose-score', stem, step, transposed_score(fixture, options),
                      description='The fixture ' + stem + ' transposed ' + label + ' by the score transposition prints the recorded score and PDF')
    for fixture, step, label, options in LENIENT:
        stem = fixture.rpartition('.')[0]
        suite.add('transpose-lenient', stem, step, transposed(fixture, options),
                  description='The fixture ' + stem + ' transposed ' + label + ' exports as the recorded MusicXML')
    companions = {'--transpose': 'backend.transpose-midi.scale-c.m3-up', '--score-transpose': 'backend.transpose-score.scale-c.p5-up'}
    for option, scenario, refusals in (('--transpose', 'export', REFUSED), ('--score-transpose', 'score', SCORE_REFUSED)):
        for step, options, label in refusals:
            suite.add('transpose-refused', scenario, step, refused(option, options),
                      description='A transposition with ' + label + ' (' + option + ') is refused with the recorded exit status',
                      requires=(companions[option],))
