from program import Builder,request
import base64,json
import media


def build():
    b=Builder('api-scanner-formats')
    b.setup.append({'id':'scan-input','kind':'scan-input'})
    b.get('unimported-book','/api/v1/books',where={'name':'Metadata'},fields=['metadata.title','metadata.summary'],want={'metadata':{'title':'Metadata','summary':''}})
    b.add('enable-comicinfo',{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}','PATCH',{'importComicInfoBook':True,'importComicInfoSeries':True}),request('/api/v1/libraries/${scanlib.id}/metadata/refresh','POST'),{'kind':'eventually','read':request('/api/v1/books',where={'name':'Metadata'},fields=['metadata'],want={'metadata':{'title':'Atlas chapter 1'}})}]})
    b.get('oneshot','/api/v1/series',where={'name':'Standalone'},fields=['name','oneshot','booksCount'],want={'oneshot':True,'booksCount':1})
    b.get('excluded-directory','/api/v1/books',catalog=True)
    b.add('include-pdf',{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}','PATCH',{'scanPdf':True}),request('/api/v1/libraries/${scanlib.id}/scan','POST',params={'deep':'true'}),{'kind':'eventually','read':request('/api/v1/books',where={'name':'Vector'},fields=['name','media'],want={'media':{'status':'READY','mediaProfile':'PDF'}})}]})
    b.add('include-epub',{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}','PATCH',{'scanEpub':True}),request('/api/v1/libraries/${scanlib.id}/scan','POST',params={'deep':'true'}),{'kind':'eventually','read':request('/api/v1/books',where={'name':'Journal'},fields=['metadata','media'],want={'media':{'status':'READY','mediaProfile':'EPUB'}})}]})
    b.add('include-skipped-directory',{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}','PATCH',{'scanDirectoryExclusions':[]}),request('/api/v1/libraries/${scanlib.id}/scan','POST',params={'deep':'true'}),{'kind':'eventually','read':request('/api/v1/books',where={'name':'Hidden'},fields=['name','metadata'],want={'media':{'status':'READY'},'metadata':{'title':'Beacon chapter 1'}})}]})
    b.add('convert-rar',{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}','PATCH',{'convertToCbz':True}),{'kind':'eventually','read':request('/api/v1/books',where={'name':'Archive'},fields=['media','url'],want={'media':{'mediaType':'application/zip'},'url':'/exchange/inbox/Scan/Normal/Archive.cbz'})}]})
    b.add('converted-archive',{'kind':'exchange-check','path':'/exchange/inbox/Scan/Normal','filename':'Archive.cbz','zip':True})
    metadata={'metadata':{'type':'comic','publisher':'Sidecar Press','name':'Mylar Title','comicid':'100','year':2024,'description_text':'Imported series description','volume':1,'booktype':'Print','comic_image':'','total_issues':7,'publication_run':'2024','status':'Ended'}}
    b.add('mylar-sidecar',{'kind':'file','action':{'op':'put_file','directory':'/exchange/inbox/Scan/Normal','filename':'series.json','base64':base64.b64encode(json.dumps(metadata).encode()).decode()},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}/scan','POST',params={'deep':'true'}),request('/api/v1/libraries/${scanlib.id}/metadata/refresh','POST'),{'kind':'eventually','read':request('/api/v1/series',where={'name':'Normal'},fields=['metadata.title','metadata.publisher','metadata.summary','metadata.totalBookCount'],want={'metadata':{'title':'Mylar Title','publisher':'Sidecar Press','totalBookCount':7}})}]}})
    b.add('sidecar-cover',{'kind':'file','action':{'op':'put_file','directory':'/exchange/inbox/Scan/Normal','filename':'cover.jpg','base64':base64.b64encode(media.png(3)).decode()},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${scanlib.id}/scan','POST',params={'deep':'true'}),request('/api/v1/libraries/${scanlib.id}/metadata/refresh','POST'),request('/api/v1/series',where={'name':'Normal'},save='normal',fields=['name']),{'kind':'eventually','read':request('/api/v1/series/${normal.id}/thumbnails',where={'type':'SIDECAR'},fields=['type','selected'],want={'selected':True})},request('/api/v1/series/${normal.id}/thumbnail',binary=True,image=True)]}})
    dependencies={'converted-archive':'convert-rar','enable-comicinfo':'unimported-book','include-skipped-directory':'enable-comicinfo'}
    for cp in b.cases:
        if cp['id'] in dependencies:cp['depends_on'].append(dependencies[cp['id']])
    return [b.build()]
