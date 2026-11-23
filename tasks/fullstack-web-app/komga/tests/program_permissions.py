from program import Builder,request
from common import AUTH

PROFILES=[('viewer',{'roles':[]}),('stream',{'roles':['PAGE_STREAMING']}),('download',{'roles':['FILE_DOWNLOAD']}),('full',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD']}),('library-none',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'sharedLibraries':{'all':False,'libraryIds':[]}}),('library-one',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'sharedLibraries':{'all':False,'libraryIds':['${lib.id}']}}),('young',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'ageRestriction':{'age':12,'restriction':'ALLOW_ONLY'}}),('adult',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'ageRestriction':{'age':12,'restriction':'EXCLUDE'}}),('allow-label',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'labelsAllow':['family']}),('exclude-label',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'labelsExclude':['adult']}),('combined',{'roles':['PAGE_STREAMING','FILE_DOWNLOAD'],'labelsAllow':['family'],'ageRestriction':{'age':10,'restriction':'ALLOW_ONLY'}})]


def build():
    b=Builder('api-permissions',library=True)
    b.setup.extend([{'id':'search-state','kind':'search-state'},{'id':'other-library','kind':'other-library'}])
    b.get('positive-admin-catalog','/api/v1/books',catalog=True)
    for name,options in PROFILES:
        b.setup.append({'id':'profile-'+name,'kind':'permission-user','name':name,'options':options})
        first=len(b.cases)
        auth=[name+'@example.test','Reader-Local-2026!']
        for label,path in [('libraries','/api/v1/libraries'),('books','/api/v1/books'),('series','/api/v1/series'),('collections','/api/v1/collections'),('readlists','/api/v1/readlists')]:
            b.get(name+'-'+label,path,auth=auth,**({'catalog':True} if label!='libraries' else {}))
        for i,key in enumerate(('b01','b11','b21','b31','otherbook')):
            path='/api/v1/books/${'+key+'.id}'
            for suffix,kw in [('',{'fields':['name','metadata','media']}),('/pages',{}),('/pages/1',{'binary':True,'image':True}),('/file',{'binary':True,'bytes':True}),('/thumbnail',{'binary':True,'image':True}),('/manifest',{})]:
                b.get(name+'-'+key+'-'+(suffix.replace('/','-') or 'detail'),path+suffix,auth=auth,status=[200,401,403,404],**kw)
        for suffix in ('','/books','/collections'):
            b.get(name+'-series-'+(suffix.strip('/') or 'detail'),'/api/v1/series/${s0.id}'+suffix,auth=auth,status=[200,403,404])
        b.get(name+'-metadata-denied','/api/v1/books/${b01.id}/metadata',method='PATCH',body={'title':'Forbidden replacement'},auth=auth,status=403)
        b.get(name+'-user-admin-denied','/api/v2/users',auth=auth,status=403)
        b.get(name+'-library-admin-denied','/api/v1/libraries/${lib.id}',method='PATCH',body={'name':'Forbidden rename'},auth=auth,status=403)
        b.get(name+'-settings-admin-denied','/api/v1/settings',method='PATCH',body={'thumbnailSize':'LARGE'},auth=auth,status=403)
        for cp in b.cases[first:]:cp['depends_on']=['setup:'+x for x in ('account','library','search-state','other-library','profile-'+name)]
    b.get('unchanged-title','/api/v1/books/${b01.id}',fields=['metadata.title'],want={'metadata':{'title':'Atlas chapter 1'}})
    b.get('unchanged-library','/api/v1/libraries/${lib.id}',fields=['name'],want={'name':'Comics'})
    for cp in b.cases[-2:]:cp['depends_on']=['setup:account','setup:library','setup:search-state']
    for cp in b.cases[1:]:cp['assertions'][0]['requires']=[b.key+'/positive-admin-catalog/result']
    return [b.build()]
