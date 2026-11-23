"""Pinned reference recipes, using only public runtime GUI operations."""
import base64
import time

FORMAT_TITLE="Format JSON data, with proper indentation and line feeds (Ctrl+I)"

class UI:
 def __init__(self,ctx):self.ctx=ctx;self.broker=ctx.broker;self.snap=None
 def call(self,req):
  ans=self.broker.call(req)
  if isinstance(ans,dict) and 'controls' in ans:self.snap=ans
  return ans
 def snapshot(self):return self.call({'op':'snapshot'})
 def find(self,**spec):
  controls=(self.snap or self.snapshot())['controls'];matches=[]
  for c in controls:
   ok=True
   for k,v in spec.items():
    if k in ('nth','contains','prefix','near_y'):continue
    have=c.get(k,'')
    if spec.get('contains') and isinstance(have,str):ok &= str(v).lower() in have.lower()
    elif spec.get('prefix') and isinstance(have,str):ok &= have.startswith(v)
    elif k=='text' and isinstance(have,str) and isinstance(v,str):ok &= ''.join(have.split())==''.join(v.split())
    else:ok &= have==v
   if 'near_y' in spec:ok &= abs(c['bounds'][1]-spec['near_y'])<8
   if ok:matches.append(c)
  idx=spec.get('nth',0)
  assert len(matches)>idx,'no reference control '+repr(spec)
  return matches[idx]
 def act(self,op,*,value=None,**spec):
  self.snapshot();c=self.find(**spec);req={'op':op,'target':{'ref':c['ref']}}
  if value is not None:req['value']=value
  return self.call(req)
 def click(self,**spec):
  if set(spec)=={'text'}:
   self.snapshot()
   try:return self.act('click',**spec)
   except AssertionError:return self.call({'op':'click','target':{'text':spec['text']}})
  return self.act('click',**spec)
 def fill(self,value,**spec):return self.act('fill',value=value,**spec)
 def press(self,key):return self.call({'op':'press','key':key})
 def row(self,node):
  self.snapshot();return self.find(text=node,tag='div')['bounds'][1]
 def row_menu(self,node=None):
  if node is None:self.click(title='Click to open the actions menu (Ctrl+M)',nth=0)
  else:self.click(title='Click to open the actions menu (Ctrl+M)',near_y=self.row(node))
 def edit(self,node,text):
  try:
   y=self.row(node);candidates=[c for c in self.snap['controls'] if c.get('tag')=='div' and 'value' in c and abs(c['bounds'][1]-y)<6]
  except AssertionError:
   candidates=[c for c in self.snap['controls'] if c.get('tag')=='div' and 'value' in c][:1]
  assert candidates,'no editable value for '+node
  self.call({'op':'fill','target':{'ref':candidates[-1]['ref']},'value':text});self.press('Tab')

