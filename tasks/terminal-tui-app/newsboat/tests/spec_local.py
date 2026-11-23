"""Local operations, persistence, live input reloads and distinct configuration effects."""
import base64
from spec_common import (C,F,K,P,article,cache,contains,cp,feed,file,focus,labels,point,quote,scenarios,scr,select,episode)
from spec_filters import query_urls
from spec_rendering import long_home


def listed(names,unordered=False):
    return labels(names,unordered=unordered,expected={'labels':sorted(names) if unordered else names})


def save_all():
    out=[]
    points=[point('files',dict(kind='dir',path='saved'))]
    for title,name,body in [('Filesystem benchmarks','Filesystem_benchmarks.txt','ext4 against btrfs.'),
                            ('Compiler news','Compiler_news.txt','GCC and Clang updates.'),
                            ('Rust in the kernel','Rust_in_the_kernel.txt','Rust support grows.'),
                            ('Kernel 6.9 released','Kernel_69_released.txt','The kernel team released version 6.9.')]:
        points.append(point('article-'+name.split('.')[0].lower(),file('saved/'+name,'contains',
                     needles=[title,body],expected={'contains':[title,body]})))
    out.append(episode('save-all-files','exports',[
        cp('save','Save all Tech Daily articles to the prepared directory.',[C('exec save-all'),P('saved')],points)],
        files=F.library(**{'saved':None}),before=feed()))
    cases=[]
    for name,reply in [('overwrite','y'),('keep-existing','n')]:
        fx=F.home('file://feeds/a.xml',{'a.xml':F.rss('Exports',[
            F.item('Same title','a',F.day(3),'Body alpha'),F.item('Another title','b',F.day(2),'Body beta')])},
            **{'saved':None,'saved/Same_title.txt':'Existing text\n'})
        cases.append((cp(name,'Save a batch encountering an existing file.',[C('exec save-all'),P('saved'),K(reply)],
            [point('conflict',file('saved/Same_title.txt','words')),point('other',file('saved/Another_title.txt','words'))]),fx,feed()))
    fx=F.home('file://feeds/a.xml',{'a.xml':F.rss('Exports',[
        F.item('Café notes','a',F.day(3),'Unicode body'),F.item('Same','b',F.day(2),'Earlier body'),
        F.item('Same','c',F.day(1),'Later overwrite body')])},**{'saved':None})
    cases.append((cp('duplicate-names','Save a batch with duplicate and Unicode titles.',[C('exec save-all'),P('saved'),K('y')],
                     [point('names',dict(kind='dir',path='saved')),point('collision',file('saved/Same.txt','words'))]),fx,feed()))
    return out+scenarios('save-all-conflicts','exports',cases)


def dialogs_search():
    out=[episode('dialog-management','dialogs',[
        cp('stack','Show the three open views.',[K('v')],[point('views',listed(['Feed List','Article List','Article -']))]),
        cp('close','Close the article view from the stack.',[K('End'),K('Control+x')],
           [point('views',labels(['Feed List','Article List','Article -'],expected={'labels':['Feed List','Article List']}))],depends=['stack']),
        cp('activate','Activate the article list.',[K('End'),K('Enter')],[point('articles',listed(list(reversed(F.TECH_TITLES))))],depends=['close']),
        cp('previous','Switch to the previous view.',[K('Control+g')],[point('feeds',listed(F.FEED_TITLES))],depends=['activate']),
        cp('next','Switch forward to the article list.',[K('Control+v')],[point('articles',listed(list(reversed(F.TECH_TITLES))))],depends=['previous']),
        cp('feed-boundary','The feed list cannot be closed from the dialog stack.',[K('v'),K('Home'),K('Control+x')],
           [point('views',listed(['Feed List','Article List'])),point('feedback',scr('message',nonempty=True))],depends=['next'])
    ],before=feed()+article())]
    out.append(episode('search-history-stack','search',[
        cp('first','Search all feeds for kernel.',[K('/'),P('kernel')],[point('items',listed(['Rust in the kernel','Kernel 6.9 released']))]),
        cp('narrow','Search within the results for Rust.',[K('/'),K('Control+u'),P('Rust')],[point('items',listed(['Rust in the kernel']))],depends=['first']),
        cp('previous','Return to the prior results.',[K('z')],[point('items',listed(['Rust in the kernel','Kernel 6.9 released']))],depends=['narrow']),
        cp('origin','Open the original feed of the selected result.',[C('exec article-feed')],
           [point('items',listed(list(reversed(F.TECH_TITLES)))),point('view',contains("Articles in feed 'Tech Daily'"))],depends=['previous'])]))
    names=[f'Article {i:02}' for i in range(1,76)]
    out.append(episode('half-page-navigation','navigation',[
        cp('half-up','Move up half a page from the end.',[C('exec halfpageup')],[point('selection',focus(names))]),
        cp('half-down','Move back down half a page.',[C('exec halfpagedown')],[point('selection',focus(names))],depends=['half-up'])
    ],files=long_home(),before=feed()+[K('End')]))
    return out


