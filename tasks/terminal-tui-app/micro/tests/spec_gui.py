"""User goals judged by the evaluator. Each goal names its inputs exactly, asks for one visible outcome and carries a
backend companion (the saved file, micro's configuration files, the status line, the panes or the tabs) that a
correct implementation also passes, so an interface that only looks right cannot pass. Recipes are the reference's
own deterministic key sequences; any equivalent route is accepted.
"""
from spec_common import (SAVE, at, cmd, columns, config, file, gui, gutter, key, keys, message, panes, paste, pos,
                         rows, status, step, tabs, typ, wait)

NOTES = 'alpha beta gamma\nthe teh quick fox\nthird line here\nfourth line\nfifth line\n'
CODE = 'def area(w, h):\n    tmp = w * h\n    return tmp\n\nprint(area(2, 3))\n'
LONG = ''.join(f'entry number {i}\n' for i in range(1, 101))
TABBED = 'name\tvalue\n\tindented with a tab\nend\n'


def g(wid, feature, files, goal, acceptance, recipe, checks, *, args=None, config_files=None, extra=(), prep=None,
      req=None, expect=None):
    """One GUI episode with one checkpoint; every frontend point requires all backend points of the checkpoint, and
    req binds a backend point that an untouched workspace would also pass to a positive one."""
    names = [c[0] for c in checks]
    requires = {('done' if isinstance(acceptance, str) else f'done-{i + 1}'): names
                for i in range(1 if isinstance(acceptance, str) else len(acceptance))}
    cp = step('goal', goal, recipe, checks, acceptance=acceptance, requires={**requires, **(req or {})})
    return gui(wid, feature, files, [cp] + list(extra), args=args, config_files=config_files, prep=prep,
               expect=expect)


def saved(path, what):
    return (f'file', what, file(path))


def edit(wid, goal, acceptance, recipe, text=NOTES, name='notes.txt', what='The file is saved with the change.'):
    return g(wid, 'editing', {name: text}, goal, acceptance, recipe + [SAVE], [saved(name, what)], args=[name])


EDITING = [
    edit('gui-insert-top', 'Insert a new first line containing exactly `TODO: review` above the current first line of '
         'notes.txt, then save the file.',
         'notes.txt now starts with the line "TODO: review" followed by the original lines, and it is saved (no '
         'unsaved-changes marker).', [typ('TODO: review'), key('Enter')]),
    edit('gui-delete-line', 'Delete the third line ("third line here") of notes.txt and save the file.',
         'The line "third line here" is gone, the other lines are unchanged, and the file is saved.',
         [at(3, 1), key('Control+K')]),
    edit('gui-fix-typo', 'On line 2 of notes.txt, change the word `teh` to `the` (leave everything else as it is) and '
         'save the file.', 'Line 2 reads "the the quick fox" and the file is saved.',
         [at(2, 5), keys('Delete', 'Delete', 'Delete'), typ('the')]),
    edit('gui-append', 'Append the text ` (done)` to the end of the first line of notes.txt and save the file.',
         'The first line reads "alpha beta gamma (done)" and the file is saved.', [key('End'), typ(' (done)')]),
    edit('gui-join', 'Join lines 4 and 5 of notes.txt into one line by removing the line break between them (no '
         'character added), then save.', 'One line now reads "fourth linefifth line" and the file is saved.',
         [at(4, 1), key('End'), key('Delete')]),
    edit('gui-duplicate', 'Duplicate the first line of notes.txt so that it appears twice in a row, then save.',
         'The first two lines both read "alpha beta gamma" and the file is saved.', [key('Control+D')]),
    edit('gui-move-up', 'Move line 4 ("fourth line") of notes.txt up so it comes before "third line here", then '
         'save.', '"fourth line" is now line 3 and "third line here" line 4; the file is saved.',
         [at(4, 1), key('Alt+Up')]),
    edit('gui-indent', 'Indent lines 2, 3 and 4 of notes.txt by one tab character each, then save.',
         'Lines 2-4 each start with one more indentation level and the file is saved.',
         [at(2, 1), keys('Shift+Down', 'Shift+Down', 'Shift+Down'), key('Tab')]),
    edit('gui-outdent', 'Remove the indentation of line 2 of tabbed.txt so it starts at the first column, then save.',
         'Line 2 reads "indented with a tab" without leading whitespace and the file is saved.',
         [at(2, 2), key('Shift+Tab')], text=TABBED, name='tabbed.txt'),
    edit('gui-cut-paste', 'Move the first line of notes.txt to the very end of the file (cut it and paste it after '
         'the last line), then save.', '"alpha beta gamma" is now the last line and the file is saved.',
         [key('Control+K'), key('Control+End'), key('Control+V')]),
    edit('gui-copy-word', 'Copy the word `alpha` from line 1 and paste it at the end of line 3 of notes.txt, then save.',
         'Line 3 reads "third line herealpha" and line 1 is unchanged; the file is saved.',
         [keys('Shift+Right', 'Shift+Right', 'Shift+Right', 'Shift+Right', 'Shift+Right'), key('Control+C'),
          key('Control+Home'), at(3, 1), key('End'), key('Control+V')]),
    edit('gui-delete-word', 'Delete the word `quick` and the space after it from line 2 of notes.txt, then save.',
         'Line 2 reads "the teh fox" and the file is saved.',
         [at(2, 9), keys(*['Delete'] * 6)]),
    edit('gui-new-line', 'Add a new line `inserted line` between line 2 and line 3 of notes.txt, then save.',
         '"inserted line" is now line 3, between "the teh quick fox" and "third line here"; the file is saved.',
         [at(2, 1), key('End'), key('Enter'), typ('inserted line')]),
    edit('gui-replace-all-text', 'Replace the whole content of notes.txt with the single line `empty`, then save.',
         'The file shows only the line "empty" and is saved.', [key('Control+A'), typ('empty')]),
    edit('gui-swap', 'Swap the first two lines of notes.txt, then save.',
         'Line 1 reads "the teh quick fox" and line 2 "alpha beta gamma"; the file is saved.',
         [key('Alt+Down')]),
    edit('gui-delete-range', 'Delete lines 2 to 4 of notes.txt (three lines), then save.',
         'Only "alpha beta gamma" and "fifth line" remain and the file is saved.',
         [at(2, 1), keys('Shift+Down', 'Shift+Down', 'Shift+Down'), key('Delete')]),
    edit('gui-paste-block', 'Insert these two lines at the end of notes.txt, then save:\n```\nsixth line\nseventh line\n'
         '```', 'The file ends with "sixth line" and "seventh line" after "fifth line" and is saved.',
         [key('Control+End'), paste('sixth line\nseventh line')]),
    edit('gui-undo-last', 'In notes.txt, type `X` at the start of line 1, then type `Y` at the start of line 2, then '
         'undo only the last of these two changes, and save.',
         'Line 1 starts with "X", line 2 does not start with "Y", and the file is saved.',
         [typ('X'), wait(1.3), key('Down'), key('Home'), typ('Y'), key('Control+Z')]),
    edit('gui-comment', 'Comment out line 2 of area.py (`    tmp = w * h`) with micro\'s comment feature, then save.',
         'Line 2 is commented out with Python\'s # syntax and the file is saved.', [at(2, 1), key('Alt+/')],
         text=CODE, name='area.py'),
    edit('gui-rename-var', 'Rename every occurrence of the variable `tmp` in area.py to `value`, then save.',
         'Both former occurrences of tmp read value and the file is saved.', [cmd('replaceall tmp value')],
         text=CODE, name='area.py'),
]

