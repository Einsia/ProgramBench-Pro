"""Independent commands using the real Xournal++ command line and document format."""
import base64
import gzip
import re
from pathlib import Path
import xml.etree.ElementTree as ET

import fixtures as f
import artifacts
import references

# Notebooks that the manifest embeds, as f.document() wrote them for the frozen manifest under CPython 3.12. Frozen
# bytes, so the manifest does not depend on the Python version: gzip.compress writes the header OS byte 3 there and
# 255 on Python 3.10 and 3.13+.
# f.document([f.page([f.stroke([(20,20),(80,80)],color='nonsense')])])
BAD_COLOR_XOPP = (
    'H4sIAAAAAAACAz1QQW6EMAy89xWWe+DUQrdVtYck+4P+IQsGIoKNEtMuv28o27VGsizPjEc2l9sc4ZtSDsK2enttKiBupQs82GrV/uVcXdyTucma'
    '2EdoE3mVZPFLlK4iE3TSrjOxIvQh0r8TfqAzGjSS25nZ1MdgFj8Q/IROR4vvnw3CSGEY1eLp3BTJ1bfTkGTlDnRbyGKWGDqEVuJ+9bm/F0LWLZb9'
    'En1ghNqZ6DdKwH6mI10udlmTTAQqEguV+GHEwpkK8JEF3amBgvMOUx9KZ+o/29L34KXdH+F+AZizRBI5AQAA')
# f.document([f.page()], encoding='zip'): stored members, written by zipfile
ZIP_MIMETYPE_XOPP = (
    'UEsDBBQAAAAAAAAAIViMBNIQFQAAABUAAAAIAAAAbWltZXR5cGVhcHBsaWNhdGlvbi94b3VybmFsKytQSwMEFAAAAAAAAAAhWMH66wYPAAAADwAA'
    'ABAAAABNRVRBLUlORi92ZXJzaW9uY3VycmVudD00Cm1pbj0xUEsDBBQAAAAAAAAAIVgWZW+L8QAAAPEAAAALAAAAY29udGVudC54bWw8P3htbCB2'
    'ZXJzaW9uPScxLjAnIGVuY29kaW5nPSd1dGYtOCc/Pgo8eG91cm5hbCBjcmVhdG9yPSJOb3RlYm9vayBkb2N1bWVudCIgZmlsZXZlcnNpb249IjQi'
    'Pjx0aXRsZT5Ob3RlczwvdGl0bGU+PHBhZ2Ugd2lkdGg9IjM2MCIgaGVpZ2h0PSIyODAiPjxiYWNrZ3JvdW5kIHR5cGU9InNvbGlkIiBjb2xvcj0i'
    'I2ZmZmZmZmZmIiBzdHlsZT0icGxhaW4iIC8+PGxheWVyIG5hbWU9Ik5vdGVzIiAvPjwvcGFnZT48L3hvdXJuYWw+UEsBAhQDFAAAAAAAAAAhWIwE'
    '0hAVAAAAFQAAAAgAAAAAAAAAAAAAAIABAAAAAG1pbWV0eXBlUEsBAhQDFAAAAAAAAAAhWMH66wYPAAAADwAAABAAAAAAAAAAAAAAAIABOwAAAE1F'
    'VEEtSU5GL3ZlcnNpb25QSwECFAMUAAAAAAAAACFYFmVvi/EAAADxAAAACwAAAAAAAAAAAAAAgAF4AAAAY29udGVudC54bWxQSwUGAAAAAAMAAwCt'
    'AAAAkgEAAAAA')
# f.document([f.page([f.stroke([(40,70),(290,200)],tool='nonsense',width=7)])])
UNKNOWN_TOOL_XOPP = (
    'H4sIAAAAAAACA0WQS26EMAxA9z2F5S5YtaQUdRgpydygd8iAgYgQoyS0w+0bClUtW5Zl+/kjb4/ZwReFaNmr4u1VFEC+5c76QRVr6l+a4qaf5IPX'
    '4I2DNpBJHBR+cqI78wQdt+tMPiH01tEfCWvUMtnkSO+VUZZHIBczEHzbLo0K3z8Ewkh2GJPCqhG55W7aaQi8+g7StpDCyM52CC27fepzfwpCTJvL'
    '+cUZ6xFKLZ3ZKIA3Mx3bxYyLKfBEkJidQs8+UtZ/WlXVddPstHOjC+pawEVAdc0mhCwPgpblLz77/YDszofoHz86+cVBAQAA')


