"""Shared steps of the feed-parsing episodes: every case is one small feed document in the local web; the
scored step subscribes to it and observes the stored feed and entries through the public API."""
import fixtures as fx
from harness import CREDS, unordered

ENTRY = ('title', 'url', 'published_at')


def project(entry, fields):
    out = {}
    for name in fields:
        assert name in entry, 'entry field missing: ' + name
        value = entry[name]
        if name == 'enclosures':
            value = [{k: x.get(k) for k in ('url', 'mime_type', 'size')} for x in (value or [])]
        out[name] = value
    return out


def parsed(url, entry_fields=ENTRY, feed_fields=(), many=False, options=None):
    """Subscribe to one fixture document and observe the requested feed and entry fields. With many, the
    entries compare as a multiset (their storage order is another case's business)."""
    def action(c):
        r, p = c.request('POST', 'feeds', body={'feed_url': url, 'category_id': c.state['category-alice']['id'],
                                                 **(options or {})})
        if r.status_code >= 400:
            return c.observe(r, p)
        assert isinstance(p, dict) and 'feed_id' in p, 'the subscription answer lacks feed_id'
        out = {'status': r.status_code}
        if feed_fields:
            rr, feed = c.request('GET', f"feeds/{p['feed_id']}")
            assert rr.status_code == 200, 'the subscribed feed cannot be read'
            out['feed'] = c.norm.clean(project(feed, feed_fields), 'feed')
        if entry_fields:
            rr, listing = c.request('GET', f"feeds/{p['feed_id']}/entries",
                                    params={'order': 'published_at', 'direction': 'asc', 'limit': 200})
            assert rr.status_code == 200 and isinstance(listing, dict), 'the feed entries cannot be read'
            entries = [c.norm.clean(project(e, entry_fields), 'entry') for e in listing.get('entries') or []]
            out['entries'] = unordered(entries) if many else entries
        return out
    return action


def build_cases(s, host, cases, documents_type, options=None):
    """cases: (name, document, entry_fields, feed_fields, many, description[, content_type]) tuples; options maps
    a case name to the subscription options of its feed."""
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    resources = []
    for case in cases:
        name, document = case[0], case[1]
        kind = case[6] if len(case) > 6 else documents_type
        body = document if isinstance(document, (bytes, str)) else document[0]
        resources.append((f'http://{host}/{name}', body, kind))
    s.fixture('web', 'publish', fx.publish_all(resources))
    for name, _, entry_fields, feed_fields, many, description, *_ in cases:
        s.add('parse', name.rsplit('.', 1)[0], 'subscribe', parsed(f'http://{host}/{name}', entry_fields, feed_fields,
                                                                   many, (options or {}).get(name)),
              needs=['fx:accounts', 'fx:web'], description=description)
