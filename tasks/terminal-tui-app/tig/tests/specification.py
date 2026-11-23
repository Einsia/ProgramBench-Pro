"""Observable Tig episodes. Every scored value is a product output, never setup state."""
import copy
import re

def key(k):return {'op':'key','key':k}
def keys(*k):return {'op':'keys','keys':list(k)}
def command(s):return {'op':'console','command':s}
def search(s):return [key('/'),{'op':'type','text':s},key('Enter')]
EXPORT=command('save-options /outbox/options.tigrc')

def point(name,check,requirement=None):return (name,requirement or name.replace('-',' '),check)
def checkpoint(id,goal,steps,checks=(),front=(),depends=(),collect=()):
    return {'id':id,'goal':goal,'steps':steps,'checks':list(checks),'front':list(front),'depends_on':list(depends),'collect':list(collect)}

def episode(id,feature,cps,spec=None,config=None,args=None,stdin=None,gui=False,setup_extra=()):
    cps=[copy.deepcopy(cp) for cp in cps]
    setup=[]
    requests=[]
    if spec is not None:requests.append({'op':'repository','spec':copy.deepcopy(spec)})
    if config is not None:requests.append({'op':'configure','text':config})
    if args is not None or stdin is not None:
        req={'op':'open','args':args or []}
        if stdin is not None:req['stdin']=stdin
        requests.append(req)
    requests.extend(setup_extra)
    if requests:setup=[{'id':'input','requests':requests}]
    for cp in cps:
        export_name=(id+'-'+cp['id'])[:90]+'.tigrc'
        for request in cp['steps']+cp.get('collect',[]):
            if request==EXPORT:request['command']='save-options /outbox/'+export_name
            # Enum date commands can leave a stale Escape notice while repainting.
            # Their exported value is the authoritative product result.
            if id=='enum-date' and request.get('op')=='console':request['artifact_only']=True
        for _,_,check in cp['checks']:
            if check['kind'] in ('config','column','color','binding'):check.setdefault('file',export_name)
        cp['depends_on']=(['setup:input'] if setup else [])+cp['depends_on']
        assertions=[]
        for suffix,requirement,check in cp.pop('checks'):
            assertions.append({'id':id+'/'+cp['id']+'/'+suffix,'channel':'backend','method':'program','requirement':requirement,'check':check})
        for i,requirement in enumerate(cp.pop('front')):
            assertions.append({'id':id+'/'+cp['id']+'/visible-'+str(i+1),'channel':'frontend','method':'agent','requirement':requirement,
                               'requires':[a['id'] for a in assertions if a['channel']=='backend']})
        for a in assertions:
            if a['id'].endswith('/worktree') and 'unstage-' in id and any(x['id']==id+'/'+cp['id']+'/status' for x in assertions):
                a['requires']=[id+'/'+cp['id']+'/status']
            if id=='cherry-pick' and a['id'].endswith('/preserve'):
                a['requires']=[id+'/'+cp['id']+'/result']
        cp['assertions']=assertions
    result={'id':id,'feature':feature,'execution':'gui' if gui else 'program',
            'initial_state':'Tig is open on the prepared local repository. Each goal names its input precisely.',
            'setup':setup,'inputs':{},'checkpoints':cps}
    if gui:
        result.update(session='Operate the local Git browser toward each goal. Use native keys or the console operation. The operating guide describes the available routes. Work only with the named repository data.',
            allowed_equivalents=['Any supported route that reaches the same visible result.'],
            forbidden_bypasses=['Do not execute shell commands or edit the repository outside the application.'],
            budget={'calls':200,'tokens':2000000,'seconds':1800})
    return result

BASE={
 'commits':[
  {'id':'seed','message':'Start field notebook','author':'Ada Rivers','email':'ada@example.test','files':{
   'README.md':'# Field Notebook\nObservations from the north trail.\n',
   'notes.txt':'oak tree\nriver bank\nstone bridge\n',
   'src/guide.py':'def heading():\n    return "north"\n',
   'docs/manual.md':'# Walking guide\nCarry water and a map.\n',
   'data/counts.csv':'site,count\nnorth,7\nsouth,4\n',
   'has space.txt':'A name with spaces.\n','café.txt':'Crème and café.\n',
   'empty.txt':'','run.sh':{'text':'#!/bin/sh\necho north\n','mode':493}}},
  {'id':'water','message':'Document river access','author':'Bea Meadow','email':'bea@example.test','files':{'notes.txt':'oak tree\nriver bank with footpath\nstone bridge\n'}},
  {'id':'guide','message':'Add safety checklist','author':'Ada Rivers','email':'ada@example.test','files':{'docs/checklist.md':'Bring boots\nBring water\nCheck weather\n'}},
  {'id':'side','parents':['water'],'message':'Mark eastern viewpoint','author':'Chen Grove','email':'chen@example.test','files':{'east.txt':'Eastern viewpoint\n'}},
  {'id':'merge','parents':['guide','side'],'message':'Merge eastern route','files':{'east.txt':'Eastern viewpoint\n'}},
  {'id':'tip','message':'Update trail heading\n\nRecord the northeast approach.\n\nReviewed-by: Trail Team <team@example.test>','author':'Bea Meadow','email':'bea@example.test','files':{'src/guide.py':'def heading():\n    return "northeast"\n','notes.txt':'oak tree\nriver bank with footpath\nstone bridge restored\n'}},
 ],
 'refs':{'main':'tip','feature/east':'side','archive':'water','refs/tags/v1.0':'seed','refs/remotes/origin/main':'merge'},
 'head':'main',
}

VIEW_COLS={
 'main':['line-number','id','date','author','committer','commit-title'],
 'reflog':['line-number','id','date','author','committer','commit-title'],
 'refs':['line-number','id','date','author','committer','ref','commit-title'],
 'stash':['line-number','id','date','author','commit-title'],
 'tree':['line-number','mode','author','committer','file-size','date','id','file-name'],
 'blame':['id','file-name','author','committer','date','line-number','text'],
 'grep':['file-name','line-number','text'],
 'status':['line-number','status','file-name'],
 **{v:['line-number','text'] for v in ('blob','diff','log','pager','stage')},
}
ATTRS={
 'author':{'display':'email','width':'18','maxwidth':'25%'},
 'committer':{'display':'abbreviated','width':'16','maxwidth':'30%'},
 'date':{'display':'custom','use-author':'yes','local':'yes','format':'%d/%m/%Y','width':'15'},
 'id':{'display':'yes','width':'12','color':'yes'},
 'line-number':{'display':'yes','interval':'2','width':'6'},
 'commit-title':{'display':'no','graph':'v1','refs':'no','overflow':'64'},
 'ref':{'display':'no','width':'22','maxwidth':'35%'},
 'file-name':{'display':'always','width':'24','maxwidth':'40%'},
 'file-size':{'display':'units','width':'10'},
 'mode':{'display':'no','width':'12'},
 'status':{'display':'long'},
 'text':{'display':'no','commit-title-overflow':'42'},
}

