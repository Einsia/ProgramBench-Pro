'''Accounts: sign-in, the native user collection and its authorization, user libraries and the OpenSubsonic user endpoints.

Every edit sends the complete user object: the product clears the fields a partial update leaves out. Account state that
changes is chained with need(), and the password change comes last because it retires the old password and token.'''
import hashlib
import json

from harness import PASSWORDS

PASSWORDS.setdefault('dave', 'Dave-Local-2026!')
PASSWORDS.setdefault('david', PASSWORDS['dave'])
OLD = 'Bob-Local-2026!'
NEW = 'Bob-New-2026!'
UNKNOWN = 'B' * 22
FIELDS = ['userName', 'name', 'email', 'isAdmin']
FILTER = FIELDS + ['scrobbleFilter']
PAGE = {'_start': 0, '_end': 50, '_sort': 'userName', '_order': 'ASC'}
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def uid(name):
    return lambda c: next(u['id'] for u in c.state['users'] if u['userName'] == name)


def at(name):
    return lambda c: 'user/' + uid(name)(c)


def made(key):
    return lambda c: 'user/' + c.state[key]['id']


def library_of(name):
    return lambda c: 'user/%s/library' % uid(name)(c)


def full(user, name, email, admin=False, **more):
    return {'userName': user, 'name': name, 'email': email, 'isAdmin': admin, **more}


def sign_in(s, step, user, password, expect, companion=None):
    def action(c, relaxed=False):
        assert not relaxed, 'sign-in checks are scored cases'
        answer = c.login(user, password)
        assert answer['status'] == expect, 'sign-in answered %s, expected %s' % (answer['status'], expect)
        if expect != 200:
            return {'status': answer['status']}
        body = answer['body']
        return {'status': 200, 'user': c.norm.clean({k: body[k] for k in ('id', 'isAdmin', 'name', 'username')}, 'user')}
    cid = s.add('users-auth', 'sign-in', step, action, description='sign in as ' + user)
    if companion:
        COMPANIONS[cid] = [companion]
    return cid


def second_admin(s, companion):
    def action(c, relaxed=False):
        assert not relaxed, 'account checks are scored cases'
        answer = c.http('POST', '/auth/createAdmin', body={'username': 'other', 'password': 'Other-Local-2026!'})
        assert answer['status'] == 403, 'a second first administrator answered %s' % answer['status']
        return {'status': 403}
    cid = s.add('users-auth', 'first-run', 'second-admin', action, description='create a second first administrator')
    COMPANIONS[cid] = [companion]


def change_password(c, relaxed=False):
    assert not relaxed, 'password checks are scored cases'
    c.state['bob-old-token'] = c.token('bob')
    answer = c.native('PUT', 'user/' + uid('bob')(c), 'bob',
                      body=full('bob', 'Bobby', 'bobby@example.test', password=NEW, currentPassword=OLD))
    assert answer['status'] == 200, 'password change answered %s' % answer['status']
    PASSWORDS['bob'] = NEW
    c.forget_token('bob')
    return c.observe_native(answer, FIELDS, 'user')


