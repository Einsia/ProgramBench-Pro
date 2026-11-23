"""Public API behavior beyond document replacement: state, options and diagnostics."""
import json
import re
import checks
from program import cp,episode,call,MODES

TREE={'branch':{'deep':{'leaf':'Deep marker'},'side':'Side marker'},'tail':'Tail marker'}

def paths(text):
 if isinstance(text,list):return text
 if not text:return []
 if text.startswith('/'):
  return [int(t) if t.isdigit() else t for t in (x.replace('~1','/').replace('~0','~') for x in text[1:].split('/'))]
 out=[]
 for m in re.finditer(r'\.([^.[\]]+)|\[([0-9]+)\]|\[([\'\"])(.*?)\3\]',text):
  if m.group(1) is not None:out.append(m.group(1))
  elif m.group(2) is not None:out.append(int(m.group(2)))
  else:out.append(m.group(4).replace('\\\'','\'').replace('\\"','"').replace('\\\\','\\'))
 return out

def errors(raw):
 assert isinstance(raw,list),'validate returned no array'
 out=[]
 for item in raw:
  assert isinstance(item,dict) and isinstance(item.get('error'),dict),'invalid validation error'
  e=item['error'];path=e.get('path',e.get('instancePath',e.get('dataPath','')))
  out.append({'type':item.get('type'),'path':paths(path),'keyword':e.get('keyword')})
 return sorted(out,key=lambda v:json.dumps(v,sort_keys=True))

def observe(ctx,checkpoint,spec):
 kind=spec['type']
 if kind=='retain':
  method=spec['method'];after={'branch':{'leaf':'New marker'},'keep':4}
  checks.api(ctx,method,json.dumps(after) if method.endswith('Text') else after)
  data=checks.value(ctx);checks.same(data,after)
  visible='New marker' in checks.visible_text(ctx)
  assert visible is spec['expanded'],'branch expansion state differs'
  return {'data':data,'expanded':visible}
 if kind=='expand':
  checks.execute(ctx,spec['steps'])
  text=checks.visible_text(ctx)
  actual={marker:marker in text for marker in ['Deep marker','Side marker','Tail marker']}
  checks.same(actual,spec['visible']);return actual
 if kind=='root-name-clear':
  checks.same(checks.value(ctx,'getName'),'Named document')
  checks.api(ctx,'setName');result=checks.api(ctx,'getName')
  assert result.get('undefined') is True,'root name was not cleared'
  return {'cleared':True,'data':checks.value(ctx)}
 if kind=='indentation':
  text=checks.value(ctx,'getText');data=json.loads(text);checks.same(data,checkpoint['data'])
  width=spec['spaces'];lines=text.splitlines()
  if width==0:assert len(lines)==1,'zero indentation should produce one line'
  else:
   assert len(lines)>1,'expected multiple lines'
   assert any(line.startswith(' '*width+'"outer"') for line in lines),'configured indentation ignored'
  return {'spaces':width,'data':data}
 if kind=='constructor':
  actual=checks.value(ctx);return {'data':actual,'mode':checks.value(ctx,'getMode')}
 if kind=='validation-detail':
  result=errors(checks.value(ctx,'validate'))
  assert result,'expected specific validation errors'
  if 'keywords' in spec:assert set(x['keyword'] for x in result)==set(spec['keywords']),'validation keywords differ'
  return {'errors':result}
 if kind=='ui-state':
  snap=ctx.broker.call({'op':'snapshot'})
  texts='\n'.join([snap.get('text','')]+[str(c.get(k,'')) for c in snap.get('controls',[]) for k in ('text','value')])
  return {'visible':{text:text in texts for text in spec['texts']},'data':checks.value(ctx)}
 raise ValueError(kind)

