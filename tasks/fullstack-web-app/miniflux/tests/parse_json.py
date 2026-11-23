"""JSON Feed 1.0 and 1.1 parsing: feed fields, item URLs, titles derived from summaries or content, HTML and text
content, dates, authors of feed and items, attachments, tags and languages; and RDF (RSS 1.0) parsing.
Each case is one small feed; the observation is the part of the stored feed and entries the case is about."""
import json

from parsing import build_cases

V11 = 'https://jsonfeed.org/version/1.1'
V10 = 'https://jsonfeed.org/version/1'


def doc(items, version=V11, **feed):
    value = {'version': version, 'title': 'JSON fixture', 'home_page_url': 'http://json.test/site/', **feed,
             'items': items}
    return json.dumps(value, ensure_ascii=False, indent=1)


def item(**fields):
    value = {'id': 'item-1', 'url': 'http://json.test/item', 'date_published': '2025-04-01T12:00:00Z'}
    value.update(fields)
    return {k: v for k, v in value.items() if v is not None}


T = ('title',)
U = ('title', 'url')
D = ('title', 'published_at')
A = ('title', 'author')
C = ('title', 'content')

CASES = [
    ('basic.json', doc([item(title='Basic item', content_html='<p>Basic <b>HTML</b></p>', tags=['b', 'a'])]),
     ('title', 'url', 'published_at', 'content', 'tags'), ('title', 'site_url'), False, 'A JSON Feed 1.1 item.'),
    ('version-1.json', doc([item(title='Old version', content_text='Text')], version=V10), U, ('title',), False,
     'A JSON Feed 1.0 document.'),
    ('title-trim.json', doc([item(title='   Trimmed title   ')]), T, (), False, 'Item titles are trimmed.'),
    ('title-from-summary.json', doc([item(title=None, summary='The summary becomes the title when there is none.',
                                          content_html='<p>Content HTML</p>')]), T, (), False,
     'Without a title, the summary is the title.'),
    ('title-from-text.json', doc([item(title=None, content_text='Only plain text content that also serves as the title '
                                                                'of this item, cut down to size after one hundred '
                                                                'characters.')]), T, (), False,
     'Without title and summary, the text content gives the title.'),
    ('title-from-url.json', doc([item(title=None)]), U, (), False, 'Without any text, the URL is the title.'),
    ('url-external.json', doc([item(title='External', url=None, external_url='http://elsewhere.test/story')]), U, (),
     False, 'The external URL is used when there is no URL.'),
    ('url-relative.json', doc([item(title='Relative', url='/stories/rel')]), U, (), False,
     'A relative item URL is resolved against the home page.'),
    ('content-text.json', doc([item(title='Text', content_text='Text <not> markup\nnew line')]), C, (), False,
     'Text content is escaped.'),
    ('content-html-wins.json', doc([item(title='Both', content_html='<p>HTML wins</p>', content_text='Text loses')]), C,
     (), False, 'HTML content wins over text content.'),
    ('content-summary.json', doc([item(title='Summary', summary='Only <a summary>')]), C, (), False,
     'Without content, the escaped summary.'),
    ('date-modified.json', doc([item(title='Modified', date_published=None, date_modified='2025-04-02T13:00:00+02:00')]),
     D, (), False, 'Without a publication date, the modification date.'),
    ('date-missing.json', doc([item(title='No date', date_published=None)]), D, (), False,
     'An item without dates is dated when it is stored.'),
    ('date-format.json', doc([item(title='Other format', date_published='Tue, 01 Apr 2025 12:00:00 GMT')]), D, (),
     False, 'An RFC 1123 date in a JSON Feed.'),
    ('authors-item.json', doc([item(title='Item authors', authors=[{'name': 'Zoe'}, {'name': 'Abe'}])]), A, (), False,
     'Item authors (1.1).'),
    ('authors-feed.json', doc([item(title='Feed authors')], authors=[{'name': 'Feed Person'}]), A, (), False,
     'Feed authors apply to items.'),
    ('authors-merge.json', doc([item(title='Merged', authors=[{'name': 'Item Person'}], author={'name': 'Legacy'})],
                               authors=[{'name': 'Feed Person'}]), A, (), False,
     'Feed authors, item authors and the 1.0 author are merged.'),
    ('author-legacy.json', doc([item(title='Legacy author', author={'name': 'One Author'})], version=V10), A, (), False,
     'The JSON Feed 1.0 author.'),
    ('attachments.json', doc([item(title='Attachments', attachments=[
        {'url': 'http://media.json.test/a.mp3', 'mime_type': 'audio/mpeg', 'size_in_bytes': 1234},
        {'url': '/media/b.pdf', 'mime_type': 'application/pdf'}])]), ('title', 'enclosures'), (), False,
     'Attachments become enclosures; relative ones are resolved.'),
    ('tags.json', doc([item(title='Tags', tags=['zeta', ' alpha ', 'zeta'])]), ('title', 'tags'), (), False,
     'Tags are trimmed, de-duplicated and sorted.'),
    ('language.json', doc([item(title='Language')], language='pt-BR'), T, ('language',), False, 'The feed language.'),
    ('feed-fields.json', doc([item(title='Fields')], title='  JSON Journal  ', description='The description',
                             feed_url='http://json.test/canonical.json'), (), ('title', 'site_url', 'description'),
     False, 'Feed title, home page and description.'),
    ('feed-no-title.json', doc([item(title='Untitled feed')], title=''), (), ('title',), False,
     'A feed without a title is titled with its home page.'),
    ('feed-no-home.json', doc([item(title='No home')], home_page_url=None), ('title', 'url'), ('site_url',), False,
     'A feed without a home page.'),
    ('duplicate-ids.json', doc([item(title='First copy', id='same', url='http://json.test/one'),
                                item(title='Second copy', id='same', url='http://json.test/two')]), U, (), True,
     'Two items with the same id.'),
    ('numeric-id.json', '{"version": "https://jsonfeed.org/version/1.1", "title": "Numeric ids", "items": [{"id": 42, '
                        '"url": "http://json.test/num", "title": "Numeric id", "date_published": "2025-04-03T00:00:00Z"}]}',
     U, (), False, 'An item with a numeric id.'),
    ('empty-items.json', doc([]), (), ('title',), False, 'A feed without items.'),
    ('language-item.json', doc([item(title='Item language', language='fr-CA'),
                                item(title='Feed language', id='item-2', url='http://json.test/item-2')],
                               language='en-US'), ('title', 'language'), (), True,
     'An item language wins over the feed language, which items without one inherit.'),
    ('url-both.json', doc([item(title='Both URLs', url='http://json.test/own', external_url='http://elsewhere.test/x')]),
     U, (), False, 'The item URL wins over the external URL.'),
    ('title-from-html-summary.json', doc([item(title=None, summary='<p>A <b>summary</b> with markup that is long enough '
                                                                  'to be cut: it keeps going well past one hundred '
                                                                  'characters of text.</p>')]), T, (), False,
     'A title made from an HTML summary is plain text cut to size.'),
    ('date-invalid-published.json', doc([item(title='Bad published', date_published='not a date',
                                              date_modified='2025-04-05T06:07:08Z')]), D, (), False,
     'An unreadable publication date falls back to the modification date.'),
    ('no-id-same-url.json', doc([item(title='First without id', id=None, url='http://json.test/same'),
                                 item(title='Second without id', id=None, url='http://json.test/same')]), U, (), True,
     'Items without ids are identified by their URL.'),
    ('home-relative.json', doc([item(title='Relative home', url='story')], home_page_url='/home/'), U, ('site_url',),
     False, 'A relative home page is resolved against the feed address, and item URLs against the home page.'),
    ('attachment-no-url.json', doc([item(title='Partial attachments', attachments=[
        {'mime_type': 'audio/mpeg', 'size_in_bytes': 10},
        {'url': 'http://media.json.test/c.ogg', 'mime_type': 'audio/ogg', 'size_in_bytes': 20}])]),
     ('title', 'enclosures'), (), False, 'Attachments without a URL are skipped.'),
    ('tags-blank.json', doc([item(title='Blank tags', tags=['', '  ', 'kept'])]), ('title', 'tags'), (), False,
     'Blank tags are dropped.'),
    ('content-blank-html.json', doc([item(title='Blank HTML', content_html='   ', content_text='Text fallback')]), C, (),
     False, 'Blank HTML content falls back to the text content.'),
]