def col_attrs(view,col):
    a=dict(ATTRS[col])
    if col=='id' and view in ('blame','reflog'):a['display']='no'
    if col=='id' and view=='blame':a['color']='no'
    if col=='line-number' and view in ('blame','grep'):a['display']='no'
    if col=='file-name' and view!='grep':a['display']='no'
    if col=='commit-title' and view!='main':a.pop('graph');a.pop('refs')
    if col=='id' and view not in ('blame','reflog'):a.pop('color')
    if col=='text' and view not in ('log','diff'):a.pop('commit-title-overflow')
    return a

def column_points(view,cols,attrs=None):
    out=[]
    for col in cols:
        values=(attrs or {}).get(col,col_attrs(view,col))
        for attr in values:
            out.append(point(col+'-'+attr,{'kind':'column','view':view,'column':col,'attribute':attr,'expected':values[attr]},
                             f'The exported {view} {col} column preserves its {attr} setting.'))
    return out

def config_episodes():
    out=[]
    for view,cols in VIEW_COLS.items():
        specs=[]
        for col in cols:
            a=col_attrs(view,col)
            specs.append(col+':'+a['display']+''.join(','+k+'='+v for k,v in a.items() if k!='display'))
        setting='set '+view+'-view = '+' '.join(specs)
        checks=column_points(view,cols)
        # Full view grammar and individual option assignment are separate public input forms.
        shorthand=[command('set '+view+'-view-'+col+('' if attr=='display' else '-'+attr)+' = '+value)
                   for col in cols for attr,value in col_attrs(view,col).items()]
        cps=[checkpoint('full','Set the complete '+view+' view specification.',[command(setting),EXPORT],checks),
             checkpoint('shorthand','Apply the same column properties through individual option names.',
                        [{'op':'configure','text':''},*shorthand,EXPORT],checks),
             checkpoint('load','Load the native column configuration from the user tigrc.',
                        [{'op':'configure','text':setting},EXPORT],checks)]
        out.append(episode('columns-'+view,'column-configuration',cps,BASE))
    settings={
     'commit-order':['reverse','topo','author-date','date','default'],
     'ignore-case':['smart-case','yes'], 'ignore-space':['all','some','at-eol'],
     'line-graphics':['ascii','utf-8','auto'], 'vertical-split':['yes','no'],
     'refresh-mode':['manual','after-command','periodic'],
     'tab-size':['4','1'], 'diff-context':['0','12'], 'horizontal-scroll':['9','25%'],
     'split-view-height':['12','60%'],'split-view-width':['28','70%'],
     'truncation-delimiter':['"!"','utf-8'],'history-size':['40','0'],
     'refresh-interval':['2'],'id-width':['10'],
     'reference-format':['"(branch) {tag} [remote]"'],
     'diff-options':['--patience -U7'],'blame-options':['-w -C'],
     'main-options':['--first-parent --max-count=4'],'log-options':['--numstat --no-merges'],
     'git-colors':['no'],
    }
    defaults_yes='show-changes show-untracked status-show-untracked-dirs status-show-untracked-files diff-indicator mailmap wrap-search focus-child send-child-enter editor-line-number'.split()
    defaults_no='word-diff diff-noprefix wrap-lines pager-autoscroll recurse-tree start-on-head mouse mouse-wheel-cursor'.split()
    settings.update({x:['no'] for x in defaults_yes});settings.update({x:['yes'] for x in defaults_no})
    settings['mouse-scroll']=['1']
    cps=[]
    for name,values in settings.items():
        for i,value in enumerate(values):
            cid=name+'-'+str(i+1)
            cps.append(checkpoint(cid,'Set '+name+' to '+value+'.',
                 [{'op':'configure','text':''},command('set '+name+' = '+value),EXPORT],
                 [point('value',{'kind':'config','name':name})]))
    out.append(episode('settings-values','configuration',cps,BASE))
    # Enums have semantically distinct serialization, not a grid of arbitrary integers.
    enum_values={'author':['no','full','abbreviated','email','email-user'],
                 'committer':['full','no','abbreviated','email','email-user'],
                 'date':['no','default','relative','relative-compact','custom'],
                 'file-name':['no','auto','always'],'file-size':['no','default','units'],
                 'status':['no','short','long']}
    for col,values in enum_values.items():
        view={'file-name':'tree','file-size':'tree','status':'status'}.get(col,'main')
        cps=[]
        for i,value in enumerate(values):
            cps.append(checkpoint('value-'+str(i),'Select the '+value+' representation of '+col+'.',
                [command('set '+view+'-view-'+col+' = '+value),EXPORT],
                [point('value',{'kind':'column','view':view,'column':col,'attribute':'display',**({'expected':value} if col=='date' else {})})],
                depends=['value-0'] if i==1 else []))
        out.append(episode('enum-'+col,'column-configuration',cps,BASE))
    return out

COLOR_AREAS='default cursor cursor-blur status delimiter date mode id overflow header section directory file file-size line-number title-blur title-focus main-commit main-annotated main-tag main-local-tag main-remote main-stash main-note main-prefetch main-other main-replace main-tracked main-ref main-head stat-none stat-staged stat-unstaged stat-untracked help-group help-action diff-stat diff-add-highlight diff-del-highlight graph-commit search-result'.split()+['palette-'+str(i) for i in range(14)]

def color_episodes():
    out=[]
    for group,names in [('general',COLOR_AREAS[:20]),('views',COLOR_AREAS[20:41]),('palette',COLOR_AREAS[41:])]:
        cps=[]
        for name in names:
            cps.append(checkpoint(name,'Customize the '+name+' color rule.',
                [command('color '+name+' cyan red bold underline'),EXPORT],
                [point('rule',{'kind':'color','name':name})]))
        out.append(episode('colors-'+group,'color-configuration',cps,BASE))
    custom=[('signed','"    Signed-off-by:"'),('diff','"+"'),('prefix','"NOTE:"'),('view','grep.file')]
    for cid,name in custom:
        raw=name.strip('"')
        out.append(episode('color-match-'+cid,'color-configuration',[
            checkpoint('configure','Configure the matching rule.',[command('color '+name+' yellow blue reverse'),EXPORT],
                       [point('rule',{'kind':'color','name':raw})])],BASE))
    return out

