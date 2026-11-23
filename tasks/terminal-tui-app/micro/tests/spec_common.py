"""Builders shared by the episode families of the micro specification.

Program episodes place their files once (setup), and every checkpoint starts the editor afresh on its own file
(a restart with that file as the command-line argument), so checkpoints are independent of each other: one
checkpoint's failure, crash or leftover prompt never reaches the next. Its steps are deterministic key/command
sequences through the runtime, and its checks read the saved file, the status line, the message line, micro's
configuration files or the command-line output. GUI episodes are user goals judged by the evaluator, each with a
backend companion so an inert interface cannot pass. The frozen record of the pinned standard answer defines the
exact expected values; requirement texts describe the behaviour.
"""
import base64


# -- fixtures --------------------------------------------------------------------------------------------------
def binary(data):
    return {'base64': base64.b64encode(data).decode()}


# -- check constructors ----------------------------------------------------------------------------------------
def file(path):
    return {'kind': 'file', 'path': path}


def listing(path='/workspace', recursive=False, contents=False):
    check = {'kind': 'listing', 'path': path}
    if recursive:
        check['action'] = 'tree'
    if contents:
        check['contents'] = True
    return check


def cells(*positions, snapshot=None):
    """Style flags of screen cells given as (row, column)."""
    check = {'kind': 'cells', 'cells': [list(p) for p in positions]}
    if snapshot:
        check['snapshot'] = snapshot
    return check


def columns(row, divider='|', snapshot=None):
    """The contents of one screen row split at the vertical split dividers."""
    check = {'kind': 'columns', 'row': row}
    if divider != '|':
        check['divider'] = divider
    if snapshot:
        check['snapshot'] = snapshot
    return check


def attrs(*positions, snapshot=None):
    """Text attributes (bold, italic, underline, reverse) of screen cells, without colours."""
    check = {'kind': 'attrs', 'cells': [list(p) for p in positions]}
    if snapshot:
        check['snapshot'] = snapshot
    return check


def differ(*pairs, snapshot=None):
    """For each pair of screen cells ((row, column), (row, column)), whether they are drawn in different styles."""
    check = {'kind': 'cellcmp', 'pairs': [[list(a), list(b)] for a, b in pairs]}
    if snapshot:
        check['snapshot'] = snapshot
    return check


def cursor(*fields):
    check = {'kind': 'cursor'}
    if fields:
        check['fields'] = list(fields)
    return check


def contains(*texts, snapshot=None):
    """Whether each text appears on the screen (for screens with volatile parts such as dates)."""
    check = {'kind': 'contains', 'texts': list(texts)}
    if snapshot:
        check['snapshot'] = snapshot
    return check


def status(*fields, snapshot=None):
    check = {'kind': 'status'}
    if fields:
        check['fields'] = list(fields)
    if snapshot:
        check['snapshot'] = snapshot
    return check


def pos(snapshot=None):
    return status('line', 'col', snapshot=snapshot)


def panes(*fields):
    check = {'kind': 'panes'}
    if fields:
        check['fields'] = list(fields)
    return check


def message(snapshot=None, reported=False, cut=None):
    """The message line. reported: only whether a message other than the command prompt is shown (for errors
    whose text comes from a library rather than from micro); cut: only the text before the first `cut` (micro's
    own words in front of such a library text)."""
    check = {'kind': 'message'}
    if snapshot:
        check['snapshot'] = snapshot
    if reported:
        check['reported'] = True
    if cut:
        check['cut'] = cut
    return check


def tabs(*fields, snapshot=None):
    """The tab bar: the tab names and the active tab's index; fields picks 'names', 'active' and 'current' (the
    active tab's name)."""
    check = {'kind': 'tabs'}
    if fields:
        check['fields'] = list(fields)
    if snapshot:
        check['snapshot'] = snapshot
    return check


def gutter(limit=None, column=0, snapshot=None):
    check = {'kind': 'gutter'}
    if snapshot:
        check['snapshot'] = snapshot
    if limit:
        check['limit'] = limit
    if column:
        check['column'] = column
    return check


def rows(start, end, snapshot=None, cut=None):
    """Screen rows start..end-1 as text; cut keeps each row only up to the first `cut`."""
    check = {'kind': 'rows', 'rows': [start, end]}
    if snapshot:
        check['snapshot'] = snapshot
    if cut:
        check['cut'] = cut
    return check


def style(token, row=None):
    check = {'kind': 'style', 'token': token}
    if row is not None:
        check['row'] = row
    return check


def config(name):
    return {'kind': 'config', 'file': name}


def cli(option, names=None, listing_only=False):
    check = {'kind': 'cli', 'option': option}
    if names:
        check['names'] = list(names)
    if listing_only:
        check['list'] = True
    return check


def mode(path):
    """The type and permission bits of a working-directory entry."""
    return {'kind': 'mode', 'path': path}


def process():
    return {'kind': 'process'}


# -- steps -----------------------------------------------------------------------------------------------------
def key(name):
    return {'key': name}


def keys(*names):
    return {'keys': list(names)}


def typ(text):
    return {'type': text}


def paste(text):
    return {'paste': text}


