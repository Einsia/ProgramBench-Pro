"""Additional public behavior checks with explicit positive relationships."""
import base64,hashlib,io,json,time,zipfile
from common import AUTH,READER,subset
import media


def observe(p,path,**kw):
    from program import response,projected,request
    spec=request(path,**kw);return projected(p,response(p,spec),spec)


def pixels(p,path):return observe(p,path,binary=True,image=True)


def blob(p,path):
    r=p.call(path,binary=True);assert r['status']==200
    return base64.b64decode(r['body_base64'])


def zip_members(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:return {i.filename:hashlib.sha256(z.read(i)).hexdigest() for i in z.infolist() if not i.is_dir()}


def execute(p,s):
    family=s['family'];action=s['action']
    if family=='page-poster':
        from hooks import compare_observation
        expected=pixels(p,'/api/v1/books/${b01.id}/pages/2/thumbnail')
        actual=pixels(p,s['path']);scaled={**expected,'image':{**expected['image'],'size':actual['image']['size']}};compare_observation(actual,scaled)
        return {'selected_page_matches':True,'poster':actual}
    if family=='reader-progress':
        row=p.ok('/api/v1/books/${modebook.id}');page=(row.get('readProgress') or {}).get('page',0)
        assert s['minimum']<=page<=row['media']['pagesCount'],'reader did not reach final pages'
        return {'at_end':True}
    if family=='posters':
        root=p.resolve(s['path'])
        if action.startswith('upload-'):
            which=action[-1];r=p.ok(root+'/thumbnails','POST',params={'selected':'true' if which=='a' else 'false'},multipart={'files':{'file':{'filename':'poster-'+which+'.png','base64':base64.b64encode(media.png(4 if which=='a' else 2)).decode(),'mime_type':'image/png'}}})
            p.state['cover-'+which]=r;p.alias(r['id'],'cover:'+which)
            listed=p.ok(root+'/thumbnails');matches=[x for x in listed if x['id']==r['id']]
            assert len(matches)==1 and matches[0]['type']=='USER_UPLOADED'
            return {'type':matches[0]['type'],'selected':matches[0]['selected'],'direct':pixels(p,root+'/thumbnails/'+r['id'])}
        if action in ['select-a','select-b']:
            which=action[-1];identity=p.state['cover-'+which]['id'];p.ok(root+'/thumbnails/'+identity+'/selected','PUT')
            rows=p.ok(root+'/thumbnails');selected=[x['id'] for x in rows if x['selected']];assert selected==[identity]
            shown=pixels(p,root+'/thumbnail');direct=pixels(p,root+'/thumbnails/'+identity)
            from hooks import compare_observation
            compare_observation(shown,direct)
            return {'selected':which,'image':shown}
        if action=='restart':
            before=pixels(p,root+'/thumbnail');assert p.broker.call({'op':'restart'})['ready'];after=pixels(p,root+'/thumbnail')
            from hooks import compare_observation
            compare_observation(after,before);return {'preserved':True,'poster':after}
        if action.startswith('delete-'):
            which=action[-1];identity=p.state['cover-'+which]['id'];p.ok(root+'/thumbnails/'+identity,'DELETE')
            rows=p.ok(root+'/thumbnails');assert all(x['id']!=identity for x in rows)
            return {'remaining_uploads':sorted(p.normalize(x['id']) for x in rows if x['type']=='USER_UPLOADED'),'fallback':pixels(p,root+'/thumbnail')}
        if action=='list':
            rows=p.ok(root+'/thumbnails');assert len([x for x in rows if x['type']=='USER_UPLOADED'])==2
            return {'uploads':sorted([{'id':p.normalize(x['id']),'selected':x['selected']} for x in rows if x['type']=='USER_UPLOADED'],key=lambda x:x['id'])}
        if action=='invalid-selection':
            before=blob(p,root+'/thumbnail');r=p.call(root+'/thumbnails/missing/selected','PUT');assert r['status']==404;assert blob(p,root+'/thumbnail')==before
            return {'status':404,'preserved':True}
    if family=='comicrack':
        if action=='ambiguous-fixture':
            p.ok('/api/v1/series/${s1.id}/metadata','PATCH',{'title':'Atlas','titleLock':True})
            p.ok('/api/v1/books/${b11.id}/metadata','PATCH',{'releaseDate':'2020-01-15','number':'1'})
            return {'second_title':p.ok('/api/v1/series/${s1.id}')['metadata']['title']}
        entries=s.get('entries',[['Atlas','1','2020']]);xml='<ReadingList><Name>ComicRack picks</Name><Books>'+''.join('<Book Series="'+x[0]+'" Number="'+x[1]+'"'+(' Volume="'+x[2]+'"' if len(x)>2 else '')+'/>' for x in entries)+'</Books></ReadingList>'
        name='reading.'+s.get('extension','cbl');p.put('/exchange/inbox',name,xml.encode())
        result=p.ok('/api/v1/readlists/match/comicrack','POST',multipart={'files':{'file':{'filename':name,'base64':base64.b64encode(xml.encode()).decode(),'mime_type':'application/xml'}}})
        req=result['requests'];assert len(req)==len(entries)
        found=[]
        for row,n in zip(req,s.get('matches',[1]*len(entries))):
            assert len(row['matches'])==n,'ComicRack matching population differs'
            ids=[b['bookId'] for m in row['matches'] for b in m['books']]
            assert len(ids)==n,'one exact book per matching series expected'
            found+=ids
        if s.get('expected'):
            assert found==p.resolve(s['expected']),'matched books or order differs'
        if action=='create':
            r=p.ok('/api/v1/readlists','POST',{'name':'Matched queue','summary':'Imported order','ordered':True,'bookIds':found})
            books=p.ok('/api/v1/readlists/'+r['id']+'/books')['content'];assert [x['id'] for x in books]==found
            return {'names':[x['name'] for x in books],'ordered':r['ordered']}
        return p.normalize(result)
    if family=='archive':
        raw=blob(p,'/api/v1/series/${s0.id}/file');members=zip_members(raw)
        expected={f'Atlas-{n:02}.cbz':hashlib.sha256(media.cbz(0,n)).hexdigest() for n in range(1,4)}
        assert {name.rsplit('/',1)[-1]:sha for name,sha in members.items()}==expected
        return {'members':expected,'verified':True}
    if family=='mihon-list':
        root='/api/v1/readlists/${queue.id}';ids=p.state['queue']['bookIds']
        actor=READER if s.get('reader') else AUTH
        if action=='set':p.ok(root+'/read-progress/tachiyomi','PUT',{'lastBookRead':s['index']},auth=actor)
        state=p.ok(root+'/read-progress/tachiyomi',auth=actor)
        books=p.ok(root+'/books',auth=actor)['content'];assert [x['id'] for x in books]==ids
        complete=[bool((x.get('readProgress') or {}).get('completed')) for x in books]
        assert state['booksReadCount']==sum(complete) and state['booksCount']==len(ids)
        if s.get('expect') is not None:assert complete==s['expect']
        if action=='invalid':
            before=complete;r=p.call(root+'/read-progress/tachiyomi','PUT',{'lastBookRead':-1},auth=actor);assert r['status']==400
            after=p.ok(root+'/books',auth=actor)['content'];assert [bool((x.get('readProgress') or {}).get('completed')) for x in after]==before
        if action=='restart':
            assert p.broker.call({'op':'restart'})['ready'];assert p.ok(root+'/read-progress/tachiyomi',auth=actor)==state
        return {'protocol':state,'completed':complete}
    if family=='self-password':
        new=s.get('password','Updated-Reader-2026!');old=p.state.get('reader-password',READER[1])
        if action=='change':
            p.ok('/api/v2/users/me/password','PATCH',{'password':new},auth=[READER[0],old]);p.state['reader-password']=new
            assert p.call('/api/v2/users/me',auth=[READER[0],old])['status']==401
            assert p.ok('/api/v2/users/me',auth=[READER[0],new])['email']==READER[0]
            assert p.ok('/api/v2/users/me')['email']==AUTH[0]
            return {'new_password_works':True,'old_password_refused':True,'admin_unchanged':True}
        actor=[READER[0],old]
        if action=='invalid':
            r=p.call('/api/v2/users/me/password','PATCH',{'password':''},auth=actor);assert r['status']==400;assert p.ok('/api/v2/users/me',auth=actor)['email']==READER[0];return {'status':400,'account_preserved':True}
        if action=='restart':
            assert p.broker.call({'op':'restart'})['ready'];return {'email':p.ok('/api/v2/users/me',auth=actor)['email']}
        if action=='activity':
            p.ok('/api/v2/users/me',auth=actor);p.call('/api/v2/users/me',auth=[READER[0],'wrong-activity-password'])
            rows=p.ok('/api/v2/users/me/authentication-activity',auth=actor,params={'size':100})['content']
            assert rows and all(x.get('email')==READER[0] for x in rows)
            assert any(x['success'] for x in rows) and any(not x['success'] for x in rows)
            allrows=p.ok('/api/v2/users/authentication-activity',params={'size':100})['content'];assert any(x.get('email')==READER[0] for x in allrows)
            assert p.call('/api/v2/users/authentication-activity',auth=actor)['status']==403
            return {'own_success_and_failure':True,'admin_sees_reader':True,'reader_admin_denied':True}
        if action=='cross-password':
            r=p.call('/api/v2/users/${admin.id}/password','PATCH',{'password':'Attempt!'},auth=actor);assert r['status']==403;assert p.ok('/api/v2/users/me')['email']==AUTH[0];return {'status':403,'admin_preserved':True}
    if family=='duplicate-single':
        if action=='matches':
            h=p.state['duplicate-hash'];rows=p.ok('/api/v1/page-hashes/'+h,params={'size':100})['content']
            assert len(rows)>=2;p.state['page-match']=next(x for x in rows if x['bookId']==p.state['b01']['id']);p.state['other-match']=next(x for x in rows if x['bookId']!=p.state['b01']['id'])
            return {'matches':len(rows),'same_image':True}
        if action=='delete':
            match=p.state['page-match'];other=p.state['other-match'];other_before=blob(p,'/api/v1/books/'+other['bookId']+'/file')
            p.ok('/api/v1/page-hashes/'+p.state['duplicate-hash']+'/delete-match','POST',match)
            p.wait(lambda:p.ok('/api/v1/books/${b01.id}')['media']['pagesCount']==3,'single duplicate removal')
            assert blob(p,'/api/v1/books/'+other['bookId']+'/file')==other_before
            names=zip_members(blob(p,'/api/v1/books/${b01.id}/file'));assert match['fileName'] not in names
            assert p.ok('/api/v1/books/'+other['bookId'])['media']['pagesCount']==4
            return {'target_pages':3,'other_pages':4,'other_archive_unchanged':True,'removed_member':match['fileName']}
        if action=='remaining':
            rows=p.ok('/api/v1/page-hashes/'+p.state['duplicate-hash'],params={'size':100})['content'];assert any(x['bookId']==p.state['other-match']['bookId'] for x in rows);assert all(x['bookId']!=p.state['b01']['id'] for x in rows)
            return {'remaining':len(rows),'target_removed_only':True}
    if family=='imports':
        source='/exchange/inbox/Incoming/'+s['name']+'.cbz'
        if action=='import':
            data=media.cbz(4,s.get('number',1));p.put('/exchange/inbox/Incoming',s['name']+'.cbz',data)
            p.ok('/api/v1/books/import','POST',{'copyMode':s['mode'],'books':[{'sourceFile':source,'seriesId':p.state['s0']['id'],'destinationName':s['name']}]})
            p.wait(lambda:any(x['name']==s['name'] and x['media']['status']=='READY' for x in p.ok('/api/v1/series/${s0.id}/books')['content']),'book import')
            book=next(x for x in p.ok('/api/v1/series/${s0.id}/books')['content'] if x['name']==s['name']);assert blob(p,'/api/v1/books/'+book['id']+'/file')==data
            files=p.broker.call({'op':'list_files','directory':'/exchange/inbox/Incoming'})['files'];exists=any(x['path']==source for x in files);assert exists==(s['mode']=='COPY')
            return {'name':book['name'],'mode':s['mode'],'source_exists':exists,'bytes_preserved':True}
    raise ValueError('unsupported extension '+family+'/'+action)
