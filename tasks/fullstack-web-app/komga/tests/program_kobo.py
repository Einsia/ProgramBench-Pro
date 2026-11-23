from program import Builder,request


def build():
    b=Builder('api-kobo',library=True,formats=True)
    b.get('key','/api/v2/users/me/api-keys',method='POST',body={'comment':'Kobo local reader'},save='kobo',fields=['comment'])
    root='/kobo/${kobo.key}'
    b.get('ping',root+'/ping',auth=None)
    b.get('initialization',root+'/v1/initialization',auth=None,fields=['Resources.image_host','Resources.image_url_template','Resources.image_url_quality_template'])
    for name in ('b01','b21','books.Journal','books.Vector'):
        path=root+'/v1/library/${'+name+'.id}'
        b.get(name+'-metadata',path+'/metadata',auth=None,field='0',fields=['Title','Contributors','Language','Publisher','Series','DownloadUrls'])
        b.get(name+'-state',path+'/state',auth=None,field='0',fields=['StatusInfo.Status'])
        b.add(name+'-progress',{'kind':'mutation','write':request('/api/v1/books/${'+name+'.id}/read-progress','PATCH',{'completed':True}),'read':request(path+'/state',auth=None,field='0',fields=['StatusInfo.Status'])})
        b.get(name+'-download',root+'/v1/books/${'+name+'.id}/file/epub',auth=None,binary=True,bytes=True)
    b.get('missing-key','/kobo/invalid-key/ping',auth=None,status=[401,403])
    b.get('missing-book',root+'/v1/library/missing-book/metadata',auth=None,status=200,want=[])
    b.add('library-sync',{'kind':'kobo-sync','path':root+'/v1/library/sync'})
    b.get('clear-syncpoints','/api/v1/syncpoints/me',method='DELETE',params={'api_key_id':'${kobo.id}'})
    return [b.build()]
