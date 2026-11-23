"""Product interfaces only: fixture setup, stable observations and field projections."""
import base64,hashlib,json,re,time,urllib.parse,xml.etree.ElementTree as ET
import media

EMAIL='admin@example.test'
PASSWORD='Admin-Local-2026!'
AUTH=[EMAIL,PASSWORD]
READER=['reader@example.test','Reader-Local-2026!']


def at(value,path):
    if path=='':return value
    for key in path.split('.'):
        if isinstance(value,list):value=value[int(key)]
        else:
            assert isinstance(value,dict) and key in value,'missing field '+path
            value=value[key]
    return value


class Product:
    def __init__(self,broker):self.broker=broker;self.state={};self.aliases={}
    def resolve(self,value):
        if isinstance(value,str):
            m=re.fullmatch(r'\$\{([^}]+)\}',value)
            if m:return at(self.state,m[1])
            return re.sub(r'\$\{([^}]+)\}',lambda m:str(at(self.state,m[1])),value)
        if isinstance(value,list):return [self.resolve(x) for x in value]
        if isinstance(value,dict):return {self.resolve(k):self.resolve(v) for k,v in value.items()}
        return value
    def call(self,path,method='GET',body=None,auth=AUTH,params=None,**kwargs):
        path=self.resolve(path);body=self.resolve(body);auth=self.resolve(auth)
        if params:path+='?'+urllib.parse.urlencode(self.resolve(params),doseq=True)
        d={'op':'api','path':path,'method':method,**self.resolve(kwargs)}
        if auth is not None:d['auth']=auth
        if body is not None:d['json']=body
        for attempt in range(2):
            try:r=self.broker.call(d);break
            except Exception as error:
                if method not in {'GET','HEAD'} or attempt or getattr(error,'error','')!='RemoteProtocolError':raise
                time.sleep(.2)
        assert not r.get('truncated'),'response was truncated'
        def names(v):
            if isinstance(v,dict):
                if 'id' in v and ('name' in v or 'email' in v):self.aliases.setdefault(str(v['id']),'entity:'+str(v.get('name',v.get('email'))))
                if 'id' in v and 'type' in v and 'selected' in v:self.aliases.setdefault(str(v['id']),'poster:'+str(v['type'])+':'+str(v.get('mediaType','')))
                for x in v.values():names(x)
            elif isinstance(v,list):
                for x in v:names(x)
        names(r.get('body'));return r
    def ok(self,path,method='GET',body=None,auth=AUTH,**kwargs):
        r=self.call(path,method,body,auth,**kwargs);assert 200<=r['status']<300,f'{method} {path}: {r["status"]} {str(r["body"])[:350]}'
        return r['body']
    def claim(self):
        self.state['admin']=self.ok('/api/v1/claim','POST',auth=None,headers={'X-Komga-Email':EMAIL,'X-Komga-Password':PASSWORD})
    def put(self,directory,name,data):
        return self.broker.call({'op':'put_file','directory':directory,'filename':name,'base64':base64.b64encode(data).decode()})
    def alias(self,value,name):
        if isinstance(value,(str,int)):self.aliases[str(value)]=name
    def discover(self):
        series=self.ok('/api/v1/series',params={'unpaged':'true'})['content']
        books=self.ok('/api/v1/books',params={'unpaged':'true'})['content']
        self.state['series']={x['name']:x for x in series};self.state['books']={x['name']:x for x in books}
        for x in series:self.alias(x['id'],'series:'+x['name'])
        for x in books:self.alias(x['id'],'book:'+x['name'])
        for i,name in enumerate(media.SERIES):
            if name in self.state['series']:self.state['s'+str(i)]=self.state['series'][name]
            for n in range(1,4):
                key=f'{name}-{n:02}'
                if key in self.state['books']:self.state[f'b{i}{n}']=self.state['books'][key]
        return books
    def library(self,rich=True,formats=False):
        nseries=6 if rich else 2
        for i in range(nseries):
            for n in range(1,4):self.put('/exchange/inbox/Comics/'+media.SERIES[i],f'{media.SERIES[i]}-{n:02}.cbz',media.cbz(i,n))
        if formats:
            self.put('/exchange/inbox/Comics/Documents','Journal.epub',media.epub())
            self.put('/exchange/inbox/Comics/Documents','Vector.pdf',media.pdf())
            self.put('/exchange/inbox/Comics/Documents','Archive.cbr',media.rar())
        lib=self.ok('/api/v1/libraries','POST',{'name':'Comics','root':'/exchange/inbox/Comics','scanInterval':'DISABLED','importComicInfoSeriesAppendVolume':False,'hashPages':True,'hashKoreader':True})
        self.state['lib']=lib;self.alias(lib['id'],'library:Comics')
        expected=nseries*3+(3 if formats else 0)
        self.wait(lambda:len(self.ok('/api/v1/books',params={'unpaged':'true'})['content'])==expected,'library scan')
        # Analysis/import are asynchronous. Give them a bounded quiet period without
        # making their correctness (or search availability) an unscored prerequisite.
        deadline=time.monotonic()+30;previous=None;quiet_since=time.monotonic()
        while time.monotonic()<deadline:
            books=self.discover()
            projection=self.normalize(books)
            if projection!=previous:previous=projection;quiet_since=time.monotonic()
            settled=all(x.get('media',{}).get('status') not in {'UNKNOWN','OUTDATED'} for x in books)
            if settled and time.monotonic()-quiet_since>=2:break
            time.sleep(.25)
        self.discover()
    def wait(self,f,description,seconds=60):
        deadline=time.monotonic()+seconds
        while True:
            if f():return
            assert time.monotonic()<deadline,'timeout waiting for '+description
            time.sleep(.25)
    def normalize_url(self,value):
        """Map opaque identities only at URL component boundaries, including short IDs."""
        parsed=urllib.parse.urlsplit(value)
        if parsed.scheme not in ('','http','https'):return value
        if not (parsed.scheme or value.startswith('/')):return value
        parts=parsed.path.split('/')
        resources={'books','book','series','libraries','collections','readlists','users','thumbnails','api-keys','kobo'}
        mapped=[]
        for i,part in enumerate(parts):
            decoded=urllib.parse.unquote(part)
            previous=urllib.parse.unquote(parts[i-1]) if i else ''
            mapped.append(self.aliases.get(decoded,decoded) if previous in resources else decoded)
        query=[]
        id_params={'book_id','series_id','library_id','collection_id','readlist_id','user_id','api_key_id','bookid','seriesid','libraryid'}
        for key,val in urllib.parse.parse_qsl(parsed.query,keep_blank_values=True):
            if key.lower() in id_params or key.lower().endswith('ids'):
                val=','.join(self.aliases.get(x,x) for x in val.split(','))
            query.append((key,val))
        origin='' if parsed.hostname in ('127.0.0.1','localhost') else (parsed.scheme+'://'+parsed.netloc if parsed.scheme else '')
        fragment=self.aliases.get(parsed.fragment,parsed.fragment)
        return origin+'/'.join(mapped)+('?' + urllib.parse.urlencode(sorted(query),doseq=True) if query else '')+('#'+fragment if fragment else '')

    def normalize(self,value,key=''):
        key=key.rsplit('.',1)[-1]
        if isinstance(value,dict):
            return {k:self.normalize(v,k) for k,v in value.items() if k not in {'created','lastModified','lastModifiedDate','createdDate','readDate','completedDate','fileLastModified','lastAuthenticationActivity','lastLogin','pageable','sort','lastRead','createdAt','updatedAt','timestamp'}}
        if isinstance(value,list):
            result=[self.normalize(v,key) for v in value]
            fields={'authors':('name','role'),'notableEntities':('name','kind'),'alternateTitles':('label','title'),
                    'links':('rel','href','url','label','type'),'publications':('metadata','links'),'navigation':('href','title','rel'),
                    'groups':('metadata','links'),'ContributorRoles':('Name',)}
            scalar_sets={'genres','tags','subject','sharingLabels','roles','labelsAllow','labelsExclude','sharedLibrariesIds','contributor','author','penciler','translator','Contributors'}
            if key in fields:
                def stable(x):
                    if not isinstance(x,dict):return json.dumps(x,sort_keys=True)
                    if key in {'publications','groups'}:return str(x.get('metadata',{}).get('title',''))
                    return json.dumps([x.get(k) for k in fields[key]],sort_keys=True,ensure_ascii=False)
                result.sort(key=stable)
            elif key in scalar_sets:result.sort(key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))
            return result
        if isinstance(value,str):
            literal={'title','name','label','summary','description','comment','email','number','language','publisher','isbn','role','kind','value'}
            identity_field=key=='' or key.lower().endswith(('id','ids')) or key=='key'
            if identity_field and value in self.aliases:return self.aliases[value]
            if key not in literal and value.startswith(('/', 'http://','https://')):return self.normalize_url(value)
            if re.fullmatch(r'\d{4}-\d\d-\d\d[T ]\d\d:\d\d.*',value):return '<timestamp>'
        if type(value) in (int,float) and (key.lower().endswith(('id','ids')) or key=='key'):
            return self.aliases.get(str(value),value)
        return value


def subset(actual,expected):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),'expected an object'
        if not expected:assert not actual,'expected an empty object'
        for key,val in expected.items():assert key in actual,'missing '+key;subset(actual[key],val)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),'collection length differs'
        for a,b in zip(actual,expected):subset(a,b)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert type(actual) in (int,float) and abs(actual-expected)<1e-6,'number differs'
    else:assert type(actual) is type(expected) and actual==expected,f'expected {expected!r}, received {actual!r}'
