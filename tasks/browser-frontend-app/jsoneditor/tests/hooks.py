"""Task-specific hooks. Every product read and action uses the public runtime."""
from evaluation.driver import Hooks as Base
import checks
from pathlib import Path
from reference import recipes

class Hooks(Base):
 def start(self,ctx):ctx.state['page']=None
 def inputs(self,ctx):
  for name in ctx.episode.get('inputs',{}).get('files',[]):
   (ctx.inputs/name).write_bytes((Path(__file__).parent/'fixtures'/name).read_bytes())
 def setup(self,ctx,item):
  if item['id']!='page':raise ValueError('unknown setup')
  ctx.broker.call({'op':'open'});ctx.state['page']='/'
 def prepare(self,ctx,cp):
  path=cp.get('page','/')
  if ctx.gui or ctx.state.get('page')!=path:
   ctx.broker.call({'op':'open','path':path});ctx.state['page']=path
  if cp.get('construct') is not None:
   checks.api(ctx,'construct',cp['construct'],cp.get('data',{}))
  elif 'data' in cp:checks.api(ctx,'set',cp['data'],editor=cp.get('editor','editor'))
  if 'text' in cp:checks.api(ctx,'setText',cp['text'])
  checks.execute(ctx,cp.get('prepare',[]))
  if 'selection_path' in cp:
   document=checks.value(ctx);parent=document
   for part in cp['selection_path'][:-1]:parent=parent[part]
   parent[cp['selection_path'][-1]]=cp['select_text'];checks.api(ctx,'set',document)
  if 'select_text' in cp:
   text=checks.value(ctx,'getText');start=text.index(cp['select_text']);end=start+len(cp['select_text'])
   def position(index):
    before=text[:index];return {'row':before.count('\n')+1,'column':len(before.rsplit('\n',1)[-1])+1}
   checks.api(ctx,'setTextSelection',position(start),position(end))
   checks.api(ctx,'focus')
 def begin(self,ctx,cp):
  if any(a.get('check',{}).get('type')=='no-download' for a in cp['assertions']):
   ctx.state['before_downloads']=[d['ref'] for d in ctx.broker.call({'op':'snapshot'}).get('downloads',[])]
 def recipe(self,ctx,cp):recipes.execute(ctx,cp)
 def check(self,ctx,cp,a):return checks.observe(ctx,cp,a['check'])
 def judge(self,ctx,cp,a,actual,expected):
  if a['check'].get('type')=='color':
   assert len(actual['rgba'])==len(expected['rgba'])==4
   assert all(abs(x-y)<=1 for x,y in zip(actual['rgba'],expected['rgba'])),'color differs'
  else:checks.same(actual,expected)
 def restarted(self,ctx):ctx.state['page']=None
