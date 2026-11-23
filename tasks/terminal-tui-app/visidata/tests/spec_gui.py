'''Frontend goals: user goals the evaluator carries out in the running application with keys and typed text.

Every episode starts a fresh application showing the directory sheet. A goal names the data file to open (the o
key and its name) and the visible result to reach; each checkpoint carries one evaluator-judged point and backend
companions that read the resulting screen facts or files, so an inert shell cannot pass. Keys and command names
are public input (help response, reference_controls); equivalent keys, menu entries and commands are accepted.
The expected values come from the frozen reference; the requirement text describes the behaviour and must also
hold for an equivalent reimplementation.
'''
from spec_core import *
from spec_logs import GRID_ROWS
from spec_matrix import MIX_ROWS, SORT_COLS
from spec_tui import K, P, cells, POSITION, SELECTED, SHEET, COUNT, STACK, NAMES, MARKS, BS, DQ

FIX = {name: f(data) for name, data in (('grid.csv', csv_text(GRID_ROWS)), ('sample.csv', SAMPLE), ('pets.csv', csv_text(PETS_ROWS)), ('mix.csv', csv_text(MIX_ROWS)))}
TYPE_WORDS = {'#': 'integer', '%': 'float', '@': 'date', '$': 'currency'}
AT = [('pos', 'The cursor stands on the cell the goal names.', POSITION)]
PICKED = [('rows', 'Exactly the rows the goal names are selected.', SELECTED)]
SORTED = [('marks', 'The sorted column carries the sort marker.', MARKS), ('order', 'The rows follow the sort order of the column.', cells('id'))]
FIELDS = ['longname', 'input', 'keystrokes']


def OPEN(name):
    return [{'open': name}]


def R(n):
    return K(*['Right'] * n)


def D(n):
    return K(*['Down'] * n)


def goal(cid, text, steps, checks, accept, depends=(), bind=None):
    return step(cid, text, steps, checks, depends=depends, acceptance=accept, requires=dict({'done': [c[0] for c in checks]}, **(bind or {})))


def one(slug, feature, name, text, steps, checks, accept):
    full = 'Open %s with the o key and its name, then %s' % (name, text) if text else 'Open %s with the o key and its name.' % name
    return gui('gui-' + slug, feature, FIX, [goal('do', full, OPEN(name) + steps, checks, accept)])


def many(prefix, feature, table, checks):
    return [one(prefix + slug, feature, name, text, steps, checks, accept) for slug, name, text, steps, accept in table]


def navigation():
    table = [
        ('last-row', 'grid.csv', 'move the cursor to the last row, staying in the first column.', K('g', 'j'), 'The cursor is in the last row of the first column.'),
        ('last-col', 'grid.csv', 'move the cursor to the last column, staying in the first row.', K('g', 'l'), 'The cursor is in the first row of the last column.'),
        ('corner', 'grid.csv', 'move the cursor to the cell in the last row and the last column.', K('g', 'j', 'g', 'l'), 'The cursor is on the cell in the last row and the last column.'),
        ('cell-4-3', 'grid.csv', 'move the cursor down four rows and right three columns.', D(4) + R(3), 'The cursor is four rows down and three columns right of the top left cell.'),
        ('cell-5-2', 'grid.csv', 'move the cursor down five rows and right two columns.', D(5) + R(2), 'The cursor is five rows down and two columns right of the top left cell.'),
        ('cell-2-4', 'mix.csv', 'move the cursor down two rows and right four columns.', D(2) + R(4), 'The cursor is two rows down and four columns right of the top left cell.'),
        ('cell-9-6', 'mix.csv', 'move the cursor down nine rows and right six columns.', D(9) + R(6), 'The cursor is nine rows down and six columns right of the top left cell.'),
        ('letters', 'mix.csv', 'using only the letter keys j, k, h and l, move the cursor down ten rows and right six columns, then up two rows and left one column.', K(*(['j'] * 10 + ['l'] * 6 + ['k'] * 2 + ['h'])), 'The cursor is eight rows down and five columns right of the top left cell.'),
        ('sample-end', 'sample.csv', 'move the cursor to the last row and the last column.', K('g', 'j', 'g', 'l'), 'The cursor is on the cell in the last row and the last column.'),
        ('pets-end', 'pets.csv', 'move the cursor to the last row and the last column.', K('g', 'j', 'g', 'l'), 'The cursor is on the cell in the last row and the last column.'),
        ('top-again', 'mix.csv', 'move the cursor to the fourth column, go to the last row and then back to the first row.', R(3) + K('g', 'j', 'g', 'k'), 'The cursor is in the first row of the fourth column.'),
        ('left-again', 'mix.csv', 'move the cursor down three rows, go to the last column and then back to the first column.', D(3) + K('g', 'l', 'g', 'h'), 'The cursor is in the fourth row of the first column.'),
    ]
    walk = [
        goal('city', 'Open mix.csv with the o key and its name, then move the cursor to the city column, staying in the first row.', OPEN('mix.csv') + R(2), AT, 'The cursor is in the first row of the city column.'),
        goal('day', 'Move the cursor to the day column, staying in the first row.', R(3), AT, 'The cursor is in the first row of the day column.', depends=['city']),
        goal('code', 'Move the cursor to the code column, staying in the first row.', R(1), AT, 'The cursor is in the first row of the code column.', depends=['day']),
        goal('first', 'Move the cursor to the first column, staying in the first row.', K('g', 'h'), AT, 'The cursor is in the first row of the first column.', depends=['code']),
    ]
    return many('nav-', 'navigation', table, AT) + [gui('gui-nav-walk', 'navigation', FIX, walk)]


