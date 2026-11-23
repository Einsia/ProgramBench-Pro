"""micro's options (`help options`): the effect of each option that works offline, set in settings.json before the
editor starts (as a user's configuration would) or with the set command while it runs, and the rules of
settings.json itself (global and local values, glob and filetype sections, JSON5 syntax, errors).

Display options are checked through layout facts (rows, line numbers, which cells are drawn differently from their
neighbours, text attributes), never through exact colours.
"""
from spec_common import (SAVE, at, attrs, cmd, columns, config, contains, cursor, differ, family, file, gutter, key,
                         keys, listing, message, modify, panes, pos, process, row, rows, snap, status, tabs, typ,
                         wait, click)

TEXT = 'alpha beta gamma\nsecond line\nthird line\nfourth line\n'
CODE = 'def f(x):\n    if x:\n        return 1\n    return 2\n'
GO = 'package main\n\n// comment here\nfunc main() {\n\tx := 42\n\ts := "str"\n}\n'
LONG = ''.join(f'line {i:02d}\n' for i in range(1, 81))
LONGLINE = ' '.join(f'word{i:02d}' for i in range(1, 26)) + '\nshort\n'
BRACES = 'call(a, [b, c], {d: (e)})\n'


def s(settings, cid, goal, text, steps, checks, **kw):
    return row(cid, goal, text, steps, checks, settings=settings, **kw)


def f(requirement, check='file'):
    return ('file', requirement, check)


def m(requirement):
    return ('msg', requirement, 'msg')


def p(requirement):
    return ('pos', requirement, 'pos')


def r(requirement, start, end, snapshot=None):
    return ('rows', requirement, rows(start, end, snapshot))


EDITING = [
    s({'autoindent': False}, 'autoindent-off', 'With autoindent off, press Enter at the end of an indented line and '
      'type y.', CODE, [at(2, 10), key('Enter'), typ('y')], [f('The new line is not indented.')], save=True),
    s({'keepautoindent': True}, 'keepautoindent', 'With keepautoindent on, press Enter twice at the end of an indented '
      'line and type y.', CODE, [at(2, 10), key('Enter'), key('Enter'), typ('y')],
      [f('The indentation of the empty line is kept.')], save=True),
    s({'tabstospaces': True}, 'tabstospaces', 'With tabstospaces on, press Tab at column 3.', TEXT,
      [at(1, 3), key('Tab')], [f('Spaces up to the next tab stop are inserted.')], save=True),
    s({'tabstospaces': True, 'tabsize': 2}, 'tabstospaces-size', 'With tabstospaces and tabsize 2, press Tab at the '
      'start of line 2.', TEXT, [at(2, 1), key('Tab')], [f('Two spaces are inserted.')], save=True),
    s({'tabstospaces': True}, 'tabstospaces-backspace', 'With tabstospaces on, press Backspace after eight leading '
      'spaces.', '        x\n', [at(1, 9), key('Backspace')], [f('Backspace removes a whole tab width of spaces.')],
      save=True),
    s({'tabstospaces': True}, 'tabstospaces-indent-sel', 'With tabstospaces on, select two lines and press Tab.',
      TEXT, [at(1, 1), key('Shift+Down'), key('Shift+Down'), key('Tab')],
      [f('Selected lines are indented with spaces.')], save=True),
    s({'tabstospaces': True, 'tabmovement': True}, 'tabmovement', 'With tabstospaces and tabmovement on, press Left '
      'after eight leading spaces.', '        x\n', [at(1, 9), key('Left')],
      [p('Left moves over a whole tab width of spaces.')]),
    s({'tabstospaces': True, 'tabmovement': True}, 'tabmovement-right', 'With tabstospaces and tabmovement on, press '
      'Right at the start of eight leading spaces.', '        x\n', [key('Right')],
      [p('Right moves over a whole tab width of spaces.')]),
    s({'eofnewline': False}, 'eofnewline-off', 'With eofnewline off, edit a file without a final newline and save.',
      'abc', [typ('x')], [f('No newline is added at the end.')], save=True),
    s({'rmtrailingws': True}, 'rmtrailingws', 'With rmtrailingws on, type x and save a file with trailing blanks.',
      'abc   \nxyz\t\n', [typ('x')], [f('Trailing whitespace is removed on save.')], save=True),
    s({'smartpaste': True}, 'smartpaste', 'Paste an indented two-line block after an indented line.',
      '    head\n', [key('End'), key('Enter'), {'paste': '        one\n        two'}],
      [f('The pasted block takes the indentation of the line it is pasted into.')], save=True),
    s({'smartpaste': False}, 'smartpaste-off', 'With smartpaste off, paste the same indented block.', '    head\n',
      [key('End'), key('Enter'), {'paste': '        one\n        two'}], [f('The pasted text keeps its own indentation.')],
      save=True, req={'file': ['smartpaste/file']}),
    s({'autosave': 1}, 'autosave', 'With autosave 1, type x and wait two seconds without saving.', TEXT,
      [typ('x'), wait(2.5)], [f('The file is saved automatically.'),
                              ('status', 'The buffer is no longer modified.', status('modified'))]),
    s({'autosave': 30}, 'autosave-quit', 'With autosave on, type x and press Control+Q.', TEXT,
      [typ('x'), key('Control+Q')], [f('Quitting saves without asking.'), ('proc', 'micro exits.', 'process')],
      req={'proc': ['autosave-quit/file']}),
    s({'fastdirty': True}, 'fastdirty', 'With fastdirty on, type x and delete it again.', TEXT,
      [typ('x'), key('Backspace')], [('status', 'The buffer stays marked modified.', status('modified'))]),
    s(None, 'fastdirty-off', 'With the default fastdirty off, type x and delete it again.', TEXT,
      [typ('x'), key('Backspace')], [('status', 'The buffer is unmodified again.', status('modified'))],
      req={'status': ['fastdirty/status']}),
    s({'mkparents': True}, 'mkparents', 'With mkparents on, save to a path in missing directories.', TEXT,
      [cmd('save optnew/deep/file.txt')], [('new', 'The directories are created and the file is written.',
                                             file('optnew/deep/file.txt'))]),
    s({'readonly': True}, 'readonly', 'With readonly on, type zz.', TEXT, [typ('zz')],
      [('status', 'The status line shows [ro] and the buffer is unchanged.', status('readonly', 'modified')),
       ('rows', 'The text is unchanged.', rows(0, 1))]),
    s(None, 'readonly-setlocal', 'Run setlocal readonly on, then type zz and save.', TEXT,
      [cmd('setlocal readonly on'), typ('zz'), key('Control+S')],
      [m('Saving a read-only buffer is refused.'), f('The file is unchanged.')],
      req={'file': ['readonly-setlocal/msg']}),
]

