'''Episode specifications for conflicts, rebase, reflog, submodules, sync, worktrees. Fixtures, actions and checks use the documented runtime channels.'''
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
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
NOUP = S(H2, ORIGIN)
FETCHABLE = S(PUSHED, git('clone', '-q', '@remotes/origin', 'other'),
              commit('upstream change', {'u.txt': text('u')}, repo='other'),
              git('push', '-q', 'origin', 'main', repo='other'))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))
SUBREPO = S(put({'seed/s.txt': text('sub content')}), git('init', '-q', '-b', 'main', repo='seed'),
            git('add', '.', repo='seed'), git('commit', '-q', '-m', 'sub one', repo='seed'), bare('sub'),
            git('remote', 'add', 'origin', '@remotes/sub', repo='seed'),
            git('push', '-q', 'origin', 'main', repo='seed'))
SUBMOD = S(H2, SUBREPO, git('submodule', 'add', '@remotes/sub', 'sub1'), git('commit', '-q', '-m', 'add submodule'))
TREE_FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')
TODO = S(K('4', 'i'), wait(2))
OPEN = S(K('3', 'j', 'M', 'm'), wait(1), K('Enter'), wait(0.5), K('2', 'Enter'), wait(0.5))


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-reflog-checkout', 'reflog', H3, 'Check out the commit of the second reflog entry as a detached head.',
             S(K('4', ']', 'j', 'Space', 'Enter'), wait(1)),
             [('head', 'HEAD is detached at the second commit.', repo('head')),
              ('status', 'No branch is checked out.', gitc(*STATUSB))],
             'The status panel shows a commit hash where the branch name main was shown.'),
        goal('gui-reflog-reset', 'reflog', H3, 'Hard reset the current branch to the commit of the second reflog entry.',
             S(K('4', ']', 'j', 'g', 'h'), wait(1)),
             [('log', 'main points at the second commit again.', repo('head', 'log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The reflog tab of the commits panel shows a new reset entry on top.',
             bind={'status': ['log']}),
        gui('gui-submodule', 'submodules', SUBMOD, [
            step('enter', 'Open the submodule sub1 as the repository shown by lazygit.', S(K('2', ']', ']', 'Enter'), wait(1)),
                 [('status', 'The status panel names the submodule repository.', pan(1))],
                 acceptance=['The status panel names the repository sub1 instead of workspace.'],
                 requires={'done': ['status']}),
            step('return', 'Go back to the parent repository.', S(K('Escape'), wait(1)),
                 [('status', 'The status panel names the parent repository again.', pan(1))],
                 acceptance=['The status panel names the repository workspace again instead of sub1.'],
                 requires={'done': ['status']}, depends=['enter']),
        ]),
        goal('gui-worktree-create', 'worktrees', H2,
             'Create a new worktree with a new branch `wt-one` from the newest commit, keeping the offered location.',
             S(K('4', 'w', 'b'), prompt('wt-one'), wait(1), K('Enter'), wait(2)),
             [('worktrees', 'A second worktree for the branch wt-one exists next to the main one.', repo('worktrees')),
              ('branches', 'The branch wt-one points at the newest commit.', repo('head', 'branches'))],
             'The interface shows the new worktree: its branch wt-one is listed as checked out.'),
        goal('gui-merge-conflict', 'conflicts', CONFLICT, 'Merge the branch feature into main.',
             S(K('3', 'j', 'M', 'm'), wait(1)),
             [('status', 'f.txt is listed as unmerged.', repo('status'))],
             ['A popup reports conflicts and offers to view them or to abort the merge.',
              'The bottom line shows that a merge is in progress.']),
        goal('gui-resolve-merge', 'conflicts', CONFLICT,
             'Merge feature into main, resolve the conflict in f.txt by keeping the lines of main and finish the merge.',
             S(K('3', 'j', 'M', 'm'), wait(1), K('Enter', 'Enter', 'Space'), wait(1), K('Enter'), wait(2)),
             [('log', 'A merge commit with the two parents is on top of main.', repo('head', 'log')),
              ('file', 'The merged file holds the side of main.', gitc('show', 'HEAD:f.txt')),
              ('status', 'No merge is in progress and the working tree is clean.', gitc(*STATUSB))],
             'The commits panel shows a merge commit on top of main.',
             bind={'file': ['log'], 'status': ['log']}),
        goal('gui-conflict-theirs', 'conflicts', CONFLICT,
             'Merge feature into main and resolve the conflict in f.txt by keeping the line of feature, without finishing the merge.',
             S(OPEN, K('j', 'Space'), wait(0.5)),
             [('status', 'The resolved file is staged.', repo('status')),
              ('content', 'The file holds the line of the merged branch and no conflict markers.', listing(fields=['sha256'])),
              ('popup', 'A confirmation says that all merge conflicts are resolved and offers to continue the merge.', scr('popup'))],
             'A confirmation says that all merge conflicts are resolved and asks whether to continue the merge.',
             bind={'content': ['status'], 'popup': ['status']}),
        goal('gui-rebase-start', 'rebase', FEATURE, 'Start an interactive rebase of all commits of feature above base.',
             TODO,
             [('status', 'A rebase is under way and HEAD is detached.', gitc(*STATUSB)),
              ('head', 'HEAD sits on the base commit and the branch feature is kept.', repo('head', 'branches')),
              ('banner', 'The bottom line shows that a rebase is in progress.', scr('banner'))],
             ['The bottom line shows that a rebase is in progress.',
              'The commits panel lists the commits of feature as pending rebase todos.'],
             bind={'head': ['status']}),
        goal('gui-rebase-drop', 'rebase', FEATURE,
             'In an interactive rebase of feature, drop the commit f-two and complete the rebase.',
             S(TODO, K('j', 'd', 'm', 'Enter'), wait(2)),
             [('log', 'The dropped commit is gone from the branch.', repo('head', 'log')),
              ('files', 'Its file is gone from the tree.', gitc(*TREE_FILES)),
              ('status', 'The rebase is finished.', gitc(*STATUSB))],
             'The commits panel lists f-three, f-one and base and no rebase is shown in progress.',
             bind={'files': ['log'], 'status': ['log']}),
        goal('gui-rebase-squash', 'rebase', FEATURE,
             'In an interactive rebase of feature, squash the commit f-two into f-one and complete the rebase.',
             S(TODO, K('j', 's', 'm', 'Enter'), wait(2)),
             [('log', 'The second commit is combined into the one below it.', repo('head', 'log')),
              ('files', 'The combined commit holds the files of both.', gitc(*TREE_FILES)),
              ('status', 'The rebase is finished.', gitc(*STATUSB)),
              ('message', 'The complete messages distinguish squash from fixup.', gitc('log', '--format=%B'))],
             'The commits panel lists two commits of feature above base.',
             bind={'files': ['log'], 'status': ['log']}),
        gui('gui-rebase-abort', 'rebase', FEATURE, [
            step('start', 'Start an interactive rebase of all commits of feature above base.', TODO,
                 [('status', 'A rebase is under way and HEAD is detached.', gitc(*STATUSB))],
                 acceptance=['The bottom line shows that a rebase is in progress.'],
                 requires={'done': ['status']}),
            step('abort', 'Abort the rebase.', S(K('m', 'a'), wait(2)),
                 [('status', 'The branch feature is checked out again and no rebase is in progress.', gitc(*STATUSB)),
                  ('log', 'All three commits of the branch are back.', repo('head', 'log'))],
                 acceptance=['The status panel shows the branch feature checked out instead of a rebase in progress.'],
                 requires={'done': ['status', 'log'], 'log': ['status']}, depends=['start']),
        ]),
        goal('gui-push-new-upstream', 'sync', NOUP,
             'Push main to the remote origin as a new upstream branch with the offered remote and branch names.',
             S(K('P', 'Enter'), wait(3)),
             [('remote', 'The remote has the two commits.', repo('log', remote='origin')),
              ('status', 'main tracks origin/main and is level with it.', gitc(*STATUSB))],
             'The branches panel shows main level with its new upstream (a check mark).',
             bind={'status': ['remote']}),
        goal('gui-fetch', 'sync', FETCHABLE, 'Fetch from the remote origin, which has a commit that is not known locally yet.',
             S(K('3', ']', 'f'), wait(2)),
             [('tracking', 'origin/main now points at the upstream change.', gitc('log', '-1', '--format=%s', 'origin/main')),
              ('log', 'The history of all refs has the new commit.', repo('log', all=True))],
             'The status panel shows main one commit behind its upstream.'),
        goal('gui-fast-forward', 'sync', BEHIND, 'Bring main up to date with its upstream, which is one commit ahead, without a merge commit.',
             S(K('3', 'f'), wait(3)),
             [('log', 'main gained the third commit without a merge commit.', repo('head', 'log')),
              ('status', 'main is level with its upstream.', gitc(*STATUSB))],
             'The commits panel lists third on top of second and first.',
             bind={'status': ['log']}),
    ]
