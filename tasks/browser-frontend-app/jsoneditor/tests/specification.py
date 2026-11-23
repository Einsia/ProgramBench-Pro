"""Functional GUI goals for the shipped editor and examples."""
import json
from program import call

MODES=['code','form','text','tree','view','preview']
FORMAT='Format JSON data, with proper indentation and line feeds (Ctrl+I)'
COMPACT='Compact JSON data, remove all whitespaces (Ctrl+Shift+I)'
REPAIR='Repair JSON: fix quotes and escape characters, remove comments and JSONP notation, turn JavaScript objects into JSON.'

def click(**target):return {'do':'click','target':target}
def press(key):return {'do':'press','key':key}
def edit(node,value):return {'do':'edit','node':node,'value':str(value)}
def jsoncheck(expected=None,path=None):
 result={'type':'json'}
 if expected is not None:result['expected']=expected
 if path:result['path']=path
 return result

def goal(cid,description,acceptance,data,recipe,check=None,mode='tree',**extra):
 out={'id':cid,'goal':description,'acceptance':acceptance,'data':data,'construct':{'mode':mode,'modes':MODES},'recipe':recipe,'checks':[] if check is None else [check]}
 out.update(extra);return out

def episode(wid,feature,cps):
 result=[]
 for c in cps:
  c=dict(c);acceptance=c.pop('acceptance');checks=c.pop('checks')
  assertions=[{'id':f'{wid}/{c["id"]}/visible','channel':'frontend','method':'agent','requirement':acceptance}]
  for i,check in enumerate(checks):assertions.append({'id':f'{wid}/{c["id"]}/data-{i}','channel':'backend','method':'program','requirement':'The public editor output reflects the requested change.','check':check})
  result.append({**c,'assertions':assertions,'depends_on':['setup:page']})
 n=len(result)
 return {'id':wid,'feature':feature,'execution':'gui','initial_state':'Each checkpoint starts on its stated upstream example with the described JSON prepared.','setup':[{'id':'page'}],'inputs':{},'session':'Each goal starts from the prepared document and mode shown. Complete the goal using the editor controls and keyboard.','allowed_equivalents':['Any visible route implementing the requested operation is valid; labels, icons, layout and dialog design may differ.'],'forbidden_bypasses':['Do not rewrite the entire document to simulate a missing operation. Use text editing only when requested.'],'budget':{'calls':40+40*n,'tokens':500000+600000*n,'seconds':300+300*n},'checkpoints':result}

def scalar_edits():
 specs=[('string','Oslo','Bergen','Bergen'),('unicode','Hello','你好 café 😀','你好 café 😀'),('number',12,'34',34),('negative',5,'-8',-8),('fraction',1,'3.125',3.125),('exponent',2,'2e3',2000),('zero',9,'0',0),('true',False,'true',True),('false',True,'false',False),('null',8,'null',None),('empty','keep','', ''),('whitespace','x','two words','two words'),('literal-number','0042','0043','0043'),('multiline','one','first\nsecond','first\nsecond')]
 result=[]
 for mode in ['tree','form']:
  cps=[]
  for cid,before,typed,after in specs:
   if mode=='form' and cid in ['exponent','literal-number','multiline']:continue
   data={'target':before,'keep':'unchanged'};expected={'target':after,'keep':'unchanged'}
   cps.append(goal(cid,'In '+mode+' mode, change the value of target to the following text:\n```\n'+typed+'\n```','target visibly shows the new value.',data,[edit('target',typed)],jsoncheck(expected),mode=mode))
  result.append(episode('gui-values-'+mode,'editing-values',cps))
 # Renaming tests field syntax, escaping and collision independently of value editing.
 cps=[]
 for cid,name in [('word','destination'),('space','full name'),('unicode','城市'),('dot','a.b'),('slash','a/b'),('empty',''),('quotes','say "hi"')]:
  cps.append(goal(cid,'Rename field target to '+json.dumps(name,ensure_ascii=False)+'.','The renamed field is visible with its original value.',{'target':42,'keep':'fixed'},[{'do':'rename','node':'target','value':name}],jsoncheck({name:42,'keep':'fixed'})))
 result.append(episode('gui-field-names','editing-fields',cps));return result

