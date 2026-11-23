'''Shared builders for the lazygit specification : fixture steps, key helpers, check constructors and the
episode, checkpoint and budget builders. The family modules (spec_*.py) and specification.py use only these.

A fixture is a list of runtime setup steps (see the setup op of the runtime): files, whitelisted git commands and
local bare remotes. Commit dates are the runtime's fixed clock (one minute per step), so a fixture always yields the
same history. A scenario inside a program episode is `scenario(steps)`: reset to an empty repository, then run the
steps; scenarios never depend on each other.
'''
from __future__ import annotations

BASE = 1704110400  # 2024-01-01T12:00:00Z, the runtime's fixture clock


# -- flatten ---------------------------------------------------------------------------------------------------
def S(*parts):
    '''Flatten a mix of step dicts and step lists into one list.'''
    out = []
    for p in parts:
        if isinstance(p, list):
            out.extend(p)
        else:
            out.append(p)
    return out


# -- setup steps ----------------------------------------------------------------------------------------------
def put(mapping, repo=None):
    '''Fixture files; with repo the paths are relative to that repository directory of the workspace.'''
    if repo:
        mapping = {repo.strip('/') + '/' + name: value for name, value in mapping.items()}
    return {'files': mapping}


def git(*argv, repo=None, date=None):
    step = {'git': list(argv)}
    if repo:
        step['repo'] = repo
    if date is not None:
        step['date'] = date
    return step


def bare(name):
    return {'bare': name}


def commit(message, mapping=None, repo=None):
    '''Write files (optional), stage everything and commit.'''
    out = []
    if mapping:
        out.append(put(mapping, repo))
    out.append(git('add', '.', repo=repo))
    out.append(git('commit', '-q', '-m', message, repo=repo))
    return out


def text(*lines):
    return ''.join(line + chr(10) for line in lines)


def scenario(steps):
    '''A fresh empty repository, then the steps (the runtime restarts the application after the steps).'''
    return [{'reset': True}, {'setup': S(steps)}]


# -- key helpers ----------------------------------------------------------------------------------------------
def key(k):
    return {'key': k}


def K(*names):
    '''One key step per name (each key settles before the next one, so no input is dropped).'''
    return [key(n) for n in names]


def typ(t):
    return {'type': t}


def wait(seconds=0.5):
    return {'wait': seconds}


def restart():
    return {'restart': True}


def down(n=1):
    return K(*['j'] * n)


def up(n=1):
    return K(*['k'] * n)


def to_panel(number, down_n=0):
    '''Focus panel 1-5 and move down n items.'''
    return K(str(number)) + down(down_n)


def prompt(value):
    '''Type into the open prompt and confirm it.'''
    return [typ(value), key('Enter')]


# -- check constructors ----------------------------------------------------------------------------------------
def repo(*parts, **kw):
    '''The repository state: head, branches, log, status, stash, tags, reflog, remotes, worktrees (default head, branches,
    log, status). Options: repo (directory of a nested repository), remote (a local bare remote), rev, all, author.'''
    check = dict(kind='repo', **kw)
    if parts:
        check['parts'] = list(parts)
    return check


def gitc(*argv, **kw):
    return dict(kind='git', argv=list(argv), **kw)


def tree(path='/workspace', action='tree', **kw):
    return dict(kind='tree', path=path, action=action, **kw)


def listing(path='/workspace', **kw):
    return tree(path, 'list', **kw)


def state(**kw):
    return dict(kind='state', **kw)


def clip(**kw):
    return dict(kind='clipboard', **kw)


def cli(option):
    return dict(kind='cli', option=option)


def scr(fact, **kw):
    return dict(kind='screen', fact=fact, **kw)


def pan(number, field='items'):
    return scr('panel', number=number, field=field)


