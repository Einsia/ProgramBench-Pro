'''Program-check vocabulary and public access to one candidate through the black-box runtime.

One operation with all its assertions is one CASE. Every request reaches the candidate through the runtime's api
operation, the channel the model also has on the reference. Nothing here reads candidate files, databases or
processes.
'''
from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import io
import json
import pathlib
import re
import urllib.parse
import zipfile

from evaluation.broker import BrokerError

# The initial account of every fresh data directory (shown on the product's own sign-in page).
ADMIN = {'username': 'admin', 'email': 'changeme@example.com', 'password': 'MyPassword'}
# The product origin as the runtime configures it (PORT 3000 on loopback, for the reference and every candidate).
ORIGIN = 'http://127.0.0.1:3000'
API = '/api/'
UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
HEX_ID = re.compile(r'(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])')
INSTANT = re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?')
DAY = re.compile(r'\d{4}-\d{2}-\d{2}')
JWT = re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')


class MissingDependency(AssertionError):
    pass


class State(dict):
    def __missing__(self, key):
        raise MissingDependency('missing successful prerequisite ' + str(key))


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object


class Ref:
    def __init__(self, key, *path):
        self.key, self.path = key, path

    def get(self, ctx):
        if self.key not in ctx.state:
            raise MissingDependency('missing result ' + self.key)
        value = ctx.state[self.key]
        try:
            for part in self.path:
                value = value[part]
        except (KeyError, IndexError, TypeError) as error:
            raise MissingDependency('prerequisite ' + self.key + ' lacks ' + str(self.path)) from error
        return value


def resolve(x, ctx):
    if isinstance(x, Ref):
        return x.get(ctx)
    if callable(x):
        return x(ctx)
    if isinstance(x, dict):
        return {k: resolve(v, ctx) for k, v in x.items()}
    if isinstance(x, (tuple, list)):
        return [resolve(v, ctx) for v in x]
    return x


def pathref(template, **values):
    return lambda c: template.format(**{k: urllib.parse.quote(str(resolve(v, c)), safe='') for k, v in values.items()})


def b64(data):
    return base64.b64encode(data.encode() if isinstance(data, str) else data).decode()


def subset(got, want):
    assert isinstance(got, dict), 'expected an object, got ' + type(got).__name__
    for k, v in want.items():
        assert k in got, 'missing ' + k
        assert got[k] == v, k + ': ' + repr(got[k])[:200] + ' != ' + repr(v)[:200]


def unordered(values):
    '''Private observation marker: membership with multiplicity, never order.'''
    return {'@unordered': list(values)}


def today():
    return datetime.datetime.now(datetime.timezone.utc).date()


class RelativeDay(str):
    pass


def day(offset):
    '''A calendar day relative to the day the case runs (meal plans are about the coming days).'''
    return RelativeDay((today() + datetime.timedelta(days=offset)).isoformat())


class Response:
    '''What a program check sees of one product response: status, allowed headers, exact bytes.'''

    def __init__(self, status, headers, content):
        self.status_code, self.content = status, content
        self.headers = {str(k).lower(): v for k, v in (headers or {}).items()}

    @property
    def text(self):
        return self.content.decode('utf-8', errors='replace')

    def json(self):
        return json.loads(self.content.decode('utf-8'))


def parse_instant(value):
    '''An instant with a time of day; naive values are UTC (the product writes some with fractions or offsets).'''
    text = value.strip().replace(' ', 'T')
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    stamp = datetime.datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=datetime.timezone.utc)
    return stamp.astimezone(datetime.timezone.utc)


