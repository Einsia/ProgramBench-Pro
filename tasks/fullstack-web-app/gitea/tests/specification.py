"""Reviewed user goals, acceptance conditions, public setup and program checks of the GUI episodes.

Reference recipes implement these specifications. Goals are authored here and
are never produced by translating a recorded click trace. Setup items are
unscored public preparation with ids (any success status); every checkpoint of
a GUI episode needs them. A point that only verifies a rejection or an
unavailable view names, in `requires`, a positive point of the same episode
that proves the feature exists.
"""
import base64
import hashlib
from harness import CREDS, blob_sha


def api(name,method,path,body=None,actor='alice',save=None):
    return {'id':name,'method':method,'path':path,'actor':actor,'body':body,'save':save}


def repo(name='workbench',private=False,owner='alice',extra=None):
    return api('repository','POST','user/repos',{'name':name,'auto_init':True,'private':private,**(extra or {})},owner,'repository')


def fixture(name):
    return {'id':name,'fixture':name}


def read(path,fields=(),expected=None,actor='alice',status=200,where=None,save=None,collection=False):
    return {'request':{'method':'GET','path':path,'actor':actor,'body':None,'status':status,'save':save},
            'fields':list(fields),'expected':expected,'where':where,'collection':collection}


def text_value(value):
    """Render an exact text input unambiguously for the evaluator."""
    if '\n' not in value:return '"'+value+'"'
    ending=' It ends with a line break.' if value.endswith('\n') else ''
    return 'exactly the lines between the ``` fences (the line breaks are part of the text).'+ending+'\n```\n'+value.removesuffix('\n')+'\n```\n'


def step(key,goal,acceptance,recipe,checks=(),visible=(),depends=(),action_required=True,requires=()):
    return {'id':key,'goal':goal,'acceptance':acceptance,'recipe':recipe,'checks':list(checks),
            'visible':list(visible),'depends_on':list(depends),'action_required':action_required,'requires':list(requires)}


def episode(key,feature,setup,steps,actor='alice',inputs=None):
    ids=[item['id'] for item in setup]
    for cp in steps:
        cp['assertions']=[{'id':key+'/'+cp['id']+'/visible','channel':'frontend','method':'agent','requirement':cp['acceptance']}]
        for i,check in enumerate(cp['checks']):
            cp['assertions'].append({'id':key+'/'+cp['id']+f'/state-{i+1}','channel':'backend','method':'program',
                'requirement':check.get('description','The independently read public product state matches the requested checkpoint.'),'check':check})
        # requires: 'checkpoint/visible' or 'checkpoint/state-N' of this episode.
        bound=[key+'/'+x for x in cp.pop('requires')]
        if bound:cp['assertions'][0]['requires']=bound
        cp['depends_on']=['setup:'+i for i in ids]+cp['depends_on']
    accounts={name:password for name,password in CREDS.items() if name==actor}
    session=('Sign in with the supplied account before authenticated goals; this is unscored preparation.' if actor
             else 'Start unauthenticated. Only sign in when the checkpoint explicitly asks you to.')
    return {'id':key,'feature':feature,'execution':'gui','initial_state':'Fresh application process and empty DATA_DIR with the public three-account baseline; listed public setup is then applied.',
            'setup':setup,'inputs':{'account':actor,'credentials':accounts,**(inputs or {})},'actor':actor,'session':session,
            'allowed_equivalents':['Different visible labels, page layouts, inline/dialog editors and ordinary navigation routes are valid.','Known product page URLs may be entered in the browser; no API browsing.'],
            'forbidden_bypasses':['Do not use APIs, developer tools, source, private files, or hidden application state to perform GUI goals.','Do not manually recreate a missing product command.'],
            'budget':{'calls':min(160,45+25*len(steps)),'seconds':min(1800,480+180*len(steps)),'tokens':min(1_500_000,350_000+180_000*len(steps))},
            'checkpoints':steps}


