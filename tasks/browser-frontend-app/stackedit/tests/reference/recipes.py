"""Reference-only routes to public goals. These captions are never candidate requirements."""
import base64
import time
from pathlib import Path
import checks


class UI:
    def __init__(self,ctx):self.ctx=ctx;self.b=ctx.broker;self.snap=None
    def call(self,op,**kw):
        r=self.b.call({'op':op,**kw})
        if isinstance(r,dict) and 'controls' in r:self.snap=r
        return r
    def snapshot(self):return self.call('snapshot')
    def quiet_offline_notice(self):
        deadline=time.monotonic()+7
        while 'You are offline.' in self.snapshot().get('text','') and time.monotonic()<deadline:
            self.call('wait',seconds=.5)
    def editor(self):return checks.source_control(self.snapshot())
    def editor_fill(self,text):
        c=self.editor();self.call('fill',target={'ref':c['ref']},value=text)
        self.call('wait',seconds=1.1)
        actual=self.editor().get('value','').rstrip('\n')
        assert actual==text.rstrip('\n'), 'Prepared or entered document differs from the exact supplied text.'
    def select(self,start,end):
        c=self.editor();self.call('select_text',target={'ref':c['ref']},start=start,end=end)
    def click_text(self,text):return self.call('click',target={'text':text})
    def title(self,title):return self.call('click',target={'title':title})
    def menu(self,label):
        snap=self.snapshot()
        close=any(c.get('title')=='Close side bar' for c in snap['controls'])
        if not close:self.title('Toggle side bar')
        if any(c.get('title')=='Main menu' for c in self.snapshot()['controls']):self.title('Main menu')
        for _ in range(3):
            candidates=[c for c in self.snapshot()['controls'] if c.get('tag') in ('a','label') and label.lower() in (c.get('text') or '').lower()]
            if candidates:return self.call('click',target={'ref':candidates[0]['ref']})
            self.call('wheel',x=1170,y=730,delta_y=600)
        return self.click_text(label)
    def execute(self,steps):
        for step in steps:
            do=step.get('do')
            if not do:
                if step['op']=='reload':self.call('wait',seconds=2)
                self.call(step['op'],**{k:v for k,v in step.items() if k!='op'})
            elif do=='title':self.title(step['value'])
            elif do=='text-contains':
                self.call('click',target={'text':step['value'],'exact':False})
            elif do=='text':self.click_text(step['value'])
            elif do=='menu':self.menu(step['value'])
            elif do=='source':self.editor_fill(step['value'])
            elif do=='selection':self.select(step['start'],step['end'])
            elif do=='rename':
                c=next(c for c in self.snapshot()['controls'] if c.get('tag')=='input' and c.get('type')=='text')
                self.call('fill',target={'ref':c['ref']},value=step['value']);self.call('press',key='Enter')
            elif do=='field':
                candidates=[c for c in self.snapshot()['controls'] if c.get('tag') in ('input','textarea','select') or c.get('editable')]
                for key in ('tag','type','label','placeholder'):
                    if key in step:candidates=[c for c in candidates if c.get(key)==step[key]]
                c=candidates[step.get('nth',0)]
                self.call('select' if c.get('tag')=='select' else 'fill',target={'ref':c['ref']},value=step['value'])
            elif do=='upload':
                data=(self.ctx.inputs/step['file']).read_bytes()
                self.call('upload',filename=step['file'],base64=base64.b64encode(data).decode(),mime_type=step.get('mime','text/plain'))
            elif do=='code-field':
                choices=[c for c in self.snapshot()['controls'] if c.get('editable') or c.get('tag')=='textarea']
                self.call('fill',target={'ref':choices[-1]['ref']},value=step['value'])
            elif do=='dismiss-tour':
                choices=[c for c in self.snapshot()['controls'] if (c.get('text') or '').strip().lower()=='skip']
                if choices:self.call('click',target={'ref':choices[0]['ref']})
            elif do=='scroll-source':
                x,y,w,h=self.editor()['bounds']
                self.call('wheel',x=x+w/2,y=max(150,min(y+h/2,650)),delta_y=step['delta'])
            elif do=='modal-ok':
                self.call('wheel',x=840,y=690,delta_y=1400)
                self.click_text('Ok')
            elif do in ('new-file','new-folder'):
                if not any(c.get('title')=='New file' for c in self.snapshot()['controls']):self.title('Toggle explorer')
                self.title('New file' if do=='new-file' else 'New folder')
                c=next(c for c in self.snapshot()['controls'] if c.get('tag')=='input' and c.get('type')=='text' and not c.get('label'))
                self.call('fill',target={'ref':c['ref']},value=step['name']);self.call('press',key='Enter')
            elif do=='drag-text':
                snap=self.snapshot()
                find=lambda word:next(c for c in snap['controls'] if (c.get('text') or '').strip()==word)
                a,b=find(step['text']),find(step['to'])
                x,y,w,h=a['bounds'];dx,dy,dw,dh=b['bounds']
                self.call('drag',x=x+w/2,y=y+h/2,to_x=dx+dw/2,to_y=dy+dh/2,steps=20)
            elif do=='tree-child':
                def entries():
                    return [c for c in self.snapshot()['controls'] if (c.get('text') or '').strip()==step['child'] and c.get('tag') in ('a','div')]
                if not entries():self.click_text(step['parent'])
                children=entries()
                assert children,'The moved child must be visible in the expanded folder.'
                parent=next(c for c in self.snap['controls'] if (c.get('text') or '').strip()==step['parent'])
                assert any(c['bounds'][1]>parent['bounds'][1] for c in children),'The child is not visibly nested beneath its destination.'
            elif do=='download':
                until=time.monotonic()+12
                while not any(d['filename'].endswith(step['suffix']) for d in self.snapshot().get('downloads',[])):
                    assert time.monotonic()<until,'No expected download appeared.'
                    self.call('wait',seconds=.3)
            elif do=='expect':
                snap=self.snapshot();text=snap.get('text','')+'\n'+'\n'.join((c.get('text') or '')+' '+(c.get('value') or '') for c in snap['controls'])
                assert step['value'] in text,'Expected visible text: '+step['value']
            else:raise ValueError('Unknown recipe instruction '+str(do))
        self.call('wait',seconds=.4)
        self.quiet_offline_notice()


def execute(ctx,cp):UI(ctx).execute(cp['recipe'])
