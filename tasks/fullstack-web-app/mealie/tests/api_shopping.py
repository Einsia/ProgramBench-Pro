'''Shopping lists of the household: lists, items, merging, recipe ingredients and label settings.

Lists are created, read, renamed, listed and deleted. Items are added singly and in bulk; an item with the same note
on the same list merges into the existing one by adding the quantities. Items are checked, moved, edited and removed.
Adding a recipe puts its ingredients on the list scaled by the requested quantity and records the recipe reference;
removing it subtracts the same amounts. Label settings order the labels of a list. Validation, missing items and
anonymous access are part of the contract.
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'


def items_of(list_key):
    return lambda c: {'queryFilter': 'shoppingListId = "%s"' % c.state[list_key]['id'],
                      'orderBy': 'note', 'orderDirection': 'asc'}


def build(s):
    a = s.api
    lists, items = 'households/shopping/lists', 'households/shopping/items'
    lf, itf = 'shopping-lists', 'shopping-items'

    sc = 'create'
    a(lf, sc, 'weekly', 'POST', lists, status=201, save='weekly', body={'name': 'Weekly'})
    a(lf, sc, 'party', 'POST', lists, status=201, save='party', body={'name': 'Party ✓'})
    a(lf, sc, 'unnamed', 'POST', lists, status=201, save='unnamed', body={})
    a(lf, sc, 'extras', 'POST', lists, status=201, body={'name': 'Camping', 'extras': {'trip': 'lake'}})
    a(lf, sc, 'bad-name', 'POST', lists, status=422, body={'name': ['x']})
    a(lf, sc, 'anonymous', 'POST', lists, actor=None, status=401, body={'name': 'x'})

    sc = 'read'
    a(lf, sc, 'weekly', 'GET', pathref(lists + '/{id}', id=Ref('weekly', 'id')))
    a(lf, sc, 'unnamed', 'GET', pathref(lists + '/{id}', id=Ref('unnamed', 'id')))
    a(lf, sc, 'missing', 'GET', lists + '/' + MISSING, status=404)
    a(lf, sc, 'not-uuid', 'GET', lists + '/weekly', status=422)
    a(lf, sc, 'anonymous', 'GET', pathref(lists + '/{id}', id=Ref('weekly', 'id')), actor=None, status=401)

    sc = 'list'
    a(lf, sc, 'by-name', 'GET', lists, params={'orderBy': 'name', 'orderDirection': 'asc'})
    a(lf, sc, 'by-name-desc', 'GET', lists, params={'orderBy': 'name', 'orderDirection': 'desc'})
    a(lf, sc, 'page', 'GET', lists, params={'orderBy': 'name', 'perPage': 2, 'page': 2})
    a(lf, sc, 'filter', 'GET', lists, params={'queryFilter': 'name = "Weekly"'})

    sc = 'update'
    a(lf, sc, 'rename', 'PUT', pathref(lists + '/{id}', id=Ref('party', 'id')), status=None,
      body=lambda c: {**c.state['party'], 'name': 'Birthday'})
    a(lf, sc, 'read-renamed', 'GET', pathref(lists + '/{id}', id=Ref('party', 'id')))
    a(lf, sc, 'missing', 'PUT', lists + '/' + MISSING, status=None,
      body=lambda c: {**c.state['party'], 'id': MISSING, 'name': 'Ghost'})

    sc = 'add'
    a(itf, sc, 'eggs', 'POST', items, status=201, save='eggs-add',
      body=lambda c: {'shoppingListId': c.state['weekly']['id'], 'note': 'eggs', 'quantity': 2})
    a(itf, sc, 'eggs-again-merges', 'POST', items, status=201,
      body=lambda c: {'shoppingListId': c.state['weekly']['id'], 'note': 'eggs', 'quantity': 3})
    a(itf, sc, 'bulk', 'POST', items + '/create-bulk', status=201, save='bulk',
      body=lambda c: [{'shoppingListId': c.state['weekly']['id'], 'note': 'milk', 'quantity': 1},
                      {'shoppingListId': c.state['weekly']['id'], 'note': 'bread'},
                      {'shoppingListId': c.state['weekly']['id'], 'note': 'apples', 'quantity': 6}])
    a(itf, sc, 'other-list-no-merge', 'POST', items, status=201,
      body=lambda c: {'shoppingListId': c.state['party']['id'], 'note': 'eggs', 'quantity': 12})
    a(itf, sc, 'zero-quantity', 'POST', items, status=201,
      body=lambda c: {'shoppingListId': c.state['party']['id'], 'note': 'candles', 'quantity': 0})
    a(itf, sc, 'missing-list-id', 'POST', items, status=422, body={'note': 'x'})
    a(itf, sc, 'bad-quantity', 'POST', items, status=422,
      body=lambda c: {'shoppingListId': c.state['weekly']['id'], 'note': 'x', 'quantity': 'lots'})
    a(itf, sc, 'anonymous', 'POST', items, actor=None, status=401,
      body=lambda c: {'shoppingListId': c.state['weekly']['id'], 'note': 'x'})
    a(itf, sc, 'weekly-items', 'GET', items, params=items_of('weekly'))
    a(itf, sc, 'party-items', 'GET', items, params=items_of('party'))
    a(lf, 'items', 'weekly-with-items', 'GET', pathref(lists + '/{id}', id=Ref('weekly', 'id')))

    sc = 'change'
    egg = Ref('eggs-add', 'createdItems', 0, 'id')
    a(itf, sc, 'read-one', 'GET', pathref(items + '/{id}', id=egg), save='egg')
    a(itf, sc, 'check', 'PUT', pathref(items + '/{id}', id=egg), status=None,
      body=lambda c: {**c.state['egg'], 'checked': True})
    a(itf, sc, 'read-checked', 'GET', pathref(items + '/{id}', id=egg))
    a(itf, sc, 'requantify', 'PUT', pathref(items + '/{id}', id=egg), status=None,
      body=lambda c: {**c.state['egg'], 'checked': True, 'quantity': 7, 'note': 'brown eggs'})
    a(itf, sc, 'read-requantified', 'GET', pathref(items + '/{id}', id=egg))
    a(itf, sc, 'bulk-reorder', 'PUT', items, status=None, hint='none',
      body=lambda c: [{**x, 'position': 10 - i} for i, x in enumerate(c.state['bulk']['createdItems'])])
    a(itf, sc, 'by-position', 'GET', items,
      params=lambda c: {'queryFilter': 'shoppingListId = "%s"' % c.state['weekly']['id'], 'orderBy': 'position'})
    a(itf, sc, 'checked-only', 'GET', items,
      params=lambda c: {'queryFilter': 'shoppingListId = "%s" AND checked = true' % c.state['weekly']['id']})
    a(itf, sc, 'missing', 'GET', items + '/' + MISSING, status=404)

    sc = 'remove'
    milk = Ref('bulk', 'createdItems', 0, 'id')
    a(itf, sc, 'one', 'DELETE', pathref(items + '/{id}', id=milk), status=None)
    a(itf, sc, 'gone', 'GET', pathref(items + '/{id}', id=milk), status=404)
    a(itf, sc, 'many', 'DELETE', items, status=None,
      params=lambda c: {'ids': [c.state['bulk']['createdItems'][1]['id']]})
    a(itf, sc, 'weekly-after', 'GET', items, params=items_of('weekly'))

    # Recipe ingredients onto a list, scaled; removal subtracts the same amounts.
    sc, rf = 'recipe', 'shopping-recipes'
    a(rf, sc, 'recipe', 'POST', 'recipes', status=201, body={'name': 'Pancakes'})
    a(rf, sc, 'ingredients', 'PATCH', 'recipes/pancakes',
      body={'recipeIngredient': [{'note': 'milk', 'quantity': 1, 'disableAmount': False},
                                 {'note': 'flour', 'quantity': 2, 'disableAmount': False},
                                 {'note': 'pinch of salt', 'disableAmount': True}]})
    a(rf, sc, 'read-recipe', 'GET', 'recipes/pancakes', save='pancakes')
    a(rf, sc, 'add-double', 'POST', pathref(lists + '/{id}/recipe', id=Ref('unnamed', 'id')),
      body=lambda c: [{'recipeId': c.state['pancakes']['id'], 'recipeIncrementQuantity': 2}])
    a(rf, sc, 'list-items', 'GET', items, params=items_of('unnamed'))
    a(rf, sc, 'add-once-more', 'POST', pathref(lists + '/{id}/recipe', id=Ref('unnamed', 'id')),
      body=lambda c: [{'recipeId': c.state['pancakes']['id'], 'recipeIncrementQuantity': 1}])
    a(rf, sc, 'list-items-triple', 'GET', items, params=items_of('unnamed'))
    a(rf, sc, 'remove-one', 'POST',
      lambda c: '%s/%s/recipe/%s/delete' % (lists, c.state['unnamed']['id'], c.state['pancakes']['id']),
      body={'recipeDecrementQuantity': 1})
    a(rf, sc, 'list-items-after-remove', 'GET', items, params=items_of('unnamed'))
    a(rf, sc, 'remove-rest', 'POST',
      lambda c: '%s/%s/recipe/%s/delete' % (lists, c.state['unnamed']['id'], c.state['pancakes']['id']),
      body={'recipeDecrementQuantity': 2})
    a(rf, sc, 'list-items-empty', 'GET', items, params=items_of('unnamed'))

    sc, lsf = 'labels', 'shopping-label-settings'
    a(lsf, sc, 'dairy', 'POST', 'groups/labels', body={'name': 'Dairy', 'color': '#2196f3'})
    a(lsf, sc, 'bakery', 'POST', 'groups/labels', body={'name': 'Bakery', 'color': '#ff9800'})
    a(lsf, sc, 'list-settings', 'GET', pathref(lists + '/{id}', id=Ref('weekly', 'id')), save='weekly-labels')
    a(lsf, sc, 'reverse-order', 'PUT', pathref(lists + '/{id}/label-settings', id=Ref('weekly', 'id')),
      body=lambda c: [{**x, 'position': len(c.state['weekly-labels']['labelSettings']) - 1 - i}
                      for i, x in enumerate(c.state['weekly-labels']['labelSettings'])])
    a(lsf, sc, 'read-reordered', 'GET', pathref(lists + '/{id}', id=Ref('weekly', 'id')))

    sc = 'delete'
    a(lf, sc, 'birthday', 'DELETE', pathref(lists + '/{id}', id=Ref('party', 'id')), status=None)
    a(lf, sc, 'gone', 'GET', pathref(lists + '/{id}', id=Ref('party', 'id')), status=404)
    a(lf, sc, 'items-gone', 'GET', items, params=items_of('party'))
    a(lf, sc, 'again', 'DELETE', pathref(lists + '/{id}', id=Ref('party', 'id')), status=None)
    a(lf, sc, 'list-after', 'GET', lists, params={'orderBy': 'name', 'orderDirection': 'asc'})
