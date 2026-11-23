'''Episode specifications for commits. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
TOPIC = S(H2, git('branch', 'topic'))
STATUSB = ('status', '--porcelain', '-b')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []

    W.append(program('commit-moves', 'commits', None, [
        cp('fixup-commit', 'Create a fixup commit for the newest commit from the staged change with the first menu entry.', STAGED,
           S(K('4', 'F', 'Enter'), wait(1)),
           [('log', 'A new commit whose subject starts with fixup! is on top and the tree is clean.', repo('log', 'status')),
            ('files', 'The fixup commit holds the staged change.', gitc('show', '--stat', '--format=%s', 'HEAD'))]),
    ]))

    return W
