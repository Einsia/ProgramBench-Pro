'''The remaining offline surface: recipe actions, household recipe data, empty labels, suggestions, session refresh
and logout, storage details, the public explore API of every organizer kind, admin reads by id, user and timeline
images, single-recipe shopping additions, export download and purge, shared recipe zips and the password-reset path.

Everything here works without any outside service; the parts that need one (scraping, AI providers, OAuth, mail
delivery, outgoing webhooks) are excluded in COVERAGE.md.
'''
import base64

from harness import Ref, pathref
from api_files import pattern_png

MISSING = '00000000-0000-4000-8000-000000000000'


def assert_suggestions(payload, expected):
    items = payload.get('items') if isinstance(payload, dict) else payload if isinstance(payload, list) else None
    assert isinstance(items, list), 'suggestions response has no items list: ' + repr(payload)[:300]
    assert bool(items) is expected, 'suggestion positive/negative corpus differs'


def build(s):
    a = s.api

    sc = 'recipes'
    f = 'extras-fixture'
    a(f, sc, 'soup', 'POST', 'recipes', body={'name': 'Tomato Soup'}, status=201)
    a(f, sc, 'pie', 'POST', 'recipes', body={'name': 'Apple Pie'}, status=201)
    a(f, sc, 'soup-read', 'GET', 'recipes/tomato-soup', status=200, save='soup')
    a(f, sc, 'pie-read', 'GET', 'recipes/apple-pie', status=200, save='pie')
    a(f, sc, 'me', 'GET', 'users/self', status=200, save='me')
    a(f, sc, 'tag', 'POST', 'organizers/tags', body={'name': 'Quick'}, status=201, save='tag')
    a(f, sc, 'category', 'POST', 'organizers/categories', body={'name': 'Dinner'}, status=201, save='cat')
    a(f, sc, 'tool', 'POST', 'organizers/tools', body={'name': 'Oven'}, status=201, save='tool')
    a(f, sc, 'food', 'POST', 'foods', body={'name': 'flour'}, status=201, save='food')
    # A positive recommendation corpus: the food is actually linked to the
    # recipe, with a second recipe left unrelated as a distractor.
    a(f, sc, 'soup-ingredient', 'PATCH', 'recipes/tomato-soup', status=200,
      body=lambda c: {'recipeIngredient': [{'quantity': 1, 'food': c.state['food']}], 'settings': {'public': True}})
    a(f, sc, 'cookbook', 'POST', 'households/cookbooks', body={'name': 'Weeknight', 'public': True}, status=201,
      save='book')
    a(f, sc, 'list', 'POST', 'households/shopping/lists', body={'name': 'Weekly'}, status=201, save='list')

    # -- recipe actions ---------------------------------------------------------------------------------------
    fam = 'recipe-actions'
    ra = 'households/recipe-actions'
    sc = 'create'
    a(fam, sc, 'link', 'POST', ra, status=201, save='action',
      body={'actionType': 'link', 'title': 'Search', 'url': 'https://example.invalid/?q=${slug}'})
    a(fam, sc, 'post', 'POST', ra, status=201, save='action2',
      body={'actionType': 'post', 'title': 'Notify', 'url': 'https://example.invalid/hook'})
    a(fam, sc, 'bad-type', 'POST', ra, status=422, body={'actionType': 'email', 'title': 'x', 'url': 'https://x.invalid'})
    a(fam, sc, 'missing-title', 'POST', ra, status=422, body={'actionType': 'link', 'url': 'https://x.invalid'})
    sc = 'read'
    a(fam, sc, 'list', 'GET', ra, status=200, params={'orderBy': 'title', 'orderDirection': 'asc'})
    a(fam, sc, 'by-id', 'GET', pathref(ra + '/{id}', id=Ref('action', 'id')), status=200)
    a(fam, sc, 'missing', 'GET', ra + '/' + MISSING, status=None)
    sc = 'update'
    a(fam, sc, 'rename', 'PUT', pathref(ra + '/{id}', id=Ref('action', 'id')), status=200,
      body=lambda c: {'actionType': 'link', 'title': 'Look up', 'url': 'https://example.invalid/find/${slug}',
                      'groupId': c.state['me']['groupId'], 'householdId': c.state['me']['householdId']})
    a(fam, sc, 'missing-owner', 'PUT', pathref(ra + '/{id}', id=Ref('action', 'id')), status=422,
      body={'actionType': 'link', 'title': 'Look up', 'url': 'https://example.invalid/find/${slug}'})
    a(fam, sc, 'after', 'GET', pathref(ra + '/{id}', id=Ref('action', 'id')), status=200)
    sc = 'trigger'
    a(fam, sc, 'link-refused', 'POST', pathref(ra + '/{id}/trigger/tomato-soup', id=Ref('action', 'id')),
      status=400)
    a(fam, sc, 'missing-recipe', 'POST', pathref(ra + '/{id}/trigger/no-such-recipe', id=Ref('action', 'id')),
      status=None)
    sc = 'delete'
    a(fam, sc, 'post', 'DELETE', pathref(ra + '/{id}', id=Ref('action2', 'id')), status=200)
    a(fam, sc, 'list-after', 'GET', ra, status=200, params={'orderBy': 'title'})

    # -- household recipe data, empty labels, suggestions -----------------------------------------------------
    fam = 'household-data'
    sc = 'recipe'
    a(fam, sc, 'never-made', 'GET', 'households/self/recipes/tomato-soup', status=200)
    a(fam, sc, 'made', 'PATCH', 'recipes/tomato-soup/last-made', body={'timestamp': '2026-03-04T05:06:07Z'},
      status=200, hint='none')
    a(fam, sc, 'after-made', 'GET', 'households/self/recipes/tomato-soup', status=200)
    a(fam, sc, 'missing', 'GET', 'households/self/recipes/no-such-recipe', status=None)
    sc = 'labels-empty'
    a(fam, sc, 'none', 'GET', 'groups/labels/empty', status=200)
    a(fam, sc, 'spare', 'POST', 'groups/labels', body={'name': 'Spare'}, status=200, hint='none')
    a(fam, sc, 'one', 'GET', 'groups/labels/empty', status=200)
    sc = 'suggestions'
    a(fam, sc, 'by-food', 'GET', 'recipes/suggestions', status=None,
      params=lambda c: {'foods': c.state['food']['id'], 'limit': 5},
      check=lambda c, r, p: assert_suggestions(p, True))
    a(fam, sc, 'without-match', 'GET', 'recipes/suggestions', status=None,
      params={'foods': MISSING, 'limit': 5}, check=lambda c, r, p: assert_suggestions(p, False))
    a(fam, sc, 'bad-limit', 'GET', 'recipes/suggestions', status=None, params={'limit': 'many'})

    # -- session ----------------------------------------------------------------------------------------------
    fam = 'session'
    sc = 'refresh'
    a(fam, sc, 'refresh', 'POST', 'auth/refresh', status=200)
    a(fam, sc, 'anonymous', 'POST', 'auth/refresh', actor=None, status=None)
    sc = 'logout'
    a(fam, sc, 'logout', 'POST', 'auth/logout', status=200)
    sc = 'password-reset'
    a(fam, sc, 'forgot-unknown', 'POST', 'users/forgot-password', actor=None, body={'email': 'nobody@example.com'},
      status=None)
    a(fam, sc, 'forgot-bad-email', 'POST', 'users/forgot-password', actor=None, body={'email': 'not-an-email'},
      status=None)
    a(fam, sc, 'reset-bad-token', 'POST', 'users/reset-password', actor=None, status=None,
      body={'token': 'not-a-token', 'email': 'changeme@example.com', 'password': 'NewPass123!',
            'passwordConfirm': 'NewPass123!'})
    a(fam, sc, 'reset-mismatch', 'POST', 'users/reset-password', actor=None, status=400,
      body={'token': 'x', 'email': 'changeme@example.com', 'password': 'NewPass123!', 'passwordConfirm': 'Other1!'})
    sc = 'mail'
    a(fam, sc, 'email-config', 'GET', 'admin/email', status=200)

    # -- admin reads ------------------------------------------------------------------------------------------
    fam = 'admin-reads'
    sc = 'by-id'
    a(fam, sc, 'household', 'GET', pathref('admin/households/{id}', id=Ref('me', 'householdId')), status=200,
      fields=['name', 'slug', 'groupId', 'id'])
    a(fam, sc, 'group', 'GET', pathref('admin/groups/{id}', id=Ref('me', 'groupId')), status=200,
      fields=['name', 'slug', 'id'])
    a(fam, sc, 'missing-household', 'GET', 'admin/households/' + MISSING, status=None)
    a(fam, sc, 'missing-group', 'GET', 'admin/groups/' + MISSING, status=None)
    a(fam, sc, 'storage', 'GET', 'admin/maintenance/storage', status=200)
    a(fam, sc, 'branding-logo', 'GET', 'app/about/branding-logo', actor=None, status=None)

    # -- images -----------------------------------------------------------------------------------------------
    image = base64.b64encode(pattern_png(180, 180)).decode()
    fam = 'images'
    sc = 'user'
    a(fam, sc, 'upload', 'POST', pathref('users/{u}/image', u=Ref('me', 'id')), status=200, hint='none',
      multipart={'files': {'profile': {'filename': 'me.png', 'base64': image, 'mime_type': 'image/png'}}})
    a(fam, sc, 'served', 'GET', pathref('media/users/{u}/profile.webp', u=Ref('me', 'id')), actor=None,
      status=200, hint='image')
    a(fam, sc, 'missing-file', 'GET', pathref('media/users/{u}/nothing.webp', u=Ref('me', 'id')), actor=None,
      status=None)
    sc = 'timeline'
    a(fam, sc, 'event', 'POST', 'recipes/timeline/events', status=201, save='event',
      body=lambda c: {'recipeId': c.state['soup']['id'], 'subject': 'Photo', 'eventType': 'info',
                      'timestamp': '2026-01-02T03:04:05Z'})
    a(fam, sc, 'upload', 'PUT', pathref('recipes/timeline/events/{e}/image', e=Ref('event', 'id')), status=200,
      multipart={'fields': {'extension': 'png'},
                 'files': {'image': {'filename': 'photo.png', 'base64': image, 'mime_type': 'image/png'}}})
    a(fam, sc, 'event-after', 'GET', pathref('recipes/timeline/events/{e}', e=Ref('event', 'id')), status=200,
      fields=['image', 'subject'])
    a(fam, sc, 'served', 'GET', pathref('media/recipes/{r}/images/timeline/{e}/original.webp',
                                         r=Ref('soup', 'id'), e=Ref('event', 'id')), actor=None, status=None,
      hint='image')

    # -- shopping: one recipe ---------------------------------------------------------------------------------
    fam = 'shopping-recipe'
    sc = 'single'
    a(fam, sc, 'ingredients', 'PATCH', 'recipes/apple-pie', status=200, hint='none',
      body={'recipeIngredient': [{'note': '6 apples', 'quantity': 6, 'display': '6 apples'},
                                 {'note': 'sugar', 'quantity': 1}]})
    a(fam, sc, 'add', 'POST', pathref('households/shopping/lists/{l}/recipe/{r}', l=Ref('list', 'id'),
                                      r=Ref('pie', 'id')), status=200,
      fields=['name', 'recipeReferences'])
    a(fam, sc, 'list-after', 'GET', pathref('households/shopping/lists/{l}', l=Ref('list', 'id')), status=200,
      fields=['listItems', 'recipeReferences'])

    # -- exports: download and purge, shared zip --------------------------------------------------------------
    fam = 'export-files'
    sc = 'bulk'
    a(fam, sc, 'start', 'POST', 'recipes/bulk-actions/export', status=202,
      body={'recipes': ['tomato-soup'], 'exportType': 'json'})
    a(fam, sc, 'list', 'GET', 'recipes/bulk-actions/export', status=200, save='exports', fields=['name'])
    a(fam, sc, 'token', 'GET', lambda c: 'recipes/bulk-actions/export/%s/download' % c.state['exports'][0]['id'],
      status=200, save='export-token')
    a(fam, sc, 'download', 'GET', lambda c: 'utils/download?token=' + c.state['export-token']['fileToken'],
      actor=None, status=200, hint='zip')
    a(fam, sc, 'missing', 'GET', 'recipes/bulk-actions/export/%s/download' % MISSING, status=None)
    a(fam, sc, 'purge', 'DELETE', 'recipes/bulk-actions/export/purge', status=200)
    a(fam, sc, 'after-purge', 'GET', 'recipes/bulk-actions/export', status=200)
    sc = 'shared-zip'
    a(fam, sc, 'share', 'POST', 'shared/recipes', body=lambda c: {'recipeId': c.state['soup']['id']},
      status=201, save='share', fields=['recipeId'])
    a(fam, sc, 'zip', 'GET', pathref('recipes/shared/{t}/zip', t=Ref('share', 'id')), actor=None, status=None,
      hint='zip')
    a(fam, sc, 'missing', 'GET', 'recipes/shared/%s/zip' % MISSING, actor=None, status=None)

    # -- explore: every organizer kind ------------------------------------------------------------------------
    fam = 'explore-all'
    ex = 'explore/groups/home/'
    sc = 'private'
    a(fam, sc, 'foods', 'GET', ex + 'foods', actor=None, status=404)
    a(fam, sc, 'households', 'GET', ex + 'households', actor=None, status=404)
    a(fam, sc, 'cookbooks', 'GET', ex + 'cookbooks', actor=None, status=404)
    sc = 'public'
    a(fam, sc, 'open-group', 'PUT', 'groups/preferences', body={'privateGroup': False, 'showAnnouncements': True},
      status=200, hint='none')
    a(fam, sc, 'open-household', 'PUT', 'households/preferences', status=200, hint='none',
      body={'privateHousehold': False, 'recipePublic': True, 'firstDayOfWeek': 0, 'showAnnouncements': True,
            'lockRecipeEditsFromOtherHouseholds': True, 'recipeShowNutrition': False, 'recipeShowAssets': False,
            'recipeLandscapeView': False, 'recipeDisableComments': False})
    a(fam, sc, 'foods', 'GET', ex + 'foods', actor=None, status=200, fields=['name'])
    a(fam, sc, 'food', 'GET', pathref(ex + 'foods/{id}', id=Ref('food', 'id')), actor=None, status=200,
      fields=['name', 'id'])
    a(fam, sc, 'households', 'GET', ex + 'households', actor=None, status=200, fields=['name', 'slug'])
    a(fam, sc, 'household', 'GET', ex + 'households/family', actor=None, status=200, fields=['name', 'slug'])
    a(fam, sc, 'missing-household', 'GET', ex + 'households/no-such-household', actor=None, status=None)
    a(fam, sc, 'tools', 'GET', ex + 'organizers/tools', actor=None, status=200, fields=['name', 'slug'])
    a(fam, sc, 'tool', 'GET', pathref(ex + 'organizers/tools/{id}', id=Ref('tool', 'id')), actor=None,
      status=200, fields=['name', 'slug'])
    a(fam, sc, 'tag', 'GET', pathref(ex + 'organizers/tags/{id}', id=Ref('tag', 'id')), actor=None,
      status=200, fields=['name', 'slug'])
    a(fam, sc, 'category', 'GET', pathref(ex + 'organizers/categories/{id}', id=Ref('cat', 'id')), actor=None,
      status=200, fields=['name', 'slug'])
    a(fam, sc, 'missing-tag', 'GET', ex + 'organizers/tags/' + MISSING, actor=None, status=None)
    a(fam, sc, 'cookbooks', 'GET', ex + 'cookbooks', actor=None, status=200, fields=['name', 'slug', 'public'])
    a(fam, sc, 'cookbook', 'GET', pathref(ex + 'cookbooks/{id}', id=Ref('book', 'id')), actor=None,
      status=None, fields=['name', 'slug'])
    a(fam, sc, 'suggestions', 'GET', ex + 'recipes/suggestions', actor=None, status=None,
      params=lambda c: {'foods': c.state['food']['id']}, check=lambda c,r,p: assert_suggestions(p,True))

    # -- bulk update of recipes -------------------------------------------------------------------------------
    fam = 'recipes-many'
    sc = 'update'
    a(fam, sc, 'put-empty', 'PUT', 'recipes', body=[], status=200)
    a(fam, sc, 'put-bad', 'PUT', 'recipes', body={'name': 'x'}, status=422)
