'''Recipes of the household: create, read, list, update, patch, duplicate and delete.

Recipes are addressed by slug, which follows the name and gets a numeric suffix on collision. A full recipe carries
ingredients, instructions, notes, nutrition, settings and organizer links; PUT replaces it, PATCH merges top-level
fields. Listing covers search, ordering, pagination and organizer filters. Validation and missing-item errors are part
of the contract.
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'


def full(c, name, slug, **extra):
    '''A complete recipe body linked to the organizers created at the start.'''
    body = {
        'name': name, 'slug': slug, 'description': 'A test recipe', 'recipeServings': 4,
        'recipeYieldQuantity': 2, 'recipeYield': 'loaves', 'totalTime': '1 hour', 'prepTime': '15 minutes',
        'performTime': '45 minutes', 'orgURL': 'https://example.com/recipe',
        'recipeIngredient': [
            {'quantity': 2, 'note': 'ripe', 'food': c.state['food'], 'unit': c.state['unit']},
            {'quantity': 1, 'note': 'a pinch of salt'},
            {'title': 'Topping', 'quantity': 0, 'note': 'sugar to taste'},
        ],
        'recipeInstructions': [{'title': 'Prep', 'text': 'Mash the bananas.'}, {'text': 'Bake for 45 minutes.'}],
        'notes': [{'title': 'Storage', 'text': 'Keeps three days.'}],
        'nutrition': {'calories': '250', 'fatContent': '9', 'proteinContent': '4'},
        'settings': {'public': True, 'showNutrition': True, 'showAssets': False, 'landscapeView': False,
                     'disableComments': False, 'locked': False},
        'recipeCategory': [c.state['cat']], 'tags': [c.state['tag']], 'tools': [c.state['tool']],
        'extras': {'source': 'family'},
    }
    body.update(extra)
    return body


def build(s):
    a = s.api
    base, fam = 'recipes', 'recipes'

    sc = 'organizers'
    a(fam, sc, 'category', 'POST', 'organizers/categories', body={'name': 'Breakfast'}, status=201, save='cat')
    a(fam, sc, 'tag', 'POST', 'organizers/tags', body={'name': 'Quick'}, status=201, save='tag')
    a(fam, sc, 'tool', 'POST', 'organizers/tools', body={'name': 'Oven'}, status=201, save='tool')
    a(fam, sc, 'food', 'POST', 'foods', body={'name': 'banana'}, status=201, save='food')
    a(fam, sc, 'unit', 'POST', 'units', body={'name': 'cup', 'abbreviation': 'c'}, status=201, save='unit')

    sc = 'create'
    a(fam, sc, 'banana-bread', 'POST', base, body={'name': 'Banana Bread'}, status=201)
    a(fam, sc, 'tomato-soup', 'POST', base, body={'name': 'Tomato Soup'}, status=201)
    a(fam, sc, 'apple-pie', 'POST', base, body={'name': 'Apple Pie'}, status=201)
    a(fam, sc, 'collision', 'POST', base, body={'name': 'Tomato Soup'}, status=201)
    a(fam, sc, 'collision-again', 'POST', base, body={'name': 'Tomato Soup'}, status=201)
    a(fam, sc, 'punctuation', 'POST', base, body={'name': "Grandma's Café: Best Pie!"}, status=201)
    a(fam, sc, 'missing-name', 'POST', base, body={}, status=422)
    a(fam, sc, 'name-not-string', 'POST', base, body={'name': ['x']}, status=422)
    a(fam, sc, 'anonymous', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)

    sc = 'read'
    a(fam, sc, 'new', 'GET', base + '/banana-bread')
    a(fam, sc, 'collision', 'GET', base + '/tomato-soup-1')
    a(fam, sc, 'punctuation', 'GET', base + '/grandmas-cafe-best-pie')
    a(fam, sc, 'missing', 'GET', base + '/no-such-recipe', status=404)
    a(fam, sc, 'anonymous', 'GET', base + '/banana-bread', actor=None, status=None)

    sc = 'replace'
    a(fam, sc, 'full', 'PUT', base + '/banana-bread', body=lambda c: full(c, 'Banana Bread', 'banana-bread'))
    a(fam, sc, 'read-full', 'GET', base + '/banana-bread')
    a(fam, sc, 'rename', 'PUT', base + '/apple-pie',
      body={'name': 'Apple Crumble', 'slug': 'apple-pie', 'description': 'Crumbly'})
    a(fam, sc, 'read-renamed', 'GET', base + '/apple-crumble')
    a(fam, sc, 'old-slug-gone', 'GET', base + '/apple-pie', status=404)
    a(fam, sc, 'missing', 'PUT', base + '/no-such-recipe', body={'name': 'X', 'slug': 'x'}, status=None)
    a(fam, sc, 'bad-servings', 'PUT', base + '/tomato-soup', body={'name': 'Tomato Soup', 'recipeServings': 'many'},
      status=422)

    sc = 'patch'
    a(fam, sc, 'description', 'PATCH', base + '/tomato-soup', body={'description': 'Warm and red'})
    a(fam, sc, 'servings', 'PATCH', base + '/tomato-soup', body={'recipeServings': 6, 'recipeYield': 'bowls'})
    a(fam, sc, 'read-patched', 'GET', base + '/tomato-soup')
    a(fam, sc, 'rename', 'PATCH', base + '/tomato-soup-2', body={'name': 'Gazpacho'})
    a(fam, sc, 'read-renamed', 'GET', base + '/gazpacho')
    a(fam, sc, 'rating', 'PATCH', base + '/gazpacho', body={'rating': 4})
    a(fam, sc, 'tags', 'PATCH', base + '/gazpacho', body=lambda c: {'tags': [c.state['tag']]})
    a(fam, sc, 'missing', 'PATCH', base + '/no-such-recipe', body={'description': 'x'}, status=None)

    sc = 'duplicate'
    a(fam, sc, 'named', 'POST', base + '/banana-bread/duplicate', body={'name': 'Banana Muffins'}, status=201)
    a(fam, sc, 'default-name', 'POST', base + '/banana-bread/duplicate', body={}, status=201)
    a(fam, sc, 'read-copy', 'GET', base + '/banana-muffins')
    a(fam, sc, 'missing', 'POST', base + '/no-such-recipe/duplicate', body={'name': 'X'}, status=None)

    sc = 'last-made'
    a(fam, sc, 'set', 'PATCH', base + '/tomato-soup/last-made', body={'timestamp': '2026-01-15T12:00:00Z'})
    a(fam, sc, 'read', 'GET', base + '/tomato-soup')
    a(fam, sc, 'bad-timestamp', 'PATCH', base + '/tomato-soup/last-made', body={'timestamp': 'soon'}, status=422)

    sc = 'list'
    a(fam, sc, 'by-name', 'GET', base, params={'orderBy': 'name', 'orderDirection': 'asc'})
    a(fam, sc, 'by-name-desc', 'GET', base, params={'orderBy': 'name', 'orderDirection': 'desc'})
    a(fam, sc, 'page-1', 'GET', base, params={'orderBy': 'name', 'perPage': 2, 'page': 1})
    a(fam, sc, 'page-2', 'GET', base, params={'orderBy': 'name', 'perPage': 2, 'page': 2})
    a(fam, sc, 'page-past-end', 'GET', base, params={'orderBy': 'name', 'perPage': 2, 'page': 9})
    a(fam, sc, 'search-word', 'GET', base, params={'search': 'banana', 'orderBy': 'name'})
    a(fam, sc, 'search-none', 'GET', base, params={'search': 'zzzz'})
    a(fam, sc, 'by-category', 'GET', base, params=lambda c: {'categories': c.state['cat']['id'], 'orderBy': 'name'})
    a(fam, sc, 'by-tag', 'GET', base, params=lambda c: {'tags': c.state['tag']['id'], 'orderBy': 'name'})
    a(fam, sc, 'by-tool', 'GET', base, params=lambda c: {'tools': c.state['tool']['id'], 'orderBy': 'name'})
    a(fam, sc, 'by-food', 'GET', base, params=lambda c: {'foods': c.state['food']['id'], 'orderBy': 'name'})
    a(fam, sc, 'filter-rating', 'GET', base, params={'queryFilter': 'rating >= 3', 'orderBy': 'name'})
    a(fam, sc, 'bad-order', 'GET', base, params={'orderBy': 'nonexistent'}, status=None)
    a(fam, sc, 'bad-per-page', 'GET', base, params={'perPage': 'many'}, status=422)

    sc = 'formats'
    a(fam, sc, 'exports', 'GET', base + '/exports')

    sc = 'delete'
    a(fam, sc, 'one', 'DELETE', base + '/tomato-soup-1')
    a(fam, sc, 'gone', 'GET', base + '/tomato-soup-1', status=404)
    a(fam, sc, 'again', 'DELETE', base + '/tomato-soup-1', status=None)
    a(fam, sc, 'list-after', 'GET', base, params={'orderBy': 'name'})
