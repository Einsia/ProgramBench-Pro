"""micro's built-in plugins: comment (Alt+/, Control+_ and the comment command, with the comment syntax of each
filetype), autoclose (brackets and quotes), ftoptions (per-filetype indentation) and the diff gutter.
"""
from spec_common import (at, cmd, family, file, key, keys, message, pos, row, rows, snap, status, typ, wait)

BODY = 'first line\n    indented line\nlast line\n'

# (filetype, file name, first line of the file): each distinct comment syntax and the filetypes users meet most.
COMMENT_TYPES = [
    ('go', 'main.go', 'package main'), ('c', 'prog.c', 'int x;'), ('c++', 'prog.cpp', 'int x;'),
    ('java', 'App.java', 'class App {}'), ('javascript', 'app.js', 'let x = 1;'), ('rust', 'lib.rs', 'fn f() {}'),
    ('python', 'tool.py', 'x = 1'), ('shell', 'run.sh', 'echo hi'), ('ruby', 'app.rb', 'puts 1'),
    ('yaml', 'conf.yaml', 'key: value'), ('toml', 'conf.toml', 'key = 1'), ('perl', 'tool.pl', 'print 1;'),
    ('lua', 'init2.lua', 'local x = 1'), ('sql', 'query.sql', 'select 1;'), ('haskell', 'Main.hs', 'main = 1'),
    ('elm', 'Main.elm', 'x = 1'), ('html', 'page.html', '<p>hi</p>'), ('markdown', 'notes.md', 'Some text'),
    ('xml', 'data.xml', '<a/>'), ('css', 'style.css', 'p { color: red; }'), ('ini', 'conf.ini', 'key=1'),
    ('batch', 'run.bat', 'echo hi'), ('ocaml', 'main.ml', 'let x = 1'), ('pascal', 'prog.pas', 'begin end.'),
    ('tex', 'doc.tex', '\\section{A}'), ('twig', 'page.twig', '<p>{{ x }}</p>'), ('json', 'data.json', '{"a": 1}'),
    ('makefile', 'Makefile', 'all: build'), ('dockerfile', 'Dockerfile', 'FROM scratch'),
    ('cmake', 'CMakeLists.txt', 'project(x)'), ('zig', 'main.zig', 'const x = 1;'), ('swift', 'app.swift', 'let x = 1'),
    ('kotlin', 'App.kt', 'val x = 1'), ('typescript', 'app.ts', 'let x = 1;'), ('php', 'index.php', '<?php echo 1;'),
    ('nim', 'app.nim', 'echo 1'), ('fish', 'conf.fish', 'set x 1'), ('unknown', 'plain.txt', 'just text'),
]


def f(requirement):
    return ('file', requirement, 'file')


def comment_rows():
    out = []
    for ft, name, first in COMMENT_TYPES:
        cid = 'type-' + (ft.replace('+', 'p') if ft != 'unknown' else 'default')
        out.append(row(cid, f'Comment out the first line of {name} with Alt+/.', first + '\nsecond\n',
                       [key('Alt+/')], [f(f'The line is commented with the {ft} comment syntax.')], save=True,
                       path=f'cm-{name}'))
    return out