RDF = ('<?xml version="1.0" encoding="utf-8"?>\n<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
       'xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
       'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n<channel rdf:about="http://rdf.test/site/">'
       '<title>{title}</title><link>http://rdf.test/site/</link><description>RDF channel</description></channel>\n'
       '{items}</rdf:RDF>\n')


def rdf(items, title='RDF fixture'):
    return RDF.format(title=title, items=items)


def ri(body, about='http://rdf.test/item'):
    return f'<item rdf:about="{about}">{body}</item>\n'


RDF_CASES = [
    ('basic.rdf', rdf(ri('<title>RDF item</title><link>http://rdf.test/item</link><description>RDF &lt;b&gt;bold'
                         '&lt;/b&gt; text</description><dc:date>2025-05-01T10:00:00Z</dc:date><dc:creator>Rae Dee'
                         '</dc:creator><dc:subject>semantic</dc:subject>')),
     ('title', 'url', 'published_at', 'author', 'content', 'tags'), ('title', 'site_url'), False, 'An RSS 1.0 item.'),
    ('content-encoded.rdf', rdf(ri('<title>Encoded</title><link>http://rdf.test/enc</link><description>Short'
                                   '</description><content:encoded><![CDATA[<p>Full RDF body</p>]]></content:encoded>'
                                   '<dc:date>2025-05-02T10:00:00Z</dc:date>')), ('title', 'content'), (), False,
     'content:encoded in an RDF item.'),
    ('no-link.rdf', rdf(ri('<title>About only</title><dc:date>2025-05-03T10:00:00Z</dc:date>',
                           about='http://rdf.test/about-url')), ('title', 'url'), (), False,
     'An RDF item without a link.'),
    ('no-date.rdf', rdf(ri('<title>Undated</title><link>http://rdf.test/undated</link>')), ('title', 'published_at'),
     (), False, 'An RDF item without a date.'),
    ('title-entities.rdf', rdf(ri('<title>R &amp;amp; D</title><link>http://rdf.test/rd</link>'
                                  '<dc:date>2025-05-04T10:00:00Z</dc:date>'), title='Research &amp; Development'),
     ('title',), ('title',), False, 'Escaped titles in an RDF document.'),
    ('relative-link.rdf', rdf(ri('<title>Relative</title><link>/rdf/relative</link><dc:date>2025-05-05T10:00:00Z'
                                 '</dc:date>')), ('title', 'url'), (), False, 'A relative RDF item link.'),
    ('dc-title.rdf', rdf(ri('<dc:title>Dublin Core title</dc:title><link>http://rdf.test/dc</link>'
                            '<dc:date>2025-05-06T10:00:00Z</dc:date>')), ('title',), (), False,
     'An RDF item titled only by dc:title.'),
    ('channel-creator.rdf', RDF.replace('<description>RDF channel</description>',
                                        '<description>RDF channel</description><dc:creator>Channel Crew</dc:creator>'
                                        ).format(title='Crew', items=ri(
        '<title>Crew item</title><link>http://rdf.test/crew</link><dc:date>2025-05-07T10:00:00Z</dc:date>') + ri(
        '<title>Own creator</title><link>http://rdf.test/own</link><dc:date>2025-05-08T10:00:00Z</dc:date>'
        '<dc:creator>Solo &lt;b&gt;Writer&lt;/b&gt;</dc:creator>', about='http://rdf.test/own')),
     ('title', 'author'), (), True, 'The channel creator applies to items without one; markup is removed.'),
    ('dc-language.rdf', RDF.replace('<description>RDF channel</description>',
                                    '<description>RDF channel</description><dc:language>de-DE</dc:language>'
                                    ).format(title='Sprachen', items=ri(
        '<title>Channel language</title><link>http://rdf.test/de</link><dc:date>2025-05-09T10:00:00Z</dc:date>') + ri(
        '<title>Item language</title><link>http://rdf.test/fr</link><dc:date>2025-05-10T10:00:00Z</dc:date>'
        '<dc:language>fr-FR</dc:language>', about='http://rdf.test/fr')),
     ('title', 'language'), ('language',), True, 'Channel and item languages of an RDF document.'),
    ('channel-title-markup.rdf', rdf(ri('<title>Plain</title><link>http://rdf.test/plain</link>'
                                        '<dc:date>2025-05-11T10:00:00Z</dc:date>'),
                                     title='&lt;b&gt;Bold&lt;/b&gt; channel'), (), ('title',), False,
     'Markup in an RDF channel title is removed.'),
    ('same-link.rdf', rdf(ri('<title>Copy one</title><link>http://rdf.test/same</link><dc:date>2025-05-12T10:00:00Z'
                             '</dc:date>', about='http://rdf.test/a') +
                          ri('<title>Copy two</title><link>http://rdf.test/same</link><dc:date>2025-05-13T10:00:00Z'
                             '</dc:date>', about='http://rdf.test/b')), ('title', 'url'), (), True,
     'RDF items are identified by their link.'),
    ('date-offset.rdf', rdf(ri('<title>Offset date</title><link>http://rdf.test/offset</link>'
                               '<dc:date>2025-05-14T10:00:00+05:30</dc:date>')), ('title', 'published_at'), (), False,
     'A Dublin Core date with a time zone offset.'),
]


def build(s):
    build_cases(s, 'json.test', CASES, 'application/feed+json')
    # A document the product cannot read counts with one that it reads.
    s.bind(f'{s.prefix}api.parse.numeric-id.subscribe', f'{s.prefix}api.parse.basic.subscribe')


def build_rdf(s):
    build_cases(s, 'rdf.test', RDF_CASES, 'application/rdf+xml')