SEARCH = [
    g('gui-goto', 'navigation', {'long.txt': LONG}, 'Move the cursor to line 42 of long.txt.',
      'The cursor is on line 42 ("entry number 42") and that line is visible.', [cmd('goto 42')],
      [('line', 'The cursor is on line 42.', status('line'))], args=['long.txt']),
    g('gui-goto-col', 'navigation', {'long.txt': LONG}, 'Move the cursor to line 10, column 7 of long.txt.',
      'The status line shows the cursor at line 10, column 7.', [cmd('goto 10:7')],
      [('pos', 'The cursor is at 10,7.', pos())], args=['long.txt']),
    g('gui-end', 'navigation', {'long.txt': LONG}, 'Move the cursor to the very end of long.txt.',
      'The cursor is on the empty last line after "entry number 100", which is visible.', [key('Control+End')],
      [('pos', 'The cursor is at the end of the buffer.', pos())], args=['long.txt']),
    g('gui-find', 'search', {'notes.txt': NOTES}, 'Find the first occurrence of `line` in notes.txt.',
      'The first "line" (in "third line here") is selected or the cursor is on it.',
      [key('Control+F'), typ('line'), key('Enter')], [('line', 'The cursor is on line 3.', status('line'))],
      args=['notes.txt']),
    g('gui-find-next', 'search', {'notes.txt': NOTES}, 'Find the second occurrence of `line` in notes.txt.',
      'The "line" of "fourth line" is selected or the cursor is on it.',
      [key('Control+F'), typ('line'), key('Enter'), key('Control+N')],
      [('line', 'The cursor is on line 4.', status('line'))], args=['notes.txt']),
    g('gui-replaceall', 'search', {'pets.txt': 'cat and cat\nmy cat\nconcatenate\n'},
      'Replace every occurrence of the text `cat` with `dog` in pets.txt (including inside other words), then save.',
      'pets.txt reads "dog and dog", "my dog", "condogenate" and is saved.', [cmd('replaceall cat dog'), SAVE],
      [('file', 'Every cat became dog.', file('pets.txt'))], args=['pets.txt']),
    g('gui-replace-one', 'search', {'colors.txt': 'red apple\nred car\nred sky\n'},
      'Replace only the second `red` (on line 2) with `blue` in colors.txt, then save.',
      'Line 2 reads "blue car" while lines 1 and 3 still say red; the file is saved.',
      [cmd('replace red blue'), key('n'), key('y'), key('Escape'), SAVE],
      [('file', 'Only line 2 changed.', file('colors.txt'))], args=['colors.txt']),
    g('gui-replace-regex', 'search', {'dates.txt': 'on 2024-01-15 and 2025-12-31\n'},
      'Using a regular-expression replace, rewrite each date YYYY-MM-DD in dates.txt as DD/MM/YYYY, then save.',
      'The line reads "on 15/01/2024 and 31/12/2025" and the file is saved.',
      [cmd('replaceall "([0-9]{4})-([0-9]{2})-([0-9]{2})" "$3/$2/$1"'), SAVE],
      [('file', 'Both dates are rewritten.', file('dates.txt'))], args=['dates.txt']),
    g('gui-brace', 'navigation', {'code.js': 'function f(a) {\n  if (a) {\n    return 1;\n  }\n  return 2;\n}\n'},
      'Move the cursor onto the closing brace that matches the opening brace at the end of line 1 of code.js.',
      'The cursor is on the "}" of the last line (line 6).', [key('Control+End'), key('Up'), key('Home')],
      [('pos', 'The cursor is on the matching brace.', pos())], args=['code.js']),
]

MULTI = [
    edit('gui-prefix-lines', 'Put `- ` (dash and space) at the start of lines 2, 3, 4 and 5 of notes.txt, then save.',
         'Lines 2 to 5 each start with "- " and line 1 is unchanged; the file is saved.',
         [at(2, 1), keys('Shift+Down', 'Shift+Down', 'Shift+Down', 'Alt+m'), typ('- ')]),
    edit('gui-suffix-lines', 'Append `;` to the end of each of the first three lines of notes.txt, then save.',
         'Lines 1, 2 and 3 each end with ";" and the file is saved.',
         [keys('Alt+Shift+Down', 'Alt+Shift+Down', 'End'), typ(';')]),
    edit('gui-multi-word', 'Change every whole word `foo` in words.txt to `bar` (not foobar), then save.',
         'words.txt reads "bar x bar foobar" and "bar" on line 2, and is saved.',
         [key('Alt+n'), key('Alt+n'), key('Alt+n'), typ('bar')],
         text='foo x foo foobar\nfoo\n', name='words.txt'),
]

