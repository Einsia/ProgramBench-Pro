'''Program episodes: text diff (monaco diff editor) and the HTML WYSIWYG editor.'''
from pbuild import NL, bind, blocks, case, clip, last_button, lines, monaco, multi, point, press, reload, select_editor, toolbar, typed, wait, episode

DEFAULT = 'Open the page without typing.'
BT = chr(96)
UNI = 'caf' + chr(233) + ' ' + chr(26085) + chr(26412) + ' ' + chr(10003)


# -- Text diff ------------------------------------------------------------------------------------------
DIFF_PAGE = '/text-diff'
DIFF_SEEN = multi(text=lines(skip=2))


def text_diff():
    def one(cid, goal, steps, requirement):
        return case(cid, goal, DIFF_PAGE, list(steps) + [wait(1.0)], [point('editors', requirement, DIFF_SEEN)])

    shown = 'Each editor shows the text typed into it, one numbered line per line of text.'
    rows = [
        ('changed-word', 'Type two lines on the left and the same lines with one changed on the right.', 'first line' + NL + 'second line', 'first line' + NL + 'changed line'),
        ('identical', 'Type the same text on both sides.', 'same text', 'same text'),
        ('left-only-text', 'Type a text on the left and clear the right.', 'only on the left', ''),
        ('right-only-text', 'Clear the left and type a text on the right.', '', 'only on the right'),
        ('both-empty', 'Clear both sides.', '', ''),
        ('added-line', 'Type two lines on the left and the same two plus a third on the right.', 'a' + NL + 'b', 'a' + NL + 'b' + NL + 'c'),
        ('removed-line', 'Type three lines on the left and the first and last on the right.', 'a' + NL + 'b' + NL + 'c', 'a' + NL + 'c'),
        ('swapped-lines', 'Type two lines on the left and the same two in the other order on the right.', 'one' + NL + 'two', 'two' + NL + 'one'),
        ('case-change', 'Type a text on the left and the same words in lower case on the right.', 'Hello World', 'hello world'),
        ('inner-spaces', 'Type a text with one space on the left and two spaces on the right.', 'a b', 'a  b'),
        ('trailing-space', 'Type a line on the left and the same line with a trailing space on the right.', 'line', 'line '),
        ('numbers', 'Type three numbers on the left and the same with the last changed on the right.', '1 2 3', '1 2 4'),
        ('markup', 'Type text with angle brackets and an ampersand on both sides, slightly different.', '<b>&amp;</b>', '<b>&</b>'),
        ('unicode', 'Type non-Latin text on the left and plain text on the right.', UNI, 'plain'),
        ('unicode-both', 'Type the same non-Latin text on both sides.', UNI, UNI),
        ('six-lines', 'Type six lines on each side with two of them changed on the right.', NL.join('line %d' % n for n in range(1, 7)), NL.join(['line 1', 'LINE 2', 'line 3', 'line 4', 'line five', 'line 6'])),
        ('long-line', 'Type a line of 120 letters on the left and the same with the last letter changed on the right.', 'w' * 120, 'w' * 119 + 'x'),
    ]
    cases = [one('default', DEFAULT, [], 'The page opens with a sample text in each editor.')]
    for cid, goal, left, right in rows:
        cases.append(one(cid, goal, [monaco(0, left), monaco(1, right)], shown))
    cases += [
        one('left-only-edit', 'Replace the text of the left editor only.', [monaco(0, 'edited on the left')], shown),
        one('right-only-edit', 'Replace the text of the right editor only.', [monaco(1, 'edited on the right')], shown),
        one('reloaded', 'Type a text on each side and reload the page.', [monaco(0, 'left text'), monaco(1, 'right text'), reload()], 'Reloading the page gives the sample texts back.'),
    ]
    return episode('text-diff', 'diff', bind(cases, {'reloaded': 'changed-word/editors'}))


