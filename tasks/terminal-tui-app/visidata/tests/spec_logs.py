'''Command-level behaviour: command logs (.vdj) replayed in batch mode (vd -b -p LOG.vdj -o OUT).

A command log is the replay format VisiData writes itself (Ctrl+D), so every placed log is a real input of the
product. A checkpoint replays one log and reads the saved sheet back; the expected values come from the frozen
reference. Fixtures are chosen so that the correct result differs from the unchanged sheet and from the result of
neighbouring rules (repeated values, an empty cell, typed against untyped numbers).
'''
import json
from spec_convert import DATA_JSON
from spec_core import *

ASC, DESC = SEP + '<', SEP + '>'
E = entry
DUP = E('dup-selected')
FIXTURES = {
    'sample.csv': SAMPLE,
    'pets.csv': csv_text(PETS_ROWS),
    'dups.csv': csv_text([['k', 'v'], ['a', '1'], ['b', '2'], ['a', '1'], ['c', ''], ['b', '2']]),
    'split.csv': csv_text([['full', 'code'], ['ann lee', 'A-1'], ['bo kim', 'B-22']]),
    'messy.csv': csv_text([['First Name', 'last-name', 'AGE %', 'x'], ['ann', 'lee', '30', '1'], ['bo', 'kim', '25', '1']]),
    'uni.csv': csv_text([['a', 'b', 'c'], ['1', 'x', 'k'], ['2', 'x', 'k'], ['3', 'y', 'k']]),
    'nums.csv': csv_text([['n'], ['10'], ['9'], ['100'], ['2']]),
    'data.json': DATA_JSON,
}


def rx(pattern):
    return {'regex': pattern, 'flags': 'I'}


def sel(*rows):
    return [E('select-row', row=r) for r in rows]


def case(name, entries, requirement, opens='sample.csv', args=(), mode='tsv', saved=None, fails=False, nofile=False):
    return {'name': name, 'log': vdj(entries, opens), 'requirement': requirement, 'args': list(args), 'mode': mode,
            'saved': saved, 'fails': fails, 'nofile': nofile}


def checkpoint(c):
    out = 'out-' + c['name'] + '.tsv'
    run = batch(c['args'] + ['-p', 'c-' + c['name'] + '.vdj'], out)
    if c['fails']:
        checks = [('message', c['requirement'], outcome(only=['exit_code', 'output']))]
        if c['nofile']:
            checks.append(('nothing', 'No output file is written when the replay stops.', file_(out, 'text', may_be_missing=True)))
    else:
        checks = [('saved%d' % i, c['requirement'], file_(p, m)) for i, (p, m) in enumerate(c['saved'] or [])] or [('sheet', c['requirement'], file_(out, c['mode']))]
    return step('cmd-' + c['name'], 'Replay the command log ' + c['name'] + ' and save the resulting sheet.', [run], checks)


def episode(key_, feature, cases):
    fixtures = {name: f(data) for name, data in FIXTURES.items()}
    fixtures.update({'c-' + c['name'] + '.vdj': f(c['log']) for c in cases})
    return program(key_, feature, fixtures, [checkpoint(c) for c in cases])


def sorting():
    return [
        case('sort-desc-name', [E('sort-desc', 'name', inp=DESC + 'name')], 'Sorting descending by a text column puts the highest value first.'),
        case('sort-two-keys', [E('sort-asc', 'city', inp=ASC + 'city'), E('sort-desc-add', 'id')], 'A second key in the opposite direction orders the rows that share the first key.'),
        case('sort-mixed', [E('sort-desc-add', 'city'), E('sort-desc-add', 'id')], 'Added sort keys build a multi-key order from nothing.'),
        case('sort-ties', [E('sort-asc', 'city', inp=ASC + 'city')], 'Rows with equal sort keys keep their original relative order.'),
        case('sort-text-numbers', [E('sort-asc', 'n', inp=ASC + 'n', sheet='nums')], 'An untyped column of numbers sorts as text.', opens='nums.csv'),
        case('sort-int-numbers', [E('type-int', 'n', sheet='nums'), E('sort-asc', 'n', inp=ASC + 'n', sheet='nums')], 'A column typed as integer sorts numerically.', opens='nums.csv'),
        case('sort-float-desc', [E('type-float', 'amount'), E('sort-desc', 'amount', inp=DESC + 'amount')], 'A float column sorts numerically.'),
        case('sort-date-desc', [E('type-date', 'date'), E('sort-desc', 'date', inp=DESC + 'date')], 'A date column sorts chronologically.'),
        case('sort-keys-asc', [E('key-col-on', 'city'), E('key-col-on', 'id'), E('sort-keys-asc')], 'Sorting by the key columns orders by all of them from the left.'),
        case('sort-keys-desc', [E('key-col-on', 'city'), E('key-col-on', 'id'), E('sort-keys-desc')], 'Sorting by the key columns descending reverses every key.'),
    ]


