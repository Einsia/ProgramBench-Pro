from evaluation.driver import Hooks as Base
import checks
from reference.recipes import execute

class Hooks(Base):
    def setup(self,ctx,item):
        for request in item['requests']:
            answer=ctx.broker.call(request)
            if request['op'] in ('open','configure','restart'):
                assert answer.get('ready'), 'application did not draw its interface'
            elif request['op']=='repository':
                assert answer['status'].get('ready'), 'application did not draw its interface'
    def prepare(self,ctx,checkpoint):
        ctx.state['cache']={}
        if not ctx.gui:drive=checks.drive;drive(ctx,checkpoint.get('steps',[]))
    def recipe(self,ctx,checkpoint):execute(ctx,checkpoint)
    def collect(self,ctx,checkpoint):
        for request in checkpoint.get('collect',[]):ctx.broker.call(request)
    def check(self,ctx,checkpoint,assertion):return checks.observe(ctx,assertion['check'])
    def judge(self,ctx,checkpoint,assertion,actual,expected):
        assert actual==expected, f'Expected {expected!r}; observed {actual!r}'
