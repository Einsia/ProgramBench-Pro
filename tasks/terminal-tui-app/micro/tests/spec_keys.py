"""Default key bindings of the editing pane (micro 2.0.15 on Linux).

Each checkpoint starts micro on its own file, moves to a position with the plain arrow keys, presses the key under
test (sometimes after a selection or a short preparation) and checks what that key did: the cursor position from the
status line, the saved file, or the message line. Cases are chosen so that each key's distinctive rule (word
boundaries, line wrap, toggles, indentation, line joins, clipboard accumulation, ...) is visible in the result.
"""
from spec_common import at, case, file, keys, message, pos, program, snap

WORDS = 'alpha beta.gamma(delta)) epsilon_zeta  eta\nsecond line\n    indented text here\n\nafter blank\nlast line\n'
CODE = 'def f(x):\n    if x:\n        return 1\n    return 2\n'
PARA = 'p1 one\np1 two\n\np2 one\np2 two\np2 three\n\n\np3 one\n'
LONG = ''.join(f'line {i:02d}\n' for i in range(1, 81))


def mv(cid, goal, text, start, names, requirement, extra=(), req=None):
    """A movement case: only the final cursor position is asserted (the file is not changed). req binds a result a
    motionless cursor would also show to a positive movement point."""
    return cid, goal, text, start, names, [('pos', requirement, pos())] + list(extra), False, req


def ed(cid, goal, text, start, names, requirement, *, where=True, msg=None, req=None):
    """An editing case: the saved file is asserted, the resulting cursor position when it is distinctive, and the
    message the key shows (captured before the save replaces it). req binds the file point of a case whose file
    does not change to a positive point that proves the key works."""
    checks = [('file', requirement, None)]
    if where:
        checks.append(('pos', 'The cursor ends where the key leaves it.', pos()))
    if msg:
        checks.append(('msg', msg, message('mid')))
    return cid, goal, text, start, names, checks, True, req


def sel(cid, goal, text, start, names, requirement, marker='#'):
    """A selection case: the selection is replaced by typing a marker, so the saved file shows its extent."""
    return cid, goal, text, start, list(names) + [marker], [('file', requirement, None)], True, None


