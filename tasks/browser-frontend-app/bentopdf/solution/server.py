#!/usr/bin/env python3
"""Serve the pinned upstream offline build without changing product assets.

The build uses upstream's documented SIMPLE_MODE and local-WASM flags. This
server supplies static files, the cross-origin isolation headers required by
LibreOffice, and a policy excluding source files and configuration interfaces.
"""
import base64
import hashlib
import http.server
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
import urllib.parse
import zipfile

HERE=Path(__file__).resolve().parent
ARCHIVE=HERE/'bentopdf-2.8.10-offline.zip'
SITE=zipfile.ZipFile(ARCHIVE)
EXTENSIONS={'.html','.js','.mjs','.css','.svg','.png','.jpg','.jpeg','.webp','.gif','.ico','.woff','.woff2','.ttf','.otf',
            '.wasm','.gz','.br','.data','.json','.icc','.whl','.zip','.bcmap','.pfb','.ftl','.properties'}

def served(name):
    p=PurePosixPath(name)
    if name.startswith('/') or any(part.startswith('.') or part=='..' for part in p.parts):return False
    if p.suffix.lower() not in EXTENSIONS:return False
    if any(s in p.parts for s in ('build_scripts','src','tests','test','types','node_modules')):return False
    if p.name in {'package.json','package-lock.json','sw.js'} or 'sandbox' in p.name.lower():return False
    if p.name.startswith(('wasm-settings.',)):return False
    return True

FILES={i.filename for i in SITE.infolist() if not i.is_dir() and served(i.filename)}
# Each document gets its own inline hashes; resources use the common policy.
BASE_CSP=("default-src 'self'; script-src 'self' blob: 'unsafe-eval' 'wasm-unsafe-eval' {hashes}; "
          "style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self' data: blob:; "
          "connect-src 'self' blob: data:; worker-src 'self' blob:; frame-src 'self'; object-src 'none'; "
          "base-uri 'self'; form-action 'none'; frame-ancestors 'self'")
def policy(name,data):
    hashes=[]
    if name and name.endswith('.html'):
        for body in re.findall(rb'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>',data,re.S):
            hashes.append("'sha256-"+base64.b64encode(hashlib.sha256(body).digest()).decode()+"'")
    return BASE_CSP.format(hashes=' '.join(sorted(set(hashes))))

TYPES={'.wasm':'application/wasm','.mjs':'text/javascript','.js':'text/javascript','.whl':'application/octet-stream',
       '.bcmap':'application/octet-stream','.icc':'application/vnd.iccprofile','.ftl':'text/plain'}

class Handler(http.server.BaseHTTPRequestHandler):
    server_version='static';sys_version=''
    def log_message(self,*a):pass
    def target(self):
        try:path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path,errors='strict')
        except (ValueError,UnicodeDecodeError):return None
        if not path.startswith('/') or path.startswith('//') or '\\' in path or any(ord(c)<32 for c in path):return None
        if path.endswith('/'):path+='index.html'
        name=path[1:]
        if any(s in ('','.','..') for s in name.split('/')):return None
        return name if name in FILES else None
    def answer(self,body=True):
        name=self.target()
        if name is None:data,code,mime=b'Not found\n',404,'text/plain; charset=utf-8'
        else:
            data=SITE.read(name);code=200
            mime=TYPES.get(PurePosixPath(name).suffix) or mimetypes.guess_type(name)[0] or 'application/octet-stream'
            if name.endswith('.json'):mime='application/json'
        self.send_response(code)
        for k,v in [('Content-Type',mime),('Content-Length',str(len(data))),('Content-Security-Policy',policy(name,data)),
                    ('Cross-Origin-Opener-Policy','same-origin'),('Cross-Origin-Embedder-Policy','require-corp'),
                    ('Cross-Origin-Resource-Policy','same-origin'),('X-Content-Type-Options','nosniff'),
                    ('Referrer-Policy','no-referrer'),('Cache-Control','no-store')]:self.send_header(k,v)
        self.end_headers()
        if body:
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):self.answer()
    def do_HEAD(self):self.answer(False)
    def refuse(self):self.send_response(405);self.send_header('Content-Length','0');self.end_headers()
    do_POST=do_PUT=do_PATCH=do_DELETE=do_OPTIONS=refuse
class Server(http.server.ThreadingHTTPServer):
    daemon_threads=True;allow_reuse_address=True
if __name__=='__main__':Server((os.environ.get('HOST','0.0.0.0'),int(os.environ.get('PORT','3000'))),Handler).serve_forever()
