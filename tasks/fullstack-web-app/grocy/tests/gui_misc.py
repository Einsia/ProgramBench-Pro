"""Shopping, accounts, preferences, custom fields and summary views."""
from specification import api,read,step
from gui_common import base,product,stock,go,button,fill,select,tick
from gui_stock import choose_product,amount
from gui_master import field


def build(add):
    setup=base()+[product(),api('list','POST','objects/shopping_lists',{'name':'Weekend'},save='list')]
    add('gui-shopping','shopping list',setup,[
      step('add','Add 3 Items of Rice to the Weekend shopping list with note "Brown rice". Show that list.',
           'Weekend visibly contains 3 Items of Rice and the note Brown rice.',
           [go('/shoppinglistitem/new'),select('shopping_list_id','Weekend'),choose_product(),amount(3),fill('note','Brown rice'),button('Save'),go('/shoppinglist?list={{list.created_object_id}}')],
           checks=[read('objects/shopping_list',fields=['product_id','amount','note','shopping_list_id'],where={'product_id':'{{product.created_object_id}}'},
             expected={'product_id':'{{product.created_object_id}}','amount':3,'note':'Brown rice','shopping_list_id':'{{list.created_object_id}}'},save='item')],visible=['Rice','Brown rice','3 Items']),
      step('note','Add a note-only item "Bring reusable bags" to Weekend, then show the list.',
           'Weekend visibly contains the note-only item alongside Rice.',
           [go('/shoppinglistitem/new'),select('shopping_list_id','Weekend'),fill('note','Bring reusable bags'),button('Save'),go('/shoppinglist?list={{list.created_object_id}}')],
           checks=[read('objects/shopping_list',fields=['note'],where={'note':'Bring reusable bags'},expected={'note':'Bring reusable bags'})],visible=['Rice','Bring reusable bags'],depends=['add']),
      step('edit','Change the Rice item on Weekend to 5 Items and note "Whole grain". Save it.',
           'The shopping list visibly shows 5 Items of Rice with note Whole grain.',
           [go('/shoppinglistitem/{{item.id}}'),amount(5),fill('note','Whole grain'),button('Save'),go('/shoppinglist?list={{list.created_object_id}}')],
           checks=[read('objects/shopping_list/{{item.id}}',fields=['amount','note'],expected={'amount':5,'note':'Whole grain'})],visible=['Rice','5 Items','Whole grain'],depends=['add']),
      step('done','Mark the Rice item on Weekend done, then filter the list to show only done items.',
           'The filtered list visibly shows Rice as done.',
           [go('/shoppinglist?list={{list.created_object_id}}'),{'op':'click','target':{'title':'Mark this item as done','nth':1}},
            {'op':'select','target':{'tag':'select','nth':1},'value':'Only done items'}],
           checks=[read('objects/shopping_list/{{item.id}}',fields=['done'],expected={'done':1})],visible=['Rice'],depends=['edit']),
      step('clear-done','Clear done items from Weekend while retaining the note Bring reusable bags. Show the list.',
           'Rice is absent and Bring reusable bags remains visible.',
           [go('/shoppinglist?list={{list.created_object_id}}'),button('Clear done items'),go('/shoppinglist?list={{list.created_object_id}}')],
           checks=[read('objects/shopping_list',fields=['note'],params={'query[]':'shopping_list_id={{list.created_object_id}}'},collection=True,expected=[{'note':'Bring reusable bags'}])],visible=['Bring reusable bags'],depends=['done','note'],requires=['add/visible']),
    ])
    add('gui-users','user account management',[],[
      step('create','Create user "casey" with first name "Casey", last name "Morgan", password "Casey-Local-42!". Save it.',
           'Casey Morgan is visible as a saved user with username casey.',
           [go('/user/new'),fill('username','casey'),fill('first_name','Casey'),fill('last_name','Morgan'),fill('password','Casey-Local-42!'),fill('password_confirm','Casey-Local-42!'),button('Save'),go('/users')],
           checks=[read('users',fields=['username','first_name','last_name'],where={'username':'casey'},expected={'username':'casey','first_name':'Casey','last_name':'Morgan'},save='user')],visible=['casey','Casey','Morgan']),
      step('edit','Change casey last name to "Reed" and save it.',
           'The user list visibly shows Casey Reed.',
           [go('/user/{{user.id}}'),fill('last_name','Reed'),button('Save'),go('/users')],
           checks=[read('users',fields=['last_name'],where={'username':'casey'},expected={'last_name':'Reed'})],visible=['casey','Reed'],depends=['create']),
      step('login','Sign out of admin and sign in as casey with password Casey-Local-42!.',
           'The authenticated interface visibly identifies the signed-in user as casey or Casey Reed.',
           [go('/logout'),fill('username','casey'),{'op':'fill','target':{'label':'Password'},'value':'Casey-Local-42!'},button('OK'),go('/stockoverview')],
           checks=[],visible=['casey'],depends=['edit']),
      step('logout','Sign out and show the sign-in page.',
           'The sign-in page is visible and offers username and password entry.',
           [go('/logout')],checks=[],visible=['Username','Password'],depends=['login']),
    ])
    # Product preferences have observable saved controls and direct per-user state.
    preferences=[
      ('stock-due','/stocksettings','Due soon days','stock_due_soon_days','9'),
      ('purchase-default','/stocksettings','Default amount for purchase','stock_default_purchase_amount','2'),
      ('consume-default','/stocksettings','Default amount for consume','stock_default_consume_amount','3'),
      ('chore-due','/choressettings','Due soon days','chores_due_soon_days','8'),
      ('battery-due','/batteriessettings','Due soon days','batteries_due_soon_days','10'),
      ('task-due','/taskssettings','Due soon days','tasks_due_soon_days','12'),
    ]
    for key,path,label,setting,value in preferences:
        add('gui-settings-'+key,'personal settings',[],[
          step('change','Set '+label.lower()+' to '+value+' in the '+path.strip('/')+' settings.',
               'The saved setting visibly retains the value '+value+' when revisited.',
               [go(path),{'op':'fill','target':{'label':label},'value':value},{'op':'press','key':'Tab'},go(path)],
               checks=[read('user/settings/'+setting,fields=['value'],expected={'value':value})]),
        ])
    setup=base()+[api('equipment','POST','objects/equipment',{'name':'Mixer'},save='equipment')]
    add('gui-userfields','custom field definition and value',setup,[
      step('define','Create a single-line text userfield for equipment named "serial", caption "Serial number", and show it as a column in tables.',
           'The saved custom field is visibly listed with its entity, name and caption.',
           [go('/userfield/new'),select('entity','equipment'),fill('name','serial'),fill('caption','Serial number'),select('type','Text (single line)'),
            tick('show_as_column_in_tables'),button('Save'),go('/userfields')],
           checks=[read('objects/userfields',fields=['entity','name','caption','type','show_as_column_in_tables'],where={'name':'serial'},
              expected={'entity':'equipment','name':'serial','caption':'Serial number','type':'text-single-line','show_as_column_in_tables':1},save='field')],visible=['serial','Serial number']),
      step('value','Set Mixer Serial number to "MX-2048" and save it.',
           'Mixer visibly shows the saved Serial number MX-2048.',
           [go('/equipment/{{equipment.created_object_id}}'),{'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'MX-2048'},button('Save'),go('/equipment')],
           checks=[read('userfields/equipment/{{equipment.created_object_id}}',fields=['serial'],expected={'serial':'MX-2048'})],visible=['Mixer','MX-2048'],depends=['define']),
      step('update','Change Mixer Serial number to "MX-4096" and save it.',
           'Mixer visibly shows the updated Serial number MX-4096.',
           [go('/equipment/{{equipment.created_object_id}}'),{'op':'fill','target':{'tag':'input','type':'text','nth':1},'value':'MX-4096'},button('Save'),go('/equipment')],
           checks=[read('userfields/equipment/{{equipment.created_object_id}}',fields=['serial'],expected={'serial':'MX-4096'})],visible=['Mixer','MX-4096'],depends=['value']),
    ])
    setup=base()+[product(),stock(),product('Expired milk','milk',due_type=2),stock('milk',amount=2,due='2026-03-08'),
                 product('Low flour','flour',min_stock_amount=5),stock('flour',amount=1)]
    add('gui-stock-views','inventory filters and reports',setup,[
      step('expired','Show expired inventory so Expired milk can be inspected.',
           'The filtered inventory visibly shows Expired milk as expired.',
           [go('/stockoverview'),{'op':'select','target':{'tag':'select','nth':2},'value':'Expired'}],checks=[],visible=['Expired milk']),
      step('minimum','Show products below their defined minimum stock amount.',
           'The filtered inventory visibly shows Low flour below its minimum.',
           [go('/stockoverview'),{'op':'select','target':{'tag':'select','nth':2},'value':'Below min. stock amount'}],checks=[],visible=['Low flour']),
      step('search','Find Rice in the stock overview using its name.',
           'The inventory search visibly selects Rice and shows its quantity.',
           [go('/stockoverview'),{'op':'fill','target':{'placeholder':'Search'},'value':'Rice'}],checks=[],visible=['Rice','8 Items']),
      step('location-sheet','Show the contents of Pantry as a location content sheet.',
           'The location sheet visibly lists Pantry stock including Rice, Expired milk and Low flour.',
           [go('/locationcontentsheet?location={{pantry.created_object_id}}')],checks=[],visible=['Rice','Expired milk','Low flour']),
      step('spendings','Show stock spending reports for the stocked products.',
           'The report visibly presents recorded spending for the stocked products.',
           [go('/stockreports/spendings')],checks=[],visible=['Rice','Expired milk','Low flour']),
    ])
