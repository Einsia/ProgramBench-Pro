"""Pinned product recipes use only public browser operations and visible controls."""
import re,time


class UI:
    def __init__(self,broker):self.broker=broker;self.snap={}
    def call(self,op,**kw):
        r=self.broker.call({'op':op,'session':'main',**kw})
        if 'controls' in r:self.snap=r
        return r
    def snapshot(self):return self.call('snapshot')
    def wait(self,predicate,description,seconds=12):
        end=time.monotonic()+seconds
        while True:
            s=self.snapshot();found=predicate(s)
            if found:return found
            assert time.monotonic()<end,description+' at '+s.get('url','')
            self.call('wait',seconds=.25)
    def require(self,*texts):
        for text in texts:self.wait(lambda s,t=text:t.casefold() in (s['text']+' '+' '.join(s.get('document_text',[]))+' '+ ' '.join(str(x.get('value','')) for x in s['controls'])).casefold(),'missing visible text '+text)
    def goto(self,path):
        self.call('open',path=path);self.call('wait',seconds=.4)
    def click(self,text,role=None,nth=0):
        def locate(s):
            cs=[c for c in s['controls'] if (role is None or c.get('role')==role or c['tag']==role) and not c.get('disabled') and any(str(c.get(k,'')).strip().casefold()==text.casefold() for k in ('text','label','aria','title'))]
            return cs[nth] if len(cs)>nth else None
        c=self.wait(locate,'missing control '+text);self.call('click',target={'ref':c['ref']})
    def fill(self,label,value):
        c=self.wait(lambda s:next((x for x in s['controls'] if x['tag'] in ('input','textarea') and (x.get('label')==label or x.get('placeholder')==label)),None),'missing field '+label)
        self.call('fill',target={'ref':c['ref']},value=str(value))
    def check(self,label,value=True):
        c=self.wait(lambda s:next((x for x in s['controls'] if x.get('label')==label and 'checked' in x),None),'missing check '+label)
        self.call('check',target={'ref':c['ref']},checked=value)
    def point(self,x,y):self.call('pointer',x=x,y=y,action='click')
    def select(self,label,value):
        c=self.wait(lambda s:next((x for x in s['controls'] if x.get('label')==label and x['tag']=='input'),None),'missing choice '+label)
        self.call('click',target={'ref':c['ref']});self.click(value)
    def sign_in(self,email,password):
        self.goto('/login');self.fill('Email',email);self.fill('Password',password);self.click('Sign In')
        self.wait(lambda s:not s['url'].startswith('/login'),'login did not complete')
    def edit(self,kind):
        # Pencil actions at the top of the pinned reference's details page.
        x=1156 if kind=='series' else 380
        control=self.wait(lambda s:next((c for c in s['controls'] if c['tag']=='button' and not c.get('disabled') and c['bounds'][0]<=x<c['bounds'][0]+c['bounds'][2] and 65<=c['bounds'][1]<120),None),'detail edit button not ready',seconds=30)
        self.call('click',target={'ref':control['ref']})
        self.require('Save Changes')
    def save(self):
        self.click('Save Changes');self.wait(lambda s:not any(c.get('role')=='dialog' and c.get('text') for c in s['controls']),'editor did not close')
        self.call('wait',seconds=.4)