def selection():
    G, M = 'grid.csv', 'mix.csv'
    table = [
        ('first-three', G, 'select the first three rows, one after the other.', K('s', 's', 's'), 'The first three rows are marked as selected.'),
        ('odd-rows', G, 'select the first, third and fifth rows and no other row.', K('s', 'Down', 's', 'Down', 's'), 'Only the first, third and fifth rows are marked as selected.'),
        ('last-two', G, 'select the last two rows.', K('g', 'j', 's', 'Up', 's'), 'Only the last two rows are marked as selected.'),
        ('toggle', G, 'toggle on the second and fourth rows.', K('Down', 't', 'Down', 't'), 'Only the second and fourth rows are marked as selected.'),
        ('regex-b', G, 'select the rows whose city starts with B, using the select by regular expression key.', R(2) + P('|', '^B'), 'Only the rows of the cities that start with B are marked as selected.'),
        ('regex-r', G, 'select the rows whose city starts with R, using the select by regular expression key.', R(2) + P('|', '^R'), 'Only the rows of the cities that start with R are marked as selected.'),
        ('regex-p', G, 'select the rows whose city starts with P, using the select by regular expression key.', R(2) + P('|', '^P'), 'Only the rows of the cities that start with P are marked as selected.'),
        ('regex-o', G, 'select the rows whose city starts with O, using the select by regular expression key.', R(2) + P('|', '^O'), 'Only the row of the city that starts with O is marked as selected.'),
        ('regex-name', G, 'select the rows whose name starts with b, c, d or e, using the select by regular expression key.', R(1) + P('|', '^[b-e]'), 'Only the rows whose name starts with b, c, d or e are marked as selected.'),
        ('unselect-paris', G, 'select every row and then unselect the rows whose city is Paris, using the unselect by regular expression key.', K('g', 's') + R(2) + P(BS, 'Paris'), 'Every row except the Paris rows is marked as selected.'),
        ('unselect-rome', G, 'select every row and then unselect the rows whose city is Rome, using the unselect by regular expression key.', K('g', 's') + R(2) + P(BS, 'Rome'), 'Every row except the Rome rows is marked as selected.'),
        ('same-rome', M, 'select every row whose city is the same as the city of the fourth row, using the select equal cells key.', D(3) + R(2) + K(','), 'The rows with the same city as the fourth row are marked as selected.'),
        ('same-paris', M, 'select every row whose city is the same as the city of the first row, using the select equal cells key.', R(2) + K(','), 'The rows with the same city as the first row are marked as selected.'),
        ('mix-code', M, 'select the rows whose code starts with the letter A in either case, using the select by regular expression key.', R(6) + P('|', '^A'), 'Only the rows whose code starts with A or a are marked as selected.'),
        ('mix-name', M, 'select the rows whose name starts with one of the letters f to j in either case, using the select by regular expression key.', R(1) + P('|', '^[f-j]'), 'Only the rows whose name starts with one of the letters f to j, in either case, are marked as selected.'),
        ('mix-city', M, 'select the rows whose city starts with Ber or ber, using the select by regular expression key.', R(2) + P('|', '^[Bb]er'), 'Only the rows whose city starts with Ber or ber are marked as selected.'),
    ]
    out = many('sel-', 'selection', table, PICKED)
    out.append(gui('gui-sel-clear', 'selection', FIX, [
        goal('all', 'Open grid.csv with the o key and its name, then select every row.', OPEN(G) + K('g', 's'), PICKED, 'Every row is marked as selected.'),
        goal('none', 'Unselect every row again.', K('g', 'u'), PICKED, 'No row is marked as selected.', depends=['all'], bind={'rows': ['gui-sel-clear/all/rows']})]))
    out.append(one('sel-dup', 'selection', G, 'select the second and third rows and open them in a sheet of their own.', K('Down', 's', 's', DQ),
                   [('sheet', 'The selected rows open in a new sheet named after the source.', SHEET), ('rows', 'It holds the selected rows.', cells('id'))],
                   'A new sheet shows exactly the second and third rows of the table.'))
    out.append(one('sel-delete', 'selection', G, 'select the first three rows and delete the selected rows.', K('s', 's', 's', 'g', 'd'),
                   [('rows', 'The other rows remain in order.', cells('id'))],
                   'The first three rows are gone and the other rows remain.'))
    return out


