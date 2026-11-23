"""Feeds through the REST API: subscription with every option, the errors of unreachable or unparsable
resources, reading, updating every setting with its validation, icons, counters, marking as read and removal."""
import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, Ref, members, ordered_groups, pathref, pick

ITEMS = [item('Morning edition', 'http://feeds.test/news/morning', 'news-1', 'Mon, 10 Feb 2025 07:00:00 GMT',
              'The morning summary.'),
         item('Evening edition', 'http://feeds.test/news/evening', 'news-2', 'Mon, 10 Feb 2025 19:00:00 GMT',
              'The evening summary.')]
PLAIN = rss('Fixture News', 'http://feeds.test/news/', ITEMS, description='News of the fixture site')
HOME = page('Fixture site', '<p>Home</p>', head='<link rel="icon" type="image/png" href="/icons/site.png">\n')
ICON = fx.png(16, 16, (200, 40, 40))
# Subscription options and the feed field each sets; every option gets its own copy of the feed.
OPTIONS = [
    ('crawler', {'crawler': True}), ('user-agent', {'user_agent': 'FeedFetcher/1.0 (fixture)'}),
    ('cookie', {'cookie': 'session=abc123; theme=dark'}),
    ('credentials', {'username': 'reader', 'password': 'Reader-Secret-2026'}),
    ('scraper-rules', {'scraper_rules': 'article .body'}), ('rewrite-rules', {'rewrite_rules': 'add_image_title'}),
    ('urlrewrite-rules', {'urlrewrite_rules': 'rewrite("^http://feeds.test/(.*)$"|"http://mirror.test/$1")'}),
    ('blocklist-rules', {'blocklist_rules': '(?i)evening'}), ('keeplist-rules', {'keeplist_rules': '(?i)morning'}),
    ('block-filter-rules', {'block_filter_entry_rules': 'EntryTitle=(?i)morning'}),
    ('keep-filter-rules', {'keep_filter_entry_rules': 'EntryTitle=(?i)evening'}),
    ('disabled', {'disabled': True}), ('ignore-http-cache', {'ignore_http_cache': True}),
    ('fetch-via-proxy', {'fetch_via_proxy': True}), ('hide-globally', {'hide_globally': True}),
    ('no-media-player', {'no_media_player': True}), ('self-signed', {'allow_self_signed_certificates': True}),
    ('disable-http2', {'disable_http2': True}), ('ignore-entry-updates', {'ignore_entry_updates': True}),
]
# One valid value per feed setting of PUT /v1/feeds/{id}.
UPDATES = [
    ('title', 'Renamed feed'), ('site_url', 'http://feeds.test/elsewhere/'),
    ('feed_url', 'http://feeds.test/relocated.xml'), ('crawler', True), ('user_agent', 'Custom Agent/2.0'),
    ('cookie', 'token=xyz'), ('username', 'editor'), ('password', 'Editor-Pass-2026'),
    ('scraper_rules', 'main p'), ('rewrite_rules', 'nl2br'),
    ('urlrewrite_rules', 'rewrite("news/(.*)"|"stories/$1")'), ('blocklist_rules', 'spam'),
    ('keeplist_rules', 'ham'), ('block_filter_entry_rules', 'EntryAuthor=(?i)bot'),
    ('keep_filter_entry_rules', 'EntryTag=(?i)go'), ('disabled', True), ('ignore_http_cache', True),
    ('allow_self_signed_certificates', True), ('fetch_via_proxy', True), ('hide_globally', True),
    ('no_media_player', True), ('disable_http2', True), ('ignore_entry_updates', True),
    ('description', 'Edited description'), ('proxy_url', 'http://proxy.test:3128'),
]
INVALID_UPDATES = [
    ('title', ''), ('feed_url', ''), ('feed_url', 'not a url'), ('site_url', ''), ('site_url', 'not a url'),
    ('blocklist_rules', '(unclosed'), ('keeplist_rules', '[z-a]'), ('rewrite_rules', 'no_such_rule'),
    ('urlrewrite_rules', 'rewrite(missing quotes)'), ('block_filter_entry_rules', 'EntryNothing=x'),
    ('keep_filter_entry_rules', 'EntryTitle=('), ('proxy_url', 'not a proxy url'),
]
ERRORS = [
    # (step, url, published resource or None, description)
    ('not-found', 'http://feeds.test/missing.xml', None, 'A feed URL answered 404.'),
    ('forbidden', 'http://feeds.test/forbidden.xml', ('Forbidden', 'text/plain', 403), 'A feed URL answered 403.'),
    ('server-error', 'http://feeds.test/broken.xml', ('Server error', 'text/plain', 500), 'A feed URL answered 500.'),
    ('unavailable', 'http://feeds.test/busy.xml', ('Busy', 'text/plain', 503), 'A feed URL answered 503.'),
    ('teapot', 'http://feeds.test/teapot.xml', ('Teapot', 'text/plain', 418), 'A feed URL answered 418.'),
    ('rate-limited', 'http://feeds.test/limited.xml', ('Slow down', 'text/plain', 429), 'A feed URL answered 429.'),
    ('unauthorized', 'http://feeds.test/private-2.xml', None,
     'A feed that needs credentials, subscribed without them.'),
    ('not-a-feed', 'http://feeds.test/plain-page.html', (page('Just a page', '<p>No feed here.</p>'), fx.HTML_TYPE),
     'A web page without any feed is not a feed.'),
    ('malformed', 'http://feeds.test/malformed.xml',
     ('<?xml version="1.0"?><rss version="2.0"><channel><title>Broken</title><item><title>x</item></channel>',
      'application/xml'), 'A feed whose XML is broken.'),
    ('empty-body', 'http://feeds.test/empty.xml', ('', 'application/xml'), 'A feed URL answering an empty body.'),
    ('json-not-feed', 'http://feeds.test/data.json', ('{"items": "not a feed"}', 'application/json'),
     'A JSON document that is not a JSON Feed.'),
]


