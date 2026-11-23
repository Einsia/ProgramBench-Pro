"""Semantic projections of public embedding messages and user-generated document files."""
import base64
from html.parser import HTMLParser
import json
import math
import re
from urllib.parse import unquote

VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
BLOCK={'root','p','div','section','article','blockquote','ul','ol','li','dl','dt','dd','table','thead','tbody','tfoot','tr','td','th','h1','h2','h3','h4','h5','h6','pre'}


class Parser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root=['root',{},[]];self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        node=[tag,dict(attrs),[]];self.stack[-1][2].append(node)
        if tag not in VOID:self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i][0]==tag:self.stack=self.stack[:i];break
    def handle_data(self,text):self.stack[-1][2].append(text)


def html_projection(text):
    assert isinstance(text,str), 'The embedding message has no HTML string.'
    parser=Parser()
    try:parser.feed(text);parser.close()
    except (ValueError,TypeError) as exc:raise AssertionError('The generated HTML could not be read.') from exc
    ids={}
    def visit(n):
        if isinstance(n,str):return
        if n[1].get('id'):ids.setdefault(n[1]['id'],'anchor-'+str(len(ids)+1))
        for c in n[2]:visit(c)
    visit(parser.root)
    def norm(n,pre=False,marks=()):
        if isinstance(n,str):
            if not n:return []
            return [{'text':n if pre else re.sub(r'[ \t\r\n\f]+',' ',n),'marks':sorted(set(marks))}]
        tag,attrs,children=n;classes=(attrs.get('class') or '').split()
        if tag in {'head','meta','link'}:return []
        tag={'b':'strong','i':'em','s':'del','strike':'del'}.get(tag,tag)
        mathclass=next((x for x in classes if x in ('katex--inline','katex--display')),None)
        if mathclass:tag='math-display' if mathclass.endswith('display') else 'math-inline'
        if 'task-list-item-checkbox' in classes and tag=='span':
            return [{'tag':'checkbox','attrs':{'checked':'checked' in classes},'children':[]}]
        if tag=='input' and attrs.get('type')=='checkbox':
            return [{'tag':'checkbox','attrs':{'checked':'checked' in attrs},'children':[]}]
        a={}
        for k in ('href','src','alt','title','start','reversed','type','colspan','rowspan','width','height','align',*[k for k in attrs if k.startswith('on')]):
            if k in attrs:
                v=attrs[k]
                if k=='href' and v and v.startswith('#'):
                    anchor=unquote(v[1:])
                    v='#'+ids[anchor] if anchor in ids else '#'+anchor
                if k in ('width','height','colspan','rowspan','start'):
                    try:v=float(v);v=int(v) if v.is_integer() else v
                    except (ValueError,TypeError,OverflowError):pass
                a[k]=v
        if tag in ('td','th') and 'align' not in a:
            match=re.search(r'text-align\s*:\s*(left|center|right)',attrs.get('style') or '')
            if match:a['align']=match[1]
        if tag=='code':
            lang=next((x[9:] for x in classes if x.startswith('language-')),None)
            if lang:a['language']=lang
        emphasis=tag in {'strong','em','del','mark','sub','sup'} and not a
        next_marks=(*marks,tag) if emphasis else marks
        preserve=pre or tag in {'pre','code','math-inline','math-display'}
        cs=[item for c in children for item in norm(c,preserve,next_marks)]
        # Inline whitespace is a text-flow property. Spaces survive between
        # words, but not at a block/line boundary. NBSP is never collapsible.
        if not preserve and not emphasis:
            cs=normalize_flow(cs,edge=tag in BLOCK or tag in {'html','body'})
        else:cs=merge_text(cs)
        if emphasis or tag in {'root','html','body','tbody'} or (tag=='div' and 'table-wrapper' in classes) or (tag=='span' and not mathclass and not a):return cs
        if tag=='div' and not a and cs and all(c.get('tag') in BLOCK for c in cs):return cs
        return [{'tag':tag,'attrs':a,'children':cs}]
    return norm(parser.root)


def merge_text(items):
    out=[]
    for item in items:
        if 'text' in item and not item['text']:continue
        if out and 'text' in item and 'text' in out[-1] and {k:v for k,v in item.items() if k!='text'}=={k:v for k,v in out[-1].items() if k!='text'}:
            out[-1]={**item,'text':out[-1]['text']+item['text']}
        else:out.append(item)
    return out


def normalize_flow(items,edge):
    def inline(items,within=()):
        for item in items:
            if item.get('tag') in {'a','abbr','kbd','samp','var','u','small','big'}:
                yield from inline(item['children'],(*within,{'tag':item['tag'],'attrs':item['attrs']}))
            else:
                path=[*within,*item.get('within',[])]
                yield {**item,**({'within':path} if path else {})}
    out=[];pending=False;line_start=edge
    for item in inline(items):
        if 'text' in item:
            # Style on a collapsed space is immaterial; give it one canonical
            # position between visible runs, outside either emphasis set.
            for part in re.split('( )',item['text']):
                if part==' ':pending=True
                elif part:
                    if pending and not line_start:out.append({'text':' ','marks':[]})
                    out.append({**item,'text':part});pending=False;line_start=False
        else:
            boundary=item['tag'] in BLOCK or item['tag']=='br'
            if pending and not line_start and not boundary:out.append({'text':' ','marks':[]})
            out.append(item);pending=False;line_start=boundary
    if pending and not edge and not line_start:out.append({'text':' ','marks':[]})
    return merge_text(out)


