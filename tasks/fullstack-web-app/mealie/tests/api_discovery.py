'''Inventory-aware suggestions, substitutions, tool requirements and scaled meal plans.'''
from harness import Ref,pathref,day


def build(s):
    a=s.api;fx='discovery-fixture'
    a(fx,'owner','household','GET','households/self',save='household')
    for name in ['tomato','rice','butter','olive oil']:
        a(fx,'foods',name.replace(' ','-'),'POST','foods',body={'name':name},save=name)
    a(fx,'foods','substitute','PUT',pathref('foods/{i}',i=Ref('butter','id')),
      body={'name':'butter','substitutions':[{'substituteFoodId':Ref('olive oil','id'),'note':'Use less oil.'}]})
    for name in ['pot','oven']:
        a(fx,'tools',name,'POST','organizers/tools',body={'name':name},save=name)
    recipes=[('Ready Soup',['tomato'],['pot']),('Rice Soup',['tomato','rice'],['pot']),
             ('Roast Tomato',['tomato'],['oven']),('Butter Tomato',['tomato','butter'],['pot'])]
    for name,foods,tools in recipes:
        slug=name.lower().replace(' ','-')
        a(fx,'recipes',slug,'POST','recipes',body={'name':name})
        a(fx,'recipes',slug+'-body','PATCH','recipes/'+slug,body={
            'recipeServings':4,'recipeIngredient':[{'quantity':i+2,'food':Ref(f)} for i,f in enumerate(foods)],
            'tools':[Ref(t) for t in tools]})
    def suggestions(step,**kw):
        a('discovery','suggest',step,'GET','recipes/suggestions',status=200,
          params=lambda c,kw=kw:{'foods':[c.state['tomato']['id'],c.state['olive oil']['id']],
            'tools':[c.state['pot']['id']],'orderBy':'name','orderDirection':'asc','includeFoodsOnHand':False,
            'includeToolsOnHand':False,**kw})
    suggestions('all-missing-details')
    suggestions('strict',maxMissingFoods=0,maxMissingTools=0,includeSubstitutions=False)
    suggestions('substitutions',maxMissingFoods=0,maxMissingTools=0,includeSubstitutions=True)
    suggestions('missing-food-allowed',maxMissingFoods=1,maxMissingTools=0,includeSubstitutions=False)
    suggestions('missing-tool-allowed',maxMissingFoods=0,maxMissingTools=1,includeSubstitutions=False)
    for kind,key,route,field in [('food','tomato','foods','householdsWithIngredientFood'),('tool','pot','organizers/tools','householdsWithTool')]:
        a('inventory',kind,'set','PUT',pathref(route+'/{i}',i=Ref(key,'id')),
          body={'name':key,field:[Ref('household','slug')]})
        a('inventory',kind,'read','GET',pathref(route+'/{i}',i=Ref(key,'id')),fields=['name',field])
    a('inventory','suggest','on-hand','GET','recipes/suggestions',status=200,
      params=lambda c:{'foods':c.state['rice']['id'],'tools':c.state['oven']['id'],'includeSubstitutions':False,'includeFoodsOnHand':True,'includeToolsOnHand':True,'maxMissingFoods':0,'maxMissingTools':0,'orderBy':'name'},
      check=lambda c,r,p: names(p,['Rice Soup']))
    a('inventory','suggest','ignored','GET','recipes/suggestions',status=200,
      params=lambda c:{'foods':c.state['rice']['id'],'tools':c.state['oven']['id'],'includeSubstitutions':False,'includeFoodsOnHand':False,'includeToolsOnHand':False,'maxMissingFoods':0,'maxMissingTools':0,'orderBy':'name'},
      check=lambda c,r,p: names(p,[]))
    for enabled in [True,False]:
        a('inventory','tools','include' if enabled else 'exclude','GET','recipes/suggestions',status=200,
          params=lambda c,enabled=enabled:{'foods':c.state['tomato']['id'],'tools':c.state['oven']['id'],
              'includeSubstitutions':False,'includeFoodsOnHand':False,'includeToolsOnHand':enabled,
              'maxMissingFoods':0,'maxMissingTools':0,'orderBy':'name'})
    s.add('inventory','persist','restart',lambda c:(c.restart_server(),{'running':c.running()})[1])
    a('inventory','persist','food','GET',pathref('foods/{i}',i=Ref('tomato','id')),fields=['householdsWithIngredientFood'])
    a('inventory','persist','tool','GET',pathref('organizers/tools/{i}',i=Ref('pot','id')),fields=['householdsWithTool'])
    a('inventory','persist','suggest','GET','recipes/suggestions',status=200,
      params=lambda c:{'foods':c.state['rice']['id'],'tools':c.state['oven']['id'],'includeSubstitutions':False,'includeFoodsOnHand':True,'includeToolsOnHand':True,'maxMissingFoods':0,'maxMissingTools':0,'orderBy':'name'},
      check=lambda c,r,p: names(p,['Rice Soup']))
    a(fx,'scale','read','GET','recipes/rice-soup',save='rice-soup')
    for label,scale in [('half',.5),('double',2)]:
        a('scaling',label,'plan','POST','households/mealplans',status=201,save=label,
          body={'date':day(1),'entryType':'dinner','recipeId':Ref('rice-soup','id'),'recipeScale':scale})
        a('scaling',label,'read','GET',pathref('households/mealplans/{i}',i=Ref(label,'id')),fields=['date','recipeId','recipeScale'])
        a('scaling',label,'list','POST','households/shopping/lists',body={'name':label+' portions'},status=201,save=label+'-list')
        a('scaling',label,'add','POST',pathref('households/shopping/lists/{i}/recipe',i=Ref(label+'-list','id')),
          body=[{'recipeId':Ref('rice-soup','id'),'recipeIncrementQuantity':Ref(label,'recipeScale')}],hint='none')
        a('scaling',label,'ingredients','GET','households/shopping/items',
          params=lambda c,label=label:{'queryFilter':'shoppingListId = "'+c.state[label+'-list']['id']+'"','orderBy':'quantity'},
          fields=['quantity','food','recipeReferences'])
    a('scaling','original','unchanged','GET','recipes/rice-soup',fields=['recipeServings','recipeIngredient'])
    a('scaling','invalid','zero','POST','households/mealplans',status=422,
      body={'date':day(1),'recipeId':Ref('rice-soup','id'),'recipeScale':0})
    a('scaling','invalid','negative','POST','households/mealplans',status=422,
      body={'date':day(1),'recipeId':Ref('rice-soup','id'),'recipeScale':-1})


def names(payload, expected):
    assert sorted(x['recipe']['name'] for x in payload['items']) == sorted(expected), 'suggested recipes differ'
