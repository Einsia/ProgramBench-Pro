'''Native collections without a module of their own: tags, genres, transcodings, players, scrobbles, missing files and plugins.

Lists are compared as sorted rows (or in order where the sort is the point), pages by their total and size. Anonymous and plugin refusals and every empty or filtered-out result are bound to a positive point of the same episode.'''
import json

import normalize

PAGE = {'_start': 0, '_end': 50}
TAG = ['tagName', 'tagValue', 'songCount', 'albumCount']
PLAYER = ['name', 'client', 'userName', 'scrobbleEnabled', 'reportRealPath', 'maxBitRate']
TRANSCODING = ['name', 'targetFormat', 'defaultBitRate']
COMPANIONS = {}
DEPENDS = {}


def listing(s, family, scenario, step, path, user='admin', params=None, fields=None, shape='sorted', anonymous=False, status=200):
    def action(c, relaxed=False):
        assert not relaxed, 'collection checks are scored cases'
        answer = c.native('GET', path, user, params=params, anonymous=anonymous)
        assert answer['status'] == status, '%s: expected %s, received %s' % (path, status, answer['status'])
        if answer['status'] >= 400:
            return {'status': answer['status']}
        body, total = answer['body'], answer['headers'].get('x-total-count')
        assert isinstance(body, list), 'expected a list'
        if shape == 'count':
            return {'status': 200, 'total': total, 'count': len(body)}
        rows = normalize.project(body, fields)
        if shape == 'sorted':
            rows = sorted(rows, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
        return {'status': 200, 'total': total, 'rows': c.norm.clean(rows, family)}
    return s.add(family, scenario, step, action, description='GET %s as %s' % (path, 'nobody' if anonymous else user))


def bind(cid, positive):
    COMPANIONS[cid] = [positive]
    return cid


def build(s):
    # -- tags ---------------------------------------------------------------------------------------------------
    tags = listing(s, 'native-tags', 'list', 'admin', 'tag', params=PAGE, fields=TAG)
    listing(s, 'native-tags', 'list', 'bob', 'tag', 'bob', params=PAGE, fields=TAG)
    bind(listing(s, 'native-tags', 'list', 'anonymous', 'tag', params=PAGE, anonymous=True, status=401), tags)
    listing(s, 'native-tags', 'filter', 'genre', 'tag', params={**PAGE, 'tag_name': 'genre'}, fields=TAG)
    bind(listing(s, 'native-tags', 'filter', 'none', 'tag', params={**PAGE, 'tag_name': 'nosuchtag'}, shape='count'), tags)
    for step, start, end in (('first', 0, 5), ('second', 5, 10), ('last', 10, 15)):
        listing(s, 'native-tags', 'page', step, 'tag', params={'_start': start, '_end': end}, shape='count')
    bind(listing(s, 'native-tags', 'page', 'past-end', 'tag', params={'_start': 50, '_end': 60}, shape='count'), tags)

    # -- genres (sorted lists and pages are read by the browsing module) -----------------------------------------------
    genres = listing(s, 'native-genres-more', 'list', 'bob', 'genre', 'bob', params=PAGE, fields=['name'])
    bind(listing(s, 'native-genres-more', 'list', 'anonymous', 'genre', params=PAGE, anonymous=True, status=401), genres)

    # -- transcodings (listed only: the image has no encoder) --------------------------------------------------------
    codecs = listing(s, 'native-transcodings', 'list', 'admin', 'transcoding', params=PAGE, fields=TRANSCODING)
    listing(s, 'native-transcodings', 'list', 'bob', 'transcoding', 'bob', params=PAGE, fields=TRANSCODING)
    bind(listing(s, 'native-transcodings', 'list', 'anonymous', 'transcoding', params=PAGE, anonymous=True, status=401), codecs)
    for step, start, end in (('first', 0, 2), ('second', 2, 4)):
        listing(s, 'native-transcodings', 'page', step, 'transcoding', params={'_start': start, '_end': end}, shape='count')
    bind(listing(s, 'native-transcodings', 'page', 'past-end', 'transcoding', params={'_start': 4, '_end': 6}, shape='count'), codecs)

    # -- players (an account sees only its own) ------------------------------------------------------------------------
    players = listing(s, 'native-players', 'list', 'admin', 'player', params=PAGE, fields=PLAYER)
    bind(listing(s, 'native-players', 'list', 'bob', 'player', 'bob', params=PAGE, shape='count'), players)
    bind(listing(s, 'native-players', 'list', 'anonymous', 'player', params=PAGE, anonymous=True, status=401), players)
    listing(s, 'native-players', 'filter', 'name', 'player', params={**PAGE, 'name': 'pbp'}, shape='count')
    bind(listing(s, 'native-players', 'filter', 'no-match', 'player', params={**PAGE, 'name': 'zzzz'}, shape='count'), players)

    # -- collections that start empty -------------------------------------------------------------------------------------
    for kind in ('scrobble', 'missing'):
        for user in ('admin', 'bob'):
            bind(listing(s, 'native-empty', kind, user, kind, user, params=PAGE, shape='count'), players)

    # -- plugins are off: not found for an administrator, forbidden for everybody else -------------------------------
    bind(listing(s, 'native-plugins', 'list', 'admin', 'plugin', params=PAGE, status=404), tags)
    bind(listing(s, 'native-plugins', 'list', 'bob', 'plugin', 'bob', params=PAGE, status=403), tags)
