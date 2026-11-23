"""Authentication, account changes, per-user preferences and hierarchical permission enforcement."""
from harness import Ref,resolve,pathref,subset
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS


def userfixture(s,name,first='Test',last='User'):
    create=s.api('user-fixture',name,'create','POST','users',body={'username':name,'first_name':first,'last_name':last,
            'password':'Local-password-42!','picture_file_name':''},status=204)
    lookup=s.api('user-fixture',name,'lookup','GET','users',params={'query[]':'username='+name},save='user-'+name)
    return [create,lookup],Ref('user-'+name,0,'id')


def permission(name):
    def find(c):
        rows=c.state['permission-list']
        matches=[x for x in rows if x['name']==name]
        assert len(matches)==1,'permission unavailable: '+name
        return matches[0]['id']
    return find


def build(s):
    f=foundation(s)
    who,uid=userfixture(s,'alex','Alex','Reader')
    auth=['alex','Local-password-42!']
    perms=s.api('user-fixture','permissions','hierarchy','GET','objects/permission_hierarchy',save='permission-list')
    s.needs=f['needs']+who+[perms]
    positive=s.api('users','auth','sign-in','GET','user',actor=auth,fields=['id','username','first_name','last_name','display_name'],hint='users')
    s.api('users','auth','wrong-password','GET','user',actor=['alex','wrong-password'],status=302,requires=[positive])
    s.api('users','auth','unknown-user','GET','user',actor=['absent-account','wrong-password'],status=302,requires=[positive])
    s.api('users','auth','anonymous','GET','user',actor=None,status=401,requires=[positive])
    s.api('users','auth','bad-api-key','GET','user',actor=None,headers={'GROCY-API-KEY':'not-a-valid-key'},status=401,requires=[positive])
    s.api('users','auth','bad-cookie','GET','user',actor=None,headers={'Cookie':'grocy_session_access_token=invalid'},status=401,requires=[positive])
    s.api('users','accounts','duplicate','POST','users',body={'username':'alex','first_name':'Duplicate','last_name':'User','password':'Duplicate-password!','picture_file_name':''},status=400,requires=[positive])
    edited=s.api('users','accounts','edit-profile','PUT',pathref('users/{id}',id=uid),body={'username':'alex','first_name':'Alex Ω','last_name':'Smith','password':'','picture_file_name':'avatar.png'},
                 status=204,after=readback('user',['username','first_name','last_name','picture_file_name'],{'username':'alex','first_name':'Alex Ω','last_name':'Smith','picture_file_name':'avatar.png'},actor=auth))
    newauth=['alex','Replacement-42!']
    changed=s.api('users','accounts','password','PUT',pathref('users/{id}',id=uid),body={'username':'alex','first_name':'Alex Ω','last_name':'Smith','password':'Replacement-42!','picture_file_name':''},status=204,needs=[edited])
    signed=s.api('users','accounts','new-password-sign-in','GET','user',actor=newauth,fields=['username','first_name','last_name'],needs=[changed],hint='users')
    # Preferences are independent per user, preserve booleans/numbers/text, and deletion restores the configured default.
    settings=[('night_mode','on','off'),('show_clock_in_header','0','1'),('auto_reload_on_db_change','0','1'),
       ('stock_due_soon_days','3','12'),('stock_default_purchase_amount','2','0.5'),
       ('stock_default_consume_amount','2','0.5'),('product_presets_location_id',f['loc'],f['cold']),
       ('stock_decimal_places_amounts','0','3'),('stock_decimal_places_prices_input','2','4'),
       ('shopping_list_auto_add_below_min_stock_amount','1','0'),('shopping_list_show_calendar','0','1'),
       ('recipe_ingredients_group_by_product_group','1','0'),('recipes_show_list_side_by_side','0','1'),
       ('recipes_show_ingredient_checkbox','1','0'),('chores_due_soon_days','1','8'),('batteries_due_soon_days','2','9'),
       ('tasks_due_soon_days','2','10'),('calendar_color_products','#123456','#654321'),
       ('calendar_color_tasks','#112233','#334455'),('calendar_color_chores','#445566','#667788'),
       ('calendar_color_batteries','#778899','#99aabb'),('calendar_color_meal_plan','#aabbcc','#ddeeff')]
    for key,v1,v2 in settings:
        path='user/settings/'+key
        s.needs=who+[signed]
        default=s.api('setting-fixture',key,'default','GET',path,save='default-'+key)
        s.needs.append(default)
        a=s.api('settings',key,'set','PUT',path,actor=newauth,body={'value':v1},status=204,
                after=readback(path,['value'],{'value':v1},actor=newauth))
        s.api('settings',key,'isolation','GET',path,needs=[a],want=Ref('default-'+key),requires=[a])
        b=s.api('settings',key,'replace','PUT',path,actor=newauth,body={'value':v2},status=204,needs=[a],
                after=readback(path,['value'],{'value':v2},actor=newauth))
        s.api('settings',key,'delete-override','DELETE',path,actor=newauth,status=204,needs=[b],
              after=readback(path,['value'],Ref('default-'+key),actor=newauth),requires=[a])
    # Each leaf is checked with no grants, its own grant, and its parent grant. Real fixtures prevent false denials.
    cases=[
      ('MASTER_DATA_EDIT','ADMIN','POST','objects/locations',{'name':'Permission location'},200),
      ('EQUIPMENT','ADMIN','POST','objects/equipment',{'name':'Permission equipment'},200),
      ('RECIPES','ADMIN','POST','objects/recipes',{'name':'Permission recipe'},200),
      ('RECIPES_MEALPLAN','RECIPES','POST','objects/meal_plan',{'day':'2026-03-20','type':'note','note':'Permission meal'},200),
      ('SHOPPINGLIST_ITEMS_ADD','SHOPPINGLIST','POST','stock/shoppinglist/add-product',None,204),
      ('SHOPPINGLIST_ITEMS_DELETE','SHOPPINGLIST','POST','stock/shoppinglist/clear',{'list_id':f['list']},204),
      ('STOCK_PURCHASE','STOCK','POST','add',{'amount':1,'price':2},200),
      ('STOCK_CONSUME','STOCK','POST','consume',{'amount':1},200),
      ('STOCK_OPEN','STOCK','POST','open',{'amount':1},200),
      ('STOCK_INVENTORY','STOCK','POST','inventory',{'new_amount':50},200),
      ('STOCK_TRANSFER','STOCK','POST','transfer',{'amount':1,'location_id_from':f['loc'],'location_id_to':f['cold']},200),
      ('CHORE_TRACK_EXECUTION','CHORES','POST','chore-execute',{'tracked_time':'2026-03-10 08:00:00'},200),
      ('BATTERIES_TRACK_CHARGE_CYCLE','BATTERIES','POST','battery-charge',{'tracked_time':'2026-03-10 08:00:00'},200),
      ('TASKS_MARK_COMPLETED','TASKS','POST','task-complete',{'done_time':'2026-03-10 08:00:00'},204),
      ('TASKS_UNDO_EXECUTION','TASKS','POST','task-undo',{},204),
      ('USERS_READ','USERS','GET','users',None,200),
    ]
    for leaf,parent,method,target,body,status in cases:
        s.needs=f['needs']+who+[perms,signed]
        fixture_deps=[]
        p=ch=bt=t=None
        if leaf.startswith(('STOCK_','SHOPPINGLIST_')):
            pf,p=fx(s,leaf,'products',product(f,'Permission '+leaf),'perm-'+leaf);fixture_deps.append(pf)
            stocked=s.api('permission-fixture',leaf,'stock','POST',route(p,'/add'),body={'amount':100,'price':2},needs=[pf])
            fixture_deps.append(stocked)
        if target=='chore-execute':
            cf,ch=fx(s,leaf,'chores',{'name':'Permission '+leaf,'period_type':'manually','assignment_type':'no-assignment'},'perm-ch-'+leaf);fixture_deps.append(cf)
        if target=='battery-charge':
            bf,bt=fx(s,leaf,'batteries',{'name':'Permission '+leaf},'perm-bt-'+leaf);fixture_deps.append(bf)
        if target in ('task-complete','task-undo'):
            tf,t=fx(s,leaf,'tasks',{'name':'Permission '+leaf,'done':1 if target=='task-undo' else 0},'perm-t-'+leaf);fixture_deps.append(tf)
        path=route(p,'/'+target) if target in ('add','consume','open','inventory','transfer') else target
        if target=='chore-execute':path=pathref('chores/{id}/execute',id=ch)
        if target=='battery-charge':path=pathref('batteries/{id}/charge',id=bt)
        if target=='task-complete':path=pathref('tasks/{id}/complete',id=t)
        if target=='task-undo':path=pathref('tasks/{id}/undo',id=t)
        if leaf=='SHOPPINGLIST_ITEMS_ADD':body={'product_id':p,'product_amount':2,'list_id':f['list']}
        s.needs=who+[perms,signed]+fixture_deps
        permpath=pathref('users/{id}/permissions',id=uid)
        reset=s.api('permissions',leaf,'remove-grants','PUT',permpath,body={'permissions':[]},status=204,
                    after=readback(permpath,['permission_id'],hint='user_permissions'))
        denied=s.api('permissions',leaf,'denied','%s'%method,path,actor=newauth,body=body,status=[400,403],needs=[reset])
        granted=s.api('permissions',leaf,'grant-leaf','PUT',permpath,body={'permissions':[permission(leaf)]},status=204,needs=[denied],
                      after=readback(permpath,['permission_id'],hint='user_permissions'))
        allowed=s.api('permissions',leaf,'allowed-leaf',method,path,actor=newauth,body=body,status=status,needs=[granted],hint='stock_log' if target in ('add','consume','open','inventory','transfer') else 'object')
        parentgrant=s.api('permissions',leaf,'grant-parent','PUT',permpath,body={'permissions':[permission(parent)]},status=204,needs=[allowed])
        parentbody=dict(body) if isinstance(body,dict) else body
        if leaf in ('MASTER_DATA_EDIT','EQUIPMENT'):parentbody['name']+=' parent'
        if leaf=='STOCK_INVENTORY':parentbody['new_amount']=55
        s.api('permissions',leaf,'allowed-parent',method,path,actor=newauth,body=parentbody,status=status,needs=[parentgrant],hint='stock_log' if target in ('add','consume','open','inventory','transfer') else 'object')
        # Bind a refusal to the positive operation in the same permission scenario.
        next(x for x in s.cases if x.id==denied).requires=(allowed,)
    s.needs=who+[signed]
    restored=s.api('permissions','account','restore-admin','PUT',pathref('users/{id}/permissions',id=uid),body={'permissions':[permission('ADMIN')]},status=204)
    # Incremental grant and session listing are exercised in api_coverage; this episode keeps the full account lifecycle.
    s.api('users','listing','filtered','GET','users',params={'query[]':'username=alex'},fields=['username','first_name','last_name','display_name'],hint='users',needs=[restored])
    deleted=s.api('users','account','delete','DELETE',pathref('users/{id}',id=uid),status=204,needs=[restored],
                  after=deleted_user_state)
    s.api('users','account','no-new-session','GET','user',actor=newauth,status=302,needs=[deleted],requires=[signed],fresh_auth=True)


def deleted_user_state(c):
    r,rows=c.request('GET','users')
    assert r.status_code==200 and isinstance(rows,list),'user list unavailable after deletion'
    assert all(x['username']!='alex' for x in rows),'deleted user remains'
    assert any(x['username']=='admin' for x in rows),'deletion removed unrelated admin'
    return c.observe(r,rows,'users',['username'])
