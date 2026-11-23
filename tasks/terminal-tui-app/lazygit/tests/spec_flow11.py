'''Episode specifications for bisect, clipboard, menus. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
TAGGED = S(H3, git('tag', 'v1'))
DIVERGE = S(commit('base', {'f.txt': text('a')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), git('checkout', '-q', 'main'), commit('m-one', {'m1.txt': text('one')}))
STATUSB = ('status', '--porcelain', '-b')
BISECT = S(K('4', 'b', 'b'), wait(1))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('clipboard-more', 'clipboard', None, [
        cp('tag', 'Copy the name of the selected tag to the clipboard.', TAGGED, K('3', ']', ']', 'Control+O'),
           [('text', 'The clipboard holds the name of the selected tag, copied once.', clip())]),
        cp('remote-branch', 'Copy the name of the selected remote branch to the clipboard.', REMBR,
           K('3', ']', 'Enter', 'j', 'Control+O'),
           [('text', 'The clipboard holds the remote branch with its remote name, copied once.', clip())]),
        cp('reflog', 'Copy the hash of the newest reflog entry to the clipboard.', H3, K('4', ']', 'Control+O'),
           [('text', 'The clipboard holds the full hash of the commit of that entry, copied once.', clip())]),
    ]))

    W.append(program('bisect-menus', 'bisect', None, [
        popup_cp('menu', 'Open the bisect menu after marking the newest commit as bad.', H5, S(BISECT, K('b')),
                 'A menu offers to mark the current commit as bad or good, to skip it or to reset the bisect and names the current commit.',
                 gitc('bisect', 'log')),
        popup_cp('reset', 'Choose the reset entry of the bisect menu.', H5, S(BISECT, K('b', 'r')),
                 'A confirmation asks whether to reset the bisect.', gitc('bisect', 'log')),
    ]))

    W.append(program('menu-popups-4', 'menus', None, [
        popup_cp('commit-files-copy', 'Open the copy menu in the files of the newest commit.', H3, K('4', 'Enter', 'y'),
                 'A menu offers to copy the file name, the relative or absolute path, a diff or the content of the selected file.',
                 repo('status', 'log')),
        popup_cp('reflog-checkout', 'Ask to check out the second entry of the reflog.', H3, K('4', ']', 'j', 'Space'),
                 'A menu offers to check out the commit of the entry as a detached head or to check out a branch.',
                 repo('status', 'log')),
    ]))

    return W
