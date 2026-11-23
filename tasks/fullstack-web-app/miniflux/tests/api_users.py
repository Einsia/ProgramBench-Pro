"""Accounts, user settings, authentication and API keys through the REST API.

Fixture accounts (dave, erin) and a fixture API key are created by setup, so the scored update, delete and
key cases depend only on that lenient setup, never on the exact output of a scored creation."""
from harness import CREDS, Ref, pathref, pick

DAVE = 'Dave-Pass-2026'
ERIN = 'Erin-Pass-2026'
# One valid value per user setting; each differs from the default.
SETTINGS = [
    ('theme', 'dark_sans_serif'), ('language', 'fr_FR'), ('timezone', 'Europe/Paris'),
    ('entry_sorting_direction', 'desc'), ('entry_sorting_order', 'created_at'),
    ('stylesheet', 'body { font-size: 18px; }'), ('external_font_hosts', 'fonts.example.com'),
    ('entries_per_page', 25), ('keyboard_shortcuts', False), ('show_reading_time', False), ('entry_swipe', False),
    ('gesture_nav', 'swipe'), ('display_mode', 'fullscreen'), ('default_reading_speed', 300),
    ('cjk_reading_speed', 700), ('default_home_page', 'starred'), ('categories_sorting_order', 'alphabetical'),
    ('mark_read_on_view', False), ('mark_read_on_media_player_completion', True), ('media_playback_rate', 1.75),
    ('block_filter_entry_rules', 'EntryTitle=(?i)sponsored'), ('keep_filter_entry_rules', 'EntryURL=example'),
    ('always_open_external_links', True), ('open_external_links_in_new_tab', False),
]
# One invalid value per validated setting (the valid case of the same setting proves the setting exists).
INVALID = [
    ('theme', 'neon'), ('language', 'xx_YY'), ('timezone', 'Mars/Olympus_Mons'), ('entry_sorting_direction', 'up'),
    ('entry_sorting_order', 'title'), ('entries_per_page', 0), ('categories_sorting_order', 'random'),
    ('display_mode', 'kiosk'), ('gesture_nav', 'pinch'), ('default_reading_speed', 0), ('cjk_reading_speed', -5),
    ('default_home_page', 'nowhere'), ('media_playback_rate', 0.1), ('block_filter_entry_rules', 'EntryTitle=('),
    ('keep_filter_entry_rules', 'Bogus=value'), ('external_font_hosts', 'not a host!'),
]
EXTRA_INVALID = [
    ('entries_per_page-large', 'entries_per_page', 10001), ('media_playback_rate-high', 'media_playback_rate', 4.5),
    ('block_filter_entry_rules-separator', 'block_filter_entry_rules', 'EntryTitle'),
    ('keep_filter_entry_rules-regex', 'keep_filter_entry_rules', 'EntryAuthor=[unclosed'),
]


