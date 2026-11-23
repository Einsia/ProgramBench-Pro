'''Interactive terminal behaviour: key sequences typed into the running application.

Every checkpoint restarts the application, opens a data file with the o key and its name, types a short key
sequence and reads layout-independent screen facts (cursor position, selected rows, sheet names, row counts, column
marks, table cells, prompt text) or the files and the input history the product wrote. The expected values come from
the frozen reference; the requirement text describes the behaviour and must also hold for an equivalent
reimplementation. Keys and command names are public input (help response, reference_controls).
'''
from spec_core import *
from spec_logs import GRID_ROWS

BS, DQ = chr(92), chr(34)
FIXTURES = {'grid.csv': csv_text(GRID_ROWS), 'sample.csv': SAMPLE, 'pets.csv': csv_text(PETS_ROWS)}
POSITION, SELECTED = scr('position'), scr('selected')
SHEET, COUNT, STACK, PROMPT = scr('sheet'), scr('count'), scr('stack'), scr('prompt')
NAMES, MARKS = scr('columns'), scr('columns', marks=True)


def cells(*names, limit=None):
    extra = {'limit': limit} if limit else {}
    return scr('table', columns=list(names), **extra)


def K(*names):
    return [key(name) for name in names]


def P(opener, text):
    '''Open a prompt with the key (or keys) of the opener, type the answer and confirm it.'''
    names = [opener] if isinstance(opener, str) else list(opener)
    return K(*names) + [typ(text), key('Enter')]


def go(cid, goal, steps, checks, opens='grid.csv', depends=(), requires=None):
    '''Restart, open the data file by name, then type the steps and check the result.'''
    return step(cid, goal, [{'restart': True}, {'open': opens}] + list(steps), checks, depends=depends, requires=requires)


def navigation():
    def at(cid, goal, steps, text):
        return go(cid, goal, steps, [('pos', text, POSITION)])
    return [
        at('down', 'Move the cursor down three rows.', K('Down', 'Down', 'Down'), 'Each press of Down moves the cursor one row down.'),
        at('right', 'Move the cursor right three columns.', K('Right', 'Right', 'Right'), 'Each press of Right moves the cursor one column right.'),
        at('left', 'Move right three columns, then left once.', K('Right', 'Right', 'Right', 'Left'), 'Left moves the cursor one column back.'),
        at('up', 'Jump to the last row, then move up once.', K('g', 'j', 'Up'), 'Up moves the cursor one row up.'),
        at('letter-keys', 'Move with the letter keys j, j, j, l.', K('j', 'j', 'j', 'l'), 'The letters j and l move like Down and Right.'),
        at('letter-keys-back', 'Move with the letter keys j, j, j, l, l, k, h.', K('j', 'j', 'j', 'l', 'l', 'k', 'h'), 'The letters k and h move like Up and Left.'),
        at('bottom', 'Jump to the last row.', K('g', 'j'), 'g then j moves the cursor to the last row.'),
        at('top', 'Move down twice and right once, then jump to the first row.', K('Down', 'Down', 'Right', 'g', 'k'), 'g then k moves the cursor to the first row and keeps the column.'),
        at('far-right', 'Jump to the last column.', K('g', 'l'), 'g then l moves the cursor to the last column.'),
        at('far-left', 'Move down and right, jump to the last column, then to the first.', K('Down', 'Right', 'g', 'l', 'g', 'h'), 'g then h moves the cursor to the first column and keeps the row.'),
    ]