def updates_retention():
    out=[]
    modified=F.TECH.replace('GCC and Clang updates.','Revised compiler body.')
    for name,rule in [('disabled',''),('selected','reset-unread-on-update "file://feeds/tech.xml"'),
                      ('other-feed','reset-unread-on-update "file://feeds/food.xml"'),
                      ('multiple','reset-unread-on-update "file://feeds/food.xml" "file://feeds/tech.xml"')]:
        out.append(episode('reset-unread-'+name,'cache-updates',[
            cp('changed','Reload the modified article with the same GUID.',[{'update_inputs':{'feeds/tech.xml':modified}},{'cli':['-x','reload']}],
               [point('read-state',cache('unread',{'guid':'t3'})),point('content',cache('content',{'guid':'t3'})),point('other-feed',cache('unread',{'guid':'f1'}))]),
            cp('unchanged','Reload identical content after marking it read again.',[{'cli':['-I','read.txt']},{'cli':['-x','reload']}],
               [point('state',cache('unread',{'guid':'t3'},expected={'rows':[[0]]}))],depends=['changed'])
        ],files=F.library(rule,**{'read.txt':'t3\nf1\n'}),before=[{'cli':['-I','read.txt']}]))
    cases=[]
    archive=F.rss('Archive',[
        F.item('A marked old','a',F.day(1),'Old protected'),F.item('B old plain','b',F.day(2),'Old plain'),
        F.item('C other flag','c',F.day(3),'Old other flag'),
        F.item('D future','d','Thu, 01 Jan 2099 00:00:00 +0000','Future item')])
    for name,keep in [('remove-old',''),('keep-marked','a'),('keep-other','z')]:
        files=F.home('file://feeds/archive.xml',{'archive.xml':archive},'article-sort-order title-asc\n')
        before=feed()+[K('Control+e'),P('a')]+select(2)+[K('Control+e'),P('z'),K('q')]
        config='article-sort-order title-asc\nkeep-articles-days 1\nkeep-forever-if-flagged-with '+quote(keep)+'\n'
        retained={'remove-old':['d'],'keep-marked':['a','d'],'keep-other':['c','d']}[name]
        cases.append((cp(name,'Reload with an age policy and flag exemption.',[{'place':{'.newsboat/config':config}},{'cli':['-x','reload']}],
                         [point('retained',cache('guid',expected={'rows':[[g] for g in retained]}))]),files,before))
    return out+scenarios('retention-flags','cache-updates',cases)


def unread_boundaries():
    out=[]
    for scope,names,before,read in [('articles',F.TECH_TITLES,feed(),'t2\nt3\n'),
                                   ('feeds',F.FEED_TITLES,[],'f1\nf2\nf3\n')]:
        out.append(episode('unread-boundaries-'+scope,'navigation',[
            cp('forward-wrap','Find an unread entry after the last row.',[K('End'),K('n')],
               [point('focus',focus(names))]),
            cp('backward-wrap','Find an unread entry before the first row.',[K('Home'),K('p')],
               [point('focus',focus(names))]),
            cp('mark-all','Mark the remaining entries read.',[K('A') if scope=='articles' else K('C'),K('y')],
               [point('state',cache('guid unread',{'feedurl':F.FEEDURL['Tech Daily']} if scope=='articles' else {}))]),
            cp('no-next','Keep a valid list when no next unread entry exists.',[C('1'),K('n')],
               [point('focus',focus(names)),point('feedback',scr('message',nonempty=True))],depends=['mark-all']),
            cp('no-previous','Keep a valid list when no previous unread entry exists.',[C('1'),K('p')],
               [point('focus',focus(names)),point('feedback',scr('message',nonempty=True))],depends=['mark-all'])
        ],files=F.library('goto-next-feed no',**{'read.txt':read}),before=[{'cli':['-I','read.txt']}]+before))
    return out


