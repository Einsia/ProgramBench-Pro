"""Program checks: one observation per assertion, read through the runtime's channels and compared semantically.

Every observation is a JSON value. Numbers compare within half a cent, text after trimming, lists in the order the check
fixes (a check that sorts states its sort key, so equal keys cannot decide the result).
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

import documents
import ledger

TOLERANCE = 0.0051


def _scratch(ctx):
    if 'scratch' not in ctx.state:
        ctx.state['scratch'] = tempfile.TemporaryDirectory(prefix='mmex-', dir=os.environ.get('TMPDIR'))
    return Path(ctx.state['scratch'].name)


def release(ctx):
    for view in ctx.state.get('observed', {}).values():
        if isinstance(view, ledger.View):
            view.close()
    ctx.state['observed'] = {}


def fetch(ctx, area, name):
    """The bytes of one exchange file; AssertionError when it is missing or cannot be fetched."""
    from evaluation.broker import BrokerError
    try:
        answer = ctx.broker.call({'op': 'download', 'area': area, 'filename': name})
    except BrokerError as exc:
        raise AssertionError(f'{name} could not be read from the {area}: {exc.detail}') from None
    return base64.b64decode(answer['body_base64'])


def listing(ctx, area):
    return [item['name'] for item in ctx.broker.call({'op': 'list_files', 'area': area})['files']]


def database(ctx, area, name):
    """The semantic view of one database document (read once per checkpoint; a torn read is repeated)."""
    key = ('db', area, name)
    cache = ctx.state.setdefault('observed', {})
    if key in cache:
        return cache[key]
    path = _scratch(ctx) / f'{len(cache)}-{area}-{Path(name).name}'
    last = None
    for _ in range(12):
        path.write_bytes(fetch(ctx, area, name))
        view = ledger.View(path)
        try:
            view.db.execute('SELECT COUNT(*) FROM sqlite_master').fetchone()
            cache[key] = view
            return view
        except sqlite3.Error as exc:
            view.close()
            last = exc
            time.sleep(.5)
    raise AssertionError(f'{name} is not a readable database: {last}')


def settle_database(ctx, area, name, quiet=3.0, timeout=45.0):
    """Program episodes: wait until the product has stopped writing the database."""
    deadline = time.monotonic() + timeout
    last, since = None, time.monotonic()
    while time.monotonic() < deadline:
        data = fetch(ctx, area, name)
        now = time.monotonic()
        if data != last:
            last, since = data, now
        elif now - since >= quiet:
            return
        time.sleep(.5)
    raise AssertionError(f'{name} did not stop changing within {timeout:g} seconds')


def program_prepare(ctx, checkpoint):
    for action in checkpoint.get('actions', ()):
        answer = ctx.broker.call(action)
        if action['op'] in ('restart', 'reset') and not answer.get('ready'):
            raise AssertionError('the application did not become ready after ' + action['op'])
    settle = checkpoint.get('settle')
    if settle:
        settle_database(ctx, settle.get('area', 'inbox'), settle['file'], settle.get('quiet', 3.0), settle.get('timeout', 45.0))


def prepare(ctx, checkpoint):
    if checkpoint.get('measure_database'):
        check = checkpoint['measure_database']
        ctx.state['database_before'] = database_stats(fetch(ctx, check.get('area','inbox'), check.get('file','ledger.mmb')))


def database_stats(data):
    db = sqlite3.connect(':memory:')
    try:
        db.deserialize(data)
        return {'pages': db.execute('PRAGMA page_count').fetchone()[0],
                'free': db.execute('PRAGMA freelist_count').fetchone()[0], 'bytes': len(data)}
    finally:
        db.close()


def _unique(rows, match, table):
    found = [row for row in rows if ledger.matches(row, match)]
    if len(found) != 1:
        raise AssertionError(f'{len(found)} {table} rows match {match}')
    return found[0]


def _visible(row):
    return {key: value for key, value in row.items() if not key.startswith('_')}


def observe(ctx, check):
    kind = check['kind']
    if kind == 'compact':
        before = ctx.state['database_before']
        after = database_stats(fetch(ctx, check.get('area','inbox'), check.get('file','ledger.mmb')))
        return {'reclaimed': before['free'] > 0 and after['free'] < before['free'] and after['bytes'] < before['bytes'],
                'valid': after['pages'] > 0}
    if kind == 'encrypted':
        import encryption
        raw = fetch(ctx, check['area'], check['file'])
        clear = encryption.decrypt(raw, check['password'])
        try:
            encryption.decrypt(raw, check['wrong_password'])
        except AssertionError:
            pass
        else:
            raise AssertionError('encrypted document accepts an incorrect password')
        path = _scratch(ctx) / 'decrypted.mmb'
        path.write_bytes(clear)
        view = ledger.View(path)
        try:
            return {table: sorted([_visible(row) for row in view.table(table)], key=lambda r: json.dumps(r, sort_keys=True))
                    for table in ('account','trx','payee','category','tag')}
        finally:
            view.close()
    if kind == 'attachment-content':
        names = [r['name'] for r in ctx.broker.call({'op':'list_files','area':'outbox','recursive':True})['files']
                 if r['name'].lower().endswith('.txt') and Path(r['name']).name.lower() != 'readme.txt']
        expected = fetch(ctx,'inbox',check['input'])
        if check.get('removed'):
            return {'remaining_payloads': len(names)}
        if len(names) != 1:
            raise AssertionError(f'expected one archived document, found {len(names)}')
        actual = fetch(ctx,'outbox',names[0])
        if actual != expected:
            raise AssertionError('archived attachment differs from the uploaded bytes')
        return {'content_sha256':hashlib.sha256(actual).hexdigest(),'size':len(actual)}
    if kind == 'backup':
        candidates=sorted(name for name in listing(ctx,'inbox') if re.fullmatch(check['pattern'],name))
        if not candidates:
            raise AssertionError('no database backup was created')
        nested=dict(check['check'],area='inbox',file=candidates[-1])
        return observe_database(ctx,nested)
    if kind in ('row', 'rows', 'count', 'names', 'info', 'schema'):
        return observe_database(ctx, check)
    if kind == 'files':
        regex = re.compile(check.get('pattern', '.*'))
        return sorted(name for name in listing(ctx, check['area']) if regex.fullmatch(name))
    if kind == 'clipboard':
        from evaluation.broker import BrokerError
        try:
            text = ctx.broker.call({'op': 'clipboard_text'})['text']
        except BrokerError as exc:
            raise AssertionError('the clipboard holds no text: ' + exc.detail) from None
        return documents.lines(text)
    if kind == 'plain':
        data = fetch(ctx, check['area'], check['file'])
        return {'plain_sqlite': data.startswith(b'SQLite format 3\x00'), 'empty': not data}
    if kind == 'window':
        titles = [w['title'] for w in ctx.broker.call({'op': 'windows'})['windows']]
        return [title for title in titles if check['contains'] in title][:1]
    if kind == 'document':
        data = fetch(ctx, check['area'], check['file'])
        return documents.observe(data, check)
    raise ValueError('unknown program check ' + kind)


def observe_database(ctx, check):
    view = database(ctx, check.get('area', 'inbox'), check.get('file', 'ledger.mmb'))
    kind = check['kind']
    try:
        if kind == 'schema':
            return view.schema_version() if check.get('what', 'version') == 'version' else view.tables()
        if kind == 'info':
            for row in view.table('info'):
                if row['name'].casefold() == check['name'].casefold():
                    return row['value']
            raise AssertionError(f'the database has no setting {check["name"]}')
        rows = view.table(check['table'])
        match = check.get('match') or {}
        selected = [row for row in rows if ledger.matches(row, match)]
        if kind == 'row':
            if len(selected) != 1:
                raise AssertionError(f'{len(selected)} {check["table"]} rows match {match}')
            return selected[0].get(check['field'])
        if kind == 'count':
            return len(selected)
        if kind == 'names':
            return sorted((str(row[check['field']]) for row in selected), key=str.casefold)
        if kind == 'rows':
            fields = check['fields']
            sort = check.get('sort') or fields
            selected = sorted(selected, key=lambda row: tuple(_sortable(row.get(key)) for key in sort))
            return [{key: row.get(key) for key in fields} for row in selected]
    except sqlite3.Error as exc:
        raise AssertionError('the database cannot answer this check: ' + str(exc)) from None
    raise ValueError('unknown database check ' + kind)


def _sortable(value):
    if isinstance(value, str):
        return (1, value.casefold())
    if isinstance(value, (int, float)):
        return (0, value)
    return (2, json.dumps(value, sort_keys=True))


MONEY_FIELDS = {'amount', 'to_amount', 'balance', 'value', 'commission', 'minimum_balance', 'credit_limit',
                'minimum_payment', 'TRANSAMOUNT', 'TOTRANSAMOUNT', 'INITIAL_BALANCE', 'AMOUNT'}
INTEGER_FIELDS = {'active','scale','color','repeats','occurrences','statement_locked','kind'}
PRECISE_FIELDS = {'rate', 'price', 'current', 'shares', 'number', 'interest'}


def same(actual, expected, tolerance=0.0051, field=None):
    """Semantic equality of two observations."""
    if isinstance(expected, bool) or isinstance(actual, bool):
        return actual == expected
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if field in INTEGER_FIELDS or (isinstance(expected, int) and isinstance(actual, int)):
            return actual == expected
        return abs(actual - expected) <= (0.00000051 if field in PRECISE_FIELDS else tolerance)
    if isinstance(expected, str) and isinstance(actual, str):
        return actual.strip() == expected.strip()
    if isinstance(expected, list) and isinstance(actual, list):
        return len(actual) == len(expected) and all(same(a, e, tolerance, field) for a, e in zip(actual, expected))
    if isinstance(expected, dict) and isinstance(actual, dict):
        return set(actual) == set(expected) and all(same(actual[k], expected[k], tolerance, k) for k in expected)
    return actual == expected


def _short(value):
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 300 else text[:297] + '...'


def compare(actual, expected, check):
    tolerance = check.get('tolerance', 0.00000051 if check.get('table') in ('stock_history', 'currency_history') else TOLERANCE)
    if check['kind'] in ('count', 'schema'):
        tolerance = 0
    if not same(actual, expected, tolerance, check.get('field')):
        raise AssertionError(f'observed {_short(actual)}, expected {_short(expected)}')


def expect(value, check):
    """Record-only guard: the reference produced the state the specification declares (a wrong recipe stops the record)."""
    if 'expect' in check:
        compare(value, check['expect'], check)
    if check.get('nonempty') and value in (None, '', [], {}):
        raise AssertionError('the reference observation is empty')
