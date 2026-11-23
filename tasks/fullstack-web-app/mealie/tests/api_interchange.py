'''Local migration formats, streaming JSON-LD import and bulk recipe replacement/patching.'''
import csv,gzip,io,json
from harness import Ref,pathref
from api_files import zipped,upload,JSONLD


def csv_file(row):
    out=io.StringIO(newline='')
    w=csv.DictWriter(out,fieldnames=list(row));w.writeheader();w.writerow(row)
    return out.getvalue().encode()


def fixtures():
    paprika={'name':'Paprika Scones','description':'Tender breakfast scones','ingredients':'2 cups flour\n1 cup cream',
             'directions':'1. Mix gently.\n\n2. Bake until golden.','servings':'6 scones','categories':['Breakfast'],
             'notes':'Do not overwork the dough.','prep_time':'15 minutes','cook_time':'20 minutes'}
    yield 'paprika','paprika.zip',zipped({'scones.paprikarecipe':gzip.compress(json.dumps(paprika).encode(),mtime=0)}),'Paprika Scones','paprika-scones'
    pte={'Title':'Plan Pancakes','Description':'Sunday pancakes','Ingredients':'1 cup flour\n1 egg',
         'Directions':'Whisk the batter.\nCook in a skillet.','Servings':'2','Course':'Breakfast','Tags':'quick,pantry','Calories':'300'}
    yield 'plantoeat','plan.csv',csv_file(pte),'Plan Pancakes','plan-pancakes'
    mrb={'title':'Box Biscuits','description':'Simple biscuits','ingredients':'2 cups flour\n1 cup milk',
         'instructions':'Mix the ingredients.\nBake for twenty minutes.','quantity':'8','categories':'Baking',
         'tags':'quick;pantry','notes':'Serve warm.','nutrition':'Protein: 8\nFat: 12'}
    yield 'myrecipebox','box.csv',csv_file(mrb),'Box Biscuits','box-biscuits'
    rk='''<html><body><div class="recipe-details"><h2 itemprop="name">Keeper Curry</h2>
    <div itemprop="recipeIngredients"><p>1 onion</p><p>2 carrots</p></div>
    <div itemprop="recipeDirections"><p>1. Chop vegetables.</p><p>2. Simmer with spices.</p></div>
    <meta itemprop="recipeYield" content="4 servings"><div itemprop="recipeCategory">Dinner</div>
    <div itemprop="recipeNotes">Serve with rice.</div></div></body></html>'''
    yield 'recipekeeper','keeper.zip',zipped({'recipes.html':rk}),'Keeper Curry','keeper-curry'
    td={'name':'Tandoor Toast','description':'Toasted bread','keywords':[{'name':'quick'}],
        'servings':2,'servings_text':'slices','working_time':5,'waiting_time':3,
        'steps':[{'name':'Toast','instruction':'Toast until crisp.',
                  'ingredients':[{'amount':2,'food':{'name':'bread'},'unit':{'name':'slice'}}]}]}
    yield 'tandoor','tandoor.zip',zipped({'toast.zip':zipped({'recipe.json':json.dumps(td)})}),'Tandoor Toast','tandoor-toast'
    cm='''<html><body><div class="recipe"><h2 id="name">Copy Couscous</h2><p id="description">Fluffy couscous</p>
    <ul id="recipeIngredients"><li>1 cup couscous</li><li>1 cup water</li></ul>
    <ol id="recipeInstructions"><li>Pour boiling water over couscous.</li><li>Cover and wait.</li></ol>
    <p id="servings">2 bowls</p><span class="recipeCategory">quick</span><p id="recipeNotes">Fluff with a fork.</p>
    </div></body></html>'''
    yield 'copymethat','copy.zip',zipped({'recipes.html':cm}),'Copy Couscous','copy-couscous'


    legacy={'name':'Legacy Loaf','slug':'legacy-loaf','description':'A loaf from an earlier version',
            'recipeIngredient':[{'note':'3 cups flour'}],'recipeInstructions':[{'text':'Knead and bake.'}],
            'extras':[],'tags':[],'categories':[]}
    yield 'mealie_alpha','legacy.zip',zipped({'recipes/legacy-loaf/legacy-loaf.json':json.dumps(legacy)}),'Legacy Loaf','legacy-loaf'
    def dsv(rows):
        keys=list(rows[0]);return '||||'.join(keys)+'!@#%^&*()'+''.join('||||'.join(str(r.get(k,'')) for k in keys)+'!@#%^&*()' for r in rows)
    tables={
        'temp_unit':[{'ID':'u','NAME':'cup','PLURAL_NAME':'cups','ABBREVIATION':'c'}],
        'temp_food':[{'ID':'f','NAME':'oats','PLURAL_NAME':'oats'}],
        'temp_brand':[{'ID':'b','NAME':''}],
        'temp_media':[{'ENTITY_ID':'none','ID':''}],
        'temp_recipe':[{'ID':'r','SERVES':'2','PREPTIME':'5','COOKTIME':'10','INSTRUCTIONS':'1. Boil water.\n2. Stir in oats.'}],
        'temp_recipe_desc':[{'ID':'r','PARENT':'c','TITLE':'Cookn Oatmeal','DESCRIPTION':'Morning oats'}],
        'temp_chapter_desc':[{'ID':'c','PARENT':'b','TITLE':'Breakfast'}],
        'temp_cookBook_desc':[{'ID':'b','TITLE':'Family'}],
        'temp_ingredient':[{'PARENT_ID':'r','AMOUNT_UNIT':'u','INGREDIENT_FOOD_ID':'f','BRAND_ID':'b','AMOUNT_QTY_STRING':'1','ORDER':'0'}],
    }
    yield 'cookn','cookn.zip',zipped({k+'.dsv':dsv(rows) for k,rows in tables.items()}),'Cookn Oatmeal','cookn-oatmeal'


