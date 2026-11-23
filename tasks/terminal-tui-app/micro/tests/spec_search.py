"""Finding and replacing: the find prompt (regular expressions and literal search, incremental search, find next and
previous with wrap-around, prefilled selections, history) and the replace and replaceall commands (interactive
answers, flags, templates, selections, messages).
"""
from spec_common import (at, cmd, differ, family, file, key, keys, message, pos, row, rows, snap, status, typ)

TEXT = ('alpha beta gamma\nsecond line 42\nthird line\nfourth a.b axb\nfoo FOO Foo foobar\n'
        'mail: ann@host and bob@site\nprice $5 and $7\n')


def p(requirement, snapshot=None):
    return ('pos', requirement, pos(snapshot) if snapshot else 'pos')


def m(requirement, snapshot=None):
    return ('msg', requirement, message(snapshot) if snapshot else 'msg')


def f(requirement):
    return ('file', requirement, 'file')


def find(pattern, *more):
    return [key('Control+F'), typ(pattern), key('Enter')] + list(more)


FIND = [
    row('basic', 'Find "line".', TEXT, find('line'), [p('The cursor ends after the first match.')]),
    row('selects', 'Find "line" and type #.', TEXT, find('line', typ('#')),
        [f('The match is selected, so typing replaces it.')], save=True),
    row('regex-dot', 'Find "s.c".', TEXT, find('s.c'), [p('. matches any character.')]),
    row('regex-class', 'Find "[0-9]+".', TEXT, find('[0-9]+', typ('#')), [f('A character class with + matches 42.')],
        save=True),
    row('regex-anchor-start', 'Find "^t".', TEXT, find('^t'), [p('^ anchors at a line start.')]),
    row('regex-anchor-end', 'Find "ne$".', TEXT, find('ne$'), [p('$ anchors at a line end.')]),
    row('regex-alternation', 'Find "gamma|second".', TEXT, find('gamma|second', typ('#')),
        [f('Alternation matches the first alternative found.')], save=True),
    row('regex-word', 'Find "\\bfoo\\b" after moving to line 5 column 2.', TEXT, [at(5, 2)] + find('\\bfoo\\b', typ('#')),
        [f('Word boundaries skip foobar... and the search starts at the cursor.')], save=True),
    row('regex-escape', 'Find "a\\.b".', TEXT, find('a\\.b', typ('#')), [f('An escaped dot matches only a dot.')],
        save=True),
    row('regex-literal-dot', 'Find "a.b" as a regular expression from line 4 column 9.', TEXT,
        [at(4, 9)] + find('a.b', typ('#')), [f('Unescaped, a.b also matches axb.')], save=True),
    row('literal', 'Press Alt+Shift+F and find "a.b" literally from line 4 column 9.', TEXT,
        [at(4, 9), key('Alt+F'), typ('a.b'), key('Enter'), typ('#')],
        [f('Literal search only matches a.b itself (wrapping around).')], save=True),
    row('literal-prompt', 'Press Alt+Shift+F.', TEXT, [key('Alt+F')], [m('The literal find prompt has its own label.')]),
    row('prompt', 'Press Control+F.', TEXT, [key('Control+F')], [m('The find prompt says it takes a regex.')]),
    row('f3', 'Press F3.', TEXT, [key('F3')], [m('F3 opens the find prompt too.')]),
    row('f7', 'Press F7.', TEXT, [key('F7')], [m('F7 opens the find prompt too.')]),
    row('ignorecase', 'Find "FOO" from the start.', TEXT, find('FOO', typ('#')),
        [f('By default the search ignores case and finds the first foo.')], save=True),
    row('no-match', 'Find "zzz" from line 2 column 3.', TEXT, [at(2, 3)] + find('zzz'),
        [m('No match is reported.'), p('The cursor stays.')], req={'pos': ['no-match/msg']}),
    row('wrap', 'From the last line, find "alpha".', TEXT, [key('Control+End')] + find('alpha'),
        [p('The search wraps around to the top.')]),
    row('next', 'Find "line", then press Control+N.', TEXT, find('line', key('Control+N')),
        [p('Control+N moves to the next match.')]),
    row('next-wrap', 'Find "line", then press Control+N twice.', TEXT, find('line', key('Control+N'),
                                                                             key('Control+N')),
        [p('After the last match Control+N wraps to the first.')]),
    row('prev', 'Find "line", then press Control+P.', TEXT, find('line', key('Control+P')),
        [p('Control+P moves to the previous match, wrapping backwards.')]),
    row('prev-twice', 'Find "line", then press Control+P twice.', TEXT, find('line', key('Control+P'),
                                                                              key('Control+P')),
        [p('Control+P keeps going backwards.')]),
    row('next-no-search', 'Press Control+N without a previous search.', TEXT, [at(2, 3), key('Control+N')],
        [p('Without a previous search Control+N does nothing.')], req={'pos': ['next/pos']}),
    row('prefill', 'Select "a.b" and press Control+F.', TEXT,
        [at(4, 8), keys('Shift+Right', 'Shift+Right', 'Shift+Right'), key('Control+F')],
        [m('The prompt is prefilled with the selection, escaped for a regex.')]),
    row('prefill-literal', 'Select "a.b" and press Alt+Shift+F.', TEXT,
        [at(4, 8), keys('Shift+Right', 'Shift+Right', 'Shift+Right'), key('Alt+F')],
        [m('The literal prompt is prefilled with the selection as it is.')]),
    row('prefill-replace', 'Select "a.b", press Control+F and type x.', TEXT,
        [at(4, 8), keys('Shift+Right', 'Shift+Right', 'Shift+Right'), key('Control+F'), typ('x')],
        [m('The prefilled text is selected, so typing replaces it.')]),
    row('escape', 'Type "third" in the find prompt, then press Escape.', TEXT,
        [at(1, 3), key('Control+F'), typ('third'), key('Escape'), typ('#')],
        [f('Escape cancels: the selection is dropped and # is typed where the incremental search left the cursor.')],
        save=True),
    row('history', 'Find "beta", then press Control+F and Up.', TEXT, find('beta') + [key('Control+F'), key('Up')],
        [m('Up recalls the previous search.')]),
    row('history-down', 'Find "beta" and "third", then press Control+F, Up, Up, Down.', TEXT,
        find('beta') + find('third') + [key('Control+F'), key('Up'), key('Up'), key('Down')],
        [m('Down moves forward in the search history.')]),
    row('unicode', 'Find "é".', 'cafe café\n', find('é', typ('#')), [f('Non-ASCII text is found.')], save=True),
    row('empty-pattern', 'Press Control+F and Enter with an empty pattern.', TEXT, [at(2, 3), key('Control+F'),
                                                                                    key('Enter')],
        [p('An empty search leaves the cursor in place.'), m('...and reports no match.')]),
    row('incremental-none', 'Type "zzz" in the find prompt.', TEXT, [at(2, 3), key('Control+F'), typ('zzz'), snap('t')],
        [p('With no match the cursor goes back to where the search started.', 't')]),
    row('next-after-edit', 'Find "line", type X, then press Control+N.', TEXT,
        find('line', typ('X'), key('Control+N'), typ('#')),
        [f('Control+N searches again after an edit.')], save=True),
]

