"""Behavioral program cases. Each checkpoint performs its own observable operation."""
import base64,hashlib,io,json,struct,subprocess,time,urllib.parse,xml.etree.ElementTree as ET,zipfile
from common import AUTH,READER,Product,at,subset
import media


def request(path,method='GET',body=None,**kw):return {'path':path,'method':method,**({'body':body} if body is not None else {}),**kw}


def response(p,spec):
    kw={k:spec[k] for k in ('auth','params','headers','binary','body_base64','multipart','content_type') if k in spec}
    if 'raw' in spec:kw['body']=spec['raw']
    r=p.call(spec['path'],spec.get('method','GET'),spec.get('body'),**kw)
    expected=spec.get('status')
    assert (r['status'] in expected if isinstance(expected,list) else r['status']==expected) if expected is not None else 200<=r['status']<300, f'{spec["path"]}: {r["status"]}, {str(r["body"])[:300]}'
    body=r['body']
    if spec.get('save'):
        p.state[spec['save']]=body
        if isinstance(body,dict) and 'id' in body:p.alias(body['id'],'saved:'+spec['save'])
        if isinstance(body,dict) and 'key' in body:p.alias(body['key'],'credential:'+spec['save'])
    if 'where' in spec:
        xs=body.get('content',[]) if isinstance(body,dict) else body
        matches=[x for x in xs if all(at(x,k)==v for k,v in p.resolve(spec['where']).items())]
        assert len(matches)==1,'expected one matching object'
        body=r['body']=matches[0]
        if spec.get('save'):p.state[spec['save']]=body;p.alias(body['id'],'saved:'+spec['save'])
    if 'want' in spec:subset(body,p.resolve(spec['want']))
    for key,values in spec.get('contains',{}).items():
        actual=at(body,key);assert isinstance(actual,list) and all(x in actual for x in p.resolve(values)),'required collection members missing: '+key
    return r


