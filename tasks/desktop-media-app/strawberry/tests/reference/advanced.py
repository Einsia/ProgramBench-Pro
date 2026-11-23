"""Standard-only recipes for extended local product features."""
import time
from reference.recipes import act,click,menu,snapshot,chooser,settings,combo,close_dialog,expand


def cover_window(c):
    titles=c.call(op='windows')['windows']
    if not any('Cover Manager' in w['title'] for w in titles):menu(c,'Tools','Cover Manager')
    act(c,'maximize');act(c,'wait',seconds=.4)


def cover_menu(c,action,album='Lina Vale - Northern Lights'):
    o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='list item' and n['name']==album)
    act(c,'click',target={'ref':n['ref']},button='right')
    x,y,w,h=n['bounds'];offset={'load':55,'save':32,'unset':123,'delete':168,'clear':146}[action]
    act(c,'click',x=int(x+w/2+90),y=int(y+h/2+offset));act(c,'wait',seconds=.4)


def execute(c,a):
    op=a['op']
    if op=='cover-embed':
        settings(c,'Covers')
        act(c,'check',target={'role':'radio button','name':'Save album covers as embedded cover'},checked=True)
        click(c,'OK','push button')
        cover_window(c);cover_menu(c,'load');chooser(c,a['file']);act(c,'wait',seconds=1)
    elif op=='cover-load':
        cover_window(c);cover_menu(c,'load');chooser(c,a['file']);act(c,'wait',seconds=1)
    elif op=='cover-save':
        cover_window(c);cover_menu(c,'save');chooser(c,a['file']);act(c,'wait',seconds=.5)
    elif op=='cover-delete':
        cover_window(c);cover_menu(c,'delete');act(c,'wait',seconds=1)
        o=snapshot(c)
        yes=next((n for n in o['nodes'] if n['role'] in ('push button','button') and n['name']=='Yes'),None)
        if yes:click(c,'Yes','push button')
    elif op=='organize-copy':organize_copy(c,a)
    elif op=='save-all':save_all(c,a)
    elif op=='smart-configure':smart_configure(c,a)
    elif op=='smart-edit':smart_edit(c,a['field'],a['value'])
    elif op=='smart-delete':smart_delete(c)
    elif op=='loudness':
        settings(c,'Collection')
        act(c,'check',target={'role':'check box','name':'Perform song EBU R 128 analysis (required for EBU R 128 loudness normalization)'},checked=True)
        click(c,'OK','push button');menu(c,'Tools','Do a full collection rescan');act(c,'wait',seconds=3)
        click(c,'Collection','page tab');o=snapshot(c)
        n=next(n for n in o['nodes'] if n['role']=='text' and 78<=n['bounds'][0]<250 and n['bounds'][1]<90)
        act(c,'fill',target={'ref':n['ref']},value=a['file'].removesuffix('.flac'));act(c,'wait',seconds=.7)
        expand(c,'Signal Ensemble');expand(c,'Channel Studies');click(c,a['file'].removesuffix('.flac'),'table cell',click_count=2)
        click(c,a['file'].removesuffix('.flac'),'table cell');act(c,'press',key='Control+e');act(c,'maximize');click(c,'Summary','page tab');act(c,'wait',seconds=1)
    else:raise ValueError('unknown advanced recipe '+op)

def smart_edit(c,field='Artist',value='Lina',mode='AND'):
    click(c,'Smart playlists','page tab');o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='list item' and n['name']=='Lina Selection');act(c,'click',target={'ref':n['ref']});o=snapshot(c)
    act(c,'click',x=123,y=54);act(c,'wait',seconds=.5);act(c,'maximize')
    # The wizard is the same public flow as creation; update the first search row.
    o=snapshot(c);combo_node=min((n for n in o['nodes'] if n['role']=='combo box' and n['bounds'][0]<170 and n['bounds'][1]>150),key=lambda n:n['bounds'][1])
    if combo_node['name']!=field:
        act(c,'click',target={'ref':combo_node['ref']});click(c,field,'list item')
    fields=[n for n in snapshot(c)['nodes'] if n['role']=='text' and n['bounds'][1]>150 and n['bounds'][2]>500]
    act(c,'fill',target={'ref':min(fields,key=lambda n:n['bounds'][1])['ref']},value=value)
    click(c,'Next >','push button');act(c,'wait',seconds=.5);click(c,'Next >','push button');act(c,'wait',seconds=.5)
    click(c,'Finish','push button');act(c,'wait',seconds=.7)


def smart_delete(c):
    click(c,'Smart playlists','page tab');o=snapshot(c);n=next(n for n in o['nodes'] if n['role']=='list item' and n['name']=='Lina Selection');act(c,'click',target={'ref':n['ref']});o=snapshot(c)
    act(c,'click',x=153,y=54);act(c,'wait',seconds=.4)
    o=snapshot(c);yes=next((n for n in o['nodes'] if n['role'] in ('push button','button') and n['name'] in ('Yes','Delete')),None)
    if yes:act(c,'click',target={'ref':yes['ref']})