SEARCHING = [
    s({'ignorecase': False}, 'ignorecase-off', 'With ignorecase off, search for ALPHA.', TEXT,
      [key('Control+F'), typ('ALPHA'), key('Enter')], [m('Nothing matches with case-sensitive search.')]),
    s(None, 'ignorecase-on', 'With the default ignorecase on, search for ALPHA.', TEXT,
      [key('Control+F'), typ('ALPHA'), key('Enter')], [p('The lower-case alpha matches.')]),
    s(None, 'incsearch', 'Type line in the find prompt without pressing Enter.', TEXT,
      [key('Control+F'), typ('line'), snap('typing')], [('pos', 'The cursor already moves to the first match.',
                                                          pos('typing'))]),
    s({'incsearch': False}, 'incsearch-off', 'With incsearch off, type line in the find prompt.', TEXT,
      [key('Control+F'), typ('line'), snap('typing')],
      [('pos', 'The cursor does not move while typing.', pos('typing'))], req={'pos': ['incsearch/pos']}),
    s({'hlsearch': True}, 'hlsearch-next-search', 'With hlsearch on, search, press Escape, then search again.', TEXT,
      [key('Control+F'), typ('line'), key('Enter'), key('Escape'), key('Control+F'), typ('line'), key('Enter')],
      [('cells', 'The next search highlights its matches again.', differ(((3, 9), (3, 2))))]),
    s({'hlsearch': True}, 'hlsearch-esc', 'With hlsearch on, search for line and press Escape.', TEXT,
      [key('Control+F'), typ('line'), key('Enter'), key('Escape')],
      [('cells', 'Escape removes the highlighting of the matches.', differ(((2, 8), (2, 2)), ((3, 9), (3, 2))))],
      req={'cells': ['hlsearch-next-search/cells']}),
]

