"""Behavioral coverage of documented navigation, Git changes and configuration."""
import base64
import copy
import re
from specification import BASE,EXPORT,checkpoint,command,key,keys,point,search,episode

def native(name,value):return point('result',{'kind':'native','name':name,'expected':value})
def selected(subject):return point('selected',{'kind':'screen','selected':subject})
def visible(present=(),absent=()):return point('content',{'kind':'screen-content','present':list(present),'absent':list(absent)})
def cap(name='text',as_='before'):return {'op':'capture-native','name':name,'as':as_}
def capture_screen():return {'op':'capture','name':'viewport','request':{'op':'screen'}}
def clean_cp(id,goal,steps,checks,*,args=None,stdin=None,config='',spec=BASE):
    prep=[{'op':'configure','text':config}]
    if args is not None or stdin is not None:
        req={'op':'open','args':args or []}
        if stdin is not None:req['stdin']=stdin
        prep.append(req)
    return checkpoint(id,goal,prep+steps,checks)

PAGER='\n'.join(f'Entry {i:03d} '+('needle' if i in (7,23,58,91) else 'NEEDLE' if i==39 else 'ordinary observation') for i in range(1,121))+'\n'

def navigation():
    cps=[]
    cases=[
      ('forward',search('needle'),'Entry 007 needle'),
      ('next',search('needle')+[key('n')],'Entry 023 needle'),
      ('previous',search('needle')+[key('n'),key('N')],'Entry 007 needle'),
      ('backward',[key('End'),key('?'),{'op':'type','text':'needle'},key('Enter')],'Entry 091 needle'),
      ('wrap-forward',[key('End'),*search('needle')],'Entry 007 needle'),
      ('wrap-back',[key('Home'),key('?'),{'op':'type','text':'needle'},key('Enter')],'Entry 091 needle'),
      ('regex',search('Entry (023|058)')+[key('n')],'Entry 058 needle'),
      ('case-sensitive',search('NEEDLE'),'Entry 039 NEEDLE'),
      ('smart-lower',[command('set ignore-case = smart-case'),*search('needle'),key('n'),key('n')],'Entry 039 NEEDLE'),
      ('smart-upper',[command('set ignore-case = smart-case'),*search('NEEDLE')],'Entry 039 NEEDLE'),
      ('ignore-case',[command('set ignore-case = yes'),*search('NEEDLE')],'Entry 007 needle'),
      ('no-wrap-end',[command('set wrap-search = no'),key('End'),*search('needle')],'Entry 120 ordinary observation'),
      ('no-wrap-start',[command('set wrap-search = no'),key('Home'),key('?'),{'op':'type','text':'needle'},key('Enter')],'Entry 001 ordinary observation'),
      ('missing',search('needle')+search('absent-pattern'),'Entry 007 needle'),
      ('invalid-regex',search('needle')+search('['),'Entry 007 needle'),
    ]
    for cid,steps,expected in cases:
        cps.append(clean_cp(cid,'Apply the '+cid+' search rule.',steps,[native('text',expected)],stdin=PAGER))
    out=[episode('behavior-search','search',cps,BASE)]
    cps=[]
    for cid,route,start,delta in [
      ('page-down',key('PageDown'),'1',(20,40)),('page-up',key('PageUp'),'120',(-40,-20)),
      ('half-down',key('Control+d'),'1',(10,25)),('half-up',key('Control+u'),'120',(-25,-10)),
      ('command-page-down',command('move-page-down'),'1',(20,40)),
      ('command-half-up',command('move-half-page-up'),'100',(-25,-10)),
    ]:
        cps.append(clean_cp(cid,'Move by the requested page amount.',[command(start),cap(),route],
                   [point('distance',{'kind':'motion','before':'before','delta':list(delta)})],stdin=PAGER))
    for cid,action,delta in [('line-down','scroll-line-down',(1,1)),('line-up','scroll-line-up',(-1,-1)),
                             ('page-down','scroll-page-down',(20,40)),('page-up','scroll-page-up',(-40,-20)),
                             ('half-down','scroll-half-page-down',(10,25)),('half-up','scroll-half-page-up',(-25,-10))]:
        cps.append(clean_cp('scroll-'+cid,'Scroll the viewport using '+action+'.',
            [command('60'),capture_screen(),command(action)],
            [point('viewport',{'kind':'screen-window','before':'viewport','delta':list(delta)})],stdin=PAGER))
    # Horizontal scrolling reveals different content and restores its first column.
    long='LEFTMARK '+('x'*70)+' MIDDLEMARK '+('y'*90)+' RIGHTMARK\n'
    cps += [clean_cp('horizontal-right','Scroll horizontally to reveal the far-right text.',[key('Right'),key('Right')],
                       [visible(['RIGHTMARK'],['LEFTMARK'])],stdin=long),
            clean_cp('horizontal-first','Restore the first column after horizontal scrolling.',[key('Right'),key('Right'),key('|')],
                       [visible(['LEFTMARK'],['RIGHTMARK'])],stdin=long),
            clean_cp('horizontal-left','Move left after scrolling right.',[command('set horizontal-scroll = 10'),key('Right'),key('Left')],
                       [visible(['LEFTMARK'],['RIGHTMARK'])],stdin=long)]
    out.append(episode('behavior-scrolling','navigation',cps,BASE))
    # Different searchable columns exercise view-specific search behavior.
    contexts=[
       ('tree-file',[key('t'),*search('notes.txt')],'file','notes.txt'),
       ('tree-author',[key('t'),*search('Chen Grove')],'file','east.txt'),
       ('refs-branch',[key('r'),*search('feature/east')],'branch','feature/east'),
       ('refs-tag',[key('r'),*search('v1.0')],'tag','v1.0'),
       ('blob-line',[key('t'),*search('notes.txt'),key('Enter'),*search('river')],'lineno','2'),
       ('blame-text',[key('t'),*search('notes.txt'),key('b'),*search('restored')],'lineno','3'),
       ('blame-author',[key('t'),*search('notes.txt'),key('b'),*search('Bea Meadow')],'lineno','2'),
       ('grep-result',[{'op':'grep','pattern':'water'},*search('Carry water')],'file','docs/manual.md'),
    ]
    out.append(episode('behavior-search-columns','search',[
        clean_cp(cid,'Find the requested value in its native view.',steps,[native(field,value)])
        for cid,steps,field,value in contexts],BASE))
    out.append(episode('behavior-merge-jumps','navigation',[
        clean_cp('next','Jump forward to the next merge.',[command('move-next-merge')],[selected('Merge eastern route')]),
        clean_cp('previous','Jump backward to the previous merge.',[key('End'),command('move-prev-merge')],[selected('Merge eastern route')]),
    ],BASE))
    return out

