"""Deterministic GUI recipes for the pinned standard, through public runtime operations only."""
import time


def act(c,op,**fields):return c.call(op=op,**fields)
def click(c,name,role=None,**extra):
    target={'name':name}
    if role:target['role']=role
    return act(c,'click',target=target,**extra)

def menu(c,*labels):
    for label in labels:click(c,label,'menu item')

def snapshot(c):return act(c,'observe',tree=True)

def dialog(c):
    o=snapshot(c)
    return any(n['role']=='dialog' for n in o['nodes'])

def close_dialog(c):
    for _ in range(4):
        if not dialog(c):return
        act(c,'press',key='Escape')

def chooser(c,path,fmt=None):
    o=snapshot(c)
    field=next(n for n in o['nodes'] if n['role'] in ('text','entry') and n.get('name','').startswith(('File name','Directory','Folder')))
    act(c,'fill',target={'ref':field['ref']},value=path)
    if fmt:
        choices={'m3u':'M3U playlists (*.m3u *.m3u8)','pls':'PLS playlists (*.pls)','xspf':'XSPF playlists (*.xspf)'}
        o=snapshot(c);combos=[n for n in o['nodes'] if n['role']=='combo box' and '(*.' in n.get('name','')]
        if combos and not combos[-1]['name'].casefold().startswith(fmt):
            act(c,'click',target={'ref':combos[-1]['ref']})
            o=snapshot(c);matches=[n for n in o['nodes'] if n.get('name','').casefold().startswith(fmt) and n['role'] in ('list item','menu item')]
            assert matches,'playlist format choice missing'
            act(c,'click',target={'ref':matches[0]['ref']})
    act(c,'press',key='Return')
    act(c,'wait',seconds=.5)

def tags_open(c,title,tab='Tags'):
    close_dialog(c);click(c,title,'table cell');act(c,'press',key='Control+e')
    act(c,'maximize');click(c,tab,'page tab')


def execute(c,actions):
    for a in actions:
        op=a['op']
        if op in ('press','wait','maximize','click','fill','type','check'):
            act(c,op,**{k:v for k,v in a.items() if k!='op'})
        elif op=='menu':menu(c,*a['path'])
        elif op in ('open','add-file','load-playlist','save-playlist'):
            if op=='open':menu(c,'Music','Open file...')
            elif op=='add-file':menu(c,'Playlist','Add file...')
            elif op=='load-playlist':click(c,'Load playlist','push button')
            else:click(c,'Save playlist','push button')
            chooser(c,a['file'],a.get('format'))
            if op=='load-playlist':
                o=snapshot(c);tabs=[n for n in o['nodes'] if n['role']=='page tab' and n['bounds'][0]>300]
                act(c,'click',target={'ref':tabs[-1]['ref']})
            if op=='open':
                menu(c,'Music','Play');act(c,'wait',seconds=1)
        elif op=='select':click(c,a['title'],'table cell',**({'click_count':2} if a.get('double') else {}));act(c,'wait',seconds=1 if a.get('double') else .1)
        elif op=='playlist-filter':
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='text' and n['bounds'][0]>400 and n['bounds'][1]<80)
            act(c,'fill',target={'ref':n['ref']},value=a['value']);act(c,'wait',seconds=.6)
        elif op=='sort':
            click(c,a['column'],'table column header')
            if a['descending']:click(c,a['column'],'table column header')
        elif op in ('undo','redo'):
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='push button' and n.get('name','').startswith(op.capitalize()))
            act(c,'activate',target={'ref':n['ref']})
        elif op=='tab':click(c,a['name'],'page tab')
        elif op=='rename-playlist':
            o=snapshot(c);tabs=[n for n in o['nodes'] if n['role']=='page tab' and n['bounds'][0]>300]
            act(c,'click',target={'ref':tabs[-1]['ref']},click_count=2)
            act(c,'press',key='Control+a');act(c,'type',value=a['name']);act(c,'press',key='Return')
        elif op=='tags':
            tags_open(c,a['title'])
            for label,v in a['fields'].items():
                role='spin button' if label in ('Year','Track','Disc') else 'text'
                act(c,'fill',target={'role':role,'name':label},value=v)
            act(c,'activate',target={'role':'push button','name':'Discard' if a.get('discard') else 'Save'});act(c,'wait',seconds=.5)
            if a.get('reopen'):tags_open(c,a['fields'].get('Title',a['title']) if not a.get('discard') else a['title'])
        elif op=='lyrics':
            tags_open(c,a['title'],'Lyrics');o=snapshot(c)
            fields=[n for n in o['nodes'] if n['role']=='text' and 'editable' in n.get('states',[]) and n['bounds'][2]>300 and n['bounds'][3]>50]
            assert fields,'lyrics editor unavailable'
            act(c,'fill',target={'ref':fields[-1]['ref']},value=a['value']);click(c,'Save','push button');act(c,'wait',seconds=.5)
            tags_open(c,a['title'],'Lyrics')
        else:raise ValueError('unknown reference recipe '+op)
    act(c,'move',x=1200,y=780)
    act(c,'wait',seconds=.3)


