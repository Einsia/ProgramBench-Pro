'''Episode specifications for branches, commits, discard, files, reflog, remotes, staging, worktrees. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
MANY = S(commit('b-base', {'b.txt': text('base')}), git('branch', 'b1'), git('branch', 'b2'), git('branch', 'b3'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
WT = S(H2, git('worktree', 'add', '-q', '../wtx', '-b', 'wt-branch'))
FEATMAIN = S(commit('base', {'b.txt': text('base')}), git('checkout', '-q', '-b', 'feature'),
             commit('f-one', {'f1.txt': text('one')}), commit('f-two', {'f2.txt': text('two')}),
             commit('f-three', {'f3.txt': text('three')}), git('checkout', '-q', 'main'))
TWO = S(H2, put({'c1.txt': text('content 1', 'first', 'x'), 'c2.txt': text('content 2', 'second', 'y')}))
EDITED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}))
NESTED = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
TAGGED = S(H3, git('tag', 'v1'))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')
REMOTES = ('for-each-ref', '--format=%(refname:short)', 'refs/remotes')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('branch-more', 'branches', None, [
        cp('from-remote', 'Create a local branch from the remote branch remote-only by typing local-copy after the suggested name.', REMBR,
           S(K('3', ']', 'Enter', 'j', 'n'), prompt('local-copy'), wait(1)),
           [('head', 'The checked-out branch is remote-onlylocal-copy.', repo('head', 'branches')),
            ('log', 'The history is unchanged.', repo('log'))],
           requires={'log': ['head']}),
    ]))

    W.append(program('remote-popups', 'remotes', None, [
        popup_cp('delete-remote-branch', 'Ask to delete the remote branch remote-only from the remote origin.', REMBR,
                 K('3', ']', 'Enter', 'j', 'd'),
                 'A confirmation asks whether to delete the remote branch remote-only from origin.', gitc(*REMOTES)),
        popup_cp('remove-remote', 'Ask to remove the remote origin.', PUSHED, K('3', ']', 'd'),
                 'A confirmation asks whether to remove the remote origin.', gitc('remote', '-v')),
    ]))

    W.append(program('worktree-popups', 'worktrees', None, [
        popup_cp('remove', 'Ask to remove the worktree wtx from the worktrees tab.', WT, K('2', ']', 'j', 'd'),
                 'A menu offers to remove the worktree, the worktree and its branch, or the worktree and its local and remote branch.',
                 gitc('worktree', 'list')),
    ]))

    W.append(program('staging-range', 'staging', None, [
        cp('stage-range', 'Select both changed files as a range and stage them.', TWO, K('2', 'j', 'v', 'j', 'Space'),
           [('status', 'Both files are staged.', repo('status'))]),
    ]))

    W.append(program('commit-edits', 'commits', None, [
        cp('cherry-pick-range', 'Copy the two newest commits of the branch feature and paste them onto main.', FEATMAIN,
           S(K('3', 'j', 'Enter', 'v', 'j', 'C', 'Escape', '4', 'V', 'Enter'), wait(2)),
           [('log', 'main holds copies of the two commits on top of base.', repo('head', 'log')),
            ('files', 'Only the files of those two commits were added.', gitc(*FILES)),
            ('feature', 'The branch feature still has its three commits.', gitc('log', '--format=%s', 'feature'))],
           requires={'feature': ['log']}),
        cp('reword-oldest', 'Reword the oldest commit to redone first.', H3,
           S(K('4', 'j', 'j', 'r', 'Control+U'), prompt('redone first'), wait(2)),
           [('log', 'The oldest commit has the new subject and the other two are unchanged.', repo('log'))]),
        cp('move-oldest', 'Move the oldest commit one place up.', H3, S(K('4', 'j', 'j', 'Control+K'), wait(2)),
           [('log', 'The oldest commit is now the middle one.', repo('log'))]),
    ]))

    W.append(program('reflog-reset', 'reflog', None, [
        cp('reset-hard', 'Hard reset to the second entry of the reflog.', H3, S(K('4', ']', 'j', 'g', 'h', 'Enter'), wait(1)),
           [('log', 'main points at the second commit again.', repo('head', 'log')),
            ('status', 'The working tree is clean.', repo('status'))],
           requires={'status': ['log']}),
    ]))


    W.append(program('discard-dir', 'discard', None, [
        popup_cp('menu', 'Open the discard menu for the untracked directory d.', NESTED, K('2', 'j', 'd'),
                 'A menu offers to discard all changes or only the unstaged ones of the directory.', repo('status')),
    ]))

    W.append(program('amend-popup', 'files', None, [
        popup_cp('confirm', 'Ask to amend the newest commit from the files panel when there is only an unstaged change.', EDITED, K('2', 'A'),
                 'A confirmation asks whether to amend the last commit and says that the message can be changed afterwards from the commits panel.', repo('status', 'log')),
        popup_cp('no-staged', 'Confirm the amend of the newest commit when nothing is staged.', EDITED,
                 S(K('2', 'A'), wait(0.5), K('Enter'), wait(1)),
                 'A confirmation says that no files are staged and asks whether to commit all files.', repo('status', 'log')),
    ]))
    return W
