"""Full-text search of entries through the REST API: words in titles and content, stemming, stop words, several
words, alternatives, phrases, exclusions, case, accents, numbers, markup, ranking, and search combined with other
filters and with another account."""
import datetime

import fixtures as fx
from fixtures import rss
from harness import CREDS, Ref, members

TITLES = members('entries', 'title')
DOCS = [
    ('Solar panels on every roof', 'Engineers expect the cost of photovoltaic modules to keep falling.'),
    ('Battery storage grows', 'Grid operators add solar battery farms to store energy for the evening.'),
    ('Wind turbines offshore', 'The new wind farm runs at full capacity during winter storms.'),
    ('Electric car sales', 'Sales of the electric car doubled while petrol car sales fell.'),
    ('Running a marathon', 'She runs every morning and has run three marathons.'),
    ('Café culture in Lisbon', 'The café scene of the old town, with pastéis de nata.'),
    ('Budget for 2025', 'The 2025 budget allocates funds to public transport.'),
    ('E-mail etiquette', 'How to write a polite e-mail to a colleague.'),
    ('Markup in content', '<p>The word <strong>emphasised</strong> sits inside a strong element.</p>'),
    ('The weekly roundup', 'A summary of the week with no particular topic.'),
    ('Solar eclipse viewing', 'Watch the eclipse safely; it is not about energy at all.'),
    ('中文 汉字 测试', '这是一个中文搜索测试。'),
]


def document():
    base = datetime.datetime(2025, 3, 1, 8, 0, tzinfo=datetime.timezone.utc)
    items = []
    for i, (title, content) in enumerate(DOCS):
        stamp = (base + datetime.timedelta(days=i)).strftime('%a, %d %b %Y %H:%M:%S GMT')
        items.append(fx.item(title, f'http://search.test/doc/{i}', f'doc-{i}', stamp, fx.html_text(content)))
    return rss('Search fixture', 'http://search.test/', items)


def remember(c):
    r, payload = c.request('GET', 'entries', params={'limit': 100})
    c.state['by-title'] = {e['title']: e for e in payload['entries']}


QUERIES = [
    ('title-word', 'turbines', 'A word that appears in one title.'),
    ('content-word', 'photovoltaic', 'A word that appears only in content.'),
    ('title-and-content', 'solar', 'A word in titles and contents, ranked.'),
    ('stemming', 'run', 'Stemming finds other forms of a word.'),
    ('stemming-plural', 'marathon', 'A singular finds the plural.'),
    ('case', 'ELECTRIC', 'Search ignores case.'),
    ('stop-word', 'the', 'A stop word alone.'),
    ('two-words', 'solar battery', 'Several words must all appear.'),
    ('alternative', 'turbines or marathon', 'Alternatives with or.'),
    ('phrase', '"electric car"', 'A quoted phrase.'),
    ('phrase-order', '"car electric"', 'A quoted phrase in the wrong order.'),
    ('exclusion', 'solar -battery', 'A word excluded with a minus sign.'),
    ('accent', 'café', 'A word with an accent.'),
    ('accent-missing', 'cafe', 'The same word without its accent.'),
    ('number', '2025', 'A number.'),
    ('hyphenated', 'e-mail', 'A hyphenated word.'),
    ('markup', 'strong', 'Words of markup in content.'),
    ('markup-text', 'emphasised', 'Text inside markup in content.'),
    ('cjk', '汉字', 'Chinese characters.'),
    ('no-match', 'zeppelin', 'A word that appears nowhere.'),
]


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    fx.default_category(s, 'accounts', 'bob')
    s.fixture('web', 'publish', fx.publish('http://search.test/feed.xml', document(), fx.RSS_TYPE))
    fx.subscribe(s, 'library', 'alice', 'http://search.test/feed.xml', 'feed')
    s.fixture('library', 'entries', remember)
    s.setup('library', 'read-one', 'PUT', 'entries', body={
        'entry_ids': [Ref('by-title', 'Solar eclipse viewing', 'id')], 'status': 'read'})
    L = ['fx:accounts', 'fx:web', 'fx:library']
    first = None
    for name, query, description in QUERIES:
        step = s.api('search', name, 'query', 'GET', 'entries', params={'search': query}, needs=L, view=TITLES,
                     requires=[first] if first and name in ('stop-word', 'no-match', 'phrase-order') else (),
                     description=description)
        first = first or step
        if name == 'accent':
            accented = step
        if name == 'accent-missing':
            s.bind(step, accented)
    s.api('search', 'unread', 'query', 'GET', 'entries', params={'search': 'solar', 'status': 'unread'}, needs=L,
          view=TITLES, description='Search combined with the unread status.')
    s.api('search', 'paged', 'query', 'GET', 'entries', params={'search': 'solar', 'limit': 1, 'offset': 1}, needs=L,
          view=TITLES, description='A page of search results.')
    s.api('search', 'feed', 'query', 'GET', 'entries', params={'search': 'car', 'feed_id': Ref('feed', 'feed_id')},
          needs=L, view=TITLES, description='Search within one feed.')
    s.api('search', 'other-account', 'query', 'GET', 'entries', actor='bob', params={'search': 'solar'}, needs=L,
          view=TITLES, requires=[first], description='Another account finds none of these entries.')
    s.api('search', 'ordered', 'query', 'GET', 'entries', params={'search': 'solar', 'order': 'title',
                                                                   'direction': 'asc'}, needs=L, view=TITLES,
          description='Search results with an explicit order.')
