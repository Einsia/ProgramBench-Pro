"""Program observations of the application's products, and their comparison.

Every observation comes through the black-box runtime: exported files (the JSON diagram file, SQL scripts, DBML,
Mermaid, Markdown documentation, images) retrieved with download after the export the user would choose, the
clipboard, and the visible page. Observations are projections that ignore representation details: generated ids
are replaced by the names they refer to, numbers given as text or as numbers are equal, absent optional flags count
as false, export file names and timestamps are not observed, and SQL scripts are read statement by statement
(sqlnorm). Each check observes only the part of the product its point is about.
"""
import io
import json
import re
import struct
import sys
import zlib

import sqlnorm
import textblocks

sys.path.insert(0, '/opt/verifier-lib')

FLAGS = ('primary', 'unique', 'notNull', 'increment', 'unsigned', 'isArray')


# -- diagram files ------------------------------------------------------------------------------------
def text(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


def field_view(field):
    out = {'name': text(field.get('name')), 'type': text(field.get('type')), 'size': text(field.get('size')),
           'default': text(field.get('default')), 'check': text(field.get('check')),
           'comment': text(field.get('comment'))}
    for flag in FLAGS:
        out[flag] = bool(field.get(flag))
    values = field.get('values')
    if field.get('type') in ('ENUM', 'SET') or values:
        out['values'] = [text(v) for v in (values or [])]
    return out


class Diagram:
    """A diagram file (the JSON export) with ids resolved to names."""

    def __init__(self, data):
        if not isinstance(data, dict):
            raise AssertionError('the diagram file is not a JSON object')
        self.data = data
        self.tables = [t for t in data.get('tables') or [] if isinstance(t, dict)]
        self.by_id = {t.get('id'): t for t in self.tables}

    def table(self, name):
        found = [t for t in self.tables if t.get('name') == name]
        if not found:
            raise AssertionError(f'the diagram has no table named {name!r}: ' + str([t.get('name') for t in self.tables]))
        return found[0]

    def field_name(self, table_id, field_id):
        table = self.by_id.get(table_id)
        if table is None:
            return '?'
        field = next((f for f in table.get('fields') or [] if f.get('id') == field_id), None)
        return f"{table.get('name')}.{field.get('name')}" if field else f"{table.get('name')}.?"

    def table_name(self, table_id):
        table = self.by_id.get(table_id)
        return table.get('name') if table else '?'

    def table_view(self, table, aspects=None):
        aspects = aspects or ('name', 'fields', 'indices', 'uniques', 'comment', 'inherits')
        out = {}
        if 'name' in aspects:
            out['name'] = text(table.get('name'))
        if 'fields' in aspects:
            out['fields'] = [field_view(f) for f in table.get('fields') or []]
        if 'indices' in aspects:
            out['indices'] = [{'name': text(i.get('name')), 'unique': bool(i.get('unique')),
                               'fields': [text(f) for f in i.get('fields') or []]} for i in table.get('indices') or []]
        if 'uniques' in aspects:
            out['uniques'] = [{'name': text(u.get('name')), 'fields': [text(f) for f in u.get('fields') or []]}
                              for u in table.get('uniqueConstraints') or []]
        if 'comment' in aspects:
            out['comment'] = text(table.get('comment'))
        if 'inherits' in aspects:
            out['inherits'] = [text(x) for x in table.get('inherits') or []]
        if 'color' in aspects:
            out['color'] = text(table.get('color')).lower()
        if 'position' in aspects:
            out['position'] = [table.get('x'), table.get('y')]
        if 'flags' in aspects:
            out['locked'] = bool(table.get('locked'))
            out['hidden'] = bool(table.get('hidden'))
        if 'types' in aspects:
            out['types'] = [[text(f.get('name')), text(f.get('type')), text(f.get('size'))]
                            for f in table.get('fields') or []]
        if 'typenames' in aspects:
            out['typenames'] = [[text(f.get('name')), text(f.get('type'))] for f in table.get('fields') or []]
        if 'collapsed' in aspects:
            out['collapsed'] = bool(table.get('collapsed'))
        if 'field_names' in aspects:
            out['field_names'] = [text(f.get('name')) for f in table.get('fields') or []]
        return out

    def relationship_view(self, r, extra=False):
        pairs = r.get('fields') if isinstance(r.get('fields'), list) and r.get('fields') else \
            [{'startFieldId': r.get('startFieldId'), 'endFieldId': r.get('endFieldId')}]
        more = {'label': text(r.get('manyLabel')), 'color': text(r.get('color')).lower()} if extra else {}
        return {**more, 'name': text(r.get('name')), 'from': self.table_name(r.get('startTableId')),
                'to': self.table_name(r.get('endTableId')),
                'pairs': [[self.field_name(r.get('startTableId'), p.get('startFieldId')),
                           self.field_name(r.get('endTableId'), p.get('endFieldId'))] for p in pairs],
                'cardinality': text(r.get('cardinality')), 'update': text(r.get('updateConstraint')),
                'delete': text(r.get('deleteConstraint'))}

    def relationships(self):
        views = [self.relationship_view(r) for r in self.data.get('relationships') or [] if isinstance(r, dict)]
        return sorted(views, key=lambda v: json.dumps(v, sort_keys=True))

    def view_view(self, v, extra=False):
        def col(c):
            return {'column': self.field_name(c.get('tableId'), c.get('fieldId')), 'alias': text(c.get('alias'))}

        def join(j):
            on = j.get('on') or {}
            return {'type': text(j.get('type')), 'table': self.table_name(j.get('tableId')),
                    'left': self.field_name(on.get('leftTableId'), on.get('leftFieldId')) if on else '',
                    'right': self.field_name(j.get('tableId'), on.get('rightFieldId')) if on else ''}

        def cond(c):
            return {'connector': text(c.get('connector')), 'column': self.field_name(c.get('tableId'), c.get('fieldId')),
                    'operator': text(c.get('operator')), 'value': text(c.get('value'))}
        return {'name': text(v.get('name')), 'base': self.table_name(v.get('baseTableId')),
                'columns': [col(c) for c in v.get('columns') or []], 'joins': [join(j) for j in v.get('joins') or []],
                'conditions': [cond(c) for c in v.get('conditions') or []], 'comment': text(v.get('comment')),
                'materialized': bool(v.get('materialized')),
                **({'color': text(v.get('color')).lower()} if extra else {})}

    def part(self, spec):
        part = spec['part']
        if part == 'tables':
            return {'tables': [text(t.get('name')) for t in self.tables]}
        if part == 'all-fields':
            return {'tables': {text(t.get('name')): [field_view(f) for f in t.get('fields') or []]
                               for t in self.tables}}
        if part == 'table':
            found = [t for t in self.tables if t.get('name') == spec['name']]
            nth = spec.get('nth', 0)
            if len(found) <= nth:
                raise AssertionError(f"the diagram has no table number {nth + 1} named {spec['name']!r}: "
                                     + str([t.get('name') for t in self.tables]))
            return {'table': self.table_view(found[nth], spec.get('aspects'))}
        if part == 'moved':
            items = {'table': self.tables, 'view': self.data.get('views') or [], 'note': self.data.get('notes') or [],
                     'area': self.data.get('subjectAreas') or []}[spec.get('kind', 'table')]
            key = 'title' if spec.get('kind') == 'note' else 'name'
            found = [i for i in items if isinstance(i, dict) and i.get(key) == spec['name']]
            if not found:
                raise AssertionError(f"no {spec.get('kind', 'table')} named {spec['name']!r}")
            dx = (found[0].get('x') or 0) - spec['from'][0]
            dy = (found[0].get('y') or 0) - spec['from'][1]
            return {'moved': {'right': dx > 40, 'left': dx < -40, 'down': dy > 40, 'up': dy < -40}}
        if part == 'spread':
            # Tables placed apart: no two tables start within 60 px of each other in both directions.
            spots = [(t.get('x') or 0, t.get('y') or 0) for t in self.tables]
            apart = all(abs(a[0] - b[0]) >= 60 or abs(a[1] - b[1]) >= 60
                        for i, a in enumerate(spots) for b in spots[i + 1:])
            return {'spread': {'tables': len(spots), 'apart': apart}}
        if part == 'snapped':
            table = self.table(spec['name'])
            x, y = table.get('x') or 0, table.get('y') or 0
            return {'snapped': {'down': y - spec['start'][1] > 40,
                                'grid': all(isinstance(v, (int, float)) and float(v) % 24 == 0 for v in (x, y))}}
        if part == 'table-width':
            width = self.table(spec['name']).get('width') or spec['width']
            return {'width': {'wider': width > spec['width'] + 40, 'narrower': width < spec['width'] - 40}}
        if part == 'area-size':
            found = [a for a in self.data.get('subjectAreas') or [] if isinstance(a, dict) and a.get('name') == spec['name']]
            if not found:
                raise AssertionError(f"no area named {spec['name']!r}")
            w0, h0 = spec['size']
            w, h = found[0].get('width') or 0, found[0].get('height') or 0
            return {'size': {'wider': w > w0 + 40, 'narrower': w < w0 - 40, 'taller': h > h0 + 40,
                             'shorter': h < h0 - 40}}
        if part == 'last-table':
            if not self.tables:
                raise AssertionError('the diagram has no table')
            return {'table': self.table_view(self.tables[-1], spec.get('aspects'))}
        if part == 'field':
            table = self.table(spec['table'])
            found = [f for f in table.get('fields') or [] if f.get('name') == spec['name']]
            if not found:
                raise AssertionError(f"table {spec['table']!r} has no column {spec['name']!r}")
            view = field_view(found[0])
            if spec.get('aspects'):
                view = {k: view.get(k) for k in spec['aspects']}
            return {'field': view}
        if part == 'relationships':
            return {'relationships': self.relationships()}
        if part == 'relationship':
            found = [self.relationship_view(r, extra=True) for r in self.data.get('relationships') or []
                     if isinstance(r, dict) and r.get('name') == spec['name']]
            if not found:
                raise AssertionError(f"no relationship named {spec['name']!r}")
            view = found[0]
            if spec.get('aspects'):
                view = {k: view[k] for k in spec['aspects']}
            return {'relationship': view}
        if part == 'notes':
            aspects = spec.get('aspects') or ('title', 'content')
            return {'notes': [{k: note_value(n, k) for k in aspects} for n in self.data.get('notes') or []]}
        if part == 'areas':
            aspects = spec.get('aspects') or ('name',)
            return {'areas': [{k: area_value(a, k) for k in aspects} for a in self.data.get('subjectAreas') or []]}
        if part == 'views':
            return {'views': [self.view_view(v) for v in self.data.get('views') or [] if isinstance(v, dict)]}
        if part == 'view':
            found = [v for v in self.data.get('views') or [] if isinstance(v, dict) and v.get('name') == spec['name']]
            if not found:
                raise AssertionError(f"no view named {spec['name']!r}")
            view = self.view_view(found[0], extra=True)
            if 'flags' in spec.get('aspects', []):
                view['flags'] = {'hidden': bool(found[0].get('hidden')), 'locked': bool(found[0].get('locked'))}
            if spec.get('aspects'):
                view = {k: view[k] for k in spec['aspects']}
            return {'view': view}
        if part == 'enums':
            return {'enums': [{'name': text(e.get('name')), 'values': [text(v) for v in e.get('values') or []]}
                              for e in self.data.get('enums') or []]}
        if part == 'types':
            return {'types': [{'name': text(t.get('name')), 'comment': text(t.get('comment')),
                               'fields': [{'name': text(f.get('name')), 'type': text(f.get('type')),
                                           **({'values': [text(v) for v in f['values']]} if f.get('values') else {})}
                                          for f in t.get('fields') or []]}
                              for t in self.data.get('types') or []]}
        if part == 'title':
            return {'title': text(self.data.get('title'))}
        if part == 'database':
            return {'database': text(self.data.get('database'))}
        if part == 'counts':
            return {'counts': {'tables': len(self.tables),
                               'relationships': len(self.data.get('relationships') or []),
                               'notes': len(self.data.get('notes') or []),
                               'areas': len(self.data.get('subjectAreas') or []),
                               'views': len(self.data.get('views') or []),
                               'enums': len(self.data.get('enums') or []),
                               'types': len(self.data.get('types') or [])}}
        raise ValueError('unknown diagram part ' + part)


def note_value(note, key):
    if key == 'locked':
        return bool(note.get('locked'))
    if key == 'position':
        return [note.get('x'), note.get('y')]
    if key == 'color':
        return text(note.get('color')).lower()
    return text(note.get(key))


def area_value(area, key):
    if key == 'locked':
        return bool(area.get('locked'))
    if key == 'position':
        return [area.get('x'), area.get('y')]
    if key == 'size':
        return [area.get('width'), area.get('height')]
    if key == 'color':
        return text(area.get('color')).lower()
    return text(area.get(key))


# -- other files -----------------------------------------------------------------------------------------
def lines(data):
    """A text file as its lines with spacing collapsed and blank lines dropped."""
    return [' '.join(line.split()) for line in data.splitlines() if line.strip()]


def image_facts(data, required, absent=()):
    from imagecheck import inspect
    return inspect(data, required, absent)


def transform(snap):
    """Pan x, pan y and scale shown by the debug coordinates panel: the three numbers that follow its 'pan x',
    'pan y' and 'scale' labels (as a header row and a value row, or as label: value)."""
    lines = [line.strip() for line in snap.get('text', '').split('\n')] + \
        [c.get('text', '') for c in snap.get('controls', [])]
    labels = ['pan x', 'pan y', 'scale']
    values = {}
    for line in lines:
        match = re.fullmatch(r'(pan x|pan y|scale)\s*[:=]\s*(-?\d+(?:\.\d+)?)', line.casefold())
        if match:
            values[match.group(1)] = float(match.group(2))
    if len(values) < 3:
        norm = [line.casefold() for line in lines]
        if 'scale' in norm:
            numbers = [float(x) for x in norm[norm.index('scale') + 1:] if re.fullmatch(r'-?\d+(?:\.\d+)?', x)][:3]
            if len(numbers) == 3:
                values = dict(zip(labels, numbers))
    if len(values) < 3:
        raise AssertionError('no pan and scale values are shown')
    return [round(values[k], 2) for k in labels]


def archive(data):
    """Entries of a zip archive (numbers in parentheses dropped from file names) with the tables of each diagram
    file in it."""
    import zipfile
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise AssertionError('the export is not a zip archive') from None
    out = {}
    for name in sorted(zf.namelist()):
        if name.endswith('/'):
            continue
        key = re.sub(r'\(\d+\)(?=\.json$)', '', name)
        try:
            content = json.loads(zf.read(name).decode('utf-8'))
            out[key] = [t.get('name') for t in content.get('tables') or []]
        except (ValueError, UnicodeDecodeError, AttributeError):
            out[key] = None
    return out


# -- comparison ------------------------------------------------------------------------------------------
def compare(actual, expected, tol=None, path='observation'):
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise AssertionError(f'{path}: expected an object, got {str(actual)[:200]}')
        missing = set(expected) - set(actual)
        extra = set(actual) - set(expected)
        if missing or extra:
            raise AssertionError(f'{path}: keys differ (missing {sorted(missing)}, unexpected {sorted(extra)})')
        for key in expected:
            compare(actual[key], expected[key], tol, f'{path}.{key}')
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(f'{path}: expected {json.dumps(expected)[:600]}, got {json.dumps(actual)[:600]}')
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, tol, f'{path}[{i}]')
        return
    if tol is not None and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or abs(actual - expected) > tol:
            raise AssertionError(f'{path}: expected {expected} (within {tol}), got {actual!r}')
        return
    if actual != expected:
        raise AssertionError(f'{path}: expected {json.dumps(expected)[:600]}, got {json.dumps(actual)[:600]}')


