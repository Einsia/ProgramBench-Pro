'''Episode specifications for staging. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
BIG = text(*['line %02d' % i for i in range(1, 21)])
BIGM = text(*[('LINE 02' if i == 2 else 'LINE 18' if i == 18 else 'line %02d' % i) for i in range(1, 21)])
HUNKS = S(commit('base', {'big.txt': BIG}), put({'big.txt': BIGM}))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
TOPIC = S(H2, git('branch', 'topic'))
DIVERGED = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'),
             commit('feat change', {'g.txt': text('g')}), git('checkout', '-q', 'main'),
             commit('main change', {'h.txt': text('h')}))
DIVERGED_F = S(DIVERGED, git('checkout', '-q', 'feature'))
CP = S(H2, git('checkout', '-q', '-b', 'feature'), commit('feat', {'f.txt': text('f')}), git('checkout', '-q', 'main'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []

    W.append(program('diff-staging', 'staging', None, [
        cp('hunk-discard', 'Discard the first hunk from the diff view and confirm.', HUNKS,
           K('2', 'Enter', 'd', 'Enter'),
           [('unstaged', 'The first hunk is gone from the working tree; the change to line 18 remains.', gitc('diff')),
            ('cached', 'Nothing is staged.', gitc('diff', '--cached'))],
           requires={'cached': ['unstaged']}),
    ]))




    return W