def selection():
    rows = lambda text: ('rows', text, SELECTED)
    where = lambda text: ('pos', text, POSITION)
    return [
        go('s-key', 'Select rows with s; the cursor moves down after each selection.', K('s', 'Down', 's', 'Down', 'Down', 's'),
           [rows('Exactly the rows where s was pressed are selected.'), where('The cursor stands below the last selected row.')]),
        go('s-twice', 'Press s on a row, go back up and press s again.', K('s', 'Up', 's'), [rows('Pressing s on a selected row keeps it selected.')]),
        go('t-twice', 'Toggle three rows on with t, go up one row and toggle it off again.', K('t', 't', 't', 'Up', 't', 'Down'),
           [rows('Pressing t on a selected row unselects it.'), where('The cursor moves down after each toggle.')]),
        go('u-key', 'Select four rows, go up two rows and press u.', K('s', 's', 's', 's', 'Up', 'Up', 'u'),
           [rows('The u key unselects the cursor row.'), where('The cursor moves down after unselecting.')]),
        go('g-s', 'Select every row.', K('g', 's'), [rows('g then s selects all rows.')]),
        go('g-u', 'Select every row, then unselect every row.', K('g', 's', 'g', 'u'), [rows('g then u unselects all rows.')],
           requires={'rows': ['tui-selection/g-s/rows']}),
        go('regex-select', 'Select the rows whose city starts with B or R.', K('Right', 'Right') + P('|', '^[BR]'), [rows('A regular expression selects the rows that match in the cursor column.')]),
        go('regex-unselect', 'Select all rows, then unselect the rows whose city is Paris.', K('g', 's', 'Right', 'Right') + P(BS, 'Paris'), [rows('A regular expression unselects the rows that match in the cursor column.')]),
        go('equal-cell', 'Select the rows whose city equals the city at the cursor.', K('Right', 'Right', ','), [rows('Rows with the same value as the cursor cell are selected.')]),
        go('palette-toggle', 'Select one row, then run stoggle-rows from the command prompt.', K('s') + P('Space', 'stoggle-rows'), [rows('A command can be run by name from the command prompt.')]),
        go('palette-equal', 'On the second row of the city column, run select-equal-cell from the command prompt.', K('Right', 'Right', 'Down') + P('Space', 'select-equal-cell'),
           [rows('The named command selects the rows whose city equals the cursor cell.')]),
        go('dup-selected', 'Select two rows and open them in a new sheet with the double quote key.', K('s', 'Down', 'Down', 's', DQ),
           [('sheet', 'The selected rows open in a new sheet named after the source.', SHEET), ('count', 'The new sheet has one row per selected row.', COUNT), ('rows', 'It holds the selected rows.', cells('id'))]),
        go('delete-selected', 'Select two rows and delete the selected rows with g then d.', K('s', 'Down', 's', 'g', 'd'),
           [('count', 'Deleting the selection removes those rows.', COUNT), ('rows', 'The other rows remain in order.', cells('id'))]),
    ]


def searching():
    at = lambda text: ('pos', text, POSITION)
    return [
        go('forward', 'Search the city column for Ber.', K('Right', 'Right') + P('/', 'Ber'), [at('The search moves the cursor to the first match after it.')]),
        go('next', 'Search for Ber, then go to the next match with n.', K('Right', 'Right') + P('/', 'Ber') + K('n'), [at('n moves the cursor to the next match.')]),
        go('next-wrap', 'Search for Ber, then press n twice.', K('Right', 'Right') + P('/', 'Ber') + K('n', 'n'),
           [at('Searching past the last match wraps around to the first.'), ('note', 'Wrapping around is reported to the user.', scr('message'))]),
        go('previous', 'Search for Paris, go to the next match, then back with N.', K('Right', 'Right') + P('/', 'Paris') + K('n', 'N'), [at('N moves the cursor to the previous match.')]),
        go('backward', 'Search backward for Paris from the first row.', K('Right', 'Right') + P('?', 'Paris'),
           [at('A backward search from the first row wraps to the last match.'), ('note', 'Wrapping around is reported to the user.', scr('message'))]),
        go('column-only', 'Search the city column for a value that only exists in the name column.', K('Right', 'Right') + P('/', 'ali'), [at('The search only looks in the cursor column, so the cursor stays.')]),
    ]


def typing_and_sorting():
    def typed(cid, goal, steps, column, text):
        checks = [('marks', text + ' The header shows its type character.', MARKS)]
        if column:
            checks.append(('cells', 'The values of the column are shown in the type format.', cells(column)))
        return go(cid, goal, steps, checks)
    return [
        typed('int', 'Type the id column as integer.', K('#'), None, 'The # key types the cursor column as integer.'),
        typed('float', 'Type the amount column as float.', K('Right', 'Right', 'Right', '%'), 'amount', 'The % key types the cursor column as float.'),
        typed('date', 'Type the date column as date.', K('Right', 'Right', 'Right', 'Right', '@'), 'date', 'The @ key types the cursor column as date.'),
        typed('currency', 'Type the amount column as currency.', K('Right', 'Right', 'Right', '$'), None, 'The $ key types the cursor column as currency.'),
        typed('string', 'Type id as integer and then back as text.', K('#', '~'), None, 'The ~ key types the cursor column as text.'),
        go('sort-asc', 'Sort the grid by city ascending.', K('Right', 'Right', '['),
           [('marks', 'The sorted column shows an ascending marker.', MARKS), ('order', 'Rows are ordered by city, equal cities keeping their order.', cells('id'))]),
        go('sort-desc', 'Sort the grid by city descending.', K('Right', 'Right', ']'),
           [('marks', 'The sorted column shows a descending marker.', MARKS), ('order', 'Rows are ordered by city, highest first.', cells('id'))]),
        go('sort-float', 'Type amount as float and sort it descending.', K('Right', 'Right', 'Right', '%', ']'),
           [('marks', 'The column shows its type and its sort direction.', MARKS), ('order', 'Numbers sort by value and empty cells go last.', cells('id'))]),
        go('key-column', 'Make the name column a key column.', K('Right', '!'),
           [('marks', 'A key column is marked as a key.', MARKS), ('order', 'Key columns move to the left of the others.', cells('name', 'id', limit=3))]),
        go('sort-keys', 'Make the city column a key column and sort by the key columns.', K('Right', 'Right', '!', 'g', '['),
           [('marks', 'The key column carries the sort marker.', MARKS), ('order', 'Rows are ordered by the key column.', cells('city', 'id'))]),
    ]