# -- observations through the runtime --------------------------------------------------------------------------
def exported(ctx, path):
    """(filename, bytes) of an export, made once per checkpoint; a path ['download', suffix, ...] is the newest file
    the goal itself downloaded with one of the suffixes."""
    cache = ctx.state.setdefault('exports', {})
    key = tuple(path)
    if key not in cache:
        ui = ctx.state['ui']
        if path[0] == 'download':
            cache[key] = ui.produced(path[1:])
        else:
            ui.editor()
            cache[key] = ui.export(*path)
    return cache[key]


def diagram(ctx):
    """The current diagram as its JSON export (once per checkpoint)."""
    _, data = exported(ctx, ('File', 'Export as', 'JSON'))
    try:
        return Diagram(json.loads(data.decode('utf-8')))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AssertionError('the JSON export is not JSON: ' + str(exc)[:200]) from None


def script(ctx, path, dialect='mysql'):
    _, data = exported(ctx, path)
    try:
        return sqlnorm.read(data.decode('utf-8'), dialect)
    except UnicodeDecodeError:
        raise AssertionError('the export is not UTF-8 text') from None


def observe(ctx, checkpoint, spec):
    ui = ctx.state['ui']
    kind = spec['type']
    database = next((step['db'] for step in checkpoint.get('prep', []) if step.get('do') == 'fresh'), 'mysql')
    dialect = {'MySQL': 'mysql', 'MariaDB': 'mariadb', 'PostgreSQL': 'postgresql', 'SQLite': 'sqlite',
               'MSSQL': 'transactsql', 'Oracle': 'oraclesql'}.get((spec.get('export') or [''])[-1], database)
    if kind == 'model':
        return diagram(ctx).part(spec)
    if kind == 'file-model':
        _, data = exported(ctx, ['download', spec['suffix']])
        try:
            return Diagram(json.loads(data.decode('utf-8'))).part(spec)
        except (UnicodeDecodeError, ValueError) as exc:
            raise AssertionError('the downloaded diagram is not JSON: ' + str(exc)[:200]) from None
    if kind == 'transform-change':
        pan_x, pan_y, scale = transform(ui.snap())
        x0, y0, s0 = spec['from']
        out = {}
        if 'zoom' in spec['aspects']:
            out['zoom'] = 'in' if scale > s0 * 1.01 else 'out' if scale < s0 * 0.99 else 'same'
        if 'pan' in spec['aspects']:
            out['pan'] = {'x': 'more' if pan_x > x0 + 5 else 'less' if pan_x < x0 - 5 else 'same',
                          'y': 'more' if pan_y > y0 + 5 else 'less' if pan_y < y0 - 5 else 'same'}
        return {'change': out}
    if kind == 'saved':
        return {'saved': ui.saved_names(spec['names'])}
    if kind == 'visible-list':
        snap = ui.snap()
        entries = []
        for control in sorted(snap.get('controls', []), key=lambda c: (c['bounds'][1], c['bounds'][0])):
            value = ' '.join(control.get('text', '').split())
            for name in spec['names']:
                if (value == name or value.startswith(name + ' ')) and name not in entries:
                    entries.append(name)
        return {'names': entries if spec.get('ordered') else sorted(entries)}
    if kind == 'json-keys':
        data = diagram(ctx).data
        required = spec['required']
        return {'properties': {key: key in data and isinstance(data[key],
                              {'list': list, 'text': str, 'object': dict}[typ])
                               for key, typ in required.items()}}
    if kind == 'sql':
        parsed = script(ctx, spec['export'], dialect)
        statement = parsed['statements'].get(spec['key'].casefold())
        if statement is None:
            raise AssertionError(f"the script has no statement for {spec['key']}; it has {parsed['order'][:40]}")
        if 'column' in spec:
            found = [c for c in statement.get('columns', []) if c.get('name') == spec['column']]
            if not found:
                raise AssertionError(f"{spec['key']} defines no column {spec['column']!r}")
            return {'column': found[0]}
        if statement['key'].startswith('table:'):
            return {'table': {k: v for k, v in statement.items() if k != 'columns'},
                    'columns': [c.get('name') for c in statement.get('columns', [])]}
        return {'statement': statement}
    if kind == 'sql-order':
        return {'order': script(ctx, spec['export'], dialect)['order']}
    if kind in ('blocks', 'blocks-order'):
        _, data = exported(ctx, spec['export'])
        try:
            parsed = textblocks.read(spec['format'], data.decode('utf-8'))
        except UnicodeDecodeError:
            raise AssertionError('the export is not UTF-8 text') from None
        if kind == 'blocks-order':
            return {'order': parsed['order']}
        if spec['key'] not in parsed['blocks']:
            raise AssertionError(f"the file has no block {spec['key']}; it has {parsed['order'][:40]}")
        return {'block': parsed['blocks'][spec['key']]}
    if kind == 'text-file':
        _, data = exported(ctx, spec['export'])
        try:
            return {'lines': lines(data.decode('utf-8'))}
        except UnicodeDecodeError:
            raise AssertionError('the export is not UTF-8 text') from None
    if kind == 'image':
        _, data = exported(ctx, spec['export'])
        facts = image_facts(data, spec['texts'], spec.get('absent', []))
        return {'image': facts}
    if kind == 'shown':
        if spec.get('open'):
            ui.call({'op': 'open', 'path': spec['open']})
            ui.wait(1)
        snap = ui.snap()
        for step in spec.get('reveal', []):
            control = ui.find(step, snap, startswith=True)
            if control is not None and control.get('expanded') is not True:
                snap = ui.call({'op': 'click', 'target': {'ref': control['ref']}})
        snap = ui.snap()
        test = ui.shown if spec.get('exact') else ui.contains
        return {'shown': {t: test(t, snap) for t in spec['texts']}}
    if kind == 'clipboard':
        answer = ui.call({'op': 'clipboard', 'action': 'read'})
        content = answer.get('text') or ''
        if spec.get('json'):
            try:
                value = json.loads(content)
            except ValueError:
                raise AssertionError('the clipboard holds no JSON: ' + content[:200]) from None
            if spec['json'] == 'table':
                return {'clipboard': Diagram({'tables': [value]}).table_view(value, spec.get('aspects'))}
            return {'clipboard': {k: text(value.get(k)) for k in spec.get('keys', [])}}
        if spec.get('image'):
            import base64
            payload = answer.get('png_base64')
            if not payload:
                raise AssertionError('the clipboard contains no image')
            try:
                data = base64.b64decode(payload, validate=True)
            except (ValueError, TypeError):
                raise AssertionError('the clipboard image is not valid encoded data') from None
            return {'clipboard': image_facts(data, spec['texts'], spec.get('absent', []))}
        if spec.get('sql'):
            statement = sqlnorm.read(content, dialect)['statements'].get(spec['sql'].casefold())
            if statement is None:
                raise AssertionError(f"the clipboard holds no statement for {spec['sql']}")
            return {'clipboard': statement}
        if spec.get('blocks'):
            parsed = textblocks.read(spec['blocks'], content)
            if spec['key'] not in parsed['blocks']:
                raise AssertionError(f"the clipboard holds no block {spec['key']}; it has {parsed['order'][:40]}")
            return {'clipboard': parsed['blocks'][spec['key']]}
        return {'clipboard': lines(content)}
    if kind == 'transform':
        return {'transform': transform(ui.snap())}
    if kind == 'archive':
        _, data = exported(ctx, spec['export'])
        return {'archive': archive(data)}
    if kind == 'page':
        snap = ui.snap()
        out = {}
        if 'path' in spec:
            out['path'] = bool(re.fullmatch(spec['path'], str(snap.get('url', ''))))
        if 'title' in spec:
            out['title'] = snap.get('title')
        return {'page': out}
    raise ValueError('unknown check type ' + kind)
