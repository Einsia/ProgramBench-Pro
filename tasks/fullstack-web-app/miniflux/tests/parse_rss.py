"""RSS 2.0 (and 0.9x) parsing: titles, links, GUIDs, publication dates, authors, content, enclosures and media,
categories, comments, podcast durations, languages, channel fallbacks, encodings and malformed documents.
Each case is one small feed; the observation is the part of the stored feed and entries the case is about."""
from parsing import build_cases

NS = (' xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/"'
      ' xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/"'
      ' xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:feedburner="http://rssnamespace.org/feedburner/ext/1.0"'
      ' xmlns:googleplay="http://www.google.com/schemas/play-podcasts/1.0" xmlns:slash="http://purl.org/rss/1.0/modules/slash/"')
DATE = 'Mon, 06 Jan 2025 10:00:00 GMT'


def doc(items, channel='', title='RSS fixture', link='http://rss.test/site/', declaration='<?xml version="1.0" encoding="UTF-8"?>\n',
        version='2.0', description='Fixture channel'):
    return (f'{declaration}<rss version="{version}"{NS}>\n<channel>\n<title>{title}</title>\n<link>{link}</link>\n'
            f'<description>{description}</description>\n{channel}{items}</channel>\n</rss>\n')


def it(body, link='http://rss.test/item', date=DATE):
    parts = ['<item>']
    if link:
        parts.append(f'<link>{link}</link>')
    if date:
        parts.append(f'<pubDate>{date}</pubDate>')
    parts.append(body + '</item>\n')
    return ''.join(parts)


def titled(title, **kw):
    return it(f'<title>{title}</title><description>Body.</description>', **kw)


T = ('title',)
U = ('title', 'url')
D = ('title', 'published_at')
A = ('title', 'author')
C = ('title', 'content')
E = ('title', 'url', 'enclosures')
G = ('title', 'tags')

