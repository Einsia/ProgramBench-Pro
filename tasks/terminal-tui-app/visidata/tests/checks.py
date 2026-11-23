'''Backend checks and deterministic driving for visidata.

A backend assertion carries a check dict naming what to observe and the projection to compare. Observations come
only through the runtime's channels: the workspace inspector (files the product wrote, read as text, rows, JSON,
command logs or SQLite tables), the input-history state file, the command-line channel (batch runs: vd -b INPUT -o
OUTPUT and vd -b -p LOG.vdj, whose exit status and printed lines are observed) and semantic facts parsed from the
terminal screen (harness.Screen). Every artifact is observed once per checkpoint and shared by its aspects. A
projection keeps only behaviour-relevant content: line endings, key order and trailing blanks are normalised and
nothing environment dependent is read. A mismatch raises AssertionError (result_mismatch); output that cannot be
parsed also raises AssertionError; any other exception is a program_exception. Both fail only that point.
'''
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import sqlite3

from evaluation.broker import BrokerError
from harness import Screen, Session

NL, TAB, CR = chr(10), chr(9), chr(13)


# -- driving ---------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    '''Apply a deterministic list of steps through the runtime's terminal, file and command-line channels.'''
    runs = session.__dict__.setdefault('runs', [])
    for step in steps or []:
        if 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'ask' in step:
            session.ask(step['ask'], step.get('text'))
        elif 'open' in step:
            session.open(step['open'])
        elif 'command' in step:
            session.command(step['command'])
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'place' in step:
            session.place(step['place'])
        elif 'reset' in step:
            session.reset()
        elif 'restart' in step:
            session.restart()
        elif 'cli' in step:
            try:
                runs.append(session.cli(step['cli']))
            except BrokerError as exc:
                runs.append({'error': str(exc)[:200]})
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


# -- setup (unscored fixture placement) --------------------------------------------------------------------------
def apply_setup(session: Session, item):
    op = item.get('op', 'place')
    if op == 'place':
        session.place(item['files'])
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)


# -- observation (one full observation per source, cached per checkpoint) ------------------------------------------
def source_key(check):
    kind = check['kind']
    if kind == 'tree':
        return ('tree', check.get('path', '/workspace'), check.get('action', 'tree'))
    if kind == 'file':
        return ('file', check['path'])
    if kind == 'state':
        return ('state', check.get('file', 'input_history'))
    if kind == 'run':
        return ('run', check.get('index', -1))
    if kind == 'screen':
        return ('screen',)
    raise ValueError('unknown check kind: ' + kind)


def observe(session: Session, check):
    kind = check['kind']
    if kind in ('tree', 'file'):
        try:
            if kind == 'tree':
                return session.workspace(check.get('action', 'tree'), check.get('path', '/workspace'))
            return session.read_file(check['path'])
        except BrokerError as exc:
            return {'missing': True, 'reason': str(exc)[:160]}
    if kind == 'state':
        return session.read_state(check.get('file', 'input_history'))
    if kind == 'run':
        runs = session.__dict__.get('runs', [])
        index = check.get('index', -1)
        if not runs or not (-len(runs) <= index < len(runs)):
            raise ValueError('no command-line run %d in this checkpoint' % index)
        return runs[index]
    if kind == 'screen':
        return session.screen()
    raise ValueError('unknown check kind: ' + kind)


# -- projection (the asserted slice of a full observation) ---------------------------------------------------------
def lines_of(text):
    text = text.replace(CR + NL, NL).replace(CR, NL)
    lines = text.split(NL)
    if lines and lines[-1] == '':
        lines.pop()
    return lines