def binding_episodes():
    actions='enter back next previous parent view-next refresh maximize view-close move-up move-down move-half-page-up move-half-page-down move-page-up move-page-down move-first-line move-last-line scroll-first-col scroll-left scroll-right scroll-line-up scroll-line-down scroll-page-up scroll-page-down scroll-half-page-up scroll-half-page-down search search-back find-next find-prev options screen-redraw stop-loading show-version'.split()
    actions += ['view-'+v for v in ('main','diff','log','reflog','tree','blob','blame','refs','status','stage','stash','pager','help')]
    cps=[]
    for action in actions:
        cps.append(checkpoint(action,'Bind x to the internal '+action+' action.',
            [command('bind generic x '+action),EXPORT],
            [point('binding',{'kind':'binding','name':'generic x'})]))
    out=[episode('bindings-actions','key-configuration',cps,BASE)]
    cps=[]
    for view,action in [('main','move-last-line'),('diff','move-down'),('log','move-up'),('reflog','refresh'),('tree','parent'),('blob','move-first-line'),('blame','parent'),('refs','move-last-line'),('status','status-update'),('stage','stage-update-line'),('stash','view-main'),('grep','enter'),('pager','scroll-right'),('help','refresh'),('search','find-next')]:
        cps.append(checkpoint(view,'Define a '+view+'-specific binding.',[command('bind '+view+' x '+action),EXPORT],
                             [point('binding',{'kind':'binding','name':view+' x'})]))
    out.append(episode('bindings-context','key-configuration',cps,BASE))
    return out

def screencheck(patterns):return {'kind':'screen','patterns':patterns}
def view_case(id,feature,goal,steps,patterns,front,args=None,config=None,spec=None,stdin=None):
    return episode(id,feature,[checkpoint('show',goal,steps,[point('content',screencheck(patterns))],front)],
                    spec or BASE,config,args,stdin,True)

def browse_episodes():
    out=[]
    out.append(view_case('gui-history','history','Show the repository history.',[key('m')],['Update trail heading','Merge eastern route'],['The history shows the latest trail change and the merge.','The entries identify authors and the main branch.']))
    out.append(view_case('gui-diff','diff','Inspect the changes in Update trail heading.',[key('d')],['northeast','north','src/guide.py'],['The selected commit diff shows the changed heading.','The diff identifies the changed file.']))
    out.append(view_case('gui-log','history','Show detailed commit messages and statistics.',[key('l')],['Record the northeast approach','Reviewed-by: Trail Team','file.*changed'],['The full commit message includes its explanation and review trailer.','The entry includes changed-file statistics.']))
    out.append(view_case('gui-tree','tree','Browse the files of the latest revision.',[key('t')],['README.md','notes.txt'],['The revision tree lists files and directories.','File sizes and file modes can be inspected.']))
    out.append(view_case('gui-tree-subdirectory','tree','Open docs in the revision tree.',[key('t'),*search('docs'),key('Enter')],['manual.md','checklist.md'],['The docs directory is open.','Both documentation files are listed.']))
    out.append(view_case('gui-blob','tree','Read notes.txt from the latest revision.',[key('t'),*search('notes.txt'),key('Enter')],['oak tree','stone bridge restored'],['The complete notebook file is visible.','The content is from the latest revision.']))
    out.append(view_case('gui-blame','blame','Show who last changed each line of notes.txt.',[],['oak tree','river bank','stone bridge'],['The file lines are annotated with authors.','Different revisions are identified for changed lines.'],args=['blame','notes.txt']))
    out.append(view_case('gui-refs','refs','Show the repository branches and tags.',[key('r')],['main','feature/east','v1.0'],['Local branches are visible.','The release tag is visible.']))
    out.append(view_case('gui-grep','grep','Find tracked lines containing river.',[{'op':'grep','pattern':'river'}],['notes.txt','river bank'],['The matching notebook line is visible.','The result identifies its file and line number.']))
    out.append(view_case('gui-grep-case','grep','Find WATER without regard to letter case.',[{'op':'grep','pattern':'WATER','flags':['-i']}],['Carry water','Bring water'],['Case-insensitive matches are displayed.','Matches from multiple documents are visible.']))
    out.append(view_case('gui-grep-path','grep','Find water only in docs/manual.md.',[{'op':'grep','pattern':'water','paths':['docs/manual.md']}],['manual.md','Carry water'],['The search is restricted to the named file.','The matching line is visible.']))
    out.append(view_case('gui-help','help','Open the built-in keyboard reference.',[key('h')],['Quick reference','bindings'],['The keyboard reference is open.','Action names and their bindings can be read.']))
    out.append(view_case('gui-history-search','search','Find and select the commit Document river access.',search('Document river access'),['Document river access'],['The river-access commit is selected.']))
    out.append(view_case('gui-history-oldest','navigation','Select the oldest commit.',[key('End')],['Start field notebook'],['The oldest commit is selected.']))
    out.append(view_case('gui-goto-tag','navigation','Navigate to the revision tagged v1.0.',[command('goto v1.0')],['Start field notebook'],['The tagged initial revision is selected.']))
    out.append(view_case('gui-split','views','Open the selected commit together with its diff.',[key('Enter')],[r'\[main\]',r'\[diff\]'],['The history and diff are visible together.','The diff belongs to the selected commit.']))
    out.append(view_case('gui-maximize','views','Expand the selected commit diff to the full terminal.',[key('Enter'),key('O')],['northeast','src/guide.py'],['The commit diff fills the main viewing area.']))
    out.append(view_case('gui-tree-recursive','tree','List all revision files recursively, including files under docs and src.',[key('t'),command('set recurse-tree = yes')],['docs/manual.md','src/guide.py'],['Nested documentation files are listed with paths.','The source file is listed with its path.']))
    out.append(view_case('gui-pager','pager','Read the supplied text in the pager.',[],['ALPHA observation','BETA observation'],['The supplied text is displayed.','Both observation sections can be read.'],stdin='ALPHA observation\nA quiet forest.\n\nBETA observation\nA flowing river.\n'))
    longtext='Title: Field report\n'+'\n'.join('Observation %02d: river and oak trees.'%i for i in range(1,61))+'\n'
    out.append(view_case('gui-pager-search','pager','Find Observation 45 in the supplied report.',search('Observation 45'),['Observation 45'],['The requested report line is selected.'],stdin=longtext))
    out.append(view_case('gui-pager-end','navigation','Go to the end of the supplied report.',[key('End')],['Observation 60'],['The last report entry is visible.'],stdin=longtext))
    out.append(view_case('gui-pager-number','navigation','Jump to line 40 of the supplied report.',[command('40')],['Observation 39'],['The requested line is selected.'],stdin=longtext))
    for cid,setting,patterns,accept in [
      ('author-email','main-view-author = email',['bea@example.test'],'Authors are displayed as email addresses.'),
      ('committer','main-view-committer = full',['Jordan Example'],'Committer names are visible.'),
      ('date-custom','main-view-date = custom',['06/01/2024'],'The history displays dates in day/month/year form.'),
      ('ids','main-view-id = yes',[r'\b[0-9a-f]{7}\b'],'Commit identifiers are visible in history entries.'),
      ('numbers','main-view-line-number = yes',[r'(?m)^\s*5'],'History entries show line numbers.'),
      ('reverse','commit-order = reverse',['Start field notebook'],'The history begins with the oldest revision.'),
      ('graph-ascii','line-graphics = ascii',['Merge eastern route'],'The branch and merge graph is readable using text line graphics.'),
      ('references','reference-format = (branch) {tag} [remote]',[r'\(main\)'],'Branch names use the requested reference formatting.'),
    ]:
        extra=[command('set main-view-date-format = "%d/%m/%Y"')] if cid=='date-custom' else []
        goal='Show history dates using the custom format "%d/%m/%Y".' if cid=='date-custom' else 'Set '+setting+'.'
        out.append(view_case('gui-display-'+cid,'display',goal,extra+[command('set '+setting)],patterns,[accept]))
    return out

