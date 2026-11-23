'''Persistence: playlists, ratings, favourites, radio stations, the play queue, accounts and the library survive a restart.

Scored cases make each kind of state, an unscored setup step restarts the product on the same data directory, and every
read after it needs only the case that made its state (and the restart, like every later case).'''
from api_browse import song_of
from harness import PASSWORDS

PASSWORDS.setdefault('erin', 'Erin-Local-2026!')
PAGE = {'_start': 0, '_end': 50, '_sort': 'path', '_order': 'ASC'}
LISTING = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
USERS = ['userName', 'name', 'email', 'isAdmin']
PLAYLIST = ['name', 'comment', 'public', 'songCount']
RADIO = ['name', 'streamUrl', 'homePageUrl']
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def restart(c, relaxed=False):
    c.restart_server()
    c.tokens.clear()


def playlist(c):
    return 'playlist/' + c.state['pl']['id']


def station_path(c):
    return 'radio/' + c.state['r1']['id']


def row(c):
    return 'song/' + song_of('Opening')(c)


def build(s):
    nat, sub = s.nat, s.sub
    nat('persist-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    opening, echo = song_of('Opening'), song_of('Echo')

    # -- state made before the restart ---------------------------------------------------------------------------
    made = nat('persist', 'make', 'playlist', 'POST', 'playlist', body={'name': 'Kept Mix', 'comment': 'Survives', 'public': False}, status=200, hint='playlist', save='pl')
    filled = need(nat('persist', 'make', 'playlist-tracks', 'POST', lambda c: playlist(c) + '/tracks', body={'ids': [opening, echo]}, status=200), made)
    rated = sub('persist', 'make', 'rating', 'setRating', id=opening, rating=3, expect='ok')
    starred = sub('persist', 'make', 'star', 'star', id=opening, expect='ok')
    station = nat('persist', 'make', 'radio', 'POST', 'radio', body={'name': 'Kept FM', 'streamUrl': 'http://stream.example.test/kept', 'homePageUrl': ''}, status=200, hint='radio', save='r1')
    queued = sub('persist', 'make', 'queue', 'savePlayQueue', id=[opening, echo], current=echo, position=500, expect='ok')
    account = nat('persist', 'make', 'user', 'POST', 'user', body={'userName': 'erin', 'name': 'Erin', 'email': 'erin@example.test', 'password': PASSWORDS['erin'], 'isAdmin': False}, status=200, hint='user')
    s.add('persist-fixture', 'restart', 'restart', restart, description='restart the product on the same data directory')

    # -- the same state after the restart: each read needs the case that made its state ------------------------------
    COMPANIONS[made] = [need(nat('persist', 'after', 'playlists', 'GET', 'playlist', params=LISTING, status=200, fields=PLAYLIST), made, filled)]
    COMPANIONS[filled] = [need(nat('persist', 'after', 'playlist-tracks', 'GET', lambda c: playlist(c) + '/tracks', params={'_start': 0, '_end': 20}, status=200, fields=['title', 'album']), filled)]
    COMPANIONS[rated] = [need(nat('persist', 'after', 'song-rating', 'GET', row, status=200, fields=['title', 'rating']), rated)]
    COMPANIONS[starred] = [need(nat('persist', 'after', 'song-star', 'GET', row, status=200, fields=['title', 'starred']), starred)]
    need(sub('persist', 'after', 'starred', 'getStarred2', unordered=['starred2.song', 'starred2.album', 'starred2.artist']), starred)
    COMPANIONS[station] = [need(nat('persist', 'after', 'radio', 'GET', station_path, status=200, fields=RADIO), station)]
    COMPANIONS[queued] = [need(sub('persist', 'after', 'queue', 'getPlayQueue'), queued)]
    COMPANIONS[account] = [need(nat('persist', 'after', 'users', 'GET', 'user', params={'_start': 0, '_end': 20, '_sort': 'userName', '_order': 'ASC'}, status=200, fields=USERS), account)]
    need(sub('persist', 'after', 'new-account', 'ping', 'erin'), account)
    sub('persist', 'after', 'old-account', 'ping', 'bob')
    nat('persist', 'after', 'library', 'GET', 'library/1', status=200, fields=['name', 'path', 'totalSongs', 'totalAlbums', 'totalArtists'])
    sub('persist', 'after', 'albums', 'getAlbumList2', type='alphabeticalByName', size=50)
    sub('persist', 'after', 'artists', 'getArtists')
