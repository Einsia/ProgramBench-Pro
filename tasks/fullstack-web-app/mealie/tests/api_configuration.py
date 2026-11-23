'''Offline provider configuration and ingredient substitutions.

Providers are stored and selected without contacting them. The credentials below are inert fixture strings.
Substitutions are exercised as food relationships and as recipe-local overrides, including clearing and persistence.
'''
from harness import Ref,pathref

MISSING='00000000-0000-4000-8000-000000000000'


def build(s):
    a=s.api
    fx='configuration-fixture'
    a(fx,'groups','home','GET','groups/self',save='home')
    a(fx,'groups','other','POST','admin/groups',body={'name':'Other'},save='other')
    a(fx,'users','member','POST','admin/users',body={'username':'member','fullName':'Member','email':'member@example.com','password':'MemberPass1','admin':False},
      before=lambda c:c.creds.update(member='MemberPass1'))
    base='groups/ai-providers'
    body={'name':'Local text service','model':'example-text','baseUrl':'http://example.invalid/v1','apiKey':'inert-fixture-key',
          'timeout':42,'requestHeaders':{'X-Example':'Kitchen'},'requestParams':{'format':'json'}}
    a('providers','create','full','POST',base+'/providers',body=body,status=200,save='provider')
    a('providers','create','defaults','POST',base+'/providers',body={'name':'Minimal','model':'example-model','apiKey':'inert-second-key'},status=200,save='minimal')
    a('providers','validation','empty-key','POST',base+'/providers',body={'name':'No key','model':'x'},status=400)
    for name,b in [('missing-name',{'model':'x'}),('missing-model',{'name':'x'}),('invalid-timeout',{**body,'timeout':'soon'}),('invalid-header',{**body,'requestHeaders':{'X-Number':2}})]:
        a('providers','validation',name,'POST',base+'/providers',body=b,status=422)
    path=pathref(base+'/providers/{id}',id=Ref('provider','id'))
    a('providers','read','stored','GET',path)
    a('providers','read','settings','GET',base+'/settings')
    a('providers','read','missing','GET',base+'/providers/'+MISSING,status=None)
    a('providers','read','malformed','GET',base+'/providers/not-a-uuid',status=422)
    a('providers','permission','anonymous','GET',path,actor=None,status=401)
    a('providers','permission','member-read','GET',path,actor='member',status=None)
    a('providers','permission','member-create','POST',base+'/providers',actor='member',body={'name':'Not allowed','model':'x'},status=None)
    a('providers','edit','update','PUT',path,body={**body,'name':'Updated service','model':'example-updated','apiKey':'','timeout':60})
    a('providers','edit','read-updated','GET',path)
    a('providers','settings','select','PUT',base+'/settings',body={'defaultProviderId':Ref('provider','id'),'audioProviderId':Ref('minimal','id'),'imageProviderId':Ref('provider','id')})
    a('providers','settings','enabled','GET',base+'/settings')
    a('providers','settings','missing-fields','PUT',base+'/settings',body={},status=422)
    a('providers','settings','bad-id','PUT',base+'/settings',body={'defaultProviderId':'bad','audioProviderId':None,'imageProviderId':None},status=422)
    a('providers','settings','clear','PUT',base+'/settings',body={'defaultProviderId':None,'audioProviderId':None,'imageProviderId':None})
    a('providers','settings','cleared','GET',base+'/settings')
    admin=pathref('admin/groups/{g}/ai-providers/providers',g=Ref('other','id'))
    a('providers-admin','create','other','POST',admin,body={'name':'Other group provider','model':'other-model','apiKey':'inert-other-key'},status=200,save='other-provider')
    otherpath=pathref('admin/groups/{g}/ai-providers/providers/{p}',g=Ref('other','id'),p=Ref('other-provider','id'))
    a('providers-admin','read','other','GET',otherpath)
    a('providers-admin','read','own-cannot-read-other','GET',pathref(base+'/providers/{p}',p=Ref('other-provider','id')),status=None)
    a('providers-admin','edit','update','PUT',otherpath,body={'name':'Other revised','model':'other-two','timeout':11})
    a('providers-admin','edit','read','GET',otherpath)
    a('providers-admin','permission','member','GET',otherpath,actor='member',status=403)
    a('providers-admin','delete','one','DELETE',otherpath)
    a('providers','delete','minimal','DELETE',pathref(base+'/providers/{p}',p=Ref('minimal','id')))
    a('providers','delete','one','DELETE',path)
    a('providers','delete','settings','GET',base+'/settings')

    a('substitutions','foods','butter','POST','foods',body={'name':'butter'},status=201,save='butter')
    a('substitutions','foods','oil','POST','foods',body={'name':'olive oil'},status=201,save='oil')
    food=pathref('foods/{id}',id=Ref('butter','id'))
    a('substitutions','food','link','PUT',food,body={'name':'butter','substitutions':[{'substituteFoodId':Ref('oil','id'),'note':'Use three quarters as much.'}]})
    a('substitutions','food','read','GET',food,fields=['name','substitutions'])
    a('substitutions','food','note-only','PUT',food,body={'name':'butter','substitutions':[{'note':'Skip for a lean dish.'}]})
    a('substitutions','food','read-note','GET',food,fields=['substitutions'])
    a('substitutions','food','bad-id','PUT',food,body={'name':'butter','substitutions':[{'substituteFoodId':'bad'}]},status=422)
    a('substitutions','recipe','create','POST','recipes',body={'name':'Butter Toast'},status=201)
    a('substitutions','recipe','override','PATCH','recipes/butter-toast',body={'recipeIngredient':[{'quantity':2,'food':Ref('butter'),
      'substitutions':[{'substituteFoodId':Ref('oil','id'),'note':'Recipe-specific alternative.'}]}]})
    a('substitutions','recipe','read','GET','recipes/butter-toast',fields=['recipeIngredient'])
    a('substitutions','food','clear','PUT',food,body={'name':'butter','substitutions':[]})
    a('substitutions','food','cleared','GET',food,fields=['substitutions'])
    a('substitutions','recipe','independent','GET','recipes/butter-toast',fields=['recipeIngredient'])
