'''Public API setup and checkpoint observation of the GUI episodes, independent of the verdicts of the evaluator.

Every read uses the same runtime api operation as the program checks. Values a request supplied (titles, texts, dates)
are compared as they are; generated identities, clock fields and secrets are projected onto the typed aliases of
harness.Normalize, so the observations of the reference and of a candidate relate by a bijection, not by counters.
'''
import hashlib
import json
import re
import time

TEMPLATE = re.compile(r'[{][{]([^{}]+)[}][}]')


def lookup(value, path):
    for part in str(path).split('.'):
        assert isinstance(value, (dict, list)), 'expected a JSON object at ' + part
        try:
            value = value[int(part)] if isinstance(value, list) else value[part]
        except (KeyError, IndexError, ValueError) as error:
            raise AssertionError('missing ' + part + ' in the public state') from error
    return value


def resolve(value, state):
    if isinstance(value, str):
        full = TEMPLATE.fullmatch(value)
        if full:
            return lookup(state, full[1])
        return TEMPLATE.sub(lambda m: str(lookup(state, m[1])), value)
    if isinstance(value, list):
        return [resolve(x, state) for x in value]
    if isinstance(value, dict):
        return {k: resolve(v, state) for k, v in value.items()}
    return value


def request(c, spec):
    spec = resolve(spec, c.state)
    response, payload = c.request(spec['method'], spec['path'], spec.get('actor', 'admin'), body=spec.get('body'),
                                  params=spec.get('params'), multipart=spec.get('multipart'))
    allowed = spec.get('status', 200)
    allowed = allowed if isinstance(allowed, list) else [allowed]
    assert response.status_code in allowed, spec['method'] + ' ' + str(spec['path']) + ': expected ' + str(allowed) + ', received ' + str(response.status_code)
    if spec.get('save'):
        c.state[spec['save']] = payload
    return response, payload


def setup(c, item):
    '''One unscored GUI setup request: any success status; saves only what later steps reference.
    settle waits before the request so that the asynchronous processing of the previous one is finished.'''
    if item.get('method') == 'TODAY':
        from harness import today
        c.state[item['save']] = today().isoformat()
        return
    time.sleep(item.get('settle', 0))
    spec = resolve({k: v for k, v in item.items() if k in ('method', 'path', 'actor', 'body', 'params', 'multipart')}, c.state)
    response, payload = c.request(spec['method'], spec['path'], spec.get('actor', 'admin'), body=spec.get('body'),
                                  params=spec.get('params'), multipart=spec.get('multipart'))
    assert 200 <= response.status_code < 300, 'setup ' + spec['method'] + ' ' + str(spec['path']) + ': status ' + str(response.status_code)
    if item.get('path') == 'admin/users' and item.get('method') == 'POST':
        c.creds[spec['body']['username']] = spec['body']['password']
    if item.get('save'):
        assert isinstance(payload, (dict, list, str, int)), 'setup response is not JSON'
        c.state[item['save']] = payload


def normalize_text(value):
    '''Form encodings and the API differ in line breaks only: CRLF and LF are the same text.'''
    if isinstance(value, str):
        return value.replace(chr(13) + chr(10), chr(10))
    if isinstance(value, list):
        return [normalize_text(x) for x in value]
    if isinstance(value, dict):
        return {k: normalize_text(v) for k, v in value.items()}
    return value


def project(obj, fields):
    return {key: normalize_text(lookup(obj, key)) for key in fields}


def observe(c, check):
    if 'auth' in check:
        spec=check['auth']
        r,p=c.raw({'op':'api','path':'/api/auth/token','method':'POST','binary':True,
                   'form':{'username':spec['username'],'password':spec['password']}})
        if spec.get('accepted',True):
            assert 200 <= r.status_code < 300 and isinstance(p,dict) and p.get('access_token'), 'new credentials not accepted'
            return {'authenticated':True,'token_type':p.get('token_type')}
        assert r.status_code==401, 'old credentials still accepted'
        return {'authenticated':False}
    if 'download' in check:
        import base64
        spec=check['download']
        snap=c.broker.call({'op':'snapshot','session':'main'})
        assert snap.get('downloads'), 'no browser download registered'
        value=c.broker.call({'op':'download','session':'main','ref':snap['downloads'][-1]['ref']})
        assert not value.get('truncated'), 'download is incomplete'
        data=base64.b64decode(value['body_base64'])
        if spec['format']=='json':
            payload=json.loads(data)
            assert isinstance(payload,list), 'expected a JSON entity collection'
            names=sorted(x['name'] for x in payload)
            assert names==sorted(spec['names']), 'downloaded entities differ'
            return {'names':names}
        assert spec['format']=='zip'
        return c.archive(data)

    if 'content_sha256' in check:
        # Stored bytes (an attachment): only their identity matters.
        response, payload = request(c, check['request'])
        digest = hashlib.sha256(response.content).hexdigest()
        assert digest == check['content_sha256'], 'stored bytes differ'
        return {'status': response.status_code, 'content_sha256': digest}
    if 'refused' in check:
        # A refusal counts only together with the positive read in the same observation.
        value = observe(c, {k: v for k, v in check.items() if k != 'refused'})
        response, payload = request(c, check['refused'])
        if response.status_code >= 400:
            return {**value, 'refused': c.observe(response, payload)}
        return {**value, 'refused': {'status': response.status_code}}
    response, payload = request(c, check['request'])
    if response.status_code >= 400:
        return c.observe(response, payload)
    allowed = check['request'].get('status', 200)
    if isinstance(allowed, list):
        return {'status_class': 'accepted-' + ','.join(str(x) for x in allowed)}
    if response.status_code == 204:
        return {'status': 204}
    if check.get('at'):
        payload = lookup(payload, check['at'])
    if isinstance(payload, dict) and isinstance(payload.get('items'), list) and (check.get('where') is not None or check.get('collection')):
        payload = payload['items']
    if check.get('where') is not None:
        wanted = resolve(check['where'], c.state)
        assert isinstance(payload, list), 'expected a resource collection'

        def has(item):
            try:
                return isinstance(item, dict) and all(lookup(item, k) == v for k, v in wanted.items())
            except AssertionError:
                return False
        matches = [x for x in payload if has(x)]
        assert len(matches) == 1, 'expected exactly one resource matching ' + str(wanted)
        payload = matches[0]
        if check['request'].get('save'):
            c.state[check['request']['save']] = payload
    assert isinstance(payload, (dict, list)), 'expected a JSON response'
    fields = check.get('fields', [])
    expected = normalize_text(resolve(check.get('expected'), c.state))
    if check.get('collection'):
        assert isinstance(payload, list), 'expected a list'
        key = lambda x: json.dumps(x, sort_keys=True)
        items = sorted(payload, key=lambda x: key(project(x, fields)))
        value = [project(x, fields) for x in items]
        if expected is not None:
            assert value == sorted(expected, key=key), 'public state differs from requested values'
        shown = [project(c.norm.clean(x), fields) for x in items]
    else:
        value = project(payload, fields)
        if expected is not None:
            assert value == expected, 'public state differs from requested values: ' + repr(value)[:350] + ' expected ' + repr(expected)[:350]
        shown = project(c.norm.clean(payload), fields)
    return {'status': response.status_code, 'value': shown}