def build(s):
    a=s.api
    fields=['name','description','recipeYield','recipeServings','recipeYieldQuantity','recipeIngredient','recipeInstructions',
            'notes','tags','recipeCategory','nutrition','prepTime','performTime','totalTime']
    for kind,filename,data,name,slug in fixtures():
        f='interchange-'+kind
        a(f,'import','upload','POST','groups/migrations',status=200,save=kind,
          multipart={'fields':{'migration_type':kind},'files':{'archive':upload(filename,data,'text/csv' if filename.endswith('.csv') else 'application/zip')}})
        a(f,'import','recipe','GET','recipes/'+slug,fields=fields,check=lambda c,r,p,n=name: p['name']==n or (_ for _ in ()).throw(AssertionError('imported name differs')))
        a(f,'import','report','GET',pathref('groups/reports/{id}',id=Ref(kind,'id')))
    a('interchange-stream','jsonld','import','POST','recipes/create/html-or-json/stream',status=200,hint='none',
      body={'data':json.dumps({**JSONLD,'name':'Streamed Stew'}),'includeTags':True,'includeCategories':True})
    a('interchange-stream','jsonld','read','GET','recipes/streamed-stew',fields=fields)
    a('interchange-bulk','create','first','POST','recipes',body={'name':'Bulk First'},status=201)
    a('interchange-bulk','create','second','POST','recipes',body={'name':'Bulk Second'},status=201)
    a('interchange-bulk','create','first-read','GET','recipes/bulk-first',save='first',fields=['name'])
    a('interchange-bulk','create','second-read','GET','recipes/bulk-second',save='second',fields=['name'])
    a('interchange-bulk','replace','put','PUT','recipes',body=lambda c:[{**c.state['first'],'description':'First replacement'},
                                                                 {**c.state['second'],'description':'Second replacement'}],hint='none')
    for slug in ['bulk-first','bulk-second']:
        a('interchange-bulk','replace',slug,'GET','recipes/'+slug,fields=['name','description','recipeIngredient'])
    a('interchange-bulk','patch','patch','PATCH','recipes',body=lambda c:[{**c.state['first'],'description':'First patch'},
                                                                       {**c.state['second'],'recipeServings':7}],hint='none')
    for slug in ['bulk-first','bulk-second']:
        a('interchange-bulk','patch',slug,'GET','recipes/'+slug,fields=['name','description','recipeServings','recipeIngredient'])
