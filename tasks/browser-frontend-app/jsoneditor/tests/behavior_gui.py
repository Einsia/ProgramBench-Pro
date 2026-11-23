"""Functional goals for read-only boundaries, configuration and navigation."""
from specification import goal,episode,example_goal,click,press,edit,jsoncheck,MODES
from program import call

def bind(w,negatives,positive):
 for c in w['checkpoints']:
  if c['id'] in negatives:
   for a in c['assertions']:a['requires']=[w['id']+'/'+positive+'/visible',w['id']+'/'+positive+'/data-0']
 return w

def readonly():
 data={'target':'Original value','keep':7}
 attempt=[{'do':'attempt-text','text':'Original value','value':'Changed value'}]
 cps=[goal('editable','Change target to Changed value.','target displays Changed value.',data,[edit('target','Changed value')],jsoncheck({'target':'Changed value','keep':7})),
 goal('view','Try to change target to Changed value in this view-only document.','The document remains available as read-only data with target still Original value.',data,attempt,jsoncheck(data),mode='view'),
 goal('form-value','Change target to Changed value in form mode.','The form permits editing the value.',data,[edit('target','Changed value')],jsoncheck({'target':'Changed value','keep':7}),mode='form'),
 goal('form-key','Try to rename target to renamed in this form.','The form preserves the target field and its value; its structure is read-only.',data,[{'do':'attempt-text','text':'target','value':'renamed'}],jsoncheck(data),mode='form'),
 goal('form-remove','Try to remove target from this form.','The form preserves target and keep as structure is read-only.',data,[click(text='target'),press('Control+Delete')],jsoncheck(data),mode='form')]
 w=bind(episode('gui-readonly-modes','readonly',cps),['view','form-key','form-remove'],'editable')
 cps=[example_goal('editable','05_custom_fields_editable','Change the editable name value to Nora.','The name value is Nora.',[edit('name','Nora')],{'type':'json','path':['name'],'expected':'Nora'})]
 for cid,text,replacement in [('id-value','123456','999'),('id-field','_id','identifier'),('name-key','name','renamed')]:
  cps.append(example_goal(cid,'05_custom_fields_editable','Try to change the protected '+text+' to '+replacement+'.','The protected field or value remains intact and the record is visible.',[{'do':'attempt-text','text':text,'value':replacement}],jsoncheck({'_id':123456,'name':'John','age':32})))
 other=bind(episode('gui-readonly-fields','readonly',cps),['id-value','id-field','name-key'],'editable')
 other['budget']['seconds']=4500
 cps=[]
 for mode in ('text','code'):
  cps.append(goal('editable-'+mode,'Replace the document with {"changed":true}.','The editable document now contains changed: true.',{},[{'do':'text-edit','value':'{"changed":true}'}],jsoncheck({'changed':True}),mode=mode))
  cps.append(example_goal('protected-'+mode,'09_readonly_text_mode','Try replacing this read-only '+mode+' document with {"changed":true}.','The initial document remains readable and cannot be edited.',[{'do':'text-edit','value':'{"changed":true}'}],jsoncheck({'array':[1,2,3],'boolean':True,'null':None,'number':123,'object':{'a':'b','c':'d'},'string':'Hello World'}),prepare=[call('setMode',mode)]))
 text=episode('gui-readonly-text','readonly',cps)
 for c in text['checkpoints']:
  if c['id'].startswith('protected'):
   for a in c['assertions']:a['requires']=[text['id']+'/editable-'+c['id'].split('-')[1]+'/visible',text['id']+'/editable-'+c['id'].split('-')[1]+'/data-0']
 return [w,other,text]

def multiple():
 data=['A','B','C','D']
 cps=[]
 for cid,key,description in [('duplicate','Control+D','Select B and C together and duplicate them.'),('delete','Control+Delete','Select B and C together and remove them.'),('move-up','Alt+Shift+ArrowUp','Select B and C together and move them one position toward the start.'),('move-down','Alt+Shift+ArrowDown','Select B and C together and move them one position toward the end.')]:
  cps.append(goal(cid,description,'The array reflects the operation on both selected entries.',data,[click(text='B'),press('Control+Shift+ArrowDown'),press(key)],jsoncheck({'duplicate':['A','B','C','B','C','D'],'delete':['A','D'],'move-up':['B','C','A','D'],'move-down':['A','D','B','C']}[cid])))
 cps.append(goal('nested-delete','Remove B and C together from the nested items array.','items retains A and D, and keep is unchanged.',{'items':data,'keep':7},[click(text='B'),press('Control+Shift+ArrowDown'),press('Control+Delete')],jsoncheck({'items':['A','D'],'keep':7}),prepare=[call('expandAll')]))
 return [episode('gui-multi-selection','multiple-selection',cps)]

