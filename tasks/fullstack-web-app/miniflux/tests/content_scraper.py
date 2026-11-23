"""Original content and reading time: the crawler that replaces entry content with the article from the entry's
web page (readability extraction or a feed's scraper rules), the fetch-content endpoint with and without saving,
pages that cannot be scraped, and the reading time of entries for different texts and reading speeds."""
import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, Ref, pathref, pick

DATE = 'Mon, 06 Jan 2025 10:00:00 GMT'
ARTICLE = page('Scraped article', '''<header><nav><a href="/">Home</a> <a href="/about">About</a></nav></header>
<main>
<article>
<h1>The scraped headline</h1>
<p class="lead">The lead paragraph of the scraped article explains what this page is about in a few words.</p>
<div class="body"><p>The first paragraph of the body has enough words to be considered the main content by an
extraction algorithm, with commas, sentences, and a <a href="related/page">relative link</a>.</p>
<p>A second paragraph continues the story with more details, more sentences, and more words for the reader.</p>
<img src="images/figure.png" alt="Figure"></div>
</article>
</main>
<aside class="sidebar"><p>Related links and other noise.</p></aside>
<footer><p>Copyright footer</p></footer>''')
BASED = page('Based article', '<article><p class="text">Relative <a href="deep/link">link</a> with a base.</p></article>',
             head='<base href="http://cdn.scrape.test/static/">\n')
LATIN = ('<!DOCTYPE html><html><head><meta charset="iso-8859-1"><title>Latin</title></head><body><article>'
         '<p class="text">Caf\xe9 cr\xe8me na\xefve, a paragraph in Latin-1 encoding.</p></article></body></html>'
         ).encode('latin-1')
WORDS = ' '.join(f'word{i}' for i in range(800))
CJK = '汉字' * 750


def feed(name, links):
    return rss(f'Scrape {name}', 'http://scrape.test/', [
        item(f'{name} item {i}', link, f'{name}-{i}', DATE, 'Feed summary only.') for i, link in enumerate(links)])


