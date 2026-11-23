"""micro's bindable actions that have no default key, and the bindings.json syntax.

Each checkpoint starts micro with its own bindings.json (F5/F6 bound to the action under test unless stated), moves
to a position with the arrow keys, presses the bound key and checks the cursor, the saved file, the view (the
first line number in the gutter) or the message line.
"""
from spec_common import (at, cmd, columns, differ, family, file, gutter, key, keys, message, panes, pos, process,
                         row, rows, snap, status, tabs, typ, wait, click)

WORDS = 'camelCaseWord snake_case_word  tail\nsecond line\n    indented text here\n\npara two\nlast line\n'
TEXT = 'alpha beta gamma\nsecond line\nthird line\nfourth line\n'
LONG = ''.join(f'line {i:02d}\n' for i in range(1, 81))
BRACES = 'call(a, [b, c], {d: (e)})\n'
PARA = 'p1 one\np1 two\n\np2 one\np2 two\n\np3 one\n'


def act(cid, action, text, start, names, checks, *, save=False, req=None, args=(), files=None, goal=None,
        settings=None):
    """action: the action bound to F5, a dict of bindings, or None for the default bindings. names: key names, or
    step dicts (typed text, commands) mixed with them."""
    bindings = {} if action is None else {'F5': action} if isinstance(action, str) else dict(action)
    steps, run = list(at(*start)), []
    for item in names:
        if isinstance(item, str):
            run.append(item)
            continue
        if run:
            steps.append(keys(*run))
            run = []
        steps.append(item)
    if run:
        steps.append(keys(*run))
    if goal is None:
        label = ', '.join(f'{k} to {v}' for k, v in bindings.items()) or 'the default bindings'
        pressed = ', '.join(i if isinstance(i, str) else next(iter(i.values())) if len(i) == 1 else str(i)
                            for i in names)
        goal = f'With {label}, press {pressed}.'
    return row(cid, goal, text, steps, checks, bindings=bindings, settings=settings, save=save, req=req, args=args,
               files=files)


def p(requirement):
    return ('pos', requirement, 'pos')


def f(requirement):
    return ('file', requirement, 'file')


def m(requirement):
    return ('msg', requirement, 'msg')


def view(requirement, limit=1):
    return ('view', requirement, gutter(limit))


