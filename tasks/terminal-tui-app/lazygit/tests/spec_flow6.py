'''Episode specifications for branches, files. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
TOPIC = S(H2, git('branch', 'topic'))
MIXED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}), git('add', 'c1.txt'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []

    W.append(program('checkout-by-name', 'branches', None, [
        cp('missing', 'Check out a branch by typing a name that does not exist.', H2, S(K('3', 'c'), prompt('nonesuch'), wait(1)),
           [('popup', 'A confirmation says that the branch was not found and offers to create a new branch with that name.', scr('popup')),
            ('same', 'No branch was created or checked out.', repo('head', 'branches'))],
           requires={'same': ['popup']}),
    ]))

    W.append(program('status-filter-pick', 'files', None, [
        cp('staged', 'Show only the staged files with the first entry of the status filter menu.', MIXED, K('2', 'Control+B', 'Enter'),
           [('panel', 'The files panel lists the staged file c1.txt and not the untracked file new.txt.', pan(2)),
            ('same', 'The repository is unchanged: c1.txt is still staged and new.txt untracked.', repo('status'))],
           requires={'same': ['panel']}),
        cp('unstaged', 'Show only the unstaged files with the second entry of the status filter menu.', MIXED, K('2', 'Control+B', 'j', 'Enter'),
           [('panel', 'The files panel lists the untracked file new.txt and not the fully staged file c1.txt.', pan(2)),
            ('same', 'The repository is unchanged: c1.txt is still staged and new.txt untracked.', repo('status'))],
           requires={'same': ['panel']}),
    ]))

    return W