def startup_reload():
    out=[]
    for name,conf in [('refresh','refresh-on-startup yes'),('manual','refresh-on-startup no')]:
        count_labels=F.FEED_TITLES if name=='refresh' else list(F.FEEDURL.values())
        out.append(episode('startup-'+name,'settings',[
            cp('loaded','Observe the initial cache under the refresh policy.',[{'wait':1}],
               [point('items',cache('guid title')),point('counts',scr('counts',labels=count_labels,nonempty=True))])],files=F.library(conf),load=False))
    out.append(episode('startup-operations','settings',[
        cp('position','Run the safe startup operation sequence.',[],[point('selected',focus(F.FOOD_TITLES)),point('items',listed(list(reversed(F.FOOD_TITLES))))])],
        files=F.library('run-on-startup next; open\n')))
    for name,value in [('lazy','no'),('prepopulated','yes')]:
        out.append(episode('query-startup-'+name,'query-feeds',[
            cp('counts','Observe query population on a cached restart.',[],[point('counts',scr('counts',labels=['Everything']))]),
            cp('open','Populate the query on opening.',feed(3),[point('items',labels(F.ALL_TITLES,unordered=True,nonempty=True))])],
            files=F.library('prepopulate-query-feeds '+value,urls=query_urls('Everything','title =~ "."'))))
    for mode in ['yes','no']:
        out.append(episode('reload-visible-'+mode,'settings',[
            cp('reload','Reload while only the tech tag is visible.',[
                {'update_inputs':{'feeds/tech.xml':F.TECH.replace('GCC and Clang updates.','Tech changed'),
                                  'feeds/food.xml':F.FOOD.replace('Flour, water, salt.','Food changed')}},K('R'),{'wait':1.5}],
               [point('visible-feed',cache('content',{'guid':'t3'})),point('hidden-feed',cache('content',{'guid':'f1'}))])],
            files=F.library('reload-only-visible-feeds '+mode),before=[C('tag tech')]))
    for mode in ['yes','no']:
        xml=F.rss('Content',[F.item('Combined body','x',F.day(1),'Description section',extra='<content:encoded>Full section</content:encoded>')])
        out.append(episode('description-precedence-'+mode,'feed-parsing',[
            cp('body','Combine or prefer the content extension.',[],[point('body',cache('content',{'guid':'x'},nonempty=True))])],
            files=F.home('file://feeds/content.xml',{'content.xml':xml},'always-display-description '+mode)))
    return out


def subscription_reload():
    cps=[]
    variants=[('add',F.LIB_URLS+'file://feeds/garden.xml garden\n'),
              ('remove','file://feeds/food.xml food\nfile://feeds/cast.xml audio\n'),
              ('alias','file://feeds/tech.xml "~Computing" tech\nfile://feeds/food.xml food\n'),
              ('reorder','file://feeds/cast.xml audio\nfile://feeds/food.xml food\nfile://feeds/tech.xml tech\n'),
              ('tags','file://feeds/tech.xml fresh\nfile://feeds/food.xml fresh\nfile://feeds/cast.xml audio\n')]
    names=F.FEED_TITLES+['Garden Journal','Computing','file://feeds/garden.xml']
    for name,urls in variants:
        cps.append(cp(name,'Reload subscription changes without restarting.',[{'update_inputs':{'.newsboat/urls':urls}},K('Control+r')],[point('feeds',labels(names))]))
    cps.append(cp('new-tags','Select a tag added by reload-urls.',[C('tag fresh')],[point('members',listed(['Tech Daily','Food Notes']))],depends=['tags']))
    return [episode('live-subscriptions','subscriptions',cps,files=F.library(**{'feeds/garden.xml':F.rss('Garden Journal',[F.item('Seed story','garden',F.day(1))])}))]