def subscribe_with(url, options):
    def action(c):
        r, p = c.request('POST', 'feeds', body={'feed_url': url, 'category_id': c.state['category-alice']['id'],
                                                **options})
        if r.status_code >= 400:
            return c.observe(r, p)
        assert isinstance(p, dict) and 'feed_id' in p, 'the subscription answer lacks feed_id'
        rr, feed = c.request('GET', f"feeds/{p['feed_id']}")
        return {'status': r.status_code, 'feed': c.observe(rr, feed, view=pick(*options))}
    return action


def counters_of(*keys):
    """Read and unread counters of the named fixture feeds only (other feeds are other cases' business)."""
    def action(c):
        r, payload = c.request('GET', 'feeds/counters')
        if r.status_code >= 400:
            return c.observe(r, payload)
        assert isinstance(payload, dict) and {'reads', 'unreads'} <= payload.keys(), 'expected reads and unreads'
        out = {}
        for key in keys:
            feed = str(c.state[key]['feed_id'])
            out[key] = {'reads': payload['reads'].get(feed, 0), 'unreads': payload['unreads'].get(feed, 0)}
        return {'status': r.status_code, 'counters': out}
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    fx.default_category(s, 'accounts', 'bob')
    s.setup('accounts', 'second-category', 'POST', 'categories', body={'title': 'Second shelf'}, save='cat-second')
    resources = [('http://feeds.test/plain.xml', PLAIN, fx.RSS_TYPE), ('http://feeds.test/news/', HOME, fx.HTML_TYPE),
                 ('http://feeds.test/icons/site.png', ICON, 'image/png'),
                 ('http://feeds.test/private.xml', PLAIN, fx.RSS_TYPE, 200, None, ['reader', 'Reader-Secret-2026']),
                 ('http://feeds.test/private-2.xml', PLAIN, fx.RSS_TYPE, 200, None, ['reader', 'Reader-Secret-2026']),
                 ('http://feeds.test/fresh.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/fresh-2.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/fresh-3.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/fresh-4.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/relocated.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/moved.xml', '', 'text/plain', 301, {'location': 'http://feeds.test/target.xml'}),
                 ('http://feeds.test/target.xml', PLAIN, fx.RSS_TYPE),
                 ('http://feeds.test/no-icon.xml', rss('Iconless', 'http://iconless.test/', ITEMS), fx.RSS_TYPE)]
    resources += [(f'http://feeds.test/opt-{name}.xml', PLAIN, fx.RSS_TYPE) for name, _ in OPTIONS]
    resources += [('http://feeds.test/opt-moved.xml', PLAIN, fx.RSS_TYPE), ('http://feeds.test/target-2.xml', PLAIN,
                                                                            fx.RSS_TYPE)]
    resources += [(url, *spec) for _, url, spec, _ in ERRORS if spec]
    s.fixture('web', 'publish', fx.publish_all(resources))
    fx.subscribe(s, 'subject', 'plain', 'http://feeds.test/target-2.xml', 'subject')
    fx.subscribe(s, 'subject', 'other-account', 'http://feeds.test/plain.xml', 'bob-feed', actor='bob')
    s.fixture('subject', 'entries', lambda c: c.state.__setitem__('subject-entries', fx.entries_of(c, 'subject')))
    A, W, F = ['fx:accounts'], ['fx:accounts', 'fx:web'], ['fx:accounts', 'fx:web', 'fx:subject']
    feed = pathref('feeds/{id}', id=Ref('subject', 'feed_id'))

    # Subscribing.
    created = s.api('feeds', 'create', 'plain', 'POST', 'feeds', needs=W, save='plain',
                    body={'feed_url': 'http://feeds.test/plain.xml', 'category_id': Ref('category-alice', 'id')},
                    description='Subscribing to a feed returns the new feed id.')
    shape = s.api('feeds', 'read', 'object', 'GET', pathref('feeds/{id}', id=Ref('plain', 'feed_id')), needs=W,
                  requires=[created], description='A subscribed feed with its title, addresses, category, icon and '
                                                  'every setting.')
    s.api('feeds', 'read', 'entries', 'GET', pathref('feeds/{id}/entries', id=Ref('plain', 'feed_id')), needs=W,
          requires=[created], params={'order': 'published_at', 'direction': 'asc'},
          view=members('entries', 'title', 'url', 'status', 'published_at'),
          description='Subscribing stores the feed\'s entries as unread.')
    second_created = s.api('feeds', 'create', 'second-category', 'POST', 'feeds', needs=W, save='second',
          body={'feed_url': 'http://feeds.test/opt-moved.xml', 'category_id': Ref('cat-second', 'id')},
          description='Subscribing into a chosen category.')
    s.api('feeds', 'read', 'second-category', 'GET', pathref('feeds/{id}', id=Ref('second', 'feed_id')), needs=W,
          view=pick('category.title'), description='The feed belongs to the chosen category.')
    listed = s.api('feeds', 'list', 'all', 'GET', 'feeds', needs=F + [created, second_created],
                   view=ordered_groups(lambda x: (x['parsing_error_count'], x['title'].lower()),
                                       pick('title', 'feed_url', 'category.title')),
                   description='The account\'s feeds, in the product\'s order (feeds with errors first, then by '
                               'title; feeds with equal keys in any order).')
    s.api('feeds', 'list', 'other-account', 'GET', 'feeds', actor='bob', needs=F, requires=[listed],
          view=pick('title', 'feed_url'), description='Another account lists only its own feeds.')
    for name, options in OPTIONS:
        s.add('feeds', 'create', 'option-' + name, subscribe_with(f'http://feeds.test/opt-{name}.xml', options),
              needs=W, description=f'Subscribing with the option {", ".join(options)} keeps it on the new feed.')
    s.api('feeds', 'create', 'credentials-needed', 'POST', 'feeds', needs=W,
          body={'feed_url': 'http://feeds.test/private.xml', 'category_id': Ref('category-alice', 'id'),
                'username': 'reader', 'password': 'Reader-Secret-2026'}, view=pick('feed_id'),
          description='A feed behind HTTP Basic authentication is subscribed with its credentials.')
    s.api('feeds', 'create', 'redirect', 'POST', 'feeds', needs=W, save='redirected',
          body={'feed_url': 'http://feeds.test/moved.xml', 'category_id': Ref('category-alice', 'id')},
          view=pick('feed_id'), description='Subscribing to a URL that redirects permanently.')
    s.api('feeds', 'read', 'redirect', 'GET', pathref('feeds/{id}', id=Ref('redirected', 'feed_id')), needs=W,
          view=pick('feed_url', 'site_url', 'title'), description='Which address a redirected subscription keeps.')
    for step, url, _, description in ERRORS:
        s.api('feeds', 'create-error', step, 'POST', 'feeds', needs=W, requires=[created],
              body={'feed_url': url, 'category_id': Ref('category-alice', 'id')}, description=description)
    s.api('feeds', 'create-error', 'duplicate', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'http://feeds.test/plain.xml', 'category_id': Ref('category-alice', 'id')},
          description='Subscribing twice to the same feed is refused.')
    s.api('feeds', 'create-error', 'no-url', 'POST', 'feeds', needs=W, requires=[created],
          body={'category_id': Ref('category-alice', 'id')}, description='The feed URL is mandatory.')
    s.api('feeds', 'create-error', 'no-category', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'http://feeds.test/fresh.xml'},
          description='Subscribing without a category (the account\'s default category or a refusal).')
    s.api('feeds', 'create-error', 'unknown-category', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'http://feeds.test/fresh-2.xml', 'category_id': 987654},
          description='An unknown category is refused.')
    s.api('feeds', 'create-error', 'foreign-category', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'http://feeds.test/fresh-3.xml', 'category_id': Ref('category-bob', 'id')},
          description='Another account\'s category is refused.')
    s.api('feeds', 'create-error', 'invalid-url', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'not a url', 'category_id': Ref('category-alice', 'id')},
          description='A feed URL that is not a URL is refused.')
    s.api('feeds', 'create-error', 'ftp-url', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'ftp://feeds.test/feed.xml', 'category_id': Ref('category-alice', 'id')},
          description='A feed URL with another scheme than HTTP is refused.')
    s.api('feeds', 'create-error', 'proxy', 'POST', 'feeds', needs=W, requires=[created],
          body={'feed_url': 'http://feeds.test/fresh-4.xml', 'category_id': Ref('category-alice', 'id'),
                'proxy_url': 'http://proxy.test:3128'},
          description='A feed fetched through an unreachable per-feed proxy.')
    for option, value in (('blocklist_rules', '[unclosed'), ('keeplist_rules', '(?P<'),
                          ('urlrewrite_rules', 'rewrite(missing quotes)'), ('block_filter_entry_rules', 'EntryNothing=x'),
                          ('keep_filter_entry_rules', 'EntryTitle=(unclosed'), ('rewrite_rules', 'no_such_rule')):
        s.api('feeds', 'create-invalid', option, 'POST', 'feeds', needs=W, requires=[created],
              body={'feed_url': f'http://feeds.test/unpublished-{option}.xml', 'category_id': Ref('category-alice', 'id'),
                    option: value},
              description=f'Subscribing with the invalid {option} {value!r} is refused with a validation message.')
    s.api('feeds', 'create-error', 'anonymous', 'POST', 'feeds', actor=None, requires=[created],
          body={'feed_url': 'http://feeds.test/plain.xml', 'category_id': 1}, description='Subscribing needs credentials.')

    # Reading.
    s.api('feeds', 'read', 'missing', 'GET', 'feeds/987654', requires=[shape],
          description='An unknown feed is not found.')
    s.api('feeds', 'read', 'other-account', 'GET', feed, actor='bob', needs=F, requires=[shape],
          description='Another account cannot read the feed.')
    s.api('feeds', 'entries', 'one', 'GET',
          pathref('feeds/{f}/entries/{e}', f=Ref('subject', 'feed_id'), e=Ref('subject-entries', 0, 'id')), needs=F,
          view=pick('title', 'url', 'feed.title'), description='One entry read through its feed.')
    s.api('feeds', 'entries', 'wrong-feed', 'GET',
          pathref('feeds/{f}/entries/{e}', f=Ref('bob-feed', 'feed_id'), e=Ref('subject-entries', 0, 'id')),
          actor='bob', needs=F, requires=[shape], description='An entry is not found through a feed of another account.')

    # Icons.
    icon = s.api('icons', 'feed', 'from-site', 'GET', pathref('feeds/{id}/icon', id=Ref('subject', 'feed_id')),
                 needs=F, save='subject-icon', view=pick('id', 'mime_type', 'data'),
                 description='The icon found on the feed\'s web site, as a data URL.')
    s.api('icons', 'by-id', 'read', 'GET', pathref('icons/{id}', id=Ref('subject-icon', 'id')), needs=F,
          requires=[icon], view=pick('id', 'mime_type', 'data'), description='The same icon read by its id.')
    s.api('icons', 'feed', 'none', 'POST', 'feeds', needs=W, save='iconless',
          body={'feed_url': 'http://feeds.test/no-icon.xml', 'category_id': Ref('category-alice', 'id')},
          view=pick('feed_id'), description='Subscribing to a feed whose site has no icon.')
    s.api('icons', 'feed', 'missing', 'GET', pathref('feeds/{id}/icon', id=Ref('iconless', 'feed_id')), needs=W,
          requires=[icon], description='A feed without an icon has none.')
    s.api('icons', 'by-id', 'missing', 'GET', 'icons/987654', requires=[icon],
          description='An unknown icon is not found.')
    s.api('icons', 'feed', 'other-account', 'GET', pathref('feeds/{id}/icon', id=Ref('subject', 'feed_id')),
          actor='bob', needs=F, requires=[icon], description='Another account cannot read the feed icon.')

    # Updating settings.
    valid = {}
    for name, value in UPDATES:
        valid.setdefault(name, s.api('feeds', 'update', name, 'PUT', feed, body={name: value}, needs=F,
                                     view=pick(name), description=f'Updating the feed setting {name}.'))
    s.api('feeds', 'update', 'category', 'PUT', feed, body={'category_id': Ref('cat-second', 'id')}, needs=F,
          view=pick('category.title'), description='Moving a feed to another category.')
    for name, value in INVALID_UPDATES:
        s.api('feeds', 'update-invalid', name + '-' + (str(value).replace(' ', '-') or 'empty'), 'PUT', feed,
              body={name: value}, needs=F, requires=[valid.get(name, valid['title'])],
              description=f'The invalid value {value!r} of {name} is refused with a validation message.')
    s.api('feeds', 'update-invalid', 'category-missing', 'PUT', feed, body={'category_id': 987654}, needs=F,
          requires=[valid['title']], description='Moving a feed to an unknown category is refused.')
    s.api('feeds', 'update-invalid', 'category-foreign', 'PUT', feed, body={'category_id': Ref('category-bob', 'id')},
          needs=F, requires=[valid['title']], description='Moving a feed to another account\'s category is refused.')
    s.api('feeds', 'update', 'missing', 'PUT', 'feeds/987654', body={'title': 'Ghost'}, requires=[valid['title']],
          description='Updating an unknown feed is not found.')
    s.api('feeds', 'update', 'other-account', 'PUT', feed, actor='bob', body={'title': 'Stolen'}, needs=F,
          requires=[valid['title']], description='Another account cannot update the feed.')
    after_updates = s.api('feeds', 'read', 'after-updates', 'GET', feed, needs=F, view=pick(
        'title', 'site_url', 'feed_url', 'crawler', 'user_agent', 'cookie', 'username', 'password', 'scraper_rules',
        'rewrite_rules', 'urlrewrite_rules', 'blocklist_rules', 'keeplist_rules', 'block_filter_entry_rules',
        'keep_filter_entry_rules', 'disabled', 'ignore_http_cache', 'allow_self_signed_certificates',
        'fetch_via_proxy', 'hide_globally', 'no_media_player', 'disable_http2', 'ignore_entry_updates',
        'description', 'proxy_url', 'category.title'), description='Reading the feed shows every updated setting '
                                                                 'together.')
    s.api('feeds', 'update', 'clear-rules', 'PUT', feed, needs=F,
          body={'scraper_rules': '', 'rewrite_rules': '', 'blocklist_rules': '', 'keeplist_rules': ''},
          view=pick('scraper_rules', 'rewrite_rules', 'blocklist_rules', 'keeplist_rules'),
          description='Rules can be cleared again.')

    # Counters, marking as read, removal.
    s.add('feeds', 'counters', 'initial', counters_of('plain', 'subject', 'second'), needs=F,
          description='Read and unread entry counters per feed.')
    marked = s.api('feeds', 'read-state', 'mark', 'PUT', pathref('feeds/{id}/mark-all-as-read', id=Ref('plain', 'feed_id')),
                   needs=W, description='Marking every entry of one feed as read.')
    entries_after = s.api('feeds', 'read-state', 'entries-after', 'GET',
                          pathref('feeds/{id}/entries', id=Ref('plain', 'feed_id')), needs=W + [marked],
                          params={'order': 'published_at', 'direction': 'asc'},
          view=members('entries', 'title', 'status'), description='The feed\'s entries are read afterwards.')
    s.add('feeds', 'counters', 'after-mark', counters_of('plain', 'subject', 'second'), needs=F + [marked],
          description='The counters after marking one feed as read.')
    s.api('feeds', 'read-state', 'other-account', 'PUT',
          pathref('feeds/{id}/mark-all-as-read', id=Ref('subject', 'feed_id')), actor='bob', needs=F,
          requires=[marked], description='Another account cannot mark the feed as read.')
    foreign_delete = s.api('feeds', 'delete', 'other-account', 'DELETE', feed, actor='bob', needs=F,
                           description='Another account cannot remove the feed.')
    removed = s.api('feeds', 'delete', 'own', 'DELETE', feed, needs=F, requires=[after_updates],
                    description='Removing a feed.')
    s.bind(foreign_delete, removed)
    # The bare confirmation of marking counts together with the read that shows its effect.
    s.bind(marked, entries_after)
    s.api('feeds', 'delete', 'gone', 'GET', feed, needs=F, requires=[removed], description='The removed feed is not found.')
    s.api('feeds', 'delete', 'entries-gone', 'GET', 'entries', needs=F, requires=[removed],
          params={'feed_id': Ref('subject', 'feed_id')}, view=members('entries', 'title'),
          description='The removed feed\'s entries are gone.')
    s.api('feeds', 'delete', 'missing', 'DELETE', 'feeds/987654', requires=[removed],
          description='Removing an unknown feed is not found.')
