"""Semantic checks of public product downloads. No candidate filesystem or internal state access."""
import base64
import io
import json
import math
from pathlib import Path
import re
import sys
import time
import unicodedata
import zipfile
sys.path.insert(0,'/opt/verifier-lib')
import fitz
from pypdf import PdfReader
from PIL import Image,ImageStat,ImageChops,ImageFilter
import semantics

def norm(text):
    return ' '.join(unicodedata.normalize('NFKC',str(text)).replace('\x00','').split())

def compare(actual,expected,tol=0.1,path='output'):
    if isinstance(expected,bool) or expected is None or isinstance(expected,str):
        assert actual==expected,f'{path}: expected {expected!r}, got {actual!r}'
    elif isinstance(expected,(int,float)):
        assert type(actual) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=tol,f'{path}: expected {expected} ±{tol}, got {actual!r}'
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected),f'{path}: list length differs'
        for i,(a,e) in enumerate(zip(actual,expected)):compare(a,e,tol,f'{path}[{i}]')
    elif isinstance(expected,dict):
        assert isinstance(actual,dict),f'{path}: expected an object'
        if not expected:assert not actual,f'{path}: expected an empty collection'
        for k,e in expected.items():
            assert k in actual,f'{path}: missing {k}'
            compare(actual[k],e,tol,f'{path}.{k}')
    else:raise AssertionError('Unsupported observation value')

class Outputs:
    def __init__(self,broker):self.broker=broker;self.reset()
    def reset(self):self.files=None;self.documents={};self.images_cache=None
    def take(self):
        if self.files is not None:return self.files
        self.files=[]
        snap=self.broker.call({'op':'snapshot'})
        for d in snap.get('downloads',[]):
            item=self.broker.call({'op':'download','ref':d['ref']})
            assert not item.get('truncated'),'download was truncated'
            content=base64.b64decode(item['body_base64']);assert content,'empty download'
            self.files.append((item['filename'],content))
        assert self.files,'No product download was produced'
        return self.files
    def expanded(self):
        result=[]
        for name,data in self.take():
            if Path(name).suffix.lower() in {'.zip','.cbz'}:
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        infos=[i for i in z.infolist() if not i.is_dir()]
                        assert infos and len(infos)<10000,'empty or excessive archive'
                        assert sum(i.file_size for i in infos)<=200_000_000,'archive too large'
                        for i in infos:
                            assert not i.filename.startswith('/') and '..' not in i.filename.split('/'),'unsafe archive paths'
                            result.append((i.filename,z.read(i)))
                except zipfile.BadZipFile:raise AssertionError('Invalid ZIP output') from None
            else:result.append((name,data))
        return result
    def pdfs(self,password=''):
        if password in self.documents:return self.documents[password]
        result=[]
        for name,data in self.expanded():
            if not name.lower().endswith('.pdf'):continue
            try:
                doc=fitz.open(stream=data,filetype='pdf')
                if doc.needs_pass:assert doc.authenticate(password),'PDF password does not open output'
                assert len(doc)>0,'PDF has no pages'
                assert len(doc)<=500,'PDF has excessive pages'
                result.append((name,data,doc))
            except AssertionError:raise
            except Exception as e:raise AssertionError('Output is not a readable PDF: '+type(e).__name__) from None
        assert result,'No PDF output'
        # Archive filenames are incidental. Preserve page order within each document, compare documents by content.
        result.sort(key=lambda v:(len(v[2]),norm(' '.join(p.get_text() for p in v[2]))))
        self.documents[password]=result;return result
    def images(self):
        if self.images_cache is not None:return self.images_cache
        result=[]
        for name,data in self.expanded():
            if Path(name).suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif'}:continue
            try:
                im=Image.open(io.BytesIO(data));im.load();result.append((name,data,im))
            except Exception as e:raise AssertionError('Unreadable image: '+type(e).__name__) from None
        assert result,'No image output';result.sort(key=lambda v:v[0]);self.images_cache=result;return result
    def close(self):
        for docs in self.documents.values():
            for _,_,d in docs:d.close()

