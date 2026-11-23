from specification import episode,step,go,click,fill
from program import request


def build():
    w=[]
    w.append(episode('gui-library-create','library-management',[
        step('create','Create a library named New Shelf using the already staged directory /exchange/inbox/NewShelf.','The newly created New Shelf library is visible in the application.',[go('/'),click('Add Library'),fill('Name','New Shelf'),fill('Root folder','/exchange/inbox/NewShelf'),click('Metadata'),click('Add'),{'op':'wait','seconds':2}],request('/api/v1/libraries',where={'name':'New Shelf'},fields=['name','root'],save='newlib'),visible=['New Shelf']),
        step('scan','Open New Shelf and wait for its staged comic to be indexed.','The new library contains the Atlas series.',[click('New Shelf'),{'op':'wait','seconds':3}],request('/api/v1/series',catalog=True),visible=['Atlas'],depends=['create']),
        step('open','Open the Atlas series in New Shelf.','The series page shows its imported first chapter.',[click('Atlas'),{'op':'wait','seconds':1}],visible=['Atlas chapter 1'],depends=['scan']),
    ],library=False,setup=[{'id':'staged','kind':'stage-library'}]))
    w.append(episode('gui-users','user-management',[
        step('create','Create a user web-reader@example.test with password Reader-Local-2026!, allowing file download and page streaming.','The new user is shown in the user list.',[go('/settings/users/add'),fill('Email','web-reader@example.test'),fill('Password','Reader-Local-2026!'),click('Add')],request('/api/v2/users',where={'email':'web-reader@example.test'},fields=['email','roles'],save='webuser'),visible=['web-reader@example.test']),
        step('refresh','Refresh the user management page.','The created user remains listed.',[{'op':'reload'}],visible=['web-reader@example.test'],depends=['create']),
        step('sign-in','Sign in as web-reader@example.test with password Reader-Local-2026! and open that account’s settings.','The account page identifies web-reader@example.test.',[{'op':'logout'},{'op':'login','auth':['web-reader@example.test','Reader-Local-2026!']},go('/account/me')],visible=['web-reader@example.test'],depends=['create']),
        step('browse','As the new reader, browse the Comics library.','The reader can browse the library and see Atlas and Beacon.',[go('/libraries/all/series')],visible=['Atlas','Beacon'],depends=['sign-in']),
    ]))
    w.append(episode('gui-api-keys','account-management',[
        step('create','Create an API key with comment Tablet reader in your account settings.','The new key is visibly listed with comment Tablet reader.',[go('/account/api-keys'),{'op':'new-api-key','comment':'Tablet reader'}],request('/api/v2/users/me/api-keys',where={'comment':'Tablet reader'},fields=['comment'],save='webkey'),visible=['Tablet reader']),
        step('refresh','Refresh your API key list.','The Tablet reader key remains listed.',[{'op':'reload'}],visible=['Tablet reader'],depends=['create']),
        step('delete','Revoke the Tablet reader API key.','The key is removed from the account’s key list, and the key management page remains usable.',[{'op':'delete-api-key'}],request('/api/v2/users/me/api-keys',want=[]),depends=['create']),
    ],library=False))
    steps=[]
    for label,value,key in [('Delete empty collections after scan',False,'deleteEmptyCollections'),('Delete empty read lists after scan',False,'deleteEmptyReadLists')]:
        steps.append(step(key,'Turn off '+label.lower()+' in server settings.','The saved setting '+label.lower()+' is disabled.',[go('/settings/server'),{'op':'wait','seconds':1},{'op':'check','label':label,'value':value},click('Save Changes'),{'op':'wait','seconds':.5},go('/settings/server'),{'op':'wait','seconds':1}],request('/api/v1/settings',fields=[key],want={key:value}),visible=[label]))
    steps.append(step('refresh','Refresh server settings and inspect the two empty-list cleanup settings.','Both cleanup settings remain disabled after refresh.',[{'op':'reload'}],request('/api/v1/settings',fields=['deleteEmptyCollections','deleteEmptyReadLists'],want={'deleteEmptyCollections':False,'deleteEmptyReadLists':False}),depends=['deleteEmptyCollections','deleteEmptyReadLists']))
    w.append(episode('gui-server-settings','server-settings',steps,library=False))
    w.append(episode('gui-theme','client-preferences',[
        step('dark','Change your interface theme to Dark.','The application is visibly using its dark theme.',[go('/dashboard'),{'op':'select','label':'Theme','value':'Dark'}]),
        step('refresh','Refresh the page.','The dark theme remains in use after refresh.',[{'op':'reload'}],depends=['dark']),
        step('light','Change your interface theme to Light.','The application is visibly using its light theme.',[{'op':'select','label':'Theme','value':'Light'}],depends=['dark']),
    ]))
    # Existing imported lists are real nonempty subjects for editing and membership navigation.
    for entity,title,key,member in [('collections','Shared World','collection','series'),('readlists','Opening arc','readlist','books')]:
        route='/libraries/all/'+entity;api='/api/v1/'+entity
        name='Edited '+('collection' if entity=='collections' else 'reading list')
        w.append(episode('gui-'+entity,'reading-organization',[
            step('open','Open '+title+' from the '+entity+' catalog.','The selected list shows its name and populated members.',[go(route),click(title)],visible=[title,'Atlas']),
            step('rename','Rename '+title+' to '+name+'.','The list visibly uses the new name.',[{'op':'list-edit'},fill('Name',name),{'op':'save'}],request(api,where={'name':name},fields=['name'],save=key),visible=[name],depends=['open']),
            step('refresh','Refresh this list.','The saved name and members remain visible.',[{'op':'reload'}],visible=[name,'Atlas'],depends=['rename']),
            step('member','Open the Atlas member from this list.','The Atlas series or book details are accessible from the list.',[{'op':'list-member','entity':entity}],visible=['Atlas'],depends=['refresh']),
        ]))
    return w
