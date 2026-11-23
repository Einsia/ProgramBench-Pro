'''Recipe activity and sharing: comments, timeline events, ratings and favorites, share tokens, bulk actions, group
and household preferences, and the public explore API.

Comments and timeline events are created, listed, updated and deleted. Ratings and favorites are per user. A share
token exposes one recipe to anonymous readers. Bulk actions tag, categorize, change settings of, export and delete many
recipes at once. The explore API serves a group's public recipes and organizers only once the group is not private.
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'


def build(s):
    a = s.api
    f = 'social'

    sc = 'fixture'
    a(f + '-fixture', sc, 'soup', 'POST', 'recipes', body={'name': 'Tomato Soup'}, status=201)
    a(f + '-fixture', sc, 'pie', 'POST', 'recipes', body={'name': 'Apple Pie'}, status=201)
    a(f + '-fixture', sc, 'salad', 'POST', 'recipes', body={'name': 'Green Salad'}, status=201)
    a(f + '-fixture', sc, 'soup-read', 'GET', 'recipes/tomato-soup', status=200, save='soup')
    a(f + '-fixture', sc, 'pie-read', 'GET', 'recipes/apple-pie', status=200, save='pie')
    a(f + '-fixture', sc, 'salad-read', 'GET', 'recipes/green-salad', status=200, save='salad')
    a(f + '-fixture', sc, 'me', 'GET', 'users/self', status=200, save='me')
    a(f + '-fixture', sc, 'tag', 'POST', 'organizers/tags', body={'name': 'Quick'}, status=201, save='tag')
    a(f + '-fixture', sc, 'category', 'POST', 'organizers/categories', body={'name': 'Dinner'}, status=201,
      save='cat')

    # -- comments ---------------------------------------------------------------------------------------------
    fam = 'comments'
    sc = 'create'
    a(fam, sc, 'first', 'POST', 'comments', body=lambda c: {'recipeId': c.state['soup']['id'], 'text': 'Nice'},
      status=201, save='comment')
    a(fam, sc, 'second', 'POST', 'comments', body=lambda c: {'recipeId': c.state['soup']['id'], 'text': 'Salty'},
      status=201, save='comment2')
    a(fam, sc, 'other-recipe', 'POST', 'comments', body=lambda c: {'recipeId': c.state['pie']['id'], 'text': 'Sweet'},
      status=201)
    a(fam, sc, 'missing-text', 'POST', 'comments', body=lambda c: {'recipeId': c.state['soup']['id']}, status=422)
    a(fam, sc, 'missing-recipe', 'POST', 'comments', body={'text': 'x'}, status=422)
    a(fam, sc, 'anonymous', 'POST', 'comments', actor=None, body=lambda c: {'recipeId': c.state['soup']['id'],
                                                                             'text': 'x'}, status=401)
    sc = 'read'
    a(fam, sc, 'by-id', 'GET', pathref('comments/{id}', id=Ref('comment', 'id')), status=200)
    a(fam, sc, 'missing', 'GET', 'comments/' + MISSING, status=404)
    a(fam, sc, 'of-recipe', 'GET', 'recipes/tomato-soup/comments', status=200)
    a(fam, sc, 'of-other-recipe', 'GET', 'recipes/apple-pie/comments', status=200)
    a(fam, sc, 'of-uncommented', 'GET', 'recipes/green-salad/comments', status=200)
    a(fam, sc, 'list', 'GET', 'comments', status=200, params={'orderBy': 'createdAt', 'orderDirection': 'asc'})
    a(fam, sc, 'list-desc', 'GET', 'comments', status=200, params={'orderBy': 'createdAt', 'orderDirection': 'desc'})
    a(fam, sc, 'list-page', 'GET', 'comments', status=200, params={'orderBy': 'createdAt', 'perPage': 2, 'page': 2})
    sc = 'update'
    a(fam, sc, 'text', 'PUT', pathref('comments/{id}', id=Ref('comment', 'id')),
      body=lambda c: {'id': c.state['comment']['id'], 'text': 'Very nice'}, status=200)
    a(fam, sc, 'after', 'GET', pathref('comments/{id}', id=Ref('comment', 'id')), status=200)
    a(fam, sc, 'without-id', 'PUT', pathref('comments/{id}', id=Ref('comment', 'id')), body={'text': 'x'},
      status=422)
    sc = 'delete'
    a(fam, sc, 'second', 'DELETE', pathref('comments/{id}', id=Ref('comment2', 'id')), status=200)
    a(fam, sc, 'gone', 'GET', pathref('comments/{id}', id=Ref('comment2', 'id')), status=404)
    a(fam, sc, 'remaining', 'GET', 'recipes/tomato-soup/comments', status=200)

    # -- timeline ---------------------------------------------------------------------------------------------
    fam = 'timeline'
    ev = 'recipes/timeline/events'
    sc = 'create'
    a(fam, sc, 'comment-event', 'POST', ev, status=201, save='event',
      body=lambda c: {'recipeId': c.state['soup']['id'], 'subject': 'Made it', 'eventType': 'comment',
                      'eventMessage': 'good', 'timestamp': '2026-01-02T03:04:05Z'})
    a(fam, sc, 'info-event', 'POST', ev, status=201, save='event2',
      body=lambda c: {'recipeId': c.state['pie']['id'], 'subject': 'Note', 'eventType': 'info',
                      'timestamp': '2025-06-01T12:00:00Z'})
    a(fam, sc, 'bad-type', 'POST', ev, status=422,
      body=lambda c: {'recipeId': c.state['soup']['id'], 'subject': 'x', 'eventType': 'party'})
    a(fam, sc, 'missing-subject', 'POST', ev, status=422,
      body=lambda c: {'recipeId': c.state['soup']['id'], 'eventType': 'info'})
    sc = 'read'
    a(fam, sc, 'by-id', 'GET', pathref(ev + '/{id}', id=Ref('event', 'id')), status=200)
    a(fam, sc, 'missing', 'GET', ev + '/' + MISSING, status=404)
    a(fam, sc, 'list', 'GET', ev, status=200, params={'orderBy': 'timestamp', 'orderDirection': 'asc'})
    a(fam, sc, 'filter-type', 'GET', ev, status=200,
      params={'queryFilter': 'eventType="comment"', 'orderBy': 'timestamp'})
    a(fam, sc, 'filter-recipe', 'GET', ev, status=200, params=lambda c: {
        'queryFilter': 'recipeId="%s"' % c.state['pie']['id'], 'orderBy': 'timestamp'})
    sc = 'update'
    a(fam, sc, 'subject', 'PUT', pathref(ev + '/{id}', id=Ref('event', 'id')), status=200,
      body={'subject': 'Made it twice', 'eventMessage': 'even better'})
    a(fam, sc, 'after', 'GET', pathref(ev + '/{id}', id=Ref('event', 'id')), status=200)
    sc = 'delete'
    a(fam, sc, 'info', 'DELETE', pathref(ev + '/{id}', id=Ref('event2', 'id')), status=200)
    a(fam, sc, 'gone', 'GET', pathref(ev + '/{id}', id=Ref('event2', 'id')), status=404)

    # -- ratings and favorites --------------------------------------------------------------------------------
    fam = 'ratings'
    sc = 'rate'
    a(fam, sc, 'rate-soup', 'POST', pathref('users/{u}/ratings/tomato-soup', u=Ref('me', 'id')),
      body={'rating': 4, 'isFavorite': False}, status=200)
    a(fam, sc, 'favorite-pie', 'POST', pathref('users/{u}/favorites/apple-pie', u=Ref('me', 'id')), status=200)
    a(fam, sc, 'mine', 'GET', 'users/self/ratings', status=200)
    a(fam, sc, 'mine-by-id', 'GET', pathref('users/{u}/ratings', u=Ref('me', 'id')), status=200,
      fields=['ratings'])
    a(fam, sc, 'favorites', 'GET', 'users/self/favorites', status=200)
    a(fam, sc, 'one', 'GET', pathref('users/self/ratings/{r}', r=Ref('soup', 'id')), status=200)
    a(fam, sc, 'unrated', 'GET', pathref('users/self/ratings/{r}', r=Ref('salad', 'id')), status=None)
    a(fam, sc, 'recipe-rating', 'GET', 'recipes/tomato-soup', status=200, fields=['rating', 'slug'])
    a(fam, sc, 're-rate', 'POST', pathref('users/{u}/ratings/tomato-soup', u=Ref('me', 'id')),
      body={'rating': 2}, status=200)
    a(fam, sc, 'after-re-rate', 'GET', 'users/self/ratings', status=200)
    a(fam, sc, 'unfavorite', 'DELETE', pathref('users/{u}/favorites/apple-pie', u=Ref('me', 'id')), status=200)
    a(fam, sc, 'after-unfavorite', 'GET', 'users/self/favorites', status=200)
    a(fam, sc, 'missing-recipe', 'POST', pathref('users/{u}/ratings/no-such-recipe', u=Ref('me', 'id')),
      body={'rating': 3}, status=None)

    # -- share tokens -----------------------------------------------------------------------------------------
    fam = 'shares'
    sc = 'create'
    a(fam, sc, 'soup', 'POST', 'shared/recipes', body=lambda c: {'recipeId': c.state['soup']['id']}, status=201,
      save='share', fields=['recipeId', 'expiresAt', 'groupId', 'id'])
    a(fam, sc, 'expiring', 'POST', 'shared/recipes', status=201, save='share2', fields=['recipeId', 'expiresAt'],
      body=lambda c: {'recipeId': c.state['pie']['id'], 'expiresAt': '2030-01-01T00:00:00Z'})
    a(fam, sc, 'missing-recipe-id', 'POST', 'shared/recipes', body={}, status=422)
    sc = 'read'
    a(fam, sc, 'list', 'GET', 'shared/recipes', status=200)
    a(fam, sc, 'list-of-recipe', 'GET', 'shared/recipes', status=200,
      params=lambda c: {'recipe_id': c.state['soup']['id']})
    a(fam, sc, 'by-id', 'GET', pathref('shared/recipes/{id}', id=Ref('share', 'id')), status=200,
      fields=['recipeId', 'expiresAt', 'id'])
    a(fam, sc, 'anonymous-recipe', 'GET', pathref('recipes/shared/{id}', id=Ref('share', 'id')), actor=None,
      status=200, fields=['name', 'slug', 'id'])
    a(fam, sc, 'anonymous-missing', 'GET', 'recipes/shared/' + MISSING, actor=None, status=404)
    sc = 'delete'
    a(fam, sc, 'soup', 'DELETE', pathref('shared/recipes/{id}', id=Ref('share', 'id')), status=None)
    a(fam, sc, 'anonymous-after', 'GET', pathref('recipes/shared/{id}', id=Ref('share', 'id')), actor=None,
      status=404)
    a(fam, sc, 'list-after', 'GET', 'shared/recipes', status=200)

    # -- last made --------------------------------------------------------------------------------------------
    fam = 'last-made'
    sc = 'set'
    a(fam, sc, 'soup', 'PATCH', 'recipes/tomato-soup/last-made', body={'timestamp': '2026-02-03T04:05:06Z'},
      status=200, fields=['slug'])
    a(fam, sc, 'read', 'GET', 'households/self/recipes/tomato-soup', status=200, fields=['lastMade'])
    a(fam, sc, 'missing-timestamp', 'PATCH', 'recipes/tomato-soup/last-made', body={}, status=422)
    a(fam, sc, 'missing-recipe', 'PATCH', 'recipes/no-such-recipe/last-made',
      body={'timestamp': '2026-02-03T04:05:06Z'}, status=None)

    # -- bulk actions -----------------------------------------------------------------------------------------
    fam = 'bulk'
    ba = 'recipes/bulk-actions'
    sc = 'organize'
    a(fam, sc, 'tag', 'POST', ba + '/tag', status=200, hint='none',
      body=lambda c: {'recipes': ['tomato-soup', 'apple-pie'], 'tags': [c.state['tag']]})
    a(fam, sc, 'tagged-soup', 'GET', 'recipes/tomato-soup', status=200, fields=['tags'])
    a(fam, sc, 'untagged-salad', 'GET', 'recipes/green-salad', status=200, fields=['tags'])
    a(fam, sc, 'categorize', 'POST', ba + '/categorize', status=200, hint='none',
      body=lambda c: {'recipes': ['green-salad'], 'categories': [c.state['cat']]})
    a(fam, sc, 'categorized-salad', 'GET', 'recipes/green-salad', status=200, fields=['recipeCategory'])
    a(fam, sc, 'tag-without-id', 'POST', ba + '/tag', status=422,
      body={'recipes': ['tomato-soup'], 'tags': [{'name': 'Quick', 'slug': 'quick'}]})
    a(fam, sc, 'filter-by-tag', 'GET', 'recipes', status=200, fields=['slug'],
      params={'tags': 'quick', 'orderBy': 'name', 'orderDirection': 'asc'})
    sc = 'settings'
    a(fam, sc, 'lock', 'POST', ba + '/settings', status=200, hint='none',
      body={'recipes': ['apple-pie'], 'settings': {'public': False, 'showNutrition': True, 'showAssets': True,
                                                   'landscapeView': True, 'disableComments': True, 'locked': True}})
    a(fam, sc, 'after', 'GET', 'recipes/apple-pie', status=200, fields=['settings'])
    a(fam, sc, 'others-untouched', 'GET', 'recipes/tomato-soup', status=200, fields=['settings'])
    sc = 'export'
    a(fam, sc, 'start', 'POST', ba + '/export', body={'recipes': ['tomato-soup', 'green-salad'],
                                                      'exportType': 'json'}, status=202)
    a(fam, sc, 'list', 'GET', ba + '/export', status=200, fields=['name', 'size', 'expires'])
    a(fam, sc, 'bad-type', 'POST', ba + '/export', body={'recipes': ['tomato-soup'], 'exportType': 'pdf'},
      status=422)
    sc = 'delete'
    a(fam, sc, 'salad', 'POST', ba + '/delete', body={'recipes': ['green-salad']}, status=200, hint='none')
    a(fam, sc, 'gone', 'GET', 'recipes/green-salad', status=404)
    a(fam, sc, 'others-remain', 'GET', 'recipes', status=200, fields=['slug'],
      params={'orderBy': 'name', 'orderDirection': 'asc'})
    a(fam, sc, 'anonymous', 'POST', ba + '/delete', actor=None, body={'recipes': ['tomato-soup']}, status=401)

    # -- preferences and explore ------------------------------------------------------------------------------
    fam = 'explore'
    sc = 'private'
    a(fam, sc, 'group-prefs', 'GET', 'groups/preferences', status=200)
    a(fam, sc, 'household-prefs', 'GET', 'households/preferences', status=200)
    a(fam, sc, 'recipes-hidden', 'GET', 'explore/groups/home/recipes', actor=None, status=404)
    a(fam, sc, 'tags-hidden', 'GET', 'explore/groups/home/organizers/tags', actor=None, status=404)
    sc = 'public'
    a(fam, sc, 'open-group', 'PUT', 'groups/preferences', body={'privateGroup': False, 'showAnnouncements': True},
      status=200)
    a(fam, sc, 'open-household', 'PUT', 'households/preferences', status=200,
      body={'privateHousehold': False, 'recipePublic': True, 'firstDayOfWeek': 1, 'showAnnouncements': True,
            'lockRecipeEditsFromOtherHouseholds': True, 'recipeShowNutrition': True, 'recipeShowAssets': False,
            'recipeLandscapeView': False, 'recipeDisableComments': False})
    a(fam, sc, 'household-after', 'GET', 'households/preferences', status=200)
    a(fam, sc, 'recipes', 'GET', 'explore/groups/home/recipes', actor=None, status=200, fields=['slug', 'name'],
      params={'orderBy': 'name', 'orderDirection': 'asc'})
    a(fam, sc, 'one-recipe', 'GET', 'explore/groups/home/recipes/tomato-soup', actor=None, status=None,
      fields=['slug', 'name'])
    a(fam, sc, 'tags', 'GET', 'explore/groups/home/organizers/tags', actor=None, status=200,
      fields=['name', 'slug'])
    a(fam, sc, 'categories', 'GET', 'explore/groups/home/organizers/categories', actor=None, status=200,
      fields=['name', 'slug'])
    a(fam, sc, 'unknown-group', 'GET', 'explore/groups/no-such-group/recipes', actor=None, status=404)
    a(fam, sc, 'bad-prefs', 'PUT', 'groups/preferences', body={'privateGroup': 'sometimes'}, status=422)
