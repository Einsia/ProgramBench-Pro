"""Additional deterministic recipes, all through the public GUI."""
def field(ui,label,roles=('spin button','text','combo box')):
    nodes=ui.nodes();caption=ui.find(label,('label',))
    x,y,w,h=caption['bounds']
    choices=[n for n in nodes if n['role'] in roles and n['bounds'][0]>=x+w-10 and abs(n['bounds'][1]+n['bounds'][3]/2-y-h/2)<22]
    if not choices:
        choices=[n for n in nodes if n['role'] in roles and 0<=n['bounds'][1]-y-h<25 and n['bounds'][0]>=x-10]
    assert choices,'field missing: '+label
    return min(choices,key=lambda n:abs(n['bounds'][1]-y)*5+abs(n['bounds'][0]-x-w))


def combo(ui,node,value):
    ui.call('click',target=node['ref']);ui.click(value,('menu item','radio menu item','list item'))


def execute(ui,a):
    ctx=ui.ctx;op=a['op']
    if op=='pref':
        ui.menu('Edit','Preferences');ui.click(a['tab'],('page tab',))
        if a.get('scroll'):ui.call('scroll',x=900,y=700,delta_y=a['scroll'])
        for label,value in a.get('fields',{}).items():
            node=field(ui,label)
            if node['role']=='combo box':combo(ui,node,str(value))
            else:ui.call('fill',target=node['ref'],value=str(value));ui.key('Tab')
        for label,value in a.get('checks',{}).items():ui.call('check',target=ui.find(label,('check box',))['ref'],checked=value)
        ui.click('Ok',('push button',),last=True)
    elif op=='mouse-map':
        ui.menu('Edit','Preferences');ui.click('Mouse',('page tab',))
        nodes=sorted([n for n in ui.nodes() if n['role']=='combo box'],key=lambda n:n['bounds'][1])
        combo(ui,nodes[2],a['tool']);ui.click('Ok',('push button',),last=True)
    elif op=='palette':
        ui.menu('Edit','Preferences');ui.click('Palette',('page tab',));ui.click(a['name'],('label',));ui.click('Ok',('push button',),last=True)
    elif op=='toolbar-copy':
        ui.menu('Edit','Toolbars','Manage');ui.click(a.get('source','Portrait'),('table cell',))
        ui.click('Copy',('push button',),last=True);ui.click('Close',('push button',),last=True)
        ui.menu('Edit','Toolbars',a.get('source','Portrait')+' Copy')
    elif op=='toolbar-remove':
        ui.menu('Edit','Toolbars','Customize')
        n=ui.find(a['tool'],('push button','toggle button'))
        x,y,w,h=n['bounds'];ui.call('drag',x=x+w//2,y=y+h//2,to_x=640,to_y=500)
        ui.click('Close',('push button',),last=True)
    elif op=='save-quit':
        ui.key('Control+Q');ui.click('Save As...',('push button',),last=True)
        ui.chooser(ctx.state['outbox']+'/'+a['name'],True)
    elif op=='overwrite':
        ui.menu('File','Save As');ui.wait(lambda ns:any(n['role']=='file chooser' for n in ns))
        field_=ui.wait(lambda ns:next((n for n in ns if n['role']=='text' and 'editable' in n.get('states',())),None))
        ui.call('fill',target=field_['ref'],value=ctx.state['outbox']+'/'+a['name']);ui.click('Save',('push button',),last=True)
        ui.wait(lambda ns:any(n['role']=='push button' and n['name']=='Replace' for n in ns))
        ui.click('Replace' if a['replace'] else 'Select another name',('push button',),last=True)
        if not a['replace']:
            ui.wait(lambda ns:not any(n['role']=='push button' and n['name']=='Replace' for n in ns))
            ui.click('Cancel',('push button',),last=True)
        ui.wait(lambda ns:not any(n['role']=='file chooser' for n in ns))
    elif op=='new-discard':
        ui.key('Control+N');ui.click('Discard',('push button',),last=True)
    elif op=='recent':
        ui.menu('File','Recent Documents')
        node=ui.wait(lambda ns:next((n for n in ns if n['role']=='menu item' and a['name'] in n.get('name','')),None))
        ui.call('click',target=node['ref'])
    elif op=='goto':
        ui.key('Control+G');node=ui.wait(lambda ns:([n for n in ns if n['role']=='spin button'] or [None])[-1])
        ui.call('fill',target=node['ref'],value=str(a['page']));ui.click('Ok',('push button',),last=True)
    elif op=='template-save':
        ui.menu('Journal','Configure Page Template')
        ui.call('check',target=ui.find('Copy current page size instead',('check box',))['ref'],checked=False)
        ui.call('check',target=ui.find('Copy current page background instead',('check box',))['ref'],checked=False)
        ui.click('Change',('push button',))
        choices=[n for n in ui.nodes() if n['role']=='combo box'];combo(ui,choices[-1],'points')
        fields=sorted([n for n in ui.nodes() if n['role']=='spin button' and n['bounds'][1]<800],key=lambda n:n['bounds'][1])
        for n,value in zip(fields,[500,300]):ui.call('fill',target=n['ref'],value=str(value));ui.key('Tab')
        ui.click('Ok',('push button',),last=True)
        ui.call('click',target=field(ui,'Background',('toggle button',))['ref'])
        choices=[n for n in ui.nodes() if n['role']=='check menu item'];ui.call('click',target=choices[5]['ref'])
        ui.call('click',target=field(ui,'Background Color',('push button',))['ref']);ui.click('Custom color',('push button',))
        ui.call('fill',target=ui.find('Color Name',('text',))['ref'],value='#FFF4CC');ui.click('Select',('push button',),last=True)
        ui.click('Save to file',('push button',));ui.chooser(ctx.state['outbox']+'/'+a['name'],True)
        ui.click('Ok',('push button',),last=True)
    elif op=='template-load':
        ui.menu('Journal','Configure Page Template');ui.click('Load from file',('push button',))
        ui.chooser(ctx.state['outbox']+'/'+a['name']);ui.click('Ok',('push button',),last=True)
    elif op=='guide-draw':
        import io,base64,math
        import numpy as np
        from PIL import Image
        guide=a['guide'];ui.tool('Pen');ui.call('check',target=ui.find(guide,('toggle button',))['ref'],checked=True)
        shot=ui.call('screenshot');im=np.asarray(Image.open(io.BytesIO(base64.b64decode(shot['png_base64']))).convert('RGB'))
        pixels=im.astype(int)
        mask=(pixels[:,:,0]>140)&(pixels[:,:,2]>90)&(pixels[:,:,2]>pixels[:,:,1]+40)&(pixels[:,:,0]>pixels[:,:,1]+40)
        mask[:160]=False;mask[820:]=False;mask[:,:200]=False
        yy,xx=np.where(mask);assert len(xx)>100,'drawing guide outline is missing'
        left,right,top,bottom=int(min(xx)),int(max(xx)),int(min(yy)),int(max(yy))
        if guide=='Setsquare':
            ui.call('drag',x=left+90,y=top+6,to_x=right-100,to_y=top+16,via=[[left+200,top+15],[right-220,top+4]])
        else:
            cx,cy=(left+right)/2,(top+bottom)/2;rad=(right-left)/2
            pts=[[round(cx+(rad-5)*math.cos(t)),round(cy+(rad-5)*math.sin(t))] for t in np.linspace(0,1.6*math.pi,22)]
            ui.call('drag',x=pts[0][0],y=pts[0][1],to_x=pts[-1][0],to_y=pts[-1][1],via=pts[1:-1])
        ui.call('check',target=ui.find(guide,('toggle button',))['ref'],checked=False)
    elif op=='bookmark':
        ui.click('Contents',('toggle button',))
        if a.get('parent'):
            node=ui.find(a['parent'],('table cell',));x,y,w,h=node['bounds']
            ui.call('click',x=x-25,y=y+h//2)
        ui.click(a['name'],('table cell',))
    elif op=='pdf-link':
        ui.tool('Select Linear Text');x,y=ui.point(a['x'],a['y']);ui.call('click',x=x,y=y)
        ui.click('Scroll to page '+str(a['page']),('push button',))
    else:raise ValueError('unknown additional recipe '+op)
