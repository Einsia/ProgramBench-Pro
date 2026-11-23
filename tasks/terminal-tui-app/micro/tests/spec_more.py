"""The default key bindings of the command bar (its own key map: editing, movement, selection, clipboard, undo and
history keys), syntax highlighting facts of more languages, regular-expression features of the find prompt, and
user runtime files in the configuration directory (syntax files, colorschemes, help topics).
"""
from spec_common import (attrs, cmd, contains, differ, family, key, keys, message, pos, row, rows, snap, status, typ,
                         wait)

TEXT = 'alpha beta gamma\nsecond line\nthird line\n'
PROMPT_TEXT = 'set ruler offXX'


def prompt(cid, goal, names, requirement, text=PROMPT_TEXT, marker='#', req=None):
    """Open the command bar, type text, press the keys under test, type a marker and read the prompt line (not run)."""
    steps = [key('Control+E'), typ(text)]
    if names:
        steps.append(keys(*names))
    if marker:
        steps.append(typ(marker))
    steps.append(snap('prompt'))
    return row(cid, goal, TEXT, steps, [('prompt', requirement, message('prompt'))], req=req)


WORDS = 'one two.three four'
COMMAND_KEYS = [
    prompt('left', 'Type a command, press Left twice, then #.', ['Left', 'Left'], 'Left moves within the prompt.'),
    prompt('home', 'Type a command, press Home, then #.', ['Home'], 'Home goes to the start of the prompt text.'),
    prompt('end', 'Type a command, press Home, End, then #.', ['Home', 'End'], 'End goes to the end of the prompt.'),
    prompt('ctrl-a', 'Type a command, press Control+A, then #.', ['Control+A'],
           'Control+A goes to the start of the prompt.'),
    prompt('ctrl-e', 'Type a command, press Control+A, Control+E, then #.', ['Control+A', 'Control+E'],
           'In the prompt Control+E goes to the end.'),
    prompt('alt-left', 'Type a command, press Alt+Left, then #.', ['Alt+Left'],
           'Alt+Left goes to the start of the prompt text.'),
    prompt('alt-right', 'Type a command, press Home, Alt+Right, then #.', ['Home', 'Alt+Right'],
           'Alt+Right goes to the end of the prompt.'),
    prompt('alt-up', 'Type a command, press Alt+Up, then #.', ['Alt+Up'],
           'Alt+Up goes to the start of the prompt (not the history).'),
    prompt('ctrl-left', 'Type words, press Control+Left twice, then #.', ['Control+Left', 'Control+Left'],
           'Control+Left moves word by word.', text=WORDS),
    prompt('ctrl-right', 'Type words, press Home, Control+Right twice, then #.', ['Home', 'Control+Right',
                                                                                'Control+Right'],
           'Control+Right moves word by word.', text=WORDS),
    prompt('ctrl-b', 'Type words, press Control+B, then #.', ['Control+B'], 'Control+B moves a word left.',
           text=WORDS),
    prompt('ctrl-f', 'Type words, press Home, Control+F, then #.', ['Home', 'Control+F'],
           'Control+F moves a word right in the prompt.', text=WORDS),
    prompt('alt-b', 'Type words, press Alt+b, then #.', ['Alt+b'], 'Alt+b moves a word left.', text=WORDS),
    prompt('alt-f', 'Type words, press Home, Alt+f, then #.', ['Home', 'Alt+f'], 'Alt+f moves a word right.',
           text=WORDS),
    prompt('backspace', 'Type a command, press Backspace twice.', ['Backspace', 'Backspace'],
           'Backspace deletes before the cursor.', marker=None),
    prompt('ctrl-h', 'Type a command, press Control+H.', ['Control+H'], 'Control+H is Backspace.', marker=None),
    prompt('delete', 'Type a command, press Home, Delete.', ['Home', 'Delete'], 'Delete removes the character under '
           'the cursor.', marker=None),
    prompt('ctrl-w', 'Type words, press Control+W.', ['Control+W'], 'Control+W deletes the word before the cursor.',
           text=WORDS, marker=None),
    prompt('ctrl-d', 'Type words, press Control+D.', ['Control+D'], 'In the prompt Control+D deletes the word before '
           'the cursor.', text=WORDS, marker=None),
    prompt('alt-backspace', 'Type words, press Alt+Backspace.', ['Alt+Backspace'],
           'Alt+Backspace deletes the word before the cursor.', text=WORDS, marker=None),
    prompt('shift-left', 'Type words, press Shift+Left three times, then #.', ['Shift+Left'] * 3,
           'Shift+Left selects; typing replaces the selection.', text=WORDS),
    prompt('shift-home', 'Type words, press Shift+Home, then #.', ['Shift+Home'],
           'Shift+Home selects to the start.', text=WORDS),
    prompt('alt-shift-left', 'Type words, press Alt+Shift+Left, then #.', ['Alt+Shift+Left'],
           'In the prompt Alt+Shift+Left selects a word left.', text=WORDS),
    prompt('ctrl-u', 'Type words, press Control+U, then #.', ['Control+U'],
           'Control+U selects to the start; typing replaces it.', text=WORDS),
    prompt('ctrl-k', 'Type words, press Control+K.', ['Control+K'], 'Control+K cuts the whole prompt line.',
           text=WORDS, marker=None),
    prompt('ctrl-k-paste', 'Type words, press Control+K, then Control+V twice.', ['Control+K', 'Control+V',
                                                                                 'Control+V'],
           'The cut prompt text can be pasted back.', text=WORDS, marker=None),
    prompt('ctrl-z', 'Type words, wait over a second, press Control+W then Control+Z.', ['Control+W', 'Control+Z'],
           'Control+Z undoes the last change in the prompt.', text=WORDS, marker=None,
           req={'prompt': ['ctrl-w/prompt']}),
    prompt('insert', 'Type a command, press Home, Insert, then XY.', ['Home', 'Insert'],
           'Insert switches the prompt to overwrite mode.', marker='XY'),
    prompt('ctrl-p', 'Run show ruler, then in the command bar press Control+P.', [], 'Control+P recalls history.',
           text='', marker=None),
]
COMMAND_KEYS[-1]['steps'] = [cmd('show ruler'), key('Control+E'), key('Control+P'), snap('prompt')]
# Undo in the prompt groups edits by wall-clock second like the buffer: the typing must lie in an earlier second.
next(r for r in COMMAND_KEYS if r['cid'] == 'ctrl-z')['steps'][2:2] = [wait(1.1)]

