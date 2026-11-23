"""Public API setup and checkpoint observation for GUI episodes, independent of agent verdicts.

Setup items are JSON-RPC calls through the runtime's api operation (any successful answer). Program checks read the
public state through the same channel and project it onto the fields the goal is about; identities are shown by
their names (column titles, usernames, category names) so that the observation does not depend on generated ids.
Downloads that a checkpoint produces are retrieved through the runtime's download operation.
"""
import base64
import csv
import io
import json
import re
from pathlib import Path

from harness import resolve

TEMPLATE = re.compile(r'\{\{([^{}]+)\}\}')
IDENTITY_COLUMNS = {'Task Id'}


def lookup(value, path):
    for part in path.split('.'):
        if isinstance(value, list):
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise AssertionError('expected a JSON object at ' + part)
    return value


def fill(value, state):
    """Resolve {{key}} and {{key.path}} templates from the episode state."""
    if isinstance(value, str):
        full = TEMPLATE.fullmatch(value)
        if full:
            return lookup(state, full[1])
        return TEMPLATE.sub(lambda m: str(lookup(state, m[1])), value)
    if isinstance(value, list):
        return [fill(x, state) for x in value]
    if isinstance(value, tuple):
        return tuple(fill(x, state) for x in value)
    if isinstance(value, dict):
        return {k: fill(v, state) for k, v in value.items()}
    return value


def inputs(ctx, episode):
    for name, content in (episode.get('files') or {}).items():
        data = base64.b64decode(content['base64']) if isinstance(content, dict) else content.encode()
        (Path(ctx.inputs) / name).write_bytes(data)


def setup(c, item):
    """One unscored setup call: any successful answer; saves the result for later templates."""
    result = c.call(item['method'], fill(item.get('params'), c.state), fill(item.get('actor', 'app'), c.state))
    assert result not in (False, None), f"setup {item['method']} did not succeed: {result!r}"
    if item.get('save'):
        c.state[item['save']] = result


def prepare(c, checkpoint):
    """Unscored API calls made right before a checkpoint (actions of other users); failures block the checkpoint."""
    for item in checkpoint.get('prepare') or []:
        setup(c, item)


def begin(ctx, c, checkpoint):
    pass


def collect(ctx, c, checkpoint):
    """Retrieve the product downloads the checkpoint left pending (the evaluator's or the recipe's)."""
    if not checkpoint.get('download'):
        return
    snap = c.broker.call({'op': 'snapshot', 'session': 'main'})
    files = []
    for item in snap.get('downloads') or []:
        answer = c.broker.call({'op': 'download', 'session': 'main', 'ref': item['ref']})
        files.append({'filename': answer.get('filename'), 'content': base64.b64decode(answer.get('body_base64') or '')})
    c.state.setdefault('downloads', {})[checkpoint['id']] = files


# -- derived names -------------------------------------------------------------------------------------------------
def names(c, kind, project_id):
    key = ('names', kind, project_id)
    if key not in c.state:
        if kind == 'column':
            rows = c.call('getColumns', [project_id], 'app')
            c.state[key] = {str(x['id']): x['title'] for x in rows}
        elif kind == 'swimlane':
            rows = c.call('getAllSwimlanes', [project_id], 'app')
            c.state[key] = {str(x['id']): x['name'] for x in rows}
        elif kind == 'category':
            rows = c.call('getAllCategories', [project_id], 'app')
            c.state[key] = {str(x['id']): x['name'] for x in rows}
    return c.state[key]


def username(c, user_id):
    if not user_id or str(user_id) == '0':
        return None
    user = c.call('getUser', [user_id], 'app')
    return user['username'] if isinstance(user, dict) else None


def project_name(c, project_id):
    project = c.call('getProjectById', [project_id], 'app')
    return project.get('name') if isinstance(project, dict) else None


def derive(c, record, fields):
    """Names of the identities a record refers to."""
    out = {}
    project_id = record.get('project_id')
    for field in fields:
        if field == 'column':
            out[field] = names(c, 'column', project_id).get(str(record.get('column_id')))
        elif field == 'swimlane':
            out[field] = names(c, 'swimlane', project_id).get(str(record.get('swimlane_id')))
        elif field == 'category':
            out[field] = names(c, 'category', project_id).get(str(record.get('category_id')))
        elif field == 'owner':
            out[field] = username(c, record.get('owner_id'))
        elif field == 'creator':
            out[field] = username(c, record.get('creator_id'))
        elif field == 'author':
            out[field] = username(c, record.get('user_id'))
        elif field == 'project':
            out[field] = project_name(c, project_id)
        elif field == 'tags':
            tags = c.call('getTaskTags', [record['id']], 'app')
            out[field] = sorted((tags or {}).values()) if isinstance(tags, dict) else []
        elif field == 'subtasks':
            rows = c.call('getAllSubtasks', [record['id']], 'app')
            out[field] = [[x['title'], x['status'], x.get('username')] for x in rows]
        elif field == 'comments':
            rows = c.call('getAllComments', [record['id']], 'app')
            out[field] = [[x['comment'], x.get('username')] for x in rows]
        elif field == 'links':
            rows = c.call('getAllTaskLinks', [record['id']], 'app')
            out[field] = sorted([x['label'], x['title']] for x in rows)
        elif field == 'external':
            rows = c.call('getAllExternalTaskLinks', [record['id']], 'app')
            out[field] = sorted([x['title'], x['url'], x['dependency']] for x in rows)
        elif field == 'files':
            rows = c.call('getAllTaskFiles', [record['id']], 'app')
            out[field] = sorted([x['name'], x['size']] for x in rows)
        else:
            raise ValueError('unknown derived field ' + field)
    return out


