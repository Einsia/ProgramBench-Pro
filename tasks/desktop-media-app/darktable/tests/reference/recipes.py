"""Deterministic GUI operations on the pinned upstream product (record only)."""
import time


def act(ctx,op,**fields):return ctx.broker.call({'op':op,**fields})


def nodes(ctx):return act(ctx,'observe').get('nodes',[])


def wait_stable(ctx, seconds=20):
    """Wait on public accessibility stability, without product-specific readiness gates."""
    deadline=time.monotonic()+seconds;previous=None;stable=0
    while time.monotonic()<deadline:
        obs=act(ctx,'observe')
        projection=[(n.get('role'),n.get('name'),n.get('text'),n.get('description'))
                    for n in obs.get('nodes',[]) if n.get('role') not in ('scroll bar','filler','panel')]
        stable=stable+1 if projection==previous else 0
        if stable>=2 and len(projection)>6:return
        previous=projection;time.sleep(.5)
    # A minimal candidate UI is still valid; stability is preparation, not a score.
    if ctx.record:
        raise AssertionError('reference accessibility did not settle before recording')


def find(ctx,*,name=None,description=None,role=None,nth=0):
    matching=[n for n in nodes(ctx) if (name is None or n.get('name')==name)
              and (description is None or description in n.get('description',''))
              and (role is None or n.get('role')==role)]
    assert len(matching)>nth,'expected visible control missing: '+str((name,description,role))
    return {'ref':matching[nth]['ref']}


def click(ctx,**match):act(ctx,'click',target=find(ctx,**match))


def press(ctx,key):act(ctx,'press',key=key)


def settle(ctx,seconds=.5):
    act(ctx,'move',x=720,y=730)
    act(ctx,'wait',seconds=seconds)


def importing(ctx,files=None):
    if not any(n.get('name')=='add to library...' for n in nodes(ctx)):
        click(ctx,name='import',role='label')
    click(ctx,name='add to library...',role='push button')
    click(ctx,name='inputs',role='table cell')
    if files and len(files)==1:
        click(ctx,name=files[0],role='table cell')
    else:click(ctx,name='select all',role='push button')
    click(ctx,name='add to library',role='push button')
    deadline=time.monotonic()+20
    imported=set(files or ctx.episode['setup'][0]['files'])
    while time.monotonic()<deadline:
        if any(n.get('role')=='panel' and n.get('description','').split('\n')[0] in imported for n in nodes(ctx)):break
        time.sleep(.25)
    else:raise AssertionError('imported image thumbnail did not appear')
    # A single-file import may automatically enter darkroom. Library episodes
    # finish their import in lighttable, so their next controls are available.
    if any(n.get('name')=='Search' for n in nodes(ctx)):
        click(ctx,name='lighttable',role='label')
    press(ctx,'Control+a')
    if ctx.episode['id'] in ('library-rating','library-labels','library-filter','library-duplicate','library-grouping'):
        click(ctx,description='click to change the type of overlays shown on thumbnails',role='push button')
        act(ctx,'check',target=find(ctx,name='permanent overlays',role='radio button'),checked=True)
        press(ctx,'Escape')
    settle(ctx,1)
    wait_stable(ctx)


def field_by_label(ctx,label,value):
    observed=nodes(ctx)
    anchor=next(n for n in observed if n.get('role')=='label' and n.get('name')==label)
    choices=[n for n in observed if n.get('role')=='text' and abs(n['bounds'][1]-anchor['bounds'][1])<5]
    assert choices,'editable field missing: '+label
    act(ctx,'fill',target={'ref':choices[-1]['ref']},value=value)