def preflight(c):
    r, _ = c.request('OPTIONS', 'me', None, headers={'Origin': 'http://client.example',
                                                    'Access-Control-Request-Method': 'GET'})
    def members(value):
        return sorted({x.strip().lower() for x in (value or '').split(',') if x.strip()})
    return {'status': r.status_code, 'allow-origin': r.headers.get('access-control-allow-origin'),
            'allow-methods': members(r.headers.get('access-control-allow-methods')),
            'allow-headers': members(r.headers.get('access-control-allow-headers'))}


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    s.setup('dave', 'create', 'POST', 'users', body={'username': 'dave', 'password': DAVE}, save='dave',
            before=lambda c: c.creds.update(dave=DAVE))
    s.setup('erin', 'create', 'POST', 'users', body={'username': 'erin', 'password': ERIN}, save='erin',
            before=lambda c: c.creds.update(erin=ERIN))
    s.setup('key', 'create', 'POST', 'api-keys', body={'description': 'Fixture key'}, save='key')
    # Created after the baseline accounts but first in username order.
    s.setup('aaron', 'create', 'POST', 'users', body={'username': 'aaron', 'password': 'Aaron-Pass-2026'})
    A = ['fx:accounts']
    U = ['fx:accounts', 'fx:dave', 'fx:erin', 'fx:aaron']

    # Identity of the signed-in account and refusals without valid credentials.
    me = s.api('users', 'me', 'alice', 'GET', 'me', description='The current user of an administrator: every '
               'setting and the administrator flag.')
    s.api('users', 'me', 'bob', 'GET', 'me', actor='bob', description='The current user of an ordinary account.')
    s.api('users', 'me', 'anonymous', 'GET', 'me', actor=None, requires=[me],
          description='Without credentials the API refuses access.')
    s.api('users', 'me', 'wrong-password', 'GET', 'me', actor='invalid', requires=[me],
          description='A wrong password is refused.')
    s.api('users', 'me', 'unknown-user', 'GET', 'me', actor=('nobody', 'Whatever-2026'), requires=[me],
          description='An unknown account is refused.')

    # Listing and reading accounts.
    listed = s.api('users', 'list', 'admin', 'GET', 'users', needs=U, view=pick('username', 'is_admin'),
                   description='An administrator lists every account, sorted by username (not by creation).')
    s.api('users', 'list', 'ordinary', 'GET', 'users', actor='bob', requires=[listed],
          description='An ordinary account cannot list accounts.')
    by_id = s.api('users', 'get', 'by-id', 'GET', pathref('users/{id}', id=Ref('bob', 'id')), needs=A,
                  view=pick('id', 'username', 'is_admin'), description='An administrator reads an account by id.')
    s.api('users', 'get', 'by-name', 'GET', 'users/carol', needs=A, view=pick('id', 'username', 'is_admin'),
          description='An administrator reads an account by username.')
    s.api('users', 'get', 'ordinary-other', 'GET', pathref('users/{id}', id=Ref('alice', 'id')), actor='bob',
          needs=A, requires=[by_id], description='An ordinary account cannot read another account.')
    s.api('users', 'get', 'ordinary-self', 'GET', pathref('users/{id}', id=Ref('bob', 'id')), actor='bob',
          needs=A, requires=[by_id], view=pick('username'),
          description='Whether an ordinary account can read its own record by id.')
    s.api('users', 'get', 'missing-id', 'GET', 'users/987654', requires=[by_id],
          description='An unknown account id is not found.')
    s.api('users', 'get', 'missing-name', 'GET', 'users/nobody-here', requires=[by_id],
          description='An unknown username is not found.')

    # Creating accounts.
    created = s.api('users', 'create', 'plain', 'POST', 'users', body={'username': 'grace', 'password': 'Grace-Pass-2026'},
                    description='Creating an account returns it with the default settings of a new account.')
    s.api('users', 'create', 'sign-in', 'GET', 'me', actor=('grace', 'Grace-Pass-2026'),
          view=pick('username', 'is_admin'), description='The created account signs in with its password.')
    administrator = s.api('users', 'create', 'administrator', 'POST', 'users',
          body={'username': 'heidi', 'password': 'Heidi-Pass-2026', 'is_admin': True},
          view=pick('username', 'is_admin'), description='Creating an administrator account.')
    characters = s.api('users', 'create', 'allowed-characters', 'POST', 'users',
          body={'username': 'ivan.o@ops-team_2', 'password': 'Ivan-Pass-2026'}, view=pick('username'),
          description='Usernames may contain letters, digits, dot, @, dash and underscore.')
    unicode_user = s.api('users', 'create', 'unicode', 'POST', 'users',
                         body={'username': 'jürgen', 'password': 'Jurgen-Pass-2026'},
          view=pick('username'), description='Usernames may contain non-ASCII letters.')
    s.api('users', 'create', 'duplicate', 'POST', 'users', body={'username': 'bob', 'password': 'Another-Pass-2026'},
          requires=[created], description='An existing username cannot be created again.')
    s.api('users', 'create', 'duplicate-case', 'POST', 'users', body={'username': 'BOB', 'password': 'Another-Pass-2026'},
          requires=[created], description='Whether usernames differing only in case are distinct.')
    s.api('users', 'create', 'empty-username', 'POST', 'users', body={'username': '', 'password': 'Some-Pass-2026'},
          requires=[created], description='The username is mandatory.')
    s.api('users', 'create', 'short-password', 'POST', 'users', body={'username': 'kim', 'password': 'abc12'},
          requires=[created], description='A password needs at least six characters.')
    s.api('users', 'create', 'invalid-username', 'POST', 'users', body={'username': 'bad name!', 'password': 'Some-Pass-2026'},
          requires=[created], description='Spaces and punctuation other than . @ - _ are refused in usernames.')
    s.api('users', 'create', 'ordinary', 'POST', 'users', actor='bob',
          body={'username': 'mallory', 'password': 'Mallory-Pass-2026'}, requires=[created],
          description='An ordinary account cannot create accounts.')
    s.api('users', 'create', 'malformed', 'POST', 'users', raw='{"username": "x",', requires=[created],
          error_text=False, description='A malformed JSON body is refused.')
    s.api('users', 'list', 'after-create', 'GET', 'users', view=pick('username', 'is_admin'),
          needs=U + [created, administrator, characters, unicode_user],
          description='The account list after the creations, sorted by username.')

    # Updating settings (alice administers dave).
    D = ['fx:dave']
    dave = pathref('users/{id}', id=Ref('dave', 'id'))
    valid = {}
    for name, value in SETTINGS:
        valid[name] = s.api('settings', 'update', name, 'PUT', dave, body={name: value}, needs=D, view=pick(name),
                            description=f'Updating the user setting {name} returns the account with the new value.')
    for name, value in INVALID:
        s.api('settings', 'invalid', name, 'PUT', dave, body={name: value}, needs=D, requires=[valid[name]],
              description=f'An invalid value of {name} is refused with a validation message.')
    for step, name, value in EXTRA_INVALID:
        s.api('settings', 'invalid', step, 'PUT', dave, body={name: value}, needs=D, requires=[valid[name]],
              description=f'An out-of-range value of {name} is refused with a validation message.')
    together = s.api('settings', 'update', 'several', 'PUT', dave,
                     body={'theme': 'system_serif', 'entries_per_page': 40, 'show_reading_time': True}, needs=D,
                     view=pick('theme', 'entries_per_page', 'show_reading_time'),
                     description='Several settings change in one request.')
    s.api('settings', 'update', 'unknown-field', 'PUT', dave, body={'favourite_color': 'teal'}, needs=D,
          requires=[together], view=pick('theme', 'entries_per_page'),
          description='An unknown field is ignored and leaves the settings unchanged.')
    s.api('settings', 'read', 'after-updates', 'GET', dave, needs=D, view=pick(
        *[n for n, _ in SETTINGS if n not in ('theme', 'entries_per_page', 'show_reading_time')],
        'theme', 'entries_per_page', 'show_reading_time'),
        description='Reading the account shows every updated setting together.')
    s.api('settings', 'update', 'administrator', 'PUT', dave, body={'is_admin': True}, needs=D, view=pick('is_admin'),
          description='An administrator grants the administrator flag.')
    s.api('settings', 'update', 'revoke-administrator', 'PUT', dave, body={'is_admin': False}, needs=D,
          view=pick('is_admin'), description='An administrator revokes the administrator flag.')
    s.api('settings', 'invalid', 'empty-username', 'PUT', dave, body={'username': ''}, needs=D,
          requires=[together], description='The username cannot be emptied.')
    s.api('settings', 'invalid', 'taken-username', 'PUT', dave, body={'username': 'carol'}, needs=D,
          requires=[together], description='The username cannot take another account\'s name.')
    s.api('settings', 'invalid', 'short-password', 'PUT', dave, body={'password': 'tiny'}, needs=D,
          requires=[together], description='A new password needs at least six characters.')
    renamed = s.api('settings', 'update', 'username', 'PUT', dave, body={'username': 'david'}, needs=D,
                    view=pick('username'), description='An account can be renamed.')
    s.api('settings', 'update', 'password', 'PUT', dave, body={'password': 'David-New-2026'}, needs=D,
          view=pick('username'), description='An administrator sets a new password.')
    s.api('settings', 'sign-in', 'new-password', 'GET', 'me', actor=('david', 'David-New-2026'), needs=D,
          view=pick('username'), description='The renamed account signs in with the new password.')
    s.api('settings', 'sign-in', 'old-password', 'GET', 'me', actor=('david', DAVE), needs=D,
          requires=[renamed], description='The old password no longer works.')

    # What an ordinary account may change.
    own = s.api('settings', 'ordinary', 'own-theme', 'PUT', pathref('users/{id}', id=Ref('bob', 'id')), actor='bob',
                body={'theme': 'dark_serif'}, needs=A, view=pick('theme'),
                description='An ordinary account changes its own settings.')
    s.api('settings', 'ordinary', 'other-account', 'PUT', pathref('users/{id}', id=Ref('carol', 'id')), actor='bob',
          body={'theme': 'dark_serif'}, needs=A, requires=[own],
          description='An ordinary account cannot change another account.')
    s.api('settings', 'ordinary', 'self-administrator', 'PUT', pathref('users/{id}', id=Ref('bob', 'id')), actor='bob',
          body={'is_admin': True}, needs=A, requires=[own],
          description='An ordinary account cannot make itself an administrator.')
    s.api('settings', 'ordinary', 'unchanged-flag', 'GET', 'me', actor='bob', needs=A, requires=[own],
          view=pick('is_admin', 'theme'), description='The ordinary account is still not an administrator.')
    s.api('settings', 'anonymous', 'update', 'PUT', pathref('users/{id}', id=Ref('carol', 'id')), actor=None,
          body={'theme': 'dark_serif'}, needs=A, requires=[own], description='Updates need credentials.')

    # Removing accounts.
    E = ['fx:erin']
    erin = pathref('users/{id}', id=Ref('erin', 'id'))
    present = s.api('users', 'delete', 'before', 'GET', erin, needs=E, view=pick('username'),
                    description='The account to be removed exists.')
    ordinary_delete = s.api('users', 'delete', 'ordinary', 'DELETE', erin, actor='bob', needs=E,
                            description='An ordinary account cannot remove accounts.')
    removed = s.api('users', 'delete', 'administrator', 'DELETE', erin, needs=E, requires=[present],
                    description='An administrator removes an account.')
    s.bind(ordinary_delete, removed)
    s.api('users', 'delete', 'gone', 'GET', erin, needs=E, requires=[removed],
          description='The removed account is not found.')
    s.api('users', 'delete', 'gone-sign-in', 'GET', 'me', actor=('erin', ERIN), needs=E, requires=[removed],
          description='The removed account cannot sign in.')
    s.api('users', 'delete', 'missing', 'DELETE', 'users/987654', requires=[removed],
          description='Removing an unknown account is not found.')
    s.api('users', 'delete', 'self', 'DELETE', pathref('users/{id}', id=Ref('alice', 'id')), needs=A,
          requires=[removed], description='Whether an administrator can remove its own account.')

    # API keys.
    K = ['fx:key']
    key = s.api('keys', 'create', 'plain', 'POST', 'api-keys', body={'description': 'Command line access'},
                description='Creating an API key returns it with its secret token and description.')
    s.api('keys', 'create', 'duplicate', 'POST', 'api-keys', body={'description': 'Command line access'},
          requires=[key], description='A description already used by the same account is refused.')
    s.api('keys', 'create', 'empty', 'POST', 'api-keys', body={'description': ''}, requires=[key],
          description='An API key needs a description.')
    s.api('keys', 'create', 'other-account', 'POST', 'api-keys', actor='bob', body={'description': 'Command line access'},
          requires=[key], view=pick('description'),
          description='Another account may use the same description for its own key.')
    s.api('keys', 'list', 'own', 'GET', 'api-keys', needs=K, view=pick('description', 'token', 'last_used_at'),
          description='An account lists its API keys with their tokens.')
    used = s.api('keys', 'use', 'me', 'GET', 'me', actor='key:key', needs=K, view=pick('username'),
                 description='The X-Auth-Token header authenticates with an API key.')
    s.api('keys', 'use', 'administration', 'GET', 'users', actor='key:key', needs=K,
          view=lambda p: sorted(x['username'] for x in p if x.get('username') in CREDS) if isinstance(p, list) else p,
          description='An administrator\'s API key carries the administrator\'s permissions (the baseline accounts '
                      'are listed).')
    s.api('keys', 'list', 'last-used', 'GET', 'api-keys', needs=K, requires=[used],
          view=pick('description', 'last_used_at'),
          description='Using a key records when it was last used.')
    s.api('keys', 'use', 'unknown-token', 'GET', 'me', actor='raw-key:0123456789abcdef', requires=[used],
          description='An unknown API key is refused.')
    s.api('keys', 'list', 'other-account', 'GET', 'api-keys', actor='carol', needs=K, requires=[used],
          view=pick('description'), description='API keys are private to their account.')
    s.api('keys', 'delete', 'other-account', 'DELETE', pathref('api-keys/{id}', id=Ref('key', 'id')), actor='carol',
          needs=K, requires=[used], description='Another account cannot remove the key.')
    deleted = s.api('keys', 'delete', 'own', 'DELETE', pathref('api-keys/{id}', id=Ref('key', 'id')), needs=K,
                    requires=[used], description='An account removes its API key.')
    s.api('keys', 'use', 'after-delete', 'GET', 'me', actor='key:key', needs=K, requires=[deleted],
          description='A removed API key no longer authenticates.')
    s.api('keys', 'delete', 'missing', 'DELETE', 'api-keys/987654', requires=[deleted],
          description='Removing an unknown API key is not found.')

    # Service endpoints.
    s.api('service', 'version', 'v1', 'GET', 'version',
          view=lambda p: {'version': p.get('version'), 'fields': {k: True for k in p}} if isinstance(p, dict) else p,
          description='The version endpoint names the product version and describes the build (build values such '
                      'as dates and commits are not compared).')
    s.api('service', 'health', 'healthcheck', 'GET', '/healthcheck', actor=None,
          description='The health check answers without credentials.')
    s.api('service', 'health', 'liveness', 'GET', '/liveness', actor=None, description='The liveness probe answers.')
    s.api('service', 'health', 'readiness', 'GET', '/readiness', actor=None,
          description='The readiness probe answers once the database is reachable.')
    s.add('service', 'cors', 'preflight', preflight,
          description='API preflight requests are answered for any origin with the allowed methods and headers.')