def smart_configure(c,a):
    """Fill the standard wizard by its visible fields, including AND/OR and limits."""
    click(c,'Smart playlists','page tab')
    click(c,'New smart playlist','push button');act(c,'maximize');act(c,'wait',seconds=.6)
    mode={'AND':'Match every search term (AND)','OR':'Match one or more search terms (OR)','ALL':'Include all songs'}[a.get('mode','AND')]
    if mode!='Match every search term (AND)':combo(c,'Match every search term (AND)',mode)
    for i,term in enumerate(a.get('terms',[])):
        if i:
            o=snapshot(c)
            placeholder=max((n for n in o['nodes'] if n['role']=='text' and n['bounds'][0]>300 and 150<n['bounds'][1]<610),key=lambda n:n['bounds'][1])
            x,y,w,h=placeholder['bounds'];act(c,'click',x=x+w//2,y=y+h//2)
        o=snapshot(c)
        rows=sorted((n for n in o['nodes'] if n['role']=='combo box' and n['bounds'][0]<170 and 150<n['bounds'][1]<610),key=lambda n:n['bounds'][1])
        row=rows[i];y=row['bounds'][1]
        if row['name']!=term['field']:
            act(c,'click',target={'ref':row['ref']});click(c,term['field'],'list item')
        o=snapshot(c)
        operator=next(n for n in o['nodes'] if n['role']=='combo box' and 170<=n['bounds'][0]<310 and abs(n['bounds'][1]-y)<10)
        wanted=term.get('operator','contains')
        if operator['name']!=wanted:
            act(c,'click',target={'ref':operator['ref']});click(c,wanted,'list item')
        o=snapshot(c)
        entry=next(n for n in o['nodes'] if n['role'] in ('text','spin button') and n['bounds'][0]>=300 and abs(n['bounds'][1]-y)<10)
        act(c,'fill',target={'ref':entry['ref']},value=str(term['value']))
    act(c,'wait',seconds=1)
    click(c,'Next >','push button');act(c,'wait',seconds=.5)
    act(c,'check',target={'role':'radio button','name':'Sort songs by'},checked=True)
    combo(c,'Album Artist','Title')
    o=snapshot(c);order=next(n for n in o['nodes'] if n['role']=='combo box' and n['bounds'][0]>700)
    act(c,'click',target={'ref':order['ref']});act(c,'press',key='Home');act(c,'press',key='Return')
    if 'limit' in a:
        act(c,'check',target={'role':'radio button','name':'Only show the first'},checked=True)
        act(c,'fill',target={'role':'spin button','name':'Limits'},value=str(a['limit']))
    else:act(c,'check',target={'role':'radio button','name':'Show all the songs'},checked=True)
    click(c,'Next >','push button');act(c,'wait',seconds=.5)
    o=snapshot(c);entry=next(n for n in o['nodes'] if n['role']=='text' and 'editable' in n.get('states',[]) and 65<n['bounds'][1]<125)
    act(c,'fill',target={'ref':entry['ref']},value=a['name'])
    if a.get('dynamic'):act(c,'check',target={'role':'check box','name':'Use dynamic mode'},checked=True)
    click(c,'Finish','push button');act(c,'wait',seconds=.5)


def organize_copy(c,a):
    click(c,'Collection','page tab');click(c,a['artist'],'table cell',click_count=2);act(c,'wait',seconds=.5)
    o=snapshot(c);n=[n for n in o['nodes'] if n['role']=='table cell' and n['name']==a['title'] and n['bounds'][0]>315][-1]
    act(c,'click',target={'ref':n['ref']},button='right');act(c,'wait',seconds=.4)
    x,y,w,h=n['bounds'];act(c,'click',x=int(x+w/2+90),y=int(y+h/2+412))
    act(c,'maximize');act(c,'wait',seconds=.5)
    o=snapshot(c);after=next(n for n in o['nodes'] if n['role']=='combo box' and 'original files' in n['name'])
    if after['name']!='Keep the original files':combo(c,after['name'],'Keep the original files')
    act(c,'fill',target={'role':'text','name':'Naming options'},value=a['pattern'])
    act(c,'check',target={'role':'check box','name':'Replace spaces with underscores'},checked=False)
    act(c,'check',target={'role':'check box','name':'Overwrite existing files'},checked=a.get('overwrite',False))
    click(c,'OK','push button');act(c,'wait',seconds=2)


def save_all(c,a):
    menu(c,'Playlist','Save all playlists...')
    o=snapshot(c);d=next(n for n in o['nodes'] if n['role']=='dialog')
    entry=next(n for n in o['nodes'] if n['role']=='text' and n.get('window')==d['ref'])
    act(c,'fill',target={'ref':entry['ref']},value=a['directory'])
    o=snapshot(c);fmt=next(n for n in o['nodes'] if n['role']=='combo box' and n.get('window')==d['ref'])
    act(c,'click',target={'ref':fmt['ref']})
    options=[n for n in snapshot(c)['nodes'] if n['role'] in ('list item','menu item') and 'xspf' in n['name'].casefold()]
    assert options,'XSPF selection unavailable';act(c,'click',target={'ref':options[0]['ref']})
    click(c,'OK','push button');act(c,'wait',seconds=1)