class Normalize:
    '''Projection of a response onto its behaviour. Generated identities (UUIDs) become aliases, compared later as a
    bijection; instants and days near the moment the case runs become offsets from it (generated clock values and
    the meal-plan days of the coming week), far ones a canonical UTC literal; secrets and signed tokens become
    markers. Everything a request supplied (names, notes, quantities, chosen dates) stays.'''

    SECRET = {'token', 'access_token', 'refresh_token', 'mealplanIcalToken', 'fileToken', 'file_token',
              'password', 'passwordHash', 'password_hash', 'hashedPassword', 'hashed_password', 'apiKey', 'api_key'}
    # Sizes of the instance's files depend on compression and generated identities, not on behaviour.
    SIZES = {'size', 'dataDirSize', 'tempDirSize', 'backupsDirSize', 'groupsDirSize', 'recipesDirSize',
             'userDirSize', 'usedStorageBytes', 'usedStorageStr'}
    ORGANIZERS = {'tags', 'recipeCategory', 'tools'}
    STAMP = re.compile(r'\d{4}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}')
    # iCalendar: the generation instant of each event, and event days in the compact basic form.
    ICAL_STAMP = re.compile(r'(?m)^(DTSTAMP|LAST-MODIFIED|CREATED):\d{8}T\d{6}Z?$')
    ICAL_DAY = re.compile(r'(?m)(;VALUE=DATE:)(\d{8})$')
    NEAR_DAYS = 400
    # Calendar literals chosen by the cases are values, not offsets from the machine's current date.
    FIXED_DAYS = {'2001-01-01', '2001-01-31', '2020-02-29', '2026-12-01', '2026-12-02',
                  '2091-03-01', '2091-03-04', '2091-03-05', '2091-03-31'}
    FIXED_INSTANTS = {'2025-06-01T12:00:00Z', '2026-01-02T03:04:05Z', '2026-01-15T12:00:00Z',
                      '2026-02-03T04:05:06Z', '2026-03-04T05:06:07Z', '2030-01-01T00:00:00Z'}
    URL_FIELDS = {'next', 'previous', 'nextPage', 'previousPage', 'next_url', 'previous_url'}

    def __init__(self, base):
        self.base = base
        self.ids = {}
        self.relative_days = set()
        self.resource = None

    def remember_relative_days(self, value):
        if isinstance(value, RelativeDay):
            self.relative_days.add(str(value))
        elif isinstance(value, dict):
            for child in value.values():
                self.remember_relative_days(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                self.remember_relative_days(child)

    def identity(self, value):
        key = value.lower().replace('-', '')
        if key not in self.ids:
            self.ids[key] = '@id:' + str(len(self.ids) + 1)
        return self.ids[key]

    def numeric_identity(self, value, resource):
        key = 'int:' + resource + ':' + str(value)
        if key not in self.ids:
            self.ids[key] = '@int:' + resource + ':' + str(sum(x.startswith('int:' + resource + ':') for x in self.ids) + 1)
        return self.ids[key]

    @staticmethod
    def canonical_url(value):
        try:
            parsed = urllib.parse.urlsplit(value)
            if not parsed.query:
                return value
            query = sorted(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                            urllib.parse.urlencode(query, doseq=True), parsed.fragment))
        except (TypeError, ValueError):
            return value

    GENERATED_CLOCK_FIELDS = {'dateAdded', 'dateUpdated', 'createdAt', 'updateAt', 'updatedAt', 'created_at', 'updated_at', 'update_at'}

    def instant(self, value, literal=True):
        try:
            stamp = parse_instant(value)
        except ValueError:
            return value
        canonical = stamp.strftime('%Y-%m-%dT%H:%M:%SZ')
        if literal and canonical in self.FIXED_INSTANTS:
            return canonical
        now = datetime.datetime.now(datetime.timezone.utc)
        delta = (stamp - now).total_seconds() / 86400
        if abs(delta) <= self.NEAR_DAYS:
            return '@now%+dd' % round(delta)
        return stamp.strftime('%Y-%m-%dT%H:%M:%SZ')

    def day(self, value, literal=True):
        if literal and value in self.FIXED_DAYS and value not in self.relative_days:
            return value
        try:
            when = datetime.date.fromisoformat(value)
        except ValueError:
            return value
        offset = (when - today()).days
        return '@day%+d' % offset if abs(offset) <= self.NEAR_DAYS else value

    def text(self, s, key=''):
        if key in self.URL_FIELDS and (s.startswith('/') or '://' in s):
            s = self.canonical_url(s)
        if INSTANT.fullmatch(s):
            return self.instant(s, literal=key not in self.GENERATED_CLOCK_FIELDS)
        if DAY.fullmatch(s):
            return self.day(s, literal=key not in self.GENERATED_CLOCK_FIELDS)
        s = s.replace(self.base, '@origin').replace('\r\n', '\n')
        s = JWT.sub('@jwt', s)
        s = self.STAMP.sub('@stamp', s)
        s = re.sub(r'(UID:mealplan-)([0-9]+)(-)', lambda m: m[1] + self.numeric_identity(int(m[2]), 'mealplan') + m[3], s)
        s = self.ICAL_STAMP.sub(lambda m: m[1] + ':@stamp', s)
        s = self.ICAL_DAY.sub(lambda m: m[1] + self.day('%s-%s-%s' % (m[2][:4], m[2][4:6], m[2][6:])), s)
        s = UUID.sub(lambda m: self.identity(m[0]), s)
        return HEX_ID.sub(lambda m: self.identity(m[0]), s)

    def clean(self, v, key='', resource='auto'):
        if resource == 'auto':
            resource = self.resource
        if key == 'tokens':
            resource = 'api-token'
        if isinstance(v, dict):
            if 'date' in v and 'entryType' in v:
                resource = 'mealplan'
            out = {}
            for k, val in sorted(v.items()):
                if k in self.SECRET and isinstance(val, str):
                    out[k] = '@secret' if val else val
                elif k in self.SIZES and isinstance(val, (str, int, float)) and not isinstance(val, bool):
                    out[k] = '@size'
                elif k == 'image' and isinstance(val, str) and val:
                    # A recipe's image field is a random cache key; only its presence is behaviour.
                    out[k] = '@image'
                elif k == 'id' and isinstance(val, int) and not isinstance(val, bool) and resource:
                    out[k] = self.numeric_identity(val, resource)
                elif k in self.ORGANIZERS and isinstance(val, list) and all(isinstance(x, dict) for x in val):
                    # The organizers attached to one recipe form a set (imports fill them in set order).
                    out[k] = self.clean(sorted(val, key=lambda x: (str(x.get('slug')), str(x.get('name')))), k, resource)
                else:
                    out[k] = self.clean(val, k, resource if k in {'items', 'tokens'} else None)
            return out
        if isinstance(v, list):
            return [self.clean(x, key, resource) for x in v]
        if isinstance(v, str):
            return self.text(v, key)
        if isinstance(v, float) and v == int(v) and abs(v) < 2 ** 53:
            # JSON numbers: 2 and 2.0 are the same value.
            return int(v)
        return v


