"""Komga hooks: all setup, checks and recipes use documented runtime channels."""
from evaluation.driver import Hooks as Base
from common import Product,AUTH,READER,subset
import media,program


def setup(p,item):
    kind=item['kind']
    if kind=='account':p.claim()
    elif kind=='library':p.library(rich=item.get('rich',True),formats=item.get('formats',False))
    elif kind in {'search-population','comicrack','extra-lists','reader-pages'}:
        import repair_fixtures
        getattr(repair_fixtures,kind.replace('-','_'))(p)
    elif kind=='duplicate-hash':
        p.wait(lambda:p.ok('/api/v1/page-hashes/unknown',params={'size':100})['totalElements']>0,'page hashing')
        rows=p.ok('/api/v1/page-hashes/unknown',params={'size':100})['content']
        for row in rows:
            matches=p.ok('/api/v1/page-hashes/'+row['hash'],params={'size':100})['content']
            if any(x['bookId']==p.state['b01']['id'] for x in matches):p.state['duplicate-hash']=row['hash'];break
        assert 'duplicate-hash' in p.state,'shared page missing'
    elif kind=='library-config':
        p.put('/exchange/inbox/Comics/Atlas','Atlas-01.cbz',media.cbz())
        p.state['lib']=p.ok('/api/v1/libraries','POST',{'name':'Comics','root':'/exchange/inbox/Comics','scanInterval':'DISABLED'})
        p.alias(p.state['lib']['id'],'library:Comics')
    elif kind=='reader':
        p.state['reader']=p.ok('/api/v2/users','POST',{'email':READER[0],'password':READER[1],'roles':['PAGE_STREAMING','FILE_DOWNLOAD']})
    elif kind=='search-state':
        for i in range(6):
            p.ok('/api/v1/series/${s'+str(i)+'.id}/metadata','PATCH',{'status':['ENDED','HIATUS','ABANDONED','ONGOING','ENDED','ONGOING'][i],'tags':['alpha'] if i%2==0 else ['beta'],'sharingLabels':['family'] if i<3 else ['adult']})
            p.ok('/api/v1/books/${b'+str(i)+'1.id}/metadata','PATCH',{'notableEntities':[{'name':'Captain Star' if i%2==0 else 'River Port','kind':'character' if i%2==0 else 'location'}]})
        p.ok('/api/v1/books/${b01.id}/read-progress','PATCH',{'completed':True})
        p.ok('/api/v1/books/${b11.id}/read-progress','PATCH',{'page':2})
    elif kind=='scan-input':
        p.put('/exchange/inbox/Scan/Normal','Metadata.cbz',media.cbz())
        p.put('/exchange/inbox/Scan/Normal','Archive.cbr',media.rar())
        p.put('/exchange/inbox/Scan/Normal','Vector.pdf',media.pdf())
        p.put('/exchange/inbox/Scan/Normal','Journal.epub',media.epub())
        p.put('/exchange/inbox/Scan/OneShots','Standalone.cbz',media.cbz(3,1))
        p.put('/exchange/inbox/Scan/Skip','Hidden.cbz',media.cbz(1,1))
        p.state['scanlib']=p.ok('/api/v1/libraries','POST',{'name':'Scanner','root':'/exchange/inbox/Scan','scanInterval':'DISABLED','scanPdf':False,'scanEpub':False,'importComicInfoBook':False,'importComicInfoSeries':False,'oneshotsDirectory':'OneShots','scanDirectoryExclusions':['Skip']})
        p.alias(p.state['scanlib']['id'],'library:Scanner')
        p.wait(lambda:len(p.ok('/api/v1/books',params={'unpaged':'true'})['content'])==3,'selective scanning')
        p.wait(lambda:all(x['media']['status']=='READY' for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']),'scanner analysis')
        p.discover()
    elif kind=='list-identities':
        p.ok('/api/v1/collections',params={'unpaged':'true'})
        p.ok('/api/v1/readlists',params={'unpaged':'true'})
    elif kind=='other-library':
        p.put('/exchange/inbox/Restricted/Night','Night.cbz',media.cbz(5,1))
        p.state['otherlib']=p.ok('/api/v1/libraries','POST',{'name':'Restricted Shelf','root':'/exchange/inbox/Restricted','scanInterval':'DISABLED'})
        p.wait(lambda:any(x['name']=='Night' and x['media']['status']=='READY' for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']),'second library')
        p.state['otherbook']=next(x for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content'] if x['name']=='Night')
    elif kind=='permission-user':
        p.ok('/api/v2/users','POST',{'email':item['name']+'@example.test','password':'Reader-Local-2026!',**p.resolve(item['options'])})
    elif kind=='request':program.response(p,item['request'])
    elif kind=='bad-media':
        p.put('/exchange/inbox/Comics/Errors','Broken.cbz',b'not a valid comic archive')
        p.put('/exchange/inbox/Comics/Copies','Copy.cbz',media.cbz())
        p.ok('/api/v1/libraries/${lib.id}/scan','POST')
        p.wait(lambda:any(x['name']=='Broken' and x['media']['status']=='UNSUPPORTED' for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']),'corrupt media analysis')
        p.wait(lambda:p.ok('/api/v1/books/duplicates')['totalElements']>0,'duplicate file hashing')
        p.discover()
        p.ok('/api/v1/books/${b03.id}/file','DELETE')
        p.wait(lambda:p.ok('/api/v1/history')['totalElements']>0,'history event')
    elif kind=='import-files':
        p.put('/exchange/inbox/Incoming','Incoming.cbz',media.cbz(5,3))
    elif kind=='stage-library':
        p.put('/exchange/inbox/NewShelf/Atlas','Atlas-01.cbz',media.cbz())
    elif kind=='empty-directory':p.broker.call({'op':'mkdir','directory':item['path']})
    else:raise ValueError('Unknown setup '+kind)


class Hooks(Base):
    def start(self,ctx):ctx.state['product']=Product(ctx.broker)
    def inputs(self,ctx):
        if ctx.episode.get('input_cbl'):
            from gui_account_import import CBL
            (ctx.inputs/'read-order.cbl').write_bytes(CBL)
    def setup(self,ctx,item):setup(ctx.state['product'],item)
    def recipe(self,ctx,checkpoint):
        from reference.recipes import execute
        execute(ctx,ctx.state['product'],checkpoint)
    def check(self,ctx,checkpoint,assertion):
        return program.execute(ctx.state['product'],assertion.get('spec',checkpoint.get('spec')))
    def judge(self,ctx,checkpoint,assertion,actual,expected):
        compare_observation(actual,expected)


UNORDERED={'authors','genres','tags','subject','sharingLabels','roles','labelsAllow','labelsExclude',
           'sharedLibrariesIds','notableEntities','alternateTitles','links','publications','navigation','groups',
           'contributor','author','penciler','translator','Contributors','ContributorRoles'}


def compare_observation(a,b,key='',unordered=False):
    """Match semantic set members recursively, allowing extra descriptive object fields."""
    key=key.rsplit('.',1)[-1]
    if isinstance(b,dict) and isinstance(b.get('image'),dict) and 'size' in b['image']:
        assert isinstance(a,dict) and isinstance(a.get('image'),dict),'image projection missing'
        x,y=a['image'],b['image'];assert x['size']==y['size'],'image dimensions differ'
        if 'format' in y:assert x.get('format')==y['format'],'image encoding differs'
        if 'media_type' in y:assert x.get('media_type')==y['media_type'],'image media type differs'
        xs,ys=x.get('pixels'),y.get('pixels');assert isinstance(xs,list) and len(xs)==len(ys),'image grid differs'
        errors=[abs(u-v) for p,q in zip(xs,ys) for u,v in zip(p,q)]
        assert sum(errors)/len(errors)<=7 and sum(v>35 for v in errors)/len(errors)<=.035,'image structure/content differs'
        assert a['status']==b['status'];return
    if isinstance(b,dict):
        assert isinstance(a,dict),'expected object'
        if not b or any('.' in k for k in b):assert a.keys()==b.keys(),'data map keys differ'
        for k,v in b.items():
            assert k in a,'missing '+k
            member_set=k in {'seriesIds','bookIds'} and b.get('ordered') is False
            compare_observation(a[k],v,k,member_set)
    elif isinstance(b,list):
        assert isinstance(a,list) and len(a)==len(b),'list differs'
        if key in UNORDERED or unordered:
            remaining=list(a)
            for wanted in b:
                for i,candidate in enumerate(remaining):
                    try:compare_observation(candidate,wanted,key)
                    except AssertionError:continue
                    remaining.pop(i);break
                else:raise AssertionError('unordered member differs: '+str(wanted)[:180])
        else:
            for x,y in zip(a,b):compare_observation(x,y,key)
    else:subset(a,b)
