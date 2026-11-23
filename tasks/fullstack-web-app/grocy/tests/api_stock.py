"""Inventory transactions, batch selection, dates, locations, prices, barcodes and shopping lists."""
from harness import Ref,resolve,pathref,subset
from common import foundation,fx,product,objpath,readback

LOG_FIELDS=['product_id','amount','best_before_date','purchased_date','transaction_type','spoiled','price',
            'location_id','shopping_location_id','note','undone']
ENTRY_FIELDS=['product_id','amount','best_before_date','purchased_date','price','open','location_id','shopping_location_id','note']


def route(ident,suffix=''):
    return pathref('stock/products/{id}'+suffix,id=ident)


def entries(ident,expected=None):
    def observe(c):
        r,p=c.request('GET',resolve(route(ident,'/entries'),c))
        assert r.status_code==200 and isinstance(p,list),'stock entries unavailable'
        if expected is not None:assert abs(sum(float(x['amount']) for x in p)-expected)<1e-8,'incorrect inventory total'
        return c.observe(r,p,'stock',ENTRY_FIELDS)
    return observe


def nonempty(c,r,p):
    assert isinstance(p,list) and p,'transaction must return its bookings'


def build(s):
    f=foundation(s)
    configs=[
      ('ordinary',{}, {'amount':5,'price':2.5,'best_before_date':'2026-04-01'}),
      ('fractional',{}, {'amount':2.75,'price':1.25,'best_before_date':'2026-04-02'}),
      ('free',{}, {'amount':3,'price':0,'best_before_date':'2026-04-03'}),
      ('never-expires',{'default_best_before_days':-1},{'amount':4,'price':1.5}),
      ('default-due',{'default_best_before_days':14},{'amount':4,'price':1.5}),
      ('explicit-purchase',{}, {'amount':4,'price':1.25,'best_before_date':'2026-04-04','purchased_date':'2026-03-01'}),
      ('past-due',{}, {'amount':4,'price':1.25,'best_before_date':'2026-03-09'}),
      ('expires-today',{'due_type':2},{'amount':4,'price':1.25,'best_before_date':'2026-03-10'}),
      ('note-store',{}, {'amount':4,'price':1.25,'best_before_date':'2026-04-05','shopping_location_id':f['shop'],'note':'Fresh Ω batch'}),
      ('freezer',{'default_best_before_days_after_freezing':30},{'amount':4,'price':1.25,'location_id':f['cold']}),
      ('opening-due',{'default_best_before_days_after_open':3},{'amount':4,'price':1.25,'best_before_date':'2026-04-06'}),
      ('move-on-open',{'move_on_open':1,'default_consume_location_id':f['cold']},{'amount':4,'price':1.25,'best_before_date':'2026-04-07'}),
    ]
    for name,extra,body in configs:
        s.needs=list(f['needs']);pfx,p=fx(s,name,'products',product(f,'Stock '+name,**extra),'p-'+name)
        s.needs=f['needs']+[pfx]
        added=s.api('stock',name,'purchase','POST',route(p,'/add'),body=body,save='tx-'+name,hint='stock_log',fields=LOG_FIELDS,
                    check=nonempty,after=entries(p,float(body['amount'])))
        s.needs=f['needs']+[pfx,added]
        s.api('stock',name,'details','GET',route(p),fields=['stock_amount','stock_amount_opened','last_price','next_due_date'],hint='products')
        s.api('stock',name,'locations','GET',route(p,'/locations'),fields=['location_id','amount'],hint='locations')
        s.api('stock',name,'price-history','GET',route(p,'/price-history'),hint='price-history')
        s.api('stock',name,'transaction','GET',pathref('stock/transactions/{id}',id=Ref('tx-'+name,0,'transaction_id')),fields=LOG_FIELDS,hint='stock_log')
        s.api('stock',name,'booking','GET',pathref('stock/bookings/{id}',id=Ref('tx-'+name,0,'id')),fields=LOG_FIELDS,hint='stock_log')
        opened=s.api('stock',name,'open-one','POST',route(p,'/open'),body={'amount':1},save='open-'+name,
                     check=nonempty,fields=LOG_FIELDS,hint='stock_log',after=entries(p,float(body['amount'])))
        consumed=s.api('stock',name,'consume-fraction','POST',route(p,'/consume'),body={'amount':0.5},save='consume-'+name,
                       check=nonempty,fields=LOG_FIELDS,hint='stock_log',needs=[opened],after=entries(p,float(body['amount'])-.5))
        undone=s.api('stock',name,'undo-consume','POST',pathref('stock/transactions/{id}/undo',id=Ref('consume-'+name,0,'transaction_id')),
                     body={},status=204,needs=[consumed],after=entries(p,float(body['amount'])))
        s.api('stock',name,'repeat-undo-refused','POST',pathref('stock/transactions/{id}/undo',id=Ref('consume-'+name,0,'transaction_id')),
              body={},status=400,needs=[undone],requires=[consumed])
        s.api('stock',name,'excess-consume','POST',route(p,'/consume'),body={'amount':1000},status=400,
              needs=[undone],requires=[added],after=entries(p,float(body['amount'])))
    # Distinguishable batches make FIFO/expiry/opened selection and transfers observable.
    s.needs=list(f['needs']);pfx,p=fx(s,'batches','products',product(f,'Batch selection',default_best_before_days_after_open=2),'batch-p')
    s.needs=f['needs']+[pfx];previous=[]
    for label,body in [('late',{'amount':5,'price':3,'best_before_date':'2026-05-01'}),
                       ('early',{'amount':2,'price':2,'best_before_date':'2026-04-01'}),
                       ('old-purchase',{'amount':3,'price':1,'best_before_date':'2026-04-01','purchased_date':'2026-03-01'})]:
        previous.append(s.api('batch',label,'add','POST',route(p,'/add'),body=body,save='batch-'+label,check=nonempty,fields=LOG_FIELDS,hint='stock_log'))
    s.needs=previous
    selected=s.api('batch','selection','consume-earliest','POST',route(p,'/consume'),body={'amount':4},fields=LOG_FIELDS,hint='stock_log',
                   after=entries(p,6))
    moved=s.api('batch','selection','transfer-two','POST',route(p,'/transfer'),body={'amount':2,'location_id_from':f['loc'],'location_id_to':f['cold']},
                needs=[selected],save='moved',fields=LOG_FIELDS,hint='stock_log',after=entries(p,6))
    s.api('batch','selection','locations-split','GET',route(p,'/locations'),fields=['location_id','amount'],hint='locations',needs=[moved])
    s.api('batch','selection','location-entries','GET',pathref('stock/locations/{id}/entries',id=f['cold']),
          params={'query[]':pathref('product_id={id}',id=p)},fields=ENTRY_FIELDS,hint='stock',needs=[moved])
    used=s.api('batch','selection','consume-at-location','POST',route(p,'/consume'),body={'amount':1,'location_id':f['cold']},
               needs=[moved],fields=LOG_FIELDS,hint='stock_log',after=entries(p,5))
    corrected=s.api('batch','selection','inventory-increase','POST',route(p,'/inventory'),body={'new_amount':8,'best_before_date':'2026-06-01','price':4},
                    needs=[used],save='inventory-up',fields=LOG_FIELDS,hint='stock_log',after=entries(p,8))
    lower=s.api('batch','selection','inventory-decrease','POST',route(p,'/inventory'),body={'new_amount':2},needs=[corrected],fields=LOG_FIELDS,hint='stock_log',after=entries(p,2))
    spoiled=s.api('batch','selection','spoiled-consumption','POST',route(p,'/consume'),body={'amount':1,'spoiled':True},needs=[lower],
                  save='spoiled',fields=LOG_FIELDS,hint='stock_log',after=entries(p,1))
    s.api('batch','selection','undo-booking','POST',pathref('stock/bookings/{id}/undo',id=Ref('spoiled',0,'id')),body={},
          status=204,needs=[spoiled],after=entries(p,2))
    # Barcodes route to the same product and maintain all ordinary transaction behavior.
    s.needs=list(f['needs']);bf,bp=fx(s,'barcode','products',product(f,'Barcode item'),'barcode-p')
    qf,_=fx(s,'barcode','quantity_unit_conversions',{'from_qu_id':f['pack'],'to_qu_id':f['unit'],'factor':6,'product_id':bp},'barcode-conversion')
    bc,_=fx(s,'barcode','product_barcodes',{'product_id':bp,'barcode':'PBP12345','amount':2,'qu_id':f['pack'],'last_price':2.75},'barcode')
    s.needs=f['needs']+[bf,qf,bc]
    s.api('barcode','routing','lookup','GET','stock/products/by-barcode/PBP12345',hint='products',fields=['product','stock_amount'])
    prev=s.api('barcode','routing','add','POST','stock/products/by-barcode/PBP12345/add',body={'amount':8,'best_before_date':'2026-05-01','price':1.25},
               fields=LOG_FIELDS,hint='stock_log',after=entries(bp,8))
    for label,body in [('open',{'amount':1}),('consume',{'amount':1}),('inventory',{'new_amount':10}),
                       ('transfer',{'amount':2,'location_id_from':f['loc'],'location_id_to':f['cold']})]:
        prev=s.api('barcode','routing',label,'POST','stock/products/by-barcode/PBP12345/'+label,body=body,needs=[prev],fields=LOG_FIELDS,hint='stock_log',after=entries(bp))
    for operation,body in [('add',{'amount':1}),('consume',{'amount':1}),('open',{'amount':1}),('inventory',{'new_amount':1}),
                           ('transfer',{'amount':1,'location_id_from':f['loc'],'location_id_to':f['cold']})]:
        s.api('barcode','missing',operation,'POST','stock/products/by-barcode/ABSENT-BARCODE/'+operation,body=body,status=400,requires=[prev])
    s.api('barcode','missing','lookup','GET','stock/products/by-barcode/ABSENT-BARCODE',status=400,requires=[prev])
    # Required parameters, invalid quantities and invalid locations on an existing stocked product.
    for label,op,body in [('add-missing','add',{}),('add-negative','add',{'amount':-1}),('add-zero','add',{'amount':0}),
        ('consume-missing','consume',{}),('consume-negative','consume',{'amount':-1}),('consume-zero','consume',{'amount':0}),
        ('open-missing','open',{}),('open-excess','open',{'amount':1000}),('inventory-missing','inventory',{}),
        ('transfer-missing-amount','transfer',{'location_id_from':f['loc'],'location_id_to':f['cold']}),
        ('transfer-missing-from','transfer',{'amount':1,'location_id_to':f['cold']}),
        ('transfer-missing-to','transfer',{'amount':1,'location_id_from':f['loc']}),
        ('transfer-excess','transfer',{'amount':1000,'location_id_from':f['loc'],'location_id_to':f['cold']}),
        ('transfer-unknown-from','transfer',{'amount':1,'location_id_from':999999,'location_id_to':f['cold']})]:
        s.api('stock-errors','parameters',label,'POST',route(bp,'/'+op),body=body,status=400,requires=[prev],after=entries(bp))
    # Tare handling derives net stock from the gross measurements.
    s.needs=list(f['needs']);tf,tp=fx(s,'tare','products',product(f,'Flour jar',enable_tare_weight_handling=1,tare_weight=.5),'tare-p')
    s.needs=f['needs']+[tf]
    a=s.api('tare','gross','purchase','POST',route(tp,'/add'),body={'amount':3.5,'price':2},fields=LOG_FIELDS,hint='stock_log',after=entries(tp,3))
    a=s.api('tare','gross','consume-to-gross','POST',route(tp,'/consume'),body={'amount':2.5},needs=[a],fields=LOG_FIELDS,hint='stock_log',after=entries(tp,2))
    a=s.api('tare','gross','exact-consumption','POST',route(tp,'/consume'),body={'amount':.5,'exact_amount':True},needs=[a],fields=LOG_FIELDS,hint='stock_log',after=entries(tp,1.5))
    s.api('tare','gross','inventory-gross','POST',route(tp,'/inventory'),body={'new_amount':4.5},needs=[a],fields=LOG_FIELDS,hint='stock_log',after=entries(tp,4))
    # Product copy and merge preserve associations and stock rather than returning only a new identifier.
    s.needs=list(f['needs']);cf,cp=fx(s,'copy','products',product(f,'Copy original',description='Copy details',calories=123),'copy-p')
    s.needs=f['needs']+[cf]
    copied=s.api('products','copy','copy','POST',route(cp,'/copy'),body={},save='copied',hint='products')
    s.api('products','copy','copied-fields','GET',objpath('products',Ref('copied','created_object_id')),needs=[copied],
          fields=['description','calories','qu_id_stock','location_id'],want={'description':'Copy details','calories':123},hint='products')
    aa=s.api('products','merge','first-stock','POST',route(cp,'/add'),body={'amount':3,'price':2},fields=LOG_FIELDS,hint='stock_log')
    bb=s.api('products','merge','second-stock','POST',route(Ref('copied','created_object_id'),'/add'),body={'amount':2,'price':3},needs=[copied],fields=LOG_FIELDS,hint='stock_log')
    merged=s.api('products','merge','merge','POST',pathref('stock/products/{a}/merge/{b}',a=cp,b=Ref('copied','created_object_id')),
                 body={},status=204,needs=[aa,bb],after=entries(cp,5))
    s.api('products','merge','removed','GET',objpath('products',Ref('copied','created_object_id')),status=404,needs=[merged],requires=[copied])
    # Shopping list commands act on isolated lists with real products and partial amounts.
    for name,body in [('ordinary',{'product_amount':3}),('fractional',{'product_amount':2.5}),
                      ('note',{'product_amount':2,'note':'Bring reusable bag'}),('quantity',{'product_amount':6,'qu_id':f['pack']})]:
        s.needs=list(f['needs']);lf,l=fx(s,name,'shopping_lists',{'name':'Shopping '+name},'shopping-'+name)
        s.needs=f['needs']+[lf,bf]
        projection=readback('objects/shopping_list',fields=['product_id','amount','note','done','qu_id'],hint='shopping_list',
                            params=pathref('query[]=shopping_list_id={id}',id=l))
        # params are a mapping, so values stay correctly encoded.
        projection=readback('objects/shopping_list',fields=['product_id','amount','note','done','qu_id'],hint='shopping_list',
                            params={'query[]':pathref('shopping_list_id={id}',id=l)})
        a=s.api('shopping',name,'add','POST','stock/shoppinglist/add-product',body={'product_id':bp,'list_id':l,**body},status=204,after=projection)
        a=s.api('shopping',name,'accumulate','POST','stock/shoppinglist/add-product',body={'product_id':bp,'list_id':l,'product_amount':1},status=204,needs=[a],after=projection)
        a=s.api('shopping',name,'remove-part','POST','stock/shoppinglist/remove-product',body={'product_id':bp,'list_id':l,'product_amount':.5},status=204,needs=[a],after=projection)
        s.api('shopping',name,'clear','POST','stock/shoppinglist/clear',body={'list_id':l},status=204,needs=[a],after=projection,requires=[a])
    s.needs=list(f['needs'])
    s.api('stock','overview','current','GET','stock',hint='products')
    s.api('stock','overview','volatile','GET','stock/volatile',hint='products')
