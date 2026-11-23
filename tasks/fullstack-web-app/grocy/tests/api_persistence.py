"""State survives process restarts; reset provides a genuinely fresh installation."""
from harness import Ref,resolve,pathref,b64
from common import foundation,fx,product,objpath,readback
from api_stock import route,entries,LOG_FIELDS


def build(s):
    f=foundation(s)
    dependencies=list(f['needs']);resources=[]
    specs=[('products',product(f,'Persistent rice',min_stock_amount=3)),
      ('recipes',{'name':'Persistent soup','description':'Simmer gently'}),
      ('chores',{'name':'Persistent chore','period_type':'daily','start_date':'2026-03-01 09:00:00'}),
      ('batteries',{'name':'Persistent battery','charge_interval_days':7}),
      ('tasks',{'name':'Persistent task','due_date':'2026-03-14 12:00:00'}),
      ('equipment',{'name':'Persistent appliance','description':'Kitchen tool'}),
      ('shopping_lists',{'name':'Persistent shopping','description':'Weekly food'}),
      ('userentities',{'name':'persistent_collection','caption':'Persistent collection'})]
    for entity,body in specs:
        fixture,ident=fx(s,'persistence',entity,body,'persist-'+entity);dependencies.append(fixture)
        resources.append((entity,ident,list(body),fixture))
    p=Ref('persist-products','created_object_id')
    stocked=s.api('persist-fixture','inventory','stock','POST',route(p,'/add'),body={'amount':5,'price':2,'best_before_date':'2026-05-01'})
    uploaded=s.api('persist-fixture','files','upload','PUT','files/userfiles/'+b64('persistent.txt'),raw='Persistent Ω data',content_type='text/plain',status=204)
    setting=s.api('persist-fixture','settings','put','PUT','user/settings/stock_due_soon_days',body={'value':'11'},status=204)
    s.needs=[stocked]
    def restart(c):
        before=entries(p,5)(c)
        status=c.broker.call({'op':'restart'})
        assert status['ready'],'restart did not become ready'
        after=entries(p,5)(c)
        c.aliases.compare(after,before)
        return after
    restarted=s.add('persistence','lifecycle','restart',restart,description='Restart retains inventory batches and quantities')
    for entity,ident,fields,fixture in resources:
        s.api('persistence',entity,'saved-object','GET',objpath(entity,ident),fields=fields,hint=entity,needs=[restarted,fixture])
    s.api('persistence','settings','saved-setting','GET','user/settings/stock_due_soon_days',want={'value':'11'},needs=[restarted,setting])
    s.api('persistence','files','saved-bytes','GET','files/userfiles/'+b64('persistent.txt'),hint='bytes',needs=[restarted,uploaded],
          check=lambda c,r,p: assert_bytes(r.content,'Persistent Ω data'.encode()))
    def reset(c):
        status=c.broker.call({'op':'reset'});assert status['ready'],'reset did not become ready'
        r,p=c.request('GET','objects/products');assert r.status_code==200 and p==[],'reset retained products'
        rr,pp=c.request('GET','user/settings/stock_due_soon_days');assert rr.status_code==200 and int(pp['value'])==5,'reset retained settings'
        fr,fp=c.request('GET','files/userfiles/'+b64('persistent.txt'));assert fr.status_code==404,'reset retained files'
        return {'products_empty':True,'default_due_soon_days':5,'file_status':404}
    s.add('persistence','lifecycle','reset',reset,description='Reset removes inventory, stored files and setting overrides',needs=[restarted,uploaded,setting],requires=[restarted])


def assert_bytes(actual,expected):
    assert actual==expected,'persisted file bytes changed'