ABORT = [
    row('esc', 'Type a command and press Escape, then type x and save.', TEXT,
        [key('Control+E'), typ('set ruler off'), key('Escape'), typ('x'), key('Control+S')],
        [('file', 'Escape aborts the prompt; the next key goes to the buffer.', 'file')]),
    row('f10', 'Type a command and press F10.', TEXT, [key('Control+E'), typ('set ruler off'), key('F10')],
        [('rows', 'F10 aborts the prompt without running the command.', rows(0, 1)),
         ('msg', 'The prompt is closed.', 'msg')], req={'rows': ['ctrl-m/rows'], 'msg': ['ctrl-m/rows']}),
    row('ctrl-m', 'Type a command and press Control+M.', TEXT, [key('Control+E'), typ('set ruler off'),
                                                               key('Control+M')],
        [('rows', 'Control+M runs the command like Enter.', rows(0, 1))]),
]

# (case id, file name, content, [(requirement, ((row, col), (row, col)))]) as in spec_filetypes.
HIGHLIGHT = [
    ('java', 'hl.java', 'public class A {\n  int x = 1; // c\n}\n',
     [('The keyword public is highlighted.', ((0, 2), (0, 15))), ('The comment is highlighted.', ((1, 17), (1, 8)))]),
    ('ruby', 'hl.rb', 'def run\n  x = "s" # c\nend\n',
     [('The keyword def is highlighted.', ((0, 2), (0, 6))), ('The string is highlighted.', ((1, 9), (1, 4)))]),
    ('php', 'hl.php', '<?php\n$x = "s"; // c\n', [('The comment is highlighted.', ((1, 15), (1, 3)))]),
    ('lua', 'hl.lua', 'local x = 1 -- c\n', [('The keyword local is highlighted.', ((0, 2), (0, 8))),
                                                ('The comment is highlighted.', ((0, 17), (0, 8)))]),
    ('css', 'hl.css', 'p { color: red; }\n', [('The property is highlighted differently from the selector.',
                                                ((0, 6), (0, 2)))]),
    ('sql', 'hl.sql', 'SELECT name FROM t;\n', [('The keyword SELECT is highlighted.', ((0, 2), (0, 9)))]),
    ('toml', 'hl.toml', '[sec]\nkey = "v" # c\n', [('The comment is highlighted.', ((1, 14), (1, 2)))]),
    ('makefile', 'Makefile', 'all: build\n\t@echo hi # c\n', [('The target is highlighted.', ((0, 2), (0, 8)))]),
    ('dockerfile', 'Dockerfile', 'FROM scratch\nRUN echo hi\n',
     [('The instruction FROM is highlighted.', ((0, 2), (0, 8)))]),
    ('haskell', 'hl.hs', 'main = do\n  print 1 -- c\n', [('The keyword do is highlighted.', ((0, 9), (0, 2))),
                                                          ('The comment is highlighted.', ((1, 13), (1, 4)))]),
    ('typescript', 'hl.ts', 'let x: number = 1; // c\n', [('The keyword let is highlighted.', ((0, 2), (0, 6))),
                                                              ('The comment is highlighted.', ((0, 23), (0, 6)))]),
    ('perl', 'hl.pl', 'my $x = 1; # c\n', [('The comment is highlighted.', ((0, 15), (0, 5)))]),
    ('xml', 'hl.xml', '<a href="x">t</a>\n', [('The tag is highlighted differently from the text.', ((0, 3), (0, 14)))]),
    ('diff', 'hl.patch', '--- a\n+++ b\n+added\n-removed\n',
     [('Added and removed lines are drawn differently.', ((2, 3), (3, 3)))]),
    ('ini', 'hl.ini', '[sec]\nkey=1 ; c\n', [('The section header is highlighted.', ((0, 3), (1, 2)))]),
]

