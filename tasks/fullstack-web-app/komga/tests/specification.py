"""User goals and acceptance conditions, independent of the standard's click recipes."""
from common import AUTH,READER
from program import request


def step(key,goal,requirement,recipe,check=None,visible=(),depends=()):
    return {'id':key,'goal':goal,'acceptance':requirement,'recipe':recipe,'check':check,'visible':list(visible),'depends_on':list(depends)}


def episode(key,feature,steps,library=True,formats=False,login=True,setup=None):
    items=([{'id':'account','kind':'account'}] if login else [])+([{'id':'library','kind':'library','formats':formats}] if library else [])+(setup or [])
    for cp in steps:
        cp['assertions']=[{'id':key+'/'+cp['id']+'/visible','channel':'frontend','method':'agent','requirement':cp.pop('acceptance')}]
        check=cp.pop('check')
        if check:cp['assertions'].append({'id':key+'/'+cp['id']+'/state','channel':'backend','method':'program','requirement':'The saved public state matches this user goal.','spec':check})
        cp['depends_on']=['setup:'+x['id'] for x in items]+cp['depends_on']
    return {'id':key,'feature':feature,'execution':'gui','initial_state':'A fresh unclaimed server with the listed public setup.','setup':items,'inputs':{'email':AUTH[0],'password':AUTH[1]},'login':login,'session':'Sign in using the supplied email and password before authenticated goals.' if login else 'Start unauthenticated; create the account only when the goal requests it.','allowed_equivalents':['Equivalent visible navigation, editors and reader layouts are accepted.'],'forbidden_bypasses':['Use visible product controls. Do not use APIs, source, developer tools or hidden state.'],'budget':{'calls':max(200,50*len(steps)),'tokens':max(3000000,600000*len(steps)),'seconds':max(1800,360*len(steps))},'checkpoints':steps}


def go(path):return {'op':'open','path':path}
def click(text):return {'op':'click','text':text}
def fill(label,value):return {'op':'fill','label':label,'value':value}


def build():
    w=[]
    w.append(episode('gui-first-account','authentication',[
        step('claim','Create the first administrator account with email admin@example.test and password Admin-Local-2026!.','The server accepts the account and shows the signed-in library setup area.',[go('/'),fill('Email',AUTH[0]),fill('Password',AUTH[1]),click('Create user account')],request('/api/v2/users/me',fields=['email','roles'],want={'email':AUTH[0]}),['Welcome to Komga']),
        step('identity','Open your account settings and inspect the signed-in identity.','The account page identifies admin@example.test as the signed-in user.',[go('/account/me')],visible=[AUTH[0]],depends=['claim']),
    ],library=False,login=False))
    w.append(episode('gui-login','authentication',[
        step('account','Sign in and open your account settings.','The account settings show the signed-in email admin@example.test.',[go('/account/me')],visible=[AUTH[0]]),
        step('refresh','Refresh the account page.','The authenticated account page remains accessible and keeps the same identity.',[{'op':'reload'}],visible=[AUTH[0]],depends=['account']),
    ],library=False))
    # Imported content is visible through ordinary series and book details, including Unicode.
    for key,title in [('s0','Atlas'),('s2','Café 漫画')]:
        path='/series/${'+key+'.id}'
        w.append(episode('gui-series-'+key,'library-browsing',[
            step('details','Find the series '+title+' and open its details.','The selected series is identified by its title and shows its three books.',[go(path)],visible=[title,'3 / 3 books']),
            step('metadata','Inspect the imported publisher, genre and contributors of '+title+'.','The series details visibly present its publisher, genre and authors.',[go(path)],visible=[title,'PUBLISHER','WRITERS','PENCILLERS'],depends=['details']),
            step('books','Inspect the books belonging to '+title+'.','All three distinct chapter titles are visible in the series.',[{'op':'scroll','y':500}],visible=[title+' chapter 1',title+' chapter 2',title+' chapter 3'],depends=['details']),
        ]))
    for key,title in [('b01','Atlas chapter 1'),('b21','Café 漫画 chapter 1')]:
        path='/book/${'+key+'.id}'
        w.append(episode('gui-book-'+key,'book-details',[
            step('details','Open the book '+title+'.','The book title, series relationship and page count are visible.',[go(path)],visible=[title,'4 pages']),
            step('summary','Inspect this book’s imported summary and credits.','The details show the book summary and its writer and penciller.',[go(path)],visible=['Adventure 1','WRITERS','PENCILLERS'],depends=['details']),
            step('refresh','Refresh the book details.','The same book and its imported metadata remain visible.',[{'op':'reload'}],visible=[title,'Adventure 1'],depends=['details']),
        ]))
    for kind,key in [('series','s0'),('book','b01')]:
        path='/'+kind+'/${'+key+'.id}';api='/api/v1/'+('series' if kind=='series' else 'books')+'/${'+key+'.id}'
        fields=[('Title','Revised '+kind+' Ω','title'),('Summary','A new story across the sea.','summary')]
        if kind=='series':fields+=[('Publisher','Ocean Press','publisher'),('Language','fr','language'),('Age Rating','16','ageRating')]
        else:fields+=[('Number','Special 2','number'),('ISBN','9780306406157','isbn')]
        steps=[]
        for label,value,field in fields:
            recipe=[go(path),{'op':'edit','kind':kind},fill(label,value),{'op':'save'},go(path)]
            if kind=='book' and field=='isbn':recipe=[go(path),{'op':'edit','kind':kind},fill(label,value),{'op':'save'},go(path)]
            expected=int(value) if field=='ageRating' else value
            # Reopen the editor so language/age/ISBN values are visibly inspectable, independent of detail formatting.
            if field in ('language','ageRating','isbn'):recipe+=[{'op':'edit','kind':kind},{'op':'focus-field','label':label}]
            steps.append(step(field,('In the '+kind+' '+repr('Atlas' if kind=='series' else 'Atlas chapter 1')+', ' if not steps else 'For the same '+kind+' edited in the preceding checkpoint, ')+'change its '+label.lower()+' to '+repr(value)+' and verify the saved value.','The saved '+label.lower()+' is visibly '+repr(value)+'.',recipe,request(api,fields=['metadata.'+field],want={'metadata':{field:expected}}),visible=[value] if field in ('title','summary','publisher','number') else (),depends=[steps[-1]['id']] if steps else []))
            if field in ('language','ageRating','isbn'):steps[-1]['recipe']+=[{'op':'require','text':['Save Changes']}]
        # Goals are independent of dismissing a prior editor; next recipe navigates afresh.
        w.append(episode('gui-edit-'+kind,'metadata-editing',steps))
    import gui_browsing,gui_management,gui_actions,gui_reader_modes,gui_account_import
    w+=gui_browsing.build()+gui_management.build()+gui_actions.build()+gui_reader_modes.build()+gui_account_import.build()
    return w