def execute(ctx,cp):
 u=UI(ctx)
 for s in cp['recipe']:
  op=s['do']
  if op=='edit':u.edit(s['node'],s['value'])
  elif op=='autocomplete':
   y=u.row(s['node']);c=[c for c in u.snap['controls'] if c.get('tag')=='div' and 'value' in c and abs(c['bounds'][1]-y)<6][-1]
   u.call({'op':'click','target':{'ref':c['ref']}});u.press('Control+A');u.call({'op':'type','value':s['token']});u.call({'op':'wait','seconds':.8});u.snapshot();options=[c for c in u.snap['controls'] if c.get('text')==s['option'] and 'value' not in c]
   if options:u.call({'op':'click','target':{'ref':options[-1]['ref']}})
   else:u.click(text=s['option'])
   u.press('Tab')
  elif op=='drag-node':
   y=u.row(s['node']);start=u.find(title='Drag to move this field (Alt+Shift+Arrows)',near_y=y)['bounds']
   ty=u.row(s['before']);end=u.find(title='Drag to move this field (Alt+Shift+Arrows)',near_y=ty)['bounds']
   u.call({'op':'drag','x':start[0]+start[2]/2,'y':start[1]+start[3]/2,'to_x':end[0]+end[2]/2,'to_y':end[1]+6,'steps':30})
  elif op=='attempt-text':
   u.call({'op':'click','target':{'text':s['text']}});u.press('Control+A');u.call({'op':'paste','value':s['value']});u.press('Tab');u.call({'op':'pointer','x':900,'y':800})
  elif op=='feature-controls':
   feature=s['feature'];title={'search':'Search fields and values','enableSort':'Sort contents','enableTransform':'Filter, sort, or transform contents'}[feature]
   snap=u.snapshot();found=[c for c in snap['controls'] if c.get('title')==title or c.get('context')==title]
   if s['enabled']:
    assert found,'expected configured facility'
    if feature=='search':u.fill('Visible',tag='input',type='text',context=title)
    else:u.click(title=title)
   else:assert not found,'disabled facility remains available'
  elif op=='wizard':
   u.click(title='Filter, sort, or transform contents')
   if s.get('filter'):
    field,relation,value=s['filter'];u.call({'op':'click','target':{'text':'field...','nth':0}});u.call({'op':'click','target':{'text':field,'nth':0}})
    u.call({'op':'click','target':{'text':'compare...'}});u.call({'op':'click','target':{'text':relation}});u.fill(value,placeholder='value...')
   if s.get('sort'):
    field,direction=s['sort'];u.call({'op':'click','target':{'text':'field...','nth':0 if s.get('filter') else 1}});u.call({'op':'click','target':{'text':field,'nth':0}})
    u.call({'op':'click','target':{'text':'order...'}});u.call({'op':'click','target':{'text':'Ascending' if direction=='asc' else 'Descending'}})
   for field in s.get('projection',[]):
    u.call({'op':'click','target':{'text':'select fields...'}});u.call({'op':'click','target':{'text':field,'nth':0}})
   u.call({'op':'wait','seconds':.5});u.click(text='Ok',tag='input');u.snapshot()
   if any(c.get('title')=='Expand all fields' for c in u.snap['controls']):u.click(title='Expand all fields')
  elif op=='rename':u.fill(s['value'],text=s['node'],tag='div');u.press('Tab')
  elif op=='click':u.click(**s['target'])
  elif op=='fill':u.fill(s['value'],**s['target'])
  elif op=='press':u.press(s['key'])
  elif op=='paste':u.call({'op':'paste','value':s['value']})
  elif op=='type':u.call({'op':'type','value':s['value']})
  elif op=='wait':u.call({'op':'wait','seconds':s.get('seconds',.5)})
  elif op=='menu':u.row_menu(s.get('node'))
  elif op=='change-type':
   u.row_menu(s.get('node'));u.click(text='Type',tag='button');u.click(text=s['type'],tag='button')
  elif op=='insert':
   if 'menu_index' in s:u.click(title='Click to open the actions menu (Ctrl+M)',nth=s['menu_index'])
   else:u.row_menu(s.get('node'))
   u.click(title='Select the type of the field to be '+('appended' if s.get('append') else 'inserted'));u.click(text=s['type'],tag='button')
   if s.get('name'):
    u.press('Control+A');u.call({'op':'paste','value':s['name']});u.press('Tab')
    if s.get('value') is not None:u.call({'op':'paste','value':s['value']});u.press('Tab')
  elif op=='mode':u.click(title='Switch Editor Mode');u.click(text=s['mode'],tag='button')
  elif op=='select':u.act('select',value=s['value'],**s['target'])
  elif op=='checkbox':
   y=u.row(s['node']);u.click(tag='input',type='checkbox',near_y=y)
  elif op=='text-edit':
   snap=u.snapshot();areas=[c for c in snap['controls'] if c['tag']=='textarea']
   if areas:u.call({'op':'click','target':{'ref':areas[-1]['ref']}})
   else:
    # The shipped Ace canvas is in the same editor rectangle as the text field.
    toolbar=[c for c in snap['controls'] if c.get('title')==FORMAT_TITLE]
    assert toolbar,'no visible text-editor toolbar'
    x,y,w,h=toolbar[0]['bounds'];u.call({'op':'pointer','x':x+180,'y':y+65})
   u.press('Control+A');u.call({'op':'paste','value':s['value']})
  elif op=='sort':
   u.click(title='Sort contents')
   if s.get('field') is not None:u.act('select',value=s['field'],title='Select the nested field by which to sort the array or object')
   u.click(title='Sort the selected field in '+s['direction']+' order');u.click(text='Ok',tag='input');u.snapshot()
   if any(c.get('title')=='Expand all fields' for c in u.snap['controls']):u.click(title='Expand all fields')
  elif op=='query':
   u.click(title='Filter, sort, or transform contents');u.fill(s['query'],title='Enter a JMESPath query');u.call({'op':'wait','seconds':.5});u.click(text='Ok',tag='input');u.snapshot()
   if any(c.get('title')=='Expand all fields' for c in u.snap['controls']):u.click(title='Expand all fields')
  elif op=='upload':
   u.snapshot()
   u.call({'op':'upload','target':{'ref':u.find(tag='input',type='file')['ref']},'filename':s.get('filename','input.json'),'mime_type':'application/json','base64':base64.b64encode(s['text'].encode()).decode()})
   u.click(title='Expand all fields')
  elif op=='dialog':u.call({'op':'dialog','dialog_action':s.get('action','accept'),'text':s.get('text','')})
  elif op=='reload':u.call({'op':'reload'})
  elif op=='color':
   y=u.row(s['node']);value=[c for c in u.snap['controls'] if 'value' in c and abs(c['bounds'][1]-y)<6][-1]
   x,y,w,h=value['bounds'];u.call({'op':'pointer','x':x-10,'y':y+h/2});u.snapshot()
   field=[c for c in u.snap['controls'] if c.get('tag')=='input' and c.get('type')=='text'][-1];u.call({'op':'fill','target':{'ref':field['ref']},'value':s['value']});u.click(text='Ok',tag='button')
  elif op=='expand-node':
   y=u.row(s['node']);u.click(title='Click to expand/collapse this field (Ctrl+E). Ctrl+Click to expand/collapse including all childs.',near_y=y)
  elif op=='expect':
   snap=u.snapshot();hay=snap['text']+'\n'+'\n'.join(c.get('text','') for c in snap['controls']);assert s['text'] in hay,'reference result not visible: '+s['text']
  else:raise ValueError('unknown reference recipe '+op)
 u.call({'op':'wait','seconds':.3})
