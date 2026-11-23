'''Episode specifications for sync. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
TOPIC = S(H2, git('branch', 'topic'))
TAGGED = S(H3, git('tag', 'v1'))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
NOUP = S(H2, ORIGIN)
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
AHEAD = S(PUSHED, commit('ahead', {'a.txt': text('a')}))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []




    W.append(program('sync', 'sync', None, [
        cp('push-upstream', 'Push main to its upstream.', AHEAD, S(K('P'), wait(3)),
           [('remote', 'The remote has the new commit.', repo('log', remote='origin')),
            ('local', 'The local history is unchanged.', repo('head', 'log'))],
           requires={'local': ['remote']}),
    ]))
    return W
