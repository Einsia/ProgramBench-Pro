"""Deterministic visible interaction with the pinned standard answer only."""
import time

from .ui import UI, plain


def ui(ctx):
    if 'ui' not in ctx.state:ctx.state['ui']=UI(ctx.broker)
    return ctx.state['ui']


def prepare(ctx):
    u=ui(ctx)
    # The window precedes the full Electron menu and the first editor. Readiness
    # remains the shared AT-SPI criterion; recipes wait for their own controls.
    u.find('Tools','push button',timeout=30)
    if ctx.episode.get('selected'):u.note(ctx.episode['selected'])
    else:u.notebook('Workbench')
    u.notice();u.settle()


def path(ctx, value):
    area,_,name=value.partition('/')
    return ctx.episode['inputs'][area]+('/'+name if name else '')


def confirm(u):
    for name in ('OK','Delete','Yes','Restore'):
        try:u.click(name,'push button');return
        except AssertionError:continue
    raise AssertionError('confirmation control is missing')


def choose_folder(u, folder):
    u.file(folder,directory=True)


def execute(ctx, checkpoint):
    u=ui(ctx)
    for action in checkpoint['recipe']:run(ctx,u,action)
    if checkpoint['recipe'] and checkpoint['recipe'][-1]['op']=='hover-text':u.call('wait',seconds=1)
    else:u.settle(1.0)


