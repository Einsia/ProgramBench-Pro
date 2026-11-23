"""Operate the unmodified reference through public runtime GUI operations only."""
import base64
import io
import time
from PIL import Image
import numpy as np


class UI:
    def __init__(self, ctx):
        self.ctx=ctx

    def call(self, op, **fields):
        return self.ctx.broker.call(dict(op=op,**fields))

    def nodes(self):
        return self.call('observe')['nodes']

    def wait(self, condition, seconds=12):
        end=time.monotonic()+seconds
        while True:
            nodes=self.nodes()
            result=condition(nodes)
            if result: return result
            assert time.monotonic()<end, 'expected visible control/state did not appear'
            time.sleep(.15)

    def find(self, name, roles=None, last=False):
        def select(nodes):
            result=[n for n in nodes if (roles is None or n['role'] in roles) and
                    name in (n.get('name'),n.get('description'),n.get('text'))]
            return (result[-1] if last else result[0]) if result else None
        return self.wait(select)

    def click(self, name, roles=None, last=False):
        node=self.find(name,roles,last)
        self.call('click',target=node['ref'])
        return node

    def key(self,key):
        return self.call('press',key=key)

    def menu(self,*names):
        for name in names:
            self.click(name,('menu','menu item','check menu item','radio menu item'))
            self.call('wait',seconds=.12)
        if names and names[-1] in ('New Page After','New Page Before','New Page at End'):
            self.ctx.state['page-width']=595.275591

    def tool(self,name):
        if name.startswith('Draw ') or name=='Shape Recognizer':
            self.menu('Tools','Drawing Type',name)
        else:
            self.menu('Tools',name)

    def color(self,name):
        self.click(name,('toggle button',))

    def chooser(self,path,save=False,button='Save'):
        self.wait(lambda ns:any(n['role']=='file chooser' for n in ns))
        if save:
            node=self.wait(lambda ns:next((n for n in ns if n['role']=='text' and 'editable' in n.get('states',())),None))
            self.call('fill',target=node['ref'],value=path)
            self.click(button,('push button',),last=True)
        else:
            self.key('Control+L')
            self.key('Control+A')
            self.call('type',value=path)
            self.key('Return')
        def finished(ns):
            replace=next((n for n in ns if n['role']=='push button' and n['name']=='Replace'),None)
            if replace:
                self.call('click',target=replace['ref'])
                return False
            return not any(n['role']=='file chooser' for n in ns)
        self.wait(finished,20)
        self.call('wait',seconds=.25)

    def open(self,path):
        self.key('Control+O')
        self.chooser(path)
        if path.endswith('.pdf'):
            if path.rsplit('/',1)[-1] in ('normal.pdf','paper.pdf','single.pdf'):
                self.ctx.state['page-width']=360
            self.menu('View','Normal Size')
            self.menu('Navigation')
            node=self.find('First Page',('menu item',))
            if 'disabled' in node.get('states',()):self.key('Escape')
            else:self.call('click',target=node['ref'])
            self.call('wait',seconds=.25)
        elif path.rsplit('/',1)[-1] in ('blank.xopp','objects.xopp','layers.xopp','pages.xopp','strokes.xopp'):
            self.ctx.state['page-width']=600

    def save(self,name):
        self.key('Escape')
        self.menu('File','Save As')
        self.chooser(self.ctx.state['outbox']+'/'+name,True)

    def normal(self):
        self.menu('View','Normal Size')
        for name in ('Grid Snapping','Rotation Snapping'):
            n=self.find(name,('toggle button',))
            if 'checked' in n.get('states',()): self.call('click',target=n['ref'])
        self.call('wait',seconds=.25)

    def point(self,x,y,width=None):
        left,top,scale=self.geometry(width)
        return [round(left+x*scale),round(top+y*scale)]

    def geometry(self,width=None):
        """Page geometry from the visible selected-page border; never from private state."""
        for attempt in range(5):
            shot=self.call('screenshot')
            img=np.asarray(Image.open(io.BytesIO(base64.b64decode(shot['png_base64']))).convert('RGB'))
            red=(img[:,:,0]>210)&(img[:,:,1]<70)&(img[:,:,2]<70)
            red[:124,:]=False;red[846:,:]=False;red[:,:150]=False
            rows=np.where(red.sum(axis=1)>200)[0]
            if len(rows):break
            # Inserting a page before the current page can temporarily leave no
            # active border. Locate the large visible paper rectangle itself.
            paper=(img.max(axis=2)>238)&(img.min(axis=2)>140)
            paper[:124,:]=False;paper[846:,:]=False;paper[:,:150]=False
            runs=np.where(paper.sum(axis=1)>200)[0]
            bands=np.split(runs,np.where(np.diff(runs)>1)[0]+1) if len(runs) else []
            bands=[b for b in bands if len(b)>100]
            if bands:
                band=max(bands,key=len)
                sample=int(band[len(band)//2]);xs=np.where(paper[sample])[0]
                left,right=int(xs[0]),int(xs[-1])
                return left,int(band[0]),(right-left)/(width or self.ctx.state.get('page-width',600))
            if attempt==0:
                tools={'Pen','Eraser','Highlighter','Text','Image','Select Rectangle','Select Region','Select Multi-Layer Rectangle',
                       'Select Multi-Layer Region','Select Object','Vertical Space','Hand','Draw Rectangle','Draw Ellipse','Draw Line',
                       'Draw Arrow','Draw Double Arrow','Draw Coordinate System','Draw Spline','Shape Recognizer'}
                selected=[n.get('description') or n.get('name') for n in self.nodes() if n['role']=='toggle button' and
                          'checked' in n.get('states',()) and (n.get('description') or n.get('name')) in tools]
                self.tool('Hand Tool')
                self.call('click',x=715,y=485)
                self.tool('Hand Tool' if selected and selected[-1]=='Hand' else selected[-1] if selected else 'Pen')
                self.call('wait',seconds=.2)
                continue
            self.click('Zoom out',('push button',))
            self.call('wait',seconds=.15)
        assert len(rows),'selected page border is not visible'
        top=int(rows[0]);xs=np.where(red[top])[0]
        left,right=int(xs[0]),int(xs[-1])
        scale=(right-left)/(width or self.ctx.state.get('page-width',600))
        return left,top,scale

    def drag(self,points,**kwargs):
        left,top,scale=self.geometry()
        coords=[[round(left+x*scale),round(top+y*scale)] for x,y in points]
        self.call('drag',x=coords[0][0],y=coords[0][1],to_x=coords[-1][0],to_y=coords[-1][1],via=coords[1:-1],seconds=.65,**kwargs)

    def text(self,value,x=85,y=80):
        self.tool('Text')
        px,py=self.point(x,y)
        self.call('click',x=px,y=py)
        self.call('wait',seconds=.15)
        px,py=self.point(x,y)
        self.call('click',x=px,y=py)
        self.call('type',value=value)
        self.key('Escape')

    def dialog_entry(self,value,index=0):
        nodes=self.wait(lambda ns:[n for n in ns if n['role']=='text' and 'editable' in n.get('states',())])
        self.call('fill',target=nodes[index]['ref'],value=str(value))

    def page_format(self,size,landscape=False):
        self.menu('Journal','Paper Format')
        combo=self.wait(lambda ns:next((n for n in ns if n['role']=='combo box'),None))
        self.call('click',target=combo['ref'])
        self.click(size,('menu item',))
        nodes=self.nodes()
        toggles=[n for n in nodes if n['role']=='toggle button' and not n.get('name') and not n.get('description')]
        assert len(toggles)>=2, 'orientation controls not found'
        self.call('check',target=toggles[-1 if landscape else -2]['ref'],checked=True)
        self.click('Ok',('push button',),last=True)

    def font(self,name,size):
        self.menu('Tools','Text Font...')
        self.call('fill',target=self.find('Search',('text',))['ref'],value=name)
        self.call('wait',seconds=.3)
        node=self.wait(lambda ns:next((n for n in ns if n['role']=='table cell' and n['name'] in (name,name+' Regular')),None))
        self.call('click',target=node['ref'])
        spin=self.wait(lambda ns:([n for n in ns if n['role']=='spin button'] or [None])[-1])
        self.call('fill',target=spin['ref'],value=str(size))
        self.click('Select',('push button',),last=True)

    def export(self,name,fmt='PDF',options=None):
        if fmt=='PDF' and not options:
            self.menu('File','Export as PDF')
            self.chooser(self.ctx.state['outbox']+'/'+name,True,'Export')
            return
        self.menu('File','Export as...')
        combos=self.wait(lambda ns:[n for n in ns if n['role']=='combo box'])
        self.call('click',target=combos[-1]['ref'])
        self.key('Home')
        for _ in range(['PDF','PNG','SVG','XOJ'].index(fmt)):self.key('Down')
        self.key('Return')
        # Export chooser uses Save and the same filename field.
        self.chooser(self.ctx.state['outbox']+'/'+name,True,'Export')
        if fmt in ('PDF','PNG','SVG') or options:
            self.wait(lambda ns:any(n.get('name')=='Ok' and n['role']=='push button' for n in ns))
            for key,value in (options or {}).items():
                if key=='background':
                    combos=[n for n in self.nodes() if n['role']=='combo box']
                    self.call('click',target=combos[0]['ref']);self.click(value,('menu item',))
                elif key=='range':
                    self.click('Pages:',('radio button',))
                    self.dialog_entry(value,-1)
                elif key=='dpi':
                    spins=[n for n in self.nodes() if n['role']=='spin button']
                    self.call('fill',target=spins[-1]['ref'],value=str(value))
            self.click('Ok',('push button',),last=True)
            self.call('wait',seconds=.4)


def execute(ctx,cp):
    ui=UI(ctx)
    for action in cp.get('recipe',[]):
        op=action['op']
        if op=='menu':ui.menu(*action['path'])
        elif op=='key':ui.key(action['key'])
        elif op=='click':ui.click(action['name'],action.get('roles'),action.get('last',False))
        elif op=='tool':ui.tool(action['name'])
        elif op=='color':ui.color(action['name'])
        elif op=='drag':ui.drag(action['points'],**({'button':action['button']} if 'button' in action else {}))
        elif op=='text':ui.text(action['value'],action.get('x',85),action.get('y',80))
        elif op=='save':ui.save(action['name'])
        elif op=='open':ui.open(ctx.state[action.get('area','inbox')]+'/'+action['name'])
        elif op=='choose-file':ui.chooser(ctx.state[action.get('area','inbox')]+'/'+action['name'])
        elif op=='normal':ui.normal()
        elif op=='page-width':ctx.state['page-width']=action['value']
        elif op=='paper-color':
            ui.menu('Journal','Paper Color');ui.click('Custom color',('push button',))
            ui.call('fill',target=ui.find('Color Name',('text',))['ref'],value=action['value'])
            ui.click('Select',('push button',),last=True)
        elif op=='pdf-opacity':
            ui.menu('Tools','Select PDF Text Options','Marker Opacity')
            slider=[n for n in ui.nodes() if n['role']=='slider'][-1]
            x,y,w,h=slider['bounds']
            ui.call('click',x=x+w//2,y=y+h-12)
            current=round([n for n in ui.nodes() if n['role']=='slider'][-1]['value'])
            wanted=action['value']
            for _ in range(abs(current-wanted)):ui.key('Left' if current>wanted else 'Right')
            ui.click('Ok',('push button',),last=True)
        elif op=='custom-paper':
            ui.menu('Journal','Paper Format')
            combos=[n for n in ui.nodes() if n['role']=='combo box']
            ui.call('click',target=combos[-1]['ref']);ui.click('points',('menu item',))
            spins=sorted([n for n in ui.nodes() if n['role']=='spin button' and n['bounds'][1]<800],key=lambda n:n['bounds'][1])
            for node,value in zip(spins,[action['width'],action['height']]):
                ui.call('fill',target=node['ref'],value=str(value));ui.key('Tab')
            ui.click('Ok',('push button',),last=True)
            ctx.state['page-width']=action['width']
        elif op=='search':
            ui.key('Control+F')
            ui.dialog_entry(action['value'])
            ui.key('Return');ui.call('wait',seconds=.5)
        elif op=='dismiss-recovery':
            node=next((n for n in ui.nodes() if n['role']=='push button' and n['name']=='Delete file'),None)
            if node:ui.call('click',target=node['ref'])
        elif op=='page-move':
            nodes=ui.nodes()
            buttons=sorted([n for n in nodes if n['role']=='push button' and n['bounds'][0]<145 and 800<n['bounds'][1]<850],key=lambda n:n['bounds'][0])
            assert len(buttons)>=2,'page move buttons not visible'
            ui.call('click',target=buttons[1 if action['direction']=='down' else 0]['ref'])
        elif op=='page-format':ui.page_format(action['name'],action.get('landscape',False))
        elif op=='rename-layer':
            ui.menu('Journal','Rename Layer');ui.dialog_entry(action['name']);ui.click('Ok',('push button',),last=True)
        elif op=='font':ui.font(action['name'],action['size'])
        elif op=='entry':ui.dialog_entry(action['value'],action.get('index',0))
        elif op=='type':ui.call('type',value=action['value'])
        elif op=='export':ui.export(action['name'],action.get('format','PDF'),action.get('options'))
        elif op=='image':
            x,y=ui.point(action.get('x',100),action.get('y',100))
            ui.tool('Image')
            if not any(n['role']=='file chooser' for n in ui.nodes()):ui.call('click',x=x,y=y)
            ui.chooser(ctx.state[action.get('area','inbox')]+'/'+action['name'])
            ui.key('Escape')
        elif op=='canvas-click':
            x,y=ui.point(action['x'],action['y']);ui.call('click',x=x,y=y,click_count=action.get('count',1))
        elif op=='wait':ui.call('wait',seconds=action.get('seconds',.5))
        elif op=='fill':ui.call('fill',target=ui.find(action['name'],action.get('roles'))['ref'],value=action['value'])
        elif op=='check':ui.call('check',target=ui.find(action['name'],action.get('roles'))['ref'],checked=action['value'])
        else:
            from .extra import execute as extra
            extra(ui,action)
    if ctx.episode.get('feature')=='layers':
        ui.call('check',target=ui.find('Layer Preview',('toggle button',))['ref'],checked=True)
    ui.call('wait',seconds=.25)


def begin(ctx,cp):
    if ctx.state.get('record-prepared'):return
    ctx.state['record-prepared']=True
    if ctx.episode.get('opened'):
        ui=UI(ctx)
        ui.open(ctx.state['inbox']+'/'+ctx.episode['opened'])
        if ctx.episode.get('normal',True):ui.normal()
