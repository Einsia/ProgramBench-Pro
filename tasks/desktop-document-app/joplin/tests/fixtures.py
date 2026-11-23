"""Deterministic document inputs, created outside the candidate filesystem."""
import base64
import io
import json
import struct
import zlib
from pathlib import Path
import hashlib


def png(width=48, height=32, *, gradient=False):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    pixels = b''.join(b'\0' + b''.join(bytes(((x*7+y*3)%256,(y*11+x)%256,(x*5+y*13)%256) if gradient else
                                          (30, 120, 210) if x < width // 2 else (220, 110, 35))
                                   for x in range(width)) for y in range(height))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) \
        + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


DOCUMENTS = {
    'plain.txt': b'First imported line.\nSecond imported line.\n',
    'field-note.md': '# Imported field note\n\nA **bold** observation with café and 中文.\n\n- Oak\n- Elm\n'.encode(),
    'front-matter.md': b'---\ntitle: Front matter journal\nauthor: Ada Lovelace\ncreated: 2024-01-02T03:04:05Z\nupdated: 2025-02-03T04:05:06Z\ntags:\n  - botany\n  - fieldwork\n---\n\n## Observations\n\nOak and elm by the river.\n',
    'clipped.html': '<!doctype html><html><head><title>Clipped journal</title></head><body><h1>River survey</h1><p>Counted <strong>three</strong> oaks.</p><ul><li>North bank</li><li>South bank</li></ul></body></html>'.encode(),
    'sample.enex': b'<?xml version="1.0" encoding="UTF-8"?><en-export export-date="20250101T120000Z" application="Evernote" version="10"><note><title>Evernote field journal</title><content><![CDATA[<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note><div>Imported observation.</div><div><b>Three oaks</b> by the river.</div></en-note>]]></content><created>20240102T030405Z</created><updated>20250203T040506Z</updated><tag>botany</tag><tag>fieldwork</tag><note-attributes><author>Ada Lovelace</author><source-url>https://example.invalid/survey</source-url></note-attributes></note></en-export>',
    'diagram.png': png(),
}

_image=png()
_image_hash=hashlib.md5(_image).hexdigest()
DOCUMENTS['multi-note.enex']=('''<?xml version="1.0" encoding="UTF-8"?>
<en-export application="Evernote" version="10" export-date="20250101T120000Z">
<note><title>ENEX source</title><content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note>
<div>A <b>bold</b> field observation.</div><div><a href="evernote:///view/1/s1/11111111-1111-1111-1111-111111111111/11111111-1111-1111-1111-111111111111/">ENEX target</a></div>
<en-media type="image/png" hash="'''+_image_hash+'''"/></en-note>]]></content>
<created>20240102T030405Z</created><updated>20250203T040506Z</updated>
<tag>botany</tag><tag>fieldwork</tag><note-attributes><author>Ada Lovelace</author></note-attributes>
<resource><data encoding="base64">'''+base64.b64encode(_image).decode()+'''</data><mime>image/png</mime>
<resource-attributes><file-name>field.png</file-name></resource-attributes></resource></note>
<note><title>ENEX target</title><content><![CDATA[<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note><div>Destination survey notes.</div></en-note>]]></content>
<created>20240103T030405Z</created><updated>20250204T040506Z</updated><tag>planning</tag>
<note-attributes><author>Grace Hopper</author></note-attributes></note></en-export>''').encode()


def bytes_for(name):
    if name=='formatting.one':return (Path(__file__).parent/'inputs'/name).read_bytes()
    return DOCUMENTS[name]


def upload(c, name, *, area='inbox'):
    return c.broker.call({'op': 'upload', 'filename': name, 'area': area,
                          'base64': base64.b64encode(bytes_for(name)).decode()})
