"""Backend observations through the runtime's channels, with behavior-only projections.

A check is a list of steps. A request step sends one HTTP request through the
runtime's api operation; placeholders in its path, headers and bodies are
filled from the episode (the local API key from help, the server ID of the
latest response, versions read just before the request, values captured from
earlier steps of the same check). A step with a view contributes one projection
of its response to the observation; the projections drop what is not behavior:
version numbers, generated keys and timestamps, the origin of absolute links,
the order of tags and collection memberships. Other step kinds read the outbox
(download), the clipboard, or look up the object a GUI goal produced.
"""
import base64
import json
import re
import time
import urllib.parse

from evaluation.broker import BrokerError
import formats

KEY_RE = re.compile(r'^[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}$')
DROP = ('version', 'dateAdded', 'dateModified', 'mtime')
PLACEHOLDER = re.compile(r'\{([a-z][a-z0-9_]*)([+-]\d+)?\}')


class Context:
    """Per-episode API state kept in ctx.state['api']."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.key = None
        self.sid = None
        self.values = {}

    def api_key(self):
        if self.key is None:
            self.key = self.ctx.broker.call({'op': 'help'}).get('api_key') or ''
        return self.key


def state(ctx):
    if 'api' not in ctx.state:
        ctx.state['api'] = Context(ctx)
    return ctx.state['api']


def call(ctx, request, timeout=None):
    """One api request; a runtime refusal or a timeout is a failed observation, never a verifier fault."""
    wait = request.get('timeout', 30)
    try:
        response = ctx.broker.call(dict(request, timeout=wait), timeout=wait + 30)
    except BrokerError as exc:
        raise AssertionError(f'the request could not be completed: {exc.error}: {exc.detail[:300]}') from None
    server = (response.get('headers') or {}).get('zotero-server-id')
    if server:
        state(ctx).sid = server
    return response


def get(ctx, path, timeout=30, retries=1):
    """A GET that is repeated once after a timeout (the product answers some early requests late)."""
    for attempt in range(retries + 1):
        try:
            return call(ctx, {'op': 'api', 'path': path, 'method': 'GET', 'timeout': timeout})
        except AssertionError as exc:
            if attempt == retries or 'Timeout' not in str(exc):
                raise


def server_id(ctx):
    api = state(ctx)
    if not api.sid:
        get(ctx, '/api/')
    return api.sid or ''


def library_version(ctx):
    response = get(ctx, '/api/users/0/items?limit=1&format=keys')
    value = (response.get('headers') or {}).get('last-modified-version')
    if value is None or not str(value).isdigit():
        raise AssertionError('the library version is not reported (Last-Modified-Version)')
    return int(value)


# ------------------------------------------------------------------------------------------ placeholders
def fill(ctx, value):
    """Placeholders: {key} API key, {sid} server ID, {version}[+-n] current library version, {name}[+-n] a value
    captured by an earlier step of the check."""
    if isinstance(value, str):
        def replace(match):
            name, offset = match.group(1), int(match.group(2) or 0)
            if name == 'key':
                return state(ctx).api_key()
            if name == 'sid':
                return server_id(ctx)
            if name == 'version':
                return str(library_version(ctx) + offset)
            if name in ('inbox', 'outbox'):
                return exchange(ctx, name)
            if name in state(ctx).values:
                captured = state(ctx).values[name]
                return str(int(captured) + offset) if offset else str(captured)
            return match.group(0)
        return PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [fill(ctx, v) for v in value]
    if isinstance(value, dict):
        return {fill(ctx, k): fill(ctx, v) for k, v in value.items()}
    return value


def exchange(ctx, area):
    """The runtime's inbox or outbox folder (from the path of a file listed there)."""
    try:
        listed = ctx.broker.call({'op': 'list_files', 'area': area})
    except BrokerError as exc:
        raise AssertionError(f'the {area} could not be listed: {exc.detail[:200]}') from None
    for entry in listed.get('files', []):
        if entry.get('path') and not entry.get('read_only'):
            return entry['path'].rsplit('/', 1)[0]
    raise AssertionError(f'the {area} lists no file')


