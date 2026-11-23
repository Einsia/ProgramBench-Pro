"""Behavioral projections that distinguish document operations without freezing serialization."""
import base64
import hashlib
import io
import json
import math
import re
import statistics
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
import fitz
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, ByteStringObject, DecodedStreamObject,
                          DictionaryObject, FloatObject, IndirectObject, NameObject, NullObject, NumberObject)
from PIL import Image, ImageChops, ImageFilter, ImageStat


def text(value):return ' '.join(str(value).replace('\x00','').split())

def render(page,scale=1):
    pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csRGB,alpha=False)
    return Image.frombytes('RGB',(pix.width,pix.height),pix.samples)

def multiset_match(actual,expected,compare,tol,path):
    assert len(actual)==len(expected),f'{path}: collection size differs'
    candidates=[]
    for item in expected:
        hits=[]
        for i,a in enumerate(actual):
            try:compare(a,item,tol,path);hits.append(i)
            except AssertionError:pass
        assert hits,f'{path}: no equivalent item in output collection'
        candidates.append(hits)
    assigned={}
    def assign(e,seen):
        for a in candidates[e]:
            if a in seen:continue
            seen.add(a)
            if a not in assigned or assign(assigned[a],seen):assigned[a]=e;return True
        return False
    assert all(assign(e,set()) for e in sorted(range(len(expected)),key=lambda x:len(candidates[x]))),f'{path}: content multiplicity differs'

def image_semantics(image,size=(32,32)):
    im=image.convert('RGB').resize(size,Image.Resampling.BOX)
    return [list(p) for p in im.getdata()]

def graph(value):
    nodes=value.get('nodes');edges=value.get('connections')
    assert isinstance(nodes,list) and nodes and isinstance(edges,list),'Invalid workflow graph'
    attrs={n['id']:{'type':n['type'],'controls':n.get('controls',{})} for n in nodes}
    assert len(attrs)==len(nodes),'Duplicate node identifiers'
    def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    colors={k:digest(v) for k,v in attrs.items()}
    for _ in range(len(nodes)):
        nxt={}
        for k in attrs:
            incoming=[];outgoing=[]
            for e in edges:
                assert e['source'] in attrs and e['target'] in attrs,'Dangling graph connection'
                if e['target']==k:incoming.append((e['sourceOutput'],e['targetInput'],colors[e['source']]))
                if e['source']==k:outgoing.append((e['sourceOutput'],e['targetInput'],colors[e['target']]))
            nxt[k]=digest([attrs[k],sorted(incoming),sorted(outgoing)])
        colors=nxt
    return {'nodes':sorted([{'attributes':attrs[k],'identity':colors[k]} for k in attrs],key=lambda x:(x['identity'],json.dumps(x['attributes'],sort_keys=True))),
            'connections':sorted([[colors[e['source']],e['sourceOutput'],colors[e['target']],e['targetInput']] for e in edges])}

def numeric_csv(rows):
    # CSV data is a table: alternate spellings of a numeric cell do not change its value.
    def cell(v):
        v=v.strip()
        if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v):return float(v)
        return v
    return [[cell(v) for v in row] for row in rows]

