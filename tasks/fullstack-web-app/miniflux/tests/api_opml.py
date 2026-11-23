"""OPML through the REST API: export of the account's subscriptions grouped by category (with the product's own
feed-setting attributes), import of categories, nested outlines and feed settings, skipped duplicates, invalid
documents and settings, and a round trip into another account."""
import xml.etree.ElementTree as ET

import fixtures as fx
from fixtures import item, rss
from harness import CREDS, Ref, pathref, pick, unordered

FEED = rss('OPML source', 'http://opml.test/site/', [
    item('OPML entry', 'http://opml.test/entry', 'opml-1', 'Mon, 06 Jan 2025 10:00:00 GMT', 'Body.')])
NS = 'xmlns:miniflux="https://miniflux.app/opml"'


def opml(outlines, extra_ns=NS):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0" {extra_ns}><head><title>Import</title></head>'
            f'<body>{outlines}</body></opml>\n')


def outline(title, url, site='http://opml.test/site/', attrs=''):
    return f'<outline type="rss" title="{title}" text="{title}" xmlUrl="{url}" htmlUrl="{site}" {attrs}/>'


IMPORT = opml('<outline text="Imported news">' + outline('Feed one', 'http://opml.test/one.xml') +
              outline('Feed two', 'http://opml.test/two.xml') + '</outline>' +
              '<outline text="Second group" title="Second group">' + outline('Feed three', 'http://opml.test/three.xml') +
              '</outline>' + outline('Top level feed', 'http://opml.test/top.xml'))
SETTINGS = opml(outline('Configured feed', 'http://opml.test/configured.xml', attrs=(
    'miniflux:userAgent="OPML Agent/1.0" miniflux:crawler="true" miniflux:rewriteRules="nl2br" '
    'miniflux:blocklistRules="(?i)ads" miniflux:keepFilterEntryRules="EntryTitle=OPML" miniflux:disabled="true" '
    'miniflux:hideGlobally="true" miniflux:ignoreEntryUpdates="true"')))
NESTED = opml('<outline text="Outer"><outline text="Inner">' + outline('Nested feed', 'http://opml.test/nested.xml') +
              '</outline></outline>')
NO_TITLE = opml('<outline type="rss" xmlUrl="http://opml.test/untitled.xml"/>')
DUPLICATE = opml(outline('Feed one again', 'http://opml.test/one.xml') + outline('Feed four', 'http://opml.test/four.xml'))
BAD_SETTING = opml(outline('Bad setting', 'http://opml.test/bad.xml', attrs='miniflux:crawler="maybe"'))
BAD_RULE = opml(outline('Bad rule', 'http://opml.test/bad-rule.xml', attrs='miniflux:rewriteRules="no_such_rule"'))
NOT_XML = 'this is not an OPML document'


def tree(text):
    """An OPML document as head fields and nested outlines with their attributes; the creation date is a clock."""
    root = ET.fromstring(text.encode() if isinstance(text, str) else text)

    def name(tag):
        return tag.replace('{https://miniflux.app/opml}', 'miniflux:')

    def walk(node):
        out = {name(k): v for k, v in sorted(node.attrib.items())}
        children = [walk(child) for child in node if child.tag == 'outline']
        if children:
            out['outlines'] = children
        return out
    head = root.find('head')
    fields = {}
    for child in (head if head is not None else []):
        fields[child.tag] = '[time]' if child.tag in ('dateCreated', 'dateModified') else (child.text or '')
    body = root.find('body')
    return {'version': root.get('version'), 'head': fields,
            'outlines': [walk(x) for x in (body if body is not None else []) if x.tag == 'outline']}


def export(actor='alice'):
    def action(c):
        r, p = c.request('GET', 'export', actor)
        if r.status_code >= 400:
            return c.observe(r, p)
        try:
            document = tree(r.content)
        except ET.ParseError as exc:
            raise AssertionError('the export is not XML: ' + str(exc)) from None
        return {'status': r.status_code, 'content_type': (r.headers.get('content-type') or '').split(';')[0],
                'opml': document}
    return action


