"""Small declarative Data API cases; all I/O uses the task runtime."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import json
import math
import re
import time


class Missing(AssertionError):
    pass


def aspects(**readers):
    """Keep independent observation failures local to their scored aspect."""
    values = {}
    for key, read in readers.items():
        try:
            values[key] = read()
        except (AssertionError, KeyError, ValueError, TypeError, IndexError) as error:
            values[key] = error
    return values


def observed(values, key):
    value = values[key]
    if isinstance(value, Exception):
        raise value
    return value


def checked(value, expected):
    expect(value, expected)
    return value


def timestamp(value):
    assert type(value) in (int, float) and value > 0, 'missing timestamp'
    return '@time'


def boolean(value):
    assert isinstance(value,bool),'expected a boolean flag'
    return value


@dataclass
class Ref:
    name: str
    key: str = 'id'


def resolve(value, state):
    if isinstance(value, Ref):
        if value.name not in state:
            raise Missing('a prerequisite did not produce ' + value.name)
        return state[value.name][value.key]
    if callable(value):
        return value(state)
    if isinstance(value, dict):
        return {k: resolve(v, state) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [resolve(v, state) for v in value]
    if isinstance(value, str):
        def replace(match):
            name = match[1]
            if name not in state or 'id' not in state[name]:
                raise Missing('a prerequisite did not produce ' + name)
            return str(state[name]['id'])
        return re.sub(r'\{([a-zA-Z0-9_-]+)\}', replace, value)
    return value


class Context:
    def __init__(self, broker):
        self.broker, self.values, self.identities = broker, {}, {}

    def call(self, method, path, *, body=None, query=None, save=None, ok=True, **kwargs):
        request = {'op': 'api', 'method': method, 'path': resolve(path, self.values)}
        if body is not None:
            request['json'] = resolve(body, self.values)
        if query is not None:
            request['query'] = resolve(query, self.values)
        request.update(resolve(kwargs, self.values))
        result = self.broker.call(request)
        assert isinstance(result, dict) and isinstance(result.get('status'), int), 'the API returned no HTTP response'
        if ok:
            assert 200 <= result['status'] < 300, f'{method} {path}: HTTP {result["status"]}: {result.get("body")}'
        if save:
            value = result.get('body')
            assert isinstance(value, dict), 'an object response is required'
            self.values[save] = value
            if value.get('id'):
                self.identities[str(value['id'])] = '@' + save
        return result

    def all(self, path, *, fields='id,title', query=None):
        rows = []
        for page in range(1, 101):
            result = self.call('GET', path, query={'fields': fields, 'page': page, 'limit': 100, **(query or {})})
            body = result['body']
            assert isinstance(body, dict) and isinstance(body.get('items'), list), 'missing items list'
            rows += body['items']
            if not body.get('has_more'):
                return rows
        raise AssertionError('pagination did not terminate')

    def clean(self, value):
        if isinstance(value, dict):
            return {k: self.clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if isinstance(value, str):
            for identity, alias in sorted(self.identities.items(), key=lambda kv: len(kv[0]), reverse=True):
                value = value.replace(identity, alias)
            return value.replace('\r\n', '\n')
        return value

    def ready_api(self):
        end = time.monotonic() + 45
        while time.monotonic() < end:
            try:
                result = self.call('GET', '/ping')
                if result.get('body') == 'JoplinClipperServer':
                    return
            except Exception:
                pass
            time.sleep(.25)
        raise AssertionError('local Data API did not become available')


@dataclass
class Case:
    key: str
    description: str
    action: object
    aspects: dict
    dependencies: list = field(default_factory=list)
    expected: dict = field(default_factory=dict)


class Suite:
    def __init__(self, key, feature):
        self.key, self.feature = key, feature
        self.cases, self.setups, self.setup_ids = [], [], []

    def setup(self, key, action, *, before=None):
        self.setups.append((key, action, before))
        self.setup_ids.append('setup:' + key)

    def add(self, key, description, action, aspects, *, depends=(), expected=None, fixtures=None):
        assert key not in {c.key for c in self.cases}, key
        case = Case(key, description, action, aspects,
                    list(self.setup_ids if fixtures is None else fixtures) + list(depends), expected or {})
        self.cases.append(case)
        return key

    def request(self, key, description, method, path, *, body=None, query=None, save=None, fields=(),
                status=False, error=False, depends=(), expected=None, clocks=(), transforms=None, **kwargs):
        requirements = {k: description + ': ' + k.replace('_', ' ') + '.' for k in fields}
        if status:
            requirements['status'] = description + ': response status.'
        if error:
            requirements['error'] = description + ': a meaningful product error is returned.'

        def action(c):
            response = c.call(method, path, body=body, query=query, save=save, ok=not error, **kwargs)
            readers = {}
            if status:
                readers['status'] = lambda: 'success' if 200 <= response['status'] < 300 else response['status']
            if error:
                def explanation():
                    assert response['status'] >= 400, 'the invalid operation was accepted'
                    message = response.get('body')
                    message = message.get('error') if isinstance(message, dict) else message
                    assert isinstance(message, str) and message.strip(), 'missing error explanation'
                    return 'explained'
                readers['error'] = explanation
            obj = response.get('body')
            for name in fields:
                def read(name=name):
                    assert isinstance(obj, dict) and name in obj, 'response lacks ' + name
                    value = obj[name]
                    if name in clocks:
                        value = timestamp(value)
                    if name in ('latitude', 'longitude', 'altitude'):
                        value = round(float(value), 6)
                    value = c.clean(value)
                    if name in (transforms or {}):
                        value = transforms[name](value)
                    return value
                readers[name] = read
            return aspects(**readers)

        return self.add(key, description, action, requirements, depends=depends, expected=expected)

    def manifest(self):
        setup = []
        for name, _fn, before in self.setups:
            item = {'id': name, 'protocol_setup': name}
            if before:
                item['before'] = before
            setup.append(item)
        checkpoints = []
        for case in self.cases:
            checkpoints.append({'id': case.key, 'goal': case.description, 'depends_on': case.dependencies,
                                'assertions': [{'id': f'{self.key}/{case.key}/{name}', 'channel': 'backend',
                                                'method': 'program', 'requirement': description, 'aspect': name}
                                               for name, description in case.aspects.items()]})
        return {'id': self.key, 'feature': self.feature, 'execution': 'program',
                'initial_state': 'Fresh desktop profile; the declared setup uses only the public local Data API.',
                'inputs': {}, 'setup': setup, 'checkpoints': checkpoints}


def project(rows, fields, c, *, ordered=False):
    assert isinstance(rows, list), 'expected an item list'
    output = []
    for row in rows:
        assert isinstance(row, dict), 'expected an object in the list'
        assert all(k in row for k in fields), 'an item lacks requested fields'
        output.append(c.clean({k: row[k] for k in fields}))
    return output if ordered else sorted(output, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))


def expect(actual, expected):
    if isinstance(expected, float):
        assert math.isclose(float(actual), expected, rel_tol=1e-7, abs_tol=1e-6), (actual, expected)
    else:
        assert actual == expected, f'{actual!r} != {expected!r}'


def b64(data):
    return base64.b64encode(data.encode() if isinstance(data, str) else data).decode()
