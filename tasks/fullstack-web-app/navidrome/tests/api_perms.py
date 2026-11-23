'''Access without credentials and with a wrong password.

One authentication layer guards each interface, so its refusals are a few points: every point makes each refused
request and then the same request with valid credentials, so a server that refuses everything, or answers every
operation alike, does not pass it.'''
from api_browse import album_of, artist_of, song_of

PAGE = {'_start': 0, '_end': 20, '_sort': 'id', '_order': 'ASC'}
LISTING = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
UNKNOWN = 'E' * 22
WRONG = 'Wrong-Password-2026!'
READS = ['song', 'album', 'artist', 'genre', 'playlist', 'radio', 'share', 'user', 'library', 'missing', 'scrobble', 'player',
         'transcoding', 'tag']
COMPANIONS = {}
DEPENDS = {}

opening, third, gamma = song_of('Opening'), album_of('Third Album', 'Gamma Trio'), artist_of('Gamma Trio')


def imported(c):
    return next(p['id'] for p in c.state['playlists'] if p['name'] == 'Favourites')


def code(c, answer):
    reply = c.reply(answer)
    return 'ok' if reply.get('status') == 'ok' else (reply.get('error') or {}).get('code')


def station(c, name):
    reply = c.reply(c.subsonic('getInternetRadioStations'))
    rows = (reply.get('internetRadioStations') or {}).get('internetRadioStation') or []
    return next((r['id'] for r in rows if r.get('name') == name), UNKNOWN)


# OpenSubsonic reads with the parameters that make them succeed.
READ_OPS = [
    ('getAlbum', lambda c: {'id': third(c)}), ('getAlbumList', lambda c: {'type': 'alphabeticalByName'}),
    ('getAlbumList2', lambda c: {'type': 'alphabeticalByName'}), ('getArtist', lambda c: {'id': gamma(c)}),
    ('getArtists', lambda c: {}), ('getGenres', lambda c: {}), ('getIndexes', lambda c: {}),
    ('getMusicDirectory', lambda c: {'id': third(c)}), ('getMusicFolders', lambda c: {}), ('getNowPlaying', lambda c: {}),
    ('getPlaylist', lambda c: {'id': imported(c)}), ('getPlaylists', lambda c: {}), ('getPlayQueue', lambda c: {}),
    ('getPlayQueueByIndex', lambda c: {}), ('getRandomSongs', lambda c: {}), ('getSong', lambda c: {'id': opening(c)}),
    ('getSongsByGenre', lambda c: {'genre': 'Rock'}), ('getStarred', lambda c: {}), ('getStarred2', lambda c: {}),
    ('getUser', lambda c: {'username': 'admin'}), ('getUsers', lambda c: {}), ('getShares', lambda c: {}),
    ('getBookmarks', lambda c: {}), ('getInternetRadioStations', lambda c: {}),
    ('getLyrics', lambda c: {'artist': 'Alpha Artist', 'title': 'Opening'}), ('getLyricsBySongId', lambda c: {'id': opening(c)}),
    ('getTopSongs', lambda c: {'artist': 'Alpha Artist'}), ('getSimilarSongs', lambda c: {'id': opening(c)}),
    ('getSimilarSongs2', lambda c: {'id': opening(c)}), ('getAlbumInfo', lambda c: {'id': third(c)}),
    ('getAlbumInfo2', lambda c: {'id': third(c)}), ('getArtistInfo', lambda c: {'id': gamma(c)}),
    ('getArtistInfo2', lambda c: {'id': gamma(c)}), ('search3', lambda c: {'query': 'first'}),
]
# OpenSubsonic writes in an order in which each succeeds; saved values carry identities to the later ones.
WRITE_OPS = [
    ('star', lambda c: {'id': opening(c)}), ('unstar', lambda c: {'id': opening(c)}),
    ('setRating', lambda c: {'id': opening(c), 'rating': 3}), ('scrobble', lambda c: {'id': opening(c)}),
    ('createPlaylist', lambda c: {'name': 'Guarded'}),
    ('updatePlaylist', lambda c: {'playlistId': c.state.get('perms-playlist', UNKNOWN), 'name': 'Guarded 2'}),
    ('deletePlaylist', lambda c: {'id': c.state.get('perms-playlist', UNKNOWN)}),
    ('createShare', lambda c: {'id': third(c)}),
    ('updateShare', lambda c: {'id': c.state.get('perms-share', UNKNOWN), 'description': 'Guarded'}),
    ('deleteShare', lambda c: {'id': c.state.get('perms-share', UNKNOWN)}),
    ('createBookmark', lambda c: {'id': opening(c), 'position': 10}), ('deleteBookmark', lambda c: {'id': opening(c)}),
    ('savePlayQueue', lambda c: {'id': opening(c)}), ('savePlayQueueByIndex', lambda c: {'id': opening(c), 'currentIndex': 0}),
    ('startScan', lambda c: {}),
    ('createInternetRadioStation', lambda c: {'streamUrl': 'http://stream.example.test/guarded', 'name': 'Guarded FM'}),
    ('updateInternetRadioStation', lambda c: {'id': station(c, 'Guarded FM'), 'streamUrl': 'http://stream.example.test/g2',
                                              'name': 'Guarded FM 2'}),
    ('deleteInternetRadioStation', lambda c: {'id': station(c, 'Guarded FM 2')}),
    ('reportPlayback', lambda c: {'mediaId': opening(c), 'mediaType': 'song', 'positionMs': 0, 'state': 'playing'}),
]
# Few wrong passwords: the product refuses even the right password for a while after five failed attempts.
WRONG_OPS = [
    ('getAlbumList2', lambda c: {'type': 'alphabeticalByName'}), ('search3', lambda c: {'query': 'first'}),
    ('star', lambda c: {'id': opening(c)}),
]


