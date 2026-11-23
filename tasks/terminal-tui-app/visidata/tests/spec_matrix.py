'''Matrix families: one rule applied to many inputs, driven through batch replays and conversions (vd -b -p LOG.vdj
and vd -b IN -o OUT).

Every point has its own column, pattern, expression or table, so an implementation that gets one rule wrong differs
from the reference on that point alone. The expected values come from the frozen reference; the requirement text
describes the behaviour and must also hold for an equivalent reimplementation.
'''
import spec_convert
from spec_core import *
from spec_logs import ASC, DESC, case, checkpoint

MIX_ROWS = [
    ['id', 'name', 'city', 'qty', 'price', 'day', 'code'],
    ['1', 'alice', 'Paris', '3', '10.5', '2024-01-03', 'A-1'],
    ['2', 'Bob', 'berlin', '12', '3', '2024-02-10', 'b-22'],
    ['3', 'carol', 'Paris', '', '7.25', '2024-01-20', 'A-3'],
    ['4', 'dave', 'Rome', '7', '', '2024-03-01', 'C-4'],
    ['5', 'erin', 'Berlin', '100', '12', '2023-12-31', 'a-5'],
    ['6', 'Frank', 'Rome', '7', '8', '2024-01-15', 'B-6'],
    ['7', 'gina', 'Paris', '2', '1.5', '2024-04-02', 'C-77'],
    ['8', 'Hank', 'Oslo', '45', '20', '2024-02-29', 'A-8'],
    ['9', 'ivy', 'oslo', '9', '0.5', '2022-07-04', 'b-9'],
    ['10', 'jack', 'Rome', '10', '100', '2025-11-30', 'C-10'],
    ['11', 'kim', 'Berlin', '', '2.25', '2024-06-15', 'A-11'],
    ['12', 'liz', 'Paris', '1', '9.99', '2023-05-05', 'b-12'],
]
CAT_ROWS = [['grp', 'sub', 'val'], ['x', 'p', '1'], ['x', 'q', '2'], ['y', 'p', '3'], ['y', 'q', '4'], ['z', 'p', '5'],
            ['x', 'p', '6'], ['y', 'q', '7'], ['z', 'q', '8'], ['z', 'p', '9'], ['x', 'q', '10']]
JL_ROWS = [['k', 'g', 'a'], ['1', 'x', 'a1'], ['2', 'x', 'a2'], ['2', 'y', 'a3'], ['3', 'y', 'a4'], ['4', 'z', 'a5']]
JR_ROWS = [['k', 'g', 'b'], ['2', 'x', 'b1'], ['2', 'y', 'b2'], ['3', 'y', 'b3'], ['3', 'z', 'b4'], ['5', 'z', 'b5']]
FIXTURES = {'mix.csv': csv_text(MIX_ROWS), 'tricky.csv': csv_text(spec_convert.TRICKY_ROWS), 'cat.csv': csv_text(CAT_ROWS),
            'jl.csv': csv_text(JL_ROWS), 'jr.csv': csv_text(JR_ROWS)}

SORT_COLS = ['id', 'name', 'city', 'qty', 'price', 'day', 'code']
TYPES = {'id': 'type-int', 'qty': 'type-int', 'price': 'type-float', 'day': 'type-date'}
SAVERS = spec_convert.SAVERS
FORMATS = ['tsv', 'psv', 'lsv', 'rec', 'vd', 'fixed', 'sqlite']
JOINS = ['inner', 'outer', 'full', 'diff', 'append', 'extend']
AGGREGATORS = ['min', 'max', 'avg', 'mean', 'median', 'mode', 'sum', 'distinct', 'count', 'list', 'stdev', 'q3',
               'q4', 'q10']

