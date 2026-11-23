'''Episode specifications for commits, rebase, sync. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
FEATURE = S(commit('base', {'b.txt': text('base')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), commit('f-two', {'f2.txt': text('two')}),
            commit('f-three', {'f3.txt': text('three')}))
CONFLICT = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'),
             commit('feat change', {'f.txt': text('a', 'feature side')}), git('checkout', '-q', 'main'),
             commit('main change', {'f.txt': text('a', 'main side')}))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))
IGN = S(H2, put({'new.txt': text('new')}))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')
TODO = S(K('4', 'i'), wait(2))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []



    W.append(program('rebase-todo-keys', 'rebase', None, [
        cp('options-menu', 'Open the rebase options menu during an interactive rebase.', FEATURE,
           S(TODO, K('m'), wait(0.5)),
           [('popup', 'The menu offers to continue, abort or skip.', scr('popup')),
            ('status', 'The rebase is still in progress.', gitc(*STATUSB))],
           requires={'status': ['popup']}),
    ]))

    W.append(program('rebase-abort', 'rebase', None, [
        cp('start', 'Start an interactive rebase.', FEATURE, TODO,
           [('head', 'HEAD sits on the base commit.', repo('head'))]),
        step('abort', 'Abort the rebase from the rebase options menu.', S(K('m', 'a'), wait(2)),
             [('status', 'The branch feature is checked out again and no rebase is in progress.', gitc(*STATUSB)),
              ('log', 'All three commits of the branch are back.', repo('head', 'log'))],
             depends=['start']),
    ]))

    W.append(program('commit-files', 'commits', None, [
        cp('discard-file', 'Discard the file c2.txt from the second commit in the commit files view and confirm.', H3,
           S(K('4', 'j', 'Enter', 'd', 'Enter'), wait(2)),
           [('files', 'The file is gone from the tree.', gitc(*FILES)),
            ('log', 'The history keeps its three commits.', repo('log'))], requires={'log': ['files']}),
        cp('patch-remove', 'Add c2.txt of the second commit to a custom patch and remove the patch from that commit.', H3,
           S(K('4', 'j', 'Enter', 'Space', 'Escape', 'Control+P', 'd', 'Enter'), wait(2)),
           [('files', 'The file is gone from the tree.', gitc(*FILES)),
            ('log', 'The history keeps its three commits.', repo('log'))], requires={'log': ['files']}),
        cp('patch-to-index', 'Add c3.txt of the newest commit to a custom patch and move the patch out into the index.', H3,
           S(K('4', 'Enter', 'Space', 'Escape', 'Control+P', 'i'), wait(2)),
           [('status', 'The file is staged for the next commit.', repo('status')),
            ('files', 'The newest commit no longer holds the file.', gitc(*FILES))]),
    ]))

    W.append(program('sync-more', 'sync', None, [
        cp('upstream-reset-menu', 'Open the reset to upstream menu of the files panel.', BEHIND,
           S(K('2', 'g'), wait(0.5)),
           [('popup', 'The menu offers mixed, soft and hard reset to the upstream.', scr('popup')),
            ('status', 'Nothing changed in the repository.', gitc(*STATUSB))],
           requires={'status': ['popup']}),
    ]))

    return W
