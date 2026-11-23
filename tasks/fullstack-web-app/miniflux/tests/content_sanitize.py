"""HTML sanitization of entry content: removed elements and attributes, iframes and their allow list, images
(data URLs, lazy loading, dimensions, pixel trackers, srcset), links (relative, anchors, blocked sharing
services, tracking parameters), media elements, tables, MathML, hidden and unknown elements, comments and
text escaping. One feed carries every case as an item; each point observes one item's stored content."""
from xml.sax.saxutils import escape

import fixtures as fx
from fixtures import rss
from harness import CREDS, Ref, pathref, pick

PNG = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR42mP8z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC'
CASES = [
    ('script', '<p>Before</p><script>alert("x")</script><p>After</p>', 'Script elements and their text are removed.'),
    ('style', '<style>p { color: red }</style><p>Styled</p>', 'Style elements are removed.'),
    ('noscript', '<noscript><p>No script</p></noscript><p>Shown</p>', 'Noscript elements are removed.'),
    ('iframe-youtube', '<iframe src="https://www.youtube.com/embed/abc123" width="560" height="315" frameborder="0" '
                       'allowfullscreen></iframe>', 'A YouTube embed is kept and rewritten to the no-cookie player.'),
    ('iframe-youtube-query', '<iframe src="https://www.youtube.com/embed/abc123?start=42"></iframe>',
     'A YouTube embed keeps its query.'),
    ('iframe-vimeo', '<iframe src="https://player.vimeo.com/video/76979871"></iframe>',
     'A Vimeo embed gets the do-not-track parameter.'),
    ('iframe-unknown', '<p>Frame:</p><iframe src="https://frames.untrusted.test/embed"></iframe>',
     'An iframe from a host outside the allow list is removed.'),
    ('iframe-javascript', '<iframe src="javascript:alert(1)"></iframe><p>x</p>', 'A javascript: iframe is removed.'),
    ('object-embed', '<object data="movie.swf"><embed src="movie.swf"></object><p>Plugin</p>',
     'Object and embed elements are removed.'),
    ('form', '<form action="/submit"><input name="q" value="v"><button>Go</button><textarea>T</textarea></form>',
     'Form controls are removed.'),
    ('event-handler', '<p onclick="steal()" onmouseover="x()">Click me</p>', 'Event handler attributes are removed.'),
    ('style-class-id', '<p style="color:red" class="lead" id="intro">Attributes</p>',
     'Style and class attributes are removed; ids only survive where allowed.'),
    ('heading-id', '<h2 id="section-2" class="x">Heading</h2>', 'Headings keep their id.'),
    ('javascript-link', '<a href="javascript:alert(1)">bad link</a>', 'A javascript: link loses its link.'),
    ('relative-link', '<a href="/about/team" title="Team">team</a>',
     'A relative link becomes absolute and opens in a new tab without referrer.'),
    ('anchor-link', '<a href="#footnote-1">see note</a>', 'An in-page anchor link stays relative.'),
    ('link-without-href', '<a name="here">anchor text</a>', 'A link without href is reduced to its text.'),
    ('mailto-link', '<a href="mailto:editor@example.test">mail</a>', 'A mailto link.'),
    ('tracking-link', '<a href="http://shop.test/item?id=7&amp;utm_source=feed&amp;utm_medium=rss&amp;fbclid=abc">'
                      'item</a>', 'Tracking parameters are removed from links.'),
    ('blocked-share', '<a href="https://twitter.com/intent/tweet?text=x">tweet</a><img src="http://feeds.feedburner.com/'
                      '~ff/blog?d=yIl2AUoC8zA">', 'Links and images of blocked sharing and tracking services.'),
    ('img-relative', '<img src="images/photo.png" alt="Photo" title="A photo">',
     'A relative image becomes absolute (proxied) with lazy loading.'),
    ('img-data', f'<img src="{PNG}" alt="dot">', 'An image data URL is kept.'),
    ('img-data-html', '<img src="data:text/html;base64,PHNjcmlwdD4=">', 'A non-image data URL is removed.'),
    ('img-dimensions', '<img src="http://img.test/a.png" width="320" height="auto">',
     'Only positive integer dimensions are kept.'),
    ('img-pixel', '<p>Text</p><img src="http://track.test/p.gif" width="1" height="1">',
     'A one-pixel tracking image is removed.'),
    ('img-no-src', '<img alt="nothing"><p>After</p>', 'An image without a source is removed.'),
    ('img-srcset', '<img src="small.jpg" srcset="small.jpg 1x, large.jpg 2x" sizes="100vw">',
     'Relative srcset candidates become absolute.'),
    ('img-priority', '<img src="http://img.test/b.png" fetchpriority="high" decoding="async" loading="eager">',
     'Valid fetch priority and decoding hints are kept.'),
    ('img-bad-priority', '<img src="http://img.test/c.png" fetchpriority="urgent" decoding="later">',
     'Invalid fetch priority and decoding values are removed.'),
    ('picture', '<picture><source srcset="pic.webp" type="image/webp"><img src="pic.jpg" alt="pic"></picture>',
     'A picture element with sources.'),
    ('video', '<video src="http://media.test/v.mp4" poster="poster.jpg" width="640" controls autoplay></video>',
     'A video element keeps its source and poster.'),
    ('audio', '<audio src="http://media.test/a.mp3" controls loop></audio>', 'An audio element keeps its source.'),
    ('table', '<table border="1"><thead><tr><th colspan="2">Head</th></tr></thead><tr><td rowspan="2" '
              'width="50">Cell</td></tr></table>', 'Tables keep their structure and spans.'),
    ('lists', '<ul id="u"><li>One</li></ul><ol start="3"><li>Two</li></ol><dl><dt>T</dt><dd>D</dd></dl>',
     'Lists and definition lists.'),
    ('quote', '<blockquote cite="http://src.test/">Quoted</blockquote><q cite="/q">short</q>',
     'Quotations and their citations.'),
    ('code', '<pre><code class="language-go">fmt.Println("x")</code></pre><kbd>Ctrl</kbd><samp>out</samp>',
     'Preformatted code.'),
    ('inline', '<b>b</b><i>i</i><u>u</u><s>s</s><small>sm</small><sub>2</sub><sup id="n1">1</sup><mark>m</mark>',
     'Inline formatting elements.'),
    ('time', '<time datetime="2025-01-06">Monday</time>', 'Time elements keep their datetime.'),
    ('math', '<math xmlns="http://example.test/wrong"><mi>x</mi><mo>=</mo><mn>2</mn></math>',
     'MathML is kept with the MathML namespace.'),
    ('svg', '<svg width="10"><circle r="4"/><text>Vector</text></svg><p>After svg</p>', 'SVG drawings.'),
    ('hidden', '<p hidden>Secret</p><p>Visible</p>', 'Hidden elements are removed.'),
    ('unknown-tags', '<custom-el>Inner</custom-el><font color="red">Font</font><span>Span</span><div>Div</div>',
     'Unknown and presentational elements are unwrapped.'),
    ('comments', '<p>Text<!-- a comment --> more</p>', 'Comments are removed.'),
    ('escaped-text', '<p>5 &lt; 6 &amp;&amp; 7 &gt; 3</p>', 'Escaped text stays text.'),
    ('meta-link-base', '<base href="http://evil.test/"><meta name="x" content="y"><link rel="stylesheet" href="s.css">'
                       '<p>Body</p>', 'Base, meta and link elements are removed.'),
    ('details', '<details><summary>More</summary><p>Hidden detail</p></details>', 'Details and summary.'),
    ('ruby', '<ruby>漢<rp>(</rp><rt>kan</rt><rp>)</rp></ruby>', 'Ruby annotations.'),
    ('figure', '<figure><img src="http://img.test/f.png"><figcaption>Caption</figcaption></figure>',
     'Figures and captions.'),
    ('nested-blocked', '<p>Keep <b>bold <script>x()</script>text</b></p>', 'A script nested in allowed markup.'),
    ('line-breaks', '<p>One<br>Two<br/>Three</p><hr>', 'Line breaks and rules.'),
]


