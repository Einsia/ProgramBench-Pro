#!/usr/bin/env python3
"""Serve the pinned upstream examples and assets offline, with a static allowlist."""
import base64
import hashlib
import http.server
import os
from pathlib import Path
import re
import tarfile
import urllib.parse

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / 'jsoneditor-10.4.3.tgz'
# A custom query executor and the advanced JSONPath completion example accept
# executable input. New-window integration is outside the single-page surface.
EXCLUDED = {'13_autocomplete_advanced.html', '23_custom_query_language.html', '24_new_window.html'}
RELOCATIONS = {
 'https://bgrins.github.io/filereader.js/filereader.js': '/vendor/filereader.js',
 'https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2014-11-29/FileSaver.min.js': '/vendor/FileSaver.min.js',
 'https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.21/lodash.min.js': '/vendor/lodash.min.js',
 'https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.6/ace.js': '/vendor/ace/ace.js',
}
TYPES = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8',
         '.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
FILES = {}
with tarfile.open(ARCHIVE) as archive:
 for m in archive.getmembers():
  name = m.name.removeprefix('package/')
  if not m.isfile(): continue
  keep = (name in {'dist/jsoneditor.js','dist/jsoneditor-minimalist.js','dist/jsoneditor.css','dist/img/jsoneditor-icons.svg','examples/css/darktheme.css'}
          or (re.fullmatch(r'examples/\d{2}_[a-z_]+\.html',name) and name.split('/')[-1] not in EXCLUDED))
  if keep:
   data=archive.extractfile(m).read()
   for url,local in RELOCATIONS.items(): data=data.replace(url.encode(),local.encode())
   FILES['/'+name]=data
for p in (HERE/'vendor').rglob('*.js'): FILES['/vendor/'+str(p.relative_to(HERE/'vendor'))]=p.read_bytes()
FILES['/']=FILES['/examples/03_switch_mode.html']
# Inline script bodies in shipped examples are explicitly admitted by hash.
hashes=set()
for name,data in FILES.items():
 if name.endswith('.html') or name=='/':
  hashes.update("'sha256-"+base64.b64encode(hashlib.sha256(s).digest()).decode()+"'" for s in re.findall(rb'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>',data,re.S))
# Schema compilation needs unsafe-eval. User-controlled script is never accepted;
# inline script execution is restricted to the static example bodies above.
CSP=("default-src 'none'; script-src 'self' 'unsafe-eval' "+' '.join(sorted(hashes))+"; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'none'; worker-src blob:; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
class Handler(http.server.BaseHTTPRequestHandler):
 server_version='static';sys_version=''
 def log_message(self,*args):pass
 def answer(self,body):
  url=urllib.parse.urlsplit(self.path); path=urllib.parse.unquote(url.path)
  good=not url.query and path in FILES
  data=FILES[path] if good else b'Not found\n'
  self.send_response(200 if good else 404)
  self.send_header('Content-Type',TYPES.get(Path(path).suffix,'text/html; charset=utf-8') if good else 'text/plain')
  self.send_header('Content-Length',str(len(data))); self.send_header('Content-Security-Policy',CSP)
  self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers()
  if body:self.wfile.write(data)
 def do_GET(self):self.answer(True)
 def do_HEAD(self):self.answer(False)
class Server(http.server.ThreadingHTTPServer):
 daemon_threads=True;allow_reuse_address=True
if __name__=='__main__':Server((os.environ.get('HOST','0.0.0.0'),int(os.environ.get('PORT','3000'))),Handler).serve_forever()
