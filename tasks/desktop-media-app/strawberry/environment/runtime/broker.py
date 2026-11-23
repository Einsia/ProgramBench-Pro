#!/usr/bin/env python3
"""Strawberry 1.2.31 desktop, command and document exchange runtime.

All application responses come from the running application.
"""
from __future__ import annotations
import base64
import hashlib
import http.server
import json
import math
import os
from pathlib import Path
import re
import shlex
import stat
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime
import document_exchange as exchange
import blackbox_desktop as desktop

PRODUCT = 'Strawberry 1.2.31'
SCREEN = (1440, 900)
MAX_FILE = 16_000_000
MAX_REQUEST = 22_000_000
RPC_SECONDS = 90
MAX_IN_FLIGHT = 8
AREAS = ('inputs', 'music', 'outputs')
AUDIO = ('.wav', '.wave', '.flac', '.ogg', '.oga', '.opus', '.spx', '.mp3', '.mp2', '.m4a', '.mp4', '.aac',
         '.aif', '.aiff', '.wv', '.ape', '.wma', '.asf', '.mka', '.tta', '.dsf', '.dsd', '.ac3', '.dts',
         '.mod', '.s3m', '.xm', '.it', '.spc', '.vgm', '.webm')
PLAYLIST = ('.m3u', '.m3u8', '.pls', '.xspf', '.asx', '.asxini', '.cue', '.wpl')
IMAGES = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp')
SUFFIXES = AUDIO + PLAYLIST + IMAGES
CATALOG = json.loads(Path(__file__).with_name('mpris_catalog.json').read_text())
FLAGS = ('--play', '--play-pause', '--pause', '--stop', '--stop-after-current', '--previous', '--next',
         '--volume-up', '--volume-down', '--restart-or-previous', '--load', '--append', '--quiet', '--help', '--version')
TEXT_VALUES = ('--create', '--play-playlist')
VALUES = ('--volume', '--volume-increase-by', '--volume-decrease-by', '--seek-to', '--seek-by', '--play-track')
# Features with unrestricted database/command or external application access.
BLOCKED = ('console', 'open in file browser', 'show in file browser', 'open in file manager',
           'open in browser', 'open url', 'open audio cd', 'rescan devices', 'configure shortcuts',
           'show in file manager', 'open file manager', 'visit website', 'homepage', 'report a bug')
UNSAFE = ('console', 'open audio cd', 'device properties')


def field(kind, description, required=False, **extra):
    return dict(type=kind, description=description, **({'required': True} if required else {}), **extra)


OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'Operations, MPRIS catalog, command-line options and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Application process and accessible-window readiness.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'summary': 'Start a fresh application profile, desktop and document folders.', 'fields': {}},
    'restart': {'kind': 'lifecycle', 'summary': 'Relaunch start.sh with the same profile and documents.', 'fields': {}},
    'mpris': {'kind': 'http', 'summary': 'Call the real MPRIS2 service on the private session bus. Replies are ok/value or ok/error/message.',
              'fields': {'interface': field('string', 'MPRIS interface alias.', True, enum=list(CATALOG)),
                         'action': field('string', 'Property read/write or method call.', True, enum=['get', 'get_all', 'set', 'call']),
                         'member': field('string', 'Property or method name from mpris_catalog; omitted for get_all.'),
                         'args': field('array', 'Ordered method arguments; file URIs must name allowed documents.'),
                         'value': field(['string', 'number', 'boolean'], 'Property value for set.')}},
    'cli': {'kind': 'http', 'summary': 'Run start.sh with documented Strawberry command-line arguments, forwarding to the running application. Returns exit_code/stdout/stderr.',
            'fields': {'args': field('array', 'Strings: permitted flags, option values and absolute document paths. See command_line.', True)}},
    'upload': {'kind': 'files', 'summary': 'Write a document to inputs or music. Music is the initially configured collection folder. The modification time is fixed.',
               'fields': {'filename': field('string', 'Non-hidden basename with an allowed media, playlist or image suffix; at most 240 UTF-8 bytes.', True),
                          'area': field('string', 'Destination; default inputs.', enum=['inputs', 'music']),
                          'base64': field('string', 'Base64 bytes, at most 16000000 decoded bytes.', True)}},
    'list_files': {'kind': 'files', 'summary': 'List allowed documents recursively in one area, including path, size and content-derived download ref.',
                   'fields': {'area': field('string', 'Document area; default outputs.', enum=list(AREAS))}},
    'download': {'kind': 'files', 'summary': 'Read an allowed document identified by a ref from list_files.',
                 'fields': {'ref': field('string', 'Content-derived document ref.', True)}},
    **desktop.operations(SCREEN),
})


