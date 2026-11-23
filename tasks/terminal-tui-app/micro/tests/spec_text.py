"""The mouse in the editing area (clicks, double and triple clicks, drags, split focus and split dividers, the command
bar) and text that is not plain ASCII: tabs, wide and combining characters, long lines, empty and unterminated
files, and line-ending details.
"""
from spec_common import (at, click, cmd, columns, family, file, key, keys, message, panes, pos, row, rows, status,
                         typ)

TEXT = 'alpha beta gamma\nsecond line here\nthird\n'


def f(requirement):
    return ('file', requirement, 'file')


def p(requirement):
    return ('pos', requirement, 'pos')


def drag(row_, col, to_row, to_col, clicks=1):
    data = {'action': 'drag', 'row': row_, 'column': col, 'to_row': to_row, 'to_column': to_col}
    if clicks > 1:
        data['clicks'] = clicks
    return {'mouse': data}


MOUSE = [
    row('click', 'Click on the "b" of beta.', TEXT, [click(0, 8)], [p('The cursor goes to the clicked character.')]),
    row('click-past-eol', 'Click to the right of the end of line 3.', TEXT, [click(2, 40)],
        [p('A click past the end of a line goes to its end.')]),
    row('click-below', 'Click below the last line.', TEXT, [click(20, 5)],
        [p('A click below the text goes to the last line.')]),
    row('click-gutter', 'Click on the line number of line 2.', TEXT, [click(1, 0)],
        [p('A click on the line numbers goes to the start of that line.')]),
    row('click-tab', 'Click in the middle of a tab character.', 'a\tb\n', [click(0, 4)],
        [p('A click inside a tab goes to the tab character.')]),
    row('double', 'Double-click "beta" and type X.', TEXT, [click(0, 9, action='double'), typ('X')],
        [f('A double click selects the word.')], save=True),
    row('double-punct', 'Double-click a dot and type X.', 'a.b\n', [click(0, 3, action='double'), typ('X')],
        [f('A double click on punctuation selects that character.')], save=True),
    row('triple', 'Triple-click line 2 and type X.', TEXT, [click(1, 5, action='triple'), typ('X')],
        [f('A triple click selects the whole line.')], save=True),
    row('drag', 'Drag from "a" of alpha to the "b" of beta and type X.', TEXT, [drag(0, 2, 0, 8), typ('X')],
        [f('A drag selects the text between the two positions.')], save=True),
    row('drag-lines', 'Drag from line 1 column 4 to line 2 column 4 and type X.', TEXT, [drag(0, 5, 1, 5), typ('X')],
        [f('A drag can span lines.')], save=True),
    row('drag-back', 'Drag from "gamma" back to "alpha" and type X.', TEXT, [drag(0, 14, 0, 4), typ('X')],
        [f('A backwards drag selects too.')], save=True),
    row('double-drag', 'Double-click "alpha", keep the button down on the second click and drag to "gamma", then '
        'type X.', TEXT, [drag(0, 3, 0, 15, clicks=2), typ('X')],
        [f('Dragging after a double click extends the selection by whole words.')], save=True),
    row('click-deselect', 'Select with Shift+Right, click elsewhere and type X.', TEXT,
        [keys('Shift+Right', 'Shift+Right'), click(1, 4), typ('X')], [f('A click drops the selection.')], save=True),
    row('click-copy-primary', 'Drag over "beta", click at the end of line 3, then middle-click.', TEXT,
        [drag(0, 8, 0, 12), click(2, 30), click(2, 30, button='middle')],
        [f('A mouse selection can be pasted with the middle button.')], save=True),
    row('split-focus', 'Open a vertical split, click in the left pane and type Z.', TEXT,
        [cmd('vsplit tx-side.txt'), click(1, 5), typ('Z')],
        [('columns', 'Clicking a pane makes it active.', columns(1))], files={'tx-side.txt': 'side\nside 2\n'}),
    row('divider-drag', 'Open a vertical split and drag the divider 20 columns to the left.', TEXT,
        [cmd('vsplit tx-side2.txt'), drag(5, 60, 5, 40)],
        [('rows', 'Dragging the divider resizes the splits.', rows(0, 1))], files={'tx-side2.txt': 'side\n'}),
    row('hdivider-drag', 'Open a horizontal split and drag its separating status line up.', TEXT,
        [cmd('hsplit tx-side3.txt'), drag(16, 10, 8, 10)],
        [('panes', 'Dragging the status line between splits resizes them.', panes('name'))],
        files={'tx-side3.txt': 'side\n'}),
    row('prompt-click', 'Type "set ruler of" in the command bar, click after "set", type x, Escape.', TEXT,
        [key('Control+E'), typ('set ruler of'), click(35, 5)],
        [('msg', 'A click in the command bar moves its cursor (shown by the terminal cursor).', 'msg'),
         ('cursor', 'The prompt cursor is where it was clicked.', {'kind': 'cursor', 'fields': ['row', 'column']})]),
    row('statusline-click', 'Click on the status line.', TEXT, [at(2, 3), click(34, 10)],
        [p('A click on the status line does not move the cursor.')]),
]