def stage_episodes():
    out=[]
    kinds=[('regular','notes.txt','oak tree\nriver bank with footpath\nstone bridge upgraded\n'),
           ('unicode','café.txt','Café menu updated.\n'),('space','has space.txt','Changed spaced name.\n'),
           ('nested','docs/manual.md','# Updated walking guide\nCarry water.\n'),
           ('empty','empty.txt','First content.\n'),('new','fresh.txt','A new document.\n'),
           ('new-nested','newdir/page.txt','A nested new document.\n'),
           ('no-newline','end.txt','No trailing newline'),('crlf','windows.txt','first\r\nsecond\r\n'),
           ('tab','tabbed.txt','one\ttwo\tthree\n'),('leading','leading.txt','  indented text\n'),
           ('long','long.txt','A'*300+'\n')]
    for cid,path,text in kinds:
        spec=copy.deepcopy(BASE);spec['worktree']={path:text}
        checks=[point('index',{'kind':'blob','path':path,'expected':text}),point('status',{'kind':'status','path':path})]
        cps=[checkpoint('stage','Stage '+path+'.',[key('s'),*search(re.escape(path)),key('u')],checks,
                        ['The file is shown among staged changes.'] if cid in ('regular','unicode','space','nested','new') else [])]
        gui=bool(cps[0]['front'])
        out.append(episode(('gui-' if gui else '')+'stage-'+cid,'staging',cps,spec,gui=gui))
        spec2=copy.deepcopy(BASE);spec2['index']={path:text}
        cps=[checkpoint('unstage','Unstage '+path+' while preserving its working copy.',
                        [key('s'),*search(re.escape(path)),key('u')],
                        [point('status',{'kind':'status','path':path}),point('worktree',{'kind':'file','path':path})],
                        ['The file is shown as unstaged or untracked.'] if cid in ('regular','unicode','space','nested','new') else [])]
        gui=bool(cps[0]['front'])
        out.append(episode(('gui-' if gui else '')+'unstage-'+cid,'staging',cps,spec2,gui=gui))
    for cid,path in [('regular','notes.txt'),('nested','docs/manual.md'),('unicode','café.txt'),('space','has space.txt')]:
        spec=copy.deepcopy(BASE);spec['worktree']={path:'Temporary replacement.\n'}
        out.append(episode('gui-revert-'+cid,'reverting',[
            checkpoint('revert','Discard the unstaged changes to '+path+'.',
                [key('s'),*search(re.escape(path)),key('!'),key('y')],
                [point('file',{'kind':'file','path':path})],['The file no longer has unstaged changes.'])],spec,gui=True))
    return out

def cli_episodes():
    return [episode('command-line','cli',[
        checkpoint('version','Print the product version.',[],[point('version',{'kind':'cli','option':'--version'})]),
        checkpoint('help','Print command-line usage.',[],[point('help',{'kind':'cli','option':'--help'})]),
    ],BASE),episode('prompt-history','persistence',[
        checkpoint('command','Display the exact message Trail marker 2024.',[command('echo Trail marker 2024')],
                   [point('message',screencheck([r'(?m)^Trail marker 2024$']))]),
        checkpoint('save','Quit normally and save native command history.',[key('Q')],
                   [point('history',{'kind':'history','text':'echo Trail marker 2024'})],depends=['command'])
    ],BASE),view_case('gui-console-message','console','Display the exact message Survey complete.',
                     [command('echo Survey complete')],[r'(?m)^Survey complete$'],['The supplied message is displayed in the application.'])]

