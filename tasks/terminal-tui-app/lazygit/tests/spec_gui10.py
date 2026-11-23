'''Episode specifications for branches, commits, discard, files, rebase, remotes, staging, stash, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
FIVE = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
TOPIC = S(H2, git('branch', 'topic'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
UNTRACKED = S(H2, put({'new.txt': text('new')}))
DIRS = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
BRANCHES = S(commit('b-base', {'b.txt': text('base')}), git('branch', 'b1'), git('branch', 'b2'), git('branch', 'b3'))
SPLIT = S(commit('base', {'f.txt': text('a')}), git('checkout', '-q', '-b', 'feature'),
          commit('f-one', {'f1.txt': text('one')}), git('checkout', '-q', 'main'), commit('m-one', {'m1.txt': text('one')}))
TREE_FILES = ('ls-tree', '-r', '--name-only', 'HEAD')


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-rename-stash', 'stash', STASHED, 'Rename the stash entry `wip` to `renamed`.',
             S(K('5', 'r', 'Control+U'), typ('renamed'), key('Enter'), wait(0.5)),
             [('stash', 'The only stash entry is named renamed.', repo('stash'))],
             'The stash panel lists the entry renamed.'),
        goal('gui-reword', 'commits', H3, 'Change the subject of the newest commit to `redone`.',
             S(K('4', 'r', 'Control+U'), typ('redone'), key('Enter'), wait(0.5)),
             [('log', 'The newest commit has the subject redone and the two older commits are unchanged.', repo('log')),
              ('renames-log', 'The newest commit has the new subject.', repo('log', 'reflog'))],
             'The newest commit in the commits panel is redone.'),
        goal('gui-rename-branch', 'branches', TOPIC, 'Rename the checked-out branch main to `renamed`.',
             S(K('3', 'R', 'Control+U'), typ('renamed'), key('Enter'), wait(0.5)),
             [('head', 'The checked-out branch is renamed and the branch topic still exists.', repo('head', 'branches'))],
             'The branches panel lists renamed as the checked-out branch.'),
        goal('gui-stash-staged', 'stash', S(STAGED, put({'c2.txt': text('content 2', 'second', 'keep unstaged')})), 'Stash only the staged changes under the name `staged stash`.',
             S(K('2', 'S', 's'), typ('staged stash'), key('Enter'), wait(0.5)),
             [('stash', 'One stash named staged stash exists.', repo('stash')),
              ('status', 'The unstaged change in c2.txt remains and c1.txt is stashed.', repo('status'))],
             ['The stash panel lists the entry staged stash.', 'The files panel lists c2.txt as unstaged; c1.txt is absent.'],
             bind={'stash': ['status']}),
        goal('gui-fixup', 'commits', H3, 'Fold the newest commit into the commit below it and discard its message.',
             S(K('4', 'f', 'Enter'), wait(0.5)),
             [('log', 'Two commits remain, second on top of first.', repo('log')),
              ('files', 'The newest commit holds the files of the three original commits.', gitc(*TREE_FILES)),
              ('message', 'The complete messages distinguish squash from fixup.', gitc('log', '--format=%B'))],
             'The commits panel lists two commits, second above first.'),
        goal('gui-add-remote', 'remotes', S(H2, bare('origin')),
             'Add a remote named `origin` with the URL `../remotes/origin.git`.',
             S(K('3', ']', 'n'), typ('origin'), key('Enter'), typ('../remotes/origin.git'), key('Enter'), wait(1)),
             [('remotes', 'The remote origin exists with the given url for fetch and push.', repo('remotes'))],
             'The remotes tab lists the remote origin.'),
        goal('gui-drop-range', 'commits', FIVE, 'Drop the two newest commits together.',
             S(K('4', 'v', 'j', 'd', 'Enter'), wait(1)),
             [('log', 'The three oldest commits remain.', repo('log')),
              ('files', 'The files of the dropped commits are gone.', gitc(*TREE_FILES))],
             'The commits panel lists three commits with c-three on top.'),
        goal('gui-exclude', 'files', UNTRACKED,
             'Make git ignore the untracked file new.txt through the exclude file of the repository, not through a gitignore file.',
             S(K('2', 'j', 'i', 'e'), wait(1)),
             [('status', 'new.txt is no longer listed as untracked.', repo('status')),
              ('tree', 'The file itself is still in the workspace.', listing(names_only=True))],
             'The files panel shows no changed files.'),
        goal('gui-stage-dir', 'staging', DIRS, 'Stage both files of the directory d at once and leave top.txt unstaged.',
             S(K('2', 'j', 'Space'), wait(0.5)),
             [('status', 'Both files of the directory d are staged and top.txt is not.', repo('status'))],
             'The files panel lists e.txt and f.txt in the directory d as staged.'),
        goal('gui-mixed-reset', 'commits', H3, 'Mixed reset the current branch to the second commit.',
             S(K('4', 'j', 'g', 'm'), wait(0.5)),
             [('log', 'The newest commit is gone from the history.', repo('log')),
              ('status', 'Its change is left in the working tree and not staged.', repo('status'))],
             ['The commits panel lists two commits, second above first.',
              'The files panel lists c3.txt as an untracked file.'],
             bind={'status': ['log']}),
        goal('gui-delete-branch-range', 'branches', BRANCHES, 'Delete the branches b1 and b2 together and keep b3.',
             S(K('3', 'j', 'v', 'j', 'd', 'Enter'), wait(1)),
             [('branches', 'Only main and b3 are left.', repo('head', 'branches')),
              ('log', 'The history is unchanged.', repo('log'))],
             'The branches panel lists only main and b3.', bind={'log': ['branches']}),
        goal('gui-unset-upstream', 'branches', PUSHED, 'Make the branch main stop tracking origin/main.',
             S(K('3', 'u', 'u'), wait(0.5)),
             [('status', 'main has no upstream any more.', gitc('status', '--porcelain', '-b')),
              ('log', 'The history is unchanged.', repo('log'))],
             'The branches panel shows main without an upstream status mark.', bind={'log': ['status']}),
        goal('gui-tag-from-tab', 'tags', S(H3, git('tag', 'v1')), 'Create a tag named `v2` on the checked-out commit.',
             S(K('3', ']', ']', 'n'), typ('v2'), key('Enter'), wait(1)),
             [('tags', 'The tags v1 and v2 both name the newest commit.', repo('tags')),
              ('log', 'The history is unchanged.', repo('log'))],
             'The tags tab lists v2 next to v1.', bind={'log': ['tags']}),
        goal('gui-discard-dir', 'discard', DIRS, 'Discard the untracked directory d and keep top.txt.',
             S(K('2', 'j', 'd', 'x'), wait(1)),
             [('status', 'Only top.txt is left untracked.', repo('status')),
              ('tree', 'The directory d is gone from the workspace.', listing(names_only=True))],
             'The files panel lists only top.txt.',
             bind={'tree': ['status']}),
        goal('gui-nuke', 'discard', DIRTY,
             'Throw away every change of the working tree, including the untracked file new.txt.',
             S(K('2', 'D', 'x', 'Enter'), wait(0.5)),
             [('status', 'The working tree is clean.', repo('status')),
              ('tree', 'No untracked file is left in the workspace.', listing(names_only=True))],
             'The files panel shows no changed files.'),
        goal('gui-rebase-onto', 'rebase', SPLIT, 'Rebase the checked-out branch main onto the branch feature.',
             S(K('3', 'j', 'r'), wait(0.5), K('Enter'), wait(2)),
             [('log', 'main holds m-one on top of f-one and base.', repo('head', 'log')),
              ('feature', 'The branch feature is unchanged.', gitc('log', '--format=%s', 'feature'))],
             'The commits panel lists m-one, f-one and base, in this order.'),
    ]
