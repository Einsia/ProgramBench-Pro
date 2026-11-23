"""Atom 1.0 and 0.3 parsing: text constructs (text, html, xhtml), links and xml:base, ids, published and updated
dates, authors, summaries and content, categories, replies links, enclosures and Media RSS, feed-level fields.
Each case is one small feed; the observation is the part of the stored feed and entries the case is about."""
from parsing import build_cases

NS = ' xmlns:media="http://search.yahoo.com/mrss/" xmlns:thr="http://purl.org/syndication/thread/1.0"'
UPDATED = '2025-03-01T09:00:00Z'


def doc(entries, head='', title='Atom fixture', link='<link href="http://atom.test/site/"/>', attrs=''):
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"{NS}{attrs}>\n'
            f'<title>{title}</title>\n{link}\n<id>urn:atom:fixture</id>\n<updated>{UPDATED}</updated>\n{head}'
            f'{entries}</feed>\n')


def en(body, link='http://atom.test/entry', entry_id='urn:atom:entry', updated=UPDATED):
    parts = ['<entry>']
    if link:
        parts.append(f'<link href="{link}"/>')
    if entry_id:
        parts.append(f'<id>{entry_id}</id>')
    if updated:
        parts.append(f'<updated>{updated}</updated>')
    parts.append(body + '</entry>\n')
    return ''.join(parts)


def titled(title, **kw):
    return en(f'<title>{title}</title><content type="html">&lt;p&gt;Body.&lt;/p&gt;</content>', **kw)


T = ('title',)
U = ('title', 'url')
D = ('title', 'published_at')
A = ('title', 'author')
C = ('title', 'content')
E = ('title', 'enclosures')
G = ('title', 'tags')

