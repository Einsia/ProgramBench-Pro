'''Value-shape families: one rule applied to columns whose cells have different shapes (signs, thousands separators,
exponents, SI suffixes, currency signs, mixed date formats, unparsable values, empty cells), driven through batch
replays and conversions (vd -b -p LOG.vdj and vd -b IN -o OUT).

Every point has its own column and rule, so an implementation that reads one shape wrongly differs from the reference
on that point alone. The expected values come from the frozen reference; the requirement text describes the
behaviour and must also hold for an equivalent reimplementation.
'''
from spec_convert import SAVERS
from spec_core import *
from spec_logs import ASC, DESC, case, checkpoint

EURO, E_UP, E_LOW = chr(0x20ac), chr(0xc9), chr(0xe9)
VAL_ROWS = [
    ['ints', 'floats', 'dates', 'si', 'money', 'mixed', 'words', 'grp'],
    ['10', '1.5', '2024-01-03', '1.5k', '$3.50', '7', 'pear', 'a'],
    ['9', '10.25', '2023-12-31', '2M', '4', 'x', 'Apple', 'b'],
    ['-3', '-0.5', '2024-1-5', '3', '5.25', '3.5', 'banana', 'a'],
    ['+4', '2e3', 'Jan 5 2024', '4G', '$1,000', '2024-01-01', 'apple', 'c'],
    ['0', '.5', '2024/02/10', '500m', '-$2', '', 'Cherry', 'b'],
    ['007', '3', '2022-07-04T10:30:00', '1.2T', EURO + '3', '-1', 'date', 'a'],
    ['100', '1,000.5', '03/04/2021', '-2k', '100', '1e2', E_UP + 'lan', 'c'],
    ['2', '7.125', '2024-02-30', '0.5', '$0', 'abc', 'zebra', 'b'],
    ['-20', '', '', '', '', '0x1f', '10x', 'a'],
    ['5', '1e-3', '2025-11-30', '10u', '7.5', '9', '_x', 'b'],
]
COLS = ['ints', 'floats', 'dates', 'si', 'money', 'mixed', 'words']
READERS = ['type-int', 'type-float', 'type-date', 'type-datetime', 'type-currency', 'type-floatsi', 'type-floatlocale', 'type-len']
NATURAL = {'ints': 'type-int', 'floats': 'type-float', 'dates': 'type-date', 'si': 'type-floatsi', 'money': 'type-currency', 'mixed': 'type-float'}
AGGREGATE_COLS = {'ints': 'type-int', 'floats': 'type-float', 'si': 'type-floatsi', 'money': 'type-currency'}
AGGREGATORS = ['sum', 'mean', 'min', 'max', 'median', 'stdev', 'count', 'distinct']
SEARCHES = [('^[A-Z]', ''), ('^[A-Z]', 'I'), ('an', ''), ('e$', ''), ('^.{4}$', ''), (E_UP, ''), (E_LOW, 'I'), ('^[a-z]+$', ''),
            ('x', 'I'), ('^_', ''), ('[0-9]', ''), ('a.*a', 'I')]


def V(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='vals')


def vals(name, entries, requirement):
    return case(name, entries, requirement, opens='vals.csv')


READERS_BY_COL = {
    'ints': ['type-int', 'type-float', 'type-len'],
    'floats': ['type-float', 'type-floatsi', 'type-currency', 'type-len'],
    'dates': ['type-date', 'type-datetime', 'type-len'],
    'si': ['type-floatsi', 'type-float', 'type-len'],
    'money': ['type-currency', 'type-float', 'type-len'],
    'mixed': ['type-float', 'type-len'],  # no type-date: dateutil completes bare numbers with the current month
    'words': ['type-len'],
}


def readers():
    return [vals('rd-%s-%s' % (col, kind[5:]), [V(kind, col)],
                 'The %s column read with %s shows every cell the way the reference does.' % (col, kind))
            for col in COLS for kind in READERS_BY_COL[col]]


