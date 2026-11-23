"""Task hooks for setup, deterministic recipes, public observations and comparison."""
import json
import time

from evaluation.driver import Hooks as Base
from harness import Context, Ref, expect, observed
import backend
import checks
import fixtures
from reference import recipes


class Hooks(Base):
    def start(self, ctx):
        ctx.state['c']=Context(ctx.broker)
        ctx.state['cache']={}

    def setup(self, ctx, item):
        c=ctx.state['c'];c.ready_api()
        if 'protocol_setup' in item:
            return backend.setup(ctx.episode['id'],item['protocol_setup'])(c)
        for book in item['books']:
            book={'title':book} if isinstance(book,str) else book
            body={'title':book['title']}
            if book.get('parent'):body['parent_id']=Ref(book['parent'])
            c.call('POST','/folders',body=body,save=book['title'])
        for note in item['notes']:
            body={k:v for k,v in note.items() if k!='book'}
            body['parent_id']=Ref(note.get('book','Workbench'))
            c.call('POST','/notes',body=body,save=note['title'])
        for name in item['files']:fixtures.upload(c,name)
        if item.get('archive'):
            import archives
            archives.setup(c,markdown=item['archive']=='markdown')
        if item.get('history'):
            history=item['history'];title=history['title']
            patch=lambda text:json.dumps([{'diffs':[[1,text]],'start1':0,'start2':0,'length1':0,'length2':len(text)}])
            c.call('DELETE','/notes/'+c.values[title]['id']+'/revisions')
            c.call('POST','/revisions',body={'item_type':1,'item_id':c.values[title]['id'],
                'item_updated_time':history['time'],'title_diff':patch(title),'body_diff':patch(history['body']),
                'metadata_diff':json.dumps({'new':{'parent_id':c.values['Workbench']['id'],'author':'Ada Lovelace'},'deleted':[]})})
        for search in item.get('searches',[]):
            end=time.monotonic()+120
            while True:
                rows=c.all('/search',fields='title',query={'query':search['query']})
                if sorted(x['title'] for x in rows)==sorted(search['titles']):break
                if time.monotonic()>=end:raise AssertionError('fixture search index did not settle: '+search['query'])
                time.sleep(.5)

    def begin(self, ctx, checkpoint):
        if ctx.record and checkpoint['id']==ctx.episode['checkpoints'][0]['id']:
            recipes.prepare(ctx)

    def recipe(self, ctx, checkpoint):
        recipes.execute(ctx,checkpoint)

    def check(self, ctx, checkpoint, assertion):
        c=ctx.state['c'];cache=ctx.state['cache']
        if 'check' in assertion:
            item=assertion['check'];key=(checkpoint['id'],json.dumps(item,sort_keys=True))
            if key not in cache:
                # Autosave and import are asynchronous. One observation is shared
                # by the independent aspects of a goal's actual result.
                end=time.monotonic()+12
                last = None
                while True:
                    try:
                        value=checks.observe(c,item)
                        last = value
                        if item['kind']=='note':
                            for field,wanted in item['values'].items():expect(observed(value,field),wanted)
                        cache[key]=(value,None);break
                    except Exception as exc:
                        if time.monotonic()>=end:
                            cache[key]=(last,None) if last is not None else (None,exc)
                            break
                        time.sleep(.4)
            value,error=cache[key]
            if error:raise error
            actual=observed(value,assertion['aspect'])
            if item['kind']=='note':expect(actual,item['values'][assertion['aspect']])
            if item['kind'].startswith('archive-'):
                import archives
                expect(actual,observed(archives.expected(markdown=item.get('format')=='markdown'),assertion['aspect']))
            return actual
        case=backend.case(ctx.episode['id'],checkpoint['id']);key=checkpoint['id']
        if key not in cache:
            try:cache[key]=(case.action(c),None)
            except Exception as exc:cache[key]=(None,exc)
        value,error=cache[key]
        if error:raise error
        aspect=assertion['aspect'];actual=observed(value,aspect)
        if aspect in case.expected:expect(actual,case.expected[aspect])
        return actual

    def judge(self, ctx, checkpoint, assertion, actual, expected):
        expect(actual,expected)