AUTH = {'Zotero-API-Key': '{key}', 'Zotero-Server-ID': '{sid}'}


# Zotero applies the fields of a written object in their order, and some fields need others first (an attachment's
# file name needs its link mode, annotation properties need the annotation type). A frozen manifest keeps JSON object
# keys sorted, so every written object is sent in one fixed order: these fields first, then the others sorted.
FIRST_FIELDS = ('key', 'version', 'itemType', 'parentItem', 'linkMode', 'annotationType', 'name', 'parentCollection')


def ordered(value):
    if isinstance(value, list):
        return [ordered(v) for v in value]
    if isinstance(value, dict):
        first = [k for k in FIRST_FIELDS if k in value]
        return {k: ordered(value[k]) for k in first + sorted(k for k in value if k not in FIRST_FIELDS)}
    return value


def request(ctx, step):
    data = {'op': 'api', 'path': fill(ctx, step['path']), 'method': step.get('method', 'GET')}
    headers = dict(AUTH) if step.get('auth', step.get('method', 'GET') != 'GET') else {}
    headers.update(step.get('headers') or {})
    headers = {k: v for k, v in fill(ctx, headers).items() if v is not None}
    if headers:
        data['headers'] = headers
    for field in ('json', 'body', 'form', 'content_type', 'body_base64', 'timeout'):
        if field in step:
            data[field] = fill(ctx, step[field])
    if 'json' in data:
        data['json'] = ordered(data['json'])
    if 'json' in data and step.get('raw_json'):
        data['body'] = data.pop('json') if isinstance(data['json'], str) else json.dumps(data['json'])
        data.setdefault('content_type', 'application/json')
    if data['method'] == 'GET' and 'timeout' not in data:
        for attempt in range(2):
            try:
                return call(ctx, data)
            except AssertionError as exc:
                if attempt or 'Timeout' not in str(exc):
                    raise
    return call(ctx, data)


# ---------------------------------------------------------------------------------------------- projections
def known_keys(check):
    return {s for s in re.findall(r'[23456789ABCDEFGHIJKLMNPQRSTUVWXYZ]{8}', json.dumps(check))}


# A date and time as notes show the moment they were generated (for example 10/29/2026, 7:06:59 PM).
DATE_TIME = re.compile(r'\b\d{1,2}/\d{1,2}/\d{4}, \d{1,2}:\d{2}(?::\d{2})? [AP]M\b')


class Keys:
    """Keys the check named stay; generated keys become new-1, new-2... in order of first appearance."""

    def __init__(self, known):
        self.known = set(known)
        self.generated = {}

    def __call__(self, value):
        if not isinstance(value, str) or not KEY_RE.match(value) or value in self.known:
            return value
        if value not in self.generated:
            self.generated[value] = f'new-{len(self.generated) + 1}'
        return self.generated[value]

    def anonymous(self):
        """The same mapping with every generated key as plain 'new' (for projections compared as unordered sets)."""
        return lambda value: (value if not isinstance(value, str) or not KEY_RE.match(value) or value in self.known
                              else 'new')


def href(value):
    """A link without its host, and with the instance's random local user ID of web library URIs as {local}."""
    if not isinstance(value, str):
        return value
    return re.sub(r'/users/local/[^/]+/', '/users/local/{local}/', re.sub(r'^https?://[^/]+', '', value))


def links(value):
    if not isinstance(value, dict):
        return value
    return {rel: {k: href(v) if k == 'href' else v for k, v in link.items()} if isinstance(link, dict) else link
            for rel, link in value.items()}


def tag_list(tags):
    out = []
    for tag in tags or []:
        if isinstance(tag, dict):
            entry = {'tag': tag.get('tag')}
            if tag.get('type'):
                entry['type'] = tag['type']
            out.append(entry)
        else:
            out.append(tag)
    return sorted(out, key=lambda t: json.dumps(t, sort_keys=True, ensure_ascii=False))


