'''Episode specifications for files, search. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H5 = history('c-one', 'c-two', 'c-three', 'c-four', 'c-five')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-search-next-match', 'search', H5, 'Search the commits list for the text `c-` and move to the second match.',
             S(K('4', '/'), prompt('c-'), K('n')),
             [('selected', 'The commit c-four is selected.', pan(4, 'selected')),
              ('same', 'The repository is unchanged.', repo('status', 'log')),
              ('hints', 'The bottom line reports match 2 of 5 and offers next, previous and exit.', scr('hints'))],
             ['The commit c-four is selected in the commits panel.', 'The bottom line reports search match 2 of 5.'],
             bind={'same': ['selected'], 'hints': ['selected']}),
        goal('gui-filter-tracked', 'files', DIRTY, 'Show only the tracked files in the files panel.',
             K('2', 'Control+B', 'j', 'j', 'Enter'),
             [('panel', 'The files panel lists only c1.txt.', pan(2)),
              ('same', 'The repository is unchanged.', repo('status'))],
             'The files panel lists only c1.txt.',
             bind={'same': ['panel']}),
        goal('gui-amend-from-files', 'files', STAGED,
             'Add the staged change to the newest commit from the files panel without creating a new commit.',
             S(K('2', 'A'), wait(0.5), K('Enter'), wait(1)),
             [('files', 'The newest commit now also holds the staged change to c1.txt.', gitc('show', '--stat', '--format=%s', 'HEAD')),
              ('log', 'The history still has the two commits.', repo('head', 'log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel still lists two commits and the files panel shows no changes.',
             bind={'log': ['files'], 'status': ['files']}),
    ]