RESOURCES = [
    ('http://scrape.test/articles/full.html', ARTICLE, fx.HTML_TYPE),
    ('http://scrape.test/articles/based.html', BASED, fx.HTML_TYPE),
    ('http://scrape.test/articles/latin.html', LATIN, 'text/html'),
    ('http://scrape.test/articles/data.json', '{"not": "html"}', 'application/json'),
    ('http://scrape.test/feeds/readability.xml', feed('readability', ['http://scrape.test/articles/full.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/rules.xml', feed('rules', ['http://scrape.test/articles/full.html']), fx.RSS_TYPE),
    ('http://scrape.test/feeds/rules-many.xml', feed('rules-many', ['http://scrape.test/articles/full.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/rules-nomatch.xml', feed('nomatch', ['http://scrape.test/articles/full.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/based.xml', feed('based', ['http://scrape.test/articles/based.html']), fx.RSS_TYPE),
    ('http://scrape.test/feeds/latin.xml', feed('latin', ['http://scrape.test/articles/latin.html']), fx.RSS_TYPE),
    ('http://scrape.test/feeds/not-html.xml', feed('not-html', ['http://scrape.test/articles/data.json']), fx.RSS_TYPE),
    ('http://scrape.test/feeds/missing.xml', feed('missing', ['http://scrape.test/articles/missing.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/on-demand.xml', feed('on-demand', ['http://scrape.test/articles/full.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/on-demand-rules.xml', feed('on-demand-rules', ['http://scrape.test/articles/full.html']),
     fx.RSS_TYPE),
    ('http://scrape.test/feeds/reading.xml', rss('Reading times', 'http://scrape.test/', [
        item('Short text', 'http://scrape.test/r/short', 'r1', DATE, 'Just a few words here.'),
        item('Long text', 'http://scrape.test/r/long', 'r2', DATE, WORDS),
        item('CJK text', 'http://scrape.test/r/cjk', 'r3', DATE, CJK)]), fx.RSS_TYPE),
    ('http://scrape.test/feeds/reading-slow.xml', rss('Slow reader', 'http://scrape.test/', [
        item('Long text slow', 'http://scrape.test/r/long-slow', 'r4', DATE, WORDS),
        item('CJK text slow', 'http://scrape.test/r/cjk-slow', 'r5', DATE, CJK)]), fx.RSS_TYPE),
    ('http://scrape.test/feeds/reading-off.xml', rss('No reading time', 'http://scrape.test/', [
        item('Long text hidden', 'http://scrape.test/r/long-off', 'r6', DATE, WORDS)]), fx.RSS_TYPE),
]


def crawled(url, options):
    """Subscribe with the crawler (and options) and observe the stored content of the feed's entry."""
    def action(c):
        r, p = c.request('POST', 'feeds', body={'feed_url': url, 'category_id': c.state['category-alice']['id'],
                                                 'crawler': True, **options})
        if r.status_code >= 400:
            return c.observe(r, p)
        rr, listing = c.request('GET', f"feeds/{p['feed_id']}/entries")
        assert rr.status_code == 200 and listing['entries'], 'no stored entry'
        return {'status': r.status_code,
                'entry': c.norm.clean({k: listing['entries'][0][k] for k in ('title', 'content')}, 'entry')}
    return action


def reading(url, settings=None):
    def action(c):
        alice = c.state['alice']['id']
        out = {}
        if settings:
            out['settings'] = c.request('PUT', f'users/{alice}', body=settings)[0].status_code
        try:
            r, p = c.request('POST', 'feeds', body={'feed_url': url, 'category_id': c.state['category-alice']['id']})
            if r.status_code >= 400:
                out.update(c.observe(r, p))
                return out
            rr, listing = c.request('GET', f"feeds/{p['feed_id']}/entries", params={'order': 'title'})
            out.update(status=r.status_code, reading=[{k: e[k] for k in ('title', 'reading_time')}
                                                      for e in listing['entries']])
            return out
        finally:
            if settings:
                c.request('PUT', f'users/{alice}', body={'default_reading_speed': 265, 'cjk_reading_speed': 500,
                                                         'show_reading_time': True})
    return action


def first_entry(feed_url, save):
    def action(c):
        r, p = c.request('POST', 'feeds', body={'feed_url': feed_url, 'category_id': c.state['category-alice']['id'],
                                                 **({'scraper_rules': '.lead'} if 'rules' in feed_url else {})})
        assert 200 <= r.status_code < 300, 'setup subscription failed'
        rr, listing = c.request('GET', f"feeds/{p['feed_id']}/entries")
        c.state[save] = listing['entries'][0]
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish_all(RESOURCES))
    s.fixture('on-demand', 'subscribe', first_entry('http://scrape.test/feeds/on-demand.xml', 'demand'))
    s.fixture('on-demand', 'subscribe-rules', first_entry('http://scrape.test/feeds/on-demand-rules.xml', 'demand-rules'))
    W = ['fx:accounts', 'fx:web']
    D = W + ['fx:on-demand']

    base = s.add('crawler', 'readability', 'subscribe', crawled('http://scrape.test/feeds/readability.xml', {}),
                 needs=W, description='The crawler replaces the content with the article extracted from the page.')
    s.add('crawler', 'rules', 'subscribe', crawled('http://scrape.test/feeds/rules.xml', {'scraper_rules': '.body'}),
          needs=W, description='Scraper rules select the content of the page.')
    s.add('crawler', 'rules-many', 'subscribe',
          crawled('http://scrape.test/feeds/rules-many.xml', {'scraper_rules': 'h1, .lead'}), needs=W,
          description='Several selectors keep every matching element in page order.')
    s.add('crawler', 'rules-nomatch', 'subscribe',
          crawled('http://scrape.test/feeds/rules-nomatch.xml', {'scraper_rules': '.does-not-exist'}), needs=W,
          requires=[base], description='Scraper rules that match nothing.')
    s.add('crawler', 'base', 'subscribe', crawled('http://scrape.test/feeds/based.xml', {'scraper_rules': '.text'}),
          needs=W, description='Relative links of a page with a base element.')
    s.add('crawler', 'latin', 'subscribe', crawled('http://scrape.test/feeds/latin.xml', {'scraper_rules': '.text'}),
          needs=W, description='A page declaring its charset in a meta element.')
    s.add('crawler', 'not-html', 'subscribe', crawled('http://scrape.test/feeds/not-html.xml', {}), needs=W,
          requires=[base], description='A page that is not HTML keeps the feed content.')
    s.add('crawler', 'missing', 'subscribe', crawled('http://scrape.test/feeds/missing.xml', {}), needs=W,
          requires=[base], description='A missing page keeps the feed content.')

    demand = Ref('demand', 'id')
    fetched = s.api('fetch-content', 'preview', 'readability', 'GET', pathref('entries/{id}/fetch-content', id=demand),
                    needs=D, description='Fetching the original content returns it without saving it.')
    s.api('fetch-content', 'preview', 'stored-unchanged', 'GET', pathref('entries/{id}', id=demand), needs=D,
          requires=[fetched], view=pick('content'), description='The preview did not change the stored content.')
    saved = s.api('fetch-content', 'save', 'update', 'GET', pathref('entries/{id}/fetch-content', id=demand), needs=D,
                  params={'update_content': 'true'}, description='Fetching the original content and saving it.')
    s.api('fetch-content', 'save', 'stored', 'GET', pathref('entries/{id}', id=demand), needs=D, requires=[saved],
          view=pick('content', 'reading_time'), description='The saved original content is stored.')
    s.api('fetch-content', 'rules', 'preview', 'GET', pathref('entries/{id}/fetch-content', id=Ref('demand-rules', 'id')),
          needs=D, description='Fetching the original content uses the feed\'s scraper rules.')
    s.api('fetch-content', 'errors', 'missing', 'GET', 'entries/987654/fetch-content', requires=[fetched],
          description='Fetching the content of an unknown entry.')
    s.api('fetch-content', 'errors', 'other-account', 'GET', pathref('entries/{id}/fetch-content', id=demand),
          actor='bob', needs=D, requires=[fetched], description='Fetching the content of another account\'s entry.')

    s.add('reading-time', 'default', 'subscribe', reading('http://scrape.test/feeds/reading.xml'), needs=W,
          description='Reading times of a short, a long and a CJK text at the default speeds.')
    s.add('reading-time', 'slow', 'subscribe', reading('http://scrape.test/feeds/reading-slow.xml', {
        'default_reading_speed': 100, 'cjk_reading_speed': 200}), needs=W,
        description='Reading times follow the user\'s reading speeds.')
    s.add('reading-time', 'off', 'subscribe', reading('http://scrape.test/feeds/reading-off.xml', {
        'show_reading_time': False}), needs=W, description='Reading times when the user hides them.')
