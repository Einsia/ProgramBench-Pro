"""Read only the semantic fields exercised by a check, from public output files."""
import base64
import json
import re
import struct
import subprocess
import zlib
from pathlib import Path
import xml.etree.ElementTree as ET

import imaging
import numpy as np

NS={'dt':'http://darktable.sf.net/','rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp':'http://ns.adobe.com/xap/1.0/','dc':'http://purl.org/dc/elements/1.1/',
    'lr':'http://ns.adobe.com/lightroom/1.0/'}


def gps(data):
    root=ET.fromstring(data);desc=root.find('.//rdf:RDF/rdf:Description',NS)
    result={}
    for key,tag in (('latitude','GPSLatitude'),('longitude','GPSLongitude')):
        v=desc.get('{http://ns.adobe.com/exif/1.0/}'+tag,'');assert v,'missing coordinate '+key
        sign=-1 if v[-1:] in ('W','S') else 1;parts=[float(s) for s in v.rstrip('NSEW').split(',')]
        result[key]=sign*(parts[0]+(parts[1]/60 if len(parts)>1 else 0)+(parts[2]/3600 if len(parts)>2 else 0))
    return result


def sidecar(data):
    try:
        root=ET.fromstring(data)
    except ET.ParseError as exc:
        raise AssertionError('invalid XMP document') from exc
    desc=root.find('.//rdf:RDF/rdf:Description',NS)
    assert desc is not None,'XMP description missing'
    def field(prefix,name,default=None):
        return desc.get('{'+NS[prefix]+'}'+name,default)
    def seq(path):return [n.text or '' for n in root.findall(path,NS)]
    history=[]
    for li in root.findall('.//dt:history/rdf:Seq/rdf:li',NS):
        node=li.find('rdf:Description',NS)
        if node is None:node=li
        h={key.rsplit('}',1)[-1]:v for key,v in node.attrib.items() if key.startswith('{'+NS['dt']+'}')}
        for n in node:
            if n.tag.startswith('{'+NS['dt']+'}'):h[n.tag.rsplit('}',1)[-1]]=n.text or ''
        history.append(h)
    end=int(field('dt','history_end',len(history)))
    result={'rating':int(field('xmp','Rating',0)),
            'labels':sorted(int(v) for v in seq('.//dt:colorlabels/rdf:Seq/rdf:li')),
            'tags':sorted(t for t in seq('.//lr:hierarchicalSubject/rdf:Bag/rdf:li') if not t.startswith('darktable|')),
            'history':history[:end]}
    for key in ('title','description','rights','creator'):
        values=seq('.//dc:'+key+'/*/rdf:li')
        result[key]=values[0] if values else ''
    return result


def binary(value):
    if value.startswith('gz'):
        return zlib.decompress(base64.b64decode(value[4:]))
    return bytes.fromhex(value)


def module(data, name, fields=()):
    entries=[h for h in sidecar(data)['history'] if h.get('operation')==name]
    assert entries, 'the saved history has no '+name+' operation'
    h=entries[-1]
    result={'enabled':int(h.get('enabled','0'))}
    blob=binary(h.get('params',''))
    for label,kind,offset in fields:
        try:result[label]=struct.unpack_from('<'+kind,blob,offset)[0]
        except struct.error:raise AssertionError('invalid '+name+' parameters') from None
    return result


def image(data,suffix,scratch):
    if suffix=='.png':a,_=imaging.decode_png(data)
    elif suffix=='.pfm':a,_=imaging.decode_pfm(data)
    elif suffix in ('.ppm','.pgm','.pnm'):a,_=imaging.decode_pnm(data)
    elif suffix=='.jxl':
        import imagecodecs
        a=imagecodecs.jpegxl_decode(data)
        if np.issubdtype(a.dtype,np.integer):a=a.astype(float)/np.iinfo(a.dtype).max
        if a.ndim==2:a=np.repeat(a[:,:,None],3,axis=2)
    elif suffix=='.exr':
        import OpenEXR
        path=Path(scratch)/'decode.exr';path.write_bytes(data)
        with OpenEXR.File(str(path),separate_channels=True) as f:
            channels=f.channels()
            assert all(c in channels for c in ('R','G','B')),'EXR lacks RGB channels'
            a=np.stack([channels[c].pixels for c in ('R','G','B')],axis=2).astype(float)
    elif suffix=='.pdf':
        import pypdfium2 as pdfium
        doc=pdfium.PdfDocument(data)
        assert len(doc)==1,'expected one exported PDF page'
        page=doc[0];bitmap=page.render(scale=2)
        a=bitmap.to_numpy().copy()[:,:,2::-1].astype(float)/255
        bitmap.close();page.close();doc.close()
        mask=np.min(a,axis=2)<.98
        ys,xs=np.nonzero(mask)
        assert len(xs)>30,'PDF contains no visible image content'
        a=a[ys.min():ys.max()+1,xs.min():xs.max()+1]
    elif suffix=='.xcf':a=xcf_pixels(data)
    else:
        path=Path(scratch)/('decode'+suffix);path.write_bytes(data)
        out=Path(scratch)/'decode.png'
        done=subprocess.run(['convert',str(path)+'[0]','-alpha','off','-depth','16','PNG48:'+str(out)],capture_output=True,timeout=30)
        assert done.returncode==0 and out.is_file(),'image output cannot be decoded'
        a,_=imaging.decode_png(out.read_bytes())
    if a.shape[2]==4:a=a[:,:,:3]
    return imaging.projection(a)


