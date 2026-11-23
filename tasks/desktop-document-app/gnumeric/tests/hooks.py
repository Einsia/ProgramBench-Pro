"""Task hooks: every application-facing action uses a public runtime channel."""
from evaluation.driver import Hooks as Base
import backend
import checks
import fixtures


class Hooks(Base):
    def setup(self,ctx,item):
        if item['op']=='upload':
            for name in item['files']:
                checks.upload(ctx,name,fixtures.named(name),area=item.get('area','inbox'),read_only=item.get('read_only',False))
        else:backend.setup(ctx,item)

    def prepare(self,ctx,checkpoint):
        ctx.state['checkpoint']=checkpoint['id']

    def begin(self,ctx,checkpoint):
        if ctx.record:
            from reference.recipes import Reference
            if 'reference' not in ctx.state:ctx.state['reference']=Reference(ctx)
            driver=ctx.state['reference']
            if checkpoint['id']==ctx.episode['checkpoints'][0]['id']:
                driver.run(ctx.episode.get('prepare',[]))
            driver.settle()

    def recipe(self,ctx,checkpoint):
        ctx.state['reference'].run(checkpoint['recipe'])
        ctx.state['reference'].settle()

    def check(self,ctx,checkpoint,assertion):
        if not ctx.gui:return backend.evaluate(ctx,checkpoint,assertion)
        value=checks.read_gui(ctx,assertion['check'])
        if ctx.record and assertion['check']['kind']=='analysis-region':
            previous=ctx.state.get('record-analysis-result')
            if previous is not None:assert value!=previous,'source edit did not change the analysis results'
            ctx.state['record-analysis-result']=value
        if ctx.record and 'expected' in assertion['check']:
            checks.compare(value,assertion['check']['expected'])
        return value

    def judge(self,ctx,checkpoint,assertion,actual,expected):
        check=assertion['check']
        if check.get('kind')=='document-export' and check.get('aspect')=='page-size':
            observed,recorded=actual['page-size'],expected['page-size']
            assert len(observed)==len(recorded),'printed page count differs'
            assert all(len(a)==2 and all(abs(x-y)<=1.0 for x,y in zip(a,b)) for a,b in zip(observed,recorded)),'paper dimensions differ'
        elif check.get('kind')=='analysis-region':
            checks.compare(actual,expected)
        elif check.get('kind')=='roundtrip-structure' and check.get('aspect') in ('column-width','row-height'):
            name='width' if check['aspect']=='column-width' else 'height'
            assert isinstance(actual.get(name),(int,float)) and abs(actual[name]-expected[name])<=1.0,'saved geometry differs'
        else:
            checks.compare(actual,expected)
