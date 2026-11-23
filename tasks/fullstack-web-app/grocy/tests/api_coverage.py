"""Aggregate queries, incremental permissions, preferences and public change notification."""
import time
from harness import Ref,resolve,pathref,subset,unordered,semantic_equal
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS
from api_users import userfixture


def permission(c,name):
    return next(x['id'] for x in c.state['coverage-permissions'] if x['name']==name)


def build(s):
    f=foundation(s)
    pf,p=fx(s,'aggregate','products',product(f,'Fulfillment rice'),'agg-p')
    stocked=s.api('aggregate-fixture','stock','add','POST',route(p,'/add'),body={'amount':4,'price':2},needs=[pf])
    deps=[pf,stocked];recipes=[]
    for label,amount in [('A',1),('B',3),('C',6),('D',9)]:
        rf,r=fx(s,label,'recipes',{'name':'Aggregate '+label},'agg-r-'+label)
        inf,_=fx(s,label,'recipes_pos',{'recipe_id':r,'product_id':p,'amount':amount,'qu_id':f['unit']},'agg-i-'+label)
        deps += [rf,inf];recipes.append(r)
    s.needs=deps
    fields=['recipe_id','need_fulfilled','need_fulfilled_with_shopping_list','missing_products_count','costs']
    for label,params in [
        ('all',{}),('enough',{'query[]':'need_fulfilled=1'}),('missing',{'query[]':'need_fulfilled=0'}),
        ('missing-count',{'query[]':'missing_products_count>0'}),
        ('id-equal',{'query[]':pathref('recipe_id={id}',id=recipes[1])}),
        ('id-not',{'query[]':pathref('recipe_id!={id}',id=recipes[1])}),
        ('id-range',{'query[]':[pathref('recipe_id>={id}',id=recipes[1]),pathref('recipe_id<={id}',id=recipes[2])]}),
        ('cost-low',{'query[]':'costs<=6'}),('cost-high',{'query[]':'costs>6'}),
        ('ascending',{'order':'costs:asc'}),('descending',{'order':'costs:desc'}),
        ('first-page',{'order':'costs:asc','limit':2}),('second-page',{'order':'costs:asc','limit':2,'offset':2}),
        ('offset-only',{'order':'costs:asc','offset':1}),('last',{'order':'costs:desc','limit':1}),
        ('filter-page',{'query[]':'need_fulfilled=0','order':'costs:desc','limit':1}),
    ]:
        s.api('aggregate-recipes',label,'query','GET','recipes/fulfillment',params=params,fields=fields,hint='recipes',ordered='order' in params)
    positive=s.cases[-1].id
    s.api('aggregate-recipes','invalid','order','GET','recipes/fulfillment',params={'order':'costs:sideways'},status=400,requires=[positive])
    # Stock-entry queries distinguish due dates, purchase dates, open state and prices.
    pf,p=fx(s,'ordered','products',product(f,'Ordered batches'),'ordered-p')
    deps=[pf]
    for label,amount,price,due,purchased in [('late',4,4,'2026-06-01','2026-03-01'),('early-old',2,2,'2026-04-01','2026-02-01'),
                                           ('early-new',3,3,'2026-04-01','2026-03-01'),('middle',1,1,'2026-05-01','2026-03-01')]:
        dep=s.api('batch-fixture',label,'add','POST',route(p,'/add'),body={'amount':amount,'price':price,'best_before_date':due,'purchased_date':purchased},needs=[pf])
        deps.append(dep)
    s.needs=deps
    for label,params in [('price-asc',{'order':'price:asc'}),('price-desc',{'order':'price:desc'}),
       ('purchase',{'order':'price:asc','query[]':'purchased_date=2026-02-01'}),('early',{'query[]':'best_before_date=2026-04-01'}),
       ('after-due',{'query[]':'best_before_date>2026-04-01'}),('before-due',{'query[]':'best_before_date<2026-06-01'}),
       ('first-page',{'order':'price:asc','limit':2}),('second-page',{'order':'price:asc','limit':2,'offset':2}),
       ('offset',{'order':'price:asc','offset':3}),('filter-page',{'query[]':'amount>=2','order':'price:desc','limit':2}),
       ('between',{'query[]':['price>=2','price<=3'],'order':'price:asc'})]:
        s.api('ordered-entries',label,'query','GET',route(p,'/entries'),params=params,fields=['amount','price','best_before_date','purchased_date','open'],hint='stock',ordered='order' in params)
    # Add permissions incrementally, and verify each actually changes a product operation.
    s.needs=[];who,uid=userfixture(s,'incremental','Incremental','User');auth=['incremental','Local-password-42!']
    hierarchy=s.api('permission-fixture','incremental','hierarchy','GET','objects/permission_hierarchy',save='coverage-permissions',needs=[])
    pf,p=fx(s,'permission','products',product(f,'Permission stock'),'permission-p')
    tf,t=fx(s,'permission','tasks',{'name':'Incremental task'},'permission-t')
    lf,l=fx(s,'permission','shopping_lists',{'name':'Incremental list'},'permission-l')
    listitem,li=fx(s,'permission','shopping_list',{'note':'Retain until delete grant','amount':1,'shopping_list_id':l},'permission-li')
    permpath=pathref('users/{id}/permissions',id=uid)
    reset=s.api('permissions-incremental','start','clear','PUT',permpath,body={'permissions':[]},status=204,needs=who+[hierarchy])
    granted=[];prev=reset
    operations=[
      ('STOCK_PURCHASE','POST',route(p,'/add'),{'amount':3,'price':2},200,entries(p,3),[pf]),
      ('TASKS_MARK_COMPLETED','POST',pathref('tasks/{id}/complete',id=t),{'done_time':'2026-03-10 08:00:00'},204,readback(objpath('tasks',t),['done'],{'done':1}),[tf]),
      ('TASKS_UNDO_EXECUTION','POST',pathref('tasks/{id}/undo',id=t),{},204,readback(objpath('tasks',t),['done'],{'done':0}),[tf]),
      ('SHOPPINGLIST_ITEMS_DELETE','POST','stock/shoppinglist/clear',{'list_id':l},204,
        readback('objects/shopping_list',['note'],params={'query[]':pathref('shopping_list_id={id}',id=l)}),[lf,listitem]),
    ]
    for leaf,method,path,body,status,after,needed in operations:
        denied=s.api('permissions-incremental',leaf,'denied','%s'%method,path,actor=auth,body=body,status=[400,403],needs=[prev,*needed])
        added=s.api('permissions-incremental',leaf,'grant','POST',permpath,body={'permission_id':lambda c,leaf=leaf:permission(c,leaf)},status=204,needs=[prev,hierarchy])
        granted.append(leaf)
        def preserve(c,r,rows,names=tuple(granted)):
            assert sorted(int(x['permission_id']) for x in rows)==sorted(permission(c,n) for n in names),'incremental grant lost or added permissions'
        listing=s.api('permissions-incremental',leaf,'retains-earlier','GET',permpath,fields=['permission_id'],hint='user_permissions',check=preserve,needs=[added])
        allowed=s.api('permissions-incremental',leaf,'effective','%s'%method,path,actor=auth,body=body,status=status,needs=[listing,*needed],after=after,hint='stock_log')
        next(x for x in s.cases if x.id==denied).requires=(allowed,);prev=allowed
    # Whole preference maps retain other overrides and are isolated between users.
    s.needs=who
    for key,first,second in [('stock_due_soon_days','3','11'),('stock_default_purchase_amount','2','0.75'),
                             ('calendar_color_products','#123456','#654321'),('night_mode','on','off')]:
        def map_read(c,actor=auth,key=key):
            r,p=c.request('GET','user/settings',actor)
            assert r.status_code==200 and isinstance(p,dict) and key in p
            return {'value':p[key],'other_setting_present':'calendar_color_tasks' in p}
        baseline=s.api('preference-fixture',key,'baseline','GET','user/settings',save='settings-'+key)
        a=s.api('preference-map',key,'first','PUT','user/settings/'+key,actor=auth,body={'value':first},status=204,after=map_read,needs=who)
        def isolated(c,key=key):
            r,p=c.request('GET','user/settings');assert r.status_code==200
            assert semantic_equal(p[key],c.state['settings-'+key][key],key),'one user changed another preferences'
            return {'isolated':True}
        s.add('preference-map',key,'isolation',isolated,needs=[a,baseline],description='Aggregate preference isolation for '+key)
        a=s.api('preference-map',key,'replace','PUT','user/settings/'+key,actor=auth,body={'value':second},status=204,after=map_read,needs=[a])
        s.api('preference-map',key,'restore','DELETE','user/settings/'+key,actor=auth,status=204,after=map_read,needs=[a])
    # mtime has one-second resolution. Wait past its tick before mutations, never freeze absolute timestamps.
    s.needs=[]
    def changed(c):
        _,before=c.request('GET','system/db-changed-time')
        previous=before['changed_time'];assert previous is not None
        time.sleep(1.1)
        r,row=c.request('POST','objects/locations',body={'name':'Notification location'})
        assert r.status_code==200
        _,after=c.request('GET','system/db-changed-time')
        assert after['changed_time']!=previous,'write did not advance public change notification'
        c.state['notification-id']=row['created_object_id']
        return {'write_changed':True}
    first=s.add('notifications','database','create',changed,description='A real write advances the public database change token')
    def remove(c):
        _,before=c.request('GET','system/db-changed-time');time.sleep(1.1)
        r,p=c.request('DELETE','objects/locations/'+str(c.state['notification-id']));assert r.status_code==204
        _,after=c.request('GET','system/db-changed-time');assert after!=before,'deletion did not advance change token'
        return {'delete_changed':True}
    s.add('notifications','database','delete',remove,needs=[first],description='Deletion advances the public database change token')
