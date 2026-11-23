"""Verifier helpers; every candidate interaction crosses the public runtime."""
import base64
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.parse
from evaluation.broker import BrokerError
import fixtures


class Context:
    def __init__(self,ctx):
        self.ctx=ctx;self.broker=ctx.broker;self.cache={};self.uploaded=set();self.current=''
        self.areas=self.call(op='help')['document_areas']
        self.scratch=Path(tempfile.mkdtemp(prefix='strawberry-',dir=os.environ.get('TMPDIR')))

    def call(self,**request):
        try:
            value=self.broker.call(request)
        except BrokerError as exc:
            raise AssertionError(f"{request.get('op')}: {exc.detail[:400]}") from None
        if request['op'] not in ('observe','screenshot','wait','help'):
            safe={k:v for k,v in request.items() if k!='base64'}
            result={k:v for k,v in value.items() if k!='body_base64'} if isinstance(value,dict) else value
            with (self.ctx.out/'protocol.jsonl').open('a') as f:f.write(json.dumps({'checkpoint':self.current,'request':safe,'reply':result},ensure_ascii=False)+'\n')
        return value

    def mpris(self,interface,action,member=None,args=None,value=None):
        req={'op':'mpris','interface':interface,'action':action}
        if member is not None:req['member']=member
        if args is not None:req['args']=args
        if value is not None:req['value']=value
        got=self.call(**req)
        assert got.get('ok') is True,f'MPRIS {member} failed: {got}'
        assert 'value' in got,'MPRIS reply missing value'
        return got['value']

    def get(self,member,interface='Player'):return self.mpris(interface,'get',member)
    def set(self,member,value,interface='Player'):return self.mpris(interface,'set',member,value=value)
    def method(self,member,*args,interface='Player'):return self.mpris(interface,'call',member,args=list(args))
    def cli(self,*args):
        got=self.call(op='cli',args=list(args))
        assert got.get('exit_code')==0,f'command-line request failed: {got}'
        return got

    def upload(self,name,payload=None,area='inputs'):
        if payload is None:payload=fixtures.audio(name).read_bytes()
        got=self.call(op='upload',filename=name,area=area,base64=base64.b64encode(payload).decode())
        assert got.get('uploaded') is True,'upload failed'
        self.uploaded.add((area,name));return got['path']

    def document(self,name,area='inputs'):
        if (area,name) not in self.uploaded:self.upload(name,area=area)
        return self.areas[area]+'/'+name

    def wait(self,predicate,seconds=15,message='product state did not settle'):
        end=time.monotonic()+seconds;last=None
        while True:
            last=predicate()
            if last:return last
            if time.monotonic()>=end:raise AssertionError(message)
            time.sleep(.15)

    def tracks(self):
        ids=self.get('Tracks','TrackList');assert isinstance(ids,list),'Tracks must be an array'
        if not ids:return []
        result=self.method('GetTracksMetadata',ids,interface='TrackList')
        assert isinstance(result,list) and len(result)==len(ids),'track metadata cardinality'
        for md in result:assert isinstance(md,dict),'track metadata must be an object'
        return result

    def load(self,paths,count=None,verify_identity=True):
        if not self.call(op='status').get('ready'):
            self.call(op='reset');self.uploaded.clear()
            raise AssertionError('application required recovery; scenario may be retried in a later checkpoint')
        self.cli('--stop');self.cli('--load',*paths)
        direct=all(Path(p).suffix.casefold() not in ('.m3u','.m3u8','.pls','.xspf','.asx','.asxini','.cue','.wpl') for p in paths)
        expected=[Path(p).name for p in paths] if direct else None
        previous=None;settle_after=time.monotonic()+.5
        def stable():
            nonlocal previous
            md=self.tracks()
            names=[document_name(m.get('xesam:url')) for m in md]
            enough=(len(md)==count) if count is not None else bool(md)
            # Stability is transport observation, never a semantic field check.
            # A bad/missing duration, title or URL must fail only its own point.
            projected=[{k:m[k] for k in fixtures.META_FIELDS if k in m} for m in md]
            identity_ok=(expected is None or names==expected) if verify_identity else True
            settled=enough and identity_ok and projected==previous and time.monotonic()>=settle_after
            previous=projected
            return md if settled else None
        return self.wait(stable,message='loaded track list did not become available')

    def take(self,name,area='outputs',seconds=20):
        def file():
            rows=self.call(op='list_files',area=area).get('files',[])
            return next((r for r in rows if r['filename']==name),None)
        row=self.wait(file,seconds,'expected output '+name+' was not written')
        payload=base64.b64decode(self.call(op='download',ref=row['ref'])['body_base64'])
        path=self.scratch/Path(name).name;path.write_bytes(payload);return path


def document_name(uri):
    if not isinstance(uri,str):return None
    try:return urllib.parse.unquote(Path(urllib.parse.urlsplit(uri).path).name)
    except ValueError:return None


def value(md,key):
    assert key in md,f'missing metadata field {key}'
    v=md[key]
    assert v is not None,f'null metadata field {key}'
    if key=='xesam:url':
        assert isinstance(v,str) and v,'document URI must be nonempty text'
        name=document_name(v);assert name,'document URI must name a file'
        return name
    if key=='mpris:length':
        assert type(v) in (int,float) and math.isfinite(v) and v>0,'audio duration must be positive'
        return {'seconds':v/1e6}
    if key in ('xesam:trackNumber','xesam:discNumber'):
        assert type(v) is int and v>=0,f'{key} must be a nonnegative integer'
    elif key in ('xesam:title','xesam:album'):
        assert isinstance(v,str),f'{key} must be text'
    elif key.startswith('xesam:'):
        assert isinstance(v,list) and all(isinstance(x,str) for x in v),f'{key} must be a text array'
    return v


def projection(md,keys=None):
    keys=keys or fixtures.META_FIELDS
    return {key:value(md,key) for key in keys if key in md}


def compare(actual,expected,path=''):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),f'{path}: expected an object'
        for k,v in expected.items():
            assert k in actual,f'{path}: missing {k}'
            if k=='loudness_lufs':
                assert type(actual[k]) in (int,float) and abs(actual[k]-v)<=.3,f'{path}: loudness differs'
            elif k=='seconds':
                assert isinstance(actual[k],(int,float)) and abs(actual[k]-v)<=.15,f'{path}: duration differs'
            elif k=='position_seconds':
                assert isinstance(actual[k],(int,float)) and abs(actual[k]-v)<=1.5,f'{path}: position differs'
            else:compare(actual[k],v,path+'/'+k)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),f'{path}: list length differs'
        for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+f'/{i}')
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=.011,f'{path}: numeric value differs ({actual!r} != {expected!r})'
    else:assert actual==expected,f'{path}: {actual!r} != {expected!r}'
