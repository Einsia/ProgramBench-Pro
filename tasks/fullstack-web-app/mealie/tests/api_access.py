'''Each permission operation uses a real target owned by the baseline household.

Mutations include an owner read before and after the request. Each actor has a separate target, so no earlier
actor can remove a later actor's object. Lists use valid resource-specific sort keys.
'''
from harness import Ref,pathref,resolve

ACTORS=[None,'erin','dave','frank','admin']
USERS={
 'dave':{'username':'dave','fullName':'Dave Dunn','email':'dave@example.com','password':'DavePassword1','admin':False,'household':'Second','group':'Home'},
 'erin':{'username':'erin','fullName':'Erin Ellis','email':'erin@example.com','password':'ErinPassword1','admin':False,'canOrganize':False,'canManage':False,'canInvite':False},
 'frank':{'username':'frank','fullName':'Frank Fox','email':'frank@example.com','password':'FrankPassword1','admin':False,'canOrganize':True,'canManage':True,'canInvite':True,'canManageHousehold':True},
}
KINDS={'tags':'organizers/tags','categories':'organizers/categories','tools':'organizers/tools','foods':'foods','units':'units',
       'labels':'groups/labels','recipes':'recipes','shopping-lists':'households/shopping/lists','cookbooks':'households/cookbooks',
       'mealplans':'households/mealplans','comments':'comments'}


def body(kind,name):
    if kind=='mealplans':return {'date':'2026-12-02','entryType':'dinner','title':name}
    if kind=='comments':return lambda c:{'recipeId':c.state['anchor']['id'],'text':name}
    if kind=='labels':return {'name':name,'color':'#336699'}
    return {'name':name}


def mutate(c,kind,target,actor,delete=False):
    route=KINDS[kind]+'/'+str(c.state[target]['slug' if kind=='recipes' else 'id'])
    before,p=c.request('GET',route)
    assert before.status_code==200,'permission target must exist before the tested operation'
    if delete:
        r,result=c.request('DELETE',route,actor)
    else:
        field='description' if kind=='recipes' else 'text' if kind=='comments' else 'title' if kind=='mealplans' else 'name'
        change={**p,field:'Changed by '+(actor or 'anonymous')}
        r,result=c.request('PATCH' if kind=='recipes' else 'PUT',route,actor,body=change)
    request=c.observe(r,result)
    after,state=c.request('GET',route)
    assert after.status_code in (200,404),'owner read failed unexpectedly'
    fields=['slug','description'] if kind=='recipes' else ['text'] if kind=='comments' else ['title'] if kind=='mealplans' else ['name']
    return {'request':request,'owner_after':c.observe(after,state,fields=fields)}


def build(s):
    a=s.api;fx='access-fixture'
    a(fx,'members','group','GET','groups/self',save='group')
    a(fx,'members','second-household','POST','admin/households',body=lambda c:{'name':'Second','groupId':c.state['group']['id']})
    for name,b in USERS.items():
        a(fx,'members',name,'POST','admin/users',body=b,before=lambda c,n=name,p=b['password']:c.creds.update({n:p}))
    a(fx,'comments','anchor','POST','recipes',body={'name':'Comment Anchor'})
    a(fx,'comments','anchor-read','GET','recipes/comment-anchor',save='anchor')
    for kind,route in KINDS.items():
        fam='access-'+kind
        targets={}
        for actor in ACTORS:
            who=actor or 'anonymous';key=kind+'-'+who;targets[who]=key
            name=kind+' target '+who
            a(fx,kind,who,'POST',route,body=body(kind,name),save=key if kind!='recipes' else None)
            if kind=='recipes':a(fx,kind,who+'-read','GET','recipes/recipes-target-'+who,save=key)
        order='createdAt' if kind=='comments' else 'date' if kind=='mealplans' else 'name'
        for actor in ACTORS:
            who=actor or 'anonymous';target=targets[who]
            a(fam,'list',who,'GET',route,actor=actor,params={'orderBy':order},status=None)
        for actor in ACTORS:
            who=actor or 'anonymous';target=targets[who]
            a(fam,'read',who,'GET',pathref(route+'/{id}',id=Ref(target,'slug' if kind=='recipes' else 'id')),actor=actor,status=None)
        for actor in ACTORS:
            who=actor or 'anonymous'
            a(fam,'create',who,'POST',route,actor=actor,body=body(kind,kind+' created '+who),status=None)
        for delete in [False,True]:
            for actor in ACTORS:
                if kind=='comments' and actor not in (None,'admin'):continue  # upstream member-comment mutation raises 500
                who=actor or 'anonymous';target=targets[who]
                s.add(fam,'delete' if delete else 'change',who,
                      lambda c,k=kind,t=target,u=actor,d=delete:mutate(c,k,t,u,d),
                      description=('Delete' if delete else 'Change')+' a real '+kind+' target as '+who+'; verify owner state.')
