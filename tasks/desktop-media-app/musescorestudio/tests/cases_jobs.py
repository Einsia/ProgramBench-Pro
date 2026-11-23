'''Program cases: batch jobs (-j) of the product command line.

A job document lists conversions as pairs of absolute document paths, with optional transposition, page, visible parts and copyright per entry. Each scenario uploads one job and observes what the job wrote. A failed entry is reported as one batch status for the whole job, and that status is part of the observation.
'''
import json
import re
import fixtures

CATALOG = fixtures.catalog()
SOURCE = 'scale-c.musicxml'
PARTS = 'two-parts.musicxml'
MULTI = ('scale-c.musicxml', 'accidentals.musicxml', 'rhythms.musicxml', 'ties.musicxml', 'lyrics.musicxml',
         'piano-grand.musicxml', 'repeats.musicxml', 'melody.mid')
PAIRS = (('scale-c.musicxml', 'repeats.musicxml'), ('accidentals.musicxml', 'ties.musicxml'),
         ('lyrics.musicxml', 'two-parts.musicxml'), ('rhythms.musicxml', 'tuplets.musicxml'),
         ('titled.musicxml', 'unicode-title.musicxml'))
TRANSPOSED = ('scale-c.musicxml', 'accidentals.musicxml', 'c-minor-eighths.musicxml', 'two-parts.musicxml',
              'piano-grand.musicxml', 'rhythms.musicxml')
# Option sets that no transposition matrix of cases_transpose uses on these fixtures, so no observation repeats.
TRANSPOSE_SETS = (
    ('dia-up-2', 'diatonically upward with interval number 2', {'mode': 'diatonically', 'direction': 'up', 'transposeInterval': 2}),
    ('key-f-keys', 'to F major (upward) with its key signature',
     {'mode': 'to_key', 'direction': 'up', 'targetKey': -1, 'transposeKeySignatures': True}))
# An empty list draws every part, which is the plain SVG export of format-svg, so it is not scored here.
VISIBLE = (('part-1', 'the first part', [0]), ('part-2', 'the second part', [1]))
OUTPUTS = (('mid', '.mid'), ('musicxml', '.musicxml'), ('mscz', '.mscz'))
NAMES = {'mid': 'MIDI file', 'musicxml': 'MusicXML file', 'mscz': 'project archive'}
NOTICE = {'text': 'Copyright 2026 Test', 'showOnAllPages': True}
assert all(name in CATALOG for name in MULTI + TRANSPOSED + (SOURCE, PARTS) + tuple(n for pair in PAIRS for n in pair)), 'unknown fixture in cases_jobs'


def source(ctx, name):
    return ctx.area('inputs') + '/' + ctx.fixture(name)


def absent(ctx):
    return ctx.area('inputs') + '/absent.musicxml'


def target(ctx, stem, suffix):
    return ctx.area('outputs') + '/' + ctx.name(stem, suffix)


def run(ctx, entries):
    name = ctx.document(ctx.name('job', '.json'), json.dumps(entries).encode())
    return ctx.convert('-j', name)


def written(ctx, reply, out):
    '''The files a job entry wrote for this output path, in page order (a paged output is named <stem>-<page><suffix>).'''
    assert reply['exit_code'] == 0, 'the product exited with status ' + str(reply['exit_code'])
    stem, _dot, kind = out.rsplit('/', 1)[1].rpartition('.')
    found = {}
    for item in reply.get('downloads', []):
        match = re.fullmatch('outputs/' + re.escape(stem) + '(?:-([0-9]+))?[.]' + re.escape(kind), item.get('filename', ''))
        if match:
            found[int(match.group(1) or 0)] = item['filename']
    assert found, 'the job wrote no .' + kind + ' file'
    return [ctx.take(found[number], reply) for number in sorted(found)]


def multi_action(fixture):
    '''One entry with three outputs: the observation is the three written files together, so it is not the observation of any single export.'''
    def action(ctx):
        outs = [target(ctx, 'out', ext) for _step, ext in OUTPUTS]
        reply = run(ctx, [{'in': source(ctx, fixture), 'out': outs}])
        return {step: ctx.project('x' + ext, written(ctx, reply, out)[0]) for (step, ext), out in zip(OUTPUTS, outs)}
    return action


def entries_action(first, second):
    def action(ctx):
        outs = [target(ctx, 'entry', '.musicxml'), target(ctx, 'entry', '.musicxml')]
        reply = run(ctx, [{'in': source(ctx, first), 'out': outs[0]}, {'in': source(ctx, second), 'out': outs[1]}])
        return [ctx.project('x.musicxml', written(ctx, reply, out)[0]) for out in outs]
    return action


def transposed_action(fixture, options):
    def action(ctx):
        out = target(ctx, 'moved', '.musicxml')
        reply = run(ctx, [{'in': source(ctx, fixture), 'out': out, 'transpose': options}])
        return ctx.project('x.musicxml', written(ctx, reply, out)[0])
    return action