def structure():
 cps=[]
 for cid,data,node in [('scalar',{'target':'copy me','keep':'fixed'},'target'),('object',{'target':{'x':7,'y':'nested'},'keep':0},'target'),('array',{'target':[1,2,3],'keep':0},'target'),('array-item',['copy me','keep'],'copy me')]:
  recipe=[{'do':'menu','node':node},click(text='Duplicate',tag='button')]
  cps.append(goal('duplicate-'+cid,'Duplicate '+('the first array item' if cid=='array-item' else 'field target')+'.','A second copy of the selected content appears.',data,recipe,jsoncheck()))
 for cid,value in [('string','remove me'),('number',45),('object',{'x':1}),('array',[1,2])]:
  data={'target':value,'keep':'remain'}
  cps.append(goal('remove-'+cid,'Remove field target.','target is removed and keep remains visible.',data,[{'do':'menu','node':'target'},click(text='Remove',tag='button')],jsoncheck({'keep':'remain'})))
 cps.append(goal('extract-object','Extract the object in target so it becomes the root document.','The document root now contains x and y.',{'target':{'x':1,'y':2},'keep':3},[{'do':'menu','node':'target'},click(text='Extract',tag='button')],jsoncheck({'x':1,'y':2})))
 cps.append(goal('extract-array','Extract the array in target so it becomes the root document.','The document root is the array [1,2,3].',{'target':[1,2,3],'keep':3},[{'do':'menu','node':'target'},click(text='Extract',tag='button')],jsoncheck([1,2,3])))
 return [episode('gui-structure','structure',cps)]

def types():
 specs=[('number-string',42,'String'),('boolean-string',True,'String'),('null-string',None,'String'),('object-array',{'a':1,'b':2},'Array'),('array-object',['x','y'],'Object'),('string-auto-number','42','Auto'),('string-auto-bool','false','Auto'),('string-auto-null','null','Auto'),('empty-object','x','Object'),('empty-array','x','Array'),('object-string',{'a':1},'String'),('array-string',[1,2],'String')]
 cps=[]
 for cid,val,typ in specs:
  cps.append(goal(cid,'Change the type of target to '+typ+'.','target is displayed in the requested type.',{'target':val,'keep':7},[{'do':'change-type','node':'target','type':typ}],jsoncheck()))
 return [episode('gui-types','value-types',cps)]

def mode_goals():
 cps=[]
 for source,target in [('tree','text'),('tree','code'),('tree','form'),('tree','view'),('tree','preview'),('text','tree'),('code','tree'),('form','code'),('view','text'),('preview','tree')]:
  data={'name':'Harbor','items':[1,True,None]}
  cps.append(goal(source+'-'+target,'Switch from '+source+' mode to '+target+' mode.','The document is visibly available in '+target+' mode.',data,[{'do':'mode','mode':target.title()}],jsoncheck(data),mode=source))
 return [episode('gui-modes','modes',cps)]

def text_tools():
 result=[]
 broken=[('single-quotes',"{'name':'Ada','age':23}"),('bare-keys','{name:"Ada",age:23}'),('trailing-comma','{"name":"Ada","age":23,}'),('comments','{/*note*/"name":"Ada",// age\n"age":23}'),('jsonp','callback({"name":"Ada","age":23})'),('python','{"active":True,"other":None}'),('missing-comma','{"a":1 "b":2}'),('unclosed','{"a": [1,2]'),('markdown','```json\n{"a":1}\n```'),('newline-list','{"a":1}\n{"a":2}')]
 for mode in ['text','code','preview']:
  cps=[];data={'name':'Harbor','items':[1,True,None]}
  cps.append(goal('format','Format the JSON document with indentation and line breaks.','The JSON is laid out over indented lines.',data,[click(title=FORMAT)],{'type':'text','style':'formatted'},mode=mode,text=json.dumps(data,separators=(',',':'))))
  cps.append(goal('compact','Compact the JSON document.','The JSON is compacted onto one line.',data,[click(title=COMPACT)],{'type':'text','style':'compact'},mode=mode))
  for cid,text in broken:
   cps.append(goal('repair-'+cid,'Repair the current malformed JSON using the editor repair operation.','The repaired document is valid JSON and is visible.',{},[click(title=REPAIR)],{'type':'json'},mode=mode,text=text))
  if mode!='preview':
   for cid,text in [('replace','{"name":"New","items":[1,2]}'),('array','["north","south"]'),('unicode','{"城市":"杭州","text":"café"}')]:
    cps.append(goal('edit-'+cid,'Replace the text document with:\n```json\n'+text+'\n```','The text editor shows the supplied JSON.',{},[{'do':'text-edit','value':text}],jsoncheck(json.loads(text)),mode=mode))
  result.append(episode('gui-text-'+mode,'text-tools',cps))
 return result

