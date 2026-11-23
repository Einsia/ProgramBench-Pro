"""Entry filtering when a feed is read: the feed's block and keep regular expressions, the feed's and the user's
block and allow rules on every entry field (title, URL, comments URL, content, author, tag, date windows, future
and maximum age), several rules together, and how the kinds of rules combine. Each case subscribes to its own
copy of one fixture feed with its rules; the observation is which entries were stored."""
import fixtures as fx
from harness import CREDS, unordered

DC = ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
ITEMS = [
    ('Release notes 2.0', 'http://filters.test/news/release', 'Ann Lee', ['release'], 'Version two is out.',
     'Fri, 10 Jan 2025 08:00:00 GMT', 'http://filters.test/comments/1'),
    ('Sponsored: buy this gadget', 'http://filters.test/ads/gadget', 'Ad Bot', ['ads'], 'Advertisement text.',
     'Sat, 11 Jan 2025 08:00:00 GMT', ''),
    ('Weekly digest', 'http://filters.test/news/digest', 'Ben Ode', ['digest', 'news'],
     'Summary of the week with golang tips.', 'Sat, 01 Jun 2024 08:00:00 GMT', ''),
    ('Go 1.30 announced', 'http://filters.test/news/go', 'Ann Lee', ['go', 'release'], 'The Go team announces.',
     'Sun, 12 Jan 2025 08:00:00 GMT', 'http://forum.test/t/9'),
    ('Podcast episode 12', 'http://media.filters.test/ep12', 'Cid Roy', ['podcast'], 'Listen now.',
     'Mon, 13 Jan 2025 08:00:00 GMT', ''),
    ('Conference next decade', 'http://filters.test/news/conference', 'Eve Moss', ['events'], 'Save the date.',
     'Fri, 01 May 2099 08:00:00 GMT', ''),
]


def document():
    items = []
    for title, link, author, tags, content, date, comments in ITEMS:
        parts = [f'<item><title>{title}</title><link>{link}</link><dc:creator>{author}</dc:creator>',
                 *[f'<category>{t}</category>' for t in tags], f'<description>{content}</description>',
                 f'<pubDate>{date}</pubDate>']
        if comments:
            parts.append(f'<comments>{comments}</comments>')
        items.append(''.join(parts) + '</item>\n')
    return fx.rss('Filter fixture', 'http://filters.test/', items, namespaces=DC)


