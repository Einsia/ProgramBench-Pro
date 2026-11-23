"""Semantic projections of public exports, terminal output and repository state."""
import base64
import json
import re
import shlex
import time

def color_value(tokens):
    """Tig ORs native attribute bits; normal contributes zero to a new rule."""
    assert len(tokens)>=2,'color rule lacks foreground or background'
    flags=set()
    for value in tokens[2:]:
        value=value.lower()
        if value!='normal':flags.add(value)
    return {'foreground':tokens[0].lower(),'background':tokens[1].lower(),'attributes':sorted(flags)}

def native(ctx,name):
    """Read a documented browsing-state variable through Tig's normal echo command."""
    key='native:'+name
    if key not in ctx.state['cache']:
        obs=ctx.broker.call({'op':'console','command':'echo PBPVALUE=%('+name+')'})
        assert obs.get('process')=='running','application is not running'
        values=[line.partition('|')[2][len('PBPVALUE='):] for line in obs['screen'] if line.partition('|')[2].startswith('PBPVALUE=')]
        assert values,'native browsing-state echo is missing'
        ctx.state['cache'][key]=values[-1].strip()
    return ctx.state['cache'][key]

def commits(ctx):
    result=read(ctx,{'op':'inspect','action':'log'})
    assert result['exit_code']==0,'Git log unavailable'
    out={}
    for line in result['stdout'].splitlines():
        f=line.split('\0')
        if len(f)>=5:out[f[0]]={'parents':f[1].split(),'author':f[2],'email':f[3],'subject':f[4]}
    assert out,'repository has no commits'
    return out

def selected_commit(ctx):
    sha=native(ctx,'commit');log=commits(ctx)
    assert sha in log,'selected commit does not identify a repository entry'
    return log[sha]['subject']

def select_text(ctx,text):
    ctx.broker.call({'op':'key','key':'/'})
    ctx.broker.call({'op':'type','text':text})
    ctx.broker.call({'op':'key','key':'Enter'})

