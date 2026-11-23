#!/usr/bin/env python3
"""Money Manager Ex desktop runtime.

Runs one application with a private X11 session and bounded document exchange.
The same operations serve the reference installation and a local application.
Input validation and observations are defined by the runtime help.
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
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'Money Manager Ex'
SCREEN = (1280, 1024)
MAX_UPLOAD = 20 * 1024 * 1024
MAX_DOWNLOAD = 50 * 1024 * 1024
MAX_REQUEST = (MAX_UPLOAD * 4 + 2) // 3 + 65_536
MAX_FILES = 128
CLIPBOARD_TEXT = 400_000
RPC_TIMEOUT = 150
SAMPLES = '/app/samples'
# Uploaded files carry one fixed modification time (2024-01-01 00:00 UTC), so file dialogs list them the same way in
# every session.
UPLOAD_TIME = 1704067200
# The wall clock of the product starts at this instant on every start and then runs normally.
CLOCK = '2026-06-15 12:00:00'
FAKETIME_LIBRARY = '/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1'
UPLOAD_TYPES = {'.mmb', '.bak', '.csv', '.tsv', '.txt', '.qif', '.ofx', '.qfx', '.xml', '.json', '.png', '.jpg', '.jpeg',
                '.gif', '.pdf'}
DATABASE_TYPES = {'.mmb', '.emb', '.bak'}
DOWNLOAD_TYPES = UPLOAD_TYPES | {'.emb', '.html', '.htm'}
# Windows closed as soon as they appear: printing leaves the exchange folders, the report manager runs scripts, the
# diagnostics show the machine, the debug file dialog runs SQL files.
CLOSED_WINDOWS = {'general reports manager': 'The General Report Manager (report scripts) is not available',
                  'general report manager': 'The General Report Manager (report scripts) is not available',
                  'print': 'Printing is not available', 'page setup': 'Printing is not available',
                  'diagnostics': 'The diagnostics window is not available',
                  'load debug file': 'Debug files are not available',
                  'theme manager': 'Loading theme packages is not available'}
CLOSED_MENU_ITEMS = {'general report manager…': CLOSED_WINDOWS['general reports manager'], 'print…': CLOSED_WINDOWS['print'],
                     'view diagnostics': CLOSED_WINDOWS['diagnostics']}
EDIT_ROLES = {'text', 'entry', 'password text', 'spin button', 'terminal'}
PASTE_KEYS = {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
# Keys that produce an opening angle bracket or start a character-code entry.
REFUSED_KEYS = {'less', 'shift+comma', 'shift+less', 'ctrl+shift+u'}
# Keys accepted while a file dialog is open: moving between its controls, editing text, confirming or leaving it.
CHOOSER_KEYS = {'ctrl+l', 'ctrl+a', 'ctrl+c', 'ctrl+x', 'ctrl+v', 'ctrl+shift+v', 'shift+Insert', 'Return', 'KP_Enter', 'Escape',
                'Tab', 'shift+Tab', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'BackSpace', 'Delete', 'space',
                'Prior', 'Next', 'shift+Up', 'shift+Down', 'ctrl+Up', 'ctrl+Down'}
AFFIRMATIVE = {'open', 'save', 'select', 'export', 'ok', 'import', 'insert', 'add', 'choose'}
MARKUP = re.compile(r'<[A-Za-z/!?]')
# Markup that a document can carry inside its values: entity-encoded angle brackets and active HTML elements.
HTML_ELEMENT = re.compile(r'<\s*/?\s*(?:script|iframe|object|embed|img|svg|link|style|meta|base|video|audio|form|input|'
                          r'button|frame|frameset|applet|math|marquee|details|source|track|template|body|html|head|a)\b',
                          re.I)
ENCODED_MARKUP = re.compile(r'&(?:lt|#0*60|#x0*3c);|<!\[CDATA\[', re.I)
# An absolute path in free text: a slash that does not continue a word, a number or a URL.
ABSOLUTE_PATH = re.compile(r'(?<![\w:/.%-])/[^\s\'"<>()\[\]{},;]*')
PARENT_PATH = re.compile(r'(?:^|[\s/\\])\.\.[/\\]')
HOME_PATH = re.compile(r'(?:^|\s)~[\w-]*/')

AREA = {'type': 'string', 'enum': ['inbox', 'outbox'], 'description': 'Exchange folder; default outbox.'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Start over: a new desktop session, empty inbox and outbox, and the product with an empty '
                         'data directory (its initial state) and no database.'},
    'restart': {'kind': 'lifecycle',
                'summary': 'Start the product again with the same data directory, desktop session and exchange '
                           'folders (for example after quitting it through its own controls). With database, the product '
                           'opens that file when it starts, as with a database file on its command line, and on later '
                           'restarts until another one is named.',
                'fields': {'database': {'type': 'string',
                                        'description': 'Base name of a file in the inbox, or an absolute path inside the '
                                                       'exchange folders; empty for none.'}}},
    **desktop.operations(SCREEN),
    'list_files': {'kind': 'files', 'summary': 'Ordinary files in the inbox or outbox (name, size, path). With recursive, includes document subfolders, without following links.',
                   'fields': {'area': AREA, 'recursive': {'type': 'boolean', 'description': 'Include up to eight levels of document subfolders; default false.'}}},
    'upload': {'kind': 'files', 'summary': 'Store one document in the inbox (default) or the outbox. Uploaded files get '
               'the modification time 2024-01-01 00:00 UTC. Accepted types: ' + ', '.join(sorted(UPLOAD_TYPES)) +
               '. Database files (.mmb, .bak) must be plain SQLite files with tables and indexes only and without '
               'general reports; no document may carry HTML markup in its values.',
               'fields': {'filename': {'type': 'string', 'required': True,
                                       'description': 'Base name (no folders, not hidden), at most 240 bytes.'},
                          'base64': {'type': 'string', 'required': True,
                                     'description': f'File bytes, base64 encoded; at most {MAX_UPLOAD} bytes, '
                                                    'empty files allowed.'},
                          'area': dict(AREA, description='Exchange folder; default inbox.')}},
    'download': {'kind': 'files', 'summary': 'Retrieve one database, text, image or PDF document from the outbox (or the '
                 'inbox) as body_base64. Plain SQLite documents are consistent snapshots including committed WAL data, even while open. Encrypted documents are returned unchanged.',
                 'fields': {'filename': {'type': 'string', 'required': True, 'description': 'Relative document path within the selected area, up to eight folders; no links or dot segments.'},
                            'area': AREA}},
    'clipboard_text': {'kind': 'observe', 'summary': 'The plain text on the desktop clipboard (UTF-8, at most '
                       f'{CLIPBOARD_TEXT} bytes).', 'fields': {}},
})
LIMITS = {'upload_bytes': MAX_UPLOAD, 'download_bytes': MAX_DOWNLOAD, 'files_per_area': MAX_FILES,
          'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_TIMEOUT, 'screen': list(SCREEN)}


def examples(inbox):
    """Request examples for help; the typed path names this runtime's own inbox."""
    return [{'op': 'observe'}, {'op': 'screenshot'}, {'op': 'click', 'target': 'e5a450812'},
            {'op': 'click', 'target': {'role': 'menu', 'name': 'Tools'}}, {'op': 'click', 'x': 90, 'y': 145},
            {'op': 'press', 'key': 'F9'}, {'op': 'type', 'value': f'{inbox}/ledger.mmb'},
            {'op': 'zoom', 'x': 0, 'y': 40, 'to_x': 640, 'to_y': 400},
            {'op': 'restart', 'database': 'ledger.mmb'}, {'op': 'list_files', 'area': 'outbox'},
            {'op': 'download', 'filename': 'saved.csv'}]


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


