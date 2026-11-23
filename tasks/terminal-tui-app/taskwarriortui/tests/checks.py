"""Backend checks and deterministic driving for taskwarrior-tui.

A backend assertion carries a `check` dict naming what to observe and the projection to compare. Observations
come only through the runtime's channels: the application's command line (`task export` for the tasks it keeps,
other read-only commands for its configuration) and semantic facts parsed from the terminal screen by the screen
conventions the instruction states (harness.Screen). Every artifact is observed once per checkpoint and shared by its aspects. Projections keep
only behaviour-relevant content: task identity is the description (UUIDs are random), dates are compared in
Taskwarrior's UTC form whatever the separators, tags are compared as sets and urgency within 0.011. A mismatch
raises AssertionError (result_mismatch); any other exception is a program_exception; both fail only that point
Each exception affects only the current point.
"""
from __future__ import annotations

import json
import re

from harness import Screen, Session, squash

# -- driving -----------------------------------------------------------------------------------------------------
def drive(session: Session, steps):
    """Apply a deterministic list of steps to the product through the runtime's GUI, command-line and lifecycle
    operations."""
    for step in steps or []:
        if 'key' in step:
            session.key(step['key'])
        elif 'keys' in step:
            session.keys(step['keys'])
        elif 'type' in step:
            session.type(step['type'])
        elif 'wait' in step:
            session.wait(step['wait'])
        elif 'resize' in step:
            session.resize(*step['resize'])
        elif 'task' in step:
            done = session.task(step['task'], step.get('stdin'))
            if step.get('keep'):
                session.__dict__.setdefault('runs', []).append(done)
        elif 'fixture' in step:
            apply_fixture(session, step['fixture'])
        elif 'reset' in step:
            session.reset()
        elif 'restart' in step:
            session.restart()
        else:
            raise ValueError('unknown recipe step: ' + repr(step))


# -- setup (unscored preparation) -----------------------------------------------------------------------------------
def apply_fixture(session: Session, item):
    """Optionally start from a fresh data directory, import the fixture tasks and apply configuration through the
    application's command line, then restart the application so it starts on that state. Any failure raises."""
    if item.get('reset'):
        status = session.reset()
        if not status.get('ready'):
            raise RuntimeError('the application did not start after a reset: ' + str(status.get('detail')))
    tasks = item.get('tasks') or []
    if tasks:
        done = session.task(['rc.confirmation=off', 'import'], json.dumps(tasks, ensure_ascii=False))
        if done.get('exit_code') != 0:
            raise RuntimeError('task import failed: ' + (done.get('stderr') or done.get('stdout') or '')[-300:])
    for name, value in item.get('config') or []:
        # A value of None removes the setting; any other value (also '') is set as given.
        done = session.task(['rc.confirmation=off', 'config', name] + ([] if value is None else [value]))
        if done.get('exit_code') != 0:
            raise RuntimeError(f'task config {name} failed: ' + (done.get('stderr') or '')[-300:])
    for args in item.get('commands') or []:
        done = session.task(['rc.confirmation=off'] + list(args))
        if done.get('exit_code') != 0:
            raise RuntimeError('task %s failed: %s' % (' '.join(args), (done.get('stderr') or '')[-300:]))
    status = session.restart()
    if not status.get('ready'):
        raise RuntimeError('the application did not start on the fixture: ' + str(status.get('detail')))


def apply_setup(session: Session, item):
    op = item.get('op', 'fixture')
    if op == 'fixture':
        apply_fixture(session, item)
    elif op == 'drive':
        drive(session, item['steps'])
    else:
        raise ValueError('unknown setup op: ' + op)


# -- observation (one full observation per source, cached per checkpoint) ------------------------------------------
def source_key(check):
    kind = check['kind']
    if kind == 'export':
        return ('export',)
    if kind == 'cli':
        return ('cli', json.dumps(check['args']))
    if kind == 'run':
        return ('run', check.get('index', -1))
    if kind == 'screen':
        return ('screen',)
    raise ValueError('unknown check kind: ' + kind)