def sorting():
 specs=[('numbers',[10,2,1,-1,3.5],'ascending',None),('numbers-desc',[10,2,1,-1,3.5],'descending',None),('strings',['Beta','Alpha','Gamma'],'ascending',None),('strings-desc',['Beta','Alpha','Gamma'],'descending',None),('object',{'z':1,'b':2,'a':3},'ascending',None),('object-desc',{'z':1,'b':2,'a':3},'descending',None),('field-age',[{'name':'Z','age':18},{'name':'A','age':42},{'name':'B','age':31}],'ascending','.age'),('field-name',[{'name':'Z','age':18},{'name':'A','age':42},{'name':'B','age':31}],'ascending','.name'),('field-desc',[{'name':'Z','age':18},{'name':'A','age':42},{'name':'B','age':31}],'descending','.age'),('nested',[{'info':{'n':3}},{'info':{'n':1}},{'info':{'n':2}}],'ascending','.info.n')]
 cps=[]
 for cid,data,direction,field in specs:
  cps.append(goal(cid,'Sort the document '+('by '+field[1:]+' ' if field else '')+'in '+direction+' order.','The entries appear in the requested order.',data,[{'do':'sort','direction':direction,'field':field}],jsoncheck()))
 return [episode('gui-sorting','sort',cps)]

def transform():
 data=[{'name':'Ada','age':21,'active':True,'tags':['red','blue']},{'name':'Bob','age':35,'active':False,'tags':['green']},{'name':'Cara','age':29,'active':True,'tags':['blue']}]
 queries=[('project','[*].name'),('filter-number','[?age > `25`]'),('filter-boolean','[?active == `true`]'),('sort','sort_by(@, &age)'),('reverse','reverse(@)'),('length','length(@)'),('nested','[*].tags[]'),('map','[*].{person: name, years: age}'),('first','[0]'),('slice','[1:3]'),('min','min_by(@, &age)'),('max','max_by(@, &age)'),('sum','sum([*].age)'),('contains',"[?contains(tags, 'blue')].name"),('join',"join(', ', [*].name)"),('filter-string',"[?name != 'Bob']")]
 cps=[]
 for cid,q in queries:
  cps.append(goal(cid,'Transform the document using this JMESPath query:\n```\n'+q+'\n```','The transformed result is visible in the editor.',data,[{'do':'query','query':q}],jsoncheck()))
 return [episode('gui-transform-a','transform',cps[:8]),episode('gui-transform-b','transform',cps[8:])]

def navigation():
 cps=[]
 data={'north':{'city':'Oslo','items':[1,2]},'south':{'city':'Rome','items':[3,4]}}
 cps.append(goal('expand-all','Expand all fields so the nested cities and array elements can be read.','Both cities and the nested array elements are visible.',data,[click(title='Expand all fields')]))
 cps.append(goal('expand-branch','Expand the north object to read its city.','The city Oslo is visible beneath north.',data,[click(title='Click to expand/collapse this field (Ctrl+E). Ctrl+Click to expand/collapse including all childs.',nth=1)]))
 for cid,query in [('key','city'),('value','Oslo'),('substring','rom'),('number','4')]:
  cps.append(goal('search-'+cid,'Search the tree for '+json.dumps(query)+'.','Matching fields or values are found and visibly highlighted.',data,[{'do':'fill','target':{'tag':'input','type':'text','context':'Search fields and values'},'value':query},{'do':'wait'}]))
 return [episode('gui-navigation','navigation',cps)]

