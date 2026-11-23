#!/usr/bin/env python3
'''Offline static server for the unmodified IT-Tools release v2024.10.22-7ca5933.

The built site is read once from the pinned release archive (members under dist/) and served byte for byte.
Like the upstream nginx configuration (try_files $uri $uri/ /index.html), every path that is not a file of the
site answers with index.html, and the page's history-mode router decides what to show. Only GET and HEAD are
answered. The archive is the only source of served content; nothing is generated or modified. HOST and PORT come
from the environment (defaults 0.0.0.0 and 3000).
'''
import http.server
import os
from pathlib import Path, PurePosixPath
import urllib.parse
import zipfile

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'it-tools-2024.10.22-7ca5933.zip'
PREFIX = 'dist/'
TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.json': 'application/json',
         '.webmanifest': 'application/manifest+json', '.txt': 'text/plain; charset=utf-8', '.xml': 'application/xml'}
CSP = ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; script-src-attr 'none'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
       "connect-src 'self' data: blob:; worker-src 'self' blob:; frame-src 'none'; object-src 'none'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def load():
    files = {}
    with zipfile.ZipFile(ARCHIVE) as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.startswith(PREFIX):
                continue
            name = info.filename[len(PREFIX):]
            if name and all(part not in ('', '.', '..') for part in name.split('/')):
                files[name] = archive.read(info)
    return files


FILES = load()


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
        if chr(92) in path or chr(0) in path:
            return None
        name = path.lstrip('/')
        return name if name in FILES else 'index.html'

    def answer(self, body):
        name = self.target()
        if name is None:
            data, status, kind = b'Bad request\n', 400, 'text/plain; charset=utf-8'
        else:
            data, status = FILES[name], 200
            kind = TYPES.get(PurePosixPath(name).suffix, 'application/octet-stream')
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