def cases():
    groups = {}
    def add(group, name, **case):
        groups.setdefault(group, []).append(dict(id=name, **case))
    # A single command exports a corpus; every page exercises a distinct input
    # behavior. Geometry/count are scored once per artifact, not once per page.
    for family, corpus in [('strokes', f.stroke_pages()), ('text', f.text_pages()), ('backgrounds', f.background_pages()), ('images', f.image_pages())]:
        for fmt in ['pdf', 'png', 'svg']:
            add('render-'+family, fmt, source='corpus.xopp', corpus=family, fmt=fmt,
                args=['--create-'+('pdf' if fmt == 'pdf' else 'img')+'=result.'+fmt] + (['--export-png-dpi=96'] if fmt == 'png' else []),
                pages=len(corpus), text=(family == 'text' and fmt == 'pdf'))
    # Explicit page expressions test ordering, duplicates, open ranges and
    # whitespace. Every page has a different size and distinct text.
    for i, expression in enumerate(['1', '4', '1-2', '2-4', '2-', '-2', '1,3', '4,1', '2,2,3', '3-1', '1-1', '1,2-3',
                                    ' 2 ', '1, 4', '0', '5', '0-2', '3-20', '2-2,4', 'all', 'x', '1,,3']):
        add('page-ranges', f'range-{i+1:02d}', source='layers.xopp', corpus='layers', fmt='pdf',
            args=['--create-pdf=result.pdf', '--export-range='+expression], flexible=True, text=True,
            error=i+1 in (10,15,16,17,18,20,21,22))
    for i, expression in enumerate(['1', '2', '3', '4', '1-2', '2-', '-2', '1,3', '3,1', '2,2', '0', '5', '0-2', '2-20', '3-1', 'x']):
        add('layer-ranges', f'layers-{i+1:02d}', source='layers.xopp', corpus='layers', fmt='pdf',
            args=['--create-pdf=result.pdf', '--export-layer-range='+expression], flexible=True, text=True,
            error=i+1 in (11,13,15,16))
    for i, expression in enumerate([None, '1-2', '2-', '1,3', '3,1']):
        args=['--create-pdf=result.pdf', '--export-layers-progressively']
        if expression:
            args += ['--export-layer-range='+expression]
        add('progressive-layers', f'progressive-{i+1}', source='layers.xopp', corpus='layers', fmt='pdf', args=args, flexible=True, text=True)
    for flag in ['--export-no-background', '--export-no-ruling']:
        for fmt in ['pdf', 'png', 'svg']:
            add('background-options', flag[9:]+'-'+fmt, source='corpus.xopp', corpus='backgrounds', fmt=fmt,
                args=['--create-'+('pdf' if fmt=='pdf' else 'img')+'=result.'+fmt, flag]+(['--export-png-dpi=72'] if fmt=='png' else []),
                pages=len(f.background_pages()), transparency=(flag=='--export-no-background' and fmt!='pdf'))
    resolutions = [[], ['--export-png-dpi=72'], ['--export-png-dpi=96'], ['--export-png-dpi=144'],
                   ['--export-png-dpi=37'], ['--export-png-width=157'], ['--export-png-height=137'],
                   ['--export-png-width=300', '--export-png-height=100'],
                   ['--export-png-dpi=72', '--export-png-width=999'],
                   ['--export-png-dpi=96', '--export-png-height=100'],
                   ['--export-png-width=1'], ['--export-png-height=1']]
    for i, options in enumerate(resolutions):
        add('png-resolution', f'sizing-{i+1:02d}', source='layers.xopp', corpus='layers', fmt='png',
            args=['--create-img=result.png', *options], pages=4, small=(i>=10))
    for fmt in ['pdf', 'png', 'svg']:
        for encoding, version in [('plain','4'),('gzip','1'),('gzip','2'),('gzip','3')]:
            add('compatibility', f'{fmt}-{encoding}-v{version}', source='compat.xoj', corpus='compat', encoding=encoding, version=version,
                fmt=fmt, args=['--create-'+('pdf' if fmt=='pdf' else 'img')+'=result.'+fmt]+(['--export-png-dpi=72'] if fmt=='png' else []), pages=2, text=fmt=='pdf',text_pages=[0])
    for kind in ['normal', 'single', 'fractional', 'rotated', 'cropped', 'images', 'navigation']:
        add('pdf-import', 'save-'+kind, source='paper.pdf', pdf=kind, fmt='xopp', args=['--save=result.xopp'],
            pages=1 if kind=='single' else 2 if kind=='fractional' else 3)
        for backend in ['cairo', 'qpdf']:
            add('pdf-background', kind+'-'+backend, source='annotation.xopp', pdf=kind, annotate=True, fmt='pdf',
                args=['--create-pdf=result.pdf','--export-pdf-backend='+backend],
                pages=1 if kind=='single' else 2 if kind=='fractional' else 3, text=True,navigation=kind=='navigation')
    for mode in ['absolute','relative','clone']:
        for fmt in ['pdf','png','svg']:
            add('image-background',mode+'-'+fmt,source='image-background.xopp',image_background=mode,fmt=fmt,
                args=['--create-'+('pdf' if fmt=='pdf' else 'img')+'=result.'+fmt]+(['--export-png-dpi=72'] if fmt=='png' else []),
                pages=2 if mode=='clone' else 1,text=fmt=='pdf')
    for flag in ['--export-no-background','--export-no-ruling']:
        add('pdf-background','flags-'+flag[9:],source='annotation.xopp',pdf='normal',annotate=True,fmt='pdf',
            args=['--create-pdf=result.pdf',flag],pages=3,text=True)
    errors = [('notebook-garbage', b'not a notebook', []), ('empty', b'', []), ('truncated-xml', b'<xournal><page', []),
              ('wrong-root', b'<other/>', []), ('bad-gzip', b'\x1f\x8b\x08\x00truncated', []),
              ('missing-width', b'<xournal fileversion="4"><page height="280"><background type="solid" color="white" style="plain"/><layer/></page></xournal>', []),
              ('bad-color', base64.b64decode(BAD_COLOR_XOPP), []),
              ('zip-mimetype', base64.b64decode(ZIP_MIMETYPE_XOPP), [])]
    for name, data, args in errors:
        add('input-errors', name, source='bad.xopp', raw=base64.b64encode(data).decode(), fmt='pdf', args=['--create-pdf=result.pdf', *args], error=True)
    for name, options in [('bad-dpi', ['--export-png-dpi=abc']), ('bad-width', ['--export-png-width=abc']),
                          ('bad-height', ['--export-png-height=abc'])]:
        add('option-errors', name, source='layers.xopp', corpus='layers', fmt='png', args=['--create-img=result.png', *options], error=True)
    add('compatibility', 'unknown-tool-fallback', source='fallback.xopp', raw=UNKNOWN_TOOL_XOPP,
        fmt='pdf',args=['--create-pdf=result.pdf'],pages=1)
    add('compatibility', 'image-extension-fallback', source='layers.xopp', corpus='layers', fmt='jpg',
        args=['--create-img=result.jpg','--export-png-dpi=72'], pages=4)
    add('option-errors', 'missing-input', source='absent.xopp', missing=True, fmt='pdf', args=['--create-pdf=result.pdf'], error=True)
    add('option-errors', 'readonly-output', source='layers.xopp', corpus='layers', fmt='pdf', readonly=True,
        args=['--create-pdf=read-only/result.pdf'], error=True)
    for mode in ['absolute','relative','inherited','repeated','attached','same-name-outbox','missing','wrong-page']:
        add('native-references',mode,source='linked.xopp',pdf_reference=mode,fmt='pdf',
            args=['--create-pdf=result.pdf'],pages=3,text=True,error=mode in ('missing','wrong-page'))
    return groups