def history():
 cps=[]
 for action in ['value','rename','duplicate','remove','type','sort','transform']:
  data={'target':12,'keep':4}
  steps={'value':[edit('target','77')],'rename':[{'do':'rename','node':'target','value':'changed'}],
   'duplicate':[{'do':'menu','node':'target'},click(text='Duplicate',tag='button')],
   'remove':[{'do':'menu','node':'target'},click(text='Remove',tag='button')],
   'type':[{'do':'change-type','node':'target','type':'String'}],
   'sort':[{'do':'sort','direction':'ascending','field':None}],
   'transform':[{'do':'query','query':'target'}]}[action]
  cps.append(goal('undo-'+action,'Perform '+{'value':'a value edit changing target to 77','rename':'a rename of target to changed','duplicate':'a duplication of target','remove':'removal of target','type':'a type change of target to String','sort':'ascending sorting of the object','transform':'the JMESPath transformation target'}[action]+', then undo it.','The document is restored after undo.',data,steps+[click(title='Undo last action (Ctrl+Z)')],jsoncheck(data)))
  cps.append(goal('redo-'+action,'Perform '+{'value':'a value edit changing target to 77','rename':'a rename of target to changed','duplicate':'a duplication of target','remove':'removal of target','type':'a type change of target to String','sort':'ascending sorting of the object','transform':'the JMESPath transformation target'}[action]+', undo it, then redo it.','The changed document is visible again after redo.',data,steps+[click(title='Undo last action (Ctrl+Z)'),click(title='Redo (Ctrl+Shift+Z)')],jsoncheck()))
 return [episode('gui-history-a','history',cps[:8]),episode('gui-history-b','history',cps[8:])]


# Examples exercise the callbacks already present in the upstream pages.
def example_goal(cid,page,description,acceptance,recipe,check=None,**extra):
 g=goal(cid,description,acceptance,None,recipe,check,construct=None,page='/examples/'+page+'.html',**extra)
 g.pop('data',None)
 return g

