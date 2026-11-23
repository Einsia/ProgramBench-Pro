"""Small public fixtures and behavioral observations shared by program scenarios."""
from harness import Ref, pathref, resolve, subset


def objpath(entity, ident):
    return pathref('objects/'+entity+'/{id}', id=ident)


def fx(s, scenario, entity, body, key):
    point=s.api('entity-fixture',scenario,key,'POST','objects/'+entity,body=body,save=key,hint=entity,needs=[])
    return point, Ref(key,'created_object_id')


def foundation(s, scenario='base'):
    values={};deps=[];bykey={}
    for key,entity,body in [('loc','locations',{'name':'Pantry'}),('cold','locations',{'name':'Freezer','is_freezer':1}),
        ('unit','quantity_units',{'name':'Item','name_plural':'Items'}),('pack','quantity_units',{'name':'Box','name_plural':'Boxes'}),
        ('shop','shopping_locations',{'name':'Corner store'}),('group','product_groups',{'name':'Staples'}),
        ('list','shopping_lists',{'name':'Weekly'}),('cat','task_categories',{'name':'Home'}),
        ('section','meal_plan_sections',{'name':'Dinner','sort_number':2,'time_info':'18:30'})]:
        point,ident=fx(s,scenario,entity,body,scenario+'-'+key);values[key]=ident;deps.append(point);bykey[key]=point
    user=s.api('entity-fixture',scenario,'current-user','GET','user',save=scenario+'-admin')
    deps.append(user);bykey['admin']=user;values['admin']=Ref(scenario+'-admin',0,'id')
    s.needs=deps
    values['needs']=list(deps)
    values['deps']=bykey
    s.foundation_ids=getattr(s,'foundation_ids',set())|set(deps)
    return values


def product(f,name,**extra):
    return {'name':name,'location_id':f['loc'],'qu_id_purchase':f['unit'],'qu_id_stock':f['unit'],**extra}


def readback(path,fields=None,want=None,hint='object',params=None,ordered=False,actor='admin'):
    def observe(c):
        r,p=c.request('GET',resolve(path,c),resolve(actor,c),params=resolve(params,c))
        assert r.status_code==200,'readback failed: '+str(r.status_code)
        if want is not None:
            if isinstance(p,list):
                assert len(p)==1,'readback expected exactly one object'
                subset(p[0],resolve(want,c),resolve(path,c))
            else:subset(p,resolve(want,c),resolve(path,c))
        return c.observe(r,p,'numeric-setting' if '/settings/' in '/'+resolve(path,c) else hint,fields,ordered)
    return observe


def check_list(fields,expected,ordered=False):
    def check(c,r,p):
        assert isinstance(p,list),'expected list'
        want=resolve(expected,c)
        assert len(p)==len(want),'unexpected number of rows'
        actual=[{k:x[k] for k in fields} for x in p]
        if ordered:
            for x,y in zip(actual,want):subset(x,y)
        else:
            import json
            actual.sort(key=lambda x:json.dumps(x,sort_keys=True));want=sorted(want,key=lambda x:json.dumps(x,sort_keys=True))
            for x,y in zip(actual,want):subset(x,y)
    return check
