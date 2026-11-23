'''Meal plans of the household: entries on days, today's meals, the random pick, plan rules and the iCal feed.

Entries are notes or recipe links on a day with a meal type. Listing filters by a day range; today's meals are the
entries dated today. The random pick chooses among recipes matching the day's rules, so the cases leave exactly one
candidate. Rules are created, read, replaced and deleted. The iCal token is created, read, used by an anonymous
client for the feed and revoked. Validation and missing-item errors are part of the contract.
'''
from harness import Ref, day, pathref

MISSING = '00000000-0000-4000-8000-000000000000'
MISSING_ENTRY = '999999'


def build(s):
    a = s.api
    base, fam = 'households/mealplans', 'mealplans'

    # A rule and a distractor are prepared before the random pick. The rule
    # should select the later Lentil Soup recipe and exclude the distractor.
    a('mealplans-fixture', 'random-filter', 'rule', 'POST', base + '/rules', status=201,
      body={'day': 'unset', 'entryType': 'unset', 'queryFilterString': 'name = "Lentil Soup"'})
    a('mealplans-fixture', 'random-filter', 'distractor', 'POST', 'recipes',
      body={'name': 'Distractor Stew'}, status=201)

    sc = 'recipes'
    a(fam, sc, 'soup', 'POST', 'recipes', body={'name': 'Lentil Soup'}, status=201)
    a(fam, sc, 'read-soup', 'GET', 'recipes/lentil-soup', save='soup')

    sc = 'create'
    a(fam, sc, 'note-today', 'POST', base, status=201, save='note',
      body=lambda c: {'date': day(0), 'entryType': 'dinner', 'title': 'Leftovers', 'text': 'Use the rice'})
    a(fam, sc, 'recipe-tomorrow', 'POST', base, status=201, save='entry',
      body=lambda c: {'date': day(1), 'entryType': 'lunch', 'recipeId': c.state['soup']['id'], 'recipeScale': 2})
    a(fam, sc, 'breakfast-today', 'POST', base, status=201,
      body=lambda c: {'date': day(0), 'entryType': 'breakfast', 'title': 'Oatmeal'})
    a(fam, sc, 'side-next-week', 'POST', base, status=201,
      body=lambda c: {'date': day(7), 'entryType': 'side', 'title': 'Salad'})
    a(fam, sc, 'far-past', 'POST', base, status=201,
      body={'date': '2020-02-29', 'entryType': 'dessert', 'title': 'Leap cake'})
    a(fam, sc, 'bad-type', 'POST', base, status=422, body=lambda c: {'date': day(0), 'entryType': 'brunch'})
    a(fam, sc, 'bad-date', 'POST', base, status=422, body={'date': 'tomorrow', 'entryType': 'dinner'})
    a(fam, sc, 'missing-date', 'POST', base, status=422, body={'entryType': 'dinner', 'title': 'x'})
    a(fam, sc, 'anonymous', 'POST', base, actor=None, status=401,
      body=lambda c: {'date': day(0), 'entryType': 'dinner'})

    sc = 'read'
    a(fam, sc, 'note', 'GET', pathref(base + '/{id}', id=Ref('note', 'id')))
    a(fam, sc, 'recipe-entry', 'GET', pathref(base + '/{id}', id=Ref('entry', 'id')))
    a(fam, sc, 'recipe-scale', 'GET', pathref(base + '/{id}', id=Ref('entry', 'id')),
      fields=['recipeId', 'recipeScale'])
    a(fam, sc, 'missing', 'GET', base + '/' + MISSING_ENTRY, status=404)
    a(fam, sc, 'today', 'GET', base + '/today')

    sc = 'list'
    a(fam, sc, 'week', 'GET', base, params=lambda c: {'start_date': day(0), 'end_date': day(6), 'orderBy': 'date'})
    a(fam, sc, 'one-day', 'GET', base, params=lambda c: {'start_date': day(1), 'end_date': day(1)})
    a(fam, sc, 'all-by-date', 'GET', base, params={'orderBy': 'date', 'orderDirection': 'asc'})
    a(fam, sc, 'all-by-date-desc', 'GET', base, params={'orderBy': 'date', 'orderDirection': 'desc'})
    a(fam, sc, 'empty-range', 'GET', base, params={'start_date': '2001-01-01', 'end_date': '2001-01-31'})
    a(fam, sc, 'page', 'GET', base, params={'orderBy': 'date', 'perPage': 2, 'page': 2})
    a(fam, sc, 'filter-type', 'GET', base, params={'queryFilter': 'entryType = "dinner"', 'orderBy': 'date'})
    a(fam, sc, 'bad-date', 'GET', base, params={'start_date': 'soon'}, status=422)

    sc = 'update'
    a(fam, sc, 'retitle', 'PUT', pathref(base + '/{id}', id=Ref('note', 'id')),
      body=lambda c: {**c.state['note'], 'title': 'Fried rice', 'entryType': 'lunch'})
    a(fam, sc, 'read-retitled', 'GET', pathref(base + '/{id}', id=Ref('note', 'id')))
    a(fam, sc, 'move-day', 'PUT', pathref(base + '/{id}', id=Ref('entry', 'id')),
      body=lambda c: {**c.state['entry'], 'date': day(2)})
    a(fam, sc, 'list-after-move', 'GET', base, params=lambda c: {'start_date': day(2), 'end_date': day(2)})
    a(fam, sc, 'bad-type', 'PUT', pathref(base + '/{id}', id=Ref('note', 'id')),
      body=lambda c: {**c.state['note'], 'entryType': 'brunch'}, status=422)
    a(fam, sc, 'missing', 'PUT', base + '/' + MISSING_ENTRY,
      body=lambda c: {**c.state['note'], 'id': MISSING}, status=None)

    sc = 'random'
    a(fam, sc, 'pick', 'POST', base + '/random', status=200, save='random-entry',
      body=lambda c: {'date': day(3), 'entryType': 'dinner'},want={'recipeId':Ref('soup','id')})
    a(fam, sc, 'picked-recipe', 'GET', pathref(base + '/{id}', id=Ref('random-entry', 'id')),
      fields=['recipeId', 'entryType'])
    a(fam, sc, 'list-day', 'GET', base, params=lambda c: {'start_date': day(3), 'end_date': day(3)})
    a(fam, sc, 'bad-type', 'POST', base + '/random', status=422, body=lambda c: {'date': day(3), 'entryType': 'x'})

    rules, rf = base + '/rules', 'mealplan-rules'
    sc = 'create'
    a(rf, sc, 'monday-dinner', 'POST', rules, status=201, save='rule',
      body={'day': 'monday', 'entryType': 'dinner', 'queryFilterString': 'name LIKE "%soup%"'})
    a(rf, sc, 'unset', 'POST', rules, status=201, body={'day': 'unset', 'entryType': 'unset'})
    a(rf, sc, 'defaults', 'POST', rules, status=201, body={})
    a(rf, sc, 'bad-day', 'POST', rules, status=422, body={'day': 'someday', 'entryType': 'dinner'})
    a(rf, sc, 'bad-type', 'POST', rules, status=422, body={'day': 'monday', 'entryType': 'brunch'})
    a(rf, sc, 'anonymous', 'POST', rules, actor=None, status=401, body={'day': 'monday'})
    sc = 'read'
    a(rf, sc, 'one', 'GET', pathref(rules + '/{id}', id=Ref('rule', 'id')))
    a(rf, sc, 'missing', 'GET', rules + '/' + MISSING, status=404)
    a(rf, sc, 'list', 'GET', rules, params={'orderBy': 'day'})
    sc = 'update'
    a(rf, sc, 'friday', 'PUT', pathref(rules + '/{id}', id=Ref('rule', 'id')),
      body={'day': 'friday', 'entryType': 'lunch', 'queryFilterString': ''})
    a(rf, sc, 'read-updated', 'GET', pathref(rules + '/{id}', id=Ref('rule', 'id')))
    a(rf, sc, 'bad-day', 'PUT', pathref(rules + '/{id}', id=Ref('rule', 'id')), body={'day': 'x'}, status=422)
    sc = 'delete'
    a(rf, sc, 'one', 'DELETE', pathref(rules + '/{id}', id=Ref('rule', 'id')))
    a(rf, sc, 'gone', 'GET', pathref(rules + '/{id}', id=Ref('rule', 'id')), status=404)
    a(rf, sc, 'list-after', 'GET', rules, params={'orderBy': 'day'})

    ical, ic = base + '/ical', 'mealplan-ical'
    sc = 'token'
    a(ic, sc, 'none-yet', 'GET', ical, status=None)
    a(ic, sc, 'create', 'POST', ical, status=None, save='ical')
    a(ic, sc, 'read', 'GET', ical)
    a(ic, sc, 'anonymous', 'POST', ical, actor=None, status=401)
    sc = 'feed'
    a(ic, sc, 'anonymous-read', 'GET', pathref(ical + '/{t}', t=Ref('ical', 'mealplanIcalToken')), actor=None, hint='text',
      check=lambda c, r, p: None)
    a(ic, sc, 'wrong-token', 'GET', ical + '/not-a-token', actor=None, status=None)
    sc = 'revoke'
    a(ic, sc, 'delete', 'DELETE', ical, status=None)
    a(ic, sc, 'old-feed', 'GET', pathref(ical + '/{t}', t=Ref('ical', 'mealplanIcalToken')), actor=None, status=None)

    sc = 'delete'
    a(fam, sc, 'one', 'DELETE', pathref(base + '/{id}', id=Ref('note', 'id')))
    a(fam, sc, 'gone', 'GET', pathref(base + '/{id}', id=Ref('note', 'id')), status=404)
    a(fam, sc, 'again', 'DELETE', pathref(base + '/{id}', id=Ref('note', 'id')), status=None)
    a(fam, sc, 'today-after', 'GET', base + '/today')