GRID_ROWS = [['id', 'name', 'city', 'amount', 'date'], ['1', 'alice', 'Paris', '10.5', '2024-01-03'], ['2', 'bob', 'Berlin', '3', '2024-02-10'], ['3', 'carol', 'Paris', '7.25', '2024-01-20'], ['4', 'dave', 'Rome', '', '2024-03-01'], ['5', 'erin', 'Berlin', '12', '2023-12-31'], ['6', 'frank', 'Rome', '8', '2024-01-15'], ['7', 'gina', 'Paris', '1.5', '2024-04-02'], ['8', 'hank', 'Oslo', '20', '2024-02-29']]
FIXTURES['grid.csv'] = csv_text(GRID_ROWS)
FIXTURES['units.csv'] = csv_text([['si', 'cur', 'loc'], ['1.5k', '$3.5', '1,234.5'], ['2M', '$4', '2.5'], ['3', '5', '7'], ['', '', '']])
FIXTURES['deep.json'] = json.dumps([{'id': 1, 'a': {'b': {'c': 1, 'd': [1, 2]}}}, {'id': 2, 'a': {'b': {'c': 2, 'd': []}}}])


def G(longname, col='', row='', inp=''):
    return entry(longname, col, row, inp, sheet='grid')


def pick(*rows):
    return [G('select-row', row=r) for r in rows]


def grid(name, entries, requirement):
    return case(name, entries + [G('dup-selected')], requirement, opens='grid.csv')


def selection():
    return [
        grid('select-rows', pick(1, 3, 6), 'Selecting rows one by one marks exactly those rows.'),
        grid('select-all-unselect-one', [G('select-rows'), G('unselect-row', row=3)], 'Selecting all rows and unselecting one leaves the others selected.'),
        grid('select-toggle-all', pick(0, 2, 4) + [G('stoggle-rows')], 'Toggling the selection of all rows inverts it.'),
        grid('select-toggle-row', [G('stoggle-row', row=5)], 'Toggling a single row selects it.'),
        grid('select-equal-cell', [G('select-equal-cell', 'city', row=0)], 'Rows whose cell in the column equals the cursor cell are selected.'),
        grid('select-equal-row', [G('select-equal-row', row=4)], 'Rows equal to the cursor row in every column are selected.'),
        grid('select-exact-cell', [G('select-exact-cell', 'city', row=1)], 'Rows whose cell is exactly the cursor cell are selected.'),
        grid('select-exact-row', [G('select-exact-row', row=2)], 'Rows that are exactly the cursor row are selected.'),
        grid('select-equal-selected', pick(0, 3) + [G('select-equal-selected', 'city')], 'Rows that share a value in the column with a selected row are selected.'),
        grid('select-regex-column', [G('select-col-regex', 'city', inp=rx('^[BR]'))], 'Rows whose cell in the column matches the regular expression are selected.'),
        grid('select-regex-any-column', [G('select-cols-regex', inp=rx('ank'))], 'Rows with a match in any column are selected.'),
        grid('unselect-regex-column', [G('select-rows'), G('unselect-col-regex', 'city', inp=rx('Paris'))], 'Rows matching the expression in the column are unselected.'),
        grid('unselect-regex-any-column', [G('select-rows'), G('unselect-cols-regex', inp=rx('ank'))], 'Rows matching the expression in any column are unselected.'),
        grid('select-expression', [G('select-expr', 'id', inp='int(id) % 3 == 0')], 'Rows for which a Python expression is true are selected.'),
        grid('unselect-expression', [G('select-rows'), G('unselect-expr', 'name', inp='len(name) == 5')], 'Rows for which a Python expression is true are unselected.'),
        grid('select-after', [G('select-after', row=5)], 'Every row from the cursor row on is selected.'),
        grid('select-before', [G('select-before', row=1)], 'Rows before the cursor row are selected.'),
        grid('select-around', pick(3) + [G('select-around-n', row=3, inp='1')], 'Rows around each selected row are selected too.'),
        grid('select-to-next', pick(1, 4) + [G('select-to-next-selected', row=1)], 'Rows between the cursor and the next selected row are selected.'),
        grid('select-to-previous', pick(2, 6) + [G('select-to-prev-selected', row=6)], 'Rows between the cursor and the previous selected row are selected.'),
        grid('toggle-after', [G('stoggle-after', row=4)], 'Toggling from the cursor row on selects the rows below it.'),
        grid('toggle-before', [G('stoggle-before', row=2)], 'Toggling before the cursor row selects the rows above it.'),
        grid('unselect-after', [G('select-rows'), G('unselect-after', row=6)], 'Rows from the cursor row on are unselected.'),
        grid('unselect-before', [G('select-rows'), G('unselect-before', row=6)], 'Rows before the cursor row are unselected.'),
        grid('unselect-all', [G('select-rows'), G('unselect-rows')], 'Unselecting all rows leaves nothing to duplicate.'),
        case('select-duplicates', [E('key-col-on', 'k', sheet='dups'), E('select-duplicate-rows', sheet='dups'), E('dup-selected', sheet='dups')], 'Rows whose key columns repeat an earlier row are selected.', opens='dups.csv'),
    ]