def index_check(path,text,mode='100644'):return point('index-'+re.sub(r'[^a-zA-Z0-9]+','-',path),{'kind':'index-entry','path':path,'mode':mode,'text':text})

def staging():
    out=[]
    original=''.join('line %02d\n'%i for i in range(1,41))
    modified=original.replace('line 05\n','FIRST\nADJACENT\nline 05\n').replace('line 33\n','SECOND\nline 33\n')
    single=original.replace('line 05\n','ADJACENT\nline 05\n').replace('line 33\n','SECOND\nline 33\n')
    part_modified=original.replace('line 05\n','FIRST\nline 05\n').replace('line 08\n','NEARBY\nline 08\n').replace('line 33\n','SECOND\nline 33\n')
    part_remaining=part_modified.replace('FIRST\n','')
    for cid,content,action,expected in [('line',modified,'1',single),('part',part_modified,'2',part_remaining)]:
        spec={'commits':[{'id':'root','message':'Base','files':{'changes.txt':original,'keep.txt':'keep\n'}}], 'index':{'changes.txt':content}}
        out.append(episode('behavior-unstage-'+cid,'partial-staging',[
            checkpoint('update','Unstage only FIRST using the '+cid+' action.',[key('s'),*search('changes.txt'),key('Enter'),*search('FIRST'),key(action)],
                [index_check('changes.txt',expected),point('worktree',{'kind':'file','path':'changes.txt','expected':content})])],spec))
    # Splitting one hunk changes which part a subsequent hunk update stages.
    spec={'commits':[{'id':'root','message':'Base','files':{'changes.txt':original}}], 'worktree':{'changes.txt':part_modified}}
    out.append(episode('behavior-split-hunk','partial-staging',[
        checkpoint('split','Split the first hunk and stage only its first piece.',[key('s'),*search('changes.txt'),key('Enter'),key('@'),key('\\'),key('u')],
            [index_check('changes.txt',original.replace('line 05\n','FIRST\nline 05\n')),
             point('remaining',{'kind':'git','request':{'action':'diff','path':'changes.txt'},'present':[r'^\+NEARBY$',r'^\+SECOND$'],'absent':[r'^\+FIRST$']})])],spec))
    # Replacement/deletion lines require a different reverse patch from insertions.
    for cid,before,after,pattern in [('delete','alpha\nbeta\ngamma\n','alpha\ngamma\n','^-beta'),
                                    ('replace','alpha\nbeta\ngamma\n','alpha\nBETA\ngamma\n','^\\+BETA'),
                                    ('eof','alpha\nbeta','alpha\nBETA','^\\+BETA')]:
        spec={'commits':[{'id':'root','message':'Base','files':{'file.txt':before}}],'worktree':{'file.txt':after}}
        out.append(episode('behavior-stage-patch-'+cid,'partial-staging',[
            checkpoint('stage','Stage the '+cid+' patch.',[key('s'),*search('file.txt'),key('Enter'),key('u')],
                       [index_check('file.txt',after),point('worktree',{'kind':'file','path':'file.txt','expected':after})])],spec))
    # Two independently changed files make section updates and preservation observable.
    spec={'commits':[{'id':'root','message':'Base','files':{'a.txt':'A\n','b.txt':'B\n','keep.txt':'keep\n'}}],
          'worktree':{'a.txt':'A updated\n','b.txt':'B updated\n','new.txt':'new\n'}}
    out.append(episode('behavior-stage-section','staging',[
        checkpoint('stage','Stage the whole unstaged section.',[key('s'),*search('Changes not staged'),key('u')],
            [index_check('a.txt','A updated\n'),index_check('b.txt','B updated\n'),point('untracked',{'kind':'status','path':'new.txt'})]),
        checkpoint('unstage','Unstage the whole staged section.',[key('Home'),*search('Changes to be committed'),key('u')],
            [index_check('a.txt','A\n'),index_check('b.txt','B\n')],depends=['stage']),
        checkpoint('untracked','Stage the untracked section.',[key('Home'),*search('Untracked files'),key('u')],
            [index_check('new.txt','new\n')],depends=['unstage'])],spec))
    # Cancel a destructive action, then prove the same route can perform it.
    spec=copy.deepcopy(BASE);spec['worktree']={'notes.txt':'temporary\n','keep-new.txt':'keep-new\n'}
    out.append(episode('behavior-revert-confirmation','reverting',[
        checkpoint('cancel','Cancel reverting notes.txt.',[key('s'),*search('notes.txt'),key('!'),key('n')],
            [point('retained',{'kind':'file','path':'notes.txt','expected':'temporary\n'})]),
        checkpoint('confirm','Confirm reverting notes.txt.',[*search('notes.txt'),key('!'),key('y')],
            [point('restored',{'kind':'file','path':'notes.txt','expected':'oak tree\nriver bank with footpath\nstone bridge restored\n'}),
             point('unrelated',{'kind':'file','path':'keep-new.txt','expected':'keep-new\n'})],depends=['cancel'])],spec))
    # Whole-file operations for deletion, executable bits, binary bytes and symlink targets.
    cases=[('deleted','gone.txt',None,None),
           ('executable','run.sh',{'text':'run\n','mode':493},'100755'),
           ('binary','data.bin',{'base64':'AAH/AEJBU0U='},'100644'),
           ('link','link',{'symlink':'target.txt'},'120000')]
    for cid,path,value,mode in cases:
        base_files={'target.txt':'target\n','keep.txt':'keep\n'}
        if cid=='deleted':base_files[path]='old\n'
        elif cid=='executable':base_files[path]='run\n'
        elif cid=='binary':base_files[path]={'base64':'AAH/AE9MRA=='}
        else:base_files['other.txt']='other\n';base_files[path]={'symlink':'other.txt'}
        spec={'commits':[{'id':'root','message':'Base','files':base_files}],'worktree':{path:value}}
        if cid=='deleted':check=point('index',{'kind':'index-entry','path':path,'absent':True})
        elif cid=='binary':check=point('index',{'kind':'index-entry','path':path,'mode':mode,'base64':value['base64']})
        else:check=index_check(path,value.get('text',value.get('symlink')),mode)
        out.append(episode('behavior-stage-type-'+cid,'staging',[
            checkpoint('stage','Stage the native '+cid+' change.',[key('s'),*search(re.escape(path)),key('u')],
                       [check,index_check('keep.txt','keep\n')])],spec))
    # Stash operations preserve unrelated tracked edits and report merge conflicts.
    stash={'commits':[{'id':'root','message':'Base','files':{'a.txt':'base a\n','b.txt':'base b\n'}}],
           'stashes':[{'files':{'a.txt':'stashed a\n'},'message':'A work'}], 'worktree':{'b.txt':'unrelated b\n'}}
    out.append(episode('behavior-stash-preserve','stash',[
        checkpoint('apply','Apply saved A work while keeping the unrelated B edit.',[key('y'),key('A'),key('y'),key('Enter')],
            [point('applied',{'kind':'file','path':'a.txt','expected':'stashed a\n'}),
             point('unrelated',{'kind':'file','path':'b.txt','expected':'unrelated b\n'}),
             point('retained',{'kind':'git','request':{'action':'stash'},'present':['A work']})])],stash))
    return out

