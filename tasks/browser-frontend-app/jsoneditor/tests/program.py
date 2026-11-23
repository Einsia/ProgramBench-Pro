"""Program episodes for public data, modes, selections, schema and error paths."""
from pathlib import Path
import json

MODES=['tree','form','view','text','code','preview']

def call(method,*args,**more):return {'op':'api','method':method,'args':list(args),**more}
def assertion(wid,cid,aid,requirement,check):
 return {'id':f'{wid}/{cid}/{aid}','channel':'backend','method':'program','requirement':requirement,'check':check}
def episode(wid,feature,cps):
 return {'id':wid,'feature':feature,'execution':'program','initial_state':'Fresh upstream mode-switch example. Each checkpoint creates its own editor configuration.','setup':[{'id':'page'}],'inputs':{},'checkpoints':cps}
def cp(wid,cid,desc,options,check,data=None,prepare=()):
 return {'id':cid,'goal':desc,'construct':options,'data':data,'prepare':list(prepare),'assertions':[assertion(wid,cid,'result',desc,check)],'depends_on':['setup:page']}

def schema_episodes():
 groups=json.loads((Path(__file__).parent/'fixtures/schema-cases.json').read_text())
 families={}
 for g in groups:families.setdefault(g['file'],[]).append(g)
 result=[]
 # Keep each semantic family in its own independent episode.
 for file,gs in families.items():
  wid='schema-'+file.removesuffix('.json').replace('/','-').replace('_','-')
  checkpoints=[]
  for g in gs:
   cid='group-'+str(g['group']); assertions=[]
   positive=next((c for c in g['cases'] if c['valid']),None)
   for case in g['cases']:
    a=assertion(wid,cid,'case-'+case['id'],g['description']+'; '+case['description'],{'type':'schema','data':case['data'],'valid':case['valid']})
    if not case['valid'] and positive:a['requires']=[f'{wid}/{cid}/case-{positive["id"]}']
    assertions.append(a)
   checkpoints.append({'id':cid,'goal':g['description'],'construct':{'mode':'text','schema':g['schema']},'data':{},'assertions':assertions,'depends_on':['setup:page']})
  result.append(episode(wid,'schema-validation',checkpoints))
 return result

def data_episodes():
 result=[]
 values={
 'object':{'nested':{'alpha':[1,False,None,{'name':'café 茶'}]},'empty':{},'zero':0},
 'array':[{'k':'v'},[0,-1,3.125],None,True,'string'],
 'string':'quoted " text\\slash\nnewline\ttab café 中文 😀',
 'number':-35.125,'true':True,'false':False,'null':None,
 'empty-object':{},'empty-array':[],'empty-string':'',
 'special-keys':{'':'empty','a.b':'dot','x/y':'slash','~':'tilde','0':'zero','__proto__':'data','constructor':'data'},
 'numeric-boundaries':[0,-0.0,1e-7,1e20,9007199254740991,-9007199254740991],
 }
 for mode in MODES:
  wid='data-'+mode;cps=[]
  for name,value in values.items():
   for method in ('set','update'):
    cps.append(cp(wid,method+'-'+name,method+' replaces the document with '+name+' in '+mode+' mode.',{'mode':mode},
      {'type':'sequence','steps':[call(method,value)],'expected':{k:v for k,v in value.items() if k!='__proto__'} if name=='special-keys' and mode in ('tree','form','view') else value},{'old':'remove'}))
  result.append(episode(wid,'document-api',cps))
 wid='text-parsing';cps=[]
 valid={'spaced':' { "a" : [1, false, null] } \n','exponent':'1.25e2','escapes':'"a\\nb\\tc\\u00e9"','duplicate':'{"key":1,"key":2}','scalar':'true','unicode':'{"茶":"☕"}'}
 invalid={'trailing-comma':'{"x":1,}','missing-colon':'{"x" 1}','unquoted':'{x:1}','single-quote':"{'x':1}",'incomplete':'{"x":','comments':'/*note*/{"a":1}','two-values':'{}{}','leading-zero':'01','bad-escape':'"\\x41"','empty':''}
 for mode in MODES:
  for name,text in valid.items():
   cps.append(cp(wid,mode+'-'+name,'Parse '+name+' JSON in '+mode,{'mode':mode},{'type':'sequence','steps':[call('setText',text)],'expected':json.loads(text)},{}))
  for name,text in invalid.items():
   check={'type':'parse','text':text}
   cps.append(cp(wid,mode+'-invalid-'+name,'Invalid JSON '+name+' in '+mode,{'mode':mode},check,{}))
 result.append(episode(wid,'text-api',cps))
 wid='mode-transitions';cps=[]
 for a in MODES:
  for b in MODES:
   if a==b:continue
   data={'payload':[None,False,123,'茶',{'nested':True}]}
   cps.append(cp(wid,a+'-to-'+b,'Keep JSON content when switching '+a+' to '+b,{'mode':a},{'type':'sequence','steps':[call('setMode',b)],'expected':data,'mode':b},data))
 for mode in ['bogus','TREE','','json']:
  cps.append(cp(wid,'invalid-'+(mode or 'empty'),'Reject unsupported mode '+repr(mode),{'mode':'tree'},{'type':'error','method':'setMode','args':[mode]},{'x':1}))
 result.append(episode(wid,'mode-api',cps))
 wid='text-selection';cps=[]
 text='{\n  "one": 1,\n  "two": "second"\n}'
 selections=[('key',{'row':2,'column':4},{'row':2,'column':7}),('multi-line',{'row':2,'column':1},{'row':3,'column':7}),('empty',{'row':1,'column':1},{'row':1,'column':1}),('last',{'row':4,'column':1},{'row':4,'column':2})]
 for mode in ['text','code']:
  for name,start,end in selections:
   cps.append(cp(wid,mode+'-'+name,'Text selection '+name+' in '+mode,{'mode':mode},{'type':'sequence','steps':[call('setTextSelection',start,end)],'read':'getTextSelection'},None,[call('setText',text)]))
 result.append(episode(wid,'selection-api',cps))
 wid='tree-selection';cps=[];data={'first':{'inner':[10,20]},'second':[1,2],'third':'last'}
 for name,args in [('single',[{'path':['second']}]),('siblings',[{'path':['first']},{'path':['third']}]),('nested',[{'path':['first','inner',0]},{'path':['first','inner',1]}]),('different-levels',[{'path':['first','inner',0]},{'path':['second']}]),('clear',[])]:
  cps.append(cp(wid,name,'Tree selection '+name,{'mode':'tree'},{'type':'sequence','steps':[call('setSelection',*args)],'read':'getSelection'},data,[call('expandAll')]+([call('setSelection',{'path':['second']})] if name=='clear' else [])))
 result.append(episode(wid,'selection-api',cps))
 return result