def copy_import(ctx,directory):
    if not any(n.get('name')=='copy & import...' for n in nodes(ctx)):
        click(ctx,name='import',role='label')
    click(ctx,name='copy & import...',role='push button')
    if any(n.get('name')=='understood & done' for n in nodes(ctx)):
        click(ctx,name='understood & done',role='push button')
    click(ctx,name='inputs',role='table cell')
    click(ctx,name='select all',role='push button')
    click(ctx,name='naming rules',role='label')
    field_by_label(ctx,"base filmroll's directory",directory)
    field_by_label(ctx,'filmroll name','batch')
    field_by_label(ctx,'file naming pattern','copied-$(FILE_NAME).$(FILE_EXTENSION)')
    click(ctx,name='copy & import',role='push button')
    settle(ctx,2)
    if any(n.get('name')=='Search' for n in nodes(ctx)):
        click(ctx,name='lighttable',role='label')


def darkroom(ctx):
    click(ctx,name='darkroom',role='label')
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if any(n.get('name')=='Search' for n in nodes(ctx)):return
        time.sleep(.3)
    raise AssertionError('darkroom did not become ready')


def search_module(ctx,name):
    act(ctx,'fill',target=find(ctx,name='Search',role='text'),value=name)
    click(ctx,name=name,role='label')
    settle(ctx)


def slider(ctx,description,value,nth=0):
    act(ctx,'click',target=find(ctx,description=description,role='drawing area',nth=nth),button='right')
    act(ctx,'type',value=str(value))
    press(ctx,'Return')
    settle(ctx,1)


def panel(ctx,name):
    # Scroll over the panel content; the scrollbar itself need not accept wheel events.
    act(ctx,'scroll',x=1410,y=400,delta_y=-2400)
    act(ctx,'wait',seconds=.5)
    if name=='styles' and any(n.get('role')=='text' and 'filter style names' in n.get('description','') for n in nodes(ctx)):
        return
    click(ctx,name=name,role='label')
    settle(ctx)


def metadata(ctx,field,value):
    observed=nodes(ctx)
    labels=[n for n in observed if n.get('role')=='label' and n.get('name')==field]
    assert labels,'metadata label missing'
    y=labels[0]['bounds'][1]
    fields=[n for n in observed if n.get('role')=='text' and abs(n['bounds'][1]-y)<5]
    assert fields,'metadata text field missing'
    act(ctx,'fill',target={'ref':fields[0]['ref']},value=value)
    click(ctx,name='apply',role='push button')


def select_image(ctx,file,add=False):
    matches=[n for n in nodes(ctx) if n.get('role')=='panel' and n.get('description','').split('\n')[0]==file]
    assert matches,'image thumbnail missing: '+file
    act(ctx,'click',target={'ref':matches[0]['ref']},modifiers=['Control'] if add else [])


def tag(ctx,value):
    act(ctx,'fill',target=find(ctx,role='text',description='enter tag name'),value=value)
    press(ctx,'Return')


def save_edit(ctx):
    search=next((n.get('text','') for n in nodes(ctx) if n.get('name')=='Search'),'')
    click(ctx,name='lighttable',role='label')
    settle(ctx,.5)
    darkroom(ctx)
    if search:act(ctx,'fill',target=find(ctx,name='Search',role='text'),value=search)
    settle(ctx,.5)


def export_image(ctx,step):
    if any(n.get('name')=='Search' for n in nodes(ctx)):
        click(ctx,name='lighttable',role='label')
    act(ctx,'scroll',x=1424,y=500,delta_y=-2400)
    if not any('enter the path where' in n.get('description','') for n in nodes(ctx)):
        click(ctx,name='export',role='label')
        settle(ctx,.5)
        act(ctx,'scroll',x=1424,y=500,delta_y=-2400)
    # The GUI appends its selected format extension to the filename pattern.
    act(ctx,'fill',target=find(ctx,role='text',description='enter the path where'),value=step['file'].rsplit('.',1)[0])
    act(ctx,'scroll',x=1424,y=500,delta_y=2400)
    if ctx.state.get('export-format','JPEG')!=step['format']:
        # GTK does not always refresh the scrolled custom control's SHOWING
        # state; this reference layout has a fixed format selector position.
        act(ctx,'click',x=1353,y=397)
        act(ctx,'type',value=step['format'])
        press(ctx,'Return')
        ctx.state['export-format']=step['format']
        settle(ctx)
    if step.get('width'):
        y=next(n['bounds'][1] for n in nodes(ctx) if n.get('role')=='label' and n.get('name')=='global options')+67
        act(ctx,'click',x=1165,y=y)
        press(ctx,'Control+a');act(ctx,'type',value=str(step['width']));press(ctx,'Tab')
    if step.get('height'):
        y=next(n['bounds'][1] for n in nodes(ctx) if n.get('role')=='label' and n.get('name')=='global options')+67
        act(ctx,'click',x=1310,y=y)
        press(ctx,'Control+a');act(ctx,'type',value=str(step['height']));press(ctx,'Tab')
    click(ctx,name='start export',role='push button')
    name='outputs/'+step['file'].rsplit('/',1)[-1]
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if any(e['filename']==name for e in act(ctx,'list_files').get('downloads',[])):break
        time.sleep(.3)
    else:raise AssertionError('GUI export did not create the requested file')


