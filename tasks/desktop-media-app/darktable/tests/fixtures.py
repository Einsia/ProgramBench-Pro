"""Deterministic synthetic photographs and public XMP sidecar documents."""
import colorsys
import functools
import struct
from xml.sax.saxutils import escape, quoteattr

import numpy as np
import imaging


@functools.lru_cache(None)
def pixels(kind='chart', width=192, height=144):
    y, x = np.mgrid[:height, :width].astype(float)
    u, v = x / (width - 1), y / (height - 1)
    if kind == 'chart':
        a = np.stack((u, v, .12 + .76 * (1-u) * (1-v)), axis=2)
        a[height//3:height//2] = u[height//3:height//2, :, None]
        for j, color in enumerate(((1,.05,.05),(.05,1,.05),(.05,.05,1),(1,1,.05),(.05,1,1),(1,.05,1))):
            a[:height//5,j*width//6:(j+1)*width//6] = color
        a[-height//6:, :width//5] = .02
        a[-height//6:, -width//5:] = .98
    elif kind == 'texture':
        rng = np.random.RandomState(42)
        a = np.stack((.5+.25*np.sin(x*.6), .45+.25*np.cos(y*.9), .2+.6*((x//7+y//11)%2)),axis=2)
        a += rng.normal(0,.07,a.shape)
        a[height//3:2*height//3, width//3:2*width//3] = [.88,.32,.07]
    elif kind == 'portrait':
        a = np.stack((.1+.25*u,.15+.35*v,.35+.25*u),axis=2)
        head=((u-.49)/.27)**2+((v-.48)/.4)**2 < 1
        shade=np.clip(.7-.25*u-.15*v,0,1)
        a[head]=np.stack((shade+.25,shade,shade*.73),axis=2)[head]
        for cx in (.4,.58):
            a[((u-cx)/.025)**2+((v-.4)/.02)**2<1]=[.04,.02,.01]
        a[((u-.49)/.08)**2+((v-.64)/.025)**2<1]=[.5,.08,.07]
    elif kind == 'hdr':
        a = np.stack((2**(u*10-6),2**(v*9-6),2**((1-u)*8-5)),axis=2)
        return a
    else:
        raise ValueError(kind)
    return np.clip(a,0,1)


@functools.lru_cache(None)
def image(name):
    if name=='bright.dtstyle':
        params=exposure(1.5)['params']
        return ('<?xml version="1.0"?><darktable_style version="1.0"><info><name>Bright study</name><description>Exposure example</description></info><style><plugin><num>0</num><module>7</module><operation>exposure</operation><op_params>'+params+'</op_params><enabled>1</enabled><blendop_params/><blendop_version>14</blendop_version><multi_priority>0</multi_priority><multi_name/><multi_name_hand_edited>0</multi_name_hand_edited></plugin></style></darktable_style>').encode()
    if name=='walk.gpx':
        return b'''<?xml version="1.0"?><gpx version="1.1" creator="fixture" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Test walk</name><trkseg><trkpt lat="51.499" lon="-0.121"><ele>35</ele><time>2023-12-31T23:59:30Z</time></trkpt><trkpt lat="51.501" lon="-0.119"><ele>36</ele><time>2024-01-01T00:00:30Z</time></trkpt></trkseg></trk></gpx>'''
    if name=='mask.png':
        y,x=np.mgrid[:144,:192];a=np.stack((x/191,y/143,(x>95).astype(float)),axis=2)
        return imaging.encode_png(a,16)
    kind=name.split('.')[0].split('-')[0]
    data=pixels(kind,768,576) if "-large" in name else pixels(kind)
    if name.endswith('.dng'):
        return dng(data)
    if name.endswith('.pfm'):
        return imaging.encode_pfm(data)
    if '-gray' in name:
        data=data.mean(axis=2,keepdims=True)
    if '-alpha' in name:
        alpha=np.linspace(0,1,data.shape[1])[None,:,None]
        data=np.concatenate((data,np.broadcast_to(alpha,(*data.shape[:2],1))),axis=2)
    if name.endswith('.ppm'):
        return ('P6\n%d %d\n65535\n' % (data.shape[1],data.shape[0])).encode()+np.rint(data*65535).astype('>u2').tobytes()
    return imaging.encode_png(data,8 if '-8' in name else 16)


def dng(data):
    """An uncompressed Bayer DNG, constructed from synthetic linear sensor samples."""
    h,w=data.shape[:2];raw=np.empty((h,w),dtype='<u2')
    for y,x,ch in ((0,0,0),(0,1,1),(1,0,1),(1,1,2)):
        raw[y::2,x::2]=np.rint(512+np.clip(data[y::2,x::2,ch],0,1)*62000).astype('<u2')
    specs=[(256,4,[w]),(257,4,[h]),(258,3,[16]),(259,3,[1]),(262,3,[32803]),
           (271,2,b'Program Bench\0'),(272,2,b'Synthetic Bayer\0'),(273,4,[0]),(274,3,[1]),
           (277,3,[1]),(278,4,[h]),(279,4,[raw.nbytes]),(33421,3,[2,2]),(33422,1,[0,1,1,2]),
           (50706,1,[1,4,0,0]),(50707,1,[1,1,0,0]),(50708,2,b'Synthetic Bayer\0'),
           (50713,3,[1,1]),(50714,5,[(512,1)]),(50717,4,[62512]),
           (50719,4,[0,0]),(50720,4,[w,h]),
           (50721,10,[(1,1),(0,1),(0,1),(0,1),(1,1),(0,1),(0,1),(0,1),(1,1)]),
           (50728,5,[(1,1)]*3),(50778,3,[21]),(50829,4,[0,0,h,w])]
    specs.sort();start=8+2+12*len(specs)+4;chunks=bytearray();entries=[]
    for tag,kind,value in specs:
        if kind in (1,2):body=bytes(value)
        elif kind==3:body=struct.pack('<'+'H'*len(value),*value)
        elif kind==4:body=struct.pack('<'+'I'*len(value),*value)
        else:body=b''.join(struct.pack('<ii' if kind==10 else '<II',*v) for v in value)
        if len(body)<=4:slot=body.ljust(4,b'\0')
        else:
            slot=struct.pack('<I',start+len(chunks));chunks.extend(body)
            if len(chunks)%2:chunks.append(0)
        entries.append((tag,kind,len(value),slot))
    raw_offset=start+len(chunks)
    entries=[(tag,kind,count,struct.pack('<I',raw_offset) if tag==273 else slot) for tag,kind,count,slot in entries]
    return b'II*\0'+struct.pack('<I',8)+struct.pack('<H',len(entries))+b''.join(struct.pack('<HHI',t,k,n)+v for t,k,n,v in entries)+b'\0'*4+chunks+raw.tobytes()


def history_item(operation, params, version, **extra):
    return dict(operation=operation, params=params, modversion=version, enabled=1,
                multi_priority=0, multi_name='', **extra)


def exposure(ev=1.0, black=0.0, enabled=1):
    return dict(operation='exposure', modversion=7, enabled=enabled, multi_priority=0,
                multi_name='', params=struct.pack('<iffffii',0,black,ev,50,-4,0,1).hex())


DEFAULT_ORDER = 'rawprepare,0,invert,0,temperature,0,rasterfile,0,highlights,0,cacorrect,0,hotpixels,0,rawdenoise,0,demosaic,0,colorin,0,denoiseprofile,0,bilateral,0,rotatepixels,0,scalepixels,0,lens,0,cacorrectrgb,0,hazeremoval,0,ashift,0,flip,0,enlargecanvas,0,overlay,0,clipping,0,liquify,0,spots,0,retouch,0,exposure,0,mask_manager,0,tonemap,0,toneequal,0,crop,0,graduatednd,0,profile_gamma,0,equalizer,0,channelmixerrgb,0,diffuse,0,censorize,0,negadoctor,0,blurs,0,primaries,0,nlmeans,0,colorchecker,0,defringe,0,atrous,0,lowpass,0,highpass,0,sharpen,0,colortransfer,0,colormapping,0,channelmixer,0,basicadj,0,colorharmonizer,0,colorbalance,0,colorequal,0,colorbalancergb,0,rgbcurve,0,rgblevels,0,basecurve,0,filmic,0,sigmoid,0,agx,0,filmicrgb,0,lut3d,0,colisa,0,tonecurve,0,levels,0,shadhi,0,zonesystem,0,globaltonemap,0,relight,0,bilat,0,colorcorrection,0,colorcontrast,0,velvia,0,vibrance,0,colorzones,0,bloom,0,colorize,0,lowlight,0,monochrome,0,grain,0,soften,0,splittoning,0,vignette,0,colorreconstruct,0,finalscale,0,colorout,0,clahe,0,overexposed,0,rawoverexposed,0,dither,0,borders,0,watermark,0,gamma,0'


def xmp(history=(), *, end=None, rating=1, labels=(), title='', description='', creator='', rights='', tags=(), extra=None, masks=()):
    """A sidecar in the product's documented RDF history and standard metadata namespaces."""
    attrs={'xmp:Rating':str(rating),'darktable:xmp_version':'5',
           'darktable:history_end':str(len(history) if end is None else end),
           'darktable:iop_order_version':'2', 'darktable:auto_presets_applied':'1',
           'darktable:raw_params':'0'}
    if any(int(h.get('multi_priority',0)) for h in history):
        parts=DEFAULT_ORDER.split(',');ordered=[]
        for op,priority in zip(parts[::2],parts[1::2]):
            priorities=sorted({int(h.get('multi_priority',0)) for h in history if h['operation']==op} | {0})
            for instance in priorities:ordered.extend([op,str(instance)])
        attrs['darktable:iop_order_list']=','.join(ordered)
        attrs['darktable:iop_order_version']='0'
    attrs.update(extra or {})
    header=' '.join(k+'='+quoteattr(str(v)) for k,v in attrs.items())
    items=[]
    for i, entry in enumerate(history):
        entry={'num':i,**entry}
        attrs=' '.join('darktable:'+k+'='+quoteattr(str(v)) for k,v in entry.items())
        items.append('<rdf:li><rdf:Description '+attrs+'/></rdf:li>')
    meta=''
    for key,value in (('title',title),('description',description),('rights',rights)):
        if value:
            meta+=f'<dc:{key}><rdf:Alt><rdf:li xml:lang="x-default">{escape(value)}</rdf:li></rdf:Alt></dc:{key}>'
    if creator:
        meta+='<dc:creator><rdf:Seq><rdf:li>'+escape(creator)+'</rdf:li></rdf:Seq></dc:creator>'
    if tags:
        meta+='<dc:subject><rdf:Bag>'+''.join('<rdf:li>'+escape(t)+'</rdf:li>' for t in tags)+'</rdf:Bag></dc:subject>'
        meta+='<lr:hierarchicalSubject><rdf:Bag>'+''.join('<rdf:li>'+escape(t)+'</rdf:li>' for t in tags)+'</rdf:Bag></lr:hierarchicalSubject>'
    if labels:
        meta+='<darktable:colorlabels><rdf:Seq>'+''.join('<rdf:li>'+str(i)+'</rdf:li>' for i in labels)+'</rdf:Seq></darktable:colorlabels>'
    if masks:
        meta+='<darktable:masks_history><rdf:Seq>'+''.join('<rdf:li><rdf:Description '+
            ' '.join('darktable:'+k+'='+quoteattr(str(v)) for k,v in row.items())+'/></rdf:li>' for row in masks)+'</rdf:Seq></darktable:masks_history>'
    return ('''<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="test document">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:darktable="http://darktable.sf.net/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:lr="http://ns.adobe.com/lightroom/1.0/" xmlns:exif="http://ns.adobe.com/exif/1.0/" '''+header+'>'+meta+
        '<darktable:history><rdf:Seq>'+''.join(items)+'</rdf:Seq></darktable:history>'+
        '</rdf:Description></rdf:RDF></x:xmpmeta>').encode()
