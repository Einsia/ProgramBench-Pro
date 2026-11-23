'''Extra families: commands that change the sheet in ways the other families do not reach (length, SI and
duration types, display precision, sort keys that are added or changed, grouped aggregates, ranks, column names
taken from selected rows, cell clearing and clipboard paste, unpivoting and unfolding nested values), driven
through batch replays (vd -b -p LOG.vdj -o OUT).

Every point has its own column, row, aggregator or pattern, so an implementation that gets one case wrong differs
from the reference on that point alone. The expected values come from the frozen reference; the requirement text
describes the behaviour and must also hold for an equivalent reimplementation.
'''
import json

from spec_core import *
from spec_logs import ASC, case, checkpoint
from spec_matrix import AGGREGATORS, MIX_ROWS, SORT_COLS
from spec_variants import M, ROWS, mix

WIDE_ROWS = [['id', 'q1_a', 'q1_b', 'q2_a', 'q2_b'], ['1', '10', '11', '12', '13'], ['2', '20', '21', '22', '23'],
             ['3', '30', '', '32', '33']]
SI_ROWS = [['n'], ['1500'], ['0.002'], ['2500000'], ['12'], ['0.5'], ['3000000000']]
NEST = json.dumps([{'id': 1, 'tags': ['a', 'b'], 'info': {'x': 1, 'y': 'p'}}, {'id': 2, 'tags': ['c'], 'info': {'x': 2}},
                   {'id': 3, 'tags': [], 'info': {'y': 'q'}}])
DEEP = json.dumps([{'a': {'b': {'c': 1, 'd': 2}, 'e': 3}}, {'a': {'b': {'c': 4}, 'e': 5}}])
FILES = {'mix.csv': csv_text(MIX_ROWS), 'wide.csv': csv_text(WIDE_ROWS), 'si.csv': csv_text(SI_ROWS), 'nest.json': NEST,
         'deep.json': DEEP}
PICK = M('select-col-regex', 'city', inp={'regex': '^P', 'flags': ''})
FIRST = M('sort-asc', 'city', inp=ASC + 'city')


def family(key_, feature, cases):
    files = {name: f(data) for name, data in FILES.items()}
    files.update({'c-' + c['name'] + '.vdj': f(c['log']) for c in cases})
    return program(key_, feature, files, [checkpoint(c) for c in cases])


def types():
    cases = []
    for col in SORT_COLS:
        cases.append(mix('len-' + col, [M('type-len', col)], 'Typing the %s column as length shows the length of every value.' % col))
    for col in ('id', 'qty', 'price'):
        cases.append(mix('cur-' + col, [M('type-currency', col)], 'The %s column typed as currency shows every value as an amount.' % col))
    for name, cmd in (('floatsi', 'type-floatsi'), ('float', 'type-float'),
                      ('len', 'type-len')):
        cases.append(case('si-' + name, [entry(cmd, 'n', sheet='si')], 'The column of large and small numbers typed with %s is shown in that type.' % cmd, opens='si.csv'))
    for n in (1, 2):
        cases.append(mix('more%d' % n, [M('type-float', 'price')] + [M('setcol-precision-more', 'price')] * n,
                         'Asking for more precision %d time(s) adds decimals to a float column.' % n))
        cases.append(mix('less%d' % n, [M('type-float', 'price')] + [M('setcol-precision-less', 'price')] * n,
                         'Asking for less precision %d time(s) removes decimals from a float column.' % n))
    return cases


def sorting():
    cases = []
    for col in SORT_COLS:
        if col == 'city':
            continue
        cases.append(mix('add-asc-' + col, [FIRST, M('sort-asc-add', col)], 'A second ascending key on %s orders the rows that share a city.' % col))
        cases.append(mix('add-desc-' + col, [FIRST, M('sort-desc-add', col)], 'A second descending key on %s orders the rows that share a city.' % col))
        cases.append(mix('chg-city-' + col, [FIRST, M('sort-asc-add', col), M('sort-desc-change', 'city')],
                         'Changing the city key to descending keeps the second key on %s.' % col))
        cases.append(mix('keys-asc-' + col, [M('key-col-on', 'city'), M('key-col-on', col), M('sort-keys-asc-add')],
                         'Sorting by the key columns city and %s ascending orders by both.' % col))
        cases.append(mix('keys-desc-' + col, [M('key-col-on', 'city'), M('key-col-on', col), M('sort-keys-desc-add')],
                         'Sorting by the key columns city and %s descending orders by both.' % col))
    return cases


