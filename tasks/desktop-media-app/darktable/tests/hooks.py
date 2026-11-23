"""darktable hooks for the shared driver; all product access uses runtime RPC."""
import os
import tempfile
import time
from pathlib import Path

from evaluation.driver import Hooks as Base
from harness import Context,compare
import fixtures
import semantic


class Hooks(Base):
    def start(self,ctx):
        ctx.state['c']=Context(ctx.broker,ctx.out,tempfile.mkdtemp(prefix='darktable-',dir=os.environ.get('TMPDIR')))

    def setup(self,ctx,item):
        c=ctx.state['c']
        for name in item.get('files',[]):c.fixture(name)
        for directory in item.get('directories',[]):c.call({'op':'mkdir','directory':directory})

    def prepare(self,ctx,checkpoint):
        if ctx.gui:
            from reference.recipes import wait_stable
            wait_stable(ctx)
        if checkpoint.get('lifecycle')=='restart':
            ctx.state['c'].files.clear()

    def recipe(self,ctx,checkpoint):
        from reference.recipes import execute
        try:
            execute(ctx,checkpoint)
        except Exception:
            import base64,json
            try:
                (ctx.out/('recipe-failure-'+checkpoint['id']+'.json')).write_text(json.dumps(ctx.broker.call({'op':'observe'}),indent=2))
                shot=ctx.broker.call({'op':'screenshot'})
                (ctx.out/('recipe-failure-'+checkpoint['id']+'.png')).write_bytes(base64.b64decode(shot['png_base64']))
            except Exception:pass
            raise

    def check(self,ctx,checkpoint,assertion):
        c=ctx.state['c'];c.current_case=assertion['id']
        if not ctx.gui:
            import backend
            return backend.observe(c,checkpoint['case'])
        check=assertion['check'];kind=check['kind']
        if kind in ('xmp','module'):
            deadline=time.monotonic()+20
            while True:
                data=c.fetch('inputs/'+check.get('file','chart.png')+'.xmp')
                try:
                    value=semantic.sidecar(data) if kind=='xmp' else semantic.module(data,check['module'],check.get('fields',[]))
                except AssertionError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.3)
                    continue
                if all(value.get(k)==v or (isinstance(v,(float,int)) and isinstance(value.get(k),(float,int)) and abs(value[k]-v)<.005) for k,v in check.get('expect',{}).items()):break
                if time.monotonic()>=deadline:raise AssertionError('sidecar did not reach requested state: '+str({k:value.get(k) for k in check.get('expect',{})}))
                time.sleep(.3)
            return {k:value[k] for k in check.get('keys',check.get('expect',{}))} if kind=='xmp' else value
        if kind=='export':
            data=c.fetch('outputs/'+check['file'])
            suffix=Path(check['file']).suffix
            return {'format':semantic.require_container(data,suffix,c.scratch),
                    'image':semantic.image(data,suffix,c.scratch)}
        if kind=='gps':
            value=semantic.gps(c.fetch('inputs/chart.png.xmp'))
            assert all(abs(value[k]-check[k])<.0001 for k in ('latitude','longitude')),'geotag coordinates differ'
            return value
        if kind=='duplicate':
            names=[n['filename'] for n in c.inventory() if n['filename'].startswith('inputs/chart') and n['filename'].endswith('.png.xmp')]
            assert len(names)==check['count'],'the expected image versions were not written'
            if 'rating' in check:
                values=[semantic.sidecar(c.fetch(n))['rating'] for n in names]
                assert all(v==check['rating'] for v in values),'the image versions have incorrect ratings'
            return {'versions':len(names),**({'rating':check['rating']} if 'rating' in check else {})}
        if kind=='style':
            value=semantic.style(c.fetch('outputs/'+check['file']))
            for key,expected in check.get('expect',{}).items():
                assert value[key]==expected,'style '+key+' differs'
            return value
        if kind=='files':
            names={n['filename'] for n in c.inventory()}
            assert set(check['present'])<=names,'requested file is missing'
            assert not set(check['absent'])&names,'removed file still exists'
            return {'present':sorted(check['present']),'absent':sorted(check['absent'])}
        if kind=='file-copy':
            data=c.fetch(check['file']);assert data==fixtures.image(check['source']),'copied image bytes differ'
            return {'identical':True}
        if kind=='history-discarded':
            value=semantic.sidecar(c.fetch('inputs/'+check['file']+'.xmp'))
            active=[h for h in value['history'] if h.get('operation')==check['module'] and h.get('enabled')=='1']
            assert not active,'discarded image still has an active edit'
            return {'discarded':check['module']}
        if kind=='history-compressed':
            data=c.fetch('inputs/'+check['file']+'.xmp')
            history=semantic.sidecar(data)['history']
            result={}
            for name,field,offset,expected in (('exposure','exposure',8,1.),('colorcontrast','contrast',0,2.5)):
                entries=[h for h in history if h.get('operation')==name]
                keys=[h.get('multi_priority','0') for h in entries]
                assert len(keys)==len(set(keys)),'history still has superseded '+name+' entries'
                value=semantic.module(data,name,[(field,'f',offset)])
                assert value['enabled']==1 and abs(value[field]-expected)<.005,'compressed history changed an edit'
                result[name]=value
            return result
        raise ValueError(kind)

    def judge(self,ctx,checkpoint,assertion,actual,expected):compare(actual,expected)

    def after(self,ctx,checkpoint):
        if ctx.episode['id']=='preferences-persistence':
            # Evidence and checks have captured the setting. Closing the modal
            # dialog allows the product to complete its normal shutdown.
            ctx.broker.call({'op':'press','key':'Escape'})

    def close(self,ctx):
        if 'c' in ctx.state:ctx.state['c'].close()