def build():
    episodes=[]
    def add(*a,**kw):episodes.append(episode(*a,**kw))
    # Authentication has its own GUI coverage; other episodes share one login.
    for mode in ('username','email','invalid-password'):
        valid=mode!='invalid-password';user='bob@example.test' if mode=='email' else 'bob';password=CREDS['bob'] if valid else 'Wrong-Password-2026!'
        checks=[]
        if not valid:
            # Positive companion: the same account still signs in with its real password; the wrong one is refused.
            checks=[{'request':{'method':'GET','path':'user','actor':'bob','body':None,'status':200,'save':None},'fields':['login'],
                     'expected':{'login':'bob'},'where':None,'collection':False,
                     'refused':{'method':'GET','path':'user','actor':'invalid','body':None,'status':401,'save':None},
                     'description':'The account signs in with its real password through the public interface and the wrong password is refused.'}]
        add('login-'+mode,'authentication',[],[
            step('session',f'Use the sign-in page /user/login. Sign in using username/email {user!r} and password {password!r}. Then open /user/settings to verify whether access was obtained.',
                 'The protected profile page is accessible and identifies Bob.' if valid else
                 'The incorrect credentials do not grant access: the protected profile page still requires sign-in and the sign-in form is offered.',
                 [{'op':'login-test','username':user,'password':password,'valid':valid}],checks,visible=['bob'] if valid else ['Sign In'],
                 requires=[] if valid else ['session/state-1'])],actor=None)
    for valid in (True,False):
        name='web-new-user' if valid else 'alice';email='web-new-user@example.test';password='New-Public-User-2026!'
        add('register-'+('valid' if valid else 'duplicate'),'registration',[],[
            step('registered',f'At /user/sign_up register {name!r} with email {email!r}, password {password!r} and the same password confirmation.',
                 f'The account {name} is created and a signed-in profile is accessible.' if valid else
                 'The sign-up form is shown again with visible feedback that the username is already taken; no replacement account is created and the visitor is not signed in.',
                 [{'op':'register','name':name,'email':email,'password':password,'valid':valid}],
                 [read('users/'+name,['login','email'],{'login':name,'email':email if valid else 'alice@example.test'})],
                 requires=[] if valid else ['registered/state-1'])],actor=None)
    for name,private,empty,template in [('public-project',False,False,False),('private-project',True,True,False),('template-project',False,False,True)]:
        desc='Repository description café Ω'
        fields={'name':name,'description':desc,'private':private,'empty':empty,'template':template,'default_branch':'main'}
        add('repository-'+name,'repositories',[],[
            step('created',f'Create repository {name!r} with description {desc!r}, private={private}, template={template}, initialize README={not empty}, default branch main. Finish on its repository page.',
                 # The standard shows a Private/Template marker, nothing for public, and no description on an empty repository page.
                 f'The new repository page identifies {name}'+('' if empty else ' and shows the requested description')+'; it is '+('marked private' if private else 'not marked private')+
                 (' and is marked as a template' if template else '')+'. '+('It shows empty repository guidance.' if empty else 'Its README/contents are visible.'),
                 [{'op':'create-repo',**fields}], [read('repos/alice/'+name,list(fields),fields,save='created')],visible=[name]),
            step('refresh','Refresh the repository page and verify the saved repository is still present.','The same repository identity and contents/empty state remain visible after refresh.',
                 [{'op':'reload'}],[read('repos/alice/'+name,list(fields),fields)],visible=[name],depends=['created'])])
    rendering={'plain':'The body text appears as entered.',
               'unicode':'The Chinese characters, accented letters, Greek letter and emoji in the title and body are preserved.',
               'markdown':'The body Markdown is visibly rendered as a heading, bold text, inline code and a task-list item rather than raw syntax.',
               'escaped':'The script markup does not execute: it is shown as inert text or removed by sanitization, and "Safe browser text" remains visible.'}
    for variant,title,body in [('plain','Issue workflow','A plain issue body'),('unicode','问题 café Ω','正文 😀 Unicode'),('markdown','Formatted issue','## Review heading\n\n**Bold text** and `code`\n- [ ] task'),('escaped','Safe issue','<script>alert(1)</script>\nSafe browser text')]:
        add('issue-lifecycle-'+variant,'issues',[repo()], [
            step('created',f'Create an issue in alice/workbench at /alice/workbench/issues/new with exactly the title {text_value(title)} and as body {text_value(body)}',
                 'The new issue shows the requested title and alice as its author. '+rendering[variant],
                 [{'op':'create-issue','title':title,'body':body}],
                 [read('repos/alice/workbench/issues',['title','body','state','user.login'],{'title':title,'body':body,'state':'open','user.login':'alice'},where={'title':title},save='issue')],visible=[title]),
            step('comment','Add the comment "Comment made through UI" to the current issue.','The comment is visible as a separate record under the issue, with its author.',
                 [{'op':'comment','body':'Comment made through UI'}],
                 [read('repos/alice/workbench/issues/{{issue.number}}/comments',['body','user.login'],[{'body':'Comment made through UI','user.login':'alice'}],collection=True)],visible=['Comment made through UI'],depends=['created']),
            step('edit-title','Change the current issue title to "Edited issue title" while preserving the body and comment.','The current title is Edited issue title; the issue body and comment remain visible.',
                 [{'op':'title','old':title,'value':'Edited issue title'}],
                 [read('repos/alice/workbench/issues/{{issue.number}}',['title','body'],{'title':'Edited issue title','body':body})],visible=['Edited issue title','Comment made through UI'],depends=['created','comment']),
            step('closed','Close the current issue using its real Close action, then refresh.','The issue visibly has Closed state after refresh, while retaining its title and content.',
                 [{'op':'click','names':['Close','Close Issue']},{'op':'reload'}],
                 [read('repos/alice/workbench/issues/{{issue.number}}',['state'],{'state':'closed'})],visible=['Closed','Edited issue title'],depends=['created']),
            step('reopened','Reopen the current issue, then refresh.','The current issue visibly has Open state after refresh.',
                 [{'op':'click','names':['Reopen','Reopen Issue']},{'op':'reload'}],
                 [read('repos/alice/workbench/issues/{{issue.number}}',['state'],{'state':'open'})],visible=['Open','Edited issue title'],depends=['closed']),
        ])
    # Equal titles/text retain multiplicity; this is not another plain-text variant.
    add('duplicate-comments','comments',[repo(),api('issue','POST','repos/alice/workbench/issues',{'title':'Repeated comments','body':'Repeated body Ω'},save='issue')],[
        step('two-comments','Open /alice/workbench/issues/1. Add two separate comments, both containing "Repeated body Ω". Do not edit the issue body.',
             'Two distinct comment records appear in addition to the issue body, even though their text is identical.',
             [{'op':'goto','path':'/alice/workbench/issues/{{issue.number}}'},{'op':'comment','body':'Repeated body Ω'},{'op':'comment','body':'Repeated body Ω'}],
             [read('repos/alice/workbench/issues/{{issue.number}}/comments',['body'],[{'body':'Repeated body Ω'},{'body':'Repeated body Ω'}],collection=True)],visible=['Repeated comments']),
        step('after-refresh','Refresh this issue and verify both comments are still displayed separately.','The original issue body and both distinct comments survive the refresh.',[{'op':'reload'}],
             [read('repos/alice/workbench/issues/{{issue.number}}/comments',['body'],[{'body':'Repeated body Ω'},{'body':'Repeated body Ω'}],collection=True)],depends=['two-comments'])])
    # One setup covers related labels and milestones; color/date boundaries stay in APIs.
    add('labels-milestones','issue-organization',[repo()],[
        step('label','Create a repository label named "Needs review Ω", color #fbca04, description "Review queue" at /alice/workbench/labels.',
             'The new label and its description appear, with the requested yellow color.',[{'op':'label','title':'Needs review Ω','color':'#fbca04','description':'Review queue'}],
             [read('repos/alice/workbench/labels',['name','color','description'],{'name':'Needs review Ω','color':'fbca04','description':'Review queue'},where={'name':'Needs review Ω'})],visible=['Needs review Ω']),
        step('milestone','Create a milestone named "Release milestone", description "Release scope", due date 2030-05-17.',
             'The milestone page shows the name, description and due date.',[{'op':'milestone','title':'Release milestone','description':'Release scope','date':'2030-05-17'}],
             [read('repos/alice/workbench/milestones',['title','description'],{'title':'Release milestone','description':'Release scope'},where={'title':'Release milestone'},save='milestone')],visible=['Release milestone']),
        step('milestone-edit','Edit that milestone to title "Updated milestone" and description "Updated scope", then refresh.',
             'The updated milestone title and description remain visible after refreshing.',[{'op':'milestone-edit','title':'Updated milestone','description':'Updated scope'},{'op':'reload'}],
             [read('repos/alice/workbench/milestones/{{milestone.id}}',['title','description'],{'title':'Updated milestone','description':'Updated scope'})],visible=['Updated milestone'],depends=['milestone'])])
    # Authorization stays isolated, with positive access and denied writes/read.
    for private,grant,actor in [(False,None,None),(True,None,'bob'),(True,'read','bob'),(True,'write','bob'),(True,'admin','bob')]:
        key=('private' if private else 'public')+'-'+(grant or actor or 'anonymous')
        setup=[repo(private=private)]
        if grant:setup.append(api('collaborator','PUT','repos/alice/workbench/collaborators/bob',{'permission':grant}))
        allowed=not private or grant is not None
        check=read('repos/alice/workbench',['full_name','private'],{'full_name':'alice/workbench','private':private},actor=actor,status=200 if allowed else [403,404])
        if not allowed:
            # The denial counts only together with the owner's access to the same private repository.
            check={**read('repos/alice/workbench',['full_name','private'],{'full_name':'alice/workbench','private':True}),
                   'refused':check['request'],
                   'description':'The owner reads the private repository through the public interface and this identity is refused.'}
        signed='The page shows a signed-in session (an account menu instead of the sign-in form), and '
        denied=(signed+'repository' if actor else 'Repository')+' administration is unavailable to this identity; no editable settings form is exposed.'
        add('access-'+key,'permissions',setup,[
            step('repository','Visit /alice/workbench using the supplied identity. Inspect repository access and contents.',
                 'The repository identity and README contents are visible.' if allowed else
                 signed+'access to the repository is denied or not found with clear visible feedback, showing no private repository content.',
                 [{'op':'goto','path':'/alice/workbench'}],[check],visible=['workbench'] if allowed else [],action_required=False,
                 requires=[] if allowed else ['repository/state-1']),
            step('settings','Visit /alice/workbench/settings and inspect whether repository settings are accessible. Do not change settings.',
                 'The repository settings are accessible and editable.' if grant=='admin' else denied,
                 [{'op':'goto','path':'/alice/workbench/settings'}],[],action_required=False,
                 requires=[] if grant=='admin' else (['repository/visible'] if allowed else ['repository/state-1']))
        ],actor=actor)
    for flag in ('archived','has_issues','has_wiki','has_pull_requests','has_releases'):
        setup=[repo(),api('configuration','PATCH','repos/alice/workbench',{flag:True if flag=='archived' else False})]
        path={'archived':'/issues/new','has_issues':'/issues','has_wiki':'/wiki','has_pull_requests':'/pulls','has_releases':'/releases'}[flag]
        add('configuration-'+flag.replace('_','-'),'repository-configuration',setup,[
            step('restricted',f'Visit /alice/workbench{path}. The repository has '+('been archived.' if flag=='archived' else flag+' disabled.')+' Inspect the corresponding unavailable operation/view.',
                 'The repository alice/workbench itself is shown (its name is visible) while the archived/disabled capability is visibly unavailable; the UI does not offer a working operation that contradicts the repository setting.',
                 [{'op':'goto','path':'/alice/workbench'+path}],[read('repos/alice/workbench',[flag],{flag:flag=='archived'})],action_required=False,
                 requires=['restricted/state-1'])])
    # Representative filtered collections have both matching and excluded items.
    setup=[repo()]
    for title,state in [('Alpha open','open'),('Beta closed','closed'),('Gamma open','open')]:
        slug=title.split()[0].lower()
        setup.append(api('issue-'+slug,'POST','repos/alice/workbench/issues',{'title':title,'body':'Collection item'},save='last'))
        if state=='closed':setup.append(api('close-'+slug,'PATCH','repos/alice/workbench/issues/{{last.number}}',{'state':'closed'}))
    add('issue-search-filter','issue-query',setup,[
        step('open','Open /alice/workbench/issues and select open issues.','Alpha open and Gamma open are listed; Beta closed is excluded from the open list.',[{'op':'goto','path':'/alice/workbench/issues?state=open'}],visible=['Alpha open','Gamma open'],action_required=False),
        step('closed','Use the visible state filter to show closed issues.','Beta closed is listed; the two open issues are excluded.',[{'op':'goto','path':'/alice/workbench/issues?state=closed'}],visible=['Beta closed']),
        step('search','Search the issue list for "Alpha", with open/all state as needed.','The result identifies Alpha open and excludes unrelated Beta/Gamma entries.',[{'op':'goto','path':'/alice/workbench/issues?state=open&q=Alpha'}],visible=['Alpha open'])])
    # The labelled issue and the milestone issue are different issues, so each filter is tested on its own.
    setup=[repo(),api('label','POST','repos/alice/workbench/labels',{'name':'bug','color':'ee0701'},save='label'),api('milestone','POST','repos/alice/workbench/milestones',{'title':'Release one'},save='milestone'),
           api('labelled-issue','POST','repos/alice/workbench/issues',{'title':'Tagged issue','body':'Tagged','labels':['{{label.id}}']}),
           api('milestone-issue','POST','repos/alice/workbench/issues',{'title':'Scheduled issue','body':'Scheduled','milestone':'{{milestone.id}}'}),
           api('other-issue','POST','repos/alice/workbench/issues',{'title':'Unrelated issue'})]
    add('issue-label-milestone-filter','issue-query',setup,[
        step('label-filter','Open /alice/workbench/issues and filter by the bug label.','Tagged issue is listed; Scheduled issue and Unrelated issue are excluded.',[{'op':'goto','path':'/alice/workbench/issues?labels={{label.id}}'}],visible=['Tagged issue']),
        step('milestone-filter','Show all issues again, then filter issues by milestone Release one.','Scheduled issue is listed; Tagged issue and Unrelated issue are excluded.',[{'op':'goto','path':'/alice/workbench/issues?milestone={{milestone.id}}'}],visible=['Scheduled issue'])])
    # File editor routes cover two distinct text/path forms; API keeps the full matrix.
    for filename,text in [('notes.txt','Created in browser\n'),('docs/文档.md','# 标题\n\n**café Ω**\n')]:
        slug='unicode' if '文档' in filename else 'plain';content=base64.b64encode(text.encode()).decode()
        changed=text+'Updated content\n'
        add('file-lifecycle-'+slug,'files',[repo()], [
            step('created',f'Create file {filename!r} in alice/workbench, branch main, with commit message "Create web file", using the public web editor. Its content is {text_value(text)}',
                 'The committed file page identifies the requested path and displays its content.',[{'op':'file-create','path':filename,'content':text,'message':'Create web file'}],
                 [read('repos/alice/workbench/contents/'+filename,['path','content'],{'path':filename,'content':content})],visible=[filename.rsplit('/',1)[-1]]),
            step('edited',f'Edit that file and commit with message "Update web file". Its new content is {text_value(changed)}',
                 'The file page displays the updated content after the commit.',[{'op':'file-edit','path':filename,'content':changed,'message':'Update web file'}],
                 [read('repos/alice/workbench/contents/'+filename,['content'],{'content':base64.b64encode(changed.encode()).decode()})],depends=['created']),
            step('history','Open the file history and inspect the two commits.','The create and update commits are visibly listed as distinct revisions.',[{'op':'goto','path':'/alice/workbench/commits/branch/main/'+filename}],visible=['Create web file','Update web file'],depends=['edited']),
            step('deleted','Delete that file through the visible product action and commit with message "Delete web file".',
                 'The deletion completes and the repository no longer lists this file as a current file.',[{'op':'file-delete','path':filename,'message':'Delete web file'}],
                 [read('repos/alice/workbench/contents/'+filename,status=404)],depends=['created'])])
    for kind,draft,pre in [('stable',False,False),('draft',True,False),('prerelease',False,True)]:
        title='Web release '+kind;tag='v-web-'+kind
        add('release-'+kind,'releases',[repo()],[
            step('published',f'Create release {title!r}, tag {tag!r}, notes "Release notes", prerelease={pre}, draft={draft}, using /alice/workbench/releases/new.',
                 'The release page/list shows the requested release name, notes and draft/prerelease state.',[{'op':'release','title':title,'tag':tag,'body':'Release notes','draft':draft,'prerelease':pre}],
                 [read('repos/alice/workbench/releases',['name','body','draft','prerelease'],{'name':title,'body':'Release notes','draft':draft,'prerelease':pre},where={'tag_name':tag})],visible=[title])])
    add('wiki-lifecycle','wiki',[repo()],[
        step('created','Create Wiki page Home in alice/workbench, content "Welcome wiki Ω", commit message "Create wiki".',
             'The Wiki page visibly shows Home and Welcome wiki Ω.',[{'op':'wiki-create','title':'Home','content':'Welcome wiki Ω','message':'Create wiki'}],visible=['Welcome wiki Ω']),
        step('edited','Edit Wiki Home to "Revised wiki Ω" with commit message "Update wiki", then refresh.',
             'The refreshed Wiki page visibly shows the revised content.',[{'op':'wiki-edit','title':'Home','content':'Revised wiki Ω','message':'Update wiki'},{'op':'reload'}],visible=['Revised wiki Ω'],depends=['created']),
        step('history','Open the Wiki revision history.','The history shows distinct Create wiki and Update wiki revisions.',[{'op':'wiki-history'}],visible=['Create wiki','Update wiki'],depends=['edited'])])
    for visibility in ('public','private'):
        name='web-org-'+visibility
        add('organization-'+visibility,'organizations',[],[
            step('created',f'Create organization {name} with {visibility} visibility at /org/create.',
                 f'The organization page identifies {name} and '+('marks it as private.' if visibility=='private' else 'does not mark it as private or limited.'),[{'op':'organization','name':name,'visibility':visibility}],
                 [read('orgs/'+name,['username','visibility'],{'username':name,'visibility':visibility})],visible=[name])])
    setup=[api('organization','POST','orgs',{'username':'web-team-org','visibility':'public'})]
    for admin in (False,True):
        name='maintainers' if admin else 'readers'
        add('team-'+name,'teams',setup,[
            step('created',f'Create team {name} in web-team-org at /org/web-team-org/teams/new. Description "Team responsibilities". Use '+('administrator access' if admin else 'general access, read access for repository units')+', specific repositories, and do not allow repository creation.',
                 f'The team page identifies {name} and its configured access.',[{'op':'team','name':name,'admin':admin}],
                 [read('orgs/web-team-org/teams',['name','description','permission','includes_all_repositories','can_create_org_repo'],where={'name':name})],visible=[name])])
    add('profile-settings','profile',[],[
        step('updated','At /user/settings change your display name to "Carol 浏览器 Ω", location to "Tokyo / Paris", website to https://example.test/carol, and biography to "Profile biography". Save, then open your public profile page.',
             'Saved profile fields show the requested values; the public profile exposes the display name, location, website and biography.',
             [{'op':'profile','fields':{'full_name':'Carol 浏览器 Ω','location':'Tokyo / Paris','website':'https://example.test/carol','description':'Profile biography'}},{'op':'goto','path':'/carol'}],
             [read('user',['full_name','location','website','description'],{'full_name':'Carol 浏览器 Ω','location':'Tokyo / Paris','website':'https://example.test/carol','description':'Profile biography'},actor='carol')],visible=['Carol 浏览器 Ω','Tokyo / Paris']),
        step('clear','Clear the location and website in profile settings and save.','The saved settings have empty location and website.',[{'op':'profile','fields':{'location':'','website':''}}],
             [read('user',['location','website'],{'location':'','website':''},actor='carol')],depends=['updated'])],actor='carol')
    add('repository-settings','repository-settings',[repo()],[
        step('updated','At /alice/workbench/settings change description to "Updated repository Ω" and website to https://example.test/project, then save.',
             'Saved settings visibly contain the requested description and website.',[{'op':'repo-settings','fields':{'description':'Updated repository Ω','website':'https://example.test/project'}}],
             [read('repos/alice/workbench',['description','website'],{'description':'Updated repository Ω','website':'https://example.test/project'})]),
        step('cleared','Clear the repository description and website and save.','Saved settings show those fields empty.',[{'op':'repo-settings','fields':{'description':'','website':''}}],
             [read('repos/alice/workbench',['description','website'],{'description':'','website':''})],depends=['updated'])])
    add('star-watch','repository-social',[repo()],[
        step('star','Open /alice/workbench and star the repository through its public control.',
             'The repository visibly indicates it is starred and offers the inverse unstar action.',[{'op':'goto','path':'/alice/workbench'},{'op':'click','names':['Star']}],
             [read('user/starred/alice/workbench',actor='bob',status=204)]),
        step('unstar','Unstar the repository.','The repository visibly indicates it is no longer starred.',[{'op':'click','names':['Unstar']}],
             [read('user/starred/alice/workbench',actor='bob',status=404)],depends=['star'])],actor='bob')
    # The search term matches both repositories, so the private one's absence tests visibility.
    setup=[repo('directory-alpha'),{**repo('directory-beta',private=True),'id':'private-repository'},api('organization','POST','orgs',{'username':'directory-org','visibility':'public'})]
    add('explore-directories','discovery',setup,[
        step('repositories','Use /explore/repos to search for "directory".','The public repository directory-alpha is listed with a usable link; the private directory-beta is absent for anonymous visitors.',[{'op':'goto','path':'/explore/repos?q=directory'}],visible=['directory-alpha'],action_required=False),
        step('users','Visit /explore/users and inspect the public user directory.','The seeded users Alice, Bob and Carol are discoverable and have profile links.',[{'op':'goto','path':'/explore/users'}],visible=['alice','bob','carol'],action_required=False),
        step('organizations','Visit /explore/organizations and inspect organizations.','The public organization directory-org is listed with a link to its page.',[{'op':'goto','path':'/explore/organizations'}],visible=['directory-org'],action_required=False)],actor=None)
    # Restart uses the same public data directory but a genuinely fresh process.
    add('restart-visible-state','persistence',[repo()],[
        step('before','Create issue "Durable issue" with body "Survives process restart" in alice/workbench.',
             'The issue title and body are visibly saved.',[{'op':'create-issue','title':'Durable issue','body':'Survives process restart'}],
             [read('repos/alice/workbench/issues',['title','body'],{'title':'Durable issue','body':'Survives process restart'},where={'title':'Durable issue'},save='issue')],visible=['Durable issue']),
        {**step('after','The framework has restarted the application using the same data directory. Reopen /alice/workbench/issues and inspect the Durable issue.',
             'The previously saved issue and its body remain visible after the fresh application process starts.',[{'op':'goto','path':'/alice/workbench/issues/{{issue.number}}'}],
             [read('repos/alice/workbench/issues/{{issue.number}}',['title','body'],{'title':'Durable issue','body':'Survives process restart'})],visible=['Durable issue','Survives process restart'],depends=['before']), 'lifecycle':'restart'}])
    # PR review and merge decisions are genuine GUI operations; protocol-only
    # approval thresholds and denied writes retain their exhaustive checks.
    for rejection in (False,True):
        setup=[repo(),api('collaborator','PUT','repos/alice/workbench/collaborators/bob',{'permission':'write'}),
               api('base-file','POST','repos/alice/workbench/contents/change.txt',{'content':base64.b64encode(b'before\n').decode(),'message':'Initial file'}),
               api('feature-branch','POST','repos/alice/workbench/branches',{'new_branch_name':'feature','old_branch_name':'main'}),
               # The update names the base file by its Git blob identity, not by a response shape.
               api('feature-change','PUT','repos/alice/workbench/contents/change.txt',{'branch':'feature','sha':blob_sha(b'before\n'),'content':base64.b64encode(b'after review\n').decode(),'message':'Proposed change'}),
               api('protection','POST','repos/alice/workbench/branch_protections',{'branch_name':'main','rule_name':'main','enable_push':False,'required_approvals':1,'block_on_rejected_reviews':True}),
               # The branch push is processed asynchronously; opening the pull request afterwards keeps the
               # reference timeline independent of that timing.
               {**api('pull','POST','repos/alice/workbench/pulls',{'head':'feature','base':'main','title':'Review this change','body':'Review body'},actor='bob',save='pull'),'settle':3}]
        stages=[step('inspect','Open the pull request Review this change in /alice/workbench/pulls. Inspect the file diff.',
                     'The pull identifies feature→main and the proposed change in change.txt from before to after review.',
                     [{'op':'goto','path':'/alice/workbench/pulls/{{pull.number}}/files'}],visible=['change.txt','before','after review'],action_required=False),
                step('commits','Open this pull request commit list and inspect the proposed commit.',
                     'The commit list contains Proposed change with a usable revision link.',
                     [{'op':'goto','path':'/alice/workbench/pulls/{{pull.number}}/commits'}],visible=['Proposed change'])]
        if rejection:stages.append(step('request-changes','Submit a Request changes review with body "Please fix this change".',
                      'The submitted review and request-changes decision are visible; the PR remains unmerged.',
                      [{'op':'review','event':'REQUEST_CHANGES','body':'Please fix this change'}],
                      [read('repos/alice/workbench/pulls/{{pull.number}}/reviews',['state','body'],{'state':'REQUEST_CHANGES','body':'Please fix this change'},where={'body':'Please fix this change'})],visible=['Please fix this change']))
        stages.extend([
            step('approved','Submit an Approve review with body "Approved through UI".',
                 'The approval review is visibly saved and attributed to the reviewer.',[{'op':'review','event':'APPROVED','body':'Approved through UI'}],
                 [read('repos/alice/workbench/pulls/{{pull.number}}/reviews',['state','body'],{'state':'APPROVED','body':'Approved through UI'},where={'body':'Approved through UI'})],visible=['Approved through UI']),
            step('merged','Merge the pull request using the normal merge-commit product action. Confirm through the visible controls when required.',
                 'The PR visibly becomes merged/closed and records the merge through the product action.',[{'op':'merge'}],
                 [read('repos/alice/workbench/pulls/{{pull.number}}',['merged','state'],{'merged':True,'state':'closed'}),read('repos/alice/workbench/contents/change.txt',['content'],{'content':base64.b64encode(b'after review\n').decode()})],visible=['Merged'],depends=['approved'])])
        add('pull-'+('rejection-resolution' if rejection else 'approval-merge'),'pull-requests',setup,stages)
    # Minimal public uploads of the viewed packages: no replay of the scored protocol cases.
    add('package-browsing-deletion','packages',[fixture('generic-packages'),fixture('npm-package'),fixture('container-image')],[
        step('generic','Visit /alice/-/packages/generic/pbp-generic/1.0.0 and inspect its package/version/file details.',
             'The package name, version and downloadable file entries are visible and correctly associated.',[{'op':'goto','path':'/alice/-/packages/generic/pbp-generic/1.0.0'}],visible=['pbp-generic','1.0.0'],action_required=False),
        step('npm','Visit /alice/-/packages/npm/pbp-npm/1.0.0 and inspect its details.',
             'The npm package identity, version and metadata are visible.',[{'op':'goto','path':'/alice/-/packages/npm/pbp-npm/1.0.0'}],visible=['pbp-npm','1.0.0'],action_required=False),
        step('container','Visit /alice/-/packages/container/pbp-image/latest and inspect its details.',
             'The container package identity and latest version are visible.',[{'op':'goto','path':'/alice/-/packages/container/pbp-image/latest'}],visible=['pbp-image','latest'],action_required=False),
        step('directory','Open /alice/-/packages and filter to generic packages using the visible filter.',
             'The generic package is listed with its correct links; npm/container entries are excluded by the type filter.',[{'op':'goto','path':'/alice/-/packages?type=generic'}],visible=['pbp-generic']),
        step('delete','Delete only generic package version pbp-generic/2.0.0-rc.1 through its visible version settings. Preserve 1.0.0.',
             'The selected version is no longer available; version 1.0.0 remains available.',[{'op':'package-delete'}],
             [read('packages/alice/generic/pbp-generic/2.0.0-rc.1',status=404),read('packages/alice/generic/pbp-generic/1.0.0',['name','version'],{'name':'pbp-generic','version':'1.0.0'})])])
    for actor in ('alice','carol'):
        owner=actor=='alice'
        stored='LFS object café\n'.encode()
        checks=[] if owner else [{'request':{'method':'GET','path':'/alice/pbp-lfs-public.git/info/lfs/objects/'+hashlib.sha256(stored).hexdigest(),
                                             'actor':'alice','body':None,'status':200,'save':None},'content_sha256':hashlib.sha256(stored).hexdigest(),
                                  'description':'The repository stores the LFS object the page would administer (owner download through the LFS interface).'}]
        add('lfs-view-'+actor,'large-files',[fixture('lfs-objects')],[
            step('objects','Visit /alice/pbp-lfs-public/settings/lfs and inspect the available LFS objects.',
                 'The owner can see the object inventory with the objects\' digests and sizes.' if owner else
                 'The page shows a signed-in session (an account menu instead of the sign-in form), and repository LFS administration is unavailable to this account: no administrative object list or management action is exposed.',
                 [{'op':'goto','path':'/alice/pbp-lfs-public/settings/lfs'}],checks,action_required=False,requires=[] if owner else ['objects/state-1'])],actor=actor)
    return episodes
