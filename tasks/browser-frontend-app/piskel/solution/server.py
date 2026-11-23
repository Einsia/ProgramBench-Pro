#!/usr/bin/env python3
"""Offline static server for the unmodified Piskel 0.15.0 editor.

The editor is the production build of the upstream v0.15.0 release (grunt build,
see NOTICE), read once from piskel-0.15.0-prod.tar.gz (members under prod/) and
served byte for byte at the entry path /. Only GET and HEAD are answered. The
serving policy is the only restriction applied to the product:

- an allow-list of the files the editor loads in its default (minified) mode:
  index.html, the minified application bundle, the style sheet, images, fonts and
  the logo (no unminified bundle, no website partials, no directory listing);
- a Content-Security-Policy that admits the editor's own scripts (same origin, the
  inline boot script of index.html and the boot script's onload handler, by hash)
  and its blob: workers, and nothing else that could run as script, plus nosniff
  and no-cache headers.

HOST and PORT come from the environment (defaults 0.0.0.0 and 3000).
"""
import base64
import hashlib
import http.server
import os
from pathlib import Path, PurePosixPath
import re
import tarfile
import urllib.parse

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'piskel-0.15.0-prod.tar.gz'
PREFIX = 'prod/'
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.gif': 'image/gif', '.svg': 'image/svg+xml',
         '.eot': 'application/vnd.ms-fontobject', '.ttf': 'font/ttf', '.woff': 'font/woff'}
# The boot script inserts the bundle with this onload attribute.
BOOT_HANDLER = b'_onPiskelReady()'


def served(name):
    """Whether a path of the production build is part of the editor as index.html loads it."""
    path = PurePosixPath(name)
    if path.suffix not in TYPES or any(part.startswith('.') for part in path.parts):
        return False
    if path.suffix == '.html':
        return name == 'index.html'
    if path.suffix == '.js':
        return path.parent == PurePosixPath('js') and path.name.startswith('piskel-packaged-min-')
    if path.parts[0] == 'img':
        return 'unused' not in path.parts
    return path.parts[0] == 'css' or name == 'logo.png'


def load():
    files = {}
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith(PREFIX):
                name = member.name[len(PREFIX):]
                if served(name):
                    files[name] = archive.extractfile(member).read()
    return files


def sha(body):
    return "'sha256-" + base64.b64encode(hashlib.sha256(body).digest()).decode() + "'"


def policy(index):
    """CSP: same-origin scripts, the inline boot script and its onload handler (by hash), blob: workers."""
    inline = re.findall(rb'<script type="text/javascript">(.*?)</script>', index, re.S)
    hashes = ' '.join(sha(body) for body in inline)
    return ("default-src 'self'; script-src 'self' 'unsafe-hashes' " + hashes + ' ' + sha(BOOT_HANDLER) +
            "; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
            "connect-src 'self' data: blob:; worker-src blob:; object-src 'none'; frame-src 'none'; "
            "child-src blob:; manifest-src 'none'; media-src 'none'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'")


FILES = load()
CSP = policy(FILES['index.html'])


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'static'
    sys_version = ''

    def log_message(self, *args):
        pass

    def target(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            path = urllib.parse.unquote(path, errors='strict')
        except UnicodeDecodeError:
            return None
        if path == '/':
            return 'index.html'
        if not path.startswith('/') or '\\' in path or '\x00' in path:
            return None
        name = path[1:]
        if any(part in ('', '.', '..') for part in name.split('/')):
            return None
        return name if name in FILES else None

    def answer(self, body):
        name = self.target()
        if name is None:
            data, status, kind = b'Not found\n', 404, 'text/plain; charset=utf-8'
        else:
            data, status, kind = FILES[name], 200, TYPES[PurePosixPath(name).suffix]
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        if body:
            self.wfile.write(data)

    def do_GET(self):
        self.answer(True)

    def do_HEAD(self):
        self.answer(False)

    def refuse(self):
        self.send_response(405)
        self.send_header('Allow', 'GET, HEAD')
        self.send_header('Content-Length', '0')
        self.end_headers()

    do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = refuse


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    Server((os.environ.get('HOST', '0.0.0.0'), int(os.environ.get('PORT', '3000'))), Handler).serve_forever()
