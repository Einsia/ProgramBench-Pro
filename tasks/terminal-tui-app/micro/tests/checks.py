"""Backend checks and deterministic driving for micro.

A backend assertion carries a `check` dict naming what to observe and the projection to compare. Observations
come only through the runtime's channels: the workspace inspector (the saved files), micro's configuration files,
the command-line channel, and semantic facts parsed from the terminal screen (harness.Screen). Every artifact is
observed once per checkpoint and shared by its aspects. Exceptions in a check fail only that point; a
mismatch raises AssertionError (result_mismatch), any other exception is a program_exception.
"""
from __future__ import annotations

import base64
import json

from evaluation.broker import BrokerError
from harness import Screen, Session


# -- driving -------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    """Apply a deterministic list of steps to the product through the runtime's GUI/lifecycle operations."""
    for step in steps or []:
        if 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'paste' in step:
            session.paste(step['paste'])
        elif 'cmd' in step:
            session.command(step['cmd'])
        elif 'mouse' in step:
            session.mouse(step['mouse'])
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'sync' in step:
            session.sync()
        elif 'snapshot' in step:
            session.snapshots[step['snapshot']] = session.screen_raw()
        elif 'resize' in step:
            session.resize(*step['resize'])
        elif 'modify' in step:
            session.modify(**step['modify'])
        elif 'restart' in step:
            _started(session.restart(step['restart']))
        elif 'reset' in step:
            _started(session.reset(step['reset']))
        elif 'place' in step:
            _started(session.place(**step['place']))
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


def _started(status):
    if not (isinstance(status, dict) and status.get('ready')):
        raise RuntimeError('the application did not start: ' + str((status or {}).get('detail')))


# -- setup (unscored fixture placement) ----------------------------------------------------------------------
def apply_setup(session: Session, item):
    op = item.get('op', 'place')
    if op == 'place':
        _started(session.place(files=item.get('files'), config=item.get('config'), args=item.get('args')))
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)
    if item.get('expect'):
        _expect(Screen(session.screen_raw()), item['expect'])


def _expect(screen, expect):
    """Postcondition of a setup item: the starting state a goal relies on (for example the splits the goal then
    closes) is really on the screen; otherwise the item fails and the checkpoints that depend on it are blocked."""
    names = [s['name'] for s in screen.segments()]
    if 'panes' in expect and names != expect['panes']:
        raise AssertionError(f'the starting state needs the panes {expect["panes"]}, the screen shows {names}')
    if 'cursor_columns' in expect:
        low, high = expect['cursor_columns']
        column = (screen.obs.get('cursor') or {}).get('column')
        if column is None or not low <= column <= high:
            raise AssertionError(f'the starting state needs the cursor in columns {low}-{high}, it is at {column}')


# -- observation (one full observation per source, cached per checkpoint) ------------------------------------
SCREEN_KINDS = ('status', 'panes', 'message', 'tabs', 'gutter', 'rows', 'style', 'process', 'cells', 'cursor',
                'contains', 'columns', 'cellcmp', 'attrs')


def source_key(check):
    kind = check['kind']
    if kind == 'file':
        return ('file', check['path'])
    if kind == 'listing':
        return ('listing', check.get('path', '/workspace'), check.get('action', 'list'))
    if kind == 'mode':
        return ('stat', check['path'])
    if kind == 'config':
        return ('config', check['file'])
    if kind == 'cli':
        return ('cli', check['option'])
    if kind in SCREEN_KINDS:
        return ('snapshot', check['snapshot']) if check.get('snapshot') else ('screen',)
    raise ValueError('unknown check kind: ' + kind)


def observe(session: Session, check):
    kind = check['kind']
    if kind == 'file':
        try:
            return session.read(check['path'])
        except BrokerError as exc:  # a missing file is an observation, not a verifier fault
            if 'no such entry' in exc.detail:
                return {'missing': True}
            raise
    if kind == 'listing':
        return session.workspace(check.get('action', 'list'), check.get('path', '/workspace'))
    if kind == 'mode':
        return session.workspace('stat', check['path'])
    if kind == 'config':
        return session.config(check['file'])
    if kind == 'cli':
        return session.cli(check['option'])
    if kind in SCREEN_KINDS:
        if check.get('snapshot'):
            # A screen captured by a 'snapshot' step before later steps (for example a save) changed it.
            if check['snapshot'] not in session.snapshots:
                raise AssertionError('the screen was not captured at ' + check['snapshot'])
            return session.snapshots[check['snapshot']]
        return session.screen_raw()
    raise ValueError('unknown check kind: ' + kind)


# -- projection (the asserted slice of a full observation) ---------------------------------------------------
STATUS_FIELDS = ('name', 'modified', 'readonly', 'overwrite', 'paste', 'line', 'col', 'filetype', 'fileformat',
                 'encoding')


