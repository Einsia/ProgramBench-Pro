'''Episode specifications for files, navigation, search. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))


def cp(cid, goal, fixture, keys, checks, requires=None):
    return step(cid, goal, S(scenario(fixture), keys, wait(0.5)), checks, requires=requires)


def build():
    W = []

    W.append(program('search-matches', 'search', None, [
        cp('previous', 'Search the commits panel for the text c-, move to the next match twice and then back to the previous one.', H5,
           S(K('4', '/'), prompt('c-'), K('n', 'n', 'N')),
           [('selected', 'The second match, the commit c-four, is selected.', pan(4, 'selected')),
            ('hints', 'The bottom line reports match 2 of 5 and offers next, previous and exit.', scr('hints')),
            ('same', 'The repository is unchanged.', repo('status', 'log'))],
           requires={'hints': ['selected'], 'same': ['selected']}),
    ]))

    W.append(program('status-filter-more', 'files', None, [
        cp('untracked', 'Show only the untracked files with the fourth entry of the status filter menu.', DIRTY,
           K('2', 'Control+B', 'j', 'j', 'j', 'Enter'),
           [('panel', 'The files panel lists the untracked file new.txt and not the modified file c1.txt.', pan(2)),
            ('same', 'The repository is unchanged: c1.txt is modified and new.txt untracked.', repo('status'))],
           requires={'same': ['panel']}),
    ]))

    W.append(program('focus-main', 'navigation', None, [
        cp('files', 'Press 0 in the files panel to move the focus to the main view on the right.', DIRTY, K('2', '0'),
           [('focus', 'The main view has the focus.', scr('focus')),
            ('same', 'The repository is unchanged.', repo('status'))],
           requires={'same': ['focus']}),
    ]))

    return W
