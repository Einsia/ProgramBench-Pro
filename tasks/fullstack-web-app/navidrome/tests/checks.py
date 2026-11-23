'''Public setup and checkpoint observation for the GUI episodes, independent of agent verdicts.

Every read goes through the runtime channels the model also has: the product native API with the account token, the
OpenSubsonic API and the sign-in endpoint.'''
import base64
import json
import re
import time


def lookup(value, path):
    for part in str(path).split('.'):
        assert isinstance(value, (dict, list)), 'expected a JSON object at ' + part
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def resolve(value, state):
    if isinstance(value, str):
        full = re.fullmatch(r'\{\{([^{}]+)\}\}', value)
        if full:
            return lookup(state, full[1])
        return re.sub(r'\{\{([^{}]+)\}\}', lambda m: str(lookup(state, m[1])), value)
    if isinstance(value, list):
        return [resolve(x, state) for x in value]
    if isinstance(value, dict):
        return {k: resolve(v, state) for k, v in value.items()}
    return value


def normalize_text(value):
    '''Form posts and the API encode the same text with different line endings.'''
    crlf = chr(13) + chr(10)
    if isinstance(value, str):
        return value.replace(crlf, chr(10))
    if isinstance(value, list):
        return [normalize_text(x) for x in value]
    if isinstance(value, dict):
        return {k: normalize_text(v) for k, v in value.items()}
    return value


def has(item, path, wanted):
    try:
        return lookup(item, path) == wanted
    except (KeyError, IndexError, TypeError, ValueError, AssertionError):
        return False


def ordered(items):
    return sorted(items, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))


def fetch(c, spec):
    '''One read: (status, payload, answer). OpenSubsonic failures answer as a failed:<code> status.'''
    spec = resolve(spec, c.state)
    kind = spec.get('api', 'native')
    if kind == 'login':
        answer = c.http('POST', '/auth/login', body={'username': spec['user'], 'password': spec['password']})
        return answer['status'], answer['body'], answer
    if kind == 'subsonic':
        answer = c.subsonic(spec['op'], spec.get('actor', 'admin'), password=spec.get('password'),
                            **dict(spec.get('query') or {}))
        reply = c.reply(answer)
        if reply.get('status') != 'ok':
            return 'failed:' + str((reply.get('error') or {}).get('code')), reply, answer
        payload = reply
        if spec.get('extract'):
            for part in spec['extract'].split('.'):
                payload = payload.get(part) if isinstance(payload, dict) else None
                if payload is None:
                    break
            if payload is None:
                payload = []  # the product leaves an empty collection out of the reply
        return 200, payload, answer
    answer = c.native(spec.get('method', 'GET'), spec['path'], spec.get('actor', 'admin'), body=spec.get('body'),
                      params=spec.get('params'))
    return answer['status'], answer['body'], answer


def library_change(c, item):
    '''Unscored change of the music folder through the runtime library operations, followed by the scan the item names
    (quick, full or none: a new song file is left for the goal to scan).'''
    if 'library_put' in item:
        import api_scan
        if 'text' in item:
            data = item['text'].encode()
        elif item['library_put'] == api_scan.ADDED['path']:
            data = api_scan.made(api_scan.ADDED)
        else:
            data = c.library_files()[item['library_put']]
        answer = c.call({'op': 'library_put', 'path': item['library_put'], 'base64': base64.b64encode(data).decode()})
        assert answer.get('size') == len(data), 'library_put ' + item['library_put']
    else:
        c.call({'op': 'library_delete', 'path': item['library_delete']})
    if item.get('scan'):
        c.rescan(item['scan'] == 'full')


def setup(c, item):
    '''One unscored setup request: any success status; keeps only what later steps reference.'''
    time.sleep(item.get('settle', 0))
    if 'library_put' in item or 'library_delete' in item:
        library_change(c, item)
        return
    spec = {k: v for k, v in item.items() if k not in ('id', 'settle', 'before', 'save', 'where')}
    status, payload, _answer = fetch(c, spec)
    assert isinstance(status, int) and 200 <= status < 300, 'setup %s: status %s' % (item['id'], status)
    if item.get('where') is not None:
        # A lookup keeps the one object that matches (with no values: the only object).
        matches = [x for x in payload if isinstance(x, dict) and all(has(x, k, v) for k, v in item['where'].items())]
        assert len(matches) == 1, 'setup %s: %d objects match %s' % (item['id'], len(matches), item['where'])
        payload = matches[0]
    if item.get('save'):
        c.state[item['save']] = payload


def observe(c, check):
    '''One independent read of a checkpoint. A check with wait reads again (up to that many seconds) until the state
    equals the requested values: state the product updates after the goal (play counts after playback) is compared
    once it has settled.'''
    deadline = time.monotonic() + check.get('wait', 0)
    while True:
        try:
            return read_once(c, check)
        except AssertionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)


def read_once(c, check):
    if 'refused' in check:
        # A refusal counts only together with the positive read in the same observation.
        value = read_once(c, {k: v for k, v in check.items() if k != 'refused'})
        status, _payload, _answer = fetch(c, check['refused'])
        allowed = check['refused'].get('status', 401)
        allowed = allowed if isinstance(allowed, list) else [allowed]
        assert status in allowed, 'the refused request answered %s, expected %s' % (status, allowed)
        return {**value, 'refused': {'status': status}}
    status, payload, _answer = fetch(c, check)
    allowed = check.get('status', 200)
    allowed = allowed if isinstance(allowed, list) else [allowed]
    assert status in allowed, 'expected status %s, received %s' % (allowed, status)
    if not isinstance(status, int) or status >= 400 or status == 204:
        return {'status': status}
    if check.get('where') is not None:
        wanted = resolve(check['where'], c.state)
        assert isinstance(payload, list), 'expected a resource collection'
        matches = [x for x in payload if isinstance(x, dict) and all(has(x, k, v) for k, v in wanted.items())]
        assert len(matches) == 1, 'expected exactly one resource matching ' + str(wanted)
        payload = matches[0]
    if check.get('save'):
        c.state[check['save']] = payload
    fields = check.get('fields', [])

    def project(obj):
        out = {}
        for key in fields:
            # A field name that ends with a question mark is optional: the product leaves it out (or answers zero or an
            # empty value) when nothing is set, and both read as None.
            optional = key.endswith('?')
            name = key[:-1] if optional else key
            try:
                value = normalize_text(lookup(obj, name))
            except (KeyError, IndexError, TypeError, AssertionError):
                if not optional:
                    raise AssertionError('missing field ' + name) from None
                value = None
            if optional and value in (0, '', [], {}, False):
                value = None
            out[name] = value
        return out
    if check.get('collection'):
        assert isinstance(payload, list), 'expected a list'
        value = ordered([project(x) for x in payload])
    else:
        assert isinstance(payload, (dict, list)), 'expected a JSON response'
        value = [project(x) for x in payload] if isinstance(payload, list) else project(payload)
    expected = resolve(check.get('expected'), c.state)
    if expected is not None:
        expected = normalize_text(expected)
        if check.get('collection'):
            expected = ordered(expected)
        assert value == expected, 'public state differs from the requested values: ' + json.dumps(value, ensure_ascii=False)[:300]
    return {'status': 200, 'value': value}
