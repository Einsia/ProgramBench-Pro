'''Public API setup and checkpoint observation of the GUI episodes, independent of the verdicts of the evaluator.

Every read uses the same runtime api operation as the program checks. Values a request supplied (titles, texts, dates)
are compared as they are; generated identities, clock fields and secrets are projected onto the typed aliases of
harness.Normalize, so the observations of the reference and of a candidate relate by a bijection, not by counters.
'''
import hashlib
import json
import re
import time
from harness import semantic_equal, semantic, unordered

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
    time.sleep(item.get('settle', 0))
    spec = resolve({k: v for k, v in item.items() if k in ('method', 'path', 'actor', 'body', 'params', 'multipart')}, c.state)
    response, payload = c.request(spec['method'], spec['path'], spec.get('actor', 'admin'), body=spec.get('body'),
                                  params=spec.get('params'), multipart=spec.get('multipart'))
    assert 200 <= response.status_code < 300, 'setup ' + spec['method'] + ' ' + str(spec['path']) + ': status ' + str(response.status_code)
    if item.get('save'):
        assert isinstance(payload, (dict, list)), 'setup response is not JSON'
        if isinstance(payload,dict) and isinstance(payload.get('created_object_id'),str) and payload['created_object_id'].isdigit():
            payload['created_object_id']=int(payload['created_object_id'])
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
    if check.get('manual'):
        from fixtures import manual_pdf
        from harness import b64
        ident=resolve(check['equipment'],c.state)
        r,p=c.request('GET','objects/equipment/'+str(ident))
        assert r.status_code==200 and p.get('instruction_manual_file_name'),'manual attachment missing'
        r,p=c.request('GET','files/equipmentmanuals/'+b64(p['instruction_manual_file_name']))
        assert r.status_code==200 and r.content==manual_pdf(),'manual bytes differ'
        return {'attached_manual_sha256':hashlib.sha256(r.content).hexdigest()}
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
    if check.get('where') is not None:
        wanted = resolve(check['where'], c.state)
        assert isinstance(payload, list), 'expected a resource collection'

        def has(item):
            try:
                return isinstance(item, dict) and all(semantic_equal(lookup(item,k),v,k,check['request']['path']) for k,v in wanted.items())
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
    path=resolve(check['request']['path'],c.state)
    hint='numeric-setting' if '/settings/' in '/'+path else 'object'
    if check.get('collection'):
        assert isinstance(payload,list),'expected a list'
        value=[project(x,fields) for x in payload]
        if expected is not None:
            assert semantic_equal(unordered(value),unordered(expected),path=path),'public collection differs from requested values'
        shown=unordered([c.norm.clean(x,hint=hint) for x in value])
    else:
        value=project(payload,fields)
        if expected is not None:
            assert semantic_equal(value,expected,path=path),'public state differs from requested values'
        shown=c.norm.clean(value,hint=hint)
    return {'status':response.status_code,'value':shown}
