"""Semantic checks of the files explicitly requested by GUI goals."""
import base64
from collections import Counter
from pathlib import Path
import re
import time
import math
import artifacts


def color(value,background=False):
    """Native-format named colors and numeric RGBA have the same RGB meaning."""
    names={'black':'000000','blue':'3333cc','red':'ff0000','green':'008000','gray':'808080','lightblue':'00c0ff',
           'lightgreen':'00ff00','magenta':'ff00ff','orange':'ff8000','yellow':'ffff00','white':'ffffff'}
    if background:names.update(blue='a0e8ff',pink='ffc0d4',green='80ffc0',orange='ffc080',yellow='ffff80')
    if value.startswith('#'):return f'#{((int(value[1:],16)&0xffffffff)>>8):06x}'
    return '#'+names[value]


def background(value):
    result={k:value[k] for k in ('type','style') if k in value}
    if 'color' in value:result['color']=color(value['color'],True)
    if 'pageno' in value:result['pageno']=int(value['pageno'])
    config={}
    for entry in value.get('config','').split(','):
        if '=' not in entry:continue
        k,v=entry.split('=',1)
        try:v=float(v)
        except ValueError:pass
        config[k.strip()]=v
    if config:result['config']=config
    return result


def collect(ctx,cp):
    if cp['artifact']['kind']=='clipboard':
        result={'kind':'clipboard','text':ctx.broker.call({'op':'clipboard_text'})['text']}
        if cp['artifact'].get('image'):
            result['image']=artifacts.bitmap(base64.b64decode(ctx.broker.call({'op':'clipboard_image'})['png_base64']))
        return result
    desc=cp['artifact'];name=desc['name'];suffix=Path(name).suffix
    deadline=time.monotonic()+20
    names=[];previous=None
    while time.monotonic()<deadline:
        listed=ctx.broker.call({'op':'list_files','area':'outbox'})['files']
        names=sorted([f['name'] for f in listed if (f['name']==name or (desc['kind']=='export' and
                     re.fullmatch(re.escape(Path(name).stem)+r'-\d+'+re.escape(suffix),f['name']))) and not f['read_only']])
        sizes=[(f['name'],f['size']) for f in listed if f['name'] in names]
        if names and sizes==previous and all(s for _,s in sizes):break
        previous=sizes;time.sleep(.25)
    assert names, 'requested file was not written: '+name
    folder=ctx.out/'artifacts'/cp['id'];folder.mkdir(parents=True,exist_ok=True)
    values=[]
    for filename in names:
        data=base64.b64decode(ctx.broker.call({'op':'download','filename':filename})['body_base64'])
        (folder/filename).write_bytes(data)
        values.append(artifacts.measure(data,suffix,folder))
    if desc['kind']=='native':
        assert len(values)==1,'expected one notebook'
        return values[0]
    return {'kind':'export','pages':[p for v in values for p in (v['pages'] if v['kind']=='pdf' else [v])]}


def items(doc):
    return [el for p in doc['pages'] for l in p['layers'] for el in l['items']]


def expect(doc,wanted):
    if 'export-colors' in wanted:
        import io
        from PIL import Image
        expected=wanted['export-colors'];page=doc['pages'][0]
        image=Image.open(io.BytesIO(base64.b64decode(page['render']['png']))).convert('RGB')
        for position,hexcolor in zip(expected['positions'],expected['colors']):
            x=round(position[0]/page['size'][0]*image.width);y=round(position[1]/page['size'][1]*image.height)
            rgb=[int(hexcolor[i:i+2],16) for i in (1,3,5)]
            artifacts.numeric(list(image.getpixel((x,y))),rgb,4)
        return
    all_=items(doc)
    found={'pages':len(doc['pages']),'layers':sum(len(p['layers']) for p in doc['pages']),
           'strokes':sum(x['kind']=='stroke' for x in all_),'images':sum(x['kind']=='image' for x in all_),
           'texts':[x['text'] for x in all_ if x['kind']=='text']}
    for k,v in wanted.items():
        if k=='sizes':
            artifacts.numeric([p['size'] for p in doc['pages']],v,.1)
            continue
        if k=='paper-colors':
            assert [color(p['background']['color'],True) for p in doc['pages']]==v,'reference paper colors differ'
            continue
        if k=='marker':
            strokes=[x for x in all_ if x['kind']=='stroke']
            assert strokes,'reference marker is absent'
            assert all(x['attrs']['tool']=='highlighter' and color(x['attrs']['color'])==v['color'] and
                       abs(int(x['attrs'].get('fill','-1'))-v['fill'])<=1 for x in strokes),'reference marker settings differ'
            continue
        assert found[k]==v,f'reference {k} {found[k]!r} differs from declared {v!r}'