def entry_of(name):
    return Ref('clean', 'http://clean.test/case/' + name, 'id')


def remember(c):
    r, payload = c.request('GET', f"feeds/{c.state['feed-clean']['feed_id']}/entries", params={'limit': 500})
    assert r.status_code == 200, 'entries unavailable'
    c.state['clean'] = {e['url']: e for e in payload['entries']}


# Cases whose stored content equals their (canonical) input: a server that stores content unchanged passes them.
KEPT_AS_IS = ('anchor-link', 'time', 'escaped-text', 'ruby', 'line-breaks')


def build(s):
    for user in CREDS:
        s.setup('accounts', 'me-' + user, 'GET', 'me', actor=user, save=user)
    fx.default_category(s, 'accounts')
    items = ''.join(f'<item><title>Case {name}</title><link>http://clean.test/case/{name}</link>'
                    f'<pubDate>Mon, 06 Jan 2025 10:00:00 GMT</pubDate><description>{escape(html)}</description></item>\n'
                    for name, html, _ in CASES)
    s.fixture('web', 'publish', fx.publish('http://clean.test/feed.xml', rss('Sanitizer cases', 'http://clean.test/',
                                                                            [items]), fx.RSS_TYPE))
    fx.subscribe(s, 'feed', 'subscribe', 'http://clean.test/feed.xml', 'feed-clean')
    s.fixture('feed', 'entries', remember)
    for name, _, description in CASES:
        s.api('sanitize', name, 'content', 'GET', pathref('entries/{id}', id=entry_of(name)),
              needs=['fx:accounts', 'fx:web', 'fx:feed'], view=pick('content'), description=description)
    # Markup that the sanitizer keeps as it is counts only with a case where it removes a script.
    for name in KEPT_AS_IS:
        s.bind(f'{s.prefix}api.sanitize.{name}.content', f'{s.prefix}api.sanitize.script.content')