def normalize_text(value):
    """HTML form CRLF and API LF encode the same text, not different content."""
    if isinstance(value, str):
        return value.replace('\r\n', '\n')
    if isinstance(value, list):
        return [normalize_text(x) for x in value]
    if isinstance(value, dict):
        return {k: normalize_text(v) for k, v in value.items()}
    return value


def moment_days(value):
    """A business timestamp as its calendar day (UTC): what a date chosen in a form means."""
    import time as _time
    if not value:
        return value
    return _time.strftime('%Y-%m-%d', _time.gmtime(int(value)))


def project_record(c, record, check):
    value = {}
    for field in check['fields']:
        raw = lookup(record, field)
        if field in ('date_due', 'date_started'):
            raw = moment_days(raw)
        value[field] = normalize_text(raw)
    for field in check.get('present') or ():
        value[field] = bool(lookup(record, field))
    value.update(derive(c, record, check['derive']))
    return value


def observe(ctx, c, checkpoint, check):
    if 'csv' in check:
        return observe_csv(c, checkpoint, check)
    if 'refused' in check:
        # A refusal counts only together with the positive read in the same observation.
        value = observe(ctx, c, checkpoint, {k: v for k, v in check.items() if k != 'refused'})
        spec = fill(check['refused'], c.state)
        response = c.rpc(spec['method'], spec.get('params'), spec.get('actor', 'app'))
        refused = response.status >= 400 or (response.has_result and response.result in (False, None, [], {}))
        assert refused, 'the refused request was performed: ' + json.dumps(response.body)[:200]
        return {**value, 'refused': True}
    params = fill(check.get('params'), c.state)
    actor = fill(check.get('actor', 'app'), c.state)
    if check.get('token_auth'):
        me = c.call(check['method'], params, actor)
        token = me.get('api_access_token') if isinstance(me, dict) else None
        assert token, 'the account has no personal access token'
        answer = c.rpc('getVersion', None, ('secret', me['username'], token))
        assert answer.has_result, 'the personal access token does not authenticate: ' + json.dumps(answer.body)[:200]
        return {'token': 'authenticates'}
    if check.get('user_feeds'):
        # The personal feeds behind the account's public-access token (read as the feeds module reads the project
        # feeds); the token itself is never compared.
        import api_feeds
        me = c.call(check['method'], params, actor)
        token = me.get('token') if isinstance(me, dict) else None
        assert token, 'the account has no public-access token'
        return {'feed': api_feeds.atom(c, c.http('GET', '/feed/user/' + token)),
                'ical': api_feeds.ical(c, c.http('GET', '/ical/user/' + token))}
    response = c.rpc(check['method'], params, actor)
    if check.get('status'):
        return {'http': response.status, 'outcome': c.outcome(response)}
    assert response.has_result, f"{check['method']}: {json.dumps(response.body)[:300]}"
    result = response.result
    expected = fill(check.get('expected'), c.state)
    if check.get('where') is not None:
        wanted = fill(check['where'], c.state)
        assert isinstance(result, list), 'expected a collection'
        matches = [x for x in result if isinstance(x, dict) and all(lookup(x, k) == v for k, v in wanted.items())]
        if check.get('expect_none'):
            assert not matches, 'a record matching ' + str(wanted) + ' exists'
            return {'absent': wanted}
        assert len(matches) == 1, f'expected exactly one record matching {wanted}, found {len(matches)}'
        result = matches[0]
    if check.get('save'):
        c.state[check['save']] = result
    if check.get('collection'):
        assert isinstance(result, list), 'expected a list'
        value = sorted((project_record(c, x, check) for x in result), key=lambda x: json.dumps(x, sort_keys=True))
    elif check['fields'] or check['derive'] or check.get('present'):
        assert isinstance(result, dict), 'expected a record: ' + json.dumps(result)[:200]
        value = project_record(c, result, check)
    else:
        value = c.norm.clean(result)
    if expected is not None:
        expected = normalize_text(expected)
        if check.get('collection'):
            expected = sorted(expected, key=lambda x: json.dumps(x, sort_keys=True))
        assert value == expected, ('public state differs from requested values: '
                                   + json.dumps(value, ensure_ascii=False)[:400])
    return {'value': value}


def observe_csv(c, checkpoint, check):
    """A downloaded CSV export: its header and rows (projected to the named columns)."""
    files = c.state.get('downloads', {}).get(checkpoint['id']) or []
    assert files, 'no product download was produced'
    content = files[-1]['content']
    text = content.decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(text)))
    assert rows, 'the download is empty'
    header = rows[0]
    columns = check['csv']
    missing = [x for x in columns if x not in header]
    assert not missing, 'export columns missing: ' + ', '.join(missing)
    picked = [[row[header.index(x)] if header.index(x) < len(row) else '' for x in columns] for row in rows[1:]]
    # Identity columns show the task by its name in this run (the store's numbering is not behavior).
    for name in columns:
        if name in IDENTITY_COLUMNS:
            for row in picked:
                i = columns.index(name)
                row[i] = c.norm.ident('task', row[i])
    value = {'columns': columns, 'rows': sorted(picked)}
    expected = check.get('expected')
    if expected is not None:
        assert value['rows'] == sorted(expected), 'exported rows differ: ' + json.dumps(value['rows'])[:400]
    return value