MOTION = [
    act('subword-right', 'SubWordRight', WORDS, (1, 1), ['F5'], [p('SubWordRight stops at the next camel-case part.')]),
    act('subword-right2', 'SubWordRight', WORDS, (1, 1), ['F5', 'F5', 'F5'],
        [p('Repeated SubWordRight walks the parts, then the space.')]),
    act('subword-snake', 'SubWordRight', WORDS, (1, 15), ['F5', 'F5'],
        [p('SubWordRight stops at underscores in snake_case.')]),
    act('subword-left', 'SubWordLeft', WORDS, (1, 14), ['F5'], [p('SubWordLeft goes back to the last part.')]),
    act('subword-left2', 'SubWordLeft', WORDS, (1, 30), ['F5', 'F5'],
        [p('SubWordLeft goes back part by part in snake_case.')]),
    act('cursor-view-top', 'CursorToViewTop', LONG, (20, 3), ['F5'],
        [p('CursorToViewTop moves to the first line of the view.')], req={'pos': ['cursor-view-center/pos']}),
    act('cursor-view-center', 'CursorToViewCenter', LONG, (2, 3), ['F5'],
        [p('CursorToViewCenter moves to the middle line of the view.')]),
    act('cursor-view-bottom', 'CursorToViewBottom', LONG, (2, 3), ['F5'],
        [p('CursorToViewBottom moves near the bottom of the view, keeping the scroll margin.')]),
    act('start-of-line', 'StartOfLine', WORDS, (3, 12), ['F5'],
        [p('StartOfLine goes to column 1 even on an indented line.')]),
    act('jump-brace', 'JumpToMatchingBrace', BRACES, (1, 5), ['F5'],
        [p('From an opening parenthesis the cursor jumps to its partner.')]),
    act('jump-brace-back', 'JumpToMatchingBrace', BRACES, (1, 25), ['F5'],
        [p('From a closing parenthesis the cursor jumps back.')]),
    act('jump-brace-left', 'JumpToMatchingBrace', BRACES, (1, 15), ['F5'],
        [p('Just after a closing bracket the brace to the left is matched.')]),
    act('jump-brace-none', 'JumpToMatchingBrace', BRACES, (1, 3), ['F5'],
        [p('Away from any brace the cursor does not move.')], req={'pos': ['jump-brace/pos']}),
    act('center', 'Center', LONG, (30, 1), ['F5'], [view('Center scrolls so the cursor line is in the middle.'),
                                                    p('The cursor stays on its line.')]),
    act('view-end', 'End', LONG, (1, 1), ['F5'], [view('End scrolls the view to the end of the buffer.')]),
    act('view-start', {'F5': 'End', 'F6': 'Start'}, LONG, (1, 1), ['F5', 'F6'],
        [view('Start scrolls the view back to the top.')], req={'view': ['view-end/view']}),
    act('view-pagedown', 'PageDown', LONG, (1, 1), ['F5'],
        [view('PageDown scrolls the view by a page.'), p('The view-only action does not move the cursor.')],
        req={'pos': ['view-pagedown/view']}),
    act('view-pageup', {'F5': 'PageDown', 'F6': 'PageUp'}, LONG, (1, 1), ['F5', 'F5', 'F6'],
        [view('PageUp scrolls the view back by a page.')]),
    act('half-page-down', 'HalfPageDown', LONG, (1, 1), ['F5'], [view('HalfPageDown scrolls half a page.')]),
    act('half-page-up', {'F5': 'HalfPageDown', 'F6': 'HalfPageUp'}, LONG, (1, 1), ['F5', 'F5', 'F6'],
        [view('HalfPageUp scrolls back half a page.')]),
    act('scroll-down', 'ScrollDown', LONG, (1, 1), ['F5'], [view('ScrollDown scrolls the view by scrollspeed lines.')]),
    act('scroll-up', {'F5': 'ScrollDown', 'F6': 'ScrollUp'}, LONG, (1, 1), ['F5', 'F5', 'F5', 'F6'],
        [view('ScrollUp scrolls back by scrollspeed lines.')]),
    act('jump-line', 'JumpLine', LONG, (1, 1), ['F5'], [m('JumpLine opens the goto prompt.')]),
]

SELECT = [
    act('select-subword-right', 'SelectSubWordRight', WORDS, (1, 1), ['F5', '#'],
        [f('SelectSubWordRight selects the first camel-case part.')], save=True),
    act('select-subword-left', 'SelectSubWordLeft', WORDS, (1, 14), ['F5', '#'],
        [f('SelectSubWordLeft selects the last camel-case part.')], save=True),
    act('select-line', 'SelectLine', TEXT, (2, 4), ['F5', '#'],
        [f('SelectLine selects the whole line with its line break.')], save=True),
    act('select-line-last', 'SelectLine', 'one\ntwo', (2, 2), ['F5', '#'],
        [f('On the last line without a line break only the text is selected.')], save=True),
    act('select-to-sol', 'SelectToStartOfLine', WORDS, (3, 12), ['F5', '#'],
        [f('SelectToStartOfLine selects back to column 1.')], save=True),
    act('select-to-sot', 'SelectToStartOfText', WORDS, (3, 12), ['F5', '#'],
        [f('SelectToStartOfText selects back to the first non-blank character.')], save=True),
    act('select-to-sot-toggle', 'SelectToStartOfTextToggle', WORDS, (3, 12), ['F5', 'F5', '#'],
        [f('A second press extends the selection to the start of the line.')], save=True),
    act('select-para-next', 'SelectToParagraphNext', PARA, (1, 3), ['F5', '#'],
        [f('SelectToParagraphNext selects to the empty line after the paragraph.')], save=True),
    act('select-para-prev', 'SelectToParagraphPrevious', PARA, (5, 3), ['F5', '#'],
        [f('SelectToParagraphPrevious selects back to the empty line before the paragraph.')], save=True),
    act('deselect', 'Deselect', TEXT, (1, 1), ['Shift+Right', 'Shift+Right', 'F5', '#'],
        [f('Deselect drops the selection, so the typed character is inserted.')], save=True),
]