def advanced_episodes():
    out=[]
    # Genuine multi-hunk patches distinguish file, hunk, part and single-line staging.
    original=''.join('line %02d\n'%i for i in range(1,41))
    first=original.replace('line 05\n','FIRST ADDED\nline 05\n')
    both=first.replace('line 33\n','SECOND ADDED\nline 33\n')
    spec={'commits':[{'id':'initial','message':'Record forty observations','files':{'observations.txt':original}}],
          'worktree':{'observations.txt':both}}
    for name,operation,selection in [('hunk','u',[key('@')]),('line','1',search('FIRST ADDED')),('part','2',search('FIRST ADDED'))]:
        case=copy.deepcopy(spec)
        if name=='part':
            case['worktree']['observations.txt']=both.replace('line 08\n','NEARBY ADDED\nline 08\n')
            expected=first
            goal='Stage only FIRST ADDED, leaving the nearby NEARBY ADDED and the later SECOND ADDED unstaged.'
            visible=['Only FIRST ADDED is staged.','NEARBY ADDED and SECOND ADDED remain unstaged.']
            remains=['NEARBY ADDED','SECOND ADDED']
        else:
            case['worktree']['observations.txt']=both.replace('FIRST ADDED\n','FIRST ADDED\nANOTHER ADDED\n')
            expected=first.replace('FIRST ADDED\n','FIRST ADDED\nANOTHER ADDED\n') if name=='hunk' else first
            goal=('Stage the first hunk containing FIRST ADDED and ANOTHER ADDED, leaving SECOND ADDED unstaged.' if name=='hunk'
                  else 'Stage only the single FIRST ADDED line, leaving the adjacent ANOTHER ADDED and the later SECOND ADDED unstaged.')
            visible=(['The first hunk is staged.','SECOND ADDED remains unstaged.'] if name=='hunk'
                     else ['Only the requested single line is staged.','The adjacent and later additions remain unstaged.'])
            remains=['SECOND ADDED'] if name=='hunk' else ['ANOTHER ADDED','SECOND ADDED']
        out.append(episode('gui-stage-'+name,'partial-staging',[
            checkpoint('stage',goal,
                [key('s'),*search('observations.txt'),key('Enter'),*selection,key(operation)],
                [point('index',{'kind':'blob','path':'observations.txt','expected':expected}),
                 point('remaining',{'kind':'git','request':{'action':'diff','path':'observations.txt'},'present':[r'^\+'+re.escape(x)+r'$' for x in remains],'absent':[r'^\+FIRST ADDED$']})],
                visible)],case,gui=True))
    staged=copy.deepcopy(spec);staged.pop('worktree');staged['index']={'observations.txt':both}
    out.append(episode('gui-unstage-hunk','partial-staging',[
        checkpoint('unstage','Unstage only the first added observation.',
            [key('s'),*search('observations.txt'),key('Enter'),key('@'),key('u')],
            [point('index',{'kind':'blob','path':'observations.txt','expected':original.replace('line 33\n','SECOND ADDED\nline 33\n')})],
            ['The first addition is removed from the staged patch.','The second addition remains staged.'])],staged,gui=True))
    out.append(episode('gui-revert-hunk','partial-staging',[
        checkpoint('revert','Discard only the first added observation.',
            [key('s'),*search('observations.txt'),key('Enter'),key('@'),key('!'),key('y')],
            [point('file',{'kind':'file','path':'observations.txt','expected':original.replace('line 33\n','SECOND ADDED\nline 33\n')})],
            ['The first addition is discarded.','The second addition remains in the working copy.'])],spec,gui=True))
    for mode,cid,text in [('line','diff-context-zero','Set the diff context to zero.',),('wide','diff-context-wide','Set the diff context to eight lines.',)]:
        value='0' if mode=='line' else '8'
        out.append(view_case('gui-'+cid,'diff',text,[key('s'),*search('observations.txt'),key('Enter'),command('set diff-context = '+value)],
            ['FIRST ADDED']+(['line 12'] if mode=='wide' else ['SECOND ADDED']),['The changed observation is visible.','The requested amount of surrounding context is used.'],spec=spec))
    # Status variants exercise distinct Git entry kinds, not filename-only repetitions.
    for cid,worktree,pattern,description in [
      ('delete',{'docs/manual.md':None},'docs/manual.md','Stage deletion of docs/manual.md.'),
      ('executable',{'run.sh':{'text':'#!/bin/sh\necho north\n','mode':420}},'run.sh','Stage the executable-mode change for run.sh.'),
      ('binary',{'picture.bin':{'base64':'AAECAwQFBgcICQ=='}},'picture.bin','Stage the new binary file picture.bin.'),
      ('symlink',{'notebook-link':{'symlink':'notes.txt'}},'notebook-link','Stage the new notebook-link symbolic link.'),
    ]:
        special=copy.deepcopy(BASE);special['worktree']=worktree
        out.append(episode('gui-stage-kind-'+cid,'staging',[
            checkpoint('stage',description,[key('s'),*search(re.escape(pattern)),key('u')],
                [point('status',{'kind':'status','path':pattern})],['The requested change appears in the staged section.'])],special,gui=True))
    stash=copy.deepcopy(BASE);stash['stashes']=[{'files':{'notes.txt':'Saved notebook work\n'},'message':'Notebook draft'},
                                             {'files':{'fresh.txt':'Unpublished trail guide\n'},'message':'Guide draft'}]
    out.append(view_case('gui-stash-list','stash','Browse the saved work entries.',[key('y')],['Notebook draft','Guide draft'],['Both saved entries are visible.','Their messages distinguish the saved work.'],spec=stash))
    out.append(view_case('gui-stash-diff','stash','Inspect the Guide draft stash.',[key('y'),*search('Guide draft'),key('Enter')],['Unpublished trail guide','fresh.txt'],['The stash diff identifies its new file.','The saved file contents are visible.'],spec=stash))
    for cid,k in [('apply','A'),('pop','P')]:
        out.append(episode('gui-stash-'+cid,'stash',[
            checkpoint(cid,('Apply' if cid=='apply' else 'Pop')+' the Guide draft stash.',
                [key('y'),*search('Guide draft'),key(k),key('y'),key('Enter'),key('s')],
                [point('file',{'kind':'file','path':'fresh.txt','expected':'Unpublished trail guide\n'})],
                ['The saved guide is restored to the working copy.']),
            checkpoint('saved-list','Inspect the remaining saved-work entries.',[key('y')],
                [point('stash',{'kind':'git','request':{'action':'stash'},'present':['Notebook draft']+(['Guide draft'] if cid=='apply' else []),'absent':['Guide draft'] if cid=='pop' else []})],
                ['The Guide draft entry remains available.' if cid=='apply' else 'Only the Notebook draft entry remains.'],depends=[cid])],stash,gui=True))
    out.append(episode('gui-stash-drop','stash',[
        checkpoint('drop','Delete the Guide draft saved-work entry.',[key('y'),*search('Guide draft'),key('!'),key('y'),key('Enter'),key('y')],
                   [point('stash',{'kind':'git','request':{'action':'stash'},'present':['Notebook draft'],'absent':['Guide draft']})],
                   ['The selected saved-work entry is removed.','The other saved-work entry remains available.'])],stash,gui=True))
    out.append(episode('gui-branch-checkout','refs',[
        checkpoint('checkout','Switch the working copy to feature/east.',[key('r'),*search('feature/east'),key('C'),key('y'),key('Enter'),key('s')],
                   [point('file',{'kind':'file','path':'src/guide.py','expected':'def heading():\n    return "north"\n'}),
                    point('branch',screencheck(['feature/east']))],
                   ['The working copy is on feature/east.'])],BASE,gui=True))
    out.append(episode('gui-branch-delete','refs',[
        checkpoint('delete','Delete the local archive branch.',[key('r'),*search('archive'),key('!'),key('y'),key('Enter'),key('r'),key('R')],
                   [point('refs',{'kind':'git','request':{'action':'refs'},'present':['refs/heads/main','refs/heads/feature/east'],'absent':['refs/heads/archive']})],
                   ['The archive branch is removed.','The main and feature branches remain.'])],BASE,gui=True))
    reflog=copy.deepcopy(BASE);reflog['checkout_history']=['archive','feature/east']
    out.append(view_case('gui-reflog','reflog','Browse the checkout history.',[key('L')],['checkout','feature/east'],['Recent branch checkouts are listed.','The history identifies the branches involved.'],spec=reflog))
    note=copy.deepcopy(BASE);note['tags']={'release-2':{'target':'tip','message':'Survey release'}};note['notes']={'tip':'Reviewed by field team'}
    out.append(view_case('gui-annotated-tag','refs','Show the annotated release-2 tag.',[key('r'),*search('release-2')],['release-2'],['The annotated release tag is listed.'],spec=note))
    out.append(view_case('gui-commit-notes','history','Inspect the notes attached to the latest commit.',[key('d')],['Reviewed by field team'],['The commit note is visible with the commit details.'],spec=note))
    for cid,args,patterns,description in [
      ('author',['--author=Bea Meadow'],['Document river access','Update trail heading'],'Show only commits by Bea Meadow.'),
      ('path',['--','src/guide.py'],['Start field notebook','Update trail heading'],'Show history for src/guide.py.'),
      ('range',['v1.0..archive'],['Document river access'],'Show commits after v1.0 through archive.'),
      ('first-parent',['--first-parent'],['Merge eastern route','Update trail heading'],'Show the mainline history using first-parent traversal.'),
    ]:
        out.append(view_case('gui-history-filter-'+cid,'history-filters',description,[],patterns,
                            ['The displayed history respects the requested restriction.'],args=args))
    # Native displays and exports provide further distinct product outputs.
    out.append(episode('export-display','export',[
        checkpoint('export','Save the history display to /outbox/history.txt.',[command('save-display /outbox/history.txt')],
            [point('file',{'kind':'export-display','file':'history.txt','contains':'Update trail heading'})])],BASE))
    out.append(view_case('gui-custom-binding','key-configuration','Bind x in the main view to move-last-line, then use x.',
                         [command('bind main x move-last-line'),key('x')],['Start field notebook'],['The custom binding selects the oldest commit.']))
    out.append(view_case('gui-display-wrap','display','Read the supplied long line with wrapping enabled.',[],['ENDING marker'],
                         ['The long line wraps across rows.','The end of the line is visible without horizontal scrolling.'],config='set wrap-lines = yes',stdin='Long report: '+'oak river '*30+'ENDING marker\n'))
    out.append(view_case('gui-display-resize','views','Resize the terminal to 80 columns and 24 rows while keeping the history readable.',
                         [{'op':'resize','columns':80,'rows':24}],['Update trail heading','Merge eastern route'],
                         ['The terminal adapts to the new size.','The history remains readable.']))
    large=copy.deepcopy(BASE);large['commits'][-1]['files']['large.txt']='x'*4096
    out.append(view_case('gui-tree-size-units','display','Display revision file sizes using units.',[key('t'),command('set tree-view-file-size = units')],['large.txt'],['The 4096-byte file size is expressed using a size unit.'],spec=large))
    out.append(view_case('gui-back-from-tree','navigation','Open docs in the revision tree, then return to the repository root.',
                         [key('t'),*search('docs'),key('Enter'),key(',')],['README.md','notes.txt'],['The revision tree is back at the repository root.']))
    return out

