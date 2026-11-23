'''Episode specifications for search, sync. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
ORIGIN = S(bare('origin'), git('remote', 'add', 'origin', '@remotes/origin'))
BEHIND = S(H3, ORIGIN, git('push', '-q', '-u', 'origin', 'main'), git('reset', '-q', '--hard', 'HEAD~1'))
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STATUSB = ('status', '--porcelain', '-b')


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-filter-files', 'search', DIRTY, 'Filter the files panel so that only files whose name contains `new` are listed.',
             S(K('2', '/'), prompt('new')),
             [('items', 'The files panel lists only the file new.txt.', pan(2)),
              ('same', 'The repository is unchanged.', repo('status')),
              ('hints', 'The bottom line says that the list is filtered by new and offers to exit the filter mode.', scr('hints'))],
             ['The files panel lists only new.txt.', 'The bottom line says that the list is filtered by new.'],
             bind={'same': ['items'], 'hints': ['items']}),
        goal('gui-search-commits', 'search', H3, 'Search the commits list for the text `second` so that the matching commit is selected.',
             S(K('4', '/'), prompt('second')),
             [('selected', 'The commit second is selected.', pan(4, 'selected')),
              ('same', 'The repository is unchanged.', repo('status', 'log')),
              ('hints', 'The bottom line says that one match was found and offers next, previous and exit.', scr('hints'))],
             ['The commits panel has the commit second selected.', 'The bottom line reports one match for second.'],
             bind={'same': ['selected'], 'hints': ['selected']}),
        goal('gui-upstream-hard-reset', 'sync', BEHIND, 'Hard reset the current branch to its upstream.',
             K('2', 'g', 'h'),
             [('log', 'main points at the third commit again.', repo('head', 'log')),
              ('status', 'main is level with its upstream.', gitc(*STATUSB))],
             ['The commits panel lists third as the newest commit.', 'The status panel shows main as up to date with its upstream.'],
             bind={'status': ['log']}),
    ]
