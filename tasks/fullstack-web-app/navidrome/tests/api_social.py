'''Interactions: ratings, favourites, play history, internet radio stations, shares, bookmarks and the play queue.

State that changes is chained with need() to the write that made it, never to a read; a write is bound to the read that
shows its effect, and denial and missing-resource points are bound to a positive point of the same episode. Each read
keeps only the fields of its own subject, so it does not depend on the other sections. Share identities are short random
tokens, so the share checks build their own observation without them.'''
from api_browse import album_of, artist_of, song_of
from harness import ORIGIN, resolve

PAGE = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
LISTING = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
ROWS = {'_start': 0, '_end': 20}
UNKNOWN = 'D' * 22
RATED = ['title', 'rating']
STARS = ['title', 'starred']
PLAYED = ['title', 'playCount', 'playDate']
RADIO = ['name', 'streamUrl', 'homePageUrl']
STARRED = ['starred2.song', 'starred2.album', 'starred2.artist']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def bind(cid, *companions):
    COMPANIONS[cid] = list(companions)
    return cid


def path_of(kind, finder):
    return lambda c: kind + '/' + finder(c)


def radio(key):
    return lambda c: 'radio/' + c.state[key]['id']


def station(name):
    # Looked up when the request is made: the station list read is not a prerequisite of the write.
    def find(c):
        reply = c.reply(c.subsonic('getInternetRadioStations'))
        rows = (reply.get('internetRadioStations') or {}).get('internetRadioStation') or []
        return next((r['id'] for r in rows if r.get('name') == name), UNKNOWN)
    return find


def share_id(key, description):
    # The share made by the create request; a product that does not return it is looked up by its description.
    def find(c):
        if key in c.state:
            return c.state[key]['id']
        shares = (c.reply(c.subsonic('getShares')).get('shares') or {}).get('share') or []
        return next((x['id'] for x in shares if x.get('description') == description), UNKNOWN)
    return find


def share_view(c, share):
    link = str(share.get('url') or '')
    return c.norm.clean({'description': share.get('description'), 'downloadable': share.get('downloadable'),
                         'username': share.get('username'), 'visitCount': share.get('visitCount'),
                         'link': link.startswith(ORIGIN + '/share/'), 'expires': bool(share.get('expires')),
                         'entries': sorted(e.get('title', '') for e in share.get('entry') or [])}, 'share')


def share_call(s, step, op, user='admin', save=None, expect=None, **query):
    def action(c, relaxed=False):
        answer = c.subsonic(op, user, **resolve(query, c))
        reply = c.reply(answer)
        got = (reply.get('error') or {}).get('code') if reply.get('status') == 'failed' else 'ok'
        if relaxed:
            assert got == 'ok', 'setup %s: %s' % (op, str(reply)[:200])
        if expect is not None:
            assert got == expect, '%s: expected %s, received %s' % (op, expect, got)
        shares = (reply.get('shares') or {}).get('share') or []
        if save and shares:
            c.state[save] = shares[0]
        if relaxed:
            return None
        view = {'status': reply.get('status')}
        if reply.get('status') == 'failed':
            view['error'] = got
        elif 'shares' in reply:
            view['shares'] = sorted((share_view(c, x) for x in shares), key=lambda v: str(v.get('description')))
        return {'status': answer['status'], 'reply': view}
    return s.add('shares', 'subsonic', step, action, description='subsonic %s as %s' % (op, user))