def data(value, keys, keep=()):
    """An item, collection or search data object without bookkeeping (versions, generated timestamps)."""
    if not isinstance(value, dict):
        return value
    result = {}
    for name, field in sorted(value.items(), key=lambda pair: (pair[0] != 'key', pair[0])):
        if name in DROP and name not in keep:
            continue
        if name == 'tags':
            field = tag_list(field)
        elif name == 'collections' and isinstance(field, list):
            # an unordered set: generated keys in it cannot be told apart by order, so they all read 'new'
            field = sorted((keys.anonymous() if isinstance(keys, Keys) else keys)(k) for k in field)
        elif name == 'relations' and isinstance(field, dict):
            field = {k: sorted(formats.local(x) for x in (v if isinstance(v, list) else [v])) for k, v in
                     sorted(field.items())}
        elif name in ('key', 'parentItem', 'parentCollection'):
            field = keys(field)
        elif name == 'note' and isinstance(field, str):
            field = formats.note_html(field)
        elif name == 'path' and isinstance(field, str):
            field = re.sub(r'^.*/files/(inbox|outbox)/', r'<\1>/', field)
        elif name == 'conditions' and isinstance(field, list):
            field = sorted((dict(c) for c in field), key=lambda c: json.dumps(c, sort_keys=True))
        elif name in ('annotationText', 'annotationComment') and isinstance(field, str):
            field = formats.spaces(field)
        result[name] = field
    return result


def obj(value, keys, keep=()):
    """A full response object: data (as above), meta, normalized links and library."""
    if not isinstance(value, dict):
        return value
    result = {}
    for name, field in value.items():
        if name in DROP and name not in keep:
            continue
        if name == 'key':
            field = keys(field)
        elif name == 'data':
            field = data(field, keys, keep)
        elif name == 'links':
            field = links(field)
        elif name == 'library' and isinstance(field, dict):
            field = dict(field, links=links(field.get('links')))
        result[name] = field
    return result


def body_objects(response):
    body = response.get('body')
    if isinstance(body, dict) and ('data' in body or 'key' in body):
        return [body]
    if isinstance(body, list):
        return body
    raise AssertionError(f'the response body is not an object list (HTTP {response.get("status")})')


def write_result(body, keys):
    if not isinstance(body, dict):
        raise AssertionError('the write response is not a JSON object')
    result = {}
    for part in ('success', 'unchanged', 'failed'):
        entries = body.get(part)
        if not isinstance(entries, dict):
            raise AssertionError(f'the write response has no "{part}" object')
        if part == 'failed':
            result[part] = {i: {'key': keys(f.get('key')), 'code': f.get('code'), 'message': versionless(f.get('message'))}
                            for i, f in sorted(entries.items()) if isinstance(f, dict)}
        else:
            result[part] = {i: keys(k) for i, k in sorted(entries.items())}
    successful = body.get('successful')
    if isinstance(successful, dict):
        result['successful'] = {i: data(o.get('data'), keys) for i, o in sorted(successful.items())
                                if isinstance(o, dict)}
    return result


def link_header(value):
    """Link header as {rel: [path, sorted query pairs]} (the origin is the client's, the order of rels free)."""
    result = {}
    for part in (value or '').split(','):
        match = re.match(r'\s*<([^>]*)>\s*;\s*rel="([^"]+)"', part)
        if match:
            parsed = urllib.parse.urlsplit(match.group(1))
            result[match.group(2)] = [parsed.path, sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))]
    return dict(sorted(result.items()))


def versionless(text):
    """Messages about versions keep their wording; the version numbers themselves are bookkeeping."""
    if isinstance(text, str) and re.search(r'version', text, re.I):
        return re.sub(r'\b\d+\b', '#', text)
    return text


def text_body(response):
    body = response.get('body')
    if isinstance(body, (dict, list)):
        return json.dumps(body, ensure_ascii=False)
    return '' if body is None else str(body)


