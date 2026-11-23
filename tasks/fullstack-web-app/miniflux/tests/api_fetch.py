"""What the product sends to other web hosts and how it treats their answers: request headers (user agent,
cookies, credentials), conditional requests with ETag and Last-Modified, the HTTP cache setting, errors and
recovery of refreshes, redirects, disabled feeds and crawling, read from the local web's request log."""
import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, Ref, members, pathref, pick, sent

V1 = rss('Fetch Daily', 'http://fetch.test/', [
    item('First fetch story', 'http://fetch.test/story/1', 'fetch-1', 'Mon, 05 May 2025 08:00:00 GMT', 'One.')])
V2 = rss('Fetch Daily', 'http://fetch.test/', [
    item('First fetch story', 'http://fetch.test/story/1', 'fetch-1', 'Mon, 05 May 2025 08:00:00 GMT', 'One.'),
    item('Second fetch story', 'http://fetch.test/story/2', 'fetch-2', 'Tue, 06 May 2025 08:00:00 GMT', 'Two.')])
CRAWLED = rss('Crawled Daily', 'http://crawl.test/', [
    item('Crawled one', 'http://crawl.test/articles/one.html', 'crawl-1', 'Mon, 05 May 2025 09:00:00 GMT', 'Short.'),
    item('Crawled two', 'http://crawl.test/articles/two.html', 'crawl-2', 'Tue, 06 May 2025 09:00:00 GMT', 'Short.')])
ARTICLE = page('Crawled article', '<article><h1>Full text</h1><p>The crawled article body, long enough to be the '
               'main content of the page for the extraction.</p><p>A second paragraph of the article.</p></article>')
SITE = page('Fetch site', '<p>Fetch site</p>', head='<link rel="icon" href="/favicon.png">\n')
ICON = fx.png(16, 16, (20, 120, 60))
HOSTS = ['agent', 'cookie', 'auth', 'etag', 'modified', 'nocache', 'errors', 'redirect', 'disabled', 'enabled']


def url(host, path='/feed.xml'):
    return f'http://{host}.fetch.test{path}'


def resources():
    out = []
    for host in HOSTS:
        auth = ['fetcher', 'Fetch-Secret-2026'] if host == 'auth' else None
        headers = {'etag': '"v1"'} if host in ('etag', 'nocache') else (
            {'last-modified': 'Mon, 05 May 2025 10:00:00 GMT'} if host == 'modified' else None)
        out.append((url(host), V1, fx.RSS_TYPE, 200, headers, auth))
    out += [('http://fetch.test/', SITE, fx.HTML_TYPE), ('http://fetch.test/favicon.png', ICON, 'image/png'),
            (url('redirect', '/old.xml'), '', 'text/plain', 302, {'location': url('redirect', '/new.xml')}),
            (url('redirect', '/new.xml'), V1, fx.RSS_TYPE),
            ('http://crawl.test/feed.xml', CRAWLED, fx.RSS_TYPE),
            ('http://crawl.test/articles/one.html', ARTICLE, fx.HTML_TYPE),
            ('http://crawl.test/articles/two.html', ARTICLE, fx.HTML_TYPE)]
    return out


def requests_of(c, host, mark):
    return [x for x in c.web_requests(host=host, since=mark)]


def subscribe_and_log(host, options=None, headers=('user-agent', 'accept', 'authorization', 'cookie'), feed_url=None):
    """Subscribe to a fixture feed and observe the requests the product sent for it."""
    def action(c):
        mark = c.web_mark()
        body = {'feed_url': feed_url or url(host), 'category_id': c.state['category-alice']['id'], **(options or {})}
        r, p = c.request('POST', 'feeds', body=body)
        if r.status_code < 400:
            c.state['feed-' + host] = p
        requests = c.wait(lambda: requests_of(c, f'{host}.fetch.test', mark), lambda x: len(x) > 0, 5)
        return {'status': r.status_code, 'requests': [sent(x, headers) for x in requests]}
    return action