PATTERNS = [
    ('name', '^[a-c]', 'I'), ('name', '^[a-c]', ''), ('name', 'a', 'I'), ('name', 'k$', 'I'),
    ('name', '^.{4}$', 'I'), ('name', '^[BH]', ''), ('name', '^[a-z]{3}$', ''), ('name', '^(bob|ivy|kim)$', 'I'),
    ('city', '^P', ''), ('city', '^b', ''), ('city', '^b', 'I'), ('city', 'o', 'I'), ('city', '^Ber', ''),
    ('city', '^[BO]', ''), ('city', '^(Rome|Oslo)$', ''),
    ('code', '^C', ''), ('code', '^[ab]-', ''), ('code', '^[a-z]-[0-9]$', ''), ('code', '[0-9]{2}', 'I'),
    ('code', '^[A-Z]-[0-9]$', ''), ('code', 'b', ''),
    ('qty', '^1', 'I'), ('price', '[.]5$', 'I'), ('day', '^2023', 'I'), ('day', '-31$', 'I'),
]
SELECT_EXPRS = [
    'id > 6', 'id % 2 == 0', 'id % 3 == 1', 'id in (2, 5, 9)', 'len(name) > 4', 'name[0].isupper() and id > 6',
    'city == `Rome`', 'city.lower() == `oslo`', 'code.startswith(`A`)', 'code[-1] == `1`', '`-1` in code',
    'day.year == 2024', 'day.month < 3', 'day.year == 2023 or day.year == 2025', 'name.endswith(`e`)',
    'name.lower() < `e`', 'id * 2 > 15 and city != `Paris`', 'name.islower() and len(name) > 3',
    'int(code.split(`-`)[1]) > 10', 'len(code) == 4 and code[0].isupper()',
]
COLUMN_EXPRS = [
    'id+1', 'id*id', 'id-10', 'id//3', 'id%4', '-id', 'id**2', 'id**3', 'id/4', 'abs(id-6)', 'max(id, 6)',
    'min(id, 6)', 'round(id/3, 2)', 'id*1.5', 'int(id/4)',
    'name.upper()', 'name.lower()', 'name.title()', 'name.capitalize()', 'name.swapcase()', 'name[0]', 'name[-1]',
    'name[1:3]', 'name[::-1]', 'len(name)', 'name*2', 'name+city', 'name.center(9, `*`)', 'name.ljust(8, `.`) + code',
    'city.replace(`o`, `0`)', 'code.split(`-`)[1]', 'code.zfill(6)', 'name.count(`a`)', 'name.find(`a`)',
    'name.startswith(`a`)', 'name.isupper()', 'city[:3].upper()', 'f`{name}:{id}`', '`%s/%s` % (name, id)',
    'code.upper().replace(`-`, `_`)', '`-`.join(code.split(`-`)[::-1])', 'name.strip(`abc`)', 'code.lstrip(`abcABC-`)',
    'name.rjust(7)', 'name.partition(`a`)[0]', 'city.casefold()',
    '`big` if id > 6 else `small`', '`x` if `a` in name else `y`', 'id > 3 and id < 9', 'name == `Bob`',
    'id % 2 == 0 or name[0] == `a`', '`odd` if id % 2 else `even`',
    'sqrt(id)', 'floor(id/4)', 'ceil(id/4)', 'log2(id)', 'hypot(id, id)', 'pi*id', 'gcd(id, 12)', 'factorial(id)',
    'isqrt(id)', 'comb(id, 2)',
    'day.year', 'day.month', 'day.day', 'day.weekday()', 'day.strftime(`%b`)', 'day.isoformat()', 'day.year - 2000',
    'day.isoweekday()', 'day.strftime(`%Y/%m`)', 'day.strftime(`%A`)', 'day.strftime(`%j`)', 'day.toordinal() % 7',
    'day > date(`2024-01-01`)',
    'sum(1 for c in name if c in `aeiou`)', 'len(set(name))', 'sorted(name)[0]', 'max(name)', 'min(code)',
    'any(c.isdigit() for c in name)', 'all(c.isalpha() for c in name)', '[c for c in name if c in `aeiou`]',
    'sorted(set(city.lower()))', 'list(range(id % 4))', 'sum(range(id))', 'len(name) + len(city)',
    'json.dumps([id, name])',
]