def examples():
 result=[];cps=[]
 for typ in ['Auto','String','Array','Object']:
  for append in [False,True]:
   cps.append(goal(('append-' if append else 'insert-')+typ.lower(),('Append' if append else 'Insert before target')+' a new '+typ.lower()+' field named added'+(' with value 42.' if typ=='Auto' else ' with the string value 42.' if typ=='String' else '.'),'The new added field is '+('after' if append else 'before')+' target and has the requested value and type.',{'target':5},[{'do':'insert','node':'target','type':typ,'append':append,'name':'added','value':'42' if typ in ('Auto','String') else None}],jsoncheck({'target':5,'added':42 if typ=='Auto' else '42' if typ=='String' else [] if typ=='Array' else {}})))
 for typ in ['Person','Address']:
  cps.append(example_goal('template-'+typ.lower(),'10_templates','Insert a new '+typ+' from the provided item templates.','A new '+typ+' template with its predefined fields is visible.',[{'do':'insert','node':None,'type':typ,'append':False,'menu_index':1}],jsoncheck()))
 result.append(episode('gui-insert-templates','templates',cps))
 cps=[]
 for cid,token,option in [('prefix','man','mandarine'),('overlap','app','appleton'),('single','cran','cranberry')]:
  cps.append(example_goal(cid,'11_autocomplete_basic','Complete the string value using the suggestion '+option+' after typing '+token+'.','The chosen completion appears as the string value.',[{'do':'autocomplete','node':'string','token':token,'option':option}],{'type':'json','path':['string'],'expected':option}))
 for cid,token,option,symbol in [('company','Apple','Apple Inc.','AAPL'),('symbol','NVDA','NVIDIA Corporation','NVDA'),('substring','Face','Meta Platforms Inc. (Facebook)','META')]:
  cps.append(example_goal(cid,'28_autocomplete_text_value_objects','In favorite_stock, type '+token+' and choose the company suggestion '+option+'.','The chosen stock symbol appears in favorite_stock.',[{'do':'autocomplete','node':'favorite_stock','token':token,'option':option}],{'type':'json','path':['favorite_stock'],'expected':symbol}))
 for cid,token,option,code in [('capital','Berlin','Germany','DE'),('country','France','France','FR'),('code','AU','Australia','AU')]:
  cps.append(example_goal(cid,'29_autocomplete_multiple_fields','In origin_country, type '+token+' and choose '+option+' from autocomplete.','origin_country displays the selected country code.',[{'do':'autocomplete','node':'origin_country','token':token,'option':option}],{'type':'json','path':['origin_country'],'expected':code}))
 result.append(episode('gui-autocomplete','autocomplete',cps))
 cps=[]
 for field,new in [('name','Diana'),('age','45')]:
  cps.append(example_goal(field,'05_custom_fields_editable','Change '+field+' to '+new+'.','The editable value has changed while the record remains visible.',[edit(field,new)],{'type':'json','path':[field],'expected':new if field=='name' else 45}))
 cps.append(example_goal('rename-age','05_custom_fields_editable','Rename age to years.','The editable field is now named years.',[{'do':'rename','node':'age','value':'years'}],{'type':'json','path':['years'],'expected':32}))
 cps.append(example_goal('dark-edit','06_custom_styling','Change number to 256.','The styled editor displays the new number.',[edit('number','256')],{'type':'json','path':['number'],'expected':256}))
 cps.append(example_goal('custom-ace-edit','08_custom_ace','Replace the code with {"custom":42}.','The code editor displays the new JSON.',[{'do':'text-edit','value':'{"custom":42}'}],jsoncheck({'custom':42})))
 result.append(episode('gui-custom-editors','configured-editors',cps))
 cps=[]
 validteam={'team':[{'name':'Joe','age':21},{'name':'Sarah','age':13},{'name':'Jack','age':16},{'name':'Megan','age':20}]}
 for mode in ['tree','text','code','preview']:
  cps.append(example_goal('team-'+mode,'18_custom_validation','Switch to '+mode+' mode and inspect the validation problems in this team.','The team validation problems are visibly available.',[{'do':'mode','mode':mode.title()}] if mode!='tree' else [click(title='Expand all fields')],{'type':'valid'}))
 cps.append(example_goal('team-fix','18_custom_validation','In text mode replace the document with:\n```json\n'+json.dumps(validteam)+'\n```','The complete valid team is visible and the validation problems are cleared.',[{'do':'mode','mode':'Text'},{'do':'text-edit','value':json.dumps(validteam)},{'do':'wait','seconds':1}],jsoncheck(validteam)))
 for name in ['Joe','Harry','Megan']:
  doc={'customers':[{'name':name}]}
  cps.append(example_goal('customer-'+name.lower(),'19_custom_validation_async','In text mode replace the document with:\n```json\n'+json.dumps(doc)+'\n```','The known customer is visible without an asynchronous validation problem.',[{'do':'mode','mode':'Text'},{'do':'text-edit','value':json.dumps(doc)},{'do':'wait','seconds':1}],jsoncheck(doc)))
 cps.append(example_goal('unknown-customer','19_custom_validation_async','In text mode replace the document with {"customers":[{"name":"Unknown"}]}, then inspect the validation result.','An asynchronous validation error identifies the unknown customer.',[{'do':'mode','mode':'Text'},{'do':'text-edit','value':'{"customers":[{"name":"Unknown"}]}'},{'do':'wait','seconds':1}],{'type':'valid'}))
 result.append(episode('gui-custom-validation','custom-validation',cps))
 cps=[]
 for cid,text in [('object','{"record":{"name":"Amina","age":27}}'),('array','[1,"two",false,null]'),('unicode','{"城市":"苏州","café":"☕"}')]:
  cps.append(example_goal('load-'+cid,'04_load_and_save','Load a JSON document containing:\n```json\n'+text+'\n```','The loaded document is visible.',[{'do':'upload','text':text}],jsoncheck(json.loads(text))))
 for name in ['document','data.json','report.txt']:
  cps.append(example_goal('save-'+name.replace('.','-'),'04_load_and_save','Save the current document using the file name '+name+'.','A JSON document download is produced.',[{'do':'dialog','text':name},click(text='Save')],{'type':'download'}))
 result.append(episode('gui-files','files',cps))
 return result


