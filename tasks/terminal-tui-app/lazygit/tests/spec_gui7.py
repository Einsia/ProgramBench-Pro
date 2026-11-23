'''Episode specifications for bisect, discard. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
KEEP = S(H2, put({'c1.txt': text('content 1', 'first', 'a')}), git('add', '.'),
         put({'c1.txt': text('content 1', 'first', 'a', 'b')}))
BISECT = S(K('4', 'b', 'b'), wait(1))


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-discard-unstaged', 'discard', KEEP,
             'Discard only the unstaged changes of c1.txt, which also has a staged change, and keep the staged change.',
             S(K('2', 'd', 'u'), wait(1)),
             [('status', 'The file is fully staged and has no unstaged change left.', repo('status')),
              ('cached', 'The staged change is still in the index.', gitc('diff', '--cached', '--numstat'))],
             ['The files panel lists c1.txt as staged only, without an unstaged mark.', 'The main view shows only staged changes and no unstaged change.'],
             bind={'cached': ['status']}),
        goal('gui-bisect-skip', 'bisect', H5,
             'Mark the newest commit as bad to start a bisect and then skip the commit that is currently checked.',
             S(BISECT, K('b', 's'), wait(1)),
             [('log', 'The bisect log records that the current commit was skipped.', gitc('bisect', 'log')),
              ('head', 'HEAD stays on the branch.', repo('head'))],
             'The interface shows that a bisect is in progress and the commits panel still lists all five commits.',
             bind={'head': ['log']}),
    ]
