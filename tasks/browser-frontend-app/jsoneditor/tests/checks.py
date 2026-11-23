"""Behavioral projections of public JSONEditor results, through the runtime only."""
import base64
import json
import math
import re

def api(ctx,method,*args,editor='editor',allow_error=False):
 result=ctx.broker.call({'op':'api','editor':editor,'method':method,'args':list(args)})
 assert isinstance(result,dict) and type(result.get('ok')) is bool, 'API returned no explicit success status'
 if not allow_error: assert result['ok'], str(result.get('error'))
 return result

def value(ctx,method='get',*args,editor='editor'):
 result=api(ctx,method,*args,editor=editor)
 assert 'result' in result,'API result missing'
 return result['result']

def same(actual,expected,path='result'):
 if isinstance(expected,bool) or expected is None:
  assert type(actual) is type(expected) and actual==expected,path+' type/value differs'
 elif isinstance(expected,(int,float)):
  assert not isinstance(actual,bool) and isinstance(actual,(int,float)) and math.isfinite(actual),path+' is not numeric'
  if isinstance(expected,int) or (isinstance(expected,float) and expected.is_integer()):
   assert actual==expected,path+' integer differs'
  else:
   assert math.isclose(actual,expected,rel_tol=1e-12,abs_tol=1e-12),path+' differs'
 elif isinstance(expected,str): assert isinstance(actual,str) and actual==expected,path+' differs'
 elif isinstance(expected,list):
  assert isinstance(actual,list) and len(actual)==len(expected),path+' length differs'
  for i,(a,b) in enumerate(zip(actual,expected)):same(a,b,path+f'[{i}]')
 elif isinstance(expected,dict):
  assert isinstance(actual,dict) and set(actual)==set(expected),path+' object keys differ'
  for k,v in expected.items():same(actual[k],v,path+'.'+k)
 else: raise AssertionError('unsupported expected data')

def execute(ctx,steps):
 replies=[]
 for step in steps:
  if step['op']=='api':
   result=api(ctx,step['method'],*step.get('args',[]),editor=step.get('editor','editor'),allow_error=step.get('allow_error',False))
   replies.append(result)
  else: replies.append(ctx.broker.call(step))
 return replies

def observe(ctx,cp,spec):
 kind=spec.get('type','json')
 if kind=='schema':
  api(ctx,'set',spec['data'])
  errors=value(ctx,'validate')
  assert isinstance(errors,list),'validate did not return an array'
  observed={'valid':not errors}
  if ctx.record:assert observed['valid']==spec['valid'],'reference validation disagrees with reviewed case'
  return observed
 if kind=='sequence':
  replies=execute(ctx,spec['steps'])
  method=spec.get('read','get')
  result=value(ctx,method,*spec.get('read_args',[]))
  if spec.get('parse_text'):
   assert isinstance(result,str),'expected textual JSON';result=json.loads(result)
  if method in ('getSelection','getTextSelection','getNodesByRange'):result=public_selection(result,method)
  if 'expected' in spec:same(result,spec['expected'])
  observation={'value':result}
  if 'mode' in spec:
   observed_mode=value(ctx,'getMode');assert observed_mode==spec['mode'],'mode transition did not occur'
   observation['mode']=observed_mode
  if spec.get('retain_state'):
   observation['retained']=retention(ctx,spec['retain_state'])
  return observation
 if kind=='parse':
  first=api(ctx,'setText',spec['text'],allow_error=True)
  if not first['ok']:return {'accepted':False}
  result=api(ctx,'get',allow_error=True)
  if not result['ok']:return {'accepted':False}
  assert 'result' in result,'parse result absent'
  return {'accepted':True,'value':result['result']}
 if kind=='error':
  result=api(ctx,spec['method'],*spec.get('args',[]),allow_error=True)
  assert not result['ok'] and isinstance(result.get('error'),dict),'expected product API error'
  return {'rejected':True}
 if kind=='json':
  result=value(ctx,editor=spec.get('editor','editor'))
  for part in spec.get('path',[]):
   assert isinstance(result,(dict,list)),'missing result path';result=result[part]
  if 'expected' in spec:same(result,spec['expected'])
  return {'value':result}
 if kind=='template':
  data=value(ctx);assert isinstance(data,list) and len(data)==2,'expected original item and one template'
  key=lambda item:json.dumps(item,ensure_ascii=True,sort_keys=True,separators=(',',':'))
  expected=[{'firstName':'John','lastName':'Doe','age':28},spec['template']]
  assert sorted(map(key,data))==sorted(map(key,expected)),'template content or original item differs'
  return {'items':sorted(data,key=key)}
 if kind=='copy-field':
  data=value(ctx);original=spec['original']
  assert isinstance(data,dict),'expected an object'
  for key,val in original.items():
   assert key in data,'original field missing';same(data[key],val)
  added=[key for key in data if key not in original]
  assert len(added)==1,'expected exactly one new duplicate field'
  same(data[added[0]],original[spec['field']])
  return {'copy':data[added[0]]}
 if kind=='color':
  data=value(ctx);assert isinstance(data,dict) and 'color' in data,'color value missing'
  rgba=color(data['color'])
  if 'expected' in spec:assert all(abs(x-y)<=1 for x,y in zip(rgba,spec['expected'])),'requested color was not applied'
  return {'rgba':rgba}
 if kind=='object-order':
  text=value(ctx,'getText');data=json.loads(text)
  assert isinstance(data,dict),'expected object'
  if 'expected_keys' in spec:same(list(data),spec['expected_keys'])
  if 'expected' in spec:same(data,spec['expected'])
  return {'keys':list(data),'data':data}
 if kind=='text':
  result=value(ctx,'getText')
  assert isinstance(result,str),'getText did not return text'
  if spec.get('style')=='compact':
   parsed=json.loads(result);assert not whitespace_outside_strings(result),'not compact'
   return {'data':parsed,'compact':True}
  if spec.get('style')=='formatted':
   parsed=json.loads(result);assert '\n' in result and any(re.match(r'^[ \t]+\S',line) for line in result.splitlines()),'not indented'
   return {'data':parsed,'formatted':True}
  if 'expected' in spec:same(result,spec['expected'])
  return {'text':result}
 if kind=='method':
  return {'value':value(ctx,spec['method'],*spec.get('args',[]),editor=spec.get('editor','editor'))}
 if kind=='valid':
  errors=value(ctx,'validate');assert isinstance(errors,list),'validate did not return array'
  return {'valid':not errors}
 if kind=='no-download':
  data=value(ctx);same(data,spec['expected'])
  downloads=[d['ref'] for d in ctx.broker.call({'op':'snapshot'}).get('downloads',[])]
  assert downloads==ctx.state.get('before_downloads',[]),'cancelled save produced a new download'
  return {'data':data,'downloaded':False}
 if kind=='download':
  files=ctx.broker.call({'op':'snapshot'}).get('downloads',[])
  assert files,'no JSON download'
  d=ctx.broker.call({'op':'download','ref':files[-1]['ref']})
  assert not d.get('truncated'),'download is truncated'
  result=json.loads(base64.b64decode(d['body_base64']))
  if 'expected' in spec:same(result,spec['expected'])
  out={'data':result}
  if 'filename' in spec:
   assert d.get('filename')==spec['filename'],'download filename differs'
   out['filename']=d['filename']
  return out
 if kind in ('retain','expand','root-name-clear','indentation','validation-detail','constructor','ui-state'):
  from behavior import observe
  return observe(ctx,cp,spec)
 raise ValueError('unknown check '+kind)