def document_parent(folder, name):
    """Resolve a relative document path using pinned directory handles."""
    if not isinstance(name, str) or name.startswith('/') or len(name.encode()) > 1800:
        raise ValueError('document path must be relative to the exchange area')
    parts = name.split('/')
    if not 1 <= len(parts) <= 9:
        raise ValueError('document path has too many folders')
    for part in parts:
        safe_name(part)
    fd = open_directory(folder)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except OSError:
        os.close(fd)
        raise ValueError('document parent must be a regular exchange folder') from None


def read_regular_at(directory, name, maximum=MAX_DOWNLOAD):
    """Read a bounded single file without following links; return bytes and identity."""
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None, None
    except OSError:
        raise ValueError('document must be a regular file') from None
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink > 1 or before.st_size > maximum:
            raise ValueError('document must be one bounded regular file')
        if before.st_nlink == 0:
            # A committing writer may unlink its journal between open and
            # fstat. Treat this generation as changed, so snapshots retry.
            return b'', False
        content = bytearray()
        while len(content) <= maximum:
            chunk = os.read(fd, min(1 << 20, maximum + 1 - len(content)))
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > maximum:
            raise ValueError('document exceeds the download size limit')
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        after = os.fstat(fd)
        return bytes(content), identity(before) if identity(before) == identity(after) else False
    finally:
        os.close(fd)