def sorts():
    cases = []
    for col in COLS:
        for word, adjective, mark in (('asc', 'ascending', ASC), ('desc', 'descending', DESC)):
            cases.append(vals('so-%s-%s' % (col, word), [V('sort-' + word, col, inp=mark + col)],
                              'Sorting %s by the untyped %s column orders its cells as text.' % (adjective, col)))
            if col in NATURAL:
                cases.append(vals('so-%s-%s-typed' % (col, word), [V(NATURAL[col], col), V('sort-' + word, col, inp=mark + col)],
                                  'Sorting %s by the typed %s column orders its cells by value.' % (adjective, col)))
    return cases


def frequencies():
    cases = [vals('fq-' + col, [V('freq-col', col)], 'The frequency table of the untyped %s column counts equal cells.' % col)
             for col in COLS + ['grp']]
    cases += [vals('fq-%s-typed' % col, [V(kind, col), V('freq-col', col)],
                   'The frequency table of the typed %s column groups cells by their typed value.' % col)
              for col, kind in NATURAL.items()]
    return cases


def aggregates():
    return [vals('ag-%s-%s' % (col, agg), [V(kind, col), V('aggregate-col', col, inp=agg), V('freq-col', 'grp')],
                 'The %s aggregator of the typed %s column is added to the frequency table of grp.' % (agg, col))
            for col, kind in AGGREGATE_COLS.items() for agg in AGGREGATORS]


SRCH_ROWS = [['w'], ['start'], ['Alpha'], ['beta'], ['Gamma'], ['delta7'], ['epsilon'], ['ZETA'], ['eta_8'], ['theta'], ['iota'], ['Kappa9'], ['lambda'], ['MU'], ['nu_end']]
FORWARD = [('^[A-Z]', ''), ('^b', ''), ('ma', 'I'), ('[0-9]', ''), ('^e.*n$', ''), ('^[A-Z]+$', ''), ('_', ''), ('^th', ''), ('io', ''), ('pp', 'I'), ('^l.*a$', ''), ('^mu$', 'I'), ('end$', '')]
BACKWARD = [('^A', ''), ('^b', ''), ('mm', ''), ('lt', ''), ('ps', ''), ('zeta', 'I'), ('8', ''), ('^th', ''), ('io', ''), ('[0-9]', ''), ('a$', ''), ('[A-Z]$', ''), ('d$', '')]


def S(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='srch')


def searches():
    cases = []
    for n, (pattern, flags) in enumerate(FORWARD):
        mode = 'ignoring case' if flags else 'respecting case'
        cases.append(case('sf%02d' % n, [S('search-col', 'w', inp={'regex': pattern, 'flags': flags}), S('delete-row')],
                          'A forward search of the column for %s %s stops on the row the reference finds; deleting that row shows which one it is.' % (pattern, mode), opens='srch.csv'))
    for n, (pattern, flags) in enumerate(BACKWARD):
        mode = 'ignoring case' if flags else 'respecting case'
        cases.append(case('sb%02d' % n, [S('searchr-col', 'w', inp={'regex': pattern, 'flags': flags}), S('edit-cell', 'w', inp='X')],
                          'A backward search of the column for %s %s stops on the row the reference finds; replacing that cell shows which one it is.' % (pattern, mode), opens='srch.csv'))
    return cases


def family(key_, feature, cases):
    files = {'vals.csv': f(csv_text(VAL_ROWS)), 'srch.csv': f(csv_text(SRCH_ROWS))}
    files.update({'c-' + c['name'] + '.vdj': f(c['log']) for c in cases})
    return program(key_, feature, files, [checkpoint(c) for c in cases])


def savers():
    cps = []
    for ext, mode in [s for s in SAVERS if s[0] != 'ndjson']:
        out = 'v.' + ext
        cps.append(step('v-' + ext, 'Convert vals.csv to ' + ext + '.', [batch(['vals.csv'], out)],
                        [('file', 'The ' + ext + ' file holds the value-shape table.', file_(out, mode))]))
    return program('sh-savers', 'conversion', {'vals.csv': f(csv_text(VAL_ROWS))}, cps)


def episodes():
    groups = [('sh-types', 'types', readers()), ('sh-sorting', 'sorting', sorts()), ('sh-freq', 'analysis', frequencies()),
              ('sh-aggregates', 'analysis', aggregates()), ('sh-search', 'search', searches())]
    return [family(*group) for group in groups] + [savers()]
