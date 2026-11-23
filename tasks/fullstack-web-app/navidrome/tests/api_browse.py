'''Browsing, listings, search and media retrieval on the fixture library: OpenSubsonic endpoints and the native
song, album, artist, genre and library collections. Read-only checks; the fixture cases only save identities.'''
import normalize
from harness import resolve

TITLES = ['Opening', 'Middle', 'Closing', 'Intro', 'Drift', 'Reprise', 'Single A', 'Single B', 'Single C', 'Blue Hour',
          'Late Train', 'Echo', 'Naïve Ω', 'loose track', 'click']
ALBUMS = [('First Album', 'Alpha Artist'), ('First Album', 'Delta Duo'), ('Second Album', 'Beta Band'),
          ('Mixtape', 'Various Artists'), ('Third Album', 'Gamma Trio'), ('Café Ω', 'Ünïcode Ärtist'),
          ('[Unknown Album]', '[Unknown Artist]')]
ARTISTS = ['Alpha Artist', 'Beta Band', 'Delta Duo', 'Gamma Trio', 'Ünïcode Ärtist', 'Various Artists', '[Unknown Artist]']
UNKNOWN = 'A' * 22
SONG = ['title', 'album', 'artist', 'albumArtist', 'trackNumber', 'discNumber', 'year', 'date', 'genre', 'suffix', 'codec',
        'size', 'duration', 'bitRate', 'sampleRate', 'channels', 'compilation', 'hasCoverArt', 'path', 'libraryPath',
        'missing']
ALBUM = ['name', 'albumArtist', 'compilation', 'songCount', 'duration', 'size', 'genre', 'minYear', 'maxYear', 'date',
         'discs', 'orderAlbumName', 'orderAlbumArtistName', 'missing']
ARTIST = ['name', 'albumCount', 'songCount', 'size', 'orderArtistName', 'missing', 'stats']
LIBRARY = ['name', 'path', 'defaultNewUsers', 'totalSongs', 'totalAlbums', 'totalArtists', 'totalMissingFiles', 'totalSize',
           'totalDuration']
QUERIES = ['first', 'Alpha', 'alpha artist', 'Ünï', 'cafe', 'café', 'naive', 'NAÏVE', 'ω', 'gamma', 'delta', 'guest',
           'blue', 'late tr', 'single', 'mix', 'band', 'unknown', 'click', 'loose', 'first album', 'a', 'the album', 'zzz']
EMPTY_QUERIES = ('a', 'the album', 'zzz')
# The relevance order of search results is the product's own ranking: results are compared as sets.
SEARCH3 = ['searchResult3.artist', 'searchResult3.album', 'searchResult3.song']
SEARCH2 = ['searchResult2.artist', 'searchResult2.album', 'searchResult2.song']
# Odd size values the album and song lists accept: zero, negative and non-numeric values give the default page.
LIMITS = [('zero', 0), ('negative', -1), ('text', 'abc')]
COMPANIONS = {}
DEPENDS = {}


def slug(text):
    return ''.join(ch.lower() if ch.isascii() and ch.isalnum() else '-' for ch in str(text)).strip('-') or 'empty'


def album_of(title, artist, key='id'):
    return lambda c: next(a[key] for a in c.state['albums']['albumList2']['album']
                          if a['name'] == title and a['artist'] == artist)


def artist_of(name):
    return lambda c: next(a['id'] for i in c.state['artists']['artists']['index'] for a in i['artist'] if a['name'] == name)


def song_of(title, key='id'):
    return lambda c: next(x[key] for x in c.state['songs'] if x['title'] == title)


def prefixed(prefix, finder):
    return lambda c: prefix + finder(c)


def media(c, answer):
    kind = (answer['headers'].get('content-type') or '').split(';')[0]
    if answer['status'] >= 400 or kind in ('application/json', 'application/xml', 'text/xml', 'text/plain'):
        return {'status': answer['status'], 'type': kind}
    return {**c.observe_bytes(answer), 'range': answer['headers'].get('content-range'),
            'ranges': answer['headers'].get('accept-ranges')}