def history():
    out=[]
    for cid,flag,present,absent in [
      ('branches','--branches',['main','archive','feature/east'],['origin/main','v1.0']),
      ('tags','--tags',['v1.0'],['main','archive','feature/east','origin/main']),
      ('remotes','--remotes',['origin/main'],['archive','feature/east','v1.0']),
    ]:
        out.append(episode('behavior-refs-'+cid,'refs',[
            checkpoint('filter','Restrict refs to '+cid+'.',[],[point('refs',{'kind':'ref-set','present':present,'absent':absent})])],BASE,args=['refs',flag]))
    # A commit graph with deliberately different author and committer order.
    graph={'commits':[
      {'id':'base','message':'Graph root','date':'2024-01-01T12:00:00+0000','files':{'file name.txt':'base\n','unchanged.txt':'keep\n'}},
      {'id':'main1','message':'Main alpha','parents':['base'],'author':'Ada','committer':'Cora','date':'2024-01-07T12:00:00+0000','commit_date':'2024-01-02T12:00:00+0000','files':{'file name.txt':'main\n'}},
      {'id':'side1','message':'Side beta','parents':['base'],'author':'Bea','committer':'Dara','date':'2024-01-04T12:00:00+0000','commit_date':'2024-01-03T12:00:00+0000','files':{'side.txt':'side\n'}},
      {'id':'side2','message':'Side gamma','parents':['side1'],'author':'Bea','committer':'Dara','date':'2024-01-05T12:00:00+0000','commit_date':'2024-01-04T12:00:00+0000','files':{'side.txt':'new side\n'}},
      {'id':'merge','message':'Graph merge','parents':['main1','side2'],'author':'Ada','committer':'Cora','date':'2024-01-06T12:00:00+0000','commit_date':'2024-01-08T12:00:00+0000','files':{'side.txt':'new side\n'}},
      {'id':'tip','message':'Main delta','author':'Bea','committer':'Cora','date':'2024-01-09T12:00:00+0000','commit_date':'2024-01-10T12:00:00+0000','files':{'file name.txt':'tip\n'}},
    ],'refs':{'main':'tip','side':'side2','refs/tags/root':'base','refs/remotes/origin/main':'main1'},'head':'main'}
    queries=[
      ('committer',['--committer=Dara'],['Side gamma','Side beta']),
      ('author-and-limit',['--author=Bea','--max-count=2'],['Main delta','Side gamma']),
      ('path-space',['--','file name.txt'],['Main delta','Main alpha','Graph root']),
      ('range-path',['root..main','--','file name.txt'],['Main delta','Main alpha']),
      ('range-author',['root..main','--author=Ada'],['Graph merge','Main alpha']),
      ('date-window',['--since=2024-01-03T00:00:00Z','--until=2024-01-08T23:59:59Z'],['Graph merge','Side gamma','Side beta']),
      ('skip-limit',['--skip=1','--max-count=2'],['Graph merge','Side gamma']),
      ('symmetric',['main...side'],['Main delta','Graph merge','Main alpha']),
      ('exclude-main-parent',['side','^origin/main'],['Side gamma','Side beta']),
      ('range-first-parent',['root..main','--first-parent'],['Main delta','Graph merge','Main alpha']),
      ('merge-limit',['--merges','--max-count=1'],['Graph merge']),
      ('no-merges-author',['--no-merges','--author=Ada'],['Main alpha']),
    ]
    out.append(episode('behavior-history-combinations','history-filters',[
        checkpoint(cid,'Apply the combined native history query.',[{'op':'open','args':args}],
                   [point('commits',{'kind':'history-set','expected':expect})]) for cid,args,expect in queries],graph))
    for cid,args,expect in [
      ('date-order',['--date-order'],['Main delta','Graph merge','Side gamma','Side beta','Main alpha','Graph root']),
      ('author-date-order',['--author-date-order'],['Main delta','Graph merge','Main alpha','Side gamma','Side beta','Graph root']),
      ('reverse',['--reverse'],['Graph root','Main alpha','Side beta','Side gamma','Graph merge','Main delta']),
    ]:
        out.append(episode('behavior-history-order-'+cid,'history',[
            checkpoint('order','Use '+cid+' traversal.',[],[point('order',{'kind':'history-set','expected':expect,'ordered':True})])],graph,args=args))
    reflog=copy.deepcopy(BASE);reflog['checkout_history']=['archive','feature/east']
    for cid,press,target in [('checkout','C','Mark eastern viewpoint'),('reset','!','Document river access')]:
        query='moving from archive to feature/east' if cid=='checkout' else 'moving from main to archive'
        path='east.txt' if cid=='checkout' else 'notes.txt'
        content='Eastern viewpoint\n' if cid=='checkout' else 'oak tree\nriver bank with footpath\nstone bridge\n'
        out.append(episode('behavior-reflog-'+cid,'reflog',[
            checkpoint('operate','Apply the selected reflog '+cid+' action.',[key('L'),*search(query),key(press),key('y'),key('Enter')],
                [point('head',{'kind':'head-subject','expected':target}),point('file',{'kind':'file','path':path,'expected':content}),point('clean',{'kind':'clean'})])],reflog))
    # Browsing variables are native outputs, not debug-memory inspection.
    variables=[
       ('main-head',[],{'name':'head','expected':'HEAD'}),
       ('selected-commit',[key('End')],{'name':'commit','subject':'Start field notebook'}),
       ('tree-file',[key('t'),*search('notes.txt')],{'name':'file','expected':'notes.txt'}),
       ('tree-blob',[key('t'),*search('notes.txt')],{'name':'blob','index_blob':'notes.txt'}),
       ('tree-directory',[key('t'),*search('docs'),key('Enter')],{'name':'directory','expected':'docs/'}),
       ('blob-line',[key('t'),*search('notes.txt'),key('Enter'),key('j')],{'name':'lineno','expected':'2'}),
       ('blob-text',[key('t'),*search('notes.txt'),key('Enter'),key('End')],{'name':'text','expected':'stone bridge restored'}),
       ('refs-name',[key('r'),*search('feature/east')],{'name':'refname','expected':'feature/east'}),
       ('refs-branch',[key('r'),*search('archive')],{'name':'branch','expected':'archive'}),
       ('refs-tag',[key('r'),*search('v1.0')],{'name':'tag','expected':'v1.0'}),
       ('blame-line',[key('t'),*search('notes.txt'),key('b'),key('End')],{'name':'lineno','expected':'3'}),
       ('blame-text',[key('t'),*search('notes.txt'),key('b'),key('Home')],{'name':'text','expected':'oak tree'}),
    ]
    out.append(episode('behavior-context-variables','console',[
        clean_cp(cid,'Inspect the documented '+check['name']+' browsing value.',steps,[point('value',dict(kind='native',**check))])
        for cid,steps,check in variables],BASE))
    return out