def query_episodes():
    out=[]
    filters=[
      ('count',['--max-count=2'],['Update trail heading','Merge eastern route'],['Start field notebook']),
      ('skip',['--skip=2'],['Start field notebook'],['Update trail heading','Merge eastern route']),
      ('merges',['--merges'],['Merge eastern route'],['Start field notebook','Update trail heading']),
      ('no-merges',['--no-merges'],['Update trail heading','Start field notebook'],['Merge eastern route']),
      ('mainline',['--first-parent'],['Add safety checklist','Merge eastern route'],['Mark eastern viewpoint']),
      ('author',['--author=Ada Rivers'],['Add safety checklist','Start field notebook'],['Update trail heading','Document river access']),
      ('message',['--grep=river'],['Document river access'],['Start field notebook','Update trail heading']),
      ('message-regex',['--grep=^Add'],['Add safety checklist'],['Document river access']),
      ('since',['--since=2024-01-04T00:00:00Z'],['Update trail heading','Mark eastern viewpoint'],['Start field notebook','Document river access']),
      ('until',['--until=2024-01-03T23:59:59Z'],['Add safety checklist','Start field notebook'],['Update trail heading','Mark eastern viewpoint']),
      ('range',['v1.0..archive'],['Document river access'],['Start field notebook','Update trail heading']),
      ('exclude',['main','^archive'],['Merge eastern route','Update trail heading'],['Start field notebook','Document river access']),
      ('one-revision',['--no-walk','v1.0'],['Start field notebook'],['Document river access']),
      ('source-file',['--','src/guide.py'],['Update trail heading','Start field notebook'],['Document river access','Add safety checklist']),
      ('docs-path',['--','docs/'],['Add safety checklist','Start field notebook'],['Update trail heading','Document river access']),
    ]
    cps=[]
    for cid,args,present,absent in filters:
        check=dict(screencheck(present),absent=absent)
        cps.append(checkpoint(cid,'Apply the native revision filter '+str(args)+'.',[{'op':'open','args':args}],[point('history',check)]))
    out.append(episode('history-query-rules','history-filters',cps,BASE))
    # Semantics of grep flags and output grouping, using inputs on which the choices differ.
    grep_spec={'commits':[{'id':'root','message':'Add search examples','files':{
      'words.txt':'river\nRIVER\nriverside\nriver bank\na.b\naxb\n',
      'nested/words.txt':'river\nstone\n','café.txt':'café au lait\n','has space.txt':'space marker\n'}}],
      'worktree':{'words.txt':'river\nRIVER\nriverside\nriver WORKTREE ONLY\na.b\naxb\nWORKTREE ONLY\n'}}
    cases=[('case','RIVER',[],[],['RIVER'],['river bank']),
           ('insensitive','RIVER',['-i'],[],['river WORKTREE ONLY','RIVER'],[]),
           ('word','river',['-w'],[],['river WORKTREE ONLY'],['riverside']),
           ('fixed','a.b',['-F'],[],['a.b'],['axb']),
           ('regex','a.b',['-E'],[],['a.b','axb'],[]),
           ('inverted','river',['-v'],['nested/words.txt'],['stone'],[]),
           ('index','river',['--cached'],['words.txt'],['river bank'],['WORKTREE ONLY']),
           ('index-control','river',[],['words.txt'],['river WORKTREE ONLY'],['river bank']),
           ('working','WORKTREE ONLY',[],[],['WORKTREE ONLY'],[]),
           ('unicode','café',[],[],['café au lait'],[]),
           ('space','space marker',[],['has space.txt'],['space marker','has space.txt'],[])]
    for cid,pattern,flags,paths,present,absent in cases:
        out.append(episode('grep-rule-'+cid,'grep',[
            checkpoint('find','Search with the '+cid+' grep rule.',[{'op':'grep','pattern':pattern,'flags':flags,'paths':paths}],
                       [point('matches',dict(screencheck(present),absent=absent))])],grep_spec))
    # Search navigation and internal actions produce visible state beyond existence of an entry.
    for cid,steps,selected in [
      ('last',[key('End')],'Start field notebook'),
      ('first',[key('End'),key('Home')],'Update trail heading'),
      ('down',[key('Home'),key('j')],'Merge eastern route'),
      ('up',[key('End'),key('k')],'Document river access'),
      ('goto-tag',[command('goto v1.0')],'Start field notebook'),
      ('goto-branch',[command('goto archive')],'Document river access'),
      ('numeric',[command('2')],'Merge eastern route'),
      ('search-forward',search('safety'),'Add safety checklist'),
      ('search-back',[key('End'),key('?'),{'op':'type','text':'safety'},key('Enter')],'Add safety checklist'),
    ]:
        out.append(episode('navigation-rule-'+cid,'navigation',[
            checkpoint('select','Use '+cid+' navigation.',steps,[point('selected',{'kind':'screen','selected':selected})])],BASE))
    # Public variable expansion is checked through echo output, as documented by Tig.
    variables=[('head','main'),('is-inside-work-tree','true')]
    for name,value in variables:
        out.append(episode('repo-variable-'+name,'console',[
            checkpoint('echo','Display the '+name+' repository value.',[command('echo %(repo:'+name+')')],
                       [point('value',screencheck([r'(?m)^'+re.escape(value)+r'$']))])],BASE))
    # These GUI goals cover content and navigation that differ from the simple view openings.
    for cid,goal,steps,patterns,accept in [
      ('older-diff','Inspect the Document river access commit.',search('Document river access')+[key('d')],['river bank with footpath'],['The older commit change is displayed.']),
      ('tag-tree','Read the file tree from the v1.0 revision.',[command('goto v1.0'),key('t')],['README.md','notes.txt'],['The initial revision tree is displayed.']),
      ('tag-blob','Read notes.txt at v1.0.',[command('goto v1.0'),key('t'),*search('notes.txt'),key('Enter')],['river bank','stone bridge'],['The original notebook content is displayed.']),
      ('diff-next','Open a split diff, then advance to the next history entry.',[key('Enter'),key('Down')],['Merge eastern route'],['The selected history entry and its diff advance together.']),
      ('blame-parent','Open blame for notes.txt and inspect the parent history of the restored bridge line.',[key('t'),*search('notes.txt'),key('b'),*search('stone bridge'),key(',')],['stone bridge'],['The blame view shows the earlier version of the selected line.']),
      ('grep-open','Find river, then open the matching notebook line.',[{'op':'grep','pattern':'river'},key('j'),key('Enter')],['river bank with footpath'],['The matching file opens at the relevant line.']),
      ('help-search','Find the key binding for move-last-line in help.',[key('h'),*search('move-last-line')],['move-last-line'],['The requested action is located in the keyboard reference.']),
      ('help-collapse','Collapse the key-binding sections in help.',[key('h'),key('j'),key('Enter')],['Expand all'],['The reference sections are collapsed.']),
      ('search-smart','Use smart-case search to find safety in the history.',[command('set ignore-case = smart-case'),*search('safety')],['Add SAFETY checklist'],['The uppercase safety title is selected by the lowercase search.']),
      ('diff-numbers','Display line numbers alongside a commit diff.',[key('d'),command('set diff-view-line-number = yes')],['src/guide.py'],['Line numbers accompany the diff text.']),
      ('diff-word','View the latest heading change as a word diff.',[key('d'),command('set word-diff = yes')],['northeast','north'],['The changed words are identified within the line.']),
      ('tree-ids','Show object IDs in the revision tree.',[key('t'),command('set tree-view-id = yes')],[r'\b[0-9a-f]{7}\b'],['Tree entries include object identifiers.']),
      ('blame-email','Show blame authors as email addresses.',[key('t'),*search('notes.txt'),key('b'),command('set blame-view-author = email')],['@example.test'],['Blame annotations identify authors by email.']),
      ('tree-sort','Sort the revision tree by author.',[key('t'),command('toggle sort-field'),command('toggle sort-field')],['README.md','notes.txt'],['The revision tree is ordered by author.']),
      ('back-diff','Open the latest commit diff, then return to its history.',[key('Enter'),key('q')],['Update trail heading','Merge eastern route'],['The history regains focus after closing the diff.']),
      ('author-date','Show author dates in the history.',[command('set main-view-date-use-author = yes')],['2024-01-06'],['The latest entry shows its January 6 author date.']),
    ]:
        data=copy.deepcopy(BASE)
        if cid=='author-date':data['commits'][-1]['commit_date']='2024-01-10T12:00:00+0000'
        if cid=='search-smart':data['commits'][2]['message']='Add SAFETY checklist'
        out.append(view_case('gui-detail-'+cid,'view-details',goal,steps,patterns,accept,spec=data))
    out.append(episode('gui-detail-refresh','refresh',[
        checkpoint('refresh','Refresh history to display the newly modified working copy.',[key('R')],
            [point('changes',screencheck(['Unstaged changes']))],['The refreshed history identifies the new unstaged changes.'])],
        BASE,config='set refresh-mode = manual',gui=True,
        setup_extra=[{'op':'place','restart':False,'files':{'notes.txt':'External notebook update\n'}}]))
    return out