REPLACE = [
    row('replaceall', 'Run replaceall foo qux.', TEXT, [cmd('replaceall foo qux')],
        [f('Every case-insensitive match is replaced, including inside foobar.'),
         m('The message counts the replacements.')], save=True),
    row('replace-a', 'Run replace foo qux -a.', TEXT, [cmd('replace foo qux -a')],
        [f('-a replaces all matches at once.')], save=True),
    row('replace-flags-first', 'Run replace -a foo qux.', TEXT, [cmd('replace -a foo qux')],
        [f('The flag may come first.')], save=True),
    row('interactive-yny', 'Run replace foo qux and answer y, n, y, then Escape.', TEXT,
        [cmd('replace foo qux'), key('y'), key('n'), key('y'), key('Escape')],
        [f('Only the confirmed matches are replaced.')], save=True),
    row('interactive-prompt', 'Run replace foo qux.', TEXT, [cmd('replace foo qux')],
        [m('micro asks about each match.'), p('The cursor is at the first match.')]),
    row('interactive-esc', 'Run replace foo qux and press Escape.', TEXT, [cmd('replace foo qux'), key('Escape')],
        [f('Escape replaces nothing.')], save=True, req={'file': ['interactive-yny/file']}),
    row('interactive-all-yes', 'Run replace beta delta2 and answer y.', TEXT, [cmd('replace beta delta2'), key('y')],
        [f('The single match is replaced.'), m('After the last match the replace prompt closes by itself.')], save=True,
        req={'msg': ['interactive-all-yes/file']}),
    row('interactive-from-cursor', 'From line 5 column 9, run replace foo qux and answer y twice.', TEXT,
        [at(5, 9), cmd('replace foo qux'), key('y'), key('y'), key('Escape')],
        [f('Interactive replace starts at the cursor.')], save=True),
    row('literal', 'Run replaceall a.b X -l.', TEXT, [cmd('replace a.b X -l -a')],
        [f('-l matches the text literally.')], save=True),
    row('regex', 'Run replaceall a.b X.', TEXT, [cmd('replaceall a.b X')],
        [f('Without -l the pattern is a regular expression.')], save=True),
    row('groups', 'Run replaceall "(\\w+)@(\\w+)" "$2 at $1".', TEXT, [cmd('replaceall "(\\w+)@(\\w+)" "$2 at $1"')],
        [f('$1 and $2 insert the captured groups.')], save=True),
    row('named-groups', 'Run replaceall "(?P<n>[0-9]+)" "<${n}>".', TEXT,
        [cmd('replaceall "(?P<n>[0-9]+)" "<${n}>"')], [f('${name} inserts a named group.')], save=True),
    row('dollar', 'Run replaceall "[0-9]" "$$".', TEXT, [cmd('replaceall "[0-9]" "$$"')],
        [f('$$ inserts a literal dollar sign.')], save=True),
    row('literal-template', 'Run replace "(\\w+)@" "$1#" -l -a.', TEXT, [cmd('replace "(\\w+)@" "$1#" -l -a')],
        [f('With -l nothing matches the literal pattern.'), m('The message says nothing matched.')], save=True,
        req={'file': ['literal-template/msg']}),
    row('line-start', 'Run replaceall "^" "> ".', TEXT, [cmd('replaceall "^" "> "')],
        [f('^ inserts at the start of every line.')], save=True),
    row('line-end', 'Run replaceall "$" ";".', TEXT, [cmd('replaceall "$" ";"')],
        [f('$ inserts at the end of every line.')], save=True),
    row('empty-replacement', 'Run replaceall "a" "".', TEXT, [cmd('replaceall "a" ""')],
        [f('An empty replacement deletes the matches.')], save=True),
    row('quoted', 'Run replaceall "second line" "2nd row".', TEXT, [cmd('replaceall "second line" "2nd row"')],
        [f('Quoted arguments may contain spaces.')], save=True),
    row('selection', 'Select lines 2-3 and run replaceall line ROW.', TEXT,
        [at(2, 1), keys('Shift+Down', 'Shift+Down'), cmd('replaceall line ROW')],
        [f('Only matches inside the selection are replaced.'), m('The message says it was in the selection.')],
        save=True),
    row('case-sensitive', 'With ignorecase off, run replaceall foo qux.', TEXT, [cmd('replaceall foo qux')],
        [f('Only exact-case matches are replaced.')], save=True, settings={'ignorecase': False}),
    row('nothing', 'Run replaceall xyz q.', TEXT, [cmd('replaceall xyz q')],
        [m('The message says nothing matched.')]),
    row('one', 'Run replaceall gamma G.', TEXT, [cmd('replaceall gamma G')],
        [m('The message reports one occurrence.')]),
    row('bad-regex', 'Run replaceall "(" x.', TEXT, [cmd('replaceall "(" x')],
        [('msg', 'An invalid regular expression is reported.', message(reported=True))]),
    row('too-few', 'Run replace foo.', TEXT, [cmd('replace foo')], [m('replace needs a replacement.')]),
    row('too-many', 'Run replace a b c.', TEXT, [cmd('replace a b c')], [m('An extra argument is reported.')]),
    row('undo', 'Run replaceall foo qux, then press Control+Z.', TEXT, [cmd('replaceall foo qux'), key('Control+Z')],
        [f('One undo restores all replacements.')], save=True, req={'file': ['replaceall/file']}),
    row('unicode', 'Run replaceall é E.', 'café résumé\n', [cmd('replaceall é E')],
        [f('Non-ASCII matches are replaced.')], save=True),
    row('expand-match', 'Run replaceall "o+" "0".', 'foo boo zoooom\n', [cmd('replaceall "o+" "0"')],
        [f('Each run of the pattern is replaced once.')], save=True),
]


def episodes():
    return family('find', 'search', FIND, 12) + family('replace', 'search', REPLACE, 12)
