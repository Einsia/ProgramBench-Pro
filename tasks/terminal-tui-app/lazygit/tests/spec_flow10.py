'''Episode specifications for commits, rebase, search. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
MANY = S(commit('b-base', {'b.txt': text('base')}), git('branch', 'b1'), git('branch', 'b2'), git('branch', 'b3'))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
DIVERGE = S(commit('base', {'f.txt': text('a')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), git('checkout', '-q', 'main'), commit('m-one', {'m1.txt': text('one')}))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('filter-panels', 'search', None, [
        cp('branches', 'Filter the branches panel by the text b2.', MANY, S(K('3', '/'), prompt('b2')),
           [('hints', 'The bottom line says that the list is filtered by b2 and offers to exit the filter mode.', scr('hints')),
            ('items', 'The branches panel lists only the branches that match b2.', pan(3)),
            ('same', 'The repository is unchanged.', repo('head', 'branches'))],
           requires={'items': ['hints'], 'same': ['hints']}),
        cp('stash', 'Filter the stash panel by the text wip.', STASHED, S(K('5', '/'), prompt('wip')),
           [('hints', 'The bottom line says that the list is filtered by wip and offers to exit the filter mode.', scr('hints')),
            ('items', 'The stash panel lists the stash that matches wip.', pan(5)),
            ('same', 'The repository is unchanged: the stash is kept.', repo('stash', 'status'))],
           requires={'items': ['hints'], 'same': ['hints']}),
    ]))

    W.append(program('revert-commit', 'commits', None, [
        popup_cp('prompt', 'Ask to revert the newest commit.', H3, K('4', 't'),
                 'A confirmation asks whether to revert the commit and names its short hash.', repo('status', 'log')),
    ]))

    W.append(program('rebase-branch', 'rebase', None, [
        popup_cp('menu', 'Open the rebase menu for the branch feature while main is checked out.', DIVERGE, K('3', 'j', 'r'),
                 'A menu offers a simple rebase and an interactive rebase onto feature and a rebase onto the base branch.', repo('status', 'log')),
    ]))

    return W
