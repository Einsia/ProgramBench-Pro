'''Native sorting and filters: the collections sorted by fields that have no case yet, sorted pages and the id filters.

Rows that tie on the sort key come back in an order the product does not fix. A sorted observation therefore keeps the sort key values in the order returned (tied rows have equal keys, so their order cannot show) and the members as a set. A product that ignores the sort returns another key sequence.'''
import normalize
from api_browse import song_of

PAGE = {'_start': 0, '_end': 50}
TITLES = {**PAGE, '_sort': 'title', '_order': 'ASC'}
NAMES = {**PAGE, '_sort': 'name', '_order': 'ASC'}
SONGS = [('album', 'album'), ('artist', 'artist'), ('album_artist', 'albumArtist'), ('year', 'year'), ('track_number', 'trackNumber'),
         ('disc_number', 'discNumber'), ('duration', 'duration')]
ALBUMS = [('song_count', 'songCount'), ('duration', 'duration'), ('size', 'size'), ('min_year', 'minYear')]
ARTISTS = [('album_count', 'albumCount'), ('song_count', 'songCount'), ('size', 'size')]
LABEL = {'song': 'title', 'album': 'name', 'artist': 'name'}
UNKNOWN = 'F' * 22
COMPANIONS = {}
DEPENDS = {}


def need(cid, *earlier):
    DEPENDS[cid] = list(earlier)
    return cid


def ordered(s, kind, scenario, step, sort, field, order='ASC', params=None, members=True):
    def action(c, relaxed=False):
        assert not relaxed, 'sort checks are scored cases'
        answer = c.native('GET', kind, 'admin', params={**PAGE, '_sort': sort, '_order': order, **(params or {})})
        assert answer['status'] == 200, '%s sorted by %s: HTTP %s' % (kind, sort, answer['status'])
        rows = answer['body']
        assert isinstance(rows, list), 'expected a list'
        seen = {'status': 200, 'total': answer['headers'].get('x-total-count')}
        if field:
            seen['keys'] = [c.norm.clean({field: row.get(field)}, kind) for row in rows]
        if members:
            seen['members'] = normalize.unordered([c.norm.clean({LABEL[kind]: row.get(LABEL[kind])}, kind) for row in rows])
        return seen
    return s.add('sorts-' + kind, scenario, step, action, description='GET %s sorted by %s %s' % (kind, sort, order))


def album_named(name):
    return lambda c: next(a['id'] for a in c.state['sort-albums'] if a['name'] == name)


def genre_named(name):
    return lambda c: next(g['id'] for g in c.state['sort-genres'] if g['name'] == name)


def build(s):
    nat, sub = s.nat, s.sub
    nat('sorts-fixture', 'library', 'songs', 'GET', 'song', params=TITLES, save='songs')
    nat('sorts-fixture', 'library', 'albums', 'GET', 'album', params=NAMES, save='sort-albums')
    nat('sorts-fixture', 'library', 'genres', 'GET', 'genre', params=NAMES, save='sort-genres')

    # -- sorting by fields that have no case yet; an unknown field is ignored ------------------------------------
    for kind, table in (('song', SONGS), ('album', ALBUMS), ('artist', ARTISTS)):
        for sort, field in table:
            for order in ('ASC', 'DESC'):
                ordered(s, kind, 'sort', '%s-%s' % (sort.replace('_', '-'), order.lower()), sort, field, order)
        ordered(s, kind, 'sort', 'unknown-field', 'bogus', None)

    # -- sorted pages: only the keys, the rows at a page border depend on how ties are broken ------------------
    ordered(s, 'song', 'page', 'year-desc-second', 'year', 'year', 'DESC', params={'_start': 5, '_end': 10}, members=False)
    ordered(s, 'album', 'page', 'size-asc-second', 'size', 'size', 'ASC', params={'_start': 3, '_end': 6}, members=False)
    ordered(s, 'song', 'page', 'duration-asc-past-end', 'duration', 'duration', params={'_start': 50, '_end': 60})

    # -- ratings and play counts exist only after they have been made --------------------------------------------
    echo, opening, middle = song_of('Echo'), song_of('Opening'), song_of('Middle')
    writes = {'rate': [], 'play': []}
    for scenario, step, op, query in (('rate', 'echo', 'setRating', {'id': echo, 'rating': 5}),
                                      ('rate', 'opening', 'setRating', {'id': opening, 'rating': 3}),
                                      ('rate', 'middle', 'setRating', {'id': middle, 'rating': 1}),
                                      ('play', 'opening-once', 'scrobble', {'id': opening}),
                                      ('play', 'opening-twice', 'scrobble', {'id': opening}),
                                      ('play', 'echo-once', 'scrobble', {'id': echo})):
        writes[scenario].append(sub('sorts-annotated', scenario, step, op, expect='ok', **query))
    for (sort, field), made in zip((('rating', 'rating'), ('play_count', 'playCount')), (writes['rate'], writes['play'])):
        reads = [need(ordered(s, 'song', 'annotated', '%s-%s' % (sort.replace('_', '-'), order.lower()), sort, field, order), *made)
                 for order in ('ASC', 'DESC')]
        for cid in made:
            COMPANIONS[cid] = [reads[0]]

    # -- filters by album, genre and year; the empty answers are bound to a positive filter -----------------------
    positive = nat('sorts-filter', 'song', 'album', 'GET', 'song', params={**TITLES, 'album_id': album_named('Third Album')}, status=200, fields=['title'])
    for step, query in (('genre-jazz', {'genre_id': genre_named('Jazz')}), ('genre-rock', {'genre_id': genre_named('Rock')}),
                        ('year-2001', {'year': 2001}), ('year-1999', {'year': 1999})):
        nat('sorts-filter', 'song', step, 'GET', 'song', params={**TITLES, **query}, status=200, fields=['title'])
    for step, query in (('unknown-album', {'album_id': UNKNOWN}), ('unknown-genre', {'genre_id': UNKNOWN}), ('year-2099', {'year': 2099})):
        COMPANIONS[nat('sorts-filter', 'song', step, 'GET', 'song', params={**TITLES, **query}, status=200, fields=['title'])] = [positive]
    jazz = nat('sorts-filter', 'album', 'genre-jazz', 'GET', 'album', params={**NAMES, 'genre_id': genre_named('Jazz')}, status=200, fields=['name'])
    nat('sorts-filter', 'album', 'genre-rock', 'GET', 'album', params={**NAMES, 'genre_id': genre_named('Rock')}, status=200, fields=['name'])
    COMPANIONS[nat('sorts-filter', 'album', 'unknown-genre', 'GET', 'album', params={**NAMES, 'genre_id': UNKNOWN}, status=200, fields=['name'])] = [jazz]