EDIT = [
    act('delete-word-right', 'DeleteWordRight', TEXT, (1, 1), ['F5'],
        [f('DeleteWordRight deletes the word to the right.')], save=True),
    act('delete-word-right-space', 'DeleteWordRight', TEXT, (1, 6), ['F5'],
        [f('From before a space it deletes the space and the next word.')], save=True),
    act('delete-subword-right', 'DeleteSubWordRight', WORDS, (1, 1), ['F5'],
        [f('DeleteSubWordRight deletes one camel-case part.')], save=True),
    act('delete-subword-left', 'DeleteSubWordLeft', WORDS, (1, 30), ['F5'],
        [f('DeleteSubWordLeft deletes the last snake_case part.')], save=True),
    act('delete-line', 'DeleteLine', TEXT, (2, 3), ['F5'], [f('DeleteLine deletes the current line.')], save=True),
    act('delete-line-sel', 'DeleteLine', TEXT, (1, 3), ['Shift+Down', 'F5'],
        [f('DeleteLine deletes every line touched by the selection.')], save=True),
    act('delete-line-msg', 'DeleteLine', TEXT, (1, 3), ['Shift+Down', 'Shift+Down', 'F5'],
        [m('The message counts the deleted lines.')]),
    act('copy-line', {'F5': 'CopyLine'}, TEXT, (2, 3), ['F5', 'Control+End', 'Control+V'],
        [f('CopyLine copies the current line.')], save=True),
    act('copy-line-sel', {'F5': 'CopyLine'}, TEXT, (1, 3), ['Shift+Down', 'F5', 'Control+End', 'Control+V'],
        [f('CopyLine with a selection copies every touched line.')], save=True),
    act('cut-sel', {'F5': 'Cut'}, TEXT, (2, 3), ['Shift+Right', 'Shift+Right', 'F5', 'Control+End', 'Control+V'],
        [f('Cut with a selection moves the selected text.')], save=True),
    act('cut-nosel', {'F5': 'Cut'}, TEXT, (2, 3), ['F5'],
        [f('Cut without a selection does nothing.')], save=True, req={'file': ['cut-sel/file']}),
    act('duplicate-line-sel', {'F5': 'DuplicateLine'}, TEXT, (1, 3), ['Shift+Down', 'F5'],
        [f('DuplicateLine duplicates all lines touched by the selection.')], save=True),
    act('duplicate-sel', {'F5': 'Duplicate'}, TEXT, (2, 3), ['Shift+Right', 'Shift+Right', 'F5'],
        [f('Duplicate with a selection inserts a copy of it after it.')], save=True),
    act('duplicate-nosel', {'F5': 'Duplicate'}, TEXT, (2, 3), ['F5'],
        [f('Duplicate without a selection does nothing.')], save=True, req={'file': ['duplicate-sel/file']}),
    act('duplicate-line-msg', {'F5': 'DuplicateLine'}, TEXT, (1, 3), ['Shift+Down', 'Shift+Down', 'F5'],
        [m('The message counts the duplicated lines.')]),
    act('indent-line', 'IndentLine', TEXT, (2, 4), ['F5'], [f('IndentLine indents the line from anywhere in it.'),
                                                           p('The cursor moves with the text.')], save=True),
    act('indent-line-sel', 'IndentLine', TEXT, (2, 4), ['Shift+Right', 'F5'],
        [f('IndentLine does nothing while there is a selection.')], save=True, req={'file': ['indent-line/file']}),
    act('outdent-line', 'OutdentLine', '\t\tdeep\n', (1, 4), ['F5'], [f('OutdentLine removes one indentation level.')],
        save=True),
    act('indent-selection-none', 'IndentSelection', TEXT, (2, 4), ['F5'],
        [f('IndentSelection does nothing without a selection.')], save=True, req={'file': ['indent-line/file']}),
    act('insert-newline', 'InsertNewline', TEXT, (1, 6), ['F5'], [f('InsertNewline splits the line.')], save=True),
    act('insert-tab', 'InsertTab', TEXT, (1, 6), ['Shift+Right', 'F5'],
        [f('InsertTab inserts a tab even with a selection (and keeps the text).')], save=True),
    act('none-binding', {'Ctrl-k': 'None', 'F5': 'DeleteLine'}, TEXT, (1, 1), ['Control+K', 'Down', 'F5'],
        [f('Ctrl-k bound to None does nothing while F5 deletes line 2.')], save=True),
    act('skip-back', 'SkipMultiCursorBack', 'foo a foo b foo c foo d\n', (1, 1), ['Alt+n', 'Alt+n', 'Alt+n', 'F5',
                                                                                typ('X')],
        [f('SkipMultiCursorBack moves the newest cursor back to the previous match, where it merges with the cursor '
           'already there.')], save=True),
]

