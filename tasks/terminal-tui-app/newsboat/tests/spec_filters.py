"""Filters, query feeds, tags, search and killfile rules."""
from spec_common import (C, F, K, P, cache, cp, feed, labels, point, quote, scr, slug, episode)

def query_urls(name, expression):
    return F.LIB_URLS + quote('query:'+name+':'+expression) + '\n'


def filter_cases():
    rows=[]
    def add(name, expression):
        rows.append((name, expression))
    for attr, value, regex in [
        ('title', 'Rust in the kernel', 'kernel'), ('author', 'Julia', 'linus'),
        ('link', 'http://example.com/t1', '/t[12]$'), ('guid', 't1', '^[tf]'),
        ('feedtitle', 'Tech Daily', 'notes'),
        ('feedlink', 'http://food.example/', 'tech'), ('rssurl', 'file://feeds/tech.xml', 'food'),
        ('enclosure_type', 'audio/mpeg', '^audio/'), ('enclosure_url', 'http://cast.example/ep1.mp3', 'ep[12]'),
        ('content', '<p>Flour, water, salt.</p>', 'kernel'), ('date', 'Wed, 03 Jan 2024 10:00:00 +0000', 'Jan 2024'),
        ('unread', 'yes', '^yes$'), ('flags', 'Bax', 'a')]:
        for op, suffix, operand in [('=', 'equal', value), ('!=', 'not-equal', value),
                                     ('=~', 'regex', regex), ('!~', 'not-regex', regex)]:
            add(attr+'-'+suffix, f'{attr} {op} {quote(operand)}')
    for attr, value in [('total_count',3),('unread_count',2),('articleindex',4),('feedindex',2)]:
        for op,suffix in [('=','equal'),('!=','not-equal'),('<','less'),('>','greater'),('<=','at-most'),('>=','at-least')]:
            add(attr+'-'+suffix,f'{attr} {op} {value}')
        add(attr+'-range',f'{attr} between {value-1}:{value+1}')
        add(attr+'-single-range',f'{attr} between {value}:{value}')
    for name, expression in [
        ('tag-membership','tags # "news"'),('tag-not-member','tags !# "news"'),
        ('tag-whole-word','tags # "new"'),('tag-regex','tags =~ "audio|food"'),
        ('equality-alias','guid == "t2"'),('regex-case','title =~ "KERNEL"'),
        ('regex-anchor','title =~ "^Kernel"'),('regex-alternation','title =~ "Rust|Bread"'),
        ('regex-dot','guid =~ "^[tc][12]$"'),('regex-quantifier','title =~ "[a-z]+ [0-9]"'),
        ('regex-escaped-dot','link =~ "example\\.com/f"'),
        ('empty-string','enclosure_type = ""'),('empty-regex','title =~ ""'),
        ('and','tags # "news" and unread = "yes"'),('or','guid = "f1" or guid = "t1"'),
        ('and-precedence','guid = "f1" or guid = "t1" and unread = "no"'),
        ('grouped-or','(guid = "f1" or guid = "t1") and unread = "yes"'),
        ('nested','((tags # "tech" and title =~ "kernel") or (tags # "food" and author = "Julia"))'),
        ('spaces','  title   =~   "kernel"  '),('tabs','title\t=~\t"kernel"'),
        ('zero-range','articleindex between 0:0'),('reverse-range','articleindex between 8:2'),
    ]:
        if '\t' not in expression:  # terminal literal input rejects control characters
            add(name,expression)
    return rows


def filtersteps(expr):
    return [K('Control+f'),K('F'),K('Control+u'),P(expr)]