def searching():
    G = 'grid.csv'
    table = [
        ('ber', G, 'search the city column for Ber and stop on the first match.', R(2) + P('/', 'Ber'), 'The cursor is on the first row whose city starts with Ber.'),
        ('paris-next', G, 'search the city column for Paris, then press n once to go on to the next match.', R(2) + P('/', 'Paris') + K('n'), 'The cursor is on the row of gina, the Paris match after the one the search found.'),
        ('rome', G, 'search the city column for Rome.', R(2) + P('/', 'Rome'), 'The cursor is on the first Rome row.'),
        ('oslo-wrap', G, 'search the city column for Oslo and press n once more.', R(2) + P('/', 'Oslo') + K('n'), 'The cursor is on the Oslo row again after wrapping around.'),
        ('berlin-back', G, 'search the city column backward for Berlin from the first row.', R(2) + P('?', 'Berlin'), 'The cursor is on the last Berlin row.'),
        ('paris-prev', G, 'search the city column for Paris, press n once to go on to the next match and then N once to go back to the previous match.', R(2) + P('/', 'Paris') + K('n', 'N'), 'The cursor is back on the row of carol, the Paris match the search found.'),
        ('name', G, 'search the name column for gin.', R(1) + P('/', 'gin'), 'The cursor is on the row of gina.'),
    ]
    return many('find-', 'search', table, AT)


def sorting():
    out = []
    for n, col in enumerate(SORT_COLS):
        for mark, word in (('[', 'ascending'), (']', 'descending')):
            out.append(one('sort-%s-%s' % (col, word[:3]), 'sorting', 'mix.csv', 'sort the table by the %s column, %s, leaving the column untyped so that its values sort as text.' % (col, word), R(n) + K(mark), SORTED, 'The %s column is untyped and the rows are ordered %s by its values compared as text.' % (col, word)))
    for col, mark_type, n in (('qty', '#', 3), ('price', '%', 4)):
        for mark, word in (('[', 'ascending'), (']', 'descending')):
            out.append(one('sort-%s-typed-%s' % (col, word[:3]), 'sorting', 'mix.csv', 'make the %s column %s and sort the table by it, %s.' % (col, TYPE_WORDS[mark_type], word), R(n) + K(mark_type, mark), SORTED, 'The %s column is typed as %s and the rows are ordered %s by its value.' % (col, TYPE_WORDS[mark_type], word)))
    return out


def typing():
    table = [('id', '#', 0), ('id', '%', 0), ('qty', '#', 3), ('qty', '%', 3), ('price', '%', 4), ('price', '$', 4), ('day', '@', 5)]
    return [one('type-%s-%s' % (col, TYPE_WORDS[k]), 'types', 'mix.csv', 'make the %s column %s.' % (col, TYPE_WORDS[k]), R(n) + K(k),
                [('marks', 'The header shows the type of the column.', MARKS)] + ([] if k == '$' or (k == '%' and col in ('id', 'qty')) else [('cells', 'The values are shown in the type format.', cells(col))]),
                'The header of the %s column shows the %s type.' % (col, TYPE_WORDS[k])) for col, k, n in table]


