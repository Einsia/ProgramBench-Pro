"""Program-check vocabulary and public access to one Miniflux candidate through the black-box runtime.

One operation with all its assertions is one CASE. Every request reaches the candidate through the
runtime's api operation (the channel the model also has on the reference); what the product sends to
other web hosts is read from the runtime's local web (web_put publishes the resources the product
fetches, web_requests lists what it sent). Nothing here reads candidate files, databases or processes.
"""
from __future__ import annotations

import base64
import dataclasses
import datetime
import html.parser
import json
import re
import time
import urllib.parse

from evaluation.broker import BrokerError

CREDS = {'alice': 'Alice-Local-2026!', 'bob': 'Bob-Local-2026!', 'carol': 'Carol-Local-2026!'}
# The product origin as the runtime configures it (PORT 3000 on loopback, for the reference and every candidate).
ORIGIN = 'http://127.0.0.1:3000'
ORIGIN_FORMS = re.compile(r'https?://(?:127\.0\.0\.1|localhost|\[::1\]|0\.0\.0\.0):3000(?![0-9])')
# A media proxy address keeps the proxied URL (base64) but its signature is a secret of the installation.
PROXY = re.compile(r'(/proxy/)([^/\s"\'<>]+)/([A-Za-z0-9_\-=]+)')
API_HEADERS = {'accept', 'accept-language', 'authorization', 'if-none-match', 'if-modified-since', 'range',
               'x-auth-token', 'origin', 'access-control-request-method', 'access-control-request-headers'}


class MissingDependency(AssertionError):
    pass


class State(dict):
    def __missing__(self, key):
        raise MissingDependency(f'missing successful prerequisite {key}')


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object
    needs: list = dataclasses.field(default_factory=list)
    requires: list = dataclasses.field(default_factory=list)
    gui: dict = None


