"""Manifest constructors, fixtures helpers and recipe primitives shared by the calcurse specification modules.

Program episodes carry the broad backend coverage; GUI episodes are user goals judged by the evaluator with
backend companions. Every checkpoint is a deterministic key sequence or command-line run through the runtime, then
checks of calcurse's data and configuration files, command-line output and a few screen facts. The frozen
reference recording defines the exact expected values; requirement text describes the behaviour and must also hold
for an equivalent reimplementation.
"""
import hashlib
import re

DATA = '~/.local/share/calcurse'
CONF = '~/.config/calcurse'
APTS = DATA + '/apts'
TODO = DATA + '/todo'
NOTES = DATA + '/notes'
CONFFILE = CONF + '/conf'
KEYSFILE = CONF + '/keys'
TODAY = '03/18/2026'   # the runtime's frozen clock: Wednesday 18 March 2026, 09:30 UTC


def slug(text):
    return re.sub('[^a-z0-9]+', '-', text.lower()).strip('-')


def sha1(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()


# -- recipe steps --------------------------------------------------------------------------------------------
def K(key):
    return {'key': key}


def KS(*keys):
    return {'keys': list(keys)}


def TY(text):
    return {'type': text}


def W(seconds=0.5):
    return {'wait': seconds}


def CLI(*args):
    return {'cli': list(args)}


def S(*parts):
    """Flatten a mix of step dicts and step lists into one step list."""
    out = []
    for part in parts:
        if isinstance(part, list):
            out.extend(part)
        else:
            out.append(part)
    return out


def answer(text):
    """Type an answer into the status-bar prompt and confirm it with Enter (an empty answer is just Enter)."""
    return ([TY(text)] if text else []) + [K('Enter')]


SAVE = [K('s')]


# -- fixtures (files placed into the home directory before the application starts) ---------------------------
def home(apts=None, todo=None, notes=(), conf=None, keys=None, files=None):
    """A placement for the place operation. apts/todo are lists of data-file lines; notes are note texts (stored
    under their SHA1 name); conf is a dict of option -> value; files maps other home paths to their text."""
    out = {}
    if apts is not None:
        out[APTS] = ''.join(line + '\n' for line in apts)
    if todo is not None:
        out[TODO] = ''.join(line + '\n' for line in todo)
    for text in notes:
        out[NOTES + '/' + sha1(text)] = text
    if conf is not None:
        out[CONFFILE] = ''.join(f'{k}={v}\n' for k, v in conf.items())
    if keys is not None:
        out[KEYSFILE] = keys
    out.update(files or {})
    return out


# -- check constructors ----------------------------------------------------------------------------------------
def file(path, mode='lines', **kw):
    return dict(kind='file', path=path, mode=mode, **kw)


def apts(mode='lines'):
    return file(APTS, mode)


def todos(mode='lines'):
    return file(TODO, mode)


def conf(*keys):
    return file(CONFFILE, 'conf', keys=list(keys))


def bindings(*actions):
    return file(KEYSFILE, 'keys', actions=list(actions))


def notes_dir(contents=True):
    return dict(kind='dir', path=NOTES, contents=contents, visible=True)


def cli(*args, part='stdout', **kw):
    return dict(kind='cli', args=list(args), part=part, **kw)


def scr(fact, **kw):
    return dict(kind='screen', fact=fact, **kw)


# -- episode / checkpoint builders -------------------------------------------------------------------------
def step(cid, goal, steps, checks=(), *, depends=(), acceptance=None, requires=None, lifecycle=None):
    """checks: (suffix, requirement, check) triples."""
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
        suffix = 'done' if len(acc) == 1 else f'done-{i + 1}'
        out.append({'id': f'{wf}/{cp["id"]}/{suffix}', 'channel': 'frontend', 'method': 'agent',
                    'requirement': text})
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


INITIAL = ('A fresh calcurse whose home directory holds the listed fixture files (an empty calendar when there are '
           'none); the clock reads Wednesday 18 March 2026, 09:30 UTC.')


def program(key, feature, fixtures, checkpoints, *, setup=()):
    """A program episode. fixtures (a placement) are written before the first checkpoint; extra setup items
    (for example a per-checkpoint fresh state) are appended."""
    items = ([{'id': 'fixtures', 'op': 'place', 'files': fixtures}] if fixtures else []) + list(setup)
    for cp in checkpoints:
        own = [f'setup:{s["id"]}' for s in items if s.get('before') == cp['id']]
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + own + list(cp.get('depends_on', []))
    return {'id': key, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': items, 'inputs': {}, 'checkpoints': _finalize(key, checkpoints)}


def scenarios(key, feature, cases, *, chunk=12):
    """Independent scenarios: each checkpoint starts from its own fresh home (reset, then its fixtures), so no
    scenario depends on a preceding one. cases: (checkpoint, fixtures) pairs."""
    out = []
    for offset in range(0, len(cases), chunk):
        cps, setup = [], []
        for cp, fixtures in cases[offset:offset + chunk]:
            steps = [{'reset': True}] + ([{'place': fixtures}] if fixtures else [])
            setup.append({'id': 'fresh-' + cp['id'], 'before': cp['id'], 'op': 'drive', 'steps': steps})
            cps.append(cp)
        name = key if len(cases) <= chunk else f'{key}-{offset // chunk + 1}'
        out.append(program(name, feature, None, cps, setup=setup))
    return out


SESSION = ('calcurse, a terminal calendar and to-do organizer, is running in the terminal. Its home directory '
           '(~) holds its data files; the clock reads Wednesday 18 March 2026, 09:30 UTC. Use the application\'s '
           'own keys and prompts to reach each goal; it lists its main key bindings at the bottom of the screen. '
           'Dates are entered in the application\'s current date format unless the goal says otherwise.')
EQUIV = ['Any key, prompt answer or command of the application that reaches the same result is equivalent (for '
         'example arrow keys or letters to move, a key or a menu entry).']
FORBID = ['Do not use a shell, run external programs, or edit files outside the application.']


def gui(key, feature, fixtures, checkpoints, *, session=SESSION, budget=None):
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if fixtures else []) + list(cp.get('depends_on', []))
    n = len(checkpoints)
    return {'id': key, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': [{'id': 'fixtures', 'op': 'place', 'files': fixtures}] if fixtures else [], 'inputs': {},
            'session': session, 'allowed_equivalents': EQUIV, 'forbidden_bypasses': FORBID,
            'budget': budget or {'calls': min(160, 100 + 30 * n), 'tokens': min(1_600_000, 900_000 + 250_000 * n),
                                 'seconds': min(1800, 600 + 300 * n)},
            'checkpoints': _finalize(key, checkpoints)}