def canonical(value):
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def plain(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        return 'hex:' + bytes(value).hex()
    return value


def _norm_entry(entry, fields):
    out = {'name': entry['name'], 'type': entry['type']}
    if 'size' in fields and entry['type'] == 'file':
        out['size'] = entry.get('size')
    if 'sha256' in fields and entry['type'] == 'file':
        out['sha256'] = entry.get('sha256')
    if 'target' in fields and entry['type'] == 'symlink':
        out['target'] = entry.get('target')
    if 'mode' in fields:
        out['mode'] = entry.get('mode')
    return out


def project_tree(full, check):
    if full.get('missing'):
        if check.get('may_be_missing'):
            return {'exists': False}
        raise AssertionError('the workspace has no entry ' + check.get('path', '/workspace'))
    fields = set(check.get('fields', ['size', 'sha256', 'target']))
    key = 'path' if check.get('action', 'tree') == 'tree' else 'name'
    entries = full['entries']
    if check.get('only') is not None:
        entries = [e for e in entries if e.get(key) in check['only']]
    if check.get('names_only'):
        return {'path': full.get('path'), 'names': [e.get(key) for e in entries]}
    return {'path': full.get('path'), 'entries': [dict(_norm_entry(e, fields), name=e.get(key)) for e in entries]}


def dump_sqlite(data, check):
    connection = sqlite3.connect(':memory:')
    q = chr(34)
    try:
        connection.deserialize(data)
        names = [r[0] for r in connection.execute(
            'select name from sqlite_master where type = ? and name not like ? order by name', ('table', 'sqlite_%'))]
        tables = {}
        for name in names:
            quoted = q + name.replace(q, q + q) + q
            info = list(connection.execute('pragma table_info(%s)' % quoted))
            rows = [[plain(v) for v in row] for row in connection.execute('select * from %s' % quoted)]
            if check.get('sorted_rows'):
                rows.sort(key=lambda row: json.dumps(row))
            columns = [[c[1], str(c[2]).upper()] for c in info] if check.get('types', True) else [c[1] for c in info]
            tables[name] = {'columns': columns, 'rows': rows}
        return tables
    except sqlite3.Error as exc:
        raise AssertionError('not a readable SQLite database: ' + str(exc)[:80]) from None
    finally:
        connection.close()


def project_file(full, check):
    if full.get('missing'):
        if check.get('may_be_missing'):
            return {'exists': False}
        raise AssertionError('the file does not exist: ' + check['path'])
    text = full.get('text', '')
    mode = check.get('as', 'text')
    out = {'exists': True}
    if mode == 'text':
        lines = lines_of(text)
        if check.get('strip'):
            lines = [line.rstrip() for line in lines]
        out['lines'] = sorted(lines) if check.get('sorted') else lines
    elif mode == 'tsv':
        rows = [line.split(TAB) for line in lines_of(text)]
        out['rows'] = sorted(rows) if check.get('sorted') else rows
    elif mode == 'csv':
        try:
            rows = [row for row in csv.reader(io.StringIO(text.replace(CR + NL, NL)))]
        except csv.Error as exc:
            raise AssertionError('not valid CSV: ' + str(exc)[:80]) from None
        out['rows'] = sorted(rows) if check.get('sorted') else rows
    elif mode in ('json', 'jsonl'):
        try:
            if mode == 'json':
                data = json.loads(text)
            else:
                data = [json.loads(line) for line in lines_of(text) if line.strip()]
        except ValueError:
            raise AssertionError('not valid JSON') from None
        if check.get('sorted') and isinstance(data, list):
            data = sorted(data, key=lambda item: json.dumps(item, sort_keys=True))
        out['data'] = data
    elif mode == 'vdj':
        fields = check.get('fields', ['longname', 'input'])
        entries = []
        for line in lines_of(text):
            if not line.strip() or line.startswith('#'):
                continue
            try:
                item = json.loads(line)
            except ValueError:
                raise AssertionError('a command log line is not valid JSON') from None
            if not isinstance(item, dict):
                raise AssertionError('a command log line is not an object')
            entries.append({name: item.get(name) for name in fields})
        out['entries'] = entries
    elif mode == 'bytes':
        data = base64.b64decode(full.get('body_base64', ''))
        out.update(size=len(data), sha256=hashlib.sha256(data).hexdigest())
    elif mode == 'sqlite':
        out['tables'] = dump_sqlite(base64.b64decode(full.get('body_base64', '')), check)
    else:
        raise ValueError('unknown file projection: ' + mode)
    return out


def project_run(full, check):
    if full.get('error'):
        raise AssertionError('the command-line channel failed: ' + str(full['error']))
    only = check.get('only', ['exit_code', 'output'])
    out = {}
    if 'exit_code' in only:
        out['exit_code'] = full.get('exit_code')
    if 'ok' in only:
        out['ok'] = full.get('exit_code') == 0
    if 'output' in only:
        lines = [line.rstrip() for line in str(full.get('output', '')).replace(CR, '').split(NL) if line.strip()]
        if check.get('match'):
            lines = [line for line in lines if check['match'] in line]
        out['output'] = lines
    return out


def project_state(full, check):
    entries = []
    for line in lines_of(full.get('text', '')):
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and (not check.get('types') or item.get('type') in check['types']):
            entries.append([item.get('type'), item.get('input'), item.get('n')])
    if check.get('sorted'):
        entries.sort(key=lambda entry: json.dumps(entry))
    return {'file': full.get('file'), 'exists': bool(full.get('exists')), 'entries': entries}


def project_screen(full, check):
    screen = full if isinstance(full, Screen) else Screen(full)
    fact = check['fact']
    out = {'fact': fact}
    if fact == 'columns':
        columns = screen.columns()
        out['columns'] = columns if check.get('marks') else [c['name'] for c in columns]
    elif fact == 'keys':
        out['keys'] = [c['name'] for c in screen.columns() if c['key']]
    elif fact == 'table':
        rows = screen.table()
        names = [c['name'] for c in screen.columns()]
        wanted = check.get('columns')
        if wanted:
            index = [names.index(n) for n in wanted if n in names]
            rows = [[row[i] for i in index if i < len(row)] for row in rows]
        out['rows'] = rows[:check['limit']] if check.get('limit') else rows
    elif fact == 'cursor':
        out['cursor'] = screen.cursor()
    elif fact == 'position':
        out.update(row=screen.cursor_row(), column=screen.cursor_column())
    elif fact == 'selected':
        table = screen.table()
        out['rows'] = [table[i] for i in screen.selected_rows() if i < len(table)]
        out['count'] = screen.selected_count()
    elif fact == 'sheet':
        out['sheet'] = screen.sheet()
    elif fact == 'stack':
        out['stack'] = screen.stack()
    elif fact == 'count':
        out['count'] = screen.count()
    elif fact == 'prompt':
        out['prompt'] = screen.prompt()
    elif fact == 'message':
        out['message'] = screen.last_message()
    elif fact == 'text':
        out['present'] = check['text'] in NL.join(screen.lines())
    elif fact == 'exited':
        out['exited'] = str(screen.process).startswith('exited')
    else:
        raise ValueError('unknown screen fact: ' + fact)
    return out


def project(full, check):
    kind = check['kind']
    if kind == 'tree':
        value = project_tree(full, check)
    elif kind == 'file':
        value = project_file(full, check)
    elif kind == 'run':
        value = project_run(full, check)
    elif kind == 'state':
        value = project_state(full, check)
    elif kind == 'screen':
        value = project_screen(full, check)
    else:
        raise ValueError('unknown check kind: ' + kind)
    return canonical(value)


# -- comparison ----------------------------------------------------------------------------------------------------
def compare(actual, expected):
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + _first_diff(actual, expected))


def _first_diff(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                return _first_diff(a.get(key), b.get(key), path + '.' + str(key))
    if isinstance(a, list) and isinstance(b, list):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                return _first_diff(x, y, path + '[%d]' % i)
        return '%s: length %d != %d' % (path or 'value', len(a), len(b))
    return '%s: %s != %s' % (path or 'value', repr(a)[:160], repr(b)[:160])
