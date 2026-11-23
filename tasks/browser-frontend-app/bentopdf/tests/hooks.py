"""Only the runtime's public GUI and file exchange reach the candidate."""
from pathlib import Path
from evaluation.driver import Hooks as Base
from runtime_client import RuntimeClient
from reference import recipes
import checks
import semantics
INPUTS=Path(__file__).resolve().parent/'fixtures'

class Hooks(Base):
    def start(self,ctx):
        ctx.broker=ctx.runtime.client=RuntimeClient(ctx.broker)
        ctx.state['outputs']=checks.Outputs(ctx.broker)
    def inputs(self,ctx):
        for name in ctx.episode['inputs']['files']:(ctx.inputs/name).write_bytes((INPUTS/name).read_bytes())
    def prepare(self,ctx,cp):
        output=ctx.state['outputs'];output.close();output.reset()
        if cp.get('fresh',True):
            status=ctx.broker.call({'op':'reset'})
            assert status.get('ready'),'Application failed to reset'
        ctx.broker.call({'op':'open','path':cp['path']})
    def recipe(self,ctx,cp):recipes.execute(ctx,cp)
    def check(self,ctx,cp,a):return checks.observe(ctx,cp,a['check'])
    def judge(self,ctx,cp,a,actual,expected):
        spec=a['check']
        if spec['kind'] in semantics.KINDS:return semantics.judge(actual,expected,spec,checks.compare)
        if spec['kind'].startswith('image-'):
            for key in expected:semantics.multiset_match(actual[key],expected[key],checks.compare,spec.get('tol',.1),key)
            return
        checks.compare(actual,expected,spec.get('tol',.1))
    def close(self,ctx):ctx.state['outputs'].close()
