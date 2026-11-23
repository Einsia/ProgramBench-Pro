"""Feed syntax, field precedence, dates, encodings and metadata."""
from spec_common import (F, cache, cp, point, slug, episode)

NS = ('xmlns:dc="http://purl.org/dc/elements/1.1/" '
      'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
      'xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
      'xmlns:media="http://search.yahoo.com/mrss/"')


def rssdoc(body, channel='', version='2.0', root=''):
    return (f'<?xml version="1.0"?><rss version="{version}" {NS} {root}><channel>'
            '<title>Parser feed</title><link>https://example.org/base/</link><description>Feed description</description>'
            + channel + body + '</channel></rss>')


def rssitem(name, overrides):
    fields = dict(title='<title>Baseline title</title>', link='<link>https://example.org/item</link>',
                  guid=f'<guid isPermaLink="false">{name}</guid>', date='<pubDate>Mon, 01 Jan 2024 10:00:00 +0000</pubDate>',
                  content='<description>&lt;p&gt;Baseline content&lt;/p&gt;</description>', author='<author>Alice</author>')
    fields.update(overrides)
    return '<item>' + ''.join(fields.values()) + '</item>'


def atomdoc(body, feedfields='', root=''):
    return (f'<feed xmlns="http://www.w3.org/2005/Atom" {NS} {root}>'
            '<title>Atom parser</title><id>urn:feed:parser</id><link rel="alternate" href="https://atom.example/base/"/>'
            '<updated>2024-01-01T10:00:00Z</updated>' + feedfields + body + '</feed>')


def atomitem(name, overrides):
    fields = dict(title='<title>Atom baseline</title>', link='<link href="https://atom.example/item"/>',
                  guid=f'<id>urn:{name}</id>', date='<updated>2024-01-01T10:00:00Z</updated>',
                  content='<content type="html">&lt;p&gt;Atom content&lt;/p&gt;</content>',
                  author='<author><name>Alice</name></author>')
    fields.update(overrides)
    return '<entry>' + ''.join(fields.values()) + '</entry>'