def stdin_modes():
    out=[]
    for cid,args,subjects,expect,raw in [
      ('main-one',['--no-walk','--stdin'],['Document river access'],['Document river access'],False),
      ('main-two',['--no-walk','--stdin'],['Update trail heading','Start field notebook'],['Update trail heading','Start field notebook'],False),
      ('main-history',['--stdin'],['Document river access'],['Document river access','Start field notebook'],False),
      ('main-count',['--stdin','--max-count=1'],['Update trail heading'],['Update trail heading'],False),
      ('raw',['--pretty=raw'],['Add safety checklist','Document river access'],['Add safety checklist','Document river access'],True),
    ]:
        out.append(episode('behavior-stdin-'+cid,'pager',[
            checkpoint('read','Load native commit input using '+cid+'.',
                [{'op':'open-commits','args':args,'subjects':subjects,'raw':raw}],
                [point('commits',{'kind':'history-set','expected':expect})])],BASE))
    for cid,subjects,present,absent in [
      ('old',['Document river access'],['river bank with footpath'],['stone bridge restored']),
      ('new',['Update trail heading'],['northeast','stone bridge restored'],[]),
    ]:
        out.append(episode('behavior-stdin-show-'+cid,'pager',[
            checkpoint('read','Load commit IDs into the native show pager.',
                       [{'op':'open-commits','args':['show','--stdin'],'subjects':subjects}],
                       [visible(present,absent)])],BASE))
    return out

