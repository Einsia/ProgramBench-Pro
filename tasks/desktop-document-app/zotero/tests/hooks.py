"""Zotero specifics for the kit driver: episode inputs, reference recipes and program checks.

Everything reaches the candidate through the black-box runtime: input files are
uploaded into its inbox, fixture libraries are written through its local API
(op api, with the key from help), and checks read the API, the outbox and the
clipboard (checks.py). GUI goals are performed by the evaluator, or during
record by the reference recipes (reference/recipes.py).
"""
import base64
import json
import time

from evaluation.broker import BrokerError
from evaluation.driver import Hooks as Base
import checks
import library
from reference import recipes

BATCH = 50


def wait_api(ctx, seconds=90):
    """The local server answers GET /api/ (any status below 500)."""
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            response = ctx.broker.call({'op': 'api', 'path': '/api/', 'timeout': 5}, timeout=40)
            if response['status'] < 500:
                return response
            last = f'HTTP {response["status"]}'
        except BrokerError as exc:
            last = exc.detail[:200]
        time.sleep(0.5)
    raise AssertionError('the local API did not answer: ' + str(last))


def warm(ctx, seconds=90):
    """An export request answers in time (the first requests after a start may be answered late)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            ctx.broker.call({'op': 'api', 'path': '/api/users/0/items?format=bibtex&limit=1', 'timeout': 5},
                            timeout=40)
            return
        except BrokerError:
            time.sleep(0.5)
    raise AssertionError('export requests were not answered')


def post(ctx, path, objects):
    """Seed independently: an unsupported object must not block the rest of a fixture library."""
    def write(batch):
        response = checks.call(ctx, {'op': 'api', 'path': path, 'method': 'POST', 'json': checks.ordered(batch),
                                     'headers': {'Zotero-API-Key': checks.state(ctx).api_key(),
                                                 'Zotero-Server-ID': checks.server_id(ctx)}, 'timeout': 60})
        return response

    def warn(message):
        if ctx.record:
            raise AssertionError(message)
        warnings = ctx.state.setdefault('fixture_warnings', [])
        warnings.append(message)
        (ctx.out / 'fixture-warnings.json').write_text(json.dumps(warnings, ensure_ascii=False))

    for start in range(0, len(objects), BATCH):
        batch = objects[start:start + BATCH]
        try:
            response = write(batch)
        except AssertionError as exc:
            warn(str(exc))
            continue
        if 200 <= response['status'] < 300:
            body = response.get('body')
            if isinstance(body, dict) and body.get('failed'):
                warn(f'setup {path}: unsupported objects {body["failed"]}')
            continue
        # A candidate may reject a whole batch for one unsupported object. Retry one object at a time.
        for obj in batch:
            try:
                answer = write([obj])
                body = answer.get('body')
                if not 200 <= answer['status'] < 300 or isinstance(body, dict) and body.get('failed'):
                    warn(f'setup {path} object {obj.get("key")}: HTTP {answer["status"]} {str(body)[:300]}')
            except AssertionError as exc:
                warn(str(exc))


def seed(ctx, content):
    """Write a fixture library: collections (parents first), items, child items, searches."""
    known = ctx.state.setdefault('known_keys', set())
    collections = content.get('collections', [])
    pending, done = list(collections), set()
    while pending:
        ready = [c for c in pending if not c.get('parentCollection') or c['parentCollection'] in done]
        if not ready:
            raise AssertionError('collection parents form a cycle')
        post(ctx, '/api/users/0/collections', ready)
        done.update(c['key'] for c in ready)
        pending = [c for c in pending if c['key'] not in done]
    for part in ('items', 'children'):
        if content.get(part):
            post(ctx, '/api/users/0/items', content[part])
    if content.get('searches'):
        post(ctx, '/api/users/0/searches', content['searches'])
    for part in ('collections', 'items', 'children', 'searches'):
        known.update(o['key'] for o in content.get(part, ()))


def attach(ctx, folder, item_key, name):
    """Give a stored-file attachment its file through the API's upload (authorize, upload, register)."""
    import hashlib
    content = library.write(folder, name).read_bytes()
    headers = {'Zotero-API-Key': checks.state(ctx).api_key(), 'Zotero-Server-ID': checks.server_id(ctx),
               'If-None-Match': '*'}
    form = {'md5': hashlib.md5(content).hexdigest(), 'filename': name, 'filesize': str(len(content)),
            'mtime': '1704067200000'}
    answer = checks.call(ctx, {'op': 'api', 'path': f'/api/users/0/items/{item_key}/file', 'method': 'POST',
                               'form': form, 'headers': headers})
    body = answer.get('body')
    if not 200 <= answer['status'] < 300 or not isinstance(body, dict) or 'uploadKey' not in body:
        raise AssertionError(f'upload authorization for {name} failed: HTTP {answer["status"]} {str(body)[:200]}')
    sent = checks.call(ctx, {'op': 'api', 'path': f'/api/local/uploads/{body["uploadKey"]}', 'method': 'POST',
                             'body_base64': base64.b64encode(content).decode(), 'content_type': 'application/pdf'})
    if not 200 <= sent['status'] < 300:
        raise AssertionError(f'upload of {name} failed: HTTP {sent["status"]}')
    done = checks.call(ctx, {'op': 'api', 'path': f'/api/users/0/items/{item_key}/file', 'method': 'POST',
                             'form': {'upload': body['uploadKey']}, 'headers': headers})
    if not 200 <= done['status'] < 300:
        raise AssertionError(f'upload registration of {name} failed: HTTP {done["status"]}')


