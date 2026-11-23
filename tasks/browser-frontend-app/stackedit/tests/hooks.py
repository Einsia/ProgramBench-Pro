"""All preparation and observations use the public, shared runtime."""
from pathlib import Path
from evaluation.driver import Hooks as Base
import checks
from reference import recipes

FIXTURES=Path(__file__).resolve().parent/'fixtures'


class Hooks(Base):
    def inputs(self,ctx):
        for name in ctx.episode.get('inputs',{}).get('files',[]):
            (ctx.inputs/name).write_bytes((FIXTURES/name).read_bytes())
    def prepare(self,ctx,cp):
        ctx.state.clear()
        if cp.get('continues'):return
        status=ctx.broker.call({'op':'reset'})
        assert status.get('ready'),'The application did not start after reset.'
        if ctx.episode['execution']=='program':return
        for document in cp.get('temporary',[]):
            ctx.broker.call({'op':'embed_open',**document})
            ctx.broker.call({'op':'wait','seconds':2})
        if cp.get('embedding'):
            ctx.broker.call({'op':'embed_open','text':cp['text'],**cp['embedding']})
            return
        ui=recipes.UI(ctx);snap=ui.call('open')
        # A first-run tour is optional; equivalent candidates need not have one.
        skips=[c for c in snap.get('controls',[]) if (c.get('text') or '').strip().lower()=='skip']
        if skips:ui.call('click',target={'ref':skips[0]['ref']})
        if cp.get('text') is not None:ui.editor_fill(cp['text'])
        if cp.get('selection') is not None:ui.select(*cp['selection'])
        # Management and history actions belong to the GUI goal, never to a
        # candidate setup route that assumes the reference's labels or layout.
        assert not cp.get('prepare'), 'GUI preparations must be explicit goal actions.'
    def recipe(self,ctx,cp):recipes.execute(ctx,cp)
    def collect(self,ctx,cp):
        if cp.get('carry_download'):
            # Preserve the exact bytes obtained from the public download
            # channel. BrokerSurface lists this ordinary input on the next
            # checkpoint, using the same runtime upload operation.
            name=cp['carry_download']
            assert Path(name).name==name
            (ctx.inputs/name).write_bytes(checks.take_download(ctx,Path(name).suffix)[1])
    def check(self,ctx,cp,assertion):return checks.observe(ctx,cp,assertion['check'])
    def judge(self,ctx,cp,assertion,actual,expected):checks.compare(actual,expected)