def cmd(text):
    return {'cmd': text}


def wait(seconds=0.5):
    return {'wait': seconds}


def sync():
    return {'sync': True}


def snap(name='mid'):
    """Capture the screen at this point of the steps (for checks of a message that a later save replaces)."""
    return {'snapshot': name}


def click(row, column, action='click', **extra):
    return {'mouse': dict(action=action, row=row, column=column, **extra)}


def restart(*args):
    return {'restart': list(args)}


def place(files=None, config_files=None, args=None):
    spec = {}
    if files:
        spec['files'] = files
    if config_files:
        spec['config'] = config_files
    if args is not None:
        spec['args'] = list(args)
    return {'place': spec}


def modify(path, text):
    return {'modify': {'path': path, 'text': text}}


SAVE = {'key': 'Control+S'}


def at(line=1, col=1):
    """Move from the start of the buffer to (line, col) with the arrow keys (Down keeps column 1, then Right
    moves along the line), so positioning relies only on the plainest cursor keys."""
    names = ['Down'] * (line - 1) + ['Right'] * (col - 1)
    return [{'keys': names}] if names else []


def flat(*parts):
    """Flatten a mix of step dicts and step lists into one step list."""
    out = []
    for part in parts:
        if isinstance(part, list):
            out.extend(part)
        elif part:
            out.append(part)
    return out


# -- episode / checkpoint builders ----------------------------------------------------------------------------
def step(cid, goal, steps, checks=(), *, depends=(), acceptance=None, requires=None):
    cp = {'id': cid, 'goal': goal, 'steps': flat(*steps) if isinstance(steps, (list, tuple)) else [steps],
          '_checks': list(checks), 'depends_on': list(depends)}
    if acceptance is not None:
        cp['_acceptance'] = [acceptance] if isinstance(acceptance, str) else list(acceptance)
    if requires:
        cp['_requires'] = requires
    return cp


def case(cid, goal, path, steps, checks, *, args=(), save=True, depends=(), requires=None):
    """A program checkpoint on its own file: start the editor on it, apply the steps, optionally save."""
    body = [restart(*args, path)] + flat(*steps) + ([SAVE] if save else [])
    return step(cid, goal, body, checks, depends=depends, requires=requires)


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
            # 'suffix' names a point of this checkpoint, 'checkpoint/suffix' one of an earlier checkpoint of the
            # same episode; a full id is used as given.
            point['requires'] = [{1: f'{wf}/{cp["id"]}/{c}', 2: f'{wf}/{c}'}.get(c.count('/') + 1, c)
                                 for c in companions]
            assert all(r in ids for r in point['requires']), (wf, cp['id'], point['requires'])
        cp.pop('_checks', None)
        cp.pop('_acceptance', None)
    return checkpoints


def _setup(files, config_files, args):
    if not (files or config_files or args):
        return []
    item = {'id': 'fixtures', 'op': 'place'}
    if files:
        item['files'] = files
    if config_files:
        item['config'] = config_files
    if args is not None:
        item['args'] = list(args)
    return [item]


INITIAL = 'Fresh micro in a working directory prepared with the listed files.'


def program(wid, feature, files, checkpoints, *, config_files=None, args=None):
    setup = _setup(files, config_files, args)
    for cp in checkpoints:
        cp['depends_on'] = (['setup:fixtures'] if setup else []) + list(cp.get('depends_on', []))
    return {'id': wid, 'feature': feature, 'execution': 'program', 'initial_state': INITIAL,
            'setup': setup, 'inputs': {}, 'checkpoints': _finalize(wid, checkpoints)}


SESSION = ('micro, the terminal text editor, is running in a terminal. The editing area shows the open file with '
           'line numbers; below it the status line shows the file name, a + when there are unsaved changes, the '
           'cursor position as (line,column), the file type, the line-ending format and the encoding; the bottom '
           'row is the message line, which also holds prompts. Control+E opens the command bar (a > prompt) for '
           'commands such as "set option value", "save", "replace", "goto", "vsplit" or "help"; Control+S saves, '
           'Control+F finds, Control+Z and Control+Y undo and redo, and Control+G shows the built-in help, which '
           'lists the default keys. Saved files are checked on disk, so save when a goal asks for it.')
EQUIV = ['Any key, chord or command that reaches the same micro action is equivalent (for example the arrow keys '
         'or a goto command to move the cursor, a key binding or the equivalent command-bar command).']
FORBID = ['Do not use a shell, run external programs, or change files other than through the editor.']


