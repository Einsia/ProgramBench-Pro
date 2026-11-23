"""Public API setup and checkpoint observation for GUI episodes, independent of agent verdicts."""
import hashlib
import json
import re
import time
from harness import blob_sha


def lookup(value,path):
    for part in path.split('.'):
        assert isinstance(value,(dict,list)),'expected a JSON object at '+part
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def resolve(value,state):
    if isinstance(value,str):
        full=re.fullmatch(r'\{\{([^{}]+)\}\}',value)
        if full:return lookup(state,full[1])
        return re.sub(r'\{\{([^{}]+)\}\}',lambda m:str(lookup(state,m[1])),value)
    if isinstance(value,list):return [resolve(x,state) for x in value]
    if isinstance(value,dict):return {k:resolve(v,state) for k,v in value.items()}
    return value


def request(c,spec):
    spec=resolve(spec,c.state)
    response,payload=c.request(spec['method'],spec['path'],spec.get('actor','alice'),body=spec.get('body'),params=spec.get('params'))
    allowed=spec.get('status',200);allowed=allowed if isinstance(allowed,list) else [allowed]
    assert response.status_code in allowed,f"{spec['method']} {spec['path']}: expected {allowed}, received {response.status_code}"
    if spec.get('save'):c.state[spec['save']]=payload
    return response,payload


def setup(c,item):
    """One unscored GUI setup request: any success status; saves only what later steps reference.
    `settle` waits before the request so the product's asynchronous processing of the previous one is finished."""
    time.sleep(item.get('settle',0))
    spec=resolve({k:v for k,v in item.items() if k in ('method','path','actor','body')},c.state)
    response,payload=c.request(spec['method'],spec['path'],spec.get('actor','alice'),body=spec.get('body'))
    assert 200<=response.status_code<300,f"setup {spec['method']} {spec['path']}: status {response.status_code}"
    if item.get('save'):
        assert isinstance(payload,dict),'setup response is not a JSON object'
        c.state[item['save']]=payload


def normalize_text(value):
    """HTML form CRLF and API LF encode the same text, not different content."""
    if isinstance(value,str):return value.replace('\r\n','\n')
    if isinstance(value,list):return [normalize_text(x) for x in value]
    if isinstance(value,dict):return {k:normalize_text(v) for k,v in value.items()}
    return value


def observe(c,check):
    if 'content_sha256' in check:
        # Stored bytes (for example an LFS object): only their identity matters.
        response,payload=request(c,check['request'])
        assert hashlib.sha256(response.content).hexdigest()==check['content_sha256'],'stored bytes differ'
        return {'status':response.status_code,'content_sha256':check['content_sha256']}
    if 'refused' in check:
        # A refusal counts only together with the positive read in the same observation.
        value=observe(c,{k:v for k,v in check.items() if k!='refused'})
        response,payload=request(c,check['refused'])
        if response.status_code>=400:c.observe(response,payload)
        allowed=check['refused'].get('status',200)
        return {**value,'refused':{'status_class':'accepted-'+','.join(str(x) for x in (allowed if isinstance(allowed,list) else [allowed]))}}
    response,payload=request(c,check['request'])
    if response.status_code>=400:c.observe(response,payload)
    allowed=check['request'].get('status',200)
    if isinstance(allowed,list):return {'status_class':'accepted-'+','.join(str(x) for x in allowed)}
    if response.status_code>=400 or response.status_code==204:return {'status':response.status_code}
    if check.get('where') is not None:
        wanted=resolve(check['where'],c.state)
        assert isinstance(payload,list),'expected a resource collection'
        matches=[x for x in payload if isinstance(x,dict) and all(lookup(x,k)==v for k,v in wanted.items())]
        assert len(matches)==1,'expected exactly one resource matching '+str(wanted)
        payload=matches[0]
        if check['request'].get('save'):c.state[check['request']['save']]=payload
    assert isinstance(payload,(dict,list)),'expected a JSON response'
    def project(obj):
        result={key:normalize_text(lookup(obj,key)) for key in check.get('fields',[])}
        for key in ('content','content_base64'):
            if key in result and isinstance(result[key],str):result[key]=''.join(result[key].split())
        return result
    if check.get('collection'):
        assert isinstance(payload,list),'expected a list'
        value=sorted([project(x) for x in payload],key=lambda x:json.dumps(x,sort_keys=True))
    else:value=project(payload)
    expected=normalize_text(resolve(check.get('expected'),c.state))
    if expected is not None:assert value==expected,'public state differs from requested values'
    return {'status':response.status_code,'value':value}


def file_sha(content):
    """Git blob identity of a known file content (the current sha a contents update names)."""
    return blob_sha(content)