def configuration_behaviors():
    out=[]
    # Textual configuration forms must change behavior, not only serialize a value.
    configs=[
      ('append','set main-options = --no-merges\nset main-options += --author=Ada',[],['Start field notebook','Add safety checklist'],['Update trail heading','Document river access','Merge eastern route']),
      ('continuation','set main-options = --no-merges \\\n --author=Bea',[],['Update trail heading','Document river access'],['Start field notebook','Merge eastern route']),
      ('comment','set main-options = --author=Chen # explanatory comment',[],['Mark eastern viewpoint'],['Start field notebook','Update trail heading']),
      ('quoted','set main-view-date = custom\nset main-view-date-format = "%d %b %Y"',[],['06 Jan 2024','01 Jan 2024'],[]),
      ('last-assignment','set main-options = --author=Ada\nset main-options = --author=Chen',[],['Mark eastern viewpoint'],['Add safety checklist']),
    ]
    for cid,config,steps,present,absent in configs:
        out.append(episode('behavior-config-format-'+cid,'configuration-format',[
            checkpoint('effect','Load the '+cid+' native configuration syntax.',steps,[visible(present,absent)])],BASE,config=config))
    binds=[
      ('generic','bind generic x move-last-line',[key('x')],'Start field notebook'),
      ('view-priority','bind generic x move-last-line\nbind main x move-down',[key('x')],'Merge eastern route'),
      ('last-binding','bind main x move-last-line\nbind main x move-down',[key('x')],'Merge eastern route'),
      ('none','bind main x move-last-line\nbind generic x none',[key('x')],'Update trail heading'),
      ('case-alias','bind main x MOVE-LAST-LINE',[key('x')],'Start field notebook'),
      ('symbolic-key','bind main <PgDown> move-last-line',[key('PageDown')],'Start field notebook'),
      ('underscore-alias','bind main x move_last_line',[key('x')],'Start field notebook'),
      ('unicode-key','bind main ø move-last-line',[key('ø')],'Start field notebook'),
      ('function-key','bind main <F2> move-last-line',[key('F2')],'Start field notebook'),
      ('control-key','bind main <Ctrl-f> move-last-line',[key('Control+f')],'Start field notebook'),
      ('internal','bind main x :goto archive',[key('x')],'Document river access'),
    ]
    for cid,config,steps,expected in binds:
        out.append(episode('behavior-bind-'+cid,'key-configuration',[
            checkpoint('operate','Execute the '+cid+' binding.',steps,[selected(expected)])],BASE,config=config))
    out.append(episode('behavior-search-map','key-configuration',[
        checkpoint('search-key','Use the search-specific binding in the native file finder.',
            [key('f'),{'op':'type','text':'.txt'},key('x'),key('Enter')],[native('file','empty.txt')])],BASE,
            config='bind search x find-next'))
    for cid,config,steps,expected in [
      ('focus-parent','set focus-child = no',[key('Enter'),key('j')],'Merge eastern route'),
      ('focus-child','set focus-child = yes',[key('Enter'),key('j')],'Update trail heading'),
    ]:
        out.append(episode('behavior-'+cid,'views',[
            checkpoint('focus','Verify which view receives cursor movement.',steps,[selected(expected)])],BASE,config=config))
    for cid,setting in [('send-enter','yes'),('keep-parent','no')]:
        out.append(episode('behavior-'+cid,'views',[
            checkpoint('enter','Apply the send-child-enter setting.',[key('Enter'),key('Enter'),key('Tab')],
                [point('text',{'kind':'native','name':'text','pattern':r'^Refs:.*main' if setting=='yes' else r'^commit [0-9a-f]{40}$'})])],BASE,config='set focus-child = no\nset send-child-enter = '+setting))
    # Actual filtering with mixed data: every setting changes visible product output.
    dirty=copy.deepcopy(BASE);dirty['index']={'notes.txt':'staged notes\n'};dirty['worktree']={'notes.txt':'working notes\n','fresh.txt':'fresh\n','newdir/item.txt':'nested\n'}
    cases=[
      ('hide-changes','set show-changes = no',[],['Update trail heading'],['Staged changes','Unstaged changes']),
      ('hide-untracked-main','set show-untracked = no',[],['Unstaged changes'],['Untracked changes']),
      ('hide-untracked-status','set status-show-untracked-files = no',[key('s')],['notes.txt'],['fresh.txt','newdir/item.txt']),
      ('collapse-untracked','set status-show-untracked-dirs = no',[key('s')],['newdir/','fresh.txt'],['newdir/item.txt']),
    ]
    for cid,config,steps,present,absent in cases:
        checks=[selected('Update trail heading')] if cid=='start-head' else [visible(present,absent)]
        out.append(episode('behavior-setting-'+cid,'configuration-effects',[
            checkpoint('effect','Apply '+cid+' to the prepared dirty repository.',steps,checks)],dirty,config=config))
    filters=[
      ('file-off',['--','src/guide.py'],'toggle file-filter',['Document river access','Add safety checklist']),
      ('file-on',['--','src/guide.py'],'toggle file-filter',['Update trail heading','Start field notebook']),
      ('rev-off',['v1.0..archive'],'toggle rev-filter',['Update trail heading','Start field notebook']),
      ('rev-on',['v1.0..archive'],'toggle rev-filter',['Document river access']),
    ]
    for cid,args,cmd,expect in filters:
        steps=[command(cmd)]*(2 if cid.endswith('-on') else 1)
        checks=[point('history',{'kind':'history-set','expected':expect})] if cid.endswith('-on') else [visible(expect)]
        out.append(episode('behavior-filter-'+cid,'history-filters',[
            checkpoint('toggle','Toggle the native '+cid+' restriction.',steps,checks)],BASE,args=args))
    # Diff whitespace settings: positive content in the patch and a disappearing whitespace-only hunk.
    before='alpha = one\nunchanged\nlast\n';after='alpha  =  one\nunchanged\nLAST\n'
    spec={'commits':[{'id':'base','message':'Base','files':{'space.txt':before}},
                     {'id':'tip','message':'Whitespace and content','files':{'space.txt':after}}]}
    for cid,value,absent in [('all','all',[r'^\+alpha',r'^-alpha']),('some','some',[r'^\+alpha',r'^-alpha'])]:
        out.append(episode('behavior-whitespace-'+cid,'diff',[
            checkpoint('filter','Ignore the requested whitespace differences.',[key('d'),command('set ignore-space = '+value)],
                       [visible([r'^\+LAST'],absent)])],spec))
    mail=copy.deepcopy(BASE);mail['commits'][-1]['files']['.mailmap']='Canonical Bea <canonical@example.test> Bea Meadow <bea@example.test>\n'
    for cid,value,present,absent in [('on','yes',['Canonical Bea'],['Bea Meadow']),('off','no',['Bea Meadow'],['Canonical Bea'])]:
        out.append(episode('behavior-mailmap-'+cid,'configuration-effects',[
            checkpoint('names','Apply mailmap '+cid+'.',[],[visible(present,absent)])],mail,config='set mailmap = '+value))
    out.append(episode('behavior-periodic-refresh','refresh',[
        checkpoint('external','Observe a new file through periodic refresh.',
            [{'op':'place','restart':False,'files':{'new.txt':'new\n'}},
             {'op':'await-screen','present':['new.txt'],'timeout':10}],
            [visible(['new.txt'])])],BASE,args=['status'],config='set refresh-mode = periodic\nset refresh-interval = 1'))
    out.append(episode('behavior-close-no-quit','views',[
        checkpoint('close','Close the only view without exiting the application.',[command('view-close-no-quit')],
            [visible(['Update trail heading'])])],BASE))
    # A process restart loses unsaved settings; persisted user configuration wins again.
    out.append(episode('behavior-config-precedence','configuration-effects',[
        checkpoint('runtime','Override the saved user configuration in memory.',[command('set main-options = --author=Chen')],
            [point('filter',{'kind':'history-set','expected':['Mark eastern viewpoint']})]),
        checkpoint('restart','Reload the saved user setting after restart.',[{'op':'restart'}],
            [point('filter',{'kind':'history-set','expected':['Add safety checklist','Start field notebook']})],depends=['runtime'])],BASE,config='set main-options = --author=Ada'))
    return out

