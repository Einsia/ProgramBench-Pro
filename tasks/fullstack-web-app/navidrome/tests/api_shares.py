'''Public share addresses and share options: the share page, its playlist export, the audio and download addresses of a
share, unknown and expired shares, visit counts, and editing a share through the native API.

The shares are made by scored writes; each later case needs the write that made its share. Share identities and the
signed audio addresses are random tokens, so observations keep their role, never their value. Refusals are bound to the
positive read of the same address.'''
import base64
import hashlib
import io
import re
import zipfile

from api_browse import album_of, song_of

PAGE = {'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC'}
ROWS = {'_start': 0, '_end': 20}
TOKEN = re.compile(r'/share/s/[A-Za-z0-9._-]+')
NATIVE = ['description', 'downloadable', 'expiresAt', 'resourceType', 'contents', 'username']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def share(description):
    # The share with this description, found when the request is made.
    def find(c):
        rows = c.native('GET', 'share', params=ROWS)['body']
        return next(x['id'] for x in rows if x.get('description') == description)
    return find


def fixture_files(c):
    return {hashlib.sha256(data).hexdigest(): name for name, data in c.library_files().items()}


def fetch(c, path):
    answer = c.http('GET', path, binary=True)
    return answer, base64.b64decode(answer.get('body_base64') or '')


def page(description):
    def action(c, relaxed=False):
        assert not relaxed, 'share checks are scored cases'
        answer, _data = fetch(c, '/share/' + share(description)(c))
        return {'status': answer['status'], 'type': (answer['headers'].get('content-type') or '').split(';')[0]}
    return action


def m3u(description):
    def action(c, relaxed=False):
        assert not relaxed, 'share checks are scored cases'
        answer, data = fetch(c, '/share/%s/m3u' % share(description)(c))
        seen = {'status': answer['status'], 'type': (answer['headers'].get('content-type') or '').split(';')[0]}
        if answer['status'] == 200:
            text = c.norm.text(data.decode('utf-8', 'replace'))
            seen['lines'] = TOKEN.sub('/share/s/@token', text).split(chr(10))
        return seen
    return action


def audio(description):
    '''The audio addresses the playlist export lists: each must answer the bytes of a library file.'''
    def action(c, relaxed=False):
        assert not relaxed, 'share checks are scored cases'
        _answer, data = fetch(c, '/share/%s/m3u' % share(description)(c))
        known = fixture_files(c)
        seen = []
        for path in TOKEN.findall(data.decode('utf-8', 'replace')):
            answer, body = fetch(c, path)
            seen.append({'status': answer['status'], 'file': known.get(hashlib.sha256(body).hexdigest())})
        return {'streams': seen}
    return action


def download(description):
    def action(c, relaxed=False):
        assert not relaxed, 'share checks are scored cases'
        answer, data = fetch(c, '/share/d/' + share(description)(c))
        seen = {'status': answer['status']}
        if answer['status'] == 200:
            known = fixture_files(c)
            archive = zipfile.ZipFile(io.BytesIO(data))
            seen['entries'] = sorted([info.filename, known.get(hashlib.sha256(archive.read(info)).hexdigest())]
                                     for info in archive.infolist())
        return seen
    return action


def unknown(c, relaxed=False):
    assert not relaxed, 'share checks are scored cases'
    return {name: c.http('GET', path)['status'] for name, path in (('page', '/share/NoSuchShare'), ('m3u', '/share/NoSuchShare/m3u'),
                                                                    ('download', '/share/d/NoSuchShare'))}


def expired(description):
    def action(c, relaxed=False):
        assert not relaxed, 'share checks are scored cases'
        ident = share(description)(c)
        return {name: c.http('GET', path % ident)['status'] for name, path in
                (('page', '/share/%s'), ('m3u', '/share/%s/m3u'), ('download', '/share/d/%s'))}
    return action


def shares_view(c, relaxed=False):
    assert not relaxed, 'share checks are scored cases'
    reply = c.reply(c.subsonic('getShares'))
    rows = (reply.get('shares') or {}).get('share') or []
    return {'shares': sorted((c.norm.clean({'description': x.get('description'), 'username': x.get('username'),
                                            'visitCount': x.get('visitCount'), 'expires': x.get('expires'),
                                            'entries': sorted(e.get('title', '') for e in x.get('entry') or [])}, 'share')
                              for x in rows), key=lambda v: str(v.get('description')))}


