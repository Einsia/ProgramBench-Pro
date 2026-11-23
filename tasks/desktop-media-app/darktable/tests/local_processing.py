"""Deterministic local masks, repair shapes and discrete deformation documents."""
import struct
import fixtures
import resources
import semantic


def cases():
    result=[]
    for algorithm in (1,2,3,4):
        for shape in ('circle','ellipse'):
            for center in ((.32,.36),(.7,.65)):
                result.append(dict(id=f'retouch-{algorithm}-{shape}-{center[0]}',feature='repair',kind='retouch',
                    algorithm=algorithm,shape=shape,center=list(center),label=f'Retouch with algorithm {algorithm}, {shape} at {center}'))
    for mode in (0,1,2):
        for dx,dy in (((44.,0.),(0.,-44.)) if mode==0 else ((72.,0.),)):
            for radius in (45.,70.):
                result.append(dict(id=f'liquify-{mode}-{dx}-{radius}',feature='liquify',kind='liquify',mode=mode,dx=dx,dy=dy,radius=radius,
                    label=f'Apply a discrete liquify control point, mode {mode}, displacement ({dx},{dy}), radius {radius}'))
    for threshold in (.04,.12,.3):
        result.append(dict(id=f'raw-denoise-{threshold}',feature='raw-denoise',kind='raw-denoise',threshold=threshold,
                           label=f'Denoise Bayer sensor samples with noise threshold {threshold}'))
    for source in ('exposure','rasterfile'):
        for inverse in (False,True):
            for channel in ((1,2,4) if source=='rasterfile' else (0,)):
                result.append(dict(id=f'raster-{source}-{inverse}-{channel}',feature='raster-masks',kind='raster',source=source,inverse=inverse,channel=channel,
                    label=f'Reuse {source} raster mask, inverse {inverse}, channel {channel}'))
    for scale,opacity in ((50.,100.),(100.,45.)):
        result.append(dict(id=f'composite-{scale}-{opacity}',feature='composite',kind='composite',scale=scale,opacity=opacity,
                           label=f'Composite the portrait over the chart at scale {scale} and opacity {opacity}'))
    return result


def history(case,c):
    kind=case['kind'];metadata={};source='chart.png'
    if kind=='retouch':
        algo=case['algorithm'];x,y=case['center'];points=struct.pack('<4f',x,y,.18,.04)
        masktype=(1 if case['shape']=='circle' else 32)|(8 if algo in (1,2) else 128)
        if case['shape']=='ellipse':points=struct.pack('<6fi',x,y,.24,.11,25.,.04,0)
        shape=resources.form(21,masktype,points);shape['mask_src']=struct.pack('<2f',.8 if x<.5 else .18,.2).hex()
        group=resources.form(22,12,struct.pack('<iiif',21,22,3,1.))
        p=bytearray(13260)
        struct.pack_into('<4ififfffi',p,0,21,0,algo,0,18.,1,1.,.05,.1,.0,2)
        struct.pack_into('<4i3fififfffi',p,13200,algo,0,0,0,-3.,0.,3.,0,10.,1,1.,.05,.1,0.,400)
        blend=resources.blend(mode=0,mask=22)
        entry=fixtures.history_item('retouch',p.hex(),3,blendop_params=blend,blendop_version=14)
        metadata={'masks':[shape,group]};items=[entry]
    elif kind=='liquify':
        p=bytearray(7600);x,y=80.,48.
        struct.pack_into('<4i4b8f2i4f',p,0,1,3,0,0,-1,0,-1,0,x,y,x+case['dx'],y+case['dy'],x+case['radius'],y,.5,.75,case['mode'],0,0.,0.,0.,0.)
        items=[fixtures.history_item('liquify',p.hex(),1)]
    elif kind=='raw-denoise':
        p=struct.pack('<41f',case['threshold'],*([0.,.25,.5,.75,1.]*4),*([.5]*20))
        items=[fixtures.history_item('rawdenoise',p.hex(),2)];source='texture.dng'
    elif kind=='raster':
        if case['source']=='exposure':
            shape=resources.form(21,129,struct.pack('<4f',.4,.5,.25,.05));group=resources.form(22,4,struct.pack('<iiif',21,22,3,1.))
            first={**fixtures.exposure(.2),'blendop_params':resources.blend(mode=3,mask=22),'blendop_version':14}
            metadata={'masks':[shape,group]};source_module='exposure'
        else:
            c.fixture('mask.png')
            p=bytearray(4100);struct.pack_into('<i',p,0,case['channel'])
            folder=(c.area('inputs')+'/').encode();p[4:4+len(folder)]=folder;p[2052:2060]=b'mask.png'
            first=fixtures.history_item('rasterfile',p.hex(),1);source_module='rasterfile'
        b=bytearray.fromhex(resources.blend(mode=9));b[388:408]=source_module.encode().ljust(20,b'\0')
        struct.pack_into('<3i',b,408,0,0,int(case['inverse']))
        # A downstream colorize module consumes the actual upstream mask.
        color=struct.pack('<4fi',.6,.8,50.,45.,2)
        second=fixtures.history_item('colorize',color.hex(),2,blendop_params=b.hex(),blendop_version=14)
        items=[first,second]
    else:raise ValueError(kind)
    return source,items,metadata


def observe(c,case):
    if case['kind']=='composite':
        for name in ('chart.png','portrait.png'):c.fixture(name)
        p=bytearray(1088)
        struct.pack_into('<4fifiiii',p,0,case['opacity'],case['scale'],0.,0.,4,0.,0,3,0,987654)
        path=(c.area('inputs')+'/portrait.png').encode();p[40:40+len(path)]=path
        side=c.name('.xmp');c.upload(side,fixtures.xmp([fixtures.history_item('overlay',p.hex(),1)]))
        prefix=c.name('');reply=c.cli(['--import','portrait.png','--import','chart.png',side,c.area('outputs')+'/'+prefix+'-$(FILE_NAME).png'])
        assert reply['exit_code']==0,'composite export failed'
        return {'image':semantic.image(c.fetch('outputs/'+prefix+'-chart.png'),'.png',c.scratch)}
    source,items,metadata=history(case,c)
    data,_=c.render(source,history=items,metadata=metadata)
    return {'image':semantic.image(data,'.png',c.scratch)}
