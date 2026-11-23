"""Recursive export exchange with descriptor-relative, no-follow traversal."""
import document_exchange as file_exchange
import blackbox_runtime as runtime
import base64
import hashlib
import os
from pathlib import Path
import stat

from joplin_api import TEXT_TYPES, Refused


def parts(name):
    from broker import safe_name
    if not isinstance(name, str) or len(name.encode()) > 1000:
        raise ValueError('filename must be a relative path of at most 1000 bytes')
    values = name.split('/')
    if len(values) > 10:
        raise ValueError('too many subfolders')
    return [safe_name(x) for x in values]


def listing(rt, data):
    from broker import MAX_FILES, open_directory
    area, folder = rt.area(data, 'outbox')
    output = []
    def walk(fd, prefix='', depth=0):
        for name, info in runtime.list_directory(fd):
            if name.startswith('.') or depth > 9 or len(output) >= MAX_FILES:
                continue
            relative = prefix + name
            if stat.S_ISDIR(info.st_mode):
                child = open_directory(name, fd)
                try:
                    walk(child, relative + '/', depth+1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                output.append({'name': relative, 'path': str(folder / relative), 'size': info.st_size,
                               'read_only': relative.startswith('read-only/')})
    fd = open_directory(folder)
    try:
        walk(fd)
    finally:
        os.close(fd)
    return {'area': area, 'files': output}


def download(rt, data):
    from broker import MAX_DOWNLOAD, open_directory
    area, folder = rt.area(data, 'outbox')
    values = parts(data['filename'])
    if data.get('read_only'):
        values.insert(0, 'read-only')
    name = '/'.join(values)
    content = file_exchange.read(rt, area, name, limit=MAX_DOWNLOAD)
    if len(content) > MAX_DOWNLOAD:
        raise ValueError('download exceeds the limit')
    if Path(name).suffix.lower() not in TEXT_TYPES | {'.jex', '.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp'}:
        raise Refused('downloads expose document and image formats only')
    if content.startswith((b'\x7fELF', b'MZ')):
        raise Refused('executable content is not downloadable')
    return {'area': area, 'name': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
            'body_base64': base64.b64encode(content).decode()}