def sqlite_snapshot(directory, name):
    """Copy a stable main/WAL generation, then let SQLite produce an atomic backup.

    SQLite only opens broker-owned temporary copies. Application-controlled
    paths, sidecar names, views and extensions are never opened or executed by
    SQLite in the broker. A write during the copy causes a retry.
    """
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        copies, identities = {}, {}
        for suffix in ('', '-wal', '-journal'):
            content, identity = read_regular_at(directory, name + suffix)
            copies[suffix], identities[suffix] = content, identity
        stable = True
        for suffix, identity in identities.items():
            try:
                s = os.stat(name + suffix, dir_fd=directory, follow_symlinks=False)
                current = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            except FileNotFoundError:
                current = None
            stable = stable and identity is not False and identity == current
        if not stable:
            time.sleep(.02)
            continue
        journal=copies['-journal']
        if journal and any(journal[:8]):
            # Wait for a rollback-mode writer to commit. Recovery journals may
            # name other databases, so the broker never replays one.
            time.sleep(.02)
            continue
        if copies[''] is None:
            raise ValueError('database disappeared during download')
        with tempfile.TemporaryDirectory(prefix='snapshot-') as temporary:
            source = Path(temporary) / 'document.mmb'
            for suffix in ('','-wal'):
                content=copies[suffix]
                if content is not None:
                    Path(str(source) + suffix).write_bytes(content)
            db = target = None
            try:
                db = sqlite3.connect(str(source), timeout=1)
                db.execute('PRAGMA trusted_schema=OFF')
                target_path = Path(temporary) / 'snapshot.mmb'
                target = sqlite3.connect(str(target_path))
                def progress(status, remaining, total):
                    if time.monotonic() >= deadline or total * 4096 > MAX_DOWNLOAD * 2:
                        raise ValueError('database snapshot exceeded its limit')
                db.backup(target, pages=256, progress=progress, sleep=.01)
                target.execute('PRAGMA journal_mode=DELETE')
                target.close(); target = None
                result = target_path.read_bytes()
                if len(result) > MAX_DOWNLOAD:
                    raise ValueError('database snapshot exceeds the download size limit')
                return result
            except sqlite3.Error:
                raise ValueError('database could not be read consistently') from None
            finally:
                if target is not None:
                    target.close()
                if db is not None:
                    db.close()
    raise ValueError('database is busy; retry download')


def vet_database(content):
    """A database document: plain SQLite with tables and indexes only, no general reports, no markup, no foreign paths."""
    if content and not content.startswith(b'SQLite format 3\x00'):
        raise Refused('database documents must be plain SQLite files; encrypted databases are made by the product')
    if not content:
        return
    with tempfile.TemporaryDirectory(prefix='vet-') as folder:
        path = Path(folder) / 'document.sqlite'
        path.write_bytes(content)
        try:
            db = sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)
        except sqlite3.Error:
            raise Refused('the database document could not be read') from None
        try:
            db.execute('PRAGMA trusted_schema=OFF')
            db.text_factory = lambda raw: raw.decode('utf-8', 'replace')
            tables = []
            for kind, name in db.execute('SELECT type, name FROM sqlite_master').fetchall():
                if kind not in ('table', 'index'):
                    raise Refused('database documents hold tables and indexes only')
                if kind == 'table':
                    tables.append(name)
            for name in tables:
                quoted = '"' + name.replace('"', '""') + '"'
                if name.upper() == 'REPORT_V1' and db.execute(f'SELECT COUNT(*) FROM {quoted}').fetchone()[0]:
                    raise Refused('database documents cannot carry general reports')
                for row in db.execute(f'SELECT * FROM {quoted}'):
                    for value in row:
                        if isinstance(value, bytes):
                            value = value.decode('utf-8', 'replace')
                        if isinstance(value, str) and (MARKUP.search(value) or ENCODED_MARKUP.search(value)):
                            raise Refused('database documents cannot carry markup in their values')
                if name.upper() == 'INFOTABLE_V1':
                    for key, value in db.execute(f'SELECT INFONAME, INFOVALUE FROM {quoted}'):
                        if str(key).upper().startswith('ATTACHMENTSFOLDER') and value not in ('', None):
                            raise Refused('database documents cannot name an attachments folder')
        except sqlite3.Error:
            raise Refused('the database document could not be read') from None
        finally:
            db.close()