def observe(session: Session, check):
    kind = check['kind']
    if kind == 'export':
        return session.export()
    if kind == 'cli':
        return session.task(check['args'])
    if kind == 'run':
        runs = session.__dict__.get('runs', [])
        index = check.get('index', -1)
        if not runs or not -len(runs) <= index < len(runs):
            raise ValueError('no command-line run %d in this episode' % index)
        return runs[index]
    if kind == 'screen':
        return session.screen_raw()
    raise ValueError('unknown check kind: ' + kind)


# -- projection ------------------------------------------------------------------------------------------------
DATE = re.compile(r'^(\d{4})-?(\d{2})-?(\d{2})[T ]?(\d{2}):?(\d{2}):?(\d{2})(?:\.\d+)?(Z|[+-]00:?00)?$')
DATE_FIELDS = ('due', 'scheduled', 'wait', 'until', 'entry', 'start', 'end', 'modified')
TEXT_FIELDS = ('status', 'description', 'project', 'priority', 'recur', 'mask', 'rtype')


def norm_date(value):
    if value is None or value == '':
        return None
    match = DATE.match(str(value).strip())
    if not match:
        return str(value)
    return '{}{}{}T{}{}{}Z'.format(*match.groups()[:6])


def uuid_of(task):
    return str(task.get('uuid', '')).lower()


