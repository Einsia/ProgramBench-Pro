'''Episode specifications for rebase. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H3 = history('first', 'second', 'third')
TAGGED = S(H3, git('tag', 'v1'))
DIVERGE = S(commit('base', {'f.txt': text('a')}), git('checkout', '-q', '-b', 'feature'),
            commit('f-one', {'f1.txt': text('one')}), git('checkout', '-q', 'main'), commit('m-one', {'m1.txt': text('one')}))
STATUSB = ('status', '--porcelain', '-b')


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-rebase-interactive-branch', 'rebase', DIVERGE,
             'Start an interactive rebase of the checked-out branch main onto the branch feature.',
             S(K('3', 'j', 'r'), wait(0.5), K('i'), wait(2)),
             [('status', 'No branch is checked out because the rebase has stopped with HEAD on the commit f-one.', gitc(*STATUSB)),
              ('log', 'HEAD is on the commit f-one above the commit base.', gitc('log', '--format=%s')),
              ('banner', 'The bottom line says that a rebase is in progress.', scr('banner'))],
             'The bottom line shows that a rebase is in progress, and the commits panel lists the pending todo pick m-one above the commits f-one and base.',
             bind={'log': ['status'], 'banner': ['status']}),
    ]