# -- HTML WYSIWYG editor --------------------------------------------------------------------------------
WYS_PAGE = '/html-wysiwyg-editor'
WYS_SEEN = multi(html=blocks())
WYS_EMPTY = multi(html=blocks(allow_empty=True))
WYS_COPY = multi(copied=clip(), html=blocks())
BOLD, ITALIC, STRIKE, CODE, H1, H2, H3, H4, BULLETS, ORDERED, CODEBLOCK, QUOTE, BREAK, CLEAR, UNDO, REDO = range(16)
ALL = select_editor()
FOLLOWS = 'The HTML shown below the editor follows the edit.'


def html_editor():
    def one(cid, goal, steps, requirement=FOLLOWS, seen=WYS_SEEN):
        return case(cid, goal, WYS_PAGE, list(steps), [point('html', requirement, seen)])

    cases = [one('default', DEFAULT, [], 'The page opens with a sample heading and paragraph and their formatted HTML.')]
    for cid, name, button in (
        ('bold', 'Bold', BOLD), ('italic', 'Italic', ITALIC), ('strike', 'Strike', STRIKE), ('inline-code', 'Inline code', CODE),
        ('heading-1', 'Heading 1', H1), ('heading-2', 'Heading 2', H2), ('heading-4', 'Heading 4', H4),
        ('bullet-list', 'Bullet list', BULLETS), ('ordered-list', 'Ordered list', ORDERED), ('code-block', 'Code block', CODEBLOCK),
        ('blockquote', 'Blockquote', QUOTE), ('hard-break', 'Hard break', BREAK), ('clear-format', 'Clear format', CLEAR),
    ):
        cases.append(one(cid, 'Select all the text and press the %s button.' % name, [ALL, toolbar(button)], 'The selected text takes the %s format.' % name))
    combos = [
        ('bold-italic', 'Select all and press Bold and Italic.', [ALL, toolbar(BOLD), toolbar(ITALIC)]),
        ('bold-twice', 'Select all and press Bold twice.', [ALL, toolbar(BOLD), toolbar(BOLD)]),
        ('heading-switch', 'Select all and press Heading 1 and then Heading 2.', [ALL, toolbar(H1), toolbar(H2)]),
        ('heading-off', 'Select all and press Heading 2 twice.', [ALL, toolbar(H2), toolbar(H2)]),
        ('list-off', 'Select all and press Bullet list twice.', [ALL, toolbar(BULLETS), toolbar(BULLETS)]),
        ('list-switch', 'Select all and press Bullet list and then Ordered list.', [ALL, toolbar(BULLETS), toolbar(ORDERED)]),
        ('quote-list', 'Select all and press Blockquote and then Bullet list.', [ALL, toolbar(QUOTE), toolbar(BULLETS)]),
        ('clear-bold', 'Select all and press Bold and then Clear format.', [ALL, toolbar(BOLD), toolbar(CLEAR)]),
        ('clear-list', 'Select all and press Bullet list and then Clear format.', [ALL, toolbar(BULLETS), toolbar(CLEAR)]),
        ('clear-quote', 'Select all and press Blockquote and then Clear format.', [ALL, toolbar(QUOTE), toolbar(CLEAR)]),
        ('undo', 'Select all, press Bold and then Undo.', [ALL, toolbar(BOLD), toolbar(UNDO)]),
        ('redo', 'Select all, press Bold, Undo and Redo.', [ALL, toolbar(BOLD), toolbar(UNDO), toolbar(REDO)]),
        ('undo-twice', 'Select all, press Bold, Italic and then Undo twice.', [ALL, toolbar(BOLD), toolbar(ITALIC), toolbar(UNDO), toolbar(UNDO)]),
        ('undo-nothing', 'Press Undo with nothing to undo.', [toolbar(UNDO)]),
        ('redo-nothing', 'Press Redo with nothing to redo.', [toolbar(REDO)]),
        ('key-bold', 'Select all and press Control and B.', [ALL, press('Control+b')]),
        ('key-italic', 'Select all and press Control and I.', [ALL, press('Control+i')]),
        ('key-undo', 'Select all, press Control and B and then Control and Z.', [ALL, press('Control+b'), press('Control+z')]),
        ('key-redo', 'Select all, press Control and B, Control and Z and then Control and Y.', [ALL, press('Control+b'), press('Control+z'), press('Control+y')]),
        ('append', 'Select all, go to the end and type more words.', [ALL, press('End'), typed(' more')]),
        ('stored-format', 'Select all, press Bold and reload the page.', [ALL, toolbar(BOLD), reload()]),
    ]
    for cid, goal, steps in combos:
        cases.append(one(cid, goal, steps))
    erase = [ALL, press('Delete')]
    typing = [
        ('type-plain', 'Clear the editor and type some words.', [typed('Plain words')]),
        ('type-two-lines', 'Clear the editor and type two lines.', [typed('one'), press('Enter'), typed('two')]),
        ('type-heading', 'Clear the editor and type a hash, a space and a title, then a line.', [typed('# Title'), press('Enter'), typed('body')]),
        ('type-heading-2', 'Clear the editor and type two hashes, a space and a title, then a line.', [typed('## Sub'), press('Enter'), typed('body')]),
        ('type-bullets', 'Clear the editor and type a dash, a space and an item, then another item.', [typed('- one'), press('Enter'), typed('two')]),
        ('type-bullets-end', 'Type a dash item, press Enter twice and type a line.', [typed('- one'), press('Enter'), press('Enter'), typed('after')]),
        ('type-ordered', 'Clear the editor and type a numbered item, then another item.', [typed('1. one'), press('Enter'), typed('two')]),
        ('type-quote', 'Clear the editor and type a quoted line, then another line.', [typed('> quoted'), press('Enter'), typed('still')]),
        ('type-bold-marks', 'Clear the editor and type a word between double asterisks, then more.', [typed('**strong** after')]),
        ('type-italic-marks', 'Clear the editor and type a word between single asterisks, then more.', [typed('*soft* after')]),
        ('type-code-marks', 'Clear the editor and type a word between backticks, then more.', [typed(BT + 'code' + BT + ' after')]),
        ('type-strike-marks', 'Clear the editor and type a word between double tildes, then more.', [typed('~~gone~~ kept')]),
        ('type-codeblock-marks', 'Clear the editor and type three backticks, a space and a line.', [typed(BT * 3 + ' x = 1')]),
        ('type-rule', 'Clear the editor and type three dashes, press Enter and type a line.', [typed('---'), press('Enter'), typed('after')]),
        ('type-special', 'Clear the editor and type a line with angle brackets and an ampersand.', [typed('a < b & c > d')]),
        ('type-unicode', 'Clear the editor and type non-Latin text.', [typed(UNI)]),
        ('type-soft-break', 'Clear the editor and type a line, press Shift and Enter and type another.', [typed('one'), press('Shift+Enter'), typed('two')]),
        ('stored-typed', 'Clear the editor, type some words and reload the page.', [typed('Kept text'), reload()]),
    ]
    for cid, goal, steps in typing:
        cases.append(one(cid, goal, erase + steps))
    cases.append(one('delete-all', 'Select all the text and delete it.', erase, 'An emptied editor shows the HTML of an empty document.', WYS_EMPTY))
    cases.append(one('copy-default', 'Press the copy button below the HTML.', [last_button()], 'The HTML is copied to the clipboard.', WYS_COPY))
    cases.append(one('copy-bold', 'Select all, press Bold and press the copy button below the HTML.', [ALL, toolbar(BOLD), last_button()], 'The edited HTML is copied to the clipboard.', WYS_COPY))
    return episode('html-wysiwyg-editor', 'editor', bind(cases, {'bold-twice': 'bold/html', 'undo': 'bold/html', 'undo-twice': 'bold/html', 'undo-nothing': 'bold/html', 'redo-nothing': 'bold/html', 'key-undo': 'key-bold/html'}))


def build():
    return [text_diff(), html_editor()]
