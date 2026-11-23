'''Episode specifications for branches, commits, conflicts, remotes, tags, worktrees. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
TOPIC = S(H2, git('branch', 'topic'))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
TAGP = S(PUSHED, git('tag', 'v1'))
WT = S(H2, git('worktree', 'add', '-q', '../wtx', '-b', 'wt-branch'))
CONFLICT = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'),
             commit('feat change', {'f.txt': text('a', 'feature side')}), git('checkout', '-q', 'main'),
             commit('main change', {'f.txt': text('a', 'main side')}))
OPEN = S(K('3', 'j', 'M', 'm'), wait(1), K('Enter'), wait(0.5), K('2', 'Enter'), wait(0.5))
REMOTES = ('for-each-ref', '--format=%(refname:short)', 'refs/remotes')


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-checkout-by-name', 'branches', TOPIC, 'Check out the branch topic by typing its name.',
             S(K('3', 'c'), prompt('topic'), wait(1)),
             [('head', 'The checked-out branch is topic.', repo('head', 'branches'))],
             'The branches panel lists topic as the current branch.'),
        goal('gui-move-commit-down', 'commits', H3, 'Move the newest commit one place down in the history.',
             K('4', 'Control+J'),
             [('log', 'The history reads second, third, first from the top.', repo('log')),
              ('files', 'The files of all three commits are still in the tree.', gitc('ls-tree', '-r', '--name-only', 'HEAD'))],
             'The commits panel lists second on top, then third, then first.', bind={'files': ['log']}),
        goal('gui-tag-push', 'tags', TAGP, 'Push the tag v1 to the remote origin.',
             S(K('3', ']', ']', 'P'), wait(0.5), K('Enter'), wait(2)),
             [('remote', 'The remote holds the tag v1.', gitc('tag', '-l', remote='origin')),
              ('local', 'The local tag v1 still exists.', repo('tags'))],
             'The interface indicates that tag v1 was pushed successfully to origin.', bind={'local': ['remote']}),
        goal('gui-remote-branch-delete', 'remotes', REMBR, 'Delete the remote branch remote-only from the remote origin.',
             S(K('3', ']', 'Enter', 'j', 'd'), wait(0.5), K('Enter'), wait(2)),
             [('remote', 'The remote holds only the branch main.', repo('branches', remote='origin')),
              ('tracking', 'The remote-tracking branch origin/remote-only is gone locally.', gitc(*REMOTES))],
             'The remote branches of origin list only main.'),
        goal('gui-worktree-remove', 'worktrees', WT, 'Remove the worktree wtx but keep its branch.',
             S(K('2', ']', 'j', 'd'), wait(0.5), K('Enter'), wait(1)),
             [('list', 'Only the main worktree is left.', gitc('worktree', 'list')),
              ('branch', 'The branch wt-branch still exists.', repo('head', 'branches'))],
             'The worktrees tab lists only the main worktree.', bind={'branch': ['list']}),
        goal('gui-conflict-both', 'conflicts', CONFLICT,
             'Merge feature into main and resolve the conflict in f.txt by keeping the lines of both sides, without finishing the merge.',
             S(OPEN, K('b'), wait(0.5)),
             [('status', 'The resolved file is staged.', repo('status')),
              ('content', 'The file holds the line of main followed by the line of feature.', listing(fields=['sha256'])),
              ('popup', 'A confirmation says that all merge conflicts are resolved and offers to continue the merge.', scr('popup'))],
             'A confirmation says that all merge conflicts are resolved and asks whether to continue the merge.', bind={'content': ['status'], 'popup': ['status']}),
        goal('gui-branch-from-commit', 'branches', H3, 'Create the branch `old` at the second commit and switch to it.',
             S(K('4', 'j', 'n'), prompt('old'), wait(1)),
             [('head', 'The checked-out branch is old.', repo('head', 'branches')),
              ('log', 'The history of the new branch ends with the second and first commits.', gitc('log', '--format=%s', '-n', '3')),
              ('at', 'old points at the second commit.', gitc('log', '-1', '--format=%s', 'old'))],
             'The branches panel lists old as the current branch.'),
        goal('gui-reword-body', 'commits', H3, 'Reword the newest commit: its subject becomes the text `new subject` and its description the single word `body`.',
             S(K('4', 'r', 'Control+U'), typ('new subject'), K('Tab'), typ('body'), K('Tab', 'Enter'), wait(1)),
             [('log', 'The newest commit has the new subject.', repo('log')),
              ('message', 'The full message is the subject followed by the description.', gitc('log', '-1', '--format=%B'))],
             'The commits panel lists new subject on top.'),
    ]