def _content(full):
    if full.get('missing'):
        return {'exists': False}
    body = base64.b64decode(full.get('body_base64', ''))
    try:
        return {'exists': True, 'text': body.decode('utf-8')}
    except UnicodeDecodeError:
        return {'exists': True, 'base64': base64.b64encode(body).decode()}


def project(full, check):
    kind = check['kind']
    if kind == 'file':
        return _content(full)
    if kind == 'listing':
        entries = full.get('entries', [])
        if check.get('contents'):
            # Names left out (for example backup files whose names encode a private absolute path): the sorted
            # types and contents of the entries.
            return {'contents': sorted([e.get('type'), e.get('sha256')] for e in entries)}
        recursive = check.get('action') == 'tree'
        key = 'path' if recursive else 'name'
        return {'entries': sorted([e.get(key), e.get('type')] for e in entries)}
    if kind == 'mode':
        return {'type': full.get('type'), 'mode': oct(full.get('mode') or 0)}
    if kind == 'config':
        if not full.get('exists'):
            return {'exists': False}
        text = full.get('text', '')
        try:
            return {'exists': True, 'json': json.loads(text)}
        except ValueError:
            return {'exists': True, 'text': text}
    if kind == 'cli':
        out = {'exit_code': full.get('exit_code')}
        stdout = full.get('stdout', '')
        if check['option'] == '-options':
            options, name = {}, None
            for line in stdout.splitlines():
                if line.startswith('-') and line.endswith(' value'):
                    name = line[1:-len(' value')]
                elif name and 'Default value:' in line:
                    options[name] = line.split('Default value:', 1)[1].strip()
                    name = None
            keys = check.get('names')
            if check.get('list'):
                out['names'] = sorted(options)
            else:
                out['options'] = {k: options.get(k) for k in keys} if keys else options
        elif check['option'] == '-version':
            out['lines'] = [ln.strip() for ln in stdout.splitlines() if ln.strip().lower().startswith('version')]
        else:
            out['stdout'] = [ln.rstrip() for ln in stdout.splitlines()]
        return out
    screen = Screen(full)
    if kind == 'process':
        return {'process': screen.process}
    if kind == 'status':
        status = screen.status()
        if status is None:
            return {'status': None}
        fields = check.get('fields') or STATUS_FIELDS
        return {f: status[f] for f in fields}
    if kind == 'panes':
        fields = check.get('fields') or ('name', 'line', 'col')
        return {'panes': [[s[f] for f in fields] for s in screen.segments()]}
    if kind == 'message':
        text = screen.message()
        if check.get('reported'):
            return {'reported': bool(text) and not text.startswith('>')}
        if check.get('cut'):
            text = text.split(check['cut'], 1)[0]
        return {'message': text}
    if kind == 'tabs':
        bar = screen.tabs()
        if bar and check.get('fields'):
            bar = dict(bar, current=bar['names'][bar['active']] if bar['active'] is not None else None)
            bar = {field: bar[field] for field in check['fields']}
        return {'tabs': bar}
    if kind == 'gutter':
        numbers = screen.gutter(check.get('column', 0))
        limit = check.get('limit')
        return {'gutter': numbers[:limit] if limit else numbers}
    if kind == 'rows':
        start, end = check['rows']
        lines = screen.text_rows(start, end)
        if check.get('cut'):
            lines = [line.split(check['cut'], 1)[0] for line in lines]
        return {'rows': lines}
    if kind == 'style':
        return {'style': screen.token_style(check['token'], check.get('row'))}
    if kind == 'cells':
        return {'cells': [screen.style_at(r, c) for r, c in check['cells']]}
    if kind == 'cursor':
        cursor = full.get('cursor') or {}
        fields = check.get('fields') or ('row', 'column', 'hidden')
        return {f: cursor.get(f) for f in fields}
    if kind == 'attrs':
        # Text attributes of cells (bold, italic, underline, reverse) without their colours.
        keep = ('bold', 'italic', 'underline', 'reverse')
        return {'attrs': [[f for f in screen.style_at(r, c) if f in keep] for r, c in check['cells']]}
    if kind == 'cellcmp':
        # Whether each pair of cells is drawn in different styles: highlighting as a fact, independent of colours.
        return {'differ': [screen.style_at(*a) != screen.style_at(*b) for a, b in check['pairs']]}
    if kind == 'columns':
        # One screen row split at micro's vertical split dividers: the panes' contents left to right, without widths.
        return {'columns': [part.strip() for part in screen.rows[check['row']].split(check.get('divider', '|'))]}
    if kind == 'contains':
        text = '\n'.join(screen.rows)
        return {'contains': [needle in text for needle in check['texts']]}
    raise ValueError('unknown check kind: ' + kind)


def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + _first_diff(actual, expected))


def _first_diff(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return f'{key}: {a.get(key)!r} != {b.get(key)!r}'[:1500]
    return f'{a!r} != {b!r}'[:1500]