def git_configuration():
    out=[]
    cases=[
      ('history',{'tig.main-options':'--author=Bea'},[],[point('history',{'kind':'history-set','expected':['Update trail heading','Document river access']})]),
      ('author-format',{'tig.main-view-author':'email'},[],[visible(['bea@example.test','ada@example.test'],['Bea Meadow'])]),
      ('binding',{'tig.bind.main':'x move-last-line'},[key('x')],[selected('Start field notebook')]),
      ('binding-multi',{'tig.bind.main':['x move-last-line','z move-first-line']},[key('x'),key('z')],[selected('Update trail heading')]),
      ('internal-binding',{'tig.bind.main':'x :goto archive'},[key('x')],[selected('Document river access')]),
      ('search',{'tig.ignore-case':'yes'},search('SAFETY'),[selected('Add safety checklist')]),
      ('tree-recursive',{'tig.recurse-tree':'yes'},[key('t')],[visible(['docs/manual.md','src/guide.py'])]),
      ('color',{'tig.color.cursor':'yellow default underline bold'},[EXPORT],[point('color',{'kind':'color','name':'cursor'})]),
      ('abbrev',{'core.abbrev':'12'},[command('set main-view-id = yes')],[visible([r'\b[0-9a-f]{12}\b'])]),
      ('encoding',{'gui.encoding':'ISO-8859-1'},[key('t'),*search('latin.txt'),key('Enter')],[visible(['café'])]),
    ]
    for cid,config,steps,checks in cases:
        spec=copy.deepcopy(BASE);spec['config']=config
        if cid=='encoding':spec['commits'][-1]['files']['latin.txt']={'base64':base64.b64encode(b'caf\xe9\n').decode()}
        out.append(episode('behavior-git-config-'+cid,'git-configuration',[
            checkpoint('effect','Load safe native Tig Git configuration.',steps,checks)],spec))
    spec=copy.deepcopy(BASE);spec['config']={'tig.main-options':'--author=Chen'}
    out.append(episode('behavior-git-user-priority','git-configuration',[
        checkpoint('effect','Resolve Git and user configuration precedence.',[],
            [point('filter',{'kind':'history-set','expected':['Mark eastern viewpoint']})])],spec,config='set main-options = --author=Ada'))
    return out