def rows():
    return [
        case('row-delete', [E('delete-row', row=2), E('delete-row', row=2)], 'Deleting a row removes it; a second deletion acts on the rows that moved up.'),
        case('row-delete-selected', sel(1, 2) + [E('delete-selected')], 'Deleting the selection removes every selected row.'),
        case('row-cut', [E('cut-row', row=1)], 'Cutting a row removes it from the sheet.'),
        case('row-add', [E('add-row', row=1)], 'A new empty row is inserted below the cursor row.'),
        case('row-copy-paste-after', [E('copy-row', row=1), E('paste-after', row=3)], 'A copied row is pasted below the cursor row.'),
        case('row-copy-paste-before', [E('copy-row', row=1), E('paste-before', row=3)], 'A copied row is pasted above the cursor row.'),
        case('cell-copy-paste', [E('copy-cell', 'city', row=1), E('paste-cell', 'city', row=3)], 'A copied cell value replaces the value of the cursor cell.'),
        case('cell-cut', [E('cut-cell', 'city', row=1)], 'Cutting a cell empties it.'),
        case('cell-delete', [E('delete-cell', 'name', row=3)], 'Deleting a cell empties it.'),
        case('cell-edit', [E('edit-cell', 'city', row=1, inp='Oslo')], 'Editing a cell replaces its value with the input.'),
        case('cell-set-expression', [E('setcell-expr', 'city', row=1, inp='name')], 'A cell can be set from an expression over its row.'),
        case('row-slide-down', [E('slide-down', row=1)], 'Sliding a row down swaps it with the row below.'),
        case('row-slide-up', [E('slide-up', row=1)], 'Sliding a row up swaps it with the row above.'),
        case('row-slide-top', [E('slide-top', row=3)], 'Sliding a row to the top moves it to the first position.'),
        case('row-slide-bottom', [E('slide-bottom', row=1)], 'Sliding a row to the bottom moves it to the last position.'),
        case('row-slide-down-n', [E('slide-down-n', row=1, inp='2')], 'Sliding a row down by a count moves it that many places.'),
    ]


