"""Public setup, input files and checkpoint observations of the GUI episodes, independent of agent verdicts.

Setup items publish local web resources and prepare product state through the public API (any success
status). Checks read the resulting product state through the API and compare a projection of it."""
import base64
import json
import re
import time

from harness import norm_text


def lookup(value, path):
    for part in path.split('.'):
        if isinstance(value, list):
            value = value[int(part)]
        else:
            assert isinstance(value, dict), 'expected a JSON object at ' + part
            value = value[part]
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


def inputs(ctx):
    """Input files a GUI episode offers the evaluator (for example an OPML document to import)."""
    for name, text in (ctx.episode.get('files') or {}).items():
        (ctx.inputs / name).write_bytes(text.encode() if isinstance(text, str) else base64.b64decode(text['base64']))


def setup(c, item):
    """One unscored GUI setup item: a local web resource or a public API request (any success status)."""
    time.sleep(item.get('settle', 0))
    if 'web' in item:
        spec = resolve(item['web'], c.state)
        body = base64.b64decode(spec['body_base64']) if 'body_base64' in spec else spec.get('body', '')
        c.web_put(spec['url'], body, spec.get('content_type'), spec.get('status', 200), spec.get('headers'),
                  spec.get('auth'))
        return
    if 'mark' in item:
        # Set the status or star of one entry known by its title.
        spec = resolve(item['mark'], c.state)
        actor = spec.get('actor', 'alice')
        r, payload = c.request('GET', 'entries', actor, params={'limit': 500})
        assert r.status_code == 200, 'entries unavailable'
        found = [e['id'] for e in payload['entries'] if e['title'] == spec['title']]
        assert len(found) == 1, 'entry not found: ' + spec['title']
        change = {k: spec[k] for k in ('status', 'starred') if k in spec}
        r, _ = c.request('PUT', 'entries', actor, body={'entry_ids': found, **change})
        assert 200 <= r.status_code < 300, f'setup mark {spec["title"]}: status {r.status_code}'
        return
    spec = resolve({k: v for k, v in item.items() if k in ('method', 'path', 'actor', 'body', 'form')}, c.state)
    r, payload = c.request(spec['method'], spec['path'], spec.get('actor', 'alice'), body=spec.get('body'),
                           form=spec.get('form'))
    assert 200 <= r.status_code < 300, f"setup {spec['method']} {spec['path']}: status {r.status_code}"
    if item.get('save'):
        c.state[item['save']] = payload


def project(value, fields):
    out = {}
    for key in fields:
        try:
            out[key] = lookup(value, key)
        except (KeyError, IndexError, ValueError) as exc:
            raise AssertionError('field missing in the product state: ' + key) from exc
    return out


def actor_of(value):
    """A JSON actor: a baseline account name, null (anonymous) or [username, password]."""
    return tuple(value) if isinstance(value, list) else value


def observe(c, check):
    """A read of the public product state after a GUI checkpoint: status and a projection of named fields.
    With `items`, the named member of the response is read; with `where`, the collection member matching the given
    fields is selected; with `collection`, every member is projected and the result compared as a multiset;
    `contains` reports whether a field contains a text and `at_least` whether a number reaches a minimum;
    `expected` must hold exactly. A `refused` request (the same read by an identity that must not succeed) is part of
    the observation. A `web` check reports whether the product fetched given URLs of the local web."""
    if 'web' in check:
        # Whether the product itself fetched the named URLs from the local web, and how often (fetches made
        # during the episode's setup count too).
        wanted = check['web']['fetched']
        read = lambda: {u: len([x for x in c.web_requests() if x['method'] == 'GET' and x['url'] == u])
                        for u in wanted}
        least = check['web'].get('at_least', {})
        counts = c.wait(read, lambda got: all(got[u] >= n for u, n in least.items()), seconds=10)
        value = {u: {'fetched': counts[u] > 0, 'again': counts[u] > 1} if check['web'].get('again') else
                 counts[u] > 0 for u in wanted}
        value = json.loads(norm_text(json.dumps(value)))
        expected = check.get('expected')
        if expected is not None:
            assert value == expected, 'the product fetched: ' + json.dumps(counts)[:400]
        return {'fetched': value}
    spec = resolve(check['request'], c.state)
    if check.get('settle'):
        time.sleep(check['settle'])
    r, payload = c.request(spec.get('method', 'GET'), spec['path'], actor_of(spec.get('actor', 'alice')),
                           body=spec.get('body'))
    status = spec.get('status', 200)
    allowed = status if isinstance(status, list) else [status]
    assert r.status_code in allowed, f"GET {spec['path']}: expected {status}, received {r.status_code}"
    out = {'status': r.status_code}
    if 'refused' in check:
        refused = resolve(check['refused'], c.state)
        rr, _ = c.request(refused.get('method', 'GET'), refused['path'], actor_of(refused.get('actor', 'alice')))
        denied = refused.get('status', [401, 403, 404])
        denied = denied if isinstance(denied, list) else [denied]
        assert rr.status_code in denied, f"{refused['path']} was not refused: {rr.status_code}"
        out['refused'] = rr.status_code
    if r.status_code >= 400:
        return out
    if check.get('items'):
        payload = lookup(payload, check['items'])
    if check.get('where') is not None:
        wanted = resolve(check['where'], c.state)
        assert isinstance(payload, list), 'expected a collection'
        matches = [x for x in payload if isinstance(x, dict) and all(lookup(x, k) == v for k, v in wanted.items())]
        assert len(matches) == 1, 'expected exactly one member matching ' + json.dumps(wanted)
        payload = matches[0]
        if check.get('save'):
            c.state[check['save']] = payload
    order = lambda x: json.dumps(x, sort_keys=True)
    if check.get('collection'):
        assert isinstance(payload, list), 'expected a collection'
        value = sorted((project(x, check.get('fields', [])) for x in payload), key=order)
    else:
        value = project(payload, check.get('fields', []))
        for field, least in (check.get('at_least') or {}).items():
            try:
                found = lookup(payload, field)
            except (KeyError, IndexError, ValueError) as exc:
                raise AssertionError('field missing in the product state: ' + field) from exc
            value[f'{field} >= {least}'] = isinstance(found, (int, float)) and found >= least
        for field, text in (check.get('contains') or {}).items():
            try:
                found = lookup(payload, field)
            except (KeyError, IndexError, ValueError) as exc:
                raise AssertionError('field missing in the product state: ' + field) from exc
            value[f'{field} contains {text!r}'] = isinstance(found, str) and text in found
    value = json.loads(norm_text(json.dumps(value)))
    expected = resolve(check.get('expected'), c.state)
    if expected is not None:
        if check.get('collection') and isinstance(expected, list):
            expected = sorted(expected, key=order)
        assert value == expected, 'public state differs from the requested values: ' + json.dumps(value)[:400]
    out['value'] = c.norm.clean(value)
    return out