def view(name, response, keys):
    """One projection of a response; a name ending in ? stands for nothing when the request did not succeed."""
    if name.endswith('?'):
        status = response.get('status')
        if not (isinstance(status, int) and 200 <= status < 300):
            return None
        name = name[:-1]
    kind, _, arg = name.partition(':')
    status = response.get('status')
    if kind == 'unordered':
        value = view(arg, response, keys.anonymous() if isinstance(keys, Keys) else keys)
        if not isinstance(value, list):
            raise AssertionError('the projection is not a list')
        return sorted(value, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if kind == 'top':
        # The local API has no /searches/KEY/items/top route. Select the equivalent item projection locally.
        objects = [o for o in body_objects(response) if not (o.get('data') or {}).get('parentItem')]
        return view(arg, dict(response, body=objects), keys)
    if kind == 'where':
        condition, projection = arg.split(':', 1)
        field, wanted = condition.split('=', 1)
        objects = [o for o in body_objects(response) if (o.get('data') or {}).get(field) == wanted]
        return view(projection, dict(response, body=objects), keys)
    if kind == 'status':
        return status
    if kind == 'header':
        value = (response.get('headers') or {}).get(arg.lower())
        if arg.lower() == 'link':
            return link_header(value)
        if arg.lower() == 'content-type' and value:
            return value.split(';')[0].strip().lower()
        return value
    if kind == 'has-header':
        return (response.get('headers') or {}).get(arg.lower()) is not None
    if kind == 'body':
        return response.get('body')
    if kind == 'sorted-body':
        body = response.get('body')
        if not isinstance(body, list):
            raise AssertionError('the response body is not a list')
        return sorted(body, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    if kind == 'json':
        value = response.get('body')
        for part in arg.split('.'):
            if not isinstance(value, dict) or part not in value:
                raise AssertionError(f'the response body has no "{arg}"')
            value = value[part]
        return value
    if kind == 'fields':
        wanted = arg.split(',')
        objects = body_objects(response)
        values = [{f: data(o.get('data') or {}, keys).get(f) for f in wanted} for o in objects]
        return values if isinstance(response.get('body'), list) else values[0]
    if kind == 'absent':
        field, _, value = arg.partition('=')
        return not any((o.get('data') or {}).get(field) == value for o in body_objects(response))
    if kind == 'tag-names':
        body = response.get('body')
        if not isinstance(body, list):
            raise AssertionError('the response body is not a tag list')
        return sorted({entry.get('tag') for entry in body if isinstance(entry, dict)})
    if kind == 'collection-tree':
        objects = body_objects(response)
        names = {o.get('key'): (o.get('data') or {}).get('name') for o in objects}
        parents = {o.get('key'): (o.get('data') or {}).get('parentCollection') for o in objects}

        def path(key, seen=()):
            parent = parents.get(key)
            if parent and parent in names and parent not in seen:
                return path(parent, seen + (key,)) + ' / ' + str(names[key])
            return str(names[key])
        return sorted(path(key) for key in names)
    if kind == 'note-text':
        return [[DATE_TIME.sub('<date-time>', line) for line in formats.html_text(o.get('data', {}).get('note', ''))]
                for o in body_objects(response)]
    if kind == 'has-data':
        return all('data' in o for o in body_objects(response))
    if kind == 'order':
        return order(body_objects(response), arg, keys)
    if kind == 'text':
        return versionless(formats.spaces(text_body(response)))
    if kind == 'data':
        objects = body_objects(response)
        values = [data(o.get('data'), keys, tuple(arg.split(',')) if arg else ()) for o in objects]
        return values if isinstance(response.get('body'), list) else values[0]
    if kind == 'object':
        objects = body_objects(response)
        values = [obj(o, keys, tuple(arg.split(',')) if arg else ()) for o in objects]
        return values if isinstance(response.get('body'), list) else values[0]
    if kind == 'meta':
        objects = body_objects(response)
        values = [({k: (o.get('meta') or {}).get(k) for k in arg.split(',')} if arg else o.get('meta')) for o in objects]
        return values if isinstance(response.get('body'), list) else values[0]
    if kind == 'links':
        objects = body_objects(response)
        values = [links(o.get('links')) for o in objects]
        return values if isinstance(response.get('body'), list) else values[0]
    if kind == 'contains-key':
        return arg in [o.get('key') for o in body_objects(response)]
    if kind == 'has-version':
        body = response.get('body')
        return isinstance(body, dict) and isinstance(body.get(arg), int)
    if kind == 'write-codes':
        body = response.get('body')
        if not isinstance(body, dict) or not isinstance(body.get('failed'), dict):
            raise AssertionError('the write response has no failed object')
        return {k: v.get('code') for k, v in body['failed'].items()}
    if kind == 'tag-order':
        body = response.get('body')
        if not isinstance(body, list):
            raise AssertionError('the response is not a tag list')
        return [entry.get('tag') for entry in body]
    if kind == 'sha256':
        import hashlib
        return hashlib.sha256(response['body']).hexdigest()
    if kind in ('pdf-pages', 'pdf-annotations'):
        import pymupdf
        with pymupdf.open(stream=response['body'], filetype='pdf') as document:
            if kind == 'pdf-pages':
                return [formats.spaces(page.get_text()) for page in document]
            annotations = [{'page': page.number + 1, 'type': annotation.type[1],
                            'content': formats.spaces(annotation.info.get('content', ''))}
                           for page in document for annotation in page.annots() or []]
            return sorted(annotations, key=lambda a: (a['page'], a['type'], a['content']))
    if kind == 'keys':
        return [keys(o.get('key')) for o in body_objects(response)]
    if kind == 'keyset':
        return sorted(keys(o.get('key')) for o in body_objects(response))
    if kind == 'keylines':
        return sorted(keys(line.strip()) for line in text_body(response).splitlines() if line.strip())
    if kind == 'count':
        body = response.get('body')
        if not isinstance(body, list):
            raise AssertionError('the response body is not a list')
        return len(body)
    if kind == 'write':
        return write_result(response.get('body'), keys)
    if kind == 'tags':
        body = response.get('body')
        if not isinstance(body, list):
            raise AssertionError('the response body is not a tag list')
        result = []
        for entry in body:
            if not isinstance(entry, dict):
                raise AssertionError('a tag entry is not an object')
            meta = entry.get('meta') or {}
            result.append({'tag': entry.get('tag'), 'type': meta.get('type'), 'numItems': meta.get('numItems'),
                           'links': links(entry.get('links'))})
        return sorted(result, key=lambda t: (str(t['tag']), str(t['type'])))
    if kind == 'versions':
        body = response.get('body')
        if not isinstance(body, dict):
            raise AssertionError('the response body is not a version object')
        return sorted(keys(k) for k in body)
    if kind == 'format':
        return formats.read(arg, text_body(response))
    if kind == 'include':
        field, _, reader = arg.partition('/')
        objects = body_objects(response)
        values = []
        for o in objects:
            if field not in o:
                raise AssertionError(f'the object has no "{field}" property')
            values.append(formats.read(reader, o[field]) if reader else o[field])
        return values if isinstance(response.get('body'), list) else values[0]
    raise AssertionError('unknown view ' + name)


def sort_value(entry, field):
    values, meta = entry.get('data') or {}, entry.get('meta') or {}
    if field == 'creator':
        return meta.get('creatorSummary', '')
    if field == 'date':
        return meta.get('parsedDate', '')
    if field == 'title':
        return next((values[f] for f in ('title', 'caseName', 'nameOfAct', 'subject') if values.get(f)), '')
    return values.get(field, '')


def order(objects, field, keys):
    """Keys in list order, grouped where consecutive objects share the sort value (equal values in any order)."""
    groups, last = [], object()
    for entry in objects:
        value = sort_value(entry, field)
        if groups and value == last:
            groups[-1].append(keys(entry.get('key')))
        else:
            groups.append([keys(entry.get('key'))])
        last = value
    return [sorted(group) for group in groups]


def relation(left, op, right):
    def number(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    a, b = number(left), number(right)
    try:
        return {'>': a > b, '<': a < b, '==': a == b, '!=': a != b, '>=': a >= b}[op]
    except TypeError:
        return False


# ---------------------------------------------------------------------------------------------------- run
def capture(ctx, response, spec):
    """{name: path} captures: header:<name>, success.<i>, status."""
    for name, source in spec.items():
        kind, _, arg = source.partition(':')
        if kind == 'header':
            value = (response.get('headers') or {}).get(arg.lower())
        elif kind == 'success':
            value = (response.get('body') or {}).get('success', {}).get(arg)
        elif kind == 'body':
            value = response.get('body')
            for part in arg.split('.') if arg else []:
                value = value[int(part)] if isinstance(value, list) else (value or {}).get(part)
        else:
            raise AssertionError('unknown capture ' + source)
        if value is None:
            raise AssertionError(f'nothing to capture for {name} ({source})')
        state(ctx).values[name] = value


def run(ctx, check):
    """The observation of one backend check (a list, one entry per viewed step)."""
    keys = Keys(known_keys(check) | ctx.state.get('known_keys', set()))
    state(ctx).values = {}
    observation = []
    for step in check['steps']:
        kind = step.get('kind', 'request')
        if kind == 'request':
            response = request(ctx, step)
        elif kind == 'sleep':
            time.sleep(step['seconds'])
            continue
        elif kind == 'version':
            state(ctx).values[step['as']] = library_version(ctx)
            continue
        elif kind == 'download':
            response = download(ctx, step)
        elif kind == 'clipboard':
            response = clipboard(ctx, step)
        elif kind == 'find':
            response = find(ctx, step)
        elif kind == 'compare':
            values = state(ctx).values
            missing = [n for r in step['relations'] for n in (r[0], r[2]) if n not in values]
            if missing:
                raise AssertionError('nothing captured for ' + ', '.join(missing))
            observation.append([relation(values[a], op, values[b]) for a, op, b in step['relations']])
            continue
        else:
            raise AssertionError('unknown step kind ' + kind)
        if step.get('capture'):
            capture(ctx, response, step['capture'])
        if 'expect' in step and response.get('status') not in step['expect']:
            raise AssertionError(f'{step["method"] if "method" in step else kind} {step.get("path", "")} answered '
                                 f'HTTP {response.get("status")}: {str(response.get("body"))[:300]}')
        for name in ([step['view']] if isinstance(step.get('view'), str) else step.get('view') or []):
            observation.append(view(name, response, keys))
    return observation


# --------------------------------------------------------------------------------- files, clipboard, lookups
def download(ctx, step):
    """A file the product wrote into the outbox, as a response-like {status, body} (text documents decoded)."""
    try:
        listed = ctx.broker.call({'op': 'list_files', 'area': step.get('area', 'outbox')})
    except BrokerError as exc:
        raise AssertionError(f'the outbox could not be listed: {exc.detail[:200]}') from None
    names = [f['name'] for f in listed.get('files', []) if not f.get('read_only')]
    name = fill(ctx, step['filename'])
    if name not in names:
        raise AssertionError(f'{name} is not in the {step.get("area", "outbox")} (found: {names[:12]})')
    try:
        answer = ctx.broker.call({'op': 'download', 'filename': name, 'area': step.get('area', 'outbox')})
    except BrokerError as exc:
        raise AssertionError(f'{name} could not be downloaded: {exc.detail[:200]}') from None
    content = base64.b64decode(answer['body_base64'])
    if step.get('binary'):
        return {'status': 200, 'body': content, 'headers': {}}
    return {'status': 200, 'body': content.decode('utf-8-sig'), 'headers': {}}


def clipboard(ctx, step):
    op = {'text': 'clipboard_text', 'html': 'clipboard_html'}[step.get('target', 'text')]
    try:
        answer = ctx.broker.call({'op': op})
    except BrokerError as exc:
        raise AssertionError(f'the clipboard holds no {step.get("target", "text")}: {exc.detail[:200]}') from None
    return {'status': 200, 'body': answer.get('text', answer.get('html', '')), 'headers': {}}


def find(ctx, step):
    """The object a GUI goal produced: items (or collections, searches) whose field equals a value (field
    note-text: a note whose visible text is the value); the first match's key is captured for later steps."""
    path = step.get('path', '/api/users/0/items?includeTrashed=1')
    objects = all_objects(ctx, fill(ctx, path))
    field, value = step['field'], step['value']
    if field == 'note-text':
        matches = [o for o in objects if ' '.join(formats.html_text((o.get('data') or {}).get('note') or '')) == value]
    else:
        matches = [o for o in objects if (o.get('data') or {}).get(field) == value]
    if step.get('itemType'):
        matches = [o for o in matches if o['data'].get('itemType') == step['itemType']]
    if not matches:
        raise AssertionError(f'no object with {field} {value!r}')
    state(ctx).values[step.get('as', 'found')] = matches[0]['data']['key']
    return {'status': 200, 'body': matches if step.get('all') else matches[0], 'headers': {}}


def all_objects(ctx, path):
    """Read every page explicitly; a candidate's default page size is not part of a GUI goal."""
    url = urllib.parse.urlsplit(path)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(url.query) if k not in ('limit', 'start')]
    result, seen, start = [], set(), 0
    for _ in range(1000):
        page_path = url.path + '?' + urllib.parse.urlencode(query + [('limit', 100), ('start', start)])
        response = get(ctx, page_path)
        if not 200 <= response.get('status', 0) < 300:
            raise AssertionError('object listing failed')
        page = body_objects(response)
        if not page:
            return result
        keys = [o.get('key', (o.get('data') or {}).get('key')) for o in page]
        if any(key in seen for key in keys):
            raise AssertionError('object pagination repeats a page')
        seen.update(keys)
        result.extend(page)
        start += len(page)
    raise AssertionError('object listing did not terminate')


def project(value, check):
    """One aspect of a shared observation: check['select'] walks list indices, dict keys,
    {'where': {field: value}} matches (the first list element whose fields equal the given values),
    {'map': field} (that field of every list element) and 'sorted' (the list in a canonical order)."""
    for part in check.get('select', []):
        if part == 'sorted':
            if not isinstance(value, list):
                raise AssertionError('the observation is not a list')
            value = sorted(value, key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
            continue
        if isinstance(part, dict) and 'map' in part:
            if not isinstance(value, list):
                raise AssertionError('the observation is not a list')
            value = [v.get(part['map']) if isinstance(v, dict) else None for v in value]
            continue
        if isinstance(part, dict):
            wanted = part['where']
            if not isinstance(value, list):
                raise AssertionError('the observation is not a list')
            match = [v for v in value if isinstance(v, dict) and all(v.get(k) == w for k, w in wanted.items())]
            if not match:
                raise AssertionError('no entry with ' + json.dumps(wanted, ensure_ascii=False))
            value = match[0]
        elif isinstance(value, list):
            if not isinstance(part, int) or not -len(value) <= part < len(value):
                raise AssertionError(f'the observation has no entry {part}')
            value = value[part]
        elif isinstance(value, dict):
            if part not in value:
                raise AssertionError(f'the observation has no "{part}"')
            value = value[part]
        else:
            raise AssertionError(f'the observation has no "{part}"')
    return value


# --------------------------------------------------------------------------------------------- comparison
def compare(actual, expected):
    # the frozen truth went through JSON (tuples are lists there); the observation is compared in that form
    actual = json.loads(json.dumps(actual, ensure_ascii=False))
    if actual != expected:
        raise AssertionError('observation differs from the reference: ' + json.dumps(actual, ensure_ascii=False)[:1500])
