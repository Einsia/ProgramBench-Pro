"""Small independent fixtures for protocol and reader coverage."""
import base64,json,time
import media
from common import AUTH,READER


def search_population(p):
    for name,n in [('Aster',1),('Zebra',2),('Lumen',4)]:
        for i in range(n):p.put('/exchange/inbox/Comics/'+name,f'{name}-{i+1}.cbz',media.cbz(3,i+1,metadata=False))
    p.put('/exchange/inbox/Comics/OneShots','Solo.cbz',media.cbz(4,1,metadata=False))
    p.put('/exchange/inbox/Comics/Formats','Paper.pdf',media.pdf())
    p.put('/exchange/inbox/Comics/Formats','Novel.epub',media.epub())
    p.put('/exchange/inbox/Comics/Corrupt','Bad.cbz',media.archive([('001.png',b'invalid PNG data')]))
    p.put('/exchange/inbox/Comics/Deleted','Vanished.cbz',media.cbz(5,1,metadata=False))
    p.ok('/api/v1/libraries/${lib.id}','PATCH',{'oneshotsDirectory':'OneShots'})
    p.ok('/api/v1/libraries/${lib.id}/scan','POST',params={'deep':'true'})
    p.wait(lambda:len(p.ok('/api/v1/books',params={'unpaged':'true'})['content'])==30,'mixed scanner fixture')
    p.wait(lambda:all(x['media']['status'] not in ['UNKNOWN','OUTDATED'] for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']),'mixed fixture analysis')
    p.discover()
    p.ok('/api/v1/books/${books.Vanished.id}/file','DELETE')
    p.wait(lambda:p.ok('/api/v1/books/${books.Vanished.id}')['deleted'],'fixture deletion')
    for path in ['/api/v1/books/${b32.id}/metadata','/api/v1/series/${s3.id}/metadata']:
        p.ok(path,'PATCH',{'tags':[]})
    p.ok('/api/v1/series/${s3.id}/metadata','PATCH',{'genres':[],'ageRating':None,'sharingLabels':[]})
    p.ok('/api/v1/books/${b02.id}/thumbnails','POST',params={'selected':'true'},multipart={'files':{'file':{'filename':'cover.png','base64':base64.b64encode(media.png(4)).decode(),'mime_type':'image/png'}}})
    # Let the async index settle, but never make correctness a setup prerequisite.
    time.sleep(2.5)


def comicrack(p):
    # Explicit current metadata rather than relying on a previous provider's changes.
    p.ok('/api/v1/series/${s0.id}/metadata','PATCH',{'title':'Atlas','titleLock':True})
    p.ok('/api/v1/books/${b01.id}/metadata','PATCH',{'number':'1','numberSort':1,'releaseDate':'2020-01-15'})


def extra_lists(p):
    p.state['shelf']=p.ok('/api/v1/collections','POST',{'name':'Cover shelf','ordered':True,'seriesIds':p.resolve(['${s0.id}','${s1.id}'])})
    p.state['queue']=p.ok('/api/v1/readlists','POST',{'name':'Mixed sequence','summary':'Reader queue','ordered':True,'bookIds':p.resolve(['${b21.id}','${b03.id}','${b11.id}','${b02.id}'])})
    for key in ['shelf','queue']:p.alias(p.state[key]['id'],'fixture:'+key)


def reader_pages(p):
    # Page widths and colored markers distinguish direction, double-page and fit modes.
    pages=[(f'{i:03}.png',media.png(i-1,i,width=600 if i==3 else 360,height=480 if i!=4 else 850)) for i in range(1,7)]
    p.put('/exchange/inbox/Reader/Directions','Modes.cbz',media.archive(pages))
    p.state['readerlib']=p.ok('/api/v1/libraries','POST',{'name':'Reader Lab','root':'/exchange/inbox/Reader','scanInterval':'DISABLED'})
    p.wait(lambda:any(x['name']=='Modes' and x['media']['status']=='READY' for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']),'reader pages')
    p.discover();p.state['modebook']=p.state['books']['Modes']
