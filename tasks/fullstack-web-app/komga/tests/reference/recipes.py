from common import AUTH,READER
from .ui import UI


def execute(ctx,p,cp):
    ui=ctx.state.setdefault('ui',UI(ctx.broker))
    if ctx.episode.get('login',True) and not ctx.state.get('signed_in'):
        ui.sign_in(*ctx.episode.get('auth',AUTH));ctx.state['signed_in']=True
    for raw in cp['recipe']:
        a=p.resolve(raw);op=a['op']
        if op=='open':ui.goto(a['path'])
        elif op=='click':ui.click(a['text'],a.get('role'),a.get('nth',0))
        elif op=='fill':ui.fill(a['label'],a['value'])
        elif op=='focus-field':
            c=ui.wait(lambda s:next((x for x in s['controls'] if x.get('label')==a['label'] and x['tag'] in ('input','textarea')),None),'field missing')
            ui.call('click',target={'ref':c['ref']});ui.call('wait',seconds=.4)
        elif op=='check':ui.check(a['label'],a.get('value',True))
        elif op=='select':ui.select(a['label'],a['value'])
        elif op=='point':ui.point(a['x'],a['y'])
        elif op=='press':ui.call('press',key=a['key'])
        elif op=='reload':ui.call('reload');ui.call('wait',seconds=.5)
        elif op=='scroll':ui.call('scroll',delta_y=a['y'])
        elif op=='wait':ui.call('wait',seconds=a.get('seconds',.5))
        elif op=='require':ui.require(*a['text'])
        elif op=='login':ui.sign_in(*a.get('auth',AUTH))
        elif op=='edit':ui.edit(a['kind'])
        elif op=='wheel-reader':ui.call('wheel',x=1100,y=500,delta_y=a['delta'])
        elif op=='reader-setting':
            ui.call('press',key='s');ui.require('Reader Settings');ui.click(a['current'],role='button');ui.click(a['value'],role='option')
            buttons=[c for c in ui.snapshot()['controls'] if c['tag']=='button' and 300<c['bounds'][0]<500 and c['bounds'][1]>100]
            assert buttons,'settings close missing';ui.call('click',target={'ref':buttons[0]['ref']});ui.call('wait',seconds=.5)
        elif op=='reader-thumbnail':
            ui.call('wait',seconds=.5)
            # Six visible page thumbnails, one evenly spaced row in this small input.
            ui.point(130+(a['page']-1)*204,480)
        elif op=='reader-poster':
            ui.point(1252,24);ui.click('Set page as poster for '+a['kind']);ui.call('wait',seconds=.5)
        elif op=='cbl-upload':
            import base64
            from gui_account_import import CBL
            ui.call('upload',target={'label':'ComicRack Reading List (.cbl)'},filename='read-order.cbl',mime_type='application/xml',base64=base64.b64encode(CBL).decode())
        elif op=='save':ui.save()
        elif op=='logout':
            ui.call('click',target={'text':'Log Out','exact':True});ui.wait(lambda s:s['url'].startswith('/login'),'logout failed')
        elif op=='new-api-key':
            ui.click('Generate API Key');ui.fill('Comment',a['comment']);ui.click('Generate');ui.click('Close');ui.require(a['comment'])
        elif op=='delete-api-key':
            ui.require('Tablet reader');ui.snapshot()
            buttons=[x for x in ui.snap['controls'] if x['tag']=='button' and x['bounds'][0]>500 and 100<x['bounds'][1]<160]
            assert buttons,'key delete control missing';c=max(buttons,key=lambda x:x['bounds'][0]);ui.call('click',target={'ref':c['ref']})
            ui.check('I understand, delete the API key "Tablet reader"');ui.click('Delete');ui.require('No API Keys')
        elif op=='tag-add':
            ui.call('wait',seconds=.5)
            c=ui.wait(lambda s:next(iter([x for x in s['controls'] if x.get('role')=='combobox' and x['bounds'][0]>400 and x['bounds'][1]>250][::-1]),None),'tag combobox missing')
            ui.call('click',target={'ref':c['ref']});ui.call('type',value=a['value']);ui.call('press',key='Enter')
            if any(c.get('role')=='listbox' for c in ui.snapshot()['controls']):ui.call('press',key='Escape')
        elif op=='list-edit':
            ui.point(1156,96);ui.require('Save Changes')
        elif op=='list-member':
            ui.snapshot();c=next((x for x in ui.snap['controls'] if x.get('href','').startswith('/series/' if a['entity']=='collections' else '/book/') and 'Atlas' in x.get('text','')),None)
            assert c,'Atlas list member missing';ui.call('click',target={'ref':c['ref']})
        else:raise ValueError('unknown recipe '+op)
    for text in cp.get('visible',[]):ui.require(text)