class AliasGraph:
    '''Compare opaque identities by a persistent bijection, not counters. Response objects may carry fields the
    reference does not have; every reference field must be present and equal. Data-keyed maps and empty objects stay
    exact: an extra entry there is different data.'''

    TOKEN = re.compile(r'@id:[0-9]+|@int:[a-z-]+:[0-9]+')
    FIELD = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
    MAPS = {'extras', 'headers', '@exact'}

    def __init__(self):
        self.forward = {}
        self.reverse = {}

    def compare(self, actual, expected):
        forward, reverse = dict(self.forward), dict(self.reverse)

        def walk(a, e, path, parent=None):
            if type(a) in (int, float) and type(e) in (int, float):
                if '.rgb_regions' in path:
                    assert abs(a - e) <= 12, path + ': image color differs'
                    return
                assert abs(a - e) <= 1e-9 * max(1, abs(e)), path + ': different numeric value'
                return
            assert type(a) is type(e), path + ': different value type'
            if isinstance(e, dict):
                if e.keys() == {'@unordered'}:
                    assert a.keys() == e.keys() and isinstance(a['@unordered'], list), path + ': different collection'
                    av, ev = a['@unordered'], e['@unordered']
                    assert len(av) == len(ev), path + ': different collection length'
                    todo = sorted(ev, key=lambda x: -sum(m[0] in forward for m in self.TOKEN.finditer(json.dumps(x))))

                    def match(index, remaining):
                        if index == len(todo):
                            return True
                        for pos in remaining:
                            saved = (dict(forward), dict(reverse))
                            try:
                                walk(av[pos], todo[index], path + '{member}')
                                if match(index + 1, [x for x in remaining if x != pos]):
                                    return True
                            except AssertionError:
                                pass
                            forward.clear()
                            forward.update(saved[0])
                            reverse.clear()
                            reverse.update(saved[1])
                        return False
                    assert match(0, list(range(len(av)))), path + ': unordered membership or identity relationships differ'
                    return
                if not e or parent in self.MAPS or not all(self.FIELD.match(k) for k in e):
                    assert a.keys() == e.keys(), path + ': different fields'
                else:
                    missing = sorted(set(e) - set(a))
                    assert not missing, path + ': missing fields ' + ', '.join(missing[:5])
                for k in e:
                    walk(a[k], e[k], path + '.' + k, k)
            elif isinstance(e, list):
                assert len(a) == len(e), path + ': different collection length'
                for i, (x, y) in enumerate(zip(a, e)):
                    walk(x, y, path + '[' + str(i) + ']', parent)
            elif isinstance(e, str):
                at, et = list(self.TOKEN.finditer(a)), list(self.TOKEN.finditer(e))
                assert self.TOKEN.split(a) == self.TOKEN.split(e) and len(at) == len(et), path + ': different text'
                for am, em in zip(at, et):
                    got, want = am[0], em[0]
                    assert got.rsplit(':',1)[0] == want.rsplit(':',1)[0], path + ': identity type differs'
                    assert forward.get(want, got) == got and reverse.get(got, want) == want, \
                        path + ': inconsistent identity relationship'
                    forward[want] = got
                    reverse[got] = want
            else:
                assert a == e, path + ': different value'

        walk(actual, expected, '$')
        self.forward, self.reverse = forward, reverse


