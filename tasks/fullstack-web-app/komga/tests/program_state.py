from program import Builder,request
from common import AUTH,READER


def build():
    out=[]
    b=Builder('api-settings')
    b.get('settings','/api/v1/settings',fields=['deleteEmptyCollections','deleteEmptyReadLists','rememberMeDurationDays','thumbnailSize','taskPoolSize'])
    for field,values in {'deleteEmptyCollections':[False,True],'deleteEmptyReadLists':[False,True],'rememberMeDurationDays':[1,30,365],'thumbnailSize':['MEDIUM','LARGE','XLARGE','DEFAULT'],'taskPoolSize':[1,3,2],'nextUiAsDefault':[True,False]}.items():
        for i,v in enumerate(values):b.mutate(field+'-'+str(i),'/api/v1/settings',{field:v},fields=[field])
    for scope in ('global','user'):
        path='/api/v1/client-settings/'+scope
        for i,value in enumerate(['plain value','{"zoom":1.5,"rtl":true}','中文 café\nline two','']):
            key='reader.layout.value'+str(i)
            body={key:{'value':value,'allowUnauthorized':i%2==0}} if scope=='global' else {key:{'value':value}}
            b.mutate(scope+'-store-'+str(i),path,body,path+'/list')
            if value=='':b.cases[-1]['spec']['write']['status']=400
        b.get(scope+'-anonymous',path+'/list',auth=None,status=200 if scope=='global' else 401)
        for i in range(4):b.mutate(scope+'-delete-'+str(i),path,['reader.layout.value'+str(i)],path+'/list',method='DELETE')
        for i,key in enumerate(['Bad.Key','single','bad key','bad..key','reader.','']):
            body={key:{'value':'invalid'}} if scope=='global' else {key:{'value':'invalid'}}
            b.get(scope+'-invalid-'+str(i),path,method='PATCH',body=body,status=[204,400])
    b.add('settings-persistence',{'kind':'restart','compare_before':True,'read':request('/api/v1/settings',fields=['thumbnailSize','taskPoolSize','rememberMeDurationDays'])})
    out.append(b.build())
    b=Builder('api-reading',library=True)
    b.setup.append({'id':'reader','kind':'reader'})
    for book in ('b01','b02','b21','b51'):
        path='/api/v1/books/${'+book+'.id}'
        for i,body in enumerate([{'page':1},{'page':2},{'page':4},{'completed':True},{'completed':False,'page':3}]):
            b.add(book+'-progress-'+str(i),{'kind':'mutation','write':request(path+'/read-progress','PATCH',body,auth=READER),'read':request(path,auth=READER,fields=['readProgress'])})
            b.get(book+'-admin-independent-'+str(i),path,fields=['readProgress'])
        b.add(book+'-unread',{'kind':'mutation','write':request(path+'/read-progress','DELETE',auth=READER),'read':request(path,auth=READER,fields=['readProgress'])})
        for i,body in enumerate([{'page':0},{'page':-1},{'page':5},{'page':2.5},{}]):b.get(book+'-invalid-'+str(i),path+'/read-progress',method='PATCH',body=body,auth=READER,status=[204,400])
    for s in ('s0','s2','s5'):
        path='/api/v1/series/${'+s+'.id}'
        for method in ('POST','DELETE'):
            b.add(s+'-whole-'+method,{'kind':'mutation','write':request(path+'/read-progress',method,auth=READER),'read':request(path,auth=READER,fields=['booksReadCount','booksUnreadCount','booksInProgressCount'])})
            b.get(s+'-books-'+method,path+'/books',auth=READER,catalog=True,item_fields=['name','readProgress'])
            b.cases[-1]['depends_on'].append(s+'-whole-'+method)
    for book in ('b01','b02','b03'):
        for direction in ('next','previous'):
            b.get(book+'-'+direction,'/api/v1/books/${'+book+'.id}/'+direction,status=[200,404],**{'fields':['name','metadata.number']})
    b.add('progress-persists',{'kind':'compound','steps':[request('/api/v1/books/${b02.id}/read-progress','PATCH',{'page':2},auth=READER),{'kind':'restart','read':request('/api/v1/books/${b02.id}',auth=READER,fields=['readProgress'])}]})
    out.append(b.build())
    b=Builder('api-libraries')
    b.setup.append({'id':'library','kind':'library-config'})
    b.get('library-details','/api/v1/libraries/${lib.id}')
    flags=['importComicInfoBook','importComicInfoSeries','importComicInfoCollection','importComicInfoReadList','importComicInfoSeriesAppendVolume','importEpubBook','importEpubSeries','importMylarSeries','importLocalArtwork','importBarcodeIsbn','scanForceModifiedTime','scanOnStartup','scanCbx','scanPdf','scanEpub','repairExtensions','convertToCbz','emptyTrashAfterScan','hashFiles','hashPages','hashKoreader','analyzeDimensions']
    for flag in flags:
        for v in (False,True):b.mutate(flag+'-'+str(v),'/api/v1/libraries/${lib.id}',{flag:v},fields=[flag,'name'])
    for field,values in {'name':['Library café Ω','Comics'],'seriesCover':['FIRST','FIRST_UNREAD_OR_FIRST','FIRST_UNREAD_OR_LAST','LAST'],'scanInterval':['DAILY','WEEKLY','DISABLED'],'scanDirectoryExclusions':[['.hidden','skip'],[]],'oneshotsDirectory':['OneShots',None]}.items():
        for i,v in enumerate(values):b.mutate(field+'-'+str(i),'/api/v1/libraries/${lib.id}',{field:v},fields=[field])
    for name in ('','   '):b.get('bad-name-'+str(len(b.cases)),'/api/v1/libraries',method='POST',body={'name':name,'root':'/exchange/inbox'},status=400)
    b.get('overlapping-root','/api/v1/libraries',method='POST',body={'name':'Overlap','root':'/exchange/inbox/Comics/Atlas'},status=400)
    b.get('missing-root','/api/v1/libraries',method='POST',body={'name':'Missing','root':'/exchange/inbox/absent'},status=400)
    for action in ('scan','analyze','metadata/refresh','empty-trash'):
        b.get('maintenance-'+action.replace('/','-'),'/api/v1/libraries/${lib.id}/'+action,method='POST')
    b.get('filesystem','/api/v1/filesystem',method='POST',body={'path':'/exchange/inbox/Comics','showFiles':True})
    b.add('library-persistence',{'kind':'restart','compare_before':True,'read':request('/api/v1/libraries/${lib.id}')})
    b.get('delete-library','/api/v1/libraries/${lib.id}',method='DELETE')
    b.get('deleted-library','/api/v1/libraries/${lib.id}',status=404)
    b.cases[-1]['depends_on'].append('delete-library')
    b.add('files-retained-after-library-delete',{'kind':'exchange-check','path':'/exchange/inbox/Comics/Atlas','filename':'Atlas-01.cbz'},depends=['delete-library'])
    out.append(b.build())
    return out
