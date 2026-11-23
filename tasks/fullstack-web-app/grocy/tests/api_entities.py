"""Entity CRUD, field boundaries, filtering and pagination on the exposed product objects."""
from harness import Ref
from common import foundation,fx,product,objpath,readback,check_list


def build(s):
    f=foundation(s)
    rp,r=fx(s,'base','recipes',{'name':'Fixture recipe'},'base-recipe')
    pp,p=fx(s,'base','products',product(f,'Fixture product'),'base-product')
    ep,e=fx(s,'base','userentities',{'name':'collection','caption':'Collection'},'base-userentity')
    foundation_deps=f['deps']
    body_deps={
      'products':['loc','unit','cold','shop','group','pack'], 'tasks':['cat','admin'],
      'shopping_list':['list','unit','pack'], 'recipes_pos':['unit'],
      'quantity_unit_conversions':['unit','pack'], 'product_barcodes':['unit','pack','shop'],
      'meal_plan':['section'],
    }
    relational={'products':[pp], 'shopping_list':[pp], 'recipes_pos':[rp,pp],
                'quantity_unit_conversions':[pp], 'product_barcodes':[pp], 'meal_plan':[rp], 'userobjects':[ep]}
    product_dependencies=[foundation_deps[k] for k in ('loc','unit')]
    specs={
      'locations':({'name':'Atlas'}, {'name':['Shelf Ω','Atlas'],'description':['Two\nlines','<b>Dry</b> goods'],'is_freezer':[1,0],'active':[0,1]}),
      'quantity_units':({'name':'Atlas'}, {'name':['Portion Ω','Atlas'],'name_plural':['Portions','Doses'],'description':['Small unit','<i>Measure</i>'],'plural_forms':['n != 1','n > 1'],'active':[0,1]}),
      'shopping_locations':({'name':'Atlas'}, {'name':['Market Ω','Atlas'],'description':['Local store','<b>Market</b>'],'active':[0,1]}),
      'product_groups':({'name':'Atlas'}, {'name':['Food Ω','Atlas'],'description':['Food group','<b>Pantry</b>'],'active':[0,1]}),
      'task_categories':({'name':'Atlas'}, {'name':['Work Ω','Atlas'],'description':['Daily tasks','<b>Work</b>'],'active':[0,1]}),
      'shopping_lists':({'name':'Atlas'}, {'name':['Weekend Ω','Atlas'],'description':['Two\nlines','<b>Weekend</b>']}),
      'equipment':({'name':'Atlas'}, {'name':['Mixer Ω','Atlas'],'description':['Read manual','<b>Instructions</b>'],'instruction_manual_file_name':['manual.pdf','guide.txt']}),
      'meal_plan_sections':({'name':'Atlas'}, {'name':['Lunch Ω','Atlas'],'sort_number':[0,3],'time_info':['12:30','19:45']}),
      'batteries':({'name':'Atlas'}, {'name':['Remote Ω','Atlas'],'description':['Rechargeable','<b>AA</b>'],'used_in':['Remote','Clock'],'charge_interval_days':[0,14],'active':[0,1]}),
      'chores':({'name':'Atlas','period_type':'manually'}, {'name':['Sweep Ω','Atlas'],'description':['Kitchen floor','<b>Weekly</b>'],'period_type':['daily','manually'],'period_days':[1,5],'period_interval':[1,3],'track_date_only':[1,0],'rollover':[1,0],'active':[0,1],'start_date':['2026-03-01','2026-03-15'],'rescheduled_date':['2026-04-01','2026-04-02']}),
      'tasks':({'name':'Atlas'}, {'name':['Read Ω','Atlas'],'description':['Chapter one','<b>Chapter two</b>'],'due_date':['2026-03-10 12:30:00','2026-04-01 15:00:00'],'category_id':[f['cat']],'done':[1,0],'assigned_to_user_id':[f['admin']]}),
      'recipes':({'name':'Atlas'}, {'name':['Soup Ω','Atlas'],'description':['Mix\nand stir','<b>Simmer</b>'],'base_servings':[2,4],'desired_servings':[1,6],'not_check_shoppinglist':[1,0],'picture_file_name':['soup.png','stew.jpg']}),
      'products':(product(f,'Atlas'), {'name':['Rice Ω','Atlas'],'description':['Long grain','<b>Brown</b> rice'],
          'active':[0,1],'product_group_id':[f['group']],'location_id':[f['cold'],f['loc']],
          'shopping_location_id':[f['shop']],'qu_id_purchase':[f['pack'],f['unit']],
          'qu_id_consume':[f['pack'],f['unit']],'qu_id_price':[f['pack'],f['unit']],
          'min_stock_amount':[0,7],'default_best_before_days':[-1,14],'default_best_before_days_after_open':[0,3],
          'default_best_before_days_after_freezing':[-1,30],'default_best_before_days_after_thawing':[0,2],
          'enable_tare_weight_handling':[1,0],'tare_weight':[0,0.25],'calories':[0,123],
          'not_check_stock_fulfillment_for_recipes':[1,0],'cumulate_min_stock_amount_of_sub_products':[1,0],
          'due_type':[2,1],'quick_consume_amount':[0.5,3],'quick_open_amount':[0.5,2],
          'hide_on_stock_overview':[1,0],'should_not_be_frozen':[1,0],'treat_opened_as_out_of_stock':[0,1],
          'no_own_stock':[1,0],'default_consume_location_id':[f['cold'],f['loc']],
          'move_on_open':[1,0],'disable_open':[1,0],'default_purchase_price_type':[2,1],
          'parent_product_id':[p],'picture_file_name':['rice.png','grain.jpg']}),
      'userentities':({'name':'Atlas','caption':'Atlas collection'}, {'name':['albums','atlas'],'caption':['Albums Ω','My collection'],'description':['Records','<b>Music</b>'],'show_in_sidebar_menu':[0,1],'icon_css_class':['fas fa-book','fas fa-home']}),
      'userfields':({'entity':'equipment','name':'atlas_field','caption':'Atlas field','type':'text-single-line'}, {'caption':['Notes Ω','Label'],'type':['number-integral','text-single-line'],'show_as_column_in_tables':[1,0],'input_required':[1,0],'sort_number':[0,5],'default_value':['Blue','Green'],'config':['First,Second','Third,Fourth']}),
      'shopping_list':({'product_id':p,'amount':2,'shopping_list_id':f['list'],'note':'Atlas'}, {'amount':[0,2.5],'done':[1,0],'note':['List Ω','Multi\nline'],'qu_id':[f['pack'],f['unit']]}),
      'recipes_pos':({'recipe_id':r,'product_id':p,'amount':2,'qu_id':f['unit']}, {'amount':[0.5,3],'note':['Ingredient Ω','<b>Fresh</b>'],'ingredient_group':['Vegetables','Sauce'],'only_check_single_unit_in_stock':[1,0],'not_check_stock_fulfillment':[1,0],'price_factor':[0.5,2],'round_up':[1,0],'variable_amount':['To taste','As needed']}),
      'quantity_unit_conversions':({'from_qu_id':f['unit'],'to_qu_id':f['pack'],'factor':0.25}, {'factor':[0.125,0.5],'product_id':[p]}),
      'product_barcodes':({'product_id':p,'barcode':'ATLAS001'}, {'barcode':['987654321','ABC-123'],'amount':[1,2.5],'qu_id':[f['pack'],f['unit']],'shopping_location_id':[f['shop']],'last_price':[0,1.75],'note':['Barcode Ω','Package']}),
      'meal_plan':({'day':'2026-03-10','type':'recipe','recipe_id':r,'recipe_servings':2}, {'day':['2026-03-11','2026-04-01'],'recipe_servings':[1,4],'note':['Dinner Ω','<b>Lunch</b>'],'done':[1,0],'section_id':[f['section']]}),
      'userobjects':({'userentity_id':e}, {}),
    }
    for entity,(body,changes) in specs.items():
        base=[foundation_deps[k] for k in body_deps.get(entity,[])]+relational.get(entity,[])
        if pp in base:base+=product_dependencies
        s.needs=list(base)
        cid=s.api('entities',entity,'create','POST','objects/'+entity,body=body,save=entity,hint=entity,
                  fields=['created_object_id'])
        ident=Ref(entity,'created_object_id');path=objpath(entity,ident)
        s.needs=base+[cid]
        s.api('entities',entity,'read-created','GET',path,hint=entity,fields=list(body),want=body)
        for field,values in changes.items():
            for index,value in enumerate(values):
                s.api('entities',entity,'change-'+field+'-'+str(index),'PUT',path,body={field:value},status=204,
                      after=readback(path,fields=[field],want={field:value},hint=entity))
        s.api('entities',entity,'empty-patch','PUT',path,body={},status=204,
              after=readback(path,fields=list(body),hint=entity))
        s.api('entities',entity,'unknown-column','PUT',path,body={'pbp_unknown_field':'value'},status=400,requires=[cid],
              after=readback(path,fields=list(body),hint=entity))
        s.api('entities',entity,'wrong-content-type','PUT',path,raw='{}',content_type='text/plain',status=400,requires=[cid])
        deleted=s.api('entities',entity,'delete','DELETE',path,status=204,requires=[cid])
        s.api('entities',entity,'gone','GET',path,status=404,needs=[deleted],requires=[cid])
        s.api('entities',entity,'delete-again','DELETE',path,status=400,needs=[deleted],requires=[cid])
        s.api('entities',entity,'edit-gone','PUT',path,body=body,status=400,needs=[deleted],requires=[cid])
        # Named collections exercise ordering and filters on five distinguishable records.
        if 'name' not in body or entity in ('userentities','userfields'):continue
        s.needs=list(base);collection=[];points=[]
        for index,name in enumerate(['Atlas','Birch','Cedar','Delta','Éclair']):
            record=dict(body,name=name+' query')
            if entity=='userfields':record['name']='field_'+str(index)
            point,oid=fx(s,'query-'+entity,entity,record,'q-'+entity+'-'+str(index));points.append(point);collection.append(record['name'])
        s.needs=base+points
        clauses=[('equal','name='+collection[1],[collection[1]]),('unequal','name!='+collection[1],[x for x in collection if x!=collection[1]]),
          ('contains','name~query',collection),('not-contains','name!~Birch',[x for x in collection if 'Birch' not in x]),
          ('less','name<Cedar query',[x for x in collection if x<'Cedar query']),
          ('greater','name>Cedar query',[x for x in collection if x>'Cedar query']),
          ('less-equal','name<=Cedar query',[x for x in collection if x<='Cedar query']),
          ('greater-equal','name>=Cedar query',[x for x in collection if x>='Cedar query']),
          ('regex','name§^B',[collection[1]])]
        # Limit the query to this scenario so seeded/default entities do not leak into pagination.
        for label,clause,names in clauses:
            s.api('query',entity,label,'GET','objects/'+entity,params={'query[]':['name~query',clause],'order':'name:asc'},
                  hint=entity,fields=['name'],ordered=True,check=check_list(['name'],[{'name':x} for x in sorted(names)],True))
        for label,params,names in [
            ('ascending',{'order':'name:asc'},collection),('descending',{'order':'name:desc'},list(reversed(collection))),
            ('limit-first',{'order':'name:asc','limit':2},collection[:2]),
            ('offset-middle',{'order':'name:asc','limit':2,'offset':2},collection[2:4]),
            ('offset-only',{'order':'name:asc','offset':3},collection[3:]),
            ('offset-end',{'order':'name:asc','limit':2,'offset':4},collection[4:]),
            ('zero-limit',{'limit':0},[]),('beyond-end',{'offset':9},[])]:
            s.api('query',entity,label,'GET','objects/'+entity,params={'query[]':['name~query'],**params},hint=entity,
                  fields=['name'],ordered=True,check=check_list(['name'],[{'name':x} for x in names],True))
        s.api('query',entity,'combined-filters','GET','objects/'+entity,
              params={'query[]':['name~query','name>=Birch query','name<Delta query'],'order':'name:asc'},hint=entity,
              fields=['name'],ordered=True,check=check_list(['name'],[{'name':x} for x in collection[1:3]],True))