def from_cpdf_json(value):
    """Read CPDF's documented JSON object/stream representation into an independent PDF writer."""
    assert isinstance(value,list) and len(value)>3,'Missing PDF object table'
    objects={int(x[0]):x[1] for x in value if isinstance(x,list) and len(x)==2}
    assert -1 in objects and 0 in objects and '/Root' in objects[0],'Missing PDF JSON header/trailer'
    assert objects[-1].get('/CPDFJSONformatversion'),'Missing format version'
    w=PdfWriter();refs={n:w._add_object(NullObject()) for n in objects if n>0}
    def convert(v,content=False):
        if v is None:return NullObject()
        if isinstance(v,bool):return BooleanObject(v)
        if isinstance(v,int):
            if content:return NumberObject(v)
            assert v in refs,'Unresolved PDF JSON reference';return refs[v]
        if isinstance(v,float):return FloatObject(v)
        if isinstance(v,str):return ByteStringObject(v.encode('latin-1',errors='replace'))
        if isinstance(v,list):return ArrayObject([convert(x,content) for x in v])
        assert isinstance(v,dict),'Invalid PDF JSON value'
        if set(v)=={'I'}:return NumberObject(v['I'])
        if set(v)=={'F'}:return FloatObject(v['F'])
        if set(v)=={'N'}:return NameObject(v['N'])
        if set(v)=={'S'}:
            attrs,body=v['S'];stream=DecodedStreamObject()
            if isinstance(body,str):raw=body.encode('latin-1')
            else:
                assert isinstance(body,list),'Invalid content stream'
                parts=[]
                for op in body:
                    assert isinstance(op,list) and op and isinstance(op[-1],str),'Invalid content operation'
                    buf=io.BytesIO()
                    for arg in op[:-1]:
                        obj=NameObject(arg) if isinstance(arg,str) and arg.startswith('/') else convert(arg,True)
                        obj.write_to_stream(buf);buf.write(b' ')
                    buf.write(op[-1].encode('ascii'));parts.append(buf.getvalue())
                raw=b'\n'.join(parts)+b'\n'
            stream.set_data(raw)
            for k,v in attrs.items():
                if k not in {'/Length','/Filter','/DecodeParms'}:stream[NameObject(k)]=convert(v)
            return stream
        return DictionaryObject({NameObject(k):convert(x,content) for k,x in v.items()})
    for n,ref in refs.items():
        obj=convert(objects[n]);obj.indirect_reference=ref;w._objects[ref.idnum-1]=obj
    root=objects[0]['/Root'];assert root in refs,'Missing catalog'
    w._root_object=refs[root].get_object();w._root=refs[root]
    buf=io.BytesIO();w.write(buf)
    return buf.getvalue()

def json_projection(output):
    docs=[]
    for name,data in output.expanded():
        if not name.lower().endswith('.json'):continue
        try:v=json.loads(data.decode('utf-8'))
        except UnicodeDecodeError:v=json.loads(data.decode('latin-1'))
        reconstructed=from_cpdf_json(v)
        with fitz.open(stream=reconstructed,filetype='pdf') as d:
            assert len(d),'PDF JSON reconstructs no pages'
            docs.append({'sizes':[[round(p.rect.width,2),round(p.rect.height,2)] for p in d],
                         'text':[text(p.get_text(sort=True)) for p in d],
                         'render':[image_semantics(render(p,.5)) for p in d]})
    assert docs,'No PDF JSON output';return {'documents':docs}

def svg_projection(output):
    pages=[]
    for name,data in output.expanded():
        if not name.lower().endswith('.svg'):continue
        root=ET.fromstring(data);assert root.tag.endswith('svg'),'Not an SVG'
        assert any(e.tag.rsplit('}',1)[-1] in {'path','rect','circle','ellipse','text','use','image','polygon'} for e in root.iter()),'Empty SVG'
        with fitz.open(stream=data,filetype='svg') as d:
            assert len(d)==1,'Invalid SVG page'
            im=render(d[0],.5);assert min(ImageStat.Stat(im).mean)<254.8,'Blank SVG'
            pages.append({'size':[round(d[0].rect.width,2),round(d[0].rect.height,2)],'render':image_semantics(im)})
    assert pages,'No SVG output';return {'pages':pages}

def archival(d,data,part):
    ns='{http://www.aiim.org/pdfa/ns/id/}'
    xml=ET.fromstring(d.get_xml_metadata());attrs={}
    for el in xml.iter():
        for k,v in el.attrib.items():attrs[k]=v
        if el.tag.startswith(ns):attrs[el.tag]=el.text
    assert int(attrs.get(ns+'part',0))==part and attrs.get(ns+'conformance','').upper()=='B','Missing requested PDF/A identification'
    r=PdfReader(io.BytesIO(data));root=r.trailer['/Root'];intents=root.get('/OutputIntents') or []
    profiles=[x.get_object().get('/DestOutputProfile') for x in intents]
    assert profiles and any(x and len(x.get_object().get_data())>=128 for x in profiles),'Missing output ICC profile'
    fontrefs={f[0] for p in d for f in p.get_fonts()}
    assert fontrefs and all(len(d.extract_font(x)[3])>0 for x in fontrefs),'Unembedded PDF/A font'
    assert not r.is_encrypted,'Encrypted archival PDF'
    return {'part':part,'conformance':'B','output_profile':True,'fonts_embedded':True,'encrypted':False}

