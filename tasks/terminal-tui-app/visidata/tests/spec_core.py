'''Builders and fixture helpers shared by the visidata episode modules.'''
import base64
import csv
import io
import json

T = 1704067200  # fixed modification time (2024-01-01) of every placed fixture
NL, TAB, CR, Q = chr(10), chr(9), chr(13), chr(34)
SEP = chr(0x241f)  # the symbol VisiData writes before the direction in logged sort inputs


def f(data, mtime=T):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return {'base64': base64.b64encode(data).decode(), 'mtime': mtime}


def d(mtime=T):
    return {'dir': True, 'mtime': mtime}


def csv_text(rows, delimiter=','):
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=delimiter, lineterminator=NL).writerows(rows)
    return buffer.getvalue()


def plain(rows, delimiter=TAB):
    '''Rows joined by a delimiter, without any quoting.'''
    return ''.join(delimiter.join(row) + NL for row in rows)


SAMPLE_ROWS = [['id', 'name', 'city', 'amount', 'date'], ['1', 'alice', 'Paris', '10.5', '2024-01-03'],
               ['2', 'bob', 'Berlin', '3', '2024-02-10'], ['3', 'carol', 'Paris', '7.25', '2024-01-20'],
               ['4', 'dave', 'Rome', '', '2024-03-01'], ['5', 'erin', 'Berlin', '12', '2023-12-31']]
PETS_ROWS = [['owner', 'pet'], ['1', 'cat'], ['1', 'dog'], ['2', 'fish'], ['9', 'bird']]
SAMPLE = csv_text(SAMPLE_ROWS)


# -- command logs (.vdj): the replay input of the batch channel -------------------------------------------------
def entry(longname, col='', row='', inp='', sheet='sample'):
    return {'sheet': sheet, 'col': col, 'row': row, 'longname': longname, 'input': inp, 'keystrokes': '',
            'comment': '', 'replayable': True}


def open_entry(name):
    return {'sheet': None, 'col': None, 'row': None, 'longname': 'open-file', 'input': name, 'keystrokes': 'o',
            'comment': None, 'replayable': True}


def vdj(entries, opens='sample.csv'):
    rows = ([open_entry(opens)] if opens else []) + list(entries)
    return '#!/usr/bin/env -S vd -p' + NL + '# VisiData v3.4' + NL + ''.join(json.dumps(e) + NL for e in rows)


# -- check constructors -------------------------------------------------------------------------------------------
def file_(path, mode='text', **kw):
    return dict({'kind': 'file', 'path': '/workspace/' + path, 'as': mode}, **kw)


def listing(path='/workspace', **kw):
    return dict(kind='tree', action='list', path=path, **kw)


def subtree(path='/workspace', **kw):
    return dict(kind='tree', action='tree', path=path, **kw)


def outcome(**kw):
    return dict(kind='run', **kw)


def history(**kw):
    return dict(kind='state', file='input_history', **kw)


def scr(fact, **kw):
    return dict(kind='screen', fact=fact, **kw)


# -- steps ----------------------------------------------------------------------------------------------------------
def batch(args, out=None):
    return {'cli': ['-b'] + list(args) + (['-o', out] if out else [])}


def key(name):
    return {'key': name}


def keys(*names):
    return {'keys': list(names)}


def typ(text):
    return {'type': text}


def ask(opener, text=None):
    return {'ask': opener, 'text': text}


def wait(seconds=0.5):
    return {'wait': seconds}


# -- episode and checkpoint builders -----------------------------------------------------------------------------
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
    for i, text in enumerate(acc):
        suffix = 'done' if len(acc) == 1 else 'done-%d' % (i + 1)
        out.append({'id': '%s/%s/%s' % (wf, cp['id'], suffix), 'channel': 'frontend', 'method': 'agent',
                    'requirement': text})
    for suffix, requirement, check in cp['_checks']:
        out.append({'id': '%s/%s/%s' % (wf, cp['id'], suffix), 'channel': 'backend', 'method': 'program',
                    'requirement': requirement, 'check': check})
    return out


def _finalize(wf, checkpoints):
    ids = set()
    for cp in checkpoints:
        cp['assertions'] = _assertions(wf, cp)
        ids.update(a['id'] for a in cp['assertions'])
    for cp in checkpoints:
        for suffix, companions in (cp.pop('_requires', {}) or {}).items():
            point = next(a for a in cp['assertions'] if a['id'] == '%s/%s/%s' % (wf, cp['id'], suffix))
            point['requires'] = [c if '/' in c else '%s/%s/%s' % (wf, cp['id'], c) for c in companions]
            assert all(r in ids for r in point['requires']), (wf, cp['id'], point['requires'])
        cp.pop('_checks', None)
        cp.pop('_acceptance', None)
    return checkpoints


def _setup(fixtures):
    return [{'id': 'fixtures', 'op': 'place', 'files': fixtures}] if fixtures else []


INITIAL = 'Fresh VisiData showing the directory sheet of a workspace prepared with the listed fixtures.'


def program(key_, feature, fixtures, checkpoints):
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + list(cp.get('depends_on', []))
    return {'id': key_, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': _setup(fixtures), 'inputs': {}, 'checkpoints': _finalize(key_, checkpoints)}


SESSION = ('VisiData is showing the directory sheet of the workspace, a table with one row per file. Open data files '
           'with the o key and a file name, and use the keys and commands of the reference (listed in the help '
           'response under reference_controls) to reach each goal. The cursor row is drawn in reverse video, the '
           'header of the column at the cursor is drawn in reverse video as well, selected rows start with a bullet, '
           'and the status line at the bottom names the open sheets and counts the rows. Equivalent keys, menu '
           'entries and command names (Space opens the command prompt) are accepted.')
EQUIV = ['Any key, menu entry or command name that reaches the same VisiData action is equivalent.']
FORBID = ['Do not run shell or Python code, and do not edit files outside the application.']


def gui(key_, feature, fixtures, checkpoints, session=SESSION):
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + list(cp.get('depends_on', []))
    n = len(checkpoints)
    return {'id': key_, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': _setup(fixtures), 'inputs': {}, 'session': session, 'allowed_equivalents': EQUIV,
            'forbidden_bypasses': FORBID,
            'budget': {'calls': min(160, 130 + 30 * n), 'tokens': min(1_500_000, 1_000_000 + 250_000 * n),
                       'seconds': min(1800, 720 + 240 * n)},
            'checkpoints': _finalize(key_, checkpoints)}