def drive(ctx,steps):
    for request in steps:
        if request.get('op')=='capture-native':
            ctx.state['cache']={}
            ctx.state[request['as']]=native(ctx,request['name'])
            ctx.state['cache']={}
            continue
        if request.get('op')=='capture':
            ctx.state[request['name']]=ctx.broker.call(request['request'])
            continue
        if request.get('op')=='open-commits':
            log=commits(ctx);subjects=request['subjects']
            ids=[next(k for k,v in log.items() if v['subject']==s) for s in subjects]
            if request.get('raw'):
                result=ctx.broker.call({'op':'inspect','action':'raw-log','revisions':ids})
                assert result['exit_code']==0
                text=result['stdout']
            else:text='\n'.join(ids)+'\n'
            ctx.broker.call({'op':'open','args':request['args'],'stdin':text})
            ctx.state['cache']={}
            continue
        if request.get('op')=='await-screen':
            until=time.monotonic()+request.get('timeout',8)
            while True:
                obs=ctx.broker.call({'op':'screen'})
                text='\n'.join(line.partition('|')[2] for line in obs['screen'])
                if all(re.search(p,text,re.MULTILINE) for p in request.get('present',[])) and not any(re.search(p,text,re.MULTILINE) for p in request.get('absent',[])):break
                assert time.monotonic()<until,'product did not reach the expected visible state'
                ctx.broker.call({'op':'wait','seconds':.3})
            continue
        if request.get('op')=='console-error':
            result=ctx.broker.call({'op':'console','command':request['command']})
            tail=(result.get('screen') or [''])[-1]
            assert re.search(r'(?i)\b(?:failed|invalid|unknown|unrecognized|not supported|unsupported|cannot|unable|out of bound|not a valid|must be between)\b',tail),'native validation error was not reported'
            continue
        if request.get('op')=='click-text':
            observation=ctx.broker.call({'op':'screen'})
            target=request['text'];found=False
            for row,line in enumerate(observation['screen']):
                text=line.partition('|')[2]
                if target in text:
                    ctx.broker.call({'op':'mouse','column':text.index(target)+len(target)//2,'row':row,'button':'left'})
                    found=True;break
            assert found,'mouse target is not visible'
            continue
        if request.get('op')=='reload-export':
            result=ctx.broker.call({'op':'download','name':request['name']})
            assert result.get('exists'), 'configuration export missing'
            # Runtime safety bindings are outside the user configuration contract.
            lines=[line for line in result['text'].splitlines() if not any(c in line for c in ('\ue000','\ue001')) and not line.startswith(('bind generic                :','bind generic                g'))]
            # Saved bindings include the protected raw prompt keys: omit those safety entries.
            lines=[line for line in lines if not (line.lstrip().startswith('bind ') and len(shlex.split(line))>=3 and shlex.split(line)[2] in (':','g'))]
            ctx.broker.call({'op':'configure','text':''})
            ctx.broker.call({'op':'configure','text':'\n'.join(lines)})
        else:
            request=dict(request)
            artifact_only=request.pop('artifact_only',False)
            result=ctx.broker.call(request)
            if not artifact_only and request.get('op')=='console' and request.get('command','').startswith(('set ','bind ','color ','save-')):
                tail=(result.get('screen') or [''])[-1]
                assert not re.search(r'(?i)\b(?:failed|invalid|unknown|unrecognized|not supported|unsupported|cannot|not a valid|must be between)\b',tail), 'native command failed: '+tail

def export(text):
    result={'set':{},'bind':{},'color':{}}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        tokens=shlex.split(line,comments=True)
        if tokens[0]=='set' and len(tokens)>=3:result['set'][tokens[1]]=tokens[3:]
        elif tokens[0]=='bind' and len(tokens)>=4:result['bind'][' '.join(tokens[1:3])]=tokens[3:]
        elif tokens[0]=='color' and len(tokens)>=4:result['color'][tokens[1]]=tokens[2:]
    return result

def read(ctx,request):
    key=json.dumps(request,sort_keys=True)
    cache=ctx.state['cache']
    if key not in cache:cache[key]=ctx.broker.call(request)
    return cache[key]

def screen(ctx):
    observation=read(ctx,{'op':'screen'})
    assert observation.get('process')=='running','application is not running'
    return '\n'.join(line.partition('|')[2] for line in observation['screen'])

def observe(ctx,check):
    kind=check['kind']
    if kind in ('config','column','binding','color'):
        result=read(ctx,{'op':'download','name':check.get('file','options.tigrc')})
        assert result.get('exists') and result.get('text'),'configuration export missing or empty'
        parsed=export(result['text'])
        if kind=='config':
            assert check['name'] in parsed['set'],'setting absent from exported configuration'
            if 'expected' in check:assert parsed['set'][check['name']]==check['expected'],'configuration value differs from the native rule'
            return parsed['set'][check['name']]
        if kind=='binding':
            assert check['name'] in parsed['bind'],'binding absent from exported configuration'
            return parsed['bind'][check['name']]
        if kind=='color':
            assert check['name'] in parsed['color'],'color rule absent from exported configuration'
            return color_value(parsed['color'][check['name']])
        columns=parsed['set'].get(check['view']+'-view')
        assert columns,'view columns missing from exported configuration'
        col=next((x for x in columns if x.split(':',1)[0]==check['column']),None)
        assert col is not None,'column missing from exported configuration'
        _,_,spec=col.partition(':');parts=spec.split(',')
        attrs={'display':parts[0]} if parts[0] else {'display':'yes'}
        for part in parts[1:]:
            name,_,value=part.partition('=');attrs[name]=value or 'yes'
        # Upstream omits default-valued column attributes when serializing.
        defaults={'width':'0','maxwidth':'0','interval':'5','local':'no','use-author':'no','color':'no','refs':'yes','graph':'no','overflow':'no','commit-title-overflow':'no'}
        value=attrs.get(check['attribute'],defaults.get(check['attribute']))
        assert value is not None,'column field absent from exported configuration'
        if check['attribute']=='maxwidth' and re.fullmatch(r'-\d+',value):value=value[1:]+'%'
        if 'expected' in check:assert value==check['expected'],f'column setting did not take effect: {value!r} versus {check["expected"]!r}'
        return value
    if kind=='screen':
        text=screen(ctx)
        for pattern in check.get('absent',[]):assert not re.search(pattern,text,re.MULTILINE),'filtered content should not be shown'
        if 'patterns' in check:
            out=[bool(re.search(p,text,re.MULTILINE)) for p in check['patterns']]
            if check.get('positive',True):assert all(out),'required content absent from terminal'
            return out
        if 'selected' in check:
            assert selected_commit(ctx)==check['selected'],'wrong history entry selected'
            return True
    if kind=='native':
        value=native(ctx,check['name'])
        if 'pattern' in check:
            assert re.search(check['pattern'],value),'wrong native browsing text'
            return True
        if check.get('index_blob'):
            index=read(ctx,{'op':'inspect','action':'index'})['stdout']
            record=next((r for r in index.split('\0') if r.endswith('\t'+check['index_blob'])),None)
            assert record and value==record.split()[1],'browsing blob differs from the repository blob'
            return check['index_blob']
        if check.get('subject'):
            log=commits(ctx);assert value in log and log[value]['subject']==check['subject'],'wrong browsing revision'
            return log[value]['subject']
        if 'expected' in check:assert value==str(check['expected']),'wrong native browsing value'
        assert value or check.get('allow_empty'),'native browsing value is empty'
        return value
    if kind=='history-set':
        if check.get('focus_main'):
            # Inspect the existing history alone. This only changes presentation;
            # it does not change its revision arguments or filtering state.
            obs=ctx.broker.call({'op':'key','key':'m'})
            ctx.state['cache'][json.dumps({'op':'screen'},sort_keys=True)]=obs
        text=screen(ctx);universe=check.get('universe') or [v['subject'] for v in commits(ctx).values()]
        visible=[s for s in universe if s in text]
        assert set(visible)==set(check['expected']),'wrong set of history entries'
        if check.get('ordered'):
            actual=sorted(visible,key=text.index)
            assert actual==check['expected'],'wrong history order'
            return actual
        return sorted(visible)
    if kind=='visible-order':
        text=screen(ctx);items=check['items']
        assert all(x in text for x in items),'ordered content missing'
        actual=sorted(items,key=text.index)
        assert actual==items,'content is in the wrong order'
        return actual
    if kind=='ref-set':
        text=screen(ctx)
        for name in check['present']:assert re.search(r'(?<![\w/])'+re.escape(name)+r'(?![\w/])',text),'reference missing'
        for name in check.get('absent',[]):assert not re.search(r'(?<![\w/])'+re.escape(name)+r'(?![\w/])',text),'excluded reference is visible'
        return sorted(check['present'])
    if kind=='screen-content':
        text=screen(ctx)
        for value in check.get('present',[]):assert re.search(value,text,re.MULTILINE),'required semantic content absent'
        for value in check.get('absent',[]):assert not re.search(value,text,re.MULTILINE),'incorrect semantic content present'
        return True
    if kind=='motion':
        value=native(ctx,'text')
        match=re.search(check.get('pattern',r'Entry (\d+)'),value)
        before=re.search(check.get('pattern',r'Entry (\d+)'),ctx.state[check['before']])
        assert match and before,'motion did not identify logical lines'
        delta=int(match[1])-int(before[1])
        low,high=check['delta']
        assert low<=delta<=high,'selection moved by the wrong amount'
        return True
    if kind=='screen-window':
        text=screen(ctx);pattern=check.get('pattern',r'Entry (\d+)')
        before=ctx.state[check['before']]
        prior='\n'.join(x.partition('|')[2] for x in before['screen'])
        now=[int(x) for x in re.findall(pattern,text)];old=[int(x) for x in re.findall(pattern,prior)]
        assert now and old,'visible content has no logical line identifiers'
        delta=min(now)-min(old)
        assert check['delta'][0]<=delta<=check['delta'][1],'viewport did not scroll as requested'
        return True
    if kind=='same-native':
        assert native(ctx,check['name'])==ctx.state[check['before']],'unrelated current item changed'
        return True
    if kind=='head-subject':
        result=read(ctx,{'op':'inspect','action':'head'});assert result['exit_code']==0
        subject=result['stdout'].strip().split('\0')[3]
        assert subject==check['expected'],'HEAD points to the wrong commit'
        return subject
    if kind=='clean':
        result=read(ctx,{'op':'inspect','action':'status'})
        assert result['exit_code']==0 and not result['stdout'],'repository is not clean'
        return True
    if kind=='history-lines':
        result=read(ctx,{'op':'state','file':'history'});assert result.get('exists'),'history was not saved'
        lines=[x for x in result['text'].splitlines() if x]
        if 'expected' in check:assert lines==check['expected'],'history contents or order differ'
        for text in check.get('present',[]):assert text in lines,'history entry missing'
        for text in check.get('absent',[]):assert text not in lines,'history entry was not removed'
        if 'limit' in check:assert len(lines)<=check['limit'],'history limit exceeded'
        return lines if check.get('compare_lines') else True
    if kind=='author-order':
        text=screen(ctx)
        sequence=[]
        for line in text.splitlines():
            for author in check['authors']:
                if author in line:sequence.append(author)
        assert set(sequence)==set(check['authors']),'author groups missing'
        groups=[a for i,a in enumerate(sequence) if i==0 or a!=sequence[i-1]]
        assert groups==check['authors'],'author groups are not in the requested order'
        return groups
    if kind=='linked-commit':
        text=screen(ctx)
        subject=selected_commit(ctx)
        assert subject==check['subject'],'the linked view has the wrong commit'
        sha=next(k for k,v in commits(ctx).items() if v['subject']==subject)
        assert re.search(r'(?i)commit\s+'+sha[:7],text),'the diff does not show the selected revision'
        assert all(s in text for s in check['history']),'the parent history is not visible'
        ctx.broker.call({'op':'key','key':'Tab'})
        ctx.state['cache'].pop('native:commit',None)
        try:other=selected_commit(ctx)
        finally:
            ctx.broker.call({'op':'key','key':'Tab'})
            ctx.state['cache'].pop('native:commit',None)
        assert other==subject,'parent and child views select different revisions'
        return True
    if kind=='index-entry':
        result=read(ctx,{'op':'inspect','action':'index'});assert result['exit_code']==0
        entries={}
        for record in result['stdout'].split('\0'):
            if not record:continue
            meta,path=record.split('\t',1);mode,oid,stage=meta.split();entries[path]=(mode,oid,stage)
        path=check['path']
        if check.get('absent'):
            assert path not in entries,'file remains in the index';return True
        assert path in entries,'file missing from the index'
        mode,oid,stage=entries[path]
        assert mode==check['mode'] and stage=='0','incorrect staged file type or mode'
        data=read(ctx,{'op':'inspect','action':'blob','revision':':','path':path})
        assert data['exit_code']==0
        wanted=check.get('base64') or base64.b64encode(check.get('text','').encode()).decode()
        assert data['body_base64']==wanted,'incorrect staged bytes'
        return {'mode':mode,'body_base64':data['body_base64']}
    if kind=='commit-result':
        result=read(ctx,{'op':'inspect','action':'head'});assert result['exit_code']==0
        sha,parents,tree,subject=result['stdout'].strip().split('\0')[:4]
        log=commits(ctx)
        assert subject==check['subject'],'commit message was not created'
        parent_ids=parents.split()
        assert len(parent_ids)==1 and log.get(parent_ids[0],{}).get('subject')==check['parent'],'new commit has the wrong parent'
        assert sha not in parent_ids,'HEAD did not advance'
        for path,content in check['files'].items():
            committed=read(ctx,{'op':'inspect','action':'blob','revision':'HEAD','path':path})
            staged=read(ctx,{'op':'inspect','action':'blob','revision':':','path':path})
            assert committed['exit_code']==staged['exit_code']==0 and committed['stdout']==staged['stdout']==content,'commit tree or index has incorrect contents'
        status=read(ctx,{'op':'inspect','action':'status'})
        assert status['exit_code']==0 and status['stdout']=='','commit did not leave a clean index and worktree'
        return {'subject':subject,'parent':check['parent'],'files':check['files'],'clean':True}
    if kind=='blob':
        result=read(ctx,{'op':'inspect','action':'blob','path':check['path'],'revision':check.get('revision',':')})
        assert result['exit_code']==0,'blob is unavailable'
        if check.get('contains'):
            assert check['contains'] in result['stdout'],'expected change is not present'
        if 'expected' in check:assert result['stdout']==check['expected'],'wrong staged content'
        return result['stdout']
    if kind=='file':
        result=read(ctx,{'op':'inspect','action':'read','path':check['path']})
        if 'expected' in check:assert result['text']==check['expected'],'wrong working copy content'
        return result['body_base64']
    if kind=='status':
        result=read(ctx,{'op':'inspect','action':'status'})
        assert result['exit_code']==0,'Git status failed'
        values=sorted(x for x in result['stdout'].split('\0') if x)
        if check.get('path'):
            values=[x for x in values if x[3:]==check['path']]
        if check.get('nonempty',True):assert values,'status must contain the expected changed file'
        return values
    if kind=='cli':
        result=read(ctx,{'op':'cli','option':check['option']})
        assert result['exit_code']==0 and result['stdout'].strip(),'CLI did not return usable output'
        if 'version' in check['option'] or check['option']=='-v':
            m=re.search(r'(?i)\btig(?: version)?\s+(\d+\.\d+\.\d+)',result['stdout'])
            assert m,'missing product version';return m.group(1)
        assert 'Usage:' in result['stdout'] or 'usage:' in result['stdout'],'missing CLI usage'
        return sorted(word for word in ['status','blame','grep','show','log','reflog','stash','refs'] if word in result['stdout'])
    if kind=='history':
        result=read(ctx,{'op':'state','file':'history'})
        assert result['exists'],'native history file missing'
        assert check['text'] in result['text'].splitlines(),'history entry missing'
        return True
    if kind=='git':
        result=read(ctx,dict(op='inspect',**check['request']))
        assert result['exit_code']==0,'Git inspection failed'
        text=result['stdout']
        for pattern in check.get('present',[]):assert re.search(pattern,text,re.MULTILINE),'expected repository state missing'
        for pattern in check.get('absent',[]):assert not re.search(pattern,text,re.MULTILINE),'repository state should have changed'
        return True
    if kind=='export-display':
        result=read(ctx,{'op':'download','name':check['file']})
        assert result.get('exists') and result.get('text'),'screen export missing'
        assert check['contains'] in result['text'],'screen export lacks requested content'
        return True
    if kind=='error':
        text=screen(ctx)
        assert re.search(check['pattern'],text,re.IGNORECASE),'native error message missing'
        return True
    raise ValueError('unknown check kind '+kind)