COMMENT = comment_rows() + [
    row('ctrl-underscore', 'Comment line 1 of a Go file with Control+_.', 'package main\nfunc f() {}\n',
        [key('Control+_')], [f('Control+_ (Control+/) comments the line.')], save=True, path='cm-ctrl.go'),
    row('command', 'Run the comment command on line 2 of a Go file.', 'package main\nfunc f() {}\n',
        [at(2, 1), cmd('comment')], [f('The comment command comments the line.')], save=True, path='cm-cmd.go'),
    row('uncomment', 'Press Alt+/ on a commented Go line.', '// func f() {}\nx\n', [key('Alt+/')],
        [f('A commented line is uncommented.')], save=True, path='cm-un.go'),
    row('uncomment-nospace', 'Press Alt+/ on "//x := 1" in a Go file.', '//x := 1\n', [key('Alt+/')],
        [f('A comment without a space is recognised too.')], save=True, path='cm-nosp.go'),
    row('indented', 'Comment an indented Python line.', 'def f():\n    return 1\n', [at(2, 1), key('Alt+/')],
        [f('The comment marker goes after the indentation.')], save=True, path='cm-ind.py'),
    row('cursor', 'Comment line 1 of a Go file with the cursor at column 5.', 'package main\n', [at(1, 5), key('Alt+/')],
        [('pos', 'The cursor moves with the text.', 'pos')], path='cm-cur.go'),
    row('selection', 'Select lines 1-3 of a Python file and press Alt+/.',
        'def f():\n    x = 1\n    return x\nprint(f())\n', [keys('Shift+Down', 'Shift+Down', 'Shift+Down'),
                                                         key('Alt+/')],
        [f('All selected lines are commented at the smallest indentation.')], save=True, path='cm-sel.py'),
    row('selection-uncomment', 'Select two commented lines and press Alt+/.', '# a\n# b\nc\n',
        [keys('Shift+Down', 'Shift+Down'), key('Alt+/')], [f('A fully commented selection is uncommented.')],
        save=True, path='cm-selun.py'),
    row('selection-mixed', 'Select a commented and an uncommented line and press Alt+/.', '# a\nb\nc\n',
        [keys('Shift+Down', 'Shift+Down'), key('Alt+/')],
        [f('A partly commented selection is commented again as a whole.')], save=True, path='cm-mixed.py'),
    row('selection-partial-end', 'Select from line 1 to the start of line 3 and press Alt+/.', 'a\nb\nc\n',
        [keys('Shift+Down', 'Shift+Down'), key('Alt+/')], [f('A selection ending at a line start excludes that line.')],
        save=True, path='cm-pend.py'),
    row('html-uncomment', 'Press Alt+/ twice on an HTML line.', '<p>x</p>\n', [key('Alt+/'), key('Alt+/')],
        [f('Commenting twice restores the line.')], save=True, path='cm-twice.html', req={'file': ['type-html/file']}),
    row('comment-type', 'Run setlocal comment.type "REM %s" and comment the line.', 'echo hi\n',
        [cmd('setlocal comment.type "REM %s"'), key('Alt+/')], [f('comment.type overrides the syntax.')], save=True,
        path='cm-type.txt'),
]

AUTOCLOSE = [
    row('paren', 'Type "(".', 'x\n', [key('End'), typ('(')], [f('The closing parenthesis is inserted.'),
                                                              ('pos', 'The cursor is between the pair.', 'pos')],
        save=True),
    row('pairs', 'Type "[", "{", a double quote, a single quote and a backquote, each at the end of a line.', 'a\nb\nc\nd\ne\n',
        [key('End'), typ('['), key('Down'), key('End'), typ('{'), key('Down'), key('End'), typ('"'), key('Down'),
         key('End'), typ("'"), key('Down'), key('End'), typ('`')],
        [f('Each opening character gets its closing partner.')], save=True),
    row('skip-close', 'Type "(" and then ")".', 'x\n', [key('End'), typ('()')],
        [f('Typing the closing character steps over the inserted one.')], save=True),
    row('before-word', 'Type "(" before a word.', 'word\n', [typ('(')],
        [f('Before a word character no partner is inserted.')], save=True),
    row('quote-after-word', 'Type a double quote right after a word.', 'word\n', [key('End'), typ('"')],
        [f('After a word character a quote is not doubled.')], save=True),
    row('backspace-pair', 'Type "(" and press Backspace.', 'x\n', [key('End'), typ('('), key('Backspace')],
        [f('Backspace between an empty pair deletes both.')], save=True, req={'file': ['paren/file']}),
    row('enter-braces', 'Type "{" and press Enter.', 'f()\n', [key('End'), typ(' {'), key('Enter')],
        [f('Enter between braces opens an indented line and puts the closing brace below.'),
         ('pos', 'The cursor is on the indented middle line.', 'pos')], save=True),
    row('enter-indented', 'Type "[" and Enter on an indented line.', '    x = \n', [key('End'), typ('['),
                                                                            key('Enter')],
        [f('The new lines keep the base indentation plus one level.')], save=True),
    row('off', 'Run set autoclose off and type "(".', 'x\n', [cmd('set autoclose off'), key('End'), typ('(')],
        [f('Without the plugin no partner is inserted.')], save=True, req={'file': ['paren/file']}),
    row('paste-no-close', 'Paste "(" through the terminal.', 'x\n', [key('End'), {'paste': '('}],
        [f('A pasted bracket is not closed.')], save=True),
]

