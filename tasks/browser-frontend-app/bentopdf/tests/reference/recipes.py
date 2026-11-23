"""Pinned-standard recipes through public runtime controls. Never used to locate candidate controls."""
import base64
import re
import time

class UI:
    def __init__(self,ctx):self.ctx=ctx;self.broker=ctx.broker;self.snap=None
    def call(self,d):
        r=self.broker.call(d)
        if isinstance(r,dict) and 'controls' in r:self.snap=r
        return r
    def snapshot(self):return self.call({'op':'snapshot'})
    def find(self,spec,snap=None):
        matches=[]
        for c in (snap or self.snap or self.snapshot()).get('controls',[]):
            ok=True
            for k in ('text','title','label','aria','placeholder','context','tag','type','role'):
                if k in spec:
                    have=' '.join(str(c.get(k,'')).split());want=' '.join(str(spec[k]).split())
                    ok&=want.lower() in have.lower() if spec.get('contains') else have==want
            if 'file' in spec:ok&=bool(c.get('file'))==spec['file']
            if 'option' in spec:ok&=any(spec['option'] in (o['value'],o['label']) for o in c.get('options',[]))
            if ok:matches.append(c)
        return matches[spec.get('nth',0)] if len(matches)>spec.get('nth',0) else None
    def locate(self,spec,scroll=True):
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            c=self.find(spec,self.snapshot())
            if c:return c
            self.call({'op':'wait','seconds':.3})
            if scroll:break
        if scroll:
            for _ in range(12):
                self.call({'op':'wheel','x':1100,'y':650,'delta_y':550})
                c=self.find(spec)
                if c:return c
            self.call({'op':'wheel','x':1100,'y':350,'delta_y':-5000})
        raise AssertionError('Reference control not found: '+str(spec))
    def click(self,spec):return self.call({'op':'click','target':{'ref':self.locate(spec)['ref']}})
    def upload(self,name,control=None,add=False,stage=False):
        if not self.snap:self.snapshot()
        if not self.snap.get('file_chooser'):
            if control:self.click(control)
            elif add:
                c=next((c for c in self.snap['controls'] if re.search(r'add more',c.get('text',''),re.I)),None)
                if c:self.call({'op':'click','target':{'ref':c['ref']}})
                else:self.click({'text':'Click to select a file','contains':True})
            else:
                c=self.find({'file':True})
                if not c:
                    c=next((c for c in self.snap['controls'] if re.search(r'click.*(?:select|drop)|choose.*(?:file|pdf)',c.get('text',''),re.I)),None)
                    if not c:c=next((c for c in self.snap['controls'] if re.search(r'upload.*(?:pdf|file|image)',c.get('text',''),re.I)),None)
                if not c:raise AssertionError('No visible upload control')
                self.call({'op':'click','target':{'ref':c['ref']}})
        data=(self.ctx.inputs/name).read_bytes()
        mime={'.pdf':'application/pdf','.json':'application/json','.png':'image/png','.jpg':'image/jpeg','.svg':'image/svg+xml'}.get('.'+name.rsplit('.',1)[-1],'application/octet-stream')
        return self.call({'op':'upload','filename':name,'base64':base64.b64encode(data).decode(),'mime_type':mime,'stage':stage})
    def download(self,suffix=None,timeout=120):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            snap=self.snapshot()
            if any(not suffix or d['filename'].lower().endswith(suffix) for d in snap.get('downloads',[])):return
            self.call({'op':'wait','seconds':1})
        raise AssertionError('No requested product download: '+str(suffix))

def execute(ctx,cp):
    ui=UI(ctx);ui.snapshot()
    for step in cp['recipe']:
        do=step['do'];spec=step.get('target',{})
        if do=='upload':ui.upload(step['file'],step.get('target'),step.get('add',False),step.get('stage',False))
        elif do=='click':ui.click(spec)
        elif do in {'fill','select','check'}:
            r={'op':do,'target':{'ref':ui.locate(spec)['ref']}}
            if do=='check':r['checked']=step.get('checked',True)
            else:r['value']=str(step['value'])
            ui.call(r)
            if step.get('enter'):ui.call({'op':'press','key':'Enter'})
        elif do=='type':ui.call({'op':'type','value':step['value']})
        elif do=='press':ui.call({'op':'press','key':step['key']})
        elif do=='wait':ui.call({'op':'wait','seconds':step.get('seconds',1)})
        elif do=='download':ui.download(step.get('suffix'),step.get('timeout',120))
        elif do=='dialog':ui.call({k:v for k,v in dict(step,op='dialog').items() if k!='do'})
        elif do=='pointer' or do=='drag':ui.call({k:v for k,v in dict(step,op=do).items() if k!='do'})
        elif do=='select-text-block':
            # The canvas and its format panel appear before the document's editable
            # paragraphs finish loading. Only a selected paragraph populates Font size.
            deadline=time.monotonic()+30
            while True:
                ready=ui.find({'title':'Font size'},ui.snapshot())
                if ready and ready.get('value') not in (None,'') and not ready.get('disabled'):break
                assert time.monotonic()<deadline,'Text paragraph did not become editable'
                ui.call({'op':'pointer','x':step['x'],'y':step['y']})
                ui.call({'op':'wait','seconds':.5})
        elif do=='wheel':ui.call({k:v for k,v in dict(step,op='wheel').items() if k!='do'})
        elif do=='expect':
            assert step['text'] in ui.snapshot()['text'],'Expected visible result is missing'
        elif do=='wait-text':
            deadline=time.monotonic()+step.get('timeout',60)
            while step['text'] not in ui.snapshot()['text'] and time.monotonic()<deadline:ui.call({'op':'wait','seconds':1})
            assert step['text'] in ui.snapshot()['text'],'Expected visible result did not appear: '+step['text']
        elif do=='open':ui.call({'op':'open','path':step['path']})
        elif do=='reopen-result':
            pending=ui.snapshot()['downloads'];suffix=step.get('suffix','.pdf')
            chosen=next(d for d in reversed(pending) if d['filename'].lower().endswith(suffix))
            ui.call({'op':'open','path':step.get('path','/form-filler.html')})
            ui.click(step.get('target',{'text':'Click to select a file','contains':True}))
            ui.call({'op':'reuse_download','ref':chosen['ref']})
        elif do=='restart':ui.call({'op':'restart'})
        elif do=='reload':ui.call({'op':'reload'})
        elif do=='close-success':
            for _ in range(3):
                snap=ui.snapshot()
                c=next((c for c in snap['controls'] if c.get('tag')=='button' and (c.get('text') or '').strip().lower() in {'ok','okay'}),None)
                if not c:break
                ui.call({'op':'click','target':{'ref':c['ref']}})
        elif do=='maybe-ok':
            c=ui.find({'text':'OK','tag':'button'},ui.snapshot())
            if c:ui.call({'op':'click','target':{'ref':c['ref']}})
        else:raise ValueError('Unknown reference action '+do)
    ui.call({'op':'wait','seconds':.3})