def columns():
    return [
        case('col-rename', [E('rename-col', 'id', inp='ident')], 'Renaming a column changes its header.'),
        case('col-hide', [E('hide-col', 'city'), E('hide-col', 'date')], 'Hidden columns are left out of a saved sheet.'),
        case('col-key', [E('key-col-on', 'date'), E('key-col-on', 'name')], 'Key columns move to the left in the order they were set.'),
        case('col-hide-uniform', [E('hide-uniform-cols', sheet='uni')], 'Columns whose values are all equal are hidden.', opens='uni.csv'),
        case('col-clean-names', [E('clean-names', sheet='messy')], 'Cleaning names replaces spaces and punctuation in headers.', opens='messy.csv'),
        case('col-normalize-names', [E('normalize-col-names', sheet='messy')], 'Normalizing names lower-cases and cleans the headers.', opens='messy.csv'),
        case('col-slide-left', [E('slide-left', 'city')], 'Sliding a column left swaps it with its left neighbour.'),
        case('col-slide-right', [E('slide-right', 'city')], 'Sliding a column right swaps it with its right neighbour.'),
        case('col-slide-leftmost', [E('slide-leftmost', 'city')], 'Sliding a column to the far left makes it the first column.'),
        case('col-slide-rightmost', [E('slide-rightmost', 'city')], 'Sliding a column to the far right makes it the last column.'),
        case('col-freeze', [E('freeze-col', 'city')], 'Freezing a column adds a copy of its current values.'),
        case('col-new-empty', [E('addcol-new', 'city', inp='x')], 'A new empty column is added next to the cursor column.'),
        case('col-incr', [E('addcol-incr', 'id')], 'An incrementing column counts the rows from one.'),
        case('col-incr-step', [E('addcol-incr-step', 'id', inp='2')], 'An incrementing column can use a step.'),
        case('col-bulk', [E('addcol-bulk', 'id', inp='2')], 'Several empty columns can be added at once.'),
        case('col-window', [E('type-int', 'id'), E('addcol-window', 'id', inp='-1 1')], 'A window column collects values from neighbouring rows.'),
        case('col-split', [E('addcol-split', 'full', inp=' ', sheet='split')], 'A column can be split on a separator into a new column.', opens='split.csv'),
        case('col-capture', [E('addcol-capture', 'code', inp='([A-Z])-([0-9]+)', sheet='split')], 'Regular expression groups are captured into a new column.', opens='split.csv'),
        case('col-regex-substitute', [E('addcol-regex-subst', 'code', inp={'before': '([A-Z])-([0-9]+)', 'after': 'x'}, sheet='split')], 'A substitution result is added as a new column.', opens='split.csv'),
        case('col-iterator', [E('addcol-iter', 'city', inp='range(1, 100)')], 'A column can be filled from the items of a sequence expression.'),
        case('col-expand', [E('expand-col', 'tags', sheet='data')], 'Expanding a list column adds one column per item.', opens='data.json'),
        case('col-expand-dict', [E('expand-col', 'meta', sheet='data')], 'Expanding a dictionary column adds one column per key.', opens='data.json'),
        case('col-expand-all', [E('expand-cols', sheet='deep')], 'Expanding all columns unpacks one level of nested dictionaries and lists.', opens='deep.json'),
        case('col-expand-depth', [E('expand-cols-depth', inp='0', sheet='deep')], 'Expanding with depth zero unpacks every nested level.', opens='deep.json'),
    ]


def expressions():
    return [
        case('expr-int', [E('type-int', 'id'), E('addcol-expr', 'id', inp='id*2')], 'An expression column computes from other columns.'),
        case('expr-untyped', [E('addcol-expr', 'id', inp='id*2')], 'An untyped column behaves as text inside an expression.'),
        case('expr-named', [E('type-int', 'id'), E('addcol-expr', 'id', inp='double=id*2')], 'An expression can name its column.'),
        case('expr-method', [E('addcol-expr', 'name', inp='name.upper()')], 'Expressions can call methods of values.'),
        case('expr-fstring', [E('addcol-expr', 'name', inp='f' + Q + '{name}-{city}' + Q)], 'Expressions can use formatted strings.'),
        case('expr-row', [E('addcol-expr', 'name', inp='row.city + ' + Q + '!' + Q)], 'An expression can read other cells through the row.'),
        case('expr-mixed-types', [E('type-float', 'amount'), E('type-int', 'id'), E('addcol-expr', 'id', inp='id + amount')], 'Typed columns of different number types add up.'),
        case('expr-date-year', [E('type-date', 'date'), E('addcol-expr', 'date', inp='date.year')], 'A date column exposes date fields in expressions.'),
        case('setcol-input', [E('select-rows'), E('setcol-input', 'city', inp='X')], 'The input replaces the column value in every selected row.'),
        case('setcol-selected-only', sel(1, 3) + [E('setcol-input', 'city', inp='X')], 'Only the selected rows receive the input.'),
        case('setcol-expression', [E('select-rows'), E('setcol-expr', 'city', inp='name.upper()')], 'An expression result replaces the column value in selected rows.'),
        case('setcol-incr', sel(1, 2) + [E('setcol-incr', 'id')], 'Selected rows are numbered from one.'),
        case('setcol-incr-step', [E('select-rows'), E('setcol-incr-step', 'id', inp='3')], 'Selected rows are numbered with a step.'),
        case('setcol-iterator', [E('select-rows'), E('setcol-iter', 'city', inp='range(10, 20)')], 'Selected rows take the items of a sequence expression.'),
        case('setcol-substitute', [E('select-rows'), E('setcol-regex-subst', 'city', inp={'before': 'a', 'after': 'A'})], 'A substitution changes the column in selected rows.'),
        case('setcol-substitute-all', [E('select-rows'), E('setcol-regex-subst-all', inp={'before': 'a', 'after': 'A'})], 'A substitution changes every column in selected rows.'),
        case('setcol-enum', [E('select-rows'), E('setcol-format-enum', 'city', inp='Paris=P Berlin=B')], 'An enum format replaces listed values when shown.'),
        case('setcol-precision', [E('type-float', 'amount'), E('setcol-precision-input', 'amount', inp='3')], 'A float column can show more decimals.'),
    ]


