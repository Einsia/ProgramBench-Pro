"""Notebook backups compared as a document graph through API and export files."""
import base64
import hashlib
import io
import json
import re
import tarfile
from datetime import datetime, timezone

from harness import Ref, aspects, b64
from fixtures import png

ASPECTS={
    'notes':'Both note titles and their document content are preserved.',
    'folders':'The child notebook remains nested beneath the exported parent.',
    'metadata':'Nondefault authors, user dates and to-do metadata are preserved.',
    'tags':'Both notes retain their distinct tags.',
    'resources':'Image and text attachment bytes and metadata are preserved.',
    'links':'The internal note and attachment references resolve to the correct imported objects.',
}


def expected(markdown=False):
    records=[
        {'id':'root','type_':2,'title':'Workbench','parent_id':''},
        {'id':'child','type_':2,'title':'Field trips','parent_id':'root'},
        {'id':'image','type_':4,'title':'field.png','mime':'image/png'},
        {'id':'file','type_':4,'title':'field.txt','mime':'text/plain'},
    ]
    for key,title,body,parent,author,todo,due,tags in [
        ('plan','Trip plan','# Trip plan\n\nPack a map and water.','child','Grace Hopper',1,1768901400000,['planning']),
        ('log','Trip log','# Trip log\n\nObserved three trees.\n\n[Plan](:/plan)\n\n![Field](:/image)\n\n[Measurements](:/file)',
         'root','Ada Lovelace',0,0,['botany','fieldwork'])]:
        records.append({'id':key,'type_':1,'title':title,'body':body,'parent_id':parent,'author':author,
            'is_todo':todo,'todo_due':due,'user_created_time':1704164645000,'user_updated_time':1738555506000})
        for tag in tags:
            records.append({'id':tag,'type_':5,'title':tag})
            records.append({'id':key+'-'+tag,'type_':6,'note_id':key,'tag_id':tag})
    if markdown:
        records=[r for r in records if r['id']!='file']
        for r in records:
            if 'body' in r:r['body']=r['body'].replace('\n\n[Measurements](:/file)','')
    identities={r['id']:hashlib.md5(r['id'].encode()).hexdigest() for r in records}
    for r in records:
        for field in ('id','parent_id','note_id','tag_id'):
            if r.get(field):r[field]=identities[r[field]]
        if 'body' in r:r['body']=re.sub(r':/([a-z]+)',lambda m:':/'+identities[m[1]],r['body'])
    result=normalized(records,lambda r:png() if r['title']=='field.png' else b'North bank: two oaks.\nSouth bank: one elm.\n')
    result['links']=[['Trip log','@note:Trip plan'],['Trip log','@resource:field.png']]+([] if markdown else [['Trip log','@resource:field.txt']])
    return result


def setup(c,markdown=False):
    c.call('POST','/folders',body={'title':'Field trips','parent_id':Ref('Workbench')},save='Field trips')
    for name,data in [('field.png',png()),('field.txt',b'North bank: two oaks.\nSouth bank: one elm.\n')]:
        c.call('POST','/resources',multipart={'filename':name,'base64':b64(data),'props':{'title':name}},save=name)
    c.call('POST','/notes',body={'title':'Trip plan','body':'# Trip plan\n\nPack a map and water.',
        'parent_id':Ref('Field trips'),'author':'Grace Hopper','tags':'planning','is_todo':1,
        'todo_due':1768901400000,'user_created_time':1704164645000,'user_updated_time':1738555506000},save='Trip plan')
    c.call('POST','/notes',body={'title':'Trip log','body':'# Trip log\n\nObserved three trees.\n\n[Plan](:/'+c.values['Trip plan']['id']+
        ')\n\n![Field](:/'+c.values['field.png']['id']+')'+('' if markdown else '\n\n[Measurements](:/'+c.values['field.txt']['id']+')'),
        'parent_id':Ref('Workbench'),'author':'Ada Lovelace','tags':'botany,fieldwork',
        'user_created_time':1704164645000,'user_updated_time':1738555506000},save='Trip log')