class Context:
    '''Public access to one candidate instance (through the runtime) plus the observation normalizers.'''

    HEADERS = ('content-disposition',)

    def __init__(self, broker, out):
        self.broker = broker
        self.base = ORIGIN
        self.out = pathlib.Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.state = State()
        self.norm = Normalize(self.base)
        self.aliases = AliasGraph()
        # Accounts: the initial administrator, plus those the cases create (name -> password).
        self.creds = {ADMIN['username']: ADMIN['password']}
        self.tokens = {}
        self.current_case = None
        self.last_order = None

    def close(self):
        pass

    def restart_server(self):
        '''Restart the product process with the same data directory (runtime op restart).'''
        status = self.broker.call({'op': 'restart'})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        return status

    def running(self):
        return bool(self.broker.call({'op': 'status'}).get('running'))

    def raw(self, rpc):
        try:
            answer = self.broker.call(rpc)
        except BrokerError as exc:
            # The runtime could not complete the product request (connection refused, timeout, malformed reply).
            raise AssertionError('candidate HTTP request failed: ' + exc.detail[:300]) from None
        assert not answer.get('truncated'), 'the product response exceeds the black-box response limit'
        r = Response(answer['status'], answer.get('headers'), base64.b64decode(answer.get('body_base64') or ''))
        try:
            payload = r.json()
        except ValueError:
            payload = r.text
        return r, payload

    def sign_in(self, user, password=None):
        '''The sign-in form of /api/auth/token; returns the session token (cached per account).'''
        r, p = self.raw({'op': 'api', 'method': 'POST', 'path': API + 'auth/token', 'binary': True,
                         'form': {'username': user, 'password': password or self.creds[user]}})
        assert 200 <= r.status_code < 300 and isinstance(p, dict) and p.get('access_token'), \
            'sign-in of ' + user + ' failed: ' + str(r.status_code)
        self.tokens[user] = p['access_token']
        return p['access_token']

    def bearer(self, actor):
        if actor not in self.tokens:
            self.sign_in(actor)
        return self.tokens[actor]

    def request(self, method, path, actor='admin', body=None, params=None, headers=None, raw=None, multipart=None,
                content_type=None, form=None):
        '''One product request. actor: None (anonymous), a known account name (signed in once, then its session
        token), token:KEY (a stored token value, or a stored object's token field) or bad (a malformed token).'''
        self.norm.remember_relative_days(body)
        self.norm.remember_relative_days(params)
        full = path if path.startswith('/') else API + path
        if params:
            pairs = [(k, str(v).lower() if isinstance(v, bool) else v) for k, v in params.items()]
            full += ('&' if '?' in full else '?') + urllib.parse.urlencode(pairs, doseq=True)
        rpc = {'op': 'api', 'method': method.upper(), 'path': full, 'binary': True}
        if actor == 'bad':
            rpc['token'] = 'not-a-valid-token'
        elif isinstance(actor, str) and actor.startswith('token:'):
            value = self.state[actor[6:]]
            rpc['token'] = value.get('token') if isinstance(value, dict) else value
        elif actor:
            assert actor in self.creds, 'unknown account ' + str(actor)
            rpc['token'] = self.bearer(actor)
        forwarded = {k.lower(): v for k, v in (headers or {}).items()}
        if 'content-type' in forwarded:
            content_type = forwarded.pop('content-type')
        if forwarded:
            rpc['headers'] = forwarded
        if multipart is not None:
            rpc['multipart'] = multipart
        elif form is not None:
            rpc['form'] = form
        elif raw is not None:
            rpc['body_base64'] = b64(raw)
            if content_type:
                rpc['content_type'] = content_type
        elif body is not None:
            rpc['json'] = body
        r, payload = self.raw(rpc)
        self.last_order = (params or {}).get('orderBy')
        self.norm.resource = 'api-token' if 'api-tokens' in full else 'mealplan' if 'mealplans' in full and '/rules' not in full and '/ical' not in full else None
        assert r.status_code < 500, 'candidate HTTP server error ' + str(r.status_code) + ': ' + str(payload)[:300]
        return r, payload

    def archive(self, content):
        '''A ZIP answer compared by normalized JSON and decoded/hashed member content.'''
        try:
            z = zipfile.ZipFile(io.BytesIO(content))
        except zipfile.BadZipFile as error:
            raise AssertionError('export is not a ZIP archive') from error
        assert z.namelist() and z.testzip() is None, 'empty or damaged ZIP archive'
        members = {}
        for name in sorted(z.namelist()):
            key = self.norm.text(name)
            data = z.read(name)
            if name.endswith('.json'):
                try:
                    payload = json.loads(data.decode('utf-8'))
                    if name == 'database.json' and isinstance(payload, dict):
                        # The exported user row contains a random browser cache
                        # suffix after a profile upload. The image bytes below
                        # carry the actual persisted image behavior.
                        for user in payload.get('users', []):
                            if isinstance(user, dict) and isinstance(user.get('cache_key'), str) and user['cache_key']:
                                user['cache_key'] = '@image-cache'
                    members[key] = self.norm.clean(payload)
                    continue
                except (ValueError, UnicodeDecodeError) as error:
                    raise AssertionError('ZIP JSON member cannot be parsed: ' + name) from error
            if pathlib.PurePosixPath(name).name.startswith('.') and 'secret' in pathlib.PurePosixPath(name).name:
                members[key] = {'present': True}
                continue
            if name.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                members[key] = self.image_signature(data)
            else:
                members[key] = {'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        return {'is_zip': True, 'members': members}

    @staticmethod
    def image_signature(content):
        """Decode public image bytes and summarize dimensions and representative regions."""
        from PIL import Image, ImageStat
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.load()
                rgb = image.convert('RGB')
        except (OSError, ValueError, SyntaxError) as error:
            raise AssertionError('download is not a decodable image') from error
        width, height = rgb.size
        assert 0 < width <= 8192 and 0 < height <= 8192, 'invalid image dimensions'
        regions = []
        for row in range(2):
            for col in range(2):
                box = (int((col + .15) * width / 2), int((row + .15) * height / 2),
                       max(1, int((col + .85) * width / 2)), max(1, int((row + .85) * height / 2)))
                regions.append([round(x, 1) for x in ImageStat.Stat(rgb.crop(box)).mean])
        return {'width': width, 'height': height, 'rgb_regions': regions}

    def observe(self, r, payload, hint='object', fields=None):
        status = r.status_code
        if status >= 400:
            return {'status': status, 'error': self.error_shape(payload)}
        kind = r.headers.get('content-type', '').split(';')[0].strip().lower()
        if hint == 'bytes':
            body = {'sha256': hashlib.sha256(r.content).hexdigest(), 'size': len(r.content)}
        elif hint == 'image':
            body = self.image_signature(r.content)
        elif hint == 'zip':
            body = self.archive(r.content)
        elif hint == 'zip-names':
            body = self.archive(r.content)
        elif hint == 'none':
            body = None
        elif isinstance(payload, (dict, list)):
            body = self.norm.clean(project(payload, fields) if fields else payload)
        else:
            body = self.norm.text(r.text)
        if self.last_order and isinstance(payload, (dict, list)) and isinstance(body, (dict, list)):
            rows = payload.get('items') if isinstance(payload, dict) else payload
            shown = body.get('items') if isinstance(body, dict) else body
            if isinstance(rows, list) and isinstance(shown, list) and len(rows) == len(shown):
                key = self.last_order
                if all(isinstance(row, dict) and key in row for row in rows):
                    grouped, i = [], 0
                    while i < len(rows):
                        end = i + 1
                        while end < len(rows) and rows[end][key] == rows[i][key]:
                            end += 1
                        grouped.append(unordered(shown[i:end]) if end > i + 1 else shown[i])
                        i = end
                    if isinstance(body, dict):
                        body['items'] = grouped
                    else:
                        body = grouped
        return {'status': status, 'content_type': kind, 'body': body}

    @staticmethod
    def error_shape(payload):
        '''What an error answer must agree on: its status, and the type of a FastAPI validation error.'''
        if isinstance(payload, dict) and isinstance(payload.get('detail'), list):
            return {'validation': sorted({str(x.get('type')) for x in payload['detail'] if isinstance(x, dict)})}
        return None


def project(payload, fields):
    '''Keep the named top-level fields (or, for a page, the named fields of each item).'''
    if isinstance(payload, list):
        return [project(x, fields) for x in payload]
    if isinstance(payload, dict) and 'items' in payload and isinstance(payload['items'], list):
        out = {k: payload[k] for k in ('page', 'per_page', 'total', 'total_pages') if k in payload}
        out['items'] = [project(x, fields) for x in payload['items']]
        return out
    if isinstance(payload, dict):
        missing = set(fields) - payload.keys()
        assert not missing, 'missing projected response fields: ' + ', '.join(sorted(missing))
        return {k: payload[k] for k in fields}
    return payload


class Suite:
    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='api', description=''):
        if family.endswith('fixture'):
            channel = 'setup'
        cid = channel + '.' + family + '.' + scenario + '.' + step
        if cid in self.ids:
            raise ValueError('duplicate ' + cid)
        self.ids.add(cid)
        self.cases.append(Case(cid, family, scenario, channel, description or step, action))
        return cid

    def api(self, family, scenario, step, method, path, actor='admin', body=None, params=None, save=None, status=None,
            want=None, check=None, hint='object', headers=None, raw=None, multipart=None, content_type=None,
            form=None, fields=None, before=None):
        def action(c, relaxed=False):
            pp, bb, qq, aa = resolve(path, c), resolve(body, c), resolve(params, c), resolve(actor, c)
            if before:
                before(c)
            r, p = c.request(method, pp, aa, bb, qq, resolve(headers, c), resolve(raw, c), resolve(multipart, c),
                             content_type, resolve(form, c))
            if relaxed:
                # Unscored setup: any success status; keep only the values later steps need.
                assert 200 <= r.status_code < 300, 'setup ' + method + ' ' + str(pp) + ': status ' + str(r.status_code) + '; ' + str(p)[:300]
                if save:
                    c.state[save] = p
                return None
            if save and r.status_code < 400:
                c.state[save] = p
            if status is not None:
                allowed = [status] if isinstance(status, int) else status
                assert r.status_code in allowed, method + ' ' + str(pp) + ': status ' + str(r.status_code) + '; ' + str(p)[:350]
            if want:
                subset(p, resolve(want, c))
            if check:
                check(c, r, p)
            observation = c.observe(r, p, hint, fields)
            # Only explicit per-case alternatives are equivalent; the actual response was validated above.
            if status is not None and not isinstance(status, int):
                observation['status'] = min(status)
            return observation

        return self.add(family, scenario, step, action,
                        description=method + ' ' + (path if isinstance(path, str) else '<relational resource>') + ' as ' + str(actor))

    def manifest(self):
        return [dict(id=x.id, family=x.family, scenario=x.scenario, channel=x.channel, scored=x.channel != 'setup',
                     description=x.description) for x in self.cases]