SETTINGS = [
    g('gui-tabsize', 'options', {'tabbed.txt': TABBED}, 'Make micro display tabs 2 columns wide, as a lasting setting.',
      'Tabs in tabbed.txt are drawn two columns wide.', [cmd('set tabsize 2')],
      [('settings', 'settings.json records tabsize 2.', config('settings.json'))], args=['tabbed.txt']),
    g('gui-ruler-off', 'options', {'notes.txt': NOTES}, 'Turn off the line numbers, as a lasting setting.',
      'No line numbers are shown beside the text.', [cmd('set ruler off')],
      [('settings', 'settings.json records ruler false.', config('settings.json'))], args=['notes.txt']),
    g('gui-softwrap', 'options', {'wide.txt': ' '.join(['word'] * 60) + '\n'},
      'Turn on soft wrapping so the long line of wide.txt wraps on screen, as a lasting setting.',
      'The long line continues on the next screen row instead of running off the screen.', [cmd('set softwrap on')],
      [('settings', 'settings.json records softwrap true.', config('settings.json'))], args=['wide.txt']),
    g('gui-tabstospaces', 'options', {'notes.txt': NOTES},
      'Make the Tab key insert spaces instead of a tab character (as a lasting setting), then press Tab at the start '
      'of line 1 and save notes.txt.', 'Line 1 is now indented and the file is saved.',
      [cmd('set tabstospaces on'), key('Tab'), SAVE],
      [('settings', 'settings.json records tabstospaces.', config('settings.json')),
       ('file', 'The saved line starts with four spaces.', file('notes.txt'))], args=['notes.txt']),
    g('gui-colorscheme', 'options', {'notes.txt': NOTES},
      'Switch the colour scheme to `solarized` as a lasting setting, then show the current colorscheme value on the '
      'message line.', 'The message line reports solarized.', [cmd('set colorscheme solarized'),
                                                               cmd('show colorscheme')],
      [('settings', 'settings.json records the colour scheme.', config('settings.json')),
       ('msg', 'The message line shows solarized.', message())], args=['notes.txt']),
    g('gui-relativeruler', 'options', {'notes.txt': NOTES},
      'Make the line numbers relative to the cursor line (lasting setting), with the cursor on line 3.',
      'The cursor line shows its own number and the other lines show their distance from it.',
      [cmd('set relativeruler on'), at(3, 1)],
      [('settings', 'settings.json records relativeruler.', config('settings.json')),
       ('gutter', 'The numbers are relative.', gutter())], args=['notes.txt']),
    g('gui-scrollbar', 'options', {'long.txt': LONG}, 'Show a scroll bar, as a lasting setting.',
      'A scroll bar is drawn at the right edge of the editing area.', [cmd('set scrollbar on')],
      [('settings', 'settings.json records scrollbar.', config('settings.json'))], args=['long.txt']),
    g('gui-showchars', 'options', {'tabbed.txt': TABBED},
      'Make tab characters visible as `>` (using the showchars option), as a lasting setting.',
      'Each tab in tabbed.txt is drawn starting with ">".', [cmd('set showchars tab=>')],
      [('settings', 'settings.json records showchars.', config('settings.json'))], args=['tabbed.txt']),
    g('gui-keymenu', 'options', {'notes.txt': NOTES}, 'Show micro\'s key menu (the list of common keys) at the bottom.',
      'A key menu listing keys such as ^Q Quit and ^S Save is shown above the message line.', [key('Alt+g')],
      [('rows', 'The key menu rows are drawn.', rows(32, 35))], args=['notes.txt']),
    g('gui-statusline-off', 'options', {'notes.txt': NOTES}, 'Hide the status line, as a lasting setting.',
      'No status line is drawn below the text.', [cmd('set statusline off')],
      [('settings', 'settings.json records statusline false.', config('settings.json'))], args=['notes.txt']),
    g('gui-crlf', 'files', {'notes.txt': NOTES}, 'Convert notes.txt to Windows (CRLF) line endings and save it.',
      'The status line reports the dos format and the file is saved.', [cmd('set fileformat dos'), SAVE],
      [('file', 'Every line ends with CRLF.', file('notes.txt')), ('ff', 'The status line says dos.',
                                                                   status('fileformat'))], args=['notes.txt']),
    g('gui-latin1', 'files', {'cafe.txt': 'café\n'}, 'Save cafe.txt in the ISO-8859-1 (Latin-1) encoding.',
      'The status line reports the iso-8859-1 encoding and the file is saved.',
      [cmd('set encoding iso-8859-1'), SAVE], [('file', 'The é is stored as one Latin-1 byte.', file('cafe.txt'))],
      args=['cafe.txt']),
    g('gui-hlsearch', 'search', {'notes.txt': NOTES},
      'Turn on highlighting of all search matches (lasting setting), then search for `line`.',
      'Every occurrence of "line" is highlighted.', [cmd('set hlsearch on'), key('Control+F'), typ('line'),
                                                     key('Enter')],
      [('settings', 'settings.json records hlsearch.', config('settings.json'))], args=['notes.txt']),
    g('gui-local-option', 'options', {'tabbed.txt': TABBED, 'other.txt': 'a\tb\n'},
      'Set the tab size to 8 for the current buffer only (not as a lasting setting).',
      'Tabs in tabbed.txt are drawn 8 columns wide.', [cmd('setlocal tabsize 8')],
      [('settings', 'settings.json does not record the local value.', config('settings.json')),
       ('rows', 'The local tab size is applied.', rows(0, 2))], args=['tabbed.txt'], req={'settings': ['rows']},
      config_files={'settings.json': '{}'}),
]

BINDINGS = [
    g('gui-bind-save', 'keybindings', {'notes.txt': NOTES},
      'Bind the F5 key to the Save action, then use F5 to save notes.txt after typing `x` at the start of line 1.',
      'Line 1 starts with "x" and the file is saved (no unsaved-changes marker).',
      [cmd('bind F5 Save'), typ('x'), key('F5')],
      [('bindings', 'bindings.json binds F5 to Save.', config('bindings.json')),
       ('file', 'The file is saved with the x.', file('notes.txt'))], args=['notes.txt']),
    g('gui-bind-delete', 'keybindings', {'notes.txt': NOTES},
      'Bind Alt-d to the DeleteLine action and use it to delete line 2 of notes.txt, then save.',
      'Line 2 ("the teh quick fox") is gone and the file is saved.',
      [cmd('bind Alt-d DeleteLine'), key('Down'), key('Alt+d'), SAVE],
      [('bindings', 'bindings.json binds Alt-d.', config('bindings.json')),
       ('file', 'Line 2 is deleted.', file('notes.txt'))], args=['notes.txt']),
    g('gui-unbind', 'keybindings', {'notes.txt': NOTES},
      'Remove the custom binding of Ctrl-r so that the key has its default action again, then show the action now '
      'bound to Ctrl-r on the message line.',
      'Showing the binding of Ctrl-r reports its default action ToggleRuler.', [cmd('unbind Ctrl-r'),
                                                                               cmd('showkey Ctrl-r')],
      [('bindings', 'bindings.json no longer binds Ctrl-r.', config('bindings.json'))], args=['notes.txt'],
      config_files={'bindings.json': '{"Ctrl-r": "Undo"}'}),
    g('gui-showkey', 'keybindings', {'notes.txt': NOTES}, 'Without running it, find out which action is bound to '
      'Ctrl-k and have micro show the name of that action on the message line.', 'The message line shows CutLine.',
      [cmd('showkey Ctrl-k')],
      [('msg', 'The message line shows the action.', message())], args=['notes.txt']),
]