def corpus(name):
    if name == 'layers':
        return f.layer_pages()
    if name == 'compat':
        return [f.page([f.text('Legacy notebook', size=24), f.stroke([(30,120),(300,200)], tool='highlighter', color='yellow', width=18)]),
                f.page([f.image()], style='lined', size=(280,360))]
    return [p for _, p in {'strokes': f.stroke_pages, 'text': f.text_pages, 'backgrounds': f.background_pages, 'images': f.image_pages}[name]()]


def upload(ctx, name, data, **kw):
    return ctx.broker.call({'op':'upload','filename':name,'base64':base64.b64encode(data).decode(), **kw})


def inputs(ctx, case):
    if case.get('missing'):
        return
    if 'raw' in case:
        data = base64.b64decode(case['raw'])
    elif case.get('image_background'):
        upload(ctx,'background.png',f.picture('alpha'))
        filename='background.png' if case['image_background']=='relative' else ctx.state['inbox']+'/background.png'
        pages=[f.page([f.text('Image stationery',45,35)],background={'type':'pixmap','domain':'absolute','filename':filename})]
        if case['image_background']=='clone':
            pages.append(f.page([f.text('Cloned background',45,35)],background={'type':'pixmap','domain':'clone','filename':'0'}))
        data=f.document(pages)
    elif case.get('pdf_reference'):
        mode=case['pdf_reference'];source=f.pdf('normal')
        upload(ctx,'paper.pdf',source)
        # Same basename in another exchange directory carries distinct content.
        other=f.pdf('images');upload(ctx,'paper.pdf',other,area='outbox')
        attrs={'type':'pdf','domain':'absolute','filename':ctx.state['inbox']+'/paper.pdf'}
        if mode in ('relative','repeated'):attrs['filename']='paper.pdf'
        if mode=='same-name-outbox':attrs['filename']='../outbox/paper.pdf'
        if mode=='missing':attrs['filename']='missing/paper.pdf'
        if mode=='attached':
            attrs.update(domain='attach',filename='bg.pdf');upload(ctx,'linked.xopp.bg.pdf',source)
        sizes=[p['size'] for p in artifacts.pdf(source)['pages']]
        pages=[]
        for i,size in enumerate(sizes):
            bg=dict(attrs,pageno=str(i+1))
            if mode in ('relative','inherited') and i>0:bg={'type':'pdf','pageno':str(i+1)}
            if mode=='wrong-page':bg['pageno']='9'
            pages.append(f.page(size=size,background=bg))
        data=f.document(pages)
    elif 'pdf' in case:
        data = f.pdf(case['pdf'])
        if case.get('annotate'):
            upload(ctx, 'paper.pdf', data)
            doc = artifacts.pdf(data)
            pages = [f.page([f.text(f'Annotation {i+1}', 45, 165, color='#cc2222ff', size=18)], size=p['size'],
                            background={'type':'pdf','domain':'absolute','filename':ctx.state['inbox']+'/paper.pdf','pageno':str(i+1)})
                     for i,p in enumerate(doc['pages'])]
            data = f.document(pages)
    else:
        data = f.document(corpus(case['corpus']), encoding=case.get('encoding','gzip'), version=case.get('version','4'))
    upload(ctx, case['source'], data)
    if case.get('readonly'):
        upload(ctx, 'result.pdf', b'%PDF-1.4\nreadonly fixture', area='outbox', read_only=True)


