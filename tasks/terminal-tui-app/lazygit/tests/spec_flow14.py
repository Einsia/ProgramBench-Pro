'''Episode specifications for clipboard, menus. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
TAGGED = S(H3, git('tag', 'v1'))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))
NESTED = S(H2, put({'d/e.txt': text('x'), 'd/f.txt': text('y'), 'top.txt': text('t')}))
BODY = S(H2, put({'c3.txt': text('content 3', 'third')}), git('add', '.'), git('commit', '-q', '-m', 'with body', '-m', 'body line'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('clipboard-commit', 'clipboard', None, [
        cp('message', 'Copy the full message of the newest commit, which has a subject and a body, with the message entry of the copy menu.',
           BODY, K('4', 'y', 'm'),
           [('text', 'The clipboard holds the subject, a blank line and the body of the newest commit, copied once.', clip())]),
        cp('body', 'Copy only the body of the newest commit, which has a subject and a body, with the body entry of the copy menu.',
           BODY, K('4', 'y', 'b'),
           [('text', 'The clipboard holds only the body of the newest commit, copied once.', clip())]),
        cp('author', 'Copy the author of the newest commit with the author entry of the copy menu.', H3, K('4', 'y', 'a'),
           [('text', 'The clipboard holds the author name and email address, copied once.', clip())]),
        cp('tags', 'Copy the tags of the newest commit with the tags entry of the copy menu.', TAGGED, K('4', 'y', 't'),
           [('text', 'The clipboard holds the tag v1, copied once.', clip())]),
        cp('diff', 'Copy the diff of the newest commit with the diff entry of the copy menu.', H3, K('4', 'y', 'd'),
           [('text', 'The clipboard holds the header, the message and the diff of the newest commit, copied once.', clip(scrub=True))]),
    ]))

    W.append(program('clipboard-file', 'clipboard', None, [
        cp('name', 'Copy the name of the selected file with the file name entry of the copy menu.', DIRTY, K('2', 'j', 'y', 'n'),
           [('text', 'The clipboard holds the file name c1.txt, copied once.', clip())]),
        cp('relative', 'Copy the relative path of the file e.txt in the directory d with the relative path entry of the copy menu.',
           NESTED, K('2', 'j', 'j', 'y', 'p'),
           [('text', 'The clipboard holds the path d/e.txt of the file below the workspace, copied once.', clip())]),
        cp('nested-name', 'Copy the name of the file e.txt in the directory d with the file name entry of the copy menu.',
           NESTED, K('2', 'j', 'j', 'y', 'n'),
           [('text', 'The clipboard holds only the file name e.txt without its directory, copied once.', clip())]),
        cp('absolute', 'Copy the absolute path of the selected file with the absolute path entry of the copy menu.', DIRTY,
           K('2', 'j', 'y', 'P'),
           [('text', 'The clipboard holds the absolute path of c1.txt in the workspace, copied once.', clip())]),
        cp('diff', 'Copy the diff of the selected file with the diff entry of the copy menu.', DIRTY, K('2', 'j', 'y', 's'),
           [('text', 'The clipboard holds the unstaged diff of c1.txt, copied once.', clip(scrub=True))]),
    ]))


    W.append(program('menu-popups-5', 'menus', None, [
        popup_cp('rebase-remote', 'Open the rebase menu for a remote branch while main is checked out.', REMBR, K('3', ']', 'Enter', 'j', 'r'),
                 'A menu offers a simple and an interactive rebase onto the remote branch and a rebase onto the remote base branch.',
                 repo('status', 'log')),
    ]))
    return W
