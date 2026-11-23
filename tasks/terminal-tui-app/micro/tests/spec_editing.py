"""Undo and redo (micro groups the edits made within the same second into one undo step), multiple cursors, keyboard
macros and word completion.
"""
from spec_common import (at, click, cmd, differ, family, file, key, keys, message, pos, row, rows, snap, status, sync,
                         typ, wait)

TEXT = 'alpha beta gamma\nsecond line\nthird line\nfourth line\n'
WORDS = 'foo bar foo foobar foo\nfoo end\n'
LIST = 'one\ntwo\nthree\nfour\nfive\n'


def f(requirement):
    return ('file', requirement, 'file')


def p(requirement):
    return ('pos', requirement, 'pos')


def m(requirement, snapshot=None):
    return ('msg', requirement, message(snapshot) if snapshot else 'msg')


def later():
    """A pause longer than micro's one-second undo grouping, so the next edit is a separate undo step."""
    return wait(1.3)


UNDO = [
    row('group', 'Type "abc" quickly, then press Control+Z.', TEXT, [sync(), typ('abc'), snap('typed'), key('Control+Z')],
        [('typed', 'The typed text appears first.', rows(0, 1, snapshot='typed')),
         f('Edits made within the same second are undone together.')], save=True, req={'file': ['group/typed']}),
    row('separate', 'Type "a", wait over a second, type "b", then press Control+Z.', TEXT,
        [typ('a'), later(), typ('b'), key('Control+Z')], [f('Only the later edit is undone.')], save=True),
    row('twice', 'Type "a", wait, type "b", then press Control+Z twice.', TEXT,
        [typ('a'), later(), typ('b'), key('Control+Z'), key('Control+Z')], [f('Both edits are undone.')], save=True,
        req={'file': ['separate/file']}),
    row('redo-one', 'Type "a", wait, type "b", undo twice, then redo once.', TEXT,
        [typ('a'), later(), typ('b'), key('Control+Z'), key('Control+Z'), key('Control+Y')],
        [f('Redo reapplies the first undone step.')], save=True),
    row('redo-cleared', 'Type "a", undo, type "b", then press Control+Y.', TEXT,
        [typ('a'), key('Control+Z'), typ('b'), key('Control+Y')],
        [f('A new edit clears the redo history.')], save=True),
    row('undo-empty', 'Press Control+Z in an unchanged buffer.', TEXT, [key('Control+Z')],
        [m('Nothing is undone and no message appears.')], req={'msg': ['msg-undo/msg']}),
    row('msg-undo', 'Type x, then press Control+Z.', TEXT, [typ('x'), key('Control+Z')],
        [m('The message reports the undo.')]),
    row('redo-empty', 'Press Control+Y with nothing to redo.', TEXT, [typ('x'), key('Control+Y')],
        [m('Nothing is redone.')], req={'msg': ['msg-undo/msg']}),
    row('cursor', 'Type on line 3, move to line 1, then undo.', TEXT,
        [at(3, 4), typ('ZZ'), key('Control+Home'), key('Control+Z')], [p('Undo moves the cursor back to the change.')]),
    row('modified', 'Type x, save, then undo.', TEXT, [typ('x'), key('Control+S'), key('Control+Z')],
        [('status', 'After undoing past the save the buffer is modified again.', status('modified'))]),
    row('unmodified', 'Type x, then undo.', TEXT, [typ('x'), key('Control+Z')],
        [('status', 'Undoing back to the saved text makes the buffer unmodified.', status('modified'))],
        req={'status': ['modified/status']}),
    row('paste', 'Copy line 1, paste it at the end, then undo.', TEXT,
        [key('Control+C'), key('Control+End'), later(), key('Control+V'), snap('pasted'), key('Control+Z')],
        [('pasted', 'The pasted line appears first.', rows(4, 5, snapshot='pasted')),
         f('The paste is undone as one step.')], save=True, req={'file': ['paste/pasted']}),
    row('multi-steps', 'Delete line 2, wait, delete another line, wait, type x, then undo three times and redo twice.',
        TEXT, [at(2, 1), key('Control+K'), later(), key('Control+K'), later(), typ('x'),
               key('Control+Z'), key('Control+Z'), key('Control+Z'), key('Control+Y'), key('Control+Y')],
        [f('Undo and redo walk the history step by step.')], save=True),
]