REGEX = [
    row('digit-class', 'Find "\\d+".', 'abc 123 def\n', [key('Control+F'), typ('\\d+'), key('Enter'), typ('#')],
        [('file', '\\d matches digits.', 'file')], save=True),
    row('space-class', 'Find "a\\sb".', 'ab a b\n', [key('Control+F'), typ('a\\sb'), key('Enter'), typ('#')],
        [('file', '\\s matches a space.', 'file')], save=True),
    row('repeat', 'Find "o{2}".', 'one boo\n', [key('Control+F'), typ('o{2}'), key('Enter'), typ('#')],
        [('file', 'Counted repetition matches.', 'file')], save=True),
    row('lazy', 'Find "a.*?b".', 'axbxb\n', [key('Control+F'), typ('a.*?b'), key('Enter'), typ('#')],
        [('file', 'A lazy quantifier stops at the first b.', 'file')], save=True),
    row('greedy', 'Find "a.*b".', 'axbxb\n', [key('Control+F'), typ('a.*b'), key('Enter'), typ('#')],
        [('file', 'A greedy quantifier runs to the last b.', 'file')], save=True),
    row('inline-case', 'With the default ignorecase, find "(?-i)Bar".', 'bar Bar\n',
        [key('Control+F'), typ('(?-i)Bar'), key('Enter'), typ('#')],
        [('file', 'An inline flag turns case sensitivity back on.', 'file')], save=True),
    row('group-alt', 'Find "(ab)+".', 'xababy\n', [key('Control+F'), typ('(ab)+'), key('Enter'), typ('#')],
        [('file', 'A repeated group matches as a whole.', 'file')], save=True),
    row('negated', 'With the default ignorecase, find "[^a-z ]+".', 'abc XYZ 123 def\n',
        [key('Control+F'), typ('[^a-z ]+'), key('Enter'), typ('#')],
        [('file', 'A negated class matches; ignoring case it excludes the capitals too, so the digits match.', 'file')],
        save=True),
]


# The autoclose plugin also works in the command bar.
AUTOCLOSE = [
    prompt('autoclose', 'Type "set x (" in the command bar, then #.', [], 'Typing ( in the command bar also inserts the '
           'closing ).', text='set x ('),
]


def highlight_rows():
    out = []
    for cid, name, text, facts in HIGHLIGHT:
        checks = [(f'hl{i + 1}', requirement, differ(pair)) for i, (requirement, pair) in enumerate(facts)]
        out.append(row(f'hl-{cid}', f'Open {name} and look at its highlighting.', text, [], checks,
                       path=f'hl2/{name}'))
    return out