def xcf_pixels(data):
    """Decode the base RGB layer of an XCF image independently of the exporter."""
    assert data.startswith(b'gimp xcf '),'invalid XCF signature'
    version=0 if data[9:13]==b'file' else int(data[10:13])
    pointer='>Q' if version>=11 else '>I';ps=struct.calcsize(pointer)
    def u32(pos):return struct.unpack_from('>I',data,pos)[0]
    def ptr(pos):return struct.unpack_from(pointer,data,pos)[0]
    width,height,kind=struct.unpack_from('>III',data,14)
    precision=u32(26) if version>=4 else 150
    assert width>0 and height>0 and width*height<20000000 and kind==0,'unsupported XCF image'
    def props(pos):
        out={}
        for _ in range(1000):
            tag,size=struct.unpack_from('>II',data,pos);pos+=8
            if tag==0:return out,pos
            assert pos+size<=len(data),'truncated XCF properties'
            out[tag]=data[pos:pos+size];pos+=size
        raise AssertionError('XCF property limit')
    properties,pos=props(30 if version>=4 else 26);compression=properties.get(17,b'\0')[0]
    layer=ptr(pos);assert layer,'XCF has no image layer'
    w,h,layer_type=struct.unpack_from('>III',data,layer);assert (w,h)==(width,height) and layer_type in (0,1),'unexpected XCF layer'
    pos=layer+12;size=u32(pos);pos+=4+size;_,pos=props(pos);hierarchy=ptr(pos)
    w,h,bpp=struct.unpack_from('>III',data,hierarchy);level=ptr(hierarchy+12)
    channels=3 if layer_type==0 else 4
    typ={100:'u1',150:'u1',200:'>u2',250:'>u2',300:'>u4',350:'>u4',500:'>f2',550:'>f2',600:'>f4',650:'>f4',700:'>f8',750:'>f8'}[precision]
    assert np.dtype(typ).itemsize*channels==bpp,'invalid XCF sample layout'
    result=np.empty((h,w,channels),dtype=float);index=0
    for y in range(0,h,64):
        for x in range(0,w,64):
            offset=ptr(level+8+index*ps);index+=1;tw,th=min(64,w-x),min(64,h-y);n=tw*th*bpp
            if compression==2:raw=zlib.decompress(data[offset:])
            elif compression==0:raw=data[offset:offset+n]
            else:raise AssertionError('XCF compression requires a supported independent decoder')
            assert len(raw)==n,'truncated XCF tile'
            samples=np.frombuffer(raw,dtype=typ).reshape(th,tw,channels).astype(float)
            if np.issubdtype(np.dtype(typ),np.integer):samples/=np.iinfo(np.dtype(typ)).max
            result[y:y+th,x:x+tw]=samples
    return result[:,:,:3]


def require_container(data,suffix,scratch):
    expected={'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.tif':'TIFF','.tiff':'TIFF',
              '.webp':'WEBP','.jxl':'JXL','.exr':'EXR','.xcf':'XCF','.pdf':'PDF'}[suffix]
    actual=metadata(data,suffix,scratch,['FileType'])['FileType']
    assert actual and (actual==expected or expected=='JXL' and actual=='JXL Codestream'), 'wrong image container'
    return expected


def style(data):
    try:root=ET.fromstring(data)
    except ET.ParseError:raise AssertionError('invalid dtstyle document') from None
    assert root.tag=='darktable_style','not a darktable style document'
    name=root.findtext('info/name');description=root.findtext('info/description') or ''
    assert name,'style name missing'
    exposures=[]
    for entry in root.findall('style/plugin'):
        if entry.findtext('operation')=='exposure' and entry.findtext('enabled')=='1':
            p=binary(entry.findtext('op_params') or '')
            assert len(p)>=12,'invalid style exposure parameters'
            exposures.append(round(struct.unpack_from('<f',p,8)[0],5))
    assert exposures,'style lacks the requested exposure edit'
    return {'name':name,'description':description,'exposures':exposures}


def metadata(data,suffix,scratch,fields):
    path=Path(scratch)/('metadata'+suffix);path.write_bytes(data)
    done=subprocess.run(['exiftool','-json','-n',*[('-'+f) for f in fields],str(path)],capture_output=True,timeout=15)
    assert done.returncode==0,'output metadata cannot be decoded'
    rows=json.loads(done.stdout)
    assert rows and isinstance(rows[0],dict),'missing metadata'
    result={f:rows[0].get(f) for f in fields}
    for key in ('Subject','HierarchicalSubject','Keywords'):
        if result.get(key) is not None:
            result[key]=sorted(result[key] if isinstance(result[key],list) else [result[key]])
    return result


def quantization(data):
    """JPEG quantizer strength, an encoding fact independent of entropy coding."""
    assert data.startswith(b'\xff\xd8'),'not a JPEG'
    pos=2;tables=[]
    while pos+4<len(data):
        if data[pos]!=255:break
        marker=data[pos+1];pos+=2
        if marker in (0xda,0xd9):break
        size=int.from_bytes(data[pos:pos+2],'big');body=data[pos+2:pos+size];pos+=size
        if marker==0xdb:
            while body:
                wide=body[0]>>4;table=body[1:1+64*(1+wide)]
                values=struct.unpack('>64H',table) if wide else table
                tables.append(round(sum(values)/64,3));body=body[1+64*(1+wide):]
    assert tables,'missing JPEG quantization tables'
    return tables


def webp_encoding(data):
    assert data[:4]==b'RIFF' and data[8:12]==b'WEBP','not a WebP image'
    pos=12
    while pos+8<=len(data):
        name=data[pos:pos+4];size=int.from_bytes(data[pos+4:pos+8],'little')
        if name in (b'VP8 ',b'VP8L'):return 'lossless' if name==b'VP8L' else 'lossy'
        pos+=8+size+(size%2)
    raise AssertionError('WebP contains no image bitstream')
