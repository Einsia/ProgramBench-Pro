'''Program-check vocabulary and public access to one candidate through the black-box runtime (task-owned).

Every request reaches the candidate through the runtime api operation, the channel the model also has on the
reference; the music library is filled with its library_put operation and the product is restarted with its
lifecycle operations. Nothing here reads candidate files, databases or processes.
'''
from __future__ import annotations

import base64
import dataclasses
import hashlib
import struct
import time
import urllib.parse

import library
import normalize
from evaluation.broker import BrokerError

ORIGIN = 'http://127.0.0.1:3000'
PASSWORDS = {'admin': 'Admin-Local-2026!', 'bob': 'Bob-Local-2026!', 'carol': 'Carol-Local-2026!'}
NAMES = {'admin': 'Admin', 'bob': 'Bob', 'carol': 'Carol'}
CLIENT = {'v': '1.16.1', 'c': 'pbp-check'}
TRACKS = len(library.tracks())
FIXTURE_PICTURES = {hashlib.sha256(library.png(rgb)).hexdigest(): name for name, rgb in library.COVERS.items()}


class MissingDependency(AssertionError):
    pass


class State(dict):
    def __missing__(self, key):
        raise MissingDependency('missing successful prerequisite ' + str(key))


class Ref:
    def __init__(self, key, *path):
        self.key, self.path = key, path

    def get(self, ctx):
        if self.key not in ctx.state:
            raise MissingDependency('missing result ' + str(self.key))
        value = ctx.state[self.key]
        try:
            for part in self.path:
                value = value[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise MissingDependency('prerequisite %s lacks %s' % (self.key, self.path)) from exc
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


def subset(got, want):
    for key, value in want.items():
        assert key in got, 'missing ' + key
        assert got[key] == value, '%s: %r != %r' % (key, got[key], value)


@dataclasses.dataclass
class Case:
    id: str
    family: str
    scenario: str
    channel: str
    description: str
    action: object


class Context:
    '''Public access to one candidate instance (through the runtime) plus the observation normalizers.'''

    def __init__(self, broker, out):
        self.broker = broker
        self.out = out
        self.state = State()
        self.norm = normalize.Normalize(ORIGIN)
        self.aliases = normalize.AliasGraph()
        self.tokens = {}
        self.logins = []
        self.current_case = None
        self.files = None
        self.notes = []

    def close(self):
        pass

    # -- channels ------------------------------------------------------------------------------------------
    def call(self, request):
        try:
            return self.broker.call(request)
        except BrokerError as exc:
            raise AssertionError('black-box request failed: ' + exc.detail[:300]) from None

    def http(self, method, path, *, headers=None, body=None, raw=None, multipart=None, content_type=None, binary=False):
        request = {'op': 'api', 'method': method, 'path': path}
        if headers:
            request['headers'] = headers
        if body is not None:
            request['json'] = body
        if raw is not None:
            request['body'] = raw
        if multipart is not None:
            request['multipart'] = multipart
        if content_type:
            request['content_type'] = content_type
        if binary:
            request['binary'] = True
        answer = self.call(request)
        assert not answer.get('truncated'), 'the product response exceeds the black-box response limit'
        assert answer['status'] < 500 or answer['status'] == 501, 'candidate server error %s: %s' % (answer['status'], str(answer.get('body'))[:300])
        answer['headers'] = {k.lower(): v for k, v in (answer.get('headers') or {}).items()}
        return answer

    def subsonic(self, op, user='admin', *, password=None, auth=True, method='GET', binary=False, fmt='json', headers=None, **query):
        values = {**CLIENT, **query}
        if fmt:
            values['f'] = fmt
        if auth:
            values['u'] = user
            values['p'] = password if password is not None else PASSWORDS.get(user, user)
        path = '/rest/' + op + '?' + urllib.parse.urlencode(values, doseq=True)
        return self.http(method, path, headers=headers, binary=binary)

    @staticmethod
    def reply(answer):
        body = answer['body']
        assert isinstance(body, dict) and isinstance(body.get('subsonic-response'), dict), \
            'not a subsonic response (HTTP %s)' % answer['status']
        return body['subsonic-response']

    def login(self, username, password):
        '''One sign-in request. The product limits /auth/login to five requests per twenty seconds and counts them in a sliding window, so the checks stay well below that and wait out a refusal.'''
        answer = None
        for _ in range(4):
            while True:
                now = time.monotonic()
                self.logins = [t for t in self.logins if now - t < 21.0]
                if len(self.logins) < 3:
                    break
                time.sleep(max(0.2, 21.0 - (now - self.logins[0])))
            self.logins.append(time.monotonic())
            answer = self.http('POST', '/auth/login', body={'username': username, 'password': password})
            if answer['status'] != 429:
                break
            time.sleep(21.0)
            self.logins = []
        return answer

    def forget_token(self, user):
        self.tokens.pop(user, None)

    def token(self, user, password=None):
        # One login per account and episode: the product limits sign-in attempts to five per twenty seconds.
        if user not in self.tokens:
            secret = password if password is not None else PASSWORDS[user]
            answer = self.login(user, secret)
            assert answer['status'] == 200 and isinstance(answer['body'], dict) and answer['body'].get('token'), \
                'sign-in of %s answered %s' % (user, answer['status'])
            self.tokens[user] = answer['body']['token']
        return self.tokens[user]

    def native(self, method, path, user='admin', *, body=None, params=None, anonymous=False, token=None, raw=None,
               multipart=None, headers=None, content_type=None, binary=False):
        target = '/api/' + path.lstrip('/')
        if params:
            target += '?' + urllib.parse.urlencode(params, doseq=True)
        sent = dict(headers or {})
        if not anonymous:
            sent['x-nd-authorization'] = 'Bearer ' + (token or self.token(user))
        return self.http(method, target, headers=sent or None, body=body, raw=raw, multipart=multipart,
                         content_type=content_type, binary=binary)

    # -- lifecycle and library -----------------------------------------------------------------------------
    def running(self):
        return bool(self.call({'op': 'status'}).get('running'))

    def scan_state(self):
        return self.reply(self.subsonic('getScanStatus')).get('scanStatus', {})

    def song_total(self):
        '''How many songs the product lists: the X-Total-Count of the native song collection, or the scan count of
        getScanStatus when the collection does not answer.'''
        answer = self.native('GET', 'song', params={'_start': 0, '_end': 1, '_sort': 'title', '_order': 'ASC'})
        total = answer['headers'].get('x-total-count') if answer['status'] == 200 else None
        if total is not None and str(total).isdigit():
            return int(total)
        return self.scan_state().get('count')

    def settle(self, count=None, first=True, quiet=3.0, timeout=60.0):
        '''Wait until no scan runs and the song total stays unchanged for a while, optionally at count. A fresh product
        scans its still empty library by itself shortly after it starts, and a scan requested meanwhile is dropped;
        with first, a product that reports lastScan is waited for until that first scan has run. Returns whether the
        product settled (at count) before the timeout.'''
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.scan_state()
            started = 'lastScan' not in state or not str(state.get('lastScan')).startswith('0001')
            if not state.get('scanning') and (started or not first):
                total = self.song_total()
                if count is None or total == count:
                    time.sleep(quiet)
                    if not self.scan_state().get('scanning') and self.song_total() == total:
                        return True
            time.sleep(0.5)
        return False

    def scan_until(self, count, attempts=4, timeout=40.0, idle=10.0):
        '''Full scans until the product lists count songs. A request the product drops (another scan runs) is
        repeated; a product that stays idle at another total keeps it, so the checks compare what it shows.'''
        for _ in range(attempts):
            self.reply(self.subsonic('startScan', fullScan='true'))
            time.sleep(1)
            deadline = time.monotonic() + timeout
            last, since = None, time.monotonic()
            while time.monotonic() < deadline:
                if self.settle(count, first=False, quiet=3.0, timeout=2.0):
                    return True
                now = (bool(self.scan_state().get('scanning')), self.song_total())
                if now != last:
                    last, since = now, time.monotonic()
                elif not now[0] and time.monotonic() - since >= idle:
                    break
                time.sleep(0.5)
        return False

    def artwork_state(self):
        '''Which songs and albums the product has found to have no image: its native objects carry imageAbsent once the background artwork worker has looked at them.'''
        state = {}
        for kind, sort in (('song', 'title'), ('album', 'name')):
            answer = self.native('GET', kind, params={'_start': 0, '_end': 500, '_sort': sort, '_order': 'ASC'})
            rows = answer['body'] if answer['status'] == 200 and isinstance(answer['body'], list) else []
            for row in rows:
                state[kind + ':' + str(row.get('id'))] = bool(row.get('imageAbsent'))
        return state

    def settle_artwork(self, window=8.0, timeout=60.0):
        '''Wait until the background artwork worker has finished after a scan. A song or an album without any image keeps offering a cover id (and image addresses) until the worker has found out that there is none, so the same request answers differently before and after. The absent flags are read until they stay unchanged for a while; a product without the flag only costs the wait.'''
        deadline = time.monotonic() + timeout
        last, since = None, time.monotonic()
        while time.monotonic() < deadline:
            now = self.artwork_state()
            if now != last:
                last, since = now, time.monotonic()
            elif time.monotonic() - since >= window:
                return
            time.sleep(1.0)

    def rescan(self, full=False, timeout=30.0, idle=6.0):
        '''Start one scan and wait until it has finished and the product stays quiet: lastScan has moved on, or a
        running scan was seen and has stopped, or (for a product without lastScan) nothing has run for a while. A
        scan requested while another one runs is dropped, so it is requested again. A product that never reports a
        finished scan keeps what it shows; the checks compare that.'''
        before = self.scan_state()
        for _ in range(3):
            self.reply(self.subsonic('startScan', fullScan='true' if full else 'false'))
            deadline = time.monotonic() + timeout
            seen, since = False, time.monotonic()
            while time.monotonic() < deadline:
                time.sleep(0.7)
                state = self.scan_state()
                if state.get('scanning'):
                    seen, since = True, time.monotonic()
                    continue
                moved = 'lastScan' in state and state.get('lastScan') != before.get('lastScan')
                if moved or seen or ('lastScan' not in state and time.monotonic() - since >= idle):
                    time.sleep(2.0)
                    return self.scan_state()
        return self.scan_state()

    def library_files(self):
        if self.files is None:
            self.files = library.materialize()
        return self.files

    def put_library(self, names=None):
        files = self.library_files()
        for name in sorted(files if names is None else names):
            answer = self.call({'op': 'library_put', 'path': name, 'base64': base64.b64encode(files[name]).decode()})
            assert answer.get('size') == len(files[name]), 'library_put ' + name

    def restart_server(self):
        status = self.call({'op': 'restart'})
        assert status.get('ready'), 'the application did not come back after a restart: ' + str(status.get('detail'))
        self.settle(first=False, quiet=4.0, timeout=30.0)
        return status

    def bootstrap(self, users=('bob', 'carol'), scan=True):
        '''Unscored preparation: the administrator, two ordinary accounts and the scanned fixture library. Any success
        status is accepted; the administrator signs in when the creation answer carries no token.'''
        answer = self.http('POST', '/auth/createAdmin', body={'username': 'admin', 'password': PASSWORDS['admin']})
        assert 200 <= answer['status'] < 300, 'administrator creation: ' + str(answer['status'])
        body = answer.get('body')
        if isinstance(body, dict) and isinstance(body.get('token'), str) and body['token']:
            self.tokens['admin'] = body['token']
        self.settle(timeout=15.0)
        for user in users:
            made = self.native('POST', 'user', body={'userName': user, 'name': NAMES[user], 'email': user + '@example.test',
                                                     'password': PASSWORDS[user], 'isAdmin': False})
            assert 200 <= made['status'] < 300, 'account %s: %s' % (user, made['status'])
        if scan:
            self.put_library()
            if not self.scan_until(TRACKS):
                # Not a setup failure: the scored checks compare what the product lists.
                self.notes.append({'kind': 'bootstrap_scan_unsettled', 'songs': self.song_total()})
            self.settle_artwork()

    # -- observations --------------------------------------------------------------------------------------
    def observe_subsonic(self, answer, fields=None, unordered=()):
        reply = dict(self.reply(answer))
        if isinstance(reply.get('error'), dict):
            reply['error'] = {'code': reply['error'].get('code')}
        if reply.get('status') == 'ok' and fields:
            kept = {}
            for name in fields:
                assert name in reply, 'missing field ' + name
                kept[name] = reply[name]
            reply = {'status': 'ok', **kept}
        cleaned = self.norm.clean(reply)
        for path in unordered:
            normalize.mark_unordered(cleaned, path)
        return {'status': answer['status'], 'reply': cleaned}

    def observe_native(self, answer, fields=None, hint='object'):
        status = answer['status']
        if status >= 400:
            return {'status': status, 'error': True}
        body = answer.get('body')
        if status == 204 or body in ('', None):
            return {'status': status}
        value = normalize.project(body, fields)
        return {'status': status, 'total': answer['headers'].get('x-total-count'), 'body': self.norm.clean(value, hint)}

    @staticmethod
    def image_size(data):
        '''Width and height of a PNG, GIF, JPEG or WebP picture, or None.'''
        if data[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10]) and len(data) >= 24:
            return list(struct.unpack('>II', data[16:24]))
        if data[:6] in (b'GIF87a', b'GIF89a'):
            return list(struct.unpack('<HH', data[6:10]))
        if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            kind = data[12:16]
            if kind == b'VP8X':
                return [int.from_bytes(data[24:27], 'little') + 1, int.from_bytes(data[27:30], 'little') + 1]
            if kind == b'VP8L':
                bits = int.from_bytes(data[21:25], 'little')
                return [(bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1]
            if kind == b'VP8 ':
                return [int.from_bytes(data[26:28], 'little') & 0x3FFF, int.from_bytes(data[28:30], 'little') & 0x3FFF]
        if data[:2] == b'\xff\xd8':
            at = 2
            while at + 9 < len(data) and data[at] == 0xFF:
                marker, length = data[at + 1], int.from_bytes(data[at + 2:at + 4], 'big')
                if marker in (0xC0, 0xC1, 0xC2):
                    return [int.from_bytes(data[at + 7:at + 9], 'big'), int.from_bytes(data[at + 5:at + 7], 'big')]
                at += 2 + length
        return None

    def observe_picture(self, answer):
        '''A picture by its size, for an image the product has resized from a fixture picture.'''
        data = base64.b64decode(answer.get('body_base64') or '')
        kind = (answer['headers'].get('content-type') or '').split(';')[0].strip().lower()
        return {'status': answer['status'], 'content_type': 'image/*' if kind.startswith('image/') else kind, 'size': self.image_size(data)}

    @staticmethod
    def observe_bytes(answer):
        data = base64.b64decode(answer.get('body_base64') or '')
        kind = (answer['headers'].get('content-type') or '').split(';')[0].strip().lower()
        if kind.startswith('image/'):
            # An image is compared by which fixture picture it is; any other picture (a placeholder or an avatar the
            # product draws itself) only has to be an image that is none of them.
            return {'status': answer['status'], 'content_type': 'image/*', 'picture': FIXTURE_PICTURES.get(hashlib.sha256(data).hexdigest())}
        return {'status': answer['status'], 'content_type': kind, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


class Suite:
    def __init__(self):
        self.cases = []
        self.ids = set()

    def add(self, family, scenario, step, action, channel='api', description=''):
        if family.endswith('fixture'):
            channel = 'setup'
        cid = '%s.%s.%s.%s' % (channel, family, scenario, step)
        if cid in self.ids:
            raise ValueError('duplicate ' + cid)
        self.ids.add(cid)
        self.cases.append(Case(cid, family, scenario, channel, description or step, action))
        return cid

    def sub(self, family, scenario, step, op, user='admin', *, expect=None, fields=None, save=None, check=None, http=None, unordered=(), **query):
        '''One OpenSubsonic request. expect is ok, failed or an error code; fields keeps only the named top-level
        members of a successful reply.'''
        def action(c, relaxed=False):
            answer = c.subsonic(op, resolve(user, c), **resolve(query, c))
            if http is not None:
                assert not relaxed, 'status checks are scored cases'
                assert answer['status'] == http, '%s: expected HTTP %s, received %s' % (op, http, answer['status'])
                return {'status': answer['status']}
            reply = c.reply(answer)
            if relaxed:
                assert reply.get('status') == 'ok', 'setup %s: %s' % (op, str(reply)[:200])
                if save:
                    c.state[save] = reply
                return None
            if save and reply.get('status') == 'ok':
                c.state[save] = reply
            if expect is not None:
                got = (reply.get('error') or {}).get('code') if reply.get('status') == 'failed' else 'ok'
                assert got == expect or (expect == 'failed' and reply.get('status') == 'failed'), \
                    '%s: expected %s, received %s' % (op, expect, got)
            if check:
                check(c, answer, reply)
            return c.observe_subsonic(answer, fields, unordered)

        return self.add(family, scenario, step, action,
                        description='subsonic %s as %s' % (op, user if isinstance(user, str) else 'a resolved user'))

    def nat(self, family, scenario, step, method, path, user='admin', *, body=None, params=None, status=None, fields=None,
            save=None, check=None, hint='object', anonymous=False, token=None, raw=None, headers=None,
            content_type=None, multipart=None):
        '''One native API request below /api/ with the account token.'''
        def action(c, relaxed=False):
            answer = c.native(method, resolve(path, c), resolve(user, c), body=resolve(body, c), params=resolve(params, c),
                              anonymous=anonymous, token=resolve(token, c), raw=raw, headers=headers,
                              content_type=content_type, multipart=multipart)
            if relaxed:
                assert 200 <= answer['status'] < 300, 'setup %s %s: status %s' % (method, path, answer['status'])
                if save:
                    c.state[save] = answer['body']
                return None
            if save and answer['status'] < 400:
                c.state[save] = answer['body']
            if status is not None:
                allowed = [status] if isinstance(status, int) else list(status)
                assert answer['status'] in allowed, '%s %s: expected %s, received %s' % (method, path, allowed, answer['status'])
            if check:
                check(c, answer)
            return c.observe_native(answer, fields, hint)

        return self.add(family, scenario, step, action,
                        description='%s %s as %s' % (method, path if isinstance(path, str) else '<relational resource>',
                                                    user if isinstance(user, str) else 'a resolved user'))

    def manifest(self):
        return [dict(id=x.id, family=x.family, scenario=x.scenario, channel=x.channel, scored=x.channel != 'setup',
                     description=x.description) for x in self.cases]
