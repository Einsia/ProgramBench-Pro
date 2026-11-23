"""HTML document semantics, independent of incidental markup and resource names."""
import base64
import hashlib
import re
from urllib.parse import unquote, urlsplit
from pathlib import Path
from lxml import html as tree
import artifacts as a


def parse(text):
    try:
        return tree.document_fromstring(text, parser=tree.HTMLParser(no_network=True))
    except (ValueError, tree.etree.ParserError) as exc:
        raise a.Unreadable('the HTML document cannot be parsed') from exc


def classes(node):
    return set((node.get('class') or '').split())


def heading(node):
    return isinstance(node.tag, str) and re.fullmatch('h[1-6]', node.tag) is not None


def titles(root):
    return [e for e in root.iter() if heading(e) and ('title' in classes(e) or e.get('data-node-id') is not None)]


def scope(root, title):
    for e in title.iterancestors():
        if 'page' in classes(e) or e.tag in ('article', 'section'):
            if sum(1 for h in titles(e))==1:
                return e
    return next(iter(root.xpath('//main | //body')), root)


def kind(text):
    root=parse(text); ts=titles(root)
    if any(any(c.startswith('level-') for c in classes(h)) or h.get('data-level') for h in ts):
        return 'single'
    if ts or root.xpath('//main//h1 | //article//h1'):return 'page'
    if root.xpath('//ul//a[@href or @onclick] | //ol//a[@href or @onclick]'):return 'index'
    if root.xpath('//h1'):return 'page'
    raise a.Unreadable('HTML contains no document content or node index')


def target(link):
    href=link.get('href') or ''
    if href in ('','#'):
        match=re.search(r'changeFrame\(\s*([\'"])(.*?)\1\s*\)', link.get('onclick') or '')
        if match:href=match.group(2)
    return a.node_page_name(unquote(href)) if not urlsplit(href).scheme else href


def references(text):
    """Only resources belonging to node content, not navigation artwork or app assets."""
    root=parse(text);ts=titles(root)
    if not ts:
        if kind(text)=='index':return []
        ts=root.xpath('//main//h1 | //article//h1 | //body//h1')
    result=[]
    for title in ts:
        for node in scope(root,title).xpath('.//img[@src] | .//a[@href]'):
            result.append(node.get('src') if node.tag=='img' else node.get('href'))
    return result


def resource(folder, ref):
    if ref.startswith('data:'):
        header,_,encoded=ref.partition(',')
        return base64.b64decode(encoded) if ';base64' in header else unquote(encoded).encode()
    if urlsplit(ref).scheme:
        raise a.Unreadable('exported resources must be local or embedded')
    base=Path(folder).resolve(); path=(base/unquote(urlsplit(ref).path)).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise a.Unreadable('an exported resource is missing or leaves the document folder')
    return path.read_bytes()


