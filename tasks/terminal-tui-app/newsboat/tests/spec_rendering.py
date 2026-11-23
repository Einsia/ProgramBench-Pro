"""HTML-to-text exports, format expansions and long-list/pager behavior."""
from spec_common import (C, F, K, P, article, contains, cp, feed, file, focus, point, quote, scenarios, scr, episode)

HTML_CASES = [
    ('paragraphs','<p>First paragraph.</p><p>Second paragraph.</p>'),
    ('line-break','Before<br>After<br/>Last'),
    ('heading-one','<h1>Main heading</h1><p>Body text.</p>'),
    ('heading-two','<h2>Section heading</h2><p>Body text.</p>'),
    ('heading-three','<h3>Subsection heading</h3><p>Body text.</p>'),
    ('unordered-list','<ul><li>First item</li><li>Second item</li></ul>'),
    ('ordered-list','<ol><li>First item</li><li>Second item</li></ol>'),
    ('nested-list','<ul><li>Outer<ul><li>Inner</li></ul></li><li>Next</li></ul>'),
    ('definition-list','<dl><dt>Term</dt><dd>Definition</dd><dt>Next term</dt><dd>Next definition</dd></dl>'),
    ('blockquote','Before<blockquote>Quoted text<blockquote>Nested quote</blockquote></blockquote>After'),
    ('preformatted','<pre>  Indented\n    More indentation\n\nLast</pre>'),
    ('table','<table><tr><th>Left</th><th>Right</th></tr><tr><td>One</td><td>Two</td></tr></table>'),
    ('horizontal-rule','Before<hr>After'),
    ('image-alt','<img src="https://images.example/a.png" alt="A picture">'),
    ('image-no-alt','<img src="https://images.example/b.png">'),
    ('link','See <a href="https://links.example/a">this link</a>.'),
    ('duplicate-links','<a href="https://links.example/a">First</a> <a href="https://links.example/a">Second</a>'),
    ('link-relative','<a href="next.html">Next page</a>'),
    ('link-fragment','<a href="#part">Section</a>'),
    ('link-empty','<a href="https://links.example/empty"></a>After'),
    ('link-mailto','<a href="mailto:person@example.org">Email</a>'),
    ('link-image','<a href="https://links.example/full"><img src="https://images.example/thumb" alt="Thumbnail"></a>'),
    ('script-hidden','Before<script>hidden_script()</script>After'),
    ('style-hidden','Before<style>.hidden { color:red }</style>After'),
    ('comment-hidden','Before<!-- hidden comment -->After'),
    ('named-entities','&amp; &lt; &gt; &quot; &apos; &copy; &euro;'),
    ('numeric-entities','&#65; &#x3a9; &#128640;'),
    ('nbsp','One&nbsp;two&nbsp;&nbsp;three'),
    ('collapsed-whitespace','One    two\n   three\t four'),
    ('unicode','<p>中文，Café é and 🚀.</p>'),
    ('malformed-nesting','<p>Before <b>bold<i>inside</b> after</i> tail'),
    ('unknown-element','Before<unknown>Visible unknown content</unknown>After'),
    ('uppercase-tags','<P>Upper paragraph</P><UL><LI>Upper item</LI></UL>'),
    ('nested-blocks','<div>Outer<div>Inner<p>Paragraph</p></div>Last</div>'),
    ('escaped-markup','&lt;b&gt;Literal tags&lt;/b&gt;'),
    ('long-word','<p>'+('LongWord'*24)+'</p>'),
    ('form-controls','<form><label>Name:</label><input value="Alice"><textarea>Comment text</textarea></form>'),
]


def rich_home():
    content=('<h1>Reading notes</h1><p>Paragraph with a <a href="https://links.example/one">useful link</a>.</p>'
             '<ul><li>Alpha entry</li><li>Beta entry</li></ul><blockquote>Quoted passage</blockquote>'
             '<pre>  fixed indentation</pre><img src="https://images.example/picture" alt="Sample picture">')
    return F.home('file://feeds/rich.xml',{'rich.xml':F.rss('Reading Lab',[F.item('Rich document','rich',F.day(10),content)])})


def long_home():
    return F.home('file://feeds/long.xml',{'long.xml':F.rss('Long feed',[
        F.item(f'Article {i:02d}',f'long-{i}',F.day((i%28)+1),'\n'.join(f'<p>Paragraph {n:02d} with text to read.</p>' for n in range(1,81)))
        for i in range(1,76)])},'article-sort-order title-asc\n')