def types():
    return [
        case('type-float', [E('type-float', 'amount')], 'A float column shows its values with two decimals.'),
        case('type-int-text', [E('type-int', 'name'), E('save-sheet', inp='int-text.json')],
             'Text typed as integer has no integer values: a JSON save writes an error marker in that column only.', saved=[('int-text.json', 'json')]),
        case('type-datetime', [E('type-datetime', 'date')], 'A datetime column shows the time of day as well.'),
        case('type-currency', [E('type-currency', 'cur', sheet='units')], 'A currency column reads and shows currency amounts.', opens='units.csv'),
        case('type-floatsi', [E('type-floatsi', 'si', sheet='units')], 'An SI float column reads values with SI suffixes.', opens='units.csv'),
        case('type-floatlocale', [E('type-floatlocale', 'loc', sheet='units')], 'A locale float column reads values with thousands separators.', opens='units.csv'),
        case('type-len', [E('type-len', 'city')], 'The length type shows the number of characters.'),
        case('type-string-again', [E('type-float', 'amount'), E('type-string', 'amount'), E('sort-desc', 'amount', inp=DESC + 'amount')],
             'A float column typed back to text sorts as text again.'),
        case('type-any-again', [E('type-float', 'amount'), E('type-any', 'amount'), E('sort-asc', 'amount', inp=ASC + 'amount')],
             'A float column typed back to its raw values sorts as text again.'),
        case('type-int-expr', [E('type-int', 'id'), E('addcol-expr', 'id', inp='id+1')], 'An integer column supports arithmetic in expressions.'),
        case('disp-float-fmt', [E('type-float', 'amount')], 'The float display option sets the decimals of float columns.', args=['--disp-float-fmt', '{:.1f}']),
        case('disp-date-fmt-slash', [E('type-date', 'date')], 'The date display option sets the format of date columns.', args=['--disp-date-fmt', '%d/%m/%Y']),
        case('disp-date-fmt-month', [E('type-date', 'date')], 'The date display option accepts month names.', args=['--disp-date-fmt', '%b %d']),
    ]


def analysis():
    return [
        case('freq-city', [E('freq-col', 'city')], 'A frequency table counts the rows per value and gives each share.'),
        case('freq-keys', [E('key-col-on', 'city'), E('key-col-on', 'id'), E('freq-keys')], 'A frequency table can group by several key columns.'),
        case('freq-summary', sel(0, 2) + [E('freq-summary')], 'The summary counts all rows and the selected rows.'),
        case('freq-aggregate-sum', [E('type-float', 'amount'), E('aggregate-col', 'amount', inp='sum'), E('freq-col', 'city')], 'An aggregator adds a column to frequency tables.'),
        case('freq-aggregate-max', [E('type-float', 'amount'), E('aggregate-col', 'amount', inp='max'), E('freq-col', 'city')], 'The max aggregator reports the largest value per bin.'),
        case('freq-aggregate-two', [E('type-float', 'amount'), E('aggregate-col', 'amount', inp='sum'), E('aggregate-col', 'amount', inp='count'), E('freq-col', 'city')], 'Several aggregators add several columns.'),
        case('freq-aggregate-median', [E('type-float', 'amount'), E('aggregate-col', 'amount', inp='median'), E('freq-col', 'city')], 'The median aggregator reports the middle value per bin.'),
        case('pivot', [E('key-col-on', 'city'), E('pivot', 'date')], 'A pivot table counts rows per key and pivot value.'),
        case('describe', [E('type-float', 'amount'), E('describe-sheet')], 'The describe sheet summarizes every column.'),
        case('transpose', [E('transpose')], 'Transposing swaps rows and columns.'),
        case('melt', [E('key-col-on', 'id'), E('melt')], 'Melting turns the other columns into variable and value rows.'),
        case('dedupe', [E('key-col-on', 'k', sheet='dups'), E('dedupe-rows', sheet='dups')], 'Rows that repeat the key columns are removed.', opens='dups.csv'),
        case('join-inner', [E('key-col-on', 'id'), open_entry('pets.csv'), E('key-col-on', 'owner', sheet='pets'), E('join-sheets-top2-inner', sheet='pets')], 'An inner join keeps only the keys present in both sheets.'),
        case('join-outer', [E('key-col-on', 'id'), open_entry('pets.csv'), E('key-col-on', 'owner', sheet='pets'), E('join-sheets-top2-outer', sheet='pets')], 'An outer join keeps the rows of the first sheet and adds unmatched rows of the others.'),
        case('join-append', [open_entry('pets.csv'), E('join-sheets-top2-append', sheet='pets')], 'An append stacks the rows of both sheets under the union of their columns.'),
        case('columns-sheet', [E('columns-sheet')], 'The columns sheet lists the columns of the sheet.'),
        case('reload', [E('delete-row', row=0), E('save-sheet', inp='reload-src.csv'), open_entry('reload-src.csv'),
                        E('delete-row', row=0, sheet='reload-src'), E('edit-cell', 'name', row=1, inp='QQ', sheet='reload-src'),
                        E('reload-sheet', sheet='reload-src')], 'Reloading a sheet discards its edits and reads its source file again.'),
    ]


