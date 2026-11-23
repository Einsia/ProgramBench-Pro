"""Shared builders of the taskwarrior-tui specification: fixtures, recipe steps, checks and episode envelopes.

Fixture tasks are plain Taskwarrior JSON (the format `task export` prints and `task import` reads) with fixed UUIDs
and dates; the application's clock stays at 2026-05-13 10:00:00 UTC, so relative dates are deterministic. Tasks are
identified by their (unique) description. Recipes are deterministic key sequences through the runtime's terminal
operations; checks read `task export` projections and semantic screen facts (see checks.py).
"""
from __future__ import annotations

NOW = '20260513T100000Z'


def U(n):
    return f'{n:08d}-0000-4000-8000-{n:012d}'


def T(n, description, status='pending', entry='20260501T080000Z', **fields):
    """One fixture task in Taskwarrior's JSON form."""
    task = {'uuid': U(n), 'description': description, 'status': status, 'entry': entry}
    for name, value in fields.items():
        if name == 'depends':
            value = [U(v) if isinstance(v, int) else v for v in value]
        if name == 'notes':
            name, value = 'annotations', [{'entry': e, 'description': d} for e, d in value]
        task[name] = value
    if status in ('completed', 'deleted') and 'end' not in task:
        task['end'] = '20260512T090000Z'
    return task


# -- recipe steps ----------------------------------------------------------------------------------------------------
def key(k):
    return {'key': k}


def K(*names):
    return [{'key': k} for k in names]


def typ(text):
    return {'type': text}


def wait(seconds=0.5):
    return {'wait': seconds}


def cmd(*args, stdin=None, keep=False):
    """Run the application's command line; keep=True records the result for a 'run' check."""
    step = {'task': list(args)}
    if stdin is not None:
        step['stdin'] = stdin
    if keep:
        step['keep'] = True
    return step


def ran(project='stdout', index=-1, **kw):
    """The recorded result of a kept command-line run of the episode."""
    return dict(kind='run', index=index, project=project, **kw)


def restart():
    return {'restart': True}


def S(*parts):
    """Flatten a mix of steps and step lists."""
    out = []
    for part in parts:
        if isinstance(part, list):
            out.extend(part)
        elif part is not None:
            out.append(part)
    return out


def prompt(opener, text=None, enter=True, clear=False):
    """Open a prompt with its key, optionally clear it, type text and confirm."""
    steps = [key(opener)]
    if clear:
        steps.append(key('Control+u'))
    if text:
        steps.append(typ(text))
    if enter:
        steps.append(key('Enter'))
    return steps


def add(description, attributes='', opener='a'):
    """The add (or log) prompt: the description goes between the automatic quotes, attributes after them."""
    steps = [key(opener), typ(description)]
    if attributes:
        steps += [key('End'), typ(' ' + attributes)]
    return steps + [key('Enter')]


def jump(task_id):
    return [key(':'), typ(str(task_id)), key('Enter')]


def filt(text):
    """Replace the live filter and confirm it."""
    return [key('/'), key('Control+u')] + ([typ(text)] if text else []) + [key('Enter')]


def modify(text, clear=False):
    """The modify prompt (prefilled with the quoted description for one task): append text, or replace it all."""
    steps = [key('m')]
    if clear:
        steps.append(key('Control+u'))
    return steps + [typ(text), key('Enter')]


# -- checks ---------------------------------------------------------------------------------------------------------
def ex(tasks, *fields):
    """Projection of `task export`: the named tasks (descriptions) with the given fields."""
    return {'kind': 'export', 'tasks': list(tasks) if not isinstance(tasks, str) else [tasks],
            'fields': list(fields) or ['status']}


def summary():
    """Every task as [description, status]."""
    return {'kind': 'export', 'summary': True}


def count(**match):
    return {'kind': 'export', 'count': match}


def cli(*args, project='stdout'):
    return {'kind': 'cli', 'args': list(args), 'project': project}


def scr(fact, **kw):
    return dict(kind='screen', fact=fact, **kw)


# -- episode envelopes ----------------------------------------------------------------------------------------------
def step(cid, goal, steps, checks=(), *, depends=(), lifecycle=None, acceptance=None, requires=None):
    cp = {'id': cid, 'goal': goal, 'steps': list(steps), '_checks': list(checks), 'depends_on': list(depends)}
    if lifecycle:
        cp['lifecycle'] = lifecycle
    if acceptance is not None:
        cp['_acceptance'] = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    if requires:
        cp['_requires'] = requires
    return cp


def _assertions(wf, cp, names):
    out = []
    acc = cp.get('_acceptance', []) or []
    for i, text in enumerate(acc):
        suffix = 'done' if len(acc) == 1 else f'done-{i + 1}'
        out.append({'id': f'{wf}/{cp["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent',
                    'requirement': text})
    for suffix, requirement, check in cp['_checks']:
        check = dict(check)
        if check['kind'] == 'screen' and 'names' not in check and check['fact'] in NAMED_FACTS:
            check['names'] = sorted(names)
        out.append({'id': f'{wf}/{cp["id"]}/{suffix}', 'channel': 'backend', 'method': 'program',
                    'requirement': requirement, 'check': check})
    return out


NAMED_FACTS = ('rows', 'rowset', 'selected', 'marked', 'indicators', 'cells')