STATE = [
    act('toggle-hl', 'ToggleHighlightSearch', TEXT, (1, 1), ['Control+F', typ('line'), 'Enter', 'F5'],
        [('cells', 'The other matches of the last search are highlighted too.', differ(((2, 8), (2, 2)), ((3, 9), (3, 2))))]),
    act('toggle-hl-twice', 'ToggleHighlightSearch', TEXT, (1, 1),
        ['Control+F', typ('line'), 'Enter', 'F5', 'F5'],
        [('cells', 'A second toggle removes the highlighting.', differ(((2, 8), (2, 2)), ((3, 9), (3, 2))))],
        req={'cells': ['toggle-hl/cells']}),
    act('hlsearch-ref', None, TEXT, (1, 1), ['Control+F', typ('line'), 'Enter'],
        [('cells', 'With hlsearch on, a search highlights every match.', differ(((2, 8), (2, 2)), ((3, 9), (3, 2))))],
        settings={'hlsearch': True}),
    act('unhighlight', {'F5': 'UnhighlightSearch'}, TEXT, (1, 1), ['Control+F', typ('line'), 'Enter', 'F5'],
        [('cells', 'UnhighlightSearch removes the hlsearch highlighting.', differ(((2, 8), (2, 2)), ((3, 9), (3, 2))))],
        settings={'hlsearch': True}, req={'cells': ['hlsearch-ref/cells']}),
    act('find-next-ref', None, TEXT, (1, 1), ['Control+F', typ('line'), 'Enter', 'Control+N'],
        [p('Without ResetSearch, FindNext goes to the next match.')]),
    act('reset-search', 'ResetSearch', TEXT, (1, 1), ['Control+F', typ('line'), 'Enter', 'F5', 'Control+N'],
        [p('After ResetSearch, FindNext has nothing to search for.')], req={'pos': ['find-next-ref/pos']}),
    act('clear-ref', None, TEXT, (1, 1), ['Control+S'], [m('Saving shows a message.')]),
    act('clear-info', 'ClearInfo', TEXT, (1, 1), ['Control+S', 'F5'],
        [m('ClearInfo empties the message line.')], req={'msg': ['clear-ref/msg']}),
    act('clear-status', 'ClearStatus', TEXT, (1, 1), ['Control+S', 'F5'],
        [m('ClearStatus empties the message line.')], req={'msg': ['clear-ref/msg']}),
    act('toggle-ruler', None, TEXT, (1, 1), ['Control+R'],
        [('render', 'Control+R hides the line numbers.', rows(0, 1)), m('The message says the ruler is disabled.')]),
    act('toggle-ruler-twice', None, TEXT, (1, 1), ['Control+R', 'Control+R'],
        [m('The message says the ruler is enabled again.')]),
    act('toggle-diffgutter', 'ToggleDiffGutter', TEXT, (1, 1), ['F5'],
        [m('ToggleDiffGutter reports that the diff gutter is enabled.'),
         ('render', 'The gutter gets wider.', rows(0, 1))]),
    act('toggle-keymenu', None, TEXT, (1, 1), ['Alt+g'],
        [('render', 'Alt+g shows the key menu at the bottom.', rows(32, 36))]),
    act('toggle-keymenu-twice', None, TEXT, (1, 1), ['Alt+g', 'Alt+g'],
        [('render', 'A second Alt+g hides the key menu.', rows(32, 36))], req={'render': ['toggle-keymenu/render']}),
]

