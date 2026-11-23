'''Several libraries: a second library on a folder of the music library, the music folder filter of the OpenSubsonic
lists, the libraries of an account, the default libraries of new accounts and the removal of a library.

The second library holds the folder Unicode, so its one song is listed once in each library. The creation of the
library is a scored write; every read after it needs that write (and the full scan of the setup step that follows it).
The reads that only show a refusal or an empty result are bound to the positive read of the same operation.'''
from harness import PASSWORDS

PASSWORDS.setdefault('fred', 'Fred-Local-2026!')
PASSWORDS.setdefault('gina', 'Gina-Local-2026!')
PAGE = {'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC'}
NAMES = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
USERS = {'_start': 0, '_end': 50, '_sort': 'userName', '_order': 'ASC'}
LIBRARY = ['name', 'path', 'defaultNewUsers', 'totalSongs', 'totalAlbums', 'totalArtists']
SECOND = {'name': 'Unicode Only', 'path': '/music/Unicode'}
# Each music folder filter: the operation, its parameters and the members compared as sets.
FILTERED = [('getIndexes', {}, ()), ('getArtists', {}, ()), ('getAlbumList2', {'type': 'alphabeticalByName', 'size': 50}, ()),
            ('search3', {'query': 'naive'}, ('searchResult3.song', 'searchResult3.album', 'searchResult3.artist')),
            ('getSongsByGenre', {'genre': 'Ambient'}, ('songsByGenre.song',)),
            ('getRandomSongs', {'size': 50}, ('randomSongs.song',))]
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def library_id(c):
    return str(c.state['library-two']['id'])


def user_id(name):
    def find(c):
        rows = c.native('GET', 'user', params=USERS)['body']
        return next(u['id'] for u in rows if u['userName'] == name)
    return find


def libraries_of(name):
    return lambda c: 'user/%s/library' % user_id(name)(c)


def rescan(c, relaxed=False):
    c.rescan(True)


def account(name, display):
    return {'userName': name, 'name': display, 'email': name + '@example.test', 'password': PASSWORDS[name], 'isAdmin': False}