def run(ctx,u,a):
    op=a['op']
    if op=='press':u.press(a['key'])
    elif op=='click':u.click(a.get('name'),a.get('role'))
    elif op=='menu':u.menu(*a['items'])
    elif op=='context':u.context(a['title'],*a['items'])
    elif op=='book':u.notebook(a['title'])
    elif op=='note':u.note(a['title'])
    elif op=='select-list':u.click(a['title'],'list item',exact=False)
    elif op=='title':u.fill('Note title',a['value'])
    elif op=='body':
        value=a['value'];paste_line='\n' not in value and not value.isascii()
        u.fill('Markdown editor',value+'\n' if paste_line else value)
        if paste_line:u.press('BackSpace')
        u.click('Note title','entry')
    elif op=='focus-body':u.click('Markdown editor','entry')
    elif op=='select-body':u.click('Markdown editor','entry');u.press('Control+A')
    elif op=='select-text':
        u.click('Markdown editor','entry');u.press('Control+Home')
        for _ in range(a.get('offset',0)):u.press('Right')
        for _ in a['text']:u.press('Shift+Right')
    elif op=='blur':u.click('Note title','entry')
    elif op=='new-note':u.create_note(a['title'],a['body'],a.get('todo',False));u.click('Markdown editor','entry')
    elif op=='new-notebook':
        if a.get('parent'):
            u.notebook(a['parent']);u.menu('File','New sub-notebook')
        else:u.click('New notebook','push button')
        u.fill('Title',a['title']);u.click('OK','push button');u.find(a['title'],'link',exact=False)
    elif op=='rename-book':
        u.context(a['old'],'Edit',role='link');u.fill('Title',a['title']);u.click('OK','push button')
    elif op in ('collapse-book','expand-book'):
        u.click(a['title'],'tree item',exact=False);u.press('Left' if op=='collapse-book' else 'Right')
    elif op=='move-note':
        u.context(a['title'],'Move to notebook')
        # The move chooser is a visible searchable notebook list.
        u.fill(None,a['book'],role='combo box');u.press('Return');u.click('OK','push button');u.notebook(a['book']);u.click(a['title'],'list item')
    elif op=='delete-permanent':
        u.note(a['title']);u.menu('Note','Permanently delete note');u.settle(.5)
        window=next(w for w in u.call('windows')['windows'] if w.get('active'))
        x,y,w,h=window['bounds'];assert w<700 and h<300,'expected the native confirmation dialog'
        u.call('click',x=round(x+w/4),y=round(y+h-36));u.settle(.7)
    elif op=='delete-note':
        u.context(a['title'],'Delete note')
        nodes=u.observe()['nodes']
        if any(n['role'] in ('dialog','alert') for n in nodes):confirm(u)
    elif op=='restore-note':
        u.context(a['title'],'Restore note');u.notebook(a['book']);u.click(a['title'],'list item')
    elif op=='todo-check':
        # Locate the completion checkbox inside the named list row, not the
        # Markdown checklist in the editor.
        obs=u.observe();row=next(n for n in obs['nodes'] if n['role']=='list item' and plain(a['title']) in plain(n['name']))
        x,y,w,h=row['bounds'];checkbox=next((n for n in obs['nodes'] if n['role']=='check box' and y<=n['bounds'][1]<y+h),None)
        assert checkbox,'the to-do completion control is missing'
        u.call('check',target=checkbox['ref'],checked=a['checked'])
    elif op=='add-tag':
        u.note('River survey')
        u.click('Tags','push button');u.fill(None,a['tag'],role='combo box');u.settle(.6);u.press('Return');u.click('OK','push button')
    elif op=='remove-tag':
        u.note('River survey')
        u.click('Tags','push button')
        node=u.find('Remove '+a['tag'],('push button','button'),exact=False)
        u.call('click',target=node['ref']);u.click('OK','push button')
    elif op=='tag':u.click(a['title'],'link',exact=False)
    elif op=='rename-tag':
        u.context(a['old'],'Rename',role='link');u.fill(None,a['title']);u.click('OK','push button')
    elif op=='body-checkbox':
        node=u.find(a['label'],'check box');u.call('check',target=node['ref'],checked=True)
    elif op=='rich-body':
        nodes=u.observe()['nodes']
        editor=next((n for n in nodes if n['role'] in ('paragraph','heading') and 'editable' in n.get('states',())),None)
        if editor is None:editor=next(n for n in nodes if n['role']=='document web' and not n['name'])
        u.call('click',target=editor['ref']);u.press('Control+A');u.call('type',value=a['value']);u.click('Note title','entry')
    elif op=='rich-select':
        nodes=u.observe()['nodes']
        editor=next(n for n in nodes if n['role'] in ('paragraph','heading') and 'editable' in n.get('states',()))
        u.call('click',target=editor['ref']);u.press('Control+A')
    elif op=='rich-cell':
        node=u.find(a['old'],('paragraph','table cell'),exact=True);u.call('click',target=node['ref'])
        u.press('Home');u.press('Shift+End');u.call('type',value=a['value']);u.click('Note title','entry')
    elif op=='rich-table-row':
        node=u.find(a['last'],('paragraph','table cell'),exact=True);u.call('click',target=node['ref']);u.press('End')
        for value in a['values']:u.press('Tab');u.call('type',value=value)
        u.click('Note title','entry')
    elif op=='hover-text':
        node=u.find(a['text'],('static','text'),exact=True);u.call('move',target=node['ref'],seconds=2)
    elif op=='line':
        u.click('Markdown editor','entry');u.press('Control+Home')
        for _ in range(a['line']):u.press('Down')
        u.press(a['key'])
    elif op=='search':
        u.fill('Search...',a['query']);u.press('Return')
        for title in a.get('titles',[]):u.find(title,'list item',exact=False,timeout=45)
        u.settle(.5)
    elif op=='goto':
        u.press('Control+P');u.settle(1.0)
        # Search indexing and the modal list update asynchronously. Refill the
        # query after a settled snapshot so the first keystrokes cannot land
        # while the picker is mounting.
        value=a['query'].split()[0]
        for attempt in range(3):
            u.fill(None,value)
            try:
                u.find(a['query'],'list item',exact=False,timeout=10)
                break
            except AssertionError:
                u.settle(.8)
                if attempt == 2: raise
                u.press('Control+A');u.call('type',value=value)
        u.click(a['query'],'list item',exact=False);u.find('Note title','entry')
    elif op=='local-find':u.click('Markdown editor','entry');u.press('Control+F');u.fill('Find',a['query']);u.press('Return')
    elif op=='replace':
        u.click('Markdown editor','entry');u.press('Control+F');u.fill('Find',a['find']);u.fill('Replace',a['replacement'])
        for label,value in [('match case',a['case']),('regexp',a['regex']),('by word',a['whole'])]:
            node=u.find(label,'check box');u.call('check',target=node['ref'],checked=value)
        u.click('replace all','push button');u.click('close','push button');u.click('Note title','entry')
    elif op=='sort':
        u.notebook('Workbench')
        # Turn off to-do pinning so a title sort has one unambiguous order.
        u.menu('View','Sort notes by','Title')
        u.click('View','push button');node=u.find('Uncompleted to-dos on top','check menu item')
        if 'checked' in node.get('states',[]):u.call('click',target=node['ref'])
        else:u.press('Escape')
        u.menu('View','Sort notes by','Reverse sort order') if a['direction']=='descending' else None
    elif op=='viewer':
        # The reference's layout sequence is editor -> split -> viewer.
        for _ in range(3):
            u.press('Control+L');u.settle(.5)
            if not any(n['role']=='entry' and n['name']=='Markdown editor' for n in u.observe()['nodes']):break
    elif op=='property-url':
        u.click('Edit','link',nth=2);u.fill(None,a['url']);u.click('OK','push button');u.click('Note properties','push button')
    elif op=='attach':
        u.click('Markdown editor','entry');u.press('Control+End');u.press('Return');u.click('Attach file','push button')
        u.file(path(ctx,a['path']));u.find('Note title','entry');u.settle()
    elif op=='note-link':
        u.click('Markdown editor','entry');u.press('Control+End');u.press('Return')
        u.click('Link to note...','push button');u.fill(None,a['title']);u.find(a['title'],('option','list item','static'),exact=False,timeout=30);u.press('Return');u.click('Note title','entry')
    elif op=='follow-link':run(ctx,u,{'op':'viewer'});u.click(a['title'],'link')
    elif op=='editor':
        for _ in range(3):
            if any(n['role']=='entry' and n['name']=='Markdown editor' for n in u.observe()['nodes']):break
            u.press('Control+L');u.settle(.4)
    elif op=='theme':
        u.menu('Tools','Options');u.click('Appearance','page tab')
        node=u.find('Automatically switch theme to match system theme','check box')
        u.call('check',target=node['ref'],checked=False)
        u.click('Theme','combo box');u.click(a['value'],'menu item');u.click('OK','push button')
    elif op=='alarm':
        for name,value in [('Month','01'),('Day','20'),('Year','2026'),('Hours','09'),('Minutes','30')]:
            u.fill(name,value,role='spin button')
        u.click('AM/PM','spin button');u.press('a');u.click('OK','push button')
    elif op=='clear-alarm':
        nodes=u.observe()['nodes'];node=next(n for n in nodes if n['role']=='push button' and ('20/01/2026' in n['name'] or '01/20/2026' in n['name']))
        u.call('click',target=node['ref']);u.click('Clear','push button')
    elif op=='wait-note':u.find('Note title','entry',timeout=30)
    elif op=='note-list-state':
        end=time.monotonic()+8
        while True:
            visible=any(n['role']=='landmark' and n['name']=='Note list' for n in u.observe()['nodes'])
            if visible==a['visible']:break
            if time.monotonic()>=end:raise AssertionError('note list did not reach requested visibility')
            u.settle(.3)
    elif op=='markdown-options':
        labels={'Sub':'~sub~','Sup':'^sup^','Emoji':'markdown emoji','Insert':'++insert++','Typographer':'typographer',
                'Deflist':'deflist','Abbr':'abbreviation','Fountain':'Fountain','Multitable':'multimarkdown table','Soft breaks':'soft breaks'}
        u.menu('Tools','Options');u.click('Markdown','page tab')
        for option in a['options']:
            u.call('scroll',x=1000,y=600,delta_y=-2500);u.settle(.2)
            # Scroll the settings pane through visible public controls.
            for _ in range(5):
                nodes=u.observe()['nodes']
                node=next((n for n in nodes if n['role']=='check box' and labels[option].casefold() in n['name'].casefold()),None)
                if node:break
                u.call('scroll',x=1000,y=600,delta_y=500);u.settle(.3)
            assert node,'Markdown option is missing: '+option
            u.call('check',target=node['ref'],checked=a['enabled'])
        u.click('OK','push button');u.find('Note title','entry')
    elif op=='history-preview':
        u.click('Note properties','push button');u.click('Previous versions of this note','link')
        u.find('Previous survey: two oak trees.',exact=False,timeout=30)
    elif op=='history-restore':
        u.click('Restore','push button');u.settle(.5)
        if any(n['role']=='push button' and n['name']=='OK' for n in u.observe()['nodes']):u.click('OK','push button')
        u.press('Escape');u.click('Restored Notes','link',exact=False);u.click('History journal','list item',exact=False)
    elif op=='archive-export':
        u.context('Workbench','Export',a['format'],role='link')
        if a['filename']:u.file(ctx.episode['inputs']['outbox']+'/'+a['filename'],save=True)
        else:choose_folder(u,ctx.episode['inputs']['outbox'])
        u.find('Note title','entry',timeout=30);u.settle(1)
    elif op=='archive-import':
        u.menu('File','Import',a['format'])
        if a['filename']:u.file(ctx.episode['inputs']['outbox']+'/'+a['filename'])
        else:choose_folder(u,ctx.episode['inputs']['outbox'])
        u.find('All notes','link',timeout=30);u.click('All notes','link');u.settle(1.5)
        nodes=[n for n in u.observe()['nodes'] if n['role']=='list item' and plain(n['name'])=='trip log']
        assert len(nodes)==2,'both original and imported Trip log must be listed'
        u.call('click',target=nodes[0]['ref']);u.notice();run(ctx,u,{'op':'viewer'})
    elif op=='export-pdf':
        u.context('River survey','Export','PDF - PDF File')
        u.file(ctx.episode['inputs']['outbox']+'/'+a['filename'],save=True);u.find('Note title','entry',timeout=30)
    elif op=='new-whiteboard':
        u.notebook('Workbench');u.menu('Tools','Create whiteboard');u.click('Add a text card','push button')
        run(ctx,u,{'op':'whiteboard-text','old':'New text card','text':a['text']})
        u.fill('Note title',a['title']);u.click('Fit View','push button')
    elif op=='whiteboard-text':
        node=u.find(a['old'],'paragraph',exact=False);u.call('click',target=node['ref'],click_count=2)
        u.fill('',a['text']);u.press('Control+Return');u.click('Fit View','push button')
    elif op=='whiteboard-note':
        u.menu('Tools','Add note to whiteboard');u.settle(.6);u.fill(None,a['title'].split()[0])
        u.find(a['title'],'list item',exact=False,timeout=30);u.click(a['title'],'list item',exact=False)
        u.click('Fit View','push button')
    elif op=='whiteboard-connect':
        u.click('Fit View','push button');u.settle(.5)
        source=u.find('Source card','paragraph',exact=False);dest=u.find('Destination card','paragraph',exact=False)
        x,y,w,h=source['bounds'];dx,dy,dw,dh=dest['bounds'];scale=w/200
        sx=x+w+10*scale;sy=y+60*scale;tx=dx-10*scale;ty=dy+60*scale
        u.call('move',target=source['ref'],seconds=.5)
        u.call('drag',x=round(sx),y=round(sy),to_x=round(tx),to_y=round(ty),seconds=1)
        u.settle(.5);u.call('click',x=round((sx+tx)/2),y=round((sy+ty)/2))
    elif op=='whiteboard-promote':
        node=u.find(a['text'],'paragraph',exact=False);u.call('click',target=node['ref'])
        u.click('Promote to note','push button');u.settle(.7)
        u.note(a['text']);u.note('Route map');u.click('Fit View','push button');u.settle(.7)
    elif op=='whiteboard-edge':
        u.click('Bidirectional','toggle button');u.fill('Label',a['label']);u.press('Return');u.settle(.5)
    elif op=='whiteboard-delete-edge':
        node=u.find('Field route',exact=True)
        u.call('click',target=node['ref']);u.press('Delete');u.settle(.5)
    elif op=='import':
        u.menu('File','Import',a['format']);u.file(path(ctx,a['path']),directory=a.get('directory',False))
        if a['format'].startswith('ONE -'):
            u.settle(.7)
            window=next(w for w in u.call('windows')['windows'] if w.get('active'))
            x,y,width,height=window['bounds']
            assert width<700 and height<300,'expected OneNote compatibility notice'
            u.call('click',x=round(x+width/4),y=round(y+height-36))
        u.find('All notes','link',timeout=30);u.click('All notes','link')
        u.find(a['title'],'list item',timeout=35);u.click(a['title'],'list item');u.notice()
        if 'HTML' in a['format'] or '(as HTML)' in a['format']:run(ctx,u,{'op':'viewer'})
    elif op=='export-raw':
        u.context('River survey','Export','RAW - Joplin Export Directory')
        choose_folder(u,ctx.episode['inputs']['outbox']);u.find('Note title','entry',timeout=30);u.settle()
    elif op=='roundtrip':
        filename=a['filename'];output=ctx.episode['inputs']['outbox']
        u.context('River survey','Export',a['format'])
        if filename:u.file(output+'/'+filename,save=True)
        else:choose_folder(u,output)
        u.find('Note title','entry',timeout=30);u.settle()
        u.menu('File','Import',a['importer'])
        if filename:u.file(output+'/'+filename)
        else:choose_folder(u,output)
        u.find('All notes','link',timeout=30);u.click('All notes','link');u.settle(1.5)
        # Imports select their destination notebook. The imported note is the
        # visible item, even when its title is derived from an HTML file name.
        candidates=[n for n in u.observe()['nodes'] if n['role']=='list item' and
                    ('River survey' in n['name'] or ('archive' in n['name'].casefold() and 'html' in a['format'].casefold()))]
        assert candidates,'the imported copy is not visible'
        u.call('click',target=candidates[0]['ref']);u.notice()
        if 'HTML' in a['format']:run(ctx,u,{'op':'viewer'})
    else:raise AssertionError('unknown reference action '+op)