MOVES = [
    mv('right-wrap', 'Press Right at the end of line 1.', 'ab\ncd\n', (1, 3), ['Right'],
       'Right at the end of a line moves to the start of the next line.'),
    mv('left-wrap', 'Press Left at the start of line 2.', 'ab\ncd\n', (2, 1), ['Left'],
       'Left at the start of a line moves to the end of the previous line.'),
    mv('left-origin', 'Press Left at the very start of the buffer.', 'ab\ncd\n', (1, 1), ['Left', 'Left'],
       'Left at the start of the buffer stays there.', req={'pos': ['left-wrap/pos']}),
    mv('up-first', 'Press Up on the first line.', 'abcdef\nxy\n', (1, 4), ['Up'],
       'Up on the first line moves to the start of that line.', req={'pos': ['down-clamp/pos']}),
    mv('down-last', 'Press Down on the last line.', 'ab\ncdefg', (2, 3), ['Down'],
       'Down on the last line moves to its end.'),
    mv('down-clamp', 'Press Down from column 6 onto a shorter line.', 'abcdefgh\nxy\nabcdefgh\n', (1, 7),
       ['Down'], 'Moving down onto a shorter line stops at its end.'),
    mv('down-remember', 'Press Down twice from column 6 across a shorter line.', 'abcdefgh\nxy\nabcdefgh\n',
       (1, 7), ['Down', 'Down'], 'The original column is restored on the next long enough line.'),
    mv('down-tab-visual', 'Press Down from a column below a tab-indented line.', 'abcdefgh\n\txyzw\n', (1, 6),
       ['Down'], 'Vertical movement keeps the visual column across a tab.'),
    mv('cright-word', 'Press Control+Right inside the first word.', WORDS, (1, 2), ['Control+Right'],
       'Control+Right moves to the end of the current word.'),
    mv('cright-space', 'Press Control+Right twice from the start of line 1.', WORDS, (1, 1),
       ['Control+Right', 'Control+Right'], 'Control+Right skips the space and stops at the end of the next word.'),
    mv('cright-dot', 'Press Control+Right from just before ".gamma".', WORDS, (1, 11), ['Control+Right'],
       'A single punctuation character before a word is skipped together with that word.'),
    mv('cright-run', 'Press Control+Right on the "))" run.', WORDS, (1, 24), ['Control+Right'],
       'A run of punctuation is skipped as one word.'),
    mv('cright-eol', 'Press Control+Right at the end of line 1.', WORDS, (1, 43), ['Control+Right'],
       'Control+Right at the end of a line moves to the start of the next line.'),
    mv('cright-underscore', 'Press Control+Right from the start of "epsilon_zeta".', WORDS, (1, 26),
       ['Control+Right'], 'An underscore is part of a word.'),
    mv('cleft-word', 'Press Control+Left at the end of "beta".', WORDS, (1, 11), ['Control+Left'],
       'Control+Left moves to the start of the word.'),
    mv('cleft-space', 'Press Control+Left from the double space before "eta".', WORDS, (1, 39),
       ['Control+Left'], 'Control+Left skips whitespace back to the start of the previous word.'),
    mv('cleft-run', 'Press Control+Left right after the "))" run.', WORDS, (1, 26), ['Control+Left'],
       'Control+Left skips a run of punctuation as one word.'),
    mv('cleft-bol', 'Press Control+Left at the start of line 2.', WORDS, (2, 1), ['Control+Left'],
       'Control+Left at the start of a line moves to the end of the previous line.'),
    mv('alt-f', 'Press Alt+f (emacs word right) twice from the start.', WORDS, (1, 1), ['Alt+f', 'Alt+f'],
       'Alt+f moves one word right like Control+Right.'),
    mv('alt-b', 'Press Alt+b (emacs word left) at the end of line 2.', WORDS, (2, 12), ['Alt+b'],
       'Alt+b moves one word left like Control+Left.'),
    mv('home-text', 'Press Home inside an indented line.', WORDS, (3, 12), ['Home'],
       'Home moves to the first non-blank character of the line.'),
    mv('home-toggle', 'Press Home twice inside an indented line.', WORDS, (3, 12), ['Home', 'Home'],
       'A second Home toggles to the very start of the line.'),
    mv('home-toggle3', 'Press Home three times inside an indented line.', WORDS, (3, 12), ['Home', 'Home', 'Home'],
       'A third Home toggles back to the first non-blank character.'),
    mv('alt-left', 'Press Alt+Left twice inside an indented line.', WORDS, (3, 9), ['Alt+Left', 'Alt+Left'],
       'Alt+Left toggles between the start of the text and the start of the line.'),
    mv('alt-a', 'Press Alt+a twice inside an indented line.', WORDS, (3, 12), ['Alt+a', 'Alt+a'],
       'Alt+a moves to the start of the text and does not toggle.'),
    mv('end', 'Press End in the middle of line 3.', WORDS, (3, 7), ['End'], 'End moves to the end of the line.'),
    mv('alt-right', 'Press Alt+Right in the middle of line 2.', WORDS, (2, 3), ['Alt+Right'],
       'Alt+Right moves to the end of the line.'),
    mv('alt-e', 'Press Alt+e in the middle of line 2.', WORDS, (2, 3), ['Alt+e'], 'Alt+e moves to the end of the line.'),
    mv('ctrl-up', 'Press Control+Up from line 5.', WORDS, (5, 4), ['Control+Up'],
       'Control+Up moves to the start of the buffer.', req={'pos': ['ctrl-down/pos']}),
    mv('ctrl-down', 'Press Control+Down from line 1.', WORDS, (1, 4), ['Control+Down'],
       'Control+Down moves to the end of the buffer.'),
    mv('ctrl-home', 'Press Control+Home from line 5.', WORDS, (5, 4), ['Control+Home'],
       'Control+Home moves to the start of the buffer.', req={'pos': ['ctrl-end/pos']}),
    mv('ctrl-end', 'Press Control+End from line 1.', WORDS, (1, 4), ['Control+End'],
       'Control+End moves to the end of the buffer.'),
    mv('alt-lbracket', 'Press Alt+[ from line 5 (no diff gutter).', WORDS, (5, 4), ['Alt+['],
       'Without diff markers Alt+[ falls back to the start of the buffer.', req={'pos': ['alt-rbracket/pos']}),
    mv('alt-rbracket', 'Press Alt+] from line 1 (no diff gutter).', WORDS, (1, 4), ['Alt+]'],
       'Without diff markers Alt+] falls back to the end of the buffer.'),
    mv('para-next', 'Press Alt+} from the first paragraph.', PARA, (1, 3), ['Alt+}'],
       'Alt+} moves to the empty line after the paragraph.'),
    mv('para-next2', 'Press Alt+} twice from the first paragraph.', PARA, (1, 3), ['Alt+}', 'Alt+}'],
       'A second Alt+} moves to the empty line after the next paragraph.'),
    mv('para-next-end', 'Press Alt+} in the last paragraph.', PARA, (9, 2), ['Alt+}'],
       'Without a following empty line Alt+} moves to the end of the buffer.'),
    mv('para-prev', 'Press Alt+{ in the third paragraph.', PARA, (9, 3), ['Alt+{'],
       'Alt+{ moves to the empty line before the paragraph (skipping consecutive empty lines).'),
    mv('para-prev-start', 'Press Alt+{ in the first paragraph.', PARA, (2, 3), ['Alt+{'],
       'Without an earlier empty line Alt+{ moves to the start of the buffer.', req={'pos': ['para-prev/pos']}),
    mv('pagedown', 'Press PageDown at the start of an 80-line file.', LONG, (1, 1), ['PageDown'],
       'PageDown moves the cursor one page (the view height less the page overlap) down.'),
    mv('pagedown2', 'Press PageDown twice.', LONG, (1, 3), ['PageDown', 'PageDown'],
       'Each PageDown moves another page down, keeping the column.'),
    mv('pageup', 'Press PageUp from line 70.', LONG, (70, 1), ['PageUp'], 'PageUp moves the cursor one page up.'),
    mv('pageup-top', 'Press PageUp from line 5.', LONG, (5, 2), ['PageUp'],
       'PageUp near the top of the buffer stops on the first line.'),
    mv('pagedown-bottom', 'Press PageDown from line 75.', LONG, (75, 2), ['PageDown'],
       'PageDown near the end of the buffer stops on the last line.'),
]