UNICODE = [
    row('wide-right', 'Move right over two CJK characters and type X.', '日本語\n', [keys('Right', 'Right'), typ('X')],
        [f('Each wide character is one step.'), ('pos', 'The column counts characters.', 'pos')], save=True),
    row('wide-cursor', 'Press Right twice on a line of CJK characters.', '日本語\n', [keys('Right', 'Right')],
        [('cursor', 'The terminal cursor moves two cells per wide character.',
          {'kind': 'cursor', 'fields': ['column']})]),
    row('wide-down', 'From column 3 of an ASCII line press Down onto a CJK line.', 'abcdef\n日本語\n',
        [keys('Right', 'Right', 'Down'), typ('X')], [f('Vertical movement keeps the visual column.')], save=True),
    row('combining', 'Move right over a letter with a combining accent and type X.', 'étude\n',
        [key('Right'), typ('X')], [f('A combining mark moves with its base letter.')], save=True),
    row('emoji', 'Move right over an emoji and type X.', '\U0001F600 smile\n', [key('Right'), typ('X')],
        [f('An emoji is one character.')], save=True),
    row('wide-backspace', 'Press End and Backspace on a CJK line.', '日本語\n', [key('End'), key('Backspace')],
        [f('Backspace removes a whole wide character.')], save=True),
    row('wide-render', 'Open a file mixing CJK and ASCII text.', 'a日b本c\nxyz\n', [],
        [('rows', 'Wide characters take two columns.', rows(0, 2))]),
    row('type-unicode', 'Type "café ☕".', TEXT, [typ('café ☕ ')], [f('Non-ASCII text is typed and saved as UTF-8.')],
        save=True),
    row('tab-col', 'Press End on a line with tabs.', 'a\tb\tc\n', [key('End')],
        [('pos', 'The column counts characters, not screen cells.', 'pos'),
         ('cursor', 'The screen cursor is past the expanded tabs.', {'kind': 'cursor', 'fields': ['column']})]),
    row('tab-visual-down', 'From column 9 of a long line press Down onto a tab-indented line and type X.',
        'abcdefghij\n\t\tz\n', [{'keys': ['Right'] * 8}, key('Down'), typ('X')],
        [f('The visual column is kept across tabs.')], save=True),
    row('no-final-newline', 'Open a file without a final newline, type x and save.', 'one\ntwo', [typ('x')],
        [f('A final newline is added on save.')], save=True),
    row('empty-file', 'Open an empty file, type x and save.', '', [typ('x')], [f('Typing into an empty file works.')],
        save=True),
    row('empty-save', 'Open an empty file and save it unchanged.', '', [],
        [f('Saving an empty buffer keeps the file empty.')], save=True, req={'file': ['empty-file/file']}),
    row('blank-lines-end', 'Open a file ending in blank lines and save.', 'x\n\n\n', [typ('y')],
        [f('Trailing blank lines are kept.')], save=True),
    row('crlf-lines', 'Open a CRLF file and press End on line 1.', 'one\r\ntwo\r\n', [key('End')],
        [('pos', 'The carriage return is not part of the line.', 'pos')]),
    row('mixed-endings', 'Open a file with mixed line endings, type x and save.', 'one\r\ntwo\nthree\r\n', [typ('x')],
        [f('A file with mixed endings is saved consistently.'), ('status', 'Its format is reported.',
                                                                 status('fileformat'))], save=True),
    row('bom', 'Open a UTF-8 file with a byte-order mark, type x and save.', '﻿hello\n', [typ('x')],
        [f('The byte-order mark is preserved or dropped as micro does.')], save=True),
    row('nul-byte', 'Open a file containing a NUL byte, type x at the end and save.',
        {'base64': 'YQBiCg=='}, [key('End'), typ('x')], [f('Binary bytes survive an edit.')], save=True),
    row('long-file-end', 'Open a file of 3000 lines and press Control+End.', ''.join(f'{i}\n' for i in range(3000)),
        [key('Control+End')], [('pos', 'The last line is reached.', 'pos'), ('rows', 'The ruler is wide enough.',
                                                                            rows(33, 34))]),
]


def episodes():
    return family('mouse', 'mouse', MOUSE, 10) + family('text', 'text', UNICODE, 10)