DISPLAY = [
    s({'ruler': False}, 'ruler-off', 'Start with ruler off.', TEXT, [], [r('No line numbers are drawn.', 0, 2)]),
    s({'relativeruler': True}, 'relativeruler', 'With relativeruler on, move to line 3.', TEXT + 'fifth\nsixth\n',
      [at(3, 1)], [('gutter', 'Line numbers are relative to the cursor line, which shows its own number.',
                    gutter())]),
    s({'softwrap': True}, 'softwrap', 'Start with softwrap on.', LONGLINE, [], [r('The long line wraps.', 0, 3)]),
    s({'softwrap': True, 'wordwrap': True}, 'wordwrap', 'Start with softwrap and wordwrap on.', LONGLINE, [],
      [r('The long line wraps at a space.', 0, 3)]),
    s({'softwrap': True}, 'softwrap-down', 'With softwrap on, press Down from the start of the long line.', LONGLINE,
      [key('Down')], [p('Down moves to the next screen row of the same line.')]),
    s(None, 'nowrap-scroll', 'Without softwrap, press End on the long line.', LONGLINE, [key('End')],
      [r('The view scrolls horizontally to show the end of the line.', 0, 2)]),
    s({'scrollbar': True}, 'scrollbar', 'Start with scrollbar on in an 80-line file.', LONG, [],
      [('columns', 'A scroll bar is drawn at the right edge.', rows(0, 4))]),
    s({'scrollbar': True, 'scrollbarchar': '#'}, 'scrollbarchar', 'Start with scrollbar on and scrollbarchar #.',
      LONG, [], [r('The scroll bar uses #.', 0, 4)]),
    s({'scrollmargin': 0}, 'scrollmargin-0', 'With scrollmargin 0, move down to line 35.', LONG,
      [{'keys': ['Down'] * 34}], [('view', 'The view scrolls only when the cursor leaves it.', gutter(1))]),
    s(None, 'scrollmargin-default', 'With the default scrollmargin, move down to line 35.', LONG,
      [{'keys': ['Down'] * 34}], [('view', 'The view keeps three lines below the cursor.', gutter(1))]),
    s({'scrollmargin': 10}, 'scrollmargin-10', 'With scrollmargin 10, move down to line 30.', LONG,
      [{'keys': ['Down'] * 29}], [('view', 'The view keeps ten lines below the cursor.', gutter(1))]),
    s({'pageoverlap': 10}, 'pageoverlap', 'With pageoverlap 10, press PageDown.', LONG, [key('PageDown')],
      [p('PageDown moves the view height less ten lines.')]),
    s({'scrollspeed': 5}, 'scrollspeed', 'With scrollspeed 5, scroll the mouse wheel down once.', LONG,
      [{'mouse': {'action': 'scroll', 'row': 5, 'column': 10, 'direction': 'down'}}],
      [('view', 'The view scrolls five lines.', gutter(1))]),
    s(None, 'scrollspeed-default', 'Scroll the mouse wheel down once.', LONG,
      [{'mouse': {'action': 'scroll', 'row': 5, 'column': 10, 'direction': 'down'}}],
      [('view', 'By default the view scrolls two lines.', gutter(1))]),
    s({'showchars': 'space=.,tab=>'}, 'showchars', 'Start with showchars space=.,tab=>.', 'a b\n\tc  \n', [],
      [r('Spaces show as dots and tabs as >.', 0, 2)]),
    s({'showchars': 'ispace=_,itab=|'}, 'showchars-indent', 'Start with showchars ispace=_,itab=|.',
      '    a b\n\tc\td\n', [], [r('Only indentation characters are replaced.', 0, 2)]),
    s({'indentchar': '|'}, 'indentchar', 'Start with indentchar |.', '\tx\ny\tz\n', [],
      [r('Tabs are drawn starting with |.', 0, 2)]),
    s({'tabsize': 8}, 'tabsize-8', 'Start with tabsize 8.', 'a\tb\n\tc\n', [], [r('Tabs are eight columns wide.', 0, 2)]),
    s({'tabsize': 2}, 'tabsize-cursor', 'With tabsize 2, press End on a line with a tab.', 'a\tb\n', [key('End')],
      [('cursor', 'The tab after one character only fills up to the next tab stop, so End puts the terminal cursor '
                  'right after the b.', cursor('column'))]),
    s({'colorcolumn': 6}, 'colorcolumn', 'Start with colorcolumn 6.', TEXT, [],
      [('cells', 'Column 6 of the text is drawn differently from its neighbours.',
        differ(((1, 8), (1, 9)), ((2, 8), (2, 7)), ((2, 9), (2, 10))))]),
    s(None, 'cursorline', 'Start a file; the cursor is on line 1.', TEXT, [],
      [('cells', 'The cursor line is highlighted.', differ(((0, 4), (1, 4))))]),
    s({'cursorline': False}, 'cursorline-off', 'Start with cursorline off.', TEXT, [],
      [('cells', 'The cursor line looks like the others.', differ(((0, 4), (1, 4))))],
      req={'cells': ['cursorline/cells']}),
    s({'hltrailingws': True}, 'hltrailingws', 'Start with hltrailingws on and the cursor on line 2.',
      'abc   \nxyz\n', [key('Down')],
      [('cells', 'Trailing blanks of line 1 are highlighted.', differ(((0, 6), (0, 10))))]),
    s({'hltaberrors': True, 'tabstospaces': True}, 'hltaberrors-tab', 'With hltaberrors and tabstospaces on, open a '
      'file indented with a tab.', 'x\n\ty\n', [], [('cells', 'The tab is highlighted.', differ(((1, 3), (1, 9))))]),
    s({'hltaberrors': True}, 'hltaberrors-space', 'With hltaberrors on, open a file indented with spaces.',
      'x\n    y\n', [], [('cells', 'The indenting spaces are highlighted.', differ(((1, 3), (1, 9))))]),
    s(None, 'matchbrace', 'Put the cursor on the first opening parenthesis.', BRACES, [at(1, 5)],
      [('attrs', 'The matching closing parenthesis is underlined.', attrs((0, 26), (0, 25)))]),
    s({'matchbrace': False}, 'matchbrace-off', 'With matchbrace off, put the cursor on the parenthesis.', BRACES,
      [at(1, 5)], [('attrs', 'No brace is underlined.', attrs((0, 26), (0, 6)))],
      req={'attrs': ['matchbrace/attrs']}),
    s(None, 'matchbraceleft', 'Put the cursor just after the last closing parenthesis.', BRACES, [key('End')],
      [('attrs', 'The brace to the left of the cursor and its partner are underlined.', attrs((0, 6), (0, 26)))]),
    s({'matchbraceleft': False}, 'matchbraceleft-off', 'With matchbraceleft off, put the cursor after the last '
      'parenthesis.', BRACES, [key('End')], [('attrs', 'Nothing is underlined.', attrs((0, 6), (0, 26)))],
      req={'attrs': ['matchbraceleft/attrs']}),
    s({'matchbracestyle': 'highlight'}, 'matchbracestyle', 'With matchbracestyle highlight, put the cursor on the '
      'parenthesis.', BRACES, [at(1, 5)],
      [('attrs', 'The partner is not underlined ...', attrs((0, 26))),
       ('cells', '... but drawn in a highlight style.', differ(((0, 26), (0, 25))))],
      req={'attrs': ['matchbracestyle/cells']}),
    s({'fakecursor': True}, 'fakecursor', 'Start with fakecursor on.', TEXT, [key('Right')],
      [('cursor', 'The terminal cursor is hidden.', cursor('hidden')),
       ('cells', 'The cursor cell is drawn differently.', differ(((0, 3), (0, 4))))]),
    s({'syntax': False}, 'syntax-off', 'Open a Go file with syntax off.', GO, [],
      [('cells', 'A keyword looks like plain text.', differ(((0, 3), (0, 11))))], path='opt-syntax-off.go',
      req={'cells': ['syntax-on/cells']}),
    s(None, 'syntax-on', 'Open a Go file.', GO, [],
      [('cells', 'The keyword package is highlighted.', differ(((0, 3), (0, 11))))], path='opt-syntax-on.go'),
    s({'colorscheme': 'simple'}, 'colorscheme-simple', 'Open a file with the simple colour scheme.', TEXT, [],
      [('cells', 'The simple scheme does not highlight the cursor line.', differ(((0, 4), (1, 4))))],
      req={'cells': ['cursorline/cells']}),
    s({'divchars': '#='}, 'divchars', 'With divchars #=, open a vertical split.', TEXT, [cmd('vsplit')],
      [r('The vertical divider is drawn with #.', 0, 2)]),
    s({'divchars': '#=', 'statusline': False}, 'divchars-h', 'With divchars #= and statusline off, open a horizontal '
      'split.', TEXT, [cmd('hsplit')], [('contains', 'The horizontal divider is drawn with =.', contains('=' * 40))]),
    s({'divreverse': False}, 'divreverse-off', 'With divreverse off, open a vertical split.', TEXT, [cmd('vsplit')],
      [('attrs', 'The divider is not drawn in reverse.', attrs((5, 60)))], req={'attrs': ['divreverse/attrs']}),
    s(None, 'divreverse', 'Open a vertical split.', TEXT, [cmd('vsplit')],
      [('attrs', 'The divider is drawn in reverse.', attrs((5, 60)))]),
    s({'statusline': False}, 'statusline-off', 'Start with statusline off.', TEXT, [],
      [r('No status line is drawn.', 32, 36)], req={'rows': ['infobar-off/rows']}),
    s({'infobar': False}, 'infobar-off', 'Start with infobar off.', TEXT, [], [r('The status line is on the last row.', 33, 36)]),
    s({'keymenu': True}, 'keymenu', 'Start with keymenu on.', TEXT, [], [r('The key menu is shown.', 32, 36)]),
    s({'basename': True}, 'basename', 'With basename on, open a file in a subdirectory.', None, [],
      [('status', 'The status line shows only the base name.', status('name'))], path='optdir/deep.txt',
      files={'optdir/deep.txt': 'deep\n'}),
    s({'basename': True}, 'basename-tabs', 'With basename on, open two files of a subdirectory.', None, [],
      [('tabs', 'The tab bar shows base names.', tabs())], path='optdir2/b.txt', args=['optdir2/a.txt'],
      files={'optdir2/a.txt': 'a\n', 'optdir2/b.txt': 'b\n'}),
    s({'colorscheme': 'simple', 'tabreverse': False}, 'tabreverse-off', 'With the simple scheme and tabreverse off, '
      'open two files.', TEXT, [], [('attrs', 'The tab bar is not drawn in reverse.', attrs((0, 1), (0, 20)))],
      args=['opt-tr2.txt'], files={'opt-tr2.txt': '2\n'}, req={'attrs': ['tabreverse/attrs']}),
    s({'colorscheme': 'simple'}, 'tabreverse', 'With the simple scheme, open two files.', TEXT, [],
      [('attrs', 'By default the tab bar is drawn in reverse.', attrs((0, 1), (0, 20)))], args=['opt-tr3.txt'],
      files={'opt-tr3.txt': '3\n'}),
    s({'colorscheme': 'simple', 'tabhighlight': True}, 'tabhighlight', 'With the simple scheme and tabhighlight on, '
      'open two files.', TEXT, [], [('attrs', 'The tab names are drawn differently from the rest of the bar.',
                                     attrs((0, 1), (0, 14), (0, 20)))], args=['opt-th2.txt'],
      files={'opt-th2.txt': '2\n'}),
    s({'helpsplit': 'vsplit'}, 'helpsplit', 'With helpsplit vsplit, press Control+G.', TEXT, [key('Control+G')],
      [('columns', 'The help opens beside the file.', columns(0))]),
]