def projected(p,r,spec):
    if r['status']>=400:return {'status':r['status']}
    body=r['body']
    if spec.get('opds_recommended'):body=opds_recommended(p,body)
    if spec.get('image'):
        raw=base64.b64decode(r['body_base64']);assert len(raw)>100,'image missing'
        proc=subprocess.run(['/usr/bin/python3','/tests/image_observation.py'],input=raw,capture_output=True)
        assert proc.returncode==0,'invalid image'
        observation=json.loads(proc.stdout)
        if spec.get('encoding'):
            mime=r.get('headers',{}).get('content-type','').split(';',1)[0].lower()
            fmt=observation['format'];assert fmt==spec['encoding'],'requested image encoding not produced'
            expected_mime={'JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp'}[fmt]
            assert mime==expected_mime,'image Content-Type does not match encoding'
            observation['media_type']=mime
        else:observation.pop('format')
        return {'status':r['status'],'image':observation}
    if spec.get('bytes'):
        raw=base64.b64decode(r['body_base64']);assert raw,'missing bytes'
        if spec.get('zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                return {'status':r['status'],'files':sorted([i.filename,hashlib.sha256(z.read(i)).hexdigest()] for i in z.infolist() if not i.is_dir())}
        return {'status':r['status'],'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
    if spec.get('xml'):
        root=ET.fromstring(body)
        def node(e):
            tag=e.tag.split('}')[-1]
            if tag in {'updated','id'}:return None
            return [tag,p.normalize(dict(e.attrib)),p.normalize((e.text or '').strip()),sorted([x for c in e if (x:=node(c)) is not None],key=lambda x:json.dumps(x,sort_keys=True))]
        return {'status':r['status'],'xml':node(root)}
    if 'field' in spec:body=at(body,spec['field'])
    if 'fields' in spec:body={f:at(body,f) for f in spec['fields']}
    if spec.get('catalog'):
        assert isinstance(body,dict) and isinstance(body.get('content'),list),'missing page content'
        content=body['content']
        for obj in content:
            if 'id' in obj and ('name' in obj or 'email' in obj):p.aliases.setdefault(str(obj['id']),'entity:'+str(obj.get('name',obj.get('email'))))
        fields=spec.get('item_fields',['name'])
        items=[{f:at(x,f) for f in fields} for x in content]
        if spec.get('unordered',True):
            # Some catalogs identify members only by generated IDs; order those by stable aliases.
            items=sorted(items,key=lambda x:json.dumps(p.normalize(x) if spec.get('sort_normalized_items') else x,
                                                       ensure_ascii=False,sort_keys=True))
        body={'items':items,**{k:body[k] for k in ('totalElements','totalPages','number','numberOfElements','first','last','size') if k in body}}
    if spec.get('unordered') and isinstance(body,list):body=sorted(body,key=lambda x:json.dumps({k:x[k] for k in ('name','email','comment','type','selected') if k in x} if isinstance(x,dict) else x,sort_keys=True))
    return {'status':r['status'],'value':p.normalize(body)}


def execute(p,spec):
    op=spec.get('kind','http')
    if op=='search-observation':
        # Repeated public reads wait for a stable result, not for a canned answer.
        previous=None;since=time.monotonic();deadline=since+10
        while True:
            actual=projected(p,response(p,spec['request']),spec['request'])
            if actual!=previous:previous=actual;since=time.monotonic()
            if time.monotonic()-since>=2 or time.monotonic()>deadline:return actual
            time.sleep(.25)
    if op=='extension':
        import extra_checks
        return extra_checks.execute(p,spec)
    if op=='kobo-sync':
        r=response(p,request(spec['path'],auth=None))
        assert isinstance(r['body'],list) and r['body'],'initial sync must contain publications'
        def titles(v):
            if isinstance(v,dict):
                return ([v['Title']] if 'Title' in v else [])+[t for x in v.values() for t in titles(x)]
            if isinstance(v,list):return [t for x in v for t in titles(x)]
            return []
        names=sorted(titles(r['body']));assert names,'sync did not contain book titles'
        token=r['headers'].get('x-kobo-synctoken');assert token,'sync token missing'
        second=response(p,request(spec['path'],auth=None,headers={'X-Kobo-SyncToken':token}))
        assert isinstance(second['body'],list),'sync continuation is not a list'
        return {'titles':names,'continued_titles':sorted(titles(second['body'])),'continued_count':len(second['body'])}
    if op=='exchange-check':
        r=p.broker.call({'op':'get_file','directory':spec['path'],'filename':spec['filename']})
        data=base64.b64decode(r['body_base64']);assert data,'empty file'
        if spec.get('zip'):
            with zipfile.ZipFile(io.BytesIO(data)) as z:return {'members':sorted([i.filename,hashlib.sha256(z.read(i)).hexdigest()] for i in z.infolist() if not i.is_dir())}
        return {'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    if op=='eventually':
        deadline=time.monotonic()+60
        while True:
            try:return projected(p,response(p,spec['read']),spec['read'])
            except (AssertionError,KeyError):
                if time.monotonic()>deadline:raise
                time.sleep(.25)
    if op=='restart':
        before=projected(p,response(p,spec['read']),spec['read']) if spec.get('compare_before') else None
        assert p.broker.call({'op':'restart'})['ready'],'restart failed'
        after=projected(p,response(p,spec['read']),spec['read'])
        if spec.get('compare_before'):
            from hooks import compare_observation
            compare_observation(after,before);return {'preserved':True}
        return after
    if op=='mutation':
        mutation=response(p,spec['write'])
        read=spec['read']
        if spec.get('eventual'):
            deadline=time.monotonic()+30
            while True:
                try:r=response(p,read);break
                except AssertionError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.2)
        else:r=response(p,read)
        return {'mutation_status':mutation['status'],'result':projected(p,r,read)}
    if op=='compound':return [execute(p,x) for x in spec['steps']]
    if op=='file':
        p.broker.call(p.resolve(spec['action']))
        return execute(p,spec['read'])
    if op=='thumbnail':
        name=spec['entity'];path=spec['path']
        r=response(p,request(path+'/thumbnails','POST',multipart={'files':{'file':{'filename':'poster.png','base64':base64.b64encode(media.png(spec.get('color',4))).decode(),'mime_type':'image/png'}}},params={'selected':'true'},save='poster-'+name))
        return projected(p,response(p,request(path+'/thumbnail',binary=True,image=True)),{'image':True})
    return projected(p,response(p,spec),spec)


class Builder:
    def __init__(self,key,feature=None,library=False,formats=False):
        self.key=key;self.cases=[];self.setup=[{'id':'account','kind':'account'}]
        if library:self.setup.append({'id':'library','kind':'library','formats':formats})
        self.feature=feature or key
    def add(self,name,spec,description=None,depends=()):
        cp={'id':name,'goal':description or name.replace('-',' '),'spec':spec,'depends_on':['setup:'+s['id'] for s in self.setup]+list(depends),'assertions':[{'id':self.key+'/'+name+'/result','channel':'backend','method':'program','requirement':description or 'The public operation preserves the requested values and product relationships: '+name.replace('-',' ')}]}
        self.cases.append(cp);return name
    def get(self,name,path,**kw):return self.add(name,request(path,**kw))
    def mutate(self,name,path,body,readpath=None,method='PATCH',fields=None,**kw):
        read=request(readpath or path,**({'fields':fields} if fields is not None else {}),**kw)
        return self.add(name,{'kind':'mutation','write':request(path,method,body),'read':read})
    def build(self):
        # A saved response is a real data dependency, including references in nested steps.
        import re
        saved={}
        last_mutation=None
        for cp in self.cases:
            spec=cp['spec'];serialized=json.dumps(spec,ensure_ascii=False)
            for ref in re.findall(r'\$\{([^}.]+)',serialized):
                if ref in saved and saved[ref] not in cp['depends_on']:cp['depends_on'].append(saved[ref])
            def walk(obj):
                if isinstance(obj,dict):
                    yield obj
                    for v in obj.values():yield from walk(v)
                elif isinstance(obj,list):
                    for v in obj:yield from walk(v)
            specs=list(walk(spec))
            for value in specs:
                if value.get('save'):saved[value['save']]=cp['id']
            if spec.get('kind')=='restart' and last_mutation and last_mutation not in cp['depends_on']:
                cp['depends_on'].append(last_mutation)
            if any(x.get('method','GET') in {'POST','PUT','PATCH','DELETE'} for x in specs):last_mutation=cp['id']
        return {'id':self.key,'feature':self.feature,'execution':'program','initial_state':'An unclaimed application; unscored public setup creates the required account and documents.','setup':self.setup,'inputs':{},'checkpoints':self.cases}



def opds_recommended(p,body):
    """Latest groups may cut through equal timestamps; validate that boundary relationally."""
    import copy,datetime,re
    body=copy.deepcopy(body)
    assert isinstance(body,dict) and isinstance(body.get('groups'),list),'missing OPDS groups'
    books={x['id']:x for x in p.ok('/api/v1/books',params={'unpaged':'true'})['content']}
    series={x['id']:x for x in p.ok('/api/v1/series',params={'unpaged':'true'})['content']}
    def date(value):
        assert isinstance(value,str),'timestamp missing'
        return datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
    for group in body['groups']:
        title=group.get('metadata',{}).get('title')
        if title not in ('Latest Books','Latest Series'):continue
        isbook=title=='Latest Books';key='publications' if isbook else 'navigation'
        records=group.get(key);assert isinstance(records,list),'missing latest entries'
        pool=books if isbook else series
        eligible={k:v for k,v in pool.items() if not v.get('deleted') and (v.get('media',{}).get('status')=='READY' if isbook else not v.get('oneshot'))}
        field='created' if isbook else 'lastModified'
        timestamps={k:date(v[field]) for k,v in eligible.items()}
        size=group['metadata'].get('itemsPerPage');assert type(size) is int and size>0,'invalid latest page size'
        assert len(records)==min(size,len(eligible)),'latest entry count differs'
        selected=[]
        for row in records:
            if isbook:
                links=row.get('links');assert isinstance(links,list),'publication links missing'
                selflink=next((x.get('href','') for x in links if x.get('rel')=='self'),'')
                match=re.search(r'/books/([^/]+)/manifest(?:$|[?#])',selflink)
                assert match and match[1] in eligible,'latest book identity is invalid'
                identity=match[1];source=eligible[identity];metadata=row.get('metadata',{})
                assert metadata.get('title')==source['metadata']['title'],'latest publication title differs'
                assert metadata.get('numberOfPages')==source['media']['pagesCount'],'latest publication page count differs'
                assert any(x.get('rel')=='http://opds-spec.org/acquisition' and '/books/'+identity+'/file' in x.get('href','') for x in links),'acquisition link identifies another book'
                assert row.get('images') and all('/books/'+identity+'/thumbnail' in x.get('href','') for x in row['images']),'poster link identifies another book'
            else:
                match=re.search(r'/series/([^/?#]+)',row.get('href',''))
                assert match and match[1] in eligible,'latest series identity is invalid'
                identity=match[1];assert row.get('title')==eligible[identity]['metadata']['title'],'latest series title differs'
            selected.append(identity)
        assert len(selected)==len(set(selected)),'duplicate latest entry'
        ranks=[timestamps[x] for x in selected];assert ranks==sorted(ranks,reverse=True),'latest entries are not chronological'
        if ranks:
            boundary=min(ranks)
            assert all(t<=boundary for k,t in timestamps.items() if k not in selected),'newer resource omitted from latest page'
        group[key]={'count':len(records),'valid_latest_membership':True}
    return body
