'''Playlists: OpenSubsonic and native playlist lifecycle, ownership and visibility, tracks and the read-only imported playlist.

State that changes is chained with need() to the write that made it; a read that sees several playlists needs every write
that shaped that list. Writes are bound to the read that shows their effect, and the denial and missing-resource points
are bound to a positive point of the same episode.'''
import normalize

PAGE = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
LISTING = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
ROWS = {'_start': 0, '_end': 20}
UNKNOWN = 'C' * 22
NATIVE = ['name', 'comment', 'songCount', 'public', 'ownerName']
TRACK = ['mediaFileId', 'playlistId', 'title', 'album', 'artist']
SUMMARY = ['name', 'songCount', 'sync']
LIST = ['playlists.playlist']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def song(title):
    return lambda c: next(x['id'] for x in c.state['songs'] if x['title'] == title)


def songs(*titles):
    return lambda c: [song(t)(c) for t in titles]


def owned(key):
    return lambda c: c.state[key]['playlist']['id']


def imported(c):
    return next(p['id'] for p in c.state['playlists'] if p['name'] == 'Favourites')


def imported_tracks(c):
    return 'playlist/%s/tracks' % imported(c)


def native(key):
    return lambda c: 'playlist/' + c.state[key]['id']


def native_tracks(key):
    return lambda c: 'playlist/%s/tracks' % c.state[key]['id']


def named(s, step, user, names):
    '''The native playlist list as user sees it, kept to the playlists named: what the others do in this episode does
    not change it.'''
    def action(c, relaxed=False):
        assert not relaxed, 'playlist checks are scored cases'
        answer = c.native('GET', 'playlist', user, params=LISTING)
        assert answer['status'] == 200 and isinstance(answer['body'], list), 'playlist list: HTTP %s' % answer['status']
        rows = [x for x in answer['body'] if x.get('name') in names]
        return {'status': 200, 'rows': c.norm.clean(sorted(normalize.project(rows, SUMMARY), key=lambda x: str(x.get('name'))), 'playlist')}
    return s.add('playlists', 'list', step, action, description='GET playlist as %s, the playlists %s' % (user, ', '.join(names)))


def positions(s, step, key):
    '''The songs of a native playlist in playlist order: the product numbers the tracks by position (their id), and a
    move or a removal renumbers them, so the titles are kept in the order of those numbers.'''
    def action(c, relaxed=False):
        assert not relaxed, 'playlist checks are scored cases'
        answer = c.native('GET', native_tracks(key)(c), params=ROWS)
        assert answer['status'] == 200 and isinstance(answer['body'], list), 'tracks: status %s' % answer['status']
        rows = sorted(answer['body'], key=lambda x: int(x['id']))
        return {'status': 200, 'titles': [c.norm.clean({'title': x.get('title')}, 'song') for x in rows]}
    return s.add('playlists', 'tracks', step, action, description='native playlist songs in playlist order ' + step)