def descriptors(case):
    if case.get('error'):
        return [('rejection','rejection')]
    if case.get('flexible'):
        # Result length and each selected page are measured in one projection;
        # this also preserves legitimate product rejection of an expression.
        return [(k,k) for k in ['result','geometry','text','render-set']]
    if case['fmt']=='xopp':
        return [(k,k) for k in ['page-count','geometry','background-links','layers']]
    result=[('page-count','page-count'),('geometry','geometry')]
    if case.get('navigation'):result += [('outline','outline'),('links','links')]
    for i in range(case['pages']):
        if not case.get('small'):
            result.append((f'page-{i+1}-render',f'render:{i}'))
        if case.get('text') and i in case.get('text_pages',range(case['pages'])):
            for k in ['text','positions','font-sizes','font-styles','text-colors']:
                result.append((f'page-{i+1}-{k}',f'{k}:{i}'))
        if case.get('transparency'):
            result.append((f'page-{i+1}-alpha',f'alpha:{i}'))
    return result


def build():
    result=[]
    for name, cases_ in cases().items():
        wid='cli-'+name
        cps=[]
        for case in cases_:
            cid=case['id']
            cps.append({'id':cid,'goal':'Run the documented command and inspect its public outputs.', 'case':case,
                        'assertions':[{'id':f'{wid}/{cid}/{key}', 'channel':'backend','method':'program',
                                       'requirement':f'{name}: {cid}, {key} matches the product output.', 'aspect':aspect}
                                      for key,aspect in descriptors(case)]})
        result.append({'id':wid,'feature':name,'execution':'program','initial_state':'Fresh desktop and empty exchange folders; independent inputs for each command.',
                       'setup':[], 'checkpoints':cps})
    return result