def whitespace_outside_strings(text):
 quoted=escaped=False
 for ch in text:
  if quoted:
   if escaped:escaped=False
   elif ch=='\\':escaped=True
   elif ch=='"':quoted=False
  elif ch=='"':quoted=True
  elif ch.isspace():return True
 return False

def public_selection(value,method):
 def node(n):
  assert isinstance(n,dict),'selection node must be an object'
  return {k:n[k] for k in ('path','value') if k in n}
 def position(n):
  assert isinstance(n,dict),'selection position must be an object'
  return {k:n[k] for k in ('row','column') if k in n}
 if method=='getNodesByRange':
  assert isinstance(value,list),'node range must be an array'
  return [node(n) for n in value]
 assert isinstance(value,dict),'selection must be an object'
 out={}
 for k in ('start','end'):
  if k in value:out[k]=None if value[k] is None else (position(value[k]) if method=='getTextSelection' else node(value[k]))
 if method=='getTextSelection' and 'text' in value:out['text']=value['text']
 return out

def color(text):
 assert isinstance(text,str),'color must be text'
 t=text.strip().lower()
 t={'red':'#ff0000','green':'#008000','blue':'#0000ff','black':'#000000','white':'#ffffff','transparent':'#00000000'}.get(t,t)
 if re.fullmatch(r'#[0-9a-f]{3,4}',t):t='#'+''.join(c*2 for c in t[1:])
 if re.fullmatch(r'#[0-9a-f]{6}(?:[0-9a-f]{2})?',t):
  values=[int(t[i:i+2],16) for i in range(1,len(t),2)]
  return values+[255] if len(values)==3 else values
 match=re.fullmatch(r'rgba?\(([^)]+)\)',t)
 assert match,'unrecognized color value'
 parts=re.split(r'[, /]+',match.group(1).strip())
 assert len(parts) in (3,4),'invalid color channel count'
 values=[round(float(x[:-1])*255/100) if x.endswith('%') else round(float(x)) for x in parts[:3]]
 alpha=parts[3] if len(parts)==4 else '1'
 values.append(round(float(alpha[:-1])*255/100) if alpha.endswith('%') else round(float(alpha)*255))
 assert all(0<=x<=255 for x in values),'invalid color channel'
 return values


def visible_text(ctx):
 snap=ctx.broker.call({'op':'snapshot'})
 return '\n'.join([snap.get('text','')]+[str(c.get(k,'')) for c in snap.get('controls',[]) for k in ('text','value')])

def retention(ctx,method):
 mode=value(ctx,'getMode')
 before={'branch':{'leaf':'Original leaf'},'keep':3}
 after={'branch':{'leaf':'Updated leaf'},'keep':4}
 api(ctx,'set',before);api(ctx,'expand',{'path':['branch'],'isExpand':True,'recursive':True})
 if mode=='tree':api(ctx,'setSelection',{'path':['branch','leaf']})
 api(ctx,method,json.dumps(after) if method.endswith('Text') else after)
 result=value(ctx);same(result,after)
 expanded='Updated leaf' in visible_text(ctx);assert expanded,'update collapsed the previously expanded branch'
 out={'data':result,'expanded':expanded}
 if mode=='tree':
  sel=public_selection(value(ctx,'getSelection'),'getSelection')
  expected={'path':['branch','leaf'],'value':'Updated leaf'}
  same(sel.get('start'),expected);same(sel.get('end'),expected);out['selection']=sel
 return out