def subscription_requests(c):
    mark = c.web_mark()
    r, p = c.request('POST', 'feeds', body={'feed_url': url('etag'), 'category_id': c.state['category-alice']['id']})
    if r.status_code < 400:
        c.state['feed-etag'] = p
    requests = [x for x in c.web_requests(since=mark) if x['host'] in ('etag.fetch.test', 'fetch.test')]
    return {'status': r.status_code, 'requests': [sent(x, ()) for x in requests]}


def refresh_and_log(host, headers=('if-none-match', 'if-modified-since'), republish=None):
    """Refresh one fixture feed and observe the conditional headers of its request and the feed's error state."""
    def action(c):
        if republish:
            c.web_put(url(host), *republish)
        mark = c.web_mark()
        feed_id = c.state['feed-' + host]['feed_id']
        r, p = c.request('PUT', f'feeds/{feed_id}/refresh')
        requests = requests_of(c, f'{host}.fetch.test', mark)
        rr, feed = c.request('GET', f'feeds/{feed_id}')
        return {'refresh': c.observe(r, p), 'requests': [sent(x, headers) for x in requests],
                'feed': c.observe(rr, feed, view=pick('parsing_error_count', 'parsing_error_message', 'etag_header',
                                                      'last_modified_header'))}
    return action


def feed_entries(host):
    def action(c):
        r, p = c.request('GET', f"feeds/{c.state['feed-' + host]['feed_id']}/entries",
                         params={'order': 'published_at', 'direction': 'asc'})
        return c.observe(r, p, view=members('entries', 'title', 'status'))
    return action


