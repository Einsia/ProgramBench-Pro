"""Filetype detection (file names, extensions, first-line headers, content signatures for ambiguous extensions) as
shown on the status line, and syntax highlighting as a fact: in a highlighted language, keywords, strings and comments
are drawn differently from plain identifiers (no colour values are compared).
"""
from spec_common import differ, family, row, status

# (case id, file name, content)
DETECT = [
    ('go', 'a.go', 'package main\n'), ('c', 'a.c', 'int x;\n'), ('h-plain', 'plain.h', 'int f(void);\n'),
    ('h-cpp', 'klass.h', 'namespace n { class A; }\n'), ('cpp', 'a.cpp', 'int x;\n'), ('cc', 'a.cc', 'int x;\n'),
    ('hpp', 'a.hpp', 'int x;\n'), ('python', 'a.py', 'x = 1\n'), ('pyw', 'a.pyw', 'x = 1\n'),
    ('python-shebang', 'pyscript', '#!/usr/bin/env python3\nprint(1)\n'),
    ('python2-shebang', 'py2script', '#!/usr/bin/env python2\nprint 1\n'),
    ('shell', 'a.sh', 'echo\n'), ('bashrc', '.bashrc', 'alias l=ls\n'), ('profile', '.profile', 'x=1\n'),
    ('sh-shebang', 'runme', '#!/bin/sh\necho hi\n'), ('bash-shebang', 'runbash', '#!/usr/bin/env bash\necho\n'),
    ('zsh', 'a.zsh', 'x=1\n'), ('zshrc', '.zshrc', 'x=1\n'), ('fish', 'a.fish', 'set x 1\n'),
    ('javascript', 'a.js', 'let x;\n'), ('mjs', 'a.mjs', 'let x;\n'), ('node-shebang', 'nodescript',
                                                                        '#!/usr/bin/env node\nlet x;\n'),
    ('typescript', 'a.ts', 'let x;\n'), ('tsx', 'a.tsx', 'let x;\n'), ('json', 'a.json', '{"a": 1}\n'),
    ('json-header', 'data', '{\n"a": 1\n}\n'), ('yaml', 'a.yml', 'a: 1\n'), ('yaml-header', 'conf', '%YAML 1.2\na: 1\n'),
    ('toml', 'a.toml', 'a = 1\n'), ('ini', 'a.ini', 'a=1\n'), ('desktop', 'app.desktop', '[Desktop Entry]\n'),
    ('markdown', 'a.md', '# T\n'), ('markdown2', 'a.markdown', '# T\n'), ('html', 'a.html', '<p>\n'),
    ('htm', 'a.htm', '<p>\n'), ('xml', 'a.xml', '<a/>\n'), ('svg', 'a.svg', '<svg/>\n'),
    ('xml-header', 'feed', '<?xml version="1.0"?>\n<a/>\n'), ('css', 'a.css', 'p {}\n'), ('scss', 'a.scss', 'p {}\n'),
    ('java', 'A.java', 'class A {}\n'), ('kotlin', 'a.kt', 'val x = 1\n'), ('rust', 'a.rs', 'fn f() {}\n'),
    ('ruby', 'a.rb', 'puts 1\n'), ('gemfile', 'Gemfile', 'gem "x"\n'), ('rakefile', 'Rakefile', 'task :a\n'),
    ('perl', 'a.pl', 'print 1;\n'), ('pm', 'Mod.pm', '1;\n'), ('php', 'a.php', '<?php\n'), ('lua', 'a.lua', 'x=1\n'),
    ('sql', 'a.sql', 'select 1;\n'), ('makefile', 'Makefile', 'all:\n'), ('makefile-lower', 'makefile', 'all:\n'),
    ('mk', 'rules.mk', 'all:\n'), ('cmake', 'CMakeLists.txt', 'project(x)\n'), ('cmake-ext', 'a.cmake', 'set(x)\n'),
    ('dockerfile', 'Dockerfile', 'FROM x\n'), ('dockerfile-suffix', 'Dockerfile.dev', 'FROM x\n'),
    ('containerfile', 'Containerfile', 'FROM x\n'), ('gomod', 'go.mod', 'module x\n'),
    ('git-commit', 'COMMIT_EDITMSG', 'msg\n'), ('gitconfig', '.gitconfig', '[user]\n'),
    ('patch', 'a.patch', 'diff --git a b\n'), ('diff-header', 'changes', 'diff -u a b\n'),
    ('systemd', 'a.service', '[Unit]\n'), ('systemd-header', 'unitfile', '[Unit]\nDescription=x\n'),
    ('nginx', 'nginx.conf', 'server {}\n'), ('tex', 'a.tex', '\\begin{document}\n'), ('bib', 'refs.bib', '@book{}\n'),
    ('haskell', 'a.hs', 'main = 1\n'), ('ocaml', 'a.ml', 'let x = 1\n'), ('swift', 'a.swift', 'let x = 1\n'),
    ('zig', 'a.zig', 'const x = 1;\n'), ('dart', 'a.dart', 'void main() {}\n'), ('scala', 'a.scala', 'val x = 1\n'),
    ('csharp', 'a.cs', 'class A {}\n'), ('vim', '.vimrc', 'set nu\n'), ('log', 'server.log', 'line\n'),
    ('log-txt', 'log.txt', 'line\n'), ('crontab', 'crontab', '* * * * * x\n'), ('r', 'a.R', 'x <- 1\n'),
    ('julia', 'a.jl', 'x = 1\n'), ('nix', 'a.nix', '{ }\n'), ('proto', 'a.proto', 'syntax = "proto3";\n'),
    ('graphql', 'a.graphql', 'type A { x: Int }\n'), ('vue', 'a.vue', '<template></template>\n'),
    ('m-objc', 'objc.m', '#import <Foundation/Foundation.h>\n@interface A : NSObject\n@end\n'),
    ('m-plain', 'plain.m', 'x = 1;\n'), ('fs', 'a.fs', 'let x = 1\n'), ('pp', 'manifest.pp', 'class a {}\n'),
    ('unknown', 'a.unknownext', 'x\n'), ('noext', 'README', 'text\n'), ('micro', 'a.micro', 'color-link default "x"\n'),
    ('lit', 'a.lit', '@code_type python .py\n'),
]