def api_options():
 result=[];wid='api-root-name';cps=[]
 for mode in ['tree','form','view']:
  for name in ['Document','Root 茶','']:
   cid=mode+'-'+('empty' if not name else 'unicode' if '茶' in name else 'word')
   cps.append(cp(wid,cid,'Set the root field name in '+mode,{'mode':mode},{'type':'sequence','steps':[call('setName',name)],'read':'getName','expected':name},{'x':1}))
 result.append(episode(wid,'document-api',cps))
 wid='api-update-text';cps=[]
 text=' { "items": [1, 2], "name":"updated" } '
 for mode in MODES:
  cps.append(cp(wid,mode,'updateText replaces changed contents in '+mode,{'mode':mode},{'type':'sequence','steps':[call('updateText',text)],'expected':json.loads(text)},{'old':True}))
  cps.append(cp(wid,mode+'-raw','getText returns the representation in '+mode,{'mode':mode},{'type':'sequence','steps':[call('updateText',text)],'read':'getText','parse_text':mode in ('tree','form','view')},{}))
 result.append(episode(wid,'text-api',cps))
 wid='api-schema-state';cps=[]
 for mode in MODES:
  schema={'type':'object','properties':{'count':{'type':'integer','minimum':2}},'required':['count']}
  cps.append(cp(wid,mode+'-invalid','Configured schema rejects an out-of-range value in '+mode,{'mode':mode,'schema':schema},{'type':'valid'},{'count':1}))
  cps.append(cp(wid,mode+'-replace','Replacing schema changes validation in '+mode,{'mode':mode,'schema':schema},{'type':'sequence','steps':[call('setSchema',{'type':'object','properties':{'count':{'maximum':1}}})],'read':'validate','expected':[]},{'count':1}))
  cps.append(cp(wid,mode+'-disable','Disable an active schema in '+mode,{'mode':mode,'schema':schema},{'type':'sequence','steps':[call('setSchema',None)],'read':'validate','expected':[]},{'count':1}))
  refs={'record':{'type':'object','properties':{'name':{'type':'string'}},'required':['name']}}
  cps.append(cp(wid,mode+'-refs','Resolve a named schema reference in '+mode,{'mode':mode,'schema':{'$ref':'record'},'schemaRefs':refs},{'type':'valid'},{'name':False}))
 result.append(episode(wid,'schema-validation',cps))
 wid='api-range';cps=[];data={'first':1,'second':{'nested':2},'third':3}
 for name,a,b in [('same',['second'],['second']),('forward',['first'],['third']),('reverse',['third'],['first'])]:
  cps.append(cp(wid,name,'Read the selected node range '+name,{'mode':'tree'},{'type':'sequence','steps':[],'read':'getNodesByRange','read_args':[{'path':a},{'path':b}]},data,[call('expandAll')]))
 result.append(episode(wid,'selection-api',cps))
 return result

def build():
 episodes=schema_episodes()+data_episodes()+api_options()
 for w in episodes:
  for c in w['checkpoints']:
   if (w['id'] in ('data-tree','data-form','data-view') and c['id'].startswith('update-')) or (w['id']=='api-update-text' and c['id'].split('-')[0] in ('tree','form','view')):
    c['assertions'][0]['check']['retain_state']='updateText' if w['id']=='api-update-text' else 'update'
 from behavior import program_episodes
 return episodes+program_episodes()
