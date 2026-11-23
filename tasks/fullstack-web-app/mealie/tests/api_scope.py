'''Cross-group isolation of identically named data through real resource IDs.'''
from harness import Ref, pathref


def build(s):
    a = s.api
    fx = 'scope-fixture'
    a(fx, 'groups', 'other', 'POST', 'admin/groups', body={'name': 'Other Group'}, save='other-group')
    a(fx, 'users', 'other', 'POST', 'admin/users',
      body={'username': 'other-user', 'fullName': 'Other User', 'email': 'other@example.com',
            'password': 'OtherPassword1', 'group': 'Other Group', 'household': 'Family',
            'canManage': True, 'canManageHousehold': True, 'canOrganize': True, 'admin': False},
      before=lambda c: c.creds.update({'other-user': 'OtherPassword1'}), save='other-user')
    for kind, route in [('tags', 'organizers/tags'), ('categories', 'organizers/categories'), ('tools', 'organizers/tools'), ('foods', 'foods'), ('units', 'units')]:
        a(fx, 'data', kind + '-home', 'POST', route, body={'name': 'Shared name'}, save=kind + '-home')
        a(fx, 'data', kind + '-other', 'POST', route, actor='other-user', body={'name': 'Shared name'},
          save=kind + '-other')
        fam = 'scope-' + kind
        a(fam, 'visible', 'home', 'GET', route, fields=['name', 'id'])
        a(fam, 'visible', 'other', 'GET', route, actor='other-user', fields=['name', 'id'])
        a(fam, 'ids', 'other-cannot-read-home', 'GET', pathref(route + '/{id}', id=Ref(kind + '-home', 'id')),
          actor='other-user', status=None)
        a(fam, 'ids', 'home-cannot-read-other', 'GET', pathref(route + '/{id}', id=Ref(kind + '-other', 'id')),
          status=None)
        for method in ['PUT','DELETE']:
            if method == 'PUT' and kind in {'tags','categories'}:
                continue  # upstream returns 500 for missing/out-of-group organizer updates
            s.add(fam,'mutation',method.lower(),
                  lambda c,r=route,k=kind,m=method:attempt(c,r+'/'+str(c.state[k+'-home']['id']), 'other-user', m),
                  description='An outsider cannot '+method+' a real '+kind+' resource; owner state remains readable.')
    a(fx, 'recipes', 'home', 'POST', 'recipes', body={'name': 'Same Soup'})
    a(fx, 'recipes', 'other', 'POST', 'recipes', actor='other-user', body={'name': 'Same Soup'})
    a(fx,'recipes','home-read','GET','recipes/same-soup',save='home-recipe')
    a(fx,'recipes','other-read','GET','recipes/same-soup',actor='other-user',save='other-recipe')
    a('scope-recipes','ids','read-other','GET',pathref('recipes/{id}',id=Ref('other-recipe','id')),status=404)
    a('scope-recipes','ids','read-home','GET',pathref('recipes/{id}',id=Ref('home-recipe','id')),actor='other-user',status=404)
    for method in ['PATCH','DELETE']:
        s.add('scope-recipes','ids',method.lower(),lambda c,m=method:recipe_attempt(c,m))
    a('scope-recipes', 'read', 'home', 'GET', 'recipes/same-soup', fields=['name', 'groupId'])
    a('scope-recipes', 'read', 'other', 'GET', 'recipes/same-soup', actor='other-user', fields=['name', 'groupId'])
    a('scope-recipes', 'update', 'other', 'PATCH', 'recipes/same-soup', actor='other-user',
      body={'description': 'Only in other group'})
    a('scope-recipes', 'update', 'home-unchanged', 'GET', 'recipes/same-soup', fields=['description'])
    a('scope-recipes', 'update', 'other-changed', 'GET', 'recipes/same-soup', actor='other-user',
      fields=['description'])

    a(fx,'households','me','GET','users/self',save='me')
    a(fx,'households','another','POST','admin/households',body={'name':'Second','groupId':Ref('me','groupId')})
    a(fx,'households','member','POST','admin/users',body={'username':'second-user','fullName':'Second User','email':'second@example.com',
      'password':'SecondPassword1','group':'Home','household':'Second','canManage':True,'canManageHousehold':True,'admin':False},
      before=lambda c:c.creds.update({'second-user':'SecondPassword1'}))
    for kind,route,body in [('webhooks','households/webhooks',{'name':'Private hook','enabled':False,'url':'https://example.invalid/hook','scheduledTime':'17:30'}),
                            ('notifiers','households/events/notifications',{'name':'Private notifier','appriseUrl':'json://example.invalid/note'})]:
        a(fx,kind,'create','POST',route,body=body,save=kind)
        a('scope-'+kind,'owner','list','GET',route,fields=['name'])
        a('scope-'+kind,'household','list','GET',route,actor='second-user',fields=['name'])
        a('scope-'+kind,'household','read','GET',pathref(route+'/{i}',i=Ref(kind,'id')),actor='second-user',status=None)
        a('scope-'+kind,'group','read','GET',pathref(route+'/{i}',i=Ref(kind,'id')),actor='other-user',status=None)
        s.add('scope-'+kind,'household','delete',lambda c,r=route,k=kind:attempt(c,r+'/'+c.state[k]['id'],'second-user','DELETE'))


def attempt(c,path,actor,method):
    before,original=c.request('GET',path)
    assert before.status_code==200,'cross-scope target missing before mutation'
    r,p=c.request(method,path,actor,body={**original,'name':'Outsider changed'} if method=='PUT' else None)
    first=c.observe(r,p)
    after,owner=c.request('GET',path)
    assert after.status_code==200,'outsider removed protected target'
    return {'request':first,'owner':c.observe(after,owner,fields=['name'])}


def recipe_attempt(c,method):
    path='recipes/'+c.state['home-recipe']['id']
    r,original=c.request('GET',path);assert r.status_code==200
    r,p=c.request(method,path,'other-user',body={'description':'Outsider changed'} if method=='PATCH' else None)
    attempted=c.observe(r,p)
    r,p=c.request('GET',path);assert r.status_code==200
    return {'request':attempted,'owner':c.observe(r,p,fields=['name','description'])}