def create_style(ctx,name,description):
    click(ctx,name='create...',role='push button')
    act(ctx,'fill',target=find(ctx,role='text',description='enter a name for the new style'),value=name)
    act(ctx,'fill',target=find(ctx,role='text',description='enter a description for the new style'),value=description)
    click(ctx,name='save',role='push button')
    act(ctx,'fill',target=find(ctx,role='text',description='filter style names'),value=name)


def preferences(ctx):
    click(ctx,description='show global preferences',role='push button')
    choices=[n for n in nodes(ctx) if n.get('role')=='label' and n.get('name')=='lighttable' and n['bounds'][0]<300]
    assert choices,'lighttable preference category missing'
    act(ctx,'click',target={'ref':choices[0]['ref']})


def chooser(ctx,path):
    deadline=time.monotonic()+12
    while not any(n.get('role')=='file chooser' for n in nodes(ctx)):
        assert time.monotonic()<deadline,'document chooser did not open'
        time.sleep(.3)
    press(ctx,'Control+l');act(ctx,'type',value=path)
    for _ in range(3):
        press(ctx,'Return');act(ctx,'wait',seconds=.8)
        if not any(n.get('role')=='file chooser' for n in nodes(ctx)):return
    raise AssertionError('document chooser did not finish')


def export_style(ctx,name,directory):
    select_style(ctx,name)
    click(ctx,description='export the selected styles',role='push button')
    chooser(ctx,directory)


def select_style(ctx,name):
    act(ctx,'fill',target=find(ctx,role='text',description='filter style names'),value=name)
    click(ctx,name=name,role='table cell')
    for _ in range(6):
        rows=[n for n in nodes(ctx) if n.get('role')=='table cell' and n.get('name')==name]
        if rows and 'selected' in rows[0].get('states',[]):return
        if rows and 'active' in rows[0].get('states',[]):
            press(ctx,'space');break
        press(ctx,'Tab')
    assert any(n.get('role')=='table cell' and n.get('name')==name
               and 'selected' in n.get('states',[]) for n in nodes(ctx)),'style row was not selected'


def confirm_dialog(ctx):
    choices=[n for n in nodes(ctx) if n.get('role') in ('push button','button') and
             n.get('name','').casefold().replace('_','') in ('yes','ok','delete permanently')]
    if choices:
        act(ctx,'click',target={'ref':choices[-1]['ref']})
    settle(ctx)


def style_description(ctx,value):
    fields=[n for n in nodes(ctx) if n.get('role')=='text' and 'description' in n.get('description','')]
    assert fields,'style description field missing'
    act(ctx,'fill',target={'ref':fields[0]['ref']},value=value)
    candidates=[n for n in nodes(ctx) if n.get('role')=='push button' and n.get('name') in ('save','ok')]
    assert candidates,'style confirmation missing'
    act(ctx,'click',target={'ref':candidates[-1]['ref']})