def project(doc,aspect,options=None):
    options=options or {}
    if aspect=='clipboard-text':return {'aspect':aspect,'value':artifacts.normalize_text(doc['text'])}
    if aspect=='clipboard-image':return {'aspect':aspect,'value':doc['image']['render']}
    pages=doc['pages']
    if aspect=='counts':
        value=[[dict(sorted(Counter(el['kind'] for el in l['items']).items())) for l in p['layers']] for p in pages]
    elif aspect=='texts':
        value=[[[el['text'] for el in l['items'] if el['kind']=='text'] for l in p['layers']] for p in pages]
    elif aspect=='text-styles':
        value=[{'text':el['text'],'font':el['attrs'].get('font','Sans'),'size':float(el['attrs']['size']),
                'color':color(el['attrs']['color'])} for el in items(doc) if el['kind']=='text']
    elif aspect=='text-regions':
        value=[{'text':el['text'],'position':[float(el['attrs']['x']),float(el['attrs']['y'])]}
               for el in items(doc) if el['kind']=='text']
        if options.get('placement'):
            return placement(doc,options['placement'])
        if options.get('upper_right_text'):
            value=[]
            for page in pages:
                width,height=page['size']
                for layer in page['layers']:
                    for el in layer['items']:
                        if el['kind']!='text':continue
                        x,y=float(el['attrs']['x']),float(el['attrs']['y'])
                        item={'text':el['text'],'position':[x,y]}
                        if el['text']==options['upper_right_text']:
                            item={'text':el['text'],'region':'upper-right' if width/2<=x<width and 0<=y<height/2 else 'outside-upper-right'}
                        value.append(item)
    elif aspect=='stroke-styles':
        value=[{'tool':el['attrs'].get('tool','pen'),'color':color(el['attrs'].get('color','black')),
                'width':float(el['attrs'].get('width','1').split()[0]),'style':el['attrs'].get('style','plain'),
                'fill':int(el['attrs'].get('fill','-1')),'cap':el['attrs'].get('capStyle','round')}
               for el in items(doc) if el['kind']=='stroke']
        if options.get('eraser_width_unspecified'):
            for item in value:
                if item['tool']=='eraser':item.pop('width')
        if options.get('fields'):
            value=[{field:item[field] for field in options['fields']} for item in value]
        if options.get('unique'):
            value=[dict(entry) for entry in sorted({tuple(sorted(item.items())) for item in value})]
    elif aspect=='backgrounds':
        value=[background(p['background']) for p in pages]
    elif aspect=='sizes':value=[p['size'] for p in pages]
    elif aspect=='layer-names':value=[[l['name'] for l in p['layers']] for p in pages]
    elif aspect=='images':value=[el['image']['render'] for el in items(doc) if el['kind']=='image']
    elif aspect=='image-alpha':value=[el['image']['alpha'] for el in items(doc) if el['kind']=='image']
    elif aspect=='stroke-boxes':value=[el['box'] for el in items(doc) if el['kind']=='stroke']
    elif aspect=='coordinate-axes':return coordinate_axes(doc)
    elif aspect in ('grid-off','grid-on','rotation-off','rotation-on','stabilized','ruler-line','compass-arc'):
        return geometry_result(doc,aspect)
    elif aspect=='export-count':value=len(pages)
    elif aspect=='export-geometry':value=[p['size'] for p in pages]
    elif aspect=='export-render':value=[p['render'] for p in pages]
    elif aspect=='export-overlap-colors':
        import io
        import numpy as np
        from PIL import Image
        assert len(pages)==1,'expected one exported page'
        page=pages[0]
        raster=np.asarray(Image.open(io.BytesIO(base64.b64decode(page['render']['png']))).convert('RGB'))
        value=[]
        for px,py in options['positions']:
            x=round(px/page['size'][0]*raster.shape[1]);y=round(py/page['size'][1]*raster.shape[0])
            patch=raster[y-1:y+2,x-1:x+2]
            assert patch.shape==(3,3,3),'overlap region is outside the exported page'
            value.append(np.median(patch.reshape(-1,3),axis=0).tolist())
    else:raise ValueError(aspect)
    return {'aspect':aspect,'value':value}


