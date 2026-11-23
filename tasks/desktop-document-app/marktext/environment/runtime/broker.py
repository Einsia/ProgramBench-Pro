#!/usr/bin/env python3
"""MarkText desktop runtime: a private X11 session, document exchange,
clipboard and application lifecycle through a bounded local interface.
The same operations serve the reference and your application.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socketserver
import stat
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import document_exchange as file_exchange
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'MarkText'
SCREEN = (1280, 900)
MAX_UPLOAD = 20 * 1024 * 1024
MAX_DOWNLOAD = 50 * 1024 * 1024
MAX_REQUEST = (MAX_UPLOAD * 4 + 2) // 3 + 65_536
MAX_FILES = 256
CLIPBOARD_TEXT = 1_000_000
CLIPBOARD_IMAGE = 16 * 1024 * 1024
RPC_TIMEOUT = 150
READ_ONLY = 'read-only'
# Uploaded files carry one fixed modification time (2024-01-01 00:00 UTC) so dialogs list them the same way.
UPLOAD_TIME = 1704067200
OPEN_TIMEOUT = 60
# Native file dialogs the application opens (GTK titles under an English locale); while one is the active window
# the broker keeps typed paths inside the exchange folders and refuses pointer input outside its confirm band.
DIALOG_TITLES = ('Save File', 'Open File', 'Open Files', 'Select Folder', 'Save', 'Open', 'Export')
PASTE_KEYS = {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
EDIT_ROLES = {'text', 'entry', 'password text', 'spin button', 'terminal'}
# Keys accepted while a native file dialog is the active window. Tab (and the file-list page keys) are left out so
# keyboard focus stays in the path/name entry and the file list and places sidebar cannot be reached; the only way
# to act is a typed exchange path plus Return or a confirm button in the bottom bar.
DIALOG_KEYS = {'ctrl+l', 'ctrl+a', 'ctrl+c', 'ctrl+x', 'ctrl+v', 'ctrl+shift+v', 'shift+Insert', 'Return', 'Escape',
               'Left', 'Right', 'Home', 'End', 'BackSpace', 'Delete', 'space'}
# Downloads expose the documents the application writes.
TEXT_SUFFIXES = {'.md', '.markdown', '.mdown', '.mkd', '.mkdn', '.mdwn', '.mdtxt', '.mdtext', '.text', '.txt',
                 '.html', '.htm', '.opml', '.svg', '.css'}
BINARY_MAGIC = (b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF8', b'PK\x03\x04', b'RIFF')

AREA = {'type': 'string', 'enum': ['inbox', 'outbox'], 'description': 'Exchange folder; default outbox.'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the application process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Start over: a new desktop session, empty inbox and outbox, and the application with an '
                         'empty data directory (its initial state).'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Start the application again with the same data directory, desktop session and exchange '
                           'folders (for example after quitting it through its own controls).'},
    **desktop.operations(SCREEN),
    'open': {'kind': 'files', 'summary': 'Open inbox or outbox documents in the running application by launching it '
             'again with their paths (the running instance receives them). Give exchange paths; a fresh instance '
             'when none is running.',
             'fields': {'paths': {'type': 'array', 'items': {'type': 'string'}, 'required': True,
                                  'description': 'One or more absolute paths inside the inbox or outbox.'},
                        'new_window': {'type': 'boolean', 'description': 'Open in a new window; default false.'}}},
    'list_files': {'kind': 'files', 'summary': 'Files in the inbox or the outbox (name, size, path, read_only); files '
                   'of the area\'s read-only subfolder are flagged read_only.',
                   'fields': {'area': AREA}},
    'upload': {'kind': 'files', 'summary': 'Store one file in the inbox (default) or the outbox; read_only places it '
               'in the area\'s read-only subfolder, which the application cannot write to. Uploaded files get the '
               'modification time 2024-01-01 00:00 UTC.',
               'fields': {'filename': {'type': 'string', 'required': True,
                                       'description': 'Base name (no folders, not hidden), at most 240 bytes.'},
                          'base64': {'type': 'string', 'required': True,
                                     'description': f'File bytes, base64 encoded; at most {MAX_UPLOAD} bytes, '
                                                    'empty files allowed.'},
                          'area': dict(AREA, description='Exchange folder; default inbox.'),
                          'read_only': {'type': 'boolean', 'description': 'Store it in the read-only subfolder; '
                                                                          'default false.'}}},
    'download': {'kind': 'files', 'summary': 'Retrieve one document (Markdown, text, HTML, PDF, image or OPML) from '
                 'the outbox (or the inbox) as body_base64.',
                 'fields': {'filename': {'type': 'string', 'required': True, 'description': 'Base name of the file.'},
                            'area': AREA,
                            'read_only': {'type': 'boolean', 'description': 'Read it from the read-only subfolder; '
                                                                           'default false.'}}},
    'clipboard_text': {'kind': 'observe', 'summary': 'The plain text on the desktop clipboard (UTF-8, at most '
                       f'{CLIPBOARD_TEXT} bytes).', 'fields': {}},
    'clipboard_html': {'kind': 'observe', 'summary': 'The text/html flavor of the desktop clipboard as html (UTF-8), '
                       'empty when none is set.', 'fields': {}},
    'clipboard_image': {'kind': 'observe', 'summary': 'The PNG image on the desktop clipboard as png_base64.',
                        'fields': {}},
})
LIMITS = {'upload_bytes': MAX_UPLOAD, 'download_bytes': MAX_DOWNLOAD, 'files_per_area': MAX_FILES,
          'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_TIMEOUT, 'screen': list(SCREEN)}


def examples(inbox):
    return [{'op': 'observe'}, {'op': 'screenshot'},
            {'op': 'upload', 'filename': 'note.md', 'base64': base64.b64encode(b'# Title\n').decode()},
            {'op': 'open', 'paths': [f'{inbox}/note.md']}, {'op': 'press', 'key': 'Control+S'},
            {'op': 'click', 'target': {'role': 'push button', 'name': 'Application Menu'}},
            {'op': 'type', 'value': 'Hello'}, {'op': 'clipboard_text'},
            {'op': 'list_files', 'area': 'outbox'}, {'op': 'download', 'filename': 'export.html'}]


class Refused(ValueError):
    """The request is outside the interface boundary."""


def safe_name(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 240:
        raise ValueError('filename must be a non-empty base name of at most 240 bytes')
    if Path(value).name != value or value in ('.', '..') or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('filename must be a base name')
    if value.startswith('.'):
        raise ValueError('hidden file names are not accepted')
    return value


def open_directory(path, parent=None):
    return file_exchange.open_directory(path, parent)


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.files = Path(config.state).resolve().parent / 'files'
        self.areas = {'inbox': self.files / 'inbox', 'outbox': self.files / 'outbox'}
        self.log = runtime.BoundedLog(config.log_dir)
        self.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        self.product = runtime.Product(config, log=self.log)
        self.account = desktop.account(config.user)
        self.switching = os.geteuid() == 0 and self.account.pw_uid != 0
        self.session = self.ui = None
        roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                 '/app/solution', '/opt', '/proc', '/sys', '/root', '/etc', '/home', '/usr', '/var', '/srv', '/tests',
                 '/logs', '/model']
        self.private = sorted({str(Path(p).resolve()) for p in roots if p and str(p) != '/'}, key=len, reverse=True)

    # Paths ----------------------------------------------------------------------------------------------------
    def inside(self, value):
        """Check normalized and resolved exchange paths; reject symbolic-link components."""
        path = os.path.normpath(str(value))
        roots = tuple(str(root) for root in self.areas.values())
        if not os.path.isabs(path) or not any(path == root or path.startswith(root + os.sep) for root in roots):
            return False
        resolved = os.path.realpath(str(value))
        if not any(resolved == root or resolved.startswith(root + os.sep) for root in roots):
            return False
        original = Path(value)
        return not any(part.is_symlink() for part in (original, *original.parents))

    def private_text(self, value):
        text = str(value)
        if '/' not in text:
            return text, False
        changed = False

        def replace(match):
            nonlocal changed
            path = match.group(0)
            if self.inside(path):
                return path
            for root in self.private:
                if path == root or path.startswith(root + '/'):
                    changed = True
                    return '[private]'
            return path
        return re.sub(r'/[^\s\'"<>()\[\]{},;]*', replace, text), changed

    def detail(self, exc):
        return self.private_text(str(exc))[0][:600]

    def chown(self, path=None, fd=None):
        if not self.switching:
            return
        if fd is not None:
            os.fchown(fd, self.account.pw_uid, self.account.pw_gid)
        else:
            os.chown(path, self.account.pw_uid, self.account.pw_gid, follow_symlinks=False)

    # Lifecycle ----------------------------------------------------------------------------------------------------
    def prepare_areas(self, clear):
        file_exchange.prepare(self, clear)

    def start_session(self):
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, log_dir=self.config.log_dir).start()
        self.ui = desktop.Desktop(self.session, log_dir=self.config.log_dir,
                                  pointer_guard=self.guard_pointer)
        self.product.extra = dict(self.session.env(), PBP_INBOX=str(self.areas['inbox']),
                                  PBP_OUTBOX=str(self.areas['outbox']))

    def stop_session(self):
        for item in (self.ui, self.session):
            try:
                if item is not None:
                    item.close()
            except Exception as exc:
                self.log.note(f'desktop teardown: {type(exc).__name__}: {exc}')
        self.ui = self.session = None

    def launch(self, fresh):
        if self.product.start(fresh=fresh):
            runtime.wait_until(self.product, self.ui.ready, failure='no application window was reachable through '
                               f'AT-SPI within {self.config.ready_timeout:g} s')
        status = self.product.status()
        self.log.note('status: ' + json.dumps(status))
        return status

    def start(self):
        with self.lock:
            self.prepare_areas(clear=True)
            self.start_session()
            return self.launch(fresh=True)

    def reset(self):
        with self.lock:
            self.product.stop()
            self.stop_session()
            self.prepare_areas(clear=True)
            self.start_session()
            return self.launch(fresh=True)

    def restart(self):
        with self.lock:
            self.product.stop()
            if self.session is None or not self.session.alive():
                self.stop_session()
                self.start_session()
            return self.launch(fresh=False)

    def close(self):
        self.product.stop()
        self.stop_session()

    # Exchange -------------------------------------------------------------------------------------------------
    def area(self, data, default):
        name = data.get('area', default)
        return name, self.areas[name]

    def list_files(self, data):
        area, _folder = self.area(data, 'outbox')
        return file_exchange.flat_listing(self, area, limit=MAX_FILES)

    def upload(self, data):
        name = safe_name(data['filename'])
        try:
            content = base64.b64decode(data['base64'], validate=True)
        except Exception:
            raise ValueError('base64 is invalid') from None
        if len(content) > MAX_UPLOAD:
            raise ValueError(f'uploaded files are limited to {MAX_UPLOAD} bytes')
        area, folder = self.area(data, 'inbox')
        read_only = bool(data.get('read_only'))
        listed = self.list_files({'area': area})['files']
        if len(listed) >= MAX_FILES and not any(f['name'] == name and f['read_only'] == read_only for f in listed):
            raise ValueError(f'the {area} holds at most {MAX_FILES} files; use reset to empty the exchange folders')
        file_exchange.write(self, area, name, content, read_only=read_only, timestamp=UPLOAD_TIME)
        path = folder / READ_ONLY / name if read_only else folder / name
        return {'area': area, 'name': name, 'path': str(path), 'size': len(content), 'read_only': read_only,
                'sha256': hashlib.sha256(content).hexdigest()}

    def download(self, data):
        name = safe_name(data['filename'])
        area, folder = self.area(data, 'outbox')
        content = file_exchange.read(self, area, name, limit=MAX_DOWNLOAD, read_only=bool(data.get('read_only')))
        if len(content) > MAX_DOWNLOAD:
            raise ValueError(f'downloads are limited to {MAX_DOWNLOAD} bytes')
        suffix = Path(name).suffix.lower()
        text_ok = suffix in TEXT_SUFFIXES
        binary_ok = any(content.startswith(magic) for magic in BINARY_MAGIC)
        if not content:
            pass
        elif not text_ok and not binary_ok:
            # Allow UTF-8 text even without a known suffix (Markdown has no magic), but never arbitrary binaries.
            try:
                content.decode('utf-8')
            except UnicodeDecodeError:
                raise ValueError('downloads expose documents (Markdown, text, HTML, PDF, images, OPML) only') from None
        return {'area': area, 'name': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                'body_base64': base64.b64encode(content).decode()}

    # Open ---------------------------------------------------------------------------------------------------------
    def open(self, data):
        paths = data.get('paths')
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise ValueError('paths must be a non-empty list of absolute exchange paths')
        if len(paths) > 32:
            raise ValueError('open accepts at most 32 paths at once')
        resolved = []
        for value in paths:
            if '/' not in value or not value.startswith('/') or '..' in Path(value).parts or not self.inside(value):
                raise Refused('open is confined to the inbox and outbox: give absolute paths under '
                              f'{self.areas["inbox"]} or {self.areas["outbox"]}')
            resolved.append(os.path.normpath(value))
        script = Path(self.config.solution) / 'start.sh'
        if not script.is_file():
            raise ValueError('the application has no start.sh to open files with')
        args = [str(script)]
        if data.get('new_window'):
            args.append('--new-window')
        args += resolved
        env = self.product.environment()
        kwargs = {}
        if self.switching:
            kwargs = dict(user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=[])
        try:
            done = subprocess.run(args, cwd=str(self.config.solution), env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=OPEN_TIMEOUT,
                                  start_new_session=True, **kwargs)
        except subprocess.TimeoutExpired:
            raise ValueError('opening the documents did not finish in time') from None
        self.log.note(f'open {resolved}: exit {done.returncode}')
        return {'opened': resolved, 'exit_code': done.returncode}

    # Clipboard ----------------------------------------------------------------------------------------------------
    def clipboard_text(self):
        raw = self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the clipboard text is not UTF-8') from None
        return {'text': text, 'characters': len(text)}

    def clipboard_html(self):
        try:
            raw = self.ui.clipboard('text/html', CLIPBOARD_TEXT)
        except desktop.DesktopError:
            return {'html': '', 'characters': 0}
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('utf-16', 'replace') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8', 'replace')
        return {'html': text, 'characters': len(text)}

    def clipboard_image(self):
        raw = self.ui.clipboard('image/png', CLIPBOARD_IMAGE)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) < 24:
            raise ValueError('the clipboard holds no PNG image')
        width, height = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
        return {'png_base64': base64.b64encode(raw).decode(), 'mime_type': 'image/png', 'width': width, 'height': height}

    # Observations -------------------------------------------------------------------------------------------------
    def clean(self, node):
        changed = False
        for key in ('name', 'text', 'description'):
            if node.get(key):
                value, hit = self.private_text(node[key])
                if hit:
                    node[key], changed = value, True
        return changed

    def public(self, observation, tree):
        hidden, boxes = set(), []
        for node in observation.get('nodes', []):
            secret = self.clean(node) or (tree and node.get('parent') in hidden)
            if secret:
                hidden.add(node['ref'])
                for key in ('name', 'text', 'description'):
                    if node.get(key) and not node[key].startswith('[private'):
                        node[key] = '[private]'
                boxes.append(node.get('visible') or node['bounds'])
        for window in observation.get('windows', []):
            window['title'] = self.private_text(window.get('title', ''))[0]
        return observation, boxes

    def screenshot(self, data):
        _, boxes = self.public(self.ui.inspect(), True)
        shot = self.ui.screenshot(data.get('region'))
        if boxes:
            from PIL import Image, ImageDraw
            picture = Image.open(io.BytesIO(base64.b64decode(shot['png_base64']))).convert('RGB')
            draw = ImageDraw.Draw(picture)
            x0, y0 = (shot['region'][:2] if shot.get('region') else (0, 0))
            factor = shot.get('factor', 1)
            for x, y, w, h in boxes:
                if w > 0 and h > 0:
                    draw.rectangle(((x - x0) * factor, (y - y0) * factor, (x + w - x0) * factor, (y + h - y0) * factor),
                                   fill=(210, 210, 210))
            stream = io.BytesIO()
            picture.save(stream, format='PNG')
            shot['png_base64'] = base64.b64encode(stream.getvalue()).decode()
            shot['redacted_regions'] = len(boxes)
        return shot

    # Guards ---------------------------------------------------------------------------------------------------
    def check_paths(self, value):
        """Text typed into a file dialog: base names, or absolute paths inside the exchange folders."""
        if not isinstance(value, str) or not value.strip():
            return
        if '://' in value or value.lstrip().startswith('~'):
            raise Refused('file dialogs accept absolute inbox or outbox paths only (no URLs or home folders)')
        if value.strip() in ('.', '..'):
            raise Refused('file dialogs require a document name or an absolute exchange path')
        if '/' not in value:
            return
        try:
            parts = shlex.split(value) if '"' in value else [value]
        except ValueError:
            raise Refused('the file dialog text is not a valid path list') from None
        for part in parts:
            if '/' in part and (not part.startswith('/') or '..' in Path(part).parts or not self.inside(part)):
                raise Refused('file dialogs are confined to the inbox and outbox: use an absolute path under '
                              f'{self.areas["inbox"]} or {self.areas["outbox"]}')

    def native_dialog(self):
        """The active top-level window when it is one of the application's native file dialogs (which are not on the
        accessibility bus), as [x, y, w, h]; otherwise None."""
        try:
            windows = self.ui.windows()
        except desktop.DesktopError:
            return None
        active = next((w for w in windows if w.get('active')), None)
        if active is None:
            return None
        title = (active.get('title') or '').strip()
        if title in DIALOG_TITLES:
            return active.get('bounds')
        return None

    def guard_pointer(self, event):
        """Validate pointer effects without issuing any input of its own."""
        data = event['pointer']
        self.guard(data)
        if data['op'] != 'drag':
            return
        chooser = self.native_dialog() is not None
        if chooser:
            raise Refused('dragging is unavailable while a file dialog is open')
        destinations = []
        if data.get('to_target') is not None:
            destinations.append({'op': 'click', 'target': data['to_target']})
        elif 'to_x' in data and 'to_y' in data:
            destinations.append({'op': 'click', 'x': data['to_x'], 'y': data['to_y']})
        destinations += [{'op': 'click', 'x': x, 'y': y} for x, y in data.get('via', [])]
        for target in destinations:
            self.guard(target)

    def guard(self, data):
        """Confine inputs to the exchange folders while a native file dialog (not on the accessibility bus) is active,
        and refuse pointer input that would browse it; the standard file dialog is also confined by the application's
        own sandboxing of the process filesystem."""
        op = data['op']
        if op in ('wait', 'zoom', 'focus_window', 'maximize'):
            return
        bounds = self.native_dialog()
        if bounds is None:
            return
        if op in ('type', 'fill'):
            self.check_paths(data.get('value'))
            return
        if op == 'press':
            key = desktop.keysym(data['key'])
            if key not in DIALOG_KEYS:
                raise Refused('in a file dialog only movement, editing, Return, Escape and Ctrl+L keys are available')
            if key in PASTE_KEYS:
                try:
                    self.check_paths(self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT).decode('utf-8', 'replace'))
                except desktop.DesktopError:
                    pass
            return
        # Pointer input: allow only the confirmation band at the bottom of the dialog (Save/Open/Cancel buttons),
        # so the file list and the places sidebar cannot be browsed.
        if op in ('click', 'activate', 'check', 'drag', 'scroll', 'move'):
            x, y = self._point(data)
            if x is None:
                raise Refused('in a file dialog, target the confirm buttons by coordinates in its bottom bar')
            bx, by, bw, bh = bounds
            if not (by + bh - 64 <= y <= by + bh and bx <= x <= bx + bw):
                raise Refused('file dialogs are confined to the inbox and outbox: type an absolute exchange path '
                              '(Ctrl+L opens the location field) and confirm with the button in the bottom bar')

    @staticmethod
    def _point(data):
        if 'x' in data and 'y' in data and isinstance(data['x'], (int, float)) and isinstance(data['y'], (int, float)):
            return int(data['x']), int(data['y'])
        return None, None

    # Dispatch -------------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=LIMITS, notes=self.notes(),
                                         examples=examples(self.areas['inbox']))
        if op == 'status':
            return self.product.status()
        with self.lock:
            if op == 'reset':
                return self.reset()
            if op == 'restart':
                return self.restart()
            if op == 'list_files':
                return self.list_files(data)
            if op == 'upload':
                return self.upload(data)
            if op == 'download':
                return self.download(data)
            if op == 'open':
                return self.open(data)
            if self.ui is None:
                raise ValueError('the desktop is not available; use reset')
            if op == 'observe':
                tree = bool(data.get('tree'))
                return self.public(self.ui.observe(tree), tree)[0]
            if op == 'screenshot':
                return self.screenshot(data)
            if op == 'windows':
                windows = self.ui.windows()
                for window in windows:
                    window['title'] = self.private_text(window.get('title', ''))[0]
                return {'windows': windows}
            if op == 'clipboard_text':
                return self.clipboard_text()
            if op == 'clipboard_html':
                return self.clipboard_html()
            if op == 'clipboard_image':
                return self.clipboard_image()
            self.guard(data)
            return self.ui.act(data)

    def notes(self):
        return [f'Exchange folders: inbox {self.areas["inbox"]} (uploads) and outbox {self.areas["outbox"]} (save '
                'outputs there to download them). The application sees them as ordinary folders.',
                'Open documents with the open operation (it launches the application again with the paths, which the '
                'running instance opens); then edit and save. The application saves an already-named document to its '
                'own path without a dialog (for example Control+S).',
                'The application\'s native save and open dialogs are confined to the exchange folders: type an '
                'absolute inbox or outbox path (Ctrl+L opens the location field of an Open dialog; a Save dialog\'s '
                'name field accepts a full path) and confirm with the button in the dialog\'s bottom bar; places and '
                'folders elsewhere are refused.',
                'GUI operations answer briefly; observe and screenshot show the new state. Refs stay valid until the '
                'next observe; object targets are matched against a fresh snapshot.',
                'reset starts a new desktop session (clipboard and windows cleared) with empty exchange folders; '
                'restart keeps the data directory, the session and the exchange folders.']


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *_args):
        pass

    def reply(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(404, {'error': 'NotFound', 'detail': 'POST a JSON request to /rpc'})

    def do_POST(self):
        started, op, status = time.monotonic(), None, 200
        rt = self.server.runtime
        try:
            self.connection.settimeout(RPC_TIMEOUT)
            if self.path != '/rpc':
                status, value = 404, {'error': 'NotFound', 'detail': 'POST a JSON request to /rpc'}
            else:
                length = int(self.headers.get('Content-Length') or 0)
                if self.headers.get('Transfer-Encoding') or not 0 < length <= MAX_REQUEST:
                    status, value = 413, {'error': 'RequestTooLarge', 'detail': f'requests carry 1-{MAX_REQUEST} bytes'}
                else:
                    data = runtime.strict_json_loads(self.rfile.read(length))
                    op = data.get('op') if isinstance(data, dict) else None
                    value = rt.dispatch(data)
        except desktop.DesktopError as exc:
            status = 408 if exc.timeout else 400
            value = {'error': 'Timeout' if exc.timeout else 'DesktopError', 'detail': rt.detail(exc)}
        except Refused as exc:
            status, value = 400, {'error': 'Refused', 'detail': rt.detail(exc)}
        except Exception as exc:
            if not isinstance(exc, (ValueError, KeyError, TypeError)):
                rt.log.note(f'rpc {op}: {type(exc).__name__}: {exc}')
            status, value = 400, {'error': type(exc).__name__, 'detail': rt.detail(exc)}
        try:
            self.reply(status, value)
        finally:
            rt.audit.record(str(op or 'invalid')[:40], status, time.monotonic() - started)


def main(argv=None):
    config = runtime.options(ready_timeout=90.0).parse_args(argv)
    rt = Runtime(config)

    runtime.exit_on_sigterm()
    try:
        rt.start()
        sock = runtime.listen(config.socket, config.socket_mode)
        server = Server(config.socket, Handler, bind_and_activate=False)
        server.socket.close()
        server.socket = sock
        server.runtime = rt
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            server.server_close()
    finally:
        rt.close()
        try:
            os.unlink(config.socket)
        except OSError:
            pass


if __name__ == '__main__':
    main()