def config_roundtrip():
    conf='text-width \\\n  31\nfeedlist-title-format "Quoted \\"title\\" and \\\\ slash"\ninclude "first.conf"\ninclude "second.conf"\n'
    conf+='opml-url "file://subscriptions.opml"\n'
    files=F.library(conf,**{'.newsboat/first.conf':'history-limit 7\n','.newsboat/second.conf':'show-read-feeds no\n',
                          'source-one.conf':'text-width 29\n','source-two.conf':'history-limit 9\n'})
    def points():return [point(n,file('dump.conf','config',name=n)) for n in ['text-width','feedlist-title-format','history-limit','show-read-feeds']]
    return [episode('configuration-roundtrip','configuration',[
        cp('parsed','Export continued, escaped and included settings.',[C('dumpconfig dump.conf')],points()),
        cp('reload','Load the exported file as configuration.',[{'restart':['-C','dump.conf']},C('dumpconfig dump.conf')],points(),depends=['parsed']),
        cp('multiple-source','Source two local files in order.',[C('source source-one.conf source-two.conf'),C('dumpconfig dump.conf')],points(),depends=['reload'])
    ],files=files)]


def bindings_formats():
    conf='''bind zx feedlist set feedlist-title-format "Prefix X"
bind zy feedlist set feedlist-title-format "Prefix Y"
bind X feedlist open
bind X articlelist set articlelist-title-format "Article local"
unbind-key A feedlist
macro m open; set articlelist-title-format "Macro entered" -- "Safe macro"
'''
    out=[episode('binding-contexts','keybindings',[
        cp('prefix-x','Execute one branch of a shared key prefix.',[K('z'),K('x')],[point('title',contains('Prefix X'))]),
        cp('prefix-y','Execute the other prefix branch.',[K('z'),K('y')],[point('title',contains('Prefix Y'))]),
        cp('cancel','Cancel a partially entered sequence.',[K('z'),K('Escape'),K('x')],[point('title',contains('Prefix Y'))],depends=['prefix-y']),
        cp('unbound','Verify the unbound marking key has no action.',[K('A')],[point('read',cache('guid unread'))]),
        cp('feed-binding','Use the feed-specific binding.',[K('X')],[point('items',listed(list(reversed(F.TECH_TITLES))))]),
        cp('article-binding','Use the same key in the article dialog.',[K('X')],[point('title',contains('Article local'))],depends=['feed-binding']),
        cp('macro','Execute an internal macro across dialogs.',[K('q'),K(','),K('m')],[point('title',contains('Macro entered'))],depends=['article-binding'])
    ],files=F.library(conf))]
    out.append(episode('query-origin-format','formatting',[
        cp('origin','Display each result’s originating feed.',[C('set articlelist-format "BEGIN%TEND %t"')],
           [point('sources',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))])],
        files=F.library(urls=query_urls('All','title =~ "."')),before=feed(3)))
    out.append(episode('right-alignment','formatting',[
        cp('right','Align a marker to the right of each feed row.',[C('set feedlist-format "L:%t%>.R"')],
           [point('relative-position',scr('right-aligned',labels=F.FEED_TITLES,left='L:',right='R',nonempty=True))])]))
    body=' '.join(['alpha beta gamma delta epsilon zeta eta theta']*6)
    cps=[cp('width-'+str(w),'Render a plain article at width '+str(w),
            [C('set text-width '+str(w)),C('save width.txt')],[point('lines',file('width.txt','body-widths'))]) for w in [20,40,0]]
    out.append(episode('render-width','html-rendering',cps,
        files=F.home('file://feeds/a.xml',{'a.xml':F.rss('Wrap',[F.item('Wrapped','w',F.day(1),body)])}),before=feed()))
    for value in [0,4]:
        files=long_home();files['.newsboat/config']+='scrolloff '+str(value)+'\n'
        names=[f'Article {i:02}' for i in range(1,76)]
        out.append(episode('scrolloff-'+str(value),'navigation',[
            cp('position','Keep configured context around the selection.',[C('30')],
               [point('selected',focus(names)),point('visible-items',labels(names))])],files=files,before=feed()))
    for name,command,setting in [('single','save','filebrowser-title-format'),('batch','save-all','dirbrowser-title-format')]:
        out.append(episode('file-dialog-format-'+name,'formatting',[
            cp('title','Show directory and dialog purpose in its title.',[C('exec '+command)],
               [point('expansion',scr('matches',pattern='BEGIN(.*?)END',nonempty=True))])],
            files=F.library(setting+' "BEGIN%f|%?O?open&save?END"'),before=feed()))
    return out