def interface_episodes():
    return [episode('gui-mouse-selection','mouse',[
        checkpoint('select','Select the Document river access history entry.',
            [{'op':'click-text','text':'Document river access'}],
            [point('selected',{'kind':'screen','selected':'Document river access'})],
            ['The river-access history entry is selected.'])],BASE,config='set mouse = yes',gui=True),
        episode('configuration-roundtrip','persistence',[
            checkpoint('export','Save a user-configured search policy and key binding.',
                [command('set ignore-case = smart-case'),command('bind main x move-last-line'),EXPORT],
                [point('search',{'kind':'config','name':'ignore-case'}),point('binding',{'kind':'binding','name':'main x'})]),
            checkpoint('import','Reload the saved native configuration and save it again.',
                [{'op':'reload-export','name':'configuration-roundtrip-export.tigrc'},EXPORT],
                [point('search',{'kind':'config','name':'ignore-case'}),point('binding',{'kind':'binding','name':'main x'})],depends=['export']),
            checkpoint('operate','Use the key binding from the reloaded configuration.',[key('x')],
                [point('selection',{'kind':'screen','selected':'Start field notebook'})],depends=['import']),
        ],BASE)]

def validation_episodes():
    defaults=[('commit-order','topo','banana'),('ignore-case','yes','banana'),
              ('ignore-space','all','banana'),('line-graphics','ascii','banana'),
              ('vertical-split','yes','banana'),('refresh-mode','manual','banana'),
              ('tab-size','4','-1')]
    cps=[checkpoint('baseline','Set valid values before testing native validation.',
                    [command('set '+name+' = '+value) for name,value,_ in defaults]+[EXPORT],
                    [point(name,{'kind':'config','name':name}) for name,_,_ in defaults])]
    fallbacks={'commit-order':'auto','ignore-case':'no','ignore-space':'no','line-graphics':'ascii','vertical-split':'horizontal','refresh-mode':'manual','tab-size':'4'}
    for name,value,bad in defaults:
        cps.append(checkpoint(name,'Report the invalid '+name+' value and apply its native fallback behavior.',
                    [{'op':'console-error','command':'set '+name+' = '+bad},EXPORT],
                    [point('result',{'kind':'config','name':name,'expected':[fallbacks[name]]})],depends=['native-validation/baseline/'+name]))
    cps.append(checkpoint('boolean-coercion','Apply the documented false coercion of a non-true boolean value.',
                    [command('set wrap-search = maybe'),EXPORT],[point('false',{'kind':'config','name':'wrap-search'})]))
    w=episode('native-validation','validation',cps,BASE)
    for cp in w['checkpoints']:
        if cp['id'] in fallbacks:cp['assertions'][0]['requires']=['native-validation/baseline/'+cp['id']]
    cherry={'commits':[{'id':'base','message':'Initial routes','files':{'main.txt':'Original main\n','side.txt':'Original side\n'}},
                       {'id':'main','parents':['base'],'message':'Main route update','files':{'main.txt':'Updated main\n'}},
                       {'id':'side','parents':['base'],'message':'Side route correction','files':{'side.txt':'Corrected side\n'}}],
            'refs':{'main':'main','feature':'side'},'head':'main'}
    return [w,episode('cherry-pick','commits',[
        checkpoint('apply','Cherry-pick Side route correction onto main.',
            [*search('Side route correction'),key('C'),key('y'),key('Enter')],
            [point('result',{'kind':'commit-result','subject':'Side route correction','parent':'Main route update','files':{'side.txt':'Corrected side\n'}}),
             point('preserve',{'kind':'file','path':'main.txt','expected':'Updated main\n'})])],cherry,args=['--all'])]