def build(s):
    nat, sub = s.nat, s.sub
    nat('users-fixture', 'accounts', 'list', 'GET', 'user', params=PAGE, save='users')

    # -- sign-in and the first administrator --------------------------------------------------------------
    listed = nat('users', 'list', 'admin', 'GET', 'user', params=PAGE, status=200, fields=FIELDS)
    ok = sign_in(s, 'bob', 'bob', OLD, 200)
    sign_in(s, 'carol', 'carol', 'Carol-Local-2026!', 200)
    for step, user, password in (('wrong-password', 'bob', 'Wrong-Password-2026!'), ('unknown-user', 'nobody', 'Whatever-2026!')):
        sign_in(s, step, user, password, 401, ok)
    second_admin(s, listed)

    # -- the user collection -----------------------------------------------------------------------------
    for step, params in (('first', {'_start': 0, '_end': 1}), ('second', {'_start': 1, '_end': 2}),
                         ('past-end', {'_start': 5, '_end': 9}), ('descending', {'_order': 'DESC'})):
        cid = nat('users', 'page', step, 'GET', 'user', params={**PAGE, **params}, status=200, fields=FIELDS)
        if step == 'past-end':
            COMPANIONS[cid] = [listed]
    COMPANIONS[nat('users', 'list', 'bob', 'GET', 'user', 'bob', params=PAGE, status=403)] = [listed]
    COMPANIONS[nat('users', 'list', 'anonymous', 'GET', 'user', anonymous=True, params=PAGE, status=401)] = [listed]
    reads = {}
    for name in ('bob', 'carol'):
        reads[name] = nat('users', 'read', 'self-' + name, 'GET', at(name), name, status=200, fields=FIELDS)
    COMPANIONS[nat('users', 'read', 'bob-reads-admin', 'GET', at('admin'), 'bob', status=403)] = [reads['bob']]
    COMPANIONS[nat('users', 'read', 'bob-reads-carol', 'GET', at('carol'), 'bob', status=403)] = [reads['bob']]
    nat('users', 'read', 'admin-reads-bob', 'GET', at('bob'), status=200, fields=FIELDS)
    COMPANIONS[nat('users', 'read', 'unknown-id', 'GET', 'user/' + UNKNOWN, status=404)] = [reads['bob']]

    # -- OpenSubsonic: credentials and the user endpoints -----------------------------------------------------
    salt = 'pbpsalt01'
    digest = hashlib.md5((OLD + salt).encode()).hexdigest()
    ping = sub('users-auth', 'ping', 'password', 'ping', 'bob')
    sub('users-auth', 'ping', 'hex-password', 'ping', auth=False, u='bob', p='enc:' + OLD.encode().hex())
    sub('users-auth', 'ping', 'salted-token', 'ping', auth=False, u='bob', t=digest, s=salt)
    COMPANIONS[sub('users-auth', 'ping', 'wrong-password', 'ping', 'bob', password='Wrong-Password-2026!', expect=40)] = [ping]
    COMPANIONS[sub('users-auth', 'ping', 'unknown-user', 'ping', 'nobody', password='x', expect=40)] = [ping]
    COMPANIONS[sub('users-auth', 'ping', 'bad-token', 'ping', auth=False, u='bob', t='0' * 32, s=salt, expect=40)] = [ping]
    COMPANIONS[sub('users-auth', 'ping', 'no-credentials', 'ping', auth=False, expect=10)] = [ping]
    mine = sub('users', 'getUser', 'self', 'getUser', 'bob', username='bob')
    sub('users', 'getUser', 'admin-self', 'getUser', 'admin', username='admin')
    COMPANIONS[sub('users', 'getUser', 'bob-views-admin', 'getUser', 'bob', username='admin', expect=50)] = [mine]
    COMPANIONS[sub('users', 'getUser', 'admin-views-bob', 'getUser', 'admin', username='bob', expect=50)] = [mine]
    everyone = sub('users', 'getUsers', 'admin', 'getUsers', unordered=['users.user'])
    COMPANIONS[sub('users', 'getUsers', 'bob', 'getUsers', 'bob', expect=50)] = [everyone]

    # -- creating accounts -----------------------------------------------------------------------------------
    pw = PASSWORDS['dave']
    created = nat('users', 'create', 'dave', 'POST', 'user', body=full('dave', 'Dave', 'dave@example.test', password=pw),
                  status=200, hint='user', save='dave')
    for step, name in (('same-name', 'dave'), ('other-case', 'DAVE')):
        COMPANIONS[need(nat('users', 'create', 'duplicate-' + step, 'POST', 'user',
                            body=full(name, 'Other', 'other@example.test', password=pw), status=400), created)] = [created]
    for step, name in (('bob', 'bob'), ('carol-case', 'Carol')):
        COMPANIONS[nat('users', 'create', 'duplicate-' + step, 'POST', 'user',
                       body=full(name, 'Other', 'other@example.test', password=pw), status=400)] = [created]
    COMPANIONS[nat('users', 'create', 'by-bob', 'POST', 'user', 'bob',
                   body=full('mallory', 'Mallory', 'mallory@example.test', password=pw), status=403)] = [created]
    COMPANIONS[nat('users', 'create', 'anonymous', 'POST', 'user', anonymous=True,
                   body=full('mallory', 'Mallory', 'mallory@example.test', password=pw), status=401)] = [created]
    need(nat('users', 'read', 'dave', 'GET', made('dave'), status=200, fields=FIELDS), created)
    need(nat('users', 'list', 'with-dave', 'GET', 'user', params=PAGE, status=200, fields=FIELDS), created)
    need(sub('users-auth', 'ping', 'new-account', 'ping', 'dave'), created)

    # -- an administrator edits an account ---------------------------------------------------------------------
    edit = need(nat('users', 'update', 'admin-edits-dave', 'PUT', made('dave'),
                    body=full('dave', 'David Example', 'david@example.test'), status=200, fields=FIELDS), created)
    need(nat('users', 'read', 'after-edit', 'GET', made('dave'), status=200, fields=FIELDS), edit)
    rename = need(nat('users', 'update', 'admin-renames-dave', 'PUT', made('dave'),
                      body=full('david', 'David Example', 'david@example.test'), status=200, fields=FIELDS), edit)
    need(sub('users-auth', 'ping', 'renamed-account', 'ping', 'david'), rename)
    COMPANIONS[need(sub('users-auth', 'ping', 'old-name', 'ping', 'dave', expect=40), rename)] = [ping]
    COMPANIONS[need(nat('users', 'update', 'rename-taken', 'PUT', made('dave'),
                        body=full('carol', 'David Example', 'david@example.test'), status=400), rename)] = [rename]
    promote = need(nat('users', 'update', 'promote-dave', 'PUT', made('dave'),
                       body=full('david', 'David Example', 'david@example.test', True), status=200, fields=FIELDS), rename)
    need(nat('users', 'read', 'promoted', 'GET', made('dave'), status=200, fields=FIELDS), promote)
    need(sub('users', 'getUsers', 'as-promoted', 'getUsers', 'david', unordered=['users.user']), promote)
    demote = need(nat('users', 'update', 'demote-dave', 'PUT', made('dave'),
                      body=full('david', 'David Example', 'david@example.test', False), status=200, fields=FIELDS), promote)
    COMPANIONS[need(sub('users', 'getUsers', 'as-demoted', 'getUsers', 'david', expect=50), demote)] = [everyone]

    # -- an account edits itself -----------------------------------------------------------------------------
    own = nat('users', 'update', 'bob-edits-self', 'PUT', at('bob'), 'bob', body=full('bob', 'Bobby', 'bobby@example.test'),
              status=200, fields=FIELDS)
    need(nat('users', 'read', 'bob-after-edit', 'GET', at('bob'), status=200, fields=FIELDS), own)
    promote_self = need(nat('users', 'update', 'bob-promotes-self', 'PUT', at('bob'), 'bob',
                            body=full('bob', 'Bobby', 'bobby@example.test', True), status=200, fields=FIELDS), own)
    rename_self = need(nat('users', 'update', 'bob-renames-self', 'PUT', at('bob'), 'bob',
                           body=full('bobby', 'Bobby', 'bobby@example.test'), status=200, fields=FIELDS), promote_self)
    need(nat('users', 'read', 'bob-after-attempts', 'GET', at('bob'), status=200, fields=FIELDS), rename_self)
    COMPANIONS[nat('users', 'update', 'bob-edits-carol', 'PUT', at('carol'), 'bob',
                   body=full('carol', 'Carol', 'carol@example.test'), status=403)] = [reads['carol']]
    COMPANIONS[nat('users', 'update', 'anonymous', 'PUT', at('carol'), anonymous=True,
                   body=full('carol', 'Carol', 'carol@example.test'), status=401)] = [reads['carol']]

    # -- the scrobble filter of an account ------------------------------------------------------------------------
    carol = full('carol', 'Carol', 'carol@example.test')
    rule = json.dumps({'all': [{'is': {'title': 'Opening'}}]})
    accepted = nat('users', 'filter', 'valid', 'PUT', at('carol'), body={**carol, 'scrobbleFilter': rule}, status=200,
                   fields=FILTER)
    need(nat('users', 'filter', 'stored', 'GET', at('carol'), status=200, fields=FILTER), accepted)
    for step, text in (('not-json', 'not json'), ('with-limit', json.dumps({'all': [{'is': {'title': 'x'}}], 'limit': 5})),
                       ('unknown-field', json.dumps({'all': [{'is': {'nosuchfield': 'x'}}]}))):
        COMPANIONS[need(nat('users', 'filter', step, 'PUT', at('carol'), body={**carol, 'scrobbleFilter': text}, status=400),
                        accepted)] = [accepted]

    # -- the libraries of an account ---------------------------------------------------------------------------------
    libs = nat('users', 'library', 'read', 'GET', library_of('carol'), status=200, fields=['name', 'path'])
    COMPANIONS[nat('users', 'library', 'bob-reads', 'GET', library_of('carol'), 'bob', status=403)] = [libs]
    COMPANIONS[nat('users', 'library', 'anonymous', 'GET', library_of('carol'), anonymous=True, status=401)] = [libs]
    assigned = nat('users', 'library', 'assign', 'PUT', library_of('carol'), body={'libraryIds': [1]}, status=200,
                   fields=['name', 'path'])
    for step, name, ids in (('unknown-library', 'carol', [9]), ('empty', 'carol', []), ('admin-account', 'admin', [1])):
        COMPANIONS[nat('users', 'library', step, 'PUT', library_of(name), body={'libraryIds': ids}, status=400)] = [assigned]

    # -- deleting an account ----------------------------------------------------------------------------------------------
    COMPANIONS[need(nat('users', 'delete', 'by-bob', 'DELETE', made('dave'), 'bob', status=403), demote)] = [reads['bob']]
    COMPANIONS[need(nat('users', 'delete', 'anonymous', 'DELETE', made('dave'), anonymous=True, status=401), demote)] = [reads['bob']]
    gone = need(nat('users', 'delete', 'dave', 'DELETE', made('dave'), status=200), demote)
    COMPANIONS[need(nat('users', 'delete', 'again', 'DELETE', made('dave'), status=404), gone)] = [reads['bob']]
    COMPANIONS[need(nat('users', 'read', 'deleted', 'GET', made('dave'), status=404), gone)] = [reads['bob']]
    COMPANIONS[need(sub('users-auth', 'ping', 'deleted-account', 'ping', 'david', expect=40), gone)] = [ping]
    need(nat('users', 'list', 'after-delete', 'GET', 'user', params=PAGE, status=200, fields=FIELDS), gone, own)

    # -- passwords (last: the change retires the old password and token) -----------------------------------------------
    body = full('bob', 'Bobby', 'bobby@example.test')
    for step, more in (('missing-current', {'password': NEW}), ('wrong-current', {'password': NEW, 'currentPassword': 'wrong'})):
        COMPANIONS[need(nat('users', 'password', step, 'PUT', at('bob'), 'bob', body={**body, **more}, status=400),
                        own)] = [reads['bob']]
    changed = need(s.add('users', 'password', 'change', change_password, description='PUT a new password for the signed-in account'), own)
    fresh = need(sign_in(s, 'new-password', 'bob', NEW, 200), changed)
    need(sign_in(s, 'old-password', 'bob', OLD, 401, fresh), changed)
    COMPANIONS[need(nat('users', 'password', 'old-token', 'GET', at('bob'), 'bob', token=lambda c: c.state['bob-old-token'],
                        status=401), changed)] = [fresh]
    need(nat('users', 'password', 'new-token', 'GET', at('bob'), 'bob', status=200, fields=FIELDS), changed)
    need(sub('users-auth', 'ping', 'new-password', 'ping', 'bob'), changed)
    COMPANIONS[need(sub('users-auth', 'ping', 'old-password', 'ping', 'bob', password=OLD, expect=40), changed)] = [ping]
