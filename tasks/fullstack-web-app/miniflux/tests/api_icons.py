"""Feed icons: where the product looks for a feed's icon (the icon the feed itself names, the icon links of the
web site and of its root page, the conventional /favicon.ico) and in which order, which icon it keeps, how it
treats data URLs, large and oversized pictures, failing downloads, shared icons and icons that appear later."""
import base64
import json
import struct

import fixtures as fx
from fixtures import item, page, rss
from harness import CREDS, norm_text

DATE = 'Mon, 06 Oct 2025 09:00:00 GMT'
SMALL = fx.png(16, 16, (220, 60, 30))
OTHER = fx.png(24, 24, (30, 160, 60))
LARGE = fx.png(64, 64, (40, 80, 200))
TOUCH = fx.png(180, 180, (120, 30, 160))
HUGE = fx.png(5000, 8, (10, 10, 10))
ICO = (struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', 16, 16, 0, 0, 1, 32, len(SMALL), 22) + SMALL)
SVG = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">\n'
       '  <!-- a comment -->\n  <rect x="0" y="0" width="16" height="16" fill="#ff0000" />\n</svg>\n').encode()
PICTURES = {'small': SMALL, 'other': OTHER, 'large': LARGE, 'touch': TOUCH, 'huge': HUGE, 'ico': ICO, 'svg': SVG}


def feed_doc(host, extra=''):
    return rss(f'Icons {host}', f'http://{host}/', [item('Icon entry', f'http://{host}/1', f'{host}-1', DATE, 'Body')],
               extra=extra)


def json_doc(host, **fields):
    return json.dumps({'version': 'https://jsonfeed.org/version/1.1', 'title': f'Icons {host}',
                       'home_page_url': f'http://{host}/', **fields,
                       'items': [{'id': '1', 'url': f'http://{host}/1', 'title': 'Icon entry',
                                  'date_published': '2025-10-06T09:00:00Z'}]})


def home(links):
    return page('Icon site', '<p>Site</p>', head=''.join(f'<link rel="{rel}" href="{href}">\n' for rel, href in links))


def png_size(data):
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return list(struct.unpack('>II', data[16:24]))
    return None


def icon_view(c, feed_id):
    """The stored icon: its type, which published picture it is (or its PNG size when it was converted)."""
    r, p = c.request('GET', f'feeds/{feed_id}/icon')
    if r.status_code != 200 or not isinstance(p, dict):
        return {'status': r.status_code}
    data = p.get('data') or ''
    raw = base64.b64decode(data.split(',', 1)[1]) if ',' in data else b''
    source = next((name for name, value in PICTURES.items() if value == raw), None)
    out = {'status': r.status_code, 'mime_type': p.get('mime_type'), 'source': source}
    if source is None:
        out['png_size'] = png_size(raw)
        out['svg'] = raw.lstrip().startswith(b'<svg') or b'<svg' in raw[:200]
    return out


def requested(c, host, mark):
    return [norm_text(x['url']) for x in c.web_requests(host=host, since=mark) if x['method'] != 'CONNECT']


def case(host, resources, feed_path='feed.xml', fetches=True):
    """Publish the case's resources, subscribe to its feed and observe the icon and the requests made for it."""
    def action(c):
        for path, body, kind in resources:
            c.web_put(f'http://{host}{path}', body, kind)
        mark = c.web_mark()
        r, p = c.request('POST', 'feeds', body={'feed_url': f'http://{host}/{feed_path}',
                                                 'category_id': c.state['category-alice']['id']})
        if r.status_code >= 400:
            return c.observe(r, p)
        out = {'status': r.status_code, 'icon': icon_view(c, p['feed_id'])}
        if fetches:
            out['requests'] = requested(c, host, mark)
        c.state['feed-' + host] = p['feed_id']
        return out
    return action


def shared(c):
    """Two feeds whose sites use the same picture share one stored icon."""
    ids = []
    for host in ('share-a.icons.test', 'share-b.icons.test'):
        c.web_put(f'http://{host}/feed.xml', feed_doc(host), fx.RSS_TYPE)
        c.web_put(f'http://{host}/', home([('icon', '/same.png')]), fx.HTML_TYPE)
        c.web_put(f'http://{host}/same.png', OTHER, 'image/png')
        r, p = c.request('POST', 'feeds', body={'feed_url': f'http://{host}/feed.xml',
                                                 'category_id': c.state['category-alice']['id']})
        assert r.status_code == 201, 'subscription failed'
        rr, icon = c.request('GET', f"feeds/{p['feed_id']}/icon")
        ids.append(icon.get('id') if rr.status_code == 200 and isinstance(icon, dict) else None)
    return {'icons': [x is not None for x in ids], 'same_icon': ids[0] is not None and ids[0] == ids[1]}