EDITS = [
    ed('enter-split', 'Press Enter in the middle of a word.', 'abcdef\n', (1, 4), ['Enter'],
       'Enter splits the line at the cursor.'),
    ed('enter-indent', 'Press Enter at the end of an indented line.', CODE, (2, 10), ['Enter'],
       'Enter on an indented line indents the new line the same way.'),
    ed('enter-indent-mid', 'Press Enter inside the indentation of a line.', CODE, (3, 3), ['Enter'],
       'Enter inside the indentation keeps only the indentation before the cursor.'),
    ed('enter-blank', 'Press Enter twice at the end of an indented line, then type x.', CODE, (2, 10),
       ['Enter', 'Enter', 'x'], 'An indented line left empty loses its indentation when Enter is pressed again.'),
    ed('enter-sel', 'Select "bcd" with Shift+Right and press Enter.', 'abcdef\n', (1, 2),
       ['Shift+Right', 'Shift+Right', 'Shift+Right', 'Enter'], 'Enter replaces the selection with a line break.'),
    ed('bs', 'Press Backspace in the middle of a line.', 'abcdef\n', (1, 4), ['Backspace'],
       'Backspace deletes the character before the cursor.'),
    ed('bs-join', 'Press Backspace at the start of line 2.', 'abc\ndef\n', (2, 1), ['Backspace'],
       'Backspace at the start of a line joins it to the previous line.'),
    ed('bs-origin', 'Press Backspace at the start of the buffer.', 'abc\n', (1, 1), ['Backspace'],
       'Backspace at the start of the buffer changes nothing.', where=False, req={'file': ['bs/file']}),
    ed('bs-sel', 'Select two characters with Shift+Left and press Backspace.', 'abcdef\n', (1, 5),
       ['Shift+Left', 'Shift+Left', 'Backspace'], 'Backspace deletes the selection.'),
    ed('ctrl-h', 'Press Control+H in the middle of a line.', 'abcdef\n', (1, 4), ['Control+H'],
       'Control+H is Backspace.'),
    ed('del', 'Press Delete in the middle of a line.', 'abcdef\n', (1, 3), ['Delete'],
       'Delete removes the character under the cursor.'),
    ed('del-join', 'Press Delete at the end of line 1.', 'abc\ndef\n', (1, 4), ['Delete'],
       'Delete at the end of a line joins the next line to it.'),
    ed('del-sel', 'Select three characters and press Delete.', 'abcdef\n', (1, 2),
       ['Shift+Right', 'Shift+Right', 'Shift+Right', 'Delete'], 'Delete removes the selection.'),
    ed('alt-bs', 'Press Alt+Backspace after "gamma".', WORDS, (1, 17), ['Alt+Backspace'],
       'Alt+Backspace deletes the word before the cursor.'),
    ed('alt-bs-space', 'Press Alt+Backspace after the double space before "eta".', WORDS, (1, 40),
       ['Alt+Backspace'], 'Alt+Backspace deletes the whitespace and the word before it.'),
    ed('alt-ctrl-h', 'Press Alt+Control+H after "beta".', WORDS, (1, 11), ['Alt+Control+H'],
       'Alt+Control+H deletes the word before the cursor.'),
    ed('tab-insert', 'Press Tab in the middle of a line.', 'abcdef\n', (1, 3), ['Tab'],
       'Tab inserts a tab character (tabstospaces is off).'),
    ed('tab-indent-sel', 'Select lines 2-3 with Shift+Down and press Tab.', 'a\nb\nc\nd\n', (2, 1),
       ['Shift+Down', 'Shift+Down', 'Tab'], 'Tab with a selection indents every selected line.'),
    ed('tab-partial-sel', 'Select from the middle of line 1 into line 2 and press Tab.', 'abc\ndef\nghi\n', (1, 2),
       ['Shift+Down', 'Tab'], 'Tab indents each line touched by the selection, including partial ones.'),
    ed('backtab-line', 'Press Shift+Tab on a tab-indented line.', '\t\tdeep\n', (1, 4), ['Shift+Tab'],
       'Shift+Tab removes one level of indentation from the line.'),
    ed('backtab-none', 'Press Shift+Tab on a line without indentation.', 'flat\n', (1, 3), ['Shift+Tab'],
       'Shift+Tab on an unindented line changes nothing.', where=False, req={'file': ['backtab-line/file']}),
    ed('backtab-spaces', 'Press Shift+Tab on a line indented by six spaces.', '      six\n', (1, 8), ['Shift+Tab'],
       'Shift+Tab removes up to one tab size of spaces.'),
    ed('backtab-sel', 'Select two indented lines and press Shift+Tab.', '\tone\n\ttwo\n\tthree\n', (1, 1),
       ['Shift+Down', 'Shift+Down', 'Shift+Tab'], 'Shift+Tab with a selection outdents every selected line.'),
    ed('ctrl-k', 'Press Control+K on line 2.', 'one\ntwo\nthree\n', (2, 2), ['Control+K'],
       'Control+K cuts the current line.', msg='The message line reports the cut line.'),
    ed('ctrl-k-acc', 'Press Control+K three times on line 1, then Control+End and Control+V.',
       'one\ntwo\nthree\nfour\n', (1, 1), ['Control+K', 'Control+K', 'Control+K', 'Control+End', 'Control+V'],
       'Consecutive Control+K cuts accumulate in the clipboard; pasting inserts all cut lines.'),
    ed('ctrl-k-reset', 'Cut line 1, paste it back, cut line 1 again, then paste at the end.',
       'one\ntwo\nthree\n', (1, 1), ['Control+K', 'Control+V', 'Up', 'Control+K', 'Control+End', 'Control+V'],
       'A paste ends the accumulation: the next cut replaces the clipboard.', where=False),
    ed('ctrl-k-msg', 'Press Control+K twice.', 'one\ntwo\nthree\n', (1, 1), ['Control+K', 'Control+K'],
       'Two lines are removed.', where=False, msg='The message line counts the accumulated cut lines.'),
    ed('ctrl-d', 'Press Control+D on line 1.', 'one\ntwo\n', (1, 2), ['Control+D'],
       'Control+D without a selection duplicates the line below itself.', msg='The message line reports it.'),
    ed('ctrl-d-sel', 'Select "ne" and press Control+D.', 'one\ntwo\n', (1, 2), ['Shift+Right', 'Shift+Right',
                                                                                    'Control+D'],
       'Control+D with a selection duplicates the selected text after it.', msg='The message line reports it.'),
    ed('ctrl-x-line', 'Press Control+X without a selection, then Control+End and Control+V.',
       'one\ntwo\nthree\n', (2, 1), ['Control+X', 'Control+End', 'Control+V'],
       'Control+X without a selection cuts the whole line.'),
    ed('ctrl-x-sel', 'Select "wo" and press Control+X, then move to the end and paste.', 'one\ntwo\nthree\n',
       (2, 2), ['Shift+Right', 'Shift+Right', 'Control+X', 'Control+End', 'Control+V'],
       'Control+X with a selection cuts just the selection.'),
    ed('ctrl-c-line', 'Press Control+C without a selection, then Control+End and Control+V.',
       'one\ntwo\nthree\n', (2, 2), ['Control+C', 'Control+End', 'Control+V'],
       'Control+C without a selection copies the whole line.'),
    ed('ctrl-c-sel', 'Select "hre" and copy, then paste at the end.', 'one\ntwo\nthree\n', (3, 2),
       ['Shift+Right', 'Shift+Right', 'Shift+Right', 'Control+C', 'Control+End', 'Control+V'],
       'Control+C with a selection copies just the selection.'),
    ed('ctrl-v-sel', 'Copy "one", then select "two" and paste over it.', 'one\ntwo\n', (1, 1),
       ['Shift+End', 'Control+C', 'Down', 'Home', 'Shift+End', 'Control+V'],
       'Pasting replaces the selection.'),
    ed('ctrl-a-del', 'Press Control+A then Delete.', 'one\ntwo\n', (2, 2), ['Control+A', 'Delete'],
       'Control+A selects the whole buffer.', where=False),
    ed('ctrl-a-type', 'Press Control+A then type z.', 'one\ntwo\n', (1, 2), ['Control+A', 'z'],
       'Typing after Control+A replaces the whole buffer.', where=False),
    ed('alt-up', 'Press Alt+Up on line 3.', 'one\ntwo\nthree\n', (3, 2), ['Alt+Up'],
       'Alt+Up moves the current line up.'),
    ed('alt-down', 'Press Alt+Down on line 1.', 'one\ntwo\nthree\n', (1, 2), ['Alt+Down'],
       'Alt+Down moves the current line down.'),
    ed('alt-up-first', 'Press Alt+Up on line 1.', 'one\ntwo\n', (1, 2), ['Alt+Up'],
       'The first line cannot move up.', where=False, msg='The message line says it cannot move further up.',
       req={'file': ['alt-up-first/msg']}),
    ed('alt-down-last', 'Press Alt+Down on the last line.', 'one\ntwo', (2, 2), ['Alt+Down'],
       'The last line cannot move down.', where=False, msg='The message line says it cannot move further down.',
       req={'file': ['alt-down-last/msg']}),
    ed('alt-down-sel', 'Select lines 1-2 and press Alt+Down.', 'one\ntwo\nthree\nfour\n', (1, 1),
       ['Shift+Down', 'Shift+Down', 'Alt+Down'], 'Alt+Down moves all selected lines down together.'),
    ed('alt-up-sel-partial', 'Select from line 2 into line 3 and press Alt+Up.', 'one\ntwo\nthree\nfour\n', (2, 2),
       ['Shift+Down', 'Alt+Up'], 'Alt+Up moves every line touched by the selection.'),
    ed('insert-ovwr', 'Press Insert and type XY over "bc".', 'abcdef\n', (1, 2), ['Insert', 'X', 'Y'],
       'In overwrite mode typed characters replace the characters under the cursor.'),
    ed('insert-toggle', 'Press Insert twice and type XY.', 'abcdef\n', (1, 2), ['Insert', 'Insert', 'X', 'Y'],
       'A second Insert returns to insert mode.'),
    ed('insert-eol', 'In overwrite mode type past the end of the line.', 'ab\ncd\n', (1, 2), ['Insert', 'X', 'Y',
                                                                                              'Z'],
       'At the end of a line overwrite mode appends instead of overwriting the line break.'),
    ed('undo', 'Delete line 2 with Control+K, then press Control+Z.', 'one\ntwo\nthree\n', (2, 1),
       ['Control+K', 'Control+Z'], 'Control+Z undoes the cut.', msg='The message line reports the undo.',
       req={'file': ['undo/msg']}),
    ed('redo', 'Cut line 2, undo, then press Control+Y.', 'one\ntwo\nthree\n', (2, 1),
       ['Control+K', 'Control+Z', 'Control+Y'], 'Control+Y redoes the cut.',
       msg='The message line reports the redo.'),
]

