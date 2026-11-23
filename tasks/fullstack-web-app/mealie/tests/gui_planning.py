'''Shopping, cookbook filters and the household meal calendar.'''
from specification import api, recipe, read, step
from gui_recipes import go, button, fill

LISTS='households/shopping/lists'

def items(expected):
    return read(LISTS+'/{{shopping.id}}',['note','checked'],expected,collection=True,at='listItems')


def build(add):
    lp='/shopping-lists/{{shopping.id}}'
    add('shopping-list','shopping-list',[api('reserve','POST',LISTS,{'name':'Reserve'})],[
        step('create','Create a shopping list named "Groceries".','Groceries appears among the shopping lists.',
             [go('/shopping-lists?disableRedirect=true'),button('Create'),fill('New List','Groceries'),button('Create'),go('/shopping-lists?disableRedirect=true')],
             [read(LISTS,['name'],{'name':'Groceries'},where={'name':'Groceries'},save='shopping')],visible=['Groceries']),
        step('items','Add "lemons" and "bread" as two unchecked items to Groceries.','Both grocery items are displayed in the list as items still to buy.',
             [go(lp),fill('Add Item','lemons',tag='input'),{'op':'press','key':'Enter'},fill('Add Item','bread',tag='input'),{'op':'press','key':'Enter'}],
             [items([{'note':'lemons','checked':False},{'note':'bread','checked':False}])],visible=['lemons','bread'],depends=['create']),
        step('check-all','Mark every item in Groceries as purchased.','The list presents both items as checked/purchased.',
             [go(lp),button('Check All Items'),button('Confirm')],
             [items([{'note':'lemons','checked':True},{'note':'bread','checked':True}])],depends=['items']),
        step('uncheck-all','Return every purchased item in Groceries to the items still to buy.','Both items are again displayed as unchecked.',
             [go(lp),button('Uncheck All Items'),button('Confirm')],
             [items([{'note':'lemons','checked':False},{'note':'bread','checked':False}])],visible=['lemons','bread'],depends=['check-all']),
        step('delete','Delete the Groceries shopping list.','The shopping-list collection retains Reserve and no longer contains Groceries.',
             [{'op':'list-delete','name':'Groceries'},button('Confirm'),go('/shopping-lists?disableRedirect=true')],
             [read(LISTS,['name'],[{'name':'Reserve'}],collection=True)],visible=['Reserve'],depends=['create']),
    ])
    setup=[api('list','POST',LISTS,{'name':'Market'},save='shopping'),
           api('item1','POST','households/shopping/items',{'shoppingListId':'{{shopping.id}}','note':'bought apples','checked':True}),
           api('item2','POST','households/shopping/items',{'shoppingListId':'{{shopping.id}}','note':'still need rice','checked':False})]
    add('shopping-cleanup','shopping-cleanup',setup,[
        step('delete-checked','Remove the purchased items from Market while retaining the items still to buy.',
             'Market still shows still need rice and no longer shows bought apples.',
             [go(lp),button('Delete Checked'),button('Confirm')],
             [items([{'note':'still need rice','checked':False}])],visible=['still need rice']),
    ])
    setup=recipe(extra={'recipeIngredient':[{'quantity':2,'note':'ripe tomatoes'},{'quantity':1,'note':'olive oil'}]})+[
        api('list','POST',LISTS,{'name':'Soup Shopping'},save='shopping')]
    add('shopping-from-recipe','shopping-from-recipe',setup,[
        step('add','Add the ingredients of Tomato Soup to Soup Shopping.','The shopping list displays the recipe\'s tomato and olive oil ingredients and links them to Tomato Soup.',
             [{'op':'recipe-menu','slug':'tomato-soup','name':'Add to List'},button('Add to List'),go(lp)],
             [read(LISTS+'/{{shopping.id}}',['note'],[{'note':'ripe tomatoes'},{'note':'olive oil'}],collection=True,at='listItems')],visible=['ripe tomatoes','olive oil','Tomato Soup']),
    ])
    setup=[api('cat','POST','organizers/categories',{'name':'Dinner'},save='cat')]+recipe(extra={'recipeCategory':['{{cat}}']})+recipe('Apple Pie','apple-pie')
    book='/g/home/cookbooks'
    add('cookbook','cookbook',setup,[
        step('create','Create a cookbook named "Dinner Ideas", description "Meals for the evening", containing recipes in the Dinner category.',
             'Dinner Ideas is available as a cookbook with the supplied description and Dinner category filter.',
             [go(book),button('Create'),fill('Cookbook Name','Dinner Ideas'),fill('Description','Meals for the evening'),
              {'op':'autocomplete','tag':'input','role':'combobox','value':'Dinner'},button('Save'),go(book),{'op':'click','tag':'button','text':'Dinner Ideas'}],
             [read('households/cookbooks',['name','description'],{'name':'Dinner Ideas','description':'Meals for the evening'},where={'name':'Dinner Ideas'},save='book')],visible=['Dinner Ideas']),
        step('browse','Open Dinner Ideas and inspect its recipes.','The cookbook contains Tomato Soup and excludes Apple Pie, which does not belong to Dinner.',
             [go('/g/home/cookbooks/dinner-ideas')],visible=['Tomato Soup'],depends=['create']),
        step('rename','Rename Dinner Ideas to "Evening Favorites".','The cookbook is shown with its new name while retaining its filter.',
             [go(book),{'op':'click','tag':'button','text':'Dinner Ideas'},fill('Cookbook Name','Evening Favorites'),button('Save'),go(book),{'op':'click','tag':'button','text':'Evening Favorites'}],
             [read('households/cookbooks',['name'],{'name':'Evening Favorites'},where={'name':'Evening Favorites'})],visible=['Evening Favorites'],depends=['create']),
        step('delete','Delete Evening Favorites.','The cookbook management page remains available and Evening Favorites is absent.',
             [go(book),{'op':'click','tag':'button','text':'Evening Favorites'},button('Delete'),button('Confirm'),go(book)],
             [read('households/cookbooks',['name'],[],collection=True)],visible=['Cookbooks'],depends=['rename']),
    ])
    plan='/household/mealplan/planner/view'
    setup=recipe()+[api('soup','GET','recipes/tomato-soup',save='soup')]
    add('meal-calendar','meal-calendar',setup,[
        step('dinner','Add Tomato Soup to today\'s dinner plan.','Today\'s meal calendar displays Tomato Soup as dinner.',
             [{'op':'recipe-menu','slug':'tomato-soup','name':'Add to Plan'},button('Confirm'),go(plan)],
             [read('households/mealplans',['recipeId','entryType'],{'recipeId':'{{soup.id}}','entryType':'dinner'},where={'recipeId':'{{soup.id}}'},save='meal')],visible=['Tomato Soup']),
        step('type','Change today\'s Tomato Soup meal from dinner to lunch.','The meal calendar identifies the existing Tomato Soup entry as lunch.',
             [go('/household/mealplan/planner/edit'),{'op':'click','text':'Dinner'}, {'op':'click','role':'listitem','text':'Lunch'},go(plan)],
             [read('households/mealplans/{{meal.id}}',['entryType'],{'entryType':'lunch'})],visible=['Tomato Soup'],depends=['dinner']),
    ])
    setup=[api('cat','POST','organizers/categories',{'name':'Dinner'},save='cat')]
    rp='/household/mealplan/settings'
    add('meal-rules','meal-rules',setup,[
        step('create','Create a meal-plan rule for Friday dinners that limits selection to the Dinner category.',
             'The saved rule visibly applies to Friday dinner and uses the Dinner category filter.',
             [go(rp),{'op':'choice','role':'combobox','has':'Rule Day','value':'Friday'},
              {'op':'choice','role':'combobox','has':'Meal Type','value':'Dinner'},
              {'op':'autocomplete','tag':'input','role':'combobox','value':'Dinner'},button('Create'),go(rp),{'op':'scroll','delta_y':600}],
             [read('households/mealplans/rules',['day','entryType'],{'day':'friday','entryType':'dinner'},where={'day':'friday'})],visible=['fridays for dinner']),
        step('delete','Delete the Friday dinner rule.','Meal-plan settings remain available and the Friday dinner rule is removed.',
             [go(rp),{'op':'scroll','delta_y':600},button('Delete'),go(rp)],
             [read('households/mealplans/rules',['day'],[],collection=True)],visible=['Meal Plan Rules'],depends=['create']),
    ])
