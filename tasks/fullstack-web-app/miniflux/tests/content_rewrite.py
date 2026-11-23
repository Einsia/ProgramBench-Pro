"""Content rewrite rules: every rule of a feed's rewrite_rules, combined rules, and the rules the product applies
by itself to entries of well-known sites. Each case is a feed subscribed with its rules; the observation is the
stored title and content of its entry."""
from xml.sax.saxutils import escape

from parsing import build_cases

DATE = 'Mon, 06 Jan 2025 10:00:00 GMT'


def doc(content, link='http://rewrite.test/entry', title='Rewrite case', extra=''):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Rewrite fixture</title>'
            f'<link>http://rewrite.test/</link><item><title>{escape(title)}</title><link>{link}</link><pubDate>{DATE}'
            f'</pubDate><description>{escape(content)}</description>{extra}</item></channel></rss>\n')


C = ('title', 'content')
# (name, rules, content, entry URL, title, extra item XML, description)
RULES = [
    ('add-image-title', 'add_image_title', '<img src="http://img.test/comic.png" title="The hover joke" alt="Comic">',
     None, None, '', 'add_image_title shows an image\'s title below it.'),
    ('add-mailto-subject', 'add_mailto_subject', '<a href="mailto:hi@example.test?subject=Hello%20from%20feed">mail</a>',
     None, None, '', 'add_mailto_subject shows the subject of a mailto link.'),
    ('add-dynamic-image', 'add_dynamic_image', '<img src="http://img.test/placeholder.gif" '
                                               'data-src="http://img.test/real.jpg" alt="lazy">',
     None, None, '', 'add_dynamic_image uses the lazily loaded image address.'),
    ('add-dynamic-image-srcset', 'add_dynamic_image', '<img data-srcset="http://img.test/a.jpg 1x, http://img.test/b.jpg 2x">',
     None, None, '', 'add_dynamic_image uses a lazily loaded srcset.'),
    ('add-dynamic-iframe', 'add_dynamic_iframe', '<iframe data-src="https://www.youtube.com/embed/xyz987"></iframe>',
     None, None, '', 'add_dynamic_iframe uses the lazily loaded iframe address.'),
    ('add-youtube-video', 'add_youtube_video', '<p>Video description</p>', 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
     None, '', 'add_youtube_video embeds the video of a YouTube watch URL.'),
    ('add-invidious-video', 'add_invidious_video', '<p>Invidious</p>', 'https://www.youtube.com/watch?v=aBcDeFgHiJk&t=30',
     None, '', 'add_invidious_video embeds the video through the Invidious instance.'),
    ('add-youtube-from-id', 'add_youtube_video_from_id',
     '<div class="video" data-config=\'{"youtube_id": "ZyXwVuTsRqP"}\'>Player</div><p>Text</p>', None, None, '',
     'add_youtube_video_from_id embeds videos referenced by id in the content.'),
    ('add-pdf-link', 'add_pdf_download_link', '<p>Paper abstract</p>', 'http://rewrite.test/papers/study.pdf', None,
     '', 'add_pdf_download_link links the PDF of a PDF entry.'),
    ('nl2br', 'nl2br', 'Line one\nLine two\nLine three', None, None, '', 'nl2br turns new lines into line breaks.'),
    ('convert-text-link', 'convert_text_link', 'Visit https://site.example.test/page?x=1 for details.', None, None, '',
     'convert_text_link turns URLs in text into links.'),
    ('fix-medium-images', 'fix_medium_images',
     '<figure class="paragraph-image"><img src="http://img.test/blur.jpg"><noscript>&lt;img src="http://img.test/'
     'full.jpg"&gt;</noscript></figure>', None, None, '', 'fix_medium_images uses the noscript image of a figure.'),
    ('use-noscript-images', 'use_noscript_figure_images',
     '<figure><img src="http://img.test/low.jpg"><noscript>&lt;img src="http://img.test/high.jpg"&gt;</noscript>'
     '<figcaption>Cap</figcaption></figure>', None, None, '', 'use_noscript_figure_images prefers noscript images.'),
    ('replace', 'replace("cat|kitten"|"dog")', '<p>The cat met a kitten.</p>', None, None, '',
     'replace substitutes a regular expression in the content.'),
    ('replace-groups', 'replace("(\\\\d+) points"|"$1 pts")', '<p>Scored 42 points and 7 points.</p>', None, None, '',
     'replace with capture groups.'),
    ('replace-title', 'replace_title("\\\\[Sponsored\\\\] "|"")', '<p>Body</p>', None, '[Sponsored] Great product', '',
     'replace_title substitutes a regular expression in the title.'),
    ('remove', 'remove(".ad, #banner")', '<p>Story</p><div class="ad">Buy now</div><p id="banner">Banner</p><p>End</p>',
     None, None, '', 'remove deletes the elements matching a selector.'),
    ('remove-nested', 'remove("div.share a")', '<div class="share"><a href="http://x.test/">share</a> text</div>',
     None, None, '', 'remove with a descendant selector.'),
    ('base64-decode', 'base64_decode(".enc")', '<p class="enc">SGlkZGVuIG1lc3NhZ2U=</p><p>Plain</p>', None, None, '',
     'base64_decode decodes the text of the selected elements.'),
    ('remove-tables', 'remove_tables', '<table><tr><td>Cell A</td><td>Cell B</td></tr></table><p>After</p>', None,
     None, '', 'remove_tables replaces tables with their content.'),
    ('remove-clickbait', 'remove_clickbait', '<p>Body</p>', None, 'YOU WON\'T BELIEVE WHAT HAPPENED NEXT', '',
     'remove_clickbait changes an all-capitals title.'),
    ('add-hn-links-hack', 'add_hn_links_using_hack',
     '<a href="https://news.ycombinator.com/item?id=4242">Comments</a>', None, None, '',
     'add_hn_links_using_hack adds a Hack app link to Hacker News links.'),
    ('add-hn-links-opener', 'add_hn_links_using_opener',
     '<a href="https://news.ycombinator.com/item?id=4343">Comments</a>', None, None, '',
     'add_hn_links_using_opener adds an Opener link to Hacker News links.'),
    ('fix-ghost-cards', 'fix_ghost_cards',
     '<figure class="kg-card kg-bookmark-card"><a class="kg-bookmark-container" href="http://ghost.test/post">'
     '<div class="kg-bookmark-title">Linked post</div><div class="kg-bookmark-author">Writer</div></a></figure>',
     None, None, '', 'fix_ghost_cards turns Ghost bookmark cards into links.'),
    ('remove-img-blur', 'remove_img_blur_params', '<img src="http://img.test/photo.jpg?blur=20&amp;w=40">', None, None,
     '', 'remove_img_blur_params drops the query of blurred placeholder images.'),
    ('add-castopod', 'add_castopod_episode', '<p>Episode notes</p>', 'http://castopod.test/@show/episodes/one', None,
     '', 'add_castopod_episode embeds the Castopod player.'),
    ('add-enclosure-links', 'add_enclosure_links', '<p>Notes</p>', None, None,
     '<enclosure url="http://media.test/ep.mp3" length="10" type="audio/mpeg"/>',
     'add_enclosure_links lists the enclosures under the content.'),
    ('combined', 'nl2br, remove(".drop")', 'One\nTwo<span class="drop">x</span>', None, None, '',
     'Several rules separated by commas apply in turn.'),
]
DOMAINS = [
    ('site-xkcd', '<img src="http://imgs.xkcd.test/comic.png" title="Alt text of the comic">', 'https://xkcd.com/3000/',
     'Entries of xkcd.com get their image titles shown without any rule.'),
    ('site-youtube', '<p>Channel upload</p>', 'https://www.youtube.com/watch?v=Qwerty12345',
     'Entries of youtube.com get the video embedded without any rule.'),
]


def build(s):
    cases = []
    for name, rules, content, link, title, extra, description in RULES:
        cases.append((f'{name}.xml', doc(content, link or 'http://rewrite.test/entry', title or 'Rewrite case', extra),
                      C, (), False, description))
    for name, content, link, description in DOMAINS:
        cases.append((f'{name}.xml', doc(content, link), C, (), False, description))
    build_cases(s, 'rewrite.test', cases, 'application/rss+xml', options={
        f'{name}.xml': {'rewrite_rules': rules} for name, rules, *_ in RULES})