def gui(wid, feature, files, checkpoints, *, args=None, config_files=None, session=SESSION, prep=None,
        expect=None):
    """expect: the starting state the goal relies on (panes, cursor columns), checked after the setup; when it is
    missing the setup fails and the goal's points are blocked, so an interface that never reaches that state
    cannot meet the goal by doing nothing."""
    setup = _setup(files, config_files, args)
    if prep:
        # Unscored preparation through the interface (for example opening a pane the goal then closes).
        setup.append({'id': 'prepare', 'op': 'drive', 'steps': flat(*prep)})
    if expect:
        setup[-1]['expect'] = dict(expect)
    for cp in checkpoints:
        cp['depends_on'] = [f'setup:{item["id"]}' for item in setup] + list(cp.get('depends_on', []))
    n = len(checkpoints)
    return {'id': wid, 'feature': feature, 'execution': 'gui', 'initial_state': INITIAL,
            'setup': setup, 'inputs': {}, 'session': session, 'allowed_equivalents': EQUIV,
            'forbidden_bypasses': FORBID,
            # Calibrated on the standard answer driven by the real evaluator model: its per-episode peak stays
            # below 40% of every budget (F5). Operating a terminal editor toward one visible goal can take tens of
            # screen round trips (looking up keys in the built-in help, for example), and the model's generation
            # time counts as active time.
            'budget': {'calls': min(180, 120 + 30 * n), 'tokens': min(1_500_000, 900_000 + 200_000 * n),
                       'seconds': min(1800, 600 + 200 * n)},
            'checkpoints': _finalize(wid, checkpoints)}


# -- table-driven families ---------------------------------------------------------------------------------------
import json as _json


def fresh(path=None, settings=None, bindings=None, args=(), extra=None):
    """Start the editor afresh: micro's settings.json and bindings.json are replaced (by default with empty objects,
    so a set or bind of an earlier checkpoint does not carry over), then it starts with the arguments and the file.
    extra adds user colorschemes, syntax or help files; they stay in place for later checkpoints of the episode."""
    files = {'settings.json': settings if isinstance(settings, str) else _json.dumps(settings or {}),
             'bindings.json': bindings if isinstance(bindings, str) else _json.dumps(bindings or {})}
    files.update(extra or {})
    return {'place': {'config': files, 'args': list(args) + ([path] if path else [])}}


def row(cid, goal, text, steps, checks, *, path=None, files=None, settings=None, bindings=None, args=(),
        save=False, req=None, depends=(), open_file=True, config_files=None):
    """One program checkpoint of a table-driven family. text is the content of its own file (None: no file);
    checks are (suffix, requirement, check) where check may be 'file', 'pos', 'msg', 'status' or a check dict."""
    return {'cid': cid, 'goal': goal, 'text': text, 'steps': steps, 'checks': checks, 'path': path,
            'files': files or {}, 'settings': settings, 'bindings': bindings, 'args': list(args), 'save': save,
            'req': req, 'depends': list(depends), 'open': open_file, 'config': config_files}


SHORTHAND = {'pos': lambda p: pos(), 'msg': lambda p: message(), 'status': lambda p: status(),
             'file': lambda p: file(p), 'tabs': lambda p: tabs(), 'panes': lambda p: panes(),
             'process': lambda p: process(), 'settings': lambda p: config('settings.json'),
             'bindings': lambda p: config('bindings.json')}


def _row_checkpoint(prefix, r):
    path = r['path'] or f'{prefix}-{r["cid"]}.txt'
    steps = [fresh(path if r['open'] else None, r['settings'], r['bindings'], r['args'], r.get('config'))]
    # When the checkpoint ends with a save, the message and cursor shorthands read the screen captured just before
    # the save (whose own message would hide the one under test).
    steps += flat(*r['steps']) + ([snap('pre'), SAVE] if r['save'] else [])
    checks = []
    for suffix, requirement, check in r['checks']:
        if isinstance(check, str):
            if r['save'] and check == 'msg':
                check = message('pre')
            elif r['save'] and check == 'pos':
                check = pos('pre')
            else:
                check = SHORTHAND[check](path)
        checks.append((suffix, requirement, check))
    return path, step(r['cid'], r['goal'], steps, checks, depends=r['depends'], requires=r['req'])


def family(prefix, feature, rows, size=12):
    """Episodes of about `size` checkpoints. Rows that name each other (companion points or dependencies, in either
    direction) form one cluster, and a cluster is never split across episodes; rows keep their order."""
    parent = {r['cid']: r['cid'] for r in rows}

    def root(cid):
        while parent[cid] != cid:
            parent[cid] = parent[parent[cid]]
            cid = parent[cid]
        return cid
    for r in rows:
        refs = {c.split('/')[0] for names in (r['req'] or {}).values() for c in names if c.count('/') == 1}
        refs |= set(r['depends'])
        for ref in refs:
            assert ref in parent, (prefix, r['cid'], ref)
            parent[root(ref)] = root(r['cid'])
    clusters = {}
    for r in rows:
        clusters.setdefault(root(r['cid']), []).append(r)
    groups, current, placed = [], [], set()
    for r in rows:
        key = root(r['cid'])
        if key in placed:
            continue
        placed.add(key)
        cluster = clusters[key]
        if current and len(current) + len(cluster) > size:
            groups.append(current)
            current = []
        current.extend(cluster)
    if current:
        groups.append(current)
    out = []
    for n, group in enumerate(groups):
        files, cps = {}, []
        for r in group:
            path, cp = _row_checkpoint(prefix, r)
            if r['text'] is not None:
                files[path] = r['text']
            files.update(r['files'])
            cps.append(cp)
        out.append(program(f'{prefix}-{n + 1}', feature, files, cps))
    return out
