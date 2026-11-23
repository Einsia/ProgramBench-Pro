#!/usr/bin/env python3
"""Zotero desktop runtime.

Runs one application with a private X11 session and bounded document exchange.
The same operations serve the reference installation and a local application.
Input validation and observations are defined by the runtime help.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import http.server
import io
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import socketserver
import stat
import sys
import threading
import time
import urllib.parse
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'Zotero'
SCREEN = (1280, 900)
MAX_UPLOAD = 20 * 1024 * 1024
MAX_DOWNLOAD = 50 * 1024 * 1024
MAX_REQUEST = (MAX_UPLOAD * 4 + 2) // 3 + 65_536
MAX_FILES = 128
CLIPBOARD_TEXT = 400_000
CLIPBOARD_IMAGE = 8 * 1024 * 1024
RPC_TIMEOUT = 150
SAMPLES = '/app/samples'
READ_ONLY = 'read-only'
# Uploaded files carry one fixed modification time (2024-01-01 00:00 UTC), so file dialogs list them the same way
# in every session.
UPLOAD_TIME = 1704067200
# The local API key the runtime grants the product (PBP_API_KEY); public, like the product's port.
API_KEY = 'PBPLocalApiKey0123456789abcdefgh'
API_BODY = 8 * 1024 * 1024
API_TIMEOUT = 30
API_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
API_HEADERS = {'zotero-api-key', 'zotero-server-id', 'zotero-api-version', 'zotero-write-token',
               'if-unmodified-since-version', 'if-modified-since-version', 'if-match', 'if-none-match',
               'authorization', 'accept', 'x-zotero-connector-api-version'}
RESPONSE_HEADERS = ('content-type', 'zotero-api-version', 'zotero-schema-version', 'zotero-server-id',
                    'last-modified-version', 'total-results', 'link', 'location', 'retry-after', 'www-authenticate',
                    'x-zotero-version', 'x-zotero-connector-api-version')
# Text documents the product exports (bibliographies, reports, export formats) and PDF/PNG/JPEG documents.
TEXT_SUFFIXES = {'.bib', '.ris', '.json', '.csv', '.xml', '.rdf', '.html', '.htm', '.rtf', '.txt', '.md', '.nbib',
                 '.enw', '.tei', '.mods', '.csl', '.cff', '.yaml', '.yml'}
PASTE_KEYS = {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
EDIT_ROLES = {'text', 'entry', 'password text', 'spin button', 'terminal'}
# Keys accepted while a file dialog is open: moving between its controls, editing text, confirming or leaving it.
CHOOSER_KEYS = {'ctrl+l', 'ctrl+a', 'ctrl+c', 'ctrl+x', 'ctrl+v', 'ctrl+shift+v', 'shift+Insert', 'Return', 'KP_Enter', 'Escape',
                'Tab', 'shift+Tab', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'BackSpace', 'Delete', 'space',
                'Prior', 'Next', 'shift+Up', 'shift+Down', 'ctrl+Up', 'ctrl+Down'}
AFFIRMATIVE = {'open', 'save', 'select', 'export', 'ok', 'import', 'insert', 'add', 'choose'}
# Features that run or show program code, printing (it writes to arbitrary files) and choosing an external
# application to open files (the product would run it): menu items and buttons are refused, and their windows are
# closed.
REFUSED_CONTROLS = {'plugins', 'developer', 'error console', 'run javascript', 'style editor', 'translator editor',
                    'config editor', 'debug output logging', 'view output', 'troubleshooting information',
                    'report errors', 'restart in troubleshooting mode', 'print', 'choose application'}
REFUSED_WINDOWS = re.compile(r'^(run javascript|browser console|browser toolbox|plugins manager|add-ons manager|'
                             r'zotero (style|translator) editor|scaffold|advanced preferences|about:config|'
                             r'config(uration)? editor|debug output|troubleshooting information|zotero error report|'
                             r'print|choose application)\b', re.I)
# The settings that pick the application opening a file type ("Open PDFs using"): only the built-in viewer.
OPEN_WITH = re.compile(r'^open \S+ using$')
HANDLER_CHOICES = {'custom', 'system default'}
REFUSAL = ('plugins, developer tools, diagnostics, the configuration editor, printing and external applications are '
           'not available')
MENU_ROLES = {'menu item', 'menu', 'check menu item', 'radio menu item'}
MENU_KEYS = {'Return', 'KP_Enter', 'space', 'Right'}
MENU_NAVIGATION = {'Escape', 'Up', 'Down', 'Left', 'Home', 'End', 'Tab', 'shift+Tab'}

AREA = {'type': 'string', 'enum': ['inbox', 'outbox'], 'description': 'Exchange folder; default outbox.'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Start over: a new desktop session, empty inbox and outbox, and the product with an empty '
                         'data directory (its initial state).'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Start the product again with the same data directory, desktop session and exchange '
                           'folders (for example after quitting it through its own controls).'},
    **desktop.operations(SCREEN),
    'api': {'kind': 'http',
            'summary': 'One HTTP request to the product\'s local server on PORT: its local Web API under /api/ and '
                       'GET /connector/ping. Write requests authenticate with the local API key (help: api_key). '
                       'Redirects are not followed; private file locations in responses read [private].',
            'fields': {
                'path': {'type': 'string', 'required': True,
                         'description': 'Absolute path with optional query, for example '
                                        '/api/users/0/items?limit=5; no dot segments.'},
                'method': {'type': 'string', 'enum': API_METHODS, 'description': 'HTTP method; default GET.'},
                'headers': {'type': 'object', 'description': 'Request headers; allowed: Zotero-API-Key, '
                            'Zotero-Server-ID, Zotero-API-Version, Zotero-Write-Token, If-Unmodified-Since-Version, '
                            'If-Modified-Since-Version, If-Match, If-None-Match, Authorization, Accept, '
                            'X-Zotero-Connector-API-Version.'},
                'json': {'type': ['object', 'array', 'string', 'number', 'boolean'],
                         'description': 'JSON request body (at most one body field; Content-Type application/json '
                                        'unless content_type says otherwise).'},
                'body': {'type': 'string', 'description': 'Text request body.'},
                'body_base64': {'type': 'string', 'description': 'Request body bytes, base64 encoded.'},
                'form': {'type': 'object', 'description': 'Form fields sent as application/x-www-form-urlencoded.'},
                'content_type': {'type': 'string', 'description': 'Content-Type of the body.'},
                'binary': {'type': 'boolean', 'description': 'Also return the response bytes as body_base64.'},
                'timeout': {'type': 'number', 'description': f'Seconds to wait for the answer, 1-120; default '
                                                             f'{API_TIMEOUT}.'},
            }},
    'list_files': {'kind': 'files', 'summary': 'Files in the inbox or the outbox (name, size, path, read_only); files '
                   'of the area\'s read-only subfolder are flagged read_only.',
                   'fields': {'area': AREA}},
    'upload': {'kind': 'files', 'summary': 'Store one file in the inbox (default) or the outbox; read_only places it '
               'in the area\'s read-only subfolder, which the product cannot write to. Uploaded files get the '
               'modification time 2024-01-01 00:00 UTC.',
               'fields': {'filename': {'type': 'string', 'required': True,
                                       'description': 'Base name (no folders, not hidden), at most 240 bytes.'},
                          'base64': {'type': 'string', 'required': True,
                                     'description': f'File bytes, base64 encoded; at most {MAX_UPLOAD} bytes, '
                                                    'empty files allowed.'},
                          'area': dict(AREA, description='Exchange folder; default inbox.'),
                          'read_only': {'type': 'boolean', 'description': 'Store it in the read-only subfolder; '
                                                                          'default false.'}}},
    'download': {'kind': 'files', 'summary': 'Retrieve one document from the outbox (or the inbox) as body_base64: '
                 'PDF, PNG or JPEG, or UTF-8 text with one of the suffixes ' + ', '.join(sorted(TEXT_SUFFIXES)) + '.',
                 'fields': {'filename': {'type': 'string', 'required': True, 'description': 'Base name of the file.'},
                            'area': AREA,
                            'read_only': {'type': 'boolean', 'description': 'Read it from the read-only subfolder; '
                                                                            'default false.'}}},
    'clipboard_text': {'kind': 'observe', 'summary': 'The plain text on the desktop clipboard (UTF-8, at most '
                       f'{CLIPBOARD_TEXT} bytes).', 'fields': {}},
    'clipboard_html': {'kind': 'observe', 'summary': 'The HTML (text/html) on the desktop clipboard, at most '
                       f'{CLIPBOARD_TEXT} bytes.', 'fields': {}},
    'clipboard_image': {'kind': 'observe', 'summary': 'The PNG image on the desktop clipboard as png_base64.',
                        'fields': {}},
})
LIMITS = {'upload_bytes': MAX_UPLOAD, 'download_bytes': MAX_DOWNLOAD, 'files_per_area': MAX_FILES,
          'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_TIMEOUT, 'api_body_bytes': API_BODY,
          'screen': list(SCREEN)}


def examples(inbox):
    """Request examples for help; the typed path names this runtime's own inbox."""
    return [{'op': 'observe'}, {'op': 'screenshot'}, {'op': 'click', 'target': {'role': 'menu', 'name': 'File'}},
            {'op': 'click', 'target': {'role': 'push button', 'name': 'New Item'}},
            {'op': 'press', 'key': 'Control+Shift+N'}, {'op': 'type', 'value': f'{inbox}/references.bib'},
            {'op': 'api', 'path': '/api/users/0/items/top?format=json&limit=10'},
            {'op': 'api', 'path': '/api/users/0/collections', 'method': 'POST',
             'headers': {'Zotero-API-Key': API_KEY, 'Zotero-Server-ID': '<from a response header>'},
             'json': [{'name': 'Reading list'}]},
            {'op': 'list_files', 'area': 'outbox'}, {'op': 'download', 'filename': 'library.bib'}]