def pages(ctx,cp):
    return [p for _,_,d in ctx.state['outputs'].pdfs(cp.get('password','')) for p in d]

def rendered(page,scale=1):
    return Image.frombytes('RGB',(lambda p:(p.width,p.height))(pix:=page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csRGB,alpha=False)),pix.samples)

def tiles(image,nx=6,ny=8):
    im=image.convert('RGB');w,h=im.size
    return [[round(v,1) for v in ImageStat.Stat(im.crop((int(x*w/nx),int(y*h/ny),int((x+1)*w/nx),int((y+1)*h/ny)))).mean]
            for y in range(ny) for x in range(nx)]

def word_positions(page,needle):
    out=[]
    for x0,y0,x1,y1,text,*_ in page.get_text('words'):
        if norm(text)==needle:
            rect=fitz.Rect(x0,y0,x1,y1)*page.rotation_matrix
            out.append([round(rect.x0,2),round(rect.y0,2),round(rect.width,2),round(rect.height,2)])
    return out

def annotation_facts(page):
    result=[]
    for a in page.annots() or []:
        rect=a.rect*page.rotation_matrix
        result.append({'type':a.type[1],'content':norm(a.info.get('content','')),'rect':[round(v,2) for v in rect],
                       'colors':{k:[round(c,3) for c in v] for k,v in a.colors.items() if v},'opacity':round(a.opacity,3)})
    return sorted(result,key=lambda d:(d['type'],d['content'],d['rect']))

def form_facts(data,password):
    try:
        r=PdfReader(io.BytesIO(data))
        if r.is_encrypted:assert r.decrypt(password),'Cannot open forms output'
        fields=r.get_fields() or {}
        return {name:{'type':str(v.get('/FT','')),'value':str(v.get('/V','')),'flags':int(v.get('/Ff',0))} for name,v in sorted(fields.items())}
    except AssertionError:raise
    except Exception as e:raise AssertionError('Cannot parse forms: '+type(e).__name__) from None