def episodes():
    return (family('cmdkey', 'command-bar', COMMAND_KEYS + ABORT + AUTOCLOSE, 11) + family('syntax-more', 'filetypes',
                                                                            highlight_rows(), 8)
            + family('regex', 'search', REGEX, 8) + family('usersyntax', 'filetypes', USER_SYNTAX, 8)
            + family('usercolors', 'display', USER_COLORS, 4) + family('userhelp', 'help', USER_HELP, 2)
            + family('userdefault', 'filetypes', USER_DEFAULT, 1))


# User runtime files in micro's configuration directory: syntax files (new filetypes, detection by name, header and
# signature, regions with skip patterns, embedded languages, overriding a built-in syntax and the default one),
# colorschemes (attributes, include, subgroup fallback) and help topics. Placed files stay for the rest of an episode,
# so every row uses its own names and only the override row touches a built-in filetype (go).
MINI = r'''filetype: mini
detect:
    filename: "\\.mini$"
rules:
    - statement: "\\b(begin|end)\\b"
    - comment: "#.*$"
'''
HDR = r'''filetype: hdrlang
detect:
    header: "^%%HDR"
rules:
    - constant: "\\bvalue\\b"
'''
GO_OVERRIDE = r'''filetype: go
detect:
    filename: "\\.go$"
rules:
    - comment: "//.*$"
'''
REGION = r'''filetype: reg
detect:
    filename: "\\.reg$"
rules:
    - constant.string:
        start: "<<"
        end: ">>"
        skip: "\\\\."
'''
EMBED = r'''filetype: emb
detect:
    filename: "\\.emb$"
rules:
    - default:
        start: "\\{\\{"
        end: "\\}\\}"
        rules:
            - include: "python"
'''
SIGNATURES = {f'syntax/uf-sig{x}.yaml': f'filetype: sig{x}\ndetect:\n    filename: "\\\\.sig$"\n    signature: "^@{x.upper()}"\n'
              'rules: []\n' for x in 'ab'}
SUBGROUP = r'''filetype: sub
detect:
    filename: "\\.sub$"
rules:
    - constant.string.special: "\\bfoo\\b"
    - constant.number: "\\b[0-9]+\\b"
'''
DEFAULT_SYNTAX = r'''filetype: unknown
detect:
    filename: ""
rules:
    - comment: "(^|\\s)#.*$"
'''
MINE = 'color-link default "white,black"\ncolor-link comment "underline white"\ncolor-link statement "bold white"\n'
INCLUDING = 'include "monokai"\ncolor-link comment "italic white"\n'
SUBGROUP_COLORS = ('color-link default "white,black"\ncolor-link constant "underline white"\n'
                   'color-link constant.number "bold white"\n')
PY = 'def f(): # c\nvalue\n'


def complete(cid, goal, typed, requirement, config_files):
    return row(cid, goal, TEXT, [key('Control+E'), typ(typed), key('Tab'), snap('line')],
               [('line', requirement, message('line'))], config_files=config_files)


