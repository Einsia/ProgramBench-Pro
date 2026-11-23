"""Reference-only browser actions for the user goals; all operations use the public runtime."""
import time
from checks import resolve
from .ui import UI


def settle(c,path,predicate,timeout=12):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        r,p=c.request('GET',path)
        if r.status_code==200:
            try:
                if predicate(p):return p
            except (KeyError,IndexError,TypeError):pass
        time.sleep(.2)
    raise AssertionError('browser state was not saved at '+path)


def named(c,entity,name):
    rows=settle(c,'objects/'+entity,lambda rows:any(x.get('name')==name for x in rows))
    matches=[x for x in rows if x.get('name')==name]
    assert len(matches)==1,'ambiguous object name'
    return matches[0]


def form(ui,fields):
    for item in fields:
        action=item.get('action','fill');criteria=item['target'];value=item['value']
        if action=='select':
            control=ui.control(**criteria)
            options=control.get('options',[])
            chosen=next((x['value'] for x in options if x['label'].strip()==str(value) or x['label'].strip().startswith(str(value)+' (')),str(value))
            ui.select(chosen,**criteria)
        elif action=='check':ui.tick(bool(value),**criteria)
        elif action=='editor':ui.editor(str(value),**criteria)
        else:ui.fill(str(value),**criteria)


def execute(ctx,c,cp):
    ui=UI(ctx.broker)
    actor=ctx.episode.get('actor')
    if actor and not ctx.state.get('gui-signed-in'):
        ui.sign_in(actor,ctx.episode['inputs']['credentials'][actor]);ctx.state['gui-signed-in']=True
    for action in cp['recipe']:
        a=resolve(action,c.state);op=a['op']
        if op=='goto':ui.goto(a['path']);ui.call('wait',seconds=.4)
        elif op=='form':form(ui,a['fields'])
        elif op=='button':ui.click_button(*a['names']);ui.call('wait',seconds=.4)
        elif op=='click':ui.click(**a['target'])
        elif op=='fill':
            ui.fill(str(a['value']),**a['target'])
            if 'placeholder' in a['target']:ui.call('wait',seconds=1.0)
        elif op=='select':form(ui,[{'action':'select','target':a['target'],'value':a['value']}])
        elif op=='check':ui.tick(a['value'],**a['target'])
        elif op=='press':ui.press(a['key'],**a.get('target',{}))
        elif op=='choose':ui.choose(a['value'],arrow=a.get('arrow',True),**a['target'])
        elif op=='require':ui.require(*a['text'])
        elif op=='save-named':c.state[a['save']]=named(c,a['entity'],a['name'])
        elif op=='edit-named':
            row=named(c,a['entity'],a['name']);c.state[a.get('save','editing')]=row
            ui.goto(a['prefix']+'/'+str(row['id']));ui.call('wait',seconds=.3)
        elif op=='delete-named':
            row=named(c,a['entity'],a['name'])
            ui.goto(a['list']);ui.call('wait',seconds=.4)
            # Grocy's row action names expose their purpose through title; row ids are part of normal link targets.
            snap=ui.snapshot();href=a['prefix']+'/'+str(row['id'])
            edit=next(x for x in snap['controls'] if x.get('href','').split('?')[0]==href)
            y=edit['bounds'][1]
            buttons=[x for x in snap['controls'] if abs(x['bounds'][1]-y)<8 and 'delete' in (x.get('title','')+' '+x.get('text','')).lower()]
            if buttons:
                ui.call('click',target={'ref':buttons[0]['ref']})
            else:
                menus=[x for x in snap['controls'] if abs(x['bounds'][1]-y)<8 and x.get('tag')=='button']
                assert menus,'row menu unavailable'
                ui.call('click',target={'ref':menus[0]['ref']});ui.click_button('Delete this item')
            ui.call('wait',seconds=.3)
            ui.click_button('Yes','OK','Delete');ui.call('wait',seconds=.5)
            settle(c,'objects/'+a['entity'],lambda rows:all(x.get('id')!=row['id'] for x in rows))
            ui.goto(a['list']);ui.call('wait',seconds=.3)
        elif op=='upload':
            import base64
            ui.call('upload',target={'label':'No file selected'},filename=a['name'],base64=a['base64'],mime_type='application/pdf')
        elif op=='snapshot':ui.snapshot()
        else:raise AssertionError('unknown recipe operation '+op)
    for text in cp.get('visible',[]):ui.require(resolve(text,c.state))
