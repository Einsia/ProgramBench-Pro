'''Accounts: users, households, groups, permissions, invitations, API tokens, preferences, webhooks and notifiers.

A second member (bob) is created in the admin's household. Self-service reads and edits, admin-only routes refused
for a member, household permissions, invitations, long-lived tokens, password change and a sign-in with the new
password, household and group preferences, webhooks and notifiers (stored only; their test calls need the network).
'''
from harness import Ref, pathref

MISSING = '00000000-0000-4000-8000-000000000000'
BOB = {'username': 'bob', 'fullName': 'Bob Baker', 'email': 'bob@example.com', 'password': 'BobPassword1', 'admin': False}
CAROL = {'username': 'carol', 'fullName': 'Carol Cook', 'email': 'carol@example.com', 'password': 'CarolPassword1',
         'admin': False}


def creds(**pairs):
    return lambda c: c.creds.update(pairs)


def build(s):
    a = s.api
    fx = 'accounts-fixture'
    a(fx, 'users', 'bob', 'POST', 'admin/users', body=BOB, save='bob', before=creds(bob=BOB['password']))
    a(fx, 'users', 'carol', 'POST', 'admin/users', body=CAROL, save='carol', before=creds(carol=CAROL['password']))
    a(fx, 'users', 'household', 'GET', 'households/self', save='home')

    # Self service.
    f, sc = 'users-self', 'profile'
    a(f, sc, 'admin-self', 'GET', 'users/self', status=200)
    a(f, sc, 'member-self', 'GET', 'users/self', actor='bob', status=200)
    a(f, sc, 'anonymous', 'GET', 'users/self', actor=None, status=401)
    a(f, sc, 'rename', 'PUT', pathref('users/{id}', id=Ref('bob', 'id')), actor='bob', status=200,
      body=lambda c: {**c.state['bob'], 'fullName': 'Robert Baker'})
    a(f, sc, 'after-rename', 'GET', 'users/self', actor='bob', status=200, fields=['fullName', 'username', 'email'])
    a(f, sc, 'edit-other', 'PUT', pathref('users/{id}', id=Ref('carol', 'id')), actor='bob', status=None,
      body=lambda c: {**c.state['carol'], 'fullName': 'Hijacked'})
    a(f, sc, 'other-unchanged', 'GET', pathref('admin/users/{id}', id=Ref('carol', 'id')), status=200,
      fields=['fullName'])
    a(f, sc, 'favorites-empty', 'GET', 'users/self/favorites', actor='bob', status=200)
    a(f, sc, 'ratings-empty', 'GET', 'users/self/ratings', actor='bob', status=200)

    # Passwords.
    f, sc = 'users-password', 'change'
    a(f, sc, 'wrong-current', 'PUT', 'users/password', actor='carol', status=400,
      body={'currentPassword': 'nope', 'newPassword': 'CarolPassword2'})
    a(f, sc, 'short-new', 'PUT', 'users/password', actor='carol', status=None,
      body={'currentPassword': CAROL['password'], 'newPassword': 'x'})
    a(f, sc, 'change', 'PUT', 'users/password', actor='carol', status=200,
      body={'currentPassword': CAROL['password'], 'newPassword': 'CarolPassword2'})
    a(f, sc, 'old-refused', 'POST', 'auth/token', actor=None, status=401, hint='none',
      form={'username': 'carol', 'password': CAROL['password']})
    a(f, sc, 'new-accepted', 'POST', 'auth/token', actor=None, status=200,
      form={'username': 'carol', 'password': 'CarolPassword2'}, fields=['token_type'])
    a(f, sc, 'by-email', 'POST', 'auth/token', actor=None, status=200,
      form={'username': 'carol@example.com', 'password': 'CarolPassword2'}, fields=['token_type'])
    a(f, sc, 'unknown-user', 'POST', 'auth/token', actor=None, status=401, hint='none',
      form={'username': 'nobody', 'password': 'whatever'})

    # Admin user management.
    f, sc = 'users-admin', 'manage'
    a(f, sc, 'list', 'GET', 'admin/users', status=200, params={'orderBy': 'username', 'orderDirection': 'asc'},
      fields=['username', 'fullName', 'admin'])
    a(f, sc, 'member-list', 'GET', 'admin/users', actor='bob', status=403)
    a(f, sc, 'member-create', 'POST', 'admin/users', actor='bob', status=403,
      body={'username': 'mallory', 'fullName': 'M', 'email': 'm@example.com', 'password': 'MalloryPass1'})
    a(f, sc, 'duplicate-username', 'POST', 'admin/users', status=None,
      body={**BOB, 'email': 'other@example.com'})
    a(f, sc, 'duplicate-email', 'POST', 'admin/users', status=None,
      body={**BOB, 'username': 'bobby'})
    a(f, sc, 'missing-email', 'POST', 'admin/users', status=422,
      body={'username': 'dave', 'fullName': 'Dave', 'password': 'DavePassword1'})
    a(f, sc, 'read', 'GET', pathref('admin/users/{id}', id=Ref('bob', 'id')), status=200,
      fields=['username', 'fullName', 'email', 'admin', 'household', 'group'])
    a(f, sc, 'read-missing', 'GET', 'admin/users/' + MISSING, status=None)
    a(f, sc, 'promote', 'PUT', pathref('admin/users/{id}', id=Ref('carol', 'id')), status=200,
      body=lambda c: {**c.state['carol'], 'admin': True, 'advanced': True})
    a(f, sc, 'after-promote', 'GET', pathref('admin/users/{id}', id=Ref('carol', 'id')), status=200,
      fields=['admin', 'advanced'])
    a(f, sc, 'reset-token', 'POST', 'admin/users/password-reset-token', status=201, body={'email': 'bob@example.com'})
    a(f, sc, 'unlock', 'POST', 'admin/users/unlock', status=200, params={'force': 'true'})
    a(f, sc, 'delete', 'DELETE', pathref('admin/users/{id}', id=Ref('carol', 'id')), status=200,
      fields=['username'])
    a(f, sc, 'after-delete', 'GET', 'admin/users', status=200, params={'orderBy': 'username', 'orderDirection': 'asc'},
      fields=['username'])
    a(f, sc, 'delete-again', 'DELETE', pathref('admin/users/{id}', id=Ref('carol', 'id')), status=None)

    # Long-lived API tokens.
    f, sc = 'users-tokens', 'tokens'
    a(f, sc, 'create', 'POST', 'users/api-tokens', actor='bob', status=201, body={'name': 'cli'}, save='tok')
    a(f, sc, 'missing-name', 'POST', 'users/api-tokens', actor='bob', status=422, body={})
    a(f, sc, 'use', 'GET', 'users/self', actor=None, status=200, fields=['username'],
      headers=lambda c: {'Authorization': 'Bearer ' + c.state['tok']['token']})
    a(f, sc, 'listed', 'GET', 'users/self', actor='bob', status=200, fields=['tokens'])
    a(f, sc, 'delete', 'DELETE', pathref('users/api-tokens/{id}', id=Ref('tok', 'id')), actor='bob', status=200, hint='none')
    a(f, sc, 'revoked', 'GET', 'users/self', actor=None, status=401, hint='none',
      headers=lambda c: {'Authorization': 'Bearer ' + c.state['tok']['token']})
    a(f, sc, 'garbage', 'GET', 'users/self', actor=None, status=401, hint='none',
      headers={'Authorization': 'Bearer not-a-token'})

    # Household.
    f, sc = 'household', 'members'
    a(f, sc, 'self', 'GET', 'households/self', status=200, fields=['name', 'slug', 'preferences'])
    a(f, sc, 'members', 'GET', 'households/members', status=200,
      params={'orderBy': 'username', 'orderDirection': 'asc'}, fields=['username', 'canManage', 'canInvite'])
    a(f, sc, 'statistics', 'GET', 'households/statistics', status=200)
    a(f, sc, 'grant', 'PUT', 'households/permissions', status=200, fields=['canManage', 'canInvite', 'canOrganize'],
      body=lambda c: {'userId': c.state['bob']['id'], 'canManage': True, 'canInvite': True, 'canOrganize': False})
    a(f, sc, 'grant-by-member', 'PUT', 'households/permissions', actor='bob', status=None,
      body=lambda c: {'userId': c.state['bob']['id'], 'canManage': True, 'canInvite': True, 'canOrganize': True})
    a(f, sc, 'grant-unknown', 'PUT', 'households/permissions', status=None,
      body={'userId': MISSING, 'canManage': True, 'canInvite': True, 'canOrganize': True})
    a(f, sc, 'after-grant', 'GET', 'users/self', actor='bob', status=200,
      fields=['canManage', 'canInvite', 'canOrganize'])

    f, sc = 'household', 'preferences'
    a(f, sc, 'read', 'GET', 'households/preferences', status=200)
    a(f, sc, 'update', 'PUT', 'households/preferences', status=200,
      body={'privateHousehold': False, 'firstDayOfWeek': 1, 'recipePublic': True, 'recipeShowNutrition': True,
            'recipeShowAssets': True, 'recipeLandscapeView': True, 'recipeDisableComments': True,
            'lockRecipeEditsFromOtherHouseholds': False, 'showAnnouncements': False})
    a(f, sc, 'after-update', 'GET', 'households/preferences', status=200)
    a(f, sc, 'bad-day', 'PUT', 'households/preferences', status=422, body={'firstDayOfWeek': 'monday'})

    f, sc = 'household', 'invitations'
    a(f, sc, 'none', 'GET', 'households/invitations', status=200)
    a(f, sc, 'create', 'POST', 'households/invitations', status=201, body={'uses': 2}, save='invite')
    a(f, sc, 'listed', 'GET', 'households/invitations', status=200)
    a(f, sc, 'register', 'POST', 'users/register', actor=None, status=201,
      body=lambda c: {'group': '', 'household': '', 'groupToken': c.state['invite']['token'], 'email': 'erin@example.com',
                      'username': 'erin', 'fullName': 'Erin', 'password': 'ErinPassword1',
                      'passwordConfirm': 'ErinPassword1', 'advanced': False, 'private': False, 'seedData': False,
                      'locale': 'en-US'}, fields=['username', 'fullName', 'email', 'household'])
    a(f, sc, 'uses-left', 'GET', 'households/invitations', status=200)
    a(f, sc, 'bad-token', 'POST', 'users/register', actor=None, status=None,
      body={'group': '', 'household': '', 'groupToken': 'not-a-token', 'email': 'frank@example.com', 'username': 'frank',
            'fullName': 'Frank', 'password': 'FrankPassword1', 'passwordConfirm': 'FrankPassword1', 'advanced': False,
            'private': False, 'seedData': False, 'locale': 'en-US'})
    a(f, sc, 'mismatch', 'POST', 'users/register', actor=None, status=422,
      body=lambda c: {'group': '', 'household': '', 'groupToken': c.state['invite']['token'], 'email': 'gina@example.com',
                      'username': 'gina', 'fullName': 'Gina', 'password': 'GinaPassword1',
                      'passwordConfirm': 'Different1', 'advanced': False, 'private': False, 'seedData': False,
                      'locale': 'en-US'})

    # Group.
    f, sc = 'group', 'self'
    a(f, sc, 'self', 'GET', 'groups/self', status=200, fields=['name', 'slug', 'preferences'])
    a(f, sc, 'preferences', 'GET', 'groups/preferences', status=200)
    a(f, sc, 'update-preferences', 'PUT', 'groups/preferences', status=200,
      body={'privateGroup': False, 'showAnnouncements': False})
    a(f, sc, 'after-update', 'GET', 'groups/preferences', status=200)
    a(f, sc, 'member-update-preferences', 'PUT', 'groups/preferences', actor='bob', status=None,
      body={'privateGroup': True, 'showAnnouncements': True})
    a(f, sc, 'members', 'GET', 'groups/members', status=200, params={'orderBy': 'username', 'orderDirection': 'asc'},
      fields=['username'])
    a(f, sc, 'member-by-name', 'GET', 'groups/members/bob', status=200, fields=['username', 'fullName'])
    a(f, sc, 'member-missing', 'GET', 'groups/members/nobody', status=None)
    a(f, sc, 'households', 'GET', 'groups/households', status=200, fields=['name', 'slug'])
    a(f, sc, 'household-by-slug', 'GET', 'groups/households/family', status=200, fields=['name', 'slug'])
    a(f, sc, 'household-missing', 'GET', 'groups/households/nowhere', status=None)

    f, sc = 'group', 'admin'
    a(f, sc, 'create', 'POST', 'admin/groups', status=201, body={'name': 'Cabin'}, save='cabin',
      fields=['name', 'slug', 'households', 'users', 'preferences'])
    a(f, sc, 'duplicate', 'POST', 'admin/groups', status=None, body={'name': 'Cabin'})
    a(f, sc, 'list', 'GET', 'admin/groups', status=200, params={'orderBy': 'name', 'orderDirection': 'asc'},
      fields=['name', 'slug'])
    a(f, sc, 'member-list', 'GET', 'admin/groups', actor='bob', status=403)
    a(f, sc, 'rename', 'PUT', pathref('admin/groups/{id}', id=Ref('cabin', 'id')), status=200,
      body=lambda c: {'id': c.state['cabin']['id'], 'name': 'Lake Cabin',
                      'preferences': {'privateGroup': False, 'showAnnouncements': True}}, fields=['name', 'preferences'])
    a(f, sc, 'add-household', 'POST', 'admin/households', status=201,
      body=lambda c: {'groupId': c.state['cabin']['id'], 'name': 'Weekend'}, save='weekend',
      fields=['name', 'slug', 'group'])
    a(f, sc, 'households', 'GET', 'admin/households', status=200, params={'orderBy': 'name', 'orderDirection': 'asc'},
      fields=['name', 'slug', 'group'])
    a(f, sc, 'rename-household', 'PUT', pathref('admin/households/{id}', id=Ref('weekend', 'id')), status=200,
      body=lambda c: {'id': c.state['weekend']['id'], 'groupId': c.state['cabin']['id'], 'name': 'Long Weekend'},
      fields=['name', 'slug'])
    a(f, sc, 'delete-household', 'DELETE', pathref('admin/households/{id}', id=Ref('weekend', 'id')), status=200,
      fields=['name'])
    a(f, sc, 'delete-group', 'DELETE', pathref('admin/groups/{id}', id=Ref('cabin', 'id')), status=None)
    a(f, sc, 'after-delete', 'GET', 'admin/groups', status=200, params={'orderBy': 'name', 'orderDirection': 'asc'},
      fields=['name'])

    # Webhooks and notifiers are stored; sending needs the network and is not scored.
    f, sc = 'household-webhooks', 'webhooks'
    hooks = 'households/webhooks'
    a(f, sc, 'create', 'POST', hooks, status=201, save='hook',
      body={'enabled': False, 'name': 'Dinner hook', 'url': 'http://example.invalid/dinner', 'webhookType': 'mealplan',
            'scheduledTime': '17:30'})
    a(f, sc, 'bad-time', 'POST', hooks, status=422,
      body={'enabled': False, 'name': 'x', 'url': 'http://example.invalid/x', 'webhookType': 'mealplan',
            'scheduledTime': 'evening'})
    a(f, sc, 'list', 'GET', hooks, status=200)
    a(f, sc, 'read', 'GET', pathref(hooks + '/{id}', id=Ref('hook', 'id')), status=200)
    a(f, sc, 'update', 'PUT', pathref(hooks + '/{id}', id=Ref('hook', 'id')), status=200,
      body={'enabled': True, 'name': 'Lunch hook', 'url': 'http://example.invalid/lunch', 'webhookType': 'mealplan',
            'scheduledTime': '11:45'})
    a(f, sc, 'delete', 'DELETE', pathref(hooks + '/{id}', id=Ref('hook', 'id')), status=200)
    a(f, sc, 'read-deleted', 'GET', pathref(hooks + '/{id}', id=Ref('hook', 'id')), status=None)

    f, sc = 'household-notifiers', 'notifiers'
    notes = 'households/events/notifications'
    a(f, sc, 'create', 'POST', notes, status=201, save='note',
      body={'name': 'Kitchen', 'appriseUrl': 'json://example.invalid/kitchen'})
    a(f, sc, 'list', 'GET', notes, status=200)
    a(f, sc, 'read', 'GET', pathref(notes + '/{id}', id=Ref('note', 'id')), status=200)
    a(f, sc, 'update', 'PUT', pathref(notes + '/{id}', id=Ref('note', 'id')), status=200,
      body=lambda c: {**c.state['note'], 'name': 'Pantry', 'enabled': False,
                      'options': {**c.state['note']['options'], 'recipeCreated': True, 'mealplanEntryCreated': True}})
    a(f, sc, 'after-update', 'GET', pathref(notes + '/{id}', id=Ref('note', 'id')), status=200)
    a(f, sc, 'delete', 'DELETE', pathref(notes + '/{id}', id=Ref('note', 'id')), status=204, hint='none')
    a(f, sc, 'after-delete', 'GET', notes, status=200)
