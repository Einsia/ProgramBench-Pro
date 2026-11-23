'''Reviewed user goals, acceptance conditions, deterministic recipes and program checks for lazygit 0.66.2.

Program episodes carry the broad backend coverage; GUI episodes are user goals judged by the evaluator with
backend companions. Every checkpoint is a deterministic key sequence through the runtime, then checks on the
repository (git channel), the working tree, lazygit's state file, the clipboard and layout-independent semantic
screen facts. Goals are authored here, never from a recorded trace. The frozen reference recording defines the exact
expected values; requirement text describes the behavior and must also hold for an equivalent reimplementation.
'''
from spec_base import *  # noqa: F401,F403

# Two commits and two uncommitted changes: c1.txt modified (unstaged) and new.txt untracked.
DIRTY = S(history('first commit', 'second commit'),
          put({'c1.txt': text('content 1', 'first commit', 'extra line'), 'new.txt': text('new file')}))
CLEAN = history('first commit', 'second commit')


def build():
    W = []

    W.append(program('initial-empty', 'startup', None, [
        step('screen', 'Observe the interface of a freshly created empty repository.', [],
             [('files', 'No changed files are listed.', pan(2)),
              ('branch', 'The only branch is main and it is the current one.', pan(3)),
              ('commits', 'There are no commits.', pan(4)),
              ('focus', 'The files panel has the focus.', scr('focus')),
              ('repo', 'The repository is on the branch main with no history.', repo())],
             requires={'files': ['branch'], 'commits': ['branch']}),
    ]))

    W.append(program('stage-unstage', 'staging', DIRTY, [
        step('stage-modified', 'Stage the modified file c1.txt.', S(to_panel(2, 1), K('Space')),
             [('panel', 'The files panel lists c1.txt as staged and new.txt as untracked.', pan(2))]),
        step('unstage', 'Unstage c1.txt again.', K('Space'),
             [('status', 'Nothing is staged any more.', repo('status'))], depends=['stage-modified']),
        step('stage-all', 'Stage all changes at once.', K('a'),
             [('status', 'Both c1.txt and new.txt are staged.', repo('status'))], depends=['unstage']),
    ]))

    W.append(program('commit-from-interface', 'commits', DIRTY, [
        step('commit', 'Stage everything and commit it with the message "third commit".',
             S(to_panel(2), K('a', 'c'), prompt('third commit'), wait(0.5)),
             [('log', 'The new commit has the given message, the right author and the previous head as parent.',
               repo('log', author=True)),
              ('status', 'The working tree is clean after the commit.', repo('status')),
              ('panel', 'The commits panel lists three commits with the new one first.', pan(4))]),
    ]))

    W.append(program('new-branch', 'branches', CLEAN, [
        step('create', 'Create the branch feature-x from the current commit and switch to it.',
             S(to_panel(3), K('n'), prompt('feature-x'), wait(0.5)),
             [('head', 'The checked-out branch is feature-x.', repo('head', 'branches')),
              ('panel', 'The branches panel lists both branches.', pan(3))]),
        step('previous', 'Switch back to the previous branch.', K('-'),
             [('head', 'The checked-out branch is main again.', repo('head'))], depends=['create']),
    ]))

    W.append(gui('gui-stage-file', 'staging', DIRTY, [
        step('stage', 'Stage the file c1.txt so that it is part of the next commit; new.txt stays untracked.',
             S(to_panel(2, 1), K('Space')),
             [('status', 'Only c1.txt is staged.', repo('status'))],
             acceptance='c1.txt is listed as staged in the files panel.',
             requires={'done': ['status']}),
    ]))
    from spec_core import build as core
    from spec_more import build as more
    from spec_gui import build as goals
    W.extend(core())
    W.extend(more())
    W.extend(goals())
    from spec_misc import build as misc
    from spec_flow import build as flow
    W.extend(misc())
    W.extend(flow())
    from spec_flow2 import build as flow2
    W.extend(flow2())
    from spec_menus import build as menus
    W.extend(menus())
    from spec_flow3 import build as flow3
    W.extend(flow3())
    from spec_flow4 import build as flow4
    W.extend(flow4())
    from spec_flow5 import build as flow5
    W.extend(flow5())
    from spec_flow6 import build as flow6
    W.extend(flow6())
    from spec_flow8 import build as flow8
    W.extend(flow8())
    from spec_gui3 import build as gui3
    W.extend(gui3())
    from spec_flow9 import build as flow9
    W.extend(flow9())
    from spec_gui4 import build as gui4
    W.extend(gui4())
    from spec_flow10 import build as flow10
    W.extend(flow10())
    from spec_gui5 import build as gui5
    W.extend(gui5())
    from spec_flow11 import build as flow11
    W.extend(flow11())
    from spec_gui6 import build as gui6
    W.extend(gui6())
    from spec_flow12 import build as flow12
    W.extend(flow12())
    from spec_gui7 import build as gui7
    W.extend(gui7())
    from spec_flow13 import build as flow13
    W.extend(flow13())
    from spec_gui8 import build as gui8
    W.extend(gui8())
    from spec_flow14 import build as flow14
    W.extend(flow14())
    from spec_gui9 import build as gui9
    W.extend(gui9())
    from spec_flow15 import build as flow15
    W.extend(flow15())
    from spec_gui2 import build as gui2
    W.extend(gui2())
    from spec_gui10 import build as gui10
    W.extend(gui10())
    from spec_gui11 import build as gui11
    W.extend(gui11())
    from spec_extended import build as extended
    W.extend(extended())
    from spec_conflict_paths import build as conflict_paths
    W.extend(conflict_paths())
    from spec_file_cases import build as file_cases
    W.extend(file_cases())
    from spec_views_messages import build as views_messages
    W.extend(views_messages())
    from spec_remaining import build as remaining
    W.extend(remaining())
    return W
