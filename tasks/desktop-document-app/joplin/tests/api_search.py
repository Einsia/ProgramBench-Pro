"""A mixed corpus that distinguishes positive, negative and combined search filters."""
import time

from harness import Ref, Suite, b64, project, aspects
from fixtures import png

CORPUS = [
    ('apple', 'Apple orchard', 'Red apples and green pears grow by the river.', 'garden', ['botany', 'red'], {}),
    ('pear', 'Pear harvest', 'Green pears for the autumn market.', 'garden', ['botany'], {'author': 'Grace'}),
    ('river', 'River walk', 'The blue river flows beside an oak tree.', 'travel', ['travel', 'blue'], {'author': 'Ada'}),
    ('trip', 'Pack a picnic', 'Bring apples, water, and a paper map.', 'travel', ['travel'], {'is_todo': 1, 'todo_due': 1768550400000}),
    ('done', 'Book tickets', 'Train tickets for the mountain trip.', 'travel', ['travel', 'done'], {'is_todo': 1, 'todo_completed': 1768478400000}),
    ('meeting', 'Project meeting', 'Review the draft plan and amber budget.', 'work', ['work', 'draft'], {'is_todo': 1}),
    ('report', 'Final report', 'The final amber budget has been approved.', 'work', ['work'], {'source_url': 'https://example.invalid/reports/final'}),
    ('cafe', 'Café résumé', 'A naïve café owner serves crème brûlée.', 'travel', ['café'], {}),
    ('chinese', '中文笔记', '中国的花园里有苹果和梨。', 'garden', ['资料'], {}),
    ('japanese', '日本語メモ', '庭でりんごを食べました。', 'garden', ['资料'], {}),
    ('punctuation', 'Literal [brackets]', 'A checklist: - [ ] pending and *stars* and hello@example.invalid', 'work', [], {}),
    ('location', 'Summit coordinates', 'Northern mountain survey and cold winds.', 'travel', [], {'latitude': 48.5, 'longitude': 8.25, 'altitude': 1200}),
    ('south', 'Southern coast', 'A warm coast by the sea.', 'travel', ['blue'], {'latitude': -33.9, 'longitude': 151.2, 'altitude': 15}),
    ('resource', 'Illustrated plan', 'A diagram for the field project.', 'work', ['draft'], {}),
]

QUERIES = [
    'apple', 'APPLES', 'pear', 'river', 'amber', 'mountain', 'fieldtok*', '"blue river"',
    '"red apples"', 'apple river', 'apple -river', 'any:1 apple mountain', 'any:0 apple river',
    'title:Apple', 'title:plan', 'title:report', 'body:river', 'body:budget', 'title:meeting body:draft',
    '-title:report amber', 'title:"Apple orchard"', 'title:Pic*',
    'tag:botany', 'tag:travel', 'tag:draft', 'tag:资料', 'tag:café', '-tag:travel fieldtoken',
    'tag:botany tag:red', 'any:1 tag:red tag:blue', 'tag:*', '-tag:*',
    'notebook:Garden', 'notebook:Travel', 'notebook:Work', 'notebook:Gar*', '-notebook:Work fieldtoken',
    'notebook:Garden apple', 'notebook:Travel type:todo',
    'type:todo', 'type:note', 'iscompleted:1', 'iscompleted:0 type:todo', '-iscompleted:1 type:todo',
    'due:20260101', 'due:20260116', '-due:20260117 type:todo',
    'created:20240101', '-created:20240105', 'created:20240103 -created:20240108',
    'updated:20250101', 'updated:20250106 -updated:20250110',
    'latitude:0', '-latitude:0', 'longitude:100', 'altitude:1000', 'latitude:40 -latitude:50',
    'sourceurl:https://example.invalid/reports/*', 'source:local.test',
    'resource:image/*', '-resource:image/*',
    'cafe', 'résumé', 'naive', '中文', '苹果', '日本語',
    '/[brackets]', '/"- [ ]"', 'draft tag:work -title:Final', 'any:1 title:Apple tag:blue',
    'fieldtoken -tag:botany -type:todo', 'fieldtoken -notebook:Garden',
]