PANES = [
    g('gui-vsplit', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Open other.txt in a vertical split beside notes.txt.',
      'notes.txt and other.txt are shown side by side.', [cmd('vsplit other.txt')],
      [('panes', 'Both files are open in two panes.', panes('name'))], args=['notes.txt']),
    g('gui-hsplit', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Open other.txt in a horizontal split below notes.txt.', 'notes.txt is shown above and other.txt below.',
      [cmd('hsplit other.txt')], [('panes', 'Both files are open, one above the other.', panes('name'))],
      args=['notes.txt']),
    g('gui-tab', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Open other.txt in a new tab.', 'A tab bar shows notes.txt and other.txt, with other.txt shown.',
      [cmd('tab other.txt')], [('tabs', 'Two tabs, the new one active.', tabs())], args=['notes.txt']),
    g('gui-close-split', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Close the split that shows other.txt, keeping notes.txt open.', 'Only notes.txt is shown, in a single pane.',
      [key('Control+Q')], [('panes', 'One pane with notes.txt.', panes('name'))],
      args=['notes.txt', 'other.txt'], config_files={'settings.json': '{"multiopen": "vsplit"}'},
      expect={'panes': ['notes.txt', 'other.txt']}),
    g('gui-switch-tab', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Two tabs are open (notes.txt and other.txt). Make the other.txt tab the active one.',
      'other.txt is shown and its tab is marked active.', [key('Alt+.')],
      [('tabs', 'The second tab is active.', tabs())], args=['notes.txt', 'other.txt']),
    g('gui-tabmove', 'splits-tabs', {'a.txt': 'a\n', 'b.txt': 'b\n', 'c.txt': 'c\n'},
      'Three tabs are open (a.txt, b.txt, c.txt). Move the c.txt tab to the first position.',
      'The tab bar order is c.txt, a.txt, b.txt.', [key('Alt+,'), cmd('tabmove 1')],
      [('tabs', 'c.txt is the first tab.', tabs('names'))], args=['a.txt', 'b.txt', 'c.txt']),
    g('gui-edit-split', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'notes.txt and other.txt are open side by side. Add the line `edited` at the start of other.txt and save '
      'other.txt (leave notes.txt unchanged).', 'other.txt starts with "edited" and is saved; notes.txt is unchanged.',
      [typ('edited'), key('Enter'), SAVE],
      [('file', 'other.txt is saved with the new line.', file('other.txt')),
       ('notes', 'notes.txt is unchanged.', file('notes.txt'))], args=['notes.txt', 'other.txt'],
      config_files={'settings.json': '{"multiopen": "vsplit"}'}, req={'notes': ['file']}),
    g('gui-close-middle-tab', 'splits-tabs', {'a.txt': 'a\n', 'b.txt': 'b\n', 'c.txt': 'c\n'},
      'Close the b.txt tab, keeping a.txt and c.txt open.', 'Only the tabs a.txt and c.txt remain.',
      [key('Alt+.'), key('Control+Q')], [('tabs', 'Two tabs remain.', tabs('names'))],
      args=['a.txt', 'b.txt', 'c.txt']),
    g('gui-help-topic', 'help', {'notes.txt': NOTES}, 'Open micro\'s built-in help for the `keybindings` topic.',
      'The keybindings help is shown in a pane next to notes.txt.', [cmd('help keybindings')],
      [('panes', 'A help pane for keybindings is open.', panes('name'))], args=['notes.txt']),
    g('gui-help-close', 'help', {'notes.txt': NOTES}, 'The help is open below notes.txt. Close the help pane.',
      'Only notes.txt is shown.', [key('Control+G')], [('panes', 'The help pane is closed.', panes('name'))],
      args=['notes.txt'], prep=[key('Control+G')], expect={'panes': ['notes.txt', 'Help help']}),
]

FILES = [
    g('gui-save-as', 'files', {'notes.txt': NOTES}, 'Save the content of notes.txt under the new name copy.txt.',
      'The buffer is now named copy.txt and has no unsaved changes.', [cmd('save copy.txt')],
      [('file', 'copy.txt holds the text.', file('copy.txt')), ('name', 'The buffer is named copy.txt.',
                                                                status('name'))], args=['notes.txt']),
    g('gui-new-file', 'files', {}, 'Create a new file named hello.txt containing the single line `hello world` and '
      'save it.', 'The buffer hello.txt shows "hello world" and is saved.',
      [typ('hello world'), key('Control+S'), typ('hello.txt'), key('Enter')],
      [('file', 'hello.txt is written.', file('hello.txt'))]),
    g('gui-open', 'files', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Open other.txt in place of notes.txt (in the same pane).', 'The single pane now shows other.txt.',
      [cmd('open other.txt')], [('name', 'The pane shows other.txt.', status('name'))], args=['notes.txt']),
    g('gui-save-all', 'files', {'a.txt': 'a\n', 'b.txt': 'b\n'},
      'Two tabs are open. Add `1` at the start of a.txt and `2` at the start of b.txt, and save both files.',
      'Both buffers show their new first character and neither has unsaved changes.',
      [typ('1'), key('Control+S'), key('Alt+.'), typ('2'), key('Control+S')],
      [('a', 'a.txt is saved.', file('a.txt')), ('b', 'b.txt is saved.', file('b.txt'))], args=['a.txt', 'b.txt']),
    g('gui-mkparents', 'files', {'notes.txt': NOTES},
      'Save the content of notes.txt as `archive/2026/notes.txt` (the archive directory does not exist yet).',
      'The buffer is named archive/2026/notes.txt and has no unsaved changes.',
      [cmd('set mkparents on'), cmd('save archive/2026/notes.txt')],
      [('file', 'The file is written in the new directories.', file('archive/2026/notes.txt'))],
      args=['notes.txt']),
    gui('gui-quit-discard', 'files', {'notes.txt': NOTES}, [
        step('save', 'Type `keep ` at the start of notes.txt and save the file.', [typ('keep '), SAVE],
             [('file', 'notes.txt is saved with the change.', file('notes.txt'))],
             acceptance='Line 1 reads "keep alpha beta gamma" and the file is saved.', requires={'done': ['file']}),
        step('discard', 'Now type `zzz` at the start of line 1, then quit micro without saving this second change.',
             [key('Home'), typ('zzz'), key('Control+Q'), key('n')],
             [('file', 'notes.txt keeps the saved change only.', file('notes.txt')),
              ('proc', 'micro has exited.', {'kind': 'process'})],
             acceptance='micro has exited.', depends=['save'],
             requires={'done': ['file', 'proc'], 'proc': ['file']}),
    ], args=['notes.txt']),
]