def coordinate_axes(doc):
    """Two intersecting axes, whether encoded as one polyline or several strokes."""
    import numpy as np
    assert len(doc['pages'])==1,'expected one coordinate-system page'
    elements=items(doc)
    assert elements and all(e['kind']=='stroke' for e in elements),'expected only the axes'
    segments=[]
    for stroke in elements:
        points=np.asarray(stroke['points'],dtype=float)
        assert np.isfinite(points).all(),'invalid axis geometry'
        parts=[(a,b) for a,b in zip(points,points[1:]) if np.linalg.norm(b-a)>.25]
        assert parts,'isolated dot is not an axis'
        segments.extend(parts)
    lengths=np.array([np.linalg.norm(b-a) for a,b in segments])
    a,b=segments[int(lengths.argmax())];u=(b-a)/np.linalg.norm(b-a)
    v=np.array([-u[1],u[0]]);groups=[[],[]]
    for a,b in segments:
        direction=(b-a)/np.linalg.norm(b-a)
        alignment=[abs(float(direction@axis)) for axis in (u,v)]
        group=int(np.argmax(alignment))
        assert alignment[group]>=math.cos(math.radians(5)),'stroke is not aligned with either axis'
        groups[group].extend([a,b])
    centers=[];extents=[]
    for group,axis,normal in zip(groups,(u,v),(v,u)):
        assert group,'one axis is missing'
        points=np.array(group);across=points@normal;along=points@axis
        assert np.ptp(across)<=4,'axis is not straight or extra parallel lines are present'
        assert np.ptp(along)>=60,'axis is too short'
        centers.append(float((across.max()+across.min())/2))
        extents.append((float(along.min()),float(along.max())))
    # For the u axis, the v-axis offset is its intersection coordinate; vice versa.
    for (low,high),intersection in zip(extents,reversed(centers)):
        assert low-3<=intersection<=high+3,'axes do not intersect'
    return {'aspect':'coordinate-axes','value':True}


def geometry_result(doc,aspect):
    import numpy as np
    strokes=[e for e in items(doc) if e['kind']=='stroke']
    assert strokes,'drawing is missing'
    path=np.array(strokes[-1]['points'],dtype=float)
    assert len(path)>=2 and np.isfinite(path).all(),'invalid stroke geometry'
    if aspect.startswith('grid-'):
        step=72/2.54
        distances=np.abs(path/step-np.round(path/step))*step
        snapped=bool(np.max(distances)<.7)
        assert snapped==(aspect=='grid-on'),'grid snapping does not match the requested state'
    elif aspect.startswith('rotation-'):
        delta=path[-1]-path[0];assert np.linalg.norm(delta)>100,'line is too short'
        angle=abs(math.degrees(math.atan2(delta[1],delta[0])))
        if aspect=='rotation-on':assert angle<.3,'line did not snap to horizontal'
        else:assert .5<angle<10,'unsnapped line lost its slight slope'
    elif aspect=='stabilized':
        assert len(strokes)==2,'expected the raw and stabilized strokes'
        def roughness(el):
            p=np.asarray(el['points']);chord=np.linalg.norm(p[-1]-p[0]);assert chord>150,'stroke is too short'
            return float(np.linalg.norm(np.diff(p,axis=0),axis=1).sum()/chord-1)
        raw,smooth=map(roughness,strokes)
        assert raw>.2 and smooth<raw*.7,'stabilization did not reduce the specified zigzag'
    elif aspect=='ruler-line':
        delta=path[-1]-path[0];length=np.linalg.norm(delta);assert length>150,'guided line is too short'
        distance=np.abs(np.cross(path-path[0],delta)/length)
        assert np.max(distance)<2,'line is not straight'
    elif aspect=='compass-arc':
        assert len(path)>12,'arc is not curved'
        coeff=np.column_stack([2*path[:,0],2*path[:,1],np.ones(len(path))])
        cx,cy,c=np.linalg.lstsq(coeff,np.sum(path*path,axis=1),rcond=None)[0]
        radius=math.sqrt(max(0,c+cx*cx+cy*cy));r=np.linalg.norm(path-[cx,cy],axis=1)
        assert radius>25 and max(np.ptp(path,axis=0))>radius,'arc extent is too small'
        angles=np.unwrap(np.arctan2(path[:,1]-cy,path[:,0]-cx))
        assert np.ptp(angles)>=math.pi-.12,'arc spans less than half a circle'
        assert np.max(np.abs(r-radius))<max(2,radius*.04),'arc is not circular'
    return {'aspect':aspect,'value':True}


