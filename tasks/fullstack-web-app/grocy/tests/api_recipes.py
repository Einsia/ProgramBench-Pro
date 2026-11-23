"""Recipe scaling, fulfillment, costs, ingredients, nesting, self production and meal planning."""
from harness import Ref,pathref,resolve
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS

FULFILL=['recipe_id','need_fulfilled','need_fulfilled_with_shopping_list','missing_products_count','costs','costs_per_serving']
POS=['recipe_id','product_id','amount','qu_id','note','ingredient_group','only_check_single_unit_in_stock','not_check_stock_fulfillment','price_factor']


def build(s):
    f=foundation(s)
    variants=[('ordinary',{}, {}, {}),('scaled',{'base_servings':2,'desired_servings':4},{},{}),
      ('single-unit',{}, {'only_check_single_unit_in_stock':1},{}),
      ('ignored-ingredient',{}, {'not_check_stock_fulfillment':1},{}),
      ('ignored-product',{}, {}, {'not_check_stock_fulfillment_for_recipes':1}),
      ('price-factor',{}, {'price_factor':.5},{}),('round-up',{'base_servings':3,'desired_servings':2},{'round_up':1},{}),
      ('converted-unit',{}, {'qu_id':f['pack']},{}),('ignore-shopping',{'not_check_shoppinglist':1},{},{}),
      ('variable-amount',{}, {'variable_amount':'To taste'}, {})]
    for name,recipeopts,posopts,productopts in variants:
        s.needs=list(f['needs'])
        pf,p=fx(s,name,'products',product(f,'Ingredient '+name,calories=50,**productopts),'p-'+name)
        rf,r=fx(s,name,'recipes',{'name':'Recipe '+name,'description':'Simmer gently','base_servings':1,'desired_servings':1,**recipeopts},'r-'+name)
        serving=s.api('servings-fixture',name,'desired','PUT',objpath('recipes',r),body={'desired_servings':recipeopts.get('desired_servings',1)},status=204)
        qf,_=fx(s,name,'quantity_unit_conversions',{'from_qu_id':f['pack'],'to_qu_id':f['unit'],'factor':2,'product_id':p},'q-'+name)
        ingredient={'recipe_id':r,'product_id':p,'amount':3,'qu_id':f['unit'],'note':'Fresh','ingredient_group':'Main',**posopts}
        ip,ip_id=fx(s,name,'recipes_pos',ingredient,'i-'+name)
        s.needs=f['needs']+[pf,rf,qf,ip,serving]
        fulfill=pathref('recipes/{id}/fulfillment',id=r)
        projection=readback(fulfill,FULFILL,hint='recipes')
        s.api('recipes',name,'initial-fulfillment','GET',fulfill,fields=FULFILL,hint='recipes')
        bought=s.api('recipes',name,'partial-stock','POST',route(p,'/add'),body={'amount':1,'price':2,'best_before_date':'2026-05-01'},
                     fields=LOG_FIELDS,hint='stock_log',after=projection)
        s.api('recipes',name,'resolved-ingredient','GET','objects/recipes_pos_resolved',params={'query[]':pathref('recipe_id={id}',id=r)},
              hint='recipes_pos',needs=[bought])
        listed=s.api('recipes',name,'shopping-missing','POST',pathref('recipes/{id}/add-not-fulfilled-products-to-shoppinglist',id=r),
                     body={},status=204,needs=[bought],after=projection)
        s.api('recipes',name,'shopping-amount','GET','objects/shopping_list',params={'query[]':pathref('product_id={id}',id=p)},
              fields=['product_id','amount','qu_id'],hint='shopping_list',needs=[listed])
        replenished=s.api('recipes',name,'enough-stock','POST',route(p,'/add'),body={'amount':10,'price':3,'best_before_date':'2026-06-01'},
                          fields=LOG_FIELDS,hint='stock_log',needs=[listed],after=projection)
        consumed=s.api('recipes',name,'consume','POST',pathref('recipes/{id}/consume',id=r),body={},status=204,needs=[replenished],after=entries(p))
        s.api('recipes',name,'consumption-statistics','GET','objects/stock_log',params={'query[]':[pathref('recipe_id={id}',id=r),'transaction_type=consume']},
              fields=['product_id','recipe_id','amount','price','transaction_type'],hint='stock_log',needs=[consumed])
        copied=s.api('recipes',name,'copy','POST',pathref('recipes/{id}/copy',id=r),body={},save='copy-'+name,hint='recipes')
        copyid=Ref('copy-'+name,'created_object_id')
        s.api('recipes',name,'copy-properties','GET',objpath('recipes',copyid),fields=['description','base_servings','desired_servings','not_check_shoppinglist'],hint='recipes',needs=[copied])
        s.api('recipes',name,'copy-ingredients','GET','objects/recipes_pos',params={'query[]':pathref('recipe_id={id}',id=copyid)},
              fields=POS,hint='recipes_pos',needs=[copied])
    # Nest a recipe at a different serving count and copy the complete relation.
    s.needs=list(f['needs'])
    pf,p=fx(s,'nested','products',product(f,'Nested ingredient',calories=20),'nested-p')
    rf,child=fx(s,'nested','recipes',{'name':'Sauce','base_servings':2,'desired_servings':2},'nested-child')
    nf,parent=fx(s,'nested','recipes',{'name':'Pasta','base_servings':1,'desired_servings':2},'nested-parent')
    ip,_=fx(s,'nested','recipes_pos',{'recipe_id':child,'product_id':p,'amount':3,'qu_id':f['unit']},'nested-ingredient')
    nesting,nestid=fx(s,'nested','recipes_nestings',{'recipe_id':parent,'includes_recipe_id':child,'servings':4},'nested-relation')
    sf=s.api('servings-fixture','nested','desired','PUT',objpath('recipes',parent),body={'desired_servings':2},status=204)
    s.needs=f['needs']+[pf,rf,nf,ip,nesting,sf]
    a=s.api('recipes','nested','stock','POST',route(p,'/add'),body={'amount':20,'price':2},fields=LOG_FIELDS,hint='stock_log')
    s.api('recipes','nested','parent-fulfillment','GET',pathref('recipes/{id}/fulfillment',id=parent),fields=FULFILL,hint='recipes',needs=[a])
    s.api('recipes','nested','resolved-amount','GET','objects/recipes_pos_resolved',params={'query[]':pathref('recipe_id={id}',id=parent)},hint='recipes_pos',needs=[a])
    consumed=s.api('recipes','nested','consume-parent','POST',pathref('recipes/{id}/consume',id=parent),body={},status=204,needs=[a],after=entries(p))
    cp=s.api('recipes','nested','copy-parent','POST',pathref('recipes/{id}/copy',id=parent),body={},save='nested-copy',hint='recipes')
    s.api('recipes','nested','copy-relation','GET','objects/recipes_nestings',params={'query[]':pathref('recipe_id={id}',id=Ref('nested-copy','created_object_id'))},
          fields=['recipe_id','includes_recipe_id','servings'],hint='recipes_nestings',needs=[cp])
    s.api('recipes','nested','change-servings','PUT',objpath('recipes_nestings',nestid),body={'servings':1},status=204,
          needs=[consumed],after=readback(pathref('recipes/{id}/fulfillment',id=parent),FULFILL,hint='recipes'))
    # A produced dish is added to stock by recipe consumption.
    s.needs=list(f['needs'])
    pf,p=fx(s,'production','products',product(f,'Raw ingredient'),'production-p')
    of,output=fx(s,'production','products',product(f,'Finished portions',default_best_before_days=7),'production-output')
    rf,r=fx(s,'production','recipes',{'name':'Bake portions','base_servings':2,'desired_servings':4,'product_id':output},'production-r')
    ip,_=fx(s,'production','recipes_pos',{'recipe_id':r,'product_id':p,'amount':3,'qu_id':f['unit']},'production-i')
    sf=s.api('servings-fixture','production','desired','PUT',objpath('recipes',r),body={'desired_servings':4},status=204)
    s.needs=f['needs']+[pf,of,rf,ip,sf]
    a=s.api('recipes','production','stock','POST',route(p,'/add'),body={'amount':10,'price':2},fields=LOG_FIELDS,hint='stock_log')
    a=s.api('recipes','production','consume','POST',pathref('recipes/{id}/consume',id=r),body={},status=204,needs=[a],after=entries(output,4))
    s.api('recipes','production','raw-remainder','GET',route(p),fields=['stock_amount'],want={'stock_amount':4},needs=[a])
    # Meal plan entries create date-specific recipe fulfillment through the normal exposed entities.
    for name,body in [('recipe',{'type':'recipe','recipe_id':r,'recipe_servings':2}),
                       ('product',{'type':'product','product_id':output,'product_amount':1,'product_qu_id':f['unit']}),
                       ('note',{'type':'note','note':'Dinner with friends'})]:
        s.needs=f['needs']+[rf,of]
        added=s.api('mealplan',name,'create','POST','objects/meal_plan',body={'day':'2026-03-12','section_id':f['section'],**body},save='meal-'+name,hint='meal_plan')
        mid=Ref('meal-'+name,'created_object_id');path=objpath('meal_plan',mid)
        s.api('mealplan',name,'read','GET',path,fields=['day','type','recipe_id','recipe_servings','product_id','product_amount','note','section_id','done'],hint='meal_plan',needs=[added])
        moved=s.api('mealplan',name,'move-day','PUT',path,body={'day':'2026-03-14'},status=204,needs=[added],after=readback(path,['day'],{'day':'2026-03-14'}))
        s.api('mealplan',name,'complete','PUT',path,body={'done':1},status=204,needs=[moved],after=readback(path,['done'],{'done':1}))
        removed=s.api('mealplan',name,'delete','DELETE',path,status=204,needs=[moved])
        s.api('mealplan',name,'gone','GET',path,status=404,needs=[removed],requires=[added])
    s.needs=[]
    for op in ['fulfillment','copy','consume']:
        s.api('recipes','missing',op,'GET' if op=='fulfillment' else 'POST','recipes/999999/'+op,body=None if op=='fulfillment' else {},status=400)
