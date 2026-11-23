"""User goals in the terminal; each checkpoint begins with its own unscored fixture preparation."""
from spec_common import (scr, C, F, K, P, article, cache, contains, cp, feed, file, focus, labels, point, quote, scenarios, select)

TECH=list(reversed(F.TECH_TITLES))
FOOD=list(reversed(F.FOOD_TITLES))
CAST=list(reversed(F.CAST_TITLES))


def build():
    groups={}
    def add(feature,name,goal,steps,check,acceptance=None,before=(),files=None):
        checks=check if isinstance(check,list) else [point('result',check)]
        groups.setdefault(feature,[]).append((cp(name,goal,steps,checks,acceptance or goal),files,list(before)))

    for name,goal,steps in [
        ('feed-next','Select Food Notes in the subscription list.',[K('Down')]),
        ('feed-last','Select Audio Cast in the subscription list.',[K('End')]),
        ('feed-first','Move from the last subscription to Tech Daily.',[K('Home')]),
        ('feed-number','Select subscription number 2.',[C('2')]),
        ('feed-goto','Select the feed whose title contains "audio".',[C('goto audio')]),
        ('feed-next-unread','From Tech Daily, select the next feed with unread articles.',[K('n')]),
        ('feed-prev-unread','From Tech Daily, select the previous feed with unread articles.',[K('p')]),
    ]:
        before=[K('End')] if name=='feed-first' else []
        files=None
        if name in ('feed-next-unread','feed-prev-unread'):
            read='f1\nf2\nf3\n' if name=='feed-next-unread' else 'c1\nc2\n'
            files=F.library(**{'read.txt':read});before=[{'cli':['-I','read.txt']}]
        add('navigation',name,goal,steps,focus(F.FEED_TITLES),before=before,files=files)
    for name,goal,steps in [
        ('article-next','Select Compiler news.',[K('Down')]),
        ('article-last','Select Kernel 6.9 released.',[K('End')]),
        ('article-first','Select Filesystem benchmarks from the bottom of the list.',[K('Home')]),
        ('article-number','Select article number 3.',[C('3')]),
        ('article-goto','Select the article with "Rust" in its title.',select(2)),
        ('article-next-unread','From Filesystem benchmarks, select the next unread article.',[K('n')]),
        ('article-prev-unread','From the oldest article, select the previous unread article.',[K('p')]),
    ]:
        files=None;before=feed(0)+([K('End')] if name in ('article-first','article-prev-unread') else [])
        if name in ('article-next-unread','article-prev-unread'):
            files=F.library(**{'read.txt':'t3\n' if name=='article-next-unread' else 't2\n'})
            before=[{'cli':['-I','read.txt']}]+before
        add('navigation',name,goal,steps,focus(F.ALL_TITLES),before=before,files=files)
    for name,goal,steps,expected in [
        ('open-feed','Open Food Notes to list its articles.',feed(1),F.FOOD_TITLES),
        ('next-feed','Show the articles from the feed following Tech Daily.',[K('j')],F.FOOD_TITLES),
        ('previous-feed','Show the articles from the feed preceding Food Notes.',[K('k')],F.TECH_TITLES),
        ('next-unread-feed','Show the next feed that has unread articles.',[K('Control+n')],F.CAST_TITLES),
        ('previous-unread-feed','Show the previous feed that has unread articles.',[K('Control+p')],F.TECH_TITLES),
        ('return-feeds','Return to the subscription list.',[K('q')],F.FEED_TITLES),
    ]:
        before=() if name=='open-feed' else feed(1 if 'previous' in name else 0)
        files=None
        if name in ('next-unread-feed','previous-unread-feed'):
            files=F.library(**{'read.txt':'f1\nf2\nf3\n'})
            before=[{'cli':['-I','read.txt']}]+feed(0 if name=='next-unread-feed' else 2)
        add('navigation',name,goal,steps,labels(expected,nonempty=True),before=before,files=files)

    add('reading','open-article','Read Rust in the kernel.',select(2)+[K('Enter')],contains('Rust support grows.'),
        'The Rust in the kernel article is open and its body can be read.',before=feed(0))
    add('reading','next-article','While reading Filesystem benchmarks, open the next article.',[K('J')],
        contains('Compiler news','GCC and Clang updates.'),before=feed(0)+article(0))
    add('reading','previous-article','While reading Compiler news, open the previous article.',[K('K')],
        contains('Filesystem benchmarks','ext4 against btrfs.'),before=feed(0)+article(1))
    add('reading','source','Show the HTML source of Rust in the kernel.',[K('Control+u')],contains('<p>Rust support grows.</p>'),
        'The article source is visible with its HTML markup.',before=feed(0)+article(2))
    add('reading','urls','List the links in Rust in the kernel.',[K('u')],
        scr('contains',needles=['http://rust.example/'],expected={'contains':['http://rust.example/']},view='urls'),
        'The article link can be inspected in the list of URLs.',before=feed(0)+article(2))
    add('reading','return-articles','Return from an article to its feed article list.',[K('q')],labels(F.TECH_TITLES),
        before=feed(0)+article(0))
    add('reading','toggle-read','Mark Filesystem benchmarks as read without opening it.',[K('N')],
        cache('unread',{'guid':'t4'}),'Filesystem benchmarks is shown as read.',before=feed(0))
    add('reading','toggle-unread','Mark Filesystem benchmarks unread again.',[K('N')],cache('unread',{'guid':'t4'}),
        'Filesystem benchmarks is shown as unread.',before=feed(0)+article(0)+[K('q'),K('Home')])
    add('reading','feed-read','Mark every article in Tech Daily as read, confirming if asked.',[K('A'),K('y')],
        cache('guid unread',{'feedurl':F.FEEDURL['Tech Daily']}),'Tech Daily has no unread articles.')
    add('reading','all-read','Mark every subscribed feed as read, confirming if asked.',[K('C'),K('y')],
        cache('guid unread'),'All subscriptions have no unread articles.')
    add('reading','read-above','Mark all articles above Rust in the kernel as read.',select(2)+[C('exec mark-all-above-as-read')],
        cache('guid unread',{'feedurl':F.FEEDURL['Tech Daily']}),'The articles above Rust in the kernel are marked read.',before=feed(0))
    files=F.library(**{'read.txt':'t1\nt2\nt3\nt4\n'})
    add('reading','hide-read-feeds','Hide subscriptions without unread articles.',[K('l')],labels(F.FEED_TITLES),
        'Food Notes and Audio Cast remain visible; the fully read Tech Daily is hidden.',
        before=[{'cli':['-I','read.txt']}],files=files)
    add('reading','show-read-articles','Show only unread articles in Tech Daily.',[C('set show-read-articles no'),K('q'),K('Enter')],
        labels(F.TECH_TITLES),'The read article is hidden and the unread articles remain.',
        before=feed(0)+article(0)+[K('q')])

    for name,value in [('single','a'),('multiple','bZa'),('normalize','aBaBz'),('clear','')]:
        before=feed(0)
        if name=='clear':
            before += [K('Control+e'),P('ab')]
        add('flags','flags-'+name,'Set the flags of Filesystem benchmarks to '+repr(value)+'.',
            [K('Control+e'),K('Control+u'),P(value),K('Control+e')],cache('flags',{'guid':'t4'}),
            'The article shows the requested flag state (letters are sorted and duplicates removed).',before=before)
    add('flags','flags-view','Set flag z while reading Rust in the kernel.',[K('Control+e'),P('z')],
        cache('flags',{'guid':'t2'}),'The open article shows flag z.',before=feed(0)+article(2))
    add('deletion','delete-one','Mark Filesystem benchmarks for deletion.',[K('D')],cache('deleted',{'guid':'t4'}),
        'The article has been marked for deletion.',before=feed(0))
    add('deletion','purge','Remove the article already marked for deletion from this list.',[K('$')],labels(F.TECH_TITLES),
        'Filesystem benchmarks is no longer listed; the other articles remain.',before=feed(0)+[K('D')])
    add('deletion','undelete','Restore the deleted Filesystem benchmarks article to unread.',[K('N')],
        cache('deleted unread',{'guid':'t4'}),'The article is no longer marked deleted and is unread.',before=feed(0)+[K('D'),K('Home')])
    add('deletion','delete-all','Delete every article in Tech Daily, confirming if asked.',[K('Control+d'),K('y')],
        cache('guid deleted',{'feedurl':F.FEEDURL['Tech Daily']}),'The articles in Tech Daily are marked deleted.',before=feed(0))
    add('deletion','delete-filtered','Delete the articles matching the current kernel filter, confirming if asked.',
        [K('Control+d'),K('y')],cache('guid deleted',{'feedurl':F.FEEDURL['Tech Daily']}),
        'The two matching kernel articles are marked deleted.',before=feed(0)+[K('F'),P('title =~ "kernel"')])

    for tag in ['news','food','audio','tech']:
        add('tags','tag-'+tag,'Show feeds tagged '+tag+'.',[C('tag '+tag)],labels(F.FEED_TITLES),
            'Only the feeds with the requested tag are listed.')
    add('tags','tag-dialog','Choose the audio tag from the tag selection dialog.',[K('t'),K('Home'),K('Enter')],
        labels(F.FEED_TITLES),'Only Audio Cast is listed.')
    add('tags','clear-tag','Show all subscriptions again by clearing the tag.',[K('Control+t')],labels(F.FEED_TITLES),
        'All three subscriptions are listed again.',before=[C('tag food')])

    for name,expr in [('feed-count','total_count > 2'),('feed-title','feedtitle =~ "food"'),
                      ('feed-tag','tags # "news"'),('feed-combined','tags # "news" and total_count > 2')]:
        add('filters',name,'Filter the subscriptions with: '+expr,[K('F'),P(expr)],labels(F.FEED_TITLES),
            'The listed feeds satisfy the requested expression.')
    for name,expr in [('article-title','title =~ "kernel"'),('article-author','author =~ "Linus"'),
                      ('article-content','content =~ "btrfs"'),('article-combined','title =~ "kernel" and author =~ "Miguel"')]:
        add('filters',name,'Filter Tech Daily with: '+expr,[K('F'),P(expr)],labels(F.TECH_TITLES),
            'The listed articles satisfy the requested expression.',before=feed(0))
    add('filters','clear-filter','Remove the active article filter.',[K('Control+f')],labels(F.TECH_TITLES),
        'All four Tech Daily articles are listed.',before=feed(0)+[K('F'),P('title =~ "kernel"')])
    add('filters','saved-filter','Choose the predefined Kernel stories filter.',[K('f'),K('Home'),K('Enter')],
        labels(F.TECH_TITLES),'The two kernel articles are listed.',before=feed(0),
        files=F.library('define-filter "Kernel stories" "title =~ \\"kernel\\""\n'))

    for name,text,before in [('search-global','kernel',()),('search-feed','kernel',feed(0)),
                             ('search-content','btrfs',()),('search-case','KERNEL',()),('search-phrase','Rust support',())]:
        search_files=F.library(); search_labels=F.ALL_TITLES
        if name in ('search-global','search-feed'):
            search_files['feeds/food.xml']=F.rss('Food Notes',[
                F.item('Corn kernel recipes','f-kernel',F.day(11),'<p>Food mentions kernel.</p>'),
                F.item('Bread at home','f1',F.day(2),'<p>Flour, water, salt.</p>'),
                F.item('Spicy noodles','f2',F.day(4),'<p>Chili oil and noodles.</p>'),
                F.item('Winter soup','f3',F.day(6),'<p>Lentils and carrots.</p>')])
            search_labels=F.ALL_TITLES+['Corn kernel recipes']
        add('search',name,'Search for '+quote(text)+(' in the current feed.' if before else ' across all feeds.'),
            [K('/'),P(text)],labels(search_labels,nonempty=True),'The matching search results are displayed.',before=before,files=search_files)
    add('search','open-search-result','Read the result titled Rust in the kernel.',[C('goto Rust'),K('Enter')],
        contains('Rust support grows.'),'The matching article body is visible.',before=[K('/'),P('kernel')])

    sort_article_files = F.home(
        'file://feeds/tech.xml tech news\nfile://feeds/food.xml food\nfile://feeds/cast.xml audio news\n',
        {'tech.xml': F.rss('Tech Daily', [
            F.item('Kernel 6.9 released','a-guid',F.day(3),link='http://example.com/a',author='linus@example.com (Linus)'),
            F.item('Rust in the kernel','z-guid',F.day(5),link='http://example.com/b',author='miguel@example.com (Miguel)'),
            F.item('Compiler news','b-guid',F.day(7),link='http://example.com/d',author='linus@example.com (Linus)'),
            F.item('Filesystem benchmarks','m-guid',F.day(9),link='http://example.com/c',author='ted@example.com (Ted)')]),
         'food.xml': F.FOOD, 'cast.xml': F.CAST})
    for key in ['title','date','author','link','guid']:
        for direction in ['asc','desc']:
            setting_direction = ('desc' if direction=='asc' else 'asc') if key=='date' else direction
            add('sorting','articles-'+key+'-'+direction,'Sort Tech Daily articles by '+key+' '+direction+'.',
                [C('set article-sort-order '+key+'-'+setting_direction)],
                labels(F.TECH_TITLES,ties=[['Kernel 6.9 released','Compiler news']] if key=='author' else []),
                'The articles are ordered by the requested field and direction.',
                before=feed(0)+[C('set article-sort-order '+key+'-'+('desc' if setting_direction=='asc' else 'asc'))],files=sort_article_files)
    # Four feeds allow five different ascending/reversed permutation pairs.
    titles=['Tech Daily','Food Notes','Audio Cast','Garden Journal']
    tags=['bravo','delta','alpha','charlie'];totals=[4,5,6,7];unread=[2,1,3,4];dates=[12,18,24,8]
    docs={};read=[]
    for i,title in enumerate(titles):
        docs[str(i)+'.xml']=F.rss(title,[F.item(title+' article '+str(j),f'sort-{i}-{j}',F.day(dates[i]-j)) for j in range(totals[i])])
        read.extend(f'sort-{i}-{j}' for j in range(unread[i],totals[i]))
    sortfiles=F.home('\n'.join(f'file://feeds/{i}.xml {tags[i]}' for i in range(4)),docs,
                     **{'read.txt':'\n'.join(read)+'\n'})
    for key in ['title','firsttag','articlecount','unreadarticlecount','latestunread']:
        for direction in ['asc','desc']:
            setting_direction = direction if key=='latestunread' else ('desc' if direction=='asc' else 'asc')
            add('sorting','feeds-'+key+'-'+direction,'Sort subscriptions by '+key+' '+direction+'.',
                [C('set feed-sort-order '+key+'-'+setting_direction)],labels(titles),
                'The subscriptions are ordered by the requested field and direction.',
                files=sortfiles,before=[{'cli':['-I','read.txt']},
                    {'expect':scr('counts',labels=titles,expected={'counts':{t:[unread[i],totals[i]] for i,t in enumerate(titles)}})},
                    C('set feed-sort-order '+key+'-'+('desc' if setting_direction=='asc' else 'asc'))])

    add('exports','save-article','Save Rust in the kernel to ~/rust.txt.',[C('save ~/rust.txt')],
        file('rust.txt','words'),'The application confirms the article was saved to the requested file.',before=feed(0)+select(2))
    add('exports','save-view','Save the currently open article to ~/reading.txt.',[C('save ~/reading.txt')],
        file('reading.txt','words'),'The application confirms the article was saved.',before=feed(1)+article(1))
    add('exports','save-dialog','Save Filesystem benchmarks using the proposed filename.',[K('s'),K('Enter')],
        file('Filesystem_benchmarks.txt','words'),'The article has been saved using its proposed filename.',before=feed(0))
    add('exports','enqueue','Add Episode 2: Growth to the podcast queue.',[K('e')],file('.newsboat/queue'),
        'The selected podcast episode is queued.',before=feed(2))
    add('exports','enqueue-view','Add the open Episode 1: Origins to the podcast queue.',[K('e')],file('.newsboat/queue'),
        'The open episode is queued.',before=feed(2)+article(1))
    add('dialogs','help-feeds','Show help for the subscription list.',[K('?')],contains('reload-all','mark-all-feeds-read'),
        'Help for actions in the subscription list is visible.')
    add('dialogs','help-articles','Show help for the article list.',[K('?')],contains('toggle-article-read','edit-flags'),
        'Help for actions in the article list is visible.',before=feed(0))
    add('dialogs','help-search','Find the reload actions in the help screen.',[K('/'),P('reload')],
        scr('help-actions',query='reload',view='help'),
        'The help screen shows matching reload actions.',before=[K('?')])
    add('dialogs','list-dialogs','Show the list of open dialogs.',[K('v')],contains('Dialogs','Tech Daily'),
        'The open views can be inspected in the dialog list.',before=feed(0)+article(0))
    add('dialogs','previous-dialog','Switch from the article view to the preceding open dialog.',[K('Control+g')],
        labels(F.TECH_TITLES),'The Tech Daily article list is active.',before=feed(0)+article(0))
    out=[]
    for feature,cases in groups.items():
        out.extend(scenarios('gui-'+feature,feature,cases,gui=True))
    return out
