"""OPML, read-state interchange, cache updates, cleanup and output files."""
from spec_common import (F, K, P, article, cache, cli, cp, feed, file, point, quote, scenarios, scr, slug, episode)


def opml(body,version='2.0',head='<title>Subscriptions</title>'):
    return '<?xml version="1.0"?><opml version="'+version+'"><head>'+head+'</head><body>'+body+'</body></opml>'


def build():
    out=[]
    cases=[]
    outline='<outline type="rss" text="New feed" xmlUrl="https://new.example/rss"/>'
    for name,body in [
        ('basic',outline),('title-only','<outline type="rss" title="Title only" xmlUrl="https://new.example/rss"/>'),
        ('text-title','<outline type="rss" text="Text name" title="Title name" xmlUrl="https://new.example/rss"/>'),
        ('without-type','<outline text="No type" xmlUrl="https://new.example/rss"/>'),
        ('without-title','<outline type="rss" xmlUrl="https://new.example/rss"/>'),
        ('html-url','<outline type="rss" text="Homepage" xmlUrl="https://new.example/rss" htmlUrl="https://new.example/"/>'),
        ('category','<outline type="rss" text="Category" xmlUrl="https://new.example/rss" category="news,tech"/>'),
        ('category-space','<outline type="rss" text="Category" xmlUrl="https://new.example/rss" category="news, tech"/>'),
        ('entities','<outline type="rss" text="Fish &amp; Chips" xmlUrl="https://new.example/rss?a=1&amp;b=2"/>'),
        ('unicode','<outline type="rss" text="世界 Café" xmlUrl="https://new.example/rss"/>'),
        ('quoted-title','<outline type="rss" text="A &quot;quote&quot;" xmlUrl="https://new.example/rss"/>'),
        ('folder','<outline text="Folder">'+outline+'</outline>'),
        ('nested-folder','<outline text="Outer"><outline text="Inner">'+outline+'</outline></outline>'),
        ('folder-title','<outline title="Folder title">'+outline+'</outline>'),
        ('empty-folder','<outline text="Empty"/>'+outline),
        ('sibling-folders','<outline text="A">'+outline+'</outline><outline text="B">'
                           '<outline type="rss" text="Second" xmlUrl="https://second.example/rss"/></outline>'),
        ('duplicate-existing','<outline type="rss" text="Renamed existing" xmlUrl="file://feeds/tech.xml"/>'+outline),
        ('duplicate-in-file',outline+outline),
        ('duplicate-new-title',outline+'<outline type="rss" text="Other name" xmlUrl="https://new.example/rss"/>'),
        ('file-url','<outline type="rss" text="Local feed" xmlUrl="file://feeds/local.xml"/>'),
        ('http-url','<outline type="rss" text="HTTP feed" xmlUrl="http://plain.example/rss"/>'),
        ('missing-url','<outline type="rss" text="Missing URL"/>'+outline),
        ('empty-url','<outline type="rss" text="Empty URL" xmlUrl=""/>'+outline),
        ('unsupported-schema','<outline type="rss" text="Unknown schema" xmlUrl="custom:feed"/>'+outline),
        ('unknown-attribute','<outline type="rss" text="Extra attribute" xmlUrl="https://new.example/rss" extra="ignored"/>'),
        ('comments','<!-- A comment -->'+outline),
    ]:
        files=F.library(**{'import.opml':opml(body)})
        c=cp(name,'Import the '+name+' OPML document.',[{'cli':['-i','import.opml']}],
             [point('subscriptions',file('.newsboat/urls','urls'),'The OPML input produces the expected subscriptions and tags.'),
              point('export',cli(['--export-to-opml2'],'opml'),'The imported subscriptions export as OPML 2.0.')])
        cases.append((c,files,[]))
    for version in ['1.0','1.1']:
        files=F.library(**{'import.opml':opml(outline,version)})
        c=cp('version-'+slug(version),'Import OPML '+version+'.',[{'cli':['--import-from-opml','import.opml']}],
             [point('subscriptions',file('.newsboat/urls','urls')),point('export',cli(['-e'],'opml'))])
        cases.append((c,files,[]))
    out.extend(scenarios('opml-import','opml',cases,chunk=7))
    cases=[]
    for name,text in [('malformed','<opml><body>'),('wrong-root','<html>Not OPML</html>'),
                      ('no-body','<opml version="2.0"><head><title>Empty</title></head></opml>'),
                      ('empty-body',opml('')),('plain-text','not xml')]:
        files=F.library(**{'bad.opml':text})
        c=cp(name,'Handle an invalid or empty OPML document.',[],
             [point('status',cli(['-i','bad.opml'],'exit')),point('subscriptions',file('.newsboat/urls','urls'))])
        cases.append((c,files,[]))
    out.extend(scenarios('opml-input-boundaries','opml',cases))
    for version,flag in [('1','-e'),('2','--export-to-opml2')]:
        files=F.library(urls=F.LIB_URLS+'"query:Unread:unread = \\"yes\\""\n')
        out.append(episode('opml-export-'+version,'opml',[
            cp('export','Export subscriptions as OPML '+version+'.',[],[point('document',cli([flag],'opml'))])],files=files))

    cps=[]
    for name,content in [('one','t1\n'),('several','t2\nf1\nc1\n'),('duplicates','t1\nt1\n'),
                         ('unknown','not-present\n'),('blank-lines','\nt3\n\n'),('crlf','t4\r\nf3\r\n'),
                         ('no-newline','c2')]:
        path='read-'+name+'.txt'
        cps.append(cp(name,'Import read-state identifiers from '+path,[{'cli':['-I',path]}],
                      [point('states',cache('guid unread')),point('count',cli(['-x','print-unread']))]))
    files=F.library(**{'read-'+name+'.txt':content for name,content in [
        ('one','t1\n'),('several','t2\nf1\nc1\n'),('duplicates','t1\nt1\n'),('unknown','not-present\n'),
        ('blank-lines','\nt3\n\n'),('crlf','t4\r\nf3\r\n'),('no-newline','c2')]})
    # Each imported read set is cumulative, so declare state dependencies explicitly.
    for prev,c in zip(cps,cps[1:]):c['depends_on'].append(prev['id'])
    cps.append(cp('export','Export the accumulated read-state identifiers.',[{'cli':['-E','read-export.txt']}],
                  [point('guids',file('read-export.txt','sorted'))],depends=[cps[-1]['id']]))
    cps.append(cp('restart','Keep read states after restart.',[{'restart':True}],
                  [point('states',cache('guid unread'))],depends=['export']))
    out.append(episode('read-state-interchange','persistence',cps,files=files))

    prepare=feed(0)+[K('Control+e'),P('aB'),K('N'),K('Home'),K('D'),K('q')]+feed(2)+[K('e'),K('q')]
    fields=['unread','flags','deleted','enqueued']
    cps=[cp('persist','Retain article states after restarting.',[{'restart':True}],
            [point(field,cache('guid '+field)) for field in fields]),
         cp('reload','Retain article states when the unchanged feeds are reloaded.',[{'cli':['-x','reload']}],
            [point(field,cache('guid '+field)) for field in fields],depends=['persist'])]
    out.append(episode('cache-state-persistence','persistence',cps,before=prepare))

    revised=F.rss('Tech Revised',[
        F.item('Filesystem benchmarks updated','t4',F.day(12),'<p>Updated body.</p>',creator='New Writer'),
        F.item('New article','t5',F.day(13),'<p>Fresh body.</p>',creator='New Writer')],link='https://revised.example/')
    cps=[cp('update','Reload a modified feed with a changed article and a new article.',
            [{'place':{'feeds/tech.xml':revised}},{'cli':['-x','reload']}],
            [point('title',cache('title',{'guid':'t4'})),point('author',cache('author',{'guid':'t4'})),
             point('content',cache('content',{'guid':'t4'})),point('date',cache('pubDate',{'guid':'t4'})),
             point('read',cache('unread',{'guid':'t4'})),point('flags',cache('flags',{'guid':'t4'})),
             point('new',cache('title unread',{'guid':'t5'},nonempty=True)),
             point('removed-kept',cache('guid title',{'feedurl':F.FEEDURL['Tech Daily']})),
             point('feed-title',cache('title',{'rssurl':F.FEEDURL['Tech Daily']},'rss_feed')),
             point('feed-link',cache('url',{'rssurl':F.FEEDURL['Tech Daily']},'rss_feed'))]),
         cp('repeat','Reload the revised feed again without adding duplicates.',[{'cli':['-x','reload']}],
            [point('articles',cache('guid title',{'feedurl':F.FEEDURL['Tech Daily']}))],depends=['update']),
         cp('malformed','Retain cached articles when the feed document is malformed.',
            [{'place':{'feeds/tech.xml':'<rss><broken>'}},{'cli':['-x','reload']}],
            [point('articles',cache('guid title content',{'feedurl':F.FEEDURL['Tech Daily']}))],depends=['repeat'])]
    out.append(episode('cache-feed-updates','cache-updates',cps,
                        before=feed(0)+[K('Control+e'),P('a'),K('Enter'),K('q'),K('q')]))

    cases=[]
    for value in [0,1,3]:
        c=cp('max-'+str(value),'Limit cached items per feed to '+str(value)+'.',[],
             [point('items',cache('guid title')),point('counts',scr('counts',labels=F.FEED_TITLES))])
        cases.append((c,F.library('max-items '+str(value)+'\n'),[]))
    for name,conf,before in [
        ('read-cleanup','cleanup-on-quit yes\ndelete-read-articles-on-quit yes\n',feed(0)+article(0)+[K('q'),K('q')]),
        ('normal-cleanup','cleanup-on-quit yes\n',feed(0)+article(0)+[K('q'),K('q')]),
    ]:
        c=cp(name,'Clean up the cache after reading an article.',[{'cli':['--cleanup']}],[point('remaining',cache('guid unread deleted'))])
        cases.append((c,F.library(conf),before))
    out.extend(scenarios('cache-retention','cache-updates',cases))
    out.append(episode('cache-unsubscribe','cache-updates',[
        cp('unsubscribe','Remove Food Notes from the subscription list and clean up its cached articles.',
           [{'place':{'.newsboat/urls':'file://feeds/tech.xml\nfile://feeds/cast.xml\n'}},{'cli':['--cleanup']}],
           [point('feeds',cache('rssurl title',table='rss_feed')),point('articles',cache('guid feedurl'))]),
        cp('vacuum','Vacuum the retained cache.',[{'cli':['-X']}],
           [point('articles',cache('guid title unread'))],depends=['unsubscribe'])]))

    cases=[]
    for name,fmt in [('url','%u'),('feed','%n/%u'),('title','%t.%e'),('feed-title','%n-%t.%e'),
                     ('date','%F-%u'),('year-month','%Y/%m/%u'),('day-time','%d-%H-%M-%S.%e'),
                     ('host','%h-%u'),('short-year','%y-%b-%u')]:
        points=[point('queue',file('.newsboat/queue'))]
        if name == 'url':
            points.append(point('enqueued',cache('enqueued',{'guid':'c2'})))
        c=cp(name,'Queue the episode with download filename format '+fmt,[K('e')],points)
        cases.append((c,F.library('download-filename-format '+quote(fmt)+'\n'),feed(2)))
    out.extend(scenarios('podcast-filenames','podcasts',cases))
    out.append(episode('podcast-auto','podcasts',[
        cp('auto','Automatically queue all enclosures during reload.',[],
           [point('queue',file('.newsboat/queue')),point('states',cache('guid enqueued',{'feedurl':F.FEEDURL['Audio Cast']}))]),
        cp('repeat','Reload without adding duplicate queue entries.',[{'cli':['-x','reload']}],
           [point('queue',file('.newsboat/queue'))],depends=['auto'])],files=F.library('podcast-auto-enqueue yes\n')))
    out.append(episode('cli-options','cli',[
        cp('help','Show command-line help.',[],[point('options',cli(['-h'],'contains',needles=['--export-to-opml','--execute','--url-file'],nonempty=True))]),
        cp('version','Show the product version.',[],[point('version',cli(['-v'],'contains',needles=['Newsboat 2.45'],nonempty=True))]),
        cp('quiet-count','Print unread count in quiet mode.',[],[point('count',cli(['-q','-x','print-unread']))]),
        cp('reload-count','Execute reload and print-unread in one invocation.',[],[point('count',cli(['-x','reload','print-unread']))]),
        cp('alternate-urls','Use an alternate subscription file.',[],[point('export',cli(['-u','other.urls','-e'],'opml'))]),
        cp('alternate-config','Use an alternate configuration file.',[],[point('count',cli(['-C','other.conf','-x','print-unread']))]),
        cp('alternate-cache','Use a separate cache file.',[],[point('count',cli(['-c','other.db','-x','reload','print-unread']))]),
        cp('missing-read','Report a missing read-state import file.',[],[point('status',cli(['-I','missing.txt'],'exit'))]),
        cp('missing-opml','Report a missing OPML import file.',[],[point('status',cli(['-i','missing.opml'],'exit'))]),
    ],files=F.library(**{'other.urls':'file://feeds/cast.xml\n','other.conf':'max-items 1\n'})))
    return out
