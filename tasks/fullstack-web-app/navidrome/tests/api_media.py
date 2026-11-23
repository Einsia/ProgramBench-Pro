'''Media and administration endpoints: the raw tags of a file, the interface translations, stream parameters the product
answers without a transcoder, zip downloads of albums, artists and playlists, players, and removing missing files.

Downloads are compared by the library files they contain, never by their bytes. Refusals are bound to the positive read
of the same endpoint; each read after a write needs that write.'''
import base64
import hashlib
import io
import json
import zipfile

from api_browse import album_of, artist_of, song_of

PAGE = {'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC'}
ROWS = {'_start': 0, '_end': 20}
PLAYER = ['name', 'client', 'userName', 'scrobbleEnabled', 'reportRealPath', 'maxBitRate']
LOOSE = 'Untagged/loose track.mp3'
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def stream(s, step, title, **query):
    def action(c, relaxed=False):
        assert not relaxed, 'media checks are scored cases'
        answer = c.subsonic('stream', binary=True, fmt=None, id=song_of(title)(c), **query)
        data = base64.b64decode(answer.get('body_base64') or '')
        known = {hashlib.sha256(body).hexdigest(): name for name, body in c.library_files().items()}
        return {'status': answer['status'], 'type': (answer['headers'].get('content-type') or '').split(';')[0],
                'file': known.get(hashlib.sha256(data).hexdigest())}
    return s.add('media', 'stream', step, action, description='subsonic stream of %s with %s' % (title, query))


def archive(s, step, ident):
    def action(c, relaxed=False):
        assert not relaxed, 'media checks are scored cases'
        answer = c.subsonic('download', binary=True, fmt=None, id=ident(c))
        seen = {'status': answer['status']}
        if answer['status'] == 200:
            data = base64.b64decode(answer.get('body_base64') or '')
            known = {hashlib.sha256(body).hexdigest(): name for name, body in c.library_files().items()}
            content = zipfile.ZipFile(io.BytesIO(data))
            seen['entries'] = sorted([info.filename, known.get(hashlib.sha256(content.read(info)).hexdigest())]
                                     for info in content.infolist())
        return seen
    return s.add('media', 'download', step, action, description='subsonic download of the %s as a zip archive' % step)


def inspect_refusals(c, relaxed=False):
    assert not relaxed, 'media checks are scored cases'
    song = song_of('Opening')(c)
    return {'ordinary': c.native('GET', 'inspect', 'bob', params={'id': song})['status'],
            'anonymous': c.native('GET', 'inspect', anonymous=True, params={'id': song})['status'],
            'unknown': c.native('GET', 'inspect', params={'id': 'NoSuchSong'})['status']}


def translations(c, relaxed=False):
    assert not relaxed, 'media checks are scored cases'
    answer = c.native('GET', 'translation', anonymous=True)
    assert answer['status'] == 200 and isinstance(answer['body'], list), 'translation list: HTTP %s' % answer['status']
    return {'languages': sorted([x.get('id'), x.get('name')] for x in answer['body'])}


def translation(language):
    def action(c, relaxed=False):
        assert not relaxed, 'media checks are scored cases'
        answer = c.native('GET', 'translation/' + language, anonymous=True)
        seen = {'status': answer['status']}
        if answer['status'] == 200 and isinstance(answer['body'], dict):
            body = answer['body']
            try:
                data = json.loads(body.get('data') or 'null')
            except ValueError:
                data = None
            seen.update(id=body.get('id'), name=body.get('name'), languageName=(data or {}).get('languageName'))
        return seen
    return action


def player(user):
    def find(c):
        rows = c.native('GET', 'player', params=ROWS)['body']
        return next(x['id'] for x in rows if x.get('userName') == user)
    return find


def drop_loose(c, relaxed=False):
    c.call({'op': 'library_delete', 'path': LOOSE})
    c.rescan(False)
    c.state['missing'] = c.native('GET', 'missing', params=ROWS)['body']