def build():
    out=[]
    files=F.library(urls=query_urls('All articles','title =~ "."'), **{'read.txt':'t1\nf2\n'})
    prep=[{'cli':['-I','read.txt']}] + feed(0)+[K('Control+e'),P('xBa'),K('q')]+feed(3)
    cps=[]
    for name, expression in filter_cases():
        cps.append(cp(name,'Filter articles with '+expression,filtersteps(expression),
                      [point('members',labels(unordered=True), 'The filter returns exactly the matching articles.')]))
    out.append(episode('filter-articles','filters',cps,files=files,before=prep))
    cps=[]
    for attr,val,regex in [('feedtitle','Food Notes','daily'),
                          ('feedlink','http://tech.example/','food'),('rssurl','file://feeds/food.xml','cast')]:
        for op,suffix,operand in [('=','equal',val),('!=','not-equal',val),('=~','regex',regex),('!~','not-regex',regex)]:
            expr=f'{attr} {op} {quote(operand)}'
            cps.append(cp(attr+'-'+suffix,'Filter feeds with '+expr,filtersteps(expr),[point('feeds',labels(F.FEED_TITLES,unordered=True))]))
    for attr in ['total_count','unread_count','feedindex']:
        for op,suffix in [('=','equal'),('!=','not-equal'),('<','less'),('>','greater'),('<=','at-most'),('>=','at-least'),('between','range')]:
            expr=f'{attr} {op} '+('2:3' if op=='between' else '2')
            cps.append(cp(attr+'-'+suffix,'Filter feeds with '+expr,filtersteps(expr),[point('feeds',labels(F.FEED_TITLES,unordered=True))]))
    for name,expr in [('tag','tags # "news"'),('not-tag','tags !# "news"'),('word-boundary','tags # "new"'),
                     ('logical-and','tags # "news" and total_count > 2'),('logical-or','tags # "food" or tags # "audio"'),
                     ('grouping','(total_count = 4 or total_count = 3) and tags # "news"')]:
        cps.append(cp(name,'Filter feeds with '+expr,filtersteps(expr),[point('feeds',labels(F.FEED_TITLES,unordered=True))]))
    filter_feed_files=F.library(**{'read.txt':'t1\nt2\nt3\nf1\nc1\nc2\n'})
    out.append(episode('filter-feeds','filters',cps,files=filter_feed_files,before=[{'cli':['-I','read.txt']}]))
    invalid=['title =', 'title ??? "a"', '((title = "a")', 'rssurl =~ "["', 'unread_count between a:b',
             'title = "unclosed', 'noattribute = "yes"', 'title = "a" trailing']
    cps=[]
    for i, expr in enumerate(invalid):
        cps.append(cp('invalid-'+str(i+1),'Handle invalid filter '+expr,filtersteps(expr),
                      [point('feedback',scr('message',nonempty=True)),point('retained-list',labels(F.FEED_TITLES))]))
    out.append(episode('filter-invalid','filters',cps))

    queries=[('Unread','unread = "yes"'),('Read','unread = "no"'),('Kernel','title =~ "kernel"'),
             ('Tagged','tags # "food"'),('Podcast','enclosure_type = "audio/mpeg"'),('Flags','flags =~ "a"'),
             ('Author','author =~ "Julia"'),('Combined','(tags # "news" and unread = "no") or guid = "f1"'),
             ('Length','content =~ "btrfs"'),('No matches','guid = "missing"'),
             ('Feed count','total_count >= 3'),('Feed url','rssurl =~ "food"')]
    for name,expr in queries:
        files=F.library(urls=query_urls(name,expr),**{'read.txt':'t1\nf2\n'})
        cps=[cp('contents','Open query feed '+name,feed(3),[point('members',labels(unordered=True))])]
        out.append(episode('query-'+slug(name),'query-feeds',cps,files=files,before=
                            [{'cli':['-I','read.txt']}]+feed(0)+[K('Control+e'),P('xBa'),K('q')]))
    for mode in ['download','display']:
        for name,scope,expr in [('global','*','title =~ "kernel"'),('feed','file://feeds/food.xml','author = "Julia"'),
                               ('regex','regex:.*tech.*','guid = "t3"'),('regex-case','regex:.*FOOD.*','title =~ "soup"'),
                               ('podcast','*','enclosure_type = "audio/mpeg"'),('no-match','*','title = "Missing"')]:
            conf=f'ignore-mode {mode}\nignore-article {quote(scope)} {quote(expr)}\n'
            cps=[cp('cache','Inspect the cache after loading with the ignore rule.',[],
                    [point('stored',cache('guid title',nonempty=True))]),
                 cp('tech','Inspect visible Tech Daily articles.',feed(0),[point('visible',labels())]),
                 cp('food','Inspect visible Food Notes articles.',[K('q')]+feed(1),[point('visible',labels())],depends=['tech']),
                 cp('cast','Inspect visible Audio Cast articles.',[K('q')]+feed(2),[point('visible',labels())],depends=['food'])]
            out.append(episode('ignore-'+mode+'-'+name,'killfiles',cps,files=F.library(conf)))
    cps=[]
    for tag in ['news','food','audio','tech','missing']:
        cps.append(cp(tag,'Select tag '+tag,[K('Control+t'),C('tag '+tag)],
                      [point('feeds',labels(F.FEED_TITLES,unordered=True))]))
    cps.append(cp('clear','Clear the active tag.',[K('Control+t')],[point('feeds',labels(F.FEED_TITLES))]))
    out.append(episode('tags-command','tags',cps))
    cps=[]
    for i,text in enumerate(['kernel','KERNEL','Julia','btrfs','<p>','example','Rust support','missing phrase','noodles']):
        # Start each search from a new feed list; results include article titles, authors and content.
        cps.append(cp('search-'+str(i+1),'Search the library for '+text,[{'restart':True},K('/'),P(text)],
                      [point('results',labels(unordered=True))]))
    out.append(episode('search-global','search',cps))
    return out