STATUS = [
    s({'statusformatl': '$(filename)|$(lines)|$(percentage)|$(opt:tabsize)|$(bind:Undo)'}, 'statusformat',
      'With a custom statusformatl, move to line 3.', TEXT, [at(3, 1)],
      [r('The directives are replaced by their values.', 34, 35)]),
    s({'statusformatl': '$(status.size)|$(status.bytes)|$(status.vcol)|$(status.lines)'}, 'statusformat-plugin',
      'With status plugin directives in statusformatl, move to column 3 of line 2.', TEXT, [at(2, 3)],
      [r('The status plugin fills in size, bytes, visual column and line count.', 34, 35)]),
    s({'statusformatl': '[$(modified)$(overwrite)]'}, 'statusformat-flags',
      'With statusformatl [$(modified)$(overwrite)], type x and press Insert.', TEXT, [typ('x'), key('Insert')],
      [r('The modified and overwrite markers are shown.', 34, 35)]),
    s({'statusformatr': '$(bind:FindNext) finds next'}, 'statusformatr', 'With a custom statusformatr, start.', TEXT,
      [], [r('The right part shows the key bound to FindNext.', 34, 35)]),
    s({'statusformatl': '$(opt:nosuch)|$(bind:NoSuchAction)|$(unknown)'}, 'statusformat-unknown',
      'With unknown directives in statusformatl, start.', TEXT, [], [r('Unknown directives show placeholders.', 34, 35)]),
    s({'paste': True}, 'paste-status', 'Start with paste on.', TEXT, [],
      [('status', 'The status line shows PASTE.', status('paste'))]),
]