def _finalize(wf, checkpoints, names):
    ids = set()
    for cp in checkpoints:
        cp['assertions'] = _assertions(wf, cp, names)
        ids.update(a['id'] for a in cp['assertions'])
    for cp in checkpoints:
        for suffix, companions in (cp.pop('_requires', {}) or {}).items():
            point = next(a for a in cp['assertions'] if a['id'] == f'{wf}/{cp["id"]}/{suffix}')
            point['requires'] = [c if '/' in c else f'{wf}/{cp["id"]}/{c}' for c in companions]
            assert all(r in ids for r in point['requires']), (wf, cp['id'], point['requires'])
        cp.pop('_checks', None)
        cp.pop('_acceptance', None)
    return checkpoints


def fixture(tasks=(), config=(), commands=(), *, sid='fixture', before=None, reset=False):
    item = {'id': sid, 'op': 'fixture', 'tasks': list(tasks), 'config': [list(c) for c in config],
            'commands': [list(c) for c in commands]}
    if before:
        item['before'] = before
        item['reset'] = True
    elif reset:
        item['reset'] = True
    return item


def _names(setup, extra):
    names = set(extra or ())
    for item in setup:
        names.update(t['description'] for t in item.get('tasks', []))
    return names


INITIAL = ('Fresh taskwarrior-tui showing the "next" report of a Taskwarrior database prepared with the listed '
           'fixture tasks and settings.')


def program(key_, feature, setup, checkpoints, names=()):
    """A program episode. setup is a fixture item (or a list of items); per-checkpoint fixtures use before=cid."""
    setup = setup if isinstance(setup, list) else ([setup] if setup else [])
    ids = [s['id'] for s in setup]
    for cp in checkpoints:
        own = [f'setup:{s["id"]}' for s in setup if s.get('before') == cp['id']]
        common = [f'setup:{s["id"]}' for s in setup if not s.get('before')]
        cp['depends_on'] = common + own + list(cp.get('depends_on', []))
    assert len(set(ids)) == len(ids), key_
    return {'id': key_, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL, 'setup': setup,
            'inputs': {}, 'checkpoints': _finalize(key_, checkpoints, _names(setup, names))}


def cases(key_, feature, items, names=()):
    """A program episode whose checkpoints each start from their own fresh fixture.
    items: (cid, fixture kwargs dict, goal, steps, checks[, depends]); a fixture of None continues from the state the
    checkpoint before left (such a checkpoint declares that checkpoint in depends)."""
    setup, cps = [], []
    for item in items:
        cid, fx, goal, steps, chks = item[:5]
        if fx is not None:
            setup.append(fixture(sid='fx-' + cid, before=cid, **fx))
        cps.append(step(cid, goal, steps, chks, depends=item[5] if len(item) > 5 else ()))
    return program(key_, feature, setup, cps, names)


def fresh(checkpoints):
    """Every checkpoint after the first starts from a restarted application on the same data, so no popup, prompt
    text, filter, view, selection or mark carries over from the checkpoint before."""
    for cp in checkpoints[1:]:
        cp.setdefault('lifecycle', 'restart')
    return checkpoints


def bind(wf, bindings):
    """Companion points: {checkpoint id or 'checkpoint/point': ['checkpoint/point' of the positive points]}; a checkpoint
    id binds all its points."""
    for cp in wf['checkpoints']:
        for a in cp['assertions']:
            short = a['id'].split('/', 1)[1]
            companions = bindings.get(short) or bindings.get(cp['id'])
            if companions:
                a['requires'] = [c if c.count('/') == 2 else f'{wf["id"]}/{c}' for c in companions]
    ids = {a['id'] for cp in wf['checkpoints'] for a in cp['assertions']}
    for cp in wf['checkpoints']:
        for a in cp['assertions']:
            assert all(r in ids and r != a['id'] for r in a.get('requires', [])), (a['id'], a.get('requires'))
    return wf


SESSION = ('taskwarrior-tui, the terminal interface of Taskwarrior, is showing its task report (the "next" report) '
           'of a Taskwarrior database. Operate it with its keys and prompts; its key bindings are listed by its own '
           'help (the ? key). The prompts take Taskwarrior command-line syntax (for example project:Home, +tag, '
           'due:tomorrow), and the add, log and annotate prompts open with a pair of double quotes around the cursor '
           'for the description.')
EQUIV = ['Any key, prompt or menu that reaches the same taskwarrior-tui action is equivalent (for example j or Down; '
         'a filter typed in the filter prompt or chosen from history).']
FORBID = ['Do not use a shell, run external programs, or change the data outside the application.']


def budget(n):
    return {'calls': min(150, 120 + 30 * n), 'tokens': min(1_400_000, 1_000_000 + 200_000 * n),
            'seconds': min(1800, 600 + 240 * n)}


def gui(key_, feature, setup, checkpoints, names=(), session=SESSION):
    setup = setup if isinstance(setup, list) else ([setup] if setup else [])
    for cp in checkpoints:
        cp['depends_on'] = [f'setup:{s["id"]}' for s in setup if not s.get('before')] + list(cp.get('depends_on', []))
    n = len(checkpoints)
    return {'id': key_, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL, 'setup': setup,
            'inputs': {}, 'session': session, 'allowed_equivalents': EQUIV, 'forbidden_bypasses': FORBID,
            'budget': budget(n), 'checkpoints': _finalize(key_, checkpoints, _names(setup, names))}
