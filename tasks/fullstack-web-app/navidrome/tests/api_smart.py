'''Smart playlists: rule files (.nsp) in the music folder become read-only playlists whose songs follow their rules.

The fixture adds rule files (one of them broken) and runs a full scan. Each playlist is read through both APIs; the
rules on ratings, favourites and plays are read again after the matching change, once the product has evaluated them
anew (it re-evaluates a rule playlist some seconds after the songs changed). Empty playlists are bound to the read that
shows the same rule matching a song.'''
import base64
import json
import time

import normalize
from api_browse import song_of

PAGE = {'_start': 0, '_end': 50, '_sort': 'title', '_order': 'ASC'}
LISTING = {'_start': 0, '_end': 50, '_sort': 'name', '_order': 'ASC'}
RULES = {
    'Rock.nsp': {'name': 'Rock Songs', 'comment': 'genre rule', 'all': [{'is': {'genre': 'Rock'}}], 'sort': 'title', 'order': 'asc'},
    'Years.nsp': {'name': 'Nineties To Oughts', 'all': [{'inTheRange': {'year': [1995, 2005]}}], 'sort': 'year', 'order': 'desc'},
    'Rated.nsp': {'name': 'Well Rated', 'all': [{'gt': {'rating': 3}}], 'sort': 'title'},
    'Loved.nsp': {'name': 'Loved', 'all': [{'is': {'loved': True}}], 'sort': 'title'},
    'Played.nsp': {'name': 'Played Once', 'all': [{'gt': {'playcount': 0}}], 'sort': 'title'},
    'Limited.nsp': {'name': 'First Three With E', 'all': [{'contains': {'title': 'e'}}], 'sort': 'title', 'limit': 3},
    'Any.nsp': {'name': 'Jazz Or Pop', 'any': [{'is': {'genre': 'Jazz'}}, {'is': {'genre': 'Pop'}}], 'sort': 'title'},
    'Contains.nsp': {'name': 'Titles With E', 'all': [{'contains': {'title': 'e'}}, {'notContains': {'title': 'Single'}}], 'sort': 'title'},
    'Starts.nsp': {'name': 'Starting With S', 'all': [{'startsWith': {'title': 's'}}], 'sort': 'title', 'order': 'desc'},
}
BROKEN = 'Broken.nsp'
SUMMARY = ['name', 'songCount', 'path', 'sync', 'rules', 'public', 'ownerName']
COMPANIONS = {}
DEPENDS = {}


def prepare(c, relaxed=False):
    for name, rule in [*RULES.items(), (BROKEN, None)]:
        data = (json.dumps(rule) if rule else '{not json').encode()
        answer = c.call({'op': 'library_put', 'path': 'Playlists/Smart/' + name, 'base64': base64.b64encode(data).decode()})
        assert answer.get('size') == len(data), 'library_put ' + name
    c.rescan(True)
    time.sleep(2.0)
    rows = c.native('GET', 'playlist', params=LISTING)['body']
    c.state['smart'] = {x['name']: x['id'] for x in rows}


def smart(name):
    return lambda c: c.state['smart'][name]


def entries(c, name, user='admin'):
    reply = c.reply(c.subsonic('getPlaylist', user, id=smart(name)(c)))
    return (reply.get('playlist') or {}).get('entry') or []


def view(c, name, rows):
    # Songs that tie on the sort key come back in an order the rule does not fix: the keys keep their order, the
    # songs are compared as a set. A title sort has no ties.
    rule = next(r for r in RULES.values() if r['name'] == name)
    key = rule.get('sort', 'title')
    titles = [c.norm.clean({'title': x.get('title')}, 'song') for x in rows]
    if key == 'title':
        return {'titles': titles}
    return {'keys': [x.get(key) for x in rows], 'titles': normalize.unordered(titles)}


def playlist(s, step, name):
    def action(c, relaxed=False):
        assert not relaxed, 'playlist checks are scored cases'
        return view(c, name, entries(c, name))
    return s.add('smart', 'playlist', step, action, description='subsonic getPlaylist of the rule playlist ' + name)


def refreshed(s, step, name):
    '''The playlist once the product has evaluated its rule again: read until it lists a song (at most 20 seconds),
    then once more after a pause.'''
    def action(c, relaxed=False):
        assert not relaxed, 'playlist checks are scored cases'
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline and not entries(c, name):
            time.sleep(1.0)
        time.sleep(1.5)
        return view(c, name, entries(c, name))
    return s.add('smart', 'refreshed', step, action, description='subsonic getPlaylist of %s after the songs changed' % name)


def listing(c, relaxed=False):
    assert not relaxed, 'playlist checks are scored cases'
    rows = c.native('GET', 'playlist', params=LISTING)['body']
    rows = [x for x in rows if x.get('name') != 'Favourites']
    return {'playlists': c.norm.clean(sorted(normalize.project(rows, SUMMARY), key=lambda x: str(x.get('name'))), 'playlist')}


def build(s):
    nat, sub = s.nat, s.sub
    nat('smart-fixture', 'library', 'songs', 'GET', 'song', params=PAGE, save='songs')
    s.add('smart-fixture', 'library', 'rule-files', prepare, description='add the rule files to the library and run a full scan')
    echo, middle, intro = song_of('Echo'), song_of('Middle'), song_of('Intro')

    # -- the rule playlists as both APIs list them (the broken rule file makes none) -------------------------------
    listed = sub('smart', 'list', 'subsonic', 'getPlaylists', unordered=['playlists.playlist'])
    s.add('smart', 'list', 'native', listing, description='GET playlist: the rule playlists with their rules')

    # -- the songs of each rule ---------------------------------------------------------------------------------------
    reads = {}
    for name, rule in RULES.items():
        reads[rule['name']] = playlist(s, name.removesuffix('.nsp').lower(), rule['name'])
    nat('smart', 'tracks', 'native', 'GET', lambda c: 'playlist/%s/tracks' % smart('Jazz Or Pop')(c),
        params={'_start': 0, '_end': 50}, status=200, fields=['title', 'album', 'artist'])

    # -- the rules follow ratings, favourites and plays ---------------------------------------------------------------
    for step, op, query, name in (('rate', 'setRating', {'id': echo, 'rating': 5}, 'Well Rated'),
                                  ('love', 'star', {'id': middle}, 'Loved'),
                                  ('play', 'scrobble', {'id': intro}, 'Played Once')):
        changed = sub('smart', 'change', step, op, expect='ok', **query)
        after = need_after(refreshed(s, step, name), changed)
        COMPANIONS[changed] = [after]
        COMPANIONS[reads[name]] = [after]

    # -- rule playlists are read-only and belong to the administrator ---------------------------------------------------
    COMPANIONS[sub('smart', 'read-only', 'subsonic-add', 'updatePlaylist', playlistId=smart('Rock Songs'), songIdToAdd=echo,
                   expect=50)] = [reads['Rock Songs']]
    COMPANIONS[nat('smart', 'read-only', 'native-add', 'POST', lambda c: 'playlist/%s/tracks' % smart('Rock Songs')(c),
                   body={'ids': [echo]}, status=409)] = [reads['Rock Songs']]
    COMPANIONS[sub('smart', 'list', 'as-bob', 'getPlaylists', 'bob', unordered=['playlists.playlist'])] = [listed]


def need_after(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid
