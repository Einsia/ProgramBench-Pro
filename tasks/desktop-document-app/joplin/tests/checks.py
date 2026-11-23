"""Observe saved notes, relationships, clipboard and exports through public RPC."""
import base64
import hashlib
import io
import json
import re
import tarfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from harness import aspects,checked


def notes(c):
    return c.all('/notes', fields='id,title,body,parent_id,is_todo,todo_due,todo_completed,source_url,markup_language,deleted_time,author,user_created_time,user_updated_time',
                 query={'include_deleted': 1})


def find_note(c, title):
    matches = [n for n in notes(c) if n['title'] == title]
    if len(matches)>1 and title in c.values:
        matches=[n for n in matches if n['id']==c.values[title]['id']]
    assert len(matches) == 1, f'expected one note titled {title!r}, found {len(matches)}'
    return matches[0]


class Text(HTMLParser):
    blocks={'p','div','li','ul','ol','blockquote','h1','h2','h3','h4','h5','h6','pre','table','tr','td','th','br','hr','dl','dt','dd'}
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ('style','script','head'): self.hidden += 1
        elif tag in self.blocks and not self.hidden:self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('style','script','head'): self.hidden = max(0,self.hidden-1)
        elif tag in self.blocks and not self.hidden:self.parts.append(' ')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def plain(body, language=1):
    if language == 1:
        from markdown_it import MarkdownIt
        body=MarkdownIt('commonmark', {'html':True}).enable('table').render(body)
    parser=Text();parser.feed(body)
    return ' '.join(''.join(parser.parts).split())


def text_normal(value):
    return value.replace('\r\n','\n').rstrip('\n')


def files(c):
    return c.broker.call({'op':'list_files','area':'outbox'})['files']


def fetch(c, name):
    return base64.b64decode(c.broker.call({'op':'download','area':'outbox','filename':name})['body_base64'])


def exported(c, spec):
    deadline=time.monotonic()+30; before=None
    while time.monotonic()<deadline:
        found=files(c); signature=[(f['name'],f['size']) for f in found]
        if signature and signature==before:break
        before=signature;time.sleep(.4)
    assert found,'no export was written'
    fmt=spec['format']; filename=spec.get('filename')
    if filename:
        assert any(f['name']==filename for f in found),'the requested export path is missing'
    blobs={f['name']:fetch(c,f['name']) for f in found}
    if fmt=='jex':
        with tarfile.open(fileobj=io.BytesIO(blobs[filename])) as archive:
            blobs={x.name:archive.extractfile(x).read() for x in archive if x.isfile()}
    if fmt in ('jex','raw'):
        rows=[]
        for name,data in blobs.items():
            if not name.endswith('.md'):continue
            text=data.decode('utf-8'); marker=re.search(r'\n\nid: [^\n]+\n',text)
            if not marker:continue
            content=text[:marker.start()];props=dict(re.findall(r'^([a-z_]+): ?(.*)$',text[marker.start()+2:],re.M))
            if props.get('type_')!='1':continue
            title,_,body=content.partition('\n\n')
            rows.append({'title':title,'body':text_normal(body),'is_todo':int(props.get('is_todo','0'))})
        assert rows,'the export contains no note records'
        return {'notes':sorted(rows,key=lambda x:x['title'])}
    if fmt.startswith('html'):
        texts=[]
        for name,data in blobs.items():
            if name.endswith(('.html','.htm')):texts.append(plain(data.decode('utf-8'),2))
        assert texts,'the export contains no HTML documents'
        return {'documents':sorted(texts)}
    if fmt in ('markdown','front-matter'):
        texts=[]
        for name,data in blobs.items():
            if name.endswith('.md'):
                text=data.decode('utf-8')
                if fmt=='front-matter':
                    import yaml
                    assert text.startswith('---\n'),'Front Matter YAML header is missing'
                    head,separator,text=text[4:].partition('\n---\n')
                    assert separator,'Front Matter YAML header is unterminated'
                    metadata=yaml.safe_load(head)
                    assert isinstance(metadata,dict),'Front Matter is not a metadata mapping'
                    values={k:metadata[k] for k in ('title','author','created','updated','tags')}
                    values['created']=date_millis(values['created'])
                    values['updated']=date_millis(values['updated'])
                    values['tags']=sorted(values['tags'])
                    if spec.get('metadata'):expect_metadata(values,spec['metadata'])
                    texts.append({'body':text_normal(text).strip(),'metadata':values})
                else:texts.append(text_normal(text).strip())
        assert texts,'the export contains no Markdown notes'
        return {'documents':sorted(texts,key=lambda x:json.dumps(x,sort_keys=True))}
    if fmt=='pdf':
        from pypdf import PdfReader
        document=PdfReader(io.BytesIO(blobs[filename]))
        return {'pages':len(document.pages),'text':' '.join(' '.join(p.extract_text() for p in document.pages).split())}
    raise AssertionError('unknown export format')


def date_millis(value):
    if isinstance(value,str):value=datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return int(value.timestamp()*1000)


