'''Episode specifications for branches, menus, rebase, staging, stash, sync, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
FORCE = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'),
          commit('rewritten', {'r.txt': text('r')}))
FF = S(H2, git('checkout', '-q', '-b', 'feature'), commit('feat', {'f.txt': text('f')}), git('checkout', '-q', 'main'))
FEATURE = S(commit('base', {'b.txt': text('base')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), commit('f-two', {'f2.txt': text('two')}),
            commit('f-three', {'f3.txt': text('three')}))
KEEP = S(H2, put({'c1.txt': text('content 1', 'first', 'a')}), git('add', '.'),
         put({'c1.txt': text('content 1', 'first', 'a', 'b')}))
DELETED = S(H2, git('rm', '-q', 'c1.txt'))
RENAMED = S(H2, git('mv', 'c1.txt', 'moved.txt'))
NESTED = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
TAGGED = S(H3, git('tag', 'v1'))
TAGGED_OLD = S(H3, git('tag', 'v1', 'HEAD~1'))
TOPIC = S(H2, git('branch', 'topic'))
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

    W.append(program('force-push', 'sync', None, [
        cp('diverged', 'Push main after the local branch was rewritten, so that it has diverged from its upstream.', FORCE,
           S(K('P'), wait(3)),
           [('popup', 'A confirmation says that the branch has diverged and offers a force push.', scr('popup')),
            ('status', 'Nothing was pushed: the branch is one commit ahead and one behind its upstream.', gitc(*STATUSB)),
            ('remote', 'The remote still holds the old third commit.', repo('log', remote='origin'))],
           requires={'status': ['popup'], 'remote': ['popup']}),
    ]))

    W.append(program('merge-variants', 'branches', None, [
        cp('merge-commit', 'Merge feature into main with a merge commit although a fast-forward is possible.', FF,
           S(K('3', 'j', 'M', 'n'), wait(1)),
           [('log', 'A merge commit with two parents is on top of main.', repo('head', 'log')),
            ('files', 'The feature file is in the tree.', gitc(*FILES))]),
        cp('squash-leave', 'Squash merge feature into main and leave the result uncommitted.', FF,
           S(K('3', 'j', 'M', 's'), wait(1)),
           [('status', 'The feature file is staged.', repo('status')),
            ('log', 'No commit was created.', repo('head', 'log'))],
           requires={'log': ['status']}),
    ]))

    W.append(program('mark-base', 'rebase', None, [
        cp('mark', 'Mark the newest commit as the base commit for the next rebase.', FEATURE, K('4', 'B'),
           [('banner', 'The bottom line says that a base commit is marked for rebase.', scr('banner')),
            ('log', 'The history is unchanged.', repo('head', 'log'))],
           requires={'log': ['banner']}),
    ]))

    W.append(program('staging-kinds', 'staging', None, [
        cp('stage-all', 'Stage all changes when a file has both a staged and an unstaged change.', KEEP, K('2', 'a'),
           [('status', 'The file is fully staged.', repo('status'))]),
        cp('toggle-all', 'Press the stage all key twice.', KEEP, K('2', 'a', 'a'),
           [('status', 'Nothing is staged after the second press.', repo('status'))]),
        cp('collapse-dir', 'Collapse the directory d with the enter key.', NESTED, K('2', 'j', 'Enter'),
           [('items', 'The files panel lists the directory d collapsed and top.txt.', pan(2)),
            ('status', 'The repository is unchanged.', repo('status'))],
           requires={'status': ['items']}),
        cp('unstage-delete', 'Unstage the staged deletion of c1.txt.', DELETED, K('2', 'j', 'Space'),
           [('status', 'The deletion is unstaged and the file is still missing.', repo('status'))]),
        cp('unstage-rename', 'Unstage the staged rename of c1.txt to moved.txt.', RENAMED, K('2', 'j', 'Space'),
           [('status', 'Only the new path is unstaged: the old file stays deleted and staged.', repo('status'))]),
    ]))

    W.append(program('stash-variants', 'stash', None, [
        cp('unstaged', 'Stash only the unstaged changes under the name unst.', KEEP,
           S(K('2', 'S', 'u'), prompt('unst'), wait(1)),
           [('stash', 'One stash named unst exists.', repo('stash')),
            ('status', 'Only the staged change is left.', repo('status'))]),
    ]))

    W.append(program('tags-force', 'tags', None, [
        popup_cp('exists', 'Create a tag named v1 on the newest commit when v1 already exists.', TAGGED,
                 S(K('4', 'T'), prompt('v1'), wait(1)),
                 'A confirmation says that the tag exists already and offers to overwrite it.', repo('tags')),
        cp('overwrite', 'Move the existing tag v1 from the second commit to the newest commit and confirm.', TAGGED_OLD,
           S(K('4', 'T'), prompt('v1'), wait(1), K('Enter'), wait(1)),
           [('tags', 'The tag v1 exists once.', repo('tags'))]),
    ]))

    W.append(program('menu-popups-2', 'menus', None, [
        popup_cp('branch-reset', 'Open the reset menu of the branches panel.', H3, K('3', 'g'),
                 'A menu offers mixed, soft and hard reset to the selected branch.', repo('status', 'log')),
        popup_cp('worktree-branch', 'Open the new worktree menu for the branch topic.', TOPIC, K('3', 'j', 'w'),
                 'A menu offers a worktree with a new branch, for the branch itself or detached.', repo('status', 'log')),
        popup_cp('discard-staged', 'Open the discard menu for the file with staged and unstaged changes.', KEEP,
                 K('2', 'j', 'd'), 'A menu offers to discard all changes or only the unstaged ones.', repo('status', 'log')),
        cp('undo', 'Drop the newest commit and then ask to undo it.', H3,
           S(K('4', 'd', 'Enter'), wait(1), K('z'), wait(0.5)),
           [('popup', 'A confirmation asks whether to hard reset to the previous head.', scr('popup')),
            ('log', 'The commit is still dropped while the confirmation is open.', repo('log'))],
           requires={'log': ['popup']}),
    ]))
    return W