class Refused(ValueError):
    """The request is outside the interface boundary."""


class NoteBoundary(HTMLParser):
    """Rich text is permitted; executable markup and resource-loading elements are not.

    Applied to the pinned product only. Imported notes and API notes use the same boundary.
    Annotation citation metadata is inert text; links are limited to web pages and item navigation.
    """
    TAGS = {'p', 'div', 'span', 'br', 'hr', 'strong', 'b', 'em', 'i', 'u', 's', 'strike', 'sub', 'sup',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'ul', 'ol', 'li', 'pre', 'code',
            'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'a'}
    ATTRS = {'class', 'id', 'title', 'style', 'dir', 'lang', 'colspan', 'rowspan', 'start', 'type',
             'href', 'rel', 'target'}

    def handle_starttag(self, tag, attrs):
        if tag not in self.TAGS:
            raise Refused('notes may contain static rich text only')
        for name, value in attrs:
            value = value or ''
            if name not in self.ATTRS and not name.startswith('data-'):
                raise Refused('active note attributes are not available')
            if name == 'style' and re.search(r'url\s*\(|expression|binding|@|\\', value, re.I):
                raise Refused('note styles cannot load resources')
            if name == 'href' and not re.match(
                    r'^(?:https?://|#|zotero://(?:select|open-pdf)/library/items/[A-Z0-9]{8}(?:[/?#]|$))', value, re.I):
                raise Refused('note links must name web pages or library items')

    handle_startendtag = handle_starttag

    def handle_decl(self, decl):
        raise Refused('document declarations are not available in notes')


def check_note(value):
    if not isinstance(value, str):
        return
    # Decode character references and URL escapes before checking schemes, including nested encodings.
    decoded = value
    for _ in range(8):
        expanded = html.unescape(urllib.parse.unquote(decoded))
        if expanded == decoded:
            break
        decoded = expanded
    compact = re.sub(r'[\x00-\x20\x7f]+', '', decoded)
    if re.search(r'(?:resource|chrome|jar|moz-[\w-]+|about|view-source|file|javascript|data|vbscript):', compact, re.I):
        raise Refused('notes cannot refer to internal resources or executable documents')
    parser = NoteBoundary(convert_charrefs=True)
    parser.feed(value)
    parser.close()


def safe_name(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 240:
        raise ValueError('filename must be a non-empty base name of at most 240 bytes')
    if Path(value).name != value or value in ('.', '..') or '\\' in value or any(ord(c) < 32 for c in value):
        raise ValueError('filename must be a base name')
    if value.startswith('.'):
        raise ValueError('hidden file names are not accepted')
    return value


def vet_incoming_document(name, content):
    """Reject active attachments and active markup before the product imports a document."""
    if Path(name).suffix.lower() in {'.html', '.htm', '.xhtml', '.svg', '.svgz', '.epub', '.mhtml', '.xul'}:
        raise Refused('active attachment documents are unavailable')
    if content.startswith((b'%PDF-', b'\x89PNG\r\n', b'\xff\xd8\xff')):
        return
    if content.startswith(b'PK'):
        raise Refused('archived attachments are unavailable')
    value = content.decode('utf-8', 'replace')
    for _ in range(8):
        decoded = html.unescape(urllib.parse.unquote(value))
        if decoded == value:
            break
        value = decoded
    if re.search(r'<\s*(?:script|iframe|object|embed|svg|applet)\b|<[^>]+\s+on[a-z]+\s*=', value, re.I):
        raise Refused('documents cannot carry executable markup')
    compact = re.sub(r'[\x00-\x20\x7f]+', '', value)
    if re.search(r'(?<![A-Za-z0-9+.-])(?:javascript|vbscript|resource|chrome|jar|view-source|file):', compact, re.I):
        raise Refused('documents cannot load executable or private resources')


def open_directory(path, parent=None):
    """Return a directory handle after checking every component without following links."""
    try:
        if parent is None:
            with runtime.open_directory(path) as fd:
                return os.dup(fd)
        with runtime.open_relative(parent, path, directory=True) as fd:
            return os.dup(fd)
    except FileNotFoundError:
        raise ValueError(f'{Path(str(path)).name} does not exist') from None
    except OSError:
        raise ValueError(f'{Path(str(path)).name} is not a plain folder') from None


def label(value):
    """A control name compared with the refused features: case and trailing ellipses ignored."""
    return re.sub(r'(\.\.\.|…)$', '', ' '.join(str(value or '').casefold().split())).strip()


REFUSED_LABELS = {label(name) for name in REFUSED_CONTROLS}


def sha256_file(path, limit=None):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


class ContentGuard:
    """The reference installation's library must not hold a copy of one of the product's own files (its installation, its
    translators and styles) or a link to a file outside the exchange folders: import formats can name local files,
    and the product shows, indexes and exports attached files. While it does, outputs are refused until reset.

    Notes must be static rich text; active attachment documents are unavailable.
    Only the pinned reference installation is guarded; other applications manage their own files."""
    # zotero-bin of the pinned reference installation (Zotero 10.0.6, Linux x86_64).
    PINNED = 'dc4ab0ea9f2bbb8b35025b25b251f9dd0efc4a811fb0736e2db63138296f0236'

    def __init__(self, rt):
        self.rt = rt
        self.enabled = False
        self.private = set()
        self.known = {}
        self.sources = {}
        self.markers = ()
        self.violation = None

    def setup(self):
        binary = Path(self.rt.config.solution) / 'zotero' / 'zotero-bin'
        try:
            self.enabled = binary.is_file() and sha256_file(binary) in self.pinned()
        except OSError:
            self.enabled = False
        if not self.enabled:
            return
        root = Path(self.rt.config.solution).resolve()
        # The installation root is searchable but not listable. Enumerate only its resource tree.
        paths = [root / name for name in ('start.sh', 'launch.py', 'SOURCE.json', 'LICENSE', 'NOTICE',
                                          'LICENSES/Mozilla-platform.txt', 'LICENSES/Zotero-assets.txt')]
        paths.extend((root / 'zotero').rglob('*'))
        for path in paths:
            if path.is_file() and not path.is_symlink():
                try:
                    self.private.add(sha256_file(path))
                except OSError:
                    continue
        self.markers = tuple(p.encode() for p in (str(Path(self.rt.config.state).resolve()), str(root),
                                                   str(Path(self.rt.config.log_dir).resolve())) if p != '/')

    def pinned(self):
        return {self.PINNED}

    def library(self):
        return Path(self.rt.product.directories['DATA_DIR']) / 'zotero'

    def refresh_sources(self):
        """Hashes of the product's translators and styles in its data directory (written on first start)."""
        for name in ('translators', 'styles'):
            folder = self.library() / name
            try:
                mark = folder.stat().st_mtime_ns
            except OSError:
                continue
            if self.sources.get(name) == mark:
                continue
            for path in folder.iterdir():
                try:
                    if path.is_file() and not path.is_symlink():
                        self.private.add(sha256_file(path))
                except OSError:
                    continue
            self.sources[name] = mark

    def stored_violation(self):
        storage = self.library() / 'storage'
        if not storage.is_dir():
            return None
        for folder in storage.iterdir():
            try:
                entries = list(folder.iterdir()) if folder.is_dir() and not folder.is_symlink() else []
            except OSError:
                continue
            for path in entries:
                try:
                    info = path.lstat()
                except OSError:
                    continue
                if stat.S_ISLNK(info.st_mode) or stat.S_ISDIR(info.st_mode):
                    return 'a stored attachment is a link or a folder'
                if not stat.S_ISREG(info.st_mode):
                    continue
                key = (str(path), info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                if key not in self.known:
                    try:
                        digest = sha256_file(path)
                        with open(path, 'rb') as stream:
                            head = stream.read(MAX_DOWNLOAD + 1)
                    except OSError:
                        continue
                    private = digest in self.private or any(marker in head for marker in self.markers)
                    private = private or self.active_document(path, head)
                    self.known[key] = private
                if self.known[key]:
                    return 'a stored attachment contains private content or an unavailable document type'
        return None

    @staticmethod
    def active_document(path, head=None):
        """Refuse snapshot, SVG and EPUB viewing, including disguised files and archived content.

        PDF and raster images retain their native readers. Plain text cannot contain markup that the product
        could sniff as HTML. Archives are refused as a whole, including all nested EPUB documents.
        """
        if Path(path).suffix.lower() in {'.html', '.htm', '.xhtml', '.svg', '.svgz', '.epub', '.mhtml', '.xul'}:
            return True
        if head is None:
            with open(path, 'rb') as stream:
                head = stream.read(MAX_DOWNLOAD + 1)
        if head.startswith((b'%PDF-', b'\x89PNG\r\n', b'\xff\xd8\xff')):
            return False
        if Path(path).name == '.zotero-sdt-cache' and head.startswith(b'\x89SDT\r\n\x1a\n'):
            # The PDF reader's binary structured-text cache is not a rendered attachment document.
            return False
        if head.startswith(b'PK') or zipfile.is_zipfile(path):
            return True
        text = head.replace(b'\x00', b'').decode('utf-8', 'replace')
        return bool(re.search(r'<\s*[!?/a-z]', text, re.I)) or len(head) > MAX_DOWNLOAD

    def linked_violation(self):
        """Inspect all notes and attachments through the API, including imported and trashed objects."""
        if not self.rt.product.running():
            return None
        try:
            items, start = [], 0
            while True:
                answer = self.rt.http_request('GET', '/api/users/0/items?itemType=note%20%7C%7C%20attachment'
                                              f'&includeTrashed=1&limit=100&start={start}', None, {}, 5)
                if answer['status'] != 200:
                    return 'the library could not be inspected yet; try again'
                page = json.loads(answer['bytes'])
                if not isinstance(page, list):
                    return 'the library could not be inspected yet; try again'
                items.extend(page)
                if not page:
                    break
                start += len(page)
        except (OSError, http.client.HTTPException, ValueError):
            return 'the library could not be inspected yet; try again'
        for item in items:
            data = item.get('data') if isinstance(item, dict) else None
            if not isinstance(data, dict):
                continue
            try:
                check_note(data.get('note'))
            except Refused as exc:
                return str(exc)
            if data.get('itemType') != 'attachment':
                continue
            if data.get('linkMode') == 'linked_url':
                if data.get('url') and not re.match(r'^https?://', str(data['url']), re.I):
                    return 'web attachments must name an HTTP or HTTPS page'
                continue
            if str(data.get('contentType', '')).lower().split(';')[0] in {
                    'text/html', 'application/xhtml+xml', 'image/svg+xml', 'application/epub+zip'}:
                return 'snapshot, SVG and EPUB attachments are unavailable'
            if data.get('linkMode') != 'linked_file':
                continue
            path = str(data.get('path') or '')
            if path.startswith('attachments:'):
                if '..' in Path(path[len('attachments:'):]).parts:
                    return 'a linked attachment leaves its base folder'
                return 'relative linked attachments cannot be inspected safely'
            if not (path.startswith('/') and self.rt.inside(path)):
                return 'a linked attachment points outside the inbox and outbox'
            try:
                if Path(path).is_symlink() or not self.rt.inside(str(Path(path).resolve())):
                    return 'a linked attachment leaves the exchange folders'
                if Path(path).is_file() and self.active_document(path):
                    return 'a linked attachment contains an unavailable document type'
            except OSError:
                return 'a linked attachment could not be inspected'
        return None

    def check(self):
        if not self.enabled:
            return
        if self.violation:
            raise Refused(self.violation + '; outputs are refused until reset')
        self.refresh_sources()
        problem = self.stored_violation() or self.linked_violation()
        if problem:
            if 'try again' not in problem:
                self.violation = problem
            raise Refused(problem + '; outputs are refused until reset')


def remove_exchange(parent, name):
    """Make owned read-only subfolders removable, using only fixed directory handles."""
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(info.st_mode):
        with runtime.open_relative(parent, name, directory=True) as directory:
            runtime.set_metadata(directory, mode=0o700)
            for child, _ in runtime.list_directory(directory):
                remove_exchange(directory, child)
    runtime.remove_entry(parent, name, missing_ok=True)


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
        self.guard_content = ContentGuard(self)
        roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                 '/app/solution', '/opt', '/proc', '/sys', '/root', '/etc', '/home', '/usr', '/var', '/srv', '/tests',
                 '/logs', '/model']
        self.private = sorted({str(Path(p).resolve()) for p in roots if p and str(p) != '/'}, key=len, reverse=True)

    # Paths ----------------------------------------------------------------------------------------------------
    def inside(self, value):
        """Whether a resolved absolute path lies in an unchanged exchange folder."""
        if not os.path.isabs(value):
            return False
        path = os.path.realpath(value)
        return any(os.path.realpath(root) == str(root)
                   and (path == str(root) or path.startswith(str(root) + os.sep))
                   for root in self.areas.values())

    def private_text(self, value):
        """Text with private filesystem locations replaced; exchange paths stay readable."""
        text = str(value)
        if '/' not in text:
            return text, False
        changed = False

        def replace(match):
            nonlocal changed
            path = match.group(0)
            # file:///x and //x name the same location as /x.
            probe = '/' + path.lstrip('/')
            if self.inside(probe):
                return path
            for root in self.private:
                if probe == root or probe.startswith(root + '/'):
                    changed = True
                    return '[private]'
            return path
        return re.sub(r'/[^\s\'"<>()\[\]{},;]*', replace, text), changed

    def detail(self, exc):
        """An error detail without private locations (exchange paths stay readable)."""
        return self.private_text(str(exc))[0][:600]

    def chown(self, path=None, fd=None):
        if fd is None:
            raise ValueError('ownership changes require an open descriptor')
        if self.switching:
            runtime.set_metadata(fd, uid=self.account.pw_uid, gid=self.account.pw_gid)

    # Lifecycle ----------------------------------------------------------------------------------------------------
    def prepare_areas(self, clear):
        with runtime.open_directory(self.files.parent, create=True) as parent:
            with runtime.owned_directory(parent, self.files.name, uid=os.geteuid(), gid=os.getegid(), mode=0o711) as files:
                for name in self.areas:
                    if clear:
                        remove_exchange(files, name)
                    uid, gid = self.account.pw_uid, self.account.pw_gid
                    with runtime.owned_directory(files, name, uid=uid, gid=gid, mode=0o755):
                        pass

    def start_session(self):
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, log_dir=self.config.log_dir).start()
        self.ui = desktop.Desktop(self.session, log_dir=self.config.log_dir, pointer_guard=self.guard_pointer)
        self.product.extra = dict(self.session.env(), PBP_INBOX=str(self.areas['inbox']),
                                  PBP_OUTBOX=str(self.areas['outbox']), PBP_SAMPLES=SAMPLES, PBP_API_KEY=API_KEY)

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
            runtime.wait_until(self.product, self.ui.ready, failure='no product window was reachable through AT-SPI '
                               f'within {self.config.ready_timeout:g} s')
        status = self.product.status()
        self.log.note('status: ' + json.dumps(status))
        return status

    def start(self):
        with self.lock:
            self.prepare_areas(clear=True)
            self.start_session()
            self.guard_content.setup()
            return self.launch(fresh=True)

    def reset(self):
        with self.lock:
            self.product.stop()
            self.stop_session()
            self.prepare_areas(clear=True)
            self.guard_content.known.clear()
            self.guard_content.sources.clear()
            self.guard_content.violation = None
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
        name, folder = self.area(data, 'outbox')
        result = []
        try:
            root = open_directory(folder)
        except ValueError:
            return {'area': name, 'files': []}
        try:
            entries = [(entry, False) for entry in sorted(os.listdir(root))]
            try:
                locked = open_directory(READ_ONLY, root)
                entries += [(entry, True) for entry in sorted(os.listdir(locked))]
            except ValueError:
                locked = None
            for entry, in_locked in entries:
                if len(result) >= MAX_FILES:
                    break
                try:
                    info = os.stat(entry, dir_fd=locked if in_locked else root, follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    path = folder / READ_ONLY / entry if in_locked else folder / entry
                    result.append({'name': entry, 'size': info.st_size, 'path': str(path), 'read_only': in_locked})
            if locked is not None:
                os.close(locked)
        finally:
            os.close(root)
        return {'area': name, 'files': result}

    def upload(self, data):
        name = safe_name(data['filename'])
        try:
            content = base64.b64decode(data['base64'], validate=True)
        except Exception:
            raise ValueError('base64 is invalid') from None
        if len(content) > MAX_UPLOAD:
            raise ValueError(f'uploaded files are limited to {MAX_UPLOAD} bytes')
        vet_incoming_document(name, content)
        area, folder = self.area(data, 'inbox')
        read_only = bool(data.get('read_only'))
        listed = self.list_files({'area': area})['files']
        if len(listed) >= MAX_FILES and not any(f['name'] == name and f['read_only'] == read_only for f in listed):
            raise ValueError(f'the {area} holds at most {MAX_FILES} files; use reset to empty the exchange folders')
        root = open_directory(folder)
        directory = root
        try:
            if read_only:
                try:
                    os.mkdir(READ_ONLY, 0o700, dir_fd=root)
                except FileExistsError:
                    pass
                directory = open_directory(READ_ONLY, root)
                os.fchmod(directory, 0o700)
            try:
                info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the destination must be one regular file')
            except FileNotFoundError:
                pass
            runtime.atomic_write(directory, name, content, uid=self.account.pw_uid, gid=self.account.pw_gid, mode=0o444 if read_only else 0o644)
            with runtime.open_relative(directory, name) as descriptor:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the uploaded file changed during setup')
                runtime.set_metadata(descriptor, ns=(UPLOAD_TIME * 1_000_000_000,) * 2)
        finally:
            if directory != root:
                self.chown(fd=directory)
                os.fchmod(directory, 0o555)
                os.close(directory)
            os.close(root)
        path = folder / READ_ONLY / name if read_only else folder / name
        return {'area': area, 'name': name, 'path': str(path), 'size': len(content), 'read_only': read_only,
                'sha256': hashlib.sha256(content).hexdigest()}

    def download(self, data):
        name = safe_name(data['filename'])
        area, folder = self.area(data, 'outbox')
        root = open_directory(folder)
        directory = root
        try:
            if data.get('read_only'):
                directory = open_directory(READ_ONLY, root)
            try:
                descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            except FileNotFoundError:
                raise ValueError(f'{name} is not in the {area}') from None
            except OSError:
                raise ValueError(f'{name} is not a regular file') from None
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_DOWNLOAD:
                    raise ValueError(f'downloads are single regular files of at most {MAX_DOWNLOAD} bytes')
                content = runtime.read_bounded(descriptor, limit=MAX_DOWNLOAD)
            finally:
                os.close(descriptor)
        finally:
            if directory != root:
                os.close(directory)
            os.close(root)
        if len(content) > MAX_DOWNLOAD:
            raise ValueError(f'downloads are limited to {MAX_DOWNLOAD} bytes')
        document = (content.startswith(b'%PDF-') or content.startswith(b'\x89PNG\r\n\x1a\n')
                    or content.startswith(b'\xff\xd8\xff'))
        if not document:
            if Path(name).suffix.lower() not in TEXT_SUFFIXES:
                raise ValueError('downloads expose PDF, PNG and JPEG documents and text documents with the suffixes '
                                 + ', '.join(sorted(TEXT_SUFFIXES)))
            try:
                content.decode('utf-8')
            except UnicodeDecodeError:
                raise ValueError('text documents must be UTF-8') from None
            if b'\x00' in content:
                raise ValueError('text documents must not contain NUL bytes')
        return {'area': area, 'name': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                'body_base64': base64.b64encode(content).decode()}

    def clipboard_text(self, target='UTF8_STRING'):
        raw = self.ui.clipboard(target, CLIPBOARD_TEXT)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the clipboard text is not UTF-8') from None
        text = self.private_text(text)[0]
        return {'text': text, 'characters': len(text)}

    def clipboard_html(self):
        value = self.clipboard_text('text/html')
        return {'html': value['text'], 'characters': value['characters']}

    def clipboard_image(self):
        raw = self.ui.clipboard('image/png', CLIPBOARD_IMAGE)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) < 24:
            raise ValueError('the clipboard holds no PNG image')
        width, height = int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
        return {'png_base64': base64.b64encode(raw).decode(), 'mime_type': 'image/png', 'width': width, 'height': height}

    # HTTP -----------------------------------------------------------------------------------------------------
    def api_path(self, value):
        if not isinstance(value, str) or not value.startswith('/') or len(value) > 8000:
            raise ValueError('path must be an absolute product path of at most 8000 characters')
        if any(ord(c) < 33 or ord(c) == 127 for c in value) or '#' in value:
            raise ValueError('path must not contain spaces, control characters or a fragment')
        parts = urllib.parse.urlsplit(value)
        if parts.scheme or parts.netloc:
            raise ValueError('path must be a product path, not a URL')
        decoded = urllib.parse.unquote(parts.path, errors='strict')
        segments = decoded.split('/')
        if '..' in segments or '.' in segments or '\\' in decoded:
            raise ValueError('path must not contain dot segments')
        if not (decoded.startswith('/api/') or decoded == '/connector/ping'):
            raise Refused('HTTP access reaches the local API under /api/ and /connector/ping only')
        return value

    def http_request(self, method, path, body, headers, timeout):
        connection = http.client.HTTPConnection('127.0.0.1', self.config.port, timeout=timeout)
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            content = response.read(API_BODY + 1)
            return {'status': response.status, 'headers': {k.lower(): v for k, v in response.getheaders()},
                    'bytes': content}
        finally:
            connection.close()

    def check_writes(self, value):
        """Attachment paths written through the API must lie in the exchange folders."""
        if isinstance(value, str):
            # A JSON MIME body may decode to a string which the endpoint parses once more.
            try:
                value = runtime.strict_json_loads(value)
            except json.JSONDecodeError:
                return
            self.check_writes(value)
            return
        if isinstance(value, list):
            for entry in value:
                self.check_writes(entry)
            return
        if not isinstance(value, dict):
            return
        if self.guard_content.enabled:
            check_note(value.get('note'))
        for child in value.values():
            if isinstance(child, (dict, list)):
                self.check_writes(child)
        path = value.get('path')
        if path is not None:
            if not isinstance(path, str) or not path:
                return
            if path.startswith('attachments:'):
                if '..' in Path(path[len('attachments:'):]).parts:
                    raise Refused('attachment paths must not leave their base folder')
            elif not (path.startswith('/') and '..' not in Path(path).parts and self.inside(path)):
                raise Refused('attachment paths must be absolute paths in the inbox or the outbox: '
                              f'{self.areas["inbox"]} or {self.areas["outbox"]}')

    def api(self, data):
        path = self.api_path(data['path'])
        method = data.get('method', 'GET')
        bodies = [key for key in ('json', 'body', 'body_base64', 'form') if key in data]
        if len(bodies) > 1:
            raise ValueError('give at most one of json, body, body_base64 and form')
        headers = {}
        for key, value in (data.get('headers') or {}).items():
            if not isinstance(key, str) or key.lower() not in API_HEADERS:
                raise ValueError(f'header {str(key)[:40]} is not allowed')
            if not isinstance(value, (str, int)) or any(c in str(value) for c in '\r\n\x00'):
                raise ValueError(f'header {key} must be a single-line value')
            headers[key] = str(value)
        body = None
        content_type = data.get('content_type')
        if 'json' in data:
            body = json.dumps(data['json'], ensure_ascii=False).encode()
            content_type = content_type or 'application/json'
            if method in ('POST', 'PUT', 'PATCH'):
                self.check_writes(data['json'])
        elif 'body' in data:
            body = data['body'].encode()
        elif 'body_base64' in data:
            try:
                body = base64.b64decode(data['body_base64'], validate=True)
            except Exception:
                raise ValueError('body_base64 is invalid') from None
        elif 'form' in data:
            form = data['form']
            if not all(isinstance(k, str) and isinstance(v, (str, int, float, bool)) for k, v in form.items()):
                raise ValueError('form values must be strings or numbers')
            if method in ('POST', 'PUT', 'PATCH'):
                self.check_writes(form)
            body = urllib.parse.urlencode({k: str(v) for k, v in form.items()}).encode()
            content_type = content_type or 'application/x-www-form-urlencoded'
        if body is not None and len(body) > API_BODY:
            raise ValueError(f'request bodies are limited to {API_BODY} bytes')
        if body is not None and urllib.parse.urlsplit(path).path.startswith('/api/local/uploads/'):
            vet_incoming_document('', body)
        if body is not None and method in ('POST', 'PUT', 'PATCH') and not any(k in data for k in ('json', 'form')):
            # The local API also parses JSON carried as text, independently of its MIME type.
            # Malformed bodies remain product observations; decoded objects use the same boundary.
            try:
                decoded = runtime.strict_json_loads(body)
            except (json.JSONDecodeError, UnicodeError):
                if (content_type or '').split(';')[0].strip().lower() == 'application/x-www-form-urlencoded':
                    try:
                        fields = urllib.parse.parse_qsl(body.decode('utf-8'), keep_blank_values=True,
                                                        max_num_fields=1000, errors='strict')
                    except (ValueError, UnicodeError):
                        pass
                    else:
                        self.check_writes(dict(fields))
            else:
                self.check_writes(decoded)
        if content_type is not None:
            if not isinstance(content_type, str) or any(c in content_type for c in '\r\n\x00'):
                raise ValueError('content_type must be a single-line value')
            headers['Content-Type'] = content_type
        timeout = data.get('timeout', API_TIMEOUT)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
            raise ValueError('timeout must be 1-120 seconds')
        headers['Host'] = f'127.0.0.1:{self.config.port}'
        try:
            answer = self.http_request(method, path, body, headers, timeout)
        except socket.timeout:
            raise desktop.DesktopError(f'the product did not answer within {timeout:g} s', timeout=True) from None
        except (ConnectionError, OSError, http.client.HTTPException) as exc:
            raise ValueError(f'the product\'s local server is not reachable ({type(exc).__name__})') from None
        content = answer['bytes']
        truncated = len(content) > API_BODY
        content = content[:API_BODY]
        text = content.decode('utf-8', errors='replace')
        text, redacted = self.private_text(text)
        kind = answer['headers'].get('content-type', '')
        body_value = text
        if 'json' in kind:
            try:
                body_value = json.loads(text)
            except ValueError:
                pass
        result_headers = {name: self.private_text(answer['headers'][name])[0] for name in RESPONSE_HEADERS
                          if name in answer['headers']}
        result = {'status': answer['status'], 'headers': result_headers, 'body': body_value, 'truncated': truncated}
        if data.get('binary'):
            if redacted:
                if kind.lower().startswith('text/') or any(part in kind.lower() for part in ('json', 'xml')):
                    content = text.encode('utf-8')
                else:
                    raise Refused('the binary response contains a private file location')
            result['body_base64'] = base64.b64encode(content).decode()
        return result

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
        """Private filesystem locations leave observations; in a tree the whole subtree of a redacted node goes.
        Returns the observation and the screen boxes of redacted nodes."""
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

    def refused_windows(self, view):
        return [w for w in view.get('windows', []) if REFUSED_WINDOWS.search(w.get('title') or '')]

    def close_refused(self):
        """Close windows of refused features (they may open through routes other than their menu items)."""
        try:
            windows = self.ui.windows()
        except desktop.DesktopError:
            return False
        closed = False
        for window in windows:
            if REFUSED_WINDOWS.search(window.get('title') or ''):
                try:
                    self.ui.act({'op': 'focus_window', 'window': window['ref']})
                    self.ui.act({'op': 'press', 'key': 'Escape'})
                    self.ui.act({'op': 'press', 'key': 'Control+w'})
                except desktop.DesktopError:
                    pass
                closed = True
        return closed

    @staticmethod
    def menu_open(by_ref, node):
        """Whether a menu entry is on an open menu: Gecko keeps the entries of closed menus in the accessibility tree,
        so the nearest enclosing menu must be expanded."""
        parent, seen = by_ref.get(node.get('parent')), set()
        while parent is not None and parent['ref'] not in seen:
            seen.add(parent['ref'])
            if parent['role'] in ('menu', 'popup menu'):
                return 'expanded' in parent.get('states', ()) or parent['role'] == 'popup menu'
            parent = by_ref.get(parent.get('parent'))
        return False

    @staticmethod
    def handler_choice(links):
        """Whether a chain (control first, then its ancestors) is an external-application choice of an "Open ... using"
        setting."""
        names = [label(link.get('name')) for link in links]
        return bool(names) and names[0] in HANDLER_CHOICES and any(
            link.get('role') == 'combo box' and OPEN_WITH.match(name) for link, name in zip(links, names))

    @staticmethod
    def ancestors(by_ref, node):
        chain, seen = [node], {node['ref']}
        while chain[-1].get('parent') in by_ref and chain[-1]['parent'] not in seen:
            seen.add(chain[-1]['parent'])
            chain.append(by_ref[chain[-1]['parent']])
        return chain

    def guard_features(self, op, data, key, nodes, chain):
        """Refuse menu items and buttons of the refused features, by pointer, accessible action or keyboard."""
        names = [label(link.get('name')) for link in chain or ()]
        if op in ('click', 'activate', 'check', 'drag') and chain and (
                any(name in REFUSED_LABELS for name in names[:2]) or self.handler_choice(chain)):
            raise Refused(REFUSAL)
        if op != 'press':
            return
        by_ref = {n['ref']: n for n in nodes}
        refused = [n for n in nodes if label(n.get('name')) in REFUSED_LABELS
                   or (label(n.get('name')) in HANDLER_CHOICES and self.handler_choice(self.ancestors(by_ref, n)))]
        shown = [n for n in refused if n['role'] not in MENU_ROLES or self.menu_open(by_ref, n)]
        focused = [n for n in shown if {'focused', 'selected'} & set(n.get('states', ()))]
        if focused and key in MENU_KEYS:
            raise Refused(REFUSAL)
        if any(n['role'] in MENU_ROLES for n in shown) and key not in MENU_NAVIGATION and key not in MENU_KEYS:
            raise Refused('while a menu with unavailable features is open, use the pointer or the arrow keys')
        active = {n['ref'] for n in nodes if n.get('depth') == 1 and 'active' in n.get('states', ())}
        handlers = [n for n in nodes if n['role'] == 'combo box' and OPEN_WITH.match(label(n.get('name')))
                    and n.get('window') in active]
        if key in ('ctrl+w', 'alt+F4'):
            return
        if any('expanded' in n.get('states', ()) for n in handlers) and key != 'Escape' or key not in (
                'Tab', 'shift+Tab', 'Escape') and any('focused' in n.get('states', ()) for n in handlers):
            raise Refused('the application opening this file type can only be chosen with the pointer, and only the '
                          'built-in viewer is available')

    def guard_pointer(self, event):
        """Check implicit clicks and every drag endpoint without performing input."""
        pointer = event['pointer']
        self.guard(pointer, pointer_only=True)
        if pointer['op'] == 'drag':
            destinations = []
            if pointer.get('to_target') is not None:
                destinations.append({'op': 'click', 'target': pointer['to_target']})
            elif 'to_x' in pointer and 'to_y' in pointer:
                destinations.append({'op': 'click', 'x': pointer['to_x'], 'y': pointer['to_y']})
            destinations.extend({'op': 'click', 'x': point[0], 'y': point[1]} for point in pointer.get('via', []))
            for destination in destinations:
                self.guard(destination, pointer_only=True)

    def guard(self, data, pointer_only=False):
        """Refuse inputs that would leave the exchange folders through a file dialog or reach a refused feature."""
        op = data['op']
        if op in ('wait', 'zoom', 'focus_window', 'maximize', 'move', 'scroll'):
            return
        view = self.ui.inspect()
        nodes = view['nodes']
        key = desktop.keysym(data['key']) if op == 'press' else None
        chain = self.target(data, view)
        self.guard_features(op, data, key, nodes, chain)
        if not any(n['role'] == 'file chooser' for n in nodes):
            return
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
        confirming = (op == 'press' and key in ('Return', 'KP_Enter', 'space')) or (
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
                              f'{self.areas["outbox"]}/library.bib (Ctrl+L opens the location field of an Open dialog)')

    def output(self, function, *args):
        """An observation, copy or download: refused while a refused window is open or the library holds private
        content (checked before and after producing it)."""
        if self.ui is not None and self.close_refused():
            raise Refused('a window of an unavailable feature was open and has been closed; observe again')
        self.guard_content.check()
        value = function(*args)
        self.guard_content.check()
        return value

    # Dispatch -------------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=LIMITS, notes=self.notes(),
                                         examples=examples(self.areas['inbox']), api_key=API_KEY)
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
                return self.output(self.download, data)
            if op == 'api':
                return self.output(self.api, data)
            if self.ui is None:
                raise ValueError('the desktop is not available; use reset')
            if op == 'observe':
                tree = bool(data.get('tree'))
                return self.output(lambda: self.public(self.ui.observe(tree), tree)[0])
            if op == 'screenshot':
                return self.output(self.screenshot, data)
            if op == 'windows':
                def windows():
                    found = self.ui.windows()
                    for window in found:
                        window['title'] = self.private_text(window.get('title', ''))[0]
                    return {'windows': found}
                return self.output(windows)
            if op == 'clipboard_text':
                return self.output(self.clipboard_text)
            if op == 'clipboard_html':
                return self.output(self.clipboard_html)
            if op == 'clipboard_image':
                return self.output(self.clipboard_image)
            self.guard_content.check()
            self.guard(data)
            result = self.ui.act(data)
            self.close_refused()
            return result

    def notes(self):
        return [f'Exchange folders: inbox {self.areas["inbox"]} (uploads) and outbox {self.areas["outbox"]} (save '
                'outputs there to download them). The product sees them as ordinary folders.',
                'File dialogs are standard file choosers (accessible role "file chooser"); inside them, files are named '
                'by typed absolute paths in the inbox and outbox (Ctrl+L opens the location field of an Open dialog; '
                'the name field of a Save dialog accepts a full path), places and path-bar folders elsewhere are '
                'refused, and a dialog confirms only inside the exchange folders. Other dialogs receive text as typed.',
                'The product\'s local HTTP server listens on PORT. Op api sends one request to it: the local Web API '
                'under /api/ and GET /connector/ping. Write requests need the local API key (api_key; the runtime '
                'grants it to the product as PBP_API_KEY) in the Zotero-API-Key header and the server ID of an earlier '
                'response in the Zotero-Server-ID header. Attachment paths written through it must lie in the inbox '
                'or the outbox.',
                'Plugins, the developer tools, the configuration editor, diagnostics, printing and opening files with '
                'external applications are not available; '
                'their menu items are refused and their windows are closed.',
                'On the reference installation, notes allow static rich text and web or library-item links only. '
                'Snapshot, SVG, EPUB and archived attachments are unavailable. A library containing private or '
                'active content refuses observations and downloads until reset.',
                'GUI operations answer briefly; observe and screenshot show the new state. Refs stay valid until the '
                'next observe; object targets are matched against a fresh snapshot.',
                'Product errors and dialogs are observations; a refused request answers 400 with the reason.',
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
