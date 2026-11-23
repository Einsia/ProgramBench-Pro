"""Configuration exports, live assignments, validation, source and key maps."""
from spec_common import (C, F, K, P, cache, cli, contains, cp, feed, file, labels, point, quote, scr, episode)

# Each setting names a different public option. Network-only service credentials and external-program
# options are intentionally absent. Their execution is unavailable in the offline reference environment.
SETTINGS = {
    'always-display-description': ('bool','yes'), 'article-sort-order':('str','title-asc'),
    'articlelist-format':('str','%i|%t'), 'articlelist-title-format':('str','Articles: %T %t'),
    'auto-reload':('bool','yes'), 'cleanup-on-quit':('str','no'),
    'confirm-delete-all-articles':('bool','no'), 'confirm-exit':('bool','yes'),
    'confirm-mark-all-feeds-read':('bool','no'), 'confirm-mark-feed-read':('bool','no'),
    'datetime-format':('str','%Y-%m-%d'), 'delete-read-articles-on-quit':('bool','yes'),
    'dialogs-title-format':('str','Open views'), 'dirbrowser-title-format':('str','Directory %f'),
    'display-article-progress':('bool','no'), 'download-filename-format':('str','%n-%t.%e'),
    'download-path':('str','~/media/'), 'error-log':('str','errors.log'),
    'feed-sort-order':('str','title-asc'), 'feedlist-format':('str','%i|%t|%u'),
    'feedlist-title-format':('str','Feeds %u/%t'), 'filebrowser-title-format':('str','Files %f'),
    'goto-first-unread':('bool','no'), 'goto-next-feed':('bool','no'),
    'help-title-format':('str','Key help'), 'history-limit':('int','8'),
    'ignore-mode':('str','display'), 'itemview-title-format':('str','Reading %T'),
    'keep-articles-days':('int','3000'), 'keep-forever-if-flagged-with':('str','aB'),
    'mark-as-read-on-hover':('bool','yes'), 'markfeedread-jumps-to-next-unread':('bool','yes'),
    'max-items':('int','25'), 'podcast-auto-enqueue':('bool','yes'),
    'prepopulate-query-feeds':('bool','yes'), 'refresh-on-startup':('bool','yes'),
    'reload-only-visible-feeds':('bool','yes'), 'reload-threads':('int','3'),
    'reload-time':('int','90'), 'restrict-filename':('bool','no'), 'save-path':('str','~/saved/'),
    'scrolloff':('int','3'), 'searchresult-title-format':('str','Search %s'),
    'selectfilter-title-format':('str','Choose filter'), 'selecttag-format':('str','%T|%u'),
    'selecttag-title-format':('str','Choose tag'), 'show-keymap-hint':('bool','no'),
    'show-read-articles':('bool','no'), 'show-read-feeds':('bool','no'),
    'show-title-bar':('bool','no'), 'suppress-first-reload':('bool','yes'),
    'swap-title-and-hints':('bool','yes'), 'text-width':('int','42'),
    'toggleitemread-jumps-to-next':('bool','no'), 'toggleitemread-jumps-to-next-unread':('bool','yes'),
    'urlview-title-format':('str','Article URLs'), 'wrap-scroll':('bool','yes'),
}


def configcheck(name, path='dump.txt'):
    return file(path,'config',name=name,value_type=SETTINGS.get(name,('str',))[0])


