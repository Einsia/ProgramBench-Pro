'''Cookbooks of the household: saved recipe filters with a name, slug, position and visibility.

Cookbooks are created (slug derived and de-duplicated), read by id and by slug, listed, replaced one at a time and in
bulk (positions), and deleted. The recipes a cookbook selects are read through the recipe list with its cookbook filter,
so the filter text is behaviour, not decoration. Invalid filters and missing ids are rejected.
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'


def build(s):
    a = s.api
    sc = 'cookbooks'
    base = 'households/cookbooks'
    fx = 'cookbooks-fixture'
    # Recipes the filters select from: tags and a category through the organizer endpoints.
    a(fx, sc, 'tag-quick', 'POST', 'organizers/tags', body={'name': 'quick'}, save='tag-quick')
    a(fx, sc, 'tag-slow', 'POST', 'organizers/tags', body={'name': 'slow'}, save='tag-slow')
    a(fx, sc, 'cat-dinner', 'POST', 'organizers/categories', body={'name': 'Dinner'}, save='cat-dinner')
    for slug, name in (('omelette', 'Omelette'), ('stew', 'Beef Stew'), ('salad', 'Green Salad')):
        a(fx, sc, 'recipe-' + slug, 'POST', 'recipes', body={'name': name})
    a(fx, sc, 'tag-omelette', 'PATCH', 'recipes/omelette',
      body=lambda c: {'tags': [c.state['tag-quick']], 'recipeCategory': [c.state['cat-dinner']]})
    a(fx, sc, 'tag-stew', 'PATCH', 'recipes/beef-stew',
      body=lambda c: {'tags': [c.state['tag-slow']], 'recipeCategory': [c.state['cat-dinner']]})
    a(fx, sc, 'tag-salad', 'PATCH', 'recipes/green-salad', body=lambda c: {'tags': [c.state['tag-quick']]})

    fam = 'cookbooks'
    a(fam, sc, 'empty-list', 'GET', base)
    a(fam, sc, 'create-weeknight', 'POST', base, status=201, save='weeknight',
      body={'name': 'Weeknight', 'description': 'Fast dinners', 'public': False,
            'queryFilterString': 'tags.name IN ["quick"]'})
    a(fam, sc, 'create-same-name', 'POST', base, status=201, save='weeknight2', body={'name': 'Weeknight'})
    a(fam, sc, 'create-dinner', 'POST', base, status=201, save='dinner',
      body={'name': 'Dinner Party', 'public': True, 'queryFilterString': 'recipeCategory.name = "Dinner"'})
    a(fam, sc, 'create-explicit-slug', 'POST', base, status=201, save='custom',
      body={'name': 'Sunday', 'slug': 'sunday-roast'})
    a(fam, sc, 'create-no-name', 'POST', base, body={'description': 'x'}, status=422)
    a(fam, sc, 'create-bad-filter', 'POST', base, body={'name': 'Broken', 'queryFilterString': 'tags.name ~~ x'},
      status=None)
    a(fam, sc, 'create-unknown-field', 'POST', base, body={'name': 'Stray', 'queryFilterString': 'nosuch = 1'},
      status=None)
    a(fam, sc, 'list', 'GET', base, params={'orderBy': 'position', 'orderDirection': 'asc'})
    a(fam, sc, 'list-by-name', 'GET', base, params={'orderBy': 'name', 'orderDirection': 'desc'})
    a(fam, sc, 'list-page', 'GET', base, params={'orderBy': 'name', 'page': 2, 'perPage': 2})
    a(fam, sc, 'list-filter-public', 'GET', base, params={'queryFilter': 'public = true'})
    a(fam, sc, 'read-by-id', 'GET', pathref(base + '/{id}', id=Ref('weeknight', 'id')))
    a(fam, sc, 'read-by-slug', 'GET', base + '/weeknight')
    a(fam, sc, 'read-second-slug', 'GET', base + '/weeknight-1')
    a(fam, sc, 'read-explicit-slug', 'GET', base + '/sunday-roast')
    a(fam, sc, 'read-missing-id', 'GET', base + '/' + MISSING, status=404)
    a(fam, sc, 'read-missing-slug', 'GET', base + '/no-such-book', status=404)

    # The recipes a cookbook selects: the recipe list filtered by the cookbook (id or slug).
    rp = {'orderBy': 'name', 'orderDirection': 'asc'}
    a(fam, sc, 'recipes-weeknight', 'GET', 'recipes', fields=['slug'],
      params=lambda c: dict(rp, cookbook=c.state['weeknight']['id']))
    a(fam, sc, 'recipes-weeknight-slug', 'GET', 'recipes', fields=['slug'],
      params=dict(rp, cookbook='weeknight'))
    a(fam, sc, 'recipes-dinner', 'GET', 'recipes', fields=['slug'],
      params=lambda c: dict(rp, cookbook=c.state['dinner']['id']))
    a(fam, sc, 'recipes-no-filter', 'GET', 'recipes', fields=['slug'],
      params=lambda c: dict(rp, cookbook=c.state['weeknight2']['id']))
    a(fam, sc, 'recipes-missing-book', 'GET', 'recipes', params=dict(rp, cookbook=MISSING), status=None)

    # Replace one cookbook: name, description, filter, visibility; the slug follows the given value.
    a(fam, sc, 'update-one', 'PUT', pathref(base + '/{id}', id=Ref('weeknight', 'id')), save='weeknight-updated',
      body=lambda c: dict(c.state['weeknight'], name='Quick Weeknight', description='Under 30 minutes',
                          queryFilterString='tags.name IN ["quick", "slow"]', public=True))
    a(fam, sc, 'after-update', 'GET', pathref(base + '/{id}', id=Ref('weeknight', 'id')))
    a(fam, sc, 'recipes-after-update', 'GET', 'recipes', fields=['slug'],
      params=lambda c: dict(rp, cookbook=c.state['weeknight']['id']))
    a(fam, sc, 'update-missing', 'PUT', base + '/' + MISSING, body={'name': 'Ghost'}, status=None)
    a(fam, sc, 'update-no-name', 'PUT', pathref(base + '/{id}', id=Ref('dinner', 'id')),
      body={'description': 'x'}, status=422)

    # Bulk update: positions reordered in one request.
    a(fam, sc, 'reorder', 'PUT', base, status=None,
      body=lambda c: [dict(c.state['custom'], position=1), dict(c.state['dinner'], position=2),
                      dict(c.state['weeknight-updated'], position=3), dict(c.state['weeknight2'], position=4)])
    a(fam, sc, 'after-reorder', 'GET', base, params={'orderBy': 'position', 'orderDirection': 'asc'},
      fields=['slug', 'position'])

    # Permissions: a member without organizing rights; anonymous access.
    a(fam, sc, 'anonymous-list', 'GET', base, actor=None, status=401)
    a(fam, sc, 'anonymous-create', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)

    # Delete.
    a(fam, sc, 'delete', 'DELETE', pathref(base + '/{id}', id=Ref('weeknight2', 'id')))
    a(fam, sc, 'after-delete', 'GET', pathref(base + '/{id}', id=Ref('weeknight2', 'id')), status=404)
    a(fam, sc, 'delete-missing', 'DELETE', base + '/' + MISSING, status=None)
    a(fam, sc, 'final-list', 'GET', base, params={'orderBy': 'position', 'orderDirection': 'asc'},
      fields=['slug', 'name'])
