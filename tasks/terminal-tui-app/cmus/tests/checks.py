"""Semantic projections of real native commands and public files, never whole-screen equality."""
import json
import base64
import io
import wave
import struct
import re
import time
from harness import paths,parse_status,setting


def drive(s,steps):
    for step in steps:
        if isinstance(step,str):value=s.remote(step)
        elif 'remote' in step:value=s.remote(step['remote'])
        elif 'console' in step:value=s.console(step['console'])
        elif 'key' in step:value=s.key(step['key'])
        elif 'keys' in step:value=s.keys(step['keys'])
        elif 'type' in step:value=s.type(step['type'])
        elif 'upload' in step:value=s.upload(step['upload'])
        elif 'wait_positive' in step:value=s.wait_positive(**step['wait_positive'])
        elif 'sort_keys' in step:value=s.sort_keys(**step['sort_keys'])
        elif 'navigate' in step:value=s.navigate(**step['navigate'])
        elif 'boundary' in step:value=s.boundary(**step['boundary'])
        elif 'random_order' in step:value=s.random_order(**step['random_order'])
        elif 'wait_stopped' in step:value=s.wait_stopped()
        elif 'quit_saved' in step:value=s.quit_saved()
        elif 'wait_status' in step:value=s.wait_status(**step['wait_status'])
        elif 'wait_list' in step:value=s.wait_list(**step['wait_list'])
        elif 'play_paused' in step:value=s.play_paused(step['play_paused'])
        elif 'order' in step:value=s.order(step['order'])
        elif 'visible' in step:value=s.visible()
        elif 'restart' in step:value=s.call('restart')
        elif 'reset' in step:value=s.call('reset')
        elif 'wait' in step:value=s.call('wait',seconds=step['wait'])
        elif 'call' in step:value=s.broker.call(step['call'])
        else:raise ValueError('unknown driving operation')
        if isinstance(step,dict) and 'save' in step:s.saved[step['save']]=value


def setup(s,item):
    if item['op']=='upload':
        for f in item['files']:s.upload(f)
    elif item['op']=='drive':drive(s,item['steps'])
    else:raise ValueError('unknown setup operation')


def observe(s,check):
    src=check.get('source','query')
    if src=='captured':return s.saved[check['name']]
    if src=='state':return s.call('state',**check['request'])
    if src=='workspace':return s.call('workspace',**check['request'])
    if src=='cli':return s.call('cli',option=check['option'])
    if src=='screen':return s.call('screen')
    if src=='visible':return s.visible()
    return s.remote(check['command'])