def program_episodes():
 result=[];wid='api-set-reset-state';cps=[]
 for mode in ('tree','form','view'):
  for method in ('set','setText'):
   cps.append(cp(wid,mode+'-'+method,'Replacing a document resets expanded branches in '+mode,{'mode':mode},{'type':'retain','method':method,'expanded':False},{'branch':{'leaf':'Old marker'},'keep':3},[call('expandAll')]))
 result.append(episode(wid,'state-preservation',cps))
 wid='api-expand-options';cps=[]
 variants=[
 ('shallow',[call('expand',{'path':['branch'],'isExpand':True,'recursive':False})],False,True),
 ('recursive',[call('expand',{'path':['branch'],'isExpand':True,'recursive':True})],True,True),
 ('with-path',[call('expand',{'path':['branch','deep'],'isExpand':True,'withPath':True})],True,True),
 ('without-path',[call('expand',{'path':['branch','deep'],'isExpand':True,'withPath':False})],False,False),
 ('collapse-recursive',[call('expandAll'),call('expand',{'path':['branch'],'isExpand':False,'recursive':True})],False,False),
 ('collapse-keep-child',[call('expandAll'),call('expand',{'path':['branch'],'isExpand':False}),call('expand',{'path':['branch'],'isExpand':True})],True,True)]
 for mode in ('tree','form','view'):
  for name,steps,deep,side in variants:
   cps.append(cp(wid,mode+'-'+name,'Expand path options '+name+' in '+mode,{'mode':mode},{'type':'expand','steps':steps,'visible':{'Deep marker':deep,'Side marker':side,'Tail marker':True}},TREE))
 result.append(episode(wid,'expansion-api',cps))
 wid='api-name-clear';cps=[]
 for mode in ('tree','form','view'):
  cps.append(cp(wid,mode,'Remove an existing root name with no arguments in '+mode,{'mode':mode,'name':'Named document'},{'type':'root-name-clear'},{'value':9}))
 result.append(episode(wid,'document-api',cps))
 wid='api-config-format';cps=[]
 for mode in ('text','code','preview'):
  for spaces in (0,4,8):
   cps.append(cp(wid,mode+'-'+str(spaces),'Apply explicit indentation '+str(spaces)+' in '+mode,{'mode':mode,'indentation':spaces},{'type':'indentation','spaces':spaces},{'outer':{'inner':[1,2]}}))
 for mode in ('tree','form','view'):
  cps.append(cp(wid,mode+'-natural-sort','Natural key sorting in '+mode,{'mode':mode,'sortObjectKeys':True},{'type':'object-order','expected_keys':['key1','key2','key10'],'expected':{'key10':10,'key2':2,'key1':1}},{'key10':10,'key2':2,'key1':1},[call('setText','{"key10":10,"key2":2,"key1":1}')]))
 result.append(episode(wid,'configuration',cps))
 wid='api-constructor-roots';cps=[]
 roots={'false':False,'zero':0,'empty-string':'','null':None,'true':True,'number':7,'text':'Root value','array':[3,1],'object':{'x':2}}
 for mode in MODES:
  for name,data in roots.items():cps.append(cp(wid,mode+'-'+name,'Constructor initial '+name+' root in '+mode,{'mode':mode},{'type':'constructor'},data))
 result.append(episode(wid,'constructor-api',cps))
 wid='validation-locations';cps=[]
 variants=[
 ('type',{'type':'integer'},'bad','type'),('minimum',{'type':'number','minimum':10},3,'minimum'),
 ('pattern',{'type':'string','pattern':'^[A-Z]+$'},'bad','pattern'),('length',{'type':'string','minLength':4},'a','minLength'),
 ('enum',{'enum':['red','blue']},'green','enum'),('items',{'type':'array','items':{'type':'integer'}},[1,'bad'],'type'),
 ('required',{'type':'object','required':['name']},{},'required'),('additional',{'type':'object','additionalProperties':False},{'extra':1},'additionalProperties'),
 ('unique',{'type':'array','uniqueItems':True},[1,1],'uniqueItems'),('not',{'not':{'type':'number'}},3,'not')]
 for mode in ('tree','text','code','preview'):
  for name,schema,data,keyword in variants:
   whole={'type':'object','properties':{'record':{'type':'object','properties':{'payload':schema}}}}
   cps.append(cp(wid,mode+'-'+name,'Report '+name+' violation at its nested path in '+mode,{'mode':mode,'schema':whole},{'type':'validation-detail','keywords':[keyword]},{'record':{'payload':data}}))
 result.append(episode(wid,'validation-diagnostics',cps))
 wid='custom-validation-locations';cps=[]
 cases=[('team-count','18_custom_validation',{'team':[{'name':'Joe','age':21}]}),('team-name','18_custom_validation',{'team':[{'name':3,'age':21},{'name':'A','age':20},{'name':'B','age':20},{'name':'C','age':20}]}),('team-age','18_custom_validation',{'team':[{'name':'A','age':'21'},{'name':'B','age':20},{'name':'C','age':20},{'name':'D','age':20}]}),('customer','19_custom_validation_async',{'customers':[{'name':'Joe'},{'name':'Unknown'}]})]
 for name,page,data in cases:
  cps.append({'id':name,'goal':'Locate '+name+' custom validation error','page':'/examples/'+page+'.html','data':data,'prepare':[call('expandAll')],'assertions':[{'id':wid+'/'+name+'/result','channel':'backend','method':'program','requirement':'Validation identifies the offending path and custom error type.','check':{'type':'validation-detail'}}],'depends_on':['setup:page']})
 result.append(episode(wid,'validation-diagnostics',cps))
 return result