def basename(name):
    if (not name or len(name.encode('utf-8')) > 240 or name.startswith('.') or Path(name).name != name
            or '\\' in name or any(ord(c) < 32 or ord(c) == 127 for c in name)):
        raise ValueError('filename must be a non-hidden basename of at most 240 UTF-8 bytes')
    if Path(name).suffix.casefold() not in SUFFIXES:
        raise ValueError('unsupported document suffix; see help')
    return name


def normalized(name):
    return str(name).replace('&', '').strip().rstrip('.…').casefold()


class MediaProduct(runtime.Product):
    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state).resolve()
        self.log = runtime.BoundedLog(config.log_dir)
        self.product = MediaProduct(config, log=self.log)
        self.session = self.desk = None
        self.lock = threading.RLock()
        self.downloads = {}
        self.hide = runtime.redactor(config.solution, config.state, config.work, config.log_dir,
                                     Path(__file__).resolve().parent, '/app/solution', '/reference')

    def read_document(self, path, limit=None):
        return exchange.read(self.state / 'files', path, MAX_FILE if limit is None else limit)

    def area(self, name):
        return self.state/'files'/name

    def start(self, fresh):
        self.product.stop()
        if fresh or self.session is None or not self.session.alive():
            if self.desk: self.desk.close()
            if self.session: self.session.close()
            self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=True,
                                                 log_dir=Path(self.config.log_dir)/'desktop').start()
            self.desk = desktop.Desktop(self.session, settle=.3, log_dir=Path(self.config.log_dir)/'desktop', pointer_guard=self.guard_pointer)
        if fresh: self.downloads.clear()
        self.product.extra = {k: v for k,v in self.session.env().items()
                              if k not in ('HOME', 'TMPDIR', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'DATA_DIR', 'AT_SPI_BUS_ADDRESS')}
        self.product.extra.update(PBP_COLLECTION_DIR=str(self.area('music')),
                                  PBP_INPUT_DIR=str(self.area('inputs')), PBP_OUTPUT_DIR=str(self.area('outputs')))
        if self.product.start(fresh):
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(200,150)),
                               failure='the application showed no accessible window within the startup deadline')
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        if self.desk: self.desk.close()
        if self.session: self.session.close()

    def inside(self, text):
        try:
            p = Path(text)
            if not p.is_absolute(): return False
            return any(p.resolve().is_relative_to(self.area(a).resolve()) for a in AREAS)
        except (OSError, ValueError, RuntimeError):
            return False

    def path(self, text, *, directory=False):
        if not isinstance(text, str) or '\x00' in text or len(text) > 4096:
            raise ValueError('invalid document path')
        original = Path(text)
        p = Path(os.path.normpath(text))
        if any(x.is_symlink() for x in [original, *original.parents]):
            raise ValueError('document paths may not traverse symbolic links')
        if not self.inside(str(p)):
            raise ValueError('paths must stay inside the document folders listed in help')
        if not directory and p.suffix.casefold() not in SUFFIXES:
            raise ValueError('unsupported document suffix; see help')
        return p

    def uri(self, text, base=None):
        if not isinstance(text, str): raise ValueError('URI must be text')
        u = urllib.parse.urlsplit(text)
        if u.scheme:
            if u.scheme != 'file' or u.netloc or u.query or u.fragment:
                raise ValueError('only file URIs in the document folders are available')
            path = urllib.parse.unquote(u.path)
        else:
            path = text
        if base is not None and not Path(path).is_absolute(): path = str(base/path)
        return str(self.path(path))

    def validate_playlist(self, payload, path):
        """Validate the playlist format selected by content, then by suffix."""
        ext = path.suffix.casefold()
        magic = payload[:512]
        lower = magic.lower()
        # The application probes these formats in this order before checking the suffix.
        if b'<playlist' in magic and b'<trackList' in magic:
            ext = '.xspf'
        elif b'#EXTM3U' in magic or b'#EXTINF' in magic:
            ext = '.m3u'
        elif b'[playlist]' in lower:
            ext = '.pls'
        elif b'<asx' in lower:
            ext = '.asx'
        elif b'[reference]' in lower:
            ext = '.asxini'
        elif re.search(rb'(?im)^\s*(?:PERFORMER|TITLE|FILE|TRACK)', magic):
            ext = '.cue'
        elif b'<?wpl' in magic or b'<smil>' in magic:
            ext = '.wpl'
        if ext not in PLAYLIST: return
        encoding = 'utf-16' if payload.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
        text = payload.decode(encoding, errors='replace')
        urls = []
        if ext in ('.m3u', '.m3u8'):
            urls = [s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
        elif ext in ('.pls', '.asxini'):
            urls = [m.group(1).strip() for m in re.finditer(r'(?im)^\s*(?:file\d+|ref\d+)\s*=\s*(.*)$',text)]
        elif ext == '.cue':
            urls = [m.group(1) or m.group(2) for m in re.finditer(r'(?im)^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+',text)]
        else:
            if re.search(r'<!DOCTYPE|<!ENTITY',text,re.I): raise ValueError('XML declarations with entities are not accepted')
            try:
                tree = ET.fromstring(text)
            except ET.ParseError:
                raise ValueError('the playlist is not valid XML') from None
            for element in tree.iter():
                tag=element.tag.rsplit('}',1)[-1].casefold()
                if tag in ('location','url') and element.text: urls.append(element.text.strip())
                for key,value in element.attrib.items():
                    if key.casefold() in ('src','href','url'): urls.append(value)
        for url in urls: self.uri(url,path.parent)

    def upload(self, data):
        name = basename(data['filename'])
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE: raise ValueError('document exceeds the byte limit')
        path = self.area(data.get('area','inputs'))/name
        self.path(str(path))
        self.validate_playlist(payload,path)
        exchange.write(self.area(data.get('area', 'inputs')), path, payload,
                       self.product.account(), mtime=1704067200)
        return {'uploaded':True,'filename':name,'path':str(path),'size':len(payload)}

    def list_files(self, data):
        area=data.get('area','outputs');rows=[]
        root=self.area(area)
        if not root.is_dir(): return {'files':[]}
        for relative, info in exchange.entries(root):
            path = root / relative
            if not stat.S_ISREG(info.st_mode) or path.suffix.casefold() not in SUFFIXES:
                continue
            try:
                payload = self.read_document(path)
            except (ValueError, OSError):
                continue
            digest = hashlib.sha256(payload).hexdigest()
            ref = hashlib.sha256((str(path.relative_to(self.state)) + '\0' + digest).encode()).hexdigest()[:24]
            self.downloads[ref] = (path, digest)
            rows.append({'ref': ref, 'filename': relative, 'path': str(path), 'size': len(payload)})
            if len(rows) >= 500:
                break
        return {'files': rows}

    def download(self, data):
        if data['ref'] not in self.downloads: raise ValueError('unknown document ref; use list_files')
        path,digest=self.downloads[data['ref']];self.path(str(path))
        payload = self.read_document(path)
        if len(payload)>MAX_FILE or hashlib.sha256(payload).hexdigest()!=digest:
            raise ValueError('document changed; use list_files again')
        return {'filename':path.name,'size':len(payload),'body_base64':base64.b64encode(payload).decode()}

    def run(self, args, input=None, timeout=25):
        if not self.product.running(): raise ValueError('application is not running; use restart or reset')
        kw=desktop.as_user(self.config.user)
        result=subprocess.run(args,input=input,text=True,env=self.product.environment(),cwd=self.product.solution,
                              capture_output=True,timeout=timeout,**kw)
        return result

    def mpris(self, data):
        spec=CATALOG[data['interface']];action=data['action'];member=data.get('member')
        request={'interface':spec['interface'],'action':action,'member':member}
        if action=='get_all':
            if any(k in data for k in ('member','value','args')): raise ValueError('get_all takes only interface/action')
        elif action in ('get','set'):
            if member not in spec['properties']: raise ValueError('unknown MPRIS property')
            if 'args' in data or (action=='get' and 'value' in data): raise ValueError('unexpected property fields')
            if action=='set':
                prop=spec['properties'][member]
                if prop['access']!='readwrite': raise ValueError('property is read-only')
                v=data.get('value');t=prop['type']
                if t=='b' and type(v) is not bool: raise ValueError('property needs a boolean')
                if t=='s' and (not isinstance(v,str) or len(v)>200): raise ValueError('property needs short text')
                if t=='d' and (type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6): raise ValueError('property needs a finite number')
                request.update(value=v,value_type=t)
        else:
            if member not in spec['methods']: raise ValueError('unknown MPRIS method')
            if 'value' in data: raise ValueError('methods use args')
            args=data.get('args',[]);method=spec['methods'][member]
            if len(args)!=len(method['arguments']): raise ValueError('wrong method argument count')
            if len(json.dumps(args))>16384: raise ValueError('method arguments exceed the limit')
            args=list(args)
            if member in ('OpenUri','AddTrack'):
                args[0]=Path(self.uri(args[0])).as_uri()
            if member=='GetTracksMetadata' and (not isinstance(args[0],list) or len(args[0])>500):
                raise ValueError('track ids must be an array of at most 500 paths')
            request.update(signature=method['signature'],args=args)
        response=self.run(['python3','-B','-I',str(Path(__file__).with_name('mpris.py'))],json.dumps(request))
        if response.returncode: raise ValueError('MPRIS request could not be delivered')
        return json.loads(response.stdout)

    def cli(self, data):
        args=data['args']
        if not args or len(args)>100 or not all(isinstance(a,str) and len(a)<4096 and '\x00' not in a for a in args):
            raise ValueError('args must contain 1-100 short strings')
        checked=[];i=0
        while i<len(args):
            item=args[i]
            if item in FLAGS: checked.append(item)
            elif item in TEXT_VALUES:
                i+=1
                if i==len(args) or len(args[i])>200 or any(ch in args[i] for ch in '/\\\x00\n'):raise ValueError('playlist name must be short text')
                checked.extend([item,args[i]])
            elif item in VALUES:
                i+=1
                if i==len(args) or not re.fullmatch(r'-?\d{1,9}',args[i]): raise ValueError('numeric command-line option requires an integer')
                checked.extend([item,args[i]])
            elif item.startswith('-'): raise ValueError('command-line option is not exposed; see help')
            else: checked.append(str(self.path(item)))
            i+=1
        result=self.run([str(self.product.solution/'start.sh'),*checked])
        return {'exit_code':result.returncode,'stdout':result.stdout[:100000],'stderr':result.stderr[:100000]}

    @staticmethod
    def under(nodes,ref):
        mapping={n['ref']:n for n in nodes};out=[]
        for node in nodes:
            cur=node;seen=set()
            while cur and cur['ref'] not in seen:
                if cur['ref']==ref: out.append(node);break
                seen.add(cur['ref']);cur=mapping.get(cur.get('parent'))
        return out

    def chooser(self, nodes):
        for node in nodes:
            if node['role'] not in ('dialog','file chooser'): continue
            inside=self.under(nodes,node['ref'])
            if node['role']=='file chooser' or (any(n['role']=='list' and n.get('name')=='Sidebar' for n in inside)
                and any('Look in' in n.get('name','') for n in inside)):
                return inside
        return []

    def confirm(self, inside):
        inside=self.chooser(self.desk.observe(tree=True).get('nodes',[]))
        entries=[n for n in inside if n['role'] in ('text','entry') and 'editable' in n.get('states',[])]
        if not entries: raise ValueError('file dialog has no editable filename field')
        entry=entries[0];text=str(entry.get('text') or entry.get('value') or '').strip()
        values=shlex.split(text) if text.startswith('"') else [text]
        for value in values: self.path(value,directory=True)
        buttons=[n for n in inside if n['role'] in ('button','push button') and normalized(n.get('name')) in ('open','save','choose','select')]
        if not values or not text: raise ValueError('type an absolute document path before confirming')
        self.desk.set_text({'ref':entry['ref']},text,confirm={'ref':buttons[0]['ref']} if buttons else None)
        if not buttons: self.desk.act({'op':'press','key':'Return'})
        return {'confirmed':text,'note':'observe again to refresh controls'}

    def guard(self, view):
        nodes=view.get('nodes',[])
        if any(n['role']=='page tab list' and n.get('name')=='Files' for n in nodes):
            fields=[n for n in nodes if n['role'] in ('text','entry') and 78<=n['bounds'][0]<313 and str(n.get('text','')).startswith('/')]
            for n in fields:
                if not self.inside(n.get('text','')):
                    current=self.desk.observe(tree=True)
                    field=next((x for x in current['nodes'] if x['role']==n['role'] and x.get('text')==n.get('text')),None)
                    if field:self.desk.set_text({'ref':field['ref']},str(self.area('music')))
                    raise ValueError('the file browser is confined to document folders')
        titles=[w.get('title','') for w in view.get('windows',[])]
        if any(any(word in title.casefold() for word in UNSAFE) for title in titles):
            self.desk.act({'op':'press','key':'Escape'})
            for title in titles:
                if any(word in title.casefold() for word in UNSAFE):
                    subprocess.run(['wmctrl','-F','-c',title],env=self.product.environment(),capture_output=True,timeout=5)
            raise ValueError('this command-capable window is not available through the runtime')

    def guard_pointer(self, event):
        """Apply control restrictions to implicit clicks and the complete drag path."""
        request = event['pointer']
        view = self.desk.inspect()
        nodes = view.get('nodes', [])
        points = [request]
        if request['op'] == 'drag':
            points += [{'target': request['to_target']}] if request.get('to_target') is not None else [
                {'x': request.get('to_x'), 'y': request.get('to_y')}]
            points += [{'x': x, 'y': y} for x, y in request.get('via', [])]
        for point in points:
            node = self.desk.resolve(point['target']) if point.get('target') is not None else (
                desktop.node_at(view, point['x'], point['y'])
                if point.get('x') is not None and point.get('y') is not None else None)
            if node and any(normalized(node.get('name')).startswith(word) for word in BLOCKED):
                raise ValueError('external application and command-capable controls are not exposed')
        chooser = self.chooser(nodes)
        if not chooser or request['op'] == 'move':
            return
        if request['op'] not in ('click', 'activate'):
            raise ValueError('this file-dialog gesture is not available')
        node = self.desk.resolve(request['target']) if request.get('target') is not None else (
            desktop.node_at(view, request['x'], request['y']) if 'x' in request and 'y' in request else None)
        if not node:
            raise ValueError('target a file dialog control')
        name = normalized(node.get('name'))
        if node['role'] in ('text', 'entry') or node['role'] in ('button', 'push button') and name == 'cancel':
            return
        if node['role'] in ('combo box', 'menu item', 'list item') and re.search(r'files of type|format|\(\*\.|all files \(', name):
            return
        raise ValueError('confirm file dialogs through their checked document path')

    def gui(self, op, data):
        view=self.desk.inspect();self.guard(view);nodes=view.get('nodes',[])
        chooser=self.chooser(nodes);node=None
        if data.get('target') is not None: node=self.desk.resolve(data['target'])
        elif 'x' in data and 'y' in data: node=desktop.node_at(view,data['x'],data['y'])
        elif op in ('press','type'): node=next((n for n in reversed(nodes) if 'focused' in n.get('states',[])),None)
        if node and any(normalized(node.get('name')).startswith(word) for word in BLOCKED):
            raise ValueError('external application and command-capable controls are not exposed')
        if op in ('type','fill'):
            value=data.get('value','')
            if '\x00' in value or '\\' in value or value.startswith('~') or '://' in value:
                raise ValueError('text may not contain external URLs or ambiguous filesystem paths')
            if value.startswith('/') or '..' in value.split('/'):
                self.path(value,directory=True)
        key=str(data.get('key','')).replace('Control','ctrl').casefold()
        affirmative=op in ('click','activate') and node and normalized(node.get('name')) in ('ok','save','start','organize','copy','move','transcode','export','apply')
        if not chooser and (affirmative or op=='press' and key in ('return','enter','ctrl+s')):
            titles=[w.get('title','').casefold() for w in view.get('windows',[])]
            if any(any(label in title for label in ('organize','transcod','save playlists','export cover','settings')) for title in titles):
                for n in nodes:
                    if n['role'] in ('text','entry') and 'editable' in n.get('states',[]):
                        v=str(n.get('text') or '').strip()
                        if v.startswith('/') or v.startswith('~') or '..' in v.replace('\\','/').split('/'):
                            self.path(v,directory=True)
        if chooser and op not in ('wait','zoom','move'):
            if op in ('type','fill'):
                if node and node['role'] not in ('text','entry'): raise ValueError('type paths in the filename field')
                if op=='type' and '/' in data.get('value',''): self.desk.act({'op':'press','key':'Control+a'})
            elif op=='press':
                if key in ('return','enter'): return self.confirm(chooser)
                if key not in ('ctrl+a','ctrl+l','escape','backspace','delete','left','right','home','end'):
                    raise ValueError('file dialog keys are limited to filename editing, Escape and Return')
            elif op in ('click','activate'):
                if not node: raise ValueError('target a file dialog control')
                role=node['role'];name=normalized(node.get('name'))
                if role in ('button','push button'):
                    if name in ('open','save','choose','select','ok'): return self.confirm(chooser)
                    if name!='cancel': raise ValueError('use absolute document paths to navigate file dialogs')
                elif role in ('text','entry'): pass
                elif role in ('combo box','menu item','list item') and re.search(r'files of type|format|\(\*\.|all files \(',name): pass
                else: raise ValueError('use absolute document paths to navigate file dialogs')
            else: raise ValueError('this file-dialog gesture is not available')
        if op=='click' and data.get('button')=='right':
            if data.get('target') is not None:
                result=self.desk.act({'op':'drag','target':data['target'],'to_target':data['target'],'button':'right','seconds':.35})
            else:
                result=self.desk.act({'op':'drag','x':data['x'],'y':data['y'],'to_x':data['x'],'to_y':data['y'],'button':'right','seconds':.35})
        elif op=='fill' and node and node['role'] in ('text','entry'):
            result=self.desk.set_text(data['target'],data['value'])
        else:
            result=self.desk.act(data)
        self.guard(self.desk.inspect())
        return result

    def help(self):
        return runtime.help_document(PRODUCT,'desktop',OPERATIONS,
            limits={'file_bytes':MAX_FILE,'request_bytes':MAX_REQUEST,'rpc_seconds':RPC_SECONDS,'screen':list(SCREEN),
                    'ready_seconds':self.config.ready_timeout},
            notes=['MPRIS uses org.mpris.MediaPlayer2.strawberry at /org/mpris/MediaPlayer2 on DBUS_SESSION_BUS_ADDRESS. The desktop, CLI and MPRIS share state.',
                   'start.sh without arguments starts the foreground application; with CLI arguments it forwards to the running instance.',
                   'PBP_COLLECTION_DIR, PBP_INPUT_DIR and PBP_OUTPUT_DIR name the three document folders. A fresh profile has one empty playlist and the music folder configured as the collection.',
                   'File dialogs accept absolute document paths. Navigation elsewhere, symbolic links, console and external application controls are refused.',
                   'Playlist resource references must remain in the document folders. Uploaded files receive a fixed modification time. Downloads expose only media, playlist and image documents.',
                   'Right clicks hold the button briefly so popup menus can finish opening. reset discards profile and documents; restart keeps both.'],
            examples=[{'op':'mpris','interface':'Player','action':'get_all'}, {'op':'cli','args':['--pause']},
                      {'op':'observe'},{'op':'list_files','area':'music'}],
            document_areas={a:str(self.area(a)) for a in AREAS},mpris_catalog=CATALOG,
            command_line={'flags':list(FLAGS),'integer_options':list(VALUES),'text_options':list(TEXT_VALUES),'files':'absolute document paths'},
            document_suffixes=list(SUFFIXES))

    def dispatch(self, data):
        op=runtime.validate(OPERATIONS,data)
        if op=='help': return self.help()
        if op=='status': return self.status()
        if op in ('reset','restart'): return self.start(op=='reset')
        if op in ('mpris','cli','upload','list_files','download'): return getattr(self,op)(data)
        if op in ('observe','screenshot','windows'):
            self.guard(self.desk.inspect())
            if op=='windows': return {'windows':self.desk.windows()}
            return getattr(self.desk,op)(**{k:v for k,v in data.items() if k!='op'})
        return self.gui(op,data)

    def redact(self, text):
        text=str(text)
        return re.sub(r'/[^\s\'"<>()\[\]{},;]*',lambda m:m.group(0) if self.inside(m.group(0)) else self.hide(m.group(0)),text)

    def clean(self, value):
        if isinstance(value,str): return self.redact(value)
        if isinstance(value,list): return [self.clean(v) for v in value]
        if isinstance(value,dict): return {k:(v if k in ('png_base64','body_base64') else self.clean(v)) for k,v in value.items()}
        return value


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

    def __init__(self, sock, broker):
        super().__init__('blackbox', Handler, bind_and_activate=False)
        self.socket.close()
        self.socket, self.address_family = sock, sock.family
        self.server_name, self.server_port = 'localhost', 0
        self.broker = broker
        self.in_flight = 0
        self.count = threading.Lock()


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def address_string(self):
        return 'blackbox'

    def reply(self, code, value):
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        server, broker, started, op = self.server, self.server.broker, time.monotonic(), None
        with server.count:
            busy = server.in_flight >= MAX_IN_FLIGHT
            if not busy:
                server.in_flight += 1
        if busy:
            self.reply(429, {'error': 'Busy', 'detail': 'too many pending requests'})
            return
        try:
            if self.path != '/rpc':
                raise ValueError('unknown RPC endpoint')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError('request size outside limits')
            data = runtime.strict_json_loads(self.rfile.read(length))
            op = data.get('op', 'help') if isinstance(data, dict) else None
            outcome, done = {}, threading.Event()

            def work():
                try:
                    if not broker.lock.acquire(timeout=RPC_SECONDS):
                        raise TimeoutError
                    try:
                        outcome['value'] = broker.clean(broker.dispatch(data))
                    finally:
                        broker.lock.release()
                except BaseException as exc:
                    outcome['error'] = exc
                finally:
                    done.set()
            threading.Thread(target=work, daemon=True).start()
            if not done.wait(RPC_SECONDS):
                code, value = 408, {'error': 'TimeoutError', 'detail': 'black-box request deadline exceeded'}
            elif 'error' in outcome:
                exc = outcome['error']
                if isinstance(exc, TimeoutError) or getattr(exc, 'timeout', False) is True:
                    code, value = 408, {'error': 'TimeoutError', 'detail': 'black-box request deadline exceeded'}
                else:
                    code, value = 400, {'error': type(exc).__name__, 'detail': broker.redact(str(exc))[:600]}
            else:
                code, value = 200, outcome['value']
        except Exception as exc:
            code, value = 400, {'error': type(exc).__name__, 'detail': broker.redact(str(exc))[:600]}
        finally:
            with server.count:
                server.in_flight -= 1
        server.audit.record(op, code, time.monotonic()-started)
        self.reply(code, value)


def main(argv=None):
    config = runtime.options(state='/reference/state', log_dir='/reference', work='/reference/work',
                             ready_timeout=30.0).parse_args(argv)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    # SIGTERM ends the runtime through the finally
    # block, which stops the product and closes the desktop session.
    runtime.exit_on_sigterm()
    broker = Broker(config)
    server = None
    try:
        # A product that fails to start is reported by status; the runtime keeps serving.
        broker.start(True)
        server = Server(runtime.listen(config.socket, config.socket_mode), broker)
        server.audit = runtime.Audit(Path(config.log_dir)/'rpc-audit.jsonl')
        server.serve_forever()
    finally:
        broker.close()
        if server is not None:
            server.server_close()


if __name__ == '__main__':
    main()
