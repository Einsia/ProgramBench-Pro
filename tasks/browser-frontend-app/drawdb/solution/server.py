#!/usr/bin/env python3
"""Offline static server for the unmodified drawDB 1.8.2 web application.

The application is the static build that drawDB's release pipeline published in its
container image ghcr.io/drawdb-io/drawdb:v1.8.2: the image layer holding
/usr/share/nginx/html (drawdb-1.8.2-dist.tar.gz) is read once and its files are
served byte for byte on HOST/PORT. Everything else follows the image's own nginx
configuration:

- /config.js answers the runtime configuration the image generates when no
  backend is configured (empty backendUrl and gistBackendUrl), uncached;
- any other path that is not a file of the build answers index.html, so the
  single-page application decides from the address what to show (nginx
  "try_files $uri /index.html").

Only GET and HEAD are answered. HOST and PORT come from the environment
(defaults 0.0.0.0 and 3000).
"""
import http.server
import os
from pathlib import Path, PurePosixPath
import tarfile
import urllib.parse

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'drawdb-1.8.2-dist.tar.gz'
PREFIX = 'usr/share/nginx/html/'
# Content types as nginx's default mime.types names them.
TYPES = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.png': 'image/png',
         '.ico': 'image/x-icon', '.txt': 'text/plain'}
CONFIG = b'window.__DRAWDB_CONFIG__ = { backendUrl: "", gistBackendUrl: "" };'
MONACO = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.52.2/min/vs/'
ICON_STYLES = ('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/ '
               'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/')
ICON_FONTS = ('https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/ '
              'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/webfonts/')
# Monaco uses same-origin/blob workers and its pinned module loader. Export
# rendering may create a blank frame; inline script and event attributes stay off.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval' " + MONACO + "; "
       "script-src-attr 'none'; style-src 'self' 'unsafe-inline' " + ICON_STYLES + ' ' + MONACO + "; "
       "font-src 'self' data: " + ICON_FONTS + "; img-src 'self' data: blob:; "
       "connect-src 'self' data: blob: " + MONACO + "; worker-src 'self' blob:; "
       "frame-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def load():
    files = {}
    with tarfile.open(ARCHIVE, 'r:gz') as archive:
        for member in archive.getmembers():
            if member.isfile() and member.name.startswith(PREFIX):
                files[member.name[len(PREFIX):]] = archive.extractfile(member).read()
    return files


FILES = load()


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'static'
    sys_version = ''

    def log_message(self, *args):
        pass

    def target(self):
        """The build file a path names, or None (then the application page answers)."""
        try:
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path, errors='strict')
        except UnicodeDecodeError:
            return None
        if '\x00' in path or '\\' in path:
            return None
        parts = [part for part in path.split('/') if part not in ('', '.')]
        if '..' in parts:
            return None
        name = '/'.join(parts)
        return name if name in FILES else None

    def answer(self, body):
        headers = {}
        if urllib.parse.urlsplit(self.path).path == '/config.js':
            data, kind = CONFIG, 'application/javascript'
            headers['Cache-Control'] = 'no-store'
        else:
            name = self.target() or 'index.html'
            data, kind = FILES[name], TYPES.get(PurePosixPath(name).suffix, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        for key, value in headers.items():
            self.send_header(key, value)
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