def columns():
    out = []
    for n, col in enumerate(SORT_COLS):
        out.append(one('hide-' + col, 'columns', 'mix.csv', 'hide the %s column.' % col, R(n) + K('-'), [('cols', 'A hidden column is not shown.', NAMES)], 'The %s column is no longer shown.' % col))
    for n, col in enumerate(SORT_COLS[1:], 1):
        out.append(one('key-' + col, 'columns', 'mix.csv', 'make the %s column the only key column.' % col, R(n) + K('!'), [('marks', 'A key column is marked as a key and moves to the left.', MARKS)], 'The %s column is the only key column and stands at the left.' % col))
    for n, col, new in ((1, 'name', 'who'), (2, 'city', 'town'), (3, 'qty', 'pcs'), (4, 'price', 'cost')):
        out.append(one('rename-' + col, 'columns', 'mix.csv', 'rename the %s column to %s.' % (col, new), R(n) + P('^', new), [('cols', 'The header shows the new name.', NAMES)], 'The %s column is now named %s.' % (col, new)))
    return out


def editing():
    G = 'grid.csv'
    cols = ('cols', 'The new column is named after the expression.', NAMES)
    count_rows = [('rows', 'The other rows remain in order.', cells('id'))]

    def new(slug, text, steps, name, accept):
        return one(slug, 'editing', G, text, steps, [cols, ('cells', 'The expression is evaluated for the rows.', cells(name, limit=3))], accept)
    return [
        one('edit-name', 'editing', G, 'replace the name in the first row with Zed and confirm the edit with Enter.', R(1) + P('e', 'Zed'), [('cell', 'The edited cell holds the typed value.', cells('name', limit=2))], 'The first row shows Zed as its name.'),
        one('edit-city', 'editing', G, 'replace the city in the second row with Lyon and confirm the edit with Enter.', D(1) + R(2) + P('e', 'Lyon'), [('cell', 'The edited cell holds the typed value.', cells('city', limit=3))], 'The second row shows Lyon as its city.'),
        one('edit-amount', 'editing', G, 'replace the amount in the third row with 99 and confirm the edit with Enter.', D(2) + R(3) + P('e', '99'), [('cell', 'The edited cell holds the typed value.', cells('amount', limit=4))], 'The third row shows 99 as its amount.'),
        new('expr-double', 'with the cursor in the id column, add a column from the expression id*2.', P('=', 'id*2'), 'id*2', 'A column named id*2 is added to the table.'),
        one('expr-typed', 'editing', G, 'make the id column integer and, with the cursor still in the id column, add a column from the expression id*2.', K('#') + P('=', 'id*2'), [('marks', 'The id header shows the integer type.', MARKS), ('cells', 'Integer arithmetic doubles the ids.', cells('id*2', limit=3))], 'A column named id*2 holds the doubled ids.'),
        new('expr-upper', 'move the cursor to the city column and add a column named up from the expression city.upper().', R(2) + P('=', 'up=city.upper()'), 'up', 'A column named up holds the cities in capital letters.'),
        new('expr-length', 'move the cursor to the name column and add a column named length from the expression len(name).', R(1) + P('=', 'length=len(name)'), 'length', 'A column named length holds the length of each name.'),
        one('delete-first', 'editing', G, 'delete the first row.', K('d'), count_rows, 'The first row is gone.'),
        one('delete-fourth', 'editing', G, 'delete the fourth row.', D(3) + K('d'), count_rows, 'The fourth row is gone.'),
        one('delete-last', 'editing', G, 'delete the last row.', K('g', 'j', 'd'), count_rows, 'The last row is gone.'),
        one('add-first', 'editing', G, 'add an empty row below the first row.', K('a'), [('rows', 'The new row is empty and sits below the cursor row.', cells('id', limit=5))], 'An empty row sits below the first row.'),
        one('add-third', 'editing', G, 'add an empty row below the third row.', D(2) + K('a'), [('rows', 'The new row is empty and sits below the cursor row.', cells('id', limit=5))], 'An empty row sits below the third row.'),
        one('copy-paste', 'editing', G, 'copy the first row and paste it below the third row.', K('y', 'Down', 'Down', 'p'), count_rows, 'A copy of the first row sits below the third row.'),
        one('undo-delete', 'editing', G, 'delete the first row and then undo the deletion.', K('d', 'Shift+U'), count_rows, 'The deleted row is back in its place.'),
        one('redo-sort', 'editing', G, 'sort the id column descending, undo the sort and redo it.', K(']', 'Shift+U', 'Shift+R'), [('rows', 'Redo applies the undone sort again.', cells('id'))], 'The rows are ordered by id, highest first.'),
        one('set-column', 'editing', G, 'select every row and set the city column of the selected rows to X.', K('g', 's') + R(2) + P(['g', 'e'], 'X'), [('cells', 'Every selected row gets the typed value.', cells('city'))], 'Every row shows X as its city.'),
        one('unhide', 'editing', G, 'hide the name column and then show the hidden columns again.', R(1) + K('-', 'g', 'v'), [('cols', 'Showing hidden columns brings them back.', NAMES)], 'The name column is shown again.'),
    ]