def build():
    out=[]
    items=[F.item(f'{i:02d} {name}',f'html-{i}',F.day(1),body) for i,(name,body) in enumerate(HTML_CASES,1)]
    files=F.home('file://feeds/html.xml',{'html.xml':F.rss('Rendering cases',items)},'article-sort-order title-asc\ntext-width 72\n')
    cps=[]
    for i,(name,_) in enumerate(HTML_CASES,1):
        cps.append(cp(name,'Export the rendered '+name+' article.',[C(str(i)),C('save '+name+'.txt')],
                      [point('text',file(name+'.txt','body-layout'),'The plain-text export renders the document semantics.')]))
    out.append(episode('render-html','html-rendering',cps,files=files,before=feed(0)))
    for name,format_name,identifiers,before in [
        ('feed','feedlist-format','ilLnStTuUc',[{'cli':['-I','partial-read.txt']},K('R'),{'wait':1.5}]),
        ('article','articlelist-format','aDfindFitLFe',feed(2)+[K('Control+e'),P('Ba'),K('N'),K('D'),K('Home')]),
        ('tag','selecttag-format','iTfnu',[K('t')])]:
        # Eliminate duplicate identifiers; one point is one named expansion in this context.
        cps=[]
        for token in dict.fromkeys(identifiers):
            cps.append(cp('field-'+token.lower()+('-upper' if token.isupper() else ''),'Display format expansion %'+token,
                          [C('set '+format_name+' '+quote('BEGIN%'+token+'END'))],
                          [point('expansion',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))]))
        files=F.library(**{'partial-read.txt':'t1\n'})
        if name=='feed':files['.newsboat/urls']+='file://feeds/missing.xml\n'
        if name=='article':files['feeds/cast.xml']=F.CAST.replace('</item>','<author>Podcast Host</author></item>')
        out.append(episode('format-'+name,'formatting',cps,before=before,files=files))
    for name,setting,tokens,before in [
        ('feeds','feedlist-title-format','TtuUF',[C('tag news'),K('F'),P('total_count > 2')]),
        ('articles','articlelist-title-format','TUutF',feed(0)+[K('F'),P('title =~ "kernel"')]),
        ('search','searchresult-title-format','sTUutF',[K('/'),P('kernel')]),
        ('reading','itemview-title-format','TFut',feed(0)+article(0))]:
        cps=[cp('field-'+token.lower()+('-upper' if token.isupper() else ''),'Expand %'+token+' in the title.',
                [C('set '+setting+' '+quote('BEGIN%'+token+'END'))],
                [point('expansion',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))]) for token in tokens]
        out.append(episode('format-title-'+name,'formatting',cps,before=before))
    cps=[]
    for name,fmt in [('literal-percent','%%|%t'),('right-padding','%-20t|'),('left-padding','%20t|'),
                     ('center','%=30t|'),('conditional-true','%?t?has-title&empty?'),
                     ('conditional-false','%?z?present&absent?'),('conditional-no-else','%?t?Title:%t?'),
                     ('unknown','%z|%t'),('nested','%?t?%?n?unread&read?&empty?')]:
        cps.append(cp(name,'Use format string '+fmt,[C('set feedlist-format '+quote('BEGIN'+fmt+'END'))],
                      [point('expansion',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))]))
    out.append(episode('format-syntax','formatting',cps))
    cps=[]
    for name,fmt in [('iso','%Y-%m-%d'),('weekday','%A'),('month','%B'),('time','%H:%M:%S'),
                     ('offset','%z'),('day-of-year','%j'),('epoch','%s'),('week','%U %W'),('literal','date:%%:%F')]:
        cps.append(cp(name,'Format the publication date as '+fmt,
                      [C('set datetime-format '+quote(fmt)),C('set articlelist-format "BEGIN%DEND"')],
                      [point('dates',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))]))
    out.append(episode('format-dates','formatting',cps,before=feed(0)))

    # A long list and long article make paging observably distinct from one-row movement.
    cases=[]
    names=[f'Article {i:02d}' for i in range(1,76)]
    for name,key,goal,before in [
        ('page-down','PageDown','Bring Article 34 into view and select it.',feed(0)),
        ('page-up','PageUp','Bring Article 42 into view and select it.',feed(0)+[K('End')]),
        ('half-page','exec halfpagedown','Select Article 18 in the article list.',feed(0)),
        ('long-last','End','Select the final article in the long feed.',feed(0)),
        ('number-60','60','Select article number 60.',feed(0)),
    ]:
        steps=[C(key)] if key.startswith('exec') or key.isdigit() else [K(key)]
        cases.append((cp(name,goal,steps,[point('focus',focus(names))],goal),long_home(),before))
    for name,steps,before,goal in [
        ('pager-down',[K('PageDown')],feed(0)+article(0),'Bring paragraph 20 of the open article into view.'),
        ('pager-end',[K('End')],feed(0)+article(0),'Move to the end of the open article.'),
        ('pager-home',[K('Home')],feed(0)+article(0)+[K('End')],'Return to the beginning of the open article.'),
    ]:
        needle={'pager-down':'Paragraph 20','pager-end':'Paragraph 80','pager-home':'Paragraph 01'}[name]
        cases.append((cp(name,goal,steps,[point('paragraphs',contains(needle))],goal),long_home(),before))
    out.extend(scenarios('gui-paging','navigation',cases,gui=True))
    cases=[]
    for name,setting,fmt,before,needles,goal in [
        ('feed-rss-urls','feedlist-format','%t | %L',[],['file://feeds/tech.xml','file://feeds/food.xml'],'Show the subscription URLs beside the feed titles.'),
        ('feed-counts','feedlist-format','%t | unread:%U total:%c',[],['unread:4 total:4'],'Show unread and total article counts next to each feed.'),
        ('feed-tags','feedlist-format','%t | %T',[],['tech','food','audio'],'Show each feed’s first tag beside its title.'),
        ('feed-links','feedlist-format','%t | %l',[],['http://tech.example/'],'Show website links beside feed titles.'),
        ('article-authors','articlelist-format','%t | %a',feed(0),['Linus','Miguel','Ted'],'Show author names beside article titles.'),
        ('article-date','datetime-format','%Y-%m-%d',feed(0),['2024-01-09','2024-01-03'],'Show article dates as YYYY-MM-DD.'),
        ('article-flags','articlelist-format','%t | flags:%F',feed(0)+[K('Control+e'),P('ab')],['flags:ab'],'Show the article flag letters beside its title.'),
        ('article-enclosure','articlelist-format','%t | %e',feed(2),['http://cast.example/ep2.mp3'],'Show enclosure URLs beside podcast titles.'),
        ('feed-title','feedlist-title-format','Library: %t feeds, %U unread',[],['Library: 3 feeds, 9 unread'],'Set the subscription title to Library: followed by feed and unread-article counts.'),
        ('article-title','articlelist-title-format','Now listing %T',feed(0),['Now listing Tech Daily'],'Set the article-list title to Now listing followed by the feed title.'),
        ('tag-counts','selecttag-format','%T | feeds:%u articles:%n',[K('t')],['news','feeds:2'],'Show the feed and article counts in the tag selector.'),
    ]:
        steps=[C('set '+setting+' '+quote(fmt))]
        check = contains(*needles)
        files=F.library()
        if name == 'feed-counts':
            files=F.library('feedlist-format "%t"\n',**{'read.txt':'t1\nf1\nf2\n'})
            before=[{'cli':['-I','read.txt']}]
            check = scr('counts',labels=F.FEED_TITLES,expected={'counts':{'Tech Daily':[3,4],'Food Notes':[1,3],'Audio Cast':[2,2]}})
        elif name == 'tag-counts':
            check = scr('tag-counts',labels=['audio','food','news','tech'],expected={'counts':{'audio':[1,2],'food':[1,3],'news':[2,6],'tech':[1,4]}})
        elif name == 'article-flags':
            check = scr('row-token',label='Filesystem benchmarks',token='ab',expected={'visible':True})
        elif name == 'article-title':
            check = scr('title-parts',parts=['Now listing','Tech Daily'],
                        expected={'parts':['Now listing','Tech Daily']})
        cases.append((cp(name,goal,steps,[point('visible',check)],goal),files,before))
    out.extend(scenarios('gui-format','formatting',cases,gui=True))
    cases=[]
    for name,goal,steps,needles in [
        ('rich-article','Open the rich document for reading.',[K('Enter')],['Reading notes','Alpha entry','Beta entry']),
        ('rich-links','Inspect the links from the rich document.',[K('Enter'),K('u')],['https://links.example/one','https://images.example/picture']),
        ('rich-source','Inspect the HTML source of the rich document.',[K('Enter'),K('Control+u')],['<h1>Reading notes</h1>']),
    ]:
        cases.append((cp(name,goal,steps,[point('content',contains(*needles))],goal),rich_home(),feed(0)))
    out.extend(scenarios('gui-html','html-rendering',cases,gui=True))
    return out