def persistence_and_boundaries():
    out=[]
    out.append(episode('behavior-history-reload','persistence',[
        checkpoint('save','Record search and command history and quit normally.',
            [*search('river'),command('echo saved marker'),key('Q')],
            [point('history',{'kind':'history-lines','present':['river','echo saved marker']})]),
        checkpoint('reload','Use the reloaded last search expression.',
            [{'op':'restart'},command('echo saved marker'),key('Q'),{'op':'restart'},*search('safety'),key('Q'),{'op':'restart'},key('n')],
            [selected('Add safety checklist')],depends=['save'])],BASE))
    out.append(episode('behavior-history-limit','persistence',[
        checkpoint('truncate','Persist only the three newest unique commands.',
            [command('echo '+x) for x in ('alpha','bravo','charlie','delta','echo')]+[key('Q')],
            [point('history',{'kind':'history-lines','limit':3,'present':['echo charlie','echo delta','echo echo'],'absent':['echo alpha','echo bravo']})])],BASE,config='set history-size = 3'))
    out.append(episode('behavior-history-deduplicate','persistence',[
        checkpoint('unique','Keep the most recent occurrence of repeated history entries.',
            [command('echo '+x) for x in ('alpha','bravo','alpha')]+[key('Q')],
            [point('history',{'kind':'history-lines','expected':['echo bravo','echo alpha'],'compare_lines':True})])],BASE))
    for cid,button,delta in [('down','wheel-down',(3,3)),('up','wheel-up',(-3,-3))]:
        out.append(episode('behavior-mouse-wheel-'+cid,'mouse',[
            checkpoint('wheel','Move the selected line with the mouse wheel.',
                [command('60'),cap(),{'op':'mouse','row':10,'column':10,'button':button}],
                [point('motion',{'kind':'motion','before':'before','delta':list(delta)})])],BASE,
                config='set mouse = yes\nset mouse-wheel-cursor = yes\nset mouse-scroll = 3',stdin=PAGER))
    # Find-next/find-prev in a real history, including distinct author/message fields.
    many=copy.deepcopy(BASE)
    for cid,steps,expect in [
      ('author-next',search('Bea Meadow')+[key('n')],'Update trail heading'),
      ('author-prev',search('Bea Meadow')+[key('N')],'Update trail heading'),
      ('message-next',search('route')+[key('n')],'Merge eastern route'),
      ('no-match',search('Document river access')+search('UNMATCHABLE'),'Document river access'),
    ]:
        out.append(episode('behavior-main-search-'+cid,'search',[
            checkpoint('select','Apply the history '+cid+' search rule.',steps,[selected(expect)])],many))
    # Close/back behavior retains navigation state in a directory tree.
    out.append(episode('behavior-tree-back','navigation',[
        checkpoint('back','Return from a nested directory using the previous-state action.',
            [key('t'),*search('docs'),key('Enter'),key('<')],[visible(['README.md','notes.txt'],['Directory path /docs/'])])],BASE))
    out.append(episode('behavior-blame-back','blame',[
        checkpoint('back','Return to the newer blame after visiting its parent.',
            [key('t'),*search('notes.txt'),key('b'),*search('stone bridge'),key(','),key('<')],
            [visible(['stone bridge restored'])])],BASE))
    # Search cancellation must leave a known selection; a later successful action is its companion.
    out.append(episode('behavior-search-cancel','search',[
        checkpoint('cancel','Cancel a pending search without executing it.',
            [key('End'),key('/'),{'op':'type','text':'Update trail'},key('Control+c')],[selected('Start field notebook')]),
        checkpoint('active','Perform the same search normally.',search('Update trail'),[selected('Update trail heading')],depends=['cancel'])],BASE))
    # User configuration affects the next process; a runtime edit is not silently persisted.
    out.append(episode('behavior-binding-restart','persistence',[
        checkpoint('in-memory','Override a configured key only in the running process.',
            [command('bind main x move-down'),key('x')],[selected('Merge eastern route')]),
        checkpoint('reload','Recover the configured binding after restart.',[{'op':'restart'},key('x')],[selected('Start field notebook')],depends=['in-memory'])],
        BASE,config='bind main x move-last-line'))
    # Contextual stash variables and status line values use the normal documented echo surface.
    stash=copy.deepcopy(BASE);stash['stashes']=[{'files':{'notes.txt':'saved\n'},'message':'Saved notes'}]
    out.append(episode('behavior-stash-variable','console',[
        checkpoint('select','Read the selected stash identity.',[key('y')],[native('stash','stash@{0}')])],stash))
    out.append(episode('behavior-empty-grep','grep',[
        checkpoint('positive','Find an existing repository line.',[{'op':'grep','pattern':'river'}],[visible(['river bank'])]),
        checkpoint('missing','Report that a new search has no matching lines.',[{'op':'grep','pattern':'UNMATCHABLE'}],
                   [visible(['No matches found'],['river bank'])],depends=['positive'])],BASE))
    return out

