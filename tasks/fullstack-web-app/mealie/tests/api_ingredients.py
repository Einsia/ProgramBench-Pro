'''Ingredient data of the group: shopping labels, foods and units.

Labels are created first so foods can point at one. Each kind is created (with aliases, plural forms, extras),
read, listed (search, ordering, filters, pagination), updated, merged and deleted. Validation and missing-item errors
are part of the contract.
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'


def build(s):
    a = s.api
    one = lambda base, key: pathref(base + '/{i}', i=Ref(key, 'id'))
    a('ingredients-fixture', 'household', 'self', 'GET', 'households/self', save='ingredient-household')

    # -- labels ---------------------------------------------------------------------------------------------
    base, fam = 'groups/labels', 'labels'
    sc = 'create'
    a(fam, sc, 'produce', 'POST', base, body={'name': 'Produce', 'color': '#4CAF50'}, status=200, save='label1')
    a(fam, sc, 'dairy', 'POST', base, body={'name': 'Dairy', 'color': '#2196F3'}, status=200, save='label2')
    a(fam, sc, 'default-color', 'POST', base, body={'name': 'Bakery'}, status=200, save='label3')
    a(fam, sc, 'missing-name', 'POST', base, body={'color': '#000000'}, status=422)
    a(fam, sc, 'anonymous', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)
    sc = 'read'
    a(fam, sc, 'by-id', 'GET', one(base, 'label1'))
    a(fam, sc, 'id-missing', 'GET', base + '/' + MISSING, status=None)
    a(fam, sc, 'id-malformed', 'GET', base + '/not-a-uuid', status=422)
    sc = 'list'
    a(fam, sc, 'all', 'GET', base, params={'orderBy': 'name'})
    a(fam, sc, 'search', 'GET', base, params={'search': 'dair'})
    a(fam, sc, 'per-page-1', 'GET', base, params={'perPage': 1, 'orderBy': 'name', 'orderDirection': 'desc'})
    a(fam, sc, 'filter-color', 'GET', base, params={'queryFilter': 'color = "#4CAF50"'})
    sc = 'update'
    a(fam, sc, 'recolor', 'PUT', one(base, 'label3'),
      body=lambda c: {'name': 'Bread & Bakery', 'color': '#795548', 'id': c.state['label3']['id'],
                      'groupId': c.state['label3']['groupId']})
    a(fam, sc, 'read-updated', 'GET', one(base, 'label3'))
    a(fam, sc, 'missing-fields', 'PUT', one(base, 'label3'), body={'name': 'X'}, status=422)

    # -- foods ----------------------------------------------------------------------------------------------
    base, fam = 'foods', 'foods'
    sc = 'create'
    a(fam, sc, 'with-label', 'POST', base, status=201, save='food1',
      body=lambda c: {'name': 'tomato', 'pluralName': 'tomatoes', 'description': 'Ripe red tomatoes',
                      'labelId': c.state['label1']['id'], 'aliases': [{'name': 'love apple'}]})
    a(fam, sc, 'plain', 'POST', base, body={'name': 'basil'}, status=201, save='food2')
    a(fam, sc, 'extras', 'POST', base, status=201, save='food3',
      body={'name': 'whole milk', 'extras': {'fat': '3.5%'}, 'aliases': [{'name': 'milk'}, {'name': 'full-fat milk'}]})
    a(fam, sc, 'fourth', 'POST', base, body={'name': 'cherry tomato'}, status=201, save='food4')
    a(fam, sc, 'duplicate-name', 'POST', base, body={'name': 'basil'}, status=None)
    a(fam, sc, 'missing-name', 'POST', base, body={'description': 'no name'}, status=422)
    a(fam, sc, 'bad-label', 'POST', base, body={'name': 'ghost food', 'labelId': 'nope'}, status=422)
    a(fam, sc, 'anonymous', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)
    sc = 'read'
    a(fam, sc, 'by-id', 'GET', one(base, 'food1'))
    a(fam, sc, 'with-extras', 'GET', one(base, 'food3'))
    a(fam, sc, 'id-missing', 'GET', base + '/' + MISSING, status=None)
    a(fam, sc, 'id-malformed', 'GET', base + '/not-a-uuid', status=422)
    sc = 'list'
    a(fam, sc, 'all', 'GET', base, params={'orderBy': 'name'})
    a(fam, sc, 'search', 'GET', base, params={'search': 'tomato'})
    a(fam, sc, 'search-alias', 'GET', base, params={'search': 'love apple'})
    a(fam, sc, 'per-page-2', 'GET', base, params={'perPage': 2, 'orderBy': 'name'})
    a(fam, sc, 'page-2', 'GET', base, params={'perPage': 2, 'page': 2, 'orderBy': 'name'})
    a(fam, sc, 'name-desc', 'GET', base, params={'orderBy': 'name', 'orderDirection': 'desc'})
    a(fam, sc, 'filter-label', 'GET', base, params=lambda c: {'queryFilter': 'label.id = "%s"' % c.state['label1']['id']})
    a(fam, sc, 'filter-null-label', 'GET', base, params={'queryFilter': 'labelId IS NULL', 'orderBy': 'name'})
    a(fam, sc, 'empty', 'GET', base + '/empty')
    sc = 'update'
    a(fam, sc, 'relabel', 'PUT', one(base, 'food2'),
      body=lambda c: {'name': 'sweet basil', 'description': 'Fresh herb', 'labelId': c.state['label1']['id'],
                      'aliases': [{'name': 'thai basil'}]})
    a(fam, sc, 'read-updated', 'GET', one(base, 'food2'))
    a(fam, sc, 'clear-label', 'PUT', one(base, 'food2'), body={'name': 'sweet basil', 'labelId': None})
    a(fam, sc, 'missing-name', 'PUT', one(base, 'food2'), body={}, status=422)
    a(fam, sc, 'missing-item', 'PUT', base + '/' + MISSING, body={'name': 'Ghost'}, status=None)
    a('food-merge-fixture', 'usage', 'recipe', 'POST', 'recipes', body={'name': 'Food Merge Usage'})
    a('food-merge-fixture', 'usage', 'link', 'PATCH', 'recipes/food-merge-usage',
      body=lambda c: {'recipeIngredient': [{'quantity': 1, 'food': c.state['food1']},
                                           {'quantity': 2, 'food': c.state['food4']}]})
    a('food-merge-fixture', 'usage', 'list', 'POST', 'households/shopping/lists', body={'name': 'Food merge list'}, save='merge-list')
    a('food-merge-fixture', 'usage', 'item', 'POST', 'households/shopping/items',
      body=lambda c: {'shoppingListId': c.state['merge-list']['id'], 'foodId': c.state['food4']['id'], 'quantity': 3})
    sc = 'merge'
    a(fam, sc, 'merge', 'PUT', base + '/merge', status=None,
      body=lambda c: {'fromFood': c.state['food4']['id'], 'toFood': c.state['food1']['id']})
    a(fam, sc, 'merge-incomplete', 'PUT', base + '/merge', body={'fromFood': MISSING}, status=422)
    a(fam, sc, 'after-merge', 'GET', base, params={'orderBy': 'name'})
    a(fam, sc, 'recipe-reference', 'GET', 'recipes/food-merge-usage', fields=['recipeIngredient'])
    a(fam, sc, 'shopping-reference', 'GET', pathref('households/shopping/lists/{i}', i=Ref('merge-list', 'id')), fields=['listItems'])
    sc = 'delete'
    a(fam, sc, 'delete', 'DELETE', one(base, 'food3'))
    a(fam, sc, 'gone', 'GET', one(base, 'food3'), status=None)
    a(fam, sc, 'list-after', 'GET', base, params={'orderBy': 'name'})

    # The On Hand flag is represented by the household membership list in the
    # public food schema. Exercise setting, reading and clearing it.
    fam = 'foods-on-hand'
    a(fam, 'state', 'create', 'POST', 'foods', status=201, save='onhand-food',
      body=lambda c: {'name': 'on-hand carrots',
                      'householdsWithIngredientFood': [c.state['ingredient-household']['slug']]})
    a(fam, 'state', 'read', 'GET', pathref('foods/{id}', id=Ref('onhand-food', 'id')),
      fields=['name', 'householdsWithIngredientFood'])
    a(fam, 'state', 'clear', 'PUT', pathref('foods/{id}', id=Ref('onhand-food', 'id')),
      body=lambda c: {'name': 'on-hand carrots', 'householdsWithIngredientFood': []})
    a(fam, 'state', 'read-cleared', 'GET', pathref('foods/{id}', id=Ref('onhand-food', 'id')),
      fields=['householdsWithIngredientFood'])

    # -- units ----------------------------------------------------------------------------------------------
    base, fam = 'units', 'units'
    sc = 'create'
    a(fam, sc, 'abbreviated', 'POST', base, status=201, save='unit1',
      body={'name': 'tablespoon', 'pluralName': 'tablespoons', 'abbreviation': 'tbsp', 'useAbbreviation': True,
            'fraction': True, 'aliases': [{'name': 'tbs'}]})
    a(fam, sc, 'plain', 'POST', base, body={'name': 'pinch'}, status=201, save='unit2')
    a(fam, sc, 'standard', 'POST', base, status=201, save='unit3',
      body={'name': 'cup', 'abbreviation': 'c', 'standardQuantity': 236.588, 'standardUnit': 'milliliter'})
    a(fam, sc, 'fourth', 'POST', base, body={'name': 'Tbsp.', 'abbreviation': 'T'}, status=201, save='unit4')
    usefam = 'ingredients-merge-fixture'
    a(usefam, 'merge-use', 'recipe', 'POST', 'recipes', body={'name': 'Ingredient Merge Usage'})
    a(usefam, 'merge-use', 'associate', 'PATCH', 'recipes/ingredient-merge-usage',
      body=lambda c: {'recipeIngredient': [
          {'quantity': 1, 'food': c.state['food1'], 'unit': c.state['unit1']},
          {'quantity': 2, 'food': c.state['food2'], 'unit': c.state['unit4']},
      ]})
    a(fam, sc, 'duplicate-name', 'POST', base, body={'name': 'pinch'}, status=None)
    a(fam, sc, 'missing-name', 'POST', base, body={'abbreviation': 'x'}, status=422)
    a(fam, sc, 'bad-fraction', 'POST', base, body={'name': 'odd', 'fraction': 'sometimes'}, status=422)
    a(fam, sc, 'anonymous', 'POST', base, actor=None, body={'name': 'Nope'}, status=401)
    sc = 'read'
    a(fam, sc, 'by-id', 'GET', one(base, 'unit1'))
    a(fam, sc, 'standard', 'GET', one(base, 'unit3'))
    a(fam, sc, 'id-missing', 'GET', base + '/' + MISSING, status=None)
    a(fam, sc, 'id-malformed', 'GET', base + '/not-a-uuid', status=422)
    sc = 'list'
    a(fam, sc, 'all', 'GET', base, params={'orderBy': 'name'})
    a(fam, sc, 'search', 'GET', base, params={'search': 'tbsp'})
    a(fam, sc, 'per-page-1', 'GET', base, params={'perPage': 1, 'page': 3, 'orderBy': 'name'})
    a(fam, sc, 'filter-fraction', 'GET', base, params={'queryFilter': 'fraction = true', 'orderBy': 'name'})
    sc = 'update'
    a(fam, sc, 'update', 'PUT', one(base, 'unit2'),
      body={'name': 'pinch', 'pluralName': 'pinches', 'description': 'A small amount', 'fraction': False})
    a(fam, sc, 'read-updated', 'GET', one(base, 'unit2'))
    a(fam, sc, 'missing-name', 'PUT', one(base, 'unit2'), body={'abbreviation': 'p'}, status=422)
    a(fam, sc, 'missing-item', 'PUT', base + '/' + MISSING, body={'name': 'Ghost'}, status=None)
    sc = 'merge'
    a(fam, sc, 'merge', 'PUT', base + '/merge', status=None,
      body=lambda c: {'fromUnit': c.state['unit4']['id'], 'toUnit': c.state['unit1']['id']})
    a(fam, sc, 'merge-incomplete', 'PUT', base + '/merge', body={'toUnit': MISSING}, status=422)
    a(fam, sc, 'after-merge', 'GET', base, params={'orderBy': 'name'})
    a(fam, sc, 'associated-recipe-after', 'GET', 'recipes/ingredient-merge-usage',
      fields=['recipeIngredient'])
    sc = 'delete'
    a(fam, sc, 'delete', 'DELETE', one(base, 'unit3'))
    a(fam, sc, 'gone', 'GET', one(base, 'unit3'), status=None)
    a(fam, sc, 'list-after', 'GET', base, params={'orderBy': 'name'})

    # -- label merge and delete (after foods point at labels) --------------------------------------------------
    base, fam = 'groups/labels', 'labels'
    sc = 'merge'
    a(fam, sc, 'merge', 'POST', base + '/merge', status=None,
      body=lambda c: {'fromId': c.state['label1']['id'], 'toId': c.state['label2']['id']})
    a(fam, sc, 'foods-follow', 'GET', 'foods', params={'orderBy': 'name'})
    a(fam, sc, 'after-merge', 'GET', base, params={'orderBy': 'name'})
    sc = 'delete'
    a(fam, sc, 'delete', 'DELETE', one(base, 'label3'))
    a(fam, sc, 'gone', 'GET', one(base, 'label3'), status=None)
    a(fam, sc, 'list-after', 'GET', base, params={'orderBy': 'name'})
