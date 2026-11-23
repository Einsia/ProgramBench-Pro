'''Episode specifications for bisect, branches, commits, discard, files, rebase, staging, stash, sync, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
BIG = text(*['line %02d' % i for i in range(1, 21)])
BIGM = text(*[('LINE 02' if i == 2 else 'LINE 18' if i == 18 else 'line %02d' % i) for i in range(1, 21)])
HUNKS = S(commit('base', {'big.txt': BIG}), put({'big.txt': BIGM}))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
EDITED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}))
KEEP = S(H2, put({'c1.txt': text('content 1', 'first', 'a')}), git('add', '.'), put({'c1.txt': text('content 1', 'first', 'a', 'b')}))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
TAGGED = S(H3, git('tag', 'v1'))
TOPIC = S(H2, git('branch', 'topic'))
IGN = S(H2, put({'new.txt': text('new')}))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
FORCE = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'), commit('rewritten', {'r.txt': text('r')}))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))
FF = S(H2, git('checkout', '-q', '-b', 'feature'), commit('feat', {'f.txt': text('f')}), git('checkout', '-q', 'main'))
FEATURE = S(commit('base', {'b.txt': text('base')}), git('checkout', '-q', '-b', 'feature'), commit('f-one', {'f1.txt': text('one')}), commit('f-two', {'f2.txt': text('two')}), commit('f-three', {'f3.txt': text('three')}))
CONFLICT = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'), commit('feat change', {'f.txt': text('a', 'feature side')}), git('checkout', '-q', 'main'), commit('main change', {'f.txt': text('a', 'main side')}))
GRACE = 'Grace Hopper <grace@example.com>'
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-stage-line', 'staging', HUNKS, 'Open the diff of big.txt and stage only the removal of line 02; leave everything else unstaged.',
             K('2', 'Enter', 'a', 'Space'),
             [('cached', 'Only the removal of line 02 is staged.', gitc('diff', '--cached')),
              ('unstaged', 'The rest of the changes are still unstaged.', gitc('diff'))],
             'Only the removal of line 02 of big.txt is shown as staged.'),
        goal('gui-stage-range', 'staging', HUNKS, 'In the diff of big.txt select the removal of line 02 together with the addition of LINE 02 and stage both.',
             K('2', 'Enter', 'a', 'v', 'j', 'Space'),
             [('cached', 'The removal and the addition at line 02 are staged.', gitc('diff', '--cached')),
              ('unstaged', 'Only the change at line 18 is still unstaged.', gitc('diff'))],
             'The change at line 02 of big.txt is shown as staged and the change at line 18 is not.'),
        goal('gui-discard-untracked', 'discard', DIRTY, 'Discard the untracked file new.txt and confirm; keep the change of c1.txt.',
             K('2', 'j', 'j', 'd', 'Enter'),
             [('status', 'Only the change of c1.txt remains.', repo('status')),
              ('tree', 'new.txt is gone from the workspace.', listing(names_only=True))],
             'new.txt is no longer listed and c1.txt still shows its change.'),
        goal('gui-stash-keep-index', 'stash', KEEP, 'Stash all changes under the name `keep` but leave the staged change in the index.',
             S(K('2', 'S', 'i'), prompt('keep')),
             [('stash', 'One stash named keep exists.', repo('stash')),
              ('status', 'The staged change is still staged.', repo('status'))],
             'The stash panel lists keep and c1.txt is still shown as staged.'),
        goal('gui-stash-untracked', 'stash', DIRTY, 'Stash all changes including the untracked file under the name `untracked stash`.',
             S(K('2', 'S', 'U'), prompt('untracked stash')),
             [('stash', 'One stash named untracked stash exists.', repo('stash')),
              ('tree', 'The untracked file is gone from the workspace.', listing(names_only=True)),
              ('status', 'The working tree is clean.', repo('status'))],
             ['The stash panel lists the entry untracked stash.', 'The files panel shows no changed files.']),
        goal('gui-stash-apply', 'stash', STASHED, 'Apply the stash wip to the working tree and keep the stash.',
             K('5', 'Space', 'Enter'),
             [('status', 'The stashed change is back in the working tree.', repo('status')),
              ('stash', 'The stash entry is kept.', repo('stash'))],
             'c1.txt is listed as changed and the stash panel still lists wip.', bind={'stash': ['status']}),
        goal('gui-stash-drop', 'stash', STASHED, 'Drop the stash wip without applying it.',
             K('5', 'd', 'Enter'),
             [('stash', 'The stash list is empty.', repo('stash')),
              ('status', 'The working tree stays clean.', repo('status'))],
             'The stash panel is empty and the files panel shows no changes.', bind={'status': ['stash']}),
        goal('gui-stash-branch', 'stash', STASHED, 'Create the branch `from-stash` from the stash wip and switch to it.',
             S(K('5', 'n'), prompt('from-stash')),
             [('head', 'The branch from-stash exists and is checked out.', repo('head', 'branches')),
              ('stash', 'The stash entry is kept.', repo('stash')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The branches panel lists from-stash as the current branch.', bind={'stash': ['head'], 'status': ['head']}),
        goal('gui-ignore', 'files', IGN, 'Add the untracked file new.txt to the gitignore file.',
             K('2', 'j', 'i', 'i'),
             [('status', 'Only the new .gitignore is untracked.', repo('status')),
              ('tree', 'The workspace holds new.txt and the new .gitignore.', listing(fields=['sha256']))],
             ['new.txt is no longer listed in the files panel.', 'The files panel lists .gitignore as an untracked file.']),
        goal('gui-force-push', 'sync', FORCE, 'Push main to its upstream even though the local branch was rewritten and has diverged, confirming the force push.',
             S(K('P'), wait(3), K('Enter'), wait(3)),
             [('remote', 'The remote history equals the rewritten local history.', repo('log', remote='origin')),
              ('status', 'main is level with its upstream.', gitc(*STATUSB))],
             'The branches panel and the status panel show main level with its upstream (a check mark) instead of one commit ahead and one behind.'),
        goal('gui-pull', 'sync', BEHIND, 'Pull the commit that the upstream of main is ahead by.',
             S(K('p'), wait(3)),
             [('log', 'main gained the third commit.', repo('head', 'log')),
              ('status', 'main is level with its upstream.', gitc(*STATUSB)),
              ('sync-log', 'The local history gained the third commit.', repo('log'))],
             'The commits panel lists three commits.'),
        goal('gui-fast-forward-merge', 'branches', FF, 'Merge feature into main so that main simply moves to the feature commit without a merge commit.',
             K('3', 'j', 'M', 'Enter'),
             [('log', 'main points at the feature commit and no merge commit exists.', repo('head', 'log')),
              ('files', 'The feature file is in the tree.', gitc(*FILES))],
             'The commits panel lists the feature commit on top of main and no merge commit.'),
        goal('gui-squash-merge', 'branches', FF, 'Squash merge feature into main and commit the result.',
             K('3', 'j', 'M', 'S'),
             [('log', 'One new commit with a squash merge message is on top of main.', repo('head', 'log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel lists a squash merge commit on top of main.', bind={'status': ['log']}),
        goal('gui-branch-delete', 'branches', TOPIC, 'Delete the local branch topic.',
             K('3', 'j', 'd', 'Enter'),
             [('branches', 'Only main is left.', repo('head', 'branches')),
              ('log', 'The history is unchanged.', repo('log'))],
             'The branches panel lists only main.', bind={'log': ['branches']}),
        goal('gui-rebase-fixup', 'rebase', FEATURE, 'In an interactive rebase of feature, fix up `f-two` into `f-one`, discarding the message of `f-two`, and complete the rebase.',
             S(K('4', 'i'), wait(2), K('j', 'f', 'm', 'Enter'), wait(2)),
             [('log', 'The second commit is combined into the one below it.', repo('head', 'log')),
              ('status', 'The rebase is finished.', gitc(*STATUSB)),
              ('message', 'The complete messages distinguish squash from fixup.', gitc('log', '--format=%B')),
              ('files', 'The combined commit holds the files of both.', gitc(*FILES))],
             'The commits panel lists two commits of feature above the base commit and no rebase is shown in progress.', bind={'files': ['log', 'message']}),
        goal('gui-bisect', 'bisect', H5, 'Start a bisect: mark the newest commit as bad and the oldest commit as good.',
             S(K('4', 'b', 'b'), K('j', 'j', 'j', 'j', 'b', 'g'), wait(1)),
             [('log', 'The bisect log records the bad and the good commit.', gitc('bisect', 'log')),
              ('head', 'HEAD moved to the commit in the middle of the range.', repo('head'))],
             'The bottom line shows that a bisect is in progress.'),
        goal('gui-set-author', 'commits', H3, 'Set the author of the newest commit to `' + GRACE + '`.',
             S(K('4', 'a', 'A'), prompt(GRACE), wait(1)),
             [('author', 'The newest commit has the new author name and email.', gitc('log', '-1', '--format=%an %ae')),
              ('log', 'The history keeps its commits.', repo('log', author=True))],
             'The newest commit is shown with the new author.'),
        goal('gui-co-author', 'commits', H3, 'Add `' + GRACE + '` as co-author of the newest commit.',
             S(K('4', 'a', 'c'), prompt(GRACE), wait(1)),
             [('message', 'The message of the newest commit gained a Co-authored-by trailer.', gitc('log', '-1', '--format=%B'))],
             'The newest commit message shows the co-author.'),
        goal('gui-commit-body', 'commits', EDITED, 'Commit the change of c1.txt with the subject `subject line` and the body `body line`.',
             S(K('2', 'a', 'c'), typ('subject line'), key('Tab'), typ('body line'), key('Tab'), key('Enter'), wait(1)),
             [('message', 'The commit message has the subject and the body.', gitc('log', '-1', '--format=%B')),
              ('status', 'The working tree is clean.', repo('status')),
              ('log', 'One new commit was created and the tree is clean.', repo('log', 'status'))],
             ['The newest commit in the commits panel is subject line.', 'The files panel shows no changed files.'], bind={'status': ['message']}),
        goal('gui-tag-delete', 'tags', TAGGED, 'Delete the local tag v1.',
             K('3', ']', ']', 'd', 'Enter'),
             [('tags', 'The tag is gone.', repo('tags')),
              ('log', 'The history is unchanged.', repo('log'))],
             'The tags tab is empty.', bind={'log': ['tags']}),
        goal('gui-tag-checkout', 'tags', TAGGED, 'Check out the tag v1 as a detached head.',
             K('3', ']', ']', 'Space'),
             [('head', 'HEAD is detached.', repo('head')),
              ('status', 'No branch is checked out.', gitc(*STATUSB))],
             'The status panel shows a detached head.'),
        goal('gui-move-commit-up', 'commits', H3, 'Move the commit named second above the commit named third.',
             K('4', 'j', 'Control+K'),
             [('log', 'The two newest commits have swapped places.', repo('log'))],
             'The commits panel lists second on top, then third, then first.'),
        goal('gui-reset-soft', 'commits', H3, 'Soft reset the current branch to the second commit.',
             K('4', 'j', 'g', 's'),
             [('log', 'The newest commit is gone from the history.', repo('log')),
              ('status', 'Its change is staged.', repo('status'))],
             ['The commits panel lists two commits, second above first.', 'The files panel lists c3.txt as a staged new file.']),
        goal('gui-checkout-commit', 'commits', H3, 'Check out the second commit as a detached head and confirm.',
             S(K('4', 'j', 'Space', 'Enter'), wait(1)),
             [('head', 'HEAD is detached at the second commit.', repo('head')),
              ('status', 'No branch is checked out.', gitc(*STATUSB))],
             'The status panel shows a detached head.'),
    ]