def normalized(records,resource_bytes):
    by_id={r['id']:r for r in records}
    prefixes={1:'note',2:'folder',4:'resource',5:'tag'}
    def name(r):
        title=r.get('title','')
        if int(r['type_'])==2:
            title=re.sub(r' \(\d+\)$','',title)
        return title
    aliases={key:'@'+prefixes.get(int(r['type_']),'item')+':'+name(r) for key,r in by_id.items()}
    def text(value):
        for key,alias in aliases.items():value=value.replace(key,alias)
        return value.replace('\r\n','\n').rstrip('\n')
    notes=[r for r in records if int(r['type_'])==1]
    folders=[r for r in records if int(r['type_'])==2]
    resources=[r for r in records if int(r['type_'])==4]
    def date(value):
        if isinstance(value,(int,float)) or str(value).isdigit():return int(value)
        return int(datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=timezone.utc).timestamp()*1000)
    def ordered(rows):return sorted(rows,key=lambda x:json.dumps(x,sort_keys=True))
    def tags():
        return ordered([[name(by_id[r['note_id']]),name(by_id[r['tag_id']])] for r in records if int(r['type_'])==6])
    def links():
        found=[]
        for n in notes:
            for rid in re.findall(r'\]\(:/([a-f0-9]{32})\)',n['body']):
                assert rid in aliases,'unresolved exported/imported link'
                found.append([name(n),aliases[rid]])
        return ordered(found)
    def metadata():
        return ordered([{'title':name(n),'author':n['author'],
                         'created':date(n['user_created_time']),'updated':date(n['user_updated_time']),
                         'is_todo':int(n['is_todo']),'todo_due':int(n['todo_due'])} for n in notes])
    return aspects(notes=lambda:ordered([{'title':name(n),'body':text(n['body'])} for n in notes]),
                   folders=lambda:ordered([[name(n),name(by_id[n['parent_id']]) if n['parent_id'] else ''] for n in folders]),
                   metadata=metadata,tags=tags,links=links,
                   resources=lambda:ordered([{'title':name(r),'mime':r['mime'],
                       'sha256':hashlib.sha256(resource_bytes(r)).hexdigest()} for r in resources]))


def exported(c,spec):
    listing=c.broker.call({'op':'list_files','area':'outbox'})['files']
    blobs={x['name']:base64.b64decode(c.broker.call({'op':'download','area':'outbox','filename':x['name']})['body_base64']) for x in listing}
    if spec['format']=='jex':
        with tarfile.open(fileobj=io.BytesIO(blobs[spec['filename']])) as archive:
            blobs={x.name:archive.extractfile(x).read() for x in archive if x.isfile()}
    records=[]
    for name,data in blobs.items():
        if not name.endswith('.md'):continue
        text=data.decode('utf-8');marker=re.search(r'^id: [^\n]+\n',text,re.M)
        if not marker:continue
        metadata=dict(re.findall(r'^([a-z_]+): ?(.*)$',text[marker.start():].lstrip('\n'),re.M))
        title,_,body=text[:marker.start()].rstrip('\n').partition('\n\n')
        metadata.update(title=title,body=body);records.append(metadata)
    assert sum(r['type_']=='1' for r in records)==2,'backup must contain both notes'
    def resource_bytes(r):
        matches=[v for k,v in blobs.items() if k.split('/')[-1].split('.')[0]==r['id'] and not k.endswith('.md')]
        assert len(matches)==1,'attachment bytes missing or ambiguous'
        return matches[0]
    return normalized(records,resource_bytes)


def imported(c,markdown=False):
    originals={c.values[x]['id'] for x in ('Trip plan','Trip log')}
    notes=[x for x in c.all('/notes',fields='id,title,body,parent_id,author,user_created_time,user_updated_time,is_todo,todo_due')
           if x['title'] in ('Trip plan','Trip log') and x['id'] not in originals]
    assert len(notes)==2,'both imported notes must exist'
    records=[{**x,'type_':1} for x in notes];seen=set(x['id'] for x in notes)
    for n in notes:
        parent=n['parent_id']
        while parent and parent not in seen:
            folder=c.call('GET','/folders/'+parent,query={'fields':'id,title,parent_id'})['body']
            seen.add(parent);records.append({**folder,'type_':2});parent=folder['parent_id']
        for tag in c.all('/notes/'+n['id']+'/tags',fields='id,title'):
            if tag['id'] not in seen:records.append({**tag,'type_':5});seen.add(tag['id'])
            records.append({'id':n['id']+tag['id'],'type_':6,'note_id':n['id'],'tag_id':tag['id']})
        for rid in re.findall(r'\]\(:/([a-f0-9]{32})\)',n['body']):
            if rid in seen:continue
            response=c.call('GET','/resources/'+rid,query={'fields':'id,title,mime'},ok=False)
            if response['status']==404:continue
            assert response['status']==200
            records.append({**response['body'],'type_':4});seen.add(rid)
    if markdown:
        # Directory import adds its selected outer directory as a container;
        # compare the exported tree rooted at Workbench, below that wrapper.
        wrappers={r['id'] for r in records if r['type_']==2 and r['title']=='outbox'}
        records=[r for r in records if r['id'] not in wrappers]
        for r in records:
            if r.get('parent_id') in wrappers:r['parent_id']=''
    def resource_bytes(r):
        response=c.call('GET','/resources/'+r['id']+'/file')
        return base64.b64decode(response['body_base64']) if 'body_base64' in response else response['body'].encode()
    return normalized(records,resource_bytes)