USER_SYNTAX = [
    row('new-filetype', 'With a user syntax file for *.mini files, open one.', 'begin x # note\nend\n', [],
        [('ft', 'A syntax file in the configuration directory defines a new filetype.', status('filetype')),
         ('hl', 'Its pattern rules highlight the keyword and the comment.', differ(((0, 2), (0, 8)), ((0, 10), (0, 8))))],
        path='uf1.mini', config_files={'syntax/uf-mini.yaml': MINI}),
    row('header', 'With a user syntax file detected by a header, open a file without extension starting with it.',
        '%%HDR\nvalue other\n', [],
        [('ft', 'The first line selects the filetype.', status('filetype')),
         ('hl', 'Its rule highlights the keyword.', differ(((1, 2), (1, 8))))],
        path='uf2-header', config_files={'syntax/uf-hdr.yaml': HDR}),
    row('override', 'With a user go.yaml that only highlights comments, open a Go file.', 'func main() // c\n', [],
        [('plain', 'The user file replaces the built-in Go syntax: func is no longer highlighted.',
          differ(((0, 2), (0, 7)))),
         ('comment', 'The user file\'s comment rule applies.', differ(((0, 14), (0, 7))))],
        path='uf3.go', config_files={'syntax/go.yaml': GO_OVERRIDE}, req={'plain': ['override/comment']}),
    row('region-skip', 'With a user syntax region from << to >> that skips escaped characters, open a file.',
        'a <<x \\>> y>> b\n', [],
        [('hl', 'The escaped >> does not end the region; the text after the real end is plain.',
          differ(((0, 12), (0, 2)), ((0, 16), (0, 2))))],
        path='uf4.reg', config_files={'syntax/uf-reg.yaml': REGION}),
    row('include', 'With a user syntax region that includes the python rules, open a file.', 'def {{ def x }}\n', [],
        [('hl', 'Python keywords are highlighted inside the region only.', differ(((0, 9), (0, 2))))],
        path='uf6.emb', config_files={'syntax/uf-emb.yaml': EMBED}),
    row('signature-a', 'With two user syntax files for *.sig told apart by signatures, open a file with the first one.',
        'x\n@A here\n', [], [('ft', 'The signature found in the first lines picks the filetype.', status('filetype'))],
        path='uf7a.sig', config_files=SIGNATURES),
    row('signature-b', 'With the same two syntax files, open a file with the second signature.', 'x\n@B here\n', [],
        [('ft', 'The other signature picks the other filetype.', status('filetype'))],
        path='uf7b.sig', config_files=SIGNATURES),
    complete('filetype-complete', 'With a user syntax file for hdrlang, type "set filetype hdrl" and press Tab.',
             'set filetype hdrl', 'User filetypes are completed.', {'syntax/uf-hdr.yaml': HDR}),
]

USER_COLORS = [
    row('attrs', 'With a user colorscheme giving comments underline and statements bold, open a Python file.', PY, [],
        [('attrs', 'The colorscheme\'s attributes are applied; plain text has none.', attrs((0, 2), (0, 11), (1, 2))),
         ('unlinked', 'Groups the colorscheme does not link (the line numbers) use its default style.',
          differ(((1, 0), (1, 2))))],
        path='uf8.py', settings={'colorscheme': 'uf-mine'}, config_files={'colorschemes/uf-mine.micro': MINE},
        req={'unlinked': ['attrs/attrs']}),
    row('include', 'With a user colorscheme that includes monokai and changes comments, open a Python file.', PY, [],
        [('attrs', 'The comment uses the new attribute.', attrs((0, 11))),
         ('base', 'The included colorscheme still styles the line numbers.', differ(((1, 0), (1, 2))))],
        path='uf9.py', settings={'colorscheme': 'uf-inc'}, config_files={'colorschemes/uf-inc.micro': INCLUDING}),
    row('subgroup', 'With a colorscheme linking constant and constant.number, open a file whose syntax uses '
        'constant.string.special and constant.number.', 'foo 42 bar\n', [],
        [('attrs', 'A missing subgroup falls back to its root group; a linked subgroup uses its own style.',
          attrs((0, 2), (0, 6), (0, 9)))],
        path='uf10.sub', settings={'colorscheme': 'uf-sub'},
        config_files={'syntax/uf-sub.yaml': SUBGROUP, 'colorschemes/uf-sub.micro': SUBGROUP_COLORS}),
    complete('complete', 'With a user colorscheme uf-mine, type "set colorscheme uf-mi" and press Tab.',
             'set colorscheme uf-mi', 'User colorschemes are completed.', {'colorschemes/uf-mine.micro': MINE}),
]

USER_HELP = [
    row('topic', 'With a help file uf-topic.md in the configuration directory, run help uf-topic.', TEXT,
        [cmd('help uf-topic')],
        [('help', 'A help file in the configuration directory is a help topic.', contains('Custom help text.'))],
        config_files={'help/uf-topic.md': '# My topic\n\nCustom help text.\n'}),
    complete('complete', 'With the same help file, type "help uf-t" and press Tab.', 'help uf-t',
             'User help topics are completed.', {'help/uf-topic.md': '# My topic\n\nCustom help text.\n'}),
]

USER_DEFAULT = [
    row('default', 'With a user default.yaml highlighting # comments, open a .txt file.', 'x # note\n', [],
        [('hl', 'The user default syntax applies to files without a filetype.', differ(((0, 4), (0, 2))))],
        path='uf5.txt', config_files={'syntax/default.yaml': DEFAULT_SYNTAX}),
]