MISC = [
    g('gui-macro', 'macros', {'list.txt': 'one\ntwo\nthree\nfour\n'},
      'Record a keyboard macro that puts `* ` at the start of the current line and moves to the next line; record it '
      'on line 1, then replay it on lines 2 and 3. Save the file.',
      'Lines 1-3 start with "* ", line 4 does not, and the file is saved.',
      [key('Control+U'), typ('* '), key('Home'), key('Down'), key('Control+U'), key('Control+J'), key('Control+J'),
       SAVE], [('file', 'The macro applied to three lines.', file('list.txt'))], args=['list.txt']),
    g('gui-ruler-toggle', 'display', {'notes.txt': NOTES}, 'Hide the line numbers for this session using their '
      'toggle key (no lasting setting).', 'No line numbers are shown.', [key('Control+R')],
      [('rows', 'The text starts at the first column.', rows(0, 2)),
       ('settings', 'settings.json is unchanged.', config('settings.json'))], args=['notes.txt'],
      req={'settings': ['rows']}, config_files={'settings.json': '{}'}),
    g('gui-autoclose', 'plugins', {'calc.py': 'x = \n'},
      'At the end of the first line of calc.py type `max(1, 2` — let micro add the closing parenthesis — then save.',
      'The line reads "x = max(1, 2)" and the file is saved.', [key('End'), typ('max(1, 2'), SAVE],
      [('file', 'The closing parenthesis was added.', file('calc.py'))], args=['calc.py']),
    g('gui-complete', 'autocomplete', {'words.txt': 'elephant\n\n'},
      'On line 2 of words.txt type `ele` and complete it to `elephant` with micro\'s word completion, then save.',
      'Line 2 reads "elephant" and the file is saved.', [key('Down'), typ('ele'), key('Tab'), SAVE],
      [('file', 'The word was completed.', file('words.txt'))], args=['words.txt']),
]


INDENTED = 'items:\n- one\n- two\n- three\nend\n'
MIXED = 'keep this\ntrailing spaces   \nmore text  \n'
PARAS = 'first paragraph\nstill first\n\nsecond paragraph\nstill second\n\nthird paragraph\n'

MORE_EDITING = [
    edit('gui-delete-to-eol', 'Delete everything from the word `quick` to the end of line 2 of notes.txt (keep '
         '"the teh "), then save.', 'Line 2 reads "the teh " and the other lines are unchanged; the file is saved.',
         [at(2, 9), key('Shift+End'), key('Delete')]),
    edit('gui-delete-word-left', 'Delete the word `gamma` at the end of line 1 of notes.txt, leaving "alpha beta ", '
         'then save.', 'Line 1 reads "alpha beta " and the file is saved.', [key('End'), key('Alt+Backspace')]),
    edit('gui-replace-line', 'Replace the whole text of line 3 of notes.txt with `line three`, then save.',
         'Line 3 reads "line three" and the other lines are unchanged; the file is saved.',
         [at(3, 1), key('Shift+End'), typ('line three')]),
    edit('gui-split-line', 'Split line 1 of notes.txt after "alpha " so that "beta gamma" starts its own line, then '
         'save.', 'The first two lines read "alpha " and "beta gamma"; the file is saved.',
         [at(1, 7), key('Enter')]),
    edit('gui-indent-spaces', 'Indent the lines "- one", "- two" and "- three" of list.yaml by four spaces each (not '
         'tabs), then save.', 'Those three lines are indented by four columns and the file is saved.',
         [at(2, 1), keys('Shift+Down', 'Shift+Down', 'Shift+Down'), key('Tab')], text=INDENTED, name='list.yaml'),
    g('gui-trailing', 'editing', {'mixed.txt': MIXED}, 'Lines 2 and 3 of mixed.txt end with spaces, which micro '
      'highlights. Remove those trailing spaces, then save.',
      'No trailing spaces are highlighted any more and the file is saved.', [cmd('set rmtrailingws on'), SAVE],
      [saved('mixed.txt', 'The file is saved with the change.')], args=['mixed.txt'],
      config_files={'settings.json': '{"hltrailingws": true}'}),
    edit('gui-uncomment', 'Uncomment lines 2 and 3 of conf.py (remove their `# ` markers), then save.',
         'Lines 2 and 3 read "a = 1" and "b = 2" and the file is saved.',
         [at(2, 1), keys('Shift+Down', 'Shift+Down'), key('Alt+/')], text='# header\n# a = 1\n# b = 2\n', name='conf.py'),
    edit('gui-comment-block', 'Comment out lines 1 to 3 of main.go with micro\'s comment feature, then save.',
         'Lines 1-3 start with "//" and the file is saved.',
         [keys('Shift+Down', 'Shift+Down', 'Shift+Down'), key('Alt+/')],
         text='package main\nimport "fmt"\nfunc main() {}\n', name='main.go'),
    g('gui-retab', 'editing', {'retab.txt': '    one\n        two\nthree\n'}, 'retab.txt is indented with spaces, '
      'which micro highlights as indentation errors. Convert the leading spaces into tabs (one tab per four spaces), '
      'then save.', 'No indentation is highlighted as an error any more and the file is saved.', [cmd('retab'), SAVE],
      [saved('retab.txt', 'The file is saved with the change.')], args=['retab.txt'],
      config_files={'settings.json': '{"hltaberrors": true}'}),
    edit('gui-duplicate-block', 'Duplicate lines 2 and 3 of notes.txt so the pair appears twice in a row, then save.',
         'Lines 2-5 read "the teh quick fox", "third line here", "the teh quick fox", "third line here"; the file '
         'is saved.', [at(2, 1), keys('Shift+Down', 'Shift+Down'), key('Control+D')]),
    edit('gui-move-block-down', 'Move lines 1 and 2 of notes.txt down by one line (below "third line here"), then '
         'save.', '"third line here" is now line 1 followed by "alpha beta gamma" and "the teh quick fox"; the file '
         'is saved.', [keys('Shift+Down', 'Shift+Down'), key('Alt+Down')]),
    edit('gui-cut-two', 'Cut lines 2 and 3 of notes.txt and paste them at the end of the file, then save.',
         'The file reads alpha beta gamma, fourth line, fifth line, the teh quick fox, third line here; it is saved.',
         [at(2, 1), key('Control+K'), key('Control+K'), key('Control+End'), key('Control+V')]),
    edit('gui-overwrite', 'Overwrite the first five characters of notes.txt ("alpha") with `OMEGA` without changing '
         'the length of the line, then save.', 'Line 1 reads "OMEGA beta gamma" and the file is saved.',
         [key('Insert'), typ('OMEGA'), key('Insert')]),
    edit('gui-eofnewline', 'Turn off micro\'s automatic final newline (lasting setting), then add `!` at the end of '
         'raw.txt and save.', 'The text ends with "!" and the file is saved.',
         [cmd('set eofnewline off'), key('Control+End'), typ('!')], text='no newline at end', name='raw.txt'),
    edit('gui-paste-indent', 'With the cursor at the end of line 2 of block.py, press Enter and paste these lines so '
         'they line up with the existing body, then save:\n```\nx = 1\ny = 2\n```',
         'Lines 3 and 4 read "    x = 1" and "    y = 2" (indented like line 2) and the file is saved.',
         [at(2, 1), key('End'), key('Enter'), paste('x = 1\ny = 2')], text='def f():\n    pass\n', name='block.py'),
]