def build(s):
    nat, sub = s.nat, s.sub
    nat('playlists-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    nat('playlists-fixture', 'library', 'playlists', 'GET', 'playlist', params=LISTING, save='playlists')

    # -- OpenSubsonic: the imported playlist, creating and reading ----------------------------------------------
    sub('playlists', 'getPlaylists', 'initial', 'getPlaylists', unordered=LIST)
    imported_read = sub('playlists', 'getPlaylist', 'imported', 'getPlaylist', id=imported)
    for step, query, code in (('none', {}, 10), ('empty', {'id': ''}, 10)):
        COMPANIONS[sub('playlists', 'getPlaylist', step, 'getPlaylist', expect=code, **query)] = [imported_read]
    created = sub('playlists', 'createPlaylist', 'named', 'createPlaylist', name='Draft', songId=songs('Opening', 'Echo'), save='draft')
    read = need(sub('playlists', 'getPlaylist', 'created', 'getPlaylist', id=owned('draft')), created)
    COMPANIONS[created] = [read]
    COMPANIONS[sub('playlists', 'createPlaylist', 'without-name', 'createPlaylist', expect=0)] = [read]
    need(sub('playlists', 'getPlaylists', 'with-draft', 'getPlaylists', unordered=LIST), created)
    COMPANIONS[sub('playlists', 'getPlaylist', 'unknown', 'getPlaylist', id=UNKNOWN, expect=70)] = [read]
    COMPANIONS[need(sub('playlists', 'createPlaylist', 'replace-private-by-bob', 'createPlaylist', 'bob', playlistId=owned('draft'), songId=songs('Opening'), expect=70), created)] = [read]

    # -- OpenSubsonic: editing -----------------------------------------------------------------------------------
    COMPANIONS[need(sub('playlists', 'updatePlaylist', 'unknown', 'updatePlaylist', playlistId=UNKNOWN, name='Nothing', expect=70), created)] = [read]
    added = need(sub('playlists', 'updatePlaylist', 'add-songs', 'updatePlaylist', playlistId=owned('draft'), songIdToAdd=songs('Intro', 'Echo')), created)
    COMPANIONS[added] = [need(sub('playlists', 'getPlaylist', 'after-add', 'getPlaylist', id=owned('draft')), added)]
    removed = need(sub('playlists', 'updatePlaylist', 'remove-first', 'updatePlaylist', playlistId=owned('draft'), songIndexToRemove=[0]), added)
    after_remove = need(sub('playlists', 'getPlaylist', 'after-remove', 'getPlaylist', id=owned('draft')), removed)
    COMPANIONS[removed] = [after_remove]
    COMPANIONS[need(sub('playlists', 'updatePlaylist', 'remove-missing-index', 'updatePlaylist', playlistId=owned('draft'), songIndexToRemove=[9]), removed)] = [after_remove]
    meta = need(sub('playlists', 'updatePlaylist', 'metadata', 'updatePlaylist', playlistId=owned('draft'), name='Renamed', comment='Notes', public='true'), removed)
    COMPANIONS[meta] = [need(sub('playlists', 'getPlaylist', 'after-metadata', 'getPlaylist', id=owned('draft')), meta)]

    # -- OpenSubsonic: another account ---------------------------------------------------------------------------
    seen = need(sub('playlists', 'getPlaylist', 'public-as-bob', 'getPlaylist', 'bob', id=owned('draft')), meta)
    need(sub('playlists', 'getPlaylists', 'public-as-bob', 'getPlaylists', 'bob', unordered=LIST), meta)
    COMPANIONS[need(sub('playlists', 'updatePlaylist', 'by-bob', 'updatePlaylist', 'bob', playlistId=owned('draft'), name='Hijack', expect=50), meta)] = [seen]
    COMPANIONS[need(sub('playlists', 'deletePlaylist', 'by-bob', 'deletePlaylist', 'bob', id=owned('draft'), expect=50), meta)] = [seen]
    COMPANIONS[need(sub('playlists', 'createPlaylist', 'replace-public-by-bob', 'createPlaylist', 'bob', playlistId=owned('draft'), songId=songs('Opening'), expect=50), meta)] = [seen]

    # -- OpenSubsonic: replacing the songs and deleting ----------------------------------------------------------
    replaced = need(sub('playlists', 'createPlaylist', 'replace', 'createPlaylist', playlistId=owned('draft'), songId=songs('Intro')), meta)
    after_replace = need(sub('playlists', 'getPlaylist', 'after-replace', 'getPlaylist', id=owned('draft')), replaced)
    COMPANIONS[replaced] = [after_replace]
    COMPANIONS[need(sub('playlists', 'createPlaylist', 'replace-unknown', 'createPlaylist', playlistId=UNKNOWN, songId=songs('Opening'), expect=70), replaced)] = [after_replace]
    gone = need(sub('playlists', 'deletePlaylist', 'owner', 'deletePlaylist', id=owned('draft')), replaced)
    after_delete = need(sub('playlists', 'getPlaylists', 'after-delete', 'getPlaylists', unordered=LIST), gone)
    COMPANIONS[gone] = [after_delete]
    COMPANIONS[need(sub('playlists', 'deletePlaylist', 'again', 'deletePlaylist', id=owned('draft'), expect=70), gone)] = [after_delete]
    COMPANIONS[need(sub('playlists', 'getPlaylist', 'deleted', 'getPlaylist', id=owned('draft'), expect=70), gone)] = [after_delete]
    for step, query, code in (('none', {}, 10), ('empty', {'id': ''}, 10)):
        COMPANIONS[sub('playlists', 'deletePlaylist', step, 'deletePlaylist', expect=code, **query)] = [after_delete]

    # -- the playlist imported from a file is read-only ------------------------------------------------------------
    listing = named(s, 'imported-native', 'admin', ('Favourites',))
    COMPANIONS[nat('playlists', 'imported', 'native-add', 'POST', imported_tracks, body={'ids': songs('Opening')}, status=409)] = [listing]
    COMPANIONS[sub('playlists', 'imported', 'subsonic-add', 'updatePlaylist', playlistId=imported, songIdToAdd=songs('Opening'), expect=50)] = [listing]
    edited = sub('playlists', 'imported', 'subsonic-comment', 'updatePlaylist', playlistId=imported, comment='Edited')
    need(sub('playlists', 'imported', 'after-comment', 'getPlaylist', id=imported), edited)

    # -- native playlists ------------------------------------------------------------------------------------------
    COMPANIONS[nat('playlists', 'list', 'anonymous', 'GET', 'playlist', anonymous=True, params=LISTING, status=401)] = [listing]
    made = nat('playlists', 'create', 'native', 'POST', 'playlist', body={'name': 'Native', 'comment': 'Kept', 'public': False}, status=200, hint='playlist', save='npl')
    owner = need(nat('playlists', 'read', 'native-owner', 'GET', native('npl'), status=200, fields=NATIVE), made)
    COMPANIONS[need(nat('playlists', 'read', 'native-private-bob', 'GET', native('npl'), 'bob', status=404), made)] = [owner]
    COMPANIONS[need(nat('playlists', 'update', 'native-private-bob', 'PUT', native('npl'), 'bob', body={'name': 'Hijack'}, status=404), made)] = [owner]
    COMPANIONS[made] = [owner]
    filled = need(nat('playlists', 'tracks', 'add', 'POST', native_tracks('npl'), body={'ids': songs('Opening', 'Echo')}, status=200), made)
    COMPANIONS[filled] = [need(nat('playlists', 'tracks', 'list', 'GET', native_tracks('npl'), params=ROWS, status=200, fields=TRACK), filled)]
    need(nat('playlists', 'read', 'native-filled', 'GET', native('npl'), status=200, fields=NATIVE), filled)
    public = need(nat('playlists', 'update', 'make-public', 'PUT', native('npl'), body={'public': True}, status=200, fields=NATIVE), filled)
    shared = need(nat('playlists', 'read', 'native-public-bob', 'GET', native('npl'), 'bob', status=200, fields=NATIVE), public)
    COMPANIONS[public] = [shared]
    need(named(s, 'native-as-bob', 'bob', ('Native', 'Favourites')), public)
    COMPANIONS[need(nat('playlists', 'delete', 'native-by-bob', 'DELETE', native('npl'), 'bob', status=403), public)] = [shared]
    removed_native = need(nat('playlists', 'delete', 'native-owner', 'DELETE', native('npl'), status=200), public)
    deleted_read = need(nat('playlists', 'read', 'native-deleted', 'GET', native('npl'), status=404), removed_native)
    COMPANIONS[deleted_read] = [owner]
    COMPANIONS[removed_native] = [deleted_read]
    COMPANIONS[need(nat('playlists', 'delete', 'native-again', 'DELETE', native('npl'), status=404), removed_native)] = [deleted_read]

    # -- the songs of a native playlist: one song, moving, removing, and the playlists of a song ------------------------
    nat('playlists-fixture', 'tracks', 'ordered-playlist', 'POST', 'playlist', body={'name': 'Ordered', 'comment': '', 'public': False},
        save='ordered')
    ordered_tracks = native_tracks('ordered')
    nat('playlists-fixture', 'tracks', 'ordered-songs', 'POST', ordered_tracks, body={'ids': songs('Opening', 'Echo', 'Intro', 'Drift')})
    position = nat('playlists', 'track', 'by-position', 'GET', lambda c: native_tracks('ordered')(c) + '/2', status=200, fields=TRACK)
    COMPANIONS[nat('playlists', 'track', 'unknown-position', 'GET', lambda c: native_tracks('ordered')(c) + '/9', status=404)] = [position]
    moved = nat('playlists', 'tracks', 'move-first-before-third', 'PUT', lambda c: native_tracks('ordered')(c) + '/1',
                body={'insert_before': '3'}, status=200)
    after_move = need(positions(s, 'after-move', 'ordered'), moved)
    COMPANIONS[moved] = [after_move]
    COMPANIONS[nat('playlists', 'tracks', 'move-unknown-position', 'PUT', lambda c: native_tracks('ordered')(c) + '/9',
                   body={'insert_before': '1'}, status=404)] = [after_move]
    cut = need(nat('playlists', 'tracks', 'remove-two', 'DELETE', ordered_tracks, params={'id': ['1', '2']}, status=200), moved)
    after_cut = need(positions(s, 'after-remove', 'ordered'), cut)
    COMPANIONS[cut] = [after_cut]
    COMPANIONS[nat('playlists', 'tracks', 'remove-by-bob', 'DELETE', ordered_tracks, 'bob', params={'id': '1'}, status=404)] = [after_cut]
    nat('playlists', 'song', 'playlists-of-song', 'GET', lambda c: 'song/%s/playlists' % song('Drift')(c), status=200,
        fields=['name', 'songCount', 'public'], hint='playlist')