def project_body(container, title, folder, section_anchor=None):
    items=[]
    def emit(item):
        if item==['break']:
            if items and items[-1]!=['break']:items.append(item)
        elif item[0]=='text' and items and items[-1][0]=='text' and items[-1][2]==item[2]:
            items[-1][1]+=item[1]
        else:items.append(item)
    def text(value,attrs):
        if not value:return
        value=re.sub(r'\s+',' ',value)
        if value.strip():emit(['text',a.nfc(value),dict(sorted(attrs.items()))])
        elif items and items[-1][0]=='text':emit(['text',' ',dict(sorted(attrs.items()))])
    def raw(node):
        # Preserve line breaks in code, including explicit HTML br elements.
        out=node.text or ''
        for c in node:
            out+=('\n' if c.tag=='br' else raw(c))+(c.tail or '')
        return out.replace('\r\n','\n')
    def walk(node,attrs,lists):
        if node is title:return
        tag=node.tag
        if not isinstance(tag,str) or tag in ('script','style','head','nav','button','iframe'):return
        attrs=dict(attrs)
        if tag in a.STYLE_TAGS:
            key,value=a.STYLE_TAGS[tag];attrs[key]=value
        attrs.update(a.css(node.get('style')))
        if attrs.get('justification')=='left':attrs.pop('justification')
        if tag=='br':emit(['break']);return
        if tag=='hr':emit(['break']);emit(['rule']);emit(['break']);return
        if tag in ('ul','ol'):
            emit(['break'])
            start=int(node.get('start','1'));reverse=node.get('reversed') is not None
            if reverse and node.get('start') is None:start=len(node.findall('li'))
            marker=node.get('type') or ('1' if tag=='ol' else 'disc')
            emit(['list-start',tag,marker,reverse])
            number=start
            for child in node:
                if child.tag=='li':
                    number=int(child.get('value',str(number)))
                    emit(['item',tag,len(lists)+1,number if tag=='ol' else None])
                    walk(child,attrs,lists+[tag]);number+=-1 if reverse else 1
                else:walk(child,attrs,lists+[tag])
            emit(['list-end',tag]);emit(['break']);return
        if tag=='pre':
            emit(['break']);emit(['code',a.nfc(raw(node))]);emit(['break']);return
        if tag=='table':
            links=node.xpath('.//a[@href]')
            if 'inline-table' in (node.get('style') or '') and links:
                link=links[0];ref=link.get('href');data=resource(folder,ref)
                emit(['file',a.nfc(''.join(link.itertext()).strip()),hashlib.sha256(data).hexdigest()]);return
            rows=[]
            for row in node.xpath('./tr | ./thead/tr | ./tbody/tr | ./tfoot/tr'):
                rows.append([a.nfc(re.sub(r'\s+',' ',''.join(c.itertext())).strip()) for c in row if c.tag in ('th','td')])
            emit(['break']);emit(['table',rows]);emit(['break']);return
        if tag=='img':
            data=resource(folder,node.get('src',''));info=a.png_info(data)
            emit(['image',[info['width'],info['height'],info['sha256']],attrs.get('link','')]);return
        if tag=='a':
            if node.get('href'):
                ref=node.get('href')
                # Links to non-document local files are attachments; their contents matter,
                # while their exported directory and generated resource basename do not.
                local=urlsplit(ref)
                if not local.scheme and local.path and not local.path.lower().endswith(('.html','.htm')):
                    data=resource(folder,ref);emit(['file',a.nfc(''.join(node.itertext()).strip()),hashlib.sha256(data).hexdigest()]);return
                attrs['link']=target(node)
            else:
                anchor=node.get('name') or node.get('id')
                if anchor and anchor!=section_anchor:emit(['anchor',a.nfc(anchor)])
        block=tag in ('p','blockquote') or heading(node)
        if block:emit(['break'])
        text(node.text,attrs)
        for child in node:
            walk(child,attrs,lists);text(child.tail,attrs)
        if block:emit(['break'])
    walk(container,{},[])
    # Pretty-print whitespace has no effect on paragraph text.
    for i,item in enumerate(items):
        if item[0]=='text':
            if i==0 or items[i-1][0] not in ('text','image','file','anchor'):item[1]=item[1].lstrip()
            if i+1==len(items) or items[i+1][0] not in ('text','image','file','anchor'):item[1]=item[1].rstrip()
    items=[x for x in items if x[0]!='text' or x[1]]
    while items and items[0]==['break']:items.pop(0)
    while items and items[-1]==['break']:items.pop()
    return {'title':a.nfc(''.join(title.itertext()).strip()),'items':items}


def page(text,folder):
    root=parse(text);ts=titles(root) or root.xpath('//main//h1 | //article//h1 | //body//h1')
    if not ts:raise a.Unreadable('HTML page has no title')
    return project_body(scope(root,ts[0]),ts[0],folder)


def single(text,folder):
    root=parse(text);sections={};order=[]
    for title in titles(root):
        body=scope(root,title)
        ids=[title.get('data-node-id'),body.get('data-node-id')]
        anchors=body.xpath('.//a[@name or @id]')
        section_anchor=next((e.get('name') or e.get('id') for e in anchors
                             if re.search(r'_\d+\.html$',e.get('name') or e.get('id') or '')),None)
        ids.append(section_anchor)
        ident=next((x for x in ids if x),None)
        if not ident:raise a.Unreadable('HTML section lacks a node destination')
        match=re.search(r'_(\d+)\.html$',ident);ident=match.group(1) if match else ident
        level=title.get('data-level') or next((c[6:] for c in classes(title) if c.startswith('level-')),None)
        if level is None:raise a.Unreadable('HTML section lacks a hierarchy level')
        if ident in sections:raise a.Unreadable('duplicate HTML node section')
        sections[ident]=dict(project_body(body,title,folder,section_anchor),level=int(level));order.append(ident)
    if not sections:raise a.Unreadable('single HTML export contains no node sections')
    return {'sections':sections,'order':order}


def index(text):
    root=parse(text)
    candidates=root.xpath('//ul | //ol')
    roots=[x for x in candidates if 'outermost' in classes(x)]
    if not roots:
        roots=[x for x in candidates if not any(p.tag in ('ul','ol') for p in x.iterancestors()) and x.xpath('.//a[@href or @onclick]')]
    if len(roots)!=1:raise a.Unreadable('HTML index must contain one node tree')
    def read(ul):
        out=[]
        for li in ul:
            if li.tag!='li':continue
            links=[x for x in li.xpath('.//a') if next((p for p in x.iterancestors() if p.tag=='li'),None) is li]
            if not links:raise a.Unreadable('index node has no destination')
            link=links[0];nested=[x for x in li.xpath('.//ul | .//ol') if next((p for p in x.iterancestors() if p.tag=='li'),None) is li]
            out.append([a.nfc(''.join(link.itertext()).strip()),target(link),[n for x in nested for n in read(x)]])
        return out
    return read(roots[0])
