#!/usr/bin/env python3
"""Serve the original StackEdit 5.15.4 release assets with a restrictive serving policy."""
import http.server
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.parse

ARCHIVE = Path(__file__).resolve().parent / 'docker-build-layer.tar.gz'
PREFIX = 'opt/stackedit/dist/'
TYPES = {'.html', '.js', '.css', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.eot'}
FILES = {}
with tarfile.open(ARCHIVE) as archive:
    for member in archive.getmembers():
        if member.isfile() and member.name.startswith(PREFIX):
            name = member.name[len(PREFIX):]
            path = PurePosixPath(name)
            if path.suffix in TYPES and not any(part.startswith('.') for part in path.parts):
                if path.suffix == '.html' and name != 'index.html':
                    continue
                if name in ('sw.js', 'style.js'):
                    continue
                FILES[name] = archive.extractfile(member).read()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'static'
    sys_version = ''

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.answer(True)

    def do_HEAD(self):
        self.answer(False)

    def answer(self, body):
        try:
            url = urllib.parse.urlsplit(self.path)
            path = urllib.parse.unquote(url.path, errors='strict')
        except (ValueError, UnicodeError):
            path = ''
        name = 'index.html' if path in ('/', '/app', '/index.html') else path[1:]
        if not path.startswith('/') or '\\' in path or '\x00' in path or any(p in ('', '.', '..') for p in name.split('/')):
            name = ''
        data = FILES.get(name)
        status = 200 if data is not None else 404
        content = data if data is not None else b'Not found\n'
        kind = mimetypes.guess_type(name)[0] if data is not None else 'text/plain'
        worker = bool(re.fullmatch(r'[a-f0-9]+\.worker\.js', name))
        policy = ("default-src 'none'; script-src 'self'" + (" 'unsafe-eval'" if worker else '') +
                  "; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
                  "connect-src 'self'; worker-src 'self'; frame-src 'none'; object-src 'none'; "
                  "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.send_response(status)
        self.send_header('Content-Type', kind or 'application/octet-stream')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Content-Security-Policy', policy)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        if body:
            self.wfile.write(content)


if __name__ == '__main__':
    http.server.ThreadingHTTPServer((os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '3000'))), Handler).serve_forever()