def added_mark(doc,original,gray=False):
    assert len(doc)==len(original),'Mark changed page count'
    marks=[]
    for a,b in zip(doc,original):
        im=render(a,1.5);base=render(b,1.5);assert im.size==base.size,'Mark changed page size'
        diff=ImageChops.difference(im,base);mask=diff.convert('L').point(lambda x:255 if x>18 else 0)
        box=mask.getbbox()
        if box is None:continue
        crop=im.crop(box);m=mask.crop(box);fraction=ImageStat.Stat(m).mean[0]/255
        assert .005<fraction<.99,'Added mark has no recognizable internal structure'
        # Translation and scale are not compared; identify the pattern inside its own content bounds.
        shape=m.resize((64,24),Image.Resampling.BOX)
        item={'shape':[round(x/255,3) for x in shape.getdata()],'coverage':round(fraction,3)}
        if not gray:item['color']=image_semantics(crop,(24,24))
        marks.append(item)
    assert marks,'No added signature or image mark'
    return {'marks':marks}

def words(page,pattern=None,margins=False):
    result=[];w,h=page.rect.width,page.rect.height
    for x0,y0,x1,y1,t,*_ in page.get_text('words'):
        if pattern and not re.fullmatch(pattern,t):continue
        rect=fitz.Rect(x0,y0,x1,y1)*page.rotation_matrix
        if margins and not (rect.y1<45 or rect.y0>h-45):continue
        result.append({'text':text(t),'center':[round((rect.x0+rect.x1)/2,2),round((rect.y0+rect.y1)/2,2)],'size':[round(rect.width,2),round(rect.height,2)]})
    return sorted(result,key=lambda x:(x['text'],x['center']))

def lines(page):
    segments=[]
    def edge(p,q):
        p=fitz.Point(p)*page.rotation_matrix;q=fitz.Point(q)*page.rotation_matrix
        if abs(p-q)<1:return
        a,b=sorted([list(p),list(q)]);segments.append([round(v,2) for v in a+b])
    for path in page.get_drawings():
        if path['type'] not in {'s','fs'} or not path.get('color'):continue
        for item in path['items']:
            if item[0]=='l':edge(item[1],item[2])
            elif item[0]=='re':
                r=item[1]
                for p,q in [(r.tl,r.tr),(r.tr,r.br),(r.br,r.bl),(r.bl,r.tl)]:edge(p,q)
    return sorted(segments)

def form_state(data):
    r=PdfReader(io.BytesIO(data));acro=r.trailer['/Root'].get('/AcroForm');result=[]
    if not acro:return result
    acro=acro.get_object()
    def walk(ref,parent_name='',inherited=None):
        f=ref.get_object();inherited=dict(inherited or {})
        for key in ['/FT','/V','/Ff','/Q','/DA','/MaxLen','/Opt']:
            if key in f:inherited[key]=f[key]
        name='.'.join(x for x in [parent_name,str(f.get('/T',''))] if x)
        named_kids=[x for x in f.get('/Kids',[]) if '/T' in x.get_object()]
        if named_kids:
            for child in named_kids:walk(child,name,inherited)
            return
        if not inherited.get('/FT') or not name:return
        da=str(inherited.get('/DA',acro.get('/DA','')))
        size=re.search(r'([-.0-9]+)\s+Tf',da);color=re.search(r'([-.0-9]+)\s+([-.0-9]+)\s+([-.0-9]+)\s+rg',da)
        g=re.search(r'([-.0-9]+)\s+g',da)
        result.append({'name':name,'type':str(inherited.get('/FT','')),'value':str(inherited.get('/V','')),
                       'flags':int(inherited.get('/Ff',0)),
                       'options':[[str(x[0]),str(x[1])] if isinstance(x,(list,tuple)) else [str(x),str(x)] for x in inherited.get('/Opt',[])],
                       'max_length':int(inherited.get('/MaxLen',0)),'alignment':int(inherited.get('/Q',0)),
                       'font_size':float(size.group(1)) if size else 0.,
                       'color':[float(v) for v in color.groups()] if color else [float(g.group(1)) if g else 0.]*3})
    for ref in acro.get('/Fields',[]):walk(ref)
    return sorted(result,key=lambda x:x['name'])

