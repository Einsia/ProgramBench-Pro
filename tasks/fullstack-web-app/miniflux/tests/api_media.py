"""The media proxy and icons as product addresses: images of entry content and image enclosures are served from
the product's own origin (/proxy/...), which fetches them from their site; HTTPS images and other media are
left alone; altered or unknown proxy addresses are refused; feed icons are served under /feed-icon/."""
import base64
import re

import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS

IMAGE = fx.png(4, 3, (10, 200, 30))
ICON = fx.png(16, 16, (90, 20, 160))
CONTENT = ('<p><img src="http://media.test/pictures/photo.png" alt="photo">'
           '<img src="https://secure.media.test/remote.png" alt="secure">'
           '<img src="http://media.test/pictures/missing.png" alt="missing"></p>'
           '<video src="http://media.test/clip.mp4" poster="http://media.test/pictures/photo.png"></video>')
FEED = rss('Media fixture', 'http://media.test/', [
    item('Media entry', 'http://media.test/entry', 'm-1', 'Mon, 06 Jan 2025 10:00:00 GMT', fx.html_text(CONTENT),
         '<enclosure url="http://media.test/pictures/photo.png" length="99" type="image/png"/>'
         '<enclosure url="http://media.test/episode.mp3" length="77" type="audio/mpeg"/>')])
SITE = page('Media site', '<p>Media</p>', head='<link rel="icon" type="image/png" href="/icon.png">\n')
PROXY = re.compile(r'/proxy/[^"\s<>]+')


def remember(c):
    c.state['entry'] = fx.entries_of(c, 'feed')[0]


def current(c):
    r, entry = c.request('GET', f"entries/{c.state['entry']['id']}")
    assert r.status_code == 200 and isinstance(entry, dict), 'the entry cannot be read'
    return entry


def proxy_addresses(c, entry=None):
    """The media proxy addresses of the stored entry: those in its content and its enclosure URLs."""
    entry = entry or current(c)
    found = PROXY.findall(entry['content'])
    found += [PROXY.search(e['url'])[0] for e in entry['enclosures'] if PROXY.search(e['url'])]
    return found


def fetch(index, tamper=None):
    """GET one media proxy address of the entry (optionally altered) and observe the bytes it serves."""
    def action(c):
        addresses = proxy_addresses(c)
        assert len(addresses) > index, 'the entry has no media proxy address number %d' % (index + 1)
        path = addresses[index]
        if tamper:
            path = tamper(path)
        r, _ = c.request('GET', path, None)
        out = {'status': r.status_code}
        if r.status_code < 300:
            out.update(content_type=(r.headers.get('content-type') or '').split(';')[0],
                       sha256_matches_site=r.content == IMAGE)
        return out
    return action


def addresses(c):
    """Which addresses of the entry were rewritten through the proxy, as decoded original URLs."""
    entry = current(c)
    decoded = []
    for path in proxy_addresses(c, entry):
        encoded = path.rsplit('/', 1)[-1]
        decoded.append(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)).decode())
    return {'proxied': sorted(decoded),
            'enclosures': [{'mime_type': e['mime_type'], 'proxied': '/proxy/' in e['url']} for e in entry['enclosures']]}


def swap_signature(path):
    """Change the first character of the signature to another character of the same alphabet: the address stays
    well formed and the signature no longer matches."""
    head, signature, encoded = path.rsplit('/', 2)
    return f"{head}/{'B' if signature[0] == 'A' else 'A'}{signature[1:]}/{encoded}"


def other_url(path):
    head, signature, _ = path.rsplit('/', 2)
    return f'{head}/{signature}/' + base64.urlsafe_b64encode(b'http://media.test/other.png').decode()


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    s.fixture('web', 'publish', fx.publish_all([
        ('http://media.test/feed.xml', FEED, fx.RSS_TYPE), ('http://media.test/', SITE, fx.HTML_TYPE),
        ('http://media.test/icon.png', ICON, 'image/png'), ('http://media.test/pictures/photo.png', IMAGE, 'image/png'),
        ('http://media.test/other.png', IMAGE, 'image/png')]))
    fx.subscribe(s, 'library', 'feed', 'http://media.test/feed.xml', 'feed')
    s.fixture('library', 'entry', remember)
    L = ['fx:accounts', 'fx:web', 'fx:library']
    rewritten = s.add('proxy', 'rewrite', 'addresses', addresses, needs=L,
                      description='HTTP images of content (sources and video posters) and image enclosures are '
                                  'rewritten to the product\'s media proxy; HTTPS images and other media are not.')
    served = s.add('proxy', 'serve', 'image', fetch(0), needs=L,
                   description='A media proxy address serves the image fetched from its site, without credentials.')
    s.add('proxy', 'serve', 'enclosure', fetch(-1), needs=L, requires=[served],
          description='The proxied image enclosure serves the image.')
    s.add('proxy', 'serve', 'missing-origin', fetch(1), needs=L, requires=[served],
          description='A proxied image whose site answers 404.')
    s.add('proxy', 'refuse', 'altered-signature', fetch(0, swap_signature), needs=L, requires=[served],
          description='A proxy address with an altered signature is refused.')
    s.add('proxy', 'refuse', 'other-url', fetch(0, other_url), needs=L, requires=[served],
          description='A signature does not authorise another URL.')
    s.api('proxy', 'refuse', 'garbage', 'GET', '/proxy/not-base64!/also-not', actor=None, requires=[served],
          description='A malformed proxy address.')

    def icon(c):
        r, payload = c.request('GET', f"feeds/{c.state['feed']['feed_id']}")
        assert r.status_code == 200 and payload.get('icon'), 'the feed has no icon'
        rr, _ = c.request('GET', '/feed-icon/' + payload['icon']['external_icon_id'], None)
        return {'status': rr.status_code, 'content_type': (rr.headers.get('content-type') or '').split(';')[0],
                'same_bytes': rr.content == ICON}
    s.add('icons', 'route', 'feed-icon', icon, needs=L, requires=[rewritten],
          description='A feed icon is served under /feed-icon/ by its external id, without credentials.')
    s.api('icons', 'route', 'unknown', 'GET', '/feed-icon/0000000000000000000000000000000000000000', actor=None,
          requires=[rewritten], description='An unknown feed icon id.')