def observe(ctx,cp,spec):
    output=ctx.state['outputs'];kind=spec['kind'];password=cp.get('password','')
    if kind in semantics.KINDS:return semantics.observe(ctx,cp,spec)
    if kind=='download-format':
        result={'extensions':sorted(Path(n).suffix.lower() for n,_ in output.take())}
    elif kind=='archive':
        data=output.expanded();result={'files':len(data),'extensions':sorted(Path(n).suffix.lower() for n,_ in data)}
    elif kind=='archive-names':result={'names':sorted(n for n,_ in output.expanded())}
    elif kind=='filename':result={'names':sorted(n for n,_ in output.take())}
    elif kind.startswith('pdf-'):
        docs=output.pdfs(password);ps=[p for _,_,d in docs for p in d]
        if 'pages' in spec:
            indices=spec['pages'];assert all(0<=i<len(ps) for i in indices),'missing output page'
            ps=[ps[i] for i in indices]
        if kind=='pdf-count':result={'pages':[len(d) for _,_,d in docs]}
        elif kind=='pdf-size':result={'sizes':[[round(p.rect.width,2),round(p.rect.height,2)] for p in ps]}
        elif kind=='pdf-text':
            texts=[norm(p.get_text(sort=True)) for p in ps]
            if spec.get('nonempty',True):assert any(texts),'PDF contains no extractable text'
            if spec.get('sequence_from'):
                with fitz.open(ctx.inputs/spec['sequence_from']) as source:
                    requested=[norm(source[i-1].get_text(sort=True)) for i in spec['page_order']]
                assert texts==requested,'Output page sequence does not match the requested source pages'
            result={'texts':texts}
        elif kind=='pdf-text-set':
            texts=[sorted(norm(p.get_text()).split()) for p in ps]
            assert any(texts),'No extractable text';result={'words':texts}
        elif kind=='pdf-change':
            original=fitz.open(ctx.inputs/spec['input']);changes=[]
            try:
                for idx,page in enumerate(ps):
                    im=rendered(page,.75).convert('RGB');before=rendered(original[idx],.75).convert('RGB')
                    assert im.size==before.size,'Changed page dimensions'
                    delta=ImageChops.difference(im,before);mask=delta.convert('L').point(lambda x:255 if x>15 else 0)
                    box=mask.getbbox();w,h=im.size
                    if box is None:changes.append({'changed':False});continue
                    amount=ImageStat.Stat(mask).mean[0]/255
                    changes.append({'changed':True,'box':[round(box[i]/(w if i%2==0 else h),3) for i in range(4)],'fraction':round(amount,4)})
            finally:original.close()
            assert any(c['changed'] for c in changes),'No visible content was added or changed'
            result={'changes':changes}
        elif kind=='pdf-raster':result={'tiles':[tiles(rendered(p,.5)) for p in ps]}
        elif kind=='pdf-text-position':
            result={'positions':[word_positions(p,spec['word']) for p in ps]};assert any(result['positions']),'Requested text is missing'
        elif kind=='pdf-added-text':
            result={'texts':[[norm(w[4]) for w in p.get_text('words') if re.fullmatch(spec['pattern'],norm(w[4]))] for p in ps]}
            assert any(result['texts']),'Requested added text is missing'
        elif kind=='pdf-text-style':
            out=[]
            for p in ps:
                chars=[]
                for b in p.get_text('rawdict')['blocks']:
                    for line in b.get('lines',[]):
                        for span in line['spans']:
                            if spec.get('margin_only') and not(span['bbox'][3]<45 or span['bbox'][1]>p.rect.height-45):continue
                            for c in span['chars']:
                                chars.append({'char':c['c'],'size':round(span['size'],2),'color':[(span['color']>>shift)&255 for shift in (16,8,0)],'flags':span['flags']&18})
                if spec.get('text'):
                    joined=''.join(c['char'] for c in chars);start=joined.find(spec['text'])
                    assert start>=0,'Text style target is missing'
                    chars=chars[start:start+len(spec['text'])]
                out.append([c for c in chars if c['char'].strip()])
            assert any(out),'Text style target is missing';result={'characters':out}
        elif kind=='pdf-compressed':
            original=(ctx.inputs/spec['input']).read_bytes();size=sum(len(data) for _,data,_ in docs)
            assert size < len(original)*.7,'Photo PDF was not meaningfully compressed'
            result={'smaller_than_seventy_percent':True}
        elif kind=='pdf-image-count':result={'images':[len(p.get_images()) for p in ps]}
        elif kind=='pdf-image-size':result={'sizes':[sorted([[i[2],i[3]] for i in p.get_images()]) for p in ps]}
        elif kind=='pdf-rasterized':
            result={'pages':[{'has_images':bool(p.get_images()),'has_text':bool(norm(p.get_text()))} for p in ps]}
        elif kind=='pdf-annotation-details':
            result={'annotations':[[{'type':a.type[1],'line_ends':list(a.line_ends) if a.line_ends else None,'opacity':round(a.opacity,2),'width':round(a.border.get('width',0),2),'stroke':list(a.colors.get('stroke') or [])} for a in (p.annots() or [])] for p in ps]}
            assert any(result['annotations']),'No annotation output'
        elif kind=='pdf-annotation-types':result={'types':[sorted(a.type[1] for a in (p.annots() or [])) for p in ps]}
        elif kind=='pdf-added-annotation':
            result={'added':[any(a.type[1] in {'Square','Circle','Line','Ink','FreeText','Polygon','PolyLine'} for a in (p.annots() or [])) for p in ps]}
            assert any(result['added']),'No new editable annotation'
        elif kind=='pdf-annotations':result={'annotations':[annotation_facts(p) for p in ps]}
        elif kind=='pdf-links':result={'links':[[{'kind':l['kind'],'uri':l.get('uri'),'page':l.get('page')} for l in p.get_links()] for p in ps]}
        elif kind=='pdf-metadata':result={'metadata':[{k:d.metadata.get(k) or '' for k in spec['fields']} for _,_,d in docs]}
        elif kind=='pdf-bookmarks':result={'bookmarks':[d.get_toc() for _,_,d in docs]}
        elif kind=='pdf-labels':result={'labels':[[p.get_label() for p in d] for _,_,d in docs]}
        elif kind=='pdf-field-types':
            result={'fields':[sorted([[f['type'],f['flags']] for f in form_facts(data,password).values()]) for _,data,_ in docs]}
            assert any(result['fields']),'No PDF form fields'
        elif kind=='pdf-forms':result={'forms':[{'count':len(fields),'names':sorted(fields),'fields':fields} for fields in [form_facts(data,password) for _,data,_ in docs]]}
        elif kind=='pdf-attachments':
            result={'attachments':[sorted([{'name':n,'text':d.embfile_get(n).decode('utf-8','replace')} for n in d.embfile_names()],key=lambda x:x['name']) for _,_,d in docs]}
        elif kind=='pdf-encryption':
            result={'encryption':[]}
            for _,data,_ in docs:
                r=PdfReader(io.BytesIO(data));enc=r.trailer.get('/Encrypt')
                if enc is not None:
                    enc=enc.get_object();result['encryption'].append({'encrypted':True,'version':int(enc.get('/V',0)),'revision':int(enc.get('/R',0)),'length':int(enc.get('/Length',40))})
                else:result['encryption'].append({'encrypted':False})
        elif kind=='pdf-digital-signature':
            import subprocess,tempfile
            from cryptography.hazmat.primitives.serialization.pkcs7 import load_der_pkcs7_certificates
            values=[]
            for _,data,_ in docs:
                r=PdfReader(io.BytesIO(data));found=[]
                for f in (r.get_fields() or {}).values():
                    if str(f.get('/FT'))!='/Sig':continue
                    sig=f.get('/V');sig=sig.get_object() if hasattr(sig,'get_object') else sig
                    assert sig,'Signature value missing';br=[int(x) for x in sig['/ByteRange']]
                    assert len(br)==4 and br[0]==0 and br[2]+br[3]==len(data),'Signature does not cover document'
                    signed=data[:br[1]]+data[br[2]:br[2]+br[3]];cms=bytes(sig['/Contents'])
                    certs=load_der_pkcs7_certificates(cms);assert certs,'No signing certificate'
                    with tempfile.TemporaryDirectory() as temp:
                        t=Path(temp);(t/'signature.der').write_bytes(cms);(t/'content.bin').write_bytes(signed)
                        done=subprocess.run(['openssl','cms','-verify','-inform','DER','-binary','-noverify','-in',str(t/'signature.der'),'-content',str(t/'content.bin'),'-out',str(t/'verified.bin')],capture_output=True,timeout=20)
                        assert done.returncode==0,'Digital signature is invalid'
                    found.append({'subject':certs[0].subject.rfc4514_string(),'reason':str(sig.get('/Reason','')),'location':str(sig.get('/Location','')),'contact':str(sig.get('/ContactInfo',''))})
                assert found,'No digital signature';values.append(found)
            result={'signatures':values}
        elif kind=='pdf-permissions':result={'permissions':[int(d.permissions)&3900 for _,_,d in docs]}
        elif kind=='pdf-layers':result={'layers':[sorted(v['name'] for v in d.get_ocgs().values()) for _,_,d in docs]}
        elif kind=='pdf-fonts-outlined':result={'fontless':[len(p.get_fonts())==0 for p in ps]}
        elif kind=='pdf-linearized':result={'linearized':[bool(re.search(rb'/Linearized\s+[\d.]+',data[:2048])) for _,data,_ in docs]}
        else:raise ValueError('Unknown PDF projection '+kind)
    elif kind.startswith('image-'):
        ims=output.images()
        if kind=='image-format':result={'formats':[im.format for _,_,im in ims]}
        elif kind=='image-size':result={'sizes':[list(im.size) for _,_,im in ims]}
        elif kind=='image-content':result={'tiles':[tiles(im) for _,_,im in ims]}
        elif kind=='image-alpha':result={'alpha':[list(im.convert('RGBA').getextrema()[3]) for _,_,im in ims]}
        elif kind=='image-frames':result={'frames':[getattr(im,'n_frames',1) for _,_,im in ims]}
        else:raise ValueError(kind)
    elif kind=='text':
        texts=[norm(data.decode('utf-8-sig')) for n,data in output.expanded() if Path(n).suffix.lower() in {'.txt','.md','.csv','.xml','.svg','.html'}]
        assert texts and any(texts),'No text output';result={'texts':sorted(texts)}
    elif kind=='text-contains':
        texts='\n'.join(data.decode('utf-8-sig','replace') for _,data in output.expanded())
        result={'present':{s:s in texts for s in spec['texts']}}
        if spec.get('require_all',True):assert all(result['present'].values()),'Requested output text is missing'
    elif kind in {'office-xml','office-text'}:
        import xml.etree.ElementTree as ET
        contents=[]
        for name,data in output.expanded():
            if not name.endswith(('.docx','.xlsx')):continue
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                paths=[spec['member']] if kind=='office-xml' else [n for n in z.namelist() if n.startswith(('word/','xl/')) and n.endswith('.xml')]
                contents.append(norm(' '.join(' '.join(ET.fromstring(z.read(n)).itertext()) for n in paths)))
        assert contents and any(contents),'No Office document content'
        result={'texts':contents} if kind=='office-xml' else {'contains':{t:any(t in text for text in contents) for t in spec['texts']}}
        if kind=='office-text':assert all(result['contains'].values()),'Missing table values'
    elif kind=='json-page-text':
        vals=[]
        for name,data in output.expanded():
            if name.endswith('.json'):
                v=json.loads(data);assert isinstance(v,list) and v,'No extracted documents';vals.extend(norm(x.get('text','')) for x in v)
        assert vals and all(vals),'Missing extracted page text';result={'texts':vals}
    elif kind=='json-structure':return semantics.json_projection(output)
    elif kind=='bookmark-json':
        vals=[]
        def bookmark(v):
            if isinstance(v,list):return [bookmark(x) for x in v]
            if isinstance(v,dict):return {k:bookmark(x) for k,x in v.items() if k.lower() not in {'id','expanded','selected'}}
            return v
        for n,data in output.expanded():
            if n.endswith('.json'):vals.append(bookmark(json.loads(data)))
        assert vals,'No bookmark JSON';result={'bookmarks':vals}
    elif kind=='workflow-json':return semantics.observe(ctx,cp,dict(spec,kind='workflow-graph'))
    elif kind=='json':
        values=[]
        for n,data in output.expanded():
            if n.lower().endswith('.json'):
                try:values.append(json.loads(data))
                except Exception:raise AssertionError('Invalid JSON output') from None
        assert values,'No JSON output';result={'values':values}
    elif kind=='csv':
        import csv
        rows=[]
        for n,data in output.expanded():
            if n.lower().endswith('.csv'):rows.append(semantics.numeric_csv(list(csv.reader(io.StringIO(data.decode('utf-8-sig'))))))
        assert rows and any(rows),'No CSV rows';result={'rows':rows}
    elif kind=='clipboard-json':
        text=ctx.broker.call({'op':'clipboard'}).get('text','')
        try:value=json.loads(text)
        except Exception:raise AssertionError('Clipboard does not contain JSON') from None
        result={'fields':{k:value.get(k) for k in spec['fields']}}
    elif kind=='no-download':
        result={'empty':not ctx.broker.call({'op':'snapshot'}).get('downloads')}
    else:raise ValueError('Unknown check '+kind)
    assert isinstance(result,dict) and result,'Empty observation'
    return result
