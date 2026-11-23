"""Feed documents and web pages of the local web, and the setup steps that publish and subscribe them.

Every document is built here from fixed data (fixed publication dates in 2024 and 2025), so the product
reads exactly the same bytes in the reference and in every candidate."""
import base64
import json
import zlib
import struct
from xml.sax.saxutils import escape

from harness import Ref

RSS_TYPE = 'application/rss+xml'
ATOM_TYPE = 'application/atom+xml'
JSON_TYPE = 'application/feed+json'
HTML_TYPE = 'text/html; charset=utf-8'


def png(width, height, rgb):
    """A small solid-colour PNG."""
    raw = b''.join(b'\x00' + bytes(rgb) * width for _ in range(height))

    def chunk(kind, data):
        body = struct.pack('>I', len(data)) + kind + data
        return body + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def rss(title, link, items, description='Fixture feed', extra='', namespaces='', declaration=True,
        encoding='UTF-8'):
    head = f'<?xml version="1.0" encoding="{encoding}"?>\n' if declaration else ''
    return (f'{head}<rss version="2.0"{namespaces}>\n<channel>\n<title>{title}</title>\n<link>{link}</link>\n'
            f'<description>{description}</description>\n{extra}{"".join(items)}</channel>\n</rss>\n')


def item(title=None, link=None, guid=None, date=None, description=None, extra=''):
    parts = ['<item>']
    if title is not None:
        parts.append(f'<title>{title}</title>')
    if link is not None:
        parts.append(f'<link>{link}</link>')
    if guid is not None:
        parts.append(f'<guid>{guid}</guid>')
    if date is not None:
        parts.append(f'<pubDate>{date}</pubDate>')
    if description is not None:
        parts.append(f'<description>{description}</description>')
    parts.append(extra)
    parts.append('</item>\n')
    return ''.join(parts)


def html_text(value):
    """HTML markup as the escaped text of an XML element."""
    return escape(value)


def atom(title, link, entries, feed_id='urn:fixture:feed', updated='2025-01-01T00:00:00Z', extra='',
         namespaces=''):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"{namespaces}>\n'
            f'<title>{title}</title>\n<link href="{link}"/>\n<id>{feed_id}</id>\n<updated>{updated}</updated>\n'
            f'{extra}{"".join(entries)}</feed>\n')


def entry(title=None, link=None, entry_id=None, updated=None, published=None, content=None, summary=None,
          extra=''):
    parts = ['<entry>']
    if title is not None:
        parts.append(f'<title>{title}</title>')
    if link is not None:
        parts.append(f'<link href="{link}"/>')
    if entry_id is not None:
        parts.append(f'<id>{entry_id}</id>')
    if published is not None:
        parts.append(f'<published>{published}</published>')
    if updated is not None:
        parts.append(f'<updated>{updated}</updated>')
    if summary is not None:
        parts.append(f'<summary>{summary}</summary>')
    if content is not None:
        parts.append(f'<content type="html">{escape(content)}</content>')
    parts.append(extra)
    parts.append('</entry>\n')
    return ''.join(parts)


def jsonfeed(title, home, items, version='https://jsonfeed.org/version/1.1', **extra):
    return json.dumps({'version': version, 'title': title, 'home_page_url': home, **extra, 'items': items},
                      ensure_ascii=False, indent=1)


def page(title, body, head=''):
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<title>{title}</title>\n{head}</head>\n'
            f'<body>\n{body}\n</body>\n</html>\n')


# -- setup steps ----------------------------------------------------------------------------------------------
def publish(url, body, content_type=None, status=200, headers=None, auth=None):
    """A setup action publishing one resource of the local web."""
    def action(c):
        c.web_put(url, body, content_type, status, headers, auth)
    return action


def publish_all(resources):
    def action(c):
        for spec in resources:
            url, body = spec[0], spec[1]
            c.web_put(url, body, *spec[2:])
    return action


def subscribe(s, group, step, url, save, category=None, actor='alice', **options):
    """A setup subscription (POST /v1/feeds, any success status); the feed id is saved under `save`."""
    body = {'feed_url': url, **options}
    body['category_id'] = Ref(category, 'id') if category else Ref('category-' + actor, 'id')
    return s.setup(group, step, 'POST', 'feeds', body=body, actor=actor, save=save)


def default_category(s, group, actor='alice'):
    """Save the account's first category (the default one) as category-<actor>."""
    def action(c):
        r, payload = c.request('GET', 'categories', actor)
        assert r.status_code == 200 and isinstance(payload, list) and payload, 'the account has no category'
        c.state['category-' + actor] = payload[0]
    return s.fixture(group, 'category-' + actor, action)


def entries_of(c, feed_key, actor='alice', **params):
    """Entries of a saved feed (setup helper), oldest first."""
    r, payload = c.request('GET', f"feeds/{c.state[feed_key]['feed_id']}/entries", actor,
                           params={'order': 'published_at', 'direction': 'asc', 'limit': 500, **params})
    assert r.status_code == 200 and isinstance(payload, dict), 'feed entries unavailable'
    return payload['entries']


def b64(data):
    return base64.b64encode(data if isinstance(data, bytes) else data.encode()).decode()
