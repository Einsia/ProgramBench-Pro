'''Episode specifications for clipboard, menus, navigation. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
TOPIC = S(H2, git('branch', 'topic'))
STASHED = S(H2, put({'c1.txt': text('content 1', 'first', 'x')}), git('stash', 'push', '-q', '-m', 'wip'))
NESTED = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
TAGGED = S(H3, git('tag', 'v1'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('clipboard-branch', 'clipboard', None, [
        cp('name', 'Copy the name of the selected branch to the clipboard.', TOPIC, K('3', 'j', 'Control+O'),
           [('text', 'The clipboard holds the name of the selected branch, copied once.', clip())]),
    ]))

    W.append(program('menu-popups-3', 'menus', None, [
        popup_cp('copy-commit', 'Open the copy menu of the commits panel.', H3, K('4', 'y'),
                 'A menu offers to copy the commit hash, subject, message, body, URL, diff, author or tags.', repo('status', 'log')),
        popup_cp('filtering', 'Open the filtering menu of the commits panel.', H3, K('4', 'Control+S'),
                 'A menu offers to filter by the current author, to enter a path or to enter an author.', repo('status', 'log')),
        popup_cp('recent-repos', 'Open the recent repositories menu from the status panel.', H2, K('1', 'Enter'),
                 'A menu of recent repositories is shown with nothing to choose but cancel.', repo('status', 'log')),
    ]))




    W.append(program('list-jumps', 'navigation', None, [
        cp('top', 'Move down two commits and then jump to the top of the commits list.', H3, K('4', 'j', 'j', '<'),
           [('selected', 'The newest commit, third, is selected.', pan(4, 'selected')),
            ('same', 'The repository is unchanged.', repo('status', 'log'))],
           requires={'same': ['selected']}),
    ]))

    W.append(program('panel-focus', 'navigation', None, [
        cp('tab', 'Press tab to move the focus to the next panel.', H2, K('Tab'),
           [('focus', 'The branches panel has the focus.', scr('focus')),
            ('same', 'The repository is unchanged.', repo('status', 'log'))],
           requires={'same': ['focus']}),
    ]))
    return W
