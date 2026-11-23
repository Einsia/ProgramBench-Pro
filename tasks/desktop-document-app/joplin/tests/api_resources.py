"""Resource upload, MIME, bytes, metadata, relationships and clipped images."""
import base64
import hashlib
import io
import re
import time

from harness import Ref, Suite, b64, project, aspects, checked, observed
from fixtures import png


def content(response):
    if 'body_base64' in response:
        return base64.b64decode(response['body_base64'])
    body = response.get('body')
    assert isinstance(body, str), 'attachment did not return bytes'
    return body.encode('utf-8')


def build():
    s = Suite('protocol-resources', 'attachments and clipped images')
    s.setup('book', lambda c: c.call('POST', '/folders', body={'title': 'Resource notebook'}, save='book'))
    samples = [
        ('plain', 'notes.txt', b'First line\nSecond line\n', 'text/plain'),
        ('unicode', '資料.txt', 'Café Ελληνικά 中文 日本語 🙂\n'.encode(), 'text/plain'),
        ('markdown', 'draft.md', b'# Heading\n\n**bold** and _italic_\n', 'text/markdown'),
        ('csv', 'counts.csv', b'name,count\n"Oak, red",3\nElm,7\n', 'text/csv'),
        ('json', 'data.json', b'{"name":"Oak","count":3}', 'application/json'),
        ('png', 'diagram.png', png(), 'image/png'),
        ('large-png', 'wider.png', png(113, 67), 'image/png'),
        ('binary', 'payload.bin', bytes(range(256)) * 16, 'application/octet-stream'),
        ('spaces', 'draft with spaces.txt', b'Spaced file name\n', 'text/plain'),
        ('punctuation', 'a+b (copy).txt', b'Punctuation name\n', 'text/plain'),
        ('empty', 'empty.txt', b'', 'text/plain'),
        ('long-text', 'large.txt', (b'Long resource line 0123456789\n' * 4096), 'text/plain'),
    ]
    for key, name, data, mime in samples:
        s.request('upload-' + key, 'Upload ' + name + ' as an attachment', 'POST', '/resources', save=key,
                  multipart={'filename': name, 'base64': b64(data), 'content_type': mime, 'props': {'title': name}},
                  fields=('id', 'title', 'mime', 'file_extension', 'size', 'type_'),
                  expected={'title': name, 'size': len(data), 'type_': 4})
        def download(c, key=key, data=data):
            response = c.call('GET', '/resources/{' + key + '}/file')
            raw = content(response)
            assert raw == data, 'attachment bytes changed'
            return {'bytes': hashlib.sha256(raw).hexdigest(), 'length': len(raw)}
        s.add('download-' + key, 'Download the exact bytes of ' + name, download,
              {'bytes': 'The downloaded bytes preserve the supplied attachment.', 'length': 'The attachment size is preserved.'},
              depends=('upload-' + key,))
        s.request('metadata-' + key, 'Read resource metadata for ' + name, 'GET', '/resources/{' + key + '}',
                  query={'fields': 'title,mime,size,file_extension'}, fields=('title', 'mime', 'size', 'file_extension'),
                  depends=('upload-' + key,))
    # The bytes assertion already entails size; each download is one observation.
    for case in s.cases:
        if case.key.startswith('download-'):
            case.aspects.pop('length')
    for key in ('plain', 'unicode', 'png', 'binary'):
        def rename(c, key=key):
            before = aspects(file=lambda:content(c.call('GET', '/resources/{' + key + '}/file')))
            c.call('PUT', '/resources/{' + key + '}', body={'title': 'Renamed ' + key, 'user_data': '{"used":true}'})
            obj = c.call('GET', '/resources/{' + key + '}', query={'fields': 'title,user_data'})['body']
            return aspects(**{'title':lambda:obj['title'],'user_data':lambda:obj['user_data'],
                 'content-retained':lambda:checked(content(c.call('GET','/resources/{'+key+'}/file'))==observed(before,'file'),True)})
        s.add('rename-' + key, 'Change resource metadata without rewriting its bytes', rename,
              {'title': 'The attachment is renamed.', 'user_data': 'Resource user metadata is retained.',
               'content-retained': 'Metadata changes preserve the attachment bytes.'}, depends=('upload-' + key,))
    def replace(c):
        data = b'New attachment contents\nwith another line.\n'
        c.call('PUT', '/resources/{plain}', multipart={'filename': 'replacement.txt', 'base64': b64(data),
                'content_type': 'text/plain', 'props': {'title': 'Replacement'}})
        meta = aspects(object=lambda:c.call('GET', '/resources/{plain}', query={'fields': 'id,title,size'})['body'])
        return aspects(bytes=lambda:hashlib.sha256(checked(content(c.call('GET','/resources/{plain}/file')),data)).hexdigest(),
                       title=lambda:observed(meta,'object')['title'],identity=lambda:c.clean(observed(meta,'object')['id']))
    s.add('replace', 'Replace the contents of an existing attachment', replace,
          {'bytes': 'PUT replaces the stored content.', 'title': 'The replacement updates the title.',
           'identity': 'Content replacement retains the resource identity.'}, depends=('upload-plain',))
    def associated_setup(c):
        body = '![Diagram](:/' + c.values['png']['id'] + ')\n\n[Read notes](:/' + c.values['plain']['id'] + ')'
        c.call('POST', '/notes', body={'title': 'Attachment links', 'body': body, 'parent_id': Ref('book')}, save='linked')
    s.setup('links', associated_setup, before='note-resources')
    def attached(c):
        rows = c.all('/notes/{linked}/resources', fields='id,title,mime')
        return {'resources': project(rows, ['id', 'title', 'mime'], c)}
    s.add('note-resources', 'List the resources referenced by a note', attached,
          {'resources': 'The note exposes its image and file resources.'}, depends=('upload-png', 'upload-plain'))
    # Cropping the clipper's image input exercises a different public resource
    # creation route and verifies actual pixel geometry rather than file names.
    for key, crop in [('whole', None), ('center', {'x': 8, 'y': 6, 'width': 20, 'height': 14}),
                      ('corner', {'x': 0, 'y': 0, 'width': 8, 'height': 10}),
                      ('bottom', {'x': 17, 'y': 24, 'width': 31, 'height': 8}),
                      ('right', {'x': 43, 'y': 9, 'width': 5, 'height': 23})]:
        def clipped(c, key=key, crop=crop):
            from PIL import Image
            values = {'title': 'Clipped image ' + key, 'body': 'Image clipping', 'parent_id': Ref('book'),
                      'image_data_url': 'data:image/png;base64,' + b64(png(gradient=True))}
            if crop is not None:
                values['crop_rect'] = crop
            note = c.call('POST', '/notes', body=values, save='image-' + key)['body']
            resources = c.all('/notes/{image-' + key + '}/resources', fields='id,mime,size')
            assert len(resources) == 1, 'image clipping did not create one resource'
            rid = resources[0]['id']; c.identities[rid] = '@clipped-' + key
            image = Image.open(io.BytesIO(content(c.call('GET', '/resources/' + rid + '/file')))).convert('RGB')
            expected = (48, 32) if crop is None else (crop['width'], crop['height'])
            source=Image.open(io.BytesIO(png(gradient=True))).convert('RGB')
            if crop:source=source.crop((crop['x'],crop['y'],crop['x']+crop['width'],crop['y']+crop['height']))
            def link():
                assert '](:/'+rid+')' in note['body'],'clipped image link is missing'
                caption=re.sub(r'!\[[^\]]*\]\(:/'+re.escape(rid)+r'\)','',note['body'])
                return {'resource':c.clean(rid),'caption':caption}
            return aspects(dimensions=lambda:list(checked(image.size,expected)),mime=lambda:resources[0]['mime'],
                           pixels=lambda:hashlib.sha256(checked(image.tobytes(),source.tobytes())).hexdigest(),link=link)
        s.add('clip-image-' + key, 'Clip a PNG image ' + key, clipped,
              {'dimensions': 'The image has the requested crop dimensions.', 'mime': 'The resource is an image.',
               'pixels': 'Cropping retains the corresponding source pixels.', 'link': 'The note references the created resource.'})
    s.request('delete-resource', 'Delete an attachment', 'DELETE', '/resources/{binary}', status=True, depends=('upload-binary',))
    for suffix in ('', '/file'):
        s.request('deleted-' + ('metadata' if not suffix else 'bytes'), 'Read a removed attachment', 'GET',
                  '/resources/{binary}' + suffix, status=True, error=True, depends=('delete-resource',), expected={'status': 404})
    s.request('missing-data', 'Reject a resource creation without uploaded bytes', 'POST', '/resources',
              body={'title': 'No file'}, status=True, error=True, expected={'status': 400})
    return s