FILES = [
    s({'fileformat': 'dos'}, 'fileformat-new', 'With fileformat dos, open a new file, type two lines and save.', None,
      [typ('one'), key('Enter'), typ('two')], [f('A new file is written with CRLF line endings.')], save=True,
      path='opt-ff-new.txt'),
    s(None, 'fileformat-set-dos', 'Run set fileformat dos and save.', TEXT, [cmd('set fileformat dos')],
      [f('The file is converted to CRLF line endings.')], save=True),
    s(None, 'fileformat-detect', 'Open a CRLF file, type x and save.', 'one\r\ntwo\r\n', [typ('x')],
      [f('CRLF line endings are kept.'), ('status', 'The status line shows dos.', status('fileformat'))], save=True),
    s(None, 'fileformat-to-unix', 'Open a CRLF file, run set fileformat unix and save.', 'one\r\ntwo\r\n',
      [cmd('set fileformat unix')], [f('The file is converted to LF line endings.')], save=True),
    s({'fileformat': 'dos'}, 'fileformat-existing', 'With fileformat dos, open an LF file and save.', TEXT,
      [typ('x')], [f('An existing file keeps its detected line endings.'),
                   ('status', 'The status line shows unix.', status('fileformat'))], save=True),
    s({'encoding': 'iso-8859-1'}, 'encoding-latin1', 'With encoding iso-8859-1, open a Latin-1 file.',
      {'base64': 'Y2Fm6SBuYe92ZQo='}, [], [r('The bytes are decoded as Latin-1.', 0, 1),
                                         ('status', 'The status line shows the encoding.', status('encoding'))]),
    s({'encoding': 'iso-8859-1'}, 'encoding-latin1-save', 'With encoding iso-8859-1, type X at the end and save.',
      {'base64': 'Y2Fm6SBuYe92ZQo='}, [key('End'), typ('X')], [f('The file is written back in Latin-1.')], save=True),
    s({'encoding': 'iso-8859-1'}, 'encoding-latin1-new', 'With encoding iso-8859-1, type é in a new file and save.',
      None, [typ('é')], [f('é is written as one Latin-1 byte.')], save=True, path='opt-enc-new.txt'),
    s({'encoding': 'utf-16le'}, 'encoding-utf16', 'With encoding utf-16le, open a UTF-16LE file, type x and save.',
      {'base64': 'aABpAAoA'}, [typ('x')], [r('The text is decoded.', 0, 1), f('It is written back as UTF-16LE.')],
      save=True),
    s({'encoding': 'shift_jis'}, 'encoding-sjis', 'With encoding shift_jis, open a Shift JIS file.',
      {'base64': 'k/qWe4zqCg=='}, [], [r('The bytes are decoded as Shift JIS.', 0, 1)]),
    s(None, 'encoding-invalid-utf8', 'Open a file with an invalid UTF-8 byte, type x at the start and save.',
      {'base64': 'Y2Fm6SBuYe92ZQo='}, [typ('x')],
      [f('Saving after an edit writes each invalid byte as U+FFFD (the replacement character).')], save=True),
    s(None, 'encoding-bad', 'Run set encoding nosuch.', TEXT, [cmd('set encoding nosuch')],
      [('msg', 'An unknown encoding is refused with an error message.', message(reported=True))]),
    s({'encoding': 'nosuch'}, 'encoding-bad-file', 'Start with an unknown encoding in settings.json.', TEXT, [],
      [('contains', 'micro reports the bad value at start.', contains('encoding'))]),
    s({'encoding': 'windows-1252'}, 'encoding-cp1252', 'With encoding windows-1252, open a Windows-1252 file, type € at '
      'the start and save.', {'base64': 'Y2Fm6Qo='}, [typ('€')],
      [f('The € and the é are written as Windows-1252 bytes.')], save=True),
    s({'encoding': 'gbk'}, 'encoding-gbk', 'With encoding gbk, open a GBK file, type 中 at the start and save.',
      {'base64': 'zsQK'}, [typ('中')], [f('The new and the existing Chinese characters are written as GBK.')],
      save=True),
]