def base_preserved(doc,original,added_text=''):
    assert len(doc)==len(original),'Form changed base page count'
    for p,b in zip(doc,original):
        assert abs(p.rect.width-b.rect.width)<1.5 and abs(p.rect.height-b.rect.height)<1.5,'Form changed base dimensions'
        # Every original word remains, independent of added field captions and widget position.
        have=Counter(text(p.get_text()).split());want=Counter(text(b.get_text()).split())
        assert not (want-have),'Form removed original text'
        # Check outside every added widget and image box at rendered coordinates.
        im=render(p);before=render(b);diff=ImageChops.difference(im,before)
        from PIL import ImageDraw
        draw=ImageDraw.Draw(diff)
        boxes=[w.rect for w in p.widgets() or []]+[a.rect for a in p.annots() or []]
        for info in p.get_image_info():boxes.append(fitz.Rect(info['bbox']))
        if added_text:boxes.extend(p.search_for(added_text))
        for box in boxes:
            box=box* p.rotation_matrix;box=box+(-3,-3,3,3);draw.rectangle(list(box),fill='black')
        assert max(ImageStat.Stat(diff).mean)<3,'Form changed base content outside added objects'
    return {'base_preserved':True}

KINDS={'pdf-archival','pdf-number-layout','pdf-word-layout','pdf-line-layout','pdf-color-grid','pdf-font-reuse','pdf-image-quality','pdf-radio-group','pdf-xfa-value','pdf-widget-pages',
       'pdf-color-geometry','pdf-highlight-text','pdf-comment-content','pdf-redacted','pdf-bookmark-style','pdf-image-color','pdf-repaired','pdf-deskew-angle','pdf-mark','pdf-base-preserved','pdf-layer-state','pdf-field-value','pdf-widget-state','pdf-decoration',
       'attachment-bytes','svg-content','json-rebuild','workflow-graph','csv-numeric','image-compression','pdf-barcode-content','table-cells'}