def uq(text):
    return text.replace(chr(96), chr(39))


def M(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='mix')


def C(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='cat')


def mix(name, entries, requirement, **kw):
    return case(name, entries, requirement, opens='mix.csv', **kw)


def cat(name, entries, requirement, **kw):
    return case(name, entries, requirement, opens='cat.csv', **kw)


def family(key_, feature, cases):
    files = {name: f(data) for name, data in FIXTURES.items()}
    files.update({'c-' + c['name'] + '.vdj': f(c['log']) for c in cases})
    return program(key_, feature, files, [checkpoint(c) for c in cases])


def sorts():
    cases = []
    for col in SORT_COLS:
        for direction, mark in (('asc', ASC), ('desc', DESC)):
            word = 'ascending' if direction == 'asc' else 'descending'
            cases.append(mix('s-%s-%s' % (col, direction), [M('sort-' + direction, col, inp=mark + col)],
                             'An untyped column sorts as text: sorting %s by %s orders the cells as strings.' % (word, col)))
            if col in TYPES and col != 'day':
                # the fixture is already in id order: drop the first row and move the next one to the bottom first
                start = [M('delete-row', row='0'), M('slide-bottom', row='0')] if (col, direction) == ('id', 'asc') else []
                cases.append(mix('s-%s-%s-typed' % (col, direction), start + [M(TYPES[col], col), M('sort-' + direction, col, inp=mark + col)],
                                 'A typed column sorts by value: sorting %s by %s orders numbers and dates by their value.' % (word, col)))
    return cases


def regexes():
    cases = []
    for n, (col, pattern, flags) in enumerate(PATTERNS):
        arg = {'regex': pattern, 'flags': flags}
        mode = 'ignoring case' if flags else 'respecting case'
        cases.append(mix('rx%02d-select' % n, [M('select-col-regex', col, inp=arg), M('dup-selected')],
                         'Rows whose %s cell matches %s %s are selected.' % (col, pattern, mode)))
        cases.append(mix('rx%02d-unselect' % n, [M('select-rows'), M('unselect-col-regex', col, inp=arg), M('dup-selected')],
                         'Rows whose %s cell matches %s %s are unselected.' % (col, pattern, mode)))
    return cases


def select_expressions():
    cases = []
    prefix = [M('type-int', 'id'), M('type-date', 'day')]
    for n, text in enumerate(SELECT_EXPRS):
        expr = uq(text)
        cases.append(mix('sx%02d-select' % n, prefix + [M('select-expr', 'id', inp=expr), M('dup-selected')],
                         'Rows for which %s is true are selected.' % expr))
        cases.append(mix('sx%02d-unselect' % n, prefix + [M('select-rows'), M('unselect-expr', 'id', inp=expr), M('dup-selected')],
                         'Rows for which %s is true are unselected.' % expr))
    return cases


def column_expressions():
    prefix = [M('type-int', 'id'), M('type-date', 'day')]
    return [mix('ce%02d' % n, prefix + [M('addcol-expr', 'id', inp=uq(text))],
                'A column computed from %s holds its value for every row.' % uq(text))
            for n, text in enumerate(COLUMN_EXPRS)]


def aggregates():
    cases = []
    for col, typing in (('price', 'type-float'), ('qty', 'type-int')):
        for agg in AGGREGATORS:
            cases.append(mix('ag-%s-%s' % (col, agg), [M(typing, col), M('aggregate-col', col, inp=agg), M('freq-col', 'city')],
                             'The %s aggregator of %s is added to the frequency table of city.' % (agg, col)))
    for col in SORT_COLS:
        cases.append(mix('fq-' + col, [M('freq-col', col)], 'The frequency table of %s counts the rows per value.' % col))
    for col, typing in ((c, TYPES[c]) for c in ('qty', 'price')):
        cases.append(mix('fqt-' + col, [M(typing, col), M('freq-col', col)],
                         'The frequency table of the typed column %s groups its values by their typed display.' % col))
    return cases


