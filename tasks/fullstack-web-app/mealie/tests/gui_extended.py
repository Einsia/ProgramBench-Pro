'''Inventory, scaled planning, local data downloads, reset and sharing episodes.'''
from specification import api,recipe,read,step
from gui_recipes import go,button,fill


def build(add):
    setup=[api('cat','POST','organizers/categories',{'name':'Pantry'},save='cat'),api('food','POST','foods',{'name':'tomato'},save='food'),
           api('tool','POST','organizers/tools',{'name':'Stockpot'},save='tool'),
           api('home','GET','households/self',save='home')]
    setup+=recipe('Pantry Soup','pantry-soup',{'recipeIngredient':[{'quantity':2,'food':'{{food}}'}],'tools':['{{tool}}'],'recipeCategory':['{{cat}}']})
    setup+=recipe('Plain Bread','plain-bread')
    add('inventory-finder','inventory-finder',setup,[
        step('food','Mark tomato as On Hand in your household.',
             'The tomato entry is saved as available in the household inventory.',
             [go('/group/data/foods'),{'op':'table-action','name':'tomato','action':'edit'},
              {'op':'tick','label':'On Hand','value':True},button('Confirm'),go('/group/data/foods')],
             [read('foods/{{food.id}}',['householdsWithIngredientFood'],{'householdsWithIngredientFood':['{{home.slug}}']})],visible=['tomato']),
        step('tool','Mark Stockpot as On Hand in your household.',
             'Stockpot is saved as an available household tool.',
             [go('/group/data/tools'),{'op':'table-action','name':'Stockpot','action':'edit'},
              {'op':'tick','label':'On Hand','value':True},button('Confirm'),go('/group/data/tools')],
             [read('organizers/tools/{{tool.id}}',['householdsWithTool'],{'householdsWithTool':['{{home.slug}}']})],visible=['Stockpot']),
        step('find','Use Recipe Finder with category Pantry and no missing ingredients or tools, including foods and tools On Hand.',
             'Recipe Finder offers Pantry Soup as a match for tomato and the available Stockpot.',
             [go('/g/home/recipes/finder'),button('Other Filters'),
              {'op':'autocomplete','tag':'input','role':'combobox','value':'Pantry','escape':False},button('Confirm'),button('Settings'),
              fill('Max Missing Ingredients','0'),fill('Max Missing Tools','0'),
              {'op':'tick','label':'Include Ingredients On Hand','value':True},
              {'op':'tick','label':'Include Tools On Hand','value':True},{'op':'press','key':'Escape'},
              {'op':'wait','seconds':1}],visible=['Pantry Soup'],depends=['food','tool']),
    ],budget={'tokens':2_000_000})
    for kind,route in [('foods','foods'),('units','units')]:
        setup=[api('first','POST',route,{'name':'Alpha'}),api('second','POST',route,{'name':'Beta'})]
        add('download-'+kind,'download-'+kind,setup,[
            step('download','Download the '+kind+' data as JSON.',
                 'The data management page makes a JSON download available for its Alpha and Beta entries.',
                 [go('/group/data/'+kind),button('Download')],
                 [{'download':{'format':'json','names':['Alpha','Beta']}}],visible=['Alpha','Beta'])
        ])
    setup=[api('from','POST','organizers/categories',{'name':'Weekday'},save='source'),
           api('to','POST','organizers/categories',{'name':'Weeknight'},save='destination')]
    setup+=recipe('Merge Soup','merge-soup',{'recipeCategory':['{{source}}','{{destination}}']})
    add('merge-category','merge-category',setup,[
        step('merge','Combine category Weekday into Weeknight.',
             'Weeknight remains in category management and Weekday is removed.',
             [go('/group/data/categories'),button('Combine'),
              {'op':'autocomplete','label':'Source Category','tag':'input','value':'Weekday','escape':False},
              {'op':'autocomplete','label':'Target Category','tag':'input','value':'Weeknight','escape':False},button('Confirm'),go('/group/data/categories')],
             [read('organizers/categories',['name'],[{'name':'Weeknight'}],collection=True)],visible=['Weeknight']),
        step('recipe','Open Merge Soup and inspect its categories.',
             'Merge Soup uses Weeknight exactly once and no longer uses Weekday.',
             [go('/g/home/r/merge-soup')],[read('recipes/merge-soup',['recipeCategory.0.name'],{'recipeCategory.0.name':'Weeknight'})],
             visible=['Weeknight'],depends=['merge'])
    ])
    setup=[api('user','POST','admin/users',{'username':'reset-user','fullName':'Reset User','email':'reset@example.com','password':'BeforeReset123','admin':False}),
           api('token','POST','admin/users/password-reset-token',{'email':'reset@example.com'},save='reset')]
    reset='/reset-password?token={{reset.token}}'
    add('password-reset','password-reset',setup,[
        step('reset','The reset form is open. Reset reset@example.com to password "AfterReset456".',
             'The completed reset returns to the sign-in page.',
             [go(reset),fill('Email','reset@example.com'),fill('Password','AfterReset456'),fill('Confirm Password','AfterReset456'),button('Reset Password')],
             [{'auth':{'username':'reset-user','password':'AfterReset456'}},{'auth':{'username':'reset-user','password':'BeforeReset123','accepted':False}}],
             visible=['Login'],open_before=reset),
        step('login','Sign in as reset-user with password "AfterReset456" and open the recipe collection.',
             'The authenticated application shows Reset User.',
             [go('/login'),{'op':'fill','name':'username','value':'reset-user'},{'op':'fill','name':'password','value':'AfterReset456'},button('Login'),go('/g/home')],
             visible=['Reset User'],depends=['reset'])
    ],actor=None)
    add('download-recipe','download-recipe',recipe('Travel Soup','travel-soup',{'description':'A recipe to take with you.'}),[
        step('download','Download Travel Soup as a recipe archive.',
             'A recipe ZIP download is available for Travel Soup.',
             [{'op':'recipe-menu','slug':'travel-soup','name':'Download'}],
             [{'download':{'format':'zip'}}],visible=['Travel Soup'])
    ])
    setup=recipe('Share Soup','share-soup',{'description':'Share with a guest.'})+[api('read','GET','recipes/share-soup',save='soup')]
    add('recipe-sharing','recipe-sharing',setup,[
        step('create','Create a private share link for Share Soup.',
             'The recipe sharing view lists an active share link and its expiration date.',
             [{'op':'recipe-menu','slug':'share-soup','name':'Share'},button('New')],
             [read('shared/recipes',['recipeId'],{'recipeId':'{{soup.id}}'},where={'recipeId':'{{soup.id}}'},save='share')],visible=['Expires']),
        step('guest','Sign out and open the provided shared recipe link.',
             'The shared Share Soup recipe is visible without signing in, including its description.',
             [go('/g/home'),button('Logout'),go('/g/home/shared/r/{{share.id}}')],
             [read('recipes/shared/{{share.id}}',['name','description'],{'name':'Share Soup','description':'Share with a guest.'},actor=None)],
             visible=['Share Soup','Share with a guest.'],depends=['create'],open_before='/g/home/shared/r/{{share.id}}'),
        step('revoke','Sign in as admin with MyPassword and revoke the Share Soup share link.',
             'The sharing view no longer lists the revoked link.',
             [{'op':'signin','user':'admin','password':'MyPassword'},{'op':'recipe-menu','slug':'share-soup','name':'Share'},
              {'op':'share-delete'}],
             [read('shared/recipes',['recipeId'],[],collection=True),read('recipes/shared/{{share.id}}',actor=None,status=404)],
             visible=['Share Recipe'],depends=['create']),
    ])
    # The current date is resolved in unscored preparation to keep the frozen manifest stable across days.
    setup=[api('day','TODAY','',save='today')]+recipe('Scaled Soup','scaled-soup',{'recipeServings':4,
      'recipeIngredient':[{'quantity':2,'note':'carrots'},{'quantity':3,'note':'tomatoes'}]})+[
      api('soup','GET','recipes/scaled-soup',save='soup'),
      api('plan','POST','households/mealplans',{'date':'{{today}}','entryType':'dinner','recipeId':'{{soup.id}}','recipeScale':1},save='meal'),
      api('list','POST','households/shopping/lists',{'name':'Meal Groceries'},save='list')]
    planner='/household/mealplan/planner/edit'
    add('scaled-plan-shopping','scaled-plan-shopping',setup,[
        step('scale','Change today\'s Scaled Soup dinner plan from 4 servings to 8 servings.',
             'The meal plan shows Scaled Soup scaled to eight servings (twice its original amount).',
             [go(planner),{'op':'click','text':'Scaled Soup'}]+[button('Increase Scale by 1') for _ in range(4)]+[button('Update'),go(planner)],
             [read('households/mealplans/{{meal.id}}',['recipeScale'],{'recipeScale':2})],visible=['2x']),
        step('day','Add today\'s planned recipes to Meal Groceries, using their planned quantities.',
             'Meal Groceries contains 4 carrots and 6 tomatoes from the doubled Scaled Soup meal.',
             [go('/household/mealplan/planner/view'),{'op':'click','tag':'button','expanded':False,'region':[650,150,780,270]},
              {'op':'click','role':'listitem','text':'Add Day To List'},button('Add to List'),go('/shopping-lists/{{list.id}}')],
             [read('households/shopping/lists/{{list.id}}',['quantity','note'],[{'quantity':4,'note':'carrots'},{'quantity':6,'note':'tomatoes'}],collection=True,at='listItems')],
             visible=['carrots','tomatoes'],depends=['scale']),
        step('plan','Add all recipes in the displayed plan to Meal Groceries once more at the planned quantities.',
             'The list now contains 8 carrots and 12 tomatoes from two additions of the planned double portion.',
             [go('/household/mealplan/planner/view'),{'op':'click','tag':'button','expanded':False,'region':[1190,95,1270,165]},
              {'op':'click','role':'listitem','text':'Add All To List'},button('Add to List'),go('/shopping-lists/{{list.id}}')],
             [read('households/shopping/lists/{{list.id}}',['quantity','note'],[{'quantity':8,'note':'carrots'},{'quantity':12,'note':'tomatoes'}],collection=True,at='listItems'),
              read('recipes/scaled-soup',['recipeServings','recipeIngredient.0.quantity'],{'recipeServings':4,'recipeIngredient.0.quantity':2})],
             visible=['carrots','tomatoes'],depends=['day']),
    ])
    public=[api('group','PUT','groups/preferences',{'privateGroup':False,'showAnnouncements':True}),
            api('household','PUT','households/preferences',{'privateHousehold':False,'firstDayOfWeek':0,
                 'recipePublic':False,'showAnnouncements':True,'lockRecipeEditsFromOtherHouseholds':True})]
    public+=recipe('Public Soup','public-soup',{'description':'Visible to visitors.'})
    add('recipe-publicity','recipe-publicity',public,[
        step('public','Make Public Soup public, then sign out and open it as a visitor.',
             'The visitor can read Public Soup and its description without signing in.',
             [go('/g/home/r/public-soup?edit=true'),button('Settings'),{'op':'tick','label':'Public Recipe','value':True},
              {'op':'press','key':'Escape'},button('Save'),button('Logout'),go('/g/home/r/public-soup')],
             [read('explore/groups/home/recipes/public-soup',['name','description'],{'name':'Public Soup','description':'Visible to visitors.'},actor=None)],
             visible=['Public Soup','Visible to visitors.']),
        step('private','Sign in as admin with MyPassword and make Public Soup private again.',
             'The saved recipe privacy setting is disabled for public access while the owner can still read the recipe.',
             [{'op':'signin','user':'admin','password':'MyPassword'},go('/g/home/r/public-soup?edit=true'),button('Settings'),
              {'op':'tick','label':'Public Recipe','value':False},{'op':'press','key':'Escape'},button('Save'),
              go('/g/home/r/public-soup?edit=true'),button('Settings')],
             [read('recipes/public-soup',['settings.public'],{'settings.public':False}),read('explore/groups/home/recipes/public-soup',actor=None,status=404)],
             depends=['public']),
    ])
    group=[api('group','POST','admin/groups',{'name':'Cabin'},save='group'),
      api('user','POST','admin/users',{'username':'cabin-user','fullName':'Cabin Cook','email':'cabin@example.com',
          'password':'CabinPassword1','group':'Cabin','household':'Family','admin':False,'canManage':True,'canOrganize':True}),
      *recipe('Home Secret','home-secret',{'description':'Only the Home group.'}),
      api('own','POST','recipes',{'name':'Cabin Secret'},actor='cabin-user'),
      api('body','PATCH','recipes/cabin-secret',{'description':'Only the Cabin group.'},actor='cabin-user')]
    add('group-isolation','group-isolation',group,[
        step('own','Open your group recipe collection.',
             'The Cabin collection contains Cabin Secret and does not list Home Secret.',
             [go('/g/cabin')],visible=['Cabin Secret']),
        step('protected','Try to open Home Secret at /g/home/r/home-secret.',
             'The other group\'s private recipe content is unavailable to Cabin Cook.',
             [go('/g/home/r/home-secret')],
             [read('recipes/home-secret',actor='cabin-user',status=404)],depends=['own'],requires=['own/visible']),
    ],actor='cabin-user')