def remaining_effects():
    out=[]
    # Relative-time presentation is checked semantically, not by exact spacing.
    for mode,pattern in [('relative',r'\b(?:months?|weeks?)\b'),('relative-compact',r'\b\d+[MW]\b')]:
        out.append(episode('behavior-relative-date-'+mode,'configuration-effects',[
            checkpoint('display','Use the native relative date representation.',
                       [command('set main-view-date = '+mode)],[visible([pattern],['2024-01-06'])])],BASE))
    # Switching line-number rendering and tab expansion changes displayed data columns.
    for size in [4,8]:
        out.append(episode('behavior-tabs-'+str(size),'pager',[
            checkpoint('expand','Expand a tab using the configured stop.',[],
                       [visible([r'(?m)^a'+r' {'+str(size-1)+r'}b\s*$'])])],BASE,
            config='set tab-size = '+str(size),stdin='a\tb\n'))
    # Restart, parent focus and linked child changes remain valid in a vertical split.
    out.append(episode('behavior-vertical-focus','views',[
        checkpoint('linked','Advance a linked revision in a vertical split.',[key('Enter'),key('Down')],
                   [point('linked',{'kind':'linked-commit','subject':'Merge eastern route','history':['Add safety checklist']})])],BASE,config='set vertical-split = yes'))
    # Blame traversal gives context-specific line and revision state after back/parent.
    out.append(episode('behavior-blame-parent-state','blame',[
        checkpoint('parent','Follow the restored bridge line to its parent version.',
                   [key('t'),*search('notes.txt'),key('b'),*search('stone bridge'),key(',')],
                   [native('text','stone bridge'),point('commit',{'kind':'native','name':'commit','subject':'Start field notebook'})])],BASE))
    # Decreasing/increasing diff context changes actual omitted/retained neighboring lines.
    text=''.join('context %02d\n'%i for i in range(1,21));modified=text.replace('context 10','CHANGED')
    spec={'commits':[{'id':'root','message':'Base','files':{'context.txt':text}},
                     {'id':'tip','message':'One change','files':{'context.txt':modified}}]}
    out.append(episode('behavior-diff-context-keys','diff',[
        checkpoint('narrow','Reduce diff context with the native bracket binding.',[key('d'),command('set diff-context = 1'),key('[')],
            [visible(['CHANGED'],[r'^ context 09$',r'^ context 11$'])]),
        checkpoint('wide','Increase context using the matching native binding.',[key(']')],
            [visible(['CHANGED','context 09','context 11'])],depends=['narrow'])],spec))
    # Staging an unborn repository is outside Tig's meaningful initial repository contract;
    # an empty commit and a newly tracked file exercise the applicable root case.
    root={'commits':[{'id':'root','message':'Empty baseline','files':{}}],'worktree':{'new.txt':'new\n'}}
    out.append(episode('behavior-root-add','staging',[
        checkpoint('stage','Stage a first file after an empty baseline commit.',[key('s'),*search('new.txt'),key('u')],
            [index_check('new.txt','new\n')])],root))
    # Index-only and worktree-only changes to the same file must remain separate.
    spec={'commits':[{'id':'root','message':'Base','files':{'mixed.txt':'base\n'}}],
          'index':{'mixed.txt':'index\n'},'worktree':{'mixed.txt':'worktree\n'}}
    out.append(episode('behavior-mixed-index-worktree','staging',[
        checkpoint('unstage','Unstage the index version without discarding the independent working version.',
                   [key('s'),*search('mixed.txt'),key('u')],
                   [index_check('mixed.txt','base\n'),point('worktree',{'kind':'file','path':'mixed.txt','expected':'worktree\n'})])],spec))
    historical=copy.deepcopy(BASE);historical['head']='archive'
    out.append(episode('behavior-start-on-head','navigation',[
        checkpoint('startup','Start on the checked-out historical branch while displaying all refs.',[],[selected('Document river access')])],
        historical,args=['--all'],config='set start-on-head = yes'))
    out.append(episode('behavior-color-normal','color-configuration',[
        checkpoint('flags','Treat normal as the zero flag when combined with native attributes.',
            [command('color cursor cyan red bold normal underline'),EXPORT],[point('rule',{'kind':'color','name':'cursor'})]),
        checkpoint('replace','Clear the previous attributes by replacing the rule with normal only.',
            [command('color cursor cyan red normal'),EXPORT],[point('rule',{'kind':'color','name':'cursor'})],depends=['flags'])],BASE))
    return out

def build():return navigation()+staging()+history()+stdin_modes()+configuration_behaviors()+git_configuration()+persistence_and_boundaries()+remaining_effects()