def execute(ctx, cp):
    case=cp['case']
    # Each command uses fresh process state; reset is a broker operation that
    # does not depend on a possibly failed product command.
    status=ctx.broker.call({'op':'reset'})
    assert status.get('ready'), 'application failed to restart for the command'
    inputs(ctx,case)
    cmd=ctx.broker.call({'op':'command_line','args':case['args']+[ctx.state['inbox']+'/'+case['source']]})
    assert not cmd.get('timed_out'), 'command timed out'
    if case.get('error'):
        assert cmd.get('exit_code') not in (None,0), 'invalid command unexpectedly succeeded'
        return {'error':True}
    if case.get('flexible') and cmd.get('exit_code') != 0:
        assert cmd.get('exit_code') is not None, 'command crashed'
        return {'error':True}
    assert cmd.get('exit_code')==0, 'command failed: '+str(cmd.get('stderr',''))[-300:]
    files=ctx.broker.call({'op':'list_files','area':'outbox'})['files']
    names=sorted([x['name'] for x in files if x['name'].startswith('result') and x['name'].endswith('.'+case['fmt'])],
                 key=lambda n:[int(p) if p.isdigit() else p for p in re.split(r'(\d+)',n)])
    assert names, 'no exported files'
    documents=[]
    for name in names:
        value=ctx.broker.call({'op':'download','filename':name})
        data=base64.b64decode(value['body_base64'])
        folder=ctx.out/'artifacts'/cp['id']
        folder.mkdir(parents=True,exist_ok=True)
        (folder/name).write_bytes(data)
        documents.append(artifacts.measure(data,Path(name).suffix,folder))
    pages=[p for d in documents for p in d['pages']] if case['fmt'] in ('pdf','xopp') else documents
    if not case.get('flexible'):
        assert len(pages)==case['pages'], f'expected {case["pages"]} pages, received {len(pages)}'
    result={'error':False,'pages':pages,'files':names,'outline':documents[0].get('outline'), 'links':documents[0].get('links')}
    if case['fmt']=='xopp':
        try:
            result['background-links']=references.pdf_backgrounds(ctx,documents[0],ctx.state['outbox']+'/'+names[0],artifacts.pdf(f.pdf(case['pdf'])))
        except Exception as exc:
            result['background-error']=str(exc)
    return result


def project(observed, aspect):
    if aspect=='rejection':
        return {'aspect':'rejection','value':observed['error']}
    if observed['error']:
        return {'aspect':'rejection','value':True}
    pages=observed['pages']
    kind,_,index=aspect.partition(':')
    if kind in ('result','page-count'):
        value={'pages':len(pages),'files':observed['files']}
    elif kind=='geometry':
        value=[p['size'] for p in pages]
    elif kind=='background-links':
        assert not observed.get('background-error'),observed.get('background-error')
        value=observed['background-links']
    elif kind=='layers':
        value=[[len(layer['items']) for layer in p['layers']] for p in pages]
    elif kind in ('outline','links'):value=observed[kind]
    elif kind=='render-set':
        value=[p['render'] for p in pages]
    elif kind=='text' and not index:
        value=[p['text'] for p in pages]
    else:
        p=pages[int(index)]
        if kind=='render': value=p['render']
        elif kind=='alpha': value=p['alpha']
        elif kind=='text': value=p['text']
        elif kind=='positions': value=[s['origin'] for s in p['spans']]
        elif kind=='font-sizes': value=[s['size'] for s in p['spans']]
        elif kind=='font-styles': value=[s['style'] for s in p['spans']]
        elif kind=='text-colors': value=[s['color'] for s in p['spans']]
        else: raise ValueError(aspect)
    return {'aspect':kind,'value':value}


def compare(a,e):
    if e['aspect']=='render-set':
        assert a['aspect']==e['aspect'] and len(a['value'])==len(e['value']), 'rendered page count differs'
        for x,y in zip(a['value'],e['value']):
            artifacts.compare_raster(x,y)
    elif e['aspect']=='links':
        assert a['aspect']=='links' and len(a['value'])==len(e['value']), 'PDF link count differs'
        for x,y in zip(a['value'],e['value']):
            artifacts.numeric(x['rect'],y['rect'],1.5)
            assert {k:v for k,v in x.items() if k!='rect'}=={k:v for k,v in y.items() if k!='rect'},'PDF link target differs'
    else:
        artifacts.compare(a,e)
