'''Episode specifications for branches. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
KEEP = S(H2, put({'c1.txt': text('content 1', 'first', 'a')}), git('add', '.'),
         put({'c1.txt': text('content 1', 'first', 'a', 'b')}))
BISECT = S(K('4', 'b', 'b'), wait(1))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []


    W.append(program('merge-remote-menu', 'branches', None, [
        popup_cp('menu', 'Open the merge menu for a remote branch that main can fast-forward to.', REMBR,
                 K('3', ']', 'Enter', 'j', 'M'),
                 'A menu offers a regular merge that fast-forwards, a merge with a merge commit and two squash merges, and explains the fast-forward.',
                 repo('status', 'log')),
    ]))

    return W