def snapshot(ctx,restore=False):
    observed=nodes(ctx)
    if restore:
        candidates=[n for n in observed if 'restore' in n.get('description','').casefold() and 'snapshot' in n.get('description','').casefold()]
    else:
        candidates=[n for n in observed if n.get('role')=='toggle button' and n.get('name','').isdigit() and n['bounds'][0]<350]
    assert candidates,'snapshot control missing'
    act(ctx,'click',target={'ref':candidates[0]['ref']})


def sort_images(ctx,name):
    click(ctx,description='determine the sort order of shown images',role='drawing area')
    act(ctx,'type',value=name);press(ctx,'Return')


def reverse_sort(ctx):
    observed=nodes(ctx);sort=next(n for n in observed if n.get('role')=='drawing area' and 'determine the sort order' in n.get('description',''))
    x,y,w,h=sort['bounds'];act(ctx,'click',x=x+w+18,y=y+h//2)


def collection_rule(ctx,query,combine=None):
    if combine:
        choices=[n for n in nodes(ctx) if n.get('role')=='push button' and 'clear this rule or add new rules' in n.get('description','')]
        act(ctx,'click',target={'ref':choices[-1]['ref']})
        click(ctx,name=combine,role='menu item')
    selectors=[n for n in nodes(ctx) if n.get('role')=='drawing area' and n['bounds'][0]<300 and 'wildcard' in n.get('description','')]
    act(ctx,'click',target={'ref':selectors[-1]['ref']},button='right')
    act(ctx,'type',value='filename');press(ctx,'Down');press(ctx,'Return')
    entries=[n for n in nodes(ctx) if n.get('role')=='text' and n['bounds'][0]<300 and 'wildcard' in n.get('description','')]
    act(ctx,'fill',target={'ref':entries[-1]['ref']},value=query);press(ctx,'Return')


def image_zoom(ctx,value):
    act(ctx,'click',target=find(ctx,role='drawing area',description='image zoom level'),button='right')
    act(ctx,'type',value=value);press(ctx,'Return')


def grouping(ctx,enabled):
    # Enabling grouping clears the currently expanded group in the product.
    target={'role':'toggle button','name':'grouped images','exact':False}
    act(ctx,'check',target=target,checked=False)
    if enabled:act(ctx,'check',target=target,checked=True)


def execute(ctx,checkpoint):
    for step in checkpoint.get('recipe',[]):
        op=step['op']
        if op=='import':importing(ctx,step.get('files'))
        elif op=='copy-import':copy_import(ctx,step['directory'])
        elif op=='darkroom':darkroom(ctx)
        elif op=='module':search_module(ctx,step['name'])
        elif op=='slider':slider(ctx,step['description'],step['value'],step.get('nth',0))
        elif op=='panel':panel(ctx,step['name'])
        elif op=='metadata':metadata(ctx,step['field'],step['value'])
        elif op=='select-image':select_image(ctx,step['file'],step.get('add',False))
        elif op=='tag':tag(ctx,step['value'])
        elif op=='save-edit':save_edit(ctx)
        elif op=='export':export_image(ctx,step)
        elif op=='create-style':create_style(ctx,step['name'],step['description'])
        elif op=='preferences':preferences(ctx)
        elif op=='export-style':export_style(ctx,step['name'],step['directory'])
        elif op=='select-style':select_style(ctx,step['name'])
        elif op=='style-description':style_description(ctx,step['value'])
        elif op=='confirm-dialog':confirm_dialog(ctx)
        elif op=='snapshot-select':snapshot(ctx)
        elif op=='snapshot-restore':snapshot(ctx,True)
        elif op=='sort':sort_images(ctx,step['name'])
        elif op=='sort-reverse':reverse_sort(ctx)
        elif op=='collection-rule':collection_rule(ctx,step['query'],step.get('combine'))
        elif op=='image-zoom':image_zoom(ctx,step['value'])
        elif op=='grouping':grouping(ctx,step['enabled'])
        elif op=='chooser':chooser(ctx,step['path'])
        elif op=='click-match':click(ctx,**step['match'])
        else:act(ctx,op,**{k:v for k,v in step.items() if k!='op'})
    settle(ctx,1)
    wait_stable(ctx)