def remember(c, op, answer):
    reply = c.reply(answer)
    if op == 'createPlaylist' and isinstance(reply.get('playlist'), dict):
        c.state['perms-playlist'] = reply['playlist'].get('id')
    if op == 'createShare':
        shares = (reply.get('shares') or {}).get('share') or []
        if shares:
            c.state['perms-share'] = shares[0].get('id')


def subsonic_pairs(ops, refused):
    '''Each operation first as refused (anonymous or with a wrong password), then with valid credentials.'''
    def action(c, relaxed=False):
        assert not relaxed, 'access checks are scored cases'
        seen = {}
        for op, params in ops:
            query = params(c)
            if refused == 'anonymous':
                denied = code(c, c.subsonic(op, auth=False, **query))
                answer = c.subsonic(op, **query)
            else:
                denied = code(c, c.subsonic(op, 'bob', password=WRONG, **query))
                answer = c.subsonic(op, 'bob', **query)
            remember(c, op, answer)
            seen[op] = {'refused': denied, 'allowed': code(c, answer)}
        return seen
    return action


def native_reads(c, relaxed=False):
    assert not relaxed, 'access checks are scored cases'
    seen = {}
    for name in READS:
        denied = c.native('GET', name, anonymous=True, params=PAGE)['status']
        seen[name] = {'refused': denied, 'allowed': c.native('GET', name, params=PAGE)['status']}
    return seen


def native_writes(c, relaxed=False):
    assert not relaxed, 'access checks are scored cases'
    album = third(c)
    created = {}

    def target(kind):
        return kind + '/' + created.get(kind, UNKNOWN)
    writes = [
        ('create-playlist', 'POST', lambda: 'playlist', {'name': 'Guarded'}),
        ('rename-playlist', 'PUT', lambda: target('playlist'), {'name': 'Guarded 2'}),
        ('create-radio', 'POST', lambda: 'radio', {'name': 'Guarded FM', 'streamUrl': 'http://stream.example.test/guarded'}),
        ('create-share', 'POST', lambda: 'share', {'resourceType': 'album', 'resourceIds': album}),
        ('create-user', 'POST', lambda: 'user', {'userName': 'mallory', 'name': 'Mallory', 'email': 'mallory@example.test',
                                                 'password': 'Mallory-Local-2026!', 'isAdmin': False}),
        ('create-library', 'POST', lambda: 'library', {'name': 'Guarded', 'path': '/music'}),
        ('delete-radio', 'DELETE', lambda: target('radio'), None),
        ('delete-playlist', 'DELETE', lambda: target('playlist'), None),
    ]
    seen = {}
    for name, method, path, body in writes:
        denied = c.native(method, path(), anonymous=True, body=body)['status']
        answer = c.native(method, path(), body=body)
        if method == 'POST' and answer['status'] < 300 and isinstance(answer['body'], dict) and answer['body'].get('id'):
            created[path()] = str(answer['body']['id'])
        seen[name] = {'refused': denied, 'allowed': answer['status']}
    return seen


def lockout(c, relaxed=False):
    '''Repeated wrong passwords: the right one is refused for a while after the fifth failed attempt.'''
    assert not relaxed, 'access checks are scored cases'
    seen = [code(c, c.subsonic('ping', 'carol'))]
    seen += [code(c, c.subsonic('ping', 'carol', password=WRONG)) for _ in range(5)]
    return {'codes': seen + [code(c, c.subsonic('ping', 'carol'))]}


def build(s):
    nat = s.nat
    nat('perms-fixture', 'library', 'songs', 'GET', 'song', params={**PAGE, '_sort': 'title'}, save='songs')
    s.sub('perms-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    s.sub('perms-fixture', 'library', 'artists', 'getArtists', save='artists')
    nat('perms-fixture', 'library', 'playlists', 'GET', 'playlist', params=LISTING, save='playlists')
    s.add('perms-native', 'anonymous', 'reads', native_reads,
          description='native collections refuse an anonymous read and answer the same read with a token')
    s.add('perms-native', 'anonymous', 'writes', native_writes,
          description='native writes refuse an anonymous request and accept (or check) the same request with a token')
    s.add('perms-subsonic', 'anonymous', 'reads', subsonic_pairs(READ_OPS, 'anonymous'),
          description='OpenSubsonic reads refuse a request without credentials and answer it with credentials')
    s.add('perms-subsonic', 'anonymous', 'writes', subsonic_pairs(WRITE_OPS, 'anonymous'),
          description='OpenSubsonic writes refuse a request without credentials and perform it with credentials')
    s.add('perms-subsonic', 'wrong-password', 'operations', subsonic_pairs(WRONG_OPS, 'wrong'),
          description='OpenSubsonic operations refuse a wrong password and answer the right one')
    s.add('perms-subsonic', 'wrong-password', 'lockout', lockout,
          description='OpenSubsonic refuses even the right password after repeated wrong ones')
