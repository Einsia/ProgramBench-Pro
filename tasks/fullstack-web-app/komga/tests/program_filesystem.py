from program import Builder,request
import base64
import media


def build():
    b=Builder('api-file-episodes',library=True)
    b.setup.append({'id':'import-files','kind':'import-files'})
    b.get('transient-scan','/api/v1/transient-books',method='POST',body={'path':'/exchange/inbox/Incoming'},save='transient')
    b.get('transient-analyze','/api/v1/transient-books/${transient.0.id}/analyze',method='POST',save='analyzed')
    for page in (1,2,4):b.get('transient-page-'+str(page),'/api/v1/transient-books/${transient.0.id}/pages/'+str(page),binary=True,image=True)
    b.add('import-copy',{'kind':'compound','steps':[request('/api/v1/books/import','POST',{'copyMode':'COPY','books':[{'sourceFile':'/exchange/inbox/Incoming/Incoming.cbz','seriesId':'${s0.id}','destinationName':'Imported'}]}),{'kind':'eventually','read':request('/api/v1/series/${s0.id}/books',catalog=True,want={'totalElements':4})}]})
    b.add('copied-input-remains',{'kind':'exchange-check','path':'/exchange/inbox/Incoming','filename':'Incoming.cbz'})
    b.get('imported-book','/api/v1/series/${s0.id}/books',where={'name':'Imported'},fields=['name','media','metadata'],save='imported')
    b.add('imported-file-roundtrip',request('/api/v1/books/${imported.id}/file',binary=True,bytes=True))
    b.add('remove-input',{'kind':'file','action':{'op':'remove_file','directory':'/exchange/inbox/Comics/Atlas','filename':'Atlas-03.cbz'},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${lib.id}/scan','POST'),{'kind':'eventually','read':request('/api/v1/books/${b03.id}',fields=['deleted'],want={'deleted':True})}]}})
    b.add('restore-input',{'kind':'file','action':{'op':'put_file','directory':'/exchange/inbox/Comics/Atlas','filename':'Atlas-03.cbz','base64':base64.b64encode(media.cbz(0,3)).decode()},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${lib.id}/scan','POST'),{'kind':'eventually','read':request('/api/v1/books',params={'unpaged':'true'},where={'name':'Atlas-03'},fields=['deleted','metadata.title'],want={'deleted':False})}]}})
    b.add('invalid-archive-analysis',{'kind':'file','action':{'op':'put_file','directory':'/exchange/inbox/Comics/Errors','filename':'Broken.cbz','base64':base64.b64encode(b'broken archive').decode()},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${lib.id}/scan','POST'),{'kind':'eventually','read':request('/api/v1/books',params={'unpaged':'true'},where={'name':'Broken'},fields=['name','media'],want={'media':{'status':'UNSUPPORTED'}})}]}})
    b.add('extension-repair',{'kind':'file','action':{'op':'put_file','directory':'/exchange/inbox/Comics/Repair','filename':'Wrong.pdf','base64':base64.b64encode(media.cbz(4,1)).decode()},'read':{'kind':'compound','steps':[request('/api/v1/libraries/${lib.id}/scan','POST'),{'kind':'eventually','read':request('/api/v1/books',params={'unpaged':'true'},where={'name':'Wrong'},fields=['name','media.mediaType'],want={'media':{'status':'READY'}})},request('/api/v1/libraries/${lib.id}','PATCH',{'repairExtensions':True}),{'kind':'eventually','read':request('/api/v1/books',params={'unpaged':'true'},where={'name':'Wrong'},fields=['media.mediaType','url'],want={'media':{'mediaType':'application/zip'},'url':'/exchange/inbox/Comics/Repair/Wrong.cbz'})}]}})
    b.add('repaired-file-present',{'kind':'exchange-check','path':'/exchange/inbox/Comics/Repair','filename':'Wrong.cbz'})
    dependencies={'copied-input-remains':'import-copy','imported-book':'import-copy','restore-input':'remove-input','repaired-file-present':'extension-repair'}
    for cp in b.cases:
        if cp['id'] in dependencies:cp['depends_on'].append(dependencies[cp['id']])
    return [b.build()]