MORE_NAV = [
    g('gui-goto-last-but-two', 'navigation', {'long.txt': LONG}, 'Move the cursor to the third-last line of long.txt '
      '("entry number 98").', 'The cursor is on line 98 ("entry number 98").', [cmd('goto -4')],
      [('line', 'The cursor is on line 98.', status('line'))], args=['long.txt']),
    g('gui-paragraph', 'navigation', {'paras.txt': PARAS}, 'Move the cursor to the empty line that follows the second '
      'paragraph of paras.txt.', 'The cursor is on the empty line 6, after "still second".',
      [key('Alt+}'), key('Alt+}')], [('pos', 'The cursor is on line 6.', pos())], args=['paras.txt']),
    g('gui-page-down', 'navigation', {'long.txt': LONG}, 'Scroll long.txt down by one page with the cursor following.',
      'The view shows later lines and the cursor is about one page further down (line 33).', [key('PageDown')],
      [('pos', 'The cursor moved a page.', pos())], args=['long.txt']),
    g('gui-word-right', 'navigation', {'notes.txt': NOTES}, 'Put the cursor at the start of the word `gamma` on line 1.',
      'The status line shows the cursor at line 1, column 12.', [{'keys': ['Right'] * 11}],
      [('pos', 'The cursor is at 1,12.', pos())], args=['notes.txt']),
    g('gui-find-backwards', 'search', {'notes.txt': NOTES}, 'From the end of notes.txt, find the last occurrence of '
      '`line` before the cursor.', 'The "line" of "fifth line" is selected or the cursor is on it.',
      [key('Control+End'), key('Control+F'), typ('line'), key('Enter'), key('Control+P')],
      [('line', 'The cursor is on line 5.', status('line'))], args=['notes.txt']),
    g('gui-find-literal', 'search', {'expr.txt': 'ab\naab\na+b\n'}, 'Find the literal text `a+b` (with the plus sign) '
      'in expr.txt.', 'The "a+b" on line 3 is selected or the cursor is on it.',
      [key('Alt+F'), typ('a+b'), key('Enter')], [('line', 'The cursor is on line 3.', status('line'))],
      args=['expr.txt']),
    g('gui-replace-in-selection', 'search', {'colors.txt': 'red apple\nred car\nred sky\n'},
      'Replace `red` with `green` only on lines 2 and 3 of colors.txt, then save.',
      'Lines 2 and 3 say green, line 1 still says red, and the file is saved.',
      [key('Down'), keys('Shift+Down', 'Shift+End'), cmd('replaceall red green'), SAVE],
      [('file', 'Only lines 2 and 3 changed.', file('colors.txt'))], args=['colors.txt']),
    g('gui-replace-case', 'search', {'case.txt': 'Word word WORD\n'},
      'Replace only the lower-case `word` (exact case) with `term` in case.txt, then save.',
      'The line reads "Word term WORD" and the file is saved.',
      [cmd('setlocal ignorecase off'), cmd('replaceall word term'), SAVE],
      [('file', 'Only the exact-case word changed.', file('case.txt'))], args=['case.txt']),
]

