"""Independent program episodes exercising the real exporter and document formats."""
import functools
import json
import struct
from pathlib import Path

import fixtures
import semantic
import resources
import local_processing


def conf(**values):
    return ['--core',*[v for k,value in values.items() for v in ('--conf',k+'='+str(value))]]


def metadata_options():
    return conf(**{**{'plugins/lighttable/metadata/'+name+'_flag':4 for name in ('title','creator','description','rights')},
                   'plugins/lighttable/export/metadata_flags':'2f'})


@functools.lru_cache(None)
def cases():
    out=[]
    out.extend(resources.cases())
    out.extend(local_processing.cases())
    out.extend(json.loads(Path(__file__).with_name('compatibility_cases.json').read_text()))
    out.extend(json.loads(Path(__file__).with_name('raw_cases.json').read_text()))
    for row in json.loads(Path(__file__).with_name('module_cases.json').read_text()):
        out.append(dict(row,feature='compositing' if row['kind']=='blend' else 'processing',kind='render'))
    for source in ('chart.png','texture.png','chart-gray.png','chart-alpha.png','chart-8.png','chart.ppm','hdr.pfm'):
        for w,h,up in ((96,0,0),(0,72,0),(96,96,0),(80,40,0),(40,80,0),(191,0,0),(0,143,0),(300,300,0),(300,300,1),(384,0,1),(0,216,1),(1,1,0)):
            out.append(dict(id=f'{source}-size-{w}-{h}-{up}',feature='resize',kind='tiny' if w==h==1 else 'render',source=source,
                            label=f'Export {source} within {w} by {h}, upscaling {up}',options=['--width',str(w),'--height',str(h),'--upscale',str(up)]))
    for interp in ('bilinear','bicubic','lanczos2','lanczos3'):
        for source in ('chart.png','texture.png'):
            out.append(dict(id=f'{source}-{interp}',feature='resize',kind='render',source=source,
                label=f'Resample {source} with {interp}',options=['--width','67',*conf(**{'plugins/lighttable/export/pixel_interpolator':interp})]))
    hq_rows=json.loads(Path(__file__).with_name('module_cases.json').read_text())
    for identifier in ('sharpen-enabled','bilat-sigma_r-15p0','bloom-enabled','atrous-preset-01','diffuse-sharpness-0p64'):
        row=next(r for r in hq_rows if r['id']==identifier)
        for hq in ('false','true'):
            out.append(dict(id=f'quality-{identifier}-{hq}',feature='resize-quality',kind='render',source='texture-large.png',
                label=f'Resample a detailed processed image with {identifier} and high quality {hq}',history=row['history'],options=['--width','96','--hq',hq]))
    for profile in ('SRGB','ADOBERGB','LIN_REC709','LIN_REC2020','XYZ','DISPLAY_P3'):
        for intent in ('RELATIVE_COLORIMETRIC',):
            for source in ('chart.png','hdr.pfm'):
                out.append(dict(id=f'{profile}-{intent}-{source}',feature='color-management',kind='render',source=source,
                    label=f'Export {source} to {profile} with {intent} intent',options=['--icc-type',profile,'--icc-intent',intent]))
    contrast=fixtures.history_item('colorcontrast',struct.pack('<4fi',3.6,0.,1.,0.,1).hex(),2)
    colorize=fixtures.history_item('colorize',struct.pack('<4fi',.08,.75,60.,35.,2).hex(),2)
    for source in ('chart.png','texture.png'):
        for reverse in (False,True):
            order=fixtures.DEFAULT_ORDER
            if reverse:
                order=order.replace('colorcontrast,0','temporary,0').replace('colorize,0','colorcontrast,0').replace('temporary,0','colorize,0')
            out.append(dict(id=f'module-order-{source}-{reverse}',feature='module-order',kind='render',source=source,
                label=f'Process {source} with '+('colorize before color contrast' if reverse else 'color contrast before colorize'),
                history=[contrast,colorize],metadata={'extra':{'darktable:iop_order_version':'0','darktable:iop_order_list':order}}))
    # History entries are documents, not precomputed output pictures. Each case tests a distinct history rule.
    for ev in (-2.,-.5,.5,2.):
        for source in ('chart.png','texture.png','hdr.pfm'):
            for mode in ('disabled','truncate','last-wins','two-instances'):
                if mode=='disabled' and ev!=-2.:continue
                a,b=fixtures.exposure(ev),fixtures.exposure(-ev/2)
                meta={}
                if mode=='disabled': a['enabled']=0;history=[a]
                elif mode=='truncate':history=[a,b];meta={'end':1}
                elif mode=='last-wins':history=[a,b]
                else:b['multi_priority']=1;b['multi_name']='second';history=[a,b]
                out.append(dict(id=f'history-{mode}-{ev}-{source}',feature='history',kind='render',source=source,
                    label=f'{source}: {mode} exposure history at {ev} EV',history=history,metadata=meta))
    for suffix in ('.jpg','.png','.tif','.webp'):
        for rating in (-1,0,1,3,5):
            out.append(dict(id=f'metadata-{suffix[1:]}-{rating}',feature='metadata',kind='metadata',source='chart.png',suffix=suffix,
                label=f'Preserve Unicode descriptive metadata and rating {rating} in {suffix}',
                metadata={'rating':rating,'title':'Colour study — 色彩','description':'Line one\nLine two & detail',
                          'creator':'Zoë García','rights':'© 2024 Example','tags':['places|coast','red & blue']},
                options=metadata_options(),
                fields=['Title','Description','Creator','Rights','Rating','Subject']))
    formats={
      '.jpg':('jpeg',[{'quality':q,'subsample':1} for q in (20,75,100)]+[{'quality':90,'subsample':s} for s in (2,3,4)]),
      '.png':('png',[{'bpp':8},{'bpp':16}]),
      '.tif':('tiff',[{'bpp':8,'compress':0},{'bpp':16,'compress':1},{'bpp':32,'compress':1,'pixelformat':0}]),
      '.webp':('webp',[{'comp_type':0,'quality':30},{'comp_type':0,'quality':90},{'comp_type':1}]),
      '.avif':('avif',[{'bpp':b} for b in (8,10,12)]+[{'bpp':8,'color_mode':1}]),
      '.jxl':('jxl',[{}]),
      '.j2k':('j2k',[{}]),
      '.heif':('heif',[{'bitdepth':8},{'bitdepth':10},{'bitdepth':12}]),
      '.exr':('exr',[{'bpp':16},{'bpp':32},{'bpp':32,'compression':0}]),
      '.ppm':('ppm',[{}]),'.pfm':('pfm',[{}]),'.pdf':('pdf',[{}]),'.xcf':('xcf',[{}])}
    for suffix,(fmt,variants) in formats.items():
        for i,values in enumerate(variants):
            out.append(dict(id=f'format-{fmt}-{i}',feature='formats',kind='format',source='texture.png',suffix=suffix,
                label=f'Export {fmt} '+str(values), options=conf(**{'plugins/imageio/format/'+fmt+'/'+k:v for k,v in values.items()}) if values else [],
                fields=['FileType','ImageWidth','ImageHeight','BitsPerSample','BitDepth','Compression','ColorType','YCbCrSubSampling',
                        'ImagePixelDepth','BitsPerComponent','Channels','SampleFormat','ColorMode','ChromaFormat','PageCount']))
    for suffix in ('.jpg','.png','.tif','.webp','.ppm','.pfm','.exr','.j2k','.avif','.jxl','.heif'):
        out.append(dict(id='roundtrip-'+suffix[1:],feature='input-formats',kind='roundtrip',suffix=suffix,
                        label=f'Read a freshly exported {suffix} image back and export PNG'))
    for name,value in [('empty.png',b''),('broken.jpg',b'not an image'),('truncated.png',fixtures.image('chart.png')[:48]),('broken.pfm',b'PF\n20 20\n-1.0\n')]:
        out.append(dict(id='error-'+name,feature='errors',kind='invalid',filename=name,data=value.hex(),label='Reject malformed image '+name))
    patterns=['$(FILE_NAME)','$(FILE_EXTENSION)','$(FILE_NAME^^)','$(FILE_NAME:1:3)',
              '$(FILE_NAME/chart/study)','$(FILE_NAME#ch)','$(FILE_NAME%rt)',
              '$(SEQUENCE)','$(SEQUENCE[4,7])','$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)',
              '$(Xmp.dc.title)','$(Xmp.dc.creator)','$(Xmp.dc.description)','$(Xmp.dc.rights)','$(STARS)','$(LABELS)',
              '$(Xmp.dc.title^^)','$(Xmp.dc.title:0:5)','$(Xmp.dc.title/Coast/Beach)']
    for i,pattern in enumerate(patterns):
        out.append(dict(id=f'filename-{i:02d}',feature='filename-patterns',kind='filename',pattern=pattern,
                        label='Expand output filename pattern '+pattern))
    for mode in ('unique','overwrite','batch','out-ext'):
        out.append(dict(id='export-'+mode,feature='export-behavior',kind=mode,label='Export with '+mode+' behavior'))
    return out