def placement(doc,mode):
    assert len(doc['pages'])==1,'expected one page'
    page=doc['pages'][0];width,height=page['size']
    elements=items(doc)
    texts=[e for e in elements if e['kind']=='text']
    named={name:[e for e in texts if e['text']==name] for name in ('Alpha note','Beta note')}
    assert len(texts)==sum(map(len,named.values())),'unexpected text'
    assert len(named['Beta note'])==1,'Beta note must remain'
    def pos(el):return [float(el['attrs'][k]) for k in ('x','y')]
    def near(a,b):return all(abs(x-y)<=3 for x,y in zip(a,b))
    alpha=[pos(e) for e in named['Alpha note']];beta=pos(named['Beta note'][0])
    if mode in ('move-right','copy-right','restored'):
        assert near(beta,[330,240]),'unselected Beta note moved'
        original=[a for a in alpha if near(a,[90,75])]
        right=[a for a in alpha if width/2<=a[0]<width and 0<=a[1]<height/2]
        if mode=='copy-right':assert len(alpha)==2 and len(original)==1 and len(right)==1,'copy must keep original and add one upper-right text'
        elif mode=='move-right':assert len(alpha)==1 and len(right)==1,'Alpha note must be in the upper-right region'
        else:assert len(alpha)==1 and len(original)==1,'original text position was not restored'
        strokes=[e for e in elements if e['kind']=='stroke']
        assert len(strokes)==1,'original rectangle must remain'
        artifacts.numeric(strokes[0]['box'],[80,180,240,270],3)
    elif mode in ('space','space-restored'):
        assert len(alpha)==1 and near(alpha[0],[90,75]),'upper text moved'
        delta=beta[1]-240
        assert abs(beta[0]-330)<=3,'lower text moved horizontally'
        if mode=='space':assert delta>=10,'vertical gap did not increase'
        else:assert abs(delta)<=3,'original spacing was not restored'
        assert beta[1]+float(named['Beta note'][0]['attrs']['size'])<=height,'lower text leaves the page'
        strokes=[e for e in elements if e['kind']=='stroke'];assert len(strokes)==1,'rectangle must remain'
        artifacts.numeric(strokes[0]['box'],[80,180+delta,240,270+delta],3)
        assert strokes[0]['box'][3]<=height,'lower rectangle leaves the page'
    else:raise ValueError(mode)
    return {'aspect':'text-regions','value':{'layout':mode,'satisfied':True}}


def compare(a,e):
    assert a['aspect']==e['aspect'],'aspect differs'
    aspect=e['aspect'];a=a['value'];e=e['value']
    if aspect=='clipboard-image':artifacts.compare_raster(a,e)
    elif aspect in ('images','export-render'):
        assert len(a)==len(e),'number of images/pages differs'
        for x,y in zip(a,e):artifacts.compare_raster(x,y)
    elif aspect in ('sizes','export-geometry'):
        artifacts.numeric(a,e,.8)
    elif aspect=='image-alpha':
        assert len(a)==len(e),'number of images differs'
        for actual,expected in zip(a,e):
            for field in expected:artifacts.numeric(actual[field],expected[field],.025)
    elif aspect=='export-overlap-colors':artifacts.numeric(a,e,10)
    elif aspect=='text-regions':
        if isinstance(e,dict):
            assert a==e,'requested relative placement differs'
            return
        assert len(a)==len(e),'text object count differs'
        for x,y in zip(a,e):
            assert x['text']==y['text'],'text content differs'
            if 'region' in y:assert x.get('region')==y['region'],'text is outside the requested page region'
            else:artifacts.numeric(x['position'],y['position'],55)
    elif aspect=='stroke-boxes':
        assert len(a)==len(e),'stroke count differs'
        for x,y in zip(a,e):
            ew,eh=y[2]-y[0],y[3]-y[1]
            if abs(ew-eh)>20:
                assert (x[2]-x[0]>x[3]-x[1])==(ew>eh),'stroke orientation differs'
        artifacts.numeric(a,e,40)
    elif aspect in ('stroke-styles','text-styles'):
        assert len(a)==len(e),'number of objects differs'
        for x,y in zip(a,e):
            for k,v in y.items():
                if k in ('size','width'):artifacts.numeric(x[k],v,.2)
                else:assert x.get(k)==v,f'{k} differs: {x.get(k)!r} != {v!r}'
    else:
        assert a==e,f'{aspect} differs: {str(a)[:300]} != {str(e)[:300]}'