def build(s):
    nat, sub = s.nat, s.sub
    nat('libraries-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    made = nat('libraries', 'create', 'second', 'POST', 'library', body=SECOND, status=200, save='library-two')
    s.add('libraries-fixture', 'library', 'scan', rescan, description='run a full scan of the libraries')
    listed = need(nat('libraries', 'list', 'both', 'GET', 'library', params={'_start': 0, '_end': 10}, status=200, fields=LIBRARY), made)
    COMPANIONS[made] = [listed]
    folders = need(sub('libraries', 'getMusicFolders', 'both', 'getMusicFolders'), made)

    # -- the music folder filter of each list ---------------------------------------------------------------------------
    for op, query, members in FILTERED:
        first = need(sub('libraries-filter', op, 'folder-1', op, musicFolderId=1, unordered=members, **query), made)
        second = need(sub('libraries-filter', op, 'folder-2', op, musicFolderId=lambda c: library_id(c), unordered=members, **query), made)
        COMPANIONS[need(sub('libraries-filter', op, 'unknown-folder', op, musicFolderId=9, expect=70, **query), made)] = [first, second]
    for step, folder in (('zero-folder', 0), ('text-folder', 'abc')):
        cid = need(sub('libraries-filter', 'getAlbumList2', step, 'getAlbumList2', type='alphabeticalByName', size=50,
                       musicFolderId=folder), made)
        COMPANIONS[cid] = [folders]
    need(sub('libraries-filter', 'getGenres', 'folder-2', 'getGenres', musicFolderId=lambda c: library_id(c),
             unordered=['genres.genre']), made)
    for kind, params, fields in (('song', PAGE, ['title', 'path']), ('album', NAMES, ['name', 'albumArtist'])):
        need(nat('libraries-native', kind, 'library-2', 'GET', kind, params=lambda c, p=params: {**p, 'library_id': library_id(c)},
                 status=200, fields=fields), made)

    # -- the libraries of an account ----------------------------------------------------------------------------------
    assigned = need(nat('libraries-account', 'assign', 'bob-second-only', 'PUT', libraries_of('bob'),
                        body=lambda c: {'libraryIds': [int(library_id(c))]}, status=200, fields=['name', 'path']), made)
    own = need(nat('libraries-account', 'read', 'bob-libraries', 'GET', libraries_of('bob'), status=200, fields=['name', 'path']), assigned)
    COMPANIONS[assigned] = [own]
    need(sub('libraries-account', 'bob', 'folders', 'getMusicFolders', 'bob'), assigned)
    bob_albums = need(sub('libraries-account', 'bob', 'albums', 'getAlbumList2', 'bob', type='alphabeticalByName', size=50), assigned)
    need(sub('libraries-account', 'bob', 'artists', 'getArtists', 'bob'), assigned)
    need(sub('libraries-account', 'bob', 'search', 'search3', 'bob', query='naive',
             unordered=['searchResult3.song', 'searchResult3.album', 'searchResult3.artist']), assigned)
    need(nat('libraries-account', 'bob', 'native-songs', 'GET', 'song', 'bob', params=PAGE, status=200, fields=['title', 'path']), assigned)
    COMPANIONS[need(sub('libraries-account', 'bob', 'other-library-folder', 'getArtists', 'bob', musicFolderId=1, expect=70),
                    assigned)] = [bob_albums]
    COMPANIONS[need(sub('libraries-account', 'bob', 'other-library-song', 'getSong', 'bob',
                        id=lambda c: next(x['id'] for x in c.state['songs'] if x['title'] == 'Opening'), expect=70),
                    assigned)] = [bob_albums]

    # -- the libraries new accounts get ---------------------------------------------------------------------------------
    fred = need(nat('libraries-defaults', 'create', 'fred', 'POST', 'user', body=account('fred', 'Fred'), status=200, hint='user'), made)
    need(nat('libraries-defaults', 'read', 'fred-libraries', 'GET', libraries_of('fred'), status=200, fields=['name', 'path']), fred)
    opened = need(nat('libraries-defaults', 'update', 'second-default', 'PUT', lambda c: 'library/' + library_id(c),
                      body={**SECOND, 'name': 'Unicode Default', 'defaultNewUsers': True}, status=200, fields=LIBRARY), made)
    COMPANIONS[opened] = [need(nat('libraries-defaults', 'read', 'second-after-update', 'GET', lambda c: 'library/' + library_id(c),
                                   status=200, fields=LIBRARY), opened)]
    gina = need(nat('libraries-defaults', 'create', 'gina', 'POST', 'user', body=account('gina', 'Gina'), status=200, hint='user'), opened)
    need(nat('libraries-defaults', 'read', 'gina-libraries', 'GET', libraries_of('gina'), status=200, fields=['name', 'path']), gina)

    # -- removing the second library -------------------------------------------------------------------------------------
    removed = need(nat('libraries', 'delete', 'second', 'DELETE', lambda c: 'library/' + library_id(c), status=200), made)
    after = need(nat('libraries', 'list', 'after-delete', 'GET', 'library', params={'_start': 0, '_end': 10}, status=200, fields=LIBRARY), removed)
    COMPANIONS[removed] = [after]
    COMPANIONS[need(nat('libraries-account', 'read', 'bob-libraries-after-delete', 'GET', libraries_of('bob'), status=200,
                        fields=['name', 'path']), removed, assigned)] = [own]
    COMPANIONS[need(sub('libraries-account', 'bob', 'albums-after-delete', 'getAlbumList2', 'bob', type='alphabeticalByName',
                        size=50), removed, assigned)] = [bob_albums]
    need(nat('libraries', 'songs', 'after-delete', 'GET', 'song', params=PAGE, status=200, fields=['title', 'path']), removed)
