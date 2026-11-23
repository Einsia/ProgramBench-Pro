'''Recipe organizers: categories, tags and tools of the group.

Each kind is created, read by id and by slug, listed (search, ordering, pagination), updated, merged and deleted; the
"empty" lists name the organizers no recipe uses. Validation and missing-item errors are part of the contract.
'''
from harness import Ref, pathref

KINDS = [('categories', 'category'), ('tags', 'tag'), ('tools', 'tool')]


def build(s):
    a = s.api
    for kind, single in KINDS:
        base = 'organizers/' + kind
        fam = 'org-' + kind
        one = lambda key, tail='': pathref(base + '/{i}' + tail, i=Ref(key, 'id'))
        extra = {'householdsWithTool': []} if kind == 'tools' else {}
        sc = 'create'
        a(fam, sc, 'first', 'POST', base, body={'name': 'Weeknight Dinner', **extra}, status=201, save=single + '1')
        a(fam, sc, 'unicode', 'POST', base, body={'name': 'Crème Brûlée & Co'}, status=201, save=single + '2')
        a(fam, sc, 'third', 'POST', base, body={'name': 'Zesty Lunch'}, status=201, save=single + '3')
        a(fam, sc, 'duplicate-name', 'POST', base, body={'name': 'Weeknight Dinner'}, status=None)
        a(fam, sc, 'missing-name', 'POST', base, body={}, status=422)
        a(fam, sc, 'name-not-string', 'POST', base, body={'name': ['x']}, status=422)
        a(fam, sc, 'not-json', 'POST', base, raw='name=x', content_type='application/x-www-form-urlencoded', status=422)
        a(fam, sc, 'anonymous', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)
        sc = 'read'
        a(fam, sc, 'by-id', 'GET', one(single + '1'))
        a(fam, sc, 'by-slug', 'GET', base + '/slug/weeknight-dinner')
        a(fam, sc, 'by-slug-unicode', 'GET', pathref(base + '/slug/{s}', s=Ref(single + '2', 'slug')))
        a(fam, sc, 'id-missing', 'GET', base + '/00000000-0000-4000-8000-000000000000', status=None)
        a(fam, sc, 'id-malformed', 'GET', base + '/not-a-uuid', status=422)
        a(fam, sc, 'anonymous', 'GET', base, actor=None, status=401)
        sc = 'list'
        a(fam, sc, 'all', 'GET', base)
        a(fam, sc, 'per-page-1', 'GET', base, params={'perPage': 1, 'orderBy': 'name', 'orderDirection': 'asc'})
        a(fam, sc, 'page-2', 'GET', base, params={'perPage': 1, 'page': 2, 'orderBy': 'name', 'orderDirection': 'asc'})
        a(fam, sc, 'page-past-end', 'GET', base, params={'perPage': 2, 'page': 9, 'orderBy': 'name'})
        a(fam, sc, 'name-desc', 'GET', base, params={'orderBy': 'name', 'orderDirection': 'desc'})
        a(fam, sc, 'search', 'GET', base, params={'search': 'lunch'})
        a(fam, sc, 'search-none', 'GET', base, params={'search': 'zzzz-nothing'})
        a(fam, sc, 'filter-name', 'GET', base, params={'queryFilter': 'name = "Zesty Lunch"'})
        a(fam, sc, 'filter-like', 'GET', base, params={'queryFilter': 'name LIKE "%Dinner%"'})
        a(fam, sc, 'filter-bad', 'GET', base, params={'queryFilter': 'nosuchfield = 1'}, status=None)
        a(fam, sc, 'order-bad', 'GET', base, params={'orderBy': 'nosuchfield'}, status=None)
        a(fam, sc, 'per-page-all', 'GET', base, params={'perPage': -1, 'orderBy': 'name'})
        a(fam, sc, 'empty', 'GET', base + '/empty')
        sc = 'update'
        a(fam, sc, 'rename', 'PUT', one(single + '3'), body={'name': 'Zesty Supper', **extra})
        a(fam, sc, 'read-renamed', 'GET', one(single + '3'))
        a(fam, sc, 'new-slug', 'GET', base + '/slug/zesty-supper', status=None)
        a(fam, sc, 'missing-name', 'PUT', one(single + '3'), body={}, status=422)
        if kind == 'tools':
            # Categories and tags answer an unknown id here with an unhandled server error (not a contract).
            a(fam, sc, 'missing-item', 'PUT', base + '/00000000-0000-4000-8000-000000000000', body={'name': 'Ghost'}, status=404)
        # Give the merge a real downstream association. Without this positive
        # corpus, deleting the source organizer would not be distinguishable
        # from correctly migrating its recipe references.
        usefam = fam + '-fixture'
        slug = 'merge-' + single
        a(usefam, 'merge-use', 'create-' + single, 'POST', 'recipes', body={'name': 'Merge ' + single})
        if kind == 'categories':
            merge_body = lambda c, single=single: {'recipeCategory': [c.state[single + '1'], c.state[single + '2']]}
        elif kind == 'tags':
            merge_body = lambda c, single=single: {'tags': [c.state[single + '1'], c.state[single + '2']]}
        else:
            merge_body = lambda c, single=single: {'tools': [c.state[single + '1'], c.state[single + '2']]}
        a(usefam, 'merge-use', 'associate-' + single, 'PATCH', 'recipes/' + slug, body=merge_body)
        sc = 'merge'
        a(fam, sc, 'merge', 'POST', base + '/merge', status=None,
          body=lambda c, single=single: {'fromId': c.state[single + '2']['id'], 'toId': c.state[single + '1']['id']})
        a(fam, sc, 'merge-missing', 'POST', base + '/merge', body={'fromId': '00000000-0000-4000-8000-000000000000'}, status=422)
        a(fam, sc, 'after-merge', 'GET', base, params={'orderBy': 'name'})
        a(fam, sc, 'associated-recipe-after', 'GET', 'recipes/' + slug,
          fields=['name', 'recipeCategory' if kind == 'categories' else 'tags' if kind == 'tags' else 'tools'])
        sc = 'delete'
        a(fam, sc, 'delete', 'DELETE', one(single + '3'))
        a(fam, sc, 'gone', 'GET', one(single + '3'), status=None)
        a(fam, sc, 'again', 'DELETE', one(single + '3'), status=None)
        a(fam, sc, 'list-after', 'GET', base, params={'orderBy': 'name'})