LIFECYCLE = [
    s({'parsecursor': True}, 'parsecursor', 'With parsecursor on, start micro with FILE:3:2.', None, [],
      [p('The cursor starts at line 3, column 2.'), ('status', 'The file name is FILE.', status('name'))],
      path='opt-pc.txt', open_file=False, args=['opt-pc.txt:3:2'], files={'opt-pc.txt': TEXT}),
    s(None, 'parsecursor-off', 'Start micro with FILE:3:2 with the default parsecursor off.', None, [],
      [('status', 'The argument is taken as a new file name.', status('name', 'line'))],
      path='opt-pc2.txt', open_file=False, args=['opt-pc2.txt:3:2'], files={'opt-pc2.txt': TEXT}),
    s({'multiopen': 'vsplit'}, 'multiopen-vsplit', 'With multiopen vsplit, start with two files.', TEXT, [],
      [('columns', 'The files open side by side.', columns(0))], args=['opt-mo1.txt'], files={'opt-mo1.txt': 'mo1\n'}),
    s({'multiopen': 'hsplit'}, 'multiopen-hsplit', 'With multiopen hsplit, start with two files.', TEXT, [],
      [('panes', 'The files open one above the other.', panes('name'))], args=['opt-mo2.txt'],
      files={'opt-mo2.txt': 'mo2\n'}),
    s(None, 'multiopen-tab', 'Start with two files.', TEXT, [],
      [('tabs', 'By default each file opens in its own tab, the first one active.', tabs())], args=['opt-mo3.txt'],
      files={'opt-mo3.txt': 'mo3\n'}),
    s({'splitright': False}, 'splitright-off', 'With splitright off, vsplit another file.', TEXT,
      [cmd('vsplit opt-sr.txt')], [('columns', 'The new split opens on the left.', columns(0))],
      files={'opt-sr.txt': 'left side\n'}),
    s({'splitbottom': False}, 'splitbottom-off', 'With splitbottom off, hsplit another file.', TEXT,
      [cmd('hsplit opt-sb.txt')], [r('The new split opens on top.', 0, 1)], files={'opt-sb.txt': 'top side\n'}),
    s(None, 'reload-prompt', 'Change the open file on disk, then press Right.', TEXT,
      [modify('opt-life-reload-prompt.txt', 'from disk\n'), key('Right')], [m('micro asks whether to reload.')],
      path='opt-life-reload-prompt.txt'),
    s(None, 'reload-yes', 'Change the open file on disk, press Right and answer y.', TEXT,
      [modify('opt-life-reload-yes.txt', 'from disk\n'), key('Right'), key('y')],
      [r('The new content is loaded.', 0, 2)], path='opt-life-reload-yes.txt'),
    s(None, 'reload-no', 'Change the open file on disk, press Right and answer n.', TEXT,
      [modify('opt-life-reload-no.txt', 'from disk\n'), key('Right'), key('n')],
      [r('The old content stays.', 0, 2)], path='opt-life-reload-no.txt', req={'rows': ['reload-yes/rows']}),
    s({'reload': 'auto'}, 'reload-auto', 'With reload auto, change the open file on disk and press Right.', TEXT,
      [modify('opt-life-reload-auto.txt', 'from disk\n'), key('Right')], [r('The file reloads without asking.', 0, 2)],
      path='opt-life-reload-auto.txt'),
    s({'reload': 'disabled'}, 'reload-disabled', 'With reload disabled, change the open file on disk and press Right.',
      TEXT, [modify('opt-life-reload-disabled.txt', 'from disk\n'), key('Right')],
      [r('The old content stays without a question.', 0, 2), m('No question is asked.')],
      path='opt-life-reload-disabled.txt', req={'rows': ['reload-auto/rows'], 'msg': ['reload-prompt/msg']}),
    s(None, 'mouse-click', 'Click on line 3, column 4.', TEXT, [click(2, 5)], [p('The click moves the cursor.')]),
    s({'mouse': False}, 'mouse-off', 'With mouse off, click on line 3, column 4.', TEXT, [click(2, 5)],
      [p('The click does nothing.')], req={'pos': ['mouse-click/pos']}),
    s(None, 'clipboard-terminal', 'With clipboard terminal, copy a line and paste it.', TEXT,
      [cmd('set clipboard terminal'), key('Control+C'), key('Down'), key('Control+V')],
      [m('micro reports that the terminal sent no clipboard.')]),
    s({'useprimary': True}, 'useprimary', 'Double-click a word, press End, then middle-click.', TEXT,
      [click(0, 4, action='double'), key('End'), click(1, 13, button='middle')],
      [f('The middle click pastes the word selected with the mouse at the cursor.')], save=True),
    s({'useprimary': False}, 'useprimary-off', 'With useprimary off, double-click a word, press End, then middle-click.',
      TEXT, [click(0, 4, action='double'), key('End'), click(1, 13, button='middle')],
      [f('Nothing is pasted.')], save=True, req={'file': ['useprimary/file']}),
    s(None, 'primary-shift-select', 'Select a word with Shift+Right, press End, then middle-click.', TEXT,
      [keys('Shift+Right', 'Shift+Right', 'Shift+Right'), key('End'), click(1, 13, button='middle')],
      [f('A keyboard selection does not fill the primary selection.')], save=True,
      req={'file': ['useprimary/file']}),
]