def saving():
    return [
        case('save-json', [E('save-sheet', inp='saved.json')], 'save-sheet writes the sheet in the format of the file extension.', saved=[('saved.json', 'json')]),
        case('save-sorted-csv', [E('sort-desc', 'city', inp=DESC + 'city'), E('save-sheet', inp='saved.csv')], 'A saved sheet keeps its current row order.', saved=[('saved.csv', 'csv')]),
        case('save-sqlite', [E('save-sheet', inp='saved.sqlite')], 'A sheet can be saved as an SQLite table.', saved=[('saved.sqlite', 'sqlite')]),
        case('save-column', [E('save-col', 'city', inp='sc.csv')], 'save-col writes only the cursor column.', saved=[('sc.csv', 'csv')]),
        case('save-column-keys', [E('key-col-on', 'id'), E('save-col-keys', 'city', inp='sck.tsv')], 'save-col-keys writes the key columns with the cursor column.', saved=[('sck.tsv', 'tsv')]),
        case('save-all-directory', [open_entry('pets.csv'), E('sort-desc', 'owner', inp=DESC + 'owner', sheet='pets'), E('save-all', inp='alldir/', sheet='pets')], 'save-all with a directory name writes one file per sheet in its current order.', saved=[('alldir/pets.tsv', 'text')]),
    ]


def errors():
    return [
        case('err-copy-nothing', [E('copy-selected')], 'Copying selected rows without a selection stops the replay.', fails=True, nofile=True),
        case('err-cut-nothing', [E('cut-selected')], 'Cutting selected rows without a selection stops the replay.', fails=True),
        case('err-freq-no-keys', [E('freq-keys')], 'A frequency table over key columns needs key columns.', fails=True),
        case('err-contract-unknown', [E('contract-col', 'meta_k', sheet='data')], 'Contracting a column that does not exist stops the replay.', opens='data.json', fails=True),
        case('err-assert-cell', [E('assert-cell', 'city', row=1, inp='Paris')], 'A failed cell assertion stops the replay.', fails=True),
        case('err-search-next', [E('search-next')], 'Searching for the next match without a search stops the replay.', fails=True),
        case('err-save-source', [E('save-source')], 'Overwriting the source file needs a confirmation that batch mode cannot give.', fails=True),
        case('assert-cell-ok', [E('assert-cell', 'city', row=0, inp='Paris'), E('delete-row', row=3)], 'A true cell assertion lets the replay continue.'),
    ]


def episodes():
    groups = [('cmd-sorting', 'sorting', sorting()), ('cmd-selection', 'selection', selection()), ('cmd-rows', 'rows', rows()),
              ('cmd-columns', 'columns', columns()), ('cmd-expressions', 'expressions', expressions()),
              ('cmd-types', 'types', types()), ('cmd-analysis', 'analysis', analysis()), ('cmd-saving', 'saving', saving()),
              ('cmd-errors', 'errors', errors())]
    return [episode(key_, feature, cases) for key_, feature, cases in groups]
