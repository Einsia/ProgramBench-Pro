"""Feed discovery through the REST API: a URL that is already a feed, alternate links of a web page (types,
relative addresses, base element, titles, duplicates, WordPress JSON), canonical pages of YouTube channels and
playlists and of GitHub, probing of well-known feed addresses, credentials and user agents, and errors."""
import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, sent

FEED = rss('Discovered feed', 'http://disco.test/', [
    item('Discovered entry', 'http://disco.test/e', 'd-1', 'Mon, 06 Jan 2025 10:00:00 GMT', 'Body.')])
ATOM = fx.atom('Discovered atom', 'http://disco.test/', [fx.entry('Atom entry', 'http://disco.test/a', 'urn:a',
                                                                 '2025-01-06T10:00:00Z')])
JSONFEED = fx.jsonfeed('Discovered JSON', 'http://disco.test/', [{'id': '1', 'url': 'http://disco.test/j',
                                                                 'title': 'JSON entry'}])


def links(*tags):
    return page('Discovery page', '<p>Page</p>', head=''.join(t + '\n' for t in tags))


ALTERNATES = links('<link rel="alternate" type="application/rss+xml" title="RSS edition" href="/feeds/rss.xml">',
                   '<link rel="alternate" type="application/atom+xml" title="Atom edition" '
                   'href="http://disco.test/feeds/atom.xml">',
                   '<link rel="alternate" type="application/feed+json" title="JSON edition" href="feeds/feed.json">',
                   '<link rel="alternate" type="text/html" title="Not a feed" href="/other.html">')
RESOURCES = [
    ('http://disco.test/feeds/rss.xml', FEED, fx.RSS_TYPE), ('http://disco.test/feeds/atom.xml', ATOM, fx.ATOM_TYPE),
    ('http://disco.test/feeds/feed.json', JSONFEED, fx.JSON_TYPE),
    ('http://disco.test/alternates/', ALTERNATES, fx.HTML_TYPE),
    ('http://disco.test/base/', links('<base href="http://cdn.disco.test/static/">',
                                      '<link rel="alternate" type="application/rss+xml" title="Based" href="based.xml">'),
     fx.HTML_TYPE),
    ('http://disco.test/untitled/', links('<link rel="alternate" type="application/atom+xml" href="/feeds/atom.xml">'),
     fx.HTML_TYPE),
    ('http://disco.test/duplicates/', links(
        '<link rel="alternate" type="application/rss+xml" title="First" href="/feeds/rss.xml">',
        '<link rel="alternate" type="application/rss+xml" title="Second" href="http://disco.test/feeds/rss.xml">'),
     fx.HTML_TYPE),
    ('http://disco.test/wordpress/', links(
        '<link rel="alternate" type="application/json" title="WP API" href="/wp-json/wp/v2/posts">',
        '<link rel="alternate" type="application/json" title="Plain JSON" href="/feeds/feed.json">'), fx.HTML_TYPE),
    ('http://disco.test/youtube-channel/', links('<link rel="canonical" href="https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv">'),
     fx.HTML_TYPE),
    ('http://disco.test/youtube-playlist/', links('<link rel="canonical" href="https://www.youtube.com/playlist?list=PLxyz123">'),
     fx.HTML_TYPE),
    ('http://disco.test/github-repo/', links('<link rel="canonical" href="https://github.com/octo/widget">'),
     fx.HTML_TYPE),
    ('http://disco.test/github-user/', links('<link rel="canonical" href="https://github.com/octo">'), fx.HTML_TYPE),
    ('http://known.test/', page('No links', '<p>Nothing declared</p>'), fx.HTML_TYPE),
    ('http://known.test/atom.xml', ATOM, fx.ATOM_TYPE), ('http://known.test/rss.xml', FEED, fx.RSS_TYPE),
    ('http://known.test/feed.xml', '', 'text/plain', 301, {'location': 'http://known.test/'}),
    ('http://known.test/blog/', page('Blog', '<p>Blog</p>'), fx.HTML_TYPE),
    ('http://known.test/blog/feed/', FEED, fx.RSS_TYPE),
    ('http://empty.test/', page('Nothing', '<p>No feeds anywhere</p>'), fx.HTML_TYPE),
    ('http://private.disco.test/', ALTERNATES, fx.HTML_TYPE, 200, None, ['finder', 'Finder-Pass-2026']),
    ('http://agent.disco.test/', FEED, fx.RSS_TYPE),
]