FEED_RULES = [
    ('blocklist-title', {'blocklist_rules': '(?i)sponsored'}, 'A block regular expression matching a title.'),
    ('blocklist-url', {'blocklist_rules': '/ads/'}, 'A block regular expression matching a URL.'),
    ('blocklist-author', {'blocklist_rules': '^Ann Lee$'}, 'A block regular expression matching an author.'),
    ('blocklist-tag', {'blocklist_rules': '^digest$'}, 'A block regular expression matching a tag.'),
    ('blocklist-content', {'blocklist_rules': 'golang'},
     'A block regular expression that only appears in content.'),
    ('keeplist', {'keeplist_rules': '(?i)release'}, 'A keep regular expression keeps only matching entries.'),
    ('keeplist-tag', {'keeplist_rules': '^podcast$'}, 'A keep regular expression matching a tag.'),
    ('block-and-keep', {'blocklist_rules': '(?i)notes', 'keeplist_rules': '(?i)release'},
     'Block wins over keep for an entry matching both.'),
    ('rule-title', {'block_filter_entry_rules': 'EntryTitle=(?i)digest'}, 'A block rule on titles.'),
    ('rule-url', {'block_filter_entry_rules': 'EntryURL=/news/'}, 'A block rule on URLs.'),
    ('rule-comments', {'block_filter_entry_rules': 'EntryCommentsURL=forum'}, 'A block rule on comments URLs.'),
    ('rule-content', {'block_filter_entry_rules': 'EntryContent=(?i)golang'}, 'A block rule on content.'),
    ('rule-author', {'block_filter_entry_rules': 'EntryAuthor=^Ann'}, 'A block rule on authors.'),
    ('rule-tag', {'block_filter_entry_rules': 'EntryTag=^podcast$'}, 'A block rule on tags.'),
    ('rule-future', {'block_filter_entry_rules': 'EntryDate=future'}, 'A block rule on future dates.'),
    ('rule-before', {'block_filter_entry_rules': 'EntryDate=before:2025-01-01'}, 'A block rule on dates before a day.'),
    ('rule-after', {'block_filter_entry_rules': 'EntryDate=after:2025-01-12'}, 'A block rule on dates after a day.'),
    ('rule-between', {'block_filter_entry_rules': 'EntryDate=between:2025-01-09,2025-01-12'},
     'A block rule on dates between two days.'),
    ('rule-max-age', {'block_filter_entry_rules': 'EntryDate=max-age:100d'},
     'A block rule on entries older than a maximum age.'),
    ('rule-several', {'block_filter_entry_rules': 'EntryTitle=Weekly\nEntryAuthor=Cid'},
     'Several block rules, one per line.'),
    ('keep-tag', {'keep_filter_entry_rules': 'EntryTag=release'}, 'An allow rule keeps only matching entries.'),
    ('keep-author', {'keep_filter_entry_rules': 'EntryAuthor=(?i)ann'}, 'An allow rule on authors.'),
    ('keep-url', {'keep_filter_entry_rules': 'EntryURL=^http://media'}, 'An allow rule on URLs.'),
    ('block-and-allow', {'block_filter_entry_rules': 'EntryTitle=Go', 'keep_filter_entry_rules': 'EntryTag=release'},
     'A block rule wins over an allow rule.'),
    ('allow-and-keeplist', {'keep_filter_entry_rules': 'EntryTag=podcast', 'keeplist_rules': '(?i)release'},
     'Allow rules take the place of the keep regular expression.'),
]
USER_RULES = [
    ('user-block', {'block_filter_entry_rules': 'EntryAuthor=^Ben'}, {},
     'The user\'s block rules apply to every feed.'),
    ('user-keep', {'keep_filter_entry_rules': 'EntryTag=go'}, {}, 'The user\'s allow rules apply to every feed.'),
    ('user-and-feed', {'block_filter_entry_rules': 'EntryTag=ads'}, {'block_filter_entry_rules': 'EntryTag=podcast'},
     'User and feed block rules both apply.'),
]
CLEAR = {'block_filter_entry_rules': '', 'keep_filter_entry_rules': ''}


def stored_titles(c, url, options, user_rules=None):
    """Optionally set the user's rules, subscribe, observe the stored titles, then clear the user's rules."""
    out = {}
    if user_rules is not None:
        r, p = c.request('PUT', f"users/{c.state['alice']['id']}", body=user_rules)
        out['rules'] = r.status_code
    try:
        r, p = c.request('POST', 'feeds', body={'feed_url': url, 'category_id': c.state['category-alice']['id'],
                                                 **options})
        if r.status_code >= 400:
            out.update(c.observe(r, p))
            return out
        rr, listing = c.request('GET', f"feeds/{p['feed_id']}/entries", params={'limit': 100})
        assert rr.status_code == 200, 'feed entries unavailable'
        out.update(status=r.status_code, titles=unordered(sorted(e['title'] for e in listing['entries'])))
        return out
    finally:
        if user_rules is not None:
            c.request('PUT', f"users/{c.state['alice']['id']}", body=CLEAR)


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish('http://filters.test/feed.xml', document(), fx.RSS_TYPE))
    W = ['fx:accounts', 'fx:web']
    baseline = s.add('filters', 'none', 'subscribe',
                     lambda c: stored_titles(c, 'http://filters.test/feed.xml?case=none', {}), needs=W,
                     description='Without rules every entry of the fixture feed is stored.')
    for name, options, description in FEED_RULES:
        s.add('filters', name, 'subscribe',
              lambda c, n=name, o=options: stored_titles(c, f'http://filters.test/feed.xml?case={n}', o), needs=W,
              requires=[baseline], description=description)
    # An expression that matches only content blocks nothing: it counts with one that blocks by title.
    s.bind(f'{s.prefix}api.filters.blocklist-content.subscribe', f'{s.prefix}api.filters.blocklist-title.subscribe')
    for name, user_rules, options, description in USER_RULES:
        s.add('filters', name, 'subscribe',
              lambda c, n=name, o=options, u=user_rules: stored_titles(c, f'http://filters.test/feed.xml?case={n}', o, u),
              needs=W, requires=[baseline], description=description)