def drawn_action(fixture, **extra):
    def action(ctx):
        out = target(ctx, 'drawn', '.svg')
        reply = run(ctx, [dict({'in': source(ctx, fixture), 'out': out}, **extra)])
        return [ctx.project('x.svg', page) for page in written(ctx, reply, out)]
    return action


def refused_action(builder):
    def action(ctx):
        return ctx.refusal(run(ctx, builder(ctx)))
    return action


def missing_input(ctx):
    return [{'in': absent(ctx), 'out': target(ctx, 'gone', '.mid')}]


def unknown_suffix(ctx):
    return [{'in': source(ctx, SOURCE), 'out': target(ctx, 'odd', '.xyz')}]


def page_beyond(ctx):
    return [{'in': source(ctx, SOURCE), 'out': target(ctx, 'late', '.svg'), 'page': 2}]


def second_fails(ctx):
    return [{'in': source(ctx, SOURCE), 'out': target(ctx, 'first', '.mid')}, {'in': absent(ctx), 'out': target(ctx, 'second', '.mid')}]


def bad_transpose(ctx):
    return [{'in': source(ctx, SOURCE), 'out': target(ctx, 'bad', '.mid'),
             'transpose': {'mode': 'sideways', 'direction': 'up', 'transposeInterval': 4}}]


def no_output(ctx):
    return [{'in': source(ctx, SOURCE)}]


def parts_pair(suffix):
    def builder(ctx):
        return [{'in': source(ctx, PARTS), 'out': [[target(ctx, 'part', '') + '-', suffix]]}]
    return builder


def skipped_action(builder, fixture):
    '''An entry the product passes over without error, followed by a normal entry: the job still writes the normal
    entry, so the observation is the batch status, the kinds of files left and the MusicXML of the normal entry.'''
    def action(ctx):
        out = target(ctx, 'next', '.musicxml')
        reply = run(ctx, builder(ctx) + [{'in': source(ctx, fixture), 'out': out}])
        return dict(ctx.refusal(reply), next=ctx.project('x.musicxml', written(ctx, reply, out)[0]))
    return action


# Entries the product passes over with status 0; the normal entry after each is a fixture no other job converts.
SKIPPED = (
    ('no-output', 'an entry without any output', no_output, 'key-change.musicxml'),
    ('parts-pdf', 'a per-part PDF output for a score without separate parts', parts_pair('.pdf'), 'clef-change.musicxml'),
)
assert all(item[3] in CATALOG for item in SKIPPED)


REFUSED = (
    ('missing-input', 'an input document that does not exist', missing_input),
    ('unknown-suffix', 'an output name with an unknown suffix', unknown_suffix),
    ('page-beyond', 'a page past the end of the score', page_beyond),
    ('second-fails', 'a second entry that fails after a first entry that succeeds', second_fails),
    ('bad-transpose', 'an invalid transposition option', bad_transpose),
    ('parts-musicxml', 'a per-part MusicXML output for a score without separate parts', parts_pair('.musicxml')),
    ('parts-mscz', 'a per-part project archive output for a score without separate parts', parts_pair('.mscz')),
)


def build(suite):
    for fixture in MULTI:
        stem, _dot, kind = fixture.rpartition('.')
        label = 'MusicXML' if kind == 'musicxml' else 'MIDI'
        suite.add('job-multi', stem, 'three', multi_action(fixture),
                  description='A job entry with three outputs (MIDI file, MusicXML file and project archive) for the ' + label + ' fixture ' + stem + ' writes the recorded files')
    for first, second in PAIRS:
        one, two = first.rpartition('.')[0], second.rpartition('.')[0]
        suite.add('job-entries', one + '-and-' + two, 'both', entries_action(first, second),
                  description='A job with two entries for the fixtures ' + one + ' and ' + two + ' writes the recorded MusicXML for each')
    for fixture in TRANSPOSED:
        stem = fixture.rpartition('.')[0]
        for step, label, options in TRANSPOSE_SETS:
            suite.add('job-transpose', stem, step, transposed_action(fixture, options),
                      description='A job entry transposing the fixture ' + stem + ' ' + label + ' writes the recorded MusicXML')
    for step, label, parts in VISIBLE:
        suite.add('job-visible', 'two-parts', step, drawn_action(PARTS, visibleParts=parts),
                  description='A job entry drawing ' + label + ' of the fixture two-parts writes the recorded SVG')
    suite.add('job-copyright', 'scale-c', 'notice', drawn_action(SOURCE, copyright=NOTICE),
              description='A job entry drawing the fixture scale-c with a copyright notice writes the recorded SVG')
    for step, label, builder, fixture in SKIPPED:
        suite.add('job-skipped', 'job', step, skipped_action(builder, fixture),
                  description='A job with ' + label + ' followed by a normal entry ends with the recorded batch status and still writes the recorded MusicXML of the normal entry')
    for step, label, builder in REFUSED:
        companion = 'backend.job-transpose.scale-c.dia-up-2' if step == 'bad-transpose' else 'backend.job-multi.scale-c.three'
        suite.add('job-refused', 'job', step, refused_action(builder),
                  description='A job with ' + label + ' ends with the recorded batch status and leaves the recorded kinds of files',
                  requires=(companion,))