def editing():
    cols = lambda text: ('cols', text, NAMES)
    return [
        go('edit-cell', 'Replace the name in the first row with Zed.', K('Right') + P('e', 'Zed'), [('cell', 'Typing at the edit prompt replaces the cell value.', cells('name', limit=2))]),
        go('add-expression', 'Add a column from the expression id*2.', P('=', 'id*2'),
           [cols('The expression becomes a new column named after it.'), ('cells', 'Untyped numbers are text, so the product repeats the text.', cells('id*2', limit=3))]),
        go('add-expression-int', 'Type id as integer and add a column from id*2.', K('#') + P('=', 'id*2'), [('cells', 'An integer column supports arithmetic in expressions.', cells('id*2', limit=3))]),
        go('add-expression-named', 'Add a column named up from city.upper().', K('Right', 'Right') + P('=', 'up=city.upper()'),
           [cols('The name before the equals sign names the new column.'), ('cells', 'The expression is evaluated for every row.', cells('up', limit=3))]),
        go('rename-column', 'Rename the name column to who.', K('Right') + P('^', 'who'), [cols('The column header shows the new name.')]),
        go('hide-column', 'Hide the name column.', K('Right', '-'), [cols('A hidden column is not shown.')]),
        go('unhide-columns', 'Hide the name column and show hidden columns again.', K('Right', '-', 'g', 'v'), [cols('g then v shows hidden columns again.')]),
        go('delete-row', 'Delete the first row.', K('d'), [('count', 'Deleting a row lowers the row count.', COUNT), ('rows', 'The other rows remain in order.', cells('id'))]),
        go('add-row', 'Add an empty row below the first row.', K('a'), [('rows', 'The new row is empty and sits below the cursor row.', cells('id', limit=3))]),
        go('copy-paste-row', 'Copy the first row and paste it below the third row.', K('y', 'Down', 'Down', 'p'), [('count', 'Pasting adds a row.', COUNT), ('rows', 'The copy sits below the cursor row.', cells('id'))]),
        go('undo-delete', 'Delete the first row, then undo.', K('d', 'Shift+U'),
           [('count', 'Undo restores the deleted row.', COUNT), ('rows', 'The rows are back in their original order.', cells('id'))],
           requires={'count': ['tui-editing/delete-row/count'], 'rows': ['tui-editing/delete-row/rows']}),
        go('redo-sort', 'Sort id descending, undo, then redo.', K(']', 'Shift+U', 'Shift+R'), [('rows', 'Redo applies the undone sort again.', cells('id'))]),
        go('undo-sort', 'Sort city ascending, then id descending, then undo once.', K('Right', 'Right', '[', 'Left', 'Left', ']', 'Shift+U'),
           [('rows', 'Undo reverts only the last sort.', cells('id'))],
           requires={'rows': ['tui-editing/redo-sort/rows']}),
        go('set-column', 'Select all rows and set the city column to X.', K('Right', 'Right', 'g', 's') + P(['g', 'e'], 'X'), [('cells', 'Every selected row gets the typed value.', cells('city'))]),
    ]


