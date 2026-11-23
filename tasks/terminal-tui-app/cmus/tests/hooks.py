from evaluation.driver import Hooks as Base
from harness import Session
import checks
class Hooks(Base):
    def start(self,ctx):ctx.state['session']=Session(ctx.broker)
    def setup(self,ctx,item):checks.setup(ctx.state['session'],item)
    def prepare(self,ctx,cp):
        ctx.state['cache']={};ctx.state['session'].saved={}
        checks.drive(ctx.state['session'],cp.get('prepare',[]))
        if not ctx.gui:checks.drive(ctx.state['session'],cp.get('steps',[]))
    def recipe(self,ctx,cp):checks.drive(ctx.state['session'],cp.get('steps',[]))
    def check(self,ctx,cp,a):
        c=a['check'];key=checks.check_key(c);cache=ctx.state['cache']
        if key not in cache:
            try:cache[key]=(checks.observe(ctx.state['session'],c),None)
            except Exception as e:cache[key]=(None,e)
        value,err=cache[key]
        if err:raise err
        return checks.project(value,c)
    def judge(self,ctx,cp,a,actual,expected):checks.compare(actual,expected,a['check'])