def build():
    out = []
    cases = []

    def rsscase(name, overrides, columns, channel='', root=''):
        cases.append((name, rssdoc(rssitem(name, overrides), channel, root=root), columns))

    for name, raw in [
        ('title-entities', 'Fish &amp; Chips &lt;3'), ('title-cdata', '<![CDATA[Fish & Chips]]>'),
        ('title-multiline', '  First\nSecond\rThird  '), ('title-unicode', '日本語 Café Ελληνικά'),
        ('title-emoji', 'Boat 🚢 and café'), ('title-combining', 'Café'),
        ('title-html', '&lt;b&gt;Bold&lt;/b&gt; plain'), ('title-empty', ''),
        ('title-numeric-entities', '&#65;&#x3A9;&#128640;'), ('title-tab', 'One\tTwo'),
    ]:
        rsscase(name, {'title': '<title>' + raw + '</title>'}, 'title')
    rsscase('title-absent', {'title': ''}, 'title')
    rsscase('title-from-link', {'title': '', 'link': '<link>https://example.org/my-new-story?q=1</link>'}, 'title')
    rsscase('title-no-link', {'title': '', 'link': ''}, 'title url')
    for name, raw in [('author-email-name', 'a@example.org (Alice Smith)'), ('author-email', 'a@example.org'),
                      ('author-name-email', 'Alice &lt;a@example.org&gt;'), ('author-unicode', 'Zoë 中文'),
                      ('author-empty', ''), ('author-space', '  Alice  '), ('author-entities', 'A &amp; B')]:
        rsscase(name, {'author': '<author>' + raw + '</author>'}, 'author')
    rsscase('author-dc', {'author': '<dc:creator>Creator</dc:creator>'}, 'author')
    rsscase('author-dc-priority', {'author': '<author>Writer</author><dc:creator>Creator</dc:creator>'}, 'author')
    rsscase('author-dc-order', {'author': '<dc:creator>Creator</dc:creator><author>Writer</author>'}, 'author')
    rsscase('author-channel-fallback', {'author': ''}, 'author', '<managingEditor>Editor</managingEditor>')
    rsscase('author-entry-over-channel', {}, 'author', '<managingEditor>Editor</managingEditor>')
    rsscase('author-none', {'author': ''}, 'author')
    for name, raw in [('link-relative', 'story'), ('link-parent', '../story'), ('link-root', '/story'),
                      ('link-protocol-relative', '//other.example/story'), ('link-query', '?q=1&amp;x=2'),
                      ('link-fragment', '#part'), ('link-https', 'https://other.example/story'),
                      ('link-unicode', 'https://other.example/café')]:
        rsscase(name, {'link': '<link>' + raw + '</link>'}, 'url')
    rsscase('guid-permalink-default', {'link': '', 'guid': '<guid>https://id.example/story</guid>'}, 'guid url')
    rsscase('guid-permalink-false', {'link': '', 'guid': '<guid isPermaLink="false">opaque-id</guid>'}, 'guid url')
    rsscase('guid-permalink-true', {'link': '', 'guid': '<guid isPermaLink="true">https://id.example/true</guid>'}, 'guid url')
    rsscase('guid-empty-link-fallback', {'guid': ''}, 'guid')
    rsscase('guid-empty-content-fallback', {'guid': '', 'link': ''}, 'guid')
    rsscase('guid-entities', {'guid': '<guid isPermaLink="false">urn:a&amp;b</guid>'}, 'guid')
    rsscase('item-xml-base', {'link': '<link>story</link>', 'extra': ''}, 'url', root='xml:base="https://base.example/root/"')
    for name, raw in [('content-cdata', '<![CDATA[<p>CDATA & text</p>]]>'),
                      ('content-escaped', '&lt;p&gt;Escaped &amp; text&lt;/p&gt;'),
                      ('content-empty', ''), ('content-unicode', '中文 &amp; café 🚢'),
                      ('content-plain', 'Plain text\nSecond line'), ('content-html-entities', '&amp;nbsp; &amp;copy;')]:
        rsscase(name, {'content': '<description>' + raw + '</description>'}, 'content content_mime_type')
    rsscase('content-encoded', {'content': '<content:encoded><![CDATA[<h1>Full</h1>]]></content:encoded>'}, 'content content_mime_type')
    rsscase('content-encoded-precedence', {'extra': '<content:encoded>Full text</content:encoded>'}, 'content')
    rsscase('content-itunes-summary', {'content': '<itunes:summary>Podcast summary</itunes:summary>'}, 'content')
    rsscase('content-itunes-precedence', {'extra': '<itunes:summary>Podcast summary</itunes:summary>'}, 'content')
    rsscase('content-base', {'content': '<description xml:base="https://base.example/">Body</description>'}, 'base')
    for name, raw in [
        ('rfc822-offset-positive', 'Mon, 01 Jan 2024 12:00:00 +0200'),
        ('rfc822-offset-negative', 'Mon, 01 Jan 2024 05:00:00 -0500'),
        ('rfc822-gmt', 'Mon, 01 Jan 2024 10:00:00 GMT'),
        ('rfc822-short-year', 'Mon, 01 Jan 24 10:00:00 +0000'),
        ('rfc822-no-weekday', '01 Jan 2024 10:00:00 +0000'),
        ('rfc822-single-day', '1 Jan 2024 10:00:00 +0000'),
        ('rfc822-est', '01 Jan 2024 05:00:00 EST'),
        ('rfc822-no-seconds', '01 Jan 2024 10:00 +0000'),
        ('rfc822-leap-day', 'Thu, 29 Feb 2024 23:59:59 +0000'),
        ('date-iso-z', '2024-01-01T10:00:00Z'), ('date-iso-offset', '2024-01-01T12:00:00+02:00'),
        ('date-before-epoch', 'Wed, 31 Dec 1969 23:59:58 +0000'),
        ('date-after-2038', 'Sat, 01 Jan 2050 00:00:00 +0000')]:
        rsscase(name, {'date': '<pubDate>' + raw + '</pubDate>'}, 'pubDate')
    rsscase('date-dc', {'date': '<dc:date>2024-02-03T12:34:56Z</dc:date>'}, 'pubDate')
    for name, attributes in [
        ('enclosure-audio', 'url="https://pod.example/e.mp3" type="audio/mpeg"'),
        ('enclosure-video', 'url="https://pod.example/e.mp4" type="video/mp4"'),
        ('enclosure-no-type', 'url="https://pod.example/e.bin"'),
        ('enclosure-empty-url', 'url="" type="audio/mpeg"'),
        ('enclosure-relative', 'url="episode.mp3" type="audio/mpeg"'),
        ('enclosure-query', 'url="https://pod.example/e.mp3?a=1&amp;b=2" type="audio/mpeg"')]:
        rsscase(name, {'extra': '<enclosure ' + attributes + '/>'}, 'enclosure_url enclosure_type')
    rsscase('multiple-enclosures', {'extra': '<enclosure url="https://e/one.png" type="image/png"/>'
             '<enclosure url="https://e/two.mp3" type="audio/mpeg"/>'}, 'enclosure_url enclosure_type')
    rsscase('media-content', {'extra': '<media:content url="https://e/media.mp3" type="audio/mpeg"/>'}, 'enclosure_url enclosure_type')
    rsscase('media-description', {'extra': '<media:content url="https://e/m.mp3" type="audio/mpeg">'
             '<media:description type="plain">Episode notes</media:description></media:content>'},
            'enclosure_url enclosure_description enclosure_description_mime_type')
    rsscase('unknown-elements', {'extra': '<unknown><title>Wrong title</title><description>Wrong body</description></unknown>'}, 'title content')
    rsscase('namespace-isolation', {'extra': '<x:title xmlns:x="urn:unrelated">Wrong title</x:title>'}, 'title')
    for version in ('0.91', '0.92'):
        cases.append(('rss-'+version.replace('.', '-'), rssdoc(rssitem('rss'+version, {}), version=version),
                      'title author url guid content pubDate'))

    atomcases = []
    def acase(name, overrides, columns, extra='', root=''):
        atomcases.append((name, atomdoc(atomitem(name, overrides), extra, root), columns))
    for name, value in [('text', 'Plain &amp; title'), ('html', '&lt;b&gt;Bold&lt;/b&gt; &amp;amp; text'),
                        ('xhtml', '<div xmlns="http://www.w3.org/1999/xhtml"><b>Bold</b> title</div>')]:
        acase('title-'+name, {'title': f'<title type="{name}">{value}</title>'}, 'title')
    acase('title-absent', {'title': ''}, 'title')
    acase('title-empty', {'title': '<title/>'}, 'title')
    acase('title-unicode', {'title': '<title>日本語 é 🚀</title>'}, 'title')
    acase('author-feed', {'author': ''}, 'author', '<author><name>Feed writer</name></author>')
    acase('author-source', {'author': '<source><author><name>Source writer</name></author></source>'}, 'author')
    acase('author-source-priority', {'extra': '<source><author><name>Source writer</name></author></source>'}, 'author')
    acase('author-multiple', {'author': '<author><name>Alice</name></author><author><name>Bob</name></author>'}, 'author')
    acase('author-email-without-name', {'author': '<author><email>a@example.org</email></author>'}, 'author')
    for name, val in [('text', 'A &amp; B <span>inline</span>'), ('html', '&lt;p&gt;A &amp;amp; B&lt;/p&gt;'),
                      ('xhtml', '<div xmlns="http://www.w3.org/1999/xhtml"><p>A &amp; B</p></div>'),
                      ('text/plain', 'Plain line'), ('text/html', '<p>Literal HTML</p>'),
                      ('application/xml', '<data>Value</data>')]:
        acase('content-'+slug(name), {'content': f'<content type="{name}">{val}</content>'}, 'content content_mime_type')
    acase('content-default-type', {'content': '<content>Plain default</content>'}, 'content content_mime_type')
    acase('summary-fallback', {'content': '<summary type="html">&lt;b&gt;Summary&lt;/b&gt;</summary>'}, 'content content_mime_type')
    acase('empty-content-summary', {'content': '<content/><summary>Summary fallback</summary>'}, 'content content_mime_type')
    acase('content-over-summary', {'extra': '<summary>Unused summary</summary>'}, 'content')
    acase('content-escaped-mode', {'content': '<content mode="escaped" type="html">&lt;p&gt;Escaped&lt;/p&gt;</content>'}, 'content content_mime_type')
    acase('published-over-updated', {'date': '<updated>2024-01-02T00:00:00Z</updated><published>2020-05-06T07:08:09Z</published>'}, 'pubDate')
    for name, value in [('offset', '2024-01-01T12:30:00+02:30'), ('fraction', '2024-01-01T10:00:00.125Z'),
                        ('negative-offset', '2024-01-01T04:30:00-05:30'), ('date-only', '2024-02-29'),
                        ('month-only', '2024-02'), ('year-only', '2024')]:
        acase('date-'+name, {'date': '<updated>'+value+'</updated>'}, 'pubDate')
    for name, links in [
        ('alternate', '<link rel="alternate" href="https://alt.example/"/>'),
        ('self-ignored', '<link rel="self" href="https://self.example/"/>'),
        ('html-over-non-http', '<link href="file://ignore"/><link href="https://web.example/"/>'),
        ('first-http-link', '<link href="https://first.example/"/><link href="https://second.example/"/>'),
        ('relative', '<link href="article"/>'), ('root', '<link href="/article"/>')]:
        acase('link-'+name, {'link': links}, 'url', root='xml:base="https://base.example/path/"')
    acase('enclosure', {'extra': '<link rel="enclosure" href="https://pod.example/a.mp3" type="audio/mpeg"/>'}, 'enclosure_url enclosure_type')
    acase('content-base', {'content': '<content xml:base="https://body.example/" type="html">Body</content>'}, 'base')
    acase('opaque-id', {'guid': '<id>opaque id &amp; special</id>'}, 'guid')
    acase('id-no-permalink', {'guid': '<id>https://id.example/</id>', 'link': ''}, 'guid url')
    acase('id-link-fallback', {'guid': ''}, 'guid')
    acase('id-content-fallback', {'guid': '', 'link': ''}, 'guid')
    acase('namespace-prefix', {}, 'title author url content pubDate')
    name, doc, cols = atomcases[-1]
    import re
    doc = doc.replace('xmlns="http://www.w3.org/2005/Atom"', 'xmlns:a="http://www.w3.org/2005/Atom"')
    doc = re.sub(r'<(/?)(feed|entry|title|id|link|updated|author|name|content)(?=[\s/>])', r'<\1a:\2', doc)
    atomcases[-1] = (name, doc, cols)

    for family, entries in [('rss', cases), ('atom', atomcases)]:
        docs, assertions = {}, []
        for name, doc, columns in entries:
            path = name + '.xml'
            docs[path] = doc
            assertions.append(point(name, cache(columns, {'feedurl': 'file://feeds/'+path}, nonempty=True),
                                    f'{family.upper()} {name.replace("-", " ")} is parsed into the corresponding fields.'))
        out.append(episode('parse-'+family, 'feed-parsing', [cp('fields', 'Read the parsed feed fields.', [], assertions)],
                            files=F.home('\n'.join('file://feeds/'+n for n in docs), docs)))

    # Feed-level metadata and format-specific fallback behavior use independent documents.
    docs, points = {}, []
    for lang in ['en', 'ar', 'he', 'fa', 'ur', 'ar-SA', 'en-US']:
        name='lang-'+slug(lang)
        docs[name+'.xml']=rssdoc(rssitem(name, {}), '<language>'+lang+'</language>')
        points.append(point(name, cache('is_rtl', {'rssurl':'file://feeds/'+name+'.xml'}, 'rss_feed', nonempty=True)))
    for name, c in [('title-last-wins','<title>Second title</title>'), ('title-entities','<title>A &amp; B</title>'),
                     ('title-unicode','<title>世界 Café</title>'), ('link-relative','<link>relative</link>'),
                     ('link-empty','<link/>'), ('link-https','<link>https://alternate.example/</link>')]:
        docs[name+'.xml']=rssdoc(rssitem(name, {}), c)
        points.append(point(name, cache('title' if 'title' in name else 'url', {'rssurl':'file://feeds/'+name+'.xml'}, 'rss_feed', nonempty=True)))
    rdf = ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
           'xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
           '<channel rdf:about="https://rdf.example/"><title>RDF News</title><link>https://rdf.example/</link>'
           '<description>RDF description</description></channel><item rdf:about="https://rdf.example/item">'
           '<title>RDF article</title><link>https://rdf.example/item</link><description>RDF body</description>'
           '<dc:creator>RDF writer</dc:creator><dc:date>2024-01-04T12:30:00Z</dc:date></item></rdf:RDF>')
    docs['rdf.xml']=rdf
    for col in ['title','url','guid','author','pubDate','content']:
        points.append(point('rdf-'+col.lower(), cache(col, {'feedurl':'file://feeds/rdf.xml'}, nonempty=True)))
    out.append(episode('parse-feed-metadata', 'feed-parsing', [cp('fields','Inspect feed metadata and RDF fields.',[],points)],
                        files=F.home('\n'.join('file://feeds/'+n for n in docs),docs)))
    return out
