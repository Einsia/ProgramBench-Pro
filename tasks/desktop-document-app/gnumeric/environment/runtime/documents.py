"""Document exchange validation, independent of the reference implementation."""
import gzip
import io
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_EXPANDED = 100 * 1024 * 1024
ACTIVE = re.compile(r'\bGETENV\s*\(|\bGnmHLink(?:External|URL|EMail)\b|<!ENTITY\b', re.I)
# A URI scheme is immediately followed by its path/authority. Ordinary prose
# such as "including file: " in a typeset export is not a document link.
EXTERNAL = re.compile(r'\b(?:file|smb|sftp|ssh|ftp):(?=\S)', re.I)


def text(value):
    if ACTIVE.search(value) or EXTERNAL.search(value):
        raise ValueError('external document links, environment access and active document content are unavailable')


def xml_text(raw):
    value=raw.decode('utf-8','replace')
    text(value)
    try:
        root=ET.fromstring(raw)
    except ET.ParseError:
        return
    for node in root.iter():
        text(node.text or '')
        for key,value in node.attrib.items():
            text(value)
            if key.rsplit('}',1)[-1]=='href' and value and not value.startswith('#'):
                raise ValueError('external document references are unavailable')
            if key.rsplit('}',1)[-1]=='TargetMode' and value=='External':
                raise ValueError('external document relationships are unavailable')


def validate(name, content, *, download=False):
    from cli import DOCUMENTS
    suffix = Path(name).suffix.casefold()
    if suffix not in DOCUMENTS:
        raise ValueError('file type is outside the document exchange; see help')
    if content.startswith(b'\x7fELF') or content.startswith(b'MZ') or content.startswith(b'#!'):
        raise ValueError('executable content is outside the document exchange')
    if content.startswith(b'\x1f\x8b'):
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
            raw = gz.read(MAX_EXPANDED+1)
        if len(raw) > MAX_EXPANDED:
            raise ValueError('expanded document exceeds 100 MiB')
        xml_text(raw)
        if download:
            root = ET.fromstring(raw)
            if root.tag.rsplit('}',1)[-1] != 'Workbook':
                raise ValueError('download is not a workbook')
    elif content.startswith(b'PK\x03\x04'):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 4096 or sum(e.file_size for e in entries) > MAX_EXPANDED:
                raise ValueError('expanded document exceeds exchange limits')
            names = {e.filename for e in entries}
            if download and not ({'xl/workbook.xml','[Content_Types].xml'} <= names or {'content.xml','mimetype'} <= names):
                raise ValueError('download is not an office workbook')
            for entry in entries:
                lower = entry.filename.casefold()
                if any(part in lower for part in ('vbaproject', 'externallinks/', '/embeddings/', 'scripts/')):
                    raise ValueError('active and external document content is unavailable')
                if lower.endswith(('.xml', '.rels')):
                    raw = archive.read(entry)
                    xml_text(raw)
    elif content.startswith(b'\xd0\xcf\x11\xe0'):
        # Legacy documents are not executable. Program and desktop boundaries
        # independently disable loading user plug-ins or launching document URLs.
        text(content.decode('utf-16le', 'ignore'))
        text(content.decode('latin1'))
        if not download:
            import xlrd
            try:
                book=xlrd.open_workbook(file_contents=content,formatting_info=True)
            except xlrd.XLRDError:
                book=None
            if book is not None:
                for sheet in book.sheets():
                    if any(getattr(link,'url_or_path',None) for link in sheet.hyperlink_list):
                        raise ValueError('external document hyperlinks are unavailable')
    elif content.startswith((b'%PDF-', b'\x89PNG', b'\xff\xd8\xff')):
        return
    else:
        if content.lstrip().startswith(b'<'):xml_text(content)
        else:text(content.decode('utf-8', 'replace'))
        if download and suffix in ('.xlsx', '.ods', '.xls', '.gnumeric'):
            if suffix != '.gnumeric' or b'Workbook' not in content[:4096]:
                raise ValueError('download is not the requested workbook format')