def sheets():
    return [
        go('freq', 'Open the frequency table of the city column.', K('Right', 'Right', 'Shift+F'),
           [('sheet', 'The table is a new sheet named after the source and the column.', SHEET), ('count', 'It has one row per distinct value.', COUNT),
            ('marks', 'It has the value column followed by count, percent and histogram columns.', MARKS),
            ('bins', 'Bins are listed by falling count with their counts and percentages.', cells('city', 'count', 'percent'))]),
        go('freq-bin-rows', 'Open the rows of the first frequency bin.', K('Right', 'Right', 'Shift+F', 'Enter'),
           [('sheet', 'The rows of a bin open in a sheet named after the value.', SHEET), ('count', 'The sheet has one row per row of the bin.', COUNT), ('rows', 'It holds the rows of the bin.', cells('id'))]),
        go('freq-select-bin', 'Select a frequency bin and return to the source sheet.', K('Right', 'Right', 'Shift+F', 's', 'q'), [('rows', 'Selecting a bin selects its rows in the source.', SELECTED)]),
        go('transpose', 'Transpose the sheet.', K('Shift+T'),
           [('sheet', 'The result is a new sheet.', SHEET), ('count', 'Rows and columns swap places.', COUNT), ('rows', 'Each column becomes a row.', scr('table', limit=3))]),
        go('pivot', 'Make city a key column and pivot on the date column.', K('Right', 'Right', '!', 'Right', 'Right', 'Shift+W'), [
            ('sheet', 'The pivot opens as a new sheet.', SHEET), ('count', 'It has one row per key.', COUNT), ('cols', 'It has one column per distinct pivot value.', NAMES), ('rows', 'Cells count the rows per key and value.', scr('table'))], opens='sample.csv'),
        go('columns-sheet', 'Open the columns sheet.', K('Shift+C'), [('count', 'It has one row per column.', COUNT), ('rows', 'It lists the columns with their widths.', cells('name', 'width'))]),
        go('sheets-stack', 'Open the sheets stack.', K('Shift+S'), [('count', 'It has one row per open sheet.', COUNT), ('rows', 'It lists the open sheets with their types.', cells('name', 'type'))]),
        go('quit-sheet', 'Quit the data sheet with q.', K('q'), [('stack', 'Quitting a sheet returns to the sheet below it.', STACK)]),
        go('quit-twice', 'Open the rows of the first frequency bin of the city column, then quit two sheets with q.', K('Right', 'Right', 'Shift+F', 'Enter', 'q', 'q'),
           [('stack', 'Each q closes only the top sheet.', STACK)]),
        go('quit-all', 'Open the frequency table of the city column, then quit every sheet at once with g then q.', K('Right', 'Right', 'Shift+F', 'g', 'q'),
           [('exited', 'g then q closes every sheet and ends the application.', scr('exited'))], requires={'exited': ['tui-sheets/quit-sheet/stack']}),
    ]


def session():
    fields = ['longname', 'input', 'keystrokes']
    return [
        go('log-custom', 'Sort the city column descending and save the command log as mylog.vdj with Control+D.', K('Right', 'Right', ']') + P('Control+D', 'mylog.vdj'),
           [('log', 'The saved log lists the opened sheets and the sort with their keystrokes.', file_('mylog.vdj', 'vdj', fields=fields)),
            ('files', 'The typed name replaces the suggested file name.', listing(names_only=True))]),
        go('log-default', 'Save the command log under the suggested name.', K('Control+D', 'Enter'),
           [('log', 'The suggested name is the name of the sheet.', file_('sample.vdj', 'vdj', fields=fields))], opens='sample.csv'),
        step('log-replay', 'Replay the command log saved from the terminal in batch mode.', [batch(['-p', 'mylog.vdj'], 'replayed.tsv')],
             [('sheet', 'The replayed log reproduces the sorted sheet.', file_('replayed.tsv', 'tsv'))], depends=['log-custom']),
    ]


def history_cases():
    kinds = ['expr', 'regex']
    return [
        go('hist-written', 'Type an expression and a search pattern at prompts.', P('=', 'id*3') + P('/', 'ali'),
           [('entries', 'Prompt inputs are appended to the input history with their prompt type.', history(types=kinds))]),
        go('hist-persist', 'After a restart, search the name column for bo.', K('Right') + P('/', 'bo'),
           [('entries', 'The input history survives a restart and new inputs are appended to it.', history(types=kinds))], depends=['hist-written']),
        go('hist-recall', 'Open the file prompt and recall the previous answer with the up key.', K('o', 'Up'), [('prompt', 'The up key recalls the previous input of that prompt.', PROMPT)]),
        go('prompt-escape', 'Open the expression prompt and cancel it with Escape.', K('=', 'Escape'),
           [('prompt', 'Escape closes the prompt.', PROMPT), ('cols', 'Cancelling adds no column.', NAMES)], requires={'prompt': ['tui-history/hist-written/entries'], 'cols': ['tui-history/hist-written/entries']}),
    ]


def episodes():
    fixtures = {name: f(data) for name, data in FIXTURES.items()}
    groups = [('tui-navigation', 'navigation', navigation()), ('tui-selection', 'selection', selection()),
              ('tui-search', 'search', searching()), ('tui-typing-sorting', 'sorting', typing_and_sorting()),
              ('tui-editing', 'editing', editing()), ('tui-sheets', 'sheets', sheets()),
              ('tui-session', 'session', session()), ('tui-history', 'history', history_cases())]
    return [program(key_, feature, fixtures, cps) for key_, feature, cps in groups]
