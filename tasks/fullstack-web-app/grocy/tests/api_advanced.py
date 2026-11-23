"""Cross-feature inventory rules, unit conversion, assignments and offline barcode lookup."""
from harness import Ref,resolve,pathref,subset
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS,ENTRY_FIELDS
from api_users import userfixture


def build(s):
    f=foundation(s)
    # Parent stock is separate from aggregate child stock; substitution changes the child.
    s.needs=list(f['needs'])
    pf,parent=fx(s,'hierarchy','products',product(f,'Parent pasta',no_own_stock=1,min_stock_amount=6),'parent')
    cf,child=fx(s,'hierarchy','products',product(f,'Child pasta',parent_product_id=parent,min_stock_amount=2),'child')
    s.needs=f['needs']+[pf,cf]
    a=s.api('hierarchy','stock','child-purchase','POST',route(child,'/add'),body={'amount':5,'price':2,'best_before_date':'2026-05-01'},fields=LOG_FIELDS,hint='stock_log')
    s.api('hierarchy','stock','aggregate','GET',route(parent),fields=['stock_amount','stock_amount_aggregated','stock_amount_opened_aggregated','is_aggregated_amount'],
          hint='products',want={'stock_amount_aggregated':5},needs=[a])
    s.api('hierarchy','stock','substitution-entries','GET',route(parent,'/entries'),params={'include_sub_products':'true'},fields=ENTRY_FIELDS,hint='stock',needs=[a],
          check=lambda c,r,p: child_entries(c,p,child,5))
    s.api('hierarchy','stock','own-entries-only','GET',route(parent,'/entries'),params={'include_sub_products':'false'},
          fields=ENTRY_FIELDS,hint='stock',needs=[a],requires=[a],check=lambda c,r,p: empty_own(p))
    denied=s.api('hierarchy','stock','no-substitution','POST',route(parent,'/consume'),body={'amount':1,'allow_subproduct_substitution':False},status=400,needs=[a],requires=[a])
    opened=s.api('hierarchy','stock','substitute-open','POST',route(parent,'/open'),body={'amount':1,'allow_subproduct_substitution':True},fields=LOG_FIELDS,hint='stock_log',needs=[denied])
    used=s.api('hierarchy','stock','substitute-consume','POST',route(parent,'/consume'),body={'amount':2,'allow_subproduct_substitution':True},fields=LOG_FIELDS,hint='stock_log',needs=[opened],after=entries(child,3))
    s.api('hierarchy','stock','child-remainder','GET',route(child),fields=['stock_amount','stock_amount_opened'],want={'stock_amount':3},needs=[used])
    # Global conversions, reverse conversions, transitive conversions and product-specific overrides.
    s.needs=list(f['needs'])
    uf,unit=fx(s,'conversions','quantity_units',{'name':'Pallet','name_plural':'Pallets'},'pallet')
    pf,p=fx(s,'conversions','products',product(f,'Conversion item'),'conversion-p')
    a,aid=fx(s,'conversions','quantity_unit_conversions',{'from_qu_id':f['pack'],'to_qu_id':f['unit'],'factor':6},'global-conversion')
    b,bid=fx(s,'conversions','quantity_unit_conversions',{'from_qu_id':unit,'to_qu_id':f['pack'],'factor':10},'chain-conversion')
    s.needs=f['needs']+[uf,pf,a,b]
    for label,fromunit,tounit in [('forward',f['pack'],f['unit']),('reverse',f['unit'],f['pack']),('chain',unit,f['unit'])]:
        s.api('conversions',label,'resolved','GET','objects/quantity_unit_conversions_resolved',
              params={'query[]':[pathref('product_id={id}',id=p),pathref('from_qu_id={id}',id=fromunit),pathref('to_qu_id={id}',id=tounit)]},
              fields=['product_id','from_qu_id','to_qu_id','factor'],hint='quantity_unit_conversions')
    override=s.api('conversions','specific','create','POST','objects/quantity_unit_conversions',body={'product_id':p,'from_qu_id':f['pack'],'to_qu_id':f['unit'],'factor':8},save='override',hint='quantity_unit_conversions')
    applied=s.api('conversions','specific','use-purchase-unit','PUT',objpath('products',p),body={'qu_id_purchase':f['pack'],'qu_id_price':f['pack']},status=204,needs=[override])
    s.api('conversions','specific','details','GET',route(p),fields=['qu_conversion_factor_purchase_to_stock','qu_conversion_factor_price_to_stock'],needs=[applied])
    s.api('conversions','specific','resolved','GET','objects/quantity_unit_conversions_resolved',
          params={'query[]':[pathref('product_id={id}',id=p),pathref('from_qu_id={id}',id=f['pack']),pathref('to_qu_id={id}',id=f['unit'])]},
          fields=['product_id','from_qu_id','to_qu_id','factor'],hint='quantity_unit_conversions',needs=[override])
    # Editing a concrete stock entry replaces amount, price, dates, open state, location and note together.
    s.needs=list(f['needs']);pf,p=fx(s,'entry-edit','products',product(f,'Editable stock'),'edit-p')
    s.needs=f['needs']+[pf]
    add=s.api('entry-edit','stock','purchase','POST',route(p,'/add'),body={'amount':5,'price':2,'best_before_date':'2026-04-01'},fields=LOG_FIELDS,hint='stock_log')
    fetched=s.api('entry-edit','stock','entries','GET',route(p,'/entries'),save='editable-entries',fields=ENTRY_FIELDS,hint='stock',needs=[add])
    sid=Ref('editable-entries',0,'id')
    s.api('entry-edit','stock','individual','GET',pathref('stock/entry/{id}',id=sid),fields=ENTRY_FIELDS,hint='stock',needs=[fetched])
    edit=s.api('entry-edit','stock','edit','PUT',pathref('stock/entry/{id}',id=sid),body={'amount':7.5,'price':3.25,'best_before_date':'2026-05-15',
         'purchased_date':'2026-03-02','location_id':f['cold'],'shopping_location_id':f['shop'],'open':True,'note':'Edited Ω'},
         fields=LOG_FIELDS,hint='stock_log',needs=[fetched],save='edit-tx',after=entries(p,7.5))
    s.api('entry-edit','stock','undo-edit','POST',pathref('stock/transactions/{id}/undo',id=Ref('edit-tx',0,'transaction_id')),body={},status=204,needs=[edit],after=entries(p,5))
    # Automatic shopping commands distinguish low stock, overdue best-before dates and expired use-by dates.
    for name,extra,due in [('missing',{'min_stock_amount':5},'2026-06-01'),('overdue',{'due_type':1},'2026-03-08'),('expired',{'due_type':2},'2026-03-08')]:
        s.needs=list(f['needs']);pf,p=fx(s,name,'products',product(f,'Automatic '+name,**extra),'automatic-'+name)
        lf,l=fx(s,name,'shopping_lists',{'name':'Automatic '+name},'auto-list-'+name)
        stock=s.api('shopping-fixture',name,'stock','POST',route(p,'/add'),body={'amount':2,'best_before_date':due})
        s.needs=f['needs']+[pf,lf,stock]
        projection=readback('objects/shopping_list',['product_id','amount','shopping_list_id'],hint='shopping_list',params={'query[]':pathref('product_id={id}',id=p)})
        added=s.api('shopping-auto',name,'add','POST','stock/shoppinglist/add-'+name+'-products',body={'list_id':l},status=204,after=projection)
        repeated=s.api('shopping-auto',name,'repeat','POST','stock/shoppinglist/add-'+name+'-products',body={'list_id':l},status=204,needs=[added],after=projection)
        saved=s.api('shopping-auto',name,'rows','GET','objects/shopping_list',params={'query[]':pathref('product_id={id}',id=p)},save='auto-rows-'+name,
                    fields=['product_id','amount','shopping_list_id','done'],hint='shopping_list',needs=[repeated])
        done=s.api('shopping-auto',name,'mark-done','PUT',objpath('shopping_list',Ref('auto-rows-'+name,0,'id')),body={'done':1},status=204,needs=[saved])
        s.api('shopping-auto',name,'clear-done','POST','stock/shoppinglist/clear',body={'list_id':l,'done_only':True},status=204,needs=[done],after=projection,requires=[added])
    # Assignment rotation is observable from consecutive executions; random assignment is checked by membership.
    s.needs=[];ua,a=userfixture(s,'aaron','Aaron','One');ub,b=userfixture(s,'brenda','Brenda','Two')
    for name in ['in-alphabetical-order','who-least-did-first','random']:
        s.needs=ua+ub
        cf,ch=fx(s,name,'chores',{'name':'Assigned '+name,'period_type':'manually','assignment_type':name,
             'assignment_config':lambda c,a=a,b=b:str(resolve(a,c))+','+str(resolve(b,c))},'assigned-'+name)
        s.needs=ua+ub+[cf]
        def membership(c,ch=ch,a=a,b=b):
            r,p=c.request('GET',resolve(objpath('chores',ch),c));assert r.status_code==200
            value=p['next_execution_assigned_to_user_id']
            assert value in (resolve(a,c),resolve(b,c)),'assignment left its configured user group'
            return {'assigned_to_group_member':True}
        for index,user in enumerate([a,a,b]):
            p=s.api('assignment',name,'execute-'+str(index),'POST',pathref('chores/{id}/execute',id=ch),
                    body={'tracked_time':'2026-03-0'+str(index+2)+' 08:00:00','done_by':user},fields=['chore_id','done_by_user_id','tracked_time'],hint='chores_log',
                    after=membership if name=='random' else readback(pathref('chores/{id}',id=ch),['next_execution_assigned_user','tracked_count'],hint='chores'))
            s.needs.append(p)
        s.api('assignment',name,'recalculate','POST','chores/executions/calculate-next-assignments',body={'chore_id':ch},status=204,
              after=membership if name=='random' else readback(pathref('chores/{id}',id=ch),['next_execution_assigned_user'],hint='chores'))
    # The upstream demo lookup plugin works offline. Its randomly generated display name is not an expected literal.
    s.needs=[]
    def lookup(c):
        r,p=c.request('GET','stock/barcodes/external-lookup/DEMO-PBP',params={'add':'true'})
        assert r.status_code==200 and isinstance(p,dict),'offline lookup failed'
        c.state['lookup']=p
        assert p.get('id'),'lookup did not add a product'
        rr,pp=c.request('GET','stock/products/by-barcode/DEMO-PBP')
        assert rr.status_code==200 and pp['product']['id']==int(p['id']),'lookup barcode does not resolve to new product'
        return {'created':True,'barcode_resolves':True}
    looked=s.add('barcode-demo','lookup','create',lookup,description='Offline upstream lookup creates a product and registers its barcode')
    s.api('barcode-demo','lookup','nothing','GET','stock/barcodes/external-lookup/nothing',status=200,requires=[looked])
    s.api('barcode-demo','lookup','error','GET','stock/barcodes/external-lookup/error',status=400,requires=[looked])


def child_entries(c,rows,child,amount):
    assert len(rows)==1 and rows[0]['product_id']==resolve(child,c),'expected the actual child batch'
    assert float(rows[0]['amount'])==amount and rows[0]['stock_id'],'missing child stock'

def empty_own(rows):
    assert rows==[],'parent without own stock must have no own entries'