MORE_PANES = [
    g('gui-split-switch', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'notes.txt (left) and other.txt (right) are open side by side with other.txt active. Make notes.txt the '
      'active split and add `>` at the start of its first line, then save notes.txt.',
      'notes.txt starts with ">" and is saved.', [key('Control+W'), typ('>'), SAVE],
      [('file', 'notes.txt is saved with the change.', file('notes.txt'))], args=['notes.txt', 'other.txt'],
      config_files={'settings.json': '{"multiopen": "vsplit"}'},
      expect={'panes': ['notes.txt', 'other.txt'], 'cursor_columns': [61, 119]}),
    g('gui-unsplit', 'splits-tabs', {'notes.txt': NOTES, 'a.txt': 'a\n', 'b.txt': 'b\n'},
      'Three splits are open (notes.txt, a.txt and b.txt). Close the a.txt and b.txt splits so that only notes.txt '
      'remains.', 'Only notes.txt is shown, in a single pane.', [key('Control+Q'), key('Control+Q')],
      [('panes', 'One pane remains.', panes('name'))], args=['notes.txt', 'a.txt', 'b.txt'],
      config_files={'settings.json': '{"multiopen": "hsplit"}'}, expect={'panes': ['notes.txt', 'a.txt', 'b.txt']}),
    g('gui-help-vsplit', 'help', {'notes.txt': NOTES}, 'Open the help topic `options` in a vertical split beside '
      'notes.txt, so that notes.txt and the help are the only two panes, side by side.',
      'notes.txt is shown on the left and the options help on the right, with no other pane.',
      [cmd('help -vsplit options')],
      [('columns', 'The help pane is beside the file.', columns(0))], args=['notes.txt']),
    g('gui-new-tab-save', 'splits-tabs', {'notes.txt': NOTES}, 'Open a new empty tab, type `tab text` in it and save '
      'it as tabfile.txt.', 'A second tab named tabfile.txt shows "tab text" and is saved.',
      [key('Control+T'), typ('tab text'), key('Control+S'), typ('tabfile.txt'), key('Enter')],
      [('file', 'tabfile.txt is written.', file('tabfile.txt')), ('tabs', 'Two tabs are open.', tabs())],
      args=['notes.txt']),
    g('gui-close-tab-save', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'},
      'Two tabs are open. In other.txt add `changed ` at the start of line 1, then close that tab, saving the change '
      'when asked.', 'Only notes.txt remains open.',
      [key('Alt+.'), typ('changed '), key('Control+Q'), key('y')],
      [('file', 'other.txt is saved.', file('other.txt')), ('tabs', 'The tab bar is gone.', tabs())],
      args=['notes.txt', 'other.txt']),
    g('gui-tab-last', 'splits-tabs', {'a.txt': 'a\n', 'b.txt': 'b\n', 'c.txt': 'c\n', 'd.txt': 'd\n'},
      'Four tabs are open with a.txt active. Make the last tab (d.txt) active.', 'd.txt is shown and its tab is active.',
      [key('Alt+,')], [('tabs', 'The last tab is active.', tabs('active', 'current'))], args=['a.txt', 'b.txt', 'c.txt', 'd.txt']),
]

MORE_OPTIONS = [
    g('gui-autoindent-off', 'options', {'block.py': 'def f():\n    pass\n'},
      'Turn off automatic indentation (lasting setting), then press Enter at the end of line 2 of block.py, type '
      '`done` and save.', 'Line 3 reads "done" at the first column and the file is saved.',
      [cmd('set autoindent off'), at(2, 1), key('End'), key('Enter'), typ('done'), SAVE],
      [('settings', 'settings.json records autoindent false.', config('settings.json')),
       ('file', 'The new line is not indented.', file('block.py'))], args=['block.py']),
    g('gui-cursorline-off', 'options', {'notes.txt': NOTES}, 'Turn off the highlighting of the cursor line (lasting '
      'setting).', 'The line with the cursor is drawn like the other lines.', [cmd('set cursorline off')],
      [('settings', 'settings.json records cursorline false.', config('settings.json'))], args=['notes.txt']),
    g('gui-colorcolumn', 'options', {'notes.txt': NOTES}, 'Mark column 10 with a coloured column guide (lasting '
      'setting).', 'Column 10 of the text area is drawn differently on every line.', [cmd('set colorcolumn 10')],
      [('settings', 'settings.json records colorcolumn 10.', config('settings.json'))], args=['notes.txt']),
    g('gui-wordwrap', 'options', {'wide.txt': ' '.join(['word'] * 60) + '\n'},
      'Make the long line of wide.txt wrap on screen at word boundaries (lasting settings).',
      'The long line wraps onto further screen rows without splitting any "word".',
      [cmd('set softwrap on'), cmd('set wordwrap on')],
      [('settings', 'settings.json records softwrap and wordwrap.', config('settings.json'))], args=['wide.txt']),
    g('gui-filetype', 'options', {'script.txt': 'echo hello\n'}, 'Set the filetype of the open buffer script.txt to '
      '`shell` for this buffer.', 'The status line reports ft:shell.', [cmd('setlocal filetype shell')],
      [('ft', 'The filetype is shell.', status('filetype'))], args=['script.txt']),
    g('gui-ignorecase', 'options', {'notes.txt': NOTES}, 'Make searches case-sensitive (lasting setting), then '
      'search notes.txt for `Alpha`.', 'The search finds no match (the lower-case "alpha" is not selected).',
      [cmd('set ignorecase off'), key('Control+F'), typ('Alpha'), key('Enter')],
      [('settings', 'settings.json records ignorecase false.', config('settings.json'))], args=['notes.txt']),
    g('gui-reset-option', 'options', {'tabbed.txt': TABBED}, 'The tab size is currently set to 8 in the settings. Put '
      'it back to micro\'s default.', 'Tabs are drawn with the default width of 4 columns.',
      [cmd('reset tabsize')], [('settings', 'settings.json no longer sets tabsize.', config('settings.json'))],
      args=['tabbed.txt'], config_files={'settings.json': '{"tabsize": 8}'}),
    g('gui-toggle-option', 'options', {'notes.txt': NOTES}, 'The ruler (line numbers) is turned off in the settings. '
      'Turn it back on as a lasting setting.', 'Line numbers are shown again.', [cmd('toggle ruler')],
      [('settings', 'settings.json no longer turns the ruler off.', config('settings.json'))], args=['notes.txt'],
      config_files={'settings.json': '{"ruler": false}'}),
]