def aggregates():
    cases = []
    for agg in AGGREGATORS:
        cases.append(mix('ga-price-' + agg, [M('type-float', 'price'), M('key-col-on', 'city'), M('addcol-aggregate', 'price', inp=agg)],
                         'A column holds the %s of price over the rows that share the key value.' % agg))
    for agg in ('mean', 'median', 'sum', 'count', 'min', 'max'):
        cases.append(mix('ga-qty-' + agg, [M('type-int', 'qty'), M('key-col-on', 'city'), M('addcol-aggregate', 'qty', inp=agg)],
                         'A column holds the %s of qty over the rows that share the key value.' % agg))
    for n, keys in enumerate((['city'], ['name'], ['qty'], ['city', 'qty'])):
        cases.append(mix('rank-%d' % n, [M('key-col-on', k) for k in keys] + [M('addcol-rank-sheet')],
                         'A rank column numbers the rows by their key columns (%s).' % ' and '.join(keys)))
    return cases


def renaming():
    cases = []
    for r in range(ROWS):
        cases.append(mix('names-row-%02d' % r, [M('select-row', row=r), M('rename-cols-selected')],
                         'The values of selected row %d become the column names.' % r))
    for col in SORT_COLS:
        cases.append(mix('name-col-' + col, [M('select-row', row=1), M('rename-col-selected', col)],
                         'The %s column is renamed after its value in the selected row.' % col))
    return cases


def cells():
    cases = []
    for col in SORT_COLS:
        cases.append(mix('del-' + col, [PICK, M('delete-cells', col)], 'The %s cells of the selected rows are emptied.' % col))
    for src, dst in (('name', 'city'), ('city', 'name'), ('code', 'name'), ('id', 'qty'), ('price', 'qty'), ('day', 'code')):
        cases.append(mix('paste-%s-%s' % (src, dst), [PICK, M('copy-cells', src), M('setcol-clipboard', dst)],
                         'The copied %s cells of the selected rows are pasted into the %s column.' % (src, dst)))
    for src, dst in (('city', 'name'), ('name', 'code')):
        cases.append(mix('cut-%s-%s' % (src, dst), [PICK, M('cut-cells', src), M('setcol-clipboard', dst)],
                         'The cut %s cells of the selected rows are emptied and pasted into the %s column.' % (src, dst)))
    return cases


def nested():
    def W(longname, col='', inp=''):
        return entry(longname, col, '', inp, sheet='wide')
    cases = []
    for n, pattern in enumerate(('(.*)_(.*)', '(q)(.)_(.)', '(.*)_a', '^(q1)_(.*)$')):
        cases.append(case('melt-%d' % n, [W('key-col-on', 'id'), W('melt-regex', inp=pattern)],
                          'Unpivoting with %s keeps the key column and splits the other names by the captured groups.' % pattern, opens='wide.csv'))
    for col in ('tags', 'info'):
        cases.append(case('unfurl-' + col, [entry('unfurl-col', col, sheet='nest')],
                          'The %s values are unfolded into one row per element.' % col, opens='nest.json'))
    for depth in (0, 1):
        cases.append(case('depth-%d' % depth, [entry('expand-col-depth', 'a', inp=str(depth), sheet='deep')],
                          'Expanding the nested column to depth %d adds the columns of that many levels.' % depth, opens='deep.json'))
    return cases


def episodes():
    groups = [('ex-types', 'types', types()), ('ex-sorting', 'sorting', sorting()), ('ex-aggregates', 'analysis', aggregates()),
              ('ex-renaming', 'columns', renaming()), ('ex-cells', 'rows', cells()), ('ex-nested', 'columns', nested())]
    return [family(*group) for group in groups]