def raw(s, family, scenario, step, op, headers=None, **query):
    def action(c, relaxed=False):
        assert not relaxed, 'media checks are scored cases'
        return media(c, c.subsonic(op, 'admin', binary=True, fmt=None, headers=headers, **resolve(query, c)))
    return s.add(family, scenario, step, action, description='subsonic %s %s' % (op, scenario))


def variants(s, family, scenario, step, op, field, values, unordered=(), **query):
    '''One point for a parameter grid: the reply to each odd value of one parameter (the values fall back to the same
    answer, so they are one behaviour).'''
    def action(c, relaxed=False):
        assert not relaxed, 'browse checks are scored cases'
        return {name: c.observe_subsonic(c.subsonic(op, **{**query, field: value}), None, unordered) for name, value in values}
    return s.add(family, scenario, step, action,
                 description='subsonic %s with %s set to %s' % (op, field, ', '.join(str(v) for _, v in values)))


def paging(s, family, scenario, step, op, group, key, offsets=range(5), offset='offset', label='title', **query):
    '''Consecutive pages: the order inside equal keys (or the relevance order) is not specified, so the pages are
    compared by their sizes and as one collection.'''
    def action(c, relaxed=False):
        assert not relaxed, 'paging checks are scored cases'
        sizes, names = [], []
        for start in offsets:
            reply = c.reply(c.subsonic(op, 'admin', **{offset: start}, **query))
            assert reply.get('status') == 'ok', '%s: %s' % (op, str(reply)[:200])
            items = (reply.get(group) or {}).get(key) or []
            sizes.append(len(items))
            names.extend(c.norm.clean({label: x.get(label)}, key) for x in items)
        return {'sizes': sizes, 'names': normalize.unordered(names)}
    return s.add(family, scenario, step, action, description='subsonic %s consecutive pages' % op)


