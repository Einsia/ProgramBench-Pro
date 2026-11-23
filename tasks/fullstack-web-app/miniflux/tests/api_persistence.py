"""Persistence across a restart of the application with the same DATA_DIR: accounts and their settings,
categories, feeds with their settings, entries with read, starred and edited state, enclosure progress, API
keys, and the refusal that still applies to a removed account."""
import fixtures as fx
from fixtures import item, rss
from harness import CREDS, Ref, members, pathref, pick

FEED = rss('Durable feed', 'http://durable.test/', [
    item('Durable one', 'http://durable.test/1', 'd1', 'Mon, 06 Jan 2025 08:00:00 GMT', 'One.',
         '<enclosure url="http://media.durable.test/one.mp3" length="50" type="audio/mpeg"/>'),
    item('Durable two', 'http://durable.test/2', 'd2', 'Tue, 07 Jan 2025 08:00:00 GMT', 'Two.'),
    item('Durable three', 'http://durable.test/3', 'd3', 'Wed, 08 Jan 2025 08:00:00 GMT', 'Three.')])


def remember(c):
    c.state['e'] = {e['title']: e for e in fx.entries_of(c, 'feed')}


def restart(c):
    # Runtime op restart: a fresh process of the application on the same DATA_DIR.
    assert c.running(), 'the application is not running before the restart'
    c.restart_server()
    assert c.running(), 'the application is not running after the restart'
    return {'fresh_process': True, 'same_data_directory': True}


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish('http://durable.test/feed.xml', FEED, fx.RSS_TYPE))
    s.setup('state', 'user', 'POST', 'users', body={'username': 'durable', 'password': 'Durable-Pass-2026'},
            save='durable')
    s.setup('state', 'user-settings', 'PUT', pathref('users/{id}', id=Ref('durable', 'id')),
            body={'theme': 'dark_serif', 'language': 'de_DE', 'timezone': 'Asia/Tokyo', 'entries_per_page': 7,
                  'entry_sorting_direction': 'desc', 'stylesheet': 'p { margin: 0 }'})
    s.setup('state', 'gone-user', 'POST', 'users', body={'username': 'ephemeral', 'password': 'Ephemeral-2026'},
            save='ephemeral')
    s.setup('state', 'remove-user', 'DELETE', pathref('users/{id}', id=Ref('ephemeral', 'id')))
    s.setup('state', 'category', 'POST', 'categories', body={'title': 'Durable shelf', 'hide_globally': True},
            save='shelf')
    fx.subscribe(s, 'state', 'feed', 'http://durable.test/feed.xml', 'feed', category='shelf',
                 user_agent='Durable Agent', crawler=False, blocklist_rules='nothing-matches-this')
    s.setup('state', 'feed-title', 'PUT', pathref('feeds/{id}', id=Ref('feed', 'feed_id')),
            body={'title': 'Durable (renamed)'})
    s.fixture('state', 'entries', remember)
    s.setup('state', 'read', 'PUT', 'entries', body={'entry_ids': [Ref('e', 'Durable one', 'id')], 'status': 'read'})
    s.setup('state', 'star', 'PUT', pathref('entries/{id}/bookmark', id=Ref('e', 'Durable two', 'id')))
    s.setup('state', 'edit', 'PUT', pathref('entries/{id}', id=Ref('e', 'Durable three', 'id')),
            body={'title': 'Durable three (edited)'})
    s.setup('state', 'progress', 'PUT', pathref('enclosures/{id}', id=Ref('e', 'Durable one', 'enclosures', 0, 'id')),
            body={'media_progression': 33})
    s.setup('state', 'key', 'POST', 'api-keys', body={'description': 'Durable key'}, save='key')
    S = ['fx:accounts', 'fx:web', 'fx:state']

    restarted = s.add('persistence', 'restart', 'process', restart, needs=S,
                      description='Restart the application without replacing DATA_DIR.')
    after = [restarted]
    s.api('persistence', 'after', 'users', 'GET', 'users', needs=S + after, view=pick('username', 'is_admin'),
          description='The accounts after the restart (a removed account stays removed).')
    s.api('persistence', 'after', 'user-settings', 'GET', pathref('users/{id}', id=Ref('durable', 'id')),
          needs=S + after, view=pick('username', 'theme', 'language', 'timezone', 'entries_per_page',
                                    'entry_sorting_direction', 'stylesheet'),
          description='An account\'s settings after the restart.')
    s.api('persistence', 'after', 'sign-in', 'GET', 'me', actor=('durable', 'Durable-Pass-2026'), needs=S + after,
          view=pick('username'), description='The account still signs in with its password.')
    s.api('persistence', 'after', 'removed-sign-in', 'GET', 'me', actor=('ephemeral', 'Ephemeral-2026'),
          needs=S + after, requires=[restarted], description='A removed account still cannot sign in.')
    s.api('persistence', 'after', 'categories', 'GET', 'categories', needs=S + after,
          view=pick('title', 'hide_globally'), description='Categories after the restart.')
    s.api('persistence', 'after', 'feed', 'GET', pathref('feeds/{id}', id=Ref('feed', 'feed_id')), needs=S + after,
          view=pick('title', 'feed_url', 'site_url', 'user_agent', 'blocklist_rules', 'category.title'),
          description='A feed and its settings after the restart.')
    s.api('persistence', 'after', 'entries', 'GET', pathref('feeds/{id}/entries', id=Ref('feed', 'feed_id')),
          needs=S + after, params={'order': 'published_at', 'direction': 'asc'},
          view=members('entries', 'title', 'status', 'starred'),
          description='Entries with their read, starred and edited state after the restart.')
    s.api('persistence', 'after', 'enclosure', 'GET',
          pathref('enclosures/{id}', id=Ref('e', 'Durable one', 'enclosures', 0, 'id')), needs=S + after,
          view=pick('media_progression', 'url'), description='Enclosure progress after the restart.')
    s.api('persistence', 'after', 'api-key', 'GET', 'me', actor='key:key', needs=S + after, view=pick('username'),
          description='An API key still authenticates after the restart.')
    s.api('persistence', 'after', 'counters', 'GET', 'categories', params={'counts': True}, needs=S + after,
          view=pick('title', 'feed_count', 'total_unread'), description='Counters after the restart.')
