"""Reject active markup in uploaded reading documents before they enter the library."""
from html.parser import HTMLParser
import re
import urllib.parse


class ReadingMarkup(HTMLParser):
    def handle_decl(self, declaration):
        if declaration.strip().lower() != 'doctype html':
            raise ValueError('Document declarations with external or custom entities are not accepted')

    def unknown_decl(self, declaration):
        raise ValueError('Custom document declarations are not accepted')

    def handle_starttag(self, tag, attrs):
        name = tag.lower().split(':')[-1]
        if name in {'script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'applet', 'base',
                    'form', 'input', 'button', 'textarea', 'select', 'foreignobject', 'animate',
                    'animatemotion', 'animatetransform', 'set'}:
            raise ValueError('Active document content is not accepted')
        fields = {}
        for key, value in attrs:
            key = key.lower().split(':')[-1]
            if key in fields:
                raise ValueError('Duplicate document attributes are not accepted')
            fields[key] = value
            if key.startswith('on') or key in {'srcdoc', 'formaction'}:
                raise ValueError('Executable document attributes are not accepted')
            if key in {'href', 'src', 'action', 'data', 'poster'} and value:
                value = re.sub(r'[\x00-\x20\x7f]', '', value)
                scheme = urllib.parse.urlsplit(value).scheme.lower()
                if scheme and scheme not in {'http', 'https', 'mailto', 'data'}:
                    raise ValueError('Unsupported document URL scheme')
                if scheme == 'data' and not re.match(r'data:image/(?:png|jpeg|gif|webp);base64,', value, re.I):
                    raise ValueError('Only raster images may be embedded as data URLs')
        if name == 'meta' and (fields.get('http-equiv') or '').strip().lower() == 'refresh':
            raise ValueError('Document refresh navigation is not accepted')

    handle_startendtag = handle_starttag


def validate_markup(data):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        text = data.decode('utf-16')
    elif data.startswith(b'<\x00'):
        text = data.decode('utf-16-le')
    elif data.startswith(b'\x00<'):
        text = data.decode('utf-16-be')
    else:
        text = data.decode('utf-8-sig')
    if re.search(r'<!\s*(?:ENTITY|DOCTYPE\s+(?!html\s*>))', text, re.I):
        raise ValueError('External and custom document entities are not accepted')
    parser = ReadingMarkup(convert_charrefs=True)
    parser.feed(text)
    parser.close()
