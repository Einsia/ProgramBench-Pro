"""Deterministic recipes for the pinned reference, using only public GUI input."""
import json
import re
import time


def norm(value):
    return ' '.join(str(value or '').replace('_','').replace('…','').replace('...','').strip().casefold().split())


class Reference:
    def __init__(self,ctx):
        self.ctx=ctx
        self.inbox=ctx.episode['inputs']['input_folder']
        self.outbox=ctx.episode['inputs']['output_folder']

    def call(self,op,**fields):return self.ctx.broker.call({'op':op,**fields})
    def observe(self):return self.call('observe',tree=True)
    def press(self,key):return self.call('press',key=key)

    def scope(self,observation=None):
        nodes=(observation or self.observe())['nodes']
        tops=[n for n in nodes if n.get('depth')==1 and n['role'] in ('frame','window','dialog','alert','file chooser')]
        modal=next((n for n in reversed(tops) if 'modal' in n.get('states',())),None)
        top=modal or next((n for n in reversed(tops) if 'active' in n.get('states',())),None)
        if top is None:return nodes
        refs={top['ref']};scope=[]
        for n in nodes:
            if n['ref'] in refs or n.get('parent') in refs:
                refs.add(n['ref']);scope.append(n)
        return scope

    def find(self,name=None,roles=(),scope=True,timeout=10):
        deadline=time.monotonic()+timeout
        while True:
            observed=self.observe();nodes=self.scope(observed) if scope else observed['nodes']
            found=[n for n in nodes if (not roles or n['role'] in roles) and
                   (name is None or any(norm(n.get(k))==norm(name) for k in ('name','text','description')))]
            if found:return found[-1]
            if time.monotonic()>=deadline:raise AssertionError('visible control not found: '+str(name))
            time.sleep(.15)

    def click(self,name=None,roles=(),scope=True):
        return self.call('click',target=self.find(name,roles,scope)['ref'])

    def button(self,name):return self.click(name,('push button','button','toggle button'))

    def menu(self,path):
        self.press('Escape')
        for name in path:
            self.click(name,('menu','menu item','check menu item','radio menu item'),False)

    def goto(self,address):
        nodes=self.scope()
        fields=[n for n in nodes if n['role']=='text' and 'editable' in n.get('states',())
                and n['bounds'][0]<150 and n['bounds'][2]>100]
        assert fields,'visible name box is missing'
        self.call('fill',target=fields[0]['ref'],value=address)
        self.press('Return')

    def setcell(self,address,value):
        self.goto(address);self.call('type',value=str(value));self.press('Return')

    def fill(self,label,value,index=None):
        nodes=self.scope()
        fields=[n for n in nodes if n['role'] in ('text','entry','spin button','password text') and 'editable' in n.get('states',())]
        if index is not None:
            assert index<len(fields),'editable field index is missing'
            field=fields[index]
        else:
            field=next((n for n in fields if any(norm(n.get(k))==norm(label) for k in ('name','description'))),None)
            if field is None:
                caption=next((n for n in nodes if n['role']=='label' and norm(n['name'])==norm(label)),None)
                assert caption is not None,'visible field label not found: '+label
                x,y,w,h=caption['bounds']
                eligible=[n for n in fields if n['bounds'][0]>=x and abs(n['bounds'][1]+n['bounds'][3]/2-y-h/2)<max(22,h)]
                if eligible:
                    field=min(eligible,key=lambda n:abs(n['bounds'][1]-y)*8+abs(n['bounds'][0]-x-w))
                else:
                    below=[n for n in fields if 0 <= n['bounds'][1]-y-h < 80
                           and n['bounds'][0] < x+w and n['bounds'][0]+n['bounds'][2] > x]
                    assert below,'editable field missing: '+label
                    field=min(below,key=lambda n:abs(n['bounds'][0]-x)+abs(n['bounds'][1]-y-h)*4)
        self.call('fill',target=field['ref'],value=str(value))
        return field

    def choose(self,name,nth=None):
        if nth is not None:
            nodes=[n for n in self.scope() if norm(n.get('name'))==norm(name) and n['role'] in ('radio button','check box','page tab','menu item','list item','table cell','label')]
            return self.call('click',target=nodes[nth]['ref'])
        return self.click(name,('radio button','check box','page tab','menu item','list item','table cell','label'))

    def combo(self,label,value):
        nodes=self.scope()
        fields=[n for n in nodes if n['role']=='combo box']
        field=next((n for n in fields if norm(n.get('name'))==norm(label)),None)
        if field is None:
            caption=next((n for n in nodes if n['role']=='label' and norm(n['name'])==norm(label)),None)
            assert caption is not None,'combo label not found: '+label
            x,y,w,h=caption['bounds']
            field=min(fields,key=lambda n:abs(n['bounds'][1]-y)*8+abs(n['bounds'][0]-x-w))
        self.call('click',target=field['ref'])
        self.click(value,('menu item','list item','radio menu item','table cell'),False)

    def analysis(self,step):
        self.goto(step.get('range','B1:C7'))
        self.menu(step['path'])
        fields=step.get('fields',{})
        for index,(label,value) in enumerate(fields.items()):
            try:self.fill(label,value)
            except AssertionError:self.fill(None,value,index=index)
        if not fields:
            try:self.fill('Input range:',step.get('range','B1:C7'))
            except AssertionError:self.fill(None,step.get('range','B1:C7'),index=0)
        if step.get('labels',True):
            self.call('check',target=self.find('Labels',('check box',))['ref'],checked=True)
        for action in step.get('options',[]):self.run([action])
        self.choose('Output');self.choose('Output range:')
        self.fill(None,step.get('output','E1'),index=0)
        self.call('check',target=self.find('Autofit columns',('check box',))['ref'],checked=True)
        self.button('OK')
        self.goto('A1')

    def consolidate(self,step):
        self.goto(step['ranges'][0]);self.menu(['Data','Consolidate...'])
        self.combo('Function:',step.get('function','SUM'))
        for source in step['ranges'][1:]:
            cells=[n for n in self.scope() if n['role']=='table cell' and n.get('name')]
            assert cells,'source area table is missing'
            last=max(cells,key=lambda n:n['bounds'][1]);x,y,w,h=last['bounds']
            self.call('click',x=x+min(50,w/2),y=y+h+8,click_count=2)
            self.call('type',value=source);self.press('Return')
        self.choose('Output');self.choose('Output range:');self.fill(None,step['output'],index=0)
        self.button('OK');self.goto(step['output'])

    def sheet_visibility(self,step):
        self.menu(['Edit','Sheet','Manage Sheets...'])
        row=self.find(step['sheet'],('table cell',))
        x,y,w,h=row['bounds']
        cells=[n for n in self.scope() if n['role']=='table cell' and abs(n['bounds'][1]-y)<3 and n['bounds'][0]<x]
        assert cells,'sheet visibility control missing'
        toggle=max(cells,key=lambda n:n['bounds'][0])
        if ('checked' in toggle.get('states',()))!=step['visible']:self.call('click',target=toggle['ref'])
        self.button('Close')

    def path(self,name,area='inbox'):
        return (self.inbox if area=='inbox' else self.outbox)+'/'+name

    def open(self,name,area='inbox'):
        self.press('Control+O')
        self.find(roles=('file chooser',))
        self.press('Control+L');self.press('Control+A')
        self.call('type',value=self.path(name,area));self.press('Return')
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            nodes=self.scope()
            if any(n['role']=='file chooser' for n in nodes):
                self.button('Open')
            elif any(n['role']=='dialog' and 'Text Import' in n['name'] for n in nodes):
                self.button('Finish')
            else:break
            time.sleep(.2)

    def save(self,name):
        self.press('Control+Shift+S')
        self.find(roles=('file chooser',))
        self.press('Control+L');self.press('Control+A')
        self.call('type',value=self.path(name,'outbox'));self.press('Tab')
        self.button('Save')
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            nodes=self.scope()
            if any(n['role']=='file chooser' for n in nodes):
                self.button('Save')
            elif any(n['role'] in ('dialog','alert') for n in nodes):
                names={norm(n['name']) for n in nodes if n['role']=='push button'}
                if 'replace' in names:self.button('Replace')
                elif 'save' in names:self.button('Save')
                elif 'ok' in names:self.button('OK')
                else:raise AssertionError('unexpected save dialog')
            else:return
            time.sleep(.2)
        raise AssertionError('save dialog did not close')

    def settle(self):
        self.call('move',x=1200,y=897,seconds=.1)
        self.call('wait',seconds=.5)

    def run(self,steps):
        for step in steps:
            op=step['op']
            if op=='analysis':self.analysis(step)
            elif op=='consolidate':self.consolidate(step)
            elif op=='sheet-visibility':self.sheet_visibility(step)
            elif op=='simulation-summary':
                self.call('maximize')
                field=next(n for n in self.scope() if n['role']=='text' and 'Simulation #' in n.get('text',''))
                self.call('click',target=field['ref']);self.press('Control+End')
            elif op=='open':self.open(step['file'],step.get('area','inbox'))
            elif op=='save':self.save(step['file'])
            elif op=='goto':self.goto(step['range'])
            elif op=='set':
                for address,value in step['cells'].items():self.setcell(address,value)
            elif op=='menu':self.menu(step['path'])
            elif op=='key':self.press(step['key'])
            elif op=='button':self.button(step['name'])
            elif op=='choose':self.choose(step['name'],step.get('nth'))
            elif op=='combo':self.combo(step['label'],step['value'])
            elif op=='fill':self.fill(step.get('label'),step['value'],step.get('index'))
            elif op=='check':self.call('check',target=self.find(step['name'],('check box','radio button','toggle button'))['ref'],checked=step.get('checked',True))
            elif op=='type':self.call('type',value=step['value'])
            elif op=='click':self.call('click',**{k:v for k,v in step.items() if k!='op'})
            elif op=='drag':self.call('drag',**{k:v for k,v in step.items() if k!='op'})
            elif op=='focus':
                active=next(w for w in self.call('windows')['windows'] if w.get('active'))
                self.call('focus_window',window=active['ref'])
            elif op=='wait':self.call('wait',seconds=step.get('seconds',.5))
            else:raise AssertionError('unknown reference recipe '+op)