def feeds_view(payload):
    assert isinstance(payload, list), 'expected the feed list'
    return unordered([{k: x[k] for k in ('title', 'feed_url', 'site_url')} | {'category': x['category']['title']}
                      for x in payload])


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    resources = [(f'http://opml.test/{name}.xml', FEED, fx.RSS_TYPE) for name in (
        'one', 'two', 'three', 'top', 'configured', 'nested', 'untitled', 'four', 'bad', 'bad-rule', 'mine-a', 'mine-b',
        'mine-c')]
    s.fixture('web', 'publish', fx.publish_all(resources))
    s.setup('library', 'category', 'POST', 'categories', body={'title': 'Zeta shelf'}, save='zeta')
    fx.subscribe(s, 'library', 'mine-a', 'http://opml.test/mine-a.xml', 'mine-a')
    fx.subscribe(s, 'library', 'mine-b', 'http://opml.test/mine-b.xml', 'mine-b', category='zeta',
                 user_agent='Exported Agent', crawler=True, scraper_rules='article', blocklist_rules='spam')
    fx.subscribe(s, 'library', 'mine-c', 'http://opml.test/mine-c.xml', 'mine-c', category='zeta')
    s.setup('library', 'rename-c', 'PUT', pathref('feeds/{id}', id=Ref('mine-c', 'feed_id')),
            body={'title': 'Another & feed'})
    L = ['fx:accounts', 'fx:web', 'fx:library']

    exported = s.add('opml', 'export', 'subscriptions', export(), needs=L,
                     description='Exporting the subscriptions as OPML, grouped by category, with feed settings.')
    s.add('opml', 'export', 'empty', export('carol'), needs=L, requires=[exported],
          description='The OPML export of an account without subscriptions.')
    s.add('opml', 'export', 'anonymous', export(None), requires=[exported], description='Exporting needs credentials.')

    imported = s.api('opml', 'import', 'categories', 'POST', 'import', actor='bob', raw=IMPORT,
                     content_type='text/x-opml', needs=L, description='Importing an OPML document.')
    s.api('opml', 'import', 'categories-feeds', 'GET', 'feeds', actor='bob', needs=L, requires=[imported],
          view=feeds_view, description='The imported feeds with their categories.')
    s.api('opml', 'import', 'categories-list', 'GET', 'categories', actor='bob', needs=L, requires=[imported],
          view=lambda p: unordered(sorted(x['title'] for x in p)), description='The categories created by the import.')
    s.add('opml', 'import', 'no-entries', imported_entries, needs=L, requires=[imported],
          description='Imported feeds are not fetched during the import.')
    s.api('opml', 'import', 'settings', 'POST', 'import', actor='bob', raw=SETTINGS, content_type='text/x-opml',
          needs=L, description='Importing a feed with the product\'s setting attributes.')
    s.add('opml', 'import', 'settings-feed', feed_by_url('http://opml.test/configured.xml', (
        'user_agent', 'crawler', 'rewrite_rules', 'blocklist_rules', 'keep_filter_entry_rules', 'disabled',
        'hide_globally', 'ignore_entry_updates')), needs=L, requires=[imported],
        description='The imported feed carries the settings of the document.')
    s.api('opml', 'import', 'nested', 'POST', 'import', actor='bob', raw=NESTED, content_type='text/x-opml', needs=L,
          description='Importing nested outlines.')
    s.add('opml', 'import', 'nested-feed', feed_by_url('http://opml.test/nested.xml', ('title', 'category.title')),
          needs=L, requires=[imported], description='The category of a feed in nested outlines.')
    s.api('opml', 'import', 'untitled', 'POST', 'import', actor='bob', raw=NO_TITLE, content_type='text/x-opml',
          needs=L, description='Importing an outline without title or text.')
    s.add('opml', 'import', 'untitled-feed', feed_by_url('http://opml.test/untitled.xml', ('title', 'site_url',
                                                                                          'category.title')),
          needs=L, requires=[imported], description='The title of a feed imported without one.')
    s.api('opml', 'import', 'duplicate', 'POST', 'import', actor='bob', raw=DUPLICATE, content_type='text/x-opml',
          needs=L, description='Importing a document with an already subscribed feed.')
    s.api('opml', 'import', 'duplicate-feeds', 'GET', 'feeds', actor='bob', needs=L, requires=[imported],
          view=lambda p: sorted(x['feed_url'] for x in p),
          description='The existing subscription is kept once and the new one added.')
    s.api('opml', 'import', 'bad-setting', 'POST', 'import', actor='bob', raw=BAD_SETTING, content_type='text/x-opml',
          needs=L, requires=[imported], description='An invalid boolean setting attribute is refused.')
    s.api('opml', 'import', 'bad-rule', 'POST', 'import', actor='bob', raw=BAD_RULE, content_type='text/x-opml',
          needs=L, requires=[imported], description='An invalid rewrite rule in a document is refused.')
    s.api('opml', 'import', 'not-xml', 'POST', 'import', actor='bob', raw=NOT_XML, content_type='text/x-opml',
          needs=L, requires=[imported], description='A body that is not OPML is refused.')
    s.api('opml', 'import', 'empty-body', 'POST', 'import', actor='bob', raw='', content_type='text/x-opml', needs=L,
          requires=[imported], description='An empty body is refused.')
    s.add('opml', 'roundtrip', 'into-carol', roundtrip, needs=L, requires=[exported],
          description='An exported document imported into another account recreates its subscriptions.')


def imported_entries(c):
    r, feeds = c.request('GET', 'feeds', 'bob')
    feed = next((f for f in feeds if f['feed_url'] == 'http://opml.test/one.xml'), None) if r.status_code == 200 else None
    assert feed, 'the imported feed is missing'
    rr, listing = c.request('GET', f"feeds/{feed['id']}/entries", 'bob')
    return {'status': rr.status_code, 'total': listing.get('total') if isinstance(listing, dict) else listing}


def feed_by_url(url, fields):
    def action(c):
        r, feeds = c.request('GET', 'feeds', 'bob')
        assert r.status_code == 200, 'feed list unavailable'
        feed = next((f for f in feeds if f['feed_url'] == url), None)
        assert feed, 'the imported feed is missing: ' + url
        return {'feed': c.norm.clean(pick(*fields)(feed), 'feed')}
    return action


def roundtrip(c):
    r, _ = c.request('GET', 'export', 'alice')
    assert r.status_code == 200, 'export unavailable'
    rr, p = c.request('POST', 'import', 'carol', raw=r.content, content_type='text/x-opml')
    if rr.status_code >= 400:
        return c.observe(rr, p)
    r3, feeds = c.request('GET', 'feeds', 'carol')
    return {'status': rr.status_code, 'feeds': feeds_view(feeds) if r3.status_code == 200 else r3.status_code,
            'settings': sorted([f['feed_url'], f['user_agent'], f['crawler'], f['scraper_rules'], f['blocklist_rules']]
                               for f in feeds) if r3.status_code == 200 else None}