def pivots():
    cases = [
        cat('pv-grp-sub', [C('key-col-on', 'grp'), C('pivot', 'sub')], 'A pivot counts the rows per group and sub value.'),
        cat('pv-sub-grp', [C('key-col-on', 'sub'), C('pivot', 'grp')], 'A pivot counts the rows per sub value and group.'),
        cat('pv-two-keys-val', [C('key-col-on', 'grp'), C('key-col-on', 'sub'), C('pivot', 'val')],
            'A pivot over two key columns has one column per distinct value.'),
        cat('pv-val-key', [C('type-int', 'val'), C('key-col-on', 'val'), C('pivot', 'grp')],
            'A typed numeric key column is a valid pivot key.'),
    ]
    for agg in ('sum', 'mean', 'max', 'min', 'median', 'list'):
        cases.append(cat('pv-agg-' + agg, [C('type-int', 'val'), C('aggregate-col', 'val', inp=agg), C('key-col-on', 'grp'), C('pivot', 'sub')],
                         'A pivot carries the %s aggregator of the value column.' % agg))
    cases += [
        cat('fk-grp-sub', [C('key-col-on', 'grp'), C('key-col-on', 'sub'), C('freq-keys')], 'A frequency table groups by several key columns.'),
        cat('fq-val', [C('type-int', 'val'), C('freq-col', 'val')], 'A frequency table of an integer column.'),
        cat('fq-grp', [C('freq-col', 'grp')], 'A frequency table of the group column.'),
    ]
    return cases


def joins():
    cases = []
    for keys in (['k'], ['k', 'g']):
        for kind in [j for j in JOINS if len(keys) == 1 or j not in ('append', 'concat')]:
            entries = ([entry('key-col-on', col, sheet='jl') for col in keys] + [open_entry('jr.csv')]
                       + [entry('key-col-on', col, sheet='jr') for col in keys] + [entry('join-sheets-top2-' + kind, sheet='jr')])
            cases.append(case('jn-%s-%d' % (kind, len(keys)), entries,
                              'A %s join over %d key column(s) combines the two sheets the way the reference does.' % (kind, len(keys)),
                              opens='jl.csv'))
    return cases


def saves():
    cases = []
    for ext, mode in [s for s in SAVERS if s[0] != 'ndjson']:
        target = 'saved.' + ext
        cases.append(mix('sv-' + ext, [M('type-float', 'price'), M('type-date', 'day'), M('sort-desc', 'city', inp=DESC + 'city'),
                                       M('save-sheet', inp=target)],
                         'save-sheet writes the typed and sorted sheet in the %s format.' % ext, saved=[(target, mode)]))
    return cases


def roundtrips():
    cps = []
    for table in ('tricky',):
        for fmt in FORMATS:
            stem = 'rt' + table
            saved = '%s.%s' % (stem, fmt)
            back = 'back-%s-%s.tsv' % (table, fmt)
            reload = [saved] + (['+%s:%s::' % (stem, table)] if fmt == 'sqlite' else [])
            cps.append(step('rt-%s-%s' % (table, fmt), 'Save the %s table as %s and read the file back.' % (table, fmt),
                            [batch([table + '.csv'], saved), batch(reload, back)],
                            [('file', 'Reading the %s file of the %s table back gives the table the reference reads.' % (fmt, table),
                              file_(back, 'text'))]))
    files = {name: f(data) for name, data in FIXTURES.items()}
    return program('mx-roundtrip', 'conversion', files, cps)


def episodes():
    groups = [('mx-sorting', 'sorting', sorts()), ('mx-select-regex', 'selection', regexes()),
              ('mx-select-expr', 'selection', select_expressions()), ('mx-expressions', 'expressions', column_expressions()),
              ('mx-aggregates', 'analysis', aggregates()), ('mx-pivots', 'analysis', pivots()),
              ('mx-joins', 'analysis', joins()), ('mx-saving', 'saving', saves())]
    return [family(*group) for group in groups] + [roundtrips()]