def build(s):
    sub, nat = s.sub, s.nat
    page = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
    sub('browse-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('browse-fixture', 'library', 'artists', 'getArtists', save='artists')
    nat('browse-fixture', 'library', 'songs', 'GET', 'song', params=page, save='songs')

    # -- OpenSubsonic: system endpoints ---------------------------------------------------------------------
    system = {}
    for op in ('ping', 'getLicense', 'getMusicFolders', 'getOpenSubsonicExtensions', 'getGenres', 'getArtists',
               'getIndexes', 'getScanStatus'):
        system[op] = sub('subsonic-system', op, 'read', op, unordered=['openSubsonicExtensions'])
    sub('subsonic-system', 'getIndexes', 'since-epoch', 'getIndexes', ifModifiedSince=0)
    COMPANIONS[sub('subsonic-system', 'getIndexes', 'since-future', 'getIndexes',
                   ifModifiedSince=4102444800000)] = [system['getIndexes']]
    for op in ('getPodcasts', 'getNewestPodcasts', 'refreshPodcasts', 'createUser', 'deleteUser', 'changePassword'):
        COMPANIONS[sub('subsonic-system', op, 'unavailable', op, http=501)] = [system['ping']]
    for op in ('getChatMessages', 'getVideos', 'search'):
        COMPANIONS[sub('subsonic-system', op, 'gone', op, http=410)] = [system['ping']]

    # -- OpenSubsonic: album lists ---------------------------------------------------------------------------
    lists = {}
    for kind in ('alphabeticalByName', 'alphabeticalByArtist'):
        lists[kind] = sub('subsonic-lists', 'getAlbumList2', kind, 'getAlbumList2', type=kind, size=50)
    sub('subsonic-lists', 'getAlbumList', 'alphabeticalByName', 'getAlbumList', type='alphabeticalByName', size=50)
    for offset in (0, 2, 4, 6, 7, 20):
        cid = sub('subsonic-lists', 'getAlbumList2-page', 'offset-%d' % offset, 'getAlbumList2',
                  type='alphabeticalByName', size=3, offset=offset)
        if offset >= 7:
            COMPANIONS[cid] = [lists['alphabeticalByName']]
    for kind in ('recent', 'frequent', 'starred', 'highest'):
        COMPANIONS[sub('subsonic-lists', 'getAlbumList2-empty', kind, 'getAlbumList2', type=kind,
                       size=10)] = [lists['alphabeticalByName']]
    for low, high in ((1999, 2005), (2010, 2020), (2001, 2001), (2020, 1999), (1900, 1950)):
        cid = sub('subsonic-lists', 'getAlbumList2-year', '%d-%d' % (low, high), 'getAlbumList2', type='byYear',
                  fromYear=low, toYear=high, size=10)
        if low == 1900:
            COMPANIONS[cid] = [lists['alphabeticalByName']]
    for i, genre in enumerate(('Rock', 'Jazz', 'Blues', 'Folk', 'Ambient', 'rock', 'Nope')):
        cid = sub('subsonic-lists', 'getAlbumList2-genre', '%02d-%s' % (i, slug(genre)), 'getAlbumList2',
                  type='byGenre', genre=genre, size=10)
        if genre == 'Nope':
            COMPANIONS[cid] = [lists['alphabeticalByName']]
    for name, query in (('no-type', {}), ('unknown-type', {'type': 'bogus'}), ('genre-without-name', {'type': 'byGenre'}),
                        ('year-without-range', {'type': 'byYear'})):
        COMPANIONS[sub('subsonic-lists', 'getAlbumList2-error', name, 'getAlbumList2', **query)] = [
            lists['alphabeticalByName']]
    COMPANIONS[sub('subsonic-lists', 'getAlbumList-error', 'no-type', 'getAlbumList')] = [lists['alphabeticalByName']]
    COMPANIONS[variants(s, 'subsonic-lists', 'getAlbumList2-size', 'odd-values', 'getAlbumList2', 'size', LIMITS,
                        type='alphabeticalByName')] = [lists['alphabeticalByName']]

    # -- OpenSubsonic: songs by genre and random songs -------------------------------------------------------
    genres = {}
    for i, genre in enumerate(('Rock', 'Electronic', 'Pop', 'Jazz', 'Blues', 'Ambient', 'Folk', 'rock', 'Nope')):
        genres[genre] = sub('subsonic-songs', 'getSongsByGenre', '%02d-%s' % (i, slug(genre)), 'getSongsByGenre',
                            genre=genre, count=20, unordered=['songsByGenre.song'])
    COMPANIONS[genres['Nope']] = [genres['Rock']]
    COMPANIONS[paging(s, 'subsonic-songs', 'getSongsByGenre-page', 'rock', 'getSongsByGenre', 'songsByGenre', 'song',
                      genre='Rock', count=1)] = [genres['Rock']]
    COMPANIONS[variants(s, 'subsonic-songs', 'getSongsByGenre-count', 'odd-values', 'getSongsByGenre', 'count', LIMITS[::2],
                        unordered=['songsByGenre.song'], genre='Rock')] = [genres['Rock']]
    randoms = {}
    for name, query in (('folk', {'genre': 'Folk'}), ('ambient', {'genre': 'Ambient'}),
                        ('year-2015', {'fromYear': 2015, 'toYear': 2015}), ('year-2005', {'fromYear': 2005, 'toYear': 2005}),
                        ('none', {'genre': 'Nope'})):
        randoms[name] = sub('subsonic-songs', 'getRandomSongs', name, 'getRandomSongs', size=5, **query)
    COMPANIONS[randoms['none']] = [randoms['folk']]

    # -- OpenSubsonic: browsing ---------------------------------------------------------------------------------
    songs_read, albums_read, artists_read = {}, {}, {}
    for title in TITLES:
        songs_read[title] = sub('subsonic-browse', 'getSong', slug(title), 'getSong', id=song_of(title))
    for name, query in (('unknown-id', {'id': UNKNOWN}), ('no-id', {}), ('empty-id', {'id': ''})):
        COMPANIONS[sub('subsonic-browse', 'getSong', name, 'getSong', **query)] = [songs_read['Opening']]
    directories = {}
    for title, artist in ALBUMS:
        name = slug(artist + ' ' + title)
        albums_read[(title, artist)] = sub('subsonic-browse', 'getAlbum', name, 'getAlbum', id=album_of(title, artist))
        directories[(title, artist)] = sub('subsonic-browse', 'getMusicDirectory-album', name, 'getMusicDirectory',
                                           id=album_of(title, artist))
    for name, query in (('unknown-id', {'id': UNKNOWN}), ('no-id', {}), ('empty-id', {'id': ''})):
        COMPANIONS[sub('subsonic-browse', 'getAlbum', name, 'getAlbum', **query)] = [albums_read[ALBUMS[0]]]
        COMPANIONS[sub('subsonic-browse', 'getMusicDirectory', name, 'getMusicDirectory', **query)] = [directories[ALBUMS[0]]]
    for artist in ARTISTS:
        artists_read[artist] = sub('subsonic-browse', 'getArtist', slug(artist), 'getArtist', id=artist_of(artist))
    for name, query in (('unknown-id', {'id': UNKNOWN}), ('no-id', {}), ('empty-id', {'id': ''})):
        COMPANIONS[sub('subsonic-browse', 'getArtist', name, 'getArtist', **query)] = [artists_read['Alpha Artist']]
    for artist in ARTISTS[:3]:
        sub('subsonic-browse', 'getMusicDirectory-artist', slug(artist), 'getMusicDirectory', id=artist_of(artist))
    sub('subsonic-browse', 'getAlbumInfo2', 'alpha-first-album', 'getAlbumInfo2', id=album_of('First Album', 'Alpha Artist'))
    top = sub('subsonic-browse', 'getTopSongs', 'alpha-artist', 'getTopSongs', artist='Alpha Artist', count=5)
    COMPANIONS[top] = [songs_read['Opening']]
    COMPANIONS[sub('subsonic-browse', 'getTopSongs', 'no-artist', 'getTopSongs')] = [top]
    COMPANIONS[sub('subsonic-browse', 'getTopSongs', 'unknown-artist', 'getTopSongs', artist='Nobody At All')] = [top]
    # Without external services the similar songs are the other songs of the album, in no fixed order.
    sub('subsonic-browse', 'getSimilarSongs2', 'opening', 'getSimilarSongs2', id=song_of('Opening'), count=5, unordered=['similarSongs2.song'])

    # -- OpenSubsonic: search -------------------------------------------------------------------------------------
    first = None
    for i, text in enumerate(QUERIES):
        cid = sub('subsonic-search', 'search3', '%02d-%s' % (i, slug(text)), 'search3', query=text, artistCount=10,
                  albumCount=10, songCount=20, unordered=SEARCH3)
        first = first or cid
        if text in EMPTY_QUERIES:
            COMPANIONS[cid] = [first]
    paging(s, 'subsonic-search', 'search3-page', 'songs', 'search3', 'searchResult3', 'song', offsets=(0, 2, 4),
           offset='songOffset', query='first', artistCount=0, albumCount=0, songCount=2)
    paging(s, 'subsonic-search', 'search3-page', 'albums', 'search3', 'searchResult3', 'album', offsets=(0, 1, 2),
           offset='albumOffset', label='name', query='first', artistCount=0, songCount=0, albumCount=1)
    sub('subsonic-search', 'search3-page', 'songs-only', 'search3', query='first', artistCount=0, albumCount=0, songCount=20,
        unordered=SEARCH3)
    COMPANIONS[variants(s, 'subsonic-search', 'search3-count', 'odd-values', 'search3', 'songCount', [('zero', 0), ('text', 'abc')],
                        unordered=SEARCH3, query='first')] = [first]
    for i, text in enumerate(('first', 'gamma', 'zzz')):
        cid = sub('subsonic-search', 'search2', '%02d-%s' % (i, text), 'search2', query=text, artistCount=10,
                  albumCount=10, songCount=20, unordered=SEARCH2)
        if text == 'zzz':
            COMPANIONS[cid] = [first]

    # -- OpenSubsonic: lyrics -----------------------------------------------------------------------------------------
    lyric = sub('subsonic-lyrics', 'getLyrics', 'opening', 'getLyrics', artist='Alpha Artist', title='Opening')
    COMPANIONS[sub('subsonic-lyrics', 'getLyrics', 'unknown', 'getLyrics', artist='Nobody', title='Nothing')] = [lyric]
    by_id = {}
    for title in ('Opening', 'Echo', 'Middle', 'Intro'):
        by_id[title] = sub('subsonic-lyrics', 'getLyricsBySongId', slug(title), 'getLyricsBySongId', id=song_of(title))
        if title in ('Middle', 'Intro'):
            COMPANIONS[by_id[title]] = [by_id['Opening']]
    for name, query in (('no-id', {}), ('unknown-id', {'id': UNKNOWN}), ('empty-id', {'id': ''})):
        COMPANIONS[sub('subsonic-lyrics', 'getLyricsBySongId', name, 'getLyricsBySongId', **query)] = [by_id['Opening']]

    # -- native API: songs --------------------------------------------------------------------------------------------
    songs = {}
    for sort in ('title', 'path', 'size'):
        for order in ('ASC', 'DESC'):
            songs[(sort, order)] = nat('native-songs', 'sort', '%s-%s' % (sort, order.lower()), 'GET', 'song',
                                       params={'_start': 0, '_end': 50, '_sort': sort, '_order': order},
                                       fields=['title', 'path'], status=200)
    base = songs[('title', 'ASC')]
    for start, end in ((0, 3), (3, 6), (12, 15), (15, 30), (100, 110)):
        cid = nat('native-songs', 'page', '%d-%d' % (start, end), 'GET', 'song',
                  params={'_start': start, '_end': end, '_sort': 'title', '_order': 'ASC'}, fields=['title'])
        if start == 100:
            COMPANIONS[cid] = [base]
    filters = (('title-single', {'title': 'Single'}), ('title-folded', {'title': 'naive'}), ('title-none', {'title': 'zzz'}),
               ('path-alpha', {'path': 'Alpha Artist'}), ('path-cd2', {'path': 'Beta Band/Second Album/CD2'}),
               ('missing-false', {'missing': 'false'}), ('missing-true', {'missing': 'true'}),
               ('starred', {'starred': 'true'}), ('library-1', {'library_id': 1}), ('library-2', {'library_id': 2}),
               ('artist', {'artists_id': artist_of('Gamma Trio')}))
    for name, query in filters:
        cid = nat('native-songs', 'filter', name, 'GET', 'song', params={**page, '_sort': 'title', **query},
                  fields=['title'])
        if name in ('title-none', 'missing-true', 'starred', 'library-2'):
            COMPANIONS[cid] = [base]
    for title in TITLES:
        nat('native-songs', 'detail', slug(title), 'GET', lambda c, t=title: 'song/' + song_of(t)(c), fields=SONG,
            hint='song')
    for title in ('Blue Hour', 'Opening', 'Single A', 'Naïve Ω'):
        nat('native-songs', 'rich', slug(title), 'GET', lambda c, t=title: 'song/' + song_of(t)(c),
            fields=['participants', 'genres', 'tags'], hint='song')
    for title in ('Opening', 'Echo'):
        nat('native-songs', 'lyrics', slug(title), 'GET', lambda c, t=title: 'song/' + song_of(t)(c), fields=['lyrics'],
            hint='song')
    COMPANIONS[nat('native-songs', 'errors', 'unknown-id', 'GET', 'song/' + UNKNOWN, fields=['title'])] = [base]
    COMPANIONS[nat('native-songs', 'errors', 'anonymous', 'GET', 'song', anonymous=True, params=page)] = [base]
    COMPANIONS[nat('native-songs', 'errors', 'bad-token', 'GET', 'song', token='not-a-token', params=page)] = [base]

    # -- native API: albums --------------------------------------------------------------------------------------------
    albums = {}
    for sort in ('name', 'max_year', 'artist'):
        for order in ('ASC', 'DESC'):
            albums[(sort, order)] = nat('native-albums', 'sort', '%s-%s' % (sort, order.lower()), 'GET', 'album',
                                        params={'_start': 0, '_end': 50, '_sort': sort, '_order': order},
                                        fields=['name', 'albumArtist'], status=200)
    abase = albums[('name', 'ASC')]
    nat('native-albums', 'list', 'detail', 'GET', 'album',
        params={'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}, fields=ALBUM, hint='album')
    for name, query in (('compilation-true', {'compilation': 'true'}), ('compilation-false', {'compilation': 'false'}),
                        ('year-2001', {'year': 2001}), ('name-first', {'name': 'first'}), ('name-none', {'name': 'zzz'}),
                        ('starred', {'starred': 'true'}), ('missing-false', {'missing': 'false'}),
                        ('library-1', {'library_id': 1}), ('artist', {'artist_id': artist_of('Alpha Artist')})):
        cid = nat('native-albums', 'filter', name, 'GET', 'album',
                  params={'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC', **query}, fields=['name', 'albumArtist'])
        if name in ('name-none', 'starred'):
            COMPANIONS[cid] = [abase]
    for title, artist in ALBUMS:
        nat('native-albums', 'detail', slug(artist + ' ' + title), 'GET',
            lambda c, t=title, a=artist: 'album/' + album_of(t, a)(c), fields=ALBUM, hint='album')
    COMPANIONS[nat('native-albums', 'errors', 'unknown-id', 'GET', 'album/' + UNKNOWN, fields=['name'])] = [abase]

    # -- native API: artists, genres, library -----------------------------------------------------------------------------
    artists = {}
    for order in ('ASC', 'DESC'):
        artists[order] = nat('native-artists', 'sort', 'name-' + order.lower(), 'GET', 'artist',
                             params={'_start': 0, '_end': 50, '_sort': 'name', '_order': order},
                             fields=['name', 'albumCount', 'songCount'], status=200)
    for name, query in (('role-albumartist', {'role': 'albumartist'}), ('role-artist', {'role': 'artist'}),
                        ('name-delta', {'name': 'delta'}), ('name-none', {'name': 'zzz'}),
                        ('missing-false', {'missing': 'false'}), ('starred', {'starred': 'true'})):
        cid = nat('native-artists', 'filter', name, 'GET', 'artist',
                  params={'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC', **query}, fields=['name', 'albumCount'])
        if name in ('name-none', 'starred'):
            COMPANIONS[cid] = [artists['ASC']]
    for artist in ARTISTS:
        nat('native-artists', 'detail', slug(artist), 'GET', lambda c, n=artist: 'artist/' + artist_of(n)(c),
            fields=ARTIST, hint='artist')
    genre_list = {}
    for order in ('ASC', 'DESC'):
        genre_list[order] = nat('native-genres', 'sort', 'name-' + order.lower(), 'GET', 'genre',
                                params={'_start': 0, '_end': 50, '_sort': 'name', '_order': order}, fields=['name'],
                                status=200)
    for start, end in ((0, 3), (3, 10), (10, 20)):
        cid = nat('native-genres', 'page', '%d-%d' % (start, end), 'GET', 'genre',
                  params={'_start': start, '_end': end, '_sort': 'name', '_order': 'ASC'}, fields=['name'])
        if start == 10:
            COMPANIONS[cid] = [genre_list['ASC']]

    # -- media: stream, download and cover art -----------------------------------------------------------------------------
    streams = {}
    for title in TITLES:
        streams[title] = raw(s, 'media', 'stream', slug(title), 'stream', id=song_of(title))
    for step, window in (('head', 'bytes=0-99'), ('tail', 'bytes=-50'), ('open', 'bytes=100-')):
        raw(s, 'media', 'stream-range', step, 'stream', headers={'range': window}, id=song_of('Opening'))
    for title in ('Opening', 'Echo', 'click'):
        raw(s, 'media', 'download', slug(title), 'download', id=song_of(title))
    COMPANIONS[raw(s, 'media', 'stream', 'unknown-id', 'stream', id=UNKNOWN)] = [streams['Opening']]
    cover = None
    for title, artist in ALBUMS:
        cid = raw(s, 'media', 'cover-album', slug(artist + ' ' + title), 'getCoverArt',
                  id=prefixed('al-', album_of(title, artist)))
        if cover is None:
            cover = cid
        else:
            COMPANIONS[cid] = [cover]
    for artist in ARTISTS[:3]:
        COMPANIONS[raw(s, 'media', 'cover-artist', slug(artist), 'getCoverArt',
                       id=prefixed('ar-', artist_of(artist)))] = [cover]
    for title in ('Opening', 'Intro', 'Echo'):
        COMPANIONS[raw(s, 'media', 'cover-song', slug(title), 'getCoverArt',
                       id=prefixed('mf-', song_of(title)))] = [cover]