# Results that equal the default filetype only count together with a positive detection.
DEFAULT_LIKE = {'unknown', 'noext', 'lit'}


def detect_rows():
    return [row(cid, f'Open {name} and read its filetype on the status line.', text,
                [], [('ft', f'{name} is detected as its filetype.', status('filetype'))], path=f'det/{name}',
                req={'ft': ['go/ft']} if cid in DEFAULT_LIKE else None)
            for cid, name, text in DETECT]


# Highlighting facts: (case id, file name, content, [(requirement, ((row, col), (row, col)))]) where each pair
# compares a highlighted token with a plain one on the screen (row 0 is the first line; text starts at column 2).
HIGHLIGHT = [
    ('go', 'hl.go', 'package main\nfunc main() {\n\tx := "str" // note\n}\n',
     [('The keyword package is highlighted.', ((0, 2), (0, 10))),
      ('The string is highlighted.', ((2, 12), (2, 6))),
      ('The comment is highlighted.', ((2, 20), (2, 6)))]),
    ('python', 'hl.py', 'def run(x):\n    return "s"  # c\n',
     [('The keyword def is highlighted.', ((0, 2), (0, 10))),
      ('The string is highlighted.', ((1, 14), (0, 10))),
      ('The comment is highlighted.', ((1, 20), (0, 10)))]),
    ('c', 'hl.c', '#include <stdio.h>\nint main(void) { return 0; }\n',
     [('The preprocessor directive is highlighted.', ((0, 2), (1, 7))),
      ('The type int is highlighted.', ((1, 2), (1, 7)))]),
    ('shell', 'hl.sh', 'if true; then\n  x=1 # c\nfi\n',
     [('The keyword if is highlighted.', ((0, 2), (1, 4))),
      ('The comment is highlighted.', ((1, 10), (1, 4)))]),
    ('json', 'hl.json', '{\n  "key": 12,\n  "flag": true\n}\n',
     [('The number is highlighted differently from the key.', ((1, 11), (1, 5))),
      ('The constant true is highlighted.', ((2, 12), (2, 5)))]),
    ('html', 'hl.html', '<p class="a">text</p>\n', [('The tag is highlighted.', ((0, 3), (0, 16)))]),
    ('markdown', 'hl.md', '# Title\nplain *em* text\n', [('The heading is highlighted.', ((0, 4), (1, 3)))]),
    ('yaml', 'hl.yaml', 'key: value\n# comment\n', [('The comment is highlighted.', ((1, 4), (0, 9)))]),
    ('rust', 'hl.rs', 'fn main() {\n    let x = 5;\n}\n', [('The keyword fn is highlighted.', ((0, 2), (0, 6))),
                                                         ('The number is highlighted.', ((1, 14), (1, 10)))]),
    ('javascript', 'hl.js', 'const x = "s"; // c\n', [('The keyword const is highlighted.', ((0, 2), (0, 8))),
                                                       ('The comment is highlighted.', ((0, 20), (0, 8)))]),
]


def highlight_rows():
    out = []
    for cid, name, text, facts in HIGHLIGHT:
        checks = [(f'hl{i + 1}', requirement, differ(pair)) for i, (requirement, pair) in enumerate(facts)]
        out.append(row(f'hl-{cid}', f'Open {name} and look at its highlighting.', text, [], checks,
                       path=f'hl/{name}'))
    return out


# A .h file matches the C, C++ and Objective-C syntax files; a signature (C++ keywords) decides, but only within the
# first detectlimit lines (default 100; 0 means every line).
LATE_SIGNATURE = ''.join(f'// line {i}\n' for i in range(1, 150)) + 'namespace a {}\n'
DETECT_LIMIT = [
    row('limit-default', 'Open a .h file whose first C++ keyword is on line 150.', LATE_SIGNATURE, [],
        [('ft', 'Only the first 100 lines are searched for a signature, so the file is C.', status('filetype'))],
        path='lim-default.h', req={'ft': ['limit-200/ft']}),
    row('limit-200', 'With detectlimit 200, open a .h file whose first C++ keyword is on line 150.', LATE_SIGNATURE,
        [], [('ft', 'With a higher limit the signature is found: C++.', status('filetype'))], path='lim-200.h',
        settings={'detectlimit': 200}),
    row('limit-0', 'With detectlimit 0, open a .h file whose first C++ keyword is on line 150.', LATE_SIGNATURE, [],
        [('ft', 'detectlimit 0 searches every line.', status('filetype'))], path='lim-0.h',
        settings={'detectlimit': 0}),
]


def episodes():
    return (family('filetype', 'filetypes', detect_rows(), 25) + family('syntax', 'filetypes', highlight_rows(), 10)
            + family('filetype-limit', 'filetypes', DETECT_LIMIT, 3))