def parser_boundaries():
    docs={};points=[]
    base=F.rss('Encoding',[F.item('Café étude','enc',F.day(1),'Crème brûlée')])
    for name,raw in [('bom',b'\xef\xbb\xbf'+base.replace('<guid>enc</guid>','<guid>bom</guid>').encode()),
                     ('latin1',base.replace('UTF-8','ISO-8859-1').encode('latin1'))]:
        docs[name+'.xml']={'base64':base64.b64encode(raw).decode()}
        for field in ['title','content']:
            points.append(point(name+'-'+field,cache(field,{'feedurl':'file://feeds/'+name+'.xml'},nonempty=True)))
    docs['empty.xml']=F.rss('Empty feed',[])
    points.append(point('empty-feed',cache('title',{'rssurl':'file://feeds/empty.xml'},'rss_feed',expected={'rows':[['Empty feed']]})))
    docs['duplicates.xml']=F.rss('Duplicate IDs',[F.item('First copy','same',F.day(1),'First body'),F.item('Second copy','same',F.day(2),'Second body')])
    points.append(point('duplicate-guid',cache('guid title content',{'feedurl':'file://feeds/duplicates.xml'},nonempty=True)))
    docs['base.xml']=('<feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://base.example/root/">'
          '<title>Inherited base</title><link rel="alternate" href="home"/>'
          '<entry xml:base="entries/"><id>base-id</id><title>Nested base</title><updated>2024-01-01T10:00:00Z</updated>'
          '<link href="story"/><content type="html" xml:base="content/">Body</content></entry></feed>')
    points.extend([point('atom-'+field,cache(field,{'feedurl':'file://feeds/base.xml'},nonempty=True)) for field in ['url','base','content']])
    files={'.newsboat/urls':'\n'.join('file://feeds/'+n for n in docs)+'\n',**{'feeds/'+n:x for n,x in docs.items()}}
    return [episode('parser-binary-inputs','feed-parsing',[cp('parse','Read encoded, empty and duplicate feed documents.',[],points)],files=files)]


def podcast_states():
    out=[episode('podcast-duplicate','podcasts',[
        cp('first','Enqueue the selected enclosure.',[K('e')],[point('queue',file('.newsboat/queue'))]),
        cp('duplicate','Enqueue the same enclosure again.',[K('e')],[point('single-entry',file('.newsboat/queue')),
           point('feedback',scr('message',nonempty=True))],depends=['first']),
        cp('no-enclosure','Attempt to enqueue an ordinary article.',[K('q')]+feed()+[K('e')],
           [point('state',cache('guid enqueued',{'feedurl':F.FEEDURL['Tech Daily']})),point('feedback',scr('message',nonempty=True))])],before=feed(2))]
    out.append(episode('podcast-query','podcasts',[
        cp('queue','Enqueue an enclosure from a query feed.',[K('e')],
           [point('queue',file('.newsboat/queue')),point('origin-state',cache('enqueued',{'guid':'c2'},expected={'rows':[[1]]}))])],
        files=F.library(urls=query_urls('Podcasts','enclosure_type = "audio/mpeg"')),before=feed(3)))
    return out


def build():
    return (save_all()+dialogs_search()+updates_retention()+unread_boundaries()+startup_reload()+subscription_reload()+
            config_roundtrip()+bindings_formats()+parser_boundaries()+podcast_states())
