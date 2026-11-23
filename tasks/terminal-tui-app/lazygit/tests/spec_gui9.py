'''Episode specifications for commits. Fixtures, actions and checks use the documented runtime channels.'''
from spec_base import *  # noqa: F401,F403

H2 = history('first', 'second')
H3 = history('first', 'second', 'third')
DIRTY = S(H2, put({'c1.txt': text('content 1', 'first', 'extra'), 'new.txt': text('new file')}))
STAGED = S(H2, put({'c1.txt': text('content 1', 'first', 'extra')}), git('add', '.'))


def goal(key_, feature, fixture, statement, keys, checks, acceptance, bind=None):
    claims = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    names = ['done'] if len(claims) == 1 else ['done-%d' % i for i in range(1, len(claims) + 1)]
    requires = dict({name: [c[0] for c in checks] for name in names}, **(bind or {}))
    return gui(key_, feature, fixture, [step('go', statement, keys, checks, acceptance=claims, requires=requires)])


def build():
    return [
        goal('gui-commit-without-hook', 'commits', STAGED,
             'Commit the staged change without running the pre-commit hook. The fresh message is prefilled with `WIP`; '
             'append `nohook msg` so the complete subject is `WIPnohook msg`.',
             S(K('2', 'w'), wait(0.5), prompt('nohook msg'), wait(1)),
             [('log', 'A new commit whose subject is the prefilled text followed by nohook msg is on top of the history.', repo('log')),
              ('status', 'The working tree is clean.', repo('status'))],
             'The commits panel lists the new commit on top of the two earlier commits and the files panel shows no changes.',
             bind={'status': ['log']}),
    ]
