"""Queries, filters, formatting and command-line validation over public calcurse interfaces."""
from itertools import combinations
from spec_common import *
from fixtures import rich, apt, event, NOTE, AGENDA


def queries(key, feature, fixtures, cases, chunk=35):
    """Each complete output checks a distinct option or combination; no separate exit-code points."""
    out = []
    for offset in range(0, len(cases), chunk):
        cps = []
        for name, args in cases[offset:offset + chunk]:
            check = cli(*args)
            check['success'] = True
            cps.append(step(name, 'Run calcurse ' + repr(args) + '.', [],
                            [('result', 'The command returns the specified selection and presentation.', check)]))
        out.append(program(key + (f'-{offset // chunk + 1}' if len(cases) > chunk else ''), feature, fixtures, cps))
    return out


def build():
    out = []
    cases = [('today', ['-a']), ('query-default', ['-Q']), ('next', ['-n']),
             ('grep', ['-G']), ('todo', ['-t']), ('combined', ['-a', '-t']),
             ('notes', ['-a', '-N']), ('status', ['--status']), ('version', ['-v']), ('help', ['-h'])]
    for date in ['today', 'tomorrow', 'yesterday', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
                 '03/16/2026', '03/18/2026', '03/20/2026', '03/31/2026', '04/01/2026']:
        cases.append(('day-' + slug(date), ['-d', date]))
    for n in [-7, -2, -1, 1, 2, 7, 14]:
        cases.append(('range-' + str(n).replace('-', 'past'), ['-Q', '--from', '03/20/2026', '--days', str(n)]))
    for n in [1, 2, 5, 10, 25, 100]:
        cases.append(('limit-' + str(n), ['-Q', '--days', '7', '--limit', str(n)]))
    for args in [['-r3'], ['--range=3'], ['-s03/19/2026'], ['--startday=03/19/2026'],
                 ['-Q', '--from', '03/17/2026', '--to', '03/20/2026'],
                 ['-Q', '--to', '03/20/2026'], ['-d', '-2'], ['-s03/19/2026', '-r2']]:
        cases.append(('syntax-' + str(len(cases)), args))
    out += queries('query', 'queries', rich(), cases)

    kinds = ['event', 'apt', 'recur-event', 'recur-apt', 'todo']
    cases = []
    # Every subset exercises the bitmask union; each member is present in the fixture.
    for n in range(1, 6):
        for subset in combinations(kinds, n):
            val = ','.join(subset)
            cases.append(('type-' + '-'.join(subset), ['-G', '--filter-type', val]))
    for shorthand in ['cal', 'recur']:
        cases.append(('type-' + shorthand, ['-G', '--filter-type', shorthand]))
    patterns = ['^Alpha', 'event$', '^Priority [1-4] ', 'Closed|Dentist', '[0-9]',
                '[[:upper:]]', 'Café', '東京', 'milk, bread;', '.*', '^$', '^No such item$',
                '^(Early|Weekly)', 'report', '(day|night)', 'D.*t', 'P(riority|repare)',
                'task$', '^[^A-Z]', '[[:space:]]']
    for i, p in enumerate(patterns):
        cases.append((f'pattern-{i+1}', ['-G', '--filter-pattern', p]))
    for k in kinds + ['cal', 'recur']:
        cases.append(('invert-' + k, ['-G', '--filter-type', k, '--filter-invert']))
        cases.append(('and-pattern-' + k, ['-G', '--filter-type', k, '--filter-pattern', '[ae]']))
    out += queries('filter-selection', 'filters', rich(), cases)

    records = [event(text='Hash event'), apt(text='Hash appointment'), event(text='Hash recurring event',rule='1D'),
               apt(text='Hash recurring appointment',rule='1W')]
    todo_record = '[3] Hash todo'
    cases=[]
    for i, line in enumerate(records + [todo_record]):
        digest=sha1(line)
        for name,value in [('full',digest),('prefix',digest[:7]),('negated','!'+digest[:7])]:
            cases.append((f'item-{i+1}-{name}',['-G','--filter-hash',value]))
    cases.append(('missing-hash',['-G','--filter-hash','0000000000000000000000000000000000000000']))
    out += queries('filter-hashes','filters',home(apts=records,todo=[todo_record]),cases)

    cases = []
    moments = ['03/17/2026', '03/18/2026', '03/18/2026 00:01', '03/18/2026 09:30',
               '03/18/2026 10:00', '03/18/2026 11:30', '03/19/2026', '03/20/2026']
    for edge in ['start', 'end']:
        for direction in ['from', 'to', 'after', 'before']:
            for i, t in enumerate(moments):
                cases.append((f'{edge}-{direction}-{i+1}', ['-G', '--filter-' + edge + '-' + direction, t]))
        for i, limits in enumerate([
                ('03/17/2026', '03/19/2026'), ('03/18/2026', '03/18/2026'),
                ('03/18/2026 09:30', '03/18/2026 11:30'), ('03/19/2026', '03/20/2026')]):
            cases.append((f'{edge}-range-{i+1}', ['-G', '--filter-' + edge + '-range', ','.join(limits)]))
    for k in kinds:
        cases.append(('type-time-' + k, ['-G', '--filter-type', k, '--filter-start-from', '03/18/2026',
                                       '--filter-end-before', '03/19/2026']))
    for opt in ['--filter-completed', '--filter-uncompleted']:
        cases.append((opt[2:], ['-G', opt]))
        for p in range(1, 10):
            cases.append((opt[2:] + '-' + str(p), ['-G', opt, '--filter-priority', str(p)]))
    for p in range(10):
        cases.append(('todo-priority-' + str(p), ['-t' + str(p)]))
    out += queries('filter-boundary', 'filters', rich(), cases)

    # Each format applies to a different product record type. Hash and raw representation are public fields.
    formats = ['%m', '%n', '%N', '%(raw)', '%(hash)', 'literal: %% %m\\n', '%m\\t%n\\n',
               '%m\\n%N', '%m\\\\end']
    cases = []
    for k in kinds:
        for i, fmt in enumerate(formats + (['%p', '[%p] %m\\n'] if k == 'todo' else [])):
            cases.append((f'{k}-field-{i+1}', ['-G', '--filter-type', k, '--format-' + k, fmt]))
    out += queries('format-records', 'formatting', rich(), cases)

    # Distinct duration fields, padding rules and clock/total modifiers at carry boundaries.
    duration_formats = ['%d', '%(duration:%d)', '%(duration:%H)', '%(duration:%M)',
                        '%(duration:%S)', '%(duration:%EH)', '%(duration:%EM)', '%(duration:%ES)',
                        '%(duration:%-d/%-H/%-M/%-S)', '%(duration:%-EH/%-EM/%-ES)']
    durations = [0, 1, 59, 60, 61, 1439, 1440, 1501, 44640, 150000]
    for n in durations:
        cal = [apt(minutes=n, text='Duration')]
        cases = [('fields', ['-G', '--filter-type', 'apt', '--format-apt', '|'.join(duration_formats)])]
        out += queries('format-duration-' + str(n), 'formatting', home(apts=cal), cases)
    time_formats = ['%s', '%e', '%S', '%E', '%r', '%(start)', '%(end)', '%(remaining:%d/%H/%M/%S)',
                    '%(remaining:%EH/%EM/%ES)', '%(remaining:%-d/%-H/%-M/%-S)',
                    '%(start:%Y-%m-%d)', '%(start:%j/%u/%w)', '%(start:%a %A %b %B)',
                    '%(start:%I:%M %p)', '%(start:%G-W%V)', '%(start:%z %Z)',
                    '%(end:%F %T)', '%(end:default)', '%(end:epoch)']
    starts = [('past', '2026-03-17 08:00', 60), ('now', '2026-03-18 09:30', 0),
              ('future', '2026-03-19 10:45', 90), ('leap', '2028-02-29 23:59', 2),
              ('iso-year', '2027-01-01 00:00', 1500)]
    for name, start, n in starts:
        cases = [('fields', ['-G', '--filter-type', 'apt', '--format-apt', '|'.join(time_formats)])]
        out += queries('format-time-' + name, 'formatting', home(apts=[apt(start=start, minutes=n)]), cases)

    for datefmt, date in [(1, '03/18/2026'), (2, '18/03/2026'), (3, '2026/03/18'), (4, '2026-03-18')]:
        cases = [('full', ['-d', date]), ('short-day', ['-d', '18']),
                 ('override', ['--input-datefmt', '1', '-d', '03/18/2026'])]
        out += queries('date-format-' + str(datefmt), 'configuration', rich(conf={'format.inputdate': str(datefmt)}), cases)
    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%A %B %e', '%j %u %w', '%G-W%V', '%a %D', '%C/%y', '%F (%Z)']
    out += queries('date-output', 'configuration', rich(),
                   [(f'format-{i+1}', ['-Q', '--output-datefmt', fmt, '--days', '3'])
                    for i, fmt in enumerate(date_formats)])

    # Invalid commands must be rejected. One assertion combines the failure class and diagnostics.
    invalid = [['--unknown-option'], ['-z'], ['--filter-type', 'bogus', '-G'], ['-Q', '--days', 'nonsense'],
               ['-Q', '--from', '02/30/2026'], ['-Q', '--to', '03/01/2026'],
               ['-Q', '--to', '03/19/2026', '--days', '2'], ['-Q', '--days', '0'],
               ['-G', '--filter-pattern', '['], ['-G', '--filter-start-range', 'bad'],
               ['-G', '--filter-end-from', 'bad'], ['-G', '--filter-priority', '11'],
               ['-G', '--filter-start-from', '03/18/2026', '--filter-start-after', '03/19/2026'],
               ['-G', '--filter-end-to', '03/18/2026', '--filter-end-before', '03/19/2026'],
               ['-xinvalid'], ['--input-datefmt', '0', '-Q'], ['--input-datefmt', '5', '-Q'],
               ['--from'], ['--filter-pattern'], ['-t11'], ['-G', '--filter-priority', '0'],
               ['-s', '03/19/2026', '-r', '2']]
    cps = [step('case-' + str(i+1), 'Reject invalid arguments ' + repr(args), [],
                [('diagnostic', 'The invalid command fails with a diagnostic.', dict(cli(*args, part='error'), failure=True))])
           for i, args in enumerate(invalid)]
    out.append(program('cli-errors', 'validation', rich(), cps))
    return out
