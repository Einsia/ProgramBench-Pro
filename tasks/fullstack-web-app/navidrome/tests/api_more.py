'''More OpenSubsonic endpoints: album and artist information, similar songs, the first-generation starred list, now playing and avatars.

The external information services are off in this product, so the information replies only carry what the product itself knows:
the artist information is empty, so each artist information point compares the reply for a known artist together with the
refusals of an unknown, a missing and an empty id. State that changes is chained with need(); denial and missing-resource
points are bound to a positive point of the same episode.'''
from api_browse import UNKNOWN, album_of, artist_of, song_of

PAGE = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
STARRED = ['starred.song', 'starred.album', 'starred.artist']
SIMILAR = ['similarSongs.song.contributors', 'similarSongs.song']
SIMILAR2 = ['similarSongs2.song.contributors', 'similarSongs2.song']
NOW = ['nowPlaying.entry.contributors', 'nowPlaying.entry']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def artist_info(op):
    def action(c, relaxed=False):
        assert not relaxed, 'information checks are scored cases'
        seen = {'known': c.observe_subsonic(c.subsonic(op, id=artist_of('Gamma Trio')(c), count=2, includeNotPresent='true'))}
        for name, query in (('unknown', {'id': UNKNOWN}), ('missing', {}), ('empty', {'id': ''})):
            reply = c.reply(c.subsonic(op, **query))
            seen[name] = 'ok' if reply.get('status') == 'ok' else (reply.get('error') or {}).get('code')
        return seen
    return action


def avatars(c, relaxed=False):
    assert not relaxed, 'avatar checks are scored cases'
    return {name: c.observe_bytes(c.subsonic('getAvatar', binary=True, fmt=None, **query))
            for name, query in (('known', {'username': 'bob'}), ('unknown', {'username': 'nobody'}), ('none', {}))}


def build(s):
    nat, sub = s.nat, s.sub
    nat('more-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    sub('more-fixture', 'library', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50, save='albums')
    sub('more-fixture', 'library', 'artists', 'getArtists', save='artists')
    opening, echo = song_of('Opening'), song_of('Echo')
    third, delta = album_of('Third Album', 'Gamma Trio'), album_of('First Album', 'Delta Duo')
    gamma = artist_of('Gamma Trio')

    # -- album information ------------------------------------------------------------------------------------
    for op in ('getAlbumInfo', 'getAlbumInfo2'):
        info = sub('more-info', op, 'album', op, id=third)
        sub('more-info', op, 'album-without-cover', op, id=delta)
        sub('more-info', op, 'by-song', op, id=opening)
        COMPANIONS[sub('more-info', op, 'unknown', op, id=UNKNOWN, expect=70)] = [info]
        COMPANIONS[sub('more-info', op, 'missing-id', op, expect=10)] = [info]
        COMPANIONS[sub('more-info', op, 'empty-id', op, id='', expect=10)] = [info]

    # -- artist information: one point per operation, the known artist and the refusals together ---------------
    for op in ('getArtistInfo', 'getArtistInfo2'):
        s.add('more-info', op, 'artist-and-refusals', artist_info(op), description='subsonic %s for a known artist and unknown, missing and empty ids' % op)

    # -- similar songs ---------------------------------------------------------------------------------------------
    for op, shape in (('getSimilarSongs', SIMILAR), ('getSimilarSongs2', SIMILAR2)):
        similar = sub('more-similar', op, 'artist', op, id=gamma, count=5, unordered=shape)
        if op == 'getSimilarSongs':
            sub('more-similar', op, 'song', op, id=opening, count=5, unordered=shape)
        COMPANIONS[sub('more-similar', op, 'unknown', op, id=UNKNOWN, expect=70)] = [similar]
        COMPANIONS[sub('more-similar', op, 'missing-id', op, expect=10)] = [similar]
        COMPANIONS[sub('more-similar', op, 'empty-id', op, id='', expect=10)] = [similar]

    # -- the first-generation starred list ---------------------------------------------------------------------
    star_song = sub('more-starred', 'star', 'song', 'star', id=opening, expect='ok')
    star_album = sub('more-starred', 'star', 'album', 'star', albumId=third, expect='ok')
    star_artist = sub('more-starred', 'star', 'artist', 'star', artistId=gamma, expect='ok')
    listed = need(sub('more-starred', 'getStarred', 'all', 'getStarred', unordered=STARRED), star_song, star_album, star_artist)
    for cid in (star_song, star_album, star_artist):
        COMPANIONS[cid] = [listed]
    COMPANIONS[need(sub('more-starred', 'getStarred', 'other-account', 'getStarred', 'bob', unordered=STARRED), star_song, star_album, star_artist)] = [listed]
    COMPANIONS[sub('more-starred', 'getStarred', 'bad-folder', 'getStarred', musicFolderId=9, expect=70)] = [listed]
    unstarred = [need(sub('more-starred', 'unstar', 'song', 'unstar', id=opening, expect='ok'), star_song),
                 need(sub('more-starred', 'unstar', 'album', 'unstar', albumId=third, expect='ok'), star_album),
                 need(sub('more-starred', 'unstar', 'artist', 'unstar', artistId=gamma, expect='ok'), star_artist)]
    after = need(sub('more-starred', 'getStarred', 'after-unstar', 'getStarred', unordered=STARRED), *unstarred)
    COMPANIONS[after] = [listed]
    for cid in unstarred:
        COMPANIONS[cid] = [after]

    # -- now playing -----------------------------------------------------------------------------------------------
    admin_plays = sub('more-now', 'scrobble', 'admin-starts-song', 'scrobble', id=opening, submission='false', expect='ok')
    bob_plays = sub('more-now', 'scrobble', 'bob-starts-song', 'scrobble', 'bob', id=echo, submission='false', expect='ok')
    playing = need(sub('more-now', 'getNowPlaying', 'as-admin', 'getNowPlaying', unordered=NOW), admin_plays, bob_plays)
    COMPANIONS[admin_plays] = [playing]
    COMPANIONS[bob_plays] = [playing]
    need(sub('more-now', 'getNowPlaying', 'as-bob', 'getNowPlaying', 'bob', unordered=NOW), admin_plays, bob_plays)

    # -- avatars: an image for a known name, an unknown name and no name -------------------------------------------
    s.add('more-avatar', 'getAvatar', 'names', avatars, description='subsonic getAvatar for a known, an unknown and no user name')