def parsed_html(text):
    parser=Parser();parser.feed(text);parser.close();return parser.root


def walk(node):
    if not isinstance(node,str):
        yield node
        for child in node[2]:yield from walk(child)


def node_text(node):
    return node if isinstance(node,str) else ''.join(node_text(c) for c in node[2])


def export_projection(text,format):
    if format=='plainText':return {'text':text.replace('\r\n','\n')}
    if format=='jekyllSite':
        import yaml
        parts=re.split(r'^---[ \t]*$',text,flags=re.M)
        assert len(parts)>=3,'The Jekyll export has no YAML front matter.'
        properties=yaml.safe_load(parts[1])
        assert isinstance(properties,dict) and properties,'Jekyll front matter is empty.'
        return {'properties':json.loads(json.dumps(properties,default=lambda v:v.isoformat())),
                'document':html_projection('---'.join(parts[2:]))}
    out={'document':html_projection(text)}
    if format in {'styledHtml','styledHtmlWithToc'}:
        nodes=list(walk(parsed_html(text)))
        styled=any((n[0]=='link' and 'stylesheet' in (n[1].get('rel') or '').split() and n[1].get('href'))
                   or (n[0]=='style' and re.search(r'[^{}]+\{[^{}]*:[^{}]+\}',node_text(n)))
                   or re.search(r'[\w-]+\s*:\s*[^;]+',n[1].get('style') or '') for n in nodes)
        assert styled,'The styled export supplies no stylesheet or inline styling.'
        out['styled']=True
        if format=='styledHtmlWithToc':
            headings={n[1]['id']:(int(n[0][1]),node_text(n)) for n in nodes if re.fullmatch('h[1-6]',n[0]) and n[1].get('id')}
            links=[]
            for n in nodes:
                href=n[1].get('href') or ''
                if n[0]=='a' and href.startswith('#') and unquote(href[1:]) in headings:
                    heading=headings[unquote(href[1:])]
                    if node_text(n).strip()==heading[1].strip():links.append(heading)
            assert links,'The contents links do not resolve to matching document headings.'
            out['toc']=[{'level':level,'text':name} for level,name in links]
    return out


def compare(actual,expected,path='observation'):
    if isinstance(expected,dict):
        assert isinstance(actual,dict),path+': expected an object'
        if path.endswith('.attrs') or 'tag' in expected or {'text','marks'}<=set(expected):
            assert set(actual)==set(expected),path+': semantic attributes differ'
        for k,e in expected.items():
            assert k in actual,path+': missing '+k
            compare(actual[k],e,path+'.'+k)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),path+': different number of items'
        for i,(a,e) in enumerate(zip(actual,expected)):compare(a,e,f'{path}[{i}]')
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        assert isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual) and abs(actual-expected)<1e-6,path+': different number'
    else:assert actual==expected,path+': expected '+repr(expected)[:160]+', got '+repr(actual)[:160]


def source_control(snap):
    choices=[c for c in snap.get('controls',[]) if c.get('editable') or c.get('tag')=='textarea']
    if not choices:
        choices=[c for c in snap.get('controls',[]) if c.get('role')=='textbox' and c.get('bounds',[0,0,0,0])[3]>100]
    assert choices,'No visible document editor was found.'
    return max(choices,key=lambda c:c.get('bounds',[0,0,0,0])[2]*c.get('bounds',[0,0,0,0])[3])


def source_text(broker):
    c=source_control(broker.call({'op':'snapshot'}))
    assert isinstance(c.get('value'),str) and not c.get('value_truncated'),'Document source is unavailable or truncated.'
    return c['value'].replace('\r\n','\n')


def take_download(ctx,suffix):
    cache=ctx.state.setdefault('downloads',{})
    if suffix not in cache:
        snap=ctx.broker.call({'op':'snapshot'})
        files=[f for f in snap.get('downloads',[]) if f.get('filename','').lower().endswith(suffix)]
        assert files,'No '+suffix+' download was produced.'
        item=ctx.broker.call({'op':'download','ref':files[-1]['ref']})
        assert not item.get('truncated'),'The download was truncated.'
        cache[suffix]=(item['filename'],base64.b64decode(item['body_base64']))
    return cache[suffix]