def observable_results(episodes):
    """Attach semantic projections to the user goals that need more than shared text."""
    selected={
        'gui-history-search':'Document river access','gui-history-oldest':'Start field notebook',
        'gui-goto-tag':'Start field notebook','gui-custom-binding':'Start field notebook',
        'gui-detail-search-smart':'Add SAFETY checklist',
    }
    projections={name:{'kind':'screen','selected':subject} for name,subject in selected.items()}
    projections.update({
        'gui-split':{'kind':'linked-commit','subject':'Update trail heading','history':['Merge eastern route','Document river access']},
        'gui-detail-diff-next':{'kind':'linked-commit','subject':'Merge eastern route','history':['Update trail heading','Document river access']},
        'gui-detail-tag-blob':{'kind':'screen-content','present':[r'\boak tree\s*$',r'\briver bank\s*$',r'\bstone bridge\s*$'],'absent':['with footpath','bridge restored']},
        'gui-detail-tag-tree':{'kind':'screen-content','present':['README.md','notes.txt'],'absent':['east.txt','checklist.md']},
        'gui-detail-blame-parent':{'kind':'screen-content','present':[r'\bstone bridge\s*$'],'absent':['bridge restored']},
        'gui-detail-tree-sort':{'kind':'author-order','authors':['Ada Rivers','Bea Meadow','Chen Grove']},
        'gui-detail-grep-open':{'kind':'screen-content','present':['oak tree','river bank with footpath','stone bridge restored']},
        'gui-grep-path':{'kind':'screen-content','present':['docs/manual.md','Carry water'],'absent':['docs/checklist.md','Bring water']},
        'gui-display-reverse':{'kind':'history-set','expected':['Start field notebook','Document river access','Add safety checklist','Mark eastern viewpoint','Merge eastern route','Update trail heading'],'ordered':True},
    })
    for key,subjects in {
        'author':['Document river access','Update trail heading'],
        'path':['Start field notebook','Update trail heading'],
        'range':['Document river access'],
        'first-parent':['Start field notebook','Document river access','Add safety checklist','Merge eastern route','Update trail heading'],
    }.items():projections['gui-history-filter-'+key]={'kind':'history-set','expected':subjects}
    frontend_only={'gui-detail-diff-word','gui-detail-diff-numbers','gui-display-graph-ascii'}
    stage={
        'gui-stage-kind-binary':{'path':'picture.bin','mode':'100644','base64':'AAECAwQFBgcICQ=='},
        'gui-stage-kind-symlink':{'path':'notebook-link','mode':'120000','text':'notes.txt'},
        'gui-stage-kind-executable':{'path':'run.sh','mode':'100644','text':'#!/bin/sh\necho north\n'},
    }
    for w in episodes:
        if w['id'] in projections:
            for a in w['checkpoints'][0]['assertions']:
                if a['channel']=='backend':a['check']=copy.deepcopy(projections[w['id']])
                if a.get('check',{}).get('kind')=='history-set':a['check']['focus_main']=True
        if w['id'] in frontend_only:
            for cp in w['checkpoints']:
                cp['assertions']=[a for a in cp['assertions'] if a['channel']=='frontend']
                for a in cp['assertions']:a.pop('requires',None)
        if w['id'] in stage:
            for a in w['checkpoints'][0]['assertions']:
                if a['channel']=='backend':a['check']=dict(kind='index-entry',**stage[w['id']])
    return episodes

def build():
    import behaviors
    return observable_results(config_episodes()+color_episodes()+binding_episodes()+stage_episodes()+cli_episodes()+browse_episodes()+advanced_episodes()+query_episodes()+interface_episodes()+validation_episodes())+behaviors.build()