def sheets():
    G, M = 'grid.csv', 'mix.csv'
    stage = [('sheet', 'The table is a new sheet named after the source.', SHEET), ('count', 'It has the number of rows the goal names.', COUNT)]
    out = []
    for n, col in ((2, 'city'), (3, 'qty'), (5, 'day'), (6, 'code')):
        out.append(one('freq-' + col, 'sheets', M, 'open the frequency table of the %s column.' % col, R(n) + K('Shift+F'), stage[:1] + [('bins', 'Bins are listed with their counts.', cells(col, 'count'))], 'A frequency table of the %s column is shown with one row per distinct value and its count.' % col))
    for name, n in ((M, 2), (G, 2)):
        out.append(one('freq-rows-' + name.split('.')[0], 'sheets', name, 'open the frequency table of the city column and then the rows of its first bin.', R(n) + K('Shift+F', 'Enter'), stage[:1] + [('rows', 'It holds the rows of the bin.', cells('id'))], 'The rows of the first frequency bin are shown in a sheet of their own.'))
    for name in (G, 'pets.csv'):
        out.append(one('transpose-' + name.split('.')[0], 'sheets', name, 'transpose the table.', K('Shift+T'), stage + [('rows', 'Each column becomes a row.', scr('table', limit=3))], 'Rows and columns of the table have swapped places.'))
    pivot = stage[:1] + [('cols', 'It has one column per distinct pivot value.', NAMES), ('rows', 'Cells count the rows per key and value.', scr('table'))]
    out.append(one('pivot-sample', 'sheets', 'sample.csv', 'make city a key column and pivot on the date column.', K('Right', 'Right', '!', 'Right', 'Right', 'Shift+W'), pivot, 'A pivot table counts the rows per city and date.'))
    out.append(one('pivot-pets', 'sheets', 'pets.csv', 'make owner a key column and pivot on the pet column.', K('!', 'Right', 'Shift+W'), pivot, 'A pivot table counts the rows per owner and pet.'))
    for name in (G, 'pets.csv', M):
        out.append(one('columns-' + name.split('.')[0], 'sheets', name, 'open the columns sheet.', K('Shift+C'), [('rows', 'It lists every column of the table by name.', cells('name'))], 'A sheet lists every column of the table.'))
    out.append(one('stack', 'sheets', 'pets.csv', 'open the sheets stack.', K('Shift+S'), [('count', 'It has one row per open sheet.', COUNT), ('rows', 'It lists the open sheets with their types.', cells('name', 'type'))], 'A sheet lists the open sheets.'))
    out.append(one('quit-sheet', 'sheets', G, 'quit the data sheet.', K('q'), [('stack', 'Quitting a sheet returns to the sheet below it.', STACK)], 'The table is closed and the sheet below it is shown.'))
    out.append(one('quit-all', 'sheets', G, 'quit every sheet at once.', K('g', 'q'), [('exited', 'The application ends.', scr('exited'))], 'The application has ended.'))
    return out


def session():
    return [
        one('log-custom', 'session', 'grid.csv', 'sort the table by the city column descending and save the command log as mylog.vdj.', R(2) + K(']') + P('Control+D', 'mylog.vdj'),
            [('log', 'The saved log lists the opened sheets and the sort.', file_('mylog.vdj', 'vdj', fields=FIELDS)), ('files', 'The typed name replaces the suggested file name.', listing(names_only=True))],
            'The command log is saved under the name mylog.vdj.'),
        one('log-default', 'session', 'sample.csv', 'save the command log under the suggested name.', K('Control+D', 'Enter'),
            [('log', 'The suggested name is the name of the sheet.', file_('sample.vdj', 'vdj', fields=FIELDS))], 'The command log is saved under the suggested name.'),
    ]


def opening():
    out = []
    for name, names in (('pets.csv', ('owner', 'pet')), ('sample.csv', ('id', 'name', 'city')), ('mix.csv', ('id', 'name', 'price')), ('grid.csv', ('id', 'city', 'date'))):
        out.append(one('open-' + name.split('.')[0], 'files', name, '', [], [('sheet', 'The file opens as a sheet named after it.', SHEET), ('rows', 'The table shows the records of the file.', cells(*names))], 'The file is open as a table showing its records.'))
    return out


def episodes():
    return navigation() + selection() + searching() + sorting() + typing() + columns() + editing() + sheets() + session() + opening()