def field_value(task, name, by_uuid):
    value = task.get(name)
    if name in DATE_FIELDS:
        return norm_date(value)
    if name == 'tags':
        if not value:
            return None
        items = value if isinstance(value, list) else str(value).split(',')
        return sorted(str(v) for v in items)
    if name == 'depends':
        if not value:
            return None
        items = value if isinstance(value, list) else str(value).split(',')
        return sorted(by_uuid.get(str(u).strip().lower(), {}).get('description', 'unknown task') for u in items)
    if name == 'parent':
        if not value:
            return None
        return by_uuid.get(str(value).lower(), {}).get('description', 'unknown task')
    if name == 'annotations':
        if not value:
            return None
        notes = sorted(value, key=lambda a: norm_date(a.get('entry')) or '') if isinstance(value, list) else []
        return [str(a.get('description')) for a in notes]
    if name == 'annotation_count':
        notes = task.get('annotations')
        return len(notes) if isinstance(notes, list) else 0
    if name == 'id':
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return str(value)
    if name == 'urgency':
        try:
            return round(float(value), 3)
        except (TypeError, ValueError):
            return None
    if name == 'imask':
        try:
            return int(float(value)) if value is not None else None
        except (TypeError, ValueError):
            return str(value)
    if name == 'active':
        return bool(task.get('start'))
    if name == 'ended':
        return bool(task.get('end'))
    if value is None or value == '':
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def project_export(tasks, check):
    by_uuid = {uuid_of(t): t for t in tasks}
    fields = check.get('fields', ['status'])
    groups = {}
    for task in tasks:
        groups.setdefault(str(task.get('description')), []).append(task)

    def one(task):
        return {name: field_value(task, name, by_uuid) for name in fields}

    def entry(name):
        found = groups.get(name, [])
        if not found:
            return None
        values = sorted((one(t) for t in found), key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
        return values[0] if len(values) == 1 else values

    if check.get('summary'):
        # Every task as [description, status], sorted: which tasks exist and in which state.
        rows = sorted([str(t.get('description')), str(t.get('status'))] for t in tasks)
        return {'tasks': rows}
    if check.get('count'):
        wanted = check['count']
        return {'count': sum(1 for t in tasks if all(str(t.get(k)) == str(v) for k, v in wanted.items()))}
    names = check.get('tasks')
    if names is None:
        names = sorted(groups)
    return {name: entry(name) for name in names}


def project_cli(done, check):
    """A command-line result: its exit status, its output lines (whitespace squashed, UUIDs the application generated
    masked, lines starting with a `drop` prefix left out), the same lines sorted where the command's order is not
    defined, its error output, or the descriptions of the tasks it exported."""
    what = check.get('project', 'stdout')
    if what == 'exit':
        return {'exit_code': done.get('exit_code')}
    out = (done.get('stdout') or '').strip()
    lines = [mask_uuids(squash(line)) for line in out.splitlines() if line.strip()]
    lines = [line for line in lines if not line.startswith(tuple(check.get('drop', ())))]
    if what == 'lines':
        return {'lines': lines}
    if what == 'sorted':
        return {'lines': sorted(lines)}
    if what == 'result':
        return {'exit_code': done.get('exit_code'), 'lines': lines}
    if what == 'stderr':
        err = (done.get('stderr') or '').strip()
        return {'exit_code': done.get('exit_code'),
                'mentions': {m: m in err for m in check.get('mentions', [])}}
    if what == 'json':
        try:
            value = json.loads(out) if out.startswith('[') else [json.loads(line) for line in out.splitlines() if line.strip()]
        except ValueError:
            raise AssertionError('the command did not print JSON: ' + out[:200]) from None
        return {'exit_code': done.get('exit_code'),
                'descriptions': sorted(str(t.get('description')) for t in value if isinstance(t, dict))}
    return {'stdout': squash(out)}


def ids_sorted(title):
    """A prompt title names the affected task IDs ('Modify Tasks 5,1'); their order is not behaviour."""
    return re.sub(r'\d+(?:,\d+)+', lambda m: ','.join(sorted(m.group(0).split(','), key=int)), title)


def styled_tail(screen, obs):
    """A completion hint drawn after the typed text of the prompt's input line: the trailing run of text whose style
    (colour or text attribute) differs from the text before it. Returns (start column, text) or None."""
    if screen.height < 1:
        return None
    row = screen.height - 1
    text = screen.rows[row].rstrip()
    if not text:
        return None
    style = [()] * len(text)
    for span in obs.get('styles', []):
        if span.get('row') == row:
            start, end = span['columns']
            for column in range(max(0, start), min(end, len(text))):
                style[column] = tuple(sorted(span.get('style', [])))
    end = len(text)
    start = end
    while start > 0 and style[start - 1] == style[end - 1]:
        start -= 1
    if start == 0 or style[end - 1] == style[start - 1] or not text[start:end].strip():
        return None
    return start, text[start:end]


def input_line(screen, obs):
    """The prompt's input line without a completion hint (trailing text drawn in a style of its own: the suggestion
    that Tab would complete) is not part of the input."""
    if screen.height < 1:
        return None
    text = screen.rows[screen.height - 1]
    tail = styled_tail(screen, obs)
    if tail is not None:
        text = text[:tail[0]]
    return text.rstrip()


def input_hint(screen, obs):
    """The completion hint drawn after the input (trailing text in a style of its own), or None."""
    tail = styled_tail(screen, obs)
    return tail[1].strip() or None if tail is not None else None


UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
FIXED_UUID = re.compile(r'^\d{8}-0000-4000-8000-\d{12}$')


def mask_uuids(text):
    """UUIDs the application generated itself are random; fixture UUIDs (fixed in the setup) are kept."""
    return UUID.sub(lambda m: m.group(0) if FIXED_UUID.match(m.group(0)) else '<uuid>', text)


ATTRIBUTES = ('bold', 'italic', 'underline', 'reverse')


def selected_row_style(screen, obs, names):
    """The text attributes (bold, italic, underline, reverse) of the selected report row, read from the widest
    style run on that row."""
    rows = [y for y, text in screen.report_rows() if text[:2].strip()[:1] in ('•', '⦿', '⦾') or
            (text[:2].strip() and text[:2].strip()[:1] not in ('✔',))]
    if not rows:
        return None
    y = rows[0]
    spans = [s for s in obs.get('styles', []) if s.get('row') == y]
    if not spans:
        return []
    widest = max(spans, key=lambda s: s['columns'][1] - s['columns'][0])
    return sorted(f for f in widest.get('style', []) if f in ATTRIBUTES)


def project_screen(obs, check):
    screen = Screen(obs)
    fact = check['fact']
    names = check.get('names') or []
    if fact == 'rows':
        return {'rows': screen.rows_listed(names)}
    if fact == 'rowset':
        return {'rowset': sorted(screen.rows_listed(names))}
    if fact == 'count':
        return {'count': len(screen.report_rows())}
    if fact == 'selected':
        return {'selected': screen.selected(names, tuple(check.get('glyphs', ('•', '⦿', '⦾'))))}
    if fact == 'marked':
        return {'marked': screen.marked(names, tuple(check.get('glyphs', ('✔', '⦿'))))}
    if fact == 'indicators':
        return {'indicators': screen.indicators(names)}
    if fact == 'prompt':
        prompt = screen.prompt()
        return {'prompt': prompt and {'title': ids_sorted(prompt['title']), 'line': input_line(screen, obs)}}
    if fact == 'title':
        prompt = screen.prompt()
        return {'title': prompt and ids_sorted(prompt['title'])}
    if fact == 'line':
        return {'line': input_line(screen, obs)}
    if fact == 'hint':
        return {'hint': input_hint(screen, obs)}
    if fact == 'history':
        return {'history': screen.history_position()}
    if fact == 'label':
        return {'label': screen.label()}
    if fact == 'view':
        return {'view': screen.view()}
    if fact == 'headers':
        return {'headers': screen.headers()}
    if fact == 'cells':
        return {'cells': screen.cells(check['label'], names)}
    if fact == 'details':
        rows = [[k, mask_uuids(v)] for k, v in screen.details()]
        keys = check.get('keys')
        if keys:
            rows = [[k, v] for k, v in rows if k in keys]
        return {'details': rows}
    if fact == 'detail':
        values = [mask_uuids(v) for k, v in screen.details() if k == check['key']]
        return {'detail': values[0] if values else None}
    if fact == 'error':
        text = screen.error()
        out = {'error': text is not None}
        if check.get('mentions'):
            out['mentions'] = {m: text is not None and m in text for m in check['mentions']}
        return out
    if fact == 'popup':
        box = screen.popup(check.get('title'))
        if box is None:
            return {'popup': None}
        lines = [squash(line) for line in box['lines'] if line.strip()]
        if 'first' in check:
            lines = lines[:check['first']]
        return {'popup': {'title': box['title'], 'lines': lines}}
    if fact == 'boxes':
        return {'boxes': [box['title'] for box in screen.boxes()]}
    if fact == 'content':
        rows = screen.content()
        if 'first' in check:
            rows = rows[:check['first']]
        if 'contains' in check:
            return {'contains': {text: any(text in row for row in rows) for text in check['contains']}}
        return {'content': rows}
    if fact == 'menu':
        return {'menu': screen.menu(check['title'])}
    if fact == 'layout':
        return {'layout': screen.layout()}
    if fact == 'details_text':
        rows = [squash(r) for r in screen.details_text()]
        return {'details_text': rows[:check.get('first', 6)]}
    if fact == 'row_style':
        return {'row_style': selected_row_style(screen, obs, names)}
    if fact == 'running':
        return {'running': obs.get('process') == 'running'}
    raise ValueError('unknown screen fact: ' + fact)


def project(full, check):
    kind = check['kind']
    if kind == 'export':
        return project_export(full, check)
    if kind in ('cli', 'run'):
        return project_cli(full, check)
    if kind == 'screen':
        return project_screen(full, check)
    raise ValueError('unknown check kind: ' + kind)


# -- comparison ------------------------------------------------------------------------------------------------
TOLERANCE = 0.011


def same(actual, expected):
    if isinstance(expected, float) and isinstance(actual, (int, float)) and not isinstance(actual, bool):
        return abs(actual - expected) <= TOLERANCE
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(actual) == set(expected) and all(same(actual[k], expected[k]) for k in expected)
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(same(a, e) for a, e in zip(actual, expected))
    return actual == expected


def compare(actual, expected):
    if not same(actual, expected):
        raise AssertionError('observation differs from the reference: ' + first_difference(actual, expected))


def first_difference(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b), key=str):
            if not same(a.get(key), b.get(key)):
                return first_difference(a.get(key), b.get(key), f'{path}/{key}')
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if not same(x, y):
                return first_difference(x, y, f'{path}[{i}]')
    return f'{path or "value"}: {json.dumps(a, ensure_ascii=False)[:300]} != {json.dumps(b, ensure_ascii=False)[:300]}'