PANES = [
    act('save-all', 'SaveAll', TEXT, (1, 1), ['x', 'Alt+.', 'y', 'F5'],
        [f('SaveAll saves the first tab.'), ('other', 'SaveAll saves the other tab too.', file('act-sa2.txt'))],
        args=['act-sa2.txt'], files={'act-sa2.txt': 'second file\n'}),
    act('save-as', 'SaveAs', TEXT, (1, 1), ['x', 'F5'], [m('SaveAs asks for a file name.')]),
    act('save-as-use', 'SaveAs', TEXT, (1, 1), ['x', 'F5', typ('act-new.txt'), 'Enter'],
        [('new', 'The buffer is written under the new name.', file('act-new.txt')),
         ('status', 'The buffer takes the new name.', status('name', 'modified'))]),
    act('force-quit', 'ForceQuit', TEXT, (1, 1), ['x', 'F5'],
        [('proc', 'ForceQuit exits without asking, even with changes.', 'process'),
         f('The change is not saved.')],
        req={'proc': ['quit-all-modified/msg'], 'file': ['force-quit/proc', 'quit-all-modified/msg']}),
    act('quit-all', 'QuitAll', TEXT, (1, 1), ['F5'],
        [('proc', 'QuitAll exits with all tabs unmodified.', 'process')], args=['act-qa2.txt'],
        files={'act-qa2.txt': 'other\n'}, req={'proc': ['quit-all-modified/msg']}),
    act('quit-all-modified', 'QuitAll', TEXT, (1, 1), ['x', 'F5'],
        [m('With changes QuitAll asks before discarding them.'), ('proc', 'micro is still running.', 'process')],
        args=['act-qa3.txt'], files={'act-qa3.txt': 'other\n'}, req={'proc': ['quit-all-modified/msg']}),
    act('quit-all-yes', 'QuitAll', TEXT, (1, 1), ['x', 'F5', 'y'],
        [('proc', 'Answering y exits without saving.', 'process'),
         ('file', 'The change in the first tab is discarded.', file('act-qa4.txt'))],
        args=['act-qa4.txt'], files={'act-qa4.txt': 'other\n'},
        req={'proc': ['quit-all-modified/msg'], 'file': ['quit-all-yes/proc', 'quit-all-modified/msg']}),
    act('first-tab', {'F5': 'FirstTab'}, TEXT, (1, 1), ['Alt+.', 'Alt+.', snap('pre'), 'F5'],
        [('tabs', 'FirstTab activates the first tab.', 'tabs'),
         ('reached', 'Before F5 the third tab is active.', tabs('active', snapshot='pre'))],
        args=['act-ft2.txt', 'act-ft3.txt'], files={'act-ft2.txt': '2\n', 'act-ft3.txt': '3\n'},
        goal='With F5 bound to FirstTab and three files open, press Alt+. twice, then F5.',
        req={'tabs': ['first-tab/reached']}),
    act('last-tab', {'F5': 'FirstTab', 'F6': 'LastTab'}, TEXT, (1, 1), ['F5', 'F6'],
        [('tabs', 'LastTab activates the last tab.', 'tabs')],
        args=['act-lt2.txt', 'act-lt3.txt'], files={'act-lt2.txt': '2\n', 'act-lt3.txt': '3\n'}),
    act('vsplit-action', 'VSplit', TEXT, (1, 1), ['F5'],
        [('panes', 'VSplit opens an empty buffer in a vertical split.', panes('name')),
         ('columns', 'The split is to the right.', columns(0))]),
    act('hsplit-action', 'HSplit', TEXT, (1, 1), ['F5'],
        [('panes', 'HSplit opens an empty buffer in a horizontal split.', panes('name'))]),
    act('previous-split', {'F5': 'VSplit', 'F6': 'PreviousSplit'}, TEXT, (1, 1), ['F5', 'F6', 'Z'],
        [('panes', 'PreviousSplit returns to the first pane, where Z is typed.', panes('name', 'modified'))]),
    act('first-split', {'F5': 'VSplit', 'F6': 'FirstSplit'}, TEXT, (1, 1), ['F5', 'F5', 'F6', 'Z'],
        [('columns', 'FirstSplit activates the first of three panes, where Z is typed.', columns(0))]),
    act('last-split', {'F5': 'VSplit', 'F6': 'LastSplit'}, TEXT, (1, 1), ['F5', 'F5', 'Control+W', 'F6', 'Z'],
        [('columns', 'LastSplit activates the last of three panes, where Z is typed.', columns(0))]),
    act('unsplit', {'F5': 'VSplit', 'F6': 'Unsplit'}, TEXT, (1, 1), ['F5', 'F6'],
        [('panes', 'Unsplit closes the other split.', panes('name'))], req={'panes': ['vsplit-action/panes']}),
]

