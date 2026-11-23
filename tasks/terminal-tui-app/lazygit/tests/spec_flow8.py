'''Episode specifications for commits, remotes, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
REMBR = S(PUSHED, git('push', '-q', 'origin', 'main:remote-only'), git('fetch', '-q', 'origin'))
TAGP = S(PUSHED, git('tag', 'v1'))
WT = S(H2, git('worktree', 'add', '-q', '../wtx', '-b', 'wt-branch'))
FIXUP = S(H2, commit('fixup! second', {'c3.txt': text('fix')}))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')
REMOTES = ('for-each-ref', '--format=%(refname:short)', 'refs/remotes')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []


    W.append(program('autosquash', 'commits', None, [
        popup_cp('menu', 'Open the apply fixup commits menu while a fixup commit is the newest commit.', FIXUP, K('4', 'S'),
                 'A menu offers to apply the fixup commits in the current branch or above the selected commit and explains why the first entry is not available.',
                 repo('status', 'log')),
        popup_cp('disabled', 'Choose the first entry of the apply fixup commits menu.', FIXUP,
                 S(K('4', 'S'), wait(0.5), K('Enter'), wait(1)),
                 'The menu stays open and still explains why the first entry is not available.', repo('status', 'log')),
    ]))

    W.append(program('tag-push', 'tags', None, [
        popup_cp('prompt', 'Push the tag v1 from the tags tab.', TAGP, K('3', ']', ']', 'P'),
                 'A prompt asks for the remote to push the tag v1 to and suggests origin.', gitc('tag', '-l', remote='origin')),
    ]))

    W.append(program('remote-delete', 'remotes', None, [
        cp('remove', 'Remove the remote origin and confirm.', PUSHED, S(K('3', ']', 'd'), wait(0.5), K('Enter'), wait(1)),
           [('remotes', 'No remote is configured any more.', gitc('remote', '-v')),
            ('status', 'The branch main has no upstream any more.', gitc(*STATUSB))],
           requires={'remotes': ['status']}),
    ]))


    return W