def project(value,c):
    kind=c.get('project','text')
    if kind=='identity':out=value
    elif kind=='format-alignment':
        rows=[line.split('|',1)[-1] for line in value['screen']]
        matches=[line for line in rows if c['left'] in line and c['right'] in line]
        out=any(line.index(c['right'])>line.index(c['left'])+len(c['left'])+2 for line in matches)
    elif kind=='clipped-priority':
        text='\n'.join(value['screen']);out=c['title'] in text and c['artist'] not in text
    elif kind=='percentage-field':
        rows=[line.split('|',1)[-1] for line in value['screen']]
        fields=[m[1] for line in rows for m in re.finditer(r'\[([^]\n]*Format Artist[^]\n]*)\]',line)]
        out=any(abs(len(f)-value['size'][0]*.5)<=1 for f in fields)
    elif kind=='pcm-output':
        with wave.open(io.BytesIO(base64.b64decode(value['body_base64'])),'rb') as wav:
            frames=wav.readframes(wav.getnframes())
            out={'channels':wav.getnchannels(),'rate':wav.getframerate(),'width':wav.getsampwidth(),'frames':wav.getnframes(),'samples_match':wav.getsampwidth()==2 and wav.getnchannels()==2 and all(abs(struct.unpack_from('<h',frames,(index*2+channel)*2)[0]-level)<=2 for index,level in ((100,1000),(4200,-500),(8400,2000),(12400,-1500)) for channel in (0,1))}
    elif kind=='workspace-names':
        if 'entries' not in value:raise AssertionError('workspace listing is missing')
        out=sorted(x['name'] for x in value['entries'] if x['type']=='file')
    elif kind=='sort-key-order':
        keys=value
        if len(set(keys))<2:raise AssertionError('sort fixture does not distinguish this key')
        present=[x for x in keys if x is not None]
        out=present==sorted(present,reverse=c['reverse'])
        if not out:raise AssertionError('the traversal is not sorted by its actual media key')
    elif kind=='variable-paths':
        lines=[x for x in value.get('text','').splitlines() if x]
        token='\x1f'+c['variable']+'\x1f'
        out=len(lines)==c['count'] and all(token in x for x in lines)
        if not out:raise AssertionError('native playlist did not use environment path tokens')
    elif kind=='absolute-paths':
        lines=[x for x in value.get('text','').splitlines() if x]
        out=len(lines)==c['count'] and all(x.startswith('/workspace/') and '\x1f' not in x for x in lines)
        if not out:raise AssertionError('native export did not use ordinary workspace paths')
    elif kind=='text':out=str(value).strip()
    elif kind=='setting':out=setting(value)
    elif kind=='selected-in':out=str(value).strip().rsplit('/',1)[-1] in c['names']
    elif kind=='paths':
        out=paths(value)
        if c.get('unordered',True):out=sorted(out)
        elif c.get('ties'):
            groups=[]
            for name in out:
                label=c['ties'].get(name,name)
                if groups and groups[-1][0]==label:groups[-1][1].append(name)
                else:groups.append([label,[name]])
            out=[sorted(g[1]) for g in groups]
        if not c.get('allow_empty',False) and not out:raise AssertionError('expected nonempty native playlist')
    elif kind=='status':
        data=parse_status(value);field=c['field']
        if field not in data:raise AssertionError('missing native status field '+field)
        out=data[field]
        if field=='file':out=out.rsplit('/',1)[-1]
        elif c.get('number'):out=float(out)
    elif kind=='state-line':
        if not value.get('exists'):raise AssertionError('native state file is missing')
        line=next((x for x in value.get('text','').splitlines() if x.startswith(c['prefix'])),None)
        if line is None:raise AssertionError('saved state field is missing')
        out=line[len(c['prefix']):]
    elif kind=='state-paths':
        if not value.get('exists'):raise AssertionError('native playlist file is missing')
        out=paths(value.get('text',''))
        if c.get('unordered',True):out=sorted(out)
        elif c.get('ties'):
            groups=[]
            for name in out:
                label=c['ties'].get(name,name)
                if groups and groups[-1][0]==label:groups[-1][1].append(name)
                else:groups.append([label,[name]])
            out=[sorted(g[1]) for g in groups]
    elif kind=='state-names':
        if not value.get('exists') or not isinstance(value.get('entries'),list):raise AssertionError('native playlist directory is missing')
        out=sorted(x['name'] for x in value['entries'])
    elif kind=='extended-records':
        text=value.get('text','')
        rows=[];current=None
        for line in text.splitlines():
            if line.startswith('file '):
                current={'file':line[5:].rsplit('/',1)[-1]};rows.append(current)
            elif current is not None and ' ' in line:
                key,val=line.split(' ',1)
                if key=='tag' and ' ' in val:key,val=val.split(' ',1)
                current[key]=val
        if not rows:raise AssertionError('extended export has no track records')
        out=sorted([{k:r[k] for k in c['fields'] if k in r} for r in rows],key=lambda r:r['file'])
    elif kind=='file-text':
        if 'text' not in value:raise AssertionError('exported text file is missing')
        out=value['text'].strip()
        if c.get('paths'):out=sorted(paths(out)) if c.get('unordered',True) else paths(out)
    elif kind=='members':out=sorted(value)
    elif kind=='missing-tag':out=c['field'] not in parse_status(value)
    elif kind=='ordered':
        out=value
        if c.get('ties'):
            groups=[]
            for name in out:
                label=c['ties'].get(name,name)
                if groups and groups[-1][0]==label:groups[-1][1].append(name)
                else:groups.append([label,[name]])
            out=[sorted(g[1]) for g in groups]
    elif kind=='error':out=bool(str(value).strip())
    elif kind=='random-selection':
        out=paths(value)
        if len(out)!=c['count'] or any(x not in c['allowed'] for x in out):raise AssertionError('random selection must contain the requested number of valid library tracks')
        out={'count':len(out),'valid':True}
    elif kind=='screen-has':out=all(x in '\n'.join(value['screen']) for x in c['texts'])
    elif kind=='cli-line':
        if value.get('exit_code')!=0:raise AssertionError('terminating option failed')
        out=next((x for x in value.get('stdout','').splitlines() if c['match'].lower() in x.lower()),'')
    elif kind=='cli-has':
        if value.get('exit_code')!=0:raise AssertionError('terminating option failed')
        out=all(x in value.get('stdout','') for x in c['texts'])
    else:raise ValueError('unknown projection '+kind)
    if kind=='screen-has' and not out:raise AssertionError('the required visible result is absent')
    if c.get('nonempty') and not out:raise AssertionError('observation must not be empty')
    if 'guard' in c and out!=c['guard']:raise AssertionError('observable behavior does not satisfy the declared scenario')
    return out


def check_key(c):return json.dumps({k:v for k,v in c.items() if k in ('source','name','command','request','option')},sort_keys=True)
def compare(actual,expected,c):
    if 'tolerance' in c:
        if abs(float(actual)-float(expected))>c['tolerance']:raise AssertionError(f'value {actual} outside tolerance of {expected}')
    elif actual!=expected:raise AssertionError(f'observation differs: {str(actual)[:300]!r} != {str(expected)[:300]!r}')