def appears_later(c):
    """An icon published after the subscription is picked up by a later refresh."""
    host = 'later.icons.test'
    feed_id = c.state['feed-' + host]
    c.web_put(f'http://{host}/', home([('icon', '/late.png')]), fx.HTML_TYPE)
    c.web_put(f'http://{host}/late.png', OTHER, 'image/png')
    mark = c.web_mark()
    r, _ = c.request('PUT', f'feeds/{feed_id}/refresh')
    return {'status': r.status_code, 'icon': icon_view(c, feed_id), 'requests': requested(c, host, mark)}


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    A = ['fx:accounts']
    H, P, X = fx.HTML_TYPE, 'image/png', fx.RSS_TYPE
    link = s.add('icons', 'site', 'link-icon', case('link.icons.test', [
        ('/feed.xml', feed_doc('link.icons.test'), X), ('/', home([('icon', '/small.png')]), H),
        ('/small.png', SMALL, P)]), needs=A, description='The icon link of the feed\'s web site.')
    s.add('icons', 'site', 'shortcut-icon', case('shortcut.icons.test', [
        ('/feed.xml', feed_doc('shortcut.icons.test'), X), ('/', home([('shortcut icon', '/favicon-site.ico')]), H),
        ('/favicon-site.ico', ICO, 'image/x-icon')]), needs=A, description='A "shortcut icon" link to an ICO file.')
    s.add('icons', 'site', 'apple-touch-icon', case('touch.icons.test', [
        ('/feed.xml', feed_doc('touch.icons.test'), X), ('/', home([('apple-touch-icon', '/touch.png')]), H),
        ('/touch.png', TOUCH, P)]), needs=A, description='An apple-touch-icon link; a large picture is reduced.')
    s.add('icons', 'site', 'document-order', case('order.icons.test', [
        ('/feed.xml', feed_doc('order.icons.test'), X),
        ('/', home([('apple-touch-icon', '/touch.png'), ('icon', '/small.png')]), H),
        ('/touch.png', TOUCH, P), ('/small.png', SMALL, P)]), needs=A,
        description='With several icon links, the first one in the page.')
    s.add('icons', 'site', 'rel-case', case('upper.icons.test', [
        ('/feed.xml', feed_doc('upper.icons.test'), X), ('/', home([('ICON', '/small.png')]), H),
        ('/small.png', SMALL, P)]), needs=A, description='An icon link whose rel is written in capitals.')
    s.add('icons', 'site', 'other-rel', case('alternate.icons.test', [
        ('/feed.xml', feed_doc('alternate.icons.test'), X), ('/', home([('preload', '/small.png')]), H),
        ('/small.png', SMALL, P)]), needs=A, requires=[link], description='Links that are not icon links are ignored.')
    s.add('icons', 'site', 'first-fails', case('broken.icons.test', [
        ('/feed.xml', feed_doc('broken.icons.test'), X),
        ('/', home([('icon', '/missing.png'), ('icon', '/other.png')]), H), ('/other.png', OTHER, P)]), needs=A,
        description='When the first icon cannot be downloaded, the next icon link.')
    s.add('icons', 'site', 'data-url', case('data.icons.test', [
        ('/feed.xml', feed_doc('data.icons.test'), X),
        ('/', home([('icon', 'data:image/png;base64,' + base64.b64encode(SMALL).decode())]), H)]), needs=A,
        description='An icon given as a data URL is used without a download.')
    s.add('icons', 'site', 'large', case('large.icons.test', [
        ('/feed.xml', feed_doc('large.icons.test'), X), ('/', home([('icon', '/large.png')]), H),
        ('/large.png', LARGE, P)]), needs=A, description='A picture larger than an icon is reduced to icon size.')
    s.add('icons', 'site', 'oversized', case('huge.icons.test', [
        ('/feed.xml', feed_doc('huge.icons.test'), X), ('/', home([('icon', '/huge.png')]), H),
        ('/huge.png', HUGE, P), ('/favicon.ico', ICO, 'image/x-icon')]), needs=A,
        description='An oversized picture is refused and the search goes on.')
    s.add('icons', 'site', 'svg', case('svg.icons.test', [
        ('/feed.xml', feed_doc('svg.icons.test'), X), ('/', home([('icon', '/logo.svg')]), H),
        ('/logo.svg', SVG, 'image/svg+xml')]), needs=A, description='An SVG icon stays an SVG picture.')
    s.add('icons', 'fallback', 'root-page', case('root.icons.test', [
        ('/blog/feed.xml', rss('Icons root', 'http://root.icons.test/blog/', [
            item('Icon entry', 'http://root.icons.test/blog/1', 'root-1', DATE, 'Body')]), X),
        ('/blog/', home([]), H), ('/', home([('icon', '/small.png')]), H), ('/small.png', SMALL, P)],
        feed_path='blog/feed.xml'), needs=A,
        description='Without icon links on the site page, the icon links of the root page.')
    s.add('icons', 'fallback', 'favicon', case('favicon.icons.test', [
        ('/feed.xml', feed_doc('favicon.icons.test'), X), ('/', home([]), H), ('/favicon.ico', ICO, 'image/x-icon')]),
        needs=A, description='Without icon links, the conventional /favicon.ico.')
    s.add('icons', 'fallback', 'none', case('none.icons.test', [
        ('/feed.xml', feed_doc('none.icons.test'), X), ('/', home([]), H)]), needs=A, requires=[link],
        description='A site without any icon: what was tried, and no icon.')
    s.add('icons', 'feed', 'rss-image', case('image.icons.test', [
        ('/feed.xml', feed_doc('image.icons.test', '<image><url>/logo.png</url><title>Logo</title>'
                                                    '<link>http://image.icons.test/</link></image>\n'), X),
        ('/', home([('icon', '/small.png')]), H), ('/logo.png', OTHER, P), ('/small.png', SMALL, P)]), needs=A,
        description='The image a feed names is its icon, before the site\'s icon links.')
    s.add('icons', 'feed', 'rss-image-missing', case('noimage.icons.test', [
        ('/feed.xml', feed_doc('noimage.icons.test', '<image><url>/gone.png</url><title>Logo</title>'
                                                      '<link>http://noimage.icons.test/</link></image>\n'), X),
        ('/', home([('icon', '/small.png')]), H), ('/small.png', SMALL, P)]), needs=A,
        description='When the feed\'s own image cannot be downloaded, the site\'s icon links.')
    s.add('icons', 'feed', 'rss-image-relative', case('relimage.icons.test', [
        ('/feed.xml', feed_doc('relimage.icons.test', '<image><url>media/logo.png</url><title>Logo</title>'
                                                       '<link>http://relimage.icons.test/</link></image>\n'), X),
        ('/media/logo.png', OTHER, P)]), needs=A, description='A relative feed image is resolved against the site.')
    s.add('icons', 'fallback', 'site-page-missing', case('nosite.icons.test', [
        ('/news/feed.xml', rss('Icons nosite', 'http://nosite.icons.test/news/', [
            item('Icon entry', 'http://nosite.icons.test/news/1', 'nosite-1', DATE, 'Body')]), X),
        ('/', home([('icon', '/small.png')]), H), ('/small.png', SMALL, P)], feed_path='news/feed.xml'), needs=A,
        description='When the site page cannot be read, the root page is searched.')
    s.add('icons', 'site', 'data-url-svg', case('datasvg.icons.test', [
        ('/feed.xml', feed_doc('datasvg.icons.test'), X),
        ('/', home([('icon', 'data:image/svg+xml;base64,' + base64.b64encode(SVG).decode())]), H)]), needs=A,
        description='An SVG icon given as a data URL.')
    s.add('icons', 'feed', 'json-favicon', case('json.icons.test', [
        ('/feed.json', json_doc('json.icons.test', favicon='/fav.png', icon='/big-icon.png'), 'application/feed+json'),
        ('/', home([]), H), ('/fav.png', SMALL, P), ('/big-icon.png', LARGE, P)], feed_path='feed.json'), needs=A,
        description='A JSON Feed\'s favicon before its icon.')
    s.add('icons', 'feed', 'json-icon', case('jsonicon.icons.test', [
        ('/feed.json', json_doc('jsonicon.icons.test', icon='/big-icon.png'), 'application/feed+json'),
        ('/', home([]), H), ('/big-icon.png', LARGE, P)], feed_path='feed.json'), needs=A,
        description='A JSON Feed\'s icon when it has no favicon.')
    later = s.add('icons', 'refresh', 'subscribe-without', case('later.icons.test', [
        ('/feed.xml', feed_doc('later.icons.test'), X), ('/', home([]), H)], fetches=False), needs=A, requires=[link],
        description='Subscribing to a feed whose site has no icon yet.')
    s.add('icons', 'refresh', 'picked-up', appears_later, needs=A + [later],
          description='A refresh looks for the missing icon again and keeps the one that appeared.')
    s.add('icons', 'shared', 'same-picture', shared, needs=A, description='Feeds with the same picture share an icon.')
