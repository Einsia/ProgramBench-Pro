'''Repository operations, conflict recovery and local repository management through the terminal interface.'''
from spec_base import *  # noqa: F401,F403
from spec_flow import FEATURE, CONFLICT, SUBMOD, SUBREPO

H3 = history('first', 'second', 'third')
H5 = history('one', 'two', 'three', 'four', 'five')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
MIXED = S(H3, put({'c1.txt': text('staged')}), git('add', 'c1.txt'),
          put({'c2.txt': text('unstaged'), 'new.txt': text('untracked')}))
PUSHED = S(history('first'), ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
AHEAD = S(PUSHED, commit('second', {'c2.txt': text('second')}), commit('third', {'c3.txt': text('third')}))
WT = S(H3, git('worktree', 'add', '-q', '../wtx', '-b', 'wt-branch'))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(.8)), checks, requires=requires)


def build():
    W = []
    W.append(program('undo-redo-drop', 'undo', H5, [
        step('drop-two', 'Drop the two newest commits separately.', K('4', 'd', 'Enter', 'd', 'Enter'),
             [('log', 'The three older commits remain.', repo('log'))]),
        step('undo-once', 'Undo the most recent drop.', K('z', 'Enter'),
             [('log', 'The fourth commit returns.', repo('log')), ('files', 'Its file returns.', gitc(*FILES))],
             depends=['drop-two']),
        step('undo-twice', 'Undo the earlier drop.', K('z', 'Enter'),
             [('log', 'All five commits return.', repo('log')), ('files', 'All five files return.', gitc(*FILES))],
             depends=['undo-once']),
        step('redo-once', 'Redo the earlier drop.', K('Z', 'Enter'),
             [('log', 'The fifth commit is dropped again.', repo('log'))], depends=['undo-twice']),
        step('redo-twice', 'Redo the most recent drop.', K('Z', 'Enter'),
             [('log', 'The fourth commit is dropped again.', repo('log'))], depends=['redo-once']),
    ]))
    W.append(program('undo-redo-reset', 'undo', H3, [
        step('reset', 'Hard reset to the oldest commit.', K('4', 'j', 'j', 'g', 'h'),
             [('log', 'Only the first commit remains.', repo('log'))]),
        step('undo', 'Undo the hard reset.', K('z', 'Enter'),
             [('log', 'All three commits return.', repo('log')), ('files', 'All three files return.', gitc(*FILES))],
             depends=['reset']),
        step('redo', 'Redo the hard reset.', K('Z', 'Enter'),
             [('log', 'Only the first commit remains again.', repo('log')), ('files', 'Only its file remains.', gitc(*FILES))],
             depends=['undo']),
    ]))
    W.append(program('move-unpushed-branch', 'branches', None, [
        cp('move', 'Move the unpushed commits from main to a new branch named moved.', AHEAD,
           S(K('3', 'N', 'Enter'), prompt('moved')),
           [('branches', 'moved holds the local commits and main returns to its upstream.', repo('head', 'branches')),
            ('main', 'main contains only the published first commit.', gitc('log', '--format=%s', 'main'))]),
    ]))
    W.append(program('todo-pick', 'rebase', FEATURE, [
        step('start', 'Start a rebase and mark the second todo entry as dropped.', S(K('4', 'i'), wait(1), K('j', 'd')),
             [('todo', 'The todo list marks the selected entry as drop.', pan(4))]),
        step('pick', 'Change the dropped entry back to pick and finish the rebase.', S(K('p', 'm', 'Enter'), wait(1)),
             [('log', 'All original commits are retained and feature is checked out.', repo('head', 'log'))], depends=['start']),
    ]))
    W.append(program('todo-reorder', 'rebase', None, [
        cp('up', 'Move f-two up in the interactive todo list and finish.', FEATURE,
           S(K('4', 'i'), wait(1), K('j', 'Control+K', 'm', 'Enter'), wait(1)),
           [('log', 'The reordered commits appear in the resulting history.', repo('head', 'log'))]),
        cp('down', 'Move f-three down in the interactive todo list and finish.', FEATURE,
           S(K('4', 'i'), wait(1), K('Control+J', 'm', 'Enter'), wait(1)),
           [('log', 'The reordered commits appear in the resulting history.', repo('head', 'log'))]),
    ]))
    W.append(program('workspace-reset-actions', 'discard', None, [
        cp('unstaged', 'Discard all unstaged tracked changes while retaining staged and untracked files.', MIXED, K('2', 'D', 'u'),
           [('status', 'Only staged and untracked changes remain.', repo('status')),
            ('worktree', 'The unstaged file is restored to its committed content.', listing(fields=['sha256']))]),
        cp('untracked', 'Remove untracked files while retaining both tracked modifications.', MIXED, K('2', 'D', 'c'),
           [('status', 'Both tracked changes remain.', repo('status')),
            ('worktree', 'new.txt is removed without changing tracked file content.', listing(fields=['sha256']))]),
        cp('staged', 'Discard staged changes while retaining unstaged and untracked files.', MIXED, K('2', 'D', 'S'),
           [('status', 'Only unstaged and untracked changes remain.', repo('status')),
            ('worktree', 'The staged file is restored and the other edits remain.', listing(fields=['sha256']))]),
        cp('mixed', 'Unstage all changes with a mixed reset to HEAD.', MIXED, K('2', 'D', 'm'),
           [('status', 'Both tracked modifications are unstaged.', repo('status')),
            ('content', 'All working files retain their content.', listing(fields=['sha256']))], requires={'content':['status']}),
        cp('hard', 'Hard reset tracked files while retaining untracked files.', MIXED, K('2', 'D', 'h', 'Enter'),
           [('status', 'Only new.txt remains untracked.', repo('status')),
            ('worktree', 'Both tracked files are restored.', listing(fields=['sha256']))]),
    ]))
    target = S(H3, git('branch', 'older', 'HEAD~2'))
    W.append(program('branch-reset-actions', 'branches', None, [
        cp(mode, 'Reset main to the branch older using a '+mode+' reset.', target, K('3', 'j', 'g', key_),
           [('log', 'main now contains only the first commit.', repo('head', 'log')),
            ('changes', 'The reset mode determines the staged and unstaged changes.', repo('status'))],
           requires={'changes':['log']})
        for mode,key_ in [('soft','s'),('mixed','m'),('hard','h')]
    ]))
    dirty_checkout = S(commit('base', {'f.txt':text('base')}),git('checkout','-q','-b','feature'),
                       commit('changed', {'f.txt':text('feature')}),git('checkout','-q','main'),put({'f.txt':text('dirty')}))
    W.append(program('branch-force-checkout', 'branches', None, [
        cp('force', 'Force checkout feature and discard the conflicting local modification.', dirty_checkout,
           K('3', 'j', 'F', 'Enter'),
           [('head', 'feature is checked out.', repo('head')),
            ('content', 'The worktree contains the feature version.', listing(fields=['sha256']))]),
    ]))
    W.append(program('branch-upstream-tag', 'branches', None, [
        cp('set-upstream', 'Set main to track origin/main.', S(PUSHED,git('branch','--unset-upstream')),
           S(K('3','u','s'),prompt('origin main')),
           [('branches','main tracks origin/main.',repo('branches'))]),
        cp('tag-branch','Create a tag on the selected older branch.',target,S(K('3','j','T'),prompt('older-tag')),
           [('tags','older-tag names the first commit.',repo('tags'))]),
    ]))
    W.append(program('tag-annotation', 'tags', None, [
        cp('create', 'Create an annotated tag with an explicit description.', H3,
           S(K('4','T'),typ('release'),K('Tab'),typ('release notes'),K('Tab','Enter')),
           [('tags','release is an annotated tag.',repo('tags')),
            ('message','The annotation preserves the description.',gitc('for-each-ref','--format=%(contents)','refs/tags/release'))]),
    ]))
    tagged_remote=S(PUSHED,git('tag','published'),git('push','-q','origin','published'))
    W.append(program('tag-delete-remote', 'tags', None, [
        cp('remote','Delete a tag locally and on its remote.',tagged_remote,K('3',']',']','d','b','Enter','Enter'),
           [('remote','The published tag is removed from origin.',repo('tags',remote='origin')),
            ('local','The local tag is also removed.',repo('tags'))],requires={'local':['remote']}),
    ]))
    tracked_branch=S(PUSHED,git('branch','topic'),git('push','-q','-u','origin','topic'))
    W.append(program('branch-delete-both', 'branches', None, [
        cp('delete','Delete topic locally and on origin.',tracked_branch,K('3','j','d','j','j','Enter','Enter'),
           [('local','Only main remains locally.',repo('branches')),
            ('remote','Only main remains on origin.',repo('branches',remote='origin'))]),
    ]))
    W.append(program('submodule-management', 'submodules', None, [
        cp('add','Add the local submodule as module-one at modules/one.',S(H3,SUBREPO),
           S(K('2',']',']','n'),prompt('../remotes/sub.git'),K('Control+U'),prompt('module-one'),
             K('Control+U'),prompt('modules/one'),wait(1)),
           [('status','The submodule and .gitmodules are staged.',repo('status')),
            ('module','The submodule is checked out at its first commit.',gitc('submodule','status')),
            ('config','The module name, path and local URL are saved.',gitc('show',':.gitmodules'))]),
        cp('remove','Remove sub1 through the submodules panel.',SUBMOD,K('2',']',']','d','Enter'),
           [('status','The submodule removal is staged.',repo('status')),
            ('index','The index no longer contains the submodule gitlink.',gitc('ls-files','--stage'))]),
    ]))
    W.append(program('worktree-management', 'worktrees', None, [
        cp('detached','Create a detached worktree at main using the default location.',H3,
           S(K('3','w','d'),wait(.5),K('Enter'),wait(1)),
           [('worktrees','A second, detached worktree exists.',repo('worktrees')),
            ('branches','No extra branch was created.',repo('branches'))],requires={'branches':['worktrees']}),
        cp('remove-branch','Remove wtx together with its local branch.',WT,K('2',']','j','d','j','Enter'),
           [('worktrees','Only the main worktree remains.',repo('worktrees')),
            ('branches','wt-branch has been deleted.',repo('branches'))]),
        cp('switch','Switch to the existing worktree wtx.',WT,K('2',']','j','Enter'),
           [('view','The status panel identifies wtx.',pan(1))]),
    ]))
    patch=S(K('4','j','Enter','Space','Escape','Control+P'))
    W.append(program('custom-patch-actions', 'patch', None, [
        cp('copy','Copy the selected patch to the clipboard.',H3,S(patch,K('y')),
           [('patch','The clipboard contains a patch adding c2.txt.',clip(scrub=True))]),
        cp('new-after','Move the patch to a new commit after the original one.',H3,S(patch,K('n'),prompt('split-after'),wait(1)),
           [('log','The new commit follows second in the history.',repo('log')),
            ('changed-files','The original commit is empty and the new commit holds c2.txt.',gitc('log','--format=%s','--name-only'))]),
        cp('new-before','Move the patch to a new commit before the original one.',H3,S(patch,K('N'),prompt('split-before'),wait(1)),
           [('log','The new commit precedes second in the history.',repo('log')),
            ('changed-files','The original commit is empty and the new commit holds c2.txt.',gitc('log','--format=%s','--name-only'))]),
    ]))
    return W