SYNTAX = [
    act('chain-comma', {'F5': 'CursorStart,DeleteLine'}, TEXT, (3, 2), ['F5'],
        [f('Actions separated by commas all run.')], save=True),
    act('sequence', {'<F5><F6>': 'DeleteLine'}, TEXT, (2, 1), ['F5', 'F6'],
        [f('A key sequence binding runs after both keys.')], save=True),
    act('sequence-partial', {'<F5><F6>': 'DeleteLine', 'F7': 'None'}, TEXT, (2, 1), ['F5', 'x'],
        [f('An incomplete sequence followed by another key does not run the action.')], save=True,
        req={'file': ['sequence/file']}),
    act('buffer-group', {'buffer': {'F5': 'DeleteLine'}}, TEXT, (2, 1), ['F5'],
        [f('A binding in the buffer group works in the editing pane.')], save=True),
    act('command-group', {'command': {'F5': 'AbortCommand'}}, TEXT, (1, 1),
        ['Control+E', typ('set ruler off'), 'F5', 'Enter'],
        [('render', 'F5 aborted the command bar, so the ruler stays.', rows(0, 1)),
         ('status', 'The Enter after the abort went to the buffer.', pos())]),
    act('alt-upper', {'Alt-G': 'DeleteLine'}, TEXT, (2, 1), ['Alt+G'],
        [f('Alt-G (upper case) is bound to Alt+Shift+g.')], save=True),
    act('alt-upper-lower', {'Alt-G': 'DeleteLine'}, TEXT, (2, 1), ['Alt+g'],
        [f('Alt+g (lower case) keeps its own binding and deletes nothing.')], save=True,
        req={'file': ['alt-upper/file']}),
    act('ctrl-case', {'Ctrl-G': 'DeleteLine'}, TEXT, (2, 1), ['Control+G'],
        [f('Ctrl-G and Ctrl-g are the same key.')], save=True),
    act('no-dash', {'CtrlShiftDown': 'DeleteLine'}, TEXT, (2, 1), ['Control+Shift+Down'],
        [f('Modifiers may be written without dashes.')], save=True),
    act('lua-binding', {'F5': 'lua:comment.comment'}, 'x = 1\n', (1, 1), ['F5'],
        [f('A lua: binding runs a function of a built-in plugin.')], save=True),
    act('command-binding', {'F5': 'command:goto 3'}, TEXT, (1, 1), ['F5'], [p('A command: binding runs the command.')]),
    row('bad-json', 'Start micro with a bindings.json that is not valid JSON.', TEXT, [],
        [('screen', 'micro reports the broken bindings.json at start (its words before the parser\'s detail).',
          rows(0, 3, cut=': '))], bindings='{"F5": '),
    row('bad-json-continue', 'Start micro with a broken bindings.json and press Enter.', TEXT, [key('Enter')],
        [('status', 'After the message the file opens normally.', status('name', 'line', 'col'))],
        bindings='{"F5": '),
    row('unknown-action-file', 'Start micro with a bindings.json that names an unknown action.', TEXT, [],
        [('screen', 'micro reports the unknown action at start.', rows(0, 3))], bindings={'F5': 'NoSuchAction'}),
]


def episodes():
    out = family('act-move', 'actions', MOTION, 12)
    out += family('act-select', 'actions', SELECT, 10)
    out += family('act-edit', 'actions', EDIT, 11)
    out += family('act-state', 'actions', STATE, 13)
    out += family('act-panes', 'actions', PANES, 8)
    out += family('act-syntax', 'keybindings', SYNTAX, 12)
    return out
