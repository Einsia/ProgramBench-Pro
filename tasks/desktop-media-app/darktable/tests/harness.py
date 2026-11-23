"""Verifier access through the public runtime only; semantic comparisons."""
import base64
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

from evaluation.broker import BrokerError
import fixtures
import imaging


class Context:
    def __init__(self, broker, out, scratch):
        self.broker=broker
        self.out=Path(out)
        self.scratch=Path(scratch)
        self.scratch.mkdir(parents=True,exist_ok=True)
        self.serial=0
        self.uploaded=set()
        self.files={}
        self.areas={}
        self.current_case=''

    def call(self, request, timeout=100):
        return self.broker.call(request,timeout=timeout)

    def area(self, name):
        if not self.areas:
            for note in self.call({'op':'help'}).get('notes',[]):
                self.areas.update(re.findall(r'(inputs|outputs) (/[^ ,]+)',note))
        assert name in self.areas, 'runtime help does not identify the document area'
        return self.areas[name].rstrip('.')

    def upload(self, name, data):
        self.call({'op':'upload','filename':name,'base64':base64.b64encode(data).decode()})
        self.uploaded.add(name)
        return name

    def fixture(self, name):
        if name not in self.uploaded:
            self.upload(name,fixtures.image(name))
        return name

    def name(self, suffix='.png'):
        self.serial+=1
        return 'export-%05d%s' % (self.serial,suffix)

    def cli(self, args):
        try:
            reply=self.call({'op':'cli','args':list(args)})
        except BrokerError as exc:
            raise AssertionError('command-line operation failed: '+str(exc)) from None
        assert isinstance(reply,dict) and type(reply.get('exit_code')) is int,'missing process exit status'
        with (self.out/'protocol.jsonl').open('a') as stream:
            stream.write(json.dumps({'case':self.current_case,'args':args,**reply},ensure_ascii=False)+'\n')
        return reply

    def collect(self):
        for entry in self.call({'op':'list_files'}).get('downloads',[]):
            value=self.call({'op':'download','ref':entry['ref']})
            self.files[value['filename']]=base64.b64decode(value['body_base64'])

    def fetch(self, path, wait=12):
        deadline=time.monotonic()+wait
        while True:
            try:
                value=self.call({'op':'read_file','filename':path})
                data=base64.b64decode(value['body_base64'])
                self.files[path]=data
                return data
            except BrokerError:
                self.files.pop(path,None)
            if time.monotonic()>=deadline:
                raise AssertionError('output was not written: '+path)
            time.sleep(.2)

    def inventory(self):
        current=self.call({'op':'documents'}).get('files',[])
        existing={row['filename'] for row in current}
        self.files={key:value for key,value in self.files.items() if key in existing}
        return current

    def render(self, source='chart.png', history=None, options=(), suffix='.png', metadata=None):
        self.fixture(source)
        output=self.name(suffix)
        args=[source]
        if history is not None or metadata is not None:
            sidecar=self.name('.xmp')
            self.upload(sidecar, fixtures.xmp(history or (),**(metadata or {})))
            args.append(sidecar)
        reply=self.cli([*args,output,*options])
        assert reply['exit_code']==0, 'export failed: '+str(reply.get('log',''))[-500:]
        if suffix in ('.j2k','.heif'):
            choices=[d['filename'] for d in reply.get('downloads',[]) if d['filename'].startswith('outputs/'+Path(output).stem+'.')]
            assert len(choices)==1,'export with a canonical extension missing'
            return self.fetch(choices[0]),reply
        return self.fetch('outputs/'+output),reply

    def close(self):
        shutil.rmtree(self.scratch,ignore_errors=True)


def compare(actual, expected, policy='exact'):
    if policy=='image':
        assert imaging.distance(actual,expected)<=.012, 'rendered image differs from the reference beyond the image tolerance'
    elif isinstance(expected,dict):
        assert isinstance(actual,dict), 'expected an object'
        for key,value in expected.items():
            assert key in actual, 'missing field '+key
            if key=='quantization':
                assert len(actual[key])==len(value) and all(abs(a-b)<=max(1.,.2*b) for a,b in zip(actual[key],value)),'JPEG quality differs'
            else:compare(actual[key],value,'image' if key=='image' else 'exact')
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected), 'list length differs'
        for a,b in zip(actual,expected): compare(a,b)
    elif isinstance(expected,float):
        assert isinstance(actual,(int,float)) and abs(actual-expected)<=max(.001,abs(expected)*.002),'numeric value differs'
    else:
        assert actual==expected, 'observation differs: %r != %r' % (actual,expected)