CASES = [
    # Titles.
    ('title-text.xml', doc(titled('Plain &amp; simple &lt;tag&gt;')), T, (), False, 'A text title with escapes.'),
    ('title-html.xml', doc(en('<title type="html">&lt;b&gt;Bold&lt;/b&gt; &amp;amp; title</title>')), T, (), False,
     'An html title.'),
    ('title-xhtml.xml', doc(en('<title type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">XHTML <em>title</em>'
                               '</div></title>')), T, (), False, 'An xhtml title.'),
    ('title-cdata.xml', doc(en('<title><![CDATA[CDATA & title]]></title>')), T, (), False, 'A CDATA title.'),
    ('title-missing.xml', doc(en('<content type="html">&lt;p&gt;Untitled Atom entry whose content provides the title of '
                                 'the entry, cut after one hundred characters of visible text in all.&lt;/p&gt;</content>')),
     T, (), False, 'An entry without a title takes the start of its content.'),
    ('title-whitespace.xml', doc(titled('\n  Atom   spaced  \n')), T, (), False, 'Whitespace around an Atom title.'),
    # Links.
    ('link-alternate.xml', doc(en('<title>Alternates</title><link rel="self" href="http://atom.test/self"/>'
                                  '<link rel="alternate" type="text/html" href="http://atom.test/html-version"/>',
                                  link=None)), U, (), False, 'The alternate link is the entry URL, not the self link.'),
    ('link-no-rel.xml', doc(en('<title>No rel</title>', link='http://atom.test/no-rel')), U, (), False,
     'A link without rel is the entry URL.'),
    ('link-relative.xml', doc(en('<title>Relative</title>', link='/relative/entry')), U, (), False,
     'A relative entry link is resolved against the feed\'s site.'),
    ('link-xml-base.xml', doc(en('<title>Base</title>', link='child/page'), attrs=' xml:base="http://base.atom.test/dir/"'),
     U, (), False, 'A relative entry link with xml:base on the feed.'),
    ('link-id-url.xml', doc(en('<title>Id as URL</title>', link=None, entry_id='http://atom.test/from-id')), U, (),
     False, 'Without a link, an absolute id is the URL.'),
    ('link-id-urn.xml', doc(en('<title>URN id</title>', link=None, entry_id='urn:uuid:1234')), U, (), False,
     'Without a link and with a URN id, the entry points to the site.'),
    ('link-several-alternates.xml', doc(en('<title>Two alternates</title>'
                                           '<link rel="alternate" type="application/pdf" href="http://atom.test/paper.pdf"/>'
                                           '<link rel="alternate" type="text/html" href="http://atom.test/paper.html"/>',
                                           link=None)), U, (), False, 'Several alternate links.'),
    # Dates.
    ('date-published.xml', doc(en('<title>Published</title><published>2025-02-01T08:00:00Z</published>')), D, (),
     False, 'The published date wins over the updated date.'),
    ('date-updated-only.xml', doc(en('<title>Updated only</title>', updated='2025-02-02T08:30:00Z')), D, (), False,
     'Only an updated date.'),
    ('date-offset.xml', doc(en('<title>Offset</title><published>2025-02-03T08:00:00-05:00</published>')), D, (), False,
     'A date with a negative offset.'),
    ('date-fraction.xml', doc(en('<title>Fraction</title><published>2025-02-04T08:00:00.123456Z</published>')), D, (),
     False, 'A date with fractional seconds.'),
    ('date-invalid-published.xml', doc(en('<title>Invalid published</title><published>yesterday</published>',
                                          updated='2025-02-05T08:00:00Z')), D, (), False,
     'An unparsable published date falls back to the updated date.'),
    ('date-missing.xml', doc(en('<title>No date</title>', updated=None)), D, (), False,
     'An entry without dates is dated when it is stored.'),
    # Authors.
    ('author-entry.xml', doc(en('<title>Entry author</title><author><name>Ada Author</name><email>ada@atom.test</email>'
                                '</author>')), A, (), False, 'The entry author name.'),
    ('author-several.xml', doc(en('<title>Two authors</title><author><name>Zed</name></author><author><name>Amy</name>'
                                  '</author>')), A, (), False, 'Several entry authors.'),
    ('author-feed.xml', doc(titled('Feed author'), head='<author><name>Feed Writer</name></author>\n'), A, (), False,
     'Without an entry author, the feed author.'),
    ('author-email-only.xml', doc(en('<title>Email author</title><author><email>only@atom.test</email></author>')), A,
     (), False, 'An author with only an e-mail address.'),
    # Content.
    ('content-html.xml', doc(en('<title>HTML content</title><content type="html">&lt;p&gt;HTML &lt;b&gt;bold&lt;/b&gt;'
                                '&lt;/p&gt;</content>')), C, (), False, 'html content.'),
    ('content-xhtml.xml', doc(en('<title>XHTML content</title><content type="xhtml"><div xmlns="http://www.w3.org/1999/'
                                 'xhtml"><p>XHTML <a href="http://atom.test/x">link</a></p></div></content>')), C, (),
     False, 'xhtml content.'),
    ('content-text.xml', doc(en('<title>Text content</title><content type="text">Text with &lt;angle&gt; brackets'
                                '</content>')), C, (), False, 'text content.'),
    ('content-summary.xml', doc(en('<title>Summary only</title><summary type="html">&lt;p&gt;The summary.&lt;/p&gt;'
                                   '</summary>')), C, (), False, 'Without content, the summary.'),
    ('content-wins.xml', doc(en('<title>Both</title><summary>Short</summary><content type="html">&lt;p&gt;Long content'
                                '&lt;/p&gt;</content>')), C, (), False, 'Content wins over the summary.'),
    ('content-media-description.xml', doc(en('<title>Media only</title><media:group><media:description>A video '
                                             'description</media:description></media:group>')), C, (), False,
     'Without content and summary, the media description.'),
    ('content-relative-base.xml', doc(en('<title>Relative in content</title><content type="html" '
                                         'xml:base="http://atom.test/posts/">&lt;a href="other"&gt;rel&lt;/a&gt;'
                                         '</content>', link='http://atom.test/posts/entry')), C, (), False,
     'Relative URLs in content.'),
    # Categories, replies, enclosures.
    ('tags.xml', doc(en('<title>Categories</title><category term="go"/><category term="web" label="Web"/>'
                        '<category term="go"/>')), G, (), False, 'Categories become tags.'),
    ('tags-feed.xml', doc(titled('Feed categories'), head='<category term="feed-level"/>\n'), G, (), False,
     'Without entry categories, the feed categories.'),
    ('replies.xml', doc(en('<title>Replies</title><link rel="replies" type="text/html" '
                           'href="http://atom.test/entry#comments" thr:count="3"/>')), ('title', 'comments_url'), (),
     False, 'A replies link is the comments URL.'),
    ('enclosure.xml', doc(en('<title>Enclosure</title><link rel="enclosure" type="audio/mpeg" length="777" '
                             'href="http://media.atom.test/e.mp3"/>')), E, (), False, 'An enclosure link.'),
    ('media-thumbnail.xml', doc(en('<title>Thumb</title><media:group><media:thumbnail url="http://media.atom.test/t.jpg"/>'
                                   '<media:content url="http://media.atom.test/v.mp4" type="video/mp4"/></media:group>')),
     E, (), False, 'Media thumbnail and content of a media group.'),
    # Feed-level fields.
    ('feed-fields.xml', doc(titled('Entry'), head='<subtitle>The subtitle</subtitle>\n',
                            link='<link rel="alternate" href="http://atom.test/home/"/><link rel="self" '
                                 'href="http://atom.test/feed-fields.xml"/>'), (), ('title', 'site_url', 'description'),
     False, 'Feed title, site link and subtitle.'),
    ('feed-no-title.xml', doc(titled('Entry'), title=''), (), ('title',), False,
     'A feed without a title is titled with its site URL.'),
    ('feed-html-title.xml', doc(titled('Entry'), title='Tom &amp;amp; Jerry'), (), ('title',), False,
     'An escaped ampersand in a feed title.'),
    ('feed-language.xml', doc(titled('Entry'), attrs=' xml:lang="de-DE"'), ('title',), ('language',), False,
     'The feed language from xml:lang.'),
    # Atom 0.3.
    ('atom03.xml', ('<?xml version="1.0" encoding="utf-8"?>\n<feed version="0.3" xmlns="http://purl.org/atom/ns#">\n'
                    '<title>Atom 0.3 feed</title><link rel="alternate" type="text/html" href="http://atom.test/old/"/>\n'
                    '<modified>2025-03-02T10:00:00Z</modified>\n<entry><title>Old style entry</title>'
                    '<link rel="alternate" type="text/html" href="http://atom.test/old/1"/><id>tag:atom.test,2025:1</id>'
                    '<issued>2025-03-02T10:00:00Z</issued><modified>2025-03-03T10:00:00Z</modified>'
                    '<author><name>Old Author</name></author><content type="text/html" mode="escaped">&lt;p&gt;Escaped '
                    '0.3 content&lt;/p&gt;</content></entry>\n</feed>\n'),
     ('title', 'url', 'published_at', 'author', 'content'), ('title', 'site_url'), False, 'An Atom 0.3 document.'),
    ('atom03-base64.xml', ('<?xml version="1.0" encoding="utf-8"?>\n<feed version="0.3" xmlns="http://purl.org/atom/ns#">'
                           '<title>Atom 0.3 base64</title><link rel="alternate" href="http://atom.test/b64/"/>'
                           '<entry><title>Encoded</title><link rel="alternate" href="http://atom.test/b64/1"/>'
                           '<id>tag:atom.test,2025:b64</id><issued>2025-03-04T10:00:00Z</issued>'
                           '<content type="text/html" mode="base64">PHA+QmFzZTY0IGNvbnRlbnQ8L3A+</content></entry>'
                           '</feed>\n'), C, (), False, 'Base64 content of an Atom 0.3 entry.'),
]


def build(s):
    build_cases(s, 'atom.test', CASES, 'application/atom+xml')
