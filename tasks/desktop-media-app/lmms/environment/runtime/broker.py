#!/usr/bin/env python3
'''LMMS desktop runtime: command-line actions, documents and application lifecycle.

Operations use the running application and its ordinary document interfaces.
'''
from __future__ import annotations

import base64
import http.server
import json
import os
from pathlib import Path
import re
import signal
import socketserver
import stat
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ElementTree
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402
import exchange  # noqa: E402

PRODUCT = 'LMMS 1.2.2'
SCREEN = (1440, 900)
SETTLE = 0.5
MAX_REQUEST = 5_600_000
MAX_FILE = 4_000_000
MAX_PROJECT = 16_000_000
MAX_DOWNLOAD = 16_000_000
RPC_SECONDS = 115
CLI_SECONDS = 100
MAX_IN_FLIGHT = 8
AREAS = ('inputs', 'outputs', 'projects')
WATCHED = ('outputs', 'projects', 'templates', 'presets')
ACTIONS = ('render', 'rendertracks', 'dump', 'upgrade')
FORMATS = ('wav', 'flac', 'ogg', 'mp3')
INTERPOLATIONS = ('linear', 'sincfastest', 'sincmedium', 'sincbest')
STEREO_MODES = ('s', 'j', 'm')
RENDER_ONLY = ('format', 'samplerate', 'bitrate', 'float', 'interpolation', 'oversampling', 'loop', 'stereo_mode')
UPLOAD_SUFFIXES = ('.wav', '.wave', '.ogg', '.flac', '.mp3', '.aif', '.aiff', '.au', '.mid', '.midi', '.rmi', '.h2song',
                   '.mmp', '.mmpz', '.mpt', '.xpf', '.sf2')
DOWNLOAD_SUFFIXES = ('.wav', '.ogg', '.flac', '.mp3', '.mmp', '.mmpz', '.mpt', '.xpf', '.mid')
SPACE = ' ' + chr(9) + chr(10) + chr(13)
QUOTES = chr(39) + chr(34)
TOKEN = re.compile('/[^' + re.escape(SPACE + QUOTES + '<>()[]{},;') + ']*')
NOISE = re.compile('libcarla|VST sync|realtime priority|QStandardPaths')
HINT = re.compile('Try ' + chr(34) + '[^' + chr(34) + ']*' + chr(34))
# Folder choosers of the Setup dialog and the VST loader are closed on sight: they
# browse the whole file system or load code.
UNSAFE_DIALOGS = ('Choose LMMS working directory', 'Choose your GIG directory', 'Choose your SF2 directory',
                  'Choose your VST-plugin directory', 'Choose artwork-theme directory', 'Choose LADSPA plugin directory',
                  'Choose STK rawwave directory', 'Choose default SoundFont', 'Choose background artwork',
                  'Open VST-plugin')
TRACK_EXPORT_TITLE = 'Select directory for writing exported tracks'
CHOOSER_FORMAT = re.compile('[(][*][.]')
CHOOSER_BUTTONS = ('cancel', 'open', 'save', 'import', 'export', 'ok')
CHOOSER_KEYS = {'ctrl+a', 'escape', 'return', 'enter', 'up', 'down', 'home', 'end', 'tab', 'shift+tab', 'backspace',
                'delete'}
BROWSER_TABS = ('My Home', 'Root directory')
EXTERNAL_HOSTS = {'vestige', 'ladspaeffect', 'carlabase', 'carlarack', 'carlapatchbay'}


def basename(value):
    if (not isinstance(value, str) or Path(value).name != value or chr(92) in value or value in ('', '.', '..')
            or len(value) > 255 or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value)):
        raise ValueError('a file name must be a basename without path separators or control characters')
    return value


def chord(key):
    return '+'.join(part.strip() for part in str(key).casefold().replace('control', 'ctrl').split('+'))


read_regular = exchange.read_regular
write_regular = exchange.write_regular


def clean_text(text):
    '''Product text without progress bars, plug-in loader noise and private program paths.'''
    lines = []
    for line in text.replace(chr(13), chr(10)).split(chr(10)):
        if not line.strip() or line.lstrip().startswith('|') or NOISE.search(line):
            continue
        lines.append(HINT.sub('Try ' + chr(34) + 'lmms --help' + chr(34), line.rstrip()))
    return chr(10).join(lines)