# -- episode and checkpoint builders --------------------------------------------------------------------------
def step(cid, goal, steps, checks=(), *, depends=(), lifecycle=None, acceptance=None, requires=None):
    cp = {'id': cid, 'goal': goal, 'steps': list(steps), '_checks': list(checks), 'depends_on': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    if acceptance is not None:
        cp['_acceptance'] = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    if requires:
        cp['_requires'] = requires
    return cp


def _assertions(wf, cp):
    out = []
    acc = cp.get('_acceptance', []) or []
    for i, text_ in enumerate(acc):
        suffix = 'done' if len(acc) == 1 else f'done-{i + 1}'
        out.append({'id': f'{wf}/{cp["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent',
                    'requirement': text_})
    for suffix, requirement, check in cp['_checks']:
        out.append({'id': f'{wf}/{cp["id"]}/{suffix}', 'channel': 'backend', 'method': 'program',
                    'requirement': requirement, 'check': check})
    return out


def _finalize(wf, checkpoints):
    ids = set()
    for cp in checkpoints:
        cp['assertions'] = _assertions(wf, cp)
        ids.update(a['id'] for a in cp['assertions'])
    for cp in checkpoints:
        for suffix, companions in (cp.pop('_requires', {}) or {}).items():
            point = next(a for a in cp['assertions'] if a['id'] == f'{wf}/{cp["id"]}/{suffix}')
            point['requires'] = [c if '/' in c else f'{wf}/{cp["id"]}/{c}' for c in companions]
            assert all(r in ids for r in point['requires']), (wf, cp['id'], point['requires'])
        cp.pop('_checks', None)
        cp.pop('_acceptance', None)
    return checkpoints


def _setup(fixtures):
    return [{'id': 'fixtures', 'op': 'steps', 'steps': S(fixtures)}] if fixtures else []


INITIAL = ('Fresh lazygit opened on the git repository prepared by the listed setup steps; an empty repository on '
           'the branch main when there are none.')


def program(key_, feature, fixtures, checkpoints):
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + list(cp.get('depends_on', []))
    return {'id': key_, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': _setup(fixtures), 'inputs': {}, 'checkpoints': _finalize(key_, checkpoints)}


SESSION = ('lazygit is showing the git repository of the workspace in its terminal interface: the left column holds '
           'the numbered panels Status [1], Files [2], Local branches [3], Commits [4] and Stash [5] (] and [ switch '
           'the tabs of a panel, the number keys jump to a panel), the large view on the right shows the diff, log or '
           'content of the selected item, and the bottom line shows the keys of the focused panel. The key map of the '
           'reference is in the help response (reference_controls). The item you act on is the one drawn highlighted '
           'in the focused panel.')
EQUIV = ['Any key or sequence of keys that reaches the same lazygit action is equivalent (for example j or Down).']
FORBID = ['Do not use a shell, run external programs, or edit files outside lazygit.']


def gui(key_, feature, fixtures, checkpoints, session=SESSION):
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + list(cp.get('depends_on', []))
    n = len(checkpoints)
    return {'id': key_, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': _setup(fixtures), 'inputs': {}, 'session': session, 'allowed_equivalents': EQUIV,
            'forbidden_bypasses': FORBID,
            # Calibrated on the standard answer driven by the real evaluator model: its peak use of any episode
            # was 45 calls and about 365,000 tokens (an evaluator retrying a malformed call), which these budgets
            # keep below 30%. The seconds also absorb one slow provider response: the evaluator estimates the
            # next step from wall time, so a short time budget closed operations after a single delayed reply.
            # Seconds scale with the checkpoint count (they drive the verifier timeout).
            'budget': {'calls': min(220, 130 + 30 * n), 'tokens': min(1_600_000, 1_000_000 + 200_000 * n),
                       'seconds': min(1500, 600 + 120 * n)},
            'checkpoints': _finalize(key_, checkpoints)}


# -- common fixtures --------------------------------------------------------------------------------------------
def history(*subjects, repo=None):
    '''A linear history: one commit per subject, each adding a file named after it (c1.txt, c2.txt, ...).'''
    out = []
    for i, subject in enumerate(subjects, 1):
        out += commit(subject, {f'c{i}.txt': text(f'content {i}', subject)}, repo)
    return out