def refresh_all_and_log(c):
    """Refresh every feed of the account (in the background) and list which fixture hosts were asked."""
    mark = c.web_mark()
    r, p = c.request('PUT', 'feeds/refresh')
    # Only the two hosts of this scenario: one enabled feed, one disabled feed.
    hosts = lambda: sorted({x['host'] for x in c.web_requests(since=mark)
                            if x['host'] in ('enabled.fetch.test', 'disabled.fetch.test')})
    asked = c.settle(hosts)
    return {'refresh': c.observe(r, p), 'hosts': asked}


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish_all(resources()))
    W = ['fx:accounts', 'fx:web']

    plain = s.add('fetch', 'subscribe', 'default-headers', subscribe_and_log('agent', headers=(
        'user-agent', 'accept', 'authorization', 'cookie')), needs=W,
        description='Subscribing fetches the feed with the product\'s default user agent and accept headers.')
    s.add('fetch', 'subscribe', 'user-agent', subscribe_and_log('cookie', {'user_agent': 'FixtureAgent/3.1'},
                                                                 headers=('user-agent',)),
          needs=W, requires=[plain], description='A feed\'s own user agent is sent when fetching it.')
    s.add('fetch', 'subscribe', 'cookie', subscribe_and_log('auth', {
        'cookie': 'session=fixture; lang=en', 'username': 'fetcher', 'password': 'Fetch-Secret-2026'},
        headers=('cookie', 'authorization')), needs=W, requires=[plain],
        description='A feed\'s cookies and HTTP Basic credentials are sent when fetching it.')
    s.add('fetch', 'subscribe', 'site-and-icon', subscription_requests, needs=W, requires=[plain],
          description='Which requests a subscription sends, in order (the feed, then its site and icon).')

    # Conditional requests.
    etag = s.add('fetch', 'refresh', 'etag', refresh_and_log('etag'), needs=W,
                 description='Refreshing a feed that sent an ETag asks with If-None-Match; 304 changes nothing.')
    s.add('fetch', 'refresh', 'etag-entries', feed_entries('etag'), needs=W, requires=[etag],
          description='After an unchanged (304) refresh the entries are the same.')
    s.add('fetch', 'subscribe', 'last-modified', subscribe_and_log('modified', headers=()), needs=W,
          description='Subscribing to a feed that sends Last-Modified.')
    s.add('fetch', 'refresh', 'last-modified', refresh_and_log('modified'), needs=W,
          description='Refreshing a feed that sent Last-Modified asks with If-Modified-Since.')
    s.add('fetch', 'subscribe', 'ignore-cache', subscribe_and_log('nocache', {'ignore_http_cache': True},
                                                                  headers=()), needs=W,
          description='Subscribing with the HTTP cache ignored.')
    s.add('fetch', 'refresh', 'ignore-cache', refresh_and_log('nocache'), needs=W, requires=[etag],
          description='With the HTTP cache ignored the refresh is not conditional.')
    changed = s.add('fetch', 'refresh', 'changed-etag', refresh_and_log('etag', republish=(
        V2, fx.RSS_TYPE, 200, {'etag': '"v2"'})), needs=W,
        description='A changed feed with a new ETag is read again and its new ETag kept.')
    s.add('fetch', 'refresh', 'changed-entries', feed_entries('etag'), needs=W, requires=[changed],
          description='The new entry of the changed feed is stored as unread.')

    # Errors while refreshing, then recovery.
    s.add('fetch', 'subscribe', 'errors', subscribe_and_log('errors', headers=()), needs=W,
          description='Subscribing to the feed whose host fails later.')
    first = s.add('fetch', 'refresh', 'server-error', refresh_and_log('errors', headers=(), republish=(
        'Down', 'text/plain', 500)), needs=W, description='A refresh answered 500 records a feed error.')
    s.add('fetch', 'refresh', 'not-found', refresh_and_log('errors', headers=(), republish=(
        'Gone', 'text/plain', 404)), needs=W, requires=[first], description='A second failure (404) counts again.')
    s.add('fetch', 'refresh', 'unparsable', refresh_and_log('errors', headers=(), republish=(
        '<html><body>Not a feed</body></html>', fx.HTML_TYPE, 200)), needs=W, requires=[first],
        description='A refresh that is not a feed counts as an error too.')
    s.add('fetch', 'refresh', 'recovered', refresh_and_log('errors', headers=(), republish=(V2, fx.RSS_TYPE, 200)),
          needs=W, requires=[first], description='A successful refresh clears the feed error.')

    # Redirects.
    s.add('fetch', 'subscribe', 'redirect', subscribe_and_log('redirect', headers=(), feed_url=url('redirect', '/old.xml')),
          needs=W, description='A temporary redirect is followed when subscribing.')
    s.api('fetch', 'subscribe', 'redirect-feed', 'GET', pathref('feeds/{id}', id=Ref('feed-redirect', 'feed_id')),
          needs=W, view=pick('feed_url'), description='The address a temporarily redirected subscription keeps.')

    # Refreshing every feed skips disabled ones.
    disabled = s.add('fetch', 'subscribe', 'disabled', subscribe_and_log('disabled', {'disabled': True}, headers=()),
                     needs=W, description='Subscribing to a feed that is disabled.')
    enabled = s.add('fetch', 'subscribe', 'enabled', subscribe_and_log('enabled', headers=()), needs=W,
                    description='Subscribing to a feed that stays enabled.')
    all_feeds = s.add('fetch', 'refresh', 'all', refresh_all_and_log, needs=W + [disabled, enabled],
                      description='Refreshing all feeds asks every enabled feed\'s host, never a disabled one.')
    s.add('fetch', 'refresh', 'disabled-one', refresh_and_log('disabled', headers=()), needs=W, requires=[all_feeds],
          description='Whether refreshing one disabled feed fetches it.')

    # Crawling new entries.
    def crawl(c):
        mark = c.web_mark()
        r, p = c.request('POST', 'feeds', body={'feed_url': 'http://crawl.test/feed.xml', 'crawler': True,
                                                 'category_id': c.state['category-alice']['id']})
        pages = sorted(x['url'] for x in c.web_requests(host='crawl.test', since=mark) if '/articles/' in x['url'])
        return {'status': r.status_code, 'pages': pages}
    s.add('fetch', 'crawler', 'pages', crawl, needs=W,
          description='With the crawler on, the product fetches the page of every new entry.')