def combo(c,current,choice):
    click(c,current,'combo box');click(c,choice,'list item')


def settings(c,page):
    close_dialog(c);act(c,'press',key='Control+p');act(c,'maximize');click(c,page,'table cell');act(c,'wait',seconds=.5)
    if page in ('Behavior','Backend'):act(c,'scroll',x=1350,y=700,delta_y=650)


def expand(c,name):
    act(c,'click',target={'name':name,'role':'table cell','exact':False});act(c,'press',key='Right');act(c,'wait',seconds=.5)


_base_execute=execute

def execute(c,actions):
    for a in actions:
        op=a['op']
        if op=='show-repeat-mode':
            menu(c,'Playlist','Repeat mode')
        elif op=='volume':
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='slider' and n['bounds'][0]>1250)
            x,y,w,h=n['bounds'];act(c,'click',x=int(x+w*a['percent']/100-1),y=int(y+h/2))
        elif op=='equalizer':
            if not dialog(c):menu(c,'Tools','Equalizer')
            act(c,'check',target={'role':'check box','name':'Enable equalizer'},checked=a['enabled'])
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='combo box')
            combo(c,n['name'],a['preset'])
        elif op=='balance':
            act(c,'check',target={'role':'check box','name':'Enable stereo balancer'},checked=True)
            o=snapshot(c);n=max((n for n in o['nodes'] if n['role']=='slider'),key=lambda n:n['bounds'][2])
            act(c,'click',target={'ref':n['ref']});act(c,'press',key='Home' if a['left'] else 'End')
        elif op=='setting':
            settings(c,a['page'])
            if 'spin' in a:act(c,'fill',target={'role':'spin button','name':a['spin']},value=a['value'])
            if 'radio' in a:act(c,'check',target={'role':'radio button','name':a['radio']},checked=True)
            if 'spin' in a or 'radio' in a:
                click(c,'Cancel' if a.get('cancel') else 'OK','push button')
                if a.get('reopen'):settings(c,a['page'])
        elif op=='collection-browse':
            click(c,'Collection','page tab');expand(c,'Lina Vale');expand(c,'Northern Lights')
        elif op=='collection-filter':
            click(c,'Collection','page tab');o=snapshot(c)
            n=next(n for n in o['nodes'] if n['role']=='text' and 78<=n['bounds'][0]<250 and n['bounds'][1]<90)
            act(c,'fill',target={'ref':n['ref']},value=a['value']);act(c,'wait',seconds=1)
            for name in a.get('expand',[]):expand(c,name)
        elif op=='collection-add':click(c,a['title'],'table cell',click_count=2);act(c,'wait',seconds=1)
        elif op=='smart-create':
            click(c,'Smart playlists','page tab');click(c,'New smart playlist','push button');act(c,'maximize');act(c,'wait',seconds=.5)
            o=snapshot(c);n=min((n for n in o['nodes'] if n['role']=='combo box' and n['name']=='Album Artist'),key=lambda n:n['bounds'][1])
            act(c,'click',target={'ref':n['ref']});click(c,a['field'],'list item')
            o=snapshot(c);n=min((n for n in o['nodes'] if n['role']=='text' and n['bounds'][1]>150 and n['bounds'][2]>500),key=lambda n:n['bounds'][1])
            act(c,'fill',target={'ref':n['ref']},value=a['value']);act(c,'wait',seconds=1)
            click(c,'Next >','push button');act(c,'wait',seconds=.7)
            act(c,'check',target={'role':'radio button','name':'Sort songs by'},checked=True)
            combo(c,'Album Artist','Title')
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='combo box' and n['bounds'][0]>700)
            act(c,'click',target={'ref':n['ref']});act(c,'press',key='Home');act(c,'press',key='Return')
            act(c,'check',target={'role':'radio button','name':'Show all the songs'},checked=True)
            click(c,'Next >','push button');act(c,'wait',seconds=.7)
            o=snapshot(c);fields=[n for n in o['nodes'] if n['role']=='text' and 'editable' in n.get('states',[]) and n['bounds'][0]<500 and 65<n['bounds'][1]<150]
            assert fields,'smart playlist name unavailable';act(c,'fill',target={'ref':fields[-1]['ref']},value=a['name'])
            click(c,'Finish','push button');act(c,'wait',seconds=.5)
        elif op=='smart-open':
            click(c,'Smart playlists','page tab');click(c,a['name'],'list item',click_count=2);act(c,'wait',seconds=1)
        elif op=='queue':
            for title in a['titles']:click(c,title,'table cell');act(c,'press',key='Control+d')
            click(c,'Queue','page tab')
        elif op=='cover-filter':
            o=snapshot(c);fields=[n for n in o['nodes'] if n['role']=='text' and 'editable' in n.get('states',[]) and n['bounds'][1]<120 and n['bounds'][0]>300]
            n=fields[-1];act(c,'fill',target={'ref':n['ref']},value=a['value']);act(c,'wait',seconds=.7)
        elif op=='organize':
            click(c,'Collection','page tab');click(c,'Lina Vale','table cell',click_count=2)
            act(c,'wait',seconds=.5);o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='table cell' and n['name']==a['title'] and n['bounds'][0]>315)
            act(c,'click',target={'ref':n['ref']},button='right');act(c,'wait',seconds=.5)
            # This Qt popup is painted but not exported as an accessible menu.
            # Its functional goals remain independent of this standard-only route.
            x,y,w,h=n['bounds'];act(c,'click',x=int(x+w/2+90),y=int(y+h/2+412))
            act(c,'maximize');act(c,'wait',seconds=.5)
            act(c,'fill',target={'role':'text','name':'Naming options'},value=a['pattern'])
            act(c,'check',target={'role':'check box','name':'Replace spaces with underscores'},checked=False)
            click(c,'OK','push button');act(c,'wait',seconds=2)
        elif op=='transcode':
            menu(c,'Tools','Transcode Music');act(c,'maximize');click(c,'Add...','push button');chooser(c,a['file'])
            o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='combo box' and '(.' in n.get('name',''))
            combo(c,n['name'],a['format']);click(c,'Select...','push button');chooser(c,a['destination'])
            click(c,'Start transcoding','push button');act(c,'wait',seconds=5)
        elif op.startswith(('cover-','smart-','loudness','organize-copy','save-all')):
            from reference.advanced import execute as advanced
            advanced(c,a)
        else:_base_execute(c,[a])
    if not actions or actions[-1]['op']!='show-repeat-mode':act(c,'move',x=1200,y=780)
    act(c,'wait',seconds=.5)
