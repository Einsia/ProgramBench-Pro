'''Sign-in, recipe discovery, cooking display, imports, images and backups.'''
import base64,json
from specification import api, recipe, read, step
from gui_recipes import PATH,go,button,fill,edit,observe
from api_files import JSONLD,png


def build(add):
    add('session','session',[],[
        step('refused','Try to sign in as admin with password "IncorrectPassword", then open your profile.',
             'The protected profile still requires sign-in after the rejected login attempt.',
             [go('/login'),{'op':'fill','name':'username','value':'admin'},{'op':'fill','name':'password','value':'IncorrectPassword'},button('Login'),go('/user/profile')],
             visible=['Login'],requires=['signin/visible']),
        step('signin','Sign in as admin using password "MyPassword" and open the recipe collection.',
             'The application is authenticated as the initial administrator and the recipe collection is available.',
             [go('/login'),{'op':'fill','name':'username','value':'admin'},{'op':'fill','name':'password','value':'MyPassword'},button('Login'),go('/g/home')],visible=['Change Me','Recipes']),
        step('signout','Sign out, then try to open your profile.',
             'The application requests sign-in again instead of showing an authenticated profile.',
             [button('Logout'),go('/user/profile')],visible=['Login'],depends=['signin'],requires=['signin/visible']),
    ],actor=None)
    setup=[api('cat','POST','organizers/categories',{'name':'Dinner'},save='cat'),
           api('tag','POST','organizers/tags',{'name':'Quick'},save='tag'),
           api('tool','POST','organizers/tools',{'name':'Stockpot'},save='tool')]
    setup+=recipe(extra={'recipeCategory':['{{cat}}'],'tags':['{{tag}}'],'tools':['{{tool}}']})+recipe('Apple Pie','apple-pie')
    add('recipe-discovery','recipe-discovery',setup,[
        step('name','Search the recipe collection for "Tomato".','The results offer Tomato Soup and exclude Apple Pie.',
             [go('/g/home?search=Tomato')],visible=['Tomato Soup']),
        step('category','Find recipes in the Dinner category.','The filtered collection offers Tomato Soup and excludes Apple Pie.',
             [go('/g/home?categories={{cat.id}}')],visible=['Tomato Soup']),
        step('tag','Find recipes tagged Quick.','The filtered collection offers Tomato Soup and excludes Apple Pie.',
             [go('/g/home?tags={{tag.id}}')],visible=['Tomato Soup']),
        step('tool','Find recipes that require Stockpot.','The filtered collection offers Tomato Soup and excludes Apple Pie.',
             [go('/g/home?tools={{tool.id}}')],visible=['Tomato Soup']),
    ])
    setup=[api('food','POST','foods',{'name':'tomato','pluralName':'tomatoes'},save='food')]+recipe(extra={
        'recipeServings':4,'recipeIngredient':[{'quantity':2,'food':'{{food}}','note':'ripe'}],
        'recipeInstructions':[{'summary':'Chop','text':'Chop the tomatoes into small pieces.'}, {'summary':'Simmer','text':'Cook slowly for twenty minutes.'}]})
    add('recipe-cooking','recipe-cooking',setup,[
        step('scale','Display Tomato Soup scaled from 4 servings to 8 servings.',
             'The page shows 8 servings and doubles the tomato quantity from 2 to 4.',
             [go(PATH)]+[button('Increase Scale by 1') for _ in range(4)],
             visible=['Serves 8']),
        step('cook','Open cooking mode for Tomato Soup.','The cooking view shows the Chop and Simmer instructions as actionable cooking steps.',
             [go(PATH),button('Cook Mode')],visible=['Chop the tomatoes into small pieces.','Cook slowly for twenty minutes.']),
    ])
    add('recipe-nutrition','recipe-nutrition',recipe(extra={'nutrition':{'calories':'320','proteinContent':'12'}}),[
        step('show','Enable nutrition values on Tomato Soup.','The saved recipe visibly displays its nutrition values, including 320 calories and 12 protein.',
             edit(button('Settings'),{'op':'tick','label':'Show Nutrition Values','value':True},{'op':'press','key':'Escape'})+[{'op':'scroll','delta_y':700}],
             [observe(['settings.showNutrition'],{'settings.showNutrition':True})],visible=['320','12']),
    ])
    encoded=base64.b64encode(png(240,160,(20,160,80))).decode()
    add('recipe-image','recipe-image',recipe(),[
        step('upload','Set the image of Tomato Soup to the provided soup.png file.',
             'The recipe header displays the supplied green image.',
             [go(PATH+'?edit=true'),button('Image'),button('Upload'),{'op':'upload','filename':'soup.png','mime_type':'image/png','base64':encoded},button('Save'),go(PATH)],
             [read('recipes/tomato-soup',['image'])]),
    ],inputs={'file':{'name':'soup.png','base64':encoded}})
    data=json.dumps(JSONLD,ensure_ascii=False)
    add('recipe-import','recipe-import',[],[
        step('import','Import this recipe from JSON-LD:\n```json\n'+data+'\n```',
             'The imported Lentil Stew recipe displays its description, ingredients and instructions.',
             [go('/g/home/r/create/html'),{'op':'fill','tag':'textarea','value':data},button('Create'),go('/g/home/r/lentil-stew')],
             [read('recipes/lentil-stew',['name','description'],{'name':'Lentil Stew','description':'Hearty and warm'})],visible=['Lentil Stew','Hearty and warm','Chop the vegetables.']),
    ])
    add('site-backups','site-backups',recipe(),[
        step('create','Create a backup of the current site.','The backup page lists a newly created backup with its size and available download/restore actions.',
             [go('/admin/backups'),button('Create A Backup')],[read('admin/backups',['imports.0.name'])],visible=['Download']),
        step('delete','Delete the backup you just created.','The backup table reports no remaining backups.',
             [go('/admin/backups'),{'op':'click','tag':'button','text':'','enabled':True,'region':[256,290,1280,420]},button('Confirm'),go('/admin/backups')],
             [read('admin/backups',['imports'],{'imports':[]})],visible=['No data available'],depends=['create']),
    ])
