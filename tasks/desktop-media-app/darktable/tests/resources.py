"""Public XMP masks, LUT documents and watermarks for local image processing."""
import base64
import struct
import zlib

import fixtures
import semantic

BLEND=zlib.decompress(base64.b64decode('eJxjYGBgYAFiCQYYOOHEgAZY0QWAgBGLGANDgz0Ej1Q+dlAx68oBEMbFxwX+AwGIBgCbGCeh'))


def blend(mode=1,opacity=100.,mask=0,channel=None,limits=None):
    b=bytearray(BLEND);struct.pack_into('<I',b,0,mode);struct.pack_into('<f',b,16,opacity);struct.pack_into('<i',b,24,mask)
    if channel is not None:
        struct.pack_into('<I',b,28,1<<channel)
        struct.pack_into('<4f',b,68+16*channel,*limits)
    return b.hex()


def form(identifier,kind,points):
    return dict(mask_num=0,mask_id=identifier,mask_type=kind,mask_name='shape-'+str(identifier),mask_version=6,
                mask_points=points.hex(),mask_nb=1,mask_src=struct.pack('<2f',0.,0.).hex())


def cases():
    result=[]
    for kind in ('circle','ellipse','gradient'):
        for x,y in ((.3,.35),(.7,.65)):
            for size in (.15,.3):
                if kind=='circle':shape=form(21,1|128,struct.pack('<4f',x,y,size,.05))
                elif kind=='ellipse':shape=form(21,32|128,struct.pack('<6fi',x,y,size,size*.5,25.,.05,0))
                else:shape=form(21,16|128,struct.pack('<6fi',x,y,35.,size,0.,0.,1))
                group=form(22,4,struct.pack('<iiif',21,22,3,1.))
                entry={**fixtures.exposure(1.5),'blendop_version':14,'blendop_params':blend(mode=3,mask=22)}
                result.append(dict(id=f'{kind}-{x}-{size}',feature='masks',kind='render',source='chart.png',history=[entry],
                    metadata={'masks':[shape,group]},label=f'Apply exposure through a feathered {kind} at ({x}, {y}), extent {size}'))
    for channel in range(4):
        for limits in ((0.,0.,.25,.45),(.35,.55,1.,1.)):
            entry={**fixtures.exposure(1.5),'blendop_version':14,'blendop_params':blend(mode=5,channel=channel,limits=limits)}
            result.append(dict(id=f'parametric-{channel}-{limits[0]}',feature='masks',kind='render',source='chart.png',history=[entry],
                label=f'Apply exposure through parametric channel {channel} with limits {limits}'))
    for variant in ('swap','warm','inverse'):
        for colorspace in (0,3,4):
            if (variant,colorspace) in (('swap',3),('inverse',4)):continue
            result.append(dict(id=f'lut-{variant}-{colorspace}',feature='lookup-tables',kind='lut',variant=variant,colorspace=colorspace,
                               label=f'Apply a {variant} cube LUT in color space {colorspace}'))
    for alignment,angle in ((0,0),(2,0),(4,0),(6,0),(8,0),(4,30),(4,-30)):
        result.append(dict(id=f'watermark-{alignment}-{angle}',feature='watermarks',kind='watermark',alignment=alignment,angle=angle,
                           label=f'Place a text watermark at alignment {alignment}, rotation {angle} degrees'))
    result.append(dict(id='icc-file',feature='color-management',kind='icc-file',label='Read an uploaded ICC profile and use it as the output profile'))
    return result


def observe(c,case):
    kind=case['kind']
    if kind=='lut':
        rows=['TITLE "Synthetic cube"','LUT_3D_SIZE 3','DOMAIN_MIN 0 0 0','DOMAIN_MAX 1 1 1']
        for b in (0.,.5,1.):
            for g in (0.,.5,1.):
                for r in (0.,.5,1.):
                    out=(b,r,g) if case['variant']=='swap' else (1-r,1-g,1-b) if case['variant']=='inverse' else (r**.7,g**1.2,b**1.7)
                    rows.append(' '.join(str(v) for v in out))
        c.upload('study.cube',('\n'.join(rows)+'\n').encode());buf=bytearray(12940);buf[:10]=b'study.cube';struct.pack_into('<ii',buf,512,case['colorspace'],0)
        history=[fixtures.history_item('lut3d',buf.hex(),3)]
        data,_=c.render('chart.png',history=history,options=['--core','--conf','plugins/darkroom/lut3d/def_path='+c.area('inputs')])
    elif kind=='watermark':
        buf=bytearray(880);struct.pack_into('<4fifiii',buf,0,100.,55.,0.,0.,case['alignment'],float(case['angle']),0,3,0)
        buf[36:36+len(b'simple-text.svg')]=b'simple-text.svg';buf[292:299]=b'PHOTO 7'
        struct.pack_into('<3f',buf,804,1.,.05,.15);font=b'DejaVu Sans 12';buf[816:816+len(font)]=font
        data,_=c.render('chart.png',history=[fixtures.history_item('watermark',buf.hex(),7)])
    elif kind=='icc-file':
        import imaging
        base,_=c.render('chart.png',options=['--icc-type','LIN_REC2020']);chunks=imaging.png_chunks(base);profile=next(v for k,v in chunks if k=='iCCP')
        profile=zlib.decompress(profile.split(b'\0',1)[1][1:]);c.upload('output.icc',profile)
        data,_=c.render('texture.png',options=['--icc-type','FILE','--icc-file','output.icc'])
    else:raise ValueError(kind)
    return {'image':semantic.image(data,'.png',c.scratch)}