def discover(url, options=None, log_host=None, headers=('user-agent', 'authorization', 'cookie')):
    def action(c):
        mark = c.web_mark()
        r, p = c.request('POST', 'discover', body={'url': url, **(options or {})})
        out = c.observe(r, p)
        if log_host:
            out['requests'] = [sent(x, headers) for x in c.web_requests(host=log_host, since=mark)]
        return out
    return action


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    s.fixture('web', 'publish', fx.publish_all(RESOURCES))
    W = ['fx:accounts', 'fx:web']

    direct = s.add('discover', 'feed', 'rss', discover('http://disco.test/feeds/rss.xml'), needs=W,
                   description='A URL that is already an RSS feed.')
    s.add('discover', 'feed', 'atom', discover('http://disco.test/feeds/atom.xml'), needs=W,
          description='A URL that is already an Atom feed.')
    s.add('discover', 'feed', 'json', discover('http://disco.test/feeds/feed.json'), needs=W,
          description='A URL that is already a JSON Feed.')
    s.add('discover', 'page', 'alternates', discover('http://disco.test/alternates/'), needs=W,
          description='The alternate feed links of a web page, in page order.')
    s.add('discover', 'page', 'base', discover('http://disco.test/base/'), needs=W,
          description='Relative feed links of a page with a base element.')
    s.add('discover', 'page', 'untitled', discover('http://disco.test/untitled/'), needs=W,
          description='A feed link without title.')
    s.add('discover', 'page', 'duplicates', discover('http://disco.test/duplicates/'), needs=W,
          description='Two links to the same feed.')
    s.add('discover', 'page', 'wordpress', discover('http://disco.test/wordpress/'), needs=W,
          description='JSON links of a WordPress REST API are not feeds.')
    s.add('discover', 'canonical', 'youtube-channel', discover('http://disco.test/youtube-channel/'), needs=W,
          description='A page whose canonical address is a YouTube channel.')
    s.add('discover', 'canonical', 'youtube-playlist', discover('http://disco.test/youtube-playlist/'), needs=W,
          description='A page whose canonical address is a YouTube playlist.')
    s.add('discover', 'canonical', 'github-repository', discover('http://disco.test/github-repo/'), needs=W,
          description='A page whose canonical address is a GitHub repository.')
    s.add('discover', 'canonical', 'github-user', discover('http://disco.test/github-user/'), needs=W,
          description='A page whose canonical address is a GitHub user.')
    s.add('discover', 'known', 'root', discover('http://known.test/'), needs=W,
          description='Well-known feed addresses of a site without links; redirects are not offered.')
    s.add('discover', 'known', 'probes', discover('http://known.test/', log_host='known.test', headers=()), needs=W,
          description='The well-known addresses the product tries, in order.')
    s.add('discover', 'known', 'subdirectory', discover('http://known.test/blog/'), needs=W,
          description='Well-known feed addresses below the page\'s directory.')
    s.add('discover', 'none', 'nothing', discover('http://empty.test/'), needs=W, requires=[direct],
          description='A site without any feed.')
    s.add('discover', 'errors', 'not-found', discover('http://disco.test/missing-page'), needs=W, requires=[direct],
          description='A page that does not exist.')
    s.add('discover', 'errors', 'unauthorized', discover('http://private.disco.test/'), needs=W, requires=[direct],
          description='A page behind credentials, without them.')
    s.add('discover', 'credentials', 'authorized', discover('http://private.disco.test/', {
        'username': 'finder', 'password': 'Finder-Pass-2026'}, log_host='private.disco.test'), needs=W,
        description='Discovery with HTTP Basic credentials.')
    s.add('discover', 'options', 'user-agent-cookie', discover('http://agent.disco.test/', {
        'user_agent': 'Discovery Agent/9', 'cookie': 'pref=1'}, log_host='agent.disco.test'), needs=W,
        description='Discovery sends the requested user agent and cookie.')
    s.add('discover', 'errors', 'empty-url', discover(''), needs=W, requires=[direct],
          description='The URL is mandatory.')
    s.add('discover', 'errors', 'invalid-url', discover('not a url'), needs=W, requires=[direct],
          description='An invalid URL is refused.')
    s.api('discover', 'errors', 'anonymous', 'POST', 'discover', actor=None, body={'url': 'http://disco.test/'},
          requires=[direct], description='Discovery needs credentials.')
