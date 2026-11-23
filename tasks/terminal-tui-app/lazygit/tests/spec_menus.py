'''Episode specifications for menus. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
TOPIC = S(H2, git('branch', 'topic'))
TAGGED = S(H3, git('tag', 'v1'))


def menu(cid, goal, fixture, keys, what):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)),
                [('popup', what, scr('popup')),
                 ('status', 'Opening it changed nothing in the repository.', repo('status', 'log'))],
                requires={'status': ['popup']})


def build():
    return [program('menu-popups', 'menus', None, [
        menu('status-filter', 'Open the status filter menu of the files panel.', DIRTY, K('2', 'Control+B'), 'A menu offers to show only staged, unstaged, tracked or untracked files, or no filter.'),
        menu('copy-path', 'Open the copy menu for the selected file in the files panel.', DIRTY, K('2', 'j', 'y'), 'A menu offers to copy the file name, the relative or absolute path or a diff.'),
        menu('diffing', 'Open the diffing menu in the commits panel.', H3, K('4', 'W'), 'A menu offers to diff the selected commit or to enter a ref to diff.'),
        menu('log-options', 'Open the commit log options menu in the commits panel.', H3, K('4', 'Control+L'), 'A menu offers the whole graph toggle, the graph display and the sort order.'),
        menu('discard-untracked', 'Open the discard menu for the untracked file new.txt.', DIRTY, K('2', 'j', 'j', 'd'), 'A menu offers to discard all changes or only the unstaged ones of the file.'),
        menu('reset-menu', 'Open the reset menu of the files panel.', DIRTY, K('2', 'D'), 'A menu offers nuke, discard and soft, mixed or hard reset entries.'),
        menu('hard-reset', 'Choose the hard reset entry of the reset menu.', DIRTY, K('2', 'D', 'h'), 'A confirmation warns that a hard reset discards all uncommitted changes.'),
        menu('bisect', 'Open the bisect menu in the commits panel.', H3, K('4', 'b'), 'A menu offers to mark the selected commit as bad or good or to choose bisect terms.'),
        menu('branch-delete', 'Open the delete menu for the branch topic.', TOPIC, K('3', 'j', 'd'), 'A menu offers to delete the local branch, the remote branch or both.'),
        menu('tag-delete', 'Open the delete menu for the tag v1 in the tags tab.', TAGGED, K('3', ']', ']', 'd'), 'A menu offers to delete the local tag, the remote tag or both.'),
        menu('new-worktree', 'Open the new worktree menu for the newest commit.', H2, K('4', 'w'), 'A menu offers a new branch and worktree or a detached worktree.'),
        menu('amend-attribute', 'Open the amend commit attribute menu.', H3, K('4', 'a'), 'A menu offers to reset the author, set the author or add a co-author.'),
        menu('fixup-commit', 'Open the create fixup commit menu with a staged change.', STAGED, K('4', 'F'), 'A menu offers a fixup commit, an amend commit with changes or a pure reword.'),
        menu('ignore', 'Open the ignore menu for the untracked file new.txt.', DIRTY, K('2', 'j', 'j', 'i'), 'A menu offers to add the file to the gitignore file or to the exclude file.'),
        menu('branch-sort', 'Open the sort order menu of the branches panel.', TOPIC, K('3', 's'), 'A menu offers recency, alphabetical and date sort orders with one selected.'),
        menu('force-checkout', 'Ask for a forced checkout of the branch topic.', TOPIC, K('3', 'j', 'F'), 'A confirmation warns that all local changes will be lost.'),
        menu('drop-confirm', 'Ask to drop the newest commit.', H3, K('4', 'd'), 'A confirmation asks whether to drop the selected commit.'),
        menu('squash-confirm', 'Ask to squash the newest commit into the one below.', H3, K('4', 's'), 'A confirmation asks whether to squash the selected commit into the commit below.'),
        menu('stash-branch', 'Ask for the name of a branch to create from the stash.', STASHED, K('5', 'n'), 'A prompt asks for the name of the new branch.'),
    ])]
