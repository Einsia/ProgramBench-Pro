"""User goals describe behavior; recipes only describe the pinned reference route."""
from evaluation.contract import files_path
HINTS=('Use the workbook name box to select a cell or range if helpful. All cell references are on the current sheet '
       'unless a sheet name is given. A formula is entered as cell content beginning with =. Enter exact requested values. '
       'If pasting a text table opens an import dialog, finish the import. Save files to exactly the full output path given; '
       'replace the entire suggested filename. Controls behind a modal belong to the underlying workbook; operate the active '
       'dialog. A save is complete when its dialog closes without an error. Do not reopen saved files unless asked. '
       'Precise saved values and formats are checked separately; judge visible results at ordinary reading scale.')


def key(k):return {'op':'key','key':k}
def goto(r):return {'op':'goto','range':r}
def set_(**cells):return {'op':'set','cells':cells}
def menu(*p):return {'op':'menu','path':list(p)}
def save(f):return {'op':'save','file':f}
def button(n):return {'op':'button','name':n}
def choose(n):return {'op':'choose','name':n}
def fill(n,v,**kw):return {'op':'fill','label':n,'value':v,**kw}


def values(file,sheet,**cells):
    import checks
    return {'kind':'values','file':file,'sheet':sheet,'cells':list(cells),
            'expected':{'cells':{k:checks.number(v) for k,v in cells.items()}},'description':'Saved cell values and recalculated results.'}


def formulas(file,sheet,**cells):
    import re
    return {'kind':'formulas','file':file,'sheet':sheet,'cells':list(cells),
            'expected':{'formulas':{k:re.sub(r'\s+','',v).casefold() for k,v in cells.items()}},'description':'Saved formulas retain their intended references.'}


def style(file,sheet,cell,property,value):
    return {'kind':'style','file':file,'sheet':sheet,'cell':cell,'property':property,'expected':{'value':value},'description':'Saved '+cell+' '+property+'.'}


def step(id,goal,acceptance,recipe,checks=(),depends=(),lifecycle=None):
    result={'id':id,'goal':goal,'acceptance':[acceptance] if isinstance(acceptance,str) else list(acceptance),
            'recipe':recipe,'checks':list(checks),'depends_on':list(depends)}
    if lifecycle:result['lifecycle']=lifecycle
    return result


def episode(id,feature,steps,inputs=(),opened=None):
    inbox=files_path('inbox', instance=False);outbox=files_path('outbox', instance=False)
    for cp in steps:
        cp['goal']=cp['goal'].replace('{inbox}',inbox).replace('{outbox}',outbox)
        cp['assertions']=[{'id':f'{id}/{cp["id"]}/visible-{i+1}','channel':'frontend','method':'agent','requirement':text}
                          for i,text in enumerate(cp.pop('acceptance'))]
        for i,c in enumerate(cp.pop('checks')):
            cp['assertions'].append({'id':f'{id}/{cp["id"]}/artifact-{i+1}','channel':'backend','method':'program',
                                     'requirement':c['description'],'check':c})
        if inputs:cp['depends_on'].append('setup:inputs')
        assert not cp.get('recipe') or any(a['channel']=='frontend' for a in cp['assertions']), 'GUI operations need a frontend checkpoint: '+id+'/'+cp['id']
    if id=='default-preferences':
        next(cp for cp in steps if cp['id']=='quit')['assertions'][0]['requires']=[id+'/persist/visible-1',id+'/persist/visible-2']
    if id=='cell-comments':
        next(a for cp in steps if cp['id']=='remove' for a in cp['assertions'] if a['id'].endswith('/artifact-1'))['requires']=[id+'/edit/artifact-1',id+'/remove/artifact-2',id+'/remove/artifact-3']
    if id=='validation':
        next(cp for cp in steps if cp['id']=='reject')['assertions'][0]['requires']=[id+'/configure/artifact-1']
    prepare=[{'op':'open','file':opened}] if opened else []
    preparation=f'Unscored preparation: open {inbox}/{opened} before the first goal. ' if opened else ''
    return {'id':id,'feature':feature,'execution':'gui','initial_state':'Fresh workbook and private desktop; input documents are in the inbox.',
            'setup':[{'id':'inputs','op':'upload','files':list(inputs)}] if inputs else [],'prepare':prepare,
            'inputs':{'input_folder':inbox,'output_folder':outbox,'documents':{n:inbox+'/'+n for n in inputs}},
            'session':preparation+HINTS,
            'allowed_equivalents':['Use any visible equivalent menu, toolbar, keyboard, pointer or dialog route.','Equivalent visual design and control layout are acceptable.'],
            'forbidden_bypasses':['Do not use terminals, hidden application state, or other applications.','Do not recreate an absent spreadsheet operation by manually entering its expected results.'],
            'budget':{'calls':300,'tokens':5000000,'seconds':3000},'checkpoints':steps}


def build():
    w=[]
    def add(*a,**k):w.append(episode(*a,**k))
    add('cell-entry','editing',[
      step('enter','Enter the text Budget in A1, 12 in A2, and 7.5 in B2. Save as {outbox}/entered.gnumeric.',
           'The worksheet displays Budget in A1 and the two entered numbers in A2 and B2.',
           [set_(A1='Budget',A2=12,B2=7.5),save('entered.gnumeric')],[values('entered.gnumeric','Sheet1',A1='Budget',A2=12,B2=7.5)]),
      step('calculate','Enter =A2*B2 in C2 and =SUM(A2:B2) in D2. Save as {outbox}/calculated.gnumeric.',
           'C2 and D2 show calculated numeric results for the multiplication and sum, while the inputs remain visible.',
           [set_(C2='=A2*B2',D2='=SUM(A2:B2)'),save('calculated.gnumeric')],
           [values('calculated.gnumeric','Sheet1',C2=90,D2=19.5),formulas('calculated.gnumeric','Sheet1',C2='=A2*B2',D2='=SUM(A2:B2)')],depends=['enter']),
      step('update','Change A2 to 20. Save as {outbox}/updated.gnumeric.',
           'Both dependent formula results update after A2 changes; B2 retains its value.',
           [set_(A2=20),save('updated.gnumeric')],[values('updated.gnumeric','Sheet1',A2=20,B2=7.5,C2=150,D2=27.5)],depends=['calculate']),
    ])
    add('reopen-workbook','persistence',[
      step('save','Change Sales!C3 to 9, then save the workbook as {outbox}/persisted.gnumeric.',
           'The Coffee row shows 9 units and its revenue is recalculated.',
           [set_(C3=9),save('persisted.gnumeric')],[values('persisted.gnumeric','Sales',C3=9,E3=54,E8=189.25)]),
      step('reopen','The application has restarted. Open {outbox}/persisted.gnumeric.',
           'The saved workbook reopens with Coffee at 9 units and the recalculated revenue.',
           [{'op':'open','file':'persisted.gnumeric','area':'outbox'}],depends=['save'],lifecycle='restart')
    ],inputs=['ledger.gnumeric'],opened='ledger.gnumeric')
    from gui_core import build as core
    from gui_data import build as data
    from gui_statistics import build as statistics
    from gui_formatting import build as formatting
    from gui_charts import build as charts
    from gui_settings import build as settings
    from gui_extra import build as extra
    from gui_data_tools import build as data_tools
    from gui_statistics_extra import build as statistics_extra
    from gui_chart_edit import build as chart_edit
    from gui_workbook_objects import build as workbook_objects
    return w+core()+data()+statistics()+formatting()+charts()+settings()+extra()+data_tools()+statistics_extra()+chart_edit()+workbook_objects()