def build(s):
    nat, sub = s.nat, s.sub
    nat('social-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    sub('social-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('social-fixture', 'library', 'artists', 'getArtists', save='artists')
    opening, echo = song_of('Opening'), song_of('Echo')
    album, artist = album_of('Third Album', 'Gamma Trio'), artist_of('Alpha Artist')
    row, other = path_of('song', opening), path_of('song', echo)
    album_row, artist_row = path_of('album', album), path_of('artist', artist)

    # -- ratings -----------------------------------------------------------------------------------------------
    nat('social', 'rating', 'song-initial', 'GET', row, status=200, fields=RATED + ['starred', 'playCount'])
    rated = sub('social', 'rating', 'song-five', 'setRating', id=opening, rating=5, expect='ok')
    five = need(nat('social', 'rating', 'song-five-read', 'GET', row, status=200, fields=RATED), rated)
    bind(rated, five)
    need(nat('social', 'rating', 'song-five-other-account', 'GET', row, 'bob', status=200, fields=RATED), rated)
    cleared = need(sub('social', 'rating', 'song-zero', 'setRating', id=opening, rating=0, expect='ok'), rated)
    bind(cleared, need(nat('social', 'rating', 'song-zero-read', 'GET', row, status=200, fields=RATED), cleared))
    album_rated = sub('social', 'rating', 'album-four', 'setRating', id=album, rating=4, expect='ok')
    bind(album_rated, need(nat('social', 'rating', 'album-read', 'GET', album_row, status=200, fields=['name', 'rating']), album_rated))
    artist_rated = sub('social', 'rating', 'artist-two', 'setRating', id=artist, rating=2, expect='ok')
    bind(artist_rated, need(nat('social', 'rating', 'artist-read', 'GET', artist_row, status=200, fields=['name', 'rating']), artist_rated))
    bind(sub('social', 'rating', 'unknown', 'setRating', id=UNKNOWN, rating=3, expect=70), five)
    bind(sub('social', 'rating', 'missing-id', 'setRating', rating=3, expect=10), five)
    bind(sub('social', 'rating', 'not-a-number', 'setRating', id=opening, rating='abc', expect=0), five)

    # -- favourites ----------------------------------------------------------------------------------------------
    starred = sub('social', 'favourite', 'star-song', 'star', id=opening, expect='ok')
    bind(starred, need(nat('social', 'favourite', 'song-read', 'GET', row, status=200, fields=STARS), starred))
    listed = need(sub('social', 'favourite', 'list-song', 'getStarred2', unordered=STARRED), starred)
    bind(need(sub('social', 'favourite', 'list-other-account', 'getStarred2', 'bob', unordered=STARRED), starred), listed)
    album_star = sub('social', 'favourite', 'star-album', 'star', albumId=album, expect='ok')
    artist_star = sub('social', 'favourite', 'star-artist', 'star', artistId=artist, expect='ok')
    bind(album_star, need(nat('social', 'favourite', 'album-read', 'GET', album_row, status=200, fields=['name', 'starred']), album_star))
    bind(artist_star, need(nat('social', 'favourite', 'artist-read', 'GET', artist_row, status=200, fields=['name', 'starred']), artist_star))
    need(sub('social', 'favourite', 'list-all', 'getStarred2', unordered=STARRED), starred, album_star, artist_star)
    unstarred = need(sub('social', 'favourite', 'unstar-song', 'unstar', id=opening, expect='ok'), starred)
    bind(unstarred, need(nat('social', 'favourite', 'song-after-unstar', 'GET', row, status=200, fields=STARS), unstarred))
    need(sub('social', 'favourite', 'list-after-unstar', 'getStarred2', unordered=STARRED), unstarred, album_star, artist_star)
    bind(sub('social', 'favourite', 'star-nothing', 'star', expect=10), listed)
    bind(sub('social', 'favourite', 'unstar-nothing', 'unstar', expect=10), listed)

    # -- play history --------------------------------------------------------------------------------------------
    played = sub('social', 'history', 'scrobble', 'scrobble', id=opening, expect='ok')
    timed = need(sub('social', 'history', 'scrobble-time', 'scrobble', id=opening, time=1700000000000, expect='ok'), played)
    pending = sub('social', 'history', 'now-playing-report', 'scrobble', id=echo, submission='false', expect='ok')
    counts = need(nat('social', 'history', 'song-counts', 'GET', row, status=200, fields=PLAYED), played, timed)
    bind(played, counts)
    bind(pending, need(nat('social', 'history', 'other-song-counts', 'GET', other, status=200, fields=PLAYED), pending))
    bind(timed, need(nat('social', 'history', 'native-list', 'GET', 'scrobble', params=ROWS, status=200,
                         fields=['mediaFileId', 'submissionTime']), played, timed))
    bind(sub('social', 'history', 'scrobble-missing-id', 'scrobble', expect=10), counts)
    report = sub('social', 'history', 'report-playback', 'reportPlayback', mediaId=opening, mediaType='song', positionMs=1000,
                 state='playing', expect='ok')
    bind(report, need(sub('social', 'history', 'now-playing-after-report', 'getNowPlaying',
                          unordered=['nowPlaying.entry', 'nowPlaying.entry.contributors']), report))
    bind(sub('social', 'history', 'report-bad-state', 'reportPlayback', mediaId=opening, mediaType='song', positionMs=1000,
             state='dancing', expect=0), report)

    # -- internet radio stations ---------------------------------------------------------------------------------
    stream = {'name': 'Morning FM', 'streamUrl': 'http://stream.example.test/morning', 'homePageUrl': 'http://home.example.test'}
    made = nat('social', 'radio', 'create', 'POST', 'radio', body=stream, status=200, hint='radio', save='r1')
    read = need(nat('social', 'radio', 'read', 'GET', radio('r1'), status=200, fields=RADIO), made)
    bind(made, read)
    need(nat('social', 'radio', 'read-other-account', 'GET', radio('r1'), 'bob', status=200, fields=RADIO), made)
    sheet = need(nat('social', 'radio', 'list', 'GET', 'radio', params=LISTING, status=200, fields=RADIO), made)
    bind(nat('social', 'radio', 'list-anonymous', 'GET', 'radio', anonymous=True, params=LISTING, status=401), sheet)
    bind(nat('social', 'radio', 'create-other-account', 'POST', 'radio', 'bob', body=stream, status=403), read)
    bind(need(nat('social', 'radio', 'update-other-account', 'PUT', radio('r1'), 'bob', body=stream, status=403), made), read)
    bind(need(nat('social', 'radio', 'delete-other-account', 'DELETE', radio('r1'), 'bob', status=403), made), read)
    edited = need(nat('social', 'radio', 'update', 'PUT', radio('r1'), body={'name': 'Evening FM', 'streamUrl': 'http://stream.example.test/evening',
                                                                      'homePageUrl': ''}, status=200, fields=RADIO), made)
    bind(edited, need(nat('social', 'radio', 'after-update', 'GET', radio('r1'), status=200, fields=RADIO), edited))
    removed = need(nat('social', 'radio', 'delete', 'DELETE', radio('r1'), status=200), edited)
    gone_radio = bind(need(nat('social', 'radio', 'read-deleted', 'GET', radio('r1'), status=404), removed), read)
    bind(removed, gone_radio)
    bind(need(nat('social', 'radio', 'delete-again', 'DELETE', radio('r1'), status=404), removed), gone_radio)
    created = sub('social', 'radio-subsonic', 'create', 'createInternetRadioStation', streamUrl='http://stream.example.test/news',
                  name='News FM', homepageUrl='http://news.example.test', expect='ok')
    seen = need(sub('social', 'radio-subsonic', 'list', 'getInternetRadioStations',
                    unordered=['internetRadioStations.internetRadioStation']), created)
    bind(created, seen)
    bind(sub('social', 'radio-subsonic', 'create-other-account', 'createInternetRadioStation', 'bob',
             streamUrl='http://stream.example.test/x', name='Other FM', expect=50), seen)
    bind(sub('social', 'radio-subsonic', 'create-without-name', 'createInternetRadioStation',
             streamUrl='http://stream.example.test/x', expect=10), seen)
    renamed = need(sub('social', 'radio-subsonic', 'update', 'updateInternetRadioStation', id=station('News FM'),
                       streamUrl='http://stream.example.test/news2', name='News FM 2', homepageUrl='', expect='ok'), created)
    bind(renamed, need(sub('social', 'radio-subsonic', 'list-after-update', 'getInternetRadioStations',
                           unordered=['internetRadioStations.internetRadioStation']), renamed))
    dropped = need(sub('social', 'radio-subsonic', 'delete', 'deleteInternetRadioStation', id=station('News FM 2'), expect='ok'), renamed)
    after_drop = bind(need(sub('social', 'radio-subsonic', 'list-after-delete', 'getInternetRadioStations',
                               unordered=['internetRadioStations.internetRadioStation']), dropped), seen)
    bind(dropped, after_drop)
    for step, query, code in (('none', {}, 10), ('unknown', {'id': UNKNOWN}, 70), ('empty', {'id': ''}, 10)):
        bind(sub('social', 'radio-subsonic', 'delete-' + step, 'deleteInternetRadioStation', expect=code, **query), after_drop)

    # -- shares ----------------------------------------------------------------------------------------------------
    first = share_id('share', 'Album link')
    shared = share_call(s, 'create-album', 'createShare', save='share', id=album, description='Album link', downloadable='true', expect='ok')
    listing = need(share_call(s, 'list', 'getShares'), shared)
    bind(shared, listing)
    bind(need(share_call(s, 'list-other-account', 'getShares', 'bob'), shared), listing)
    bind(share_call(s, 'create-unknown', 'createShare', id=UNKNOWN, expect=70), listing)
    bind(share_call(s, 'create-without-id', 'createShare', expect=10), listing)
    bind(share_call(s, 'create-empty-id', 'createShare', id='', expect=70), listing)
    bind(share_call(s, 'create-mixed', 'createShare', id=[album, opening], expect=0), listing)
    updated = need(share_call(s, 'update', 'updateShare', id=first, description='Renamed link', expect='ok'), shared)
    after_update = need(share_call(s, 'list-after-update', 'getShares'), updated)
    bind(updated, after_update)
    bind(need(share_call(s, 'update-other-account', 'updateShare', 'bob', id=first, description='Hijack', expect=70), shared), after_update)
    for step, query, code in (('none', {}, 10), ('unknown', {'id': UNKNOWN}, 70), ('empty', {'id': ''}, 10)):
        bind(share_call(s, 'update-' + step, 'updateShare', description='Nothing', expect=code, **query), after_update)
    bind(need(share_call(s, 'delete-other-account', 'deleteShare', 'bob', id=first, expect=50), shared), after_update)
    native = nat('social', 'share-native', 'create', 'POST', 'share', body={'resourceType': 'album', 'resourceIds': album, 'description': 'Native link'},
                 status=200, fields=['description'], save='nshare')
    page = need(nat('social', 'share-native', 'list', 'GET', 'share', params=ROWS, status=200,
                    fields=['description', 'resourceType', 'resourceIds', 'downloadable']), native)
    bind(native, page)
    bind(nat('social', 'share-native', 'list-other-account', 'GET', 'share', 'bob', params=ROWS, status=200), page)
    native_gone = need(nat('social', 'share-native', 'delete', 'DELETE', lambda c: 'share/' + c.state['nshare']['id'], status=200), native)
    bind(native_gone, need(nat('social', 'share-native', 'read-deleted', 'GET', lambda c: 'share/' + c.state['nshare']['id'], status=404),
                           native_gone))
    gone = need(share_call(s, 'delete', 'deleteShare', id=first, expect='ok'), updated)
    after_delete = bind(need(share_call(s, 'list-after-delete', 'getShares'), gone), listing)
    bind(gone, after_delete)
    bind(need(share_call(s, 'delete-again', 'deleteShare', id=first, expect=70), gone), after_delete)
    for step, query, code in (('none', {}, 10), ('empty', {'id': ''}, 10)):
        bind(share_call(s, 'delete-' + step, 'deleteShare', expect=code, **query), after_delete)

    # -- bookmarks -------------------------------------------------------------------------------------------------
    marked = sub('social', 'bookmark', 'create', 'createBookmark', id=opening, position=1500, comment='Resume here', expect='ok')
    kept = need(sub('social', 'bookmark', 'list', 'getBookmarks'), marked)
    bind(marked, kept)
    bind(need(sub('social', 'bookmark', 'list-other-account', 'getBookmarks', 'bob'), marked), kept)
    for step, query, code in (('unknown', {'id': UNKNOWN}, 70), ('none', {}, 10), ('empty', {'id': ''}, 10)):
        bind(sub('social', 'bookmark', 'create-' + step, 'createBookmark', position=1, expect=code, **query), kept)
    unmarked = need(sub('social', 'bookmark', 'delete', 'deleteBookmark', id=opening, expect='ok'), marked)
    after_unmark = bind(need(sub('social', 'bookmark', 'list-after-delete', 'getBookmarks'), unmarked), kept)
    bind(unmarked, after_unmark)
    for step, query, code in (('none', {}, 10), ('unknown', {'id': UNKNOWN}, 'ok'), ('empty', {'id': ''}, 10)):
        bind(sub('social', 'bookmark', 'delete-' + step, 'deleteBookmark', expect=code, **query), after_unmark)

    # -- the play queue --------------------------------------------------------------------------------------------
    empty = sub('social', 'queue', 'get-empty', 'getPlayQueue')
    saved = sub('social', 'queue', 'save', 'savePlayQueue', id=[opening, echo], current=echo, position=500, expect='ok')
    queued = need(sub('social', 'queue', 'get', 'getPlayQueue'), saved)
    bind(saved, queued)
    bind(empty, queued)
    bind(need(sub('social', 'queue', 'get-other-account', 'getPlayQueue', 'bob'), saved), queued)
    by_index = need(sub('social', 'queue', 'save-by-index', 'savePlayQueueByIndex', id=[opening, echo], currentIndex=1, position=1, expect='ok'), saved)
    indexed = need(sub('social', 'queue', 'get-by-index', 'getPlayQueueByIndex'), by_index)
    bind(by_index, indexed)
    bind(need(sub('social', 'queue', 'save-index-out-of-range', 'savePlayQueueByIndex', id=[opening], currentIndex=3, expect=10), by_index), indexed)
    bind(need(sub('social', 'queue', 'save-index-missing', 'savePlayQueueByIndex', id=[opening], expect=10), by_index), indexed)
    cleared_queue = need(sub('social', 'queue', 'clear', 'savePlayQueue', expect='ok'), by_index)
    bind(cleared_queue, bind(need(sub('social', 'queue', 'get-after-clear', 'getPlayQueue'), cleared_queue), queued))
    stored = nat('social', 'queue-native', 'save', 'POST', 'queue', body={'ids': [opening, echo], 'current': 1, 'position': 10}, status=204)
    stored_read = need(nat('social', 'queue-native', 'read', 'GET', 'queue', status=200, fields=['current', 'position']), stored)
    bind(stored, stored_read)
    bind(need(nat('social', 'queue-native', 'save-out-of-range', 'POST', 'queue', body={'ids': [opening], 'current': 5}, status=400), stored), stored_read)
    moved = need(nat('social', 'queue-native', 'move-current', 'PUT', 'queue', body={'current': 0}, status=204), stored)
    bind(need(nat('social', 'queue-native', 'move-out-of-range', 'PUT', 'queue', body={'current': 9}, status=400), moved), stored_read)
    seek = need(nat('social', 'queue-native', 'seek', 'PUT', 'queue', body={'position': 25}, status=204), moved)
    edited_queue = need(nat('social', 'queue-native', 'read-after-edit', 'GET', 'queue', status=200, fields=['current', 'position']), moved, seek)
    bind(moved, edited_queue)
    bind(seek, edited_queue)
    dropped_queue = need(nat('social', 'queue-native', 'delete', 'DELETE', 'queue', status=204), seek)
    bind(dropped_queue, bind(need(nat('social', 'queue-native', 'read-after-delete', 'GET', 'queue', status=200,
                                      fields=['current', 'position']), dropped_queue), stored_read))
