'''Episode specifications for files, navigation, stash, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
TOPIC = S(H2, git('branch', 'topic'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
NESTED = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
TAGGED = S(H3, git('tag', 'v1'))


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-jump-to-oldest', 'navigation', H3, 'Select the oldest commit in the commits list.',
             K('4', '>'),
             [('selected', 'The oldest commit, first, is selected.', pan(4, 'selected')),
              ('same', 'The repository is unchanged.', repo('status', 'log'))],
             'The commits panel has the oldest commit first selected.', bind={'same': ['selected']}),
        goal('gui-collapse-all', 'files', NESTED, 'Collapse every directory of the files panel.',
             K('2', '-'),
             [('items', 'The files panel shows the root entry collapsed.', pan(2)),
              ('same', 'The repository is unchanged.', repo('status'))],
             ['The files panel shows the root entry as collapsed.', 'The files panel lists no file or directory below the root entry.'], bind={'same': ['items']}),
        goal('gui-stash-files', 'stash', STASHED, 'Open the files of the stash wip.',
             K('5', 'Enter'),
             [('hints', 'The key hints offer to check out a file, to toggle a file in the patch and to leave the subview.', scr('hints')),
              ('diff', 'The main view shows the diff of the stashed change to c1.txt.', scr('main', lines=8)),
              ('same', 'The repository is unchanged: the stash is kept.', repo('stash', 'status'))],
             'The right view shows the diff of c1.txt that adds the line x.',
             bind={'diff': ['hints'], 'same': ['hints']}),
        goal('gui-tag-commits', 'tags', TAGGED, 'Open the commits of the tag v1.',
             K('3', ']', ']', 'Enter'),
             [('hints', 'The key hints offer to check out, reset or copy a commit and to leave the subview.', scr('hints')),
              ('first', 'The main view shows the commit the tag names, tagged v1.', scr('main', lines=1)),
              ('same', 'The repository is unchanged.', repo('status', 'log', 'tags'))],
             'The right view shows the commit third with the tag v1.', bind={'first': ['hints'], 'same': ['hints']}),
    ]