def build():
    s = Suite('protocol-search', 'full text search and structured filters')
    def setup(c):
        for key, title in [('garden', 'Garden'), ('travel', 'Travel'), ('work', 'Work')]:
            c.call('POST', '/folders', body={'title': title}, save=key)
        for key, title, body, folder, tags, props in CORPUS:
            index = [row[0] for row in CORPUS].index(key)
            c.call('POST', '/notes', body={'title': title, 'body': body + '\n\nfieldtoken', 'parent_id': Ref(folder),
                'tags': ','.join(tags), 'source': 'local.test', 'user_created_time': 1704067200000 + index * 86400000,
                'user_updated_time': 1735689600000 + index * 86400000, **props}, save=key)
        c.call('POST', '/resources', multipart={'filename': 'diagram.png', 'base64': b64(png()),
               'props': {'title': 'Search diagram'}}, save='image')
        old = c.values['resource']['body']
        c.call('PUT', '/notes/{resource}', body={'body': old + '\n\n![Diagram](:/' + c.values['image']['id'] + ')',
               'user_updated_time': 1735689600000 + 13 * 86400000})
        # Search indexing is asynchronous. Require every member to be searchable
        # before freezing any query, including intentional no-match queries.
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            rows = c.all('/search', fields='id,title', query={'query': 'fieldtoken'})
            images=c.all('/search',fields='id',query={'query':'resource:image/*'})
            without=c.all('/search',fields='id',query={'query':'-resource:image/*'})
            all_ids={c.values[x[0]]['id'] for x in CORPUS}
            image_ids={c.values['resource']['id']}
            if {x['id'] for x in rows}==all_ids and {x['id'] for x in images}==image_ids and \
                    {x['id'] for x in without}==all_ids-image_ids:
                return
            time.sleep(.5)
        raise AssertionError('the mixed search corpus was not indexed completely')
    s.setup('corpus', setup)
    for i, query in enumerate(QUERIES + ['nonexistentxyzzword', 'title:Apple tag:blue', 'created:20990101']):
        def search(c, query=query):
            rows = c.all('/search', fields='id,title', query={'query': query})
            return {'matches': project(rows, ['id', 'title'], c)}
        s.add('query-' + str(i).zfill(3), 'Search for ' + repr(query), search,
              {'matches': 'The query returns the matching notes and excludes the other corpus members.'})
    for kind, queries in [('folder', ['Garden', 'Gar*', '*a*', 'TRAVEL']), ('tag', ['botany', 'bo*', '*r*', '资料'])]:
        for i, query in enumerate(queries):
            def entity_search(c, kind=kind, query=query):
                rows = c.all('/search', fields='title', query={'query': query, 'type': kind})
                return {'matches': project(rows, ['title'], c)}
            s.add(kind + '-' + str(i), 'Search ' + kind + ' titles for ' + query, entity_search,
                  {'matches': 'Non-note search respects title matching, wildcards and case.'})
    for direction in ('ASC', 'DESC'):
        def ordered(c, direction=direction):
            result = c.call('GET', '/search', query={'query': 'fieldtoken', 'fields': 'title', 'order_by': 'title',
                                                    'order_dir': direction, 'limit': 100})['body']
            return {'order': [x['title'] for x in result['items']]}
        s.add('sort-' + direction.lower(), 'Sort search results by title ' + direction, ordered,
              {'order': 'An explicit sort overrides search relevance order.'})
    for page in (1, 2, 5, 6):
        def page_search(c, page=page):
            result = c.call('GET', '/search', query={'query': 'fieldtoken', 'fields': 'title', 'order_by': 'title',
                                                    'limit': 3, 'page': page})['body']
            return aspects(**{'page': lambda: [x['title'] for x in result['items']],
                              'more': lambda: result['has_more']})
        s.add('page-' + str(page), 'Read search result page ' + str(page), page_search,
              {'page': 'Pagination slices the sorted matching notes.', 'more': 'The continuation flag follows the result boundary.'})
    s.request('missing-query', 'Reject a search without a query', 'GET', '/search', status=True, error=True,
              expected={'status': 400})
    s.request('post-search', 'Reject a write to the search route', 'POST', '/search', body={'query': 'apple'},
              status=True, error=True, expected={'status': 405})
    return s