def expect_metadata(value,wanted):
    for field,expected in wanted.items():
        assert value[field]==expected,f'metadata {field}: {value[field]!r} != {expected!r}'


def edge_semantics(edges):
    """An edge's direction is independent of its stored source/target ordering."""
    output=[]
    for edge in edges:
        arrows=[]
        if edge['fromEnd']=='arrow':arrows.append(edge['from'])
        if edge['toEnd']=='arrow':arrows.append(edge['to'])
        output.append({'nodes':sorted([edge['from'],edge['to']]),'arrows':sorted(arrows),'label':edge['label']})
    return sorted(output,key=lambda x:json.dumps(x,sort_keys=True))


def observe(c, item):
    kind=item['kind']
    if kind.startswith('archive-'):
        import archives
        return archives.exported(c,item) if kind=='archive-export' else archives.imported(c,markdown=item.get('format')=='markdown')
    if kind=='markdown-tree-export':
        listed=files(c);paths=[x['name'] for x in listed]
        markdown=[p for p in paths if p.endswith('.md')]
        assert len(markdown)==2,'both notes must be exported as Markdown'
        nested=next(p for p in markdown if 'Trip plan' in p)
        assert 'Field trips' in nested.split('/'),'child notebook path is missing'
        docs={p:fetch(c,p).decode() for p in markdown}
        assert any('Observed three trees.' in text for text in docs.values())
        assert any('Pack a map and water.' in text for text in docs.values())
        return {kind:{'paths':sorted(markdown),'bodies':sorted(plain(t) for t in docs.values())}}
    if kind=='enex-complete':
        import fixtures
        source=find_note(c,'ENEX source');target=find_note(c,'ENEX target');both=[source,target]
        def content():
            values=[plain(n['body'],n['markup_language']) for n in both]
            assert 'A bold field observation.' in values[0]
            assert 'Destination survey notes.' in values[1]
            from bs4 import BeautifulSoup
            from markdown_it import MarkdownIt
            soup=BeautifulSoup(MarkdownIt().render(source['body']),'html.parser')
            assert any(x.get_text()=='bold' for x in soup.find_all('strong'))
            return values
        def tags():
            value=[sorted(x['title'] for x in c.all('/notes/'+n['id']+'/tags',fields='title')) for n in both]
            return checked(value,[['botany','fieldwork'],['planning']])
        def resource():
            rows=c.all('/notes/'+source['id']+'/resources',fields='id,mime')
            assert len(rows)==1
            response=c.call('GET','/resources/'+rows[0]['id']+'/file')
            raw=base64.b64decode(response['body_base64']);assert raw==fixtures.png()
            return {'mime':rows[0]['mime'],'sha256':hashlib.sha256(raw).hexdigest()}
        return aspects(titles=lambda:[n['title'] for n in both],content=content,
            authors=lambda:checked([n['author'] for n in both],['Ada Lovelace','Grace Hopper']),
            dates=lambda:checked([[n['user_created_time'],n['user_updated_time']] for n in both],
                                 [[1704164645000,1738555506000],[1704251045000,1738641906000]]),
            tags=tags,resource=resource,link=lambda:checked('](:/'+target['id']+')' in source['body'],True))
    if kind=='history-copy':
        rows=[n for n in notes(c) if n['title']==item['title']]
        original=[n for n in rows if n['body']==item['current']]
        restored=[n for n in rows if n['body']==item['old']]
        assert len(original)==len(restored)==1,'current and restored versions must both exist'
        folder=c.call('GET','/folders/'+restored[0]['parent_id'],query={'fields':'title'})['body']['title']
        assert folder=='Restored Notes'
        return {kind:{'original':original[0]['body'],'restored':restored[0]['body'],'folder':folder}}
    if kind in ('canvas-edges','canvas-promoted'):
        n=find_note(c,item['title']);canvas=json.loads(re.search(r'```jsoncanvas\s*\n(.*?)\n```',n['body'],re.S)[1])
        nodes={x['id']:x for x in canvas['nodes']}
        if kind=='canvas-promoted':
            target=find_note(c,item['target'])
            value=any(x['type']=='file' and x['file']==':/'+target['id'] for x in nodes.values());assert value
        else:
            value=sorted([{'from':nodes[x['fromNode']]['text'],'to':nodes[x['toNode']]['text'],
                           'fromEnd':x.get('fromEnd','none'),'toEnd':x.get('toEnd','arrow'),'label':x.get('label','')}
                          for x in canvas['edges']],key=lambda x:json.dumps(x,sort_keys=True))
            value=edge_semantics(value)
            assert value==edge_semantics(item['edges']),value
        return {kind:value}
    if kind=='note':
        if item.get('selector')=='new-copy':
            seeded={x['id'] for x in c.values.values() if isinstance(x,dict) and 'id' in x}
            matches=[n for n in notes(c) if n['id'] not in seeded]
            assert len(matches)==1,'one additional duplicate note is required'
            n=matches[0]
        else:n=find_note(c,item['title'])
        readers={}
        for field in item['values']:
            def read(field=field):
                if field=='parent':return c.call('GET','/folders/'+n['parent_id'],query={'fields':'title'})['body']['title']
                if field=='deleted':return n['deleted_time']>0
                if field=='completed':return n['todo_completed']>0
                if field=='body':return text_normal(n['body'])
                return n[field]
            readers[field]=read
        return aspects(**readers)
    if kind=='folder':
        folders=c.all('/folders',fields='id,title,parent_id');matches=[f for f in folders if f['title']==item['title']]
        assert len(matches)==1,'notebook title is missing or ambiguous'
        parent=matches[0]['parent_id'];parent_title=next((f['title'] for f in folders if f['id']==parent),'')
        assert parent_title==item['parent'],'notebook has the wrong parent'
        return {kind:{'title':matches[0]['title'],'parent':parent_title}}
    if kind=='note-count':
        count=sum(n['title']==item['title'] for n in notes(c));assert count==item['count']
        return {kind:count}
    if kind=='tags':
        n=find_note(c,item['title']);rows=c.all('/notes/'+n['id']+'/tags',fields='title')
        tags=sorted(t['title'] for t in rows);assert tags==sorted(item['tags'])
        return {kind:tags}
    if kind=='clipboard':
        value=c.broker.call({'op':'clipboard_text'})['text'];assert text_normal(value)==item['text']
        return {kind:text_normal(value)}
    if kind in ('plain-body','markup','checklist','indented','note-link','attachments','table'):
        n=find_note(c,item['title'])
        if kind=='plain-body':
            text=plain(n['body'],n['markup_language']);assert text==item['text'];value=text
        elif kind=='markup':
            from markdown_it import MarkdownIt
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(MarkdownIt().render(n['body']),'html.parser')
            texts=[' '.join(x.get_text().split()) for x in soup.find_all(item['tag'])]
            if item.get('also'):
                texts=[' '.join(x.get_text().split()) for x in soup.find_all(item['tag'])
                       if x.find_parent(item['also']) or x.find(item['also'])]
            assert item['text'] in texts,'requested formatting is missing';value=texts
        elif kind=='table':
            from markdown_it import MarkdownIt
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(MarkdownIt().enable('table').render(n['body']),'html.parser')
            value=[[' '.join(cell.get_text().split()) for cell in row.find_all(['th','td'])] for row in soup.find_all('tr')]
            assert value==item['rows'],value
        elif kind=='checklist':
            value=re.findall(r'^\s*[-*+] \[[xX]\] (.*)$',n['body'],re.M)
            assert sorted(value)==sorted(item['checked'])
        elif kind=='indented':
            value=any(re.match(r'^\s+'+re.escape(item['text'])+r'$',line) for line in n['body'].splitlines());assert value
        elif kind=='note-link':
            destination=find_note(c,item['target'])
            assert '](:/'+destination['id']+')' in n['body'],'internal link target is missing';value=item['target']
        else:
            rows=c.all('/notes/'+n['id']+'/resources',fields='id,title,mime,size')
            value=sorted(x['title'] for x in rows);assert value==sorted(item['names'])
        return {kind:value}
    if kind=='imported':
        n=find_note(c,item['title']);text=plain(n['body'],n['markup_language'])
        assert item['text'] in text,'imported content is missing'
        return {kind:{'title':n['title'],'text':text}}
    if kind=='imported-copy':
        rows=notes(c);matches=[n for n in rows if item['text'] in plain(n['body'],n['markup_language'])]
        assert len(matches)>=item.get('minimum',2),'the expected reimported content is not available'
        return {kind:sorted(plain(n['body'],n['markup_language']) for n in matches)}
    if kind=='metadata-copies':
        matches=[n for n in notes(c) if n['title']==item['title']]
        assert len(matches)==item.get('count',2),'the metadata-bearing copy is missing'
        values=[]
        for n in matches:
            value={'title':n['title'],'author':n['author'],'created':n['user_created_time'],
                   'updated':n['user_updated_time'],
                   'tags':sorted(x['title'] for x in c.all('/notes/'+n['id']+'/tags',fields='title'))}
            expect_metadata(value,item['metadata']);values.append(value)
        return {kind:values}
    if kind=='export':return {kind:exported(c,item)}
    if kind=='whiteboard':
        n=find_note(c,item['title']);match=re.search(r'```jsoncanvas\s*\n(.*?)\n```',n['body'],re.S)
        assert match,'the note has no whiteboard document'
        canvas=json.loads(match[1]);nodes=canvas['nodes']
        texts=sorted(x['text'] for x in nodes if x['type']=='text')
        groups=sum(x['type']=='group' for x in nodes)
        links=[]
        for x in nodes:
            if x['type']=='file':
                assert x['file'].startswith(':/')
                links.append(c.call('GET','/notes/'+x['file'][2:],query={'fields':'title'})['body']['title'])
        assert texts==sorted(item['texts']) and groups==item['groups'] and sorted(links)==sorted(item['links'])
        return {kind:{'texts':texts,'groups':groups,'links':sorted(links)}}
    raise AssertionError('unknown check '+kind)
