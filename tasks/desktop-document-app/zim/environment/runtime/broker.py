#!/usr/bin/env python3
"""Zim desktop runtime.

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
import pty
import re
import select
import shlex
import shutil
import signal
import socketserver
import stat
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blackbox_runtime as runtime  # noqa: E402
import blackbox_desktop as desktop  # noqa: E402

PRODUCT = 'Zim'
SCREEN = (1280, 900)
MAX_UPLOAD = 5 * 1024 * 1024
MAX_DOWNLOAD = 8 * 1024 * 1024
MAX_REQUEST = (MAX_UPLOAD * 4 + 2) // 3 + 65_536
MAX_FILES = 1500
MAX_FOLDERS = 5
MAX_ARGS = 24
MAX_ARG = 2000
MAX_OUTPUT = 120_000
CLIPBOARD_TEXT = 400_000
RPC_TIMEOUT = 150
CLI_SECONDS = 120
# Uploaded files carry one fixed modification time (2024-01-01 00:00 UTC).
UPLOAD_TIME = 1704067200
AREAS = ('inbox', 'outbox', 'notebook')
# The wall clock of the product stays at this instant (the monotonic clock keeps running, so timers and autosave work).
CLOCK = '2026-01-15 12:00:00'
FAKETIME_LIBRARY = '/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1'
GIT = {'GIT_AUTHOR_NAME': 'Zim User', 'GIT_AUTHOR_EMAIL': 'zim@example.invalid', 'GIT_COMMITTER_NAME': 'Zim User',
       'GIT_COMMITTER_EMAIL': 'zim@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
TEXT_TYPES = ('.txt', '.md', '.markdown', '.html', '.htm', '.tex', '.rst', '.zim', '.css', '.js', '.svg', '.csv')
IMAGE_TYPES = {'.png': bytes([0x89]) + b'PNG', '.jpg': bytes([0xff, 0xd8, 0xff]), '.jpeg': bytes([0xff, 0xd8, 0xff]),
               '.gif': b'GIF8'}
FORBIDDEN = ' ' + chr(9) + chr(10) + chr(13) + chr(39) + chr(34) + '<>()[]{},;'
PATH_TEXT = re.compile('/[^' + re.escape(FORBIDDEN) + ']*')

EDIT_ROLES = {'text', 'entry', 'password text', 'spin button', 'terminal'}
MENU_ITEMS = {'menu item', 'check menu item', 'radio menu item'}
PASTE_KEYS = {'ctrl+v', 'ctrl+shift+v', 'shift+Insert'}
# Keys accepted while a file dialog is open: moving between its controls, editing text, confirming or leaving it.
CHOOSER_KEYS = {'ctrl+l', 'ctrl+a', 'ctrl+c', 'ctrl+x', 'ctrl+v', 'ctrl+shift+v', 'shift+Insert', 'Return', 'KP_Enter', 'Escape',
                'Tab', 'shift+Tab', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'BackSpace', 'Delete', 'space', 'Prior',
                'Next', 'shift+Up', 'shift+Down', 'ctrl+Up', 'ctrl+Down'}
MENU_KEYS = {'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Return', 'KP_Enter', 'Escape', 'space'}
CONFIRM_KEYS = {'Return', 'KP_Enter', 'space'}
AFFIRMATIVE = {'open', 'save', 'select', 'export', 'ok', 'import', 'insert', 'add', 'choose', 'forward', 'link', 'jump'}
# Controls that start other programs, load code, open manuals or notebooks, or reach places outside the exchange folders.
REFUSED_NAMES = {'open with', 'customize', 'customise', 'open folder', 'open containing folder', 'open attachments folder',
                 'open notebook folder', 'open document root', 'edit source', 'send to', 'print to browser',
                 'view debug log', 'start web server', 'custom tools', 'templates', 'contents', 'faq', 'keybindings',
                 'bugs', 'recent changes', 'open another notebook', 'open plugins folder', 'get more plugins online',
                 'get more templates online', 'set default text editor', 'set default browser', 'add application',
                 'help', 'side by side'}
REFUSED_ROLES = {'menu item', 'check menu item', 'radio menu item', 'push button', 'button', 'link', 'toggle button'}
REFUSED_TABS = {'key bindings', 'applications'}
# Controls that start another program only in one window (window title prefix -> control names): a text editor for a
# settings file, a web browser for printing, a file manager for a folder.
REFUSED_IN_WINDOW = {'insert date and time': {'edit'}, 'insert symbol': {'edit'}, 'tasks': {'print'}, 'file exists': {'browse'}}
REFUSED_PLUGINS = {'command palette', 'print to browser', 'insert screenshot', 'tray icon', 'attachment browser'}
REFUSED_KEYS = {'ctrl+o', 'ctrl+p', 'ctrl+shift+p', 'F1'}
# Dialogs whose text fields take file system paths (typed text is confined to the exchange folders).
PATH_DIALOGS = {'export', 'properties', 'preferences', 'edit link', 'insert link', 'edit image', 'insert text from file', 'insert image',
                'attach file', 'import page', 'save copy'}
IGNORED_DEFAULTS = {'~/Templates'}

# Command line of the product: flags, options with a value, and the number of arguments after the options.
CLI_COMMANDS = {
    'search': ({'-s', '--scores', '-w', '--whole-word', '-c', '--match-case', '--sorted'}, set(), 2, 2),
    'export': ({'-r', '--recursive', '-s', '--singlefile', '-O', '--overwrite'},
               {'-o', '--output', '--format', '--template', '--root-url', '--index-page'}, 1, 2),
    'import': ({'--assubpage'}, {'--format'}, 3, MAX_ARGS),
    'index': ({'-f', '--flush'}, set(), 1, 1),
    'convert-notebook': (set(), {'--format', '--extension'}, 1, 1),
    'version': (set(), set(), 0, 0),
}
BUILTIN_TEMPLATES = {
    'Default', 'Default.html', 'Default.markdown', 'Default.rst', 'Default.txt',
    'Default_with_index', 'Default_with_index.html', 'Presentation', 'Presentation.html',
    'Print', 'Print.html', 'SlideShow_(S5)', 'SlideShow_(S5).html', 'ZeroFiveEight', 'ZeroFiveEight.html',
    'Article', 'Article.tex', 'Part', 'Part.tex', 'Report', 'Report.tex', 'Journal', 'Journal.txt',
}

AREA = {'type': 'string', 'enum': list(AREAS),
        'description': 'Exchange folder: inbox (uploads), outbox (files the product writes, for example exports) or notebook '
                       '(the folder of the wiki notebook the product opens).'}
OPERATIONS = runtime.check_operations({
    'help': {'kind': 'info', 'summary': 'This description of operations, fields and limits.', 'fields': {}},
    'status': {'kind': 'lifecycle', 'summary': 'Whether the product process is running and ready.', 'fields': {}},
    'reset': {'kind': 'lifecycle', 'fields': {},
              'summary': 'Start over: a new desktop session, empty inbox, outbox and notebook folders, and the product with '
                         'an empty data directory (its initial state).'},
    'restart': {'kind': 'lifecycle', 'fields': {},
                'summary': 'Start the product again with the same data directory, desktop session and exchange folders '
                           '(for example after quitting it through its own controls).'},
    **desktop.operations(SCREEN),
    'list_files': {'kind': 'files', 'summary': 'Files below an exchange folder (name relative to the folder, size, path); '
                   'hidden files and folders are not listed.',
                   'fields': {'area': dict(AREA, description=AREA['description'] + ' Default outbox.')}},
    'upload': {'kind': 'files', 'summary': 'Store one file in an exchange folder, creating its folders; an existing file of '
               'the same name is replaced. Uploaded files get the modification time 2024-01-01 00:00 UTC.',
               'fields': {'filename': {'type': 'string', 'required': True,
                                       'description': 'Name relative to the folder, for example Projects/Alpha.txt: at most '
                                                      f'{MAX_FOLDERS} folders, no hidden names, at most 600 bytes.'},
                          'base64': {'type': 'string', 'required': True,
                                     'description': f'File bytes, base64 encoded; at most {MAX_UPLOAD} bytes, empty files '
                                                    'allowed.'},
                          'area': dict(AREA, description=AREA['description'] + ' Default inbox.')}},
    'download': {'kind': 'files', 'summary': 'Retrieve one text, wiki, HTML, LaTeX, Markdown, reStructuredText, CSS, '
                 'JavaScript, SVG, CSV, PNG, JPEG or GIF file of an exchange folder as body_base64.',
                 'fields': {'filename': {'type': 'string', 'required': True,
                                         'description': 'Name relative to the folder, as listed by list_files.'},
                            'area': dict(AREA, description=AREA['description'] + ' Default outbox.')}},
    'clipboard_text': {'kind': 'observe', 'summary': 'The plain text on the desktop clipboard (UTF-8, at most '
                       f'{CLIPBOARD_TEXT} bytes).', 'fields': {}},
    'cli': {'kind': 'http',
            'summary': 'Run the command line of the product once, on files of the exchange folders, and return its exit '
                       'code and the text it printed. Commands: search (options -s, -w, -c, --sorted; arguments notebook '
                       'and query), export (options -o, --format, --template, -r, -s, -O, --root-url, --index-page; '
                       'arguments notebook and optional page), import (option --format, --assubpage; arguments notebook, '
                       'page and files), index (option -f; argument notebook), convert-notebook (options --format, '
                       '--extension; argument notebook) and version. File paths are absolute exchange paths or '
                       'relative to the inbox; the notebook folder is the one listed in the notes.',
            'fields': {'command': {'type': 'string', 'required': True, 'enum': sorted(CLI_COMMANDS),
                                   'description': 'Command of the product command line.'},
                       'args': {'type': 'array', 'items': {'type': 'string'},
                                'description': f'Options and arguments in command line order, at most {MAX_ARGS} items; '
                                               'default none.'}}},
})
LIMITS = {'upload_bytes': MAX_UPLOAD, 'download_bytes': MAX_DOWNLOAD, 'files_per_area': MAX_FILES,
          'folders_per_name': MAX_FOLDERS, 'cli_arguments': MAX_ARGS, 'cli_output_chars': MAX_OUTPUT,
          'cli_seconds': CLI_SECONDS, 'request_bytes': MAX_REQUEST, 'rpc_seconds': RPC_TIMEOUT, 'screen': list(SCREEN)}


def examples(areas):
    '''Request examples for help; the typed paths name this runtime own exchange folders.'''
    return [{'op': 'observe'}, {'op': 'screenshot'}, {'op': 'click', 'target': {'role': 'menu', 'name': 'File'}},
            {'op': 'press', 'key': 'Control+S'}, {'op': 'list_files', 'area': 'notebook'},
            {'op': 'download', 'area': 'notebook', 'filename': 'Home.txt'},
            {'op': 'upload', 'area': 'notebook', 'filename': 'Projects/Alpha.txt', 'base64': 'SGVsbG8='},
            {'op': 'cli', 'command': 'search', 'args': [str(areas['notebook']), 'alpha']}]


class Refused(ValueError):
    '''The request is outside the interface boundary.'''


def refused_here(title, name):
    '''Whether a control name starts another program in the window with this title.'''
    return any(title.startswith(prefix) and name in names for prefix, names in REFUSED_IN_WINDOW.items())


def plain(name):
    '''A control name without mnemonics, trailing dots and case, for comparisons.'''
    return (name or '').replace('_', '').strip().rstrip('.' + chr(8230) + ' ').casefold()


def safe_name(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 240:
        raise ValueError('names must be non-empty and at most 240 bytes')
    if value in ('.', '..') or '/' in value or chr(92) in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('names must be plain file or folder names')
    if value.startswith('.'):
        raise ValueError('hidden names are not accepted')
    return value


def relative_parts(value):
    if not isinstance(value, str) or not value or len(value.encode('utf-8')) > 600:
        raise ValueError('filename must be a relative path of at most 600 bytes')
    parts = value.split('/')
    if len(parts) > MAX_FOLDERS + 1:
        raise ValueError(f'filename may name at most {MAX_FOLDERS} folders')
    return [safe_name(part) for part in parts]


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
        self.areas = {name: self.files / name for name in AREAS}
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
        '''Whether a resolved absolute path lies in an unchanged exchange folder.'''
        if not os.path.isabs(value):
            return False
        path = os.path.realpath(value)
        return any(os.path.realpath(root) == str(root)
                   and (path == str(root) or path.startswith(str(root) + os.sep))
                   for root in self.areas.values())

    def private_text(self, value):
        '''Text with private filesystem locations replaced; exchange paths stay readable.'''
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
        return PATH_TEXT.sub(replace, text), changed

    def detail(self, exc):
        '''An error detail without private locations (exchange paths stay readable).'''
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
        self.product.extra = dict(self.session.env(), PBP_INBOX=str(self.areas['inbox']), PBP_OUTBOX=str(self.areas['outbox']),
                                  PBP_NOTEBOOK=str(self.areas['notebook']), LD_PRELOAD=FAKETIME_LIBRARY, FAKETIME=CLOCK,
                                  FAKETIME_DONT_FAKE_MONOTONIC='1', **GIT)

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

    def descend(self, root, parts, create):
        '''Descriptors of the folders below root named by parts (never following links); root stays the first one.'''
        handles = [root]
        try:
            for part in parts:
                try:
                    handle = open_directory(part, handles[-1])
                except ValueError:
                    if not create:
                        raise
                    try:
                        os.mkdir(part, 0o755, dir_fd=handles[-1])
                    except OSError:
                        raise ValueError(f'{part} is not a plain folder') from None
                    handle = open_directory(part, handles[-1])
                    self.chown(fd=handle)
                    os.fchmod(handle, 0o755)
                handles.append(handle)
        except BaseException:
            for handle in handles[1:]:
                os.close(handle)
            raise
        return handles

    def walk(self, fd, prefix, depth, found, folder):
        for name in sorted(os.listdir(fd)):
            if name.startswith('.') or len(found) >= MAX_FILES:
                continue
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                found.append({'name': prefix + name, 'size': info.st_size, 'path': str(folder / (prefix + name))})
            elif stat.S_ISDIR(info.st_mode) and depth < MAX_FOLDERS:
                try:
                    sub = open_directory(name, fd)
                except ValueError:
                    continue
                try:
                    self.walk(sub, prefix + name + '/', depth + 1, found, folder)
                finally:
                    os.close(sub)

    def list_files(self, data):
        name, folder = self.area(data, 'outbox')
        found = []
        try:
            root = open_directory(folder)
        except ValueError:
            return {'area': name, 'files': []}
        try:
            self.walk(root, '', 0, found, folder)
        finally:
            os.close(root)
        return {'area': name, 'files': found}

    def upload(self, data):
        parts = relative_parts(data['filename'])
        try:
            content = base64.b64decode(data['base64'], validate=True)
        except Exception:
            raise ValueError('base64 is invalid') from None
        if len(content) > MAX_UPLOAD:
            raise ValueError(f'uploaded files are limited to {MAX_UPLOAD} bytes')
        area, folder = self.area(data, 'inbox')
        relative = '/'.join(parts)
        listed = self.list_files({'area': area})['files']
        if len(listed) >= MAX_FILES and not any(f['name'] == relative for f in listed):
            raise ValueError(f'the {area} holds at most {MAX_FILES} files; use reset to empty the exchange folders')
        root = open_directory(folder)
        try:
            handles = self.descend(root, parts[:-1], True)
            try:
                directory, name = handles[-1], parts[-1]
                try:
                    info = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError('the destination must be one regular file')
                except FileNotFoundError:
                    pass
                runtime.atomic_write(directory, name, content, uid=self.account.pw_uid, gid=self.account.pw_gid, mode=0o644)
                with runtime.open_relative(directory, name) as descriptor:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError('the uploaded file changed during setup')
                    runtime.set_metadata(descriptor, ns=(UPLOAD_TIME * 1_000_000_000,) * 2)
            finally:
                for handle in handles[1:]:
                    os.close(handle)
        finally:
            os.close(root)
        return {'area': area, 'name': relative, 'path': str(folder / relative), 'size': len(content),
                'sha256': hashlib.sha256(content).hexdigest()}

    def download(self, data):
        parts = relative_parts(data['filename'])
        suffix = Path(parts[-1]).suffix.casefold()
        if suffix not in TEXT_TYPES and suffix not in IMAGE_TYPES:
            raise ValueError('downloads expose wiki, text, HTML, LaTeX, Markdown, reStructuredText, CSS, JavaScript, SVG, CSV '
                             'and PNG, JPEG or GIF image files only')
        area, folder = self.area(data, 'outbox')
        root = open_directory(folder)
        try:
            handles = self.descend(root, parts[:-1], False)
            try:
                try:
                    descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=handles[-1])
                except FileNotFoundError:
                    raise ValueError(f'{parts[-1]} is not in the {area}') from None
                except OSError:
                    raise ValueError(f'{parts[-1]} is not a regular file') from None
                try:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_DOWNLOAD:
                        raise ValueError(f'downloads are single regular files of at most {MAX_DOWNLOAD} bytes')
                    content = runtime.read_bounded(descriptor, limit=MAX_DOWNLOAD)
                finally:
                    os.close(descriptor)
            finally:
                for handle in handles[1:]:
                    os.close(handle)
        finally:
            os.close(root)
        if len(content) > MAX_DOWNLOAD:
            raise ValueError(f'downloads are limited to {MAX_DOWNLOAD} bytes')
        if suffix in IMAGE_TYPES and not content.startswith(IMAGE_TYPES[suffix]):
            raise ValueError('the file is not an image of its type')
        if suffix in TEXT_TYPES and bytes([0]) in content[:8192]:
            raise ValueError('the file is not text')
        return {'area': area, 'name': '/'.join(parts), 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                'body_base64': base64.b64encode(content).decode()}

    def clipboard_text(self):
        raw = self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT)
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError('the clipboard text is not UTF-8') from None
        return {'text': text, 'characters': len(text)}

    # Command line ---------------------------------------------------------------------------------------------
    def check_arg(self, token):
        '''Resolve a file argument against the command's inbox working directory.'''
        if not token or any(ord(c) < 32 or ord(c) == 127 for c in token):
            raise Refused('file arguments must be non-empty paths without control characters')
        if token.startswith('~') or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', token):
            raise Refused('file arguments must name files in the exchange folders, without home aliases or URLs')
        path = os.path.realpath(token if os.path.isabs(token) else self.areas['inbox'] / token)
        if not self.inside(path):
            raise Refused('file arguments must stay inside the exchange folders')
        return path

    def cli_argv(self, command, args):
        flags, valued, low, high = CLI_COMMANDS[command]
        if not isinstance(args, list) or len(args) > MAX_ARGS or not all(
                isinstance(a, str) and len(a) <= MAX_ARG and chr(0) not in a for a in args):
            raise ValueError(f'args must be a list of at most {MAX_ARGS} texts of at most {MAX_ARG} characters')
        argv = ['--version'] if command == 'version' else ['--' + command]
        positional, index = 0, 0
        while index < len(args):
            token = args[index]
            index += 1
            if token.startswith('-') and len(token) > 1:
                name, equals, value = token.partition('=') if token.startswith('--') else (token, '', '')
                if name in flags and not equals:
                    argv.append(token)
                elif name in valued:
                    if not equals:
                        if index >= len(args):
                            raise ValueError(f'option {name} needs a value')
                        value = args[index]
                        index += 1
                    if name in ('-o', '--output'):
                        value = self.check_arg(value)
                    elif name == '--template':
                        # Only installed template names are exempt from file-path resolution.
                        if value not in BUILTIN_TEMPLATES:
                            value = self.check_arg(value)
                    elif name == '--extension' and (
                            not re.fullmatch(r'\.?[A-Za-z0-9][A-Za-z0-9._-]*', value) or value in ('.', '..')):
                        raise Refused('the notebook extension must be a plain filename suffix')
                    argv.extend([name, value])
                else:
                    raise ValueError(f'unknown option {name} for {command}; see the cli description in help')
            else:
                # Notebook and imported-file positions are paths; page names and search queries are text.
                if positional == 0 or (command == 'import' and positional >= 2):
                    token = self.check_arg(token)
                argv.append(token)
                positional += 1
        if not low <= positional <= high:
            raise ValueError(f'{command} takes {low} to {high} arguments after its options, got {positional}')
        return argv

    def cli_environment(self, fixed_clock):
        '''Environment of one command line run: the product environment, without the fake clock when the command cannot run under it.'''
        env = dict(self.product.environment())
        if not fixed_clock:
            for name in ('LD_PRELOAD', 'FAKETIME', 'FAKETIME_DONT_FAKE_MONOTONIC'):
                env.pop(name, None)
        return env

    def run_cli(self, argv, fixed_clock=True):
        script = self.product.solution / 'start.sh'
        if not script.is_file():
            raise ValueError('start.sh does not exist in the solution directory')
        cwd = Path(self.config.work) / 'cli'
        with runtime.open_directory(self.config.work, create=True) as work:
            with runtime.owned_directory(work, 'cli', uid=self.account.pw_uid, gid=self.account.pw_gid, mode=0o700):
                pass
        kwargs = {}
        if self.switching:
            kwargs = dict(user=self.account.pw_uid, group=self.account.pw_gid, extra_groups=[])
        master, slave = pty.openpty()
        try:
            proc = subprocess.Popen([str(script), *argv], env=self.cli_environment(fixed_clock), cwd=str(cwd), stdin=slave,
                                    stdout=slave, stderr=slave, close_fds=True, start_new_session=True, **kwargs)
        except OSError as exc:
            os.close(master)
            os.close(slave)
            raise ValueError(f'start.sh could not be executed ({type(exc).__name__})') from None
        os.close(slave)
        chunks, size, truncated, timed_out = [], 0, False, False
        deadline = time.monotonic() + CLI_SECONDS
        try:
            while True:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                ready, _, _ = select.select([master], [], [], 0.5)
                if ready:
                    try:
                        chunk = os.read(master, 65536)
                    except OSError:
                        break
                    if not chunk:
                        break
                    if size < MAX_OUTPUT:
                        chunks.append(chunk[:MAX_OUTPUT - size])
                        size += len(chunks[-1])
                    else:
                        truncated = True
                elif proc.poll() is not None:
                    break
        finally:
            os.close(master)
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(proc.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    proc.wait(3)
                    break
                except subprocess.TimeoutExpired:
                    continue
        if timed_out:
            raise ValueError(f'the command did not finish within {CLI_SECONDS} s')
        text = b''.join(chunks).decode('utf-8', 'replace')
        return text.replace(chr(13) + chr(10), chr(10)).replace(chr(13), ''), proc.returncode, truncated

    def cli(self, data):
        command = data['command']
        argv = self.cli_argv(command, data.get('args', []))
        output, code, truncated = self.run_cli(argv, command != 'convert-notebook')
        return {'command': command, 'exit_code': code, 'output': self.private_text(output)[0], 'truncated': truncated}

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
        '''Private filesystem locations leave observations; in a tree the whole subtree of a redacted node goes. Returns
        the observation and the screen boxes of redacted nodes.'''
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
    def check_paths(self, value, urls=False):
        '''Text typed into a path field: absolute paths inside the exchange folders (links may also be plain URLs).'''
        if not isinstance(value, str) or not value.strip():
            return
        text = value.strip()
        if text.startswith('~') or text.casefold().startswith('file:'):
            raise Refused('paths must be absolute paths inside the exchange folders (no home folders or file URLs)')
        if '://' in text:
            if urls and not text.casefold().startswith('smb:'):
                return
            raise Refused('paths must be absolute paths inside the exchange folders (no URLs)')
        if '/' not in text:
            return
        try:
            parts = shlex.split(text) if chr(34) in text else [text]
        except ValueError:
            raise Refused('the text is not a valid path list') from None
        for part in parts:
            if '/' not in part:
                continue
            if urls and not part.startswith('/') and '..' not in Path(part).parts:
                continue
            if not part.startswith('/') or '..' in Path(part).parts or not self.inside(part):
                raise Refused('paths are confined to the exchange folders: use an absolute path under '
                              f'{self.files}')

    @staticmethod
    def lineage(nodes, node):
        '''The node and its ancestors in a tree observation.'''
        by_ref = {n['ref']: n for n in nodes}
        chain, seen = [node], {node['ref']}
        while chain[-1].get('parent') in by_ref and chain[-1]['parent'] not in seen:
            seen.add(chain[-1]['parent'])
            chain.append(by_ref[chain[-1]['parent']])
        return chain

    def crumbs(self, nodes):
        '''GTK path-bar folder buttons with their absolute folders, and the current folder (None when unknown).'''
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
        '''[role, name, description, bounds, states] chain (node first) of the control an input would reach.'''
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

    @staticmethod
    def point(data, node):
        if 'x' in data and 'y' in data:
            return data['x'], data['y']
        if node is not None and node.get('bounds'):
            x, y, w, h = node['bounds']
            return x + w / 2, y + h / 2
        return None

    @staticmethod
    def plugin_row(nodes, point):
        '''Whether a point lies on the row of a plugin that is not available (rows are matched by their name cell).'''
        if point is None:
            return False
        for node in nodes:
            if node['role'] == 'table cell' and plain(node.get('name')) in REFUSED_PLUGINS:
                _x, y, _w, h = node['bounds']
                if y <= point[1] <= y + h:
                    return True
        return False

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
        '''Refuse inputs that would start other programs, load code, open notebooks or manuals, or leave the exchange
        folders through a dialog.'''
        op = data['op']
        if op in ('wait', 'zoom', 'focus_window', 'maximize', 'move', 'scroll'):
            return
        view = self.ui.inspect()
        nodes = view['nodes']
        key = desktop.keysym(data['key']) if op == 'press' else None
        chain = self.target(data, view)
        node = chain[0] if chain else None
        active = [w for w in self.ui.windows() if w.get('active')]
        title = plain(active[0].get('title')) if active else ''
        menu_open = any(n['role'] in MENU_ITEMS for n in nodes)
        self.guard_entry_points(op, data, key, nodes, chain, node, title, menu_open)
        self.guard_paths(op, data, key, nodes, chain, title)

    def guard_entry_points(self, op, data, key, nodes, chain, node, title, menu_open):
        why = 'this control starts another program, opens a manual or a notebook, or reaches outside the exchange folders'
        if op in ('click', 'activate', 'check', 'drag') or (op == 'press' and data.get('target') is not None):
            for link in (chain or [])[:3]:
                name = plain(link.get('name'))
                role = link.get('role')
                if role in REFUSED_ROLES and (name in REFUSED_NAMES or name.startswith('open with') or refused_here(title, name)):
                    raise Refused(why)
                if role == 'page tab' and name in REFUSED_TABS:
                    raise Refused('this settings tab is not available')
            if title == 'preferences' and self.plugin_row(nodes, self.point(data, node)):
                raise Refused('this plugin is not available')
        if op == 'press':
            if key in REFUSED_KEYS:
                raise Refused('this key starts another program, opens a manual or a notebook, or reaches outside the '
                              'exchange folders')
            if key in CONFIRM_KEYS:
                for n in nodes:
                    states = set(n.get('states', ()))
                    name = plain(n.get('name'))
                    if n['role'] in MENU_ITEMS and states & {'focused', 'selected'} and (
                            name in REFUSED_NAMES or name.startswith('open with') or refused_here(title, name)):
                        raise Refused(why)
                    if n['role'] in ('push button', 'button', 'toggle button') and 'focused' in states and (
                            name in REFUSED_NAMES or refused_here(title, name)):
                        raise Refused(why)
                    if title == 'preferences' and n['role'] == 'table cell' and name in REFUSED_PLUGINS \
                            and 'selected' in states:
                        raise Refused('this plugin is not available')
            if menu_open and key not in MENU_KEYS:
                raise Refused('while a menu is open only movement keys, Return, space and Escape are available')
        if op == 'type' and menu_open:
            raise Refused('text cannot be typed while a menu is open')
        tab = [n for n in nodes if n['role'] == 'page tab' and plain(n.get('name')) in REFUSED_TABS
               and set(n.get('states', ())) & {'selected', 'checked', 'active'}]
        if tab:
            roles = [link.get('role') for link in (chain or [])[:3]]
            names = [plain(link.get('name')) for link in (chain or [])[:3]]
            allowed = (op in ('click', 'activate') and ('page tab' in roles or 'cancel' in names)) or (
                op == 'press' and key == 'Escape')
            if not allowed:
                raise Refused('this settings tab is not available: choose another tab or cancel')

    def guard_paths(self, op, data, key, nodes, chain, title):
        chooser = any(n['role'] == 'file chooser' for n in nodes)
        if not chooser and title not in PATH_DIALOGS:
            return
        urls = title in ('edit link', 'insert link')
        if op in ('type', 'fill'):
            self.check_paths(data.get('value'), urls)
        if op == 'press' and chooser and key not in CHOOSER_KEYS:
            raise Refused('in a file dialog only movement, editing, Return, Escape and Ctrl+L keys are available')
        if op == 'press' and key in PASTE_KEYS:
            try:
                self.check_paths(self.ui.clipboard('UTF8_STRING', CLIPBOARD_TEXT).decode('utf-8', 'replace'), urls)
            except desktop.DesktopError:
                pass
        crumbs, current = self.crumbs(nodes)
        inside_current = current is not None and self.inside(current)
        target = chain[0] if chain else None
        in_chooser = bool(chain) and any(link['role'] == 'file chooser' for link in chain)
        names = [link.get('name') for link in chain or ()]
        if chooser and in_chooser and op in ('click', 'activate', 'check', 'drag'):
            if 'Places' in names and target['role'] != 'scroll pane':
                place = next((link.get('description') for link in chain if link.get('description')), '') or ''
                if not (place.startswith('/') and self.inside(place)):
                    raise Refused('places outside the exchange folders are not available in file dialogs; type an '
                                  'absolute path inside them')
            if target['role'] == 'toggle button' and 'PathBar Layer' in names:
                path = next((p for bounds, p in crumbs if bounds == target.get('bounds')), None)
                if path is None or not self.inside(path):
                    raise Refused('folders outside the exchange folders are not available in file dialogs')
            in_list = 'Files' in names and 'Places' not in names
            if in_list and not inside_current and (op == 'activate' or data.get('click_count', 1) > 1):
                raise Refused('this folder is outside the exchange folders; type an absolute path inside them')
        confirming = (op == 'press' and key in ('Return', 'KP_Enter', 'space')) or (
            op in ('click', 'activate') and target is not None and (
                (target['role'] in ('push button', 'button') and plain(target.get('name')) in AFFIRMATIVE)
                or (in_chooser and data.get('click_count', 1) > 1)))
        if confirming:
            typed = [n.get('text') or '' for n in nodes if n['role'] in ('text', 'entry')
                     and 'editable' in n.get('states', ()) and '/' in (n.get('text') or '')
                     and any(a['role'] in ('file chooser', 'dialog') for a in self.lineage(nodes, n))]
            for value in typed:
                if value.strip() not in IGNORED_DEFAULTS:
                    self.check_paths(value, urls)
            if chooser and not typed and not inside_current:
                raise Refused('file dialogs confirm only inside the exchange folders: type an absolute path such as '
                              f'{self.areas["outbox"]}/name.txt')

    # Dispatch -------------------------------------------------------------------------------------------------
    def dispatch(self, data):
        op = runtime.validate(OPERATIONS, data)
        if op == 'help':
            return runtime.help_document(PRODUCT, 'desktop', OPERATIONS, limits=LIMITS, notes=self.notes(),
                                         examples=examples(self.areas))
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
            if op == 'cli':
                return self.cli(data)
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
            self.guard(data)
            return self.ui.act(data)

    def notes(self):
        return [f'Exchange folders: inbox {self.areas["inbox"]} (uploads), outbox {self.areas["outbox"]} (files the product '
                f'writes, for example exports) and notebook {self.areas["notebook"]} (the folder of the wiki notebook the '
                'product opens at start). The product sees them as ordinary folders; its pages are plain text files in '
                'the notebook folder.',
                'upload, list_files and download name files relative to a folder (for example Projects/Alpha.txt in the '
                'notebook folder); hidden names are refused, and downloads cover text, wiki, HTML, LaTeX, Markdown, '
                'reStructuredText, CSS, JavaScript, SVG, CSV and image files only.',
                'cli runs the command line of the product once on files of the exchange folders (search, export, import, '
                'index, convert-notebook, version) and returns its exit code and printed text.',
                f'The wall clock of the product stays at {CLOCK} UTC (the convert-notebook command of cli runs with the real clock).',
                'File dialogs must be standard file choosers that expose the accessible role file chooser; inside them '
                'documents are named by typed absolute paths in the exchange folders (Ctrl+L opens the location field of an '
                'Open dialog; the name field of a Save dialog accepts a full path), places and path-bar folders elsewhere '
                'are refused, and a dialog confirms only inside the exchange folders. Text fields that take paths in other '
                'dialogs are checked the same way.',
                'Menu items, buttons, tabs and keys that start other programs, load code, open manuals or other notebooks, '
                'or reach outside the exchange folders are refused with a reason.',
                'GUI operations answer briefly; observe and screenshot show the new state. Refs stay valid until the next '
                'observe; object targets are matched against a fresh snapshot.',
                'Product errors and dialogs are observations; a refused request answers 400 with the reason.',
                'reset starts a new desktop session (clipboard and windows cleared) with empty exchange folders; restart '
                'keeps the data directory, the session and the exchange folders.']


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
