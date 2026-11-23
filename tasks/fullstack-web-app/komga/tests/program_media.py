from program import Builder,request
import base64
import media


def build():
    b=Builder('api-media',library=True,formats=True)
    for key in ('b01','b12','b21','b33','b41','b52'):
        path='/api/v1/books/${'+key+'.id}'
        b.get(key+'-analysis',path,fields=['name','media','metadata'])
        b.get(key+'-pages',path+'/pages')
        b.get(key+'-download',path+'/file',binary=True,bytes=True)
        for n in (1,2,4):
            for suffix in ('','/thumbnail'):
                b.get(key+'-page-'+str(n)+suffix.replace('/','-'),path+'/pages/'+str(n)+suffix,binary=True,image=True)
        for n in (0,-1,5):b.get(key+'-bad-page-'+str(n),path+'/pages/'+str(n),status=[400,404])
        b.get(key+'-convert-jpeg',path+'/pages/2',params={'convert':'jpeg'},binary=True,image=True,encoding='JPEG')
        b.get(key+'-zero-based',path+'/pages/0',params={'zero_based':'true'},binary=True,image=True)
        b.get(key+'-poster',path+'/thumbnail',binary=True,image=True)
        b.get(key+'-webpub',path+'/manifest')
        b.get(key+'-divina',path+'/manifest/divina')
    for key in ('Journal','Vector','Archive'):
        path='/api/v1/books/${books.'+key+'.id}'
        b.get(key+'-metadata',path,fields=['media','metadata'])
        b.get(key+'-original',path+'/file',binary=True,bytes=True)
        b.get(key+'-manifest',path+'/manifest')
        b.get(key+'-poster',path+'/thumbnail',binary=True,image=True)
        b.get(key+'-pages',path+'/pages')
    b.get('epub-manifest','/api/v1/books/${books.Journal.id}/manifest/epub')
    b.get('epub-positions','/api/v1/books/${books.Journal.id}/positions')
    for resource in ['OEBPS/nav.xhtml','OEBPS/chapter1.xhtml','OEBPS/chapter2.xhtml','OEBPS/chapter3.xhtml']:
        import urllib.parse
        b.get('epub-resource-'+str(len(b.cases)),'/api/v1/books/${books.Journal.id}/resource/'+urllib.parse.quote(resource,safe='/'),binary=True,bytes=True)
    for n in (1,2):b.get('pdf-page-'+str(n),'/api/v1/books/${books.Vector.id}/pages/'+str(n),params={'convert':'png','contentNegotiation':'false'},binary=True,image=True)
    b.get('cbz-raw-unsupported','/api/v1/books/${b01.id}/pages/1/raw',status=400)
    for page in (1,2,4):b.get('rar-page-'+str(page),'/api/v1/books/${books.Archive.id}/pages/'+str(page),binary=True,image=True)
    b.get('pdf-manifest','/api/v1/books/${books.Vector.id}/manifest/pdf')
    for path,name in [('/api/v1/books/${b01.id}','book'),('/api/v1/series/${s0.id}','series')]:
        b.add(name+'-poster-upload',{'kind':'thumbnail','entity':name,'path':path})
        b.get(name+'-poster-list',path+'/thumbnails')
    return [b.build()]
