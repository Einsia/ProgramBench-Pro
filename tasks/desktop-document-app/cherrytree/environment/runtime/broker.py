#!/usr/bin/env python3
"""CherryTree desktop runtime: a private X11 session, document exchange,
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
import signal
import socketserver
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import document_exchange as file_exchange
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'CherryTree'
SCREEN = (1280, 900)
MAX_UPLOAD = 20 * 1024 * 1024
MAX_DOWNLOAD = 50 * 1024 * 1024
MAX_REQUEST = (MAX_UPLOAD * 4 + 2) // 3 + 65_536
MAX_FILES = 400
MAX_DEPTH = 10
CLIPBOARD_TEXT = 400_000
CLIPBOARD_IMAGE = 8 * 1024 * 1024
RPC_TIMEOUT = 150
EXPORT_SECONDS = 60
READ_ONLY = 'read-only'
# Uploaded files carry one fixed modification time (2024-01-01 00:00 UTC), so file dialogs list them the same way
# in every session.
UPLOAD_TIME = 1704067200
# Downloads: documents, exports, images and text only.
MAGIC = (b'SQLite format 3\x00', b'7z\xbc\xaf\x27\x1c', b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a',
         b'GIF89a', b'BM')
PASTE_KEYS = {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
# Keys accepted while a file dialog is open: moving between its controls, editing text, confirming or leaving it.
CHOOSER_KEYS = {'ctrl+l', 'ctrl+a', 'ctrl+c', 'ctrl+x', 'ctrl+v', 'ctrl+shift+v', 'shift+Insert', 'Return', 'Escape',
                'Tab', 'shift+Tab', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'BackSpace', 'Delete', 'space',
                'Prior', 'Next', 'shift+Up', 'shift+Down', 'ctrl+Up', 'ctrl+Down'}
AFFIRMATIVE = {'open', 'save', 'select', 'export', 'ok', 'import', 'insert', 'add', 'choose', 'save as', 'create'}
EXPORT_FORMATS = {'html': '--export_to_html_dir', 'txt': '--export_to_txt_dir', 'pdf': '--export_to_pdf_dir'}

AREA = {'type': 'string', 'enum': ['inbox', 'outbox'], 'description': 'Exchange folder; default outbox.'}
NAME = {'type': 'string', 'required': True,
        'description': f'File path relative to the area: a base name, or up to {MAX_DEPTH} folder names and a base name joined by '
                       '"/" (no hidden names, at most 240 bytes each).'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Start over: a new desktop session, empty inbox and outbox, and the product with an empty '
                         'data directory (its initial state).'},
    'restart': {'kind': 'lifecycle',
                'summary': 'Start the product again with the same data directory, desktop session and exchange '
                           'folders (for example after quitting it through its own controls). With document, the '
                           'product is started with that document as its only command-line argument '
                           '(start.sh DOCUMENT), as when a document is opened from a file manager.',
                'fields': {'document': {'type': 'string', 'description': 'Absolute path of a document file or '
                                        'document folder inside the inbox or the outbox.'}}},
    **desktop.operations(SCREEN),
    'list_files': {'kind': 'files', 'summary': 'Files in the inbox or the outbox and its subfolders, in path order '
                   '(name relative to the area, size, path, read_only); files of the area\'s read-only subfolder are '
                   'flagged read_only; folders lists the subfolders. With folder, only that subfolder is listed (names '
                   f'stay relative to the area). At most {MAX_FILES} files are listed; truncated tells whether more '
                   'exist.',
                   'fields': {'area': AREA, 'folder': {'type': 'string', 'description': 'Relative name of a subfolder '
                                                                                       'of the area to list.'}}},
    'upload': {'kind': 'files', 'summary': 'Store one file in the inbox (default) or the outbox; folders in the name '
               'are created; read_only places it in the area\'s read-only subfolder, which the product cannot write '
               'to. Uploaded files get the modification time 2024-01-01 00:00 UTC.',
               'fields': {'filename': NAME,
                          'base64': {'type': 'string', 'required': True,
                                     'description': f'File bytes, base64 encoded; at most {MAX_UPLOAD} bytes, '
                                                    'empty files allowed.'},
                          'area': dict(AREA, description='Exchange folder; default inbox.'),
                          'read_only': {'type': 'boolean', 'description': 'Store it in the read-only subfolder; '
                                                                          'default false.'}}},
    'download': {'kind': 'files', 'summary': 'Retrieve one file from the outbox (or the inbox) as body_base64: '
                 'CherryTree documents (XML, SQLite, 7-Zip), PDF, PNG, JPEG, GIF and BMP images, and UTF-8 text '
                 '(HTML, CSS, JavaScript, CSV, plain text).',
                 'fields': {'filename': dict(NAME, description=NAME['description'] + ' A file of the read-only '
                                             'subfolder is named read-only/NAME.'),
                            'area': AREA}},
    'export': {'kind': 'files',
               'summary': 'Run the product\'s command-line export of one document in a separate process, as '
                          '"start.sh DOCUMENT --export_to_<format>_dir FOLDER [--export_single_file] '
                          '[--export_overwrite] [--password PASSWORD]" with the same environment as the running '
                          'application (its own display, no session bus), and wait for it to end. Answers with the '
                          'exit status, whether it was stopped at the time limit, and the listing of the export folder afterwards.',
               'fields': {'document': {'type': 'string', 'required': True,
                                       'description': 'Absolute path of a document file or document folder inside '
                                                      'the inbox or the outbox.'},
                          'format': {'type': 'string', 'required': True, 'enum': list(EXPORT_FORMATS),
                                     'description': 'Export format: html, txt or pdf.'},
                          'folder': {'type': 'string', 'description': 'Absolute path of a folder inside the outbox '
                                     'to export into (created when missing); default the outbox.'},
                          'single_file': {'type': 'boolean', 'description': 'Add --export_single_file; default false.'},
                          'overwrite': {'type': 'boolean', 'description': 'Add --export_overwrite; default false.'},
                          'password': {'type': 'string', 'description': 'Add --password with this value.'},
                          'seconds': {'type': 'number', 'description': f'Time limit, 1-120 s; default '
                                                                       f'{EXPORT_SECONDS}.'}}},
    'clipboard_text': {'kind': 'observe', 'summary': 'The plain text on the desktop clipboard (UTF-8, at most '
                       f'{CLIPBOARD_TEXT} bytes).', 'fields': {}},
    'clipboard_html': {'kind': 'observe', 'summary': 'The HTML (text/html) on the desktop clipboard, when the '
                       f'clipboard offers it (UTF-8, at most {CLIPBOARD_TEXT} bytes).', 'fields': {}},
    'clipboard_image': {'kind': 'observe', 'summary': 'The PNG image on the desktop clipboard as png_base64.',
                        'fields': {}},
})
LIMITS = {'upload_bytes': MAX_UPLOAD, 'download_bytes': MAX_DOWNLOAD, 'files_per_area': MAX_FILES,
          'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_TIMEOUT, 'screen': list(SCREEN)}


def examples(inbox, outbox):
    """Request examples for help; the paths name this runtime's own exchange folders."""
    return [{'op': 'observe'}, {'op': 'screenshot'}, {'op': 'click', 'target': 'e5a450812'},
            {'op': 'click', 'target': {'role': 'menu item', 'name': 'Add Node...'}},
            {'op': 'press', 'key': 'Control+S'}, {'op': 'press', 'key': 'Control+L'},
            {'op': 'type', 'value': f'{inbox}/notes.ctd'},
            {'op': 'upload', 'filename': 'notes.ctd', 'base64': '<base64>', 'area': 'outbox'},
            {'op': 'restart', 'document': f'{outbox}/notes.ctd'},
            {'op': 'export', 'document': f'{outbox}/notes.ctd', 'format': 'txt', 'single_file': True},
            {'op': 'list_files', 'area': 'outbox'}, {'op': 'download', 'filename': 'notes.ctd_TXT/a_1.txt'}]