def schema_ui():
 cps=[]
 schema={'type':'object','properties':{'name':{'type':'string','minLength':3},'age':{'type':'integer','minimum':18},'role':{'enum':['reader','writer']},'enabled':{'type':'boolean'}},'required':['name','age'],'additionalProperties':False}
 base={'name':'Al','age':16,'role':'other','enabled':True}
 for mode in ['tree','form','view','text','code','preview']:
  cps.append(goal(mode,'Inspect the validation problems in the current '+mode+' document.','Schema validation problems are visibly indicated for this document.',base,[{'do':'wait','seconds':1}],{'type':'valid'},mode=mode,construct={'mode':mode,'modes':MODES,'schema':schema,'showErrorTable':True}))
 good={'name':'Alice','age':25,'role':'writer','enabled':True}
 cps.append(goal('correct','In text mode replace the document with:\n```json\n'+json.dumps(good)+'\n```','The valid record is displayed and schema problems are cleared.',base,[{'do':'text-edit','value':json.dumps(good)},{'do':'wait','seconds':1}],jsoncheck(good),mode='text',construct={'mode':'text','schema':schema,'showErrorTable':True}))
 return [episode('gui-schema','schema-feedback',cps)]

def sync_examples():
 cps=[]
 for cid,node,value in [('string','string','Synchronized'),('number','number','789')]:
  g=example_goal(cid,'16_synchronize_editors','Change '+node+' in the left editor to '+value+'.','Both editors display the new value.',[edit(node,value)],{'type':'json','editor':'editor2','path':[node],'expected':value if node=='string' else 789})
  cps.append(g)
 for cid,node in [('expand','student_details'),('array','marks')]:
  cps.append(example_goal(cid,'25_sync_node_expand','Expand '+node+' in the left editor.','The matching branch is expanded in both editors.',[click(title='Click to expand/collapse this field (Ctrl+E). Ctrl+Click to expand/collapse including all childs.',nth=2 if node=='marks' else 1)]))
 return [episode('gui-synchronization','synchronization',cps)]


def more_features():
 cps=[]
 for cid,color in [('red','#ff0000'),('green','#00aa00'),('alpha','#3366cc80')]:
  cps.append(goal('picker-'+cid,'Use the color picker for color to select '+color+'.','The color value and swatch reflect the chosen color.',{'color':'#82b92c'},[{'do':'color','node':'color','value':color}],jsoncheck()))
 cps.append(goal('timestamp','Set time to 1704067200000 and inspect its timestamp annotation.','The time value is accompanied by its corresponding UTC date and time.',{'time':1575599819000},[edit('time','1704067200000')],jsoncheck({'time':1704067200000})))
 cps.append(goal('unicode','Change text to café 茶 in this editor configured to escape Unicode.','The edited text is displayed with Unicode escape sequences.',{'text':'old'},[edit('text','café 茶')],jsoncheck({'text':'café 茶'}),construct={'mode':'tree','escapeUnicode':True}))
 data={'branch':{'child':{'leaf':'Visible leaf'}}}
 cps.append(goal('collapse-all','Collapse the tree to its root.','The root remains visible with its content collapsed.',data,[click(title='Collapse all fields')],prepare=[call('expandAll')]))
 cps.append(goal('recursive-expand','Expand branch recursively so leaf becomes visible.','Visible leaf can be read in the expanded branch.',data,[click(title='Click to expand/collapse this field (Ctrl+E). Ctrl+Click to expand/collapse including all childs.',nth=1),click(title='Expand all fields')]))
 items={'items':['item-'+str(i) for i in range(8)]}
 cps.append(goal('show-more','Expand items and show more children.','More than the first three items are visible.',items,[{'do':'expand-node','node':'items'},click(text='show more',tag='a'),{'do':'expect','text':'item-5'}],construct={'mode':'tree','maxVisibleChilds':3}))
 cps.append(goal('show-all','Expand items and show all children.','Every item through item-7 is visible.',items,[{'do':'expand-node','node':'items'},click(text='show all',tag='a'),{'do':'expect','text':'item-7'}],construct={'mode':'tree','maxVisibleChilds':3}))
 result=[episode('gui-display-tools','display-tools',cps)]
 cps=[]
 cps.append(example_goal('translation','14_translate','Change number to 456 in this translated editor.','The editor remains translated and the number changes.',[edit('number','456')],{'type':'json','path':['number'],'expected':456}))
 cps.append(example_goal('validation-event','22_on_validation_event','Replace the code with {"firstName":"Mia","lastName":"Lane","age":35}.','The new record is visible and the validation callback output reflects the valid record.',[{'do':'text-edit','value':'{"firstName":"Mia","lastName":"Lane","age":35}'},{'do':'wait','seconds':1}],jsoncheck({'firstName':'Mia','lastName':'Lane','age':35})))
 cps.append(example_goal('dynamic-completion','12_autocomplete_dynamic','Complete the string field using the existing word number from the dynamic suggestions.','string contains the suggested word number.',[{'do':'autocomplete','node':'string','token':'num','option':'number'}],{'type':'json','path':['string'],'expected':'number'}))
 cps.append(example_goal('jq-path','21_customize_context_menu','Use the custom jq Path action for the number field.','The action reports the path for number.',[{'do':'menu','node':'number'},click(text='jq Path',tag='button')]))
 result.append(episode('gui-example-callbacks','example-callbacks',cps))
 return result