def hierarchy():
 cps=[]
 for name,data,node in [('into',{'branch':{'first':'First'},'moving':'Moving','tail':'End'},'Moving'),('out',{'branch':{'moving':'Moving','stay':'Stay'},'tail':'End'},'Moving')]:
  for limited in (False,True):
   cps.append(goal(name+'-'+str(limited).lower(),'Drag Moving '+('into branch before First.' if name=='into' else 'out of branch and before branch at the root.')+' Parent changes are '+('disabled.' if limited else 'enabled.'),'The entry '+('remains inside its original parent.' if limited else 'moves across the parent boundary.'),data,[{'do':'drag-node','node':'Moving','before':'First' if name=='into' else 'branch'},click(title='Expand all fields')],jsoncheck(data) if limited else jsoncheck({'branch':{'moving':'Moving','first':'First'},'tail':'End'} if name=='into' else {'moving':'Moving','branch':{'stay':'Stay'},'tail':'End'}),construct={'mode':'tree','limitDragging':limited},prepare=[call('expandAll')]))
 w=episode('gui-hierarchy','hierarchy',cps)
 for c in w['checkpoints']:
  if c['id'].endswith('true'):
   for a in c['assertions']:a['requires']=[w['id']+'/'+c['id'].replace('true','false')+'/data-0']
 return [w]

def search():
 data={name:{'label':'Beacon '+name,**{'padding'+str(i):name+' item '+str(i) for i in range(22)}} for name in ('north','south','west')}
 base=[{'do':'fill','target':{'tag':'input','type':'text','context':'Search fields and values'},'value':'Beacon'},{'do':'wait','seconds':.5}]
 cps=[goal('first','Search for Beacon.','Beacon north is located and highlighted in the viewport.',data,base),
 goal('next','Search for Beacon and navigate to the next matching value.','Beacon south is brought into view and highlighted.',data,base+[click(title='Next result (Enter)')]),
 goal('previous','Search for Beacon, advance twice, then go to the previous match.','Beacon south is brought back into view and highlighted.',data,base+[click(title='Next result (Enter)'),click(title='Next result (Enter)'),click(title='Previous result (Shift + Enter)')]),
 goal('wrap','Search for Beacon and go to the previous match from the first one.','Beacon west is brought into view and highlighted.',data,base+[click(title='Previous result (Shift + Enter)')]),
 goal('clear','Search for Beacon, then clear the search.','The full document is available again with no active search highlighting.',data,base+[{'do':'fill','target':{'tag':'input','type':'text','context':'Search fields and values'},'value':''}])]
 return [episode('gui-search-navigation','search-navigation',cps)]

def wizard():
 data=[{'name':'Ada','age':21,'active':True},{'name':'Bob','age':35,'active':False},{'name':'Cara','age':29,'active':True}]
 specs=[('filter','Filter the records to age greater than 25.',{'filter':('age','>','25')},data[1:]),
 ('sort','Sort records by age descending.',{'sort':('age','desc')},[data[1],data[2],data[0]]),
 ('project','Select only the name field from each record.',{'projection':['name']},['Ada','Bob','Cara']),
 ('filter-sort','Keep age greater than 25 and sort by age descending.',{'filter':('age','>','25'),'sort':('age','desc')},[data[1],data[2]]),
 ('filter-project','Keep age greater than 25 and select only name.',{'filter':('age','>','25'),'projection':['name']},['Bob','Cara']),
 ('sort-project','Sort by age descending and select only name.',{'sort':('age','desc'),'projection':['name']},['Bob','Cara','Ada']),
 ('combined','Keep age greater than 25, sort age descending and select only name.',{'filter':('age','>','25'),'sort':('age','desc'),'projection':['name']},['Bob','Cara'])]
 cps=[]
 for cid,desc,opts,expected in specs:cps.append(goal(cid,desc+' Use the transformation wizard fields; do not enter a query.','The editor shows the requested filtered, sorted or projected result.',data,[{'do':'wizard',**opts}],jsoncheck(expected)))
 return [episode('gui-transform-wizard','transform-wizard',cps)]