LIBRARIES = {
    'query': library.query_library,
    'types': lambda: {'items': list(library.TYPE_ITEMS.values())},
}


class Hooks(Base):
    def start(self, ctx):
        ctx.state['fixtures'] = ctx.out / 'fixtures'
        ctx.state['observed'] = {}

    def setup(self, ctx, item):
        op = item['op']
        if op == 'api-ready':
            wait_api(ctx)
            if item.get('warm'):
                warm(ctx)
        elif op == 'library':
            wait_api(ctx)
            content = {}
            for name in item['libraries']:
                for part, objects in LIBRARIES[name]().items():
                    content.setdefault(part, []).extend(objects)
            seed(ctx, content)
        elif op == 'objects':
            wait_api(ctx)
            seed(ctx, item['content'])
            for entry in item.get('files', []):
                attach(ctx, ctx.state['fixtures'], entry['key'], entry['name'])
                if entry.get('fulltext'):
                    answer = checks.request(ctx, {'method': 'PUT',
                        'path': f'/api/users/0/items/{entry["key"]}/fulltext',
                        'json': {'content': entry['fulltext'], 'indexedPages': 3, 'totalPages': 3}})
                    if not 200 <= answer['status'] < 300:
                        raise AssertionError('the fixture full text could not be prepared')
        elif op == 'upload':
            folder = ctx.state['fixtures']
            for name in item['files']:
                data = library.write(folder, name).read_bytes()
                ctx.broker.call({'op': 'upload', 'filename': name, 'base64': base64.b64encode(data).decode(),
                                 'area': item.get('area', 'inbox')})
        else:
            raise AssertionError('unknown setup operation ' + op)

    def prepare(self, ctx, checkpoint):
        if checkpoint.get('lifecycle') == 'restart':
            checks.state(ctx).sid = None
            wait_api(ctx)

    def restarted(self, ctx):
        checks.state(ctx).sid = None

    def begin(self, ctx, checkpoint):
        if ctx.record:
            recipes.begin(ctx, checkpoint)

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx, checkpoint)

    def check(self, ctx, checkpoint, assertion):
        """One backend point; checks that share an artifact (one download, one response) observe it once."""
        check = assertion['check']
        share = check.get('share')
        if share:
            cache = ctx.state['observed']
            key = (checkpoint['id'], share)
            if key not in cache:
                try:
                    cache[key] = (checks.run(ctx, check['shared']), None)
                except Exception as exc:
                    cache[key] = (None, exc)
            value, error = cache[key]
            if error is not None:
                raise error
            return checks.project(value, check)
        return checks.run(ctx, check)

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        checks.compare(actual, expected)
