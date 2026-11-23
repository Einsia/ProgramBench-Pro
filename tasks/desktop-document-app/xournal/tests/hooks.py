"""Task hooks; all product interaction travels through the public runtime."""
from evaluation.driver import Hooks as Base
import checks
import fixtures
import program
from reference import recipes


class Hooks(Base):
    def start(self,ctx):
        files=ctx.runtime.instance.parent/'files'
        ctx.state.update(inbox=str(files/'inbox'),outbox=str(files/'outbox'),observed={})

    def setup(self,ctx,item):
        assert item['op']=='upload'
        for value in item['files']:
            entry={'name':value,'fixture':value} if isinstance(value,str) else value
            program.upload(ctx,entry['name'],fixtures.gui(entry['fixture']),area=item.get('area','inbox'))

    def begin(self,ctx,cp):
        if ctx.record:recipes.begin(ctx,cp)

    def recipe(self,ctx,cp):
        recipes.execute(ctx,cp)

    def check(self,ctx,cp,assertion):
        cache=ctx.state['observed']
        if cp['id'] not in cache:
            try:
                if ctx.gui:
                    value=checks.collect(ctx,cp)
                    if ctx.record and cp.get('expect'):checks.expect(value,cp['expect'])
                else:value=program.execute(ctx,cp)
                cache[cp['id']]=(value,None)
            except Exception as e:cache[cp['id']]=(None,e)
        value,error=cache[cp['id']]
        if error is not None:raise error
        return checks.project(value,assertion['aspect'],assertion.get('projection')) if ctx.gui else program.project(value,assertion['aspect'])

    def judge(self,ctx,cp,assertion,actual,expected):
        (checks if ctx.gui else program).compare(actual,expected)
