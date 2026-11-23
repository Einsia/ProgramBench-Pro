"""Resolve native document backgrounds through the public exchange channels."""
import base64
import posixpath
import artifacts


def read_exchange(ctx,path):
    path=posixpath.normpath(path)
    for area in ('inbox','outbox'):
        folder=ctx.state[area]
        if not path.startswith(folder+'/'):continue
        relative=path[len(folder)+1:]
        parts=relative.split('/')
        locked=len(parts)==2 and parts[0]=='read-only'
        assert len(parts)==1 or locked,'background is not an accessible exchange resource'
        name=parts[-1]
        files=ctx.broker.call({'op':'list_files','area':area})['files']
        assert any(f['name']==name and bool(f['read_only'])==locked for f in files),'background resource is missing'
        value=ctx.broker.call({'op':'download','area':area,'filename':name,'read_only':locked})
        return base64.b64decode(value['body_base64'])
    raise AssertionError('background reference is outside the exchange folders')


def pdf_backgrounds(ctx,doc,document_path,expected_pdf):
    """Canonical resource identity and page number, independent of XML spelling.

    Repeated attributes and inherited references resolve identically. Resource
    contents, including differently serialized equivalent PDFs, must correspond
    to the uploaded input. No product-private path is accessed.
    """
    current=None;cache={};result=[]
    for page in doc['pages']:
        bg=page['background'];assert bg.get('type')=='pdf','PDF background is missing'
        # The native format has one document-wide PDF resource. Only its first
        # PDF background declares it; later redundant attributes are ignored.
        if current is None and bg.get('filename'):
            value=bg['filename'];domain=bg.get('domain','absolute')
            assert domain in ('absolute','attach'),'unsupported PDF reference domain'
            if domain=='attach':path=document_path+'.'+value
            else:path=value if value.startswith('/') else posixpath.join(posixpath.dirname(document_path),value)
            current=posixpath.normpath(path)
        assert current,'PDF background reference has no resource'
        if current not in cache:
            measured=artifacts.pdf(read_exchange(ctx,current))
            assert len(measured['pages'])==len(expected_pdf['pages']),'wrong background page count'
            for actual,wanted in zip(measured['pages'],expected_pdf['pages']):
                artifacts.numeric(actual['size'],wanted['size'],.6)
                assert actual['text']==wanted['text'],'wrong background text'
                artifacts.compare_raster(actual['render'],wanted['render'])
            cache[current]=measured
        number=int(bg['pageno'])
        assert 1<=number<=len(cache[current]['pages']),'background page number is invalid'
        result.append({'resource':'input-pdf','page':number})
    return result