SELECTS = [
    sel('shift-right', 'Press Shift+Right twice, then type #.', 'abcdef\n', (1, 2), ['Shift+Right', 'Shift+Right'],
        'Shift+Right extends the selection one character at a time.'),
    sel('shift-left', 'Press Shift+Left three times from column 5, then type #.', 'abcdef\n', (1, 5),
        ['Shift+Left'] * 3, 'Shift+Left selects backwards.'),
    sel('shift-down', 'Press Shift+Down from column 3, then type #.', 'abcdef\nghijkl\n', (1, 3), ['Shift+Down'],
        'Shift+Down selects to the same column on the next line.'),
    sel('shift-up', 'Press Shift+Up from line 2 column 3, then type #.', 'abcdef\nghijkl\n', (2, 3), ['Shift+Up'],
        'Shift+Up selects to the same column on the previous line.'),
    sel('shift-reverse', 'Press Shift+Right three times then Shift+Left once, then type #.', 'abcdef\n', (1, 2),
        ['Shift+Right', 'Shift+Right', 'Shift+Right', 'Shift+Left'],
        'Shifted movement in the other direction shrinks the selection from its moving end.'),
    sel('cshift-right', 'Press Control+Shift+Right twice from the start, then type #.', WORDS, (1, 1),
        ['Control+Shift+Right', 'Control+Shift+Right'], 'Control+Shift+Right selects word by word.'),
    sel('cshift-left', 'Press Control+Shift+Left from the end of "gamma", then type #.', WORDS, (1, 17),
        ['Control+Shift+Left'], 'Control+Shift+Left selects the word to the left.'),
    sel('shift-home', 'Press Shift+Home inside an indented line, then type #.', WORDS, (3, 12), ['Shift+Home'],
        'Shift+Home selects to the start of the text.'),
    sel('shift-home2', 'Press Shift+Home twice inside an indented line, then type #.', WORDS, (3, 12),
        ['Shift+Home', 'Shift+Home'], 'A second Shift+Home extends the selection to the start of the line.'),
    sel('alt-shift-left', 'Press Alt+Shift+Left inside an indented line, then type #.', WORDS, (3, 12),
        ['Alt+Shift+Left'], 'Alt+Shift+Left selects to the start of the text.'),
    sel('shift-end', 'Press Shift+End in the middle of line 2, then type #.', WORDS, (2, 4), ['Shift+End'],
        'Shift+End selects to the end of the line.'),
    sel('alt-shift-right', 'Press Alt+Shift+Right in the middle of line 2, then type #.', WORDS, (2, 4),
        ['Alt+Shift+Right'], 'Alt+Shift+Right selects to the end of the line.'),
    sel('cshift-up', 'Press Control+Shift+Up from line 3, then type #.', WORDS, (3, 7), ['Control+Shift+Up'],
        'Control+Shift+Up selects to the start of the buffer.'),
    sel('cshift-down', 'Press Control+Shift+Down from line 5, then type #.', WORDS, (5, 3), ['Control+Shift+Down'],
        'Control+Shift+Down selects to the end of the buffer.'),
    sel('shift-pagedown', 'Press Shift+PageDown from line 2, then type #.', LONG, (2, 3), ['Shift+PageDown'],
        'Shift+PageDown selects one page down.'),
    sel('shift-pageup', 'Press Shift+PageUp from line 60, then type #.', LONG, (60, 3), ['Shift+PageUp'],
        'Shift+PageUp selects one page up.'),
    sel('ctrl-a', 'Press Control+A, then type #.', 'one\ntwo\n', (2, 2), ['Control+A'],
        'Control+A selects the whole buffer.'),
    sel('esc-deselect', 'Select two characters, press Escape, then type #.', 'abcdef\n', (1, 2),
        ['Shift+Right', 'Shift+Right', 'Escape'], 'Escape removes the selection, so typing inserts instead.'),
    sel('right-deselect', 'Select two characters, press Right, then type #.', 'abcdef\n', (1, 2),
        ['Shift+Right', 'Shift+Right', 'Right'], 'Right with a selection collapses it to its end.'),
    sel('left-deselect', 'Select two characters, press Left, then type #.', 'abcdef\n', (1, 2),
        ['Shift+Right', 'Shift+Right', 'Left'], 'Left with a selection collapses it to its start.'),
    sel('up-deselect', 'Select two characters on line 2, press Up, then type #.', 'abcdef\nghijkl\n', (2, 2),
        ['Shift+Right', 'Shift+Right', 'Up'], 'Up with a selection moves up from the start of the selection.'),
    sel('down-deselect-nl', 'Select line 1 including its line break, press Down, then type #.', 'abc\ndef\nghi\n',
        (1, 1), ['Shift+Down', 'Down'], 'Down after a selection ending at a line start goes to that line start.'),
]