def vet_document(name, content):
    """Documents the product can import reach its web views as values; they may not bring markup or scripts along."""
    suffix = Path(name).suffix.lower()
    if '.emb' in name.lower():
        raise Refused('encrypted databases are made by the product, not uploaded')
    if suffix not in UPLOAD_TYPES:
        raise Refused('this file type is not accepted; accepted types: ' + ', '.join(sorted(UPLOAD_TYPES)))
    if suffix in ('.mmb', '.bak'):
        vet_database(content)
    elif suffix in ('.csv', '.tsv', '.txt', '.qif', '.json'):
        text = content.decode('utf-8', 'replace')
        if MARKUP.search(text) or ENCODED_MARKUP.search(text):
            raise Refused('this document carries markup in its values')
    elif suffix in ('.xml', '.ofx', '.qfx'):
        text = content.decode('utf-8', 'replace')
        if HTML_ELEMENT.search(text) or ENCODED_MARKUP.search(text) or re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.I):
            raise Refused('this document carries markup in its values')


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
        self.database = ''
        self.dialog_ids = {}
        self.moved = False
        roots = [config.solution, config.state, config.work, config.log_dir, str(Path(__file__).resolve().parent),
                 '/app/solution', '/opt', '/proc', '/sys', '/root', '/etc', '/home', '/usr', '/var', '/srv', '/tests',
                 '/logs', '/model', '/tmp', '/run', '/bin', '/lib', '/sbin', '/dev', '/mnt', '/media', '/boot']
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

    def product_environment(self):
        return dict(self.session.env(), PBP_INBOX=str(self.areas['inbox']), PBP_OUTBOX=str(self.areas['outbox']),
                    PBP_DATABASE=self.database, PBP_SAMPLES=SAMPLES, LD_PRELOAD=FAKETIME_LIBRARY, FAKETIME='@' + CLOCK,
                    FAKETIME_DONT_FAKE_MONOTONIC='1', NO_FAKE_STAT='1',
                    WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS='1')

    def start_session(self):
        self.session = desktop.DesktopSession(user=self.config.user, screen=SCREEN, log_dir=self.config.log_dir).start()
        self.ui = desktop.Desktop(self.session, log_dir=self.config.log_dir, pointer_guard=self.guard_pointer)
        self.dialog_ids = {}

    def stop_session(self):
        for item in (self.ui, self.session):
            try:
                if item is not None:
                    item.close()
            except Exception as exc:
                self.log.note(f'desktop teardown: {type(exc).__name__}: {exc}')
        self.ui = self.session = None

    def launch(self, fresh):
        self.product.extra = self.product_environment()
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
            return self.launch(fresh=True)

    def reset(self):
        with self.lock:
            self.product.stop()
            self.stop_session()
            self.prepare_areas(clear=True)
            self.database = ''
            self.start_session()
            return self.launch(fresh=True)

    def database_path(self, value):
        """The database a restart names: an inbox base name or a path inside the exchange folders."""
        if not value:
            return ''
        path = value if value.startswith('/') else str(self.areas['inbox'] / safe_name(value))
        path = os.path.normpath(path)
        if not self.inside(path) or len(Path(path).relative_to(self.files).parts) != 2:
            raise Refused('database names a file directly in the inbox or the outbox')
        if Path(path).is_symlink() or not Path(path).is_file():
            raise ValueError(f'{Path(path).name} is not in the exchange folders')
        return path

    def restart(self, data):
        with self.lock:
            if 'database' in data:
                self.database = self.database_path(data['database'])
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
        def visit(directory, prefix='', depth=0):
            for entry in sorted(os.listdir(directory)):
                if len(result) >= MAX_FILES:
                    break
                try:
                    safe_name(entry)
                    info = os.stat(entry, dir_fd=directory, follow_symlinks=False)
                except OSError:
                    continue
                except ValueError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    result.append({'name': prefix + entry, 'size': info.st_size, 'path': str(folder / (prefix + entry))})
                elif data.get('recursive') and stat.S_ISDIR(info.st_mode) and depth < 8:
                    try:
                        child = os.open(entry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                    except OSError:
                        continue
                    try:
                        visit(child, prefix + entry + '/', depth + 1)
                    finally:
                        os.close(child)
        try:
            visit(root)
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
        vet_document(name, content)
        area, folder = self.area(data, 'inbox')
        listed = self.list_files({'area': area})['files']
        if len(listed) >= MAX_FILES and not any(f['name'] == name for f in listed):
            raise ValueError(f'the {area} holds at most {MAX_FILES} files; use reset to empty the exchange folders')
        root = open_directory(folder)
        try:
            try:
                info = os.stat(name, dir_fd=root, follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the destination must be one regular file')
            except FileNotFoundError:
                pass
            runtime.atomic_write(root, name, content, uid=self.account.pw_uid, gid=self.account.pw_gid, mode=0o644)
            with runtime.open_relative(root, name) as descriptor:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError('the uploaded file changed during setup')
                runtime.set_metadata(descriptor, ns=(UPLOAD_TIME * 1_000_000_000,) * 2)
        finally:
            os.close(root)
        return {'area': area, 'name': name, 'path': str(folder / name), 'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest()}

    def download(self, data):
        name = data['filename']
        area, folder = self.area(data, 'outbox')
        root, leaf = document_parent(folder, name)
        try:
            content, identity = read_regular_at(root, leaf)
            if content is None:
                raise ValueError(f'{name} is not in the {area}') from None
            if content.startswith(b'SQLite format 3\x00'):
                content = sqlite_snapshot(root, leaf)
            elif identity is False:
                raise ValueError('document changed while reading; retry download')
        finally:
            os.close(root)
        if len(content) > MAX_DOWNLOAD:
            raise ValueError(f'downloads are limited to {MAX_DOWNLOAD} bytes')
        self.vet_download(name, content)
        return {'area': area, 'name': name, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                'body_base64': base64.b64encode(content).decode()}

    @staticmethod
    def vet_download(name, content):
        """Databases, images, PDF and text; never executables or other binary files."""
        if Path(name).suffix.lower() not in DOWNLOAD_TYPES:
            raise ValueError('downloads expose database, text, image and PDF documents only')
        if content.startswith((b'\x7fELF', b'MZ', b'PK\x03\x04')):
            raise ValueError('executable files and archives cannot be downloaded')
        if Path(name).suffix.lower() in DATABASE_TYPES or any(
                content.startswith(magic) for magic in (b'SQLite format 3\x00', b'%PDF-', b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff',
                                                        b'GIF8')):
            return
        if b'\x00' in content[:65536] or content.startswith(b'\x7fELF'):
            raise ValueError('downloads expose database, text, image and PDF documents only')

    def clipboard_text(self):
        raw = self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the clipboard text is not UTF-8') from None
        text = self.private_text(text)[0]
        return {'text': text, 'characters': len(text)}

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
        """Private filesystem locations leave observations; in a tree the whole subtree of a redacted node goes. Returns
        the observation and the screen boxes of redacted nodes."""
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

    # Window policy ---------------------------------------------------------------------------------------------
    def x_run(self, args, timeout=5):
        env = {'DISPLAY': self.session.display, 'PATH': os.environ.get('PATH', '/usr/bin:/bin')}
        return subprocess.run(args, env=env, capture_output=True, text=True, timeout=timeout)

    def top_windows(self):
        """(id, title) of the managed windows."""
        done = self.x_run(['wmctrl', '-l'])
        result = []
        for line in done.stdout.splitlines():
            fields = line.split(None, 3)
            if len(fields) >= 3:
                result.append((fields[0], fields[3] if len(fields) > 3 else ''))
        return result

    def is_dialog(self, window):
        known = self.dialog_ids.get(window)
        if known is None:
            done = self.x_run(['xprop', '-id', window, '_NET_WM_WINDOW_TYPE'])
            known = self.dialog_ids[window] = '_NET_WM_WINDOW_TYPE_DIALOG' in done.stdout
        return known

    def center_dialog(self, window):
        """Dialogs sit centered on the screen. The window manager centers a new dialog while it is still tiny; the
        toolkit gives it its size afterwards, so the size is taken into account here."""
        info = self.x_run(['xwininfo', '-id', window]).stdout
        numbers = {key: int(value) for key, value in re.findall(r'(Absolute upper-left [XY]|Width|Height):\s+(-?\d+)', info)}
        if len(numbers) != 4:
            return
        extents = self.x_run(['xprop', '-id', window, '_NET_FRAME_EXTENTS']).stdout
        found = re.findall(r'-?\d+', extents)
        left, right, top, bottom = (int(v) for v in found[:4]) if len(found) >= 4 else (0, 0, 0, 0)
        width, height = numbers['Width'] + left + right, numbers['Height'] + top + bottom
        x, y = numbers['Absolute upper-left X'] - left, numbers['Absolute upper-left Y'] - top
        wanted_x, wanted_y = max(0, (SCREEN[0] - width) // 2), max(0, (SCREEN[1] - height) // 2)
        if abs(x - wanted_x) > 1 or abs(y - wanted_y) > 1:
            self.x_run(['wmctrl', '-i', '-r', window, '-e', f'0,{wanted_x},{wanted_y},-1,-1'])
            time.sleep(.1)
            self.moved = True

    def police_windows(self):
        """Close windows that are not available and center dialogs; returns the reason when a window was closed."""
        if self.session is None or not self.session.alive():
            return None
        reason = None
        try:
            for window, title in self.top_windows():
                closed = CLOSED_WINDOWS.get(title.strip().casefold())
                if closed:
                    reason = closed
                    self.x_run(['wmctrl', '-i', '-c', window])
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline and any(w == window for w, _ in self.top_windows()):
                        time.sleep(.05)
                elif self.is_dialog(window):
                    self.center_dialog(window)
        except (OSError, subprocess.SubprocessError) as exc:
            self.log.note(f'window policy: {type(exc).__name__}')
        return reason

    def police_text(self, nodes):
        """Text fields never keep a private path or markup: entered piece by piece or pasted, it is removed at once."""
        for node in nodes:
            states = node.get('states', ())
            if node['role'] in EDIT_ROLES and 'editable' in states and 'focused' in states and self.bad_text(node.get('text') or ''):
                x, y, width, height = node['bounds']
                self.ui.act({'op': 'click', 'x': x + width // 2, 'y': y + height // 2})
                self.ui.act({'op': 'press', 'key': 'Control+a'})
                self.ui.act({'op': 'press', 'key': 'BackSpace'})
                raise Refused('this text cannot be entered here: paths outside the exchange folders and markup are removed')

    def bad_text(self, value):
        if (MARKUP.search(value) or ENCODED_MARKUP.search(value) or PARENT_PATH.search(value) or HOME_PATH.search(value)
                or 'file:' in value.lower() or any(alias in value.upper() for alias in ('%DOCUMENTS%', '%USERPROFILE%', '%APPDATA%'))):
            return True
        return any(not self.inside(match.group(0)) for match in ABSOLUTE_PATH.finditer(value))

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

    def check_text(self, value):
        """Text typed anywhere: no markup, no paths outside the exchange folders."""
        if not isinstance(value, str):
            return
        if '<' in re.sub(r'<(?=[\s\d=])', '', value):
            raise Refused('this interface does not accept markup in text (an opening angle bracket before a letter or at '
                          'the end of the text)')
        if self.bad_text(value):
            raise Refused('paths outside the exchange folders cannot be entered')

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
        """Refuse inputs that would leave the exchange folders, open closed windows or bring markup into the product."""
        op = data['op']
        if not pointer_only:
            self.moved = False
            reason = self.police_windows()
            if reason:
                raise Refused(reason)
        if op in ('wait', 'zoom', 'focus_window', 'maximize', 'move', 'scroll'):
            return
        if self.moved:
            raise Refused('a dialog has just been centered on the screen; observe again before acting on it')
        view = self.ui.inspect()
        nodes = view['nodes']
        key = desktop.keysym(data['key']) if op == 'press' else None
        chain = self.target(data, view)
        target = chain[0] if chain else None
        if not pointer_only and op == 'click' and target is not None and target['role'] == 'panel' and 'x' in data and 'y' in data:
            # Drawn toolbars expose their hovered command as the panel's
            # accessible description. Refresh it at the actual click point.
            # Some native toolbars update on motion after the pointer enters.
            # A final one-pixel movement makes the description current even
            # when this is the first pointer entry into the toolbar.
            self.ui.act({'op':'move','x':max(0, data['x']-1),'y':data['y']})
            self.ui.act({'op':'move','x':data['x'],'y':data['y']})
            time.sleep(.6)
            view = self.ui.inspect()
            nodes = view['nodes']
            chain = self.target(data, view)
            target = chain[0] if chain else None
        if op == 'press' and key in REFUSED_KEYS:
            raise Refused('this key is not available: an opening angle bracket or a character code entry')
        if op in ('click', 'activate') and target is not None and target['role'] in ('menu item', 'check menu item'):
            closed = CLOSED_MENU_ITEMS.get((target.get('name') or '').strip().casefold())
            if closed:
                raise Refused(closed)
        if op in ('click', 'activate') and target is not None:
            for label in (target.get('name'), target.get('description')):
                closed = CLOSED_WINDOWS.get((label or '').strip().casefold())
                if closed:
                    raise Refused(closed)
        pasting = (op == 'press' and key in PASTE_KEYS) or (op == 'click' and data.get('button') == 'middle') or (
            op in ('click', 'activate') and target is not None and 'menu item' in target['role']
            and (target.get('name') or '').casefold().startswith('paste'))
        if pasting:
            try:
                text = self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT).decode('utf-8', 'replace')
            except desktop.DesktopError:
                text = ''
            self.check_text(text)
        if not any(n['role'] == 'file chooser' for n in nodes):
            if op in ('type', 'fill'):
                self.check_text(data.get('value'))
            return
        if op in ('type', 'fill'):
            self.check_paths(data.get('value'))
            if MARKUP.search(str(data.get('value'))):
                raise Refused('file names cannot carry markup')
        if op == 'press' and key not in CHOOSER_KEYS:
            raise Refused('in a file dialog only movement, editing, Return, Escape and Ctrl+L keys are available')
        if op == 'drag':
            raise Refused('dragging is not available in a file dialog')
        crumbs, current = self.crumbs(nodes)
        inside_current = current is not None and self.inside(current)
        in_chooser = bool(chain) and any(link['role'] == 'file chooser' for link in chain)
        names = [link.get('name') for link in chain or ()]
        if in_chooser and op in ('click', 'activate', 'check'):
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
                              f'{self.areas["outbox"]}/name.mmb (Ctrl+L opens the location field of an Open dialog)')

    def after(self, data):
        """Close what a GUI operation opened and clean what it entered."""
        reason = self.police_windows()
        if reason:
            raise Refused(reason)
        if data['op'] in ('type', 'fill', 'press', 'click', 'activate'):
            nodes = self.ui.inspect()['nodes']
            if not any(n['role'] == 'file chooser' for n in nodes):
                self.police_text(nodes)

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
                return self.restart(data)
            if op == 'list_files':
                return self.list_files(data)
            if op == 'upload':
                return self.upload(data)
            if op == 'download':
                return self.download(data)
            if self.ui is None:
                raise ValueError('the desktop is not available; use reset')
            if op in ('observe', 'screenshot', 'windows'):
                self.police_windows()
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
            self.guard(data)
            result = self.ui.act(data)
            self.after(data)
            return result

    def notes(self):
        return [f'Exchange folders: inbox {self.areas["inbox"]} (uploads) and outbox {self.areas["outbox"]} (save '
                'outputs there to download them). The product sees them as ordinary folders.',
                f'The wall clock of the product starts at {CLOCK} UTC on every start and then runs normally.',
                'restart with database opens that file at the start of the product (PBP_DATABASE in its environment); '
                'a new database made through the product can be saved in the outbox. Databases stay readable with '
                'download while the product has them open.',
                'File dialogs: in standard file choosers documents are named by typed absolute paths in the inbox and '
                'outbox (Ctrl+L opens the location field of an Open dialog; the name field of a Save dialog accepts a '
                'full path), places and path-bar folders elsewhere are refused, and a dialog confirms only inside the '
                'exchange folders. Other dialogs receive text as typed; text fields do not keep paths outside the '
                'exchange folders.',
                'Dialogs are centered on the screen. Printing, the General Report Manager, Theme Manager and the diagnostics window are '
                'closed as soon as they open; markup in typed text and documents is refused.',
                'GUI operations answer briefly; observe and screenshot show the new state. Refs stay valid until the '
                'next observe; object targets are matched against a fresh snapshot. Submenus open with the Right key or '
                'after the pointer rests on them.',
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