def build(s):
    nat, sub = s.nat, s.sub
    nat('media-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    sub('media-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('media-fixture', 'library', 'artists', 'getArtists', save='artists')
    nat('media-fixture', 'library', 'playlists', 'GET', 'playlist', params={'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'},
        save='playlists')

    # -- the raw tags of a file --------------------------------------------------------------------------------------------
    tags = {}
    for title in ('Opening', 'Intro', 'Single A', 'click'):
        tags[title] = nat('media', 'inspect', title.lower().replace(' ', '-'), 'GET', 'inspect', params=lambda c, t=title: {'id': song_of(t)(c)},
                          status=200, fields=['file', 'rawTags'])
    COMPANIONS[s.add('media', 'inspect', 'refusals', inspect_refusals,
                     description='GET inspect as an ordinary account, without a token and for an unknown song')] = [tags['Opening']]

    # -- the interface translations ------------------------------------------------------------------------------------------
    languages = s.add('media', 'translation', 'list', translations, description='GET translation: the languages offered')
    s.add('media', 'translation', 'german', translation('de'), description='GET translation/de')
    COMPANIONS[s.add('media', 'translation', 'unknown', translation('xx'), description='GET translation/xx')] = [languages]

    # -- stream parameters without a transcoder, and zip downloads -----------------------------------------------------------
    stream(s, 'raw-format', 'Middle', format='raw')
    stream(s, 'bitrate-limit', 'Middle', maxBitRate=64)
    archive(s, 'album', album_of('First Album', 'Alpha Artist'))
    archive(s, 'artist', artist_of('Beta Band'))
    archive(s, 'playlist', lambda c: next(p['id'] for p in c.state['playlists'] if p['name'] == 'Favourites'))

    # -- players: each account sees its own, and the owner edits one ----------------------------------------------------------
    sub('media-fixture', 'players', 'bob-client', 'ping', 'bob')
    listed = nat('media', 'player', 'list-admin', 'GET', 'player', params=ROWS, status=200, fields=PLAYER)
    nat('media', 'player', 'list-bob', 'GET', 'player', 'bob', params=ROWS, status=200, fields=PLAYER)
    edited = nat('media', 'player', 'edit', 'PUT', lambda c: 'player/' + player('admin')(c),
                 body=lambda c: {**next(x for x in c.native('GET', 'player', params=ROWS)['body'] if x.get('userName') == 'admin'),
                                 'name': 'Kitchen', 'maxBitRate': 128, 'scrobbleEnabled': False, 'reportRealPath': True},
                 status=200, fields=PLAYER)
    after = need(nat('media', 'player', 'after-edit', 'GET', lambda c: 'player/' + player('admin')(c), status=200, fields=PLAYER), edited)
    COMPANIONS[edited] = [after]
    COMPANIONS[nat('media', 'player', 'edit-by-bob', 'PUT', lambda c: 'player/' + player('admin')(c), 'bob',
                   body={'name': 'Hijack'}, status=403)] = [after]
    COMPANIONS[nat('media', 'player', 'read-by-bob', 'GET', lambda c: 'player/' + player('admin')(c), 'bob', status=404)] = [listed]

    # -- removing a missing file ------------------------------------------------------------------------------------------------
    s.add('media-fixture', 'missing', 'delete-file', drop_loose, description='delete a song file and run a quick scan')
    missing = nat('media', 'missing', 'listed', 'GET', 'missing', params=ROWS, status=200, fields=['title', 'path'])
    removed = nat('media', 'missing', 'remove', 'DELETE', 'missing', params=lambda c: {'id': c.state['missing'][0]['id']}, status=200)
    after_missing = need(nat('media', 'missing', 'after-remove', 'GET', 'missing', params=ROWS, status=200, fields=['title', 'path']), removed)
    COMPANIONS[removed] = [after_missing]
    COMPANIONS[after_missing] = [missing]
    need(nat('media', 'missing', 'songs-after-remove', 'GET', 'song', params=PAGE, status=200, fields=['title', 'missing']), removed)
