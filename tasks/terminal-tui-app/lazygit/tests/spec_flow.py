'''Episode specifications for bisect, clipboard, commits, conflicts, menus, search, submodules. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
EDITED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}))
FEATURE = S(commit('base', {'b.txt': text('base')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), commit('f-two', {'f2.txt': text('two')}),
            commit('f-three', {'f3.txt': text('three')}))
CONFLICT = S(commit('base', {'f.txt': text('a', 'b')}), git('checkout', '-q', '-b', 'feature'),
             commit('feat change', {'f.txt': text('a', 'feature side')}), git('checkout', '-q', 'main'),
             commit('main change', {'f.txt': text('a', 'main side')}))
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
PUSHED = S(H2, ORIGIN, git('push', '-q', '-u', 'origin', 'main'))
FETCHABLE = S(PUSHED, git('clone', '-q', '@remotes/origin', 'other'),
              commit('upstream change', {'u.txt': text('u')}, repo='other'),
              git('push', '-q', 'origin', 'main', repo='other'))
SUBREPO = S(put({'seed/s.txt': text('sub content')}), git('init', '-q', '-b', 'main', repo='seed'),
            git('add', '.', repo='seed'), git('commit', '-q', '-m', 'sub one', repo='seed'), bare('sub'),
            git('remote', 'add', 'origin', '@remotes/sub', repo='seed'),
            git('push', '-q', 'origin', 'main', repo='seed'))
SUBMOD = S(H2, SUBREPO, git('submodule', 'add', '@remotes/sub', 'sub1'), git('commit', '-q', '-m', 'add submodule'))
AUTHORED = S(H2, put({'c3.txt': text('content 3', 'third')}), git('add', '.'),
             git('commit', '-q', '-m', 'third', '--author=Grace Hopper <grace@example.com>'))
FILES = ('ls-tree', '-r', '--name-only', 'HEAD')
STATUSB = ('status', '--porcelain', '-b')
BAD5 = K('4', 'b', 'b')
GOOD1 = K('j', 'j', 'j', 'j', 'b', 'g')
GRACE = 'Grace Hopper <grace@example.com>'


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []


    W.append(program('bisect', 'bisect', None, [
        cp('bad', 'Start a bisect by marking the newest commit as bad.', H5, S(BAD5, wait(1)),
           [('log', 'The bisect log records the start and the bad commit.', gitc('bisect', 'log')),
            ('head', 'HEAD stays on the branch.', repo('head'))],
           requires={'head': ['log']}),
        cp('narrow', 'Mark the commit in the middle as bad to narrow the range.', H5,
           S(BAD5, GOOD1, K('b', 'b'), wait(1)),
           [('log', 'The bisect log records a second bad commit.', gitc('bisect', 'log')),
            ('head', 'HEAD moved to the remaining candidate.', repo('head'))]),
        cp('reset', 'Reset the bisect from the bisect menu.', H5, S(BAD5, GOOD1, K('b', 'r'), wait(1)),
           [('log', 'There is no bisect any more.', gitc('bisect', 'log')),
            ('head', 'HEAD is back on the branch.', repo('head'))]),
    ]))


    W.append(program('submodules', 'submodules', None, [
        cp('tab', 'Open the submodules tab of the files panel.', SUBMOD, S(K('2', ']', ']'), wait(1)),
           [('items', 'The submodules tab lists the submodule sub1.', pan(2)),
            ('hints', 'The bottom line offers the submodule actions.', scr('hints'))]),
        cp('enter', 'Enter the submodule sub1 from the submodules tab.', SUBMOD,
           S(K('2', ']', ']', 'Enter'), wait(1)),
           [('hints', 'The bottom line offers returning to the parent repository.', scr('hints'))]),
        cp('leave', 'Enter the submodule and return to the parent repository with Escape.', SUBMOD,
           S(K('2', ']', ']', 'Enter'), wait(1), K('Escape'), wait(1)),
           [('status', 'The status panel names the parent repository again.', pan(1)),
            ('hints', 'The bottom line shows the submodules tab actions again.', scr('hints'))]),
    ]))

    W.append(program('conflicts', 'conflicts', None, [
        cp('merge', 'Merge the branch feature into main so that the merge conflicts.', CONFLICT,
           S(K('3', 'j', 'M', 'm'), wait(1)),
           [('popup', 'A popup offers to view the conflicts or abort the merge.', scr('popup')),
            ('banner', 'The bottom line shows that a merge is in progress.', scr('banner'))]),
        step('abort', 'Abort the conflicting merge from the popup.', S(K('a'), wait(1)),
             [('status', 'The working tree is clean and no merge is in progress.', gitc(*STATUSB)),
              ('log', 'No merge commit was created.', repo('head', 'log'))],
             depends=['merge'], requires={'log': ['status']}),
        cp('pick', 'Resolve the conflict by picking the hunk of the current branch in the conflict view.', CONFLICT,
           S(K('3', 'j', 'M', 'm'), wait(1), K('Enter', 'Enter', 'Space'), wait(1)),
           [('index', 'The resolved file holds the main side and is staged.', gitc('show', ':f.txt')),
            ('popup', 'A popup asks whether to continue the merge.', scr('popup'))], requires={'index': ['popup']}),
    ]))

    W.append(program('filter-search', 'search', None, [
        cp('path-filter', 'Filter the commits by the path c2.txt from the filtering menu.', H3,
           S(K('4', 'Control+S', 'j', 'Enter'), prompt('c2.txt'), wait(1)),
           [('items', 'The selected commit that touches c2.txt is second.', scr('commit-subject')),
            ('banner', 'The bottom line names the active filter.', scr('banner'))]),
        cp('search', 'Search the commits for c- and jump to the third match.', H5,
           S(K('4', '/'), typ('c-'), K('Enter', 'n', 'n'), wait(0.5)),
           [('selected', 'The third match, c-three, is selected.', pan(4, 'selected')),
            ('hints', 'The bottom line shows the match counter.', scr('hints'))]),
        cp('filter-branches', 'Filter the branches list by the text top.', S(H2, git('branch', 'topic')),
           S(K('3', '/'), prompt('top'), wait(0.5)),
           [('items', 'Only the branch topic is listed.', pan(3))]),
    ]))

    W.append(program('commit-message', 'commits', None, [
        cp('reset-author', 'Reset the author of a commit made by someone else to the configured user.', AUTHORED,
           S(K('4', 'a', 'a'), wait(1)),
           [('author', 'The newest commit is authored by the configured user.', gitc('log', '-1', '--format=%an %ae')),
            ('log', 'The history keeps its commits.', repo('log', author=True))]),
    ]))


    W.append(program('range-ops', 'commits', None, [
        cp('squash', 'Select the two newest commits and squash them into the one below.', H5,
           S(K('4', 'v', 'j', 's', 'Enter'), wait(1)),
           [('log', 'The three oldest commits remain.', repo('log')),
            ('files', 'The remaining newest commit still holds the files of all five.', gitc(*FILES)),
              ('message', 'The complete messages distinguish squash from fixup.', gitc('log', '--format=%B'))], requires={'files': ['log', 'message']}),
    ]))


    W.append(program('clipboard-menu', 'clipboard', None, [
        cp('hash', 'Copy the full hash of the newest commit with the copy attribute menu.', H3,
           S(K('4', 'y', 'Enter'), wait(0.5)), [('text', 'The clipboard holds the full hash of the newest commit.', clip())]),
        cp('subject', 'Copy the subject of the newest commit with the copy attribute menu.', H3,
           S(K('4', 'y', 's'), wait(0.5)), [('text', 'The clipboard holds the subject of the newest commit.', clip())]),
    ]))

    W.append(program('menus', 'menus', None, [
        cp('patch', 'Add a commit file to the custom patch and open the patch options menu.', H3,
           S(K('4', 'Enter', 'Space', 'Escape', 'Control+P'), wait(0.5)),
           [('menu', 'The patch options menu lists the patch actions.', scr('popup')),
            ('banner', 'The bottom line shows that a patch is being built.', scr('banner'))]),
        cp('upstream', 'Open the upstream options menu of the current branch.', PUSHED, S(K('3', 'u'), wait(0.5)),
           [('menu', 'The upstream options menu lists the upstream actions.', scr('popup'))]),
    ]))
    return W