def configuration():
 cps=[]
 data=['A','B']
 for enabled in (True,False):
  cps.append(goal('history-'+str(enabled).lower(),'Duplicate A, then try to undo the duplication.','The array contains '+('only A and B after undo.' if enabled else 'two copies of A because product history is disabled.'),data,[click(text='A'),press('Control+D'),press('Control+Z')],jsoncheck(['A','B'] if enabled else ['A','A','B']),construct={'mode':'tree','history':enabled}))
 w=bind(episode('gui-config-history','configuration',cps),['history-false'],'history-true')
 data={'target':{'leaf':'Visible leaf'},'keep':7};cps=[]
 for opt,desc in [('search','search'),('enableSort','sort'),('enableTransform','transformation')]:
  for enabled in (True,False):
   recipe=[{'do':'feature-controls','feature':opt,'enabled':enabled}]
   cps.append(goal(opt+'-'+str(enabled).lower(),'Inspect the editor and '+('open its '+desc+' facility.' if enabled else 'confirm that its '+desc+' facility is disabled while reading the document.'),'The document remains visible and '+desc+' is '+('available.' if enabled else 'unavailable.'),data,recipe,jsoncheck(data),construct={'mode':'tree',opt:enabled}))
 controls=episode('gui-config-tools','configuration',cps)
 for c in controls['checkpoints']:
  if c['id'].endswith('false'):
   for a in c['assertions']:a['requires']=[controls['id']+'/'+c['id'].replace('false','true')+'/visible',controls['id']+'/'+c['id'].replace('false','true')+'/data-0']
 return [w,controls]


def file_errors():
 doc={'record':'Retained document','values':[3,1,4]};path='04_load_and_save'
 cps=[example_goal('load','04_load_and_save','Load the supplied file recovery.json.','The document Retained document and its values are visible.',[{'do':'upload','filename':'recovery.json','text':'{"record":"Retained document","values":[3,1,4]}'}],jsoncheck(doc)),
 example_goal('malformed',path,'Try loading the malformed file malformed.json and inspect the result.','The previous Retained document remains available after the invalid input.',[{'do':'upload','filename':'malformed.json','text':'{}{}'}],jsoncheck(doc)),
 example_goal('save',path,'Save the current document as recovery.json.','A recovery.json download is produced.',[{'do':'dialog','text':'recovery.json'},click(text='Save')],{'type':'download','expected':doc,'filename':'recovery.json'}),
 example_goal('cancel-save',path,'Start saving the current document, then cancel the filename prompt.','The Retained document stays available and saving is cancelled.',[{'do':'dialog','action':'dismiss'},click(text='Save')],{'type':'no-download','expected':doc})]
 # example_goal intentionally retains upstream initial data unless it is explicitly provided here.
 for c in cps:
  if c['id']!='load':c['data']=doc
 w=episode('gui-file-errors','files',cps);w['inputs']={'files':['recovery.json','malformed.json']}
 for c in w['checkpoints']:
  positive='load' if c['id']=='malformed' else 'save'
  if c['id'] in ('malformed','cancel-save'):
   for a in c['assertions']:a['requires']=[w['id']+'/'+positive+'/visible',w['id']+'/'+positive+'/data-0']
 return [w]


def display_configuration():
 data={'target':'Before','keep':7};cps=[]
 for option,label in [('mainMenuBar','main toolbar'),('navigationBar','breadcrumb navigation')]:
  cps.append(goal(option,'Change target to After in the editor configured without '+label+'.','target shows After while the configured '+label+' is absent.',data,[edit('target','After')],jsoncheck({'target':'After','keep':7}),construct={'mode':'tree',option:False}))
 cps.append(goal('statusBar','Replace the document with {"changed":true} in the text editor configured without a status bar.','The new text is visible without a position/status bar.',{},[{'do':'text-edit','value':'{"changed":true}'}],jsoncheck({'changed':True}),mode='text',construct={'mode':'text','statusBar':False}))
 cps.append(goal('custom-label','Open the type choices for target and inspect the custom automatic-type label.','The type choices show the configured label Detect value.',{'target':'42'},[{'do':'menu','node':'target'},click(text='Type',tag='button'),{'do':'expect','text':'Detect value'}],construct={'mode':'tree','languages':{'en':{'auto':'Detect value'}}}))
 return [episode('gui-config-display','configuration',cps)]

def gui_episodes():
 return readonly()+multiple()+hierarchy()+search()+wizard()+configuration()+file_errors()+display_configuration()