def observe(ctx,cp,spec):
    kind=spec['type']
    if ctx.episode['execution']=='program':
        if 'program_error' in ctx.state:raise AssertionError(ctx.state['program_error'])
        if 'result' not in ctx.state:
            try:
                args={'op':'embed_open','text':cp['text'],'name':cp.get('name','Document'),'properties':cp.get('properties','')}
                result=ctx.broker.call(args)
                if cp.get('selection') is not None:
                    control=source_control(ctx.broker.call({'op':'snapshot'}));start,end=cp['selection']
                    ctx.broker.call({'op':'select_text','target':{'ref':control['ref']},'start':start,'end':end})
                for action in cp.get('actions',[]):ctx.broker.call(action)
                if cp.get('actions'):result=ctx.broker.call({'op':'embed_read'})
                assert isinstance(result,dict) and isinstance(result.get('text'),str) and isinstance(result.get('html'),str),'No complete embedding result.'
                ctx.state['result']=result
            except Exception as exc:
                # Runtime connection failures remain infrastructure faults, per kit contract.
                from evaluation.contract import InfrastructureError
                if isinstance(exc,InfrastructureError):raise
                ctx.state['program_error']=str(exc)[:400]
                raise AssertionError(ctx.state['program_error']) from exc
        result=ctx.state['result']
        if kind=='html':return {'document':html_projection(result['html'])}
        if kind=='text':return {'text':result['text'].replace('\r\n','\n')}
        if kind=='name':return {'name':result.get('name')}
        if kind=='properties':
            assert isinstance(result.get('properties'),dict),'No computed file properties.'
            return {'properties':result['properties']}
    if kind=='render-source':
        text=source_text(ctx.broker)
        if ctx.record and cp.get('exact_source') is not None:
            assert text.rstrip('\n')==cp['exact_source'].rstrip('\n'),'The reference operation did not produce the required source.'
        result=ctx.broker.call({'op':'embed_open','text':text,'name':'Observed document'})
        assert isinstance(result.get('html'),str),'No HTML was emitted for the resulting document.'
        return {'document':html_projection(result['html'])}
    if kind=='backup':
        _,data=take_download(ctx,'.json')
        try:items=json.loads(data)
        except (ValueError,UnicodeError):raise AssertionError('Not a readable workspace backup.')
        assert isinstance(items,dict) and items,'The backup contains no workspace data.'
        import yaml
        def parent_path(ident,seen=()):
            assert ident not in seen,'Cyclic folder hierarchy in the backup.'
            if not ident:return []
            parent=items.get(ident,{})
            if parent.get('type')!='folder':return ['Trash'] if ident=='trash' else []
            return parent_path(parent.get('parentId'),(*seen,ident))+[parent.get('name')]
        files=[];folders=[]
        for ident,item in items.items():
            if not isinstance(item,dict):continue
            if item.get('type')=='folder':folders.append(parent_path(ident))
            if item.get('type')=='file':
                content=items.get(ident+'/content',{})
                assert isinstance(item.get('name'),str) and isinstance(content.get('text'),str),'The backup contains an unreadable document.'
                props=yaml.safe_load(content.get('properties') or '') or {}
                files.append({'name':item['name'],'text':content['text'],'path':parent_path(item.get('parentId')),
                              'properties':json.loads(json.dumps(props,default=lambda v:v.isoformat()))})
        assert files,'The backup contains no documents.'
        files.sort(key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False));folders.sort()
        part=spec.get('part')
        if part=='folders':return {'folders':folders}
        if part=='names':return {'files':[{'name':f['name'],'path':f['path']} for f in files]}
        if part=='contents':return {'files':[{'name':f['name'],'path':f['path'],'text':f['text']} for f in files]}
        if part=='properties':return {'files':[{'name':f['name'],'path':f['path'],'properties':f['properties']} for f in files]}
        return {'files':[{'name':f['name'],'text':f['text']} for f in files]}
    if kind=='conversion':
        text=source_text(ctx.broker)
        style=spec['style']
        patterns={
          'setext':r'Harbor\n=+\n+Tide\n-+', 'bullet':r'^\+ +North\n\+ +South',
          'rule':r'^\*\*\*$', 'indented':r'^ {4}first\n {6}second',
          'fence':r'^~~~[^\n]*\nfirst\n  second', 'emphasis':r'(?<!\*)\*Tide\*(?!\*)',
          'strong':r'__Harbor__', 'reference':r'\[Harbor\]\[[^\]]+\]',
          'collapsed':r'\[Harbor\]\[\]', 'shortcut':r'\[Harbor\](?![\[(])'}
        assert re.search(patterns[style],text,re.M),'The converted source does not use the selected '+style+' setting.'
        result=ctx.broker.call({'op':'embed_open','text':text,'name':'Converted document'})
        return {'style_applied':True,'document':html_projection(result['html'])}
    if kind=='embedding':
        result=ctx.broker.call({'op':'embed_read'})
        key=spec['field']
        assert key in result,'The embedding result is missing '+key
        return {key:html_projection(result[key]) if key=='html' else result[key]}
    if kind=='source':
        text=source_text(ctx.broker).rstrip('\n')
        if ctx.record and cp.get('exact_source') is not None:
            assert text==cp['exact_source'].rstrip('\n'),'Entered source differs from the goal input.'
        return {'text':text}
    if kind=='download':
        filename,data=take_download(ctx,spec['suffix']);out={}
        if spec.get('name'):out['filename']=filename
        text=data.decode('utf-8-sig')
        out['content']=export_projection(text,spec.get('format','plainHtml')) if spec['suffix']=='.html' else text.replace('\r\n','\n').rstrip('\n')
        return out
    raise ValueError('Unknown check '+kind)