FTOPTIONS = [
    row('python-spaces', 'Press Tab at the start of a Python line.', 'x = 1\n', [key('Tab')],
        [f('Python files indent with spaces.')], save=True, path='ft-a.py'),
    row('yaml-spaces', 'Press Tab at the start of a YAML line.', 'a: 1\n', [key('Tab')],
        [f('YAML files indent with spaces.')], save=True, path='ft-b.yaml'),
    row('go-tabs', 'With tabstospaces on, press Tab in a Go file.', 'package main\n', [key('Tab')],
        [f('Go files keep tabs.')], save=True, path='ft-c.go', settings={'tabstospaces': True}),
    row('make-tabs', 'With tabstospaces on, press Tab in a Makefile.', 'all:\n', [key('Down'), key('Tab')],
        [f('Makefiles keep tabs.')], save=True, path='ft-d/Makefile', settings={'tabstospaces': True}),
    row('text-tabs', 'Press Tab in a text file.', 'x\n', [key('Tab')], [f('Other files use tabs by default.')],
        save=True, path='ft-e.txt'),
    row('off', 'With ftoptions off, press Tab at the start of a Python line.', 'x = 1\n', [key('Tab')],
        [f('Without ftoptions Python files use tabs too.')], save=True, path='ft-f.py',
        settings={'ftoptions': False}, req={'file': ['python-spaces/file']}),
    row('show', 'Run show tabstospaces in a Python file.', 'x = 1\n', [cmd('show tabstospaces')],
        [('msg', 'The buffer reports tabstospaces true.', 'msg')], path='ft-g.py'),
]

DIFF = [
    row('modified', 'With diffgutter on, change line 2.', 'one\ntwo\nthree\n', [at(2, 1), typ('X'), wait(1)],
        [('rows', 'Line 2 gets a change marker in the gutter.', rows(0, 3))], settings={'diffgutter': True}),
    row('added', 'With diffgutter on, add a line after line 1.', 'one\ntwo\nthree\n',
        [key('End'), key('Enter'), typ('new'), wait(1)],
        [('rows', 'The new line gets a marker in the gutter.', rows(0, 4))], settings={'diffgutter': True}),
    row('deleted', 'With diffgutter on, delete line 2.', 'one\ntwo\nthree\n', [at(2, 1), key('Control+K'), wait(1)],
        [('rows', 'A deletion marker is shown where the line was.', rows(0, 3))], settings={'diffgutter': True}),
    row('saved-base', 'With diffgutter on, change line 2, save, then change line 3.', 'one\ntwo\nthree\n',
        [at(2, 1), typ('X'), key('Control+S'), key('Down'), typ('Y'), wait(1)],
        [('rows', 'The diff base is the text when the file was opened, not when it was saved.', rows(0, 3))],
        settings={'diffgutter': True}),
    row('diff-next', 'With diffgutter on, change lines 2 and 5, go to the start and press Alt+].',
        'a\nb\nc\nd\ne\nf\n', [at(2, 1), typ('X'), key('Control+Home'), at(5, 1), typ('Y'), wait(1),
                                   key('Control+Home'), key('Alt+]')],
        [('pos', 'Alt+] jumps to the next block of changes.', 'pos')], settings={'diffgutter': True}),
]


def episodes():
    return (family('plug-comment', 'plugins', COMMENT, 13) + family('plug-autoclose', 'plugins', AUTOCLOSE, 10)
            + family('plug-ftoptions', 'plugins', FTOPTIONS, 7) + family('plug-diff', 'display', DIFF, 5))