def preview_actions():
 cps=[]
 for direction in ['ascending','descending']:
  cps.append(goal('sort-'+direction,'Sort the preview document in '+direction+' order.','The preview shows the numbers in the requested order.',[10,2,5,1],[{'do':'sort','direction':direction,'field':None}],jsoncheck(),mode='preview'))
 cps.append(goal('transform','Transform this preview with the JMESPath query [*].name.','The preview shows the projected names.',[{'name':'Ada','age':21},{'name':'Bob','age':35}],[{'do':'query','query':'[*].name'}],jsoncheck(['Ada','Bob']),mode='preview'))
 cps.append(goal('undo-sort','Sort the preview in ascending order, then undo it.','The original number order is restored.',[10,2,5,1],[{'do':'sort','direction':'ascending','field':None},click(title='Undo last action (Ctrl+Z)')],jsoncheck([10,2,5,1]),mode='preview'))
 return [episode('gui-preview-actions','preview',cps)]



def keyboard_and_schema():
 cps=[]
 for cid,key,goaltext,data,expected in [
  ('move-down','Alt+Shift+ArrowDown','Move the item target one position down.',['first','target','last'],['first','last','target']),
  ('move-up','Alt+Shift+ArrowUp','Move the item target one position up.',['first','target','last'],['target','first','last']),
  ('duplicate','Control+D','Duplicate the item target.',['first','target','last'],['first','target','target','last']),
  ('remove','Control+Delete','Remove the item target.',['first','target','last'],['first','last']),
 ]:
  cps.append(goal(cid,goaltext,'The array visibly reflects the requested change.',data,[click(text='target',tag='div'),press(key)],jsoncheck(expected)))
 result=[episode('gui-keyboard-structure','structure',cps)]
 cps=[]
 for cid,page in [('basic','26_autocomplete_by_schema'),('recursive','27_autocomplete_by_schema_recursive_refs')]:
  cps.append(example_goal(cid,page,'Use schema autocomplete to replace the selected firstName value with the suggestion John.','The schema completion is inserted into firstName.',[{'do':'paste','value':'Jo'},press('Control+Space'),{'do':'wait','seconds':.5},press('Enter')],{'type':'json','path':(['personalDetails','firstName'] if cid=='recursive' else ['firstName']),'expected':'John'},select_text='Draft',selection_path=(['personalDetails','firstName'] if cid=='recursive' else ['firstName'])))
 result.append(episode('gui-schema-completion','autocomplete',cps))
 return result

