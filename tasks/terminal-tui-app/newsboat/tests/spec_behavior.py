"""State-dependent options, histories, bindings, visible styling and subscription rules."""
from spec_common import (C, F, K, P, article, cache, cli, cp, feed, file, focus, labels, point, scenarios, scr, episode)
from spec_filters import query_urls


def build():
    out=[]
    cases=[]
    def add(name,steps,checks,config='',before=(),extra=None):
        files=F.library(config,**(extra or {}))
        cases.append((cp(name,name.replace('-',' ').capitalize()+'.',steps,checks),files,list(before)))
    for value in ['yes','no']:
        add('first-unread-'+value,feed(0),[point('focus',focus())], 'goto-first-unread '+value,
            before=[{'cli':['-I','read.txt']}],extra={'read.txt':'t4\n'})
        add('toggle-next-'+value,[K('N')],[point('focus',focus()),point('state',cache('unread',{'guid':'t4'}))],
            'toggleitemread-jumps-to-next '+value,before=feed(0))
        add('toggle-next-unread-'+value,[K('N')],[point('focus',focus())],
            'toggleitemread-jumps-to-next no\ntoggleitemread-jumps-to-next-unread '+value,
            before=[{'cli':['-I','read.txt']}]+feed(0),extra={'read.txt':'t3\n'})
        add('read-on-hover-'+value,[K('Down')],[point('states',cache('guid unread',{'feedurl':F.FEEDURL['Tech Daily']}))],
            'mark-as-read-on-hover '+value,before=feed(0))
        add('mark-feed-jump-'+value,[K('A')],[point('focus',focus(F.ALL_TITLES)),point('states',cache('guid unread'))],
            'confirm-mark-feed-read no\nmarkfeedread-jumps-to-next-unread '+value,
            before=[{'cli':['-I','read.txt']}]+feed(0),extra={'read.txt':'f1\nf2\nf3\n'})
        add('wrap-scroll-'+value,[K('Down')],[point('focus',focus(F.FEED_TITLES))],'wrap-scroll '+value,before=[K('End')])
        add('confirm-mark-feed-'+value,[K('A')],[point('states',cache('guid unread')),point('prompt',scr('message'))],
            'confirm-mark-feed-read '+value)
        add('confirm-mark-all-'+value,[K('C')],[point('states',cache('guid unread')),point('prompt',scr('message'))],
            'confirm-mark-all-feeds-read '+value)
        add('confirm-delete-'+value,[K('Control+d')],[point('states',cache('guid deleted')),point('prompt',scr('message'))],
            'confirm-delete-all-articles '+value,before=feed(0))
        add('confirm-exit-'+value,[K('q')],[point('exit',scr('exited')),point('prompt',scr('message',after_exit=True))],
            'confirm-exit '+value)
        add('show-read-feeds-'+value,[],[point('feeds',labels(F.FEED_TITLES))],'show-read-feeds '+value,
            before=[{'cli':['-I','read.txt']}],extra={'read.txt':'t1\nt2\nt3\nt4\n'})
        add('show-read-articles-'+value,feed(0),[point('articles',labels(F.TECH_TITLES))],'show-read-articles '+value,
            before=[{'cli':['-I','read.txt']}],extra={'read.txt':'t4\n'})
        add('goto-next-feed-'+value,[K('n')],[point('selection',focus(F.ALL_TITLES))],'goto-next-feed '+value,
            before=[{'cli':['-I','read.txt']}]+feed(0),extra={'read.txt':'t1\nt2\nt3\nt4\n'})
    add('random-single-unread',[K('Control+k')],[point('focus',focus(F.TECH_TITLES))],'goto-next-feed no',
        before=[{'cli':['-I','read.txt']}]+feed(0),extra={'read.txt':'t1\nt2\nt4\n'})
    add('hard-quit',[K('Q')],[point('exit',scr('exited'))],'confirm-exit yes')
    add('cancel-read-confirmation',[K('A'),K('n')],[point('states',cache('guid unread'))])
    add('cancel-delete-confirmation',[K('Control+d'),K('n')],[point('states',cache('guid deleted'))],before=feed(0))
    add('cancel-flags',[K('Control+e'),{'type':'xyz'},K('Escape')],[point('flags',cache('flags',{'guid':'t4'}))],
        before=feed(0)+[K('Control+e'),P('a')])
    add('cancel-filter',[K('F'),{'type':'title =~ "kernel"'},K('Escape')],[point('articles',labels(F.TECH_TITLES))],before=feed(0))
    out.extend(scenarios('setting-effects','settings',cases,chunk=8))

    files=F.library(**{'source.conf':'text-width 44\n'})
    steps=[C('set text-width 21'),C('set text-width 22'),C('set text-width 21'),K('q')]
    out.append(episode('command-history','history',[
        cp('saved','Keep command history when quitting.',steps,[point('history',file('.newsboat/history.cmdline'))]),
        cp('recalled','Recall the latest command after restarting.',[{'restart':True},K(':'),K('Up')],
           [point('line',scr('message',nonempty=True))],depends=['saved']),
    ],files=files))
    out.append(episode('search-history','history',[
        cp('saved','Keep search history when quitting.',
           [K('/'),P('kernel'),K('q'),K('/'),P('noodles'),K('q'),K('q')],
           [point('history',file('.newsboat/history.search'))]),
        cp('recalled','Recall the latest search after restarting.',[{'restart':True},K('/'),K('Up')],
           [point('line',scr('message',nonempty=True))],depends=['saved']),
    ]))
    out.append(episode('history-limit','history',[
        cp('bounded','Bound persisted history to two commands.',
           [C('set text-width 11'),C('set text-width 12'),C('set text-width 13'),K('q')],
           [point('history',file('.newsboat/history.cmdline'))])],files=F.library('history-limit 2\n')))
    out.append(episode('history-alternate-files','history',[
        cp('saved','Use alternate search and command-history files.',
           [{'restart':['--search-history-file','searches.txt','--cmdline-history-file','commands.txt']},
            C('set text-width 25'),K('/'),P('kernel'),K('q'),K('q')],
           [point('commands',file('commands.txt')),point('searches',file('searches.txt'))])]))

    cases=[]
    for name,config,before,pattern,attrs in [
        ('focus-colors','color listfocus_unread red blue bold',[], 'Tech Daily',['fg=red','bg=blue','bold']),
        ('title-color','color info green default',[], 'Newsboat',['fg=green']),
        ('text-highlight','highlight all "kernel" red default bold',feed(0),'kernel',['fg=red','bold']),
        ('article-highlight','highlight-article "author =~ \\"Linus\\"" yellow default bold',feed(0),'Compiler news',['fg=brown','bold']),
        ('feed-highlight','highlight-feed "tags # \\"food\\"" cyan default bold',[],'Food Notes',['fg=cyan','bold']),
        ('source-highlight','highlight article "Rust" magenta',feed(0)+article(2),'Rust',['fg=magenta']),
    ]:
        c=cp(name,'Apply '+name+'.',[],[point('styles',scr('style-flags',pattern=pattern,attributes=attrs,nonempty=True))])
        cases.append((c,F.library(config),before))
    out.extend(scenarios('colors-highlights','appearance',cases))
    for name,config in [('hidden','show-title-bar no'),('hints-hidden','show-keymap-hint no'),
                        ('swapped','swap-title-and-hints yes')]:
        out.append(episode('display-'+name,'appearance',[
            cp('display','Apply '+name+' to the screen.',[],[point('bars',scr('bars'))])],files=F.library(config)))

    # Subscription syntax changes names, tags and membership, independently of the RSS payload.
    cases=[]
    for name,urls in [('title-override','file://feeds/tech.xml "~Computing"\nfile://feeds/food.xml\n'),
                      ('hidden','file://feeds/tech.xml "!"\nfile://feeds/food.xml\n'),
                      ('quoted-tag','file://feeds/tech.xml "two words" news\nfile://feeds/food.xml\n'),
                      ('comments','# comment\n\nfile://feeds/tech.xml tech # inline comment\nfile://feeds/food.xml\n'),
                      ('duplicate-url','file://feeds/tech.xml tech\nfile://feeds/tech.xml duplicate\nfile://feeds/food.xml\n'),
                      ('reordered','file://feeds/cast.xml\nfile://feeds/tech.xml\nfile://feeds/food.xml\n')]:
        c=cp(name,'Read subscription syntax '+name+'.',[],[point('feeds',labels(F.FEED_TITLES+['Computing'])),
                                                        point('opml',cli(['--export-to-opml2'],'opml'))])
        cases.append((c,F.library(urls=urls),[]))
    out.extend(scenarios('subscriptions','subscriptions',cases))
    out.append(episode('query-read-through','query-feeds',[
        cp('read','Reading a query result marks the original article read.',feed(3)+article(0)+[K('q')],
           [point('origin-state',cache('unread',{'guid':'t4'},expected={'rows':[[0]]}))]),
        cp('flags','Changing flags through a query updates the original article.',[K('Control+e'),P('z')],
           [point('origin-flags',cache('flags',{'guid':'t4'}))],depends=['read']),
        cp('delete','Deleting a query result marks the original article deleted.',[K('D')],
           [point('origin-delete',cache('deleted',{'guid':'t4'}))],depends=['flags']),
    ],files=F.library(urls=query_urls('Every article','title =~ "."'))))
    return out