def _build(cid, goal, text, start, names, checks, save, req):
    path = f'k-{cid}.txt'
    steps = at(*start) + [keys(*names)]
    if any(check and check.get('snapshot') for _, _, check in checks):
        steps.append(snap('mid'))
    out = [(suffix, requirement, check or file(path)) for suffix, requirement, check in checks]
    return path, text, case(cid, goal, path, steps, out, save=save, requires=req)


def chunks(rows, size):
    """Split cases into episodes of about `size` checkpoints; cases that name each other's points (in either order)
    stay in one episode."""
    parent = {r[0]: r[0] for r in rows}

    def root(cid):
        while parent[cid] != cid:
            cid = parent[cid]
        return cid
    for r in rows:
        for names in (r[-1] or {}).values():
            for c in names:
                if c.count('/') == 1:
                    parent[root(c.split('/')[0])] = root(r[0])
    groups, current, placed = [], [], set()
    for r in rows:
        key = root(r[0])
        if key in placed:
            continue
        placed.add(key)
        cluster = [x for x in rows if root(x[0]) == key]
        if current and len(current) + len(cluster) > size:
            groups.append(current)
            current = []
        current.extend(cluster)
    if current:
        groups.append(current)
    return groups


def _episode(wid, rows):
    files, cps = {}, []
    for row in rows:
        path, text, cp = _build(*row)
        files[path] = text
        cps.append(cp)
    return program(wid, 'keys', files, cps)


def episodes():
    out = []
    for prefix, rows, size in (('keys-move', MOVES, 15), ('keys-edit', EDITS, 13), ('keys-select', SELECTS, 11)):
        for n, group in enumerate(chunks(rows, size)):
            out.append(_episode(f'{prefix}-{n + 1}', group))
    return out