class Ref:
    def __init__(self, key, *path):
        self.key, self.path = key, path

    def get(self, ctx):
        if self.key not in ctx.state:
            raise MissingDependency(f'missing result {self.key}')
        value = ctx.state[self.key]
        try:
            for part in self.path:
                value = value[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise MissingDependency(f'prerequisite {self.key} lacks {self.path}') from exc
        return value


def resolve(value, ctx):
    if isinstance(value, Ref):
        return value.get(ctx)
    if callable(value):
        return value(ctx)
    if isinstance(value, dict):
        return {k: resolve(v, ctx) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [resolve(v, ctx) for v in value]
    return value


def pathref(template, **values):
    return lambda c: template.format(**{k: urllib.parse.quote(str(resolve(v, c)), safe='') for k, v in values.items()})


# -- observation normalization ----------------------------------------------------------------------------
# The product's own error wording is compared; details that its libraries append (decoder positions, network
# errors with resolver addresses, database messages) are implementation and environment details.
ERROR_DETAILS = [
    (re.compile(r'^(\w+): unable to parse (feed|document): .*$', re.S), r'\1: unable to parse \2: [detail]'),
    (re.compile(r'^(opml: invalid miniflux attribute "[^"]*"): .*$', re.S), r'\1: [detail]'),
    (re.compile(r'^fetcher: (?:GET|HEAD|POST|Get|Head|Post) "[^"]*": .*$', re.S), 'fetcher: [connection error]'),
    (re.compile(r'^store: .*$', re.S), 'store: [internal error]'),
]


def error_text(value):
    for pattern, replacement in ERROR_DETAILS:
        value = pattern.sub(replacement, value)
    return norm_text(value)


def norm_text(value):
    """This run's origin and media proxy signatures are installation details; the rest of a text is behavior."""
    value = ORIGIN_FORMS.sub('[origin]', value)
    return PROXY.sub(lambda m: m[1] + '[signature]/' + m[3], value)


VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
SPACE = re.compile(r'[ \t\n\r\f]+')


class Canon(html.parser.HTMLParser):
    """HTML as a token sequence: tags with sorted attributes, entity-decoded text with collapsed ASCII
    whitespace; serialization details (quotes, self-closing slashes, entity spelling, whitespace between
    tags) are not behavior."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []

    def attrs(self, attrs):
        parts = []
        for name, value in sorted(attrs, key=lambda x: x[0]):
            value = '' if value is None else norm_text(SPACE.sub(' ', value).strip())
            parts.append(f' {name}="{value}"')
        return ''.join(parts)

    def handle_starttag(self, tag, attrs):
        self.out.append(f'<{tag}{self.attrs(attrs)}>')

    def handle_startendtag(self, tag, attrs):
        self.out.append(f'<{tag}{self.attrs(attrs)}>')
        if tag not in VOID:
            self.out.append(f'</{tag}>')

    def handle_endtag(self, tag):
        if tag not in VOID:
            self.out.append(f'</{tag}>')

    def handle_data(self, data):
        text = SPACE.sub(' ', data).strip()
        if text:
            self.out.append(norm_text(text))

    def handle_comment(self, data):
        self.out.append('<!--' + data + '-->')

    def handle_decl(self, decl):
        self.out.append('<!' + decl + '>')


def canonical_html(value):
    if not isinstance(value, str):
        return value
    parser = Canon()
    parser.feed(value)
    parser.close()
    return ''.join(parser.out)


def utc_text(stamp):
    utc = stamp.astimezone(datetime.timezone.utc)
    return utc.strftime('%Y-%m-%dT%H:%M:%S') + (f'.{utc.microsecond:06d}'.rstrip('0') if utc.microsecond else '') + 'Z'


def is_time(value):
    try:
        stamp = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None
    return stamp if stamp.tzinfo is not None else None


class Normalize:
    """Generated identities become typed tokens (@kind:N), consistent for the whole episode; wall-clock times
    become markers. Feed-supplied data (titles, URLs, publication dates, content) stays exact."""

    CLOCK = {'created_at', 'changed_at', 'checked_at', 'next_check_at', 'last_login_at', 'last_used_at'}
    ID_KEYS = {'feed_id': 'feed', 'user_id': 'user', 'category_id': 'category', 'icon_id': 'icon',
               'entry_id': 'entry', 'enclosure_id': 'enclosure'}
    OPAQUE = {'hash': 'hash', 'external_icon_id': 'icon-hash', 'share_code': 'share', 'token': 'secret'}
    HTML = {'content'}

    def __init__(self):
        self.ids = {}
        self.counts = {}

    def identity(self, kind, value):
        if value in (None, '', 0):
            return value
        key = (kind, str(value))
        if key not in self.ids:
            self.counts[kind] = self.counts.get(kind, 0) + 1
            self.ids[key] = f'@{kind}:{self.counts[kind]}'
        return self.ids[key]

    @staticmethod
    def kind(obj, hint):
        keys = obj.keys()
        if 'hash' in keys and 'feed_id' in keys:
            return 'entry'
        if 'feed_url' in keys:
            return 'feed'
        if 'username' in keys and ('theme' in keys or 'is_admin' in keys):
            return 'user'
        if 'entry_id' in keys and 'mime_type' in keys:
            return 'enclosure'
        if {'mime_type', 'data'} <= keys:
            return 'icon'
        if 'token' in keys and 'description' in keys:
            return 'apikey'
        if {'feed_id', 'icon_id'} <= keys and 'title' not in keys:
            return 'feed-icon'
        if 'title' in keys and 'user_id' in keys:
            return 'category'
        return hint

    def time(self, value):
        if value is None:
            return None
        assert isinstance(value, str) and is_time(value), 'timestamp must be an RFC 3339 string or null'
        return '[unset]' if value.startswith('0001-') else '[time]'

    def published(self, value):
        """Publication dates come from the feed; an entry without one is dated when it is stored. A date compares
        as an instant (written in UTC), not as the text of one time zone offset."""
        stamp = is_time(value) if isinstance(value, str) else None
        if stamp is None:
            return value
        if abs((stamp - datetime.datetime.now(datetime.timezone.utc)).total_seconds()) < 172800:
            return '[now]'
        return utc_text(stamp)

    def clean(self, value, hint='object', key=''):
        if isinstance(value, dict):
            kind = self.kind(value, hint)
            out = {}
            for k, v in value.items():
                if k == 'id' and isinstance(v, int) and not isinstance(v, bool):
                    out[k] = self.identity(kind, v)
                elif k in self.ID_KEYS and isinstance(v, int) and not isinstance(v, bool):
                    out[k] = self.identity(self.ID_KEYS[k], v)
                elif k in self.OPAQUE and isinstance(v, str) and (k != 'token' or kind == 'apikey'):
                    out[k] = self.identity(self.OPAQUE[k], v)
                elif k == 'entry_ids' and isinstance(v, list):
                    out[k] = [self.identity('entry', x) for x in v]
                elif k in self.CLOCK:
                    out[k] = self.time(v)
                elif k == 'published_at':
                    out[k] = self.published(v)
                elif k in self.HTML and isinstance(v, str):
                    out[k] = canonical_html(v)
                elif k == 'parsing_error_message' and isinstance(v, str):
                    out[k] = error_text(v)
                else:
                    out[k] = self.clean(v, kind, k)
            return out
        if isinstance(value, list):
            return [self.clean(x, hint, key) for x in value]
        if isinstance(value, str):
            return norm_text(value)
        return value


class AliasGraph:
    """Compare opaque identities by a persistent typed bijection, not counters.

    Counters label observations, not product behavior. Missing an unrelated earlier entity must not change a
    later correct entity's score. Bindings are transactional per case: an otherwise failed response cannot poison
    future unrelated comparisons. Every successful relationship stays constrained.

    Response objects may carry fields the reference does not have; every reference field must be present and
    equal. Objects marked {"@unordered": [...]} compare as multisets; {"@exact": {...}} objects need the same keys.
    """

    TOKEN = re.compile(r'@[A-Za-z][A-Za-z0-9_.%+-]*:[0-9]+')
    FIELD = re.compile(r'^[a-z_][a-z0-9_]*$')

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward = dict(self.forward)
        reverse = dict(self.reverse)

        def walk(a, e, path):
            if type(a) in (int, float) and type(e) in (int, float):
                assert a == e, path + ': different numeric value'
                return
            assert type(a) is type(e), path + ': different value type'
            if isinstance(e, dict):
                if e.keys() == {'@unordered'}:
                    assert a.keys() == {'@unordered'}, path + ': different fields'
                    av, ev = a['@unordered'], e['@unordered']
                    assert isinstance(av, list) and isinstance(ev, list) and len(av) == len(ev), (
                        path + ': different collection length')

                    def bindings(x):
                        return sum(m[0] in forward for m in self.TOKEN.finditer(json.dumps(x)))

                    todo = sorted(ev, key=bindings, reverse=True)

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            f, r = dict(forward), dict(reverse)
                            try:
                                walk(av[pos], todo[index], path + '{member}')
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(f)
                            reverse.clear()
                            reverse.update(r)
                        return False

                    assert match(0, list(range(len(av)))), path + ': unordered membership or identity relationships differ'
                    return
                if e.keys() == {'@exact'}:
                    assert a.keys() == {'@exact'} and isinstance(a['@exact'], dict), path + ': different fields'
                    a, e = a['@exact'], e['@exact']
                    assert a.keys() == e.keys(), path + ': different fields'
                elif not e or not all(self.FIELD.match(k) for k in e):
                    assert a.keys() == e.keys(), path + ': different fields'
                else:
                    missing = sorted(set(e) - set(a))
                    assert not missing, path + ': missing fields ' + ', '.join(missing[:5])
                for k in e:
                    walk(a[k], e[k], path + '.' + k)
            elif isinstance(e, list):
                assert len(a) == len(e), path + ': different collection length'
                for i, (x, y) in enumerate(zip(a, e)):
                    walk(x, y, path + '[' + str(i) + ']')
            elif isinstance(e, str):
                at = list(self.TOKEN.finditer(a))
                et = list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(et), path + ': different text'
                for am, em in zip(at, et):
                    av, ev = am[0], em[0]
                    assert av.rsplit(':', 1)[0] == ev.rsplit(':', 1)[0], path + ': different identity namespace'
                    assert forward.get(ev, av) == av and reverse.get(av, ev) == ev, (
                        path + ': inconsistent identity relationship')
                    forward[ev] = av
                    reverse[av] = ev
            else:
                assert a == e, path + ': different value'

        walk(actual, expected, '$')
        self.forward, self.reverse = forward, reverse


def unordered(values):
    return {'@unordered': list(values)}


def exact(value):
    return {'@exact': value}


# -- access through the runtime -----------------------------------------------------------------------------
class Headers(dict):
    """Response headers with case-insensitive lookup."""

    def __init__(self, values=()):
        super().__init__({str(k).lower(): v for k, v in dict(values or {}).items()})

    def get(self, key, default=None):
        return super().get(str(key).lower(), default)


class Response:
    def __init__(self, status, headers, content):
        self.status_code, self.headers, self.content = status, Headers(headers), content

    @property
    def text(self):
        return self.content.decode('utf-8', errors='replace')

    def json(self):
        return json.loads(self.content.decode('utf-8'))


def query(params):
    if not params:
        return ''
    pairs = []
    for key, value in params.items():
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            pairs.append((key, str(item).lower() if isinstance(item, bool) else str(item)))
    return '?' + urllib.parse.urlencode(pairs)


class Context:
    """Public access to one candidate instance (through the runtime) plus the observation normalizers."""

    def __init__(self, broker, out):
        self.broker = broker
        self.out = out
        self.state = State()
        self.norm = Normalize()
        self.aliases = AliasGraph()
        self.creds = dict(CREDS)
        self.current_case = None

    # -- product HTTP ---------------------------------------------------------------------------------------
    def call(self, request):
        try:
            return self.broker.call(request)
        except BrokerError as exc:
            # The runtime could not complete the product request (connection refused, timeout, malformed reply).
            raise AssertionError('candidate request failed: ' + exc.detail[:300]) from None

    def auth(self, actor, rpc, headers):
        if actor is None:
            return
        if isinstance(actor, (list, tuple)):
            rpc['auth'] = [str(actor[0]), str(actor[1])]
        elif actor == 'invalid':
            rpc['auth'] = ['alice', 'Wrong-Password-2026!']
        elif actor.startswith('key:'):
            headers['x-auth-token'] = str(self.state[actor[4:]]['token'])
        elif actor.startswith('raw-key:'):
            headers['x-auth-token'] = actor[8:]
        elif actor in self.creds:
            rpc['auth'] = [actor, self.creds[actor]]
        else:
            raise MissingDependency('unknown account ' + actor)

    def request(self, method, path, actor='alice', body=None, params=None, headers=None, form=None, raw=None,
                content_type=None):
        path = path if path.startswith('/') else '/v1/' + path
        rpc = {'op': 'api', 'method': method.upper(), 'path': path + query(params), 'binary': True}
        sent = {}
        self.auth(actor, rpc, sent)
        for key, value in (headers or {}).items():
            assert key.lower() in API_HEADERS, 'header not available through the black-box api: ' + key
            sent[key.lower()] = value
        if sent:
            rpc['headers'] = sent
        if form is not None:
            rpc['form'] = form
        elif raw is not None:
            rpc['body_base64'] = base64.b64encode(raw if isinstance(raw, bytes) else raw.encode()).decode()
        elif body is not None:
            rpc['body_base64'] = base64.b64encode(json.dumps(body).encode()).decode()
        if content_type:
            rpc['content_type'] = content_type
        answer = self.call(rpc)
        assert not answer.get('truncated'), 'the product response exceeds the black-box response limit'
        r = Response(answer['status'], answer.get('headers'), base64.b64decode(answer.get('body_base64') or ''))
        try:
            payload = r.json()
        except ValueError:
            payload = r.text
        return r, payload

    def restart_server(self):
        """Restart the product process with the same data directory (runtime op restart)."""
        status = self.call({'op': 'restart'})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def running(self):
        return bool(self.call({'op': 'status'}).get('running'))

    # -- the local web -------------------------------------------------------------------------------------
    def web_put(self, url, body=b'', content_type=None, status=200, headers=None, auth=None):
        request = {'op': 'web_put', 'url': url, 'status': status,
                   'body_base64': base64.b64encode(body if isinstance(body, bytes) else body.encode()).decode()}
        if content_type:
            request['content_type'] = content_type
        if headers:
            request['headers'] = headers
        if auth:
            request['auth'] = list(auth)
        return self.call(request)

    def web_delete(self, url):
        return self.call({'op': 'web_delete', 'url': url})

    def web_mark(self):
        return self.call({'op': 'web_requests', 'since': 10 ** 12})['last']

    def web_requests(self, host=None, since=0):
        request = {'op': 'web_requests', 'since': since}
        if host:
            request['host'] = host
        return self.call(request)['requests']

    # -- observations --------------------------------------------------------------------------------------
    def error(self, payload):
        if isinstance(payload, dict) and isinstance(payload.get('error_message'), str):
            return error_text(payload['error_message'])
        return error_text(str(payload).strip())

    def observe(self, r, payload, hint='object', view=None, error_text=True):
        status = r.status_code
        if 300 <= status < 400:
            return {'status': status, 'location': norm_text(r.headers.get('location', ''))}
        if status >= 400:
            # Messages produced by a parser of the request itself (malformed JSON) are not compared.
            return {'status': status, 'error': self.error(payload)} if error_text else {'status': status}
        if view is not None:
            payload = view(payload)
        return {'status': status, 'body': self.norm.clean(payload, hint)}

    def settle(self, read, quiet=3.0, limit=30.0, interval=0.25):
        """Poll a read of asynchronous product work until its value stays unchanged for `quiet` seconds."""
        deadline = time.monotonic() + limit
        value = read()
        since = time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(interval)
            current = read()
            if current != value:
                value, since = current, time.monotonic()
            elif time.monotonic() - since >= quiet:
                break
        return value

    def wait(self, read, predicate, seconds=20, interval=0.25, what='state'):
        """Poll a read until the predicate holds (asynchronous product work); the last value otherwise."""
        deadline = time.monotonic() + seconds
        while True:
            value = read()
            try:
                if predicate(value):
                    return value
            except (KeyError, TypeError, IndexError, AttributeError):
                pass
            if time.monotonic() > deadline:
                return value
            time.sleep(interval)


class Suite:
    """Cases of one protocol module in execution order.

    fixture() cases are unscored setup (any success status); a scored case names the fixture groups and earlier
    cases it needs (needs) and, when it only shows a rejection or that nothing changed, the positive cases that
    prove the feature exists (requires)."""

    def __init__(self, prefix=''):
        self.prefix = prefix
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='api', description='', needs=(), requires=(), gui=None):
        cid = f'{self.prefix}{channel}.{family}.{scenario}.{step}'
        if cid in self.ids:
            raise ValueError('duplicate ' + cid)
        known = self.ids | {'fx:' + c.family for c in self.cases if c.channel == 'setup'}
        for item in [*needs, *requires]:
            if item not in known:
                raise ValueError(f'{cid} names an unknown earlier case or fixture: {item}')
        self.ids.add(cid)
        self.cases.append(Case(cid, family, scenario, channel, description or step, action, list(needs),
                               list(requires), gui))
        return cid

    def check(self, family, scenario, step, action, description=''):
        """A program check run only as a backend point of a browser checkpoint (never a checkpoint of its own)."""
        return self.add(family, scenario, step, action, channel='check', description=description)

    def fixture(self, group, step, action, description=''):
        """Unscored setup in fixture group `group` (needed as 'fx:<group>')."""
        return self.add(group, 'fixture', step, action, channel='setup', description=description)

    def gui(self, scenario, step, goal, acceptance, recipe, checks=(), needs=(), requires=()):
        """A checkpoint the evaluator operates in the browser; its backend points are the named check cases."""
        return self.add('browser', scenario, step, None, channel='ui', description=goal, needs=needs,
                        requires=requires, gui={'goal': goal, 'acceptance': acceptance, 'recipe': recipe,
                                                'checks': list(checks)})

    def api(self, family, scenario, step, method, path, actor='alice', body=None, params=None, form=None, raw=None,
            content_type=None, headers=None, save=None, status=None, want=None, check=None, view=None,
            hint='object', before=None, description=None, needs=(), requires=(), error_text=True):
        def action(c, relaxed=False):
            if before:
                before(c)
            pp, bb, qq, ff, aa = (resolve(x, c) for x in (path, body, params, form, actor))
            r, p = c.request(method, pp, aa, body=bb, params=qq, headers=resolve(headers, c), form=ff,
                             raw=resolve(raw, c), content_type=content_type)
            if relaxed:
                # Unscored setup: any success status; keep only the values later steps need.
                assert 200 <= r.status_code < 300, f'setup {method} {pp}: status {r.status_code}; {str(p)[:300]}'
                if save:
                    c.state[save] = p
                return None
            if save and r.status_code < 400:
                c.state[save] = p
            if status is not None:
                allowed = status if isinstance(status, (list, tuple)) else [status]
                assert r.status_code in allowed, f'{method} {pp}: status {r.status_code}; {str(p)[:300]}'
            if want:
                expected = resolve(want, c)
                assert isinstance(p, dict), 'expected a JSON object'
                for k, v in expected.items():
                    assert k in p and p[k] == v, f'{k}: {p.get(k)!r} != {v!r}'
            if check:
                check(c, r, p)
            shown = (lambda payload: view(payload, c)) if getattr(view, 'contextual', False) else view
            return c.observe(r, p, hint, shown, error_text)

        text = description or f'{method} {path if isinstance(path, str) else "<resource>"} as {actor}'
        if family.endswith('-fixture') or scenario == 'fixture':
            return self.add(family, 'fixture', step, action, channel='setup', description=text)
        return self.add(family, scenario, step, action, description=text, needs=needs, requires=requires)

    def setup(self, group, step, method, path, **kw):
        """An unscored setup request in fixture group `group`."""
        return self.api(group, 'fixture', step, method, path, **kw)

    def bind(self, case_id, *companions, replace=False):
        """Bind a point to companion points defined anywhere in the module (for example a bare confirmation to
        the later read that shows its effect); with replace, the earlier companions are dropped."""
        target = next(c for c in self.cases if c.id == case_id)
        for item in companions:
            assert item in self.ids and item != case_id, f'{case_id}: unknown companion {item}'
        target.requires[:] = ([] if replace else [x for x in target.requires if x not in companions]) + list(companions)

    def unbind(self, case_id):
        """A point that shows a positive result by itself needs no companion."""
        next(c for c in self.cases if c.id == case_id).requires.clear()


# -- projections -------------------------------------------------------------------------------------------
def field(value, path):
    for part in path.split('.'):
        if isinstance(value, list):
            assert part.isdigit() and int(part) < len(value), 'missing list member ' + part
            value = value[int(part)]
        else:
            assert isinstance(value, dict) and part in value, 'missing field ' + part
            value = value[part]
    return value


def pick(*paths):
    """View: the named fields (dotted paths) of an object, or of every member of a list."""
    def view(payload):
        if isinstance(payload, list):
            return [view(x) for x in payload]
        assert isinstance(payload, dict), 'expected a JSON object'
        return {p: field(payload, p) for p in paths}
    return view


def members(key, *paths, unordered_by=None):
    """View: {total?, key: [projected members]} of a collection response such as {total, entries}."""
    def view(payload):
        assert isinstance(payload, dict) and isinstance(payload.get(key), list), 'expected a ' + key + ' collection'
        items = [{p: field(x, p) for p in paths} if paths else x for x in payload[key]]
        out = {key: unordered(items) if unordered_by else items}
        if 'total' in payload:
            out['total'] = payload['total']
        return out
    return view


# -- the product's outbound requests --------------------------------------------------------------------------
SENT_HEADERS = ('user-agent', 'accept', 'authorization', 'cookie', 'if-none-match', 'if-modified-since',
                'content-type', 'referer')


def sent(request, headers=SENT_HEADERS):
    """One request the product sent to the local web: method, URL and the named headers (absent ones as null)."""
    out = {'method': request['method'], 'url': norm_text(request['url'])}
    for name in headers:
        out[name] = request['headers'].get(name)
    return out


def contextual(view):
    """Mark a view that also needs the episode context: view(payload, c)."""
    view.contextual = True
    return view


def ordered_groups(key, project):
    """View of an ordered collection whose members with equal sort keys may come in any order: the sequence of
    groups (one per run of equal key(member)), each the multiset of project(member)."""
    def view(payload):
        assert isinstance(payload, list), 'expected a collection'
        groups = []
        for member in payload:
            value = key(member)
            if groups and groups[-1][0] == value:
                groups[-1][1].append(project(member))
            else:
                groups.append((value, [project(member)]))
        return [unordered(members) for _, members in groups]
    return view


def grouped(key, label='title'):
    """View of an ordered entry collection where members with equal sort keys may come in any order: the sequence
    of groups (one per run of equal keys) with the members of each group as a multiset."""
    def view(payload):
        assert isinstance(payload, dict) and isinstance(payload.get('entries'), list), 'expected an entries collection'
        groups = []
        for member in payload['entries']:
            value = field(member, key)
            if groups and groups[-1][0] == value:
                groups[-1][1].append(field(member, label))
            else:
                groups.append((value, [field(member, label)]))
        return {'total': payload.get('total'),
                'groups': [{'key': value, 'members': unordered(sorted(names))} for value, names in groups]}
    return view