def build():
 from behavior_gui import gui_episodes
 episodes=(gui_episodes()+scalar_edits()+structure()+types()+mode_goals()+text_tools()+sorting()+transform()+navigation()+history()+examples()+schema_ui()+sync_examples()+more_features()+preview_actions()+keyboard_and_schema())
 for w in episodes:
  if w['id']=='gui-files':
   w['inputs']={'files':['object.json','array.json','unicode.json']}
   for c in w['checkpoints']:
    if c['id'].startswith('load-'):
     name=c['id'][5:]+'.json'
     c['goal']='Load the supplied file '+name+'.'
     c['recipe'][0]['filename']=name
    elif c['id'].startswith('save-'):
     filename={'save-document':'document.json','save-data-json':'data.json','save-report-txt':'report.json'}[c['id']]
     document={'save-document':{'record':{'name':'Amina','age':27}},'save-data-json':[1,'two',False,None],'save-report-txt':{'城市':'苏州','café':'☕'}}[c['id']]
     c['data']=document
     c['assertions'][1]['check']['expected']=document
     c['assertions'][1]['check']['filename']=filename
     c['assertions'][0]['requirement']='A JSON document named '+filename+' is downloaded.'
  if w['id']=='gui-insert-templates':
   for c in w['checkpoints']:
    if c['id'].startswith(('insert-','append-')):
     original=c['assertions'][1]['check'];c['assertions'][1]['check']={**original,'type':'object-order','expected_keys':['target','added'] if c['id'].startswith('append-') else ['added','target']}
    if c['id'] in ('template-person','template-address'):
     template={'firstName':'John','lastName':'Do','age':28} if c['id']=='template-person' else {'street':'','city':'','state':'','ZIP code':''}
     c['assertions'][1]['check']={'type':'template','template':template}
  ids={c['id']:c for c in w['checkpoints']}
  for c in w['checkpoints']:
   if (w['feature']=='structure' and c['id'] in ('duplicate-scalar','duplicate-object','duplicate-array')) or (w['feature']=='history' and c['id']=='redo-duplicate'):
    for a in c['assertions']:
     if a['channel']=='backend':a['check']={'type':'copy-field','field':'target','original':c['data']}
   if c['id'].startswith('extract-') or (w['feature']=='history' and c['id']=='undo-transform'):
    c['recipe'].append(click(title='Expand all fields'))
   if w['feature']=='history' and c['id'] in ('undo-sort','redo-sort'):
    c['assertions'][1]['check']={'type':'object-order'}
   if w['id']=='gui-preview-actions' and c['id']=='undo-sort':
    for a in c['assertions']:a['requires']=[w['id']+'/sort-ascending/data-0']
   if w['feature']=='value-types':
    c['assertions'][0]['requires']=[a['id'] for a in c['assertions'] if a['channel']=='backend']
   if w['id']=='gui-sorting' and c['id'] in ('object','object-desc'):
    c['assertions'][1]['check']={'type':'object-order'}
    c['data']={'z':1,'a':3,'b':2}
    c.setdefault('prepare',[]).append(call('setText',json.dumps(c['data'],ensure_ascii=False,separators=(',',':'))))
   if w['feature']=='history' and c['id'] in ('undo-sort','redo-sort'):
    c.setdefault('prepare',[]).append(call('setText',json.dumps(c['data'],ensure_ascii=False,separators=(',',':'))))
   if c['id'].startswith('picker-') and w['feature']=='display-tools':
    for a in c['assertions']:
     if a['channel']=='backend':a['check']={'type':'color','expected':{'picker-red':[255,0,0,255],'picker-green':[0,170,0,255],'picker-alpha':[51,102,204,128]}[c['id']]}
   if c['id'].startswith('undo-') and w['feature']=='history':
    redo=ids.get(c['id'].replace('undo-','redo-',1))
    if redo:
     positive=[a['id'] for a in redo['assertions'] if a['channel']=='backend']
     for a in c['assertions']:a['requires']=positive
 result=[]
 for w in episodes:
  if len(w['checkpoints'])<=8:result.append(w);continue
  original=w['id']
  for offset in range(0,len(w['checkpoints']),8):
   wid=original+'-'+str(offset//8+1);cps=w['checkpoints'][offset:offset+8]
   for c in cps:
    for a in c['assertions']:
     a['id']=a['id'].replace(original+'/',wid+'/',1)
     if 'requires' in a:a['requires']=[x.replace(original+'/',wid+'/',1) for x in a['requires']]
   n=len(cps)
   result.append({**w,'id':wid,'checkpoints':cps,'budget':{'calls':40+40*n,'tokens':500000+600000*n,'seconds':300+300*n}})
 return result