CASES = [
    # Titles.
    ('title-entities.xml', doc(titled('Fish &amp; Chips &lt;3')), T, (), False, 'Entity-escaped title text is decoded.'),
    ('title-double-escaped.xml', doc(titled('Salt &amp;amp; Pepper')), T, (), False,
     'A doubly escaped ampersand in a title is decoded twice.'),
    ('title-cdata.xml', doc(titled('<![CDATA[Bold <b>move</b> & more]]>')), T, (), False,
     'A CDATA title with markup.'),
    ('title-whitespace.xml', doc(titled('\n    Spaced    out   title  \n  ')), T, (), False,
     'Whitespace around and inside a title.'),
    ('title-charrefs.xml', doc(titled('&#169; 2025 &#x2603; snow')), T, (), False, 'Numeric character references.'),
    ('title-dublin-core.xml', doc(it('<title>Plain title</title><dc:title>Dublin Core title</dc:title>')), T, (),
     False, 'A Dublin Core title replaces the item title.'),
    ('title-from-content.xml', doc(it('<description>&lt;p&gt;An item without a title starts with this rather long '
                                      'paragraph, which goes on well beyond one hundred characters so that it must be '
                                      'shortened.&lt;/p&gt;</description>')), T, (), False,
     'An item without a title takes the start of its content, shortened.'),
    ('title-from-url.xml', doc(it('<description></description>', link='http://rss.test/untitled-item')), U, (), False,
     'An item without title and content is titled with its URL.'),
    ('title-markup.xml', doc(titled('Escaped &lt;i&gt;markup&lt;/i&gt; in title')), T, (), False,
     'Escaped markup inside a title.'),
    # Links and GUIDs.
    ('link-relative.xml', doc(titled('Relative link', link='/articles/relative-1')), U, (), False,
     'A relative item link is resolved against the channel link.'),
    ('link-relative-path.xml', doc(titled('Relative path', link='posts/second')), U, (), False,
     'A relative path without a leading slash is resolved against the channel link.'),
    ('link-whitespace.xml', doc(titled('Spaced link', link='\n   http://rss.test/spaced-link   \n')), U, (), False,
     'Whitespace around an item link is ignored.'),
    ('link-feedburner.xml', doc(it('<title>Feedburner</title><feedburner:origLink>http://rss.test/original-link'
                                   '</feedburner:origLink>', link='http://feeds.example.net/~r/x/1')), U, (), False,
     'A Feedburner original link wins over the item link.'),
    ('link-atom.xml', doc(it('<title>Atom link</title><atom:link rel="alternate" href="http://rss.test/atom-alternate"/>',
                             link=None)), U, (), False, 'An Atom alternate link inside an RSS item.'),
    ('link-guid-permalink.xml', doc(it('<title>GUID link</title><guid>http://rss.test/from-guid</guid>', link=None)),
     U, (), False, 'Without a link, a permalink GUID is the URL.'),
    ('link-guid-not-permalink.xml', doc(it('<title>Opaque GUID</title><guid isPermaLink="false">tag:rss.test,2025:9</guid>',
                                           link=None)), U, (), False,
     'Without a link and with an opaque GUID, the item points to the channel site.'),
    ('link-enclosure.xml', doc(it('<title>Only media</title><guid isPermaLink="false">media-only</guid>'
                                  '<enclosure url="http://media.rss.test/only.mp3" length="10" type="audio/mpeg"/>',
                                  link=None)), U, (), False, 'Without a link, the first enclosure is the URL.'),
    ('link-site-relative.xml', doc(titled('Relative site', link='/item-on-site'), link='/relative-site/'),
     ('title', 'url'), ('site_url', 'feed_url'), False,
     'A relative channel link is resolved against the feed URL, then items against it.'),
    ('guid-duplicate.xml', doc(it('<title>Same GUID one</title><guid>same-guid</guid>', link='http://rss.test/dup/1') +
                               it('<title>Same GUID two</title><guid>same-guid</guid>', link='http://rss.test/dup/2',
                                  date='Tue, 07 Jan 2025 10:00:00 GMT')), U, (), True,
     'Items sharing one GUID are kept apart by their links.'),
    ('guid-identical-items.xml', doc(it('<title>Twin</title><description>Same.</description>', link=None, date=None) +
                                     it('<title>Twin</title><description>Same.</description>', link=None, date=None)),
     ('title',), (), True, 'Identical items without link and GUID are stored once.'),
    # Publication dates.
    ('date-gmt.xml', doc(titled('GMT', date='Mon, 06 Jan 2025 10:00:00 GMT')), D, (), False, 'An RFC 1123 date in GMT.'),
    ('date-offset.xml', doc(titled('Offset', date='Mon, 06 Jan 2025 10:00:00 +0200')), D, (), False,
     'An RFC 822 date with a numeric offset.'),
    ('date-est.xml', doc(titled('EST', date='Mon, 06 Jan 2025 10:00:00 EST')), D, (), False,
     'A date in Eastern Standard Time.'),
    ('date-pdt.xml', doc(titled('PDT', date='Fri, 06 Jun 2025 10:00:00 PDT')), D, (), False,
     'A date in Pacific Daylight Time.'),
    ('date-cest.xml', doc(titled('CEST', date='Mon, 06 Jan 2025 10:00:00 CEST')), D, (), False,
     'A date with the zone abbreviation CEST.'),
    ('date-ut.xml', doc(titled('UT', date='Mon, 06 Jan 2025 10:00:00 UT')), D, (), False, 'A date in UT.'),
    ('date-z.xml', doc(titled('Zulu', date='Mon, 06 Jan 2025 10:00:00 Z')), D, (), False, 'A date with the Z zone.'),
    ('date-no-seconds.xml', doc(titled('No seconds', date='Mon, 06 Jan 2025 10:00 GMT')), D, (), False,
     'A date without seconds.'),
    ('date-no-weekday.xml', doc(titled('No weekday', date='06 Jan 2025 10:00:00 GMT')), D, (), False,
     'A date without the day of the week.'),
    ('date-two-digit-year.xml', doc(titled('Short year', date='Mon, 06 Jan 25 10:00:00 GMT')), D, (), False,
     'A date with a two-digit year.'),
    ('date-single-digit-day.xml', doc(titled('Single digit', date='Mon, 6 Jan 2025 10:00:00 GMT')), D, (), False,
     'A date with a one-digit day.'),
    ('date-iso.xml', doc(titled('ISO', date='2025-01-06T10:00:00Z')), D, (), False, 'An ISO 8601 date in UTC.'),
    ('date-iso-offset.xml', doc(titled('ISO offset', date='2025-01-06T10:00:00+05:30')), D, (), False,
     'An ISO 8601 date with an offset.'),
    ('date-iso-day.xml', doc(titled('ISO day', date='2025-01-06')), D, (), False, 'A date without a time.'),
    ('date-iso-space.xml', doc(titled('ISO space', date='2025-01-06 10:00:00')), D, (), False,
     'A date with a space instead of T and no zone.'),
    ('date-dublin-core.xml', doc(it('<title>Dublin date</title><dc:date>2025-02-03T04:05:06Z</dc:date>')), D, (),
     False, 'A Dublin Core date replaces pubDate.'),
    ('date-full-names.xml', doc(titled('Full names', date='Monday, 06 January 2025 10:00:00 GMT')), D, (), False,
     'A date with full weekday and month names.'),
    ('date-lowercase.xml', doc(titled('Lowercase', date='mon, 06 jan 2025 10:00:00 -0000')), D, (), False,
     'A date written in lowercase.'),
    ('date-wrong-weekday.xml', doc(titled('Wrong weekday', date='Fri, 06 Jan 2025 10:00:00 GMT')), D, (), False,
     'A date whose weekday does not match.'),
    ('date-unix.xml', doc(titled('Unix', date='1736157600')), D, (), False, 'A Unix timestamp as the date.'),
    ('date-french.xml', doc(titled('French', date='lun, 06 janvier 2025 10:00:00 GMT')), D, (), False,
     'A date with French day and month names.'),
    ('date-us-slashes.xml', doc(titled('Slashes', date='01/06/2025')), D, (), False, 'A date written with slashes.'),
    ('date-am-pm.xml', doc(titled('AM PM', date='January 6, 2025 3:04 PM')), D, (), False,
     'A date with an AM/PM time.'),
    ('date-ordinal.xml', doc(titled('Ordinal', date='Mon, 6th Jan 2025 10:00:00 GMT')), D, (), False,
     'A date with an ordinal day.'),
    ('date-invalid.xml', doc(titled('Invalid date', date='not a date at all')), D, (), False,
     'An unparsable date makes the entry dated when it is stored.'),
    ('date-missing.xml', doc(titled('Missing date', date=None)), D, (), False,
     'A missing date makes the entry dated when it is stored.'),
    # Authors.
    ('author-email-name.xml', doc(it('<title>Email and name</title><author>edith@rss.test (Edith Editor)</author>')),
     A, (), False, 'An author written as e-mail address with a name.'),
    ('author-email.xml', doc(it('<title>Email only</title><author>only@rss.test</author>')), A, (), False,
     'An author written as an e-mail address only.'),
    ('author-dublin-core.xml', doc(it('<title>DC creator</title><dc:creator>Dora Creator</dc:creator>')), A, (), False,
     'A Dublin Core creator.'),
    ('author-itunes.xml', doc(it('<title>iTunes author</title><itunes:author>Ian Tunes</itunes:author>'
                                 '<dc:creator>Ignored Creator</dc:creator>')), A, (), False,
     'An iTunes author wins over a Dublin Core creator.'),
    ('author-markup.xml', doc(it('<title>Marked author</title><dc:creator>&lt;b&gt;Bold&lt;/b&gt; Writer</dc:creator>')),
     A, (), False, 'Markup in an author name is removed.'),
    ('author-cdata.xml', doc(it('<title>CDATA author</title><author><![CDATA[Cara <cara@rss.test>]]></author>')), A,
     (), False, 'An author in CDATA.'),
    ('author-channel-editor.xml', doc(titled('Editor fallback'), channel='<managingEditor>Mona Editor</managingEditor>\n'),
     A, (), False, 'Without an item author, the channel managing editor is the author.'),
    ('author-channel-itunes.xml', doc(titled('Channel iTunes'), channel='<itunes:author>Channel Voice</itunes:author>\n'
                                      '<managingEditor>Not this one</managingEditor>\n'), A, (), False,
     'The channel iTunes author wins over the managing editor.'),
    ('author-google-play.xml', doc(it('<title>Play author</title><googleplay:author>Gail Play</googleplay:author>'
                                      '<itunes:author>Not iTunes</itunes:author>')), A, (), False,
     'A Google Play author wins over the iTunes author.'),
    # Content.
    ('content-escaped.xml', doc(it('<title>Escaped</title><description>&lt;p&gt;Paragraph with &lt;em&gt;emphasis'
                                   '&lt;/em&gt;.&lt;/p&gt;</description>')), C, (), False, 'Escaped HTML content.'),
    ('content-cdata.xml', doc(it('<title>CDATA content</title><description><![CDATA[<p>CDATA <strong>strong</strong> '
                                 'text</p>]]></description>')), C, (), False, 'HTML content in CDATA.'),
    ('content-encoded.xml', doc(it('<title>Encoded</title><description>Short summary</description><content:encoded>'
                                   '<![CDATA[<p>The full <i>encoded</i> body.</p>]]></content:encoded>')), C, (), False,
     'content:encoded wins over the description.'),
    ('content-plain-text.xml', doc(it('<title>Plain</title><description>Line one\nLine two &amp; three</description>')),
     C, (), False, 'Plain-text content.'),
    ('content-itunes-summary.xml', doc(it('<title>Summary only</title><itunes:summary>The iTunes summary text.'
                                          '</itunes:summary>')), C, (), False,
     'Without a description, the iTunes summary is the content.'),
    ('content-relative-urls.xml', doc(it('<title>Relative URLs</title><description><![CDATA[<p><a href="/linked/page">'
                                         'link</a> <img src="images/pic.png" alt="pic"></p>]]></description>',
                                         link='http://rss.test/section/article')), C, (), False,
     'Relative links and images in content are made absolute against the entry URL.'),
    ('content-empty.xml', doc(it('<title>No content</title>')), C, (), False, 'An item without any content.'),
    # Enclosures and media.
    ('enclosure-audio.xml', doc(it('<title>Audio</title><enclosure url="http://media.rss.test/a.mp3" length="5000" '
                                   'type="audio/mpeg"/>')), E, (), False, 'An audio enclosure with its size.'),
    ('enclosure-no-length.xml', doc(it('<title>No length</title><enclosure url="http://media.rss.test/b.ogg" '
                                       'type="audio/ogg"/>')), E, (), False, 'An enclosure without length.'),
    ('enclosure-relative.xml', doc(it('<title>Relative enclosure</title><enclosure url="/media/c.mp3" length="7" '
                                      'type="audio/mpeg"/>')), E, (), False,
     'A relative enclosure URL is resolved against the site.'),
    ('enclosure-duplicates.xml', doc(it('<title>Duplicates</title>'
                                        '<enclosure url="http://media.rss.test/d.mp3" length="1" type="audio/mpeg"/>'
                                        '<enclosure url="http://media.rss.test/d.mp3" length="1" type="audio/mpeg"/>'
                                        '<enclosure url="http://media.rss.test/e.mp4" length="2" type="video/mp4"/>')),
     E, (), False, 'Duplicate enclosures are stored once.'),
    ('media-content.xml', doc(it('<title>Media content</title><media:content url="http://media.rss.test/f.jpg" '
                                 'type="image/jpeg" fileSize="4321" medium="image"/>')), E, (), False,
     'Media RSS content becomes an enclosure.'),
    ('media-thumbnail.xml', doc(it('<title>Thumbnail</title><media:thumbnail url="http://media.rss.test/thumb.jpg" '
                                   'width="120" height="90"/>')), E, (), False,
     'A Media RSS thumbnail becomes an enclosure.'),
    ('media-group.xml', doc(it('<title>Media group</title><media:group><media:content url="http://media.rss.test/g1.mp4" '
                               'type="video/mp4"/><media:content url="http://media.rss.test/g2.webm" type="video/webm"/>'
                               '</media:group>')), E, (), False, 'Media contents inside a media group.'),
    ('media-description.xml', doc(it('<title>Media description</title><media:group><media:description>Description of '
                                     'the video.</media:description><media:content url="http://media.rss.test/h.mp4" '
                                     'type="video/mp4"/></media:group>')), C, (), False,
     'Content of an item that only has a media description.'),
    ('enclosure-feedburner.xml', doc(it('<title>Feedburner media</title><enclosure url="http://feeds.example.net/~r/x/ep.mp3" '
                                        'length="9" type="audio/mpeg"/><feedburner:origEnclosureLink>'
                                        'http://media.rss.test/real/ep.mp3</feedburner:origEnclosureLink>')), E, (),
     False, 'A Feedburner original enclosure link replaces the enclosure URL.'),
    # Categories and comments.
    ('tags-sorted.xml', doc(it('<title>Tags</title><category>zeta</category><category> alpha </category>'
                               '<category>alpha</category><category>Mid</category>')), G, (), False,
     'Item categories become tags: trimmed, de-duplicated and sorted.'),
    ('tags-channel.xml', doc(titled('Channel tags'), channel='<category>channel-topic</category>\n'), G, (), False,
     'Without item categories, the channel categories are the tags.'),
    ('tags-itunes.xml', doc(titled('iTunes categories'), channel='<itunes:category text="Technology"><itunes:category '
                                                                 'text="Podcasting"/></itunes:category>\n'), G, (),
     False, 'iTunes categories of the channel become tags.'),
    ('tags-media.xml', doc(it('<title>Media categories</title><media:category label="Science">sci</media:category>'
                              '<category>news</category>')), G, (), False, 'Media RSS category labels become tags.'),
    ('comments-absolute.xml', doc(it('<title>Comments</title><comments>http://rss.test/comments/1</comments>')),
     ('title', 'comments_url'), (), False, 'An absolute comments URL is kept.'),
    ('comments-relative.xml', doc(it('<title>Relative comments</title><comments>/comments/2</comments>')),
     ('title', 'comments_url'), (), False, 'A relative comments URL is not kept.'),
    # Podcasts and languages.
    ('itunes-duration-hms.xml', doc(it('<title>Long episode</title><itunes:duration>1:02:03</itunes:duration>')),
     ('title', 'reading_time'), (), False, 'An iTunes duration of h:mm:ss is the listening time.'),
    ('itunes-duration-seconds.xml', doc(it('<title>Seconds episode</title><itunes:duration>754</itunes:duration>')),
     ('title', 'reading_time'), (), False, 'An iTunes duration in seconds.'),
    ('language-channel.xml', doc(titled('Language'), channel='<language>fr-CA</language>\n'), ('title',),
     ('language',), False, 'The channel language.'),
    # Channel fields.
    ('channel-title-entities.xml', doc(titled('Item'), title='News &amp; Views &#8212; Daily'), (),
     ('title', 'site_url', 'description'), False, 'The channel title and description.'),
    ('channel-no-title.xml', doc(titled('Item'), title=''), (), ('title',), False,
     'A channel without a title is titled with its site URL.'),
    ('channel-self-link.xml', doc(titled('Item'), channel='<atom:link rel="self" href="http://rss.test/canonical.xml"/>\n'),
     (), ('feed_url',), False, 'The channel\'s self link becomes the feed URL.'),
    ('rss-091.xml', doc(titled('Old version'), version='0.91'), ('title', 'url', 'published_at'), ('title',), False,
     'An RSS 0.91 document.'),
    # Encodings and malformed documents.
    ('encoding-latin1.xml', ('<?xml version="1.0" encoding="ISO-8859-1"?>\n<rss version="2.0"><channel><title>Caf\xe9 '
                             'feed</title><link>http://rss.test/site/</link><item><title>Cr\xe8me br\xfbl\xe9e</title>'
                             f'<link>http://rss.test/latin</link><pubDate>{DATE}</pubDate></item></channel></rss>\n'
                             ).encode('latin-1'), T, ('title',), False, 'A document encoded in ISO-8859-1.'),
    ('encoding-cp1252.xml', ('<?xml version="1.0" encoding="windows-1252"?>\n<rss version="2.0"><channel><title>Quotes'
                             '</title><link>http://rss.test/site/</link><item><title>“Smart” quotes – '
                             f'and dashes</title><link>http://rss.test/cp1252</link><pubDate>{DATE}</pubDate></item>'
                             '</channel></rss>\n').encode('cp1252'), T, (), False, 'A document encoded in windows-1252.'),
    ('encoding-bom.xml', b'\xef\xbb\xbf' + doc(titled('Byte order mark')).encode(), T, (), False,
     'A UTF-8 document starting with a byte order mark.'),
    ('encoding-header.xml', ('<rss version="2.0"><channel><title>Header charset</title><link>http://rss.test/site/'
                             f'</link><item><title>\xc9t\xe9 header</title><link>http://rss.test/hdr</link><pubDate>{DATE}'
                             '</pubDate></item></channel></rss>\n').encode('latin-1'), T, (), False,
     'The charset given only in the Content-Type header.', 'application/rss+xml; charset=ISO-8859-1'),
    ('html-entities.xml', doc(titled('Caf&eacute; &mdash; na&iuml;ve &nbsp;space')), T, (), False,
     'HTML named entities that XML does not define.'),
    ('bare-ampersand.xml', doc(titled('Salt & pepper')), T, (), False, 'An unescaped ampersand in a title.'),
    ('no-declaration.xml', doc(titled('No declaration'), declaration=''), T, (), False,
     'A document without an XML declaration.'),
]


def build(s):
    build_cases(s, 'rss.test', CASES, 'application/rss+xml')
    s.bind(f'{s.prefix}api.parse.comments-relative.subscribe', f'{s.prefix}api.parse.comments-absolute.subscribe')
