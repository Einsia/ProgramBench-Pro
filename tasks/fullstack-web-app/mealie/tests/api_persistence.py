'''Persistence: state written before a restart of the application with the same data directory is read back afterwards.

The fixtures create state through the public interfaces; one scored case replaces the product process; the reads that
follow compare what survived. Session tokens issued before the restart stay valid because the signing secret lives in
the data directory. Nothing is replayed.
'''
import base64

from harness import Ref, pathref

FAM = 'persist-fixture'


def text_file(name, text):
    return {'filename': name, 'base64': base64.b64encode(text.encode()).decode(), 'mime_type': 'text/plain'}


def build(s):
    a = s.api
    sc = 'state'
    a(FAM, sc, 'self', 'GET', 'users/self', save='me')
    a(FAM, sc, 'group', 'GET', 'groups/self', save='group')
    a(FAM, sc, 'tag', 'POST', 'organizers/tags', body={'name': 'Durable tag'}, save='tag')
    a(FAM, sc, 'category', 'POST', 'organizers/categories', body={'name': 'Durable category'}, save='cat')
    a(FAM, sc, 'tool', 'POST', 'organizers/tools', body={'name': 'Durable pot', 'householdsWithTool': []}, save='tool')
    a(FAM, sc, 'label', 'POST', 'groups/labels', body={'name': 'Durable aisle', 'color': '#123456'}, status=200, save='label')
    a(FAM, sc, 'food', 'POST', 'foods', body={'name': 'durable bean', 'pluralName': 'durable beans', 'description': 'kept',
                                             'labelId': Ref('label', 'id'), 'aliases': [{'name': 'legume'}]}, save='food')
    a(FAM, sc, 'unit', 'POST', 'units', body={'name': 'durable cup', 'abbreviation': 'dc', 'fraction': True,
                                             'useAbbreviation': True}, save='unit')
    a(FAM, sc, 'recipe', 'POST', 'recipes', body={'name': 'Durable Stew'})
    a(FAM, sc, 'recipe-body', 'PATCH', 'recipes/durable-stew', body={
        'description': 'Slow and steady', 'recipeYield': '4 bowls', 'recipeServings': 4, 'totalTime': '2 hours',
        'rating': 4, 'orgURL': 'https://example.invalid/stew',
        'tags': [Ref('tag')], 'recipeCategory': [Ref('cat')], 'tools': [Ref('tool')],
        'recipeIngredient': [{'quantity': 2, 'unit': Ref('unit'), 'food': Ref('food'), 'note': 'soaked',
                              'referenceId': '7d5f3a8e-1c2b-4e6f-9a0b-1c2d3e4f5a6b'}],
        'recipeInstructions': [{'id': '0b9f6a0e-3a51-4d8c-9e1f-2a3b4c5d6e7f', 'title': 'Start', 'text': 'Simmer for two hours.'}],
        'notes': [{'title': 'Tip', 'text': 'Better the next day.'}],
        'nutrition': {'calories': '320', 'proteinContent': '18'},
        'settings': {'public': True, 'showNutrition': True, 'showAssets': True, 'landscapeView': False,
                     'disableComments': False, 'locked': False}})
    a(FAM, sc, 'asset', 'POST', 'recipes/durable-stew/assets', status=200, save='asset',
      multipart={'fields': {'name': 'Stew notes', 'icon': 'mdi-file', 'extension': 'txt'},
                 'files': {'file': text_file('stew-notes.txt', 'Low heat only.')}})
    a(FAM, sc, 'recipe-read', 'GET', 'recipes/durable-stew', save='recipe-read')
    a(FAM, sc, 'comment', 'POST', 'comments', body={'recipeId': Ref('recipe-read', 'id'), 'text': 'Durable comment'})
    a(FAM, sc, 'favorite', 'POST', pathref('users/{u}/favorites/{r}', u=Ref('me', 'id'), r=Ref('recipe-read', 'slug')))
    a(FAM, sc, 'mealplan', 'POST', 'households/mealplans', body={'date': '2091-03-04', 'entryType': 'dinner',
                                                                'recipeId': Ref('recipe-read', 'id')}, save='plan')
    a(FAM, sc, 'mealplan-note', 'POST', 'households/mealplans', body={'date': '2091-03-05', 'entryType': 'lunch',
                                                                     'title': 'Leftovers', 'text': 'From the stew'})
    a(FAM, sc, 'rule', 'POST', 'households/mealplans/rules', body={'day': 'friday', 'entryType': 'dinner',
                                                                   'queryFilterString': 'tags.name IN ["Durable tag"]'})
    a(FAM, sc, 'list', 'POST', 'households/shopping/lists', body={'name': 'Durable list'}, save='list')
    a(FAM, sc, 'item', 'POST', 'households/shopping/items', body={'shoppingListId': Ref('list', 'id'), 'quantity': 3,
                                                                 'foodId': Ref('food', 'id'), 'note': 'dried'})
    a(FAM, sc, 'item-checked', 'POST', 'households/shopping/items', body={'shoppingListId': Ref('list', 'id'),
                                                                         'note': 'already bought', 'checked': True})
    a(FAM, sc, 'cookbook', 'POST', 'households/cookbooks', body={'name': 'Durable book', 'description': 'Kept',
                                                                 'public': True, 'queryFilterString': 'tags.name IN ["Durable tag"]'})
    a(FAM, sc, 'household-prefs', 'PUT', 'households/preferences', body={
        'privateHousehold': False, 'lockRecipeEditsFromOtherHouseholds': True, 'firstDayOfWeek': 1,
        'recipePublic': True, 'recipeShowNutrition': True, 'recipeShowAssets': True, 'recipeLandscapeView': False,
        'recipeDisableComments': False})
    a(FAM, sc, 'user-update', 'PUT', pathref('users/{u}', u=Ref('me', 'id')),
      body=lambda c: {**c.state['me'], 'fullName': 'Durable Admin'})
    a(FAM, sc, 'token', 'POST', 'users/api-tokens', body={'name': 'durable-cli'}, save='api-token')
    a(FAM, sc, 'webhook', 'POST', 'households/webhooks', body={'enabled': False, 'name': 'Durable hook',
                                                              'url': 'https://example.invalid/hook',
                                                              'webhookType': 'mealplan', 'scheduledTime': '09:30'})

    fam, sc = 'persistence', 'restart'
    s.add(fam, sc, 'restart', lambda c: (c.restart_server(), {'running': c.running()})[1],
          description='The application is replaced by a new process on the same data directory.')

    def back(step, path, **kw):
        a(fam, 'after-restart', step, 'GET', path, **kw)

    back('recipe', 'recipes/durable-stew')
    back('recipe-list', 'recipes', params={'orderBy': 'name'}, fields=['slug', 'name', 'rating', 'tags'])
    back('asset-bytes', pathref('media/recipes/{r}/assets/{f}', r=Ref('recipe-read', 'id'), f=Ref('asset', 'fileName')),
         actor=None, hint='bytes')
    back('tags', 'organizers/tags', params={'orderBy': 'name'})
    back('categories', 'organizers/categories', params={'orderBy': 'name'})
    back('tools', 'organizers/tools', params={'orderBy': 'name'})
    back('labels', 'groups/labels', params={'orderBy': 'name'})
    back('foods', 'foods', params={'orderBy': 'name'})
    back('units', 'units', params={'orderBy': 'name'})
    back('comments', 'recipes/durable-stew/comments')
    back('favorites', pathref('users/{u}/favorites', u=Ref('me', 'id')))
    back('mealplans', 'households/mealplans', params={'start_date': '2091-03-01', 'end_date': '2091-03-31',
                                                       'orderBy': 'date'})
    back('mealplan-entry', pathref('households/mealplans/{p}', p=Ref('plan', 'id')))
    back('rules', 'households/mealplans/rules')
    back('list', pathref('households/shopping/lists/{l}', l=Ref('list', 'id')))
    back('cookbooks', 'households/cookbooks', params={'orderBy': 'name'})
    back('cookbook', 'households/cookbooks/durable-book')
    back('household-prefs', 'households/preferences')
    back('self', 'users/self')
    back('webhooks', 'households/webhooks')
    back('public-recipe', 'explore/groups/home/recipes/durable-stew', actor=None)
    a(fam, 'after-restart', 'api-token', 'GET', 'users/self', actor=None,
      headers=lambda c: {'authorization': 'Bearer ' + c.state['api-token']['token']})
    a(fam, 'after-restart', 'session-token', 'GET', 'households/self')
    a(fam, 'after-restart', 'sign-in', 'POST', 'auth/token', actor=None,
      form={'username': 'admin', 'password': 'MyPassword'}, fields=['token_type'])
    a(fam, 'after-restart', 'write', 'POST', 'organizers/tags', body={'name': 'After restart'})
    back('tags-after-write', 'organizers/tags', params={'orderBy': 'name'})