def observe(ctx,cp,spec):
    output=ctx.state['outputs'];kind=spec['kind']
    if kind=='table-cells':
        import csv
        tables=[]
        for n,data in output.expanded():
            s=data.decode('utf-8-sig')
            if spec['format']=='csv':rows=list(csv.reader(io.StringIO(s)))
            elif spec['format']=='json':rows=json.loads(s)
            else:
                rows=[[v.strip() for v in line.strip().strip('|').split('|')] for line in s.splitlines() if '|' in line and not re.fullmatch(r'[\s|:\-]+',line)]
            assert isinstance(rows,list) and rows and all(isinstance(r,list) for r in rows),'Missing table cells'
            tables.append([[text(v if v is not None else '') for v in row] for row in rows])
        assert tables,'No extracted tables';return {'tables':tables}
    if kind=='attachment-bytes':return {'files':sorted([{'name':Path(n).name,'sha256':hashlib.sha256(d).hexdigest()} for n,d in output.expanded()],key=lambda x:(x['name'],x['sha256']))}
    if kind=='json-rebuild':return json_projection(output)
    if kind=='svg-content':return svg_projection(output)
    if kind=='workflow-graph':
        return {'graphs':sorted([graph(json.loads(data)) for n,data in output.expanded() if n.endswith('.json')],key=lambda v:json.dumps(v,sort_keys=True))}
    if kind=='csv-numeric':
        import csv
        vals=[numeric_csv(list(csv.reader(io.StringIO(d.decode('utf-8-sig'))))) for n,d in output.expanded() if n.endswith('.csv')]
        assert vals and all(vals),'No CSV data';return {'tables':vals}
    if kind=='image-compression':return {'compression':sorted(int(im.tag_v2.get(259,1)) for _,_,im in output.images())}
    docs=output.pdfs(cp.get('password',''));ps=[p for _,_,d in docs for p in d]
    if kind=='pdf-archival':return {'archival':[archival(d,data,spec['part']) for _,data,d in docs]}
    if kind=='pdf-highlight-text':
        vals=[]
        for p in ps:
            highlights={}
            for a in p.annots() or []:
                # PDF.js saves a drag begun just outside the text layer as an Ink
                # highlighter. Its visible mark is equivalent when it covers the same word.
                if a.type[1] not in {'Highlight','Ink'}:continue
                for w in p.get_text('words'):
                    r=fitz.Rect(w[:4])
                    if (r & a.rect).get_area()<=.3*r.get_area():continue
                    center=[round((r.x0+r.x1)/2,2),round((r.y0+r.y1)/2,2)]
                    color=list(a.colors.get('stroke') or [])
                    highlights[(w[4],*center,*color)]={'text':w[4],'center':center,'color':color}
            vals.append(sorted(highlights.values(),key=lambda x:(x['center'][1],x['center'][0],x['text'])))
        assert any(vals),'No text highlight';return {'highlights':vals}
    if kind=='pdf-comment-content':
        vals=[[{'type':a.type[1],'text':text(a.info.get('content',''))} for a in p.annots() or []] for p in ps]
        assert any(vals),'No annotation';return {'comments':vals}
    if kind=='pdf-redacted':
        for _,_,d in docs:
            visible=' '.join(p.get_text() for p in d)
            assert all(t not in visible for t in spec['absent']),'Sensitive text remains extractable'
            assert all(t in visible for t in spec.get('present',[])),'Unrelated content was removed'
            streams=b''.join(d.xref_stream(i) or b'' for i in range(1,d.xref_length()) if d.xref_is_stream(i))
            assert all(t.encode() not in streams for t in spec['absent']),'Sensitive text remains in PDF streams'
        return {'removed':spec['absent'],'retained':spec.get('present',[])}
    if kind=='pdf-bookmark-style':
        vals=[]
        for _,_,d in docs:
            vals.append([{'level':n[0],'title':n[1],'page':n[2],'color':list(n[3].get('color') or [0,0,0]),'bold':bool(n[3].get('bold')),'italic':bool(n[3].get('italic'))} for n in d.get_toc(simple=False)])
        return {'bookmarks':vals}
    if kind=='pdf-image-color':
        vals=[]
        for _,_,d in docs:
            for p in d:
                for info in p.get_images():
                    im=Image.open(io.BytesIO(d.extract_image(info[0])['image'])).convert('RGB')
                    a,b,c=im.split();vals.append(max(ImageStat.Stat(ImageChops.difference(a,b)).mean+ImageStat.Stat(ImageChops.difference(b,c)).mean)<1.5)
        assert vals and all(vals),'Images remain colored';return {'grayscale':vals}
    if kind=='pdf-number-layout':
        vals=[words(p,r'\d+',True) for p in ps];assert all(vals),'No page number in page margins';return {'numbers':vals}
    if kind=='pdf-word-layout':return {'words':[words(p,spec.get('pattern')) for p in ps]}
    if kind=='pdf-line-layout':return {'lines':[lines(p) for p in ps]}
    if kind=='pdf-color-geometry':
        vals=[]
        for p in ps:
            im=render(p,1);colors=[];w,h=im.size
            for channel in range(3):
                coords=[(i%w,i//w) for i,pix in enumerate(im.getdata()) if pix[channel]>max(pix[(channel+1)%3],pix[(channel+2)%3])+45 and pix[channel]>80]
                if not coords:colors.append(None);continue
                xs,ys=zip(*coords);colors.append({'box':[min(xs),min(ys),max(xs),max(ys)],'center':[round(sum(xs)/len(xs),2),round(sum(ys)/len(ys),2)]})
            vals.append(colors)
        assert any(any(x is not None for x in row) for row in vals),'No colored content in output'
        return {'colored_regions':vals}
    if kind=='pdf-color-grid':
        return {'regions':[image_semantics(render(p,.5),(12,16)) for p in ps]}
    if kind=='pdf-layer-state':
        return {'layers':[sorted([{'name':x['name'],'on':x['on']} for x in d.get_ocgs().values()],key=lambda x:x['name']) for _,_,d in docs]}
    if kind=='pdf-field-value':
        matches=[f for _,data,_ in docs for f in form_state(data) if f['name']==spec['field'] and f['value']==spec['value']]
        assert matches,'Saved field value does not match';return {'field':spec['field'],'value':spec['value']}
    if kind=='pdf-widget-state':
        states=[form_state(data) for _,data,_ in docs]
        result={'fields':[[f for f in fields if not spec.get('fields') or f['name'] in spec['fields']] for fields in states]}
        if spec.get('retain_types'):result['field_types']=[[[f['name'],f['type']] for f in fields] for fields in states]
        return result
    if kind=='pdf-widget-pages':return {'widgets':[[[w.field_type_string for w in p.widgets() or []] for p in d] for _,_,d in docs]}
    if kind=='pdf-xfa-value':
        found=[]
        for _,data,_ in docs:
            r=PdfReader(io.BytesIO(data));xfa=r.trailer['/Root']['/AcroForm']['/XFA']
            streams=[v.get_object().get_data() for v in xfa[1::2]] if isinstance(xfa,list) else [xfa.get_data()]
            for raw in streams:
                try:xml=ET.fromstring(raw)
                except ET.ParseError:continue
                for node in xml.iter():
                    if node.tag.rsplit('}',1)[-1]==spec['field']:found.append(text(node.text or ''))
        assert spec['value'] in found,'Saved XFA data is missing the entered value'
        return {'field':spec['field'],'value':spec['value']}
    if kind=='pdf-radio-group':
        result=[]
        for _,data,d in docs:
            groups=[]
            r=PdfReader(io.BytesIO(data))
            for name,f in (r.get_fields() or {}).items():
                if f.get('/FT')!='/Btn' or not int(f.get('/Ff',0)) & 32768:continue
                options=f.get('/Opt')
                widgets=[w for p in d for w in p.widgets() or [] if w.field_name==name]
                exports=[str(x[0]) if isinstance(x,(list,tuple)) else str(x) for x in options] if options else sorted({x for w in widgets for x in (w.button_states() or {}).get('normal',[]) if x!='Off'})
                selected=str(f.get('/V','/Off')).lstrip('/')
                if selected.isdigit() and options and int(selected)<len(exports):selected=exports[int(selected)]
                groups.append({'name':name,'options':sorted(exports),'widgets':len(widgets),'selected':selected})
            assert groups,'No radio group';result.append(groups)
        return {'groups':result}
    if kind=='pdf-base-preserved':
        with fitz.open(ctx.inputs/spec.get('input','single.pdf')) as original:return base_preserved(docs[0][2],original,spec.get('added_text',''))
    if kind=='pdf-mark':
        with fitz.open(ctx.inputs/spec.get('input','single.pdf')) as original:
            result=added_mark(docs[0][2],original,spec.get('gray',False))
        if spec.get('flatten'):
            assert not any(list(p.annots() or []) for p in ps),'Flattened signature is still editable'
            result['editable_annotations']=0
        return result
    if kind=='pdf-font-reuse':
        counts=[]
        for _,data,_ in docs:
            r=PdfReader(io.BytesIO(data));programs={}
            for page in r.pages:
                for ref in page['/Resources'].get('/Font',{}).values():
                    f=ref.get_object()
                    for descendant in f.get('/DescendantFonts',[f]):
                        descriptor=descendant.get_object().get('/FontDescriptor')
                        if not descriptor:continue
                        descriptor=descriptor.get_object()
                        for key in ('/FontFile','/FontFile2','/FontFile3'):
                            if key not in descriptor:continue
                            stream=descriptor[key];digest=hashlib.sha256(stream.get_data()).hexdigest()
                            identity=stream.indirect_reference.idnum if getattr(stream,'indirect_reference',None) else id(stream)
                            programs.setdefault(digest,set()).add(identity)
            assert programs,'No embedded programs to deduplicate'
            copies=sorted(len(x) for x in programs.values())
            assert max(copies)==1,'Duplicate embedded font programs remain'
            counts.append(copies)
        return {'copies_per_font':counts}
    if kind=='pdf-image-quality':
        vals=[]
        for _,_,d in docs:
            for p in d:
                for info in p.get_images():
                    v=d.extract_image(info[0]);im=Image.open(io.BytesIO(v['image']))
                    quant=getattr(im,'quantization',None)
                    assert quant,'Expected lossy image quantization'
                    vals.append({'size':list(im.size),'quantization':round(statistics.mean(quant[0]),1)})
        assert vals,'No compressed image';return {'images':vals}
    if kind=='pdf-repaired':
        for _,data,d in docs:
            assert data.startswith(b'%PDF-'),'PDF header damage was not repaired'
            assert not d.is_repaired,'Output still needs PDF repair'
            assert re.search(rb'startxref\s+(\d+)',data),'No cross-reference offset'
            offset=int(list(re.finditer(rb'startxref\s+(\d+)',data))[-1].group(1))
            assert 0<offset<len(data) and (data[offset:offset+4]==b'xref' or re.match(rb'\d+ \d+ obj',data[offset:offset+40])),'Broken cross-reference offset'
            PdfReader(io.BytesIO(data),strict=True)
        return {'structurally_repaired':True}
    if kind=='pdf-deskew-angle':
        # Horizontal projection has highest variance at the corrected orientation; no OCR model is needed.
        vals=[]
        for p in ps:
            im=render(p,1.5).convert('L');im=ImageChops.invert(im).resize((700,450))
            scores=[]
            for i in range(-32,33):
                angle=i*.25;rot=im.rotate(angle,resample=Image.Resampling.BILINEAR,fillcolor=0)
                profile=[sum(rot.crop((0,y,700,y+1)).getdata())/700 for y in range(450)]
                scores.append((statistics.pvariance(profile),angle))
            vals.append(max(scores)[1])
        assert all(abs(v)<1.25 for v in vals),'Text remains visibly skewed';return {'residual_angle':vals}
    if kind=='pdf-decoration':
        vals=[]
        with fitz.open(ctx.inputs/spec.get('input','single.pdf')) as original:
            for page,before in zip(ps,original):
                rects=before.search_for(spec.get('text','Harbor Map'));assert rects,'Heading missing'
                r=rects[0];scale=3;box=fitz.Rect(r.x0-2,r.y0-3,r.x1+2,r.y1+5)
                pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=box,colorspace=fitz.csGRAY,alpha=False)
                prior=before.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=box,colorspace=fitz.csGRAY,alpha=False)
                im=Image.frombytes('L',(pix.width,pix.height),pix.samples);base=Image.frombytes('L',(prior.width,prior.height),prior.samples)
                added=ImageChops.subtract(base,im);w,h=added.size
                scores=[sum(x>45 for x in added.crop((0,y,w,y+1)).getdata())/w for y in range(h)]
                peak=max(scores);assert peak>.35,'No line spanning the heading'
                rows=[i for i,x in enumerate(scores) if x>peak*.85]
                ratio=((sum(rows)/len(rows))/scale+box.y0-r.y0)/r.height
                vals.append(round(ratio,3))
        return {'line_height_ratios':vals}
    if kind=='pdf-barcode-content':
        result=[]
        for _,_,d in docs:
            ims=[]
            for p in d:
                for info in p.get_images():
                    data=d.extract_image(info[0])['image'];im=Image.open(io.BytesIO(data));ims.append(image_semantics(im,(32,32)))
            assert ims,'Barcode graphic missing';result.append(ims)
        return {'barcodes':result}
    raise ValueError(kind)