MORE_FILES = [
    g('gui-open-subdir', 'files', {'notes.txt': NOTES, 'docs/guide.txt': 'guide text\n'},
      'Open the file docs/guide.txt in place of notes.txt.', 'The pane shows docs/guide.txt with "guide text".',
      [cmd('open docs/guide.txt')], [('name', 'The buffer is docs/guide.txt.', status('name'))], args=['notes.txt']),
    g('gui-quit-save', 'files', {'notes.txt': NOTES}, 'Type `final ` at the start of notes.txt, then quit micro and '
      'save the change when asked.', 'micro has exited.', [typ('final '), key('Control+Q'), key('y')],
      [('file', 'notes.txt is saved with the change.', file('notes.txt')), ('proc', 'micro has exited.',
                                                                         {'kind': 'process'})], args=['notes.txt'],
      req={'proc': ['file']}),
    g('gui-save-copy-continue', 'files', {'notes.txt': NOTES}, 'Save the content of notes.txt also as backup.txt, '
      'then add `v2 ` at the start of line 1 and save again (into backup.txt, the buffer\'s new name).',
      'The buffer is named backup.txt, starts with "v2 alpha" and is saved.',
      [cmd('save backup.txt'), typ('v2 '), SAVE],
      [('backup', 'backup.txt has the second change.', file('backup.txt')),
       ('notes', 'notes.txt is unchanged.', file('notes.txt'))], args=['notes.txt'], req={'notes': ['backup']}),
    g('gui-crlf-to-unix', 'files', {'dos.txt': 'one\r\ntwo\r\n'}, 'Convert dos.txt to Unix (LF) line endings and save '
      'it.', 'The status line reports the unix format and the file is saved.', [cmd('set fileformat unix'), SAVE],
      [('file', 'The file has LF line endings.', file('dos.txt'))], args=['dos.txt']),
    g('gui-utf16', 'files', {'u.txt': 'hi\n'}, 'Save u.txt in the UTF-16LE encoding.',
      'The status line reports utf-16le and the file is saved.', [cmd('set encoding utf-16le'), SAVE],
      [('file', 'The file is UTF-16LE.', file('u.txt'))], args=['u.txt']),
]

MORE_MULTI = [
    g('gui-cursors-down', 'multicursor', {'list.txt': 'one\ntwo\nthree\nfour\n'},
      'Put `> ` at the start of the first three lines of list.txt at the same time (or one by one), then save.',
      'Lines 1-3 start with "> ", line 4 does not, and the file is saved.',
      [keys('Alt+Shift+Down', 'Alt+Shift+Down'), typ('> '), SAVE],
      [('file', 'Three lines are prefixed.', file('list.txt'))], args=['list.txt']),
    g('gui-delete-occurrences', 'multicursor', {'tags.txt': 'tag a tag b tag c\n'},
      'Delete every whole word `tag` (and the space after it) from tags.txt, then save.',
      'The line reads "a b c" and the file is saved.', [cmd('replaceall "tag " ""'), SAVE],
      [('file', 'All tags are removed.', file('tags.txt'))], args=['tags.txt']),
]

TWO_STEP = [
    gui('gui-tab-roundtrip', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'}, [
        step('open', 'Open other.txt in a new tab.', [cmd('tab other.txt')],
             [('tabs', 'Two tabs, other.txt active.', tabs())],
             acceptance='A tab bar shows notes.txt and other.txt with other.txt active.', requires={'done': ['tabs']}),
        step('back', 'Go back to the notes.txt tab.', [key('Alt+,')],
             [('tabs', 'The notes.txt tab is active.', tabs('active', 'current'))],
             acceptance='notes.txt is shown and its tab is active.', depends=['open'], requires={'done': ['tabs']}),
    ], args=['notes.txt']),
    gui('gui-edit-undo-redo', 'undo', {'notes.txt': NOTES}, [
        step('delete', 'Delete line 2 of notes.txt (do not save).', [at(2, 1), key('Control+K')],
             [('rows', 'Line 2 is gone.', rows(0, 2))], acceptance='"the teh quick fox" is no longer shown.',
             requires={'done': ['rows']}),
        step('undo', 'Undo the deletion.', [key('Control+Z')], [('rows', 'Line 2 is back.', rows(0, 2))],
             acceptance='"the teh quick fox" is shown again as line 2.', depends=['delete'],
             requires={'done': ['rows']}),
        step('redo', 'Redo the deletion, then save.', [key('Control+Y'), SAVE],
             [('file', 'The file is saved without line 2.', file('notes.txt'))],
             acceptance='Line 2 is gone again and the file is saved.', depends=['undo'],
             requires={'done': ['file']}),
    ], args=['notes.txt']),
    gui('gui-split-then-close', 'splits-tabs', {'notes.txt': NOTES, 'other.txt': 'other file\n'}, [
        step('split', 'Open other.txt in a horizontal split below notes.txt.', [cmd('hsplit other.txt')],
             [('panes', 'Two panes.', panes('name'))], acceptance='notes.txt is shown above and other.txt below.',
             requires={'done': ['panes']}),
        step('close', 'Close the other.txt split.', [key('Control+Q')], [('panes', 'One pane.', panes('name'))],
             acceptance='Only notes.txt is shown.', depends=['split'], requires={'done': ['panes']}),
    ], args=['notes.txt']),
    gui('gui-find-then-replace', 'search', {'notes.txt': NOTES}, [
        step('find', 'Find the word `fourth` in notes.txt.', [key('Control+F'), typ('fourth'), key('Enter')],
             [('line', 'The cursor is on line 4.', status('line'))],
             acceptance='"fourth" on line 4 is selected or the cursor is on it.', requires={'done': ['line']}),
        step('replace', 'Replace every `line` with `row` in the whole of notes.txt and save.',
             [key('Escape'), cmd('replaceall line row'), SAVE],
             [('file', 'The file is saved with the replacements.', file('notes.txt'))],
             acceptance='The lines read "third row here", "fourth row", "fifth row" and the file is saved.',
             requires={'done': ['file']}),
    ], args=['notes.txt']),
    gui('gui-set-then-check', 'options', {'tabbed.txt': TABBED}, [
        step('set', 'Make tabs 8 columns wide as a lasting setting.', [cmd('set tabsize 8')],
             [('settings', 'settings.json records tabsize 8.', config('settings.json'))],
             acceptance='Tabs in tabbed.txt are drawn eight columns wide.', requires={'done': ['settings']}),
        step('show', 'Show the current value of the tabsize option on the message line.', [cmd('show tabsize')],
             [('msg', 'The message line shows 8.', message())], acceptance='The message line shows 8.',
             depends=['set'], requires={'done': ['msg']}),
    ], args=['tabbed.txt']),
]

EPISODES_MORE = MORE_EDITING + MORE_NAV + MORE_PANES + MORE_OPTIONS + MORE_FILES + MORE_MULTI + TWO_STEP


def episodes():
    return EDITING + SEARCH + MULTI + SETTINGS + BINDINGS + PANES + FILES + MISC + EPISODES_MORE