def build():
    episodes=[];groups={}
    for case in cases():groups.setdefault(case['feature'],[]).append(case)
    for feature,rows in groups.items():
        partitions={}
        for position,case in enumerate(rows):
            part=case.get('partition',position//55+1)
            cid=case.get('checkpoint','p%03d'%(position%55))
            clean={k:v for k,v in case.items() if k not in ('partition','checkpoint')}
            partitions.setdefault(part,[]).append((cid,clean))
        for part,part_rows in partitions.items():
            key='program-'+feature+'-%02d'%part
            checkpoints=[]
            for cid,case in part_rows:
                checkpoints.append({'id':cid,'goal':case['label'],'case':case,'assertions':[{
                    'id':key+'/'+cid+'/result','channel':'backend','method':'program',
                    'requirement':case['label']+'. Compare the independently decoded output with the frozen semantic observation.'}]})
            episodes.append({'id':key,'feature':feature,'execution':'program','initial_state':'Fresh application and document folder. Each checkpoint uses its own output name and sidecar; the exporter is a new process for every command.',
                              'setup':[],'inputs':{},'checkpoints':checkpoints})
    return episodes


def observe(c,case):
    kind=case['kind'];suffix=case.get('suffix','.png')
    if kind in ('retouch','liquify','raw-denoise','raster','composite'):return local_processing.observe(c,case)
    if kind in ('lut','watermark','icc-file'):return resources.observe(c,case)
    if kind=='tiny':
        c.fixture(case['source']);output=c.name('.png')
        reply=c.cli([case['source'],output,*case['options']])
        assert reply['exit_code']!=0,'a zero-height export was not rejected'
        return {'rejected':True}
    if kind=='filename':
        c.fixture('chart.png');sidecar=c.name('.xmp')
        c.upload(sidecar,fixtures.xmp(title='Coast Study',creator='Ana',description='Sunny',rights='Example',rating=3,labels=[0,2]))
        prefix=c.name('')+'-';pattern=c.area('outputs')+'/'+prefix+case['pattern']+'.png'
        reply=c.cli(['chart.png',sidecar,pattern,*metadata_options()]);assert reply['exit_code']==0,'filename pattern export failed'
        names=[Path(d['filename']).name for d in reply.get('downloads',[]) if Path(d['filename']).name.startswith(prefix)]
        assert len(names)==1,'filename pattern did not create exactly one image'
        name=names[0][len(prefix):];assert name not in ('.png',''),'filename variable unexpectedly empty'
        return {'filename':name,'image':semantic.image(c.fetch('outputs/'+names[0]),'.png',c.scratch)}
    if kind in ('unique','overwrite'):
        c.fixture('chart.png');out=c.name('.png')
        opts=conf(**{'plugins/imageio/storage/disk/overwrite':1}) if kind=='overwrite' else []
        first=c.cli(['chart.png',out,*opts]);assert first['exit_code']==0
        original=c.fetch('outputs/'+out)
        sidecar=c.name('.xmp');c.upload(sidecar,fixtures.xmp([fixtures.exposure(-2.)]))
        second=c.cli(['chart.png',sidecar,out,*opts]);assert second['exit_code']==0
        found=[d for d in second['downloads'] if d['filename'].startswith('outputs/'+Path(out).stem)]
        assert len(found)==1,'repeated export did not write one image'
        expected='outputs/'+out if kind=='overwrite' else 'outputs/'+Path(out).stem+'_01.png'
        assert found[0]['filename']==expected,'filename conflict behavior differs'
        return {'same_name':found[0]['filename']=='outputs/'+out,'image':semantic.image(c.fetch(expected),'.png',c.scratch)}
    if kind=='batch':
        for n in ('chart.png','portrait.png'):c.fixture(n)
        prefix=c.name('');out=c.area('outputs')+'/'+prefix+'-$(FILE_NAME).png'
        reply=c.cli(['--import','chart.png','--import','portrait.png',out]);assert reply['exit_code']==0
        rows={Path(d['filename']).name[len(prefix)+1:]:semantic.image(c.fetch(d['filename']),'.png',c.scratch) for d in reply['downloads'] if Path(d['filename']).name.startswith(prefix)}
        assert set(rows)=={'chart.png','portrait.png'},'batch export did not produce both images'
        return {'images':{name:{'image':value} for name,value in rows.items()}}
    if kind=='out-ext':
        c.fixture('chart.png');out=c.name('.jpg');reply=c.cli(['chart.png',out,'--out-ext','png']);assert reply['exit_code']==0
        rows=[d for d in reply['downloads'] if Path(d['filename']).name.startswith(Path(out).stem)]
        assert len(rows)==1 and rows[0]['filename'].endswith('.png'),'output extension did not override the name'
        return {'image':semantic.image(c.fetch(rows[0]['filename']),'.png',c.scratch)}
    if kind in ('render','format','metadata'):
        data,_=c.render(case.get('source','chart.png'),case.get('history'),case.get('options',()),suffix,case.get('metadata'))
        if kind=='metadata':
            result=semantic.metadata(data,suffix,c.scratch,case['fields'])
            assert all(v is not None for v in result.values()),'required descriptive metadata was not exported'
            return result
        if kind=='format':
            result=semantic.metadata(data,suffix,c.scratch,case['fields'])
            assert result.get('FileType'),'no recognized image container'
            # Integer and floating formats have different header conventions; ignore absent optional fields.
            result={k:v for k,v in result.items() if v is not None}
            if suffix=='.jpg':result['quantization']=semantic.quantization(data)
            if suffix=='.webp':result['encoding']=semantic.webp_encoding(data)
            result['image']=semantic.image(data,suffix,c.scratch)
            return result
        return {'image':semantic.image(data,suffix,c.scratch)}
    if kind=='roundtrip':
        data,_=c.render('chart.png',suffix=suffix)
        name='roundtrip'+suffix;c.upload(name,data)
        output=c.name('.png');reply=c.cli([name,output]);assert reply['exit_code']==0,'exported image cannot be reimported'
        return {'image':semantic.image(c.fetch('outputs/'+output),'.png',c.scratch)}
    if kind=='invalid':
        c.upload(case['filename'],bytes.fromhex(case['data']))
        out=c.name('.png');reply=c.cli([case['filename'],out]);c.collect()
        assert reply['exit_code']!=0,'malformed image was accepted'
        assert 'outputs/'+out not in c.files,'malformed image produced an export'
        return {'rejected':True}
    raise ValueError(kind)
