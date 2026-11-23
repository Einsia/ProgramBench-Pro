'''Account, household, group and administration goals through visible product controls.'''
from specification import api, read, step
from gui_recipes import go, button, fill


def tick(label,value): return {'op':'tick','label':label,'value':value}
def click_text(text): return {'op':'click','tag':'button','text':text}


def build(add):
    profile='/user/profile/edit'
    add('account-profile','account-profile',[],[
        step('name','Change your full name to "Jamie Cook".','The saved profile and signed-in identity display Jamie Cook.',
             [go(profile),fill('Full Name','Jamie Cook'),button('Update'),go(profile)],
             [read('users/self',['fullName'],{'fullName':'Jamie Cook'})],visible=['Jamie Cook']),
        step('email','Change your email address to "jamie@example.com".','The profile displays the saved email address.',
             [go(profile),fill('Email','jamie@example.com'),button('Update'),go(profile)],
             [read('users/self',['email'],{'email':'jamie@example.com'})]),
        step('announcements','Disable announcements in your personal preferences.','The personal announcement preference is visibly disabled after reopening settings.',
             [go(profile),tick('Show announcements from Mealie',False),go(profile),{'op':'scroll','delta_y':500}],
             [read('users/self',['showAnnouncements'],{'showAnnouncements':False})]),
    ])
    token='/user/profile/api-tokens'
    add('account-tokens','account-tokens',[],[
        step('create','Generate an API token named "Kitchen tablet".','The API token page shows Kitchen tablet among the active tokens.',
             [go(token),fill('Token Name','Kitchen tablet'),button('Generate'),button('Close')],
             [read('users/self',['tokens.0.name'],{'tokens.0.name':'Kitchen tablet'})],visible=['Kitchen tablet']),
        step('delete','Delete the Kitchen tablet API token.','The token page reports no active tokens after the token is removed.',
             [go(token),button('Delete'),go(token)],
             [read('users/self',['tokens'],{'tokens':[]})],visible=['You have no active tokens.'],depends=['create']),
    ])
    add('group-preferences','group-preferences',[],[
        step('public','Make the Home group public.','Group settings visibly show that the group is no longer private.',
             [go('/group'),tick('Private Group',False),button('Update',index=0),go('/group')],
             [read('groups/preferences',['privateGroup'],{'privateGroup':False})]),
        step('announcements','Disable group announcements.','The group announcement preference remains disabled when settings are reopened.',
             [go('/group'),tick('Show announcements from Mealie',False),button('Update',index=0),go('/group')],
             [read('groups/preferences',['showAnnouncements'],{'showAnnouncements':False})]),
    ])
    prefs=[('privacy','Private Household','privateHousehold',False,'Make the Family household public.'),
           ('nutrition','Show nutrition information','recipeShowNutrition',True,'Enable nutrition information by default for new household recipes.'),
           ('assets','Show recipe assets','recipeShowAssets',True,'Enable recipe assets by default for new household recipes.'),
           ('comments','Disable users from commenting on recipes','recipeDisableComments',True,'Disable comments by default for new household recipes.')]
    add('household-preferences','household-preferences',[],[
        step(key,goal,'The requested household preference is visibly saved and remains selected after reopening settings.',
             [go('/household'),tick(label,value),button('Update'),go('/household'),{'op':'scroll','delta_y':0 if key=='privacy' else 700}],
             [read('households/preferences',[field],{field:value})])
        for key,label,field,value,goal in prefs
    ])
    notes='households/events/notifications';np='/household/notifiers'
    add('household-notifiers','household-notifiers',[],[
        step('create','Create an event notifier named "Kitchen" with Apprise URL "json://example.invalid/kitchen".',
             'Kitchen appears as a configured event notifier.',
             [go(np),button('Create'),fill('Name','Kitchen'),fill('Apprise URL','json://example.invalid/kitchen'),button('Create'),go(np)],
             [read(notes,['name'],{'name':'Kitchen'},where={'name':'Kitchen'})],visible=['Kitchen']),
        step('disable','Disable the Kitchen event notifier.','The Kitchen notifier visibly remains configured with its enabled setting turned off.',
             [go(np),click_text('Kitchen'),tick('Enable Notifier',False),button('Save'),go(np),click_text('Kitchen')],
             [read(notes,['enabled'],{'enabled':False},where={'name':'Kitchen'})],depends=['create']),
        step('delete','Delete the Kitchen event notifier.','The notifier list is available and no longer contains Kitchen.',
             [go(np),click_text('Kitchen'),button('Delete'),button('Confirm'),go(np)],
             [read(notes,['name'],[],collection=True)],visible=['Event Notifiers'],depends=['create']),
    ])
    hooks='households/webhooks';hp='/household/webhooks'
    add('household-webhooks','household-webhooks',[],[
        step('create','Create a webhook named "Dinner bell", URL "https://example.invalid/dinner", scheduled for 17:30 UTC. Leave it disabled.',
             'The configured Dinner bell webhook is shown with the requested schedule and disabled state.',
             [go(hp),button('Create'),{'op':'click','tag':'button','has':'New Webhook'},
              fill('Webhook Name','Dinner bell'),fill('Webhook URL','https://example.invalid/dinner'),
              {'op':'fill','type':'time','value':'17:30'},tick('Enabled',False),button('Save'),go(hp),{'op':'click','tag':'button','has':'Dinner bell'}],
             [read(hooks,['name','url','scheduledTime','enabled'],{'name':'Dinner bell','url':'https://example.invalid/dinner','scheduledTime':'17:30:00','enabled':False},where={'name':'Dinner bell'})],visible=['Dinner bell']),
        step('rename','Rename Dinner bell to "Evening meal".','The webhook is displayed under its new name.',
             [go(hp),{'op':'click','tag':'button','has':'Dinner bell'},fill('Webhook Name','Evening meal'),button('Save'),go(hp)],
             [read(hooks,['name'],{'name':'Evening meal'},where={'name':'Evening meal'})],visible=['Evening meal'],depends=['create']),
        step('delete','Delete the Evening meal webhook.','The webhooks page remains available and the deleted webhook is absent.',
             [go(hp),{'op':'click','tag':'button','has':'Evening meal'},button('Delete'),go(hp)],
             [read(hooks,['name'],[],collection=True)],visible=['Webhooks'],depends=['rename']),
    ])
    gp='/admin/manage/groups'
    add('admin-groups','admin-groups',[],[
        step('create','Create a group named "Weekend Kitchen".','Group management shows Weekend Kitchen alongside Home.',
             [go(gp),button('Create'),fill('Group Name','Weekend Kitchen'),button('Create'),go(gp)],
             [read('admin/groups',['name'],{'name':'Weekend Kitchen'},where={'name':'Weekend Kitchen'},save='created')],visible=['Weekend Kitchen','Home']),
        step('delete','Delete the empty Family household belonging to Weekend Kitchen, then delete the Weekend Kitchen group.','Group management retains Home and no longer lists Weekend Kitchen.',
             [go('/admin/manage/households'),{'op':'click','tag':'button','text':'','enabled':True,'region':[1100,200,1280,500]},button('Confirm'),go(gp),{'op':'click','tag':'button','text':'','enabled':True,'region':[1100,200,1280,500]},button('Confirm'),go(gp)],
             [read('admin/groups',['name'],[{'name':'Home'}],collection=True)],visible=['Home'],depends=['create']),
    ])
    hp='/admin/manage/households'
    add('admin-households','admin-households',[],[
        step('create','Create a household named "Cabin" in the Home group.','Household management lists Cabin in Home alongside the existing Family household.',
             [go(hp),button('Create'),{'op':'choice','role':'combobox','text':'Household Group','value':'Home'},fill('Household Name','Cabin'),button('Create'),go(hp)],
             [read('admin/households',['name'],{'name':'Cabin'},where={'name':'Cabin'})],visible=['Cabin','Family']),
        step('delete','Delete the empty Cabin household.','Household management retains Family and no longer lists Cabin.',
             [go(hp),{'op':'click','tag':'button','text':'','enabled':True,'region':[1100,200,1280,500]},button('Confirm'),go(hp)],
             [read('admin/households',['name'],[{'name':'Family'}],collection=True)],visible=['Family'],depends=['create']),
    ])
    user={'username':'robin','fullName':'Robin Baker','email':'robin@example.com','password':'RobinPassword1','admin':False}
    add('admin-users','admin-users',[],[
        step('create','Create a non-administrator user in Home / Family: username "robin", full name "Robin Baker", email "robin@example.com", password "RobinPassword1".',
             'User management displays the new Robin Baker account with the requested identity and household.',
             [go('/admin/manage/users/create'),{'op':'choice','tag':'div','role':'combobox','text':'User Group','value':'Home'},
              {'op':'choice','role':'combobox','text':'User Household','value':'Family'},
              fill('User Name','robin'),fill('Full Name','Robin Baker'),fill('Email','robin@example.com'),fill('Password','RobinPassword1'),button('Create'),go('/admin/manage/users')],
             [read('admin/users',['username','fullName','email','admin'],{k:user[k] for k in ('username','fullName','email','admin')},where={'username':'robin'},save='robin')],visible=['Robin Baker']),
        step('rename','Change Robin Baker\'s full name to "Robin Cook" in user administration.',
             'The user account shows the saved name Robin Cook.',
             [go('/admin/manage/users/{{robin.id}}'),fill('Full Name','Robin Cook'),button('Update'),go('/admin/manage/users')],
             [read('admin/users/{{robin.id}}',['fullName'],{'fullName':'Robin Cook'})],visible=['Robin Cook'],depends=['create']),
        step('promote','Grant the robin account administrator permission.','The account\'s administrator permission is visibly enabled when reopened.',
             [go('/admin/manage/users/{{robin.id}}'),tick('Administrator',True),button('Update'),go('/admin/manage/users/{{robin.id}}')],
             [read('admin/users/{{robin.id}}',['admin'],{'admin':True})],depends=['create']),
    ])