def build():
    out=[]
    out.append(episode('config-defaults','configuration',[
        cp('export','Export the default effective configuration.',[C('dumpconfig dump.txt')],
           [point(name,configcheck(name),'The exported value of '+name+' has its default meaning.') for name in SETTINGS])
    ],load=False))
    for chunk in range(0,len(SETTINGS),12):
        cps=[]
        for name,(typ,value) in list(SETTINGS.items())[chunk:chunk+12]:
            # Every case starts from fresh app/config so transient display settings cannot affect later cases.
            steps=[{'restart':True},C('set '+name+' '+quote(value)),C('dumpconfig dump.txt')]
            cps.append(cp(name+'-assign','Assign '+name+' to '+value,steps,
                          [point('value',configcheck(name),'The live assignment appears in the effective configuration.')]))
            cps.append(cp(name+'-reset','Reset '+name+' to its default.',[C('set '+name+'&'),C('dumpconfig dump.txt')],
                          [point('value',configcheck(name),'The reset restores the default configuration value.')],
                          depends=[name+'-assign']))
        out.append(episode('config-live-'+str(chunk//12+1),'configuration',cps,load=False))
    cps=[]
    for name,(typ,value) in SETTINGS.items():
        if typ not in ('bool','int'):
            continue
        bad='maybe' if typ=='bool' else 'twelve'
        cps.append(cp(name,'Reject the invalid value '+bad+' for '+name,
                      [C('set '+name+' '+bad)], [point('error',scr('message',nonempty=True))]))
    out.append(episode('config-invalid-values','configuration',cps,load=False))
    cps=[]
    for name,value in [('yes','yes'),('no','no'),('true','true'),('false','false')]:
        cps.append(cp('boolean-'+name,'Use Boolean spelling '+name,
                      [C('set show-read-feeds '+value),C('dumpconfig dump.txt')],
                      [point('value',configcheck('show-read-feeds'))]))
    for name,value in [('zero','0'),('positive','17'),('negative','-1'),('leading-zero','007')]:
        cps.append(cp('integer-'+name,'Set text-width to '+value,
                      [C('set text-width '+value),C('dumpconfig dump.txt')],
                      [point('value',configcheck('text-width'))],depends=['integer-positive'] if name=='negative' else []))
    cps.extend([
        cp('toggle','Toggle a Boolean value.',[C('set show-read-feeds no'),C('set show-read-feeds!'),C('dumpconfig dump.txt')],
           [point('value',configcheck('show-read-feeds'))]),
        cp('query','Query the current value of text-width.',[C('set text-width 33'),C('set text-width')],
           [point('value',contains('text-width=33'))]),
        cp('unknown-setting','Query an unknown setting.',[C('set not-a-setting')],[point('error',scr('message',nonempty=True))]),
        cp('unknown-command','Execute an unknown command.',[C('not-a-command')],[point('error',scr('message',nonempty=True))]),
        cp('no-operation','Request an unknown operation.',[C('exec not-an-operation')],[point('error',scr('message',nonempty=True))]),
        cp('wrong-dialog','Request an article-only operation in the feed list.',[C('exec save-all')],[point('error',scr('message',nonempty=True))]),
    ])
    out.append(episode('config-value-syntax','configuration',cps,load=False))

    source='''# comment before assignments
text-width 31 # inline comment
feedlist-title-format "Quoted # remains"
include "nested.conf"
show-read-feeds yes
show-read-feeds no
'''
    files=F.library(**{'source.conf':source,'nested.conf':'history-limit 12\nfeedlist-format "%i \\"quoted\\" %t"\n'})
    out.append(episode('config-source','configuration',[
        cp('source','Load source.conf.',[C('source source.conf'),C('dumpconfig dump.txt')],
           [point(n,configcheck(n)) for n in ['text-width','feedlist-title-format','history-limit','feedlist-format','show-read-feeds']]),
        cp('missing','Load a missing configuration file.',[C('source missing.conf')],[point('error',scr('message',nonempty=True))]),
    ],files=files,load=False))
    badconfig=[('unknown-command','not-a-command yes'),('missing-argument','text-width'),
               ('invalid-boolean','show-read-feeds perhaps'),('invalid-number','max-items abc'),
               ('missing-include','include missing.conf'),('invalid-color','color listfocus notacolor default'),
               ('invalid-element','color missing red default'),('invalid-attribute','color listfocus red black nothing'),
               ('invalid-regex','highlight all "[" red'),('missing-filter','define-filter "Name"'),
               ('invalid-bind','bind-key X nonexistent-op'),('invalid-context','bind-key X open nosuchdialog'),
               ('missing-macro','macro'),('missing-ignore','ignore-article "*"'),
               ('invalid-query','ignore-article "*" "broken"')]
    # The per-case config is passed to CLI rather than replacing the interactive config: a deliberate
    # configuration error must not prevent the next scenario from running.
    files=F.library(**{name+'.conf':text+'\n' for name,text in badconfig})
    cps=[cp(name,'Load invalid configuration '+name,[],
            [point('exit',cli(['-C',name+'.conf','-x','print-unread'],'exit')),
             point('diagnostic',cli(['-C',name+'.conf','-x','print-unread'],'stderr',nonempty=True))])
         for name,_ in badconfig]
    out.append(episode('config-startup-errors','configuration',cps,files=files,load=False))

    conf='''bind-key X open feedlist
bind-key Y toggle-article-read articlelist
bind-key Z edit-flags articlelist
unbind-key A feedlist
bind zz feedlist set feedlist-title-format "Sequence complete" -- "Sequence title"
bind <C-y> everywhere set feedlist-title-format "Control binding"
macro x set feedlist-format "%i|%t" ; set feedlist-title-format "Macro complete" -- "Custom format"
define-filter "Kernel stories" "title =~ \\"kernel\\""
define-filter "Unread stories" "unread = \\"yes\\""
'''
    cps=[
        cp('bind-open','Use X to open the feed.',[K('X')],[point('articles',labels(F.TECH_TITLES,nonempty=True))]),
        cp('bind-toggle','Use Y to toggle read status.',[K('Y')],[point('read',cache('guid unread'))],depends=['bind-open']),
        cp('bind-flags','Use Z to edit flags.',[K('Home'),K('Z'),P('dbB')],[point('flags',cache('flags',{'guid':'t4'}))],depends=['bind-toggle']),
        cp('sequence','Use the custom two-key sequence.',[K('q'),K('z'),K('z')],[point('title',contains('Sequence complete'))],depends=['bind-flags']),
        cp('control','Use the custom control binding.',[K('Control+y')],[point('title',contains('Control binding'))]),
        cp('macro','Run the custom macro.',[K(','),K('x')],[point('title',contains('Macro complete'))]),
        cp('defined-filter','Choose the saved Kernel stories filter.',feed(0)+[K('f'),K('Home'),K('Enter')],
           [point('articles',labels(F.TECH_TITLES,nonempty=True))]),
    ]
    out.append(episode('config-bindings-macros','keybindings',cps,files=F.library(conf)))
    return out