MULTI = [
    row('alt-n-word', 'Put the cursor in foo, press Alt+n twice and type X.', WORDS, [at(1, 2), keys('Alt+n', 'Alt+n'),
                                                                                       typ('X')],
        [f('Alt+n selects the word, then adds a cursor at its next whole-word occurrence.')], save=True),
    row('alt-n-skip-partial', 'Put the cursor in foo, press Alt+n three times and type X.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Alt+n'), typ('X')],
        [f('Whole-word matching skips foobar.')], save=True),
    row('alt-n-selection', 'Select "fo", press Alt+n twice and type X.', WORDS,
        [keys('Shift+Right', 'Shift+Right', 'Alt+n', 'Alt+n'), typ('X')],
        [f('With a selection Alt+n finds the selected text anywhere, also inside words.')], save=True),
    row('alt-n-wrap', 'Put the cursor in the last foo, press Alt+n twice and type X.', WORDS,
        [at(2, 2), keys('Alt+n', 'Alt+n'), typ('X')], [f('The search for the next occurrence wraps around.')],
        save=True),
    row('alt-x', 'Put the cursor in foo, press Alt+n, Alt+n, Alt+x and type X.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Alt+x'), typ('X')],
        [f('Alt+x moves the newest cursor on to the following occurrence.')], save=True),
    row('alt-p', 'Put the cursor in foo, press Alt+n three times, then Alt+p, and type X.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Alt+n', 'Alt+p'), typ('X')],
        [f('Alt+p removes the newest cursor.')], save=True),
    row('alt-c', 'Put the cursor in foo, press Alt+n twice, then Alt+c, and type X.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Alt+c'), typ('X')],
        [f('Alt+c removes all extra cursors.')], save=True),
    row('esc', 'Put the cursor in foo, press Alt+n twice, then Escape, and type X.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Escape'), typ('X')],
        [f('Escape also removes the extra cursors and the selection.')], save=True),
    row('down', 'Press Alt+Shift+Down twice and type >.', LIST, [keys('Alt+Shift+Down', 'Alt+Shift+Down'), typ('>')],
        [f('Alt+Shift+Down adds cursors below.')], save=True),
    row('up', 'From line 4 press Alt+Shift+Up and type >.', LIST, [at(4, 1), key('Alt+Shift+Up'), typ('>')],
        [f('Alt+Shift+Up adds a cursor above.')], save=True),
    row('down-column', 'From column 5 of line 3 press Alt+Shift+Down twice and type |.', LIST,
        [at(3, 5), keys('Alt+Shift+Down', 'Alt+Shift+Down'), typ('|')],
        [f('A cursor on a shorter line stops at its end.')], save=True),
    row('down-last', 'On the last line press Alt+Shift+Down and type >.', 'one\ntwo', [at(2, 1), key('Alt+Shift+Down'),
                                                                                 typ('>')],
        [f('No cursor is added below the last line.')], save=True),
    row('alt-m', 'Select lines 2-4 and press Alt+m, then type "# ".', LIST,
        [at(2, 3), keys('Shift+Down', 'Shift+Down', 'Alt+m'), typ('# ')],
        [f('Alt+m puts a cursor at the start of every selected line.'), m('The message reports the new cursors.')],
        save=True),
    row('alt-m-none', 'Press Alt+m without a selection and type x.', LIST, [at(2, 2), key('Alt+m'), typ('x')],
        [f('Without a selection Alt+m does nothing.')], save=True, req={'file': ['alt-m/file']}),
    row('backspace', 'Add a cursor below and press Backspace.', LIST, [at(1, 3), key('Alt+Shift+Down'),
                                                                      key('Backspace')],
        [f('Backspace acts at every cursor.')], save=True),
    row('enter', 'Add a cursor below and press Enter.', LIST, [at(1, 2), key('Alt+Shift+Down'), key('Enter')],
        [f('Enter splits the line at every cursor.')], save=True),
    row('end', 'Add a cursor below, press End and type !.', LIST, [key('Alt+Shift+Down'), key('End'), typ('!')],
        [f('Movement keys move every cursor.')], save=True),
    row('copy-paste', 'Select foo at two cursors, copy, move to the line ends and paste.', WORDS,
        [at(1, 2), keys('Alt+n', 'Alt+n', 'Control+C', 'End', 'Control+V')],
        [f('Each cursor pastes its own copied text.')], save=True),
    row('undo', 'Add cursors on three lines, type x, then undo.', LIST,
        [keys('Alt+Shift+Down', 'Alt+Shift+Down'), typ('x'), key('Control+Z')],
        [f('One undo removes the text typed at all cursors.')], save=True, req={'file': ['down/file']}),
    row('ctrl-click', 'Control+click on line 3 and type >.', LIST,
        [{'mouse': {'action': 'click', 'row': 2, 'column': 3, 'modifiers': ['Control']}}, typ('>')],
        [f('Control+click adds a cursor at the clicked position.')], save=True),
    row('ctrl-click-remove', 'Control+click twice on line 3 and type >.', LIST,
        [{'mouse': {'action': 'click', 'row': 2, 'column': 3, 'modifiers': ['Control']}},
         {'mouse': {'action': 'click', 'row': 2, 'column': 3, 'modifiers': ['Control']}}, typ('>')],
        [f('Control+clicking an existing cursor removes it.')], save=True, req={'file': ['ctrl-click/file']}),
    row('status-last', 'Add a cursor two lines below.', LIST, [at(1, 2), keys('Alt+Shift+Down', 'Alt+Shift+Down')],
        [p('The status line shows the position of the newest cursor.')]),
]