CLI_ENDPOINT = {
    'invocation': 'The application start.sh is also run with the command line of the product: start.sh <action> '
                  '<project path> [options], from the solution folder, with the environment of the application (HOME and '
                  'TMPDIR are scratch folders of that call, DATA_DIR and PBP_FILES_DIR are the instance folders, DISPLAY '
                  'is the desktop). The exit status and the text on standard output and standard error form the reply; '
                  'dump and upgrade write their XML to standard output.',
    'actions': {
        'render': 'render <project> -o <output file> plus options: audio file of the whole project',
        'rendertracks': 'rendertracks <project> -o <output folder> plus options: one audio file per track (the folder is '
                        'created first)',
        'dump': 'dump <project>: the project XML of a compressed project file',
        'upgrade': 'upgrade <project> [output file]: the project upgraded to the current file format, as XML on '
                   'standard output or in the output file'},
    'options': {'format': '-f', 'samplerate': '-s', 'bitrate': '-b', 'float': '-a', 'interpolation': '-i',
                'oversampling': '-x', 'loop': '-l', 'stereo_mode': '-m'},
}
NOTES = [
    'cli runs the application own command line; no product behaviour is simulated.',
    'DOCUMENT_AREAS',
    'File dialogs (Open Project, Save Project, Import file, Select file for project-export, Open audio file and the like) '
    'are confined to the document areas: type an absolute document path into the File name field, confirm with Return '
    'or the Open/Save button; navigation controls of the dialog and the sidebar tabs My Home and Root directory are '
    'refused, and a typed path outside the document areas is refused wherever it is typed.',
    'The Export Tracks folder chooser accepts only the existing output document folder; enter that absolute folder '
    'in its Folder field and confirm. Directory navigation remains unavailable.',
    'The Paths page of the Setup dialog is not available; its folder choosers, the VST loader and plug-in host windows '
    'are closed and the request fails.',
    'Uploaded XML projects and compressed projects cannot select external plugin hosts or declare external entities. '
    'XML text uses Unicode or ASCII encodings; compressed project text is limited to 16,000,000 bytes.',
    'After a native save or export, list_files shows the new files (up to 16,000,000 bytes) with refs; download retrieves each once. settings '
    'returns the settings file of the running application.',
    'restart keeps uploaded inputs, outputs, projects and settings; reset discards them.',
]
LIMITS = {'upload_bytes': MAX_FILE, 'download_bytes': MAX_DOWNLOAD, 'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_SECONDS, 'cli_seconds': CLI_SECONDS,
          'screen': list(SCREEN), 'ready_seconds': None}


def specs():
    '''Help specs: the shared desktop operations plus the channels of this product.'''
    integer = lambda text: {'type': 'integer', 'description': text}
    ops = {
        'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
        'status': {'kind': 'lifecycle', 'fields': {},
                   'summary': 'Whether the application is running and ready (an accessible window).'},
        'reset': {'kind': 'lifecycle', 'fields': {},
                  'summary': 'Fresh instance: new desktop session and empty data, inputs, outputs, projects and settings; '
                             'the application is started again.'},
        'restart': {'kind': 'lifecycle', 'fields': {},
                    'summary': 'Relaunch the application with the same data, inputs, outputs, projects and settings.'},
        'cli': {'kind': 'http',
                'summary': 'Run one action of the application own command line (render, rendertracks, dump, upgrade) on '
                           'a project document: returns exit_code, the text output and, for dump and upgrade, the XML '
                           'in body; files it wrote are listed in downloads. It runs beside the desktop with scratch '
                           'settings, so it never changes the settings of the running application.',
                'fields': {
                    'action': {'type': 'string', 'required': True, 'enum': list(ACTIONS),
                               'description': 'The command line action.'},
                    'project': {'type': 'string', 'required': True,
                                'description': 'Project document: a name in the input or project area, or an absolute '
                                               'document path.'},
                    'output': {'type': 'string',
                               'description': 'render: output file; rendertracks: output folder; upgrade: optional output '
                                              'file. A name goes to the output area; an absolute document path is '
                                              'accepted.'},
                    'format': {'type': 'string', 'enum': list(FORMATS), 'description': 'Output format (-f).'},
                    'samplerate': integer('Output sample rate in Hz (-s).'),
                    'bitrate': integer('Output bit rate in KBit/s (-b).'),
                    'float': {'type': 'boolean', 'description': 'Use 32 bit float depth (-a).'},
                    'interpolation': {'type': 'string', 'enum': list(INTERPOLATIONS),
                                      'description': 'Interpolation method (-i).'},
                    'oversampling': integer('Oversampling (-x).'),
                    'loop': {'type': 'boolean', 'description': 'Render as a loop (-l).'},
                    'stereo_mode': {'type': 'string', 'enum': list(STEREO_MODES),
                                    'description': 'Stereo mode of MP3 export (-m): s, j or m.'}}},
        'upload': {'kind': 'files',
                   'summary': 'Place one document (audio, MIDI, Hydrogen song, project, preset or SoundFont) in the input '
                              'area, replacing a document of the same name.',
                   'fields': {
                       'filename': {'type': 'string', 'required': True,
                                    'description': 'Document name: a basename with one of the suffixes ' +
                                                   ' '.join(UPLOAD_SUFFIXES) + '.'},
                       'base64': {'type': 'string', 'required': True,
                                  'description': f'File bytes, base64 encoded, at most {MAX_FILE} bytes.'}}},
        'list_files': {'kind': 'files', 'fields': {},
                       'summary': 'Uploaded input names and the pending downloads: files the application or cli wrote '
                                  'into the output, project, template and preset folders since they were last listed, '
                                  'each with a ref.'},
        'download': {'kind': 'files', 'summary': 'Retrieve a pending download once, as body_base64.',
                     'fields': {'ref': {'type': 'string', 'required': True,
                                        'description': 'A ref from list_files or from a cli reply.'}}},
        'settings': {'kind': 'files', 'fields': {},
                     'summary': 'The settings file of the running application as text in body.'},
    }
    for op, spec in desktop.operations(SCREEN).items():
        ops[op] = spec
    return runtime.check_operations(ops)


