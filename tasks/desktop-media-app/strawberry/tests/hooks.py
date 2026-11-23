"""Strawberry episode hooks for the episode driver."""
from evaluation.driver import Hooks as Base
from harness import Context,compare,value
import backend

class Hooks(Base):
    def start(self,ctx):ctx.state['c']=Context(ctx)
    def setup(self,ctx,item):
        c=ctx.state['c']
        if item['op']=='documents':
            for name in item['files']:
                area=item.get('area','inputs')
                if name.casefold().endswith(('.png','.jpg','.jpeg','.bmp','.gif','.webp')):area='inputs'
                c.document(name,area)
        elif item['op']=='load':c.load([c.document(n,item.get('area','inputs')) for n in item['files']],len(item['files']))
        elif item['op']=='rating-collection':
            import fixtures
            for name in list(fixtures.GUI)[:3]:c.document(name,'music')
            c.call(op='restart');c.call(op='wait',seconds=1)
        elif item['op']=='playlist-library':
            import fixtures
            for title,file in zip(('Zulu Mix','Alpha Mix','Evening 音楽'),list(fixtures.GUI)[:3]):
                c.cli('--create',title,c.document(file))
            c.wait(lambda:c.get('PlaylistCount','Playlists')==4)
        elif item['op']=='restart':
            c.call(op='restart');c.call(op='wait',seconds=1)
        elif item['op']=='collection':
            for n in item['files']:c.document(n,'music')
            from reference.recipes import menu
            menu(c,'Tools','Do a full collection rescan')
            c.call(op='wait',seconds=1)
        else:raise ValueError(item['op'])
    def prepare(self,ctx,cp):
        c=ctx.state['c'];c.current=cp['id'];c.cache={}
        if not ctx.gui and not c.call(op='status').get('ready'):
            c.call(op='reset');c.uploaded.clear()
        for item in cp.get('preparation',[]):self.setup(ctx,item)
    def recipe(self,ctx,cp):
        from reference.recipes import execute
        execute(ctx.state['c'],cp['recipe'])
    def check(self,ctx,cp,a):
        c=ctx.state['c']
        if ctx.gui:
            import checks
            return checks.observe(c,a['check'])
        if not c.cache:
            try:c.cache['result']=backend.run(c,cp['action'])
            except Exception as exc:c.cache['error']=exc
        if 'error' in c.cache:raise c.cache['error']
        raw=c.cache['result'];key=a['field']
        if cp['action']['kind'] in ('metadata','metadata-variant'):
            if cp['action']['kind']=='metadata-variant':
                return {'present':False} if key not in raw else {'present':True,'value':value(raw,key)}
            return value(raw,key)
        assert key in raw,'missing observation '+key
        return raw[key]
    def judge(self,ctx,cp,a,actual,expected):compare(actual,expected)
