'''Episode specifications for branches, commits, reflog, stash, tags. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H3 = history('first', 'second', 'third')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
STASHED = S(history('first', 'second'), put({'c1.txt': text('content 1', 'first', 'x')}),
            git('stash', 'push', '-q', '-m', 'wip'))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def popup_cp(cid, goal, fixture, keys, what, check):
    return cp(cid, goal, fixture, keys,
              [('popup', what, scr('popup')), ('same', 'Opening it changed nothing in the repository.', check)],
              requires={'same': ['popup']})


def build():
    W = []

    W.append(program('tag-prompt', 'tags', None, [
        popup_cp('open', 'Open the tag prompt on the newest commit.', H3, K('4', 'T'),
                 'A prompt with a field for the tag name and a field for the tag description is shown.', repo('tags', 'log')),
    ]))

    W.append(program('stash-file-checkout', 'stash', None, [
        cp('go', 'Open the files of the stash and check the file c1.txt out of it.', STASHED, S(K('5', 'Enter', 'c'), wait(1)),
           [('status', 'c1.txt holds the stashed change and is staged.', repo('status')),
            ('diff', 'The staged change of c1.txt is the stashed one.', gitc('diff', '--cached')),
            ('stash', 'The stash entry is kept.', repo('stash'))],
           requires={'diff': ['status'], 'stash': ['status']}),
    ]))

    W.append(program('reflog-detach', 'reflog', None, [
        cp('go', 'Check out the commit of the second reflog entry as a detached head.', H3,
           S(K('4', ']', 'j', 'Space', 'd'), wait(1)),
           [('status', 'No branch is checked out.', gitc(*STATUSB)),
            ('head', 'HEAD is detached at the second commit.', repo('head')),
            ('main', 'The branch main still points at the third commit.', gitc('log', '--format=%s', '-n', '1', 'main'))],
           requires={'head': ['status'], 'main': ['status']}),
    ]))

    W.append(program('range-fixup', 'commits', None, [
        popup_cp('menu', 'Select the two newest commits and open the fixup menu.', H5, K('4', 'v', 'j', 'f'),
                 'A menu offers to fix up the selected commits or to fix them up and use their message, and explains the fixup.',
                 repo('status', 'log')),
        cp('go', 'Select the two newest commits and fix them up into the commit below them.', H5,
           S(K('4', 'v', 'j', 'f'), wait(0.5), K('Enter'), wait(1)),
           [('log', 'The three oldest commits remain.', repo('log')),
            ('files', 'The newest remaining commit holds the files of all five commits.', gitc(*FILES)),
            ('message', 'The newest remaining commit keeps its own message only.', gitc('log', '-1', '--format=%B'))],
           requires={'files': ['log'], 'message': ['log']}),
    ]))

    W.append(program('detached-branch', 'branches', None, [
        cp('create', 'Check out the second commit as a detached head and then create the branch fromdet from the branches panel.',
           H3, S(K('4', 'j', 'Space', 'Enter'), wait(1), K('3', 'n', 'Control+U'), prompt('fromdet'), wait(1)),
           [('head', 'The checked-out branch is fromdet.', repo('head', 'branches')),
            ('log', 'The history of fromdet ends with the second and first commits.', gitc('log', '--format=%s', '-n', '3'))]),
    ]))
    return W