def judge(actual,expected,spec,compare):
    kind=spec['kind'];tol=spec.get('tol',.1)
    if kind=='pdf-highlight-text':
        assert len(actual['highlights'])==len(expected['highlights']),'Highlight page count differs'
        for aa,ee in zip(actual['highlights'],expected['highlights']):
            assert len(aa)==len(ee),'Highlighted words differ'
            for a,e in zip(aa,ee):
                compare(a['text'],e['text']);compare(a['center'],e['center'],2);compare(a['color'],e['color'],.06)
        return
    if kind=='pdf-image-quality':
        assert len(actual['images'])==len(expected['images']),'Compressed image count differs'
        for a,e in zip(actual['images'],expected['images']):
            compare(a['size'],e['size'],1)
            # Quantization is a lossy-quality proxy, not a demand for a byte-identical JPEG table.
            compare(a['quantization'],e['quantization'],max(tol,.18*e['quantization']))
        return
    if kind=='pdf-mark':
        am=actual['marks'];em=expected['marks'];assert len(am)==len(em),'Mark count differs'
        for a,e in zip(am,em):
            assert abs(a['coverage']-e['coverage'])<.15,'Mark pattern is unrelated to the requested signature/image'
            assert sum(abs(x-y) for x,y in zip(a['shape'],e['shape']))/len(e['shape'])<.16,'Mark shape does not match'
            if spec.get('stroke_shape'):
                def expanded(item):
                    im=Image.new('L',(64,24));im.putdata([round(v*255) for v in item['shape']]);return im.filter(ImageFilter.MaxFilter(5))
                aa,ee=expanded(a),expanded(e)
                overlap=sum(ImageChops.darker(aa,ee).getdata())/max(1,sum(ImageChops.lighter(aa,ee).getdata()))
                assert overlap>.25,'Freehand stroke does not have the requested shape'
            if 'color' in e:assert sum(abs(x-y) for ac,ec in zip(a['color'],e['color']) for x,y in zip(ac,ec))/(len(e['color'])*3)<22,'Stamp colors differ'
        if spec.get('flatten'):assert actual.get('editable_annotations')==0
        return
    if kind=='svg-content':multiset_match(actual['pages'],expected['pages'],compare,tol,'SVG pages');return
    compare(actual,expected,tol)