class Refused(ValueError):
    """The request is outside the interface boundary."""


def safe_part(value):
    if not value or len(value.encode('utf-8')) > 240 or value in ('.', '..') or '\\' in value \
            or any(ord(c) < 32 for c in value):
        raise ValueError('file names must be non-empty base names of at most 240 bytes')
    if value.startswith('.'):
        raise ValueError('hidden file names are not accepted')
    return value


def safe_name(value):
    """A relative path: folder names and a base name joined by '/'."""
    if not isinstance(value, str) or not value or value.startswith('/') or '\x00' in value:
        raise ValueError('filename must be a relative name inside the area')
    parts = value.split('/')
    if len(parts) > MAX_DEPTH + 1:
        raise ValueError(f'at most {MAX_DEPTH} folder levels')
    return [safe_part(p) for p in parts]


def open_directory(path, parent=None):
    return file_exchange.open_directory(path, parent)


def downloadable(content):
    if content.startswith(MAGIC):
        return True
    if b'\x00' in content:
        return False
    try:
        content.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


class DocumentProduct(runtime.Product):
    """The application process, optionally started with one command-line argument (a document to open)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.arguments = []

    def start(self, fresh=False, arguments=None):
        self.stop()
        self.prepare(fresh)
        self.ready, self.starts = False, self.starts + 1
        script = self.solution / 'start.sh'
        if not script.is_file():
            self.detail = 'start.sh does not exist in the solution directory'
            self.log.note(self.detail)
            return False
        kwargs = {}
        if self.switching():
            account = self.account()
            kwargs = dict(user=account.pw_uid, group=account.pw_gid, extra_groups=[])
        read, write = os.pipe()
        try:
            self.proc = subprocess.Popen([str(script), *(arguments or [])], cwd=str(self.solution),
                                         env=self.environment(), stdin=subprocess.DEVNULL, stdout=write, stderr=write,
                                         start_new_session=True, **kwargs)
        except OSError as exc:
            os.close(read)
            self.proc = None
            self.detail = f'start.sh could not be executed ({type(exc).__name__}: {exc.strerror or exc})'
            self.log.note(self.detail)
            return False
        finally:
            os.close(write)
        self.log.pump(read)
        self.log.note(f'start {self.starts}: pid {self.proc.pid}' + (' with a document' if arguments else ''))
        self.detail = 'starting'
        return True


class Runtime:
    def __init__(self, config):
        self.config = config
        self.lock = threading.RLock()
        self.files = Path(config.state).resolve().parent / 'files'
        self.areas = {'inbox': self.files / 'inbox', 'outbox': self.files / 'outbox'}
        self.log = runtime.BoundedLog(config.log_dir)
        self.audit = runtime.Audit(Path(config.log_dir) / 'rpc-audit.jsonl')
        self.product = DocumentProduct(config, log=self.log)
        self.account = desktop.account(config.user)
        self.switching = os.geteuid() == 0 and self.account.pw_uid != 0
        self.session = self.ui = None
        roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                 '/app/solution', '/opt', '/proc', '/sys', '/root', '/etc', '/home', '/usr', '/var', '/srv', '/tests',
                 '/logs', '/model', '/tmp', '/reference', '/app']
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

    def exchange_path(self, value, what, outbox_only=False):
        """An absolute path inside the exchange folders (inside the outbox when outbox_only)."""
        if not isinstance(value, str) or not value.startswith('/') or '\x00' in value or '..' in value.split('/'):
            raise Refused(f'{what} must be an absolute path inside the inbox or the outbox')
        path = os.path.normpath(value)
        root = str(self.areas['outbox']) if outbox_only else str(self.files)
        if not self.inside(value):
            raise Refused(f'{what} must stay in the exchange folders without symbolic links')
        if not (path == root or path.startswith(root + os.sep)):
            raise Refused(f'{what} must lie inside the ' + ('outbox' if outbox_only else 'inbox or the outbox'))
        if path in (str(self.files),):
            raise Refused(f'{what} must lie inside the inbox or the outbox')
        real = os.path.realpath(path)
        if not (real == root or real.startswith(root + os.sep)):
            raise Refused(f'{what} leaves the exchange folders')
        return path

    def private_text(self, value):
        """Text with private filesystem locations replaced; exchange paths stay readable."""
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
        """An error detail without private locations (exchange paths stay readable)."""
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
                                  PBP_OUTBOX=str(self.areas['outbox']),
                                  LD_PRELOAD='/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1',
                                  FAKETIME='2024-01-01 12:00:00', FAKETIME_DONT_FAKE_MONOTONIC='1')

    def stop_session(self):
        for item in (self.ui, self.session):
            try:
                if item is not None:
                    item.close()
            except Exception as exc:
                self.log.note(f'desktop teardown: {type(exc).__name__}: {exc}')
        self.ui = self.session = None

    def launch(self, fresh, arguments=None):
        if self.product.start(fresh=fresh, arguments=arguments):
            runtime.wait_until(self.product, self.ui.ready, failure='no product window was reachable through AT-SPI '
                               f'within {self.config.ready_timeout:g} s')
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

    def restart(self, data):
        with self.lock:
            arguments = None
            if data.get('document') is not None:
                document = self.exchange_path(data['document'], 'document')
                if not os.path.exists(document):
                    raise ValueError('the document does not exist')
                arguments = [document]
            self.product.stop()
            if self.session is None or not self.session.alive():
                self.stop_session()
                self.start_session()
            return self.launch(fresh=False, arguments=arguments)

    def close(self):
        self.product.stop()
        self.stop_session()

    # Exchange -------------------------------------------------------------------------------------------------
    def area(self, data, default):
        name = data.get('area', default)
        return name, self.areas[name]

    def walk(self, folder):
        return file_exchange.walk(folder, limit=MAX_FILES, depth_limit=MAX_DEPTH)

    def list_files(self, data):
        area, folder = self.area(data, 'outbox')
        parts = safe_name(data['folder']) if data.get('folder') else []
        prefix = '/'.join(parts) + '/' if parts else ''
        with runtime.open_directory(folder) as root:
            with runtime.open_relative(root, '/'.join(parts) or '.', directory=True) as directory:
                files, folders, truncated = self.walk(directory)
        result = [{'name': prefix + rel, 'size': info.st_size, 'path': str(folder / (prefix + rel)),
                   'read_only': (prefix + rel).split('/')[0] == READ_ONLY} for rel, info in files]
        return {'area': area, 'files': result, 'folders': [prefix + f for f in folders], 'truncated': truncated}

    def descend(self, root, parts, create):
        """Descriptor of the folder parts below root (created when create), never through symbolic links."""
        current = root
        try:
            for part in parts:
                if create:
                    try:
                        os.mkdir(part, 0o755, dir_fd=current)
                        made = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
                        self.chown(fd=made)
                        os.fchmod(made, 0o755)
                        os.close(made)
                    except FileExistsError:
                        pass
                following = open_directory(part, current)
                if current != root:
                    os.close(current)
                current = following
        except Exception:
            if current != root:
                os.close(current)
            raise
        return current

    def upload(self, data):
        parts = safe_name(data['filename'])
        try:
            content = base64.b64decode(data['base64'], validate=True)
        except Exception:
            raise ValueError('base64 is invalid') from None
        if len(content) > MAX_UPLOAD:
            raise ValueError(f'uploaded files are limited to {MAX_UPLOAD} bytes')
        # Document parsers must not resolve external XML entities or local HTML resources.
        # Normal hyperlinks are inert document data; images and external entities cause reads.
        if content.lstrip().startswith(b'<'):
            text = content.decode('utf-8', 'replace')
            if re.search(r'<!ENTITY\s|<!DOCTYPE[^>]+(?:SYSTEM|PUBLIC)\s', text, re.I):
                raise Refused('external XML entities are not accepted')
            for value in re.findall(r'(?:src|xlink:href)\s*=\s*[\"\']([^\"\']+)[\"\']', text, re.I):
                local = unquote(value)
                if local.startswith('file:'):
                    local = urlsplit(local).path
                if local.startswith('/') and not self.inside(local) or '..' in local.split('/'):
                    raise Refused('local document resources must stay inside the exchange folders')
        area, folder = self.area(data, 'inbox')
        read_only = bool(data.get('read_only'))
        if parts[0] == READ_ONLY:
            raise ValueError('use read_only to store a file in the read-only subfolder')
        if read_only and len(parts) > 1:
            raise ValueError('the read-only subfolder holds base names only')
        relative = '/'.join(([READ_ONLY] if read_only else []) + parts)
        listed = self.list_files({'area': area})['files']
        if len(listed) >= MAX_FILES and not any(f['name'] == relative for f in listed):
            raise ValueError(f'the {area} holds at most {MAX_FILES} files; use reset to empty the exchange folders')
        file_exchange.write(self, area, '/'.join(parts), content, read_only=read_only, timestamp=UPLOAD_TIME)
        return {'area': area, 'name': relative, 'path': str(folder / relative), 'size': len(content),
                'read_only': read_only, 'sha256': hashlib.sha256(content).hexdigest()}

    def download(self, data):
        parts = safe_name(data['filename'])
        area, folder = self.area(data, 'outbox')
        content = file_exchange.read(self, area, '/'.join(parts), limit=MAX_DOWNLOAD)
        if len(content) > MAX_DOWNLOAD:
            raise ValueError(f'downloads are limited to {MAX_DOWNLOAD} bytes')
        if not downloadable(content):
            raise ValueError('downloads expose CherryTree documents, PDF, images and UTF-8 text only')
        return {'area': area, 'name': '/'.join(parts), 'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest(), 'body_base64': base64.b64encode(content).decode()}

    def export(self, data):
        document = self.exchange_path(data['document'], 'document')
        if not os.path.exists(document):
            raise ValueError('the document does not exist')
        folder = self.exchange_path(data.get('folder') or str(self.areas['outbox']), 'folder', outbox_only=True)
        relative = os.path.relpath(folder, self.areas['outbox'])
        if relative != '.':
            parts = safe_name(relative)
            if len(parts) > MAX_DEPTH:
                raise ValueError(f'the export folder may be at most {MAX_DEPTH} levels deep')
            root = open_directory(str(self.areas['outbox']))
            try:
                os.close(self.descend(root, parts, create=True))
            except (FileNotFoundError, NotADirectoryError, OSError):
                raise ValueError('the export folder is not a folder in the outbox') from None
            finally:
                os.close(root)
        seconds = data.get('seconds', EXPORT_SECONDS)
        if not 1 <= seconds <= 120:
            raise ValueError('seconds must be 1-120')
        arguments = [document, EXPORT_FORMATS[data['format']], folder]
        if data.get('single_file'):
            arguments.append('--export_single_file')
        if data.get('overwrite'):
            arguments.append('--export_overwrite')
        if data.get('password') is not None:
            if '\x00' in data['password'] or len(data['password']) > 200:
                raise ValueError('password must be at most 200 characters')
            arguments += ['--password', data['password']]
        script = self.product.solution / 'start.sh'
        if not script.is_file():
            raise ValueError('start.sh does not exist in the solution directory')
        env = self.product.environment()
        env['DBUS_SESSION_BUS_ADDRESS'] = 'disabled:'
        kwargs = {}
        if self.switching:
            kwargs = dict(user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=[])
        read, write = os.pipe()
        try:
            proc = subprocess.Popen([str(script), *arguments], cwd=str(self.product.solution), env=env,
                                    stdin=subprocess.DEVNULL, stdout=write, stderr=write, start_new_session=True,
                                    **kwargs)
        except OSError as exc:
            os.close(read)
            raise ValueError(f'start.sh could not be executed ({type(exc).__name__})') from None
        finally:
            os.close(write)
        self.log.note(f'export: pid {proc.pid}, format {data["format"]}')
        self.log.pump(read)
        timed_out = False
        try:
            proc.wait(seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            pass
        self.log.wait(2.0)
        return {'exit_code': None if timed_out else proc.returncode, 'timed_out': timed_out,
                'arguments': arguments,
                'outbox': self.list_files({'area': 'outbox', **({'folder': relative} if relative != '.' else {})})}

    def clipboard_text(self, target='UTF8_STRING'):
        raw = self.ui.clipboard(target, CLIPBOARD_TEXT)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the clipboard text is not UTF-8') from None
        return {'text': text, 'characters': len(text)}

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
        """Private filesystem locations and the private clipboard format leave observations; in a tree the whole
        subtree of a redacted node goes. Returns the observation and the screen boxes of redacted nodes."""
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

    @staticmethod
    def lineage(nodes, node):
        """The node and its ancestors in a tree observation."""
        by_ref = {n['ref']: n for n in nodes}
        chain, seen = [node], {node['ref']}
        while chain[-1].get('parent') in by_ref and chain[-1]['parent'] not in seen:
            seen.add(chain[-1]['parent'])
            chain.append(by_ref[chain[-1]['parent']])
        return chain

    def crumbs(self, nodes):
        """GTK path-bar folder buttons with their absolute folders, and the current folder (None when unknown)."""
        buttons = sorted((n for n in nodes if n['role'] == 'toggle button'
                          and any(a['role'] == 'filler' and a['name'] == 'PathBar Layer' for a in self.lineage(nodes, n))),
                         key=lambda n: n['bounds'][0])
        if not buttons or buttons[0]['name'] != 'File System Root':
            return [], None
        result, current = [], None
        for index, button in enumerate(buttons):
            path = '/' + '/'.join(b['name'] for b in buttons[1:index + 1])
            result.append((button['bounds'], path))
            if 'checked' in button.get('states', ()):
                current = path
        return result, current

    def target(self, data, view):
        """[role, name, description, bounds, states] chain (node first) of the control an input would reach."""
        if data.get('target') is not None:
            record = self.ui.resolve(data['target'])
            node = {'role': record['role'], 'name': record['name'], 'description': record.get('description') or '',
                    'bounds': record['bounds'], 'states': record.get('states', [])}
            return [node] + [{'role': role, 'name': name} for role, name in record['chain'][1:]]
        if data['op'] in ('click', 'drag', 'scroll', 'move') and 'x' in data and 'y' in data:
            hit = desktop.node_at(view, data['x'], data['y'])
            if hit is not None:
                return self.lineage(view['nodes'], hit)
        return None

    def guard_pointer(self, event):
        """Validate pointer effects without issuing any input of its own."""
        data = event['pointer']
        self.guard(data)
        if data['op'] != 'drag':
            return
        chooser = any(n['role'] == 'file chooser' for n in self.ui.inspect()['nodes'])
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
        """Refuse inputs that would leave the exchange folders through a file dialog."""
        op = data['op']
        if op in ('wait', 'zoom', 'focus_window', 'maximize', 'move', 'scroll'):
            return
        view = self.ui.inspect()
        nodes = view['nodes']
        key = desktop.keysym(data['key']) if op == 'press' else None
        # Pasting a local URI can embed a file without opening a chooser. Apply the same
        # exchange-folder boundary to clipboard routes and complete local paths in fields.
        if op in ('type', 'fill'):
            value = data.get('value', '').strip()
            if value.startswith(('/', 'file:')) and '\n' not in value:
                local = unquote(urlsplit(value).path) if value.startswith('file:') else value
                if not self.inside(local):
                    raise Refused('local file references must stay inside the exchange folders')
        paste = op == 'press' and key in PASTE_KEYS
        if op in ('click', 'activate'):
            target = self.target(data, view)
            paste = bool(target and 'paste' in target[0].get('name', '').casefold())
        if paste:
            for target in ('text/uri-list', 'UTF8_STRING'):
                try:
                    value = self.ui.clipboard(target, CLIPBOARD_TEXT).decode('utf-8', 'replace').strip()
                except desktop.DesktopError:
                    continue
                for line in value.splitlines():
                    if line.startswith(('/', 'file:')):
                        local = unquote(urlsplit(line).path) if line.startswith('file:') else line
                        if not self.inside(local):
                            raise Refused('pasted local file references must stay inside the exchange folders')
        if not any(n['role'] == 'file chooser' for n in nodes):
            return
        chain = self.target(data, view)
        if op in ('type', 'fill'):
            self.check_paths(data.get('value'))
        if op == 'press' and key not in CHOOSER_KEYS:
            raise Refused('in a file dialog only movement, editing, Return, Escape and Ctrl+L keys are available')
        if op == 'press' and key in PASTE_KEYS:
            try:
                self.check_paths(self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT).decode('utf-8', 'replace'))
            except desktop.DesktopError:
                pass
        crumbs, current = self.crumbs(nodes)
        inside_current = current is not None and self.inside(current)
        target = chain[0] if chain else None
        in_chooser = bool(chain) and any(link['role'] == 'file chooser' for link in chain)
        names = [link.get('name') for link in chain or ()]
        if in_chooser and op in ('click', 'activate', 'check', 'drag'):
            if 'Places' in names and target['role'] != 'scroll pane':
                place = next((link.get('description') for link in chain if link.get('description')), '') or ''
                if not (place.startswith('/') and self.inside(place)):
                    raise Refused('places outside the inbox and outbox are not available in file dialogs; type an '
                                  'absolute inbox or outbox path (Ctrl+L in an Open dialog)')
            if target['role'] == 'toggle button' and 'PathBar Layer' in names:
                path = next((p for bounds, p in crumbs if bounds == target.get('bounds')), None)
                if path is None or not self.inside(path):
                    raise Refused('folders outside the inbox and outbox are not available in file dialogs')
            in_list = 'Files' in names and 'Places' not in names
            if in_list and not inside_current and (op == 'activate' or data.get('click_count', 1) > 1):
                raise Refused('this folder is outside the inbox and outbox; type an absolute inbox or outbox path')
        confirming = (op == 'press' and key == 'Return') or (
            op in ('click', 'activate') and target is not None and (
                (target['role'] in ('push button', 'button')
                 and (target.get('name') or '').replace('_', '').strip().casefold() in AFFIRMATIVE)
                or (in_chooser and data.get('click_count', 1) > 1)))
        if confirming:
            typed = [n.get('text') or '' for n in nodes if n['role'] in ('text', 'entry')
                     and 'editable' in n.get('states', ()) and '/' in (n.get('text') or '')
                     and any(a['role'] == 'file chooser' for a in self.lineage(nodes, n))]
            for value in typed:
                self.check_paths(value)
            if not typed and not inside_current:
                raise Refused('file dialogs confirm only inside the inbox and outbox: type an absolute path such as '
                              f'{self.areas["outbox"]}/notes.ctd (Ctrl+L opens the location field of an Open dialog)')

    # Dispatch -------------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=LIMITS, notes=self.notes(),
                                         examples=examples(self.areas['inbox'], self.areas['outbox']))
        if op == 'status':
            return self.product.status()
        with self.lock:
            if op == 'reset':
                return self.reset()
            if op == 'restart':
                return self.restart(data)
            if op == 'list_files':
                return self.list_files(data)
            if op == 'upload':
                return self.upload(data)
            if op == 'download':
                return self.download(data)
            if op == 'export':
                return self.export(data)
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
                return self.clipboard_text('text/html')
            if op == 'clipboard_image':
                return self.clipboard_image()
            self.guard(data)
            return self.ui.act(data)

    def notes(self):
        return [f'Exchange folders: inbox {self.areas["inbox"]} (uploads) and outbox {self.areas["outbox"]} (save '
                'outputs there to download them). The product sees them as ordinary folders; uploads, listings and '
                'downloads reach their subfolders by relative names such as folder/file.txt.',
                'In standard file choosers (accessible role "file chooser") documents and folders are named by typed '
                'absolute paths in the inbox and outbox (Ctrl+L opens the location field of an Open dialog; the name '
                'field of a Save dialog accepts a full path), places and path-bar folders elsewhere are refused, and '
                'a dialog confirms only inside the exchange folders. Other dialogs receive text as typed.',
                'export runs the product\'s own command line on a document while the application keeps running; '
                'restart with document starts the application on that document.',
                'The application clock is fixed at 2024-01-01 12:00:00 UTC; monotonic timers run normally.',
                'GUI operations answer briefly; observe and screenshot show the new state. Refs stay valid until the '
                'next observe; object targets are matched against a fresh snapshot.',
                'Product errors and dialogs are observations; a refused request answers 400 with the reason.',
                'Local file references in fields, pasted file URIs and local document image resources must remain '
                'inside the exchange folders; external XML entities are refused. The reference process confines '
                'writes to instance and exchange data and disables command execution and external applications.',
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
        # A product that fails to start is reported by status; the runtime keeps serving.
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
