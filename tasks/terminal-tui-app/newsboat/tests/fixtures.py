"""Feed documents and home-directory fixtures for the Newsboat episodes.

Every feed is a local file below ~/feeds, subscribed with a relative file:// URL, and every article carries a
fixed publication date, so listings, dates and the cache are deterministic. Titles are unique across a fixture so
that a listed row can be identified by its title alone.
"""
from __future__ import annotations

from xml.sax.saxutils import escape


def esc(text):
    return escape(text, {'"': '&quot;'})


def item(title, guid, date='Mon, 01 Jan 2024 10:00:00 +0000', body=None, *, link=None, author=None,
         creator=None, enclosure=None, extra=''):
    return dict(title=title, guid=guid, date=date, body=body if body is not None else f'Text of {title}.',
                link=link or f'http://example.com/{guid}', author=author, creator=creator, enclosure=enclosure,
                extra=extra)


def rss(title, items, *, link='http://example.com/', description=None, extra='', version='2.0'):
    """An RSS 2.0 document; item bodies are HTML (escaped into <description>)."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n',
           f'<rss version="{version}" xmlns:dc="http://purl.org/dc/elements/1.1/" '
           'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n<channel>\n',
           f'<title>{esc(title)}</title>\n<link>{esc(link)}</link>\n',
           f'<description>{esc(description if description is not None else title + " description")}</description>\n',
           extra]
    for it in items:
        out.append('<item>\n')
        if it['title'] is not None:
            out.append(f'<title>{esc(it["title"])}</title>\n')
        if it['link']:
            out.append(f'<link>{esc(it["link"])}</link>\n')
        if it['guid']:
            out.append(f'<guid>{esc(it["guid"])}</guid>\n')
        if it['date']:
            out.append(f'<pubDate>{it["date"]}</pubDate>\n')
        if it['author']:
            out.append(f'<author>{esc(it["author"])}</author>\n')
        if it['creator']:
            out.append(f'<dc:creator>{esc(it["creator"])}</dc:creator>\n')
        if it['body'] is not None:
            out.append(f'<description>{esc(it["body"])}</description>\n')
        if it['enclosure']:
            url, kind = it['enclosure']
            out.append(f'<enclosure url="{esc(url)}" type="{esc(kind)}" length="1000"/>\n')
        out.append(it['extra'])
        out.append('</item>\n')
    out.append('</channel>\n</rss>\n')
    return ''.join(out)


def atom(title, entries, *, link='http://example.org/', extra=''):
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n',
           f'<title>{esc(title)}</title>\n<link href="{esc(link)}"/>\n<id>urn:feed:{esc(title)}</id>\n'
           '<updated>2024-01-01T00:00:00Z</updated>\n', extra]
    for e in entries:
        out.append('<entry>\n')
        out.append(f'<title>{esc(e["title"])}</title>\n<id>{esc(e["guid"])}</id>\n')
        out.append(f'<link href="{esc(e["link"])}"/>\n')
        if e['date']:
            out.append(f'<updated>{e["date"]}</updated>\n')
        if e['author']:
            out.append(f'<author><name>{esc(e["author"])}</name></author>\n')
        if e['body'] is not None:
            out.append(f'<content type="html">{esc(e["body"])}</content>\n')
        out.append(e['extra'])
        out.append('</entry>\n')
    out.append('</feed>\n')
    return ''.join(out)


def day(n, hour=10):
    """An RFC 822 date in January 2024 (n = 1..31)."""
    names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    return f'{names[(n - 1) % 7]}, {n:02d} Jan 2024 {hour:02d}:00:00 +0000'


def home(urls, feeds, config=None, **files):
    """A place payload: the urls file, feed documents below ~/feeds, an optional config and other files."""
    out = {'.newsboat/urls': urls if urls.endswith('\n') else urls + '\n'}
    for name, text in feeds.items():
        out['feeds/' + name] = text
    if config is not None:
        out['.newsboat/config'] = config if config.endswith('\n') else config + '\n'
    out.update(files)
    return out


# -- the reading library: three feeds with tags, authors, enclosures and distinct dates --------------------------
TECH = rss('Tech Daily', [
    item('Kernel 6.9 released', 't1', day(3), '<p>The <b>kernel</b> team released version 6.9.</p>',
         author='linus@example.com (Linus)'),
    item('Rust in the kernel', 't2', day(5), '<p>Rust support grows.</p><p>See <a href="http://rust.example/">the site</a>.</p>',
         author='miguel@example.com (Miguel)'),
    item('Compiler news', 't3', day(7), '<p>GCC and Clang updates.</p>', author='linus@example.com (Linus)'),
    item('Filesystem benchmarks', 't4', day(9), '<p>ext4 against btrfs.</p>', author='ted@example.com (Ted)'),
], link='http://tech.example/', description='News about computing')
FOOD = rss('Food Notes', [
    item('Bread at home', 'f1', day(2), '<p>Flour, water, salt.</p>', creator='Julia'),
    item('Spicy noodles', 'f2', day(4), '<p>Chili oil and noodles.</p>', creator='Ken'),
    item('Winter soup', 'f3', day(6), '<p>Lentils and carrots.</p>', creator='Julia'),
], link='http://food.example/', description='Cooking and recipes')
CAST = rss('Audio Cast', [
    item('Episode 1: Origins', 'c1', day(1), '<p>The first episode.</p>',
         enclosure=('http://cast.example/ep1.mp3', 'audio/mpeg')),
    item('Episode 2: Growth', 'c2', day(8), '<p>The second episode.</p>',
         enclosure=('http://cast.example/ep2.mp3', 'audio/mpeg')),
], link='http://cast.example/', description='A podcast')
LIB_URLS = ('file://feeds/tech.xml tech news\n'
            'file://feeds/food.xml food\n'
            'file://feeds/cast.xml audio news\n')
LIB_FEEDS = {'tech.xml': TECH, 'food.xml': FOOD, 'cast.xml': CAST}
FEED_TITLES = ['Tech Daily', 'Food Notes', 'Audio Cast']
TECH_TITLES = ['Kernel 6.9 released', 'Rust in the kernel', 'Compiler news', 'Filesystem benchmarks']
FOOD_TITLES = ['Bread at home', 'Spicy noodles', 'Winter soup']
CAST_TITLES = ['Episode 1: Origins', 'Episode 2: Growth']
ALL_TITLES = TECH_TITLES + FOOD_TITLES + CAST_TITLES
GUIDS = {'Kernel 6.9 released': 't1', 'Rust in the kernel': 't2', 'Compiler news': 't3',
         'Filesystem benchmarks': 't4', 'Bread at home': 'f1', 'Spicy noodles': 'f2', 'Winter soup': 'f3',
         'Episode 1: Origins': 'c1', 'Episode 2: Growth': 'c2'}
FEEDURL = {'Tech Daily': 'file://feeds/tech.xml', 'Food Notes': 'file://feeds/food.xml',
           'Audio Cast': 'file://feeds/cast.xml'}


def library(config=None, urls=LIB_URLS, **files):
    return home(urls, LIB_FEEDS, config, **files)