def build(s):
    nat, sub = s.nat, s.sub
    nat('shares-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    sub('shares-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    third, opening = album_of('Third Album', 'Gamma Trio'), song_of('Opening')

    # -- two shares: an album that may be downloaded and a song that may not ----------------------------------------------
    opened = sub('shares', 'create', 'album-downloadable', 'createShare', id=third, description='Open', downloadable='true', expect='ok',
                 fields=['status'])
    closed = sub('shares', 'create', 'song-not-downloadable', 'createShare', id=opening, description='Closed', downloadable='false',
                 expect='ok', fields=['status'])
    listed = need(s.add('shares', 'list', 'subsonic', shares_view, description='subsonic getShares of both shares'), opened, closed)
    COMPANIONS[opened] = [listed]
    COMPANIONS[closed] = [listed]
    native = need(nat('shares', 'list', 'native', 'GET', 'share', params=ROWS, status=200, fields=NATIVE),
                  opened, closed)

    # -- the public addresses of a share -----------------------------------------------------------------------------------
    shown = need(s.add('shares', 'page', 'album', page('Open'), description='GET /share/<id> of the album share'), opened)
    exported = need(s.add('shares', 'm3u', 'album', m3u('Open'), description='GET /share/<id>/m3u of the album share'), opened)
    need(s.add('shares', 'm3u', 'song', m3u('Closed'), description='GET /share/<id>/m3u of the song share'), closed)
    need(s.add('shares', 'audio', 'album', audio('Open'), description='GET the audio addresses of the album share'), opened)
    zipped = need(s.add('shares', 'download', 'album', download('Open'), description='GET /share/d/<id> of the downloadable share'), opened)
    COMPANIONS[need(s.add('shares', 'download', 'song-refused', download('Closed'), description='GET /share/d/<id> of a share that may not be downloaded'),
                    closed)] = [zipped]
    COMPANIONS[s.add('shares', 'unknown', 'addresses', unknown, description='GET the public addresses of an unknown share')] = [shown, exported]
    need(s.add('shares', 'list', 'visits', shares_view, description='subsonic getShares after the share addresses were visited'), opened, closed)

    # -- editing a share through the native API -------------------------------------------------------------------------------
    edited = need(nat('shares-native', 'update', 'closed', 'PUT', lambda c: 'share/' + share('Closed')(c),
                      body={'description': 'Closed', 'downloadable': True, 'expiresAt': '2099-01-01T00:00:00Z'}, status=200,
                      fields=NATIVE), closed)
    after = need(nat('shares-native', 'read', 'closed-after-update', 'GET', lambda c: 'share/' + share('Closed')(c), status=200,
                     fields=NATIVE), edited)
    COMPANIONS[edited] = [after]
    need(s.add('shares', 'download', 'song-after-update', download('Closed'), description='GET /share/d/<id> after the share became downloadable'),
         edited)
    COMPANIONS[need(nat('shares-native', 'update', 'by-bob', 'PUT', lambda c: 'share/' + share('Open')(c), 'bob',
                        body={'description': 'Hijack'}, status=403), opened)] = [after]
    COMPANIONS[need(nat('shares-native', 'read', 'list-as-bob', 'GET', 'share', 'bob', params=ROWS, status=200), opened)] = [native]

    # -- an expired share answers no more ------------------------------------------------------------------------------------
    ended = need(nat('shares-native', 'update', 'expire-open', 'PUT', lambda c: 'share/' + share('Open')(c),
                     body={'description': 'Open', 'downloadable': True, 'expiresAt': '2001-01-01T00:00:00Z'}, status=200,
                     fields=NATIVE), opened)
    gone = need(s.add('shares', 'expired', 'addresses', expired('Open'), description='GET the public addresses of an expired share'), ended)
    COMPANIONS[gone] = [shown, exported]
    COMPANIONS[ended] = [gone]