SETTINGS = [
    s({'*.txt': {'tabsize': 8}}, 'glob', 'With a *.txt section setting tabsize 8, open a .txt file.', 'a\tb\n', [],
      [r('The glob section applies.', 0, 1)]),
    s({'*.txt': {'tabsize': 8}}, 'glob-other', 'With a *.txt section setting tabsize 8, open a .md file.', 'a\tb\n', [],
      [r('The glob section does not apply to other files.', 0, 1)], path='opt-set-glob.md',
      req={'rows': ['glob/rows']}),
    s({'ft:go': {'tabsize': 2}}, 'ft-section', 'With an ft:go section setting tabsize 2, open a Go file.', GO, [],
      [r('The filetype section applies.', 4, 5)], path='opt-set-ft.go'),
    s({'ft:go': {'tabsize': 2}}, 'ft-section-show', 'With an ft:go section setting tabsize 2, show tabsize in a Go file.',
      GO, [cmd('show tabsize')], [m('show reports the filetype value.')], path='opt-set-ft2.go'),
    s('{\n  // a comment\n  tabsize: 8,\n}\n', 'json5', 'With a settings.json in JSON5 (comment, bare key, trailing '
      'comma), open a file with a tab.', 'a\tb\n', [], [r('The JSON5 file is understood.', 0, 1)]),
    s('{"tabsize": ', 'bad-json', 'Start with a settings.json that is not valid JSON.', TEXT, [],
      [('rows', 'micro reports the broken settings.json at start (its words before the parser\'s detail).',
        rows(0, 3, cut=': '))]),
    s('{"tabsize": ', 'bad-json-set', 'With a broken settings.json, press Enter, then run set tabsize 3.', TEXT,
      [key('Enter'), cmd('set tabsize 3')], [('settings', 'micro does not overwrite a broken settings.json.',
                                              config('settings.json'))]),
    s({'tabsize': 'abc'}, 'bad-value', 'Start with a settings.json holding an invalid tabsize.', TEXT, [],
      [('rows', 'micro reports the setting with the wrong type at start.', rows(0, 3, cut=' ('))]),
    s({'nosuch': 1}, 'unknown-kept', 'With an unknown option in settings.json, run set tabsize 3.', TEXT,
      [key('Enter'), cmd('set tabsize 3')],
      [('settings', 'settings.json keeps the unknown entry and adds the new one.', config('settings.json'))]),
    s({'*.txt': {'tabsize': 8}}, 'glob-kept', 'With a glob section in settings.json, run set ruler false.', TEXT,
      [cmd('set ruler false')], [('settings', 'settings.json keeps the glob section.', config('settings.json'))]),
    s(None, 'set-global-panes', 'Open a vertical split of another file and run set tabsize 8.', 'a\tb\n',
      [cmd('vsplit opt-gl.txt'), cmd('set tabsize 8')],
      [('columns', 'set changes the option in every pane.', columns(0))], files={'opt-gl.txt': 'c\td\n'}),
    s(None, 'setlocal-panes', 'Open a vertical split of another file and run setlocal tabsize 8.', 'a\tb\n',
      [cmd('vsplit opt-lo.txt'), cmd('setlocal tabsize 8')],
      [('columns', 'setlocal changes only the active pane.', columns(0))], files={'opt-lo.txt': 'c\td\n'}),
    s({'tabsize': 8}, 'setlocal-not-saved', 'With tabsize 8 in settings.json, run setlocal tabsize 2.', 'a\tb\n',
      [cmd('setlocal tabsize 2')], [('settings', 'setlocal leaves settings.json alone.', config('settings.json')),
                                    r('The buffer uses the local value.', 0, 1)]),
    s({'tabsize': 8}, 'reset-to-default', 'With tabsize 8 in settings.json, run reset tabsize.', 'a\tb\n',
      [cmd('reset tabsize')], [('settings', 'reset removes the value from settings.json.', config('settings.json')),
                               r('The default tab size is used.', 0, 1)]),
]


def episodes():
    out = family('opt-edit', 'options', EDITING, 10)
    out += family('opt-search', 'options', SEARCHING, 10)
    out += family('opt-display', 'display', DISPLAY, 12)
    out += family('opt-status', 'display', STATUS, 10)
    out += family('opt-files', 'files', FILES, 10)
    out += family('opt-life', 'options', LIFECYCLE, 9)
    out += family('opt-set', 'settings', SETTINGS, 10)
    return out