OPERATIONS = specs()
GUI_GUARDED = {op for op, spec in OPERATIONS.items() if spec['kind'] == 'gui'} - {'zoom', 'wait', 'move'}


def examples(inputs):
    return [{'op': 'cli', 'action': 'render', 'project': 'song.mmp', 'output': 'song.wav', 'format': 'wav'},
            {'op': 'cli', 'action': 'dump', 'project': 'song.mmpz'},
            {'op': 'observe'},
            {'op': 'press', 'key': 'Control+o'},
            {'op': 'fill', 'target': {'role': 'text', 'name': 'File name:'}, 'value': f'{inputs}/song.mmp'},
            {'op': 'press', 'key': 'Return'},
            {'op': 'upload', 'filename': 'song.mmp', 'base64': '<base64 bytes>'},
            {'op': 'list_files'},
            {'op': 'settings'}]


class LmmsProduct(runtime.Product):
    '''start.sh with the instance layout plus the owned document areas.'''

    def prepare(self, fresh):
        super().prepare(fresh)
        exchange.prepare(self, AREAS)


class Broker:
    def __init__(self, config):
        self.config = config
        self.state = Path(config.state)
        self.log = runtime.BoundedLog(config.log_dir)
        directories = {**runtime.layout(config.state), 'PBP_FILES_DIR': self.state / 'files'}
        self.product = LmmsProduct(config, log=self.log, directories=directories)
        self.session = self.desk = None
        self.downloads, self.seen, self.serial, self.commands = {}, {}, 0, 0
        self.lock = threading.RLock()
        self.roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                      '/app/solution', '/reference']
        self.hide = runtime.redactor(*self.roots)

    # -- lifecycle ----------------------------------------------------------------------------------------------
    def area(self, name):
        return self.state / 'files' / name

    def start_session(self):
        if self.session is not None:
            self.session.close()
        if self.desk is not None:
            self.desk.close()
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, maximize=True, audio=True,
                                              log_dir=Path(self.config.log_dir) / 'desktop', ).start()
        self.desk = desktop.Desktop(self.session, settle=SETTLE, log_dir=Path(self.config.log_dir) / 'desktop', pointer_guard=self.guard_pointer)
        self.hide = runtime.redactor(*self.roots, str(self.session.root))

    def settle(self, seconds=6.0):
        '''After readiness: wait until the set of product windows stays the same for one second.'''
        end, last, since = time.monotonic() + seconds, None, time.monotonic()
        while time.monotonic() < end:
            now = sorted(self.titles())
            if now != last:
                last, since = now, time.monotonic()
            elif time.monotonic() - since >= 1.0:
                return
            time.sleep(0.3)

    def start(self, fresh):
        '''Start (fresh: a new desktop session and empty instance) and wait for an accessible window.'''
        self.product.stop()
        if fresh or self.session is None or not self.session.alive():
            self.start_session()
        if fresh:
            self.downloads.clear()
            self.seen.clear()
        self.product.extra = {key: value for key, value in self.session.env().items()
                              if key not in ('HOME', 'TMPDIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'DATA_DIR')}
        started = self.product.start(fresh)
        if started:
            runtime.wait_until(self.product, lambda: self.desk.ready(minimum=(200, 150)),
                               failure=f'the application showed no accessible window within '
                                       f'{self.config.ready_timeout:g} s')
            if self.product.ready:
                self.settle()
        return self.status()

    def status(self):
        return self.product.status()

    def close(self):
        self.product.stop()
        if self.desk is not None:
            self.desk.close()
        if self.session is not None:
            self.session.close()

    # -- documents ----------------------------------------------------------------------------------------------
    def inside(self, value):
        '''Whether an absolute path lies in the files folder (dot segments removed first).'''
        path = os.path.normpath(str(value))
        root = str(self.state / 'files')
        return path == root or path.startswith(root + os.sep)

    def document_path(self, value, *, where):
        """Normalize an absolute document path and validate every existing component."""
        text = str(value).strip()
        if (not text.startswith('/') or text.startswith('//') or '://' in text or '\\' in text
                or len(text) > 4000 or any(ord(c) < 32 for c in text)):
            raise ValueError(f'{where} accepts absolute document paths only')
        path = Path(os.path.normpath(text))
        root = Path(os.path.normpath(str(self.state / 'files')))
        if not path.is_relative_to(root):
            raise ValueError(f'{where} is confined to the document folder {root}')
        # Check the original path too: normalization must not hide a link before a parent step.
        original = Path(text)
        if any(part.is_symlink() for part in (original, *original.parents)):
            raise ValueError(f'{where} does not follow symbolic links')
        if original.resolve() != path or root.resolve() != root:
            raise ValueError(f'{where} does not resolve to the document folder')
        return path

    def resolve_document(self, value, where, search, default):
        '''A document name (looked up in the search areas) or an absolute document path.'''
        text = str(value)
        if '/' in text:
            return self.document_path(text, where=where)
        name = basename(text)
        for area in search:
            if (self.area(area) / name).exists():
                return self.document_path(str(self.area(area) / name), where=where)
        return self.document_path(str(self.area(default) / name), where=where)

    def make_directory(self, path):
        relative = Path(path).relative_to(self.state)
        with exchange.directory(self.state, relative, self.product.account()):
            pass

    def upload(self, data):
        filename = basename(data['filename'])
        if not filename.casefold().endswith(UPLOAD_SUFFIXES):
            raise ValueError('uploads are audio, MIDI, Hydrogen, project, preset or SoundFont documents (suffixes ' +
                             ' '.join(UPLOAD_SUFFIXES) + ')')
        payload = base64.b64decode(data['base64'], validate=True)
        if len(payload) > MAX_FILE:
            raise ValueError(f'upload exceeds {MAX_FILE} bytes')
        self.check_project(payload)
        write_regular(self.area('inputs') / filename, payload,
                      self.product.account() if self.product.switching() else None)
        return {'uploaded': True, 'filename': filename, 'size': len(payload)}

    @staticmethod
    def check_project(payload, resource_check=None):
        """Reject external plugin hosts in plain XML and Qt-compressed project documents."""
        data = payload
        if (len(data) >= 6 and data[4] & 0x0f == 8 and data[4] >> 4 <= 7
                and int.from_bytes(data[4:6], 'big') % 31 == 0):
            try:
                inflater = zlib.decompressobj()
                unpacked = inflater.decompress(data[4:], MAX_PROJECT + 1)
                if len(unpacked) > MAX_PROJECT or inflater.unconsumed_tail:
                    raise ValueError('the project exceeds the decompressed size limit')
                if inflater.eof:
                    if int.from_bytes(data[:4], 'big') > MAX_PROJECT:
                        raise ValueError('the project declares more than the decompressed size limit')
                    data = unpacked
            except zlib.error:
                pass  # The application reports malformed containers itself.
        if data.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')):
            encoding = 'utf-32'
        elif data.startswith((b'\xff\xfe', b'\xfe\xff')):
            encoding = 'utf-16'
        elif data.startswith(b'<\x00\x00\x00'):
            encoding = 'utf-32-le'
        elif data.startswith(b'\x00\x00\x00<'):
            encoding = 'utf-32-be'
        elif data.startswith(b'<\x00'):
            encoding = 'utf-16-le'
        elif data.startswith(b'\x00<'):
            encoding = 'utf-16-be'
        else:
            encoding = 'utf-8-sig'
        try:
            text = data.decode(encoding)
        except UnicodeError:
            text = data.decode('latin-1')
        declaration = re.match(r'\s*<\?xml\b[^?]*\?>', text, re.I)
        if declaration:
            encoding_name = re.search(r'''encoding\s*=\s*["']([^"']+)["']''', declaration.group(0), re.I)
            if encoding_name and encoding_name.group(1).lower().replace('_', '-') not in {
                'utf-8', 'utf8', 'utf-16', 'utf-16le', 'utf-16be', 'utf-32', 'utf-32le', 'utf-32be',
                'ascii', 'us-ascii',
            }:
                raise ValueError('XML projects must use a Unicode or ASCII encoding')
        # Project notes contain literal HTML in CDATA, including an inert HTML doctype.
        markup = re.sub(r'<!\[CDATA\[.*?\]\]>|<!--.*?-->|<\?.*?\?>', '', text, flags=re.S)
        if re.search(r'<!ENTITY|<!DOCTYPE\s+[^>]*(?:\[|\bSYSTEM\b|\bPUBLIC\b)', markup, re.I):
            raise ValueError('external declarations and entity definitions are not available in project documents')
        try:
            root = ElementTree.fromstring(text)
        except (ElementTree.ParseError, LookupError, ValueError):
            return
        for node in root.iter():
            tag = node.tag.rsplit('}', 1)[-1].casefold()
            name = node.get('name', '').casefold()
            if tag in EXTERNAL_HOSTS or tag in ('instrument', 'effect') and name in EXTERNAL_HOSTS:
                raise ValueError('external plugin hosts are not available in project documents')
            if resource_check is not None:
                for key, value in node.attrib.items():
                    if key.casefold() in ('src', 'file', 'filename', 'userwavefile', 'patch', 'path') and value:
                        resource_check(value)
                if tag in ('filename', 'path', 'drumkitpath', 'playbacktrackfilename') and node.text:
                    resource_check(node.text)


    def validate_resources(self, path, *, load_resources=True):
        """Validate a document at use; dump/upgrade only transform inert references."""
        try:
            payload = read_regular(path, MAX_DOWNLOAD)
        except FileNotFoundError:
            return
        def resource(value):
            text = str(value).strip()
            if not text:
                return
            if '\\' in text or '://' in text or text.startswith('~') or any(ord(c) < 32 for c in text):
                raise ValueError('project resources must be document paths or library-relative names')
            if text.startswith('data:/'):
                relative = text.removeprefix('data:/')
                if not relative or '..' in Path(relative).parts or ':' in relative:
                    raise ValueError('factory resource names must stay inside the factory library')
            elif text.startswith('/'):
                self.document_path(text, where='a project resource')
            elif ':' in text or '..' in Path(text).parts:
                raise ValueError('project resources must stay in the document and sample libraries')
            else:
                # LMMS checks the user sample directory before its read-only factory library.
                self.document_path(str(self.state / 'files' / 'samples' / text), where='a sample resource')
        self.check_project(payload, resource_check=resource if load_resources else None)

    def register(self, path):
        info = exchange.file_info(path, MAX_DOWNLOAD)
        self.seen[str(path)] = (info.st_mtime_ns, info.st_size)
        self.serial += 1
        ref = f'd{self.serial}'
        self.downloads[ref] = path
        return {'ref': ref, 'filename': path.name, 'size': info.st_size}

    def scan(self):
        """Register bounded regular documents found through directory descriptors."""
        for area in WATCHED:
            directory = self.area(area)
            for name, info in exchange.inventory(directory, DOWNLOAD_SUFFIXES, MAX_DOWNLOAD, recursive=True):
                path = directory / name
                if self.seen.get(str(path)) == (info.st_mtime_ns, info.st_size):
                    continue
                if info.st_size == 0:
                    continue
                try:
                    self.register(path)
                except (OSError, ValueError):
                    continue

    def list_files(self):
        self.scan()
        pending = []
        for ref, path in self.downloads.items():
            try:
                info = exchange.file_info(path, MAX_DOWNLOAD)
            except (OSError, ValueError):
                continue
            item = {'ref': ref, 'filename': path.name, 'size': info.st_size}
            pending.append(item)
        names = [name for name, _ in exchange.inventory(self.area('inputs'), UPLOAD_SUFFIXES, MAX_FILE)]
        return {'inputs': names, 'downloads': pending}

    def download(self, data):
        ref = data['ref']
        if ref not in self.downloads:
            raise ValueError('unknown download reference; use list_files')
        path = self.downloads.pop(ref)
        try:
            payload = read_regular(path, MAX_DOWNLOAD)
        except (OSError, ValueError):
            raise ValueError('the file is no longer available or exceeds the download limit') from None
        return {'filename': path.name, 'size': len(payload), 'body_base64': base64.b64encode(payload).decode()}

    def settings(self):
        try:
            payload = read_regular(self.state / 'home' / '.lmmsrc.xml', MAX_FILE)
        except (OSError, ValueError):
            raise ValueError('the application has not written its settings file yet') from None
        return {'filename': '.lmmsrc.xml', 'body': payload.decode('utf-8', 'replace')}

    # -- command line ---------------------------------------------------------------------------------------------
    def cli(self, data):
        action = data['action']
        project = self.resolve_document(data['project'], 'the project', ('inputs', 'projects'), 'inputs')
        if not project.is_dir():
            self.validate_resources(project, load_resources=action in ('render', 'rendertracks'))
        if action not in ('render', 'rendertracks') and any(key in data for key in RENDER_ONLY):
            raise ValueError('format, samplerate, bitrate, float, interpolation, oversampling, loop and stereo_mode '
                             'apply to render and rendertracks only')
        for key in ('samplerate', 'bitrate', 'oversampling'):
            if key in data and abs(data[key]) > 10_000_000:
                raise ValueError(f'{key} is out of range')
        output = data.get('output')
        target = None
        if action in ('render', 'rendertracks'):
            if output is None:
                raise ValueError(f'{action} needs output: a name or an absolute document path')
            target = self.resolve_document(output, 'the output', ('outputs',), 'outputs')
            if action == 'rendertracks':
                self.make_directory(target)
        elif action == 'upgrade' and output is not None:
            target = self.resolve_document(output, 'the output', ('outputs',), 'outputs')
        elif output is not None:
            raise ValueError('dump writes its XML to the reply body')
        argv = [action, str(project)]
        for key, flag in (('format', '-f'), ('samplerate', '-s'), ('bitrate', '-b'), ('interpolation', '-i'),
                          ('oversampling', '-x'), ('stereo_mode', '-m')):
            if key in data:
                argv += [flag, str(data[key])]
        for key, flag in (('float', '-a'), ('loop', '-l')):
            if data.get(key):
                argv.append(flag)
        if target is not None:
            argv += ['-o', str(target)] if action != 'upgrade' else [str(target)]
        self.commands += 1
        self.make_directory(self.state / 'cli')
        scratch = self.state / 'cli' / str(self.commands)
        runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
        for path in (scratch, scratch / 'tmp'):
            self.make_directory(path)
        env = self.product.environment()
        env.update(HOME=str(scratch), TMPDIR=str(scratch / 'tmp'))
        kwargs = {}
        if self.product.switching():
            account = self.product.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        solution = Path(self.config.solution)
        try:
            proc = subprocess.Popen([str(solution / 'start.sh'), *argv], cwd=str(solution), env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True, **kwargs)
        except OSError as exc:
            runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
            raise ValueError(f'start.sh could not be executed ({type(exc).__name__})') from None
        try:
            try:
                out, err = proc.communicate(timeout=CLI_SECONDS)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                raise ValueError(f'the command did not finish within {CLI_SECONDS} s') from None
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            runtime.remove_entry(self.state, str(scratch.relative_to(self.state)), missing_ok=True)
        if len(out) > MAX_FILE:
            raise ValueError('the command output exceeds the size limit')
        code = proc.returncode if proc.returncode >= 0 else 128 - proc.returncode
        result = {'exit_code': code}
        if action in ('dump', 'upgrade') and target is None:
            result['body'] = out.decode('utf-8', 'replace')
            result['output'] = clean_text(err.decode('utf-8', 'replace'))[:6000]
        else:
            result['output'] = clean_text(err.decode('utf-8', 'replace') + chr(10) + out.decode('utf-8', 'replace'))[:6000]
        files = []
        if target is not None:
            if action == 'rendertracks':
                candidates = [target / name for name, _ in
                              exchange.inventory(target, DOWNLOAD_SUFFIXES, MAX_DOWNLOAD)]
            else:
                candidates = [target]
            for path in candidates:
                try:
                    info = exchange.file_info(path, MAX_DOWNLOAD)
                except (OSError, ValueError):
                    continue
                if stat.S_ISREG(info.st_mode) and 0 < info.st_size <= MAX_DOWNLOAD and path.suffix.casefold() in DOWNLOAD_SUFFIXES:
                    files.append(self.register(path))
        result['downloads'] = files
        return result

    # -- desktop ------------------------------------------------------------------------------------------------
    def titles(self):
        return [str(w.get('title', '')) for w in self.desk.windows()]

    @staticmethod
    def filename_field(node):
        return (node.get('role') in ('text', 'entry') and 'editable' in node.get('states', [])
                and str(node.get('name', '')).rstrip(':').casefold() in ('file name', 'folder', 'directory'))

    def chooser(self, nodes):
        '''(dialog, its nodes) of an open Qt file dialog, found by its Look in label and File name field.'''
        for top in nodes:
            if top.get('role') != 'dialog':
                continue
            members = [n for n in nodes if n.get('window') == top['ref']]
            if (any(n.get('role') == 'label' and str(n.get('name', '')).rstrip(':').casefold() == 'look in'
                    for n in members) and any(self.filename_field(n) for n in members)):
                return top, members
        return None

    def open_chooser(self):
        if len(self.desk.windows()) < 2:
            return None
        return self.chooser(self.desk.inspect().get('nodes', []))

    def dialog_folder(self, members):
        combos = [n for n in members if n.get('role') == 'combo box' and not CHOOSER_FORMAT.search(str(n.get('name', '')))]
        if not combos:
            raise ValueError('the file dialog shows no folder')
        return str(min(combos, key=lambda n: n['bounds'][1]).get('name', ''))

    def dialog_control(self, top, target):
        '''The node a target designates; it must be inside the open file dialog.'''
        if target is None:
            raise ValueError('coordinate input is not available in a file dialog; target its controls')
        record = self.desk.resolve(target)
        chain = record.get('chain', [])
        if not chain or chain[-1][0] != 'dialog' or chain[-1][1] != top.get('name'):
            raise ValueError('the control is outside the active file dialog')
        return record

    def confirm(self, members, top=None):
        '''Check the path typed in the File name field before a dialog is confirmed.'''
        field = next((n for n in members if self.filename_field(n)), None)
        typed = str(field.get('text') or '').strip() if field else ''
        if top and str(top.get('name', '')).startswith(TRACK_EXPORT_TITLE):
            selected = typed if typed.startswith('/') else os.path.join(self.dialog_folder(members), typed)
            chosen = self.document_path(selected, where='the track export folder')
            if chosen != self.area('outputs') or not chosen.is_dir():
                raise ValueError('Export Tracks accepts only the output document folder')
            return
        if not typed:
            return
        path = self.document_path(typed if '/' in typed else os.path.join(self.dialog_folder(members), typed),
                                  where='a file dialog')
        if path.suffix.casefold() in ('.mmp', '.mmpz', '.mpt', '.xpf', '.h2song'):
            self.validate_resources(path)

    def in_chooser(self, op, request, top, members):
        '''Rules of an open file dialog: only its File name field, file type list and buttons can be used.'''
        target = request.get('target')
        if op in ('type', 'fill'):
            if op == 'fill' or target is not None:
                if target is None or not self.filename_field(self.dialog_control(top, target)):
                    raise ValueError('text in a file dialog goes into its File name field')
            if op == 'type' and '/' in str(request.get('value', '')):
                # A dialog pre-fills a name and selects only its stem: a typed path replaces the whole field.
                self.desk.act({'op': 'press', 'key': 'Control+a', **({'target': target} if target is not None else {})})
            return
        if op in ('focus_window', 'maximize'):
            return
        if op == 'press':
            key = chord(request.get('key', ''))
            if key not in CHOOSER_KEYS or target is not None:
                raise ValueError('keys in a file dialog are limited to ' + ', '.join(sorted(CHOOSER_KEYS)))
            if key in ('return', 'enter'):
                self.confirm(members, top)
            elif key in ('backspace', 'delete'):
                field = next((n for n in members if self.filename_field(n)), None)
                if field is None or 'focused' not in field.get('states', []):
                    raise ValueError('delete keys act only inside the File name field of a file dialog')
            return
        if op in ('click', 'activate'):
            node = self.dialog_control(top, target)
            role, label = node.get('role'), str(node.get('name', ''))
            if role in ('push button', 'button'):
                cleaned = label.rstrip('.' + chr(8230)).casefold()
                if cleaned not in CHOOSER_BUTTONS:
                    raise ValueError('file dialog navigation is not available')
                if cleaned != 'cancel':
                    self.confirm(members, top)
            elif role in ('combo box', 'list item'):
                if not CHOOSER_FORMAT.search(label):
                    raise ValueError('file dialog navigation is not available')
            elif not self.filename_field(node):
                raise ValueError('file dialog navigation is not available')
            return
        raise ValueError('file dialog navigation is not available')

    def wmctrl(self, *args):
        return subprocess.run(['wmctrl', *args], env={**os.environ, **self.session.env()}, capture_output=True, timeout=10)

    def helper_windows(self):
        '''Windows of plug-in host processes (their own toolkit, outside the accessibility tree).'''
        found = []
        for line in self.wmctrl('-lGp').stdout.decode(errors='replace').splitlines():
            fields = line.split(None, 8)
            if len(fields) < 8:
                continue
            try:
                pid = int(fields[2])
                comm = Path('/proc', str(pid), 'comm').read_text().strip() if pid > 0 else ''
            except (ValueError, OSError):
                continue
            if comm.startswith('Remote'):
                found.append(fields[0])
        return found

    def unsafe_titles(self):
        return [t for t in self.titles() if any(label.casefold() in t.casefold() for label in UNSAFE_DIALOGS)]

    def close_unsafe(self):
        hosted = self.helper_windows()
        for window in hosted:
            self.wmctrl('-i', '-c', window)
        titles = self.unsafe_titles()
        if titles:
            self.desk.act({'op': 'press', 'key': 'Escape'})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                left = self.unsafe_titles()
                if not left:
                    break
                for title in left:
                    self.wmctrl('-F', '-c', title)
                time.sleep(0.3)
        if hosted or titles:
            raise ValueError('plug-in hosts, folder choosers and code-loading dialogs are outside reference exploration')

    def browser_tabs(self, nodes):
        '''The sidebar tabs that list the whole file system are switched back to the first tab.'''
        for node in nodes:
            if node.get('role') == 'check box' and node.get('name') in BROWSER_TABS and 'checked' in node.get('states', []):
                self.desk.act({'op': 'click', 'target': {'role': 'check box', 'name': 'Instrument Plugins'}})
                raise ValueError('the sidebar tabs My Home and Root directory are not available')

    def keep_inside(self, members):
        '''A file dialog that started outside the document areas (for example beside a factory project) is moved in.'''
        if self.inside(self.dialog_folder(members)):
            return
        field = next(n for n in members if self.filename_field(n))
        selector = {'role': 'text', 'name': field.get('name', '')}
        self.desk.act({'op': 'fill', 'target': selector, 'value': str(self.area('projects'))})
        self.desk.act({'op': 'press', 'key': 'Return'})
        again = self.chooser(self.desk.inspect().get('nodes', []))
        if again is None or not self.inside(self.dialog_folder(again[1])):
            self.desk.act({'op': 'press', 'key': 'Escape'})
            raise ValueError('file dialogs are confined to the document areas')
        self.desk.act({'op': 'fill', 'target': selector, 'value': ''})

    def setup_paths(self, nodes):
        '''The Paths page of the Setup dialog (path fields and folder choosers) is switched back to the first page.'''
        for top in nodes:
            if top.get('role') != 'dialog' or top.get('name') != 'Setup LMMS':
                continue
            members = [n for n in nodes if n.get('window') == top['ref']]
            if any(n.get('role') == 'label' and n.get('name') in ('Paths', 'Directories') for n in members):
                tabs = sorted((n for n in members if n.get('role') == 'check box' and n['bounds'][2] == 64),
                              key=lambda n: n['bounds'][1])
                if tabs:
                    x, y, w, h = tabs[0]['bounds']
                    self.desk.act({'op': 'click', 'x': x + w // 2, 'y': y + h // 2})
                raise ValueError('the Paths page of the Setup dialog is not available')

    def after_gui(self):
        self.close_unsafe()
        nodes = self.desk.inspect().get('nodes', [])
        self.browser_tabs(nodes)
        self.setup_paths(nodes)
        found = self.chooser(nodes)
        if found is not None:
            if str(found[0].get('name', '')).startswith(TRACK_EXPORT_TITLE) and not self.inside(self.dialog_folder(found[1])):
                # A directory dialog may accept Return immediately. Only the
                # existing output area is selected during confinement.
                field = next(n for n in found[1] if self.filename_field(n))
                self.desk.act({'op': 'fill', 'target': {'ref': field['ref']}, 'value': str(self.area('outputs'))})
                ready = self.chooser(self.desk.inspect().get('nodes', []))
                if ready is None:
                    raise ValueError('the track export folder chooser is unavailable')
                self.confirm(ready[1], ready[0])
                self.desk.act({'op': 'press', 'key': 'Return'})
                return
            self.keep_inside(found[1])

    def guard_pointer(self, event):
        """Constrain pointer actions before direct and compound inputs reach the desktop."""
        request = event['pointer']
        op = request['op']
        nodes = self.desk.inspect().get('nodes', [])
        if self.unsafe_titles() or self.helper_windows():
            node = self.desk.resolve(request['target']) if request.get('target') is not None else None
            if op in ('click', 'activate') and node and str(node.get('name', '')).casefold() in ('cancel', 'no', 'close'):
                return
            raise ValueError('close the unavailable dialog before continuing')
        found = self.chooser(nodes)
        if found is not None:
            if op != 'move':
                self.in_chooser(op, request, *found)
            return
        for top in nodes:
            if top.get('role') == 'dialog' and top.get('name') == 'Setup LMMS':
                members = [n for n in nodes if n.get('window') == top['ref']]
                if any(n.get('role') == 'label' and n.get('name') in ('Paths', 'Directories') for n in members):
                    # The broker's repair can select the first non-path page. No other pointer input is permitted.
                    tabs = sorted((n for n in members if n.get('role') == 'check box' and n['bounds'][2] == 64),
                                  key=lambda n: n['bounds'][1])
                    if op == 'click' and tabs:
                        x, y, w, h = tabs[0]['bounds']
                        if desktop.bounds_contain((x, y, w, h), request.get('x', -1), request.get('y', -1)):
                            return
                    raise ValueError('the Paths page of the Setup dialog is not available')

    def gui(self, op, data):
        request = {key: value for key, value in data.items() if key != 'op'}
        self.after_gui()
        if op in ('type', 'fill'):
            # Typed text is passed through unchanged; a file system path in it must stay in the document areas,
            # wherever it is typed (a file dialog or one of the product own path fields).
            value = str(request.get('value', ''))
            if chr(92) in value:
                raise ValueError('typed text does not contain backslashes; document paths use /')
            if '/' in value:
                self.document_path(value, where='a typed document path')
        if op in GUI_GUARDED:
            found = self.open_chooser()
            if found is not None:
                self.in_chooser(op, request, *found)
        result = self.desk.act({'op': op, **request})
        if op in GUI_GUARDED:
            self.after_gui()
        return result

    # -- dispatch -----------------------------------------------------------------------------------------------
    def notes(self):
        areas = ', '.join(f'{area} {self.area(area)}' for area in AREAS)
        return [f'Document areas: {areas}. Uploads arrive in the input area; the application reads and writes them as '
                'ordinary files (its configured document workspace is the files folder that holds them), and files it leaves in '
                'the output, project, template and preset folders can be downloaded.'
                if note == 'DOCUMENT_AREAS' else note for note in NOTES]

    def help(self):
        limits = dict(LIMITS, ready_seconds=self.config.ready_timeout)
        return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=limits, notes=self.notes(),
                                     examples=examples(self.area('inputs')), cli_endpoint=CLI_ENDPOINT)

    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return self.help()
        if op == 'status':
            return self.status()
        if op == 'reset':
            return self.start(True)
        if op == 'restart':
            return self.start(False)
        if op == 'cli':
            return self.cli(data)
        if op == 'upload':
            return self.upload(data)
        if op == 'list_files':
            return self.list_files()
        if op == 'download':
            return self.download(data)
        if op == 'settings':
            return self.settings()
        if op in ('observe', 'windows', 'screenshot'):
            self.after_gui()
        if op == 'observe':
            return self.desk.observe(**{k: v for k, v in data.items() if k != 'op'})
        if op == 'windows':
            return {'windows': self.desk.windows()}
        if op == 'screenshot':
            return self.desk.screenshot(**{k: v for k, v in data.items() if k != 'op'})
        return self.gui(op, data)

    def redact(self, text):
        '''Text with private filesystem locations replaced; document paths stay readable (they are public).'''
        text = str(text)
        if '/' not in text:
            return text
        return TOKEN.sub(lambda m: m.group(0) if self.inside(m.group(0)) else self.hide(m.group(0)), text)

    def clean(self, value):
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, list):
            return [self.clean(item) for item in value]
        if isinstance(value, dict):
            return {key: (item if key in ('png_base64', 'body_base64') else self.clean(item))
                    for key, item in value.items()}
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
        server.audit.record(op, code, time.monotonic() - started)
        self.reply(code, value)


def main(argv=None):
    config = runtime.options(state='/reference/state', log_dir='/reference', work='/reference/work',
                             ready_timeout=30.0).parse_args(argv)
    Path(config.work).mkdir(parents=True, exist_ok=True)
    # SIGTERM ends the process through the finally
    # block, which stops the product and closes the desktop session.
    runtime.exit_on_sigterm()
    broker = Broker(config)
    server = None
    try:
        # A product that fails to start is reported by status; the runtime keeps serving.
        broker.start(True)
        server = Server(runtime.listen(config.socket, config.socket_mode), broker)
        server.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        server.serve_forever()
    finally:
        broker.close()
        if server is not None:
            server.server_close()


if __name__ == '__main__':
    main()
