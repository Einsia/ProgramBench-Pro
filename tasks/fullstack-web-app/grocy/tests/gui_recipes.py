"""Recipe preparation, ingredient changes, fulfillment and meal plan interactions."""
from specification import api,read,step
from gui_common import base,product,stock,go,button,fill
from gui_stock import choose_product,amount
from gui_master import field


def recipe_setup(stocked=True):
    setup=base()+[product()]
    if stocked:setup.append(stock(amount=8))
    setup += [api('recipe','POST','objects/recipes',{'name':'Rice bowl','base_servings':2,'description':'Cook gently'},save='recipe'),
              api('ingredient','POST','objects/recipes_pos',{'recipe_id':'{{recipe.created_object_id}}','product_id':'{{product.created_object_id}}',
                 'amount':2,'qu_id':'{{unit.created_object_id}}','ingredient_group':'Main','note':'Rinse first'},save='ingredient')]
    return setup


def build(add):
    add('gui-recipe-authoring','recipe authoring',base()+[product()], [
      step('create','Create a recipe named "Rice bowl" for 2 servings, with preparation text "Rinse rice and simmer gently." Save it.',
           'The saved recipe visibly shows its name, servings and preparation text.',
           [go('/recipe/new'),fill('name','Rice bowl'),fill('base_servings','2'),
            {'op':'form','fields':[{'action':'editor','target':{'role':'textbox'},'value':'Rinse rice and simmer gently.'}]},
            button('Save & return to recipes'),{'op':'save-named','entity':'recipes','name':'Rice bowl','save':'recipe'},go('/recipes?recipe={{recipe.id}}')],
           checks=[read('objects/recipes',fields=['name','base_servings'],where={'name':'Rice bowl'},expected={'name':'Rice bowl','base_servings':2},save='recipe')],visible=['Rice bowl','Rinse rice and simmer gently.']),
      step('ingredient','Add Rice as an ingredient of Rice bowl: 2 Items, group "Main", note "Rinse first". Save it.',
           'Rice bowl visibly lists 2 Items of Rice under Main with the ingredient note.',
           [go('/recipe/{{recipe.id}}/pos/new'),choose_product(),amount(2),fill('ingredient_group','Main'),fill('note','Rinse first'),button('Save'),go('/recipes?recipe={{recipe.id}}')],
           checks=[read('objects/recipes_pos',fields=['product_id','amount','ingredient_group','note'],collection=True,
             expected=[{'product_id':'{{product.created_object_id}}','amount':2,'ingredient_group':'Main','note':'Rinse first'}],save='ingredients')],visible=['Rice','Main','Rinse first'],depends=['create']),
      step('edit-ingredient','Change the Rice ingredient in Rice bowl to 3 Items and its note to "Wash thoroughly". Save it.',
           'The recipe visibly shows 3 Items of Rice and the new note.',
           [go('/recipe/{{recipe.id}}/pos/{{ingredients.0.id}}'),choose_product(),amount(3),fill('note','Wash thoroughly'),button('Save'),go('/recipes?recipe={{recipe.id}}')],
           checks=[read('objects/recipes_pos',fields=['amount','note'],collection=True,expected=[{'amount':3,'note':'Wash thoroughly'}])],visible=['Wash thoroughly'],depends=['ingredient']),
    ])
    add('gui-recipe-cooking','recipe fulfillment and consumption',recipe_setup(),[
      step('view','Show Rice bowl with its ingredient requirements and stock fulfillment.',
           'The recipe visibly lists Rice and indicates that enough stock is available.',
           [go('/recipes?recipe={{recipe.created_object_id}}')],checks=[],visible=['Rice bowl','Enough in stock','Rinse first']),
      step('scale','Set Rice bowl desired servings to 4 and show the recalculated recipe.',
           'The recipe visibly shows 4 desired servings and 4 Items of Rice.',
           [fill('servings-scale','4'),{'op':'press','key':'Tab','target':{'name':'servings-scale'}}],
           checks=[read('objects/recipes/{{recipe.created_object_id}}',fields=['desired_servings'],expected={'desired_servings':4})],visible=['Rice'],depends=['view']),
      step('cook','Consume all ingredients required to make Rice bowl for the current 4 servings. Show the stock overview.',
           'Rice stock visibly decreases from 8 Items to 4 Items.',
           [go('/recipes?recipe={{recipe.created_object_id}}'),{'op':'click','target':{'title':'Consume all ingredients needed by this recipe'}},button('Yes'),go('/stockoverview')],
           checks=[read('stock/products/{{product.created_object_id}}',fields=['stock_amount'],expected={'stock_amount':4})],visible=['Rice','4 Items'],depends=['scale']),
    ])
    add('gui-recipe-shopping','recipe shortages and shopping list',recipe_setup(False),[
      step('shortage','Show Rice bowl and inspect its missing ingredients.',
           'The recipe visibly identifies Rice as insufficient in stock.',
           [go('/recipes?recipe={{recipe.created_object_id}}')],checks=[],visible=['Rice bowl','Not enough in stock']),
      step('add-missing','Put the missing ingredients for Rice bowl on the shopping list and show that list.',
           'The shopping list visibly contains the missing 2 Items of Rice.',
           [{'op':'click','target':{'title':'Put missing products on shopping list'}},button('Yes'),go('/shoppinglist')],
           checks=[read('objects/shopping_list',fields=['product_id','amount'],collection=True,expected=[{'product_id':'{{product.created_object_id}}','amount':2}])],visible=['Rice','2 Items'],depends=['shortage']),
      step('fulfillment','Show Rice bowl again to inspect whether its shortage is covered by the shopping list.',
           'The recipe visibly indicates that the missing ingredients are already on the shopping list.',
           [go('/recipes?recipe={{recipe.created_object_id}}')],
           checks=[read('recipes/{{recipe.created_object_id}}/fulfillment',fields=['need_fulfilled_with_shopping_list'],expected={'need_fulfilled_with_shopping_list':1})],visible=['already on the shopping list'],depends=['add-missing']),
    ])
    setup=recipe_setup()+[api('section','POST','objects/meal_plan_sections',{'name':'Dinner','sort_number':1,'time_info':'18:30'},save='section')]
    add('gui-mealplan','meal planning',setup,[
      step('add','Plan Rice bowl for dinner on 2026-03-10, with 2 servings.',
           'The meal plan visibly contains Rice bowl on March 10.',
           [go('/mealplan?week=2026-03-10'),{'op':'click','target':{'title':'Add recipe','nth':2}},
            {'op':'choose','value':'Rice bowl','target':{'tag':'input','type':'text','nth':1}},fill('recipe_servings','2'),{'op':'select','target':{'name':'section_id_recipe'},'value':'Dinner'},button('Save')],
           checks=[read('objects/meal_plan',fields=['day','recipe_id','recipe_servings'],where={'recipe_id':'{{recipe.created_object_id}}'},
             expected={'day':'2026-03-10','recipe_id':'{{recipe.created_object_id}}','recipe_servings':2},save='meal')],visible=['Rice bowl']),
      step('calendar','Show the calendar for March 2026 to inspect the planned Rice bowl meal.',
           'The calendar visibly includes Rice bowl on March 10.',
           [go('/calendar')],checks=[],visible=['Rice bowl'],depends=['add']),
    ])
