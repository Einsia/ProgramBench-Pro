'''Episode specifications for branches, commits, discard, staging, stash. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
BIG = text(*['line %02d' % i for i in range(1, 21)])
BIGM = text(*[('LINE 02' if i == 2 else 'LINE 18' if i == 18 else 'line %02d' % i) for i in range(1, 21)])
HUNKS = S(commit('base', {'big.txt': BIG}), put({'big.txt': BIGM}))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
DIVERGED = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'),
             commit('feat change', {'g.txt': text('g')}), git('checkout', '-q', 'main'),
             commit('main change', {'h.txt': text('h')}))
DIVERGED_F = S(DIVERGED, git('checkout', '-q', 'feature'))
CP = S(H2, git('checkout', '-q', '-b', 'feature'), commit('feat', {'f.txt': text('f')}), git('checkout', '-q', 'main'))
FILES = ['ls-tree', '-r', '--name-only', 'HEAD']


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-stage-hunk', 'staging', HUNKS,
             'Open the diff of big.txt and stage only its first change, the one at line 02; leave the change at line 18 unstaged.',
             K('2', 'Enter', 'Space'),
             [('cached', 'Only the first change is staged.', gitc('diff', '--cached')),
              ('unstaged', 'The second change is still unstaged.', gitc('diff')),
              ('status', 'big.txt is both staged and modified.', repo('status'))],
             ['The staged changes view shows only the change at line 02.', 'The unstaged changes view shows only the change at line 18.']),
        goal('gui-discard-file', 'discard', DIRTY,
             'Discard the uncommitted changes of c1.txt without touching new.txt.', K('2', 'j', 'd', 'x'),
             [('status', 'c1.txt is restored and new.txt stays untracked.', repo('status')),
              ('diff', 'There is no unstaged change left in tracked files.', gitc('diff'))],
             'c1.txt is no longer listed in the files panel.'),
        goal('gui-stash-all', 'stash', DIRTY,
             'Stash only the tracked changes under the name `my stash`; leave the untracked file `new.txt` in the working tree.',
             S(K('2', 's'), prompt('my stash')),
             [('stash', 'One stash named my stash exists.', repo('stash')),
              ('status', 'The tracked change is stashed.', repo('status'))],
             ['The stash panel lists an entry named my stash.', 'c1.txt is no longer listed in the files panel.']),
        goal('gui-stash-pop', 'stash', STASHED,
             'Pop the stash so that its changes return to the working tree and the stash list is empty.',
             K('5', 'g', 'Enter'),
             [('stash', 'The stash list is empty.', repo('stash')),
              ('status', 'The stashed change is back in the working tree.', repo('status'))],
             ['The stash panel is empty.', 'c1.txt is listed as modified in the files panel.']),
        goal('gui-amend', 'commits', STAGED,
             'Add the staged change to the newest commit without creating a new commit.', K('4', 'A', 'Enter'),
             [('log', 'The history keeps its two commits and the tree is clean.', repo('log', 'status')),
              ('files', 'The newest commit now holds the staged change.', gitc('show', '--stat', '--format=%s', 'HEAD'))],
             'The files panel shows no changes.'),
        goal('gui-squash', 'commits', H3,
             'Squash the newest commit into the commit below it.', K('4', 's', 'Enter'),
             [('log', 'The two newest commits are combined.', repo('log')),
              ('files', 'The combined commit holds the files of both.', gitc(*FILES)),
              ('message', 'The complete messages distinguish squash from fixup.', gitc('log', '--format=%B'))],
             'The commits panel lists two commits instead of three.'),
        goal('gui-drop', 'commits', H3,
             'Drop the newest commit.', K('4', 'd', 'Enter'),
             [('log', 'The newest commit is gone.', repo('log')),
              ('files', 'Its file is gone from the tree.', gitc(*FILES))],
             ['The commits panel lists two commits.', 'The commit third is no longer listed in the commits panel.']),
        goal('gui-revert', 'commits', H3,
             'Revert the newest commit.', K('4', 't', 'Enter'),
             [('log', 'A new commit reverts the newest one.', repo('log')),
              ('files', 'The reverted file is gone from the tree.', gitc(*FILES)),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel lists a new revert commit on top of the three existing ones.', bind={'status': ['log']}),
        goal('gui-tag', 'commits', H3,
             'Tag the newest commit with the name `v1`.', S(K('4', 'T'), prompt('v1')),
             [('tags', 'A tag named v1 exists.', repo('tags'))],
             'The newest commit is shown with the tag v1.'),
        goal('gui-reset-hard', 'commits', H3,
             'Reset the current branch hard to the second commit.', K('4', 'j', 'g', 'h'),
             [('log', 'The newest commit is gone from the history.', repo('log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel lists two commits, second above first.',
             bind={'status': ['log']}),
        goal('gui-new-branch', 'branches', H2,
             'Create a branch named `feature-x` and switch to it.', S(K('3', 'n'), prompt('feature-x')),
             [('head', 'The branch feature-x is checked out.', repo('head', 'branches'))],
             'The branches panel lists feature-x as the current branch.'),
        goal('gui-merge', 'branches', DIVERGED,
             'Merge the branch feature into main with a merge commit.', K('3', 'j', 'M', 'm'),
             [('log', 'A merge commit with two parents is on top of main.', repo('head', 'log')),
              ('files', 'Both sides files are in the tree.', gitc(*FILES))],
             'The commits panel shows a merge commit on top of main.'),
        goal('gui-rebase', 'branches', DIVERGED_F,
             'Rebase the branch feature onto main.', K('3', 'j', 'r', 'Enter'),
             [('log', 'The feature commit sits on top of the main commit.', repo('head', 'log')),
              ('files', 'Both sides files are in the tree.', gitc(*FILES))],
             'The commits panel lists the feature commit above the main commit.'),
        goal('gui-cherry-pick', 'branches', CP,
             'Copy the newest commit of feature and paste it onto main.',
             K('3', 'j', 'Enter', 'C', 'Escape', '4', 'V', 'Enter'),
             [('log', 'main gained a commit with the subject of the copied one.', repo('head', 'log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel of main lists a commit named feat on top.',
             bind={'status': ['log']}),
    ]
