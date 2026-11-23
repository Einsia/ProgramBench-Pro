from program import Builder,request
from common import AUTH
import hashlib,base64
import media


def build():
    out=[]
    b=Builder('api-reader-protocols',library=True,formats=True)
    for series in ('s0','s2'):
        path='/api/v2/series/${'+series+'.id}/read-progress/tachiyomi'
        for n in (0,1,2.5,3):
            b.mutate(series+'-mihon-'+str(n),path,{'lastBookNumberSortRead':n},method='PUT')
            b.get(series+'-mihon-books-'+str(n),'/api/v1/series/${'+series+'.id}/books',catalog=True,item_fields=['name','readProgress'])
    for i,(href,percent) in enumerate([('OEBPS/chapter1.xhtml',.1),('OEBPS/chapter2.xhtml',.5),('OEBPS/chapter3.xhtml',.95)]):
        b.mutate('epub-progression-'+str(i),'/api/v1/books/${books.Journal.id}/progression',{'modified':'2050-01-0'+str(i+2)+'T00:00:00Z','device':{'id':'reader-one','name':'Test reader'},'locator':{'href':href,'type':'application/xhtml+xml','title':'Harbor '+str(i+1),'locations':{'progression':.25,'totalProgression':percent,'position':i+1}}},method='PUT')
    b.get('sync-key','/api/v2/users/me/api-keys',method='POST',body={'comment':'KOReader test'},save='kosync',fields=['comment'])
    headers={'X-Auth-User':'${kosync.key}'}
    b.get('koreader-auth','/koreader/users/auth',auth=None,headers=headers)
    for i,(series,num) in enumerate([(0,1),(2,2),(4,3)]):
        raw=media.cbz(series,num);h=hashlib.md5()
        for j in range(-1,11):
            offset=(1024<<((2*j)&63))&((1<<64)-1);h.update(raw[offset:offset+1024])
        digest=h.hexdigest()
        b.add('ko-'+str(i),{'kind':'mutation','eventual':True,'write':request('/api/v1/books/${b'+str(series)+str(num)+'.id}/read-progress','PATCH',{'page':2}),'read':request('/koreader/syncs/progress/'+digest,auth=None,headers=headers)})
        for page in (1,3,4):
            b.add('ko-'+str(i)+'-set-'+str(page),{'kind':'mutation','write':request('/koreader/syncs/progress','PUT',{'document':digest,'percentage':page/4,'progress':str(page),'device':'Offline reader','device_id':'reader-one'},auth=None,headers=headers),'read':request('/api/v1/books/${b'+str(series)+str(num)+'.id}',fields=['readProgress'])})
    b.get('ko-create-refused','/koreader/users/create',method='POST',auth=None,headers=headers,status=403)
    b.get('ko-missing','/koreader/syncs/progress/'+'0'*32,auth=None,headers=headers,status=404)
    b.add('progression-persistence',{'kind':'restart','read':request('/api/v1/books/${books.Journal.id}/progression')})
    out.append(b.build())
    b=Builder('api-maintenance',library=True)
    b.get('initial-book','/api/v1/books/${b01.id}',fields=['name','metadata.title','deleted'])
    b.add('locked-title-survives-import',{'kind':'compound','steps':[request('/api/v1/books/${b01.id}/metadata','PATCH',{'title':'Locked manual title','titleLock':True}),{'kind':'mutation','write':request('/api/v1/books/${b01.id}/metadata/refresh','POST'),'read':request('/api/v1/books/${b01.id}',fields=['metadata.title','metadata.titleLock'],want={'metadata':{'title':'Locked manual title','titleLock':True}}),'eventual':True}]})
    b.add('unlocked-title-reimport',{'kind':'compound','steps':[request('/api/v1/books/${b01.id}/metadata','PATCH',{'titleLock':False}),{'kind':'mutation','write':request('/api/v1/books/${b01.id}/metadata/refresh','POST'),'read':request('/api/v1/books/${b01.id}',fields=['metadata.title','metadata.titleLock'],want={'metadata':{'title':'Atlas chapter 1','titleLock':False}}),'eventual':True}]})
    for i,name in enumerate(('b01','b22','b53')):
        b.add(name+'-analysis',{'kind':'mutation','write':request('/api/v1/books/${'+name+'.id}/analyze','POST'),'read':request('/api/v1/books/${'+name+'.id}',fields=['media'],want={'media':{'status':'READY','pagesCount':4}}),'eventual':True})
    for name,path in [('book','/api/v1/books/${b02.id}'),('series','/api/v1/series/${s1.id}')]:
        b.add(name+'-delete-file',{'kind':'mutation','write':request(path+'/file','DELETE'),'read':request(path,fields=['deleted'],want={'deleted':True}),'eventual':True})
    b.get('known-page-hashes','/api/v1/page-hashes')
    b.get('unknown-page-hashes','/api/v1/page-hashes/unknown',params={'size':50},save='hashes')
    b.get('duplicate-matches','/api/v1/page-hashes/${hashes.content.0.hash}',catalog=True,
          item_fields=['bookId','fileName','pageNumber'],sort_normalized_items=True)
    b.get('duplicate-preview','/api/v1/page-hashes/unknown/${hashes.content.0.hash}/thumbnail',binary=True,image=True)
    b.mutate('classify-duplicate','/api/v1/page-hashes',{'hash':'${hashes.content.0.hash}','size':'${hashes.content.0.size}','action':'IGNORE'},method='PUT')
    b.get('known-preview','/api/v1/page-hashes/${hashes.content.0.hash}/thumbnail',binary=True,image=True)
    b.mutate('manual-duplicate-policy','/api/v1/page-hashes',{'hash':'${hashes.content.0.hash}','size':'${hashes.content.0.size}','action':'DELETE_MANUAL'},method='PUT')
    b.add('remove-duplicate-pages',{'kind':'mutation','eventual':True,'write':request('/api/v1/page-hashes/${hashes.content.0.hash}/delete-all','POST'),'read':request('/api/v1/page-hashes/${hashes.content.0.hash}',catalog=True,item_fields=['bookId','fileName','pageNumber'],want={'totalElements':0})})
    b.get('history','/api/v1/history',params={'size':100},fields=['totalElements'])
    b.get('clear-queue','/api/v1/tasks',method='DELETE')
    out.append(b.build())
    return out