MACRO = [
    row('record-msg', 'Press Control+U.', TEXT, [key('Control+U')], [m('micro reports that it is recording.')]),
    row('stop-msg', 'Press Control+U twice.', TEXT, [key('Control+U'), key('Control+U')],
        [m('micro reports that recording stopped.')]),
    row('play', 'Record typing "> " and Down, then play it twice.', TEXT,
        [key('Control+U'), typ('> '), key('Home'), key('Down'), key('Control+U'), key('Control+J'), key('Control+J')],
        [f('Playing the macro repeats the typing and the movement.')], save=True),
    row('play-action', 'Record Control+D (duplicate line) and play it.', TEXT,
        [key('Control+U'), key('Control+D'), key('Control+U'), key('Control+J')],
        [f('Macros replay actions too.')], save=True),
    row('play-while-recording', 'Start recording, press Control+J, type x, stop, then play.', TEXT,
        [key('Control+U'), key('Control+J'), typ('x'), key('Control+U'), key('Control+J')],
        [f('Playing during recording does nothing; the recorded macro inserts x.')], save=True),
    row('replace-macro', 'Record typing a, then record typing b, then play.', TEXT,
        [key('Control+U'), typ('a'), key('Control+U'), key('Control+U'), typ('b'), key('Control+U'),
         key('Control+J')], [f('A new recording replaces the previous macro.')], save=True),
]

COMPLETE = [
    row('tab-complete', 'Type "al" on an empty line and press Tab.', 'alphabet alpine\n\n',
        [at(2, 1), typ('al'), key('Tab')], [f('Tab completes a word from the buffer.')], save=True),
    row('suggestions', 'Type "al" on an empty line and press Tab.', 'alphabet alpine\n\n',
        [at(2, 1), typ('al'), key('Tab')], [('rows', 'The suggestions are listed on the status line.', rows(34, 35))]),
    row('cycle', 'Type "al" and press Tab twice.', 'alphabet alpine\n\n', [at(2, 1), typ('al'), key('Tab'), key('Tab')],
        [f('A second Tab cycles to the next suggestion.')], save=True),
    row('cycle-back', 'Type "al" and press Tab twice, then Shift+Tab.', 'alphabet alpine\n\n',
        [at(2, 1), typ('al'), key('Tab'), key('Tab'), key('Shift+Tab')],
        [f('Shift+Tab cycles back.')], save=True),
    row('single', 'Type "zeb" and press Tab when only zebra matches.', 'zebra alpha\n\n',
        [at(2, 1), typ('zeb'), key('Tab')], [f('A single candidate is completed.')], save=True),
    row('no-candidate', 'Type "qq" and press Tab.', 'alpha\n\n', [at(2, 1), typ('qq'), key('Tab')],
        [f('Without candidates Tab inserts a tab.')], save=True),
    row('inside-word', 'Put the cursor inside "alpha" and press Tab.', 'alpha alpine\n', [at(1, 3), key('Tab')],
        [f('Inside a word Tab inserts a tab instead of completing.')], save=True),
    row('accept-continue', 'Type "al", press Tab, then type x.', 'alphabet alpine\n\n',
        [at(2, 1), typ('al'), key('Tab'), typ('x')], [f('Typing after a completion keeps the completed word.')],
        save=True),
]


def episodes():
    return (family('undo', 'undo', UNDO, 13) + family('multi', 'multicursor', MULTI, 12)
            + family('macro', 'macros', MACRO, 6) + family('complete', 'autocomplete', COMPLETE, 8))
