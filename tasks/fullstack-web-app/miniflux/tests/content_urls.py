"""Entry URLs: removal of tracking parameters (by name, by prefix, outbound ref parameters), URLs left alone, and
the URL rewrite rules of a feed. Each case is a feed whose entry URL exercises one rule; the observation is the
stored entry URL."""
from xml.sax.saxutils import escape

from parsing import build_cases

DATE = 'Mon, 06 Jan 2025 10:00:00 GMT'


def doc(link, site='http://urls.test/'):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>URL fixture</title>'
            f'<link>{site}</link><item><title>URL case</title><link>{escape(link)}</link><pubDate>{DATE}</pubDate>'
            '<description>Body</description></item></channel></rss>\n')


U = ('url',)
CLEANING = [
    ('utm', 'http://urls.test/a?utm_source=rss&utm_medium=feed&utm_campaign=x&id=7',
     'utm_ tracking parameters are removed from entry URLs.'),
    ('only-trackers', 'http://urls.test/b?utm_source=rss&fbclid=abc', 'A URL with only trackers loses its query.'),
    ('click-ids', 'http://urls.test/c?gclid=1&msclkid=2&yclid=3&twclid=4&page=2', 'Ad click identifiers are removed.'),
    ('mailchimp', 'http://urls.test/d?mc_cid=1&mc_eid=2&keep=yes', 'Mailchimp identifiers are removed.'),
    ('hubspot', 'http://urls.test/e?_hsenc=x&_hsmi=y&__hstc=z&q=search', 'HubSpot parameters are removed.'),
    ('matomo-prefix', 'http://urls.test/f?mtm_campaign=x&mtm_kwd=y&lang=en', 'mtm_ parameters are removed.'),
    ('case', 'http://urls.test/g?UTM_SOURCE=rss&Fbclid=x&Page=1', 'Parameter names are compared without case.'),
    ('ref-same-site', 'http://urls.test/h?ref=urls.test&x=1', 'A ref parameter naming the feed\'s own site.'),
    ('ref-other', 'http://other.test/i?ref=somewhere.test&x=1', 'A ref parameter naming another site.'),
    ('no-query', 'http://urls.test/j/plain-path', 'A URL without query is unchanged.'),
    ('fragment', 'http://urls.test/k?utm_source=x&id=3#section-2', 'The fragment survives the cleaning.'),
    ('order', 'http://urls.test/l?zeta=1&alpha=2&utm_term=x', 'The remaining parameters after cleaning.'),
    ('encoded', 'http://urls.test/m?q=caf%C3%A9+au+lait&utm_source=x', 'Encoded values survive the cleaning.'),
]
REWRITES = [
    ('rewrite-host', 'rewrite("^http://urls.test/(.*)$"|"http://mirror.test/$1")', 'http://urls.test/story/1',
     'A URL rewrite rule moves entries to another host.'),
    ('rewrite-path', 'rewrite("/amp/"|"/")', 'http://urls.test/amp/story/2', 'A URL rewrite rule edits the path.'),
    ('rewrite-no-match', 'rewrite("^https://nomatch/(.*)$"|"x")', 'http://urls.test/story/3',
     'A URL rewrite rule that does not match leaves the URL.'),
]


def build(s):
    cases = [(f'{name}.xml', doc(link), U, (), False, description) for name, link, description in CLEANING]
    cases += [(f'{name}.xml', doc(link), U, (), False, description) for name, _, link, description in REWRITES]
    build_cases(s, 'urls.test', cases, 'application/rss+xml', options={
        f'{name}.xml': {'urlrewrite_rules': rule} for name, rule, *_ in REWRITES})
    # URLs left unchanged count only with a case where the product changes the URL.
    parsed = lambda name: f'{s.prefix}api.parse.{name}.subscribe'
    for name in ('ref-other', 'no-query'):
        s.bind(parsed(name), parsed('utm'))
    s.bind(parsed('rewrite-no-match'), parsed('rewrite-host'))
